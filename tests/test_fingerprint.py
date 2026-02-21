"""Tests for fingerprint module."""

from finance_llm.lib.fingerprint import fingerprint, normalize_payee


def test_normalize_payee_basic():
    assert normalize_payee("  TRADER JOE'S #123  ") == "trader joes 123"


def test_normalize_payee_amazon():
    assert normalize_payee("AMZN Mktp US*AB1CD2EF3") == "amzn mktp usab1cd2ef3"


def test_normalize_payee_idempotent():
    raw = "Some Merchant"
    assert normalize_payee(normalize_payee(raw)) == normalize_payee(raw)


def test_fingerprint_deterministic():
    fp1 = fingerprint("Liabilities:Chase", "2026-02-15", "42.50", "TRADER JOE'S")
    fp2 = fingerprint("Liabilities:Chase", "2026-02-15", "42.50", "TRADER JOE'S")
    assert fp1 == fp2


def test_fingerprint_different_amounts():
    fp1 = fingerprint("Liabilities:Chase", "2026-02-15", "42.50", "Store")
    fp2 = fingerprint("Liabilities:Chase", "2026-02-15", "42.51", "Store")
    assert fp1 != fp2


def test_fingerprint_is_sha256():
    fp = fingerprint("acc", "2026-01-01", "10.00", "payee")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)
