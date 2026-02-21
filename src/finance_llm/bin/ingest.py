"""bin/ingest — Import pipeline orchestrator.

Imports bank CSV files into the staging journal. Supports both
manual CSV file input and (future) email-based ingestion.
"""

from __future__ import annotations

import shutil
from hashlib import sha256
from pathlib import Path

import click

from finance_llm.lib.csv_normalizer import CSVProfile, normalize_csv, write_canonical
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


@click.command()
@click.option("--file", "-f", "csv_file", type=click.Path(exists=True), help="CSV file to import")
@click.option("--profile", "-p", required=True, help="CSV profile name (e.g., chase, amex)")
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory")
def main(csv_file: str | None, profile: str, root: str | None) -> None:
    """Import bank CSV into staging journal."""
    project_root = Path(root) if root else get_project_root()

    # Load CSV profile
    profile_path = project_root / "import" / "rules" / "csv_profiles" / f"{profile}.yaml"
    if not profile_path.exists():
        click.echo(f"Error: Profile not found: {profile_path}", err=True)
        raise SystemExit(1)
    csv_profile = CSVProfile.load(profile_path)

    if csv_file is None:
        click.echo("Error: --file is required (email mode not yet implemented)", err=True)
        raise SystemExit(1)

    csv_path = Path(csv_file)
    click.echo(f"Importing {csv_path.name} with profile '{profile}'...")

    # Archive raw CSV
    file_hash = sha256(csv_path.read_bytes()).hexdigest()[:16]
    from datetime import datetime

    month_dir = datetime.now().strftime("%Y-%m")
    raw_dir = project_root / "import" / "raw" / profile / month_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / f"sha256_{file_hash}.csv"
    if not archive_path.exists():
        shutil.copy2(csv_path, archive_path)
        click.echo(f"  Archived to {archive_path.relative_to(project_root)}")

    # Normalize CSV to canonical format
    transactions = normalize_csv(csv_path, csv_profile)
    click.echo(f"  Parsed {len(transactions)} transactions")

    if not transactions:
        click.echo("  No transactions found.")
        return

    # Write canonical JSONL
    canonical_dir = project_root / "import" / "canonical" / month_dir
    canonical_path = canonical_dir / f"{profile}.jsonl"
    write_canonical(transactions, canonical_path)
    click.echo(f"  Wrote canonical JSONL to {canonical_path.relative_to(project_root)}")

    # Load rules and state
    rules = RuleEngine(project_root / "import" / "rules")
    state_path = project_root / "import" / "state" / "seen_transactions.sqlite"
    with SeenTransactions(state_path) as seen:
        # Write to staging journals
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
