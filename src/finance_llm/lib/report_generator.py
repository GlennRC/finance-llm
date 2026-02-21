"""Report generator — AI-powered financial report summarization.

Collects hledger data via fin commands, sends to OpenAI API for
narrative analysis, generates markdown reports.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from finance_llm.lib.fin_commands import FinCommands

SYSTEM_PROMPT = """You are a personal finance analyst. You receive structured financial data
from hledger (a plain-text accounting tool) and produce clear, actionable insights.

Your reports should include:
- A brief executive summary (2-3 sentences)
- Spending breakdown by category with notable changes
- Top merchants and any unusual charges
- Income vs expenses comparison
- Actionable recommendations

Keep the tone professional but approachable. Use markdown formatting.
Amounts should use $ with 2 decimal places."""


class ReportGenerator:
    """Generates AI-narrated financial reports from hledger data."""

    def __init__(self, fin: FinCommands, model: str = "gpt-4o") -> None:
        self.fin = fin
        self.model = model
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    def collect_data(self, period: str) -> dict[str, str]:
        """Collect all relevant financial data for a period."""
        data = {}

        commands = {
            "balance": lambda: self.fin.balance(period=period),
            "income": lambda: self.fin.income(period=period),
            "merchants": lambda: self.fin.merchants(period=period),
            "anomalies": lambda: self.fin.anomalies(period=period, threshold=100),
            "trend": lambda: self.fin.trend(months=3),
            "stats": lambda: self.fin.stats(),
        }

        for key, cmd in commands.items():
            result = cmd()
            if result.success:
                data[key] = result.output
            else:
                data[key] = f"(unavailable: {result.error})"

        return data

    def generate_report(self, period: str) -> str:
        """Generate a full narrative financial report for a period."""
        data = self.collect_data(period)

        user_prompt = f"""Generate a financial report for period: {period}

Here is the data from hledger:

## Expense Balances
{data.get('balance', '(no data)')}

## Income Statement
{data.get('income', '(no data)')}

## Top Merchants
{data.get('merchants', '(no data)')}

## Large/Unusual Transactions (>$100)
{data.get('anomalies', '(no data)')}

## 3-Month Spending Trend
{data.get('trend', '(no data)')}

## Journal Stats
{data.get('stats', '(no data)')}

Please provide a comprehensive financial summary with insights and recommendations."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return response.choices[0].message.content or ""

    def save_report(self, content: str, reports_dir: Path, period: str) -> Path:
        """Save a report to the reports directory."""
        reports_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{period}_summary.md"
        path = reports_dir / filename
        path.write_text(content)
        return path
