"""CSV normalizer — parses institution-specific CSVs into canonical JSONL.

Uses YAML profiles (import/rules/csv_profiles/*.yaml) to handle different
bank/credit card CSV formats. Outputs one canonical JSON object per line.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path

import yaml


@dataclass
class CanonicalTransaction:
    """Normalized transaction record — the common format between CSV and journal."""

    date: str  # YYYY-MM-DD
    amount: str  # Decimal string, positive = expense
    payee: str  # Raw payee from bank
    memo: str  # Additional description
    account: str  # Source account (e.g., Liabilities:CreditCard:Chase)
    source_id: str  # Institution reference ID if available
    institution: str  # Profile name (e.g., "chase")

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "CanonicalTransaction":
        return cls(**json.loads(line))


@dataclass
class CSVProfile:
    """Parsed CSV profile from YAML config."""

    institution: str
    name: str
    encoding: str
    delimiter: str
    skip_rows: int
    has_header: bool
    columns: dict[str, str]  # field -> column header name
    date_format: str
    amount_invert: bool
    default_account: str

    @classmethod
    def load(cls, path: Path) -> "CSVProfile":
        with open(path) as f:
            data = yaml.safe_load(f)
        csv_conf = data.get("csv", {})
        return cls(
            institution=data["institution"],
            name=data["name"],
            encoding=csv_conf.get("encoding", "utf-8"),
            delimiter=csv_conf.get("delimiter", ","),
            skip_rows=csv_conf.get("skip_rows", 0),
            has_header=csv_conf.get("has_header", True),
            columns=data["columns"],
            date_format=data["date_format"],
            amount_invert=data.get("amount_invert", False),
            default_account=data["default_account"],
        )


def normalize_csv(csv_path: Path, profile: CSVProfile) -> list[CanonicalTransaction]:
    """Parse a CSV file using the given profile and return canonical transactions."""
    with open(csv_path, encoding=profile.encoding) as f:
        content = f.read()

    # Skip rows if needed
    lines = content.splitlines()
    if profile.skip_rows > 0:
        lines = lines[profile.skip_rows :]
    content = "\n".join(lines)

    reader = csv.DictReader(
        StringIO(content),
        delimiter=profile.delimiter,
    )

    transactions: list[CanonicalTransaction] = []
    for row in reader:
        date_str = row.get(profile.columns.get("date", ""), "").strip()
        if not date_str:
            continue

        try:
            parsed_date = datetime.strptime(date_str, profile.date_format)
        except ValueError:
            continue

        raw_amount = row.get(profile.columns.get("amount", ""), "0").strip()
        try:
            amount = float(raw_amount.replace(",", ""))
        except ValueError:
            continue

        if profile.amount_invert:
            amount = -amount

        description = row.get(profile.columns.get("description", ""), "").strip()
        memo = row.get(profile.columns.get("memo", ""), "").strip()
        reference = row.get(profile.columns.get("reference", ""), "").strip()

        txn = CanonicalTransaction(
            date=parsed_date.strftime("%Y-%m-%d"),
            amount=f"{amount:.2f}",
            payee=description,
            memo=memo,
            account=profile.default_account,
            source_id=reference,
            institution=profile.institution,
        )
        transactions.append(txn)

    return transactions


def write_canonical(transactions: list[CanonicalTransaction], output_path: Path) -> None:
    """Write canonical transactions as JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a") as f:
        for txn in transactions:
            f.write(txn.to_json() + "\n")
