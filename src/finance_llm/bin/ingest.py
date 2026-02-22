"""bin/ingest — Import pipeline orchestrator.

Imports bank transactions into the staging journal. Supports:
- Manual CSV file import (--file + --profile)
- SimpleFIN API pull (--source simplefin)
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import click

from finance_llm.lib.csv_normalizer import (
    CSVProfile,
    CanonicalTransaction,
    normalize_csv,
    write_canonical,
)
from finance_llm.lib.journal_writer import write_staging_journals
from finance_llm.lib.rules import RuleEngine
from finance_llm.lib.state import SeenTransactions


def get_project_root() -> Path:
    """Find the project root by looking for journal/main.journal."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "journal" / "main.journal").exists():
            return parent
    return cwd


def ingest_csv(project_root: Path, csv_file: str, profile: str) -> list[CanonicalTransaction]:
    """Import from a local CSV file."""
    profile_path = project_root / "import" / "rules" / "csv_profiles" / f"{profile}.yaml"
    if not profile_path.exists():
        click.echo(f"Error: Profile not found: {profile_path}", err=True)
        raise SystemExit(1)
    csv_profile = CSVProfile.load(profile_path)

    csv_path = Path(csv_file)
    click.echo(f"Importing {csv_path.name} with profile '{profile}'...")

    # Archive raw CSV
    file_hash = sha256(csv_path.read_bytes()).hexdigest()[:16]
    month_dir = datetime.now().strftime("%Y-%m")
    raw_dir = project_root / "import" / "raw" / profile / month_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / f"sha256_{file_hash}.csv"
    if not archive_path.exists():
        shutil.copy2(csv_path, archive_path)
        click.echo(f"  Archived to {archive_path.relative_to(project_root)}")

    transactions = normalize_csv(csv_path, csv_profile)
    click.echo(f"  Parsed {len(transactions)} transactions")

    # Write canonical JSONL
    if transactions:
        canonical_dir = project_root / "import" / "canonical" / month_dir
        canonical_path = canonical_dir / f"{profile}.jsonl"
        write_canonical(transactions, canonical_path)
        click.echo(f"  Wrote canonical JSONL to {canonical_path.relative_to(project_root)}")

    return transactions


def ingest_simplefin(project_root: Path, days: int) -> list[CanonicalTransaction]:
    """Pull transactions from SimpleFIN API.

    SimpleFIN allows max 60-day windows per request. For longer ranges,
    we chunk into 60-day windows automatically.
    """
    from finance_llm.lib.simplefin_client import SimpleFINClient, load_access_url

    state_dir = project_root / "import" / "state"
    access_url = load_access_url(state_dir)
    if not access_url:
        click.echo(
            "Error: SimpleFIN not configured. Run 'fin setup-simplefin' first.", err=True
        )
        raise SystemExit(1)

    client = SimpleFINClient(access_url)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    # Chunk into 60-day windows (SimpleFIN API constraint)
    chunk_size = 60
    windows = []
    window_end = end_date
    while window_end > start_date:
        window_start = max(start_date, window_end - timedelta(days=chunk_size))
        windows.append((window_start, window_end))
        window_end = window_start

    click.echo(f"Fetching transactions from SimpleFIN ({days} days, {len(windows)} request(s))...")
    accounts_by_id: dict[str, object] = {}
    for i, (w_start, w_end) in enumerate(windows, 1):
        if len(windows) > 1:
            click.echo(f"  Request {i}/{len(windows)}: {w_start.strftime('%Y-%m-%d')} → {w_end.strftime('%Y-%m-%d')}")
        chunk_accounts = client.get_accounts(start_date=w_start, end_date=w_end)
        for acct in chunk_accounts:
            if acct.id in accounts_by_id:
                # Merge transactions, dedup by transaction ID
                existing = accounts_by_id[acct.id]
                seen_ids = {t.id for t in existing.transactions}
                for txn in acct.transactions:
                    if txn.id not in seen_ids:
                        existing.transactions.append(txn)
                        seen_ids.add(txn.id)
            else:
                accounts_by_id[acct.id] = acct

    accounts = list(accounts_by_id.values())

    all_transactions: list[CanonicalTransaction] = []
    for acct in accounts:
        institution = acct.institution
        click.echo(f"  {acct.name} ({institution}): {len(acct.transactions)} transactions")

        # Map default account based on account name/type
        default_account = _map_account(acct.name, institution)

        for txn in acct.transactions:
            if txn.pending:
                continue  # Skip pending transactions

            canonical = CanonicalTransaction(
                date=txn.date,
                amount=txn.amount,
                payee=txn.description,
                memo="",
                account=default_account,
                source_id=txn.id,
                institution=institution,
            )
            all_transactions.append(canonical)

    click.echo(f"  Total: {len(all_transactions)} transactions from {len(accounts)} accounts")
    return all_transactions


_INSTITUTION_DISPLAY = {
    "firsttech": "FirstTech",
    "citi": "Citi",
    "chase": "Chase",
    "amex": "Amex",
    "discover": "Discover",
    "wellsfargo": "WellsFargo",
}


def _map_account(account_name: str, institution: str) -> str:
    """Map a SimpleFIN account name to an hledger account."""
    display = _INSTITUTION_DISPLAY.get(institution, institution.title())
    name_lower = account_name.lower()
    if any(kw in name_lower for kw in ["checking", "share draft"]):
        return f"Assets:Checking:{display}"
    elif any(kw in name_lower for kw in ["saving", "money market"]):
        return f"Assets:Savings:{display}"
    elif any(kw in name_lower for kw in ["credit", "card"]):
        return f"Liabilities:CreditCard:{display}"
    elif any(kw in name_lower for kw in ["loan", "mortgage", "auto"]):
        return f"Liabilities:Loan:{display}"
    else:
        return f"Assets:Other:{display}"


@click.command()
@click.option("--file", "-f", "csv_file", type=click.Path(exists=True), help="CSV file to import")
@click.option("--profile", "-p", default=None, help="CSV profile name (e.g., chase, amex)")
@click.option("--source", "-s", type=click.Choice(["csv", "simplefin"]), default="csv",
              help="Data source")
@click.option("--days", "-d", default=30, help="Days of history to fetch; >60 auto-chunks (SimpleFIN only)")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory")
def main(
    csv_file: str | None, profile: str | None, source: str, days: int, root: str | None
) -> None:
    """Import bank transactions into staging journal."""
    project_root = Path(root) if root else get_project_root()

    if source == "simplefin":
        transactions = ingest_simplefin(project_root, days)
    else:
        if csv_file is None or profile is None:
            click.echo("Error: --file and --profile required for CSV import", err=True)
            raise SystemExit(1)
        transactions = ingest_csv(project_root, csv_file, profile)

    if not transactions:
        click.echo("  No transactions found.")
        return

    # Load rules and state, write to staging
    rules = RuleEngine(project_root / "import" / "rules")
    state_path = project_root / "import" / "state" / "seen_transactions.sqlite"
    with SeenTransactions(state_path) as seen:
        staging_dir = project_root / "journal" / "staging"
        stats = write_staging_journals(transactions, rules, seen, staging_dir)

    if stats:
        total = sum(stats.values())
        click.echo(f"  Wrote {total} new transactions to staging/")
        for inst, count in stats.items():
            click.echo(f"    {inst}: {count}")
    else:
        click.echo("  No new transactions (all duplicates)")

    click.echo("Done. Run 'fin-review' to review staged transactions.")


if __name__ == "__main__":
    main()
