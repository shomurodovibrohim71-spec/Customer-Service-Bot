"""Async SQLite data access layer (per-tenant database files)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER NOT NULL,
    tenant_id TEXT NOT NULL,
    name TEXT,
    username TEXT,
    phone TEXT,
    language TEXT,
    branch_id INTEGER,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_user
    ON messages(tenant_id, user_id, id DESC);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    service TEXT NOT NULL,
    branch TEXT,
    address TEXT,
    preferred_time TEXT NOT NULL,
    payment_method TEXT DEFAULT 'cash',
    payment_status TEXT DEFAULT 'unpaid',
    amount INTEGER DEFAULT 0,
    courier_name TEXT,
    courier_phone TEXT,
    courier_car TEXT,
    eta_minutes INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_status
    ON orders(tenant_id, status, id DESC);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    price TEXT NOT NULL,
    price_value INTEGER DEFAULT 0,
    description TEXT,
    category TEXT,
    image_url TEXT,
    position INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_tenant
    ON products(tenant_id, is_active, position);

CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    phone TEXT,
    lat REAL,
    lon REAL,
    maps_url TEXT,
    hours_json TEXT,
    position INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_branches_tenant
    ON branches(tenant_id, is_active, position);

CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    label TEXT,
    text TEXT NOT NULL,
    lat REAL,
    lon REAL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_addresses_user
    ON addresses(tenant_id, user_id, is_active);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_tenant
    ON feedback(tenant_id, id DESC);

CREATE TABLE IF NOT EXISTS loyalty (
    tenant_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    points REAL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, key)
);

CREATE TABLE IF NOT EXISTS categories (
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    code TEXT NOT NULL,
    discount_type TEXT NOT NULL DEFAULT 'percent',  -- 'percent' | 'fixed'
    discount_value INTEGER NOT NULL,                -- % (1-100) or so'm
    max_uses INTEGER DEFAULT 0,                     -- 0 = unlimited
    used_count INTEGER DEFAULT 0,
    expires_at TEXT,                                -- ISO date or NULL
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_promo_tenant
    ON promo_codes(tenant_id, is_active);

CREATE TABLE IF NOT EXISTS feedback_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL,
    tenant_id TEXT NOT NULL,
    role TEXT NOT NULL,        -- 'user' | 'ai' | 'admin'
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_msgs
    ON feedback_messages(tenant_id, feedback_id, id);
"""

# Idempotent column-level migrations. Run after the main schema so newly added
# columns get applied to existing databases without dropping data.
_MIGRATIONS = [
    ("orders", "items_json",   "TEXT"),
    ("orders", "discount",     "INTEGER DEFAULT 0"),
    ("orders", "promo_code",   "TEXT"),
    # Building details + notes (matches Mini Food checkout fields).
    ("orders", "note",         "TEXT"),   # restaurant-facing note ("less mayo")
    ("orders", "courier_note", "TEXT"),   # courier-facing note (delivery instructions)
    ("orders", "entrance",     "TEXT"),   # podyez
    ("orders", "intercom",     "TEXT"),   # domofon
    ("orders", "apartment",    "TEXT"),   # xonadon
    ("orders", "floor",        "TEXT"),   # qavat
    # Feedback dashboard: classification + AI reply + status + username cache.
    ("feedback", "username",    "TEXT"),
    ("feedback", "category",    "TEXT DEFAULT 'question'"),
    ("feedback", "ai_response", "TEXT"),
    ("feedback", "status",      "TEXT DEFAULT 'open'"),
    # Branch open/closed manual override (NULL = use hours schedule, 1 = forced open, 0 = forced closed).
    ("branches", "is_open",     "INTEGER DEFAULT 1"),
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class Database:
    """Per-tenant async SQLite wrapper.

    Each tenant gets its own file under DATA_DIR/<tenant_id>.db. Tenant_id is still
    stored on every row so a single file could later host multiple tenants if needed.
    """

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.path: Path = DATA_DIR / f"{tenant_id}.db"
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the connection and ensure schema exists."""
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        # Apply per-column migrations (idempotent: ignore "duplicate column" errors).
        for table, col, decl in _MIGRATIONS:
            try:
                await self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            except Exception:  # noqa: BLE001 — column already exists
                pass
        await self._conn.commit()
        logger.info("DB ready for tenant %s at %s", self.tenant_id, self.path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected; call connect() first")
        return self._conn

    # ------------------------------------------------------------------ users

    async def upsert_user(self, user_id: int, name: str, username: str | None) -> None:
        """Insert a new user or update last_seen for an existing one."""
        now = _now()
        await self.conn.execute(
            """
            INSERT INTO users (id, tenant_id, name, username, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id, tenant_id) DO UPDATE SET
                name=excluded.name,
                username=excluded.username,
                last_seen=excluded.last_seen
            """,
            (user_id, self.tenant_id, name, username, now, now),
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        """Return the user row for this tenant or None."""
        async with self.conn.execute(
            "SELECT * FROM users WHERE id=? AND tenant_id=?",
            (user_id, self.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def set_language(self, user_id: int, language: str) -> None:
        await self.conn.execute(
            "UPDATE users SET language=? WHERE id=? AND tenant_id=?",
            (language, user_id, self.tenant_id),
        )
        await self.conn.commit()

    async def set_phone(self, user_id: int, phone: str) -> None:
        await self.conn.execute(
            "UPDATE users SET phone=? WHERE id=? AND tenant_id=?",
            (phone, user_id, self.tenant_id),
        )
        await self.conn.commit()

    async def set_user_branch(self, user_id: int, branch_id: int) -> None:
        await self.conn.execute(
            "UPDATE users SET branch_id=? WHERE id=? AND tenant_id=?",
            (branch_id, user_id, self.tenant_id),
        )
        await self.conn.commit()

    async def count_users(self) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE tenant_id=?", (self.tenant_id,)
        ) as cur:
            row = await cur.fetchone()
            return int(row["n"]) if row else 0

    async def count_new_users_today(self) -> int:
        cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE tenant_id=? AND created_at LIKE ?",
            (self.tenant_id, f"{cutoff}%"),
        ) as cur:
            row = await cur.fetchone()
            return int(row["n"]) if row else 0

    # --------------------------------------------------------------- messages

    async def save_message(self, user_id: int, role: str, content: str) -> None:
        """Persist a single message (role = 'user' | 'assistant')."""
        await self.conn.execute(
            "INSERT INTO messages (tenant_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (self.tenant_id, user_id, role, content, _now()),
        )
        await self.conn.commit()

    async def get_history(self, user_id: int, limit: int) -> list[dict[str, str]]:
        """Return last `limit` messages for the user, oldest-first, in Anthropic format."""
        async with self.conn.execute(
            """
            SELECT role, content FROM messages
            WHERE tenant_id=? AND user_id=?
            ORDER BY id DESC LIMIT ?
            """,
            (self.tenant_id, user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def count_messages_since(self, since: datetime) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE tenant_id=? AND created_at>=?",
            (self.tenant_id, since.isoformat(timespec="seconds")),
        ) as cur:
            row = await cur.fetchone()
            return int(row["n"]) if row else 0

    async def message_stats(self) -> dict[str, int]:
        """Return total / today / this-week message counts."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        week = today - timedelta(days=7)
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE tenant_id=?", (self.tenant_id,)
        ) as cur:
            row = await cur.fetchone()
            total = int(row["n"]) if row else 0
        return {
            "total": total,
            "today": await self.count_messages_since(today),
            "week": await self.count_messages_since(week),
        }

    async def top_users_by_messages(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return the most active users (proxy for 'top topics')."""
        async with self.conn.execute(
            """
            SELECT m.user_id, u.name, u.username, COUNT(*) AS n
            FROM messages m LEFT JOIN users u
                ON u.id=m.user_id AND u.tenant_id=m.tenant_id
            WHERE m.tenant_id=? AND m.role='user'
            GROUP BY m.user_id
            ORDER BY n DESC LIMIT ?
            """,
            (self.tenant_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------------- orders

    async def create_order(
        self,
        user_id: int,
        full_name: str,
        phone: str,
        service: str,
        preferred_time: str,
        branch: str = "",
        address: str = "",
        payment_method: str = "cash",
        amount: int = 0,
        items_json: str = "",
        discount: int = 0,
        promo_code: str = "",
        note: str = "",
        courier_note: str = "",
        entrance: str = "",
        intercom: str = "",
        apartment: str = "",
        floor: str = "",
    ) -> int:
        """Insert a new pending order and return its id."""
        cur = await self.conn.execute(
            """
            INSERT INTO orders
                (tenant_id, user_id, full_name, phone, service, branch, address,
                 preferred_time, payment_method, payment_status, amount, status,
                 items_json, discount, promo_code,
                 note, courier_note, entrance, intercom, apartment, floor,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid', ?, 'pending', ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?)
            """,
            (self.tenant_id, user_id, full_name, phone, service, branch, address,
             preferred_time, payment_method, amount, items_json, discount, promo_code,
             note, courier_note, entrance, intercom, apartment, floor,
             _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def recent_user_orders(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Return a user's most recent orders (any status), newest first."""
        async with self.conn.execute(
            """SELECT * FROM orders WHERE tenant_id=? AND user_id=?
               ORDER BY id DESC LIMIT ?""",
            (self.tenant_id, user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_product(
        self, product_id: int,
        name: str | None = None,
        price: str | None = None,
        description: str | None = None,
        category: str | None = None,
        image_url: str | None = None,
    ) -> bool:
        """Patch any subset of product fields. Auto-recomputes price_value."""
        import re
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name=?"); params.append(name)
        if price is not None:
            updates.append("price=?"); params.append(price)
            digits = re.sub(r"\D", "", price)
            updates.append("price_value=?"); params.append(int(digits) if digits else 0)
        if description is not None:
            updates.append("description=?"); params.append(description)
        if category is not None:
            updates.append("category=?"); params.append(category)
        if image_url is not None:
            updates.append("image_url=?"); params.append(image_url)
        if not updates:
            return False
        params.extend([product_id, self.tenant_id])
        cur = await self.conn.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id=? AND tenant_id=?",
            params,
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_courier_info(
        self, order_id: int,
        name: str = "", phone: str = "", car: str = "", eta: int | None = None,
    ) -> bool:
        cur = await self.conn.execute(
            """UPDATE orders SET courier_name=?, courier_phone=?, courier_car=?,
               eta_minutes=? WHERE id=? AND tenant_id=?""",
            (name, phone, car, eta, order_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_order_status(self, order_id: int, status: str) -> bool:
        cur = await self.conn.execute(
            "UPDATE orders SET status=? WHERE id=? AND tenant_id=?",
            (status, order_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def get_order(self, order_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM orders WHERE id=? AND tenant_id=?",
            (order_id, self.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def list_orders(
        self, status: str | None = None, limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return all orders (newest-first), optionally filtered by status."""
        if status:
            q = ("SELECT * FROM orders WHERE tenant_id=? AND status=? "
                 "ORDER BY id DESC LIMIT ?")
            args = (self.tenant_id, status, limit)
        else:
            q = "SELECT * FROM orders WHERE tenant_id=? ORDER BY id DESC LIMIT ?"
            args = (self.tenant_id, limit)
        async with self.conn.execute(q, args) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def pending_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM orders WHERE tenant_id=? AND status='pending' ORDER BY id DESC LIMIT ?",
            (self.tenant_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def recent_orders(self, limit: int = 5) -> list[dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM orders WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
            (self.tenant_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------- products

    async def list_products(self, active_only: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM products WHERE tenant_id=?"
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY position, id"
        async with self.conn.execute(q, (self.tenant_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def add_product(
        self,
        name: str,
        price: str,
        description: str = "",
        category: str = "",
        image_url: str = "",
        price_value: int | None = None,
    ) -> int:
        async with self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM products WHERE tenant_id=?",
            (self.tenant_id,),
        ) as cur:
            row = await cur.fetchone()
            pos = int(row["p"]) if row else 1
        if price_value is None:
            import re
            digits = re.sub(r"\D", "", price or "")
            price_value = int(digits) if digits else 0
        cur = await self.conn.execute(
            """INSERT INTO products
               (tenant_id, name, price, price_value, description, category, image_url, position, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (self.tenant_id, name, price, price_value, description, category, image_url, pos, _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def list_categories(self) -> list[str]:
        """Return all known categories: union of registered categories and
        distinct categories actually used by active products. Ordered by
        registry position when available, else by first product position."""
        # 1. Registered (standalone) categories.
        async with self.conn.execute(
            "SELECT name, position FROM categories WHERE tenant_id=? ORDER BY position, name",
            (self.tenant_id,),
        ) as cur:
            registered_rows = await cur.fetchall()
        registered = [(r["name"], int(r["position"] or 0)) for r in registered_rows]
        registered_names = {n for n, _ in registered}

        # 2. Categories used by products that aren't yet in the registry.
        async with self.conn.execute(
            """SELECT category, MIN(position) AS p FROM products
               WHERE tenant_id=? AND is_active=1 AND category IS NOT NULL AND category != ''
               GROUP BY category ORDER BY p""",
            (self.tenant_id,),
        ) as cur:
            product_rows = await cur.fetchall()
        from_products = [(r["category"], 1000 + int(r["p"] or 0))
                          for r in product_rows if r["category"] not in registered_names]

        all_cats = registered + from_products
        all_cats.sort(key=lambda x: x[1])
        return [n for n, _ in all_cats]

    async def add_category(self, name: str) -> bool:
        """Register a standalone category (no products yet). Returns True if newly
        added, False if it already existed."""
        try:
            await self.conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM categories WHERE tenant_id=?",
                (self.tenant_id,),
            )
            async with self.conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM categories WHERE tenant_id=?",
                (self.tenant_id,),
            ) as cur:
                row = await cur.fetchone()
                pos = int(row["p"]) if row else 1
            cur = await self.conn.execute(
                "INSERT OR IGNORE INTO categories (tenant_id, name, position, created_at) VALUES (?, ?, ?, ?)",
                (self.tenant_id, name, pos, _now()),
            )
            await self.conn.commit()
            return cur.rowcount > 0
        except Exception:  # noqa: BLE001
            return False

    async def delete_category_registry(self, name: str) -> None:
        """Remove a category from the registry (does NOT touch products)."""
        await self.conn.execute(
            "DELETE FROM categories WHERE tenant_id=? AND name=?",
            (self.tenant_id, name),
        )
        await self.conn.commit()

    async def list_products_by_category(self, category: str) -> list[dict[str, Any]]:
        async with self.conn.execute(
            """SELECT * FROM products WHERE tenant_id=? AND is_active=1 AND category=?
               ORDER BY position, id""",
            (self.tenant_id, category),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def delete_product(self, product_id: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE products SET is_active=0 WHERE id=? AND tenant_id=?",
            (product_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def get_product(self, product_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM products WHERE id=? AND tenant_id=?",
            (product_id, self.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    # --------------------------------------------------------------- branches

    async def list_branches(self, active_only: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM branches WHERE tenant_id=?"
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY position, id"
        async with self.conn.execute(q, (self.tenant_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_branch(self, branch_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM branches WHERE id=? AND tenant_id=?",
            (branch_id, self.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def add_branch(
        self,
        name: str,
        address: str,
        phone: str = "",
        lat: float | None = None,
        lon: float | None = None,
        maps_url: str = "",
        hours_json: str = "",
    ) -> int:
        async with self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM branches WHERE tenant_id=?",
            (self.tenant_id,),
        ) as cur:
            row = await cur.fetchone()
            pos = int(row["p"]) if row else 1
        cur = await self.conn.execute(
            """INSERT INTO branches
               (tenant_id, name, address, phone, lat, lon, maps_url, hours_json, position, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (self.tenant_id, name, address, phone, lat, lon, maps_url, hours_json, pos, _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def delete_branch(self, branch_id: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE branches SET is_active=0 WHERE id=? AND tenant_id=?",
            (branch_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_branch_open(self, branch_id: int, is_open: bool) -> bool:
        cur = await self.conn.execute(
            "UPDATE branches SET is_open=? WHERE id=? AND tenant_id=?",
            (1 if is_open else 0, branch_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def update_branch(
        self,
        branch_id: int,
        name: str,
        address: str,
        phone: str = "",
        lat: float | None = None,
        lon: float | None = None,
        maps_url: str = "",
        hours_json: str = "",
    ) -> bool:
        cur = await self.conn.execute(
            """UPDATE branches
               SET name=?, address=?, phone=?, lat=?, lon=?, maps_url=?, hours_json=?
               WHERE id=? AND tenant_id=?""",
            (name, address, phone, lat, lon, maps_url, hours_json, branch_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    # --------------------------------------------------------------- addresses

    async def list_addresses(self, user_id: int) -> list[dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM addresses WHERE tenant_id=? AND user_id=? AND is_active=1 ORDER BY id",
            (self.tenant_id, user_id),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def add_address(
        self, user_id: int, text: str, label: str = "",
        lat: float | None = None, lon: float | None = None,
    ) -> int:
        cur = await self.conn.execute(
            """INSERT INTO addresses (tenant_id, user_id, label, text, lat, lon, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (self.tenant_id, user_id, label, text, lat, lon, _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def delete_address(self, addr_id: int, user_id: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE addresses SET is_active=0 WHERE id=? AND tenant_id=? AND user_id=?",
            (addr_id, self.tenant_id, user_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------------- feedback

    async def add_feedback(
        self, user_id: int, content: str,
        username: str = "", category: str = "question",
        ai_response: str = "",
    ) -> int:
        """Create a feedback record with classification + (optional) AI draft reply."""
        cur = await self.conn.execute(
            """INSERT INTO feedback
                 (tenant_id, user_id, content, username, category, ai_response, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
            (self.tenant_id, user_id, content, username, category, ai_response, _now()),
        )
        await self.conn.commit()
        fb_id = int(cur.lastrowid)
        # Seed the message thread with the original user message + AI draft.
        await self.add_feedback_message(fb_id, "user", content)
        if ai_response:
            await self.add_feedback_message(fb_id, "ai", ai_response)
        return fb_id

    async def list_feedback(
        self, category: str | None = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return all feedback (newest-first), optionally filtered by category."""
        if category:
            q = ("SELECT * FROM feedback WHERE tenant_id=? AND category=? "
                 "ORDER BY id DESC LIMIT ?")
            args = (self.tenant_id, category, limit)
        else:
            q = "SELECT * FROM feedback WHERE tenant_id=? ORDER BY id DESC LIMIT ?"
            args = (self.tenant_id, limit)
        async with self.conn.execute(q, args) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_feedback(self, fb_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM feedback WHERE id=? AND tenant_id=?",
            (fb_id, self.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def feedback_counts_by_category(self) -> dict[str, int]:
        async with self.conn.execute(
            """SELECT category, COUNT(*) AS n FROM feedback
               WHERE tenant_id=? GROUP BY category""",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        return {r["category"] or "question": int(r["n"]) for r in rows}

    async def set_feedback_status(self, fb_id: int, status: str) -> None:
        await self.conn.execute(
            "UPDATE feedback SET status=? WHERE id=? AND tenant_id=?",
            (status, fb_id, self.tenant_id),
        )
        await self.conn.commit()

    async def add_feedback_message(
        self, feedback_id: int, role: str, content: str,
    ) -> int:
        cur = await self.conn.execute(
            """INSERT INTO feedback_messages
                 (feedback_id, tenant_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (feedback_id, self.tenant_id, role, content, _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def list_feedback_messages(self, feedback_id: int) -> list[dict[str, Any]]:
        async with self.conn.execute(
            """SELECT * FROM feedback_messages
               WHERE tenant_id=? AND feedback_id=? ORDER BY id""",
            (self.tenant_id, feedback_id),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # Kept for backwards compat: old code that expected a flat list still works.
    async def recent_feedback(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.list_feedback(limit=limit)

    # ----------------------------------------------------------------- loyalty

    async def get_points(self, user_id: int) -> float:
        async with self.conn.execute(
            "SELECT points FROM loyalty WHERE tenant_id=? AND user_id=?",
            (self.tenant_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return float(row["points"]) if row else 0.0

    async def add_points(self, user_id: int, amount: float) -> float:
        await self.conn.execute(
            """INSERT INTO loyalty (tenant_id, user_id, points, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                 points = points + excluded.points, updated_at = excluded.updated_at""",
            (self.tenant_id, user_id, amount, _now()),
        )
        await self.conn.commit()
        return await self.get_points(user_id)

    # ---------------------------------------------------------- tenant_settings

    async def get_setting(self, key: str, default: str = "") -> str:
        async with self.conn.execute(
            "SELECT value FROM tenant_settings WHERE tenant_id=? AND key=?",
            (self.tenant_id, key),
        ) as cur:
            row = await cur.fetchone()
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """INSERT INTO tenant_settings (tenant_id, key, value, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tenant_id, key) DO UPDATE SET
                 value=excluded.value, updated_at=excluded.updated_at""",
            (self.tenant_id, key, value, _now()),
        )
        await self.conn.commit()

    async def all_settings(self) -> dict[str, str]:
        async with self.conn.execute(
            "SELECT key, value FROM tenant_settings WHERE tenant_id=?",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    async def count_products(self) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM products WHERE tenant_id=? AND is_active=1",
            (self.tenant_id,),
        ) as cur:
            row = await cur.fetchone()
            return int(row["n"]) if row else 0

    # ------------------------------------------------------------- promo codes

    async def list_promos(self) -> list[dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM promo_codes WHERE tenant_id=? ORDER BY id DESC",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def add_promo(
        self, code: str, discount_type: str, discount_value: int,
        max_uses: int = 0, expires_at: str = "",
    ) -> int:
        cur = await self.conn.execute(
            """INSERT INTO promo_codes
               (tenant_id, code, discount_type, discount_value, max_uses,
                used_count, expires_at, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, 1, ?)""",
            (self.tenant_id, code.strip().upper(), discount_type, discount_value,
             max_uses, expires_at or None, _now()),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def get_promo(self, code: str) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM promo_codes WHERE tenant_id=? AND code=? AND is_active=1",
            (self.tenant_id, code.strip().upper()),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def increment_promo_use(self, code: str) -> None:
        await self.conn.execute(
            """UPDATE promo_codes SET used_count = used_count + 1
               WHERE tenant_id=? AND code=?""",
            (self.tenant_id, code.strip().upper()),
        )
        await self.conn.commit()

    async def delete_promo(self, promo_id: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE promo_codes SET is_active=0 WHERE id=? AND tenant_id=?",
            (promo_id, self.tenant_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    # -------------------------------------------------------------- analytics

    async def revenue_summary(self) -> dict[str, int]:
        """Aggregate revenue for confirmed/pending orders: total, today, week."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        week  = today - timedelta(days=7)
        out: dict[str, int] = {}
        # Count cancelled separately — they don't add to revenue.
        async with self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS s, COUNT(*) AS n
               FROM orders WHERE tenant_id=? AND status != 'cancelled'""",
            (self.tenant_id,),
        ) as cur:
            r = await cur.fetchone()
            out["total_revenue"] = int(r["s"] or 0)
            out["total_orders"]  = int(r["n"] or 0)
        async with self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS s, COUNT(*) AS n
               FROM orders WHERE tenant_id=? AND status != 'cancelled' AND created_at>=?""",
            (self.tenant_id, today.isoformat(timespec="seconds")),
        ) as cur:
            r = await cur.fetchone()
            out["today_revenue"] = int(r["s"] or 0)
            out["today_orders"]  = int(r["n"] or 0)
        async with self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS s, COUNT(*) AS n
               FROM orders WHERE tenant_id=? AND status != 'cancelled' AND created_at>=?""",
            (self.tenant_id, week.isoformat(timespec="seconds")),
        ) as cur:
            r = await cur.fetchone()
            out["week_revenue"] = int(r["s"] or 0)
            out["week_orders"]  = int(r["n"] or 0)
        return out

    async def daily_revenue(self, days: int = 7) -> list[dict[str, Any]]:
        """Per-day revenue/order count for the last N days, oldest-first."""
        async with self.conn.execute(
            """SELECT substr(created_at, 1, 10) AS day,
                      COALESCE(SUM(amount), 0)   AS revenue,
                      COUNT(*)                    AS count
               FROM orders
               WHERE tenant_id=? AND status != 'cancelled'
                 AND created_at >= ?
               GROUP BY day ORDER BY day""",
            (self.tenant_id,
             (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat(timespec="seconds")),
        ) as cur:
            rows = await cur.fetchall()
        return [{"day": r["day"], "revenue": int(r["revenue"]), "count": int(r["count"])} for r in rows]

    async def top_products(self, limit: int = 5) -> list[dict[str, Any]]:
        """Aggregate product counts from items_json across all non-cancelled orders."""
        import json as _json
        counts: dict[str, int] = {}
        async with self.conn.execute(
            """SELECT items_json FROM orders
               WHERE tenant_id=? AND status != 'cancelled' AND items_json IS NOT NULL AND items_json != ''""",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        for r in rows:
            try:
                items = _json.loads(r["items_json"])
            except (_json.JSONDecodeError, TypeError, ValueError):
                continue
            for it in items or []:
                name = it.get("name") or ""
                qty = int(it.get("qty") or 0)
                if name and qty:
                    counts[name] = counts.get(name, 0) + qty
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"name": n, "qty": q} for n, q in ranked]

    async def peak_hours(self) -> list[int]:
        """Return order counts per hour-of-day (24 values, index 0..23)."""
        buckets = [0] * 24
        async with self.conn.execute(
            """SELECT substr(created_at, 12, 2) AS hh
               FROM orders WHERE tenant_id=? AND status != 'cancelled'""",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        for r in rows:
            try:
                h = int(r["hh"])
                if 0 <= h < 24:
                    buckets[h] += 1
            except (TypeError, ValueError):
                continue
        return buckets

    async def count_orders_by_status(self) -> dict[str, int]:
        async with self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM orders WHERE tenant_id=? GROUP BY status",
            (self.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
        return {r["status"]: int(r["n"]) for r in rows}
