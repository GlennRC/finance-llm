"""MCP server — exposes fin tools to ChatGPT desktop app.

Implements the Model Context Protocol (MCP) over stdio transport.
ChatGPT calls tools like fin_balance("2026-02") during conversation.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from finance_llm.lib.fin_commands import FinCommands

# Server instance
server = Server("finance-llm")


def get_fin() -> FinCommands:
    """Get FinCommands instance from FINANCE_ROOT env var."""
    root = Path(os.environ.get("FINANCE_ROOT", "."))
    journal = root / "journal" / "main.journal"
    return FinCommands(journal)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Register all available finance tools."""
    return [
        Tool(
            name="fin_balance",
            description=(
                "Get account balances for a time period. "
                "Shows spending breakdown by category. "
                "Example: 'What did I spend in February?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period (e.g., '2026-02', 'last month', 'this quarter')",
                    },
                    "account": {
                        "type": "string",
                        "description": "Account filter (default: expenses)",
                        "default": "expenses",
                    },
                },
            },
        ),
        Tool(
            name="fin_register",
            description=(
                "Get transaction register with optional filters. "
                "Shows individual transactions. "
                "Example: 'Show me all Amazon purchases'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (account name, payee, etc.)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period filter",
                    },
                    "payee": {
                        "type": "string",
                        "description": "Filter by payee name",
                    },
                },
            },
        ),
        Tool(
            name="fin_trend",
            description=(
                "Show monthly spending trend for a category. "
                "Example: 'How has my grocery spending trended over 6 months?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account": {
                        "type": "string",
                        "description": "Account/category to trend (default: expenses)",
                        "default": "expenses",
                    },
                    "months": {
                        "type": "integer",
                        "description": "Number of months to show (default: 6, max: 24)",
                        "default": 6,
                    },
                },
            },
        ),
        Tool(
            name="fin_merchants",
            description=(
                "Show top merchants/payees by total spend. "
                "Example: 'Who are my top 10 merchants this month?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period filter",
                    },
                },
            },
        ),
        Tool(
            name="fin_networth",
            description=(
                "Show current net worth (assets minus liabilities). "
                "Example: 'What is my net worth?'"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="fin_income",
            description=(
                "Show income statement (income vs expenses). "
                "Example: 'What was my income vs expenses last month?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period filter",
                    },
                },
            },
        ),
        Tool(
            name="fin_anomalies",
            description=(
                "Find unusually large transactions above a threshold. "
                "Example: 'Any unusual charges this month?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period filter",
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Amount threshold (default: 100)",
                        "default": 100,
                    },
                },
            },
        ),
        Tool(
            name="fin_stats",
            description="Show journal statistics (date range, transaction count, accounts).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="fin_accounts",
            description="List all accounts in the journal.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route MCP tool calls to fin commands."""
    fin = get_fin()

    handlers = {
        "fin_balance": lambda: fin.balance(
            period=arguments.get("period"),
            account=arguments.get("account", "expenses"),
        ),
        "fin_register": lambda: fin.register(
            query=arguments.get("query", ""),
            period=arguments.get("period"),
            payee=arguments.get("payee"),
        ),
        "fin_trend": lambda: fin.trend(
            account=arguments.get("account", "expenses"),
            months=arguments.get("months", 6),
        ),
        "fin_merchants": lambda: fin.merchants(period=arguments.get("period")),
        "fin_networth": lambda: fin.networth(),
        "fin_income": lambda: fin.income(period=arguments.get("period")),
        "fin_anomalies": lambda: fin.anomalies(
            period=arguments.get("period"),
            threshold=arguments.get("threshold", 100),
        ),
        "fin_stats": lambda: fin.stats(),
        "fin_accounts": lambda: fin.accounts(),
    }

    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    result = handler()
    if result.success:
        return [TextContent(type="text", text=result.output or "(no output)")]
    else:
        return [TextContent(type="text", text=f"Error: {result.error}")]


async def run_server() -> None:
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
