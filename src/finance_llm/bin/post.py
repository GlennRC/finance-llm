"""bin/post — Finalize staged transactions into the journal.

Moves staging journal files into journal/postings/YYYY/YYYY-MM/
and updates main.journal with include directives.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click


def get_project_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "journal" / "main.journal").exists():
            return parent
    return cwd


def extract_months_from_journal(journal_path: Path) -> set[str]:
    """Extract YYYY-MM month keys from a staging journal file."""
    months = set()
    with open(journal_path) as f:
        for line in f:
            match = re.match(r"^(\d{4})-(\d{2})-\d{2}\s", line)
            if match:
                months.add(f"{match.group(1)}-{match.group(2)}")
    return months


def get_institution_from_filename(filename: str) -> str:
    """Extract institution name from staging filename like 'chase_2026-02.journal'."""
    return filename.split("_")[0] if "_" in filename else filename.replace(".journal", "")


def update_main_journal(main_journal: Path, postings_dir: Path) -> None:
    """Regenerate include directives in main.journal."""
    # Collect all posted journal files
    journal_files = sorted(postings_dir.rglob("*.journal"))
    if not journal_files:
        return

    includes = []
    for jf in journal_files:
        rel = jf.relative_to(main_journal.parent)
        includes.append(f"include {rel}")

    content = "; Main hledger journal — auto-generated includes\n"
    content += "; DO NOT edit directly — use bin/post to add transactions\n\n"
    content += "\n".join(includes) + "\n"

    main_journal.write_text(content)


@click.command()
@click.option("--root", type=click.Path(exists=True), default=None, help="Project root directory")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def main(root: str | None, dry_run: bool) -> None:
    """Finalize staged transactions into the journal."""
    project_root = Path(root) if root else get_project_root()
    staging_dir = project_root / "journal" / "staging"
    postings_dir = project_root / "journal" / "postings"
    main_journal = project_root / "journal" / "main.journal"

    if not staging_dir.exists() or not list(staging_dir.glob("*.journal")):
        click.echo("No staged transactions to post.")
        return

    staged_files = sorted(staging_dir.glob("*.journal"))
    click.echo(f"Found {len(staged_files)} staging file(s):")

    for sf in staged_files:
        institution = get_institution_from_filename(sf.name)
        months = extract_months_from_journal(sf)

        for month in sorted(months):
            year = month.split("-")[0]
            dest_dir = postings_dir / year / month
            dest_file = dest_dir / f"{institution}.journal"

            click.echo(f"  {sf.name} → {dest_file.relative_to(project_root)}")

            if dry_run:
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)

            # Append to destination (may already have entries from previous posts)
            with open(sf) as src, open(dest_file, "a") as dst:
                dst.write(src.read())

    if not dry_run:
        # Remove staged files
        for sf in staged_files:
            sf.unlink()
        click.echo(f"\nRemoved {len(staged_files)} staging file(s).")

        # Update main.journal includes
        update_main_journal(main_journal, postings_dir)
        click.echo("Updated main.journal includes.")
        click.echo("\nDone. Transactions are now live in hledger.")
    else:
        click.echo("\n[dry-run] No changes made.")


if __name__ == "__main__":
    main()
