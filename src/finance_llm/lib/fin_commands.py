"""fin_commands — Safe hledger command registry.

Maps controlled verbs to hledger command lines with input validation
and safety constraints. Shared by both the CLI (bin/fin) and MCP server.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FinResult:
    """Result from a fin command execution."""

    command: str
    output: str
    success: bool
    error: str = ""


# Maximum output lines to prevent unbounded queries
MAX_OUTPUT_LINES = 500

# Maximum date range in months
MAX_MONTHS = 24


class FinCommands:
    """Registry of safe hledger commands."""

    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        if not journal_path.exists():
            raise FileNotFoundError(f"Journal not found: {journal_path}")

    def _run_hledger(self, args: list[str]) -> FinResult:
        """Execute an hledger command with the configured journal."""
        cmd = ["hledger", "-f", str(self.journal_path), *args]
        cmd_str = " ".join(cmd)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            # Cap output
            lines = output.splitlines()
            if len(lines) > MAX_OUTPUT_LINES:
                output = "\n".join(lines[:MAX_OUTPUT_LINES])
                output += f"\n... (truncated, {len(lines)} total lines)"

            return FinResult(
                command=cmd_str,
                output=output,
                success=result.returncode == 0,
                error=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return FinResult(command=cmd_str, output="", success=False, error="Command timed out")
        except FileNotFoundError:
            return FinResult(
                command=cmd_str, output="", success=False,
                error="hledger not found. Install with: brew install hledger",
            )

    def balance(self, period: str | None = None, account: str = "expenses") -> FinResult:
        """Account balances, optionally filtered by period.

        Example: fin balance 2026-02 → spending breakdown for February.
        """
        args = ["bal", account, "--tree"]
        if period:
            args.extend(["--period", period])
        return self._run_hledger(args)

    def register(
        self, query: str = "", period: str | None = None, payee: str | None = None
    ) -> FinResult:
        """Transaction register with optional filters.

        Example: fin register "Amazon" → all Amazon transactions.
        """
        args = ["reg"]
        if query:
            args.append(query)
        if period:
            args.extend(["--period", period])
        if payee:
            args.extend(["payee:" + payee])
        return self._run_hledger(args)

    def trend(self, account: str = "expenses", months: int = 6) -> FinResult:
        """Monthly spending trend for an account.

        Example: fin trend groceries 6 → grocery spending last 6 months.
        """
        months = min(months, MAX_MONTHS)
        args = ["bal", account, "--monthly", "-b", f"{months} months ago"]
        return self._run_hledger(args)

    def merchants(self, period: str | None = None, limit: int = 20) -> FinResult:
        """Top merchants by spend.

        Example: fin merchants 2026-02 → top merchants in February.
        """
        args = ["reg", "expenses", "--output-format", "%(account)s  %(total)s\n"]
        if period:
            args.extend(["--period", period])
        # Use hledger's built-in payee grouping
        args = ["bal", "expenses", "--pivot", "payee", "--flat", "--sort"]
        if period:
            args.extend(["--period", period])
        return self._run_hledger(args)

    def networth(self) -> FinResult:
        """Current net worth (assets minus liabilities)."""
        return self._run_hledger(["bal", "assets", "liabilities", "--tree"])

    def income(self, period: str | None = None) -> FinResult:
        """Income statement.

        Example: fin income 2026-02 → income vs expenses for February.
        """
        args = ["incomestatement"]
        if period:
            args.extend(["--period", period])
        return self._run_hledger(args)

    def anomalies(self, period: str | None = None, threshold: float = 100.0) -> FinResult:
        """Find unusually large transactions.

        Returns transactions above the threshold amount.
        """
        args = ["reg", "expenses"]
        if period:
            args.extend(["--period", period])
        args.extend(["amt:>" + str(threshold)])
        return self._run_hledger(args)

    def accounts(self) -> FinResult:
        """List all accounts in the journal."""
        return self._run_hledger(["accounts"])

    def stats(self) -> FinResult:
        """Journal statistics."""
        return self._run_hledger(["stats"])
