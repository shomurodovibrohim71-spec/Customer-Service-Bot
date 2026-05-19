"""Seed products + branches from tenant config into the DB on first run."""
from __future__ import annotations

import json
import logging

from core.database import Database
from core.tenant import Tenant

logger = logging.getLogger(__name__)


async def seed_tenant(db: Database, tenant: Tenant) -> None:
    """If products/branches tables are empty for this tenant, copy from config."""
    existing_products = await db.list_products(active_only=False)
    existing_names = {p["name"] for p in existing_products}
    seeded = 0
    for p in tenant.get("services", []):
        if p["name"] not in existing_names:
            await db.add_product(
                name=p["name"],
                price=p.get("price", ""),
                description=p.get("description", ""),
                category=p.get("category", ""),
                image_url=p.get("image_url", ""),
                price_value=p.get("price_value"),
            )
            existing_names.add(p["name"])
            seeded += 1
    if seeded:
        logger.info("[%s] seeded %d new products", tenant.id, seeded)

    # Seed the standalone-categories registry from config so the admin sees
    # categories even when there are no products in them.
    for cat in tenant.get("categories", []):
        await db.add_category(cat)

    existing_branches = await db.list_branches(active_only=False)
    if not existing_branches:
        for b in tenant.get("branches", []):
            await db.add_branch(
                name=b["name"],
                address=b.get("address", ""),
                phone=b.get("phone", ""),
                lat=b.get("lat"),
                lon=b.get("lon"),
                maps_url=b.get("maps_url", ""),
                hours_json=json.dumps(b.get("hours", {}), ensure_ascii=False),
            )
        logger.info("[%s] seeded %d branches", tenant.id, len(tenant.get("branches", [])))
