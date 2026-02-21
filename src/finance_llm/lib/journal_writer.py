"""Journal writer — converts canonical JSONL transactions to hledger journal entries.

Applies rules, deduplicates, and writes to staging directory.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .csv_normalizer import CanonicalTransaction
from .fingerprint import fingerprint
from .rules import RuleEngine
from .state import SeenTransactions


def format_journal_entry(
    date: str,
    payee: str,
    expense_account: str,
    source_account: str,
    amount: str,
    fp: str,
) -> str:
    """Format a single hledger journal entry.

    Returns a string like:
        2026-02-15 Trader Joe's  ; fingerprint:abc123
            Expenses:Groceries    $42.50
            Liabilities:CreditCard:Chase
    """
    lines = [
        f"{date} {payee}  ; fingerprint:{fp}",
        f"    {expense_account}    ${amount}",
        f"    {source_account}",
        "",
    ]
    return "\n".join(lines)


def write_staging_journals(
    transactions: list[CanonicalTransaction],
    rules: RuleEngine,
    seen: SeenTransactions,
    staging_dir: Path,
) -> dict[str, int]:
    """Write canonical transactions to staging journal files.

    Groups transactions by institution and month. Deduplicates using
    fingerprints. Returns stats: {institution: count_written}.

    Args:
        transactions: Canonical transactions to write
        rules: Rule engine for payee/account matching
        seen: Transaction dedup state
        staging_dir: Directory for staging journal files

    Returns:
        Dict mapping institution to number of new transactions written
    """
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Group by institution + month
    grouped: dict[str, list[str]] = defaultdict(list)
    stats: dict[str, int] = defaultdict(int)

    for txn in transactions:
        fp = fingerprint(
            account=txn.account,
            date=txn.date,
            amount=txn.amount,
            payee=txn.payee,
            source_id=txn.source_id,
        )

        if seen.is_seen(fp):
            continue

        clean_payee, expense_account = rules.apply(txn.payee)

        entry = format_journal_entry(
            date=txn.date,
            payee=clean_payee,
            expense_account=expense_account,
            source_account=txn.account,
            amount=txn.amount,
            fp=fp,
        )

        # Parse month for grouping
        try:
            dt = datetime.strptime(txn.date, "%Y-%m-%d")
            month_key = dt.strftime("%Y-%m")
        except ValueError:
            month_key = "unknown"

        file_key = f"{txn.institution}_{month_key}"
        grouped[file_key].append(entry)
        seen.mark_seen(fp, txn.institution)
        stats[txn.institution] = stats.get(txn.institution, 0) + 1

    # Write grouped entries to staging files
    for file_key, entries in grouped.items():
        staging_file = staging_dir / f"{file_key}.journal"
        with open(staging_file, "a") as f:
            for entry in entries:
                f.write(entry + "\n")

    return dict(stats)
