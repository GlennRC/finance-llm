"""bin/fin — Controlled hledger CLI wrapper.

Safe entrypoint for querying hledger journals. Used directly by humans
and internally by the MCP server. Hardcoded command allowlist.
"""

from __future__ import annotations

from pathlib import Path

import click

from finance_llm.lib.fin_commands import FinCommands


def get_project_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "journal" / "main.journal").exists():
            return parent
    return cwd


def get_fin(root: str | None = None) -> FinCommands:
    project_root = Path(root) if root else get_project_root()
    journal = project_root / "journal" / "main.journal"
    return FinCommands(journal)


@click.group()
def main() -> None:
    """fin — safe hledger query tool for your finances."""
    pass


@main.command()
@click.argument("period", required=False)
@click.option("--account", "-a", default="expenses", help="Account to query")
@click.option("--root", default=None)
def balance(period: str | None, account: str, root: str | None) -> None:
    """Show account balances for a period."""
    result = get_fin(root).balance(period=period, account=account)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.argument("query", required=False, default="")
@click.option("--period", "-p", default=None)
@click.option("--payee", default=None)
@click.option("--root", default=None)
def register(query: str, period: str | None, payee: str | None, root: str | None) -> None:
    """Show transaction register."""
    result = get_fin(root).register(query=query, period=period, payee=payee)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.argument("account", default="expenses")
@click.option("--months", "-m", default=6)
@click.option("--root", default=None)
def trend(account: str, months: int, root: str | None) -> None:
    """Show monthly spending trend."""
    result = get_fin(root).trend(account=account, months=months)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.argument("period", required=False)
@click.option("--root", default=None)
def merchants(period: str | None, root: str | None) -> None:
    """Show top merchants by spend."""
    result = get_fin(root).merchants(period=period)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.option("--root", default=None)
def networth(root: str | None) -> None:
    """Show current net worth."""
    result = get_fin(root).networth()
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.argument("period", required=False)
@click.option("--root", default=None)
def income(period: str | None, root: str | None) -> None:
    """Show income statement."""
    result = get_fin(root).income(period=period)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.argument("period", required=False)
@click.option("--threshold", "-t", default=100.0, help="Amount threshold")
@click.option("--root", default=None)
def anomalies(period: str | None, threshold: float, root: str | None) -> None:
    """Find unusually large transactions."""
    result = get_fin(root).anomalies(period=period, threshold=threshold)
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


@main.command()
@click.option("--root", default=None)
def stats(root: str | None) -> None:
    """Show journal statistics."""
    result = get_fin(root).stats()
    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}", err=True)


if __name__ == "__main__":
    main()
