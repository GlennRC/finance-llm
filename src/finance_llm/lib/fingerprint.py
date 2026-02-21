"""Transaction fingerprinting for deduplication.

Generates stable SHA-256 hashes from transaction fields to prevent
duplicate imports across the pipeline.
"""

from __future__ import annotations

import hashlib
import re


def normalize_payee(raw_payee: str) -> str:
    """Normalize a payee string for consistent fingerprinting.

    Strips whitespace, lowercases, removes non-alphanumeric chars,
    and collapses multiple spaces.
    """
    s = raw_payee.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def fingerprint(
    account: str,
    date: str,
    amount: str,
    payee: str,
    source_id: str = "",
) -> str:
    """Generate a stable transaction fingerprint.

    Args:
        account: The hledger account (e.g., "Liabilities:CreditCard:Chase")
        date: Transaction date as string (e.g., "2026-02-15")
        amount: Transaction amount as string (e.g., "-42.50")
        payee: Raw payee string (will be normalized)
        source_id: Optional institution-specific transaction ID

    Returns:
        SHA-256 hex digest string
    """
    normalized = normalize_payee(payee)
    parts = f"{account}|{date}|{amount}|{normalized}|{source_id}"
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()
