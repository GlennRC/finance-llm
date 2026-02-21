"""Tests for rules engine."""

from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from finance_llm.lib.rules import RuleEngine


def _create_rules_dir(payees=None, accounts=None):
    tmp = TemporaryDirectory()
    rules_dir = Path(tmp.name)

    payees_data = {"rules": payees or []}
    with open(rules_dir / "payees.yaml", "w") as f:
        yaml.dump(payees_data, f)

    accounts_data = {"rules": accounts or []}
    with open(rules_dir / "accounts.yaml", "w") as f:
        yaml.dump(accounts_data, f)

    return tmp, rules_dir


def test_empty_rules():
    tmp, rules_dir = _create_rules_dir()
    engine = RuleEngine(rules_dir)
    clean, account = engine.apply("RANDOM STORE")
    assert clean == "RANDOM STORE"
    assert account == "Expenses:Uncategorized"
    tmp.cleanup()


def test_payee_normalization():
    tmp, rules_dir = _create_rules_dir(
        payees=[{"pattern": "^TRADER JOE", "name": "Trader Joe's"}]
    )
    engine = RuleEngine(rules_dir)
    assert engine.normalize_payee("TRADER JOE'S #123") == "Trader Joe's"
    assert engine.normalize_payee("WALMART") == "WALMART"
    tmp.cleanup()


def test_account_categorization():
    tmp, rules_dir = _create_rules_dir(
        payees=[{"pattern": "AMZN|AMAZON", "name": "Amazon"}],
        accounts=[{"payee": "Amazon", "account": "Expenses:Shopping"}],
    )
    engine = RuleEngine(rules_dir)
    clean, account = engine.apply("AMZN Mktp US*123")
    assert clean == "Amazon"
    assert account == "Expenses:Shopping"
    tmp.cleanup()


def test_save_and_reload():
    tmp, rules_dir = _create_rules_dir()
    engine = RuleEngine(rules_dir)
    engine.add_payee_rule("^NETFLIX", "Netflix")
    engine.add_account_rule("Netflix", "Expenses:Subscriptions")
    engine.save()

    engine2 = RuleEngine(rules_dir)
    clean, account = engine2.apply("NETFLIX.COM")
    assert clean == "Netflix"
    assert account == "Expenses:Subscriptions"
    tmp.cleanup()
