"""SQLite state management for deduplication.

Manages two databases:
- seen_emails: tracks processed email message IDs
- seen_transactions: tracks posted transaction fingerprints
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class StateDB:
    """Generic SQLite state store with mark/check semantics."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "StateDB":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class SeenEmails(StateDB):
    """Tracks processed email message IDs to prevent re-downloading."""

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_emails (
                message_id TEXT PRIMARY KEY,
                institution TEXT,
                fetched_at TEXT NOT NULL,
                file_path TEXT
            )
        """)
        self._conn.commit()

    def is_seen(self, message_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_emails WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def mark_seen(
        self, message_id: str, institution: str, file_path: str | None = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_emails (message_id, institution, fetched_at, file_path) "
            "VALUES (?, ?, ?, ?)",
            (message_id, institution, now, file_path),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM seen_emails").fetchone()
        return row[0] if row else 0


class SeenTransactions(StateDB):
    """Tracks posted transaction fingerprints to prevent duplicates."""

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_transactions (
                fingerprint TEXT PRIMARY KEY,
                source TEXT,
                posted_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def is_seen(self, fp: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_transactions WHERE fingerprint = ?", (fp,)
        ).fetchone()
        return row is not None

    def mark_seen(self, fp: str, source: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_transactions (fingerprint, source, posted_at) "
            "VALUES (?, ?, ?)",
            (fp, source, now),
        )
        self._conn.commit()

    def mark_batch(self, fingerprints: list[tuple[str, str]]) -> int:
        """Mark multiple fingerprints as seen. Returns count of new entries."""
        now = datetime.now(timezone.utc).isoformat()
        added = 0
        for fp, source in fingerprints:
            if not self.is_seen(fp):
                self.mark_seen(fp, source)
                added += 1
        return added

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM seen_transactions").fetchone()
        return row[0] if row else 0
