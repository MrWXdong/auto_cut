from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS credit_accounts (
    tenant_id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    ref_type TEXT NOT NULL DEFAULT '',
    ref_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'committed',
    expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_reservation
    ON credit_ledger (tenant_id, ref_type, ref_id) WHERE kind = 'reserve';

CREATE INDEX IF NOT EXISTS idx_credit_ledger_tenant
    ON credit_ledger (tenant_id, created_at);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class InsufficientCredits(ValueError):
    pass


class CreditService:
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

    @staticmethod
    def _ensure_account(connection: sqlite3.Connection, tenant_id: str) -> None:
        connection.execute(
            """
            INSERT INTO credit_accounts (tenant_id, balance, updated_at)
            VALUES (?, 0, ?)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id, utcnow()),
        )

    def balance(self, tenant_id: str) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT balance FROM credit_accounts WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        return int(row["balance"]) if row is not None else 0

    def grant(
        self,
        tenant_id: str,
        amount: int,
        reason: str,
        expires_at: str | None = None,
    ) -> None:
        if amount <= 0:
            raise ValueError("grant amount must be positive")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, tenant_id)
            connection.execute(
                """
                UPDATE credit_accounts
                SET balance = balance + ?, updated_at = ?
                WHERE tenant_id = ?
                """,
                (amount, utcnow(), tenant_id),
            )
            connection.execute(
                """
                INSERT INTO credit_ledger
                    (id, tenant_id, amount, kind, reason, status, expires_at, created_at)
                VALUES (?, ?, ?, 'grant', ?, 'committed', ?, ?)
                """,
                (uuid.uuid4().hex, tenant_id, amount, reason, expires_at, utcnow()),
            )
            connection.commit()

    def reserve(
        self,
        tenant_id: str,
        amount: int,
        ref_type: str,
        ref_id: str,
    ) -> str:
        if amount <= 0:
            raise ValueError("reserve amount must be positive")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT id FROM credit_ledger
                WHERE tenant_id = ? AND ref_type = ? AND ref_id = ? AND kind = 'reserve'
                """,
                (tenant_id, ref_type, ref_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return str(existing["id"])

            self._ensure_account(connection, tenant_id)
            account = connection.execute(
                "SELECT balance FROM credit_accounts WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            if account is None or int(account["balance"]) < amount:
                connection.rollback()
                raise InsufficientCredits("积分不足")

            ledger_id = uuid.uuid4().hex
            connection.execute(
                """
                UPDATE credit_accounts
                SET balance = balance - ?, updated_at = ?
                WHERE tenant_id = ?
                """,
                (amount, utcnow(), tenant_id),
            )
            connection.execute(
                """
                INSERT INTO credit_ledger
                    (id, tenant_id, amount, kind, ref_type, ref_id, status, created_at)
                VALUES (?, ?, ?, 'reserve', ?, ?, 'pending', ?)
                """,
                (ledger_id, tenant_id, -amount, ref_type, ref_id, utcnow()),
            )
            connection.commit()
            return ledger_id

    def settle_ref(
        self,
        tenant_id: str,
        ref_type: str,
        ref_id: str,
        actual_amount: int | None = None,
    ) -> int:
        with closing(self._connect()) as connection:
            reservation = connection.execute(
                """
                SELECT * FROM credit_ledger
                WHERE tenant_id = ? AND ref_type = ? AND ref_id = ?
                  AND kind = 'reserve' AND status = 'pending'
                """,
                (tenant_id, ref_type, ref_id),
            ).fetchone()
            if reservation is None:
                return 0
            reserved = abs(int(reservation["amount"]))
            actual = reserved if actual_amount is None else max(0, actual_amount)
            difference = reserved - actual
            connection.execute("BEGIN IMMEDIATE")
            if difference:
                connection.execute(
                    """
                    UPDATE credit_accounts
                    SET balance = balance + ?, updated_at = ?
                    WHERE tenant_id = ?
                    """,
                    (difference, utcnow(), tenant_id),
                )
                connection.execute(
                    """
                    INSERT INTO credit_ledger
                        (id, tenant_id, amount, kind, reason, ref_type, ref_id, created_at)
                    VALUES (?, ?, ?, 'settle', 'settle difference', ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        tenant_id,
                        difference,
                        ref_type,
                        ref_id,
                        utcnow(),
                    ),
                )
            connection.execute(
                "UPDATE credit_ledger SET status = 'settled' WHERE id = ?",
                (reservation["id"],),
            )
            connection.commit()
            return difference

    def refund_ref(self, tenant_id: str, ref_type: str, ref_id: str) -> int:
        with closing(self._connect()) as connection:
            reservation = connection.execute(
                """
                SELECT * FROM credit_ledger
                WHERE tenant_id = ? AND ref_type = ? AND ref_id = ?
                  AND kind = 'reserve' AND status = 'pending'
                """,
                (tenant_id, ref_type, ref_id),
            ).fetchone()
            if reservation is None:
                return 0
            amount = abs(int(reservation["amount"]))
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE credit_accounts
                SET balance = balance + ?, updated_at = ?
                WHERE tenant_id = ?
                """,
                (amount, utcnow(), tenant_id),
            )
            connection.execute(
                """
                INSERT INTO credit_ledger
                    (id, tenant_id, amount, kind, reason, ref_type, ref_id, created_at)
                VALUES (?, ?, ?, 'refund', 'task refund', ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    tenant_id,
                    amount,
                    ref_type,
                    ref_id,
                    utcnow(),
                ),
            )
            connection.execute(
                "UPDATE credit_ledger SET status = 'refunded' WHERE id = ?",
                (reservation["id"],),
            )
            connection.commit()
            return amount

    def ledger(self, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM credit_ledger
                WHERE tenant_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
