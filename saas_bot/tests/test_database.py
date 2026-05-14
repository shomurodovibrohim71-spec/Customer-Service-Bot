"""Database round-trip tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_user_upsert_phone_language(tmp_data_dir):
    from core.database import Database
    db = Database("t")
    await db.connect()
    try:
        await db.upsert_user(1, "Alice", "alice")
        await db.set_language(1, "uz")
        await db.set_phone(1, "+998901234567")
        row = await db.get_user(1)
        assert row["language"] == "uz"
        assert row["phone"] == "+998901234567"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_products_crud(tmp_data_dir):
    from core.database import Database
    db = Database("t")
    await db.connect()
    try:
        p1 = await db.add_product("Burger", "35,000", "tasty")
        p2 = await db.add_product("Pizza", "75,000", "italian")
        active = await db.list_products()
        assert len(active) == 2
        assert await db.delete_product(p1)
        assert (await db.count_products()) == 1
        # Soft-deleted ones excluded from list:
        assert all(p["id"] != p1 for p in await db.list_products())
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_branches_crud(tmp_data_dir):
    from core.database import Database
    db = Database("t")
    await db.connect()
    try:
        b1 = await db.add_branch(
            name="Main", address="Tashkent 1", phone="+998",
            lat=41.0, lon=69.0, maps_url="https://maps", hours_json='{"mon":"9-18"}',
        )
        all_b = await db.list_branches()
        assert len(all_b) == 1
        got = await db.get_branch(b1)
        assert got["name"] == "Main" and got["lat"] == 41.0
        assert await db.delete_branch(b1)
        assert (await db.list_branches()) == []
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_order_with_branch_and_address(tmp_data_dir):
    from core.database import Database
    db = Database("t")
    await db.connect()
    try:
        oid = await db.create_order(
            user_id=1, full_name="A", phone="+998",
            service="Burger", preferred_time="19:00",
            branch="Main", address="Yunusobod 5",
        )
        order = await db.get_order(oid)
        assert order["branch"] == "Main" and order["address"] == "Yunusobod 5"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_message_history(tmp_data_dir):
    from core.database import Database
    db = Database("t")
    await db.connect()
    try:
        await db.upsert_user(1, "A", "a")
        await db.save_message(1, "user", "hi")
        await db.save_message(1, "assistant", "hello")
        history = await db.get_history(1, 10)
        assert [m["role"] for m in history] == ["user", "assistant"]
    finally:
        await db.close()
