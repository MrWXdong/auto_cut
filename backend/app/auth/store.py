from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_codes (
    phone TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT NOT NULL
);
"""


class AuthStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def save_code(self, phone: str, code: str, ttl_seconds: int = 300) -> None:
        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO auth_codes (phone, code, expires_at, attempts, sent_at)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT (phone) DO UPDATE SET
                    code = excluded.code,
                    expires_at = excluded.expires_at,
                    attempts = 0,
                    sent_at = excluded.sent_at
                """,
                (phone, code, expires_at, now.isoformat(timespec="seconds")),
            )
            connection.commit()

    def get_code(self, phone: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM auth_codes WHERE phone = ?",
                (phone,),
            ).fetchone()
        return dict(row) if row is not None else None

    def increment_attempts(self, phone: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE auth_codes SET attempts = attempts + 1 WHERE phone = ?",
                (phone,),
            )
            connection.commit()

    def delete_code(self, phone: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM auth_codes WHERE phone = ?", (phone,))
            connection.commit()
