"""Rules engine — payee normalization and account categorization from YAML.

Loads payees.yaml and accounts.yaml, applies regex/exact matching to
map raw bank payee strings to clean names and expense accounts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PayeeRule:
    pattern: str
    name: str
    _compiled: re.Pattern | None = None

    def matches(self, raw_payee: str) -> bool:
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, re.IGNORECASE)
        return bool(self._compiled.search(raw_payee))


@dataclass
class AccountRule:
    payee: str  # Matches against the *cleaned* payee name
    account: str


class RuleEngine:
    """Loads and applies payee/account rules."""

    def __init__(self, rules_dir: Path) -> None:
        self.rules_dir = rules_dir
        self.payee_rules: list[PayeeRule] = []
        self.account_rules: list[AccountRule] = []
        self._load_payees()
        self._load_accounts()

    def _load_payees(self) -> None:
        path = self.rules_dir / "payees.yaml"
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for rule in data.get("rules", []) or []:
            self.payee_rules.append(
                PayeeRule(pattern=rule["pattern"], name=rule["name"])
            )

    def _load_accounts(self) -> None:
        path = self.rules_dir / "accounts.yaml"
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for rule in data.get("rules", []) or []:
            self.account_rules.append(
                AccountRule(payee=rule["payee"], account=rule["account"])
            )

    def normalize_payee(self, raw_payee: str) -> str:
        """Apply payee rules to get a clean name. Returns raw if no match."""
        for rule in self.payee_rules:
            if rule.matches(raw_payee):
                return rule.name
        return raw_payee

    def categorize(self, clean_payee: str) -> str | None:
        """Find the expense account for a cleaned payee name. None if uncategorized."""
        for rule in self.account_rules:
            if rule.payee.lower() == clean_payee.lower():
                return rule.account
        return None

    def apply(self, raw_payee: str) -> tuple[str, str]:
        """Apply both payee normalization and account categorization.

        Returns:
            (clean_payee, account) where account is "Expenses:Uncategorized"
            if no rule matched.
        """
        clean = self.normalize_payee(raw_payee)
        account = self.categorize(clean) or "Expenses:Uncategorized"
        return clean, account

    def add_payee_rule(self, pattern: str, name: str) -> None:
        """Add a payee rule in memory (does not persist to disk)."""
        self.payee_rules.append(PayeeRule(pattern=pattern, name=name))

    def add_account_rule(self, payee: str, account: str) -> None:
        """Add an account rule in memory (does not persist to disk)."""
        self.account_rules.append(AccountRule(payee=payee, account=account))

    def save(self) -> None:
        """Persist current rules back to YAML files."""
        payees_data = {
            "rules": [{"pattern": r.pattern, "name": r.name} for r in self.payee_rules]
        }
        with open(self.rules_dir / "payees.yaml", "w") as f:
            yaml.dump(payees_data, f, default_flow_style=False, allow_unicode=True)

        accounts_data = {
            "rules": [{"payee": r.payee, "account": r.account} for r in self.account_rules]
        }
        with open(self.rules_dir / "accounts.yaml", "w") as f:
            yaml.dump(accounts_data, f, default_flow_style=False, allow_unicode=True)
