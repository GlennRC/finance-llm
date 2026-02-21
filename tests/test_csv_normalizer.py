"""Tests for CSV normalizer."""

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from finance_llm.lib.csv_normalizer import CSVProfile, CanonicalTransaction, normalize_csv


def _make_chase_csv(content: str) -> Path:
    tmp = NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _chase_profile() -> CSVProfile:
    return CSVProfile(
        institution="chase",
        name="Chase",
        encoding="utf-8",
        delimiter=",",
        skip_rows=0,
        has_header=True,
        columns={
            "date": "Transaction Date",
            "description": "Description",
            "amount": "Amount",
            "memo": "Memo",
        },
        date_format="%m/%d/%Y",
        amount_invert=True,
        default_account="Liabilities:CreditCard:Chase",
    )


def test_parse_chase_csv():
    csv_content = (
        "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
        "02/15/2026,02/16/2026,TRADER JOE'S #123,Groceries,Sale,-42.50,\n"
        "02/14/2026,02/15/2026,AMAZON.COM,Shopping,Sale,-29.99,\n"
    )
    csv_path = _make_chase_csv(csv_content)
    profile = _chase_profile()

    transactions = normalize_csv(csv_path, profile)
    assert len(transactions) == 2

    assert transactions[0].date == "2026-02-15"
    assert transactions[0].amount == "42.50"
    assert transactions[0].payee == "TRADER JOE'S #123"
    assert transactions[0].institution == "chase"

    csv_path.unlink()


def test_canonical_json_roundtrip():
    txn = CanonicalTransaction(
        date="2026-02-15",
        amount="42.50",
        payee="Test Store",
        memo="",
        account="Liabilities:Chase",
        source_id="",
        institution="chase",
    )
    json_str = txn.to_json()
    restored = CanonicalTransaction.from_json(json_str)
    assert restored == txn
