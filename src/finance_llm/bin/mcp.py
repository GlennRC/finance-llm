"""bin/mcp — MCP server entry point.

Supports two transports:
  fin-mcp                       → stdio  (ChatGPT desktop app)
  fin-mcp --http                → streamable HTTP on /mcp (ChatGPT web, Fly.io)
  fin-mcp --http --port 8080
"""

from __future__ import annotations

import click


@click.command()
@click.option("--http", "use_http", is_flag=True, help="Run as streamable HTTP server (for remote/web access)")
@click.option("--port", default=8000, help="Port for HTTP server (default: 8000)")
@click.option("--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
def main(use_http: bool, port: int, host: str) -> None:
    """Start the finance MCP server."""
    from finance_llm.lib.mcp_server import mcp

    if use_http:
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.settings.stateless_http = True
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
