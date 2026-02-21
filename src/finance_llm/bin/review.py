"""bin/review — Review staged transactions before posting.

Shows uncategorized transactions, new payees, and allows inline
categorization updates.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from finance_llm.lib.rules import RuleEngine

console = Console()


def get_project_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "journal" / "main.journal").exists():
            return parent
    return cwd


def parse_staging_entries(staging_dir: Path) -> list[dict]:
    """Parse journal entries from staging files into structured dicts."""
    entries = []
    if not staging_dir.exists():
        return entries

    for jfile in sorted(staging_dir.glob("*.journal")):
        with open(jfile) as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            # Transaction header: "2026-02-15 Payee Name  ; fingerprint:abc123"
            match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(.+?)(?:\s{2,};\s*fingerprint:(\S+))?$", line)
            if match:
                date, payee, fp = match.groups()
                expense_account = ""
                source_account = ""
                amount = ""

                # Read posting lines
                i += 1
                while i < len(lines) and lines[i].startswith("    "):
                    posting = lines[i].strip()
                    if posting.startswith("$") or "    $" in lines[i]:
                        parts = posting.rsplit("$", 1)
                        expense_account = parts[0].strip()
                        amount = parts[1].strip() if len(parts) > 1 else ""
                    elif expense_account and not source_account:
                        source_account = posting
                    i += 1

                entries.append({
                    "date": date,
                    "payee": payee,
                    "expense_account": expense_account,
                    "source_account": source_account,
                    "amount": amount,
                    "fingerprint": fp or "",
                    "file": jfile.name,
                })
            else:
                i += 1

    return entries


@click.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory")
@click.option("--uncategorized", "-u", is_flag=True, help="Show only uncategorized transactions")
def main(root: str | None, uncategorized: bool) -> None:
    """Review staged transactions before posting."""
    project_root = Path(root) if root else get_project_root()
    staging_dir = project_root / "journal" / "staging"

    entries = parse_staging_entries(staging_dir)
    if not entries:
        console.print("[green]No staged transactions to review.[/green]")
        return

    if uncategorized:
        entries = [e for e in entries if e["expense_account"] == "Expenses:Uncategorized"]

    # Summary
    total = len(entries)
    uncat = sum(1 for e in entries if e["expense_account"] == "Expenses:Uncategorized")
    console.print(f"\n[bold]Staged transactions:[/bold] {total}")
    console.print(f"[yellow]Uncategorized:[/yellow] {uncat}\n")

    # Table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Date", width=12)
    table.add_column("Payee", width=30)
    table.add_column("Amount", width=12, justify="right")
    table.add_column("Account", width=30)
    table.add_column("File", width=20)

    for entry in entries:
        style = "yellow" if entry["expense_account"] == "Expenses:Uncategorized" else ""
        table.add_row(
            entry["date"],
            entry["payee"],
            f"${entry['amount']}",
            entry["expense_account"],
            entry["file"],
            style=style,
        )

    console.print(table)

    if uncat > 0:
        console.print(
            f"\n[yellow]{uncat} uncategorized transactions.[/yellow] "
            "Add rules to import/rules/payees.yaml and accounts.yaml, then re-ingest."
        )

    console.print("\nRun [bold]fin-post[/bold] to finalize staged transactions into the journal.")


if __name__ == "__main__":
    main()
