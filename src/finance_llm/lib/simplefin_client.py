"""SimpleFIN API client — pulls bank transactions via SimpleFIN Bridge.

SimpleFIN is a lightweight protocol for read-only bank data access.
Users create a setup token at https://bridge.simplefin.org/simplefin/create,
the app claims an access URL, then polls for accounts/transactions.

API constraints:
- Max 24 requests per day per connection
- Max 60-day date range per request
- Access URL contains Basic Auth credentials (store securely)
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


@dataclass
class SimpleFINTransaction:
    """A transaction from the SimpleFIN API."""

    id: str
    posted: int  # UNIX timestamp
    amount: str  # Numeric string, negative = debit
    description: str
    pending: bool = False
    transacted_at: int | None = None

    @property
    def date(self) -> str:
        """Transaction date as YYYY-MM-DD."""
        ts = self.transacted_at or self.posted
        if ts == 0:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass
class SimpleFINAccount:
    """A bank account from the SimpleFIN API."""

    id: str
    name: str
    currency: str
    balance: str
    balance_date: int
    org_domain: str
    org_sfin_url: str | None
    transactions: list[SimpleFINTransaction]

    @property
    def institution(self) -> str:
        """Derive institution name from org domain."""
        domain = self.org_domain.lower()
        # Map known domains to our profile names
        mappings = {
            "firsttechfed.com": "firsttech",
            "chase.com": "chase",
            "americanexpress.com": "amex",
            "bankofamerica.com": "bofa",
            "wellsfargo.com": "wells",
            "capitalone.com": "capital_one",
            "citibank.com": "citi",
            "discover.com": "discover",
        }
        for key, value in mappings.items():
            if key in domain:
                return value
        # Fallback: use first part of domain
        return domain.split(".")[0]


class SimpleFINClient:
    """Client for the SimpleFIN Bridge API."""

    def __init__(self, access_url: str) -> None:
        """Initialize with an access URL (contains Basic Auth credentials).

        Args:
            access_url: Full URL like https://user:pass@bridge.simplefin.org/simplefin
        """
        self.access_url = access_url.rstrip("/")
        self._parse_auth()

    def _parse_auth(self) -> None:
        """Extract auth credentials and base URL from access URL."""
        parsed = urlparse(self.access_url)
        self.username = parsed.username or ""
        self.password = parsed.password or ""
        # Rebuild URL without credentials for requests
        self.base_url = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            self.base_url += f":{parsed.port}"
        self.base_url += parsed.path

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Make authenticated GET request."""
        url = f"{self.base_url}{path}"
        resp = requests.get(
            url,
            auth=(self.username, self.password),
            params=params,
            timeout=30,
        )
        if resp.status_code == 403:
            raise PermissionError(
                "SimpleFIN access denied. Token may be revoked — "
                "re-run setup to create a new connection."
            )
        resp.raise_for_status()
        return resp.json()

    def get_accounts(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[SimpleFINAccount]:
        """Fetch accounts with transactions.

        Args:
            start_date: Only include transactions after this date
            end_date: Only include transactions before this date

        Returns:
            List of SimpleFINAccount with embedded transactions
        """
        params = {}
        if start_date:
            params["start-date"] = str(int(start_date.timestamp()))
        if end_date:
            params["end-date"] = str(int(end_date.timestamp()))

        data = self._get("/accounts", params=params)

        # Surface any errors
        errors = data.get("errors", [])
        if errors:
            # Log but don't fail — errors are informational
            for err in errors:
                print(f"SimpleFIN warning: {err}")

        accounts = []
        for acct_data in data.get("accounts", []):
            org = acct_data.get("org", {})
            txns = []
            for t in acct_data.get("transactions", []):
                txns.append(SimpleFINTransaction(
                    id=t["id"],
                    posted=t["posted"],
                    amount=t["amount"],
                    description=t["description"],
                    pending=t.get("pending", False),
                    transacted_at=t.get("transacted_at"),
                ))

            accounts.append(SimpleFINAccount(
                id=acct_data["id"],
                name=acct_data["name"],
                currency=acct_data.get("currency", "USD"),
                balance=acct_data["balance"],
                balance_date=acct_data["balance-date"],
                org_domain=org.get("domain", "unknown"),
                org_sfin_url=org.get("sfin-url"),
                transactions=txns,
            ))

        return accounts

    @staticmethod
    def claim_access_url(setup_token: str) -> str:
        """Exchange a setup token for an access URL.

        The setup token is a base64-encoded URL. POST to it to claim
        the access URL. This can only be done ONCE per token.

        Args:
            setup_token: Base64-encoded claim URL from SimpleFIN Bridge

        Returns:
            Access URL string (contains credentials — store securely)
        """
        claim_url = base64.b64decode(setup_token).decode("utf-8")
        resp = requests.post(claim_url, timeout=30)

        if resp.status_code == 403:
            raise PermissionError(
                "Setup token already claimed or expired. "
                "Create a new token at https://bridge.simplefin.org/simplefin/create"
            )
        resp.raise_for_status()
        return resp.text.strip()


# --- Access URL storage ---

def save_access_url(access_url: str, state_dir: Path) -> None:
    """Save access URL to state directory."""
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "simplefin_access.json"
    data = {
        "access_url": access_url,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data))
    # Restrict permissions (contains credentials)
    path.chmod(0o600)


def load_access_url(state_dir: Path) -> str | None:
    """Load access URL from state directory."""
    path = state_dir / "simplefin_access.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("access_url")
