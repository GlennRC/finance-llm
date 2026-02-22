"""MCP server — exposes fin tools to ChatGPT.

Supports two transports:
  - stdio: ChatGPT desktop app (local)
  - streamable-http: ChatGPT web via remote HTTPS (/mcp endpoint)
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from finance_llm.lib.fin_commands import FinCommands

mcp = FastMCP(
    "finance-llm",
    instructions=(
        "Personal finance MCP server. Query balances, transactions, trends, "
        "merchants, net worth, income, anomalies, and account lists via hledger."
    ),
)


def _get_fin() -> FinCommands:
    """Get FinCommands instance from FINANCE_ROOT env var."""
    root = Path(os.environ.get("FINANCE_ROOT", "."))
    journal = root / "journal" / "main.journal"
    return FinCommands(journal)


@mcp.tool()
def fin_balance(
    period: str | None = None,
    account: str = "expenses",
) -> str:
    """Get account balances for a time period. Shows spending breakdown by category.
    Example: 'What did I spend in February?'"""
    r = _get_fin().balance(period=period, account=account)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_register(
    query: str = "",
    period: str | None = None,
    payee: str | None = None,
) -> str:
    """Get transaction register with optional filters. Shows individual transactions.
    Example: 'Show me all Amazon purchases'"""
    r = _get_fin().register(query=query, period=period, payee=payee)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_trend(
    account: str = "expenses",
    months: int = 6,
) -> str:
    """Show monthly spending trend for a category.
    Example: 'How has my grocery spending trended over 6 months?'"""
    r = _get_fin().trend(account=account, months=months)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_merchants(period: str | None = None) -> str:
    """Show top merchants/payees by total spend.
    Example: 'Who are my top 10 merchants this month?'"""
    r = _get_fin().merchants(period=period)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_networth() -> str:
    """Show current net worth (assets minus liabilities).
    Example: 'What is my net worth?'"""
    r = _get_fin().networth()
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_income(period: str | None = None) -> str:
    """Show income statement (income vs expenses).
    Example: 'What was my income vs expenses last month?'"""
    r = _get_fin().income(period=period)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_anomalies(
    period: str | None = None,
    threshold: float = 100,
) -> str:
    """Find unusually large transactions above a threshold.
    Example: 'Any unusual charges this month?'"""
    r = _get_fin().anomalies(period=period, threshold=threshold)
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_stats() -> str:
    """Show journal statistics (date range, transaction count, accounts)."""
    r = _get_fin().stats()
    return r.output if r.success else f"Error: {r.error}"


@mcp.tool()
def fin_accounts() -> str:
    """List all accounts in the journal."""
    r = _get_fin().accounts()
    return r.output if r.success else f"Error: {r.error}"
