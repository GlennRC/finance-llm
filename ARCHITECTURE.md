# Finance LLM — Architecture Document

## Overview

Finance LLM is a personal finance system that combines **hledger** (plain-text accounting) with **LLM-powered insights** via ChatGPT. Bank data flows in via **SimpleFIN** (direct bank API), gets transformed into hledger journals, and becomes queryable through both a CLI and ChatGPT.

The system has three layers: **data ingestion**, **accounting engine**, and **LLM interaction**.

---

## System Flow

```
                          ┌──────────────────────┐
                          │      SimpleFIN        │
                          │  (bank API access)    │
                          └──────────┬───────────┘
                                     │ REST API
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   LAYER 1: DATA INGESTION                                           │
│                                                                     │
│   ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐    │
│   │ SimpleFIN     │───▶│csv_normalizer│───▶│  journal_writer   │    │
│   │              │    │              │    │                   │    │
│   │ Fetch bank   │    │ Parse with   │    │ Apply rules,     │    │
│   │ transactions │    │ CSV profile  │    │ dedup, write     │    │
│   │ via API      │    │ → JSONL      │    │ hledger entries   │    │
│   └──────┬───────┘    └──────┬───────┘    └────────┬──────────┘    │
│          │                   │                     │               │
│          ▼                   ▼                     ▼               │
│   ┌────────────┐     ┌────────────┐        ┌────────────┐         │
│   │import/raw/ │     │ import/    │        │ journal/   │         │
│   │ (archived  │     │ canonical/ │        │ staging/   │         │
│   │  data)     │     │ (JSONL)    │        │ (pending)  │         │
│   └────────────┘     └────────────┘        └────────────┘         │
│                                                                     │
│   Supporting: fingerprint.py (dedup) │ rules.py (YAML) │ state.py │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                          bin/review  │  bin/post
                          (human QA)  │  (finalize)
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   LAYER 2: ACCOUNTING ENGINE (hledger)                              │
│                                                                     │
│   journal/                                                          │
│   ├── main.journal          ◄── single entry point                  │
│   └── postings/                                                     │
│       └── 2026/                                                     │
│           └── 2026-02/                                              │
│               ├── chase.journal    ◄── posted transactions          │
│               └── amex.journal                                      │
│                                                                     │
│   hledger reads main.journal (which includes all posting files)     │
│   and provides: balances, registers, income statements, stats       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                          fin_commands.py
                          (safe command registry)
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   LAYER 3: LLM INTERACTION                                          │
│                                                                     │
│   ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│   │  MCP Server      │  │  fin CLI          │  │  Report Gen      │  │
│   │                  │  │                  │  │                  │  │
│   │  ChatGPT desktop │  │  Human terminal  │  │  Automated       │  │
│   │  calls tools     │  │  queries         │  │  weekly reports  │  │
│   │  interactively   │  │                  │  │  via OpenAI API  │  │
│   └─────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│   All three use fin_commands.py → hledger (no other path exists)    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Services

### 1. MCP Server (`finance-mcp-server`)

**Type:** MCP stdio server (launched by ChatGPT desktop app)
**Entry point:** `fin-mcp` / `python -m finance_llm.bin.mcp`
**Module:** `lib/mcp_server.py`

The primary way to interact with your finances through an LLM. The ChatGPT desktop app connects to this server over stdio and can call tools during conversation.

**Available tools:**

| Tool | What it does | Example prompt |
|------|-------------|----------------|
| `fin_balance` | Spending breakdown by category | "What did I spend in February?" |
| `fin_register` | Individual transaction list | "Show me all Amazon purchases" |
| `fin_trend` | Monthly spending over time | "How has grocery spending trended?" |
| `fin_merchants` | Top payees by total spend | "Who are my top 10 merchants?" |
| `fin_networth` | Assets minus liabilities | "What's my net worth?" |
| `fin_income` | Income vs expenses | "Income vs spending last month?" |
| `fin_anomalies` | Large/unusual transactions | "Any unusual charges this month?" |
| `fin_stats` | Journal overview | "How many transactions do I have?" |
| `fin_accounts` | List all accounts | "What accounts are tracked?" |

**ChatGPT desktop config** (`Settings → MCP Servers → Add`):
```json
{
  "mcpServers": {
    "finance": {
      "command": "/path/to/finance-llm/.venv/bin/python",
      "args": ["-m", "finance_llm.bin.mcp"],
      "env": {
        "FINANCE_ROOT": "/path/to/finance-llm"
      }
    }
  }
}
```

**Safety model:** Every tool validates inputs, enforces date range limits (24 months max), caps output at 500 lines, and returns plain text only. The LLM cannot access raw files, execute shell commands, or modify the journal.

---

### 2. Weekly Report Generator

**Type:** Cron job
**Entry point:** `bin/weekly-report` (planned)
**Module:** `lib/report_generator.py`

Collects financial data via `fin_commands` (balances, income, merchants, anomalies, trends), sends it to the OpenAI API with a finance analyst system prompt, and writes a narrative markdown report to `reports/weekly/`.

**Output example:** `reports/weekly/2026-02-21_2026-02_summary.md`

---

## CLI Tools

### `fin` — hledger query wrapper

The human-facing CLI for querying finances. Same commands the MCP server uses internally.

```bash
fin balance 2026-02              # spending breakdown
fin register --payee "Amazon"    # transaction list
fin trend groceries --months 6   # monthly trend
fin merchants 2026-02            # top merchants
fin networth                     # assets - liabilities
fin income 2026-02               # income statement
fin anomalies --threshold 200    # large transactions
fin stats                        # journal overview
```

### `fin-ingest` — import pipeline

Imports bank CSVs into the staging journal.

```bash
# Manual import (from downloaded CSV)
fin-ingest --file chase_statement.csv --profile chase

# What happens:
# 1. Archives raw CSV to import/raw/chase/2026-02/sha256_<hash>.csv
# 2. Parses CSV using chase.yaml profile → canonical JSONL
# 3. Applies payee/account rules from YAML
# 4. Deduplicates via transaction fingerprints
# 5. Writes hledger entries to journal/staging/
```

### `fin-review` — transaction review

Shows staged transactions before they're posted to the live journal.

```bash
fin-review                # show all staged transactions
fin-review --uncategorized  # show only uncategorized
```

Displays a rich terminal table with date, payee, amount, and category. Uncategorized transactions are highlighted.

### `fin-post` — finalize to journal

Moves reviewed transactions from staging into the live journal.

```bash
fin-post                  # post all staged transactions
fin-post --dry-run        # preview without making changes
```

Moves `journal/staging/*.journal` → `journal/postings/YYYY/YYYY-MM/` and updates `main.journal` with include directives.

---

## Core Libraries

### Data Flow Libraries

| Library | Input | Output | Purpose |
|---------|-------|--------|---------|
| `csv_normalizer.py` | Raw CSV + profile YAML | Canonical JSONL | Parse institution-specific CSVs |
| `journal_writer.py` | Canonical JSONL | `journal/staging/*.journal` | Generate hledger entries |
| `fin_commands.py` | Query parameters | hledger text output | Safe hledger command execution |
| `mcp_server.py` | MCP tool calls | Text responses | ChatGPT ↔ hledger bridge |
| `report_generator.py` | hledger data | Markdown report | AI-narrated summaries |

### Supporting Libraries

| Library | Purpose |
|---------|---------|
| `fingerprint.py` | SHA-256 transaction hashing: `hash(account + date + amount + normalized_payee + source_id)` |
| `rules.py` | YAML-based payee normalization + account categorization with regex support |
| `state.py` | SQLite wrapper for `seen_transactions` dedup database |

---

## Data Formats

### Canonical JSONL (intermediate format)

Every transaction passes through this format between CSV parsing and journal writing:

```json
{"date": "2026-02-15", "amount": "42.50", "payee": "TRADER JOE'S #123", "memo": "", "account": "Liabilities:CreditCard:Chase", "source_id": "", "institution": "chase"}
```

### hledger Journal Entry

```
2026-02-15 Trader Joe's  ; fingerprint:a1b2c3d4...
    Expenses:Groceries    $42.50
    Liabilities:CreditCard:Chase
```

### CSV Profile (YAML)

```yaml
institution: chase
name: "Chase"
csv:
  encoding: utf-8
  delimiter: ","
  has_header: true
columns:
  date: "Transaction Date"
  description: "Description"
  amount: "Amount"
date_format: "%m/%d/%Y"
amount_invert: true                    # Chase: negative = debit
default_account: "Liabilities:CreditCard:Chase"
```

### Payee Rules (YAML)

```yaml
rules:
  - pattern: "^TRADER JOE"
    name: "Trader Joe's"
  - pattern: "AMZN|AMAZON"
    name: "Amazon"
```

### Account Rules (YAML)

```yaml
rules:
  - payee: "Trader Joe's"
    account: "Expenses:Groceries"
  - payee: "Amazon"
    account: "Expenses:Shopping"
```

---

## State Management

| Store | Location | Purpose |
|-------|----------|---------|
| `seen_transactions.sqlite` | `import/state/` | Prevents duplicate journal entries. Key: SHA-256 fingerprint. |

Both SQLite databases use WAL mode for safe concurrent access.

---

## Directory Structure

```
finance-llm/
├── src/finance_llm/
│   ├── bin/                        # CLI entry points
│   │   ├── fin.py                  #   hledger query wrapper
│   │   ├── ingest.py               #   import pipeline
│   │   ├── review.py               #   transaction review
│   │   ├── post.py                 #   finalize to journal
│   │   └── mcp.py                  #   MCP server entry point
│   └── lib/                        # Core libraries
│       ├── mcp_server.py           #   MCP protocol + tool registration
│       ├── fin_commands.py         #   safe hledger command registry
│       ├── csv_normalizer.py       #   CSV → canonical JSONL
│       ├── journal_writer.py       #   JSONL → hledger journal
│       ├── report_generator.py     #   AI report summarization
│       ├── fingerprint.py          #   transaction dedup hashing
│       ├── rules.py                #   YAML payee/account matching
│       └── state.py                #   SQLite state management
├── journal/
│   ├── main.journal                # Root journal (includes postings)
│   ├── staging/                    # Pre-review transactions
│   └── postings/                   # Live transactions
│       └── YYYY/YYYY-MM/*.journal
├── import/
│   ├── raw/                        # Archived original CSVs
│   ├── canonical/                  # Normalized JSONL
│   ├── rules/
│   │   ├── payees.yaml             # Payee normalization
│   │   ├── accounts.yaml           # Account categorization
│   │   └── csv_profiles/           # Per-institution CSV formats
│   │       ├── chase.yaml
│   │       └── amex.yaml
│   └── state/                      # Dedup databases
├── reports/weekly/                  # AI-generated summaries
├── tests/
├── pyproject.toml
└── README.md
```

---

## Design Principles

1. **hledger is the source of truth.** All financial data lives in plain-text journal files. No parallel databases for totals or balances. Every query goes through hledger.

2. **LLM is sandboxed.** The LLM (ChatGPT) can only access finances through `fin_commands.py` — a hardcoded allowlist of safe hledger queries. No raw file access, no shell execution, no journal modification.

3. **Idempotent imports.** Every transaction gets a SHA-256 fingerprint. Re-importing the same CSV produces zero duplicates.

4. **Two-phase posting.** Transactions land in `staging/` first, get reviewed, then move to `postings/`. Nothing appears in hledger queries until explicitly posted.

5. **Rules are data, not code.** Payee normalization and account categorization live in YAML files. Add a new merchant by editing a YAML file, not Python code.

6. **Canonical intermediate format.** Raw CSV → JSONL → journal. The JSONL step decouples institution-specific parsing from journal generation, making it easy to add new banks.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Accounting engine | hledger 1.51+ |
| Runtime | Python 3.11+ |
| Bank data ingestion | SimpleFIN API |
| LLM interaction | MCP (Model Context Protocol) via `mcp` SDK |
| ChatGPT integration | ChatGPT desktop app MCP support |
| Automated reports | OpenAI API (`gpt-4o`) |
| Email ingestion | *(removed — replaced by SimpleFIN)* |
| CLI framework | Click |
| Terminal UI | Rich |
| Config format | YAML (PyYAML) |
| State stores | SQLite (built-in) |
