from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.auth.security import hash_password, verify_password
from app.billing.credits import SCHEMA as CREDIT_SCHEMA
from app.config import Settings
from app.studio.script_styles import DEFAULT_SCRIPT_STYLES

PLANS: dict[str, dict[str, Any]] = {
    "trial": {
        "name": "试用版",
        "price_cents": 0,
        "price_monthly_cents": 0,
        "price_yearly_cents": 0,
        "credits": 300,
        "render_minutes": 30,
        "storage_gb": 5,
        "seats": 3,
        "concurrency": 1,
        "projects": 3,
        "assets": 100,
        "scripts": 100,
        "jobs": 300,
    },
    "basic": {
        "name": "标准版",
        "price_cents": 29900,
        "price_monthly_cents": 29900,
        "price_yearly_cents": 299000,
        "credits": 3000,
        "render_minutes": 300,
        "storage_gb": 50,
        "seats": 10,
        "concurrency": 2,
        "projects": 20,
        "assets": 1000,
        "scripts": 1000,
        "jobs": 3000,
    },
    "pro": {
        "name": "高级版",
        "price_cents": 89900,
        "price_monthly_cents": 89900,
        "price_yearly_cents": 899000,
        "credits": 10000,
        "render_minutes": 1200,
        "storage_gb": 200,
        "seats": 30,
        "concurrency": 5,
        "projects": 100,
        "assets": 5000,
        "scripts": 5000,
        "jobs": 15000,
    },
    "enterprise": {
        "name": "旗舰版",
        "price_cents": 299900,
        "price_monthly_cents": 299900,
        "price_yearly_cents": 2999000,
        "credits": 40000,
        "render_minutes": 4000,
        "storage_gb": 1024,
        "seats": 30,
        "concurrency": 10,
        "projects": 500,
        "assets": 20000,
        "scripts": 20000,
        "jobs": 50000,
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'trial',
    status TEXT NOT NULL DEFAULT 'active',
    seats INTEGER NOT NULL DEFAULT 3,
    render_minutes INTEGER NOT NULL DEFAULT 30,
    storage_gb INTEGER NOT NULL DEFAULT 5,
    concurrency INTEGER NOT NULL DEFAULT 1,
    credits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_admins (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_users (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users (tenant_id);

CREATE TABLE IF NOT EXISTS activation_codes (
    code TEXT PRIMARY KEY,
    plan TEXT NOT NULL,
    duration_days INTEGER NOT NULL DEFAULT 30,
    used_by TEXT,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    plan TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    owner_email TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    owner_password_hash TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'manual',
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    tenant_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status, created_at);

CREATE TABLE IF NOT EXISTS platform_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS script_style_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    prompt TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 100,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_script_style_order
    ON script_style_presets (enabled, sort_order, created_at);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PlatformStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA + CREDIT_SCHEMA)
            connection.commit()

        self._migrate()

        with closing(self._connect()) as connection:
            self._seed_script_styles(connection)
            connection.commit()

    @staticmethod
    def _seed_script_styles(connection: sqlite3.Connection) -> None:
        seeded = connection.execute(
            "SELECT value FROM platform_meta WHERE key = 'script_styles_seeded'"
        ).fetchone()
        if seeded is not None:
            return
        now = utcnow()
        for index, item in enumerate(DEFAULT_SCRIPT_STYLES):
            connection.execute(
                """
                INSERT OR IGNORE INTO script_style_presets
                    (id, name, prompt, sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    str(item["id"]),
                    str(item["name"]),
                    str(item["prompt"]),
                    (index + 1) * 10,
                    now,
                    now,
                ),
            )
        connection.execute(
            """
            INSERT INTO platform_meta (key, value)
            VALUES ('script_styles_seeded', '1')
            """
        )

    def _migrate(self) -> None:
        with closing(self._connect()) as connection:
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tenants)")
            }
            if "credits" not in columns:
                connection.execute(
                    "ALTER TABLE tenants ADD COLUMN credits INTEGER NOT NULL DEFAULT 0"
                )
                connection.commit()

            rows = connection.execute("SELECT * FROM tenants").fetchall()
            for row in rows:
                plan = PLANS.get(str(row["plan"]), PLANS["trial"])
                if int(row["credits"] or 0) != 0:
                    continue
                credits = int(plan["credits"])
                connection.execute(
                    "UPDATE tenants SET credits = ? WHERE id = ?",
                    (credits, row["id"]),
                )
                existing = connection.execute(
                    """
                    SELECT id FROM credit_ledger
                    WHERE tenant_id = ? AND kind = 'grant' LIMIT 1
                    """,
                    (row["id"],),
                ).fetchone()
                if existing is None:
                    now = utcnow()
                    connection.execute(
                        """
                        INSERT INTO credit_accounts (tenant_id, balance, updated_at)
                        VALUES (?, 0, ?)
                        ON CONFLICT (tenant_id) DO NOTHING
                        """,
                        (row["id"], now),
                    )
                    connection.execute(
                        """
                        UPDATE credit_accounts
                        SET balance = balance + ?, updated_at = ?
                        WHERE tenant_id = ?
                        """,
                        (credits, now, row["id"]),
                    )
                    connection.execute(
                        """
                        INSERT INTO credit_ledger
                            (id, tenant_id, amount, kind, reason, status, created_at)
                        VALUES (?, ?, ?, 'grant', 'plan backfill', 'committed', ?)
                        """,
                        (uuid.uuid4().hex, row["id"], credits, now),
                    )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def seed(self, settings: Settings) -> None:
        with closing(self._connect()) as connection:
            admin = connection.execute(
                "SELECT id FROM platform_admins LIMIT 1"
            ).fetchone()
            if admin is None:
                connection.execute(
                    """
                    INSERT INTO platform_admins (id, email, password_hash, name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex[:10],
                        settings.platform_admin_email,
                        hash_password(settings.platform_admin_password),
                        "Platform Admin",
                        utcnow(),
                    ),
                )

            tenant = connection.execute("SELECT id FROM tenants LIMIT 1").fetchone()
            if tenant is None and settings.seed_demo_tenant:
                self._create_tenant(
                    connection,
                    name="Demo 企业",
                    plan="trial",
                    tenant_id="demo",
                    owner_email="demo@local",
                    owner_password="demo",
                    owner_name="Demo Owner",
                )
            connection.commit()

    @staticmethod
    def _create_tenant(
        connection: sqlite3.Connection,
        *,
        name: str,
        plan: str,
        tenant_id: str,
        owner_email: str,
        owner_password: str | None = None,
        owner_name: str,
        owner_password_hash: str | None = None,
    ) -> None:
        config = PLANS.get(plan, PLANS["trial"])
        now = utcnow()
        connection.execute(
            """
            INSERT INTO tenants (
                id, name, plan, status, seats, render_minutes,
                storage_gb, concurrency, credits, created_at, updated_at
            )
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                name,
                plan,
                config["seats"],
                config["render_minutes"],
                config["storage_gb"],
                config["concurrency"],
                config["credits"],
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO tenant_users (
                id, tenant_id, email, password_hash, name, role, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'owner', 'active', ?)
            """,
            (
                uuid.uuid4().hex[:10],
                tenant_id,
                owner_email,
                owner_password_hash or hash_password(owner_password or ""),
                owner_name,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO credit_accounts (tenant_id, balance, updated_at)
            VALUES (?, 0, ?)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id, now),
        )
        connection.execute(
            """
            UPDATE credit_accounts
            SET balance = balance + ?, updated_at = ?
            WHERE tenant_id = ?
            """,
            (config["credits"], now, tenant_id),
        )
        connection.execute(
            """
            INSERT INTO credit_ledger
                (id, tenant_id, amount, kind, reason, status, created_at)
            VALUES (?, ?, ?, 'grant', 'plan grant', 'committed', ?)
            """,
            (uuid.uuid4().hex, tenant_id, config["credits"], now),
        )

    def verify_platform_admin(self, email: str, password: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM platform_admins WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "email": row["email"], "name": row["name"]}

    def verify_tenant_user(self, email: str, password: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT u.*, t.name AS tenant_name, t.status AS tenant_status
                FROM tenant_users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE u.email = ? AND u.status = 'active'
                """,
                (email.strip().lower(),),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        if row["tenant_status"] != "active":
            return None
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "tenant_name": row["tenant_name"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
        }

    def list_tenants(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT t.*,
                    (SELECT COUNT(*) FROM tenant_users u WHERE u.tenant_id = t.id) AS user_count
                FROM tenants t
                ORDER BY t.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT t.*,
                    (SELECT COUNT(*) FROM tenant_users u WHERE u.tenant_id = t.id) AS user_count
                FROM tenants t WHERE t.id = ?
                """,
                (tenant_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_tenant(
        self,
        name: str,
        plan: str,
        owner_email: str,
        owner_password: str,
        owner_name: str = "Owner",
    ) -> dict[str, Any]:
        if plan not in PLANS:
            raise ValueError("unknown plan")
        name = name.strip()
        email = owner_email.strip().lower()
        if not name or not email or len(owner_password) < 4:
            raise ValueError("name, owner email and password are required")
        tenant_id = uuid.uuid4().hex[:8]
        with closing(self._connect()) as connection:
            try:
                self._create_tenant(
                    connection,
                    name=name,
                    plan=plan,
                    tenant_id=tenant_id,
                    owner_email=email,
                    owner_password=owner_password,
                    owner_name=owner_name.strip() or "Owner",
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("owner email already exists") from exc
        return self.get_tenant(tenant_id) or {}

    def update_tenant(
        self,
        tenant_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in (
            "name",
            "status",
            "plan",
            "seats",
            "render_minutes",
            "storage_gb",
            "concurrency",
            "credits",
        ):
            if values.get(key) is not None:
                fields.append(f"{key} = ?")
                args.append(values[key])
        if not fields:
            return self.get_tenant(tenant_id)
        fields.append("updated_at = ?")
        args.append(utcnow())
        args.append(tenant_id)
        with closing(self._connect()) as connection:
            connection.execute(
                f"UPDATE tenants SET {', '.join(fields)} WHERE id = ?",
                args,
            )
            connection.commit()
        return self.get_tenant(tenant_id)

    def list_tenant_users(self, tenant_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, tenant_id, email, name, role, status, created_at
                FROM tenant_users WHERE tenant_id = ?
                ORDER BY created_at
                """,
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # activation codes
    def create_activation_codes(
        self,
        plan: str,
        count: int,
        duration_days: int = 30,
    ) -> list[dict[str, Any]]:
        if plan not in PLANS:
            raise ValueError("unknown plan")
        count = max(1, min(count, 100))
        created: list[dict[str, Any]] = []
        with closing(self._connect()) as connection:
            for _ in range(count):
                code = "AC" + uuid.uuid4().hex[:10].upper()
                now = utcnow()
                connection.execute(
                    """
                    INSERT INTO activation_codes
                        (code, plan, duration_days, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (code, plan, duration_days, now),
                )
                created.append(
                    {
                        "code": code,
                        "plan": plan,
                        "duration_days": duration_days,
                        "created_at": now,
                    }
                )
            connection.commit()
        return created

    def list_activation_codes(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM activation_codes
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def redeem_activation_code(
        self,
        code: str,
        company_name: str,
        owner_email: str,
        owner_password: str,
        owner_name: str = "Owner",
    ) -> dict[str, Any]:
        code = code.strip().upper()
        email = owner_email.strip().lower()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM activation_codes WHERE code = ? AND used_by IS NULL",
                (code,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ValueError("激活码无效或已使用")
            tenant_id = uuid.uuid4().hex[:8]
            try:
                self._create_tenant(
                    connection,
                    name=company_name.strip(),
                    plan=row["plan"],
                    tenant_id=tenant_id,
                    owner_email=email,
                    owner_password=owner_password,
                    owner_name=owner_name.strip() or "Owner",
                )
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("管理员邮箱已存在") from exc
            connection.execute(
                "UPDATE activation_codes SET used_by = ?, used_at = ? WHERE code = ?",
                (email, utcnow(), code),
            )
            connection.commit()
        return {
            "tenant": self.get_tenant(tenant_id),
            "user": self.verify_tenant_user(email, owner_password),
            "plan": row["plan"],
        }

    # orders
    def create_order(
        self,
        *,
        plan: str,
        company_name: str,
        owner_email: str,
        owner_name: str,
        owner_password: str,
        provider: str = "manual",
    ) -> dict[str, Any]:
        if plan not in PLANS:
            raise ValueError("unknown plan")
        order_id = "ORD" + uuid.uuid4().hex[:12].upper()
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO orders (
                    id, plan, amount_cents, company_name, owner_email, owner_name,
                    owner_password_hash, provider, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    order_id,
                    plan,
                    PLANS[plan]["price_cents"],
                    company_name.strip(),
                    owner_email.strip().lower(),
                    owner_name.strip() or "Owner",
                    hash_password(owner_password),
                    provider,
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_order(order_id) or {}

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_order_paid(
        self,
        order_id: str,
        external_id: str | None = None,
    ) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise KeyError("order not found")
        if order["status"] == "paid" and order["tenant_id"]:
            return {"order": order, "tenant": self.get_tenant(order["tenant_id"])}
        if order["status"] != "pending":
            raise ValueError("order is not pending")

        tenant_id = uuid.uuid4().hex[:8]
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._create_tenant(
                    connection,
                    name=order["company_name"],
                    plan=order["plan"],
                    tenant_id=tenant_id,
                    owner_email=order["owner_email"],
                    owner_name=order["owner_name"],
                    owner_password_hash=order["owner_password_hash"],
                )
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                connection.execute(
                    "UPDATE orders SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                    ("owner email already exists", utcnow(), order_id),
                )
                connection.commit()
                raise ValueError("管理员邮箱已存在") from exc
            connection.execute(
                """
                UPDATE orders
                SET status = 'paid', tenant_id = ?, external_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (tenant_id, external_id, utcnow(), order_id),
            )
            connection.commit()
        return {
            "order": self.get_order(order_id),
            "tenant": self.get_tenant(tenant_id),
        }

    # platform-managed script style presets
    def list_script_styles(self, include_disabled: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM script_style_presets"
        if not include_disabled:
            query += " WHERE enabled = 1"
        query += " ORDER BY sort_order, created_at"
        with closing(self._connect()) as connection:
            rows = connection.execute(query).fetchall()
        return [self._script_style_dict(row) for row in rows]

    def get_script_style(self, style_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM script_style_presets WHERE id = ?",
                (style_id,),
            ).fetchone()
        return self._script_style_dict(row) if row is not None else None

    @staticmethod
    def _script_style_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data["enabled"])
        return data

    def create_script_style(
        self,
        name: str,
        prompt: str,
        sort_order: int | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("style name is required")
        style_id = "ss_" + uuid.uuid4().hex[:10]
        now = utcnow()
        with closing(self._connect()) as connection:
            if sort_order is None:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order "
                    "FROM script_style_presets"
                ).fetchone()
                sort_order = int(row["next_order"])
            try:
                connection.execute(
                    """
                    INSERT INTO script_style_presets
                        (id, name, prompt, sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        style_id,
                        name,
                        prompt.strip(),
                        int(sort_order),
                        int(enabled),
                        now,
                        now,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("style name already exists") from exc
        return self.get_script_style(style_id) or {}

    def update_script_style(
        self,
        style_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        if values.get("name") is not None:
            name = str(values["name"]).strip()
            if not name:
                raise ValueError("style name is required")
            fields.append("name = ?")
            args.append(name)
        if values.get("prompt") is not None:
            fields.append("prompt = ?")
            args.append(str(values["prompt"]).strip())
        if values.get("sort_order") is not None:
            fields.append("sort_order = ?")
            args.append(int(values["sort_order"]))
        if values.get("enabled") is not None:
            fields.append("enabled = ?")
            args.append(int(bool(values["enabled"])))
        if not fields:
            return self.get_script_style(style_id)
        fields.append("updated_at = ?")
        args.append(utcnow())
        args.append(style_id)
        with closing(self._connect()) as connection:
            try:
                cursor = connection.execute(
                    f"UPDATE script_style_presets SET {', '.join(fields)} WHERE id = ?",
                    args,
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("style name already exists") from exc
        return self.get_script_style(style_id) if cursor.rowcount == 1 else None

    def delete_script_style(self, style_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM script_style_presets WHERE id = ?",
                (style_id,),
            )
            connection.commit()
        return cursor.rowcount == 1
