# Finance LLM

Personal finance system with LLM-assisted insights via hledger.

## Architecture

```
SimpleFIN → Ingest → hledger Journal
ChatGPT → MCP Server → fin tools → hledger → Insight
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Import from SimpleFIN
fin-ingest

# Review uncategorized transactions
fin-review

# Post reviewed transactions to journal
fin-post

# Query finances via CLI
fin balance 2026-02
fin trend groceries 6m

# Start MCP server for ChatGPT
fin-mcp
```

## Project Structure

```
src/finance_llm/
├── lib/                    # Core libraries
│   ├── fingerprint.py      # Transaction dedup hashing
│   ├── state.py            # SQLite state management
│   ├── csv_normalizer.py   # CSV → canonical JSONL
│   ├── rules.py            # Payee/account matching
│   ├── journal_writer.py   # JSONL → hledger journal
│   ├── fin_commands.py     # Safe hledger command registry
│   ├── mcp_server.py       # MCP protocol handler
│   └── report_generator.py # AI report summarization
├── bin/                    # CLI entry points
│   ├── fin.py              # hledger wrapper CLI
│   ├── ingest.py           # Import pipeline (SimpleFIN)
│   ├── review.py           # Transaction review
│   ├── post.py             # Finalize to journal
│   └── mcp.py              # MCP server entry point
journal/                    # hledger journals (source of truth)
import/                     # Import pipeline
├── raw/                    # Original CSVs
├── canonical/              # Normalized JSONL
├── rules/                  # Payee/account/CSV rules (YAML)
└── state/                  # Dedup SQLite databases
reports/weekly/             # AI-generated summaries
```
