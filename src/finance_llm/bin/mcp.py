"""bin/mcp — MCP server entry point for ChatGPT desktop app.

Start with: fin-mcp
Or configure in ChatGPT: python -m finance_llm.bin.mcp
"""

from __future__ import annotations

import asyncio

import click


@click.command()
def main() -> None:
    """Start the finance MCP server (stdio transport)."""
    from finance_llm.lib.mcp_server import run_server

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
