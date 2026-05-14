"""FastAPI: admin REST API + Telegram Mini App for the order flow.

Run with:
    uvicorn api.server:app --host 0.0.0.0 --port 8080

Then expose via cloudflared:
    cloudflared tunnel --url http://localhost:8080

Set the resulting HTTPS URL in `.env` as WEBAPP_URL so the bot can serve the
WebApp button.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import BASE_DIR
from core.database import Database
from core.initdata import verify_init_data
from core.tenant import Tenant, load_tenants

logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("API_TOKEN", "")

_tenants: dict[str, Tenant] = {}
_dbs: dict[str, Database] = {}
WEBAPP_DIR = BASE_DIR / "webapp"


@asynccontextmanager
async def lifespan(_: FastAPI):
    tenants = load_tenants(BASE_DIR / "config" / "tenants")
    for t in tenants:
        _tenants[t.id] = t
        db = Database(t.id)
        await db.connect()
        _dbs[t.id] = db
    logger.info("API ready with %d tenants", len(_tenants))
    yield
    for db in _dbs.values():
        await db.close()


app = FastAPI(title="SaaS Bot API + WebApp", version="2.0.0", lifespan=lifespan)

# Static frontend files at /static/*
if WEBAPP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")


# WebApp HTMLs must never be cached — Telegram WebView keeps stale copies for
# hours otherwise, so language switches and JS updates don't reach the user.
_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _webapp_file(name: str) -> FileResponse:
    path = WEBAPP_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(str(path), headers=_NO_CACHE)


# =========================================================== Admin auth API

def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="API_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization.split(" ", 1)[1].strip() != API_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")


def get_tenant(tenant_id: str) -> Tenant:
    tenant = _tenants.get(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    return tenant


def get_db(tenant_id: str) -> Database:
    db = _dbs.get(tenant_id)
    if db is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    return db


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "tenants": len(_tenants), "webapp": WEBAPP_DIR.exists()}


# =================================================== Telegram WebApp (Mini App)

@app.get("/webapp")
async def webapp_index() -> FileResponse:
    index = WEBAPP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="webapp not built")
    return FileResponse(str(index))


@app.get("/webapp/branches")
async def webapp_branches() -> FileResponse:
    index = WEBAPP_DIR / "branches.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="branches page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/products")
async def webapp_admin_products() -> FileResponse:
    index = WEBAPP_DIR / "admin-products.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin products page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/stats")
async def webapp_admin_stats() -> FileResponse:
    index = WEBAPP_DIR / "admin-stats.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin stats page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/promos")
async def webapp_admin_promos() -> FileResponse:
    index = WEBAPP_DIR / "admin-promos.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin promos page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/company")
async def webapp_admin_company() -> FileResponse:
    index = WEBAPP_DIR / "admin-company.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin company page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/feedback")
async def webapp_admin_feedback() -> FileResponse:
    index = WEBAPP_DIR / "admin-feedback.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin feedback page not built")
    return FileResponse(str(index))


@app.get("/webapp/admin/orders")
async def webapp_admin_orders() -> FileResponse:
    index = WEBAPP_DIR / "admin-orders.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="admin orders page not built")
    return FileResponse(str(index))


def _check_admin(tenant: Tenant, init_data: str, fallback_uid: int | None) -> int:
    """Resolve current user_id from either initData (preferred) or URL uid fallback,
    then verify they are an admin for this tenant. Returns the user_id or raises 401/403."""
    uid = 0
    if init_data:
        parsed = verify_init_data(init_data, tenant.bot_token)
        if parsed:
            user = parsed.get("user") or {}
            uid = int(user.get("id") or 0)
    if not uid and fallback_uid:
        uid = int(fallback_uid)
    if not uid:
        raise HTTPException(status_code=401, detail="missing user id")
    if not tenant.is_admin(uid):
        raise HTTPException(status_code=403, detail="not an admin")
    return uid


class AdminQuery(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str


class AdminProductIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    id: int | None = None
    name: str
    category: str
    price_value: int
    description: str = ""
    image_url: str = ""


@app.get("/api/admin/products")
async def api_admin_products_list(
    tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    products = await db.list_products()
    categories = await db.list_categories()
    return {
        "products": [{
            "id": p["id"], "name": p["name"],
            "category": p.get("category") or "",
            "price": p.get("price", ""),
            "price_value": int(p.get("price_value") or 0),
            "description": p.get("description") or "",
            "image_url": p.get("image_url") or "",
        } for p in products],
        "categories": categories,
    }


@app.post("/api/admin/products")
async def api_admin_products_create(payload: AdminProductIn) -> dict[str, Any]:
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    price_str = f"{payload.price_value:,} so'm"
    pid = await db.add_product(
        name=payload.name, price=price_str, description=payload.description,
        category=payload.category, image_url=payload.image_url,
        price_value=payload.price_value,
    )
    return {"ok": True, "id": pid}


@app.put("/api/admin/products/{product_id}")
async def api_admin_products_update(product_id: int, payload: AdminProductIn) -> dict[str, Any]:
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    price_str = f"{payload.price_value:,} so'm"
    await db.update_product(
        product_id,
        name=payload.name, price=price_str, description=payload.description,
        category=payload.category, image_url=payload.image_url,
    )
    return {"ok": True}


@app.delete("/api/admin/products/{product_id}")
async def api_admin_products_delete(product_id: int, payload: AdminQuery) -> dict[str, Any]:
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    ok = await db.delete_product(product_id)
    return {"ok": ok}


@app.get("/api/admin/categories")
async def api_admin_categories(
    tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    """Return all categories (registered + used by products) with product counts."""
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    all_cats = await db.list_categories()  # union: registry + product distinct
    products = await db.list_products()
    counts: dict[str, int] = {}
    for p in products:
        cat = p.get("category") or ""
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return {"categories": [{"name": c, "count": counts.get(c, 0)} for c in all_cats]}


class AdminCategoryIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    name: str


@app.post("/api/admin/categories")
async def api_admin_category_add(payload: AdminCategoryIn) -> dict[str, Any]:
    """Register a new standalone category."""
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="empty name")
    added = await db.add_category(name)
    return {"ok": True, "added": added}


@app.post("/api/admin/categories/delete")
async def api_admin_category_delete(payload: AdminCategoryIn) -> dict[str, Any]:
    """Delete a category from the registry AND soft-delete every product in it."""
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    prods = await db.list_products_by_category(payload.name)
    for p in prods:
        await db.delete_product(p["id"])
    await db.delete_category_registry(payload.name)
    return {"ok": True, "deleted": len(prods)}


@app.get("/api/branches")
async def api_branches(tenant_id: str = Query(..., alias="tenant")) -> dict[str, Any]:
    """Public read-only: full branch info incl. hours, phone, maps URL."""
    import json as _json
    db = get_db(tenant_id)
    rows = await db.list_branches()
    branches = []
    for b in rows:
        hours: Any = b.get("hours_json") or {}
        if isinstance(hours, str):
            try:
                hours = _json.loads(hours)
            except (_json.JSONDecodeError, ValueError):
                hours = {}
        branches.append({
            "id": b["id"], "name": b["name"], "address": b.get("address", ""),
            "phone": b.get("phone", ""), "lat": b.get("lat"), "lon": b.get("lon"),
            "maps_url": b.get("maps_url", ""), "hours": hours,
        })
    return {"tenant_id": tenant_id, "branches": branches}


def _resolve_tenant_by_token_from_init(init_data_str: str) -> Tenant | None:
    """Verify initData against each tenant's bot_token. First match wins."""
    for t in _tenants.values():
        ok = verify_init_data(init_data_str, t.bot_token)
        if ok is not None:
            return t
    return None


@app.get("/api/reverse-geocode")
async def api_reverse_geocode(
    lat: float = Query(...),
    lon: float = Query(...),
    lang: str = Query("uz"),
) -> dict[str, Any]:
    """Convert lat/lon to a human-readable address (Nominatim)."""
    from core.geocoder import reverse_geocode
    addr = await reverse_geocode(lat, lon, lang)
    return {"address": addr or "", "lat": lat, "lon": lon}


@app.get("/api/menu")
async def api_menu(tenant_id: str = Query(..., alias="tenant")) -> dict[str, Any]:
    """Public read-only: tenant menu grouped by category.

    No auth required (read-only and tenant_id is public). For private apps you
    can require initData here too.
    """
    db = get_db(tenant_id)
    products = await db.list_products()
    branches = await db.list_branches()
    tenant = get_tenant(tenant_id)
    # Group products by category preserving order.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in products:
        cat = p.get("category") or "Boshqalar"
        grouped.setdefault(cat, []).append({
            "id": p["id"], "name": p["name"], "price": p.get("price", ""),
            "price_value": int(p.get("price_value") or 0),
            "description": p.get("description") or "",
            "image_url": p.get("image_url") or "",
        })
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "categories": list(grouped.keys()),
        "products": grouped,
        "branches": [
            {"id": b["id"], "name": b["name"], "address": b.get("address", ""),
             "lat": b.get("lat"), "lon": b.get("lon")}
            for b in branches
        ],
    }


class OrderItem(BaseModel):
    product_id: int
    qty: int


class OrderIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    branch_id: int | None = None
    delivery_type: str  # 'delivery' | 'pickup'
    address: str
    address_lat: float | None = None
    address_lon: float | None = None
    preferred_time: str
    items: list[OrderItem]
    payment_method: str = "cash"  # 'cash' | 'card'
    promo_code: str = ""
    # Building details + notes (Mini Food-style checkout)
    note: str = ""           # restaurant note (e.g. "less mayo")
    courier_note: str = ""   # courier note (e.g. "leave at door")
    entrance: str = ""       # podyez
    intercom: str = ""       # domofon
    apartment: str = ""      # xonadon
    floor: str = ""          # qavat


# ============================================================ Order history
def _resolve_user(tenant: Tenant, init_data: str, fallback_uid: int | None) -> int:
    """Return user_id from initData HMAC or fallback uid. Raises 401 if neither."""
    if init_data:
        parsed = verify_init_data(init_data, tenant.bot_token)
        if parsed:
            user = parsed.get("user") or {}
            uid = int(user.get("id") or 0)
            if uid:
                return uid
    if fallback_uid:
        return int(fallback_uid)
    raise HTTPException(status_code=401, detail="missing user id")


@app.get("/api/orders/history")
async def api_orders_history(
    tenant: str, init_data: str = "", uid: int | None = None, limit: int = 20,
) -> dict[str, Any]:
    """Return current user's recent orders (newest first), with parsed items."""
    import json as _json
    t = get_tenant(tenant)
    user_id = _resolve_user(t, init_data, uid)
    db = get_db(tenant)
    rows = await db.recent_user_orders(user_id, limit=limit)
    orders: list[dict[str, Any]] = []
    for o in rows:
        items: list[dict[str, Any]] = []
        raw = o.get("items_json") or ""
        if raw:
            try:
                items = _json.loads(raw)
            except (_json.JSONDecodeError, ValueError):
                items = []
        orders.append({
            "id": o["id"],
            "created_at": o.get("created_at", ""),
            "status": o.get("status", "pending"),
            "amount": int(o.get("amount") or 0),
            "discount": int(o.get("discount") or 0),
            "promo_code": o.get("promo_code") or "",
            "service": o.get("service") or "",
            "address": o.get("address") or "",
            "branch": o.get("branch") or "",
            "payment_method": o.get("payment_method") or "cash",
            "items": items,
        })
    return {"orders": orders}


# ========================================================== Primary address

@app.get("/api/user/primary-address")
async def api_user_primary_address(
    tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    """Return the customer's most recently saved address (used by the order
    WebApp to pre-fill the 'Shu manzilga buyurtma berilsinmi?' prompt)."""
    t = get_tenant(tenant)
    user_id = _resolve_user(t, init_data, uid)
    db = get_db(tenant)
    addrs = await db.list_addresses(user_id)
    if not addrs:
        return {"address": None}
    # Newest first — list_addresses orders by id ascending, so take last.
    a = addrs[-1]
    return {"address": {
        "id": a["id"], "text": a.get("text") or "",
        "lat": a.get("lat"), "lon": a.get("lon"),
    }}


# ============================================================ Order extend

class OrderExtendIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    order_id: int
    items: list[OrderItem]


# Same 2-minute window as self-cancel.
_USER_EXTEND_WINDOW_SECONDS = 120


@app.post("/api/orders/extend")
async def api_user_extend_order(payload: OrderExtendIn) -> dict[str, Any]:
    """Append items to a still-pending order within the 2-minute window."""
    from datetime import datetime as _dt
    import json as _json
    t = get_tenant(payload.tenant_id)
    user_id = _resolve_user(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    order = await db.get_order(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    if int(order["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="not your order")
    if order.get("status") != "pending":
        raise HTTPException(status_code=400, detail="too_late_status")
    try:
        created = _dt.fromisoformat((order.get("created_at") or "").replace("Z", ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="bad timestamp")
    elapsed = (_dt.utcnow() - created).total_seconds()
    if elapsed > _USER_EXTEND_WINDOW_SECONDS:
        raise HTTPException(status_code=400, detail="too_late_window")
    if not payload.items:
        raise HTTPException(status_code=400, detail="empty extend")

    # Re-fetch product prices server-side; never trust the client for amounts.
    products = {p["id"]: p for p in await db.list_products()}
    add_items: list[dict[str, Any]] = []
    add_amount = 0
    add_lines: list[str] = []
    for it in payload.items:
        p = products.get(it.product_id)
        if not p:
            continue
        price = int(p.get("price_value") or 0)
        add_amount += price * it.qty
        add_items.append({"product_id": it.product_id, "name": p["name"],
                          "qty": it.qty, "price": price})
        add_lines.append(f"{p['name']} × {it.qty} = {price * it.qty:,}")
    if not add_items:
        raise HTTPException(status_code=400, detail="no valid items")

    # Merge with existing items_json.
    existing_items = []
    raw = order.get("items_json") or ""
    if raw:
        try:
            existing_items = _json.loads(raw)
        except (_json.JSONDecodeError, ValueError):
            existing_items = []
    merged = existing_items + add_items
    new_amount = int(order.get("amount") or 0) + add_amount
    new_service = (order.get("service") or "") + " | + " + "; ".join(add_lines)

    # Direct update — Database has no bulk-update helper for orders.
    await db.conn.execute(
        """UPDATE orders SET items_json=?, amount=?, service=?
           WHERE id=? AND tenant_id=?""",
        (_json.dumps(merged, ensure_ascii=False), new_amount, new_service,
         payload.order_id, payload.tenant_id),
    )
    await db.conn.commit()

    # Notify admins about the supplement.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for admin_id in t.admin_ids:
                await client.post(
                    f"https://api.telegram.org/bot{t.bot_token}/sendMessage",
                    json={"chat_id": admin_id,
                          "text": (f"➕ Buyurtma #{payload.order_id} ga qo'shimcha "
                                   f"kelidi:\n" + "\n".join(add_lines) +
                                   f"\n\n💰 Yangi jami: {new_amount:,} so'm"),
                          "parse_mode": "Markdown"},
                )
    except httpx.HTTPError as exc:
        logger.warning("[%s] extend notify failed: %s", t.id, exc)
    return {"ok": True, "order_id": payload.order_id, "new_total": new_amount}


# ============================================================ Self-cancel

class UserCancelOrderIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    order_id: int


# Window during which the customer can self-cancel their order.
_USER_CANCEL_WINDOW_SECONDS = 120


@app.post("/api/orders/cancel")
async def api_user_cancel_order(payload: UserCancelOrderIn) -> dict[str, Any]:
    """Customer cancels their own order — only allowed within the first 2 minutes
    after placing it AND only while still in 'pending' status."""
    from datetime import datetime as _dt
    t = get_tenant(payload.tenant_id)
    user_id = _resolve_user(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    order = await db.get_order(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    if int(order["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="not your order")
    if order.get("status") != "pending":
        raise HTTPException(status_code=400, detail="too_late_status")
    try:
        created = _dt.fromisoformat((order.get("created_at") or "").replace("Z", ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="bad timestamp")
    elapsed = (_dt.utcnow() - created).total_seconds()
    if elapsed > _USER_CANCEL_WINDOW_SECONDS:
        raise HTTPException(status_code=400, detail="too_late_window")
    await db.set_order_status(payload.order_id, "cancelled")
    # Notify admins.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for admin_id in t.admin_ids:
                await client.post(
                    f"https://api.telegram.org/bot{t.bot_token}/sendMessage",
                    json={"chat_id": admin_id,
                          "text": f"❌ Buyurtma #{payload.order_id} mijoz tomonidan bekor qilindi (2 daq. ichida)."},
                )
    except httpx.HTTPError as exc:
        logger.warning("[%s] cancel notify failed: %s", t.id, exc)
    return {"ok": True, "elapsed": int(elapsed)}


# ============================================================== Promo codes

def _validate_promo(promo: dict[str, Any] | None, total: int) -> tuple[bool, str, int]:
    """Returns (ok, reason_or_label, discount_uzs)."""
    if not promo:
        return False, "Promokod topilmadi", 0
    if not promo.get("is_active"):
        return False, "Promokod faol emas", 0
    max_uses = int(promo.get("max_uses") or 0)
    used = int(promo.get("used_count") or 0)
    if max_uses and used >= max_uses:
        return False, "Promokod limiti tugadi", 0
    exp = promo.get("expires_at")
    if exp:
        try:
            from datetime import date
            d = date.fromisoformat(exp[:10])
            if d < date.today():
                return False, "Promokod muddati tugagan", 0
        except (TypeError, ValueError):
            pass
    dtype = promo.get("discount_type") or "percent"
    dval  = int(promo.get("discount_value") or 0)
    discount = (total * dval) // 100 if dtype == "percent" else dval
    if discount > total:
        discount = total
    label = f"-{dval}%" if dtype == "percent" else f"-{dval:,} so'm"
    return True, label, discount


class PromoCheckIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    code: str
    total: int = 0


@app.post("/api/promo/check")
async def api_promo_check(payload: PromoCheckIn) -> dict[str, Any]:
    """Validate a promo code and return the discount it would apply."""
    t = get_tenant(payload.tenant_id)
    _resolve_user(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    promo = await db.get_promo(payload.code)
    ok, msg, discount = _validate_promo(promo, payload.total)
    if not ok:
        return {"ok": False, "message": msg}
    return {
        "ok": True, "discount": discount, "label": msg,
        "discount_type": promo.get("discount_type"),
        "discount_value": int(promo.get("discount_value") or 0),
        "final": max(0, payload.total - discount),
    }


class AdminPromoIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    code: str
    discount_type: str = "percent"
    discount_value: int
    max_uses: int = 0
    expires_at: str = ""


@app.get("/api/admin/promos")
async def api_admin_promos_list(
    tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    rows = await db.list_promos()
    return {"promos": rows}


@app.post("/api/admin/promos")
async def api_admin_promos_create(payload: AdminPromoIn) -> dict[str, Any]:
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="empty code")
    if payload.discount_type not in ("percent", "fixed"):
        raise HTTPException(status_code=400, detail="bad discount_type")
    if payload.discount_value <= 0:
        raise HTTPException(status_code=400, detail="bad discount_value")
    db = get_db(payload.tenant_id)
    try:
        pid = await db.add_promo(
            code=payload.code, discount_type=payload.discount_type,
            discount_value=payload.discount_value, max_uses=payload.max_uses,
            expires_at=payload.expires_at,
        )
    except Exception as exc:  # noqa: BLE001 — unique-constraint, etc.
        raise HTTPException(status_code=400, detail=f"could not add: {exc}") from exc
    return {"ok": True, "id": pid}


class AdminPromoDeleteIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    id: int


@app.post("/api/admin/promos/delete")
async def api_admin_promos_delete(payload: AdminPromoDeleteIn) -> dict[str, Any]:
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    ok = await db.delete_promo(payload.id)
    return {"ok": ok}


# ============================================================ Company info

# Editable company-info fields. Mirrors handlers/admin_panel.py COMPANY_FIELDS.
_COMPANY_FIELDS = [
    "name", "tagline", "about", "phone", "address", "working_hours",
    "card_number", "alif_phone",
    "click_merchant_id", "click_service_id", "payme_merchant_id",
]


@app.get("/api/admin/company")
async def api_admin_company_get(
    tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    """Return all company-info fields: prefer DB tenant_settings, fall back to tenant config."""
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    out: dict[str, str] = {}
    for field in _COMPANY_FIELDS:
        val = await db.get_setting(f"company.{field}", "")
        if not val:
            val = str(t.get(field, "") or "")
        out[field] = val
    return {"fields": out}


class AdminCompanyIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    fields: dict[str, str]


@app.post("/api/admin/company")
async def api_admin_company_save(payload: AdminCompanyIn) -> dict[str, Any]:
    """Bulk-save any subset of company-info fields."""
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    saved = 0
    for k, v in (payload.fields or {}).items():
        if k not in _COMPANY_FIELDS:
            continue
        await db.set_setting(f"company.{k}", v.strip() if isinstance(v, str) else "")
        saved += 1
    return {"ok": True, "saved": saved}


# ============================================================ Feedback dashboard

@app.get("/api/admin/feedback")
async def api_admin_feedback_list(
    tenant: str, init_data: str = "", uid: int | None = None,
    category: str = "", limit: int = 100,
) -> dict[str, Any]:
    """Return feedback list (optionally filtered by category) + counts per category."""
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    cat = category.strip() or None
    if cat and cat not in ("complaint", "question", "suggestion"):
        cat = None
    rows = await db.list_feedback(category=cat, limit=limit)
    counts = await db.feedback_counts_by_category()
    # Enrich with user name + phone for display.
    items: list[dict[str, Any]] = []
    for r in rows:
        u = await db.get_user(int(r["user_id"]))
        items.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "username": r.get("username") or (u or {}).get("username") or "",
            "name": (u or {}).get("name") or "",
            "phone": (u or {}).get("phone") or "",
            "category": r.get("category") or "question",
            "status": r.get("status") or "open",
            "content": r.get("content") or "",
            "ai_response": r.get("ai_response") or "",
            "created_at": r.get("created_at") or "",
        })
    return {
        "items": items,
        "counts": {
            "complaint":  int(counts.get("complaint", 0)),
            "question":   int(counts.get("question", 0)),
            "suggestion": int(counts.get("suggestion", 0)),
            "total":      sum(int(v) for v in counts.values()),
        },
    }


@app.get("/api/admin/feedback/{fb_id}")
async def api_admin_feedback_thread(
    fb_id: int, tenant: str, init_data: str = "", uid: int | None = None,
) -> dict[str, Any]:
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    fb = await db.get_feedback(fb_id)
    if not fb:
        raise HTTPException(status_code=404, detail="feedback not found")
    u = await db.get_user(int(fb["user_id"]))
    msgs = await db.list_feedback_messages(fb_id)
    return {
        "feedback": {
            "id": fb["id"], "user_id": fb["user_id"],
            "username": fb.get("username") or (u or {}).get("username") or "",
            "name":  (u or {}).get("name") or "",
            "phone": (u or {}).get("phone") or "",
            "category": fb.get("category") or "question",
            "status": fb.get("status") or "open",
            "created_at": fb.get("created_at") or "",
        },
        "messages": [
            {"id": m["id"], "role": m["role"], "content": m["content"],
             "created_at": m["created_at"]} for m in msgs
        ],
    }


class AdminFeedbackReplyIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    feedback_id: int
    text: str


@app.post("/api/admin/feedback/reply")
async def api_admin_feedback_reply(payload: AdminFeedbackReplyIn) -> dict[str, Any]:
    """Admin replies to a feedback thread. Saves the message and sends it to the customer."""
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    db = get_db(payload.tenant_id)
    fb = await db.get_feedback(payload.feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="feedback not found")
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    await db.add_feedback_message(payload.feedback_id, "admin", text)
    await db.set_feedback_status(payload.feedback_id, "answered")
    # Forward to the customer.
    cust_lang = "uz"
    u = await db.get_user(int(fb["user_id"]))
    if u and u.get("language"):
        cust_lang = u["language"]
    prefix = {
        "uz": "📧 *Murojaatingiz bo'yicha javob:*",
        "en": "📧 *Reply to your feedback:*",
        "ru": "📧 *Ответ на ваше обращение:*",
    }.get(cust_lang, "📧 *Murojaatingiz bo'yicha javob:*")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{t.bot_token}/sendMessage",
                json={"chat_id": int(fb["user_id"]),
                      "text": f"{prefix}\n\n{text}",
                      "parse_mode": "Markdown"},
            )
    except httpx.HTTPError as exc:
        logger.warning("[%s] feedback reply send failed: %s", t.id, exc)
    return {"ok": True}


# ============================================================ Orders dashboard

@app.get("/api/admin/orders")
async def api_admin_orders_list(
    tenant: str, init_data: str = "", uid: int | None = None,
    status: str = "", limit: int = 200,
) -> dict[str, Any]:
    """Return all orders (newest-first), filtered by status if provided, plus counts."""
    import json as _json
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    st = status.strip() or None
    rows = await db.list_orders(status=st, limit=limit)
    counts = await db.count_orders_by_status()
    out: list[dict[str, Any]] = []
    for r in rows:
        items: list[dict[str, Any]] = []
        raw = r.get("items_json") or ""
        if raw:
            try:
                items = _json.loads(raw)
            except (_json.JSONDecodeError, ValueError):
                items = []
        u = await db.get_user(int(r["user_id"]))
        out.append({
            "id": r["id"], "user_id": r["user_id"],
            "username": (u or {}).get("username") or "",
            "full_name": r.get("full_name") or (u or {}).get("name") or "",
            "phone": r.get("phone") or (u or {}).get("phone") or "",
            "branch": r.get("branch") or "",
            "address": r.get("address") or "",
            "entrance": r.get("entrance") or "",
            "intercom": r.get("intercom") or "",
            "apartment": r.get("apartment") or "",
            "floor": r.get("floor") or "",
            "courier_note": r.get("courier_note") or "",
            "note": r.get("note") or "",
            "preferred_time": r.get("preferred_time") or "",
            "payment_method": r.get("payment_method") or "cash",
            "amount": int(r.get("amount") or 0),
            "discount": int(r.get("discount") or 0),
            "promo_code": r.get("promo_code") or "",
            "service": r.get("service") or "",
            "items": items,
            "status": r.get("status") or "pending",
            "created_at": r.get("created_at") or "",
        })
    total = sum(int(v) for v in counts.values())
    return {
        "orders": out,
        "counts": {
            "pending":   int(counts.get("pending", 0)),
            "confirmed": int(counts.get("confirmed", 0)),
            "delivered": int(counts.get("delivered", 0)),
            "cancelled": int(counts.get("cancelled", 0)),
            "total":     total,
        },
    }


class AdminOrderStatusIn(BaseModel):
    init_data: str = ""
    fallback_uid: int | None = None
    tenant_id: str
    order_id: int
    status: str  # 'confirmed' | 'cancelled' | 'delivered' | 'pending'


@app.post("/api/admin/orders/status")
async def api_admin_orders_status(payload: AdminOrderStatusIn) -> dict[str, Any]:
    """Admin updates an order's status. Notifies the customer in their language."""
    t = get_tenant(payload.tenant_id)
    _check_admin(t, payload.init_data, payload.fallback_uid)
    if payload.status not in ("pending", "confirmed", "delivered", "cancelled"):
        raise HTTPException(status_code=400, detail="bad status")
    db = get_db(payload.tenant_id)
    order = await db.get_order(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    await db.set_order_status(payload.order_id, payload.status)

    # Notify customer in their language (skip for 'pending').
    if payload.status != "pending":
        u = await db.get_user(int(order["user_id"]))
        cust_lang = (u or {}).get("language") or t.default_language
        amount = int(order.get("amount") or 0)
        oid = payload.order_id
        msg = {
            "confirmed": {
                "uz": f"✅ Buyurtmangiz #{oid} tasdiqlandi! 💰 Summa: {amount:,} so'm\nTez orada bog'lanamiz 🚗",
                "en": f"✅ Your order #{oid} is confirmed! 💰 Amount: {amount:,} so'm\nWe'll be in touch soon 🚗",
                "ru": f"✅ Ваш заказ #{oid} подтверждён! 💰 Сумма: {amount:,} сум\nСкоро свяжемся 🚗",
            },
            "delivered": {
                "uz": f"📦 Buyurtmangiz #{oid} yetkazildi! Yaxshi ovqatlanishingizni tilaymiz 🍔",
                "en": f"📦 Your order #{oid} has been delivered! Enjoy your meal 🍔",
                "ru": f"📦 Ваш заказ #{oid} доставлен! Приятного аппетита 🍔",
            },
            "cancelled": {
                "uz": f"❌ Buyurtmangiz #{oid} bekor qilindi.\nIltimos qayta buyurtma bering.",
                "en": f"❌ Your order #{oid} has been cancelled.\nPlease place a new order.",
                "ru": f"❌ Ваш заказ #{oid} отменён.\nПожалуйста, оформите заказ снова.",
            },
        }[payload.status].get(cust_lang)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{t.bot_token}/sendMessage",
                    json={"chat_id": int(order["user_id"]), "text": msg},
                )
        except httpx.HTTPError as exc:
            logger.warning("[%s] order status notify failed: %s", t.id, exc)
    return {"ok": True}


# ============================================================ Admin dashboard

@app.get("/api/admin/stats")
async def api_admin_stats(
    tenant: str, init_data: str = "", uid: int | None = None, days: int = 7,
) -> dict[str, Any]:
    t = get_tenant(tenant)
    _check_admin(t, init_data, uid)
    db = get_db(tenant)
    summary = await db.revenue_summary()
    daily   = await db.daily_revenue(days=days)
    top     = await db.top_products(limit=5)
    hours   = await db.peak_hours()
    by_status = await db.count_orders_by_status()
    users_total = await db.count_users()
    users_today = await db.count_new_users_today()
    return {
        **summary,
        "daily": daily, "top_products": top, "peak_hours": hours,
        "by_status": by_status,
        "users_total": users_total, "users_today": users_today,
        "tenant_name": t.name,
    }


def _build_payment_urls(db_settings: dict[str, str], order_id: int, amount_uzs: int) -> dict[str, Any]:
    """Build Click + Payme + Alif universal links and the card-number string.

    Universal links (https://...) auto-open the bank app on mobile if installed,
    otherwise fall through to the website. With merchant credentials we generate
    a fully prefilled checkout URL; without them we use a generic app URL.
    """
    import base64
    click_merchant = db_settings.get("company.click_merchant_id", "").strip()
    click_service  = db_settings.get("company.click_service_id", "").strip()
    payme_merchant = db_settings.get("company.payme_merchant_id", "").strip()
    alif_phone     = db_settings.get("company.alif_phone", "").strip()
    card_number    = db_settings.get("company.card_number", "").strip()

    # --- Click ---------------------------------------------------------
    if click_merchant and click_service:
        click_url = (
            "https://my.click.uz/services/pay"
            f"?service_id={click_service}&merchant_id={click_merchant}"
            f"&amount={amount_uzs}&transaction_param={order_id}"
        )
        click_configured = True
    else:
        click_url = "https://my.click.uz/"
        click_configured = False

    # --- Payme ---------------------------------------------------------
    if payme_merchant:
        tiyin = int(amount_uzs) * 100
        raw = f"m={payme_merchant};ac.order_id={order_id};a={tiyin};l=uz"
        encoded = base64.b64encode(raw.encode()).decode()
        payme_url = f"https://checkout.paycom.uz/{encoded}"
        payme_configured = True
    else:
        payme_url = "https://payme.uz/"
        payme_configured = False

    # --- Alif Mobile ---------------------------------------------------
    # Alif has no documented public deep-link for "send to phone" yet. We use
    # https://alif.uz (universal link to the bank's site / app banner). On
    # phones with Alif Mobile installed the OS will offer to open the app.
    if alif_phone:
        digits = ''.join(ch for ch in alif_phone if ch.isdigit())
        # The Alif Mobile bot accepts /start payload with phone+amount; use it
        # as a sane "open Alif and pay" entry point.
        alif_url = f"https://t.me/alifmobile_bot?start=pay_{digits}_{amount_uzs}"
        alif_configured = True
    else:
        alif_url = "https://alif.uz/"
        alif_configured = False

    return {
        "click_url": click_url, "click_configured": click_configured,
        "payme_url": payme_url, "payme_configured": payme_configured,
        "alif_url":  alif_url,  "alif_configured":  alif_configured,
        "card_number": card_number,
    }


@app.post("/api/order")
async def api_order(payload: OrderIn) -> dict[str, Any]:
    """Submit a new order. Authenticated via Telegram initData HMAC."""
    tenant = get_tenant(payload.tenant_id)
    user: dict[str, Any] = {}
    user_id = 0
    # Preferred: verify Telegram-signed initData (HMAC). Trust it fully.
    if payload.init_data:
        parsed = verify_init_data(payload.init_data, tenant.bot_token)
        if parsed:
            user = parsed.get("user") or {}
            user_id = int(user.get("id") or 0)
        else:
            logger.warning("[%s] initData HMAC failed, trying fallback_uid", tenant.id)
    # Fallback: trust the uid embedded in the WebApp URL by the bot. Less secure
    # (anyone could forge it), but works when Telegram clients don't pass initData
    # (e.g., BotFather setdomain not configured yet, older Desktop builds).
    if not user_id and payload.fallback_uid:
        user_id = int(payload.fallback_uid)
        logger.info("[%s] using fallback_uid=%s", tenant.id, user_id)
    if not user_id:
        raise HTTPException(status_code=400, detail="missing user id")
    db = get_db(payload.tenant_id)
    if not user:
        # Hydrate from DB so we have name/phone.
        row = await db.get_user(user_id)
        if row:
            user = {"id": user_id, "first_name": row.get("name") or "",
                    "username": row.get("username") or ""}

    # Build cart summary + total
    products = {p["id"]: p for p in await db.list_products()}
    lines: list[str] = []
    items_for_json: list[dict[str, Any]] = []
    subtotal = 0
    for item in payload.items:
        p = products.get(item.product_id)
        if not p:
            continue
        price = int(p.get("price_value") or 0)
        subtotal += price * item.qty
        lines.append(f"{p['name']} × {item.qty} = {price * item.qty:,}")
        items_for_json.append({
            "product_id": item.product_id, "name": p["name"],
            "qty": item.qty, "price": price,
        })
    service_summary = "; ".join(lines) if lines else "-"
    if not lines:
        raise HTTPException(status_code=400, detail="empty cart")

    # Apply promo code (if any).
    discount = 0
    applied_code = ""
    if payload.promo_code:
        promo = await db.get_promo(payload.promo_code)
        ok, _label, discount = _validate_promo(promo, subtotal)
        if not ok:
            raise HTTPException(status_code=400, detail=f"promo: {_label}")
        applied_code = (promo or {}).get("code", "")
    total = max(0, subtotal - discount)

    branch_name = ""
    if payload.branch_id:
        b = await db.get_branch(payload.branch_id)
        if b:
            branch_name = b["name"]

    user_row = await db.get_user(user_id)
    phone = (user_row or {}).get("phone", "")
    full_name = (user_row or {}).get("name") or user.get("first_name") or ""

    payment_method = payload.payment_method if payload.payment_method in ("cash", "card") else "cash"
    order_id = await db.create_order(
        user_id=user_id, full_name=full_name, phone=phone,
        service=service_summary, preferred_time=payload.preferred_time,
        branch=branch_name, address=payload.address,
        payment_method=payment_method, amount=total,
        items_json=json.dumps(items_for_json, ensure_ascii=False),
        discount=discount, promo_code=applied_code,
        note=payload.note, courier_note=payload.courier_note,
        entrance=payload.entrance, intercom=payload.intercom,
        apartment=payload.apartment, floor=payload.floor,
    )
    if applied_code:
        await db.increment_promo_use(applied_code)
    if total:
        await db.add_points(user_id, total * 0.05)

    # Build Click/Payme URLs (always present for 'card', empty for 'cash').
    settings = await db.all_settings()
    if payment_method == "card":
        pay_urls = _build_payment_urls(settings, order_id, total)
    else:
        pay_urls = {"click_url": "", "payme_url": "", "click_configured": False, "payme_configured": False}

    pay_method_label = "💳 Karta" if payment_method == "card" else "💵 Naqd"
    discount_line = f"\n🎟 Promokod: {applied_code} (-{discount:,} so'm)" if applied_code else ""

    # Building details inline (only show fields that were filled).
    bldg_parts: list[str] = []
    if payload.entrance:  bldg_parts.append(f"Podyez: {payload.entrance}")
    if payload.intercom:  bldg_parts.append(f"Domofon: {payload.intercom}")
    if payload.apartment: bldg_parts.append(f"Xonadon: {payload.apartment}")
    if payload.floor:     bldg_parts.append(f"Qavat: {payload.floor}")
    bldg_line = f"\n🏠 {' · '.join(bldg_parts)}" if bldg_parts else ""
    courier_line = f"\n📝 Kuryerga: {payload.courier_note}" if payload.courier_note else ""
    note_line    = f"\n💬 Restoranga: {payload.note}" if payload.note else ""

    admin_text = (
        f"🆕 *Yangi buyurtma* #{order_id} (WebApp)\n\n"
        f"👤 {full_name} (@{user.get('username') or '-'})\n"
        f"📞 {phone}\n"
        f"🚚 Usul: {payload.delivery_type}\n"
        f"🏪 Filial: {branch_name or '-'}\n"
        f"📍 {payload.address}"
        f"{bldg_line}"
        f"\n🕐 {payload.preferred_time}\n"
        f"💳 To'lov: {pay_method_label}"
        f"{discount_line}"
        f"{courier_line}"
        f"{note_line}\n\n"
        f"🛒 *Mahsulotlar:*\n" + "\n".join(lines) + f"\n\n💰 *Jami:* {total:,} so'm"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        for admin_id in tenant.admin_ids:
            try:
                await client.post(
                    f"https://api.telegram.org/bot{tenant.bot_token}/sendMessage",
                    json={"chat_id": admin_id, "text": admin_text, "parse_mode": "Markdown"},
                )
            except httpx.HTTPError as exc:
                logger.warning("Admin notify failed: %s", exc)
        # Customer confirmation - translated to the customer's language.
        cust_lang = (user_row or {}).get("language") or tenant.default_language
        if cust_lang == "ru":
            pay_label_cust = "💳 Карта" if payment_method == "card" else "💵 Наличные"
            cust_text = (
                f"✅ Ваш заказ #{order_id} принят.\n"
                f"💰 Сумма: {total:,} сум\n"
                f"💳 Оплата: {pay_label_cust}\n\n"
                f"Скоро оператор свяжется с вами 🚗"
            )
        elif cust_lang == "en":
            pay_label_cust = "💳 Card" if payment_method == "card" else "💵 Cash"
            cust_text = (
                f"✅ Your order #{order_id} has been accepted.\n"
                f"💰 Amount: {total:,} so'm\n"
                f"💳 Payment: {pay_label_cust}\n\n"
                f"An operator will contact you soon 🚗"
            )
        else:
            cust_text = (
                f"✅ Buyurtmangiz #{order_id} tasdiqlandi.\n"
                f"💰 Summa: {total:,} so'm\n"
                f"💳 To'lov: {pay_method_label}\n\n"
                f"Tez orada operator siz bilan bog'lanadi 🚗"
            )
        customer_msg = {"chat_id": user_id, "text": cust_text}
        try:
            await client.post(
                f"https://api.telegram.org/bot{tenant.bot_token}/sendMessage",
                json=customer_msg,
            )
        except httpx.HTTPError as exc:
            logger.warning("Customer confirm failed: %s", exc)

    return {
        "ok": True, "order_id": order_id, "total": total,
        "subtotal": subtotal, "discount": discount, "promo_code": applied_code,
        "payment_method": payment_method,
        "click_url": pay_urls.get("click_url", ""),
        "payme_url": pay_urls.get("payme_url", ""),
        "alif_url":  pay_urls.get("alif_url", ""),
        "click_configured": pay_urls.get("click_configured", False),
        "payme_configured": pay_urls.get("payme_configured", False),
        "alif_configured":  pay_urls.get("alif_configured", False),
        "card_number": pay_urls.get("card_number", ""),
    }


# =================================================== Existing admin endpoints
# (kept for backward compatibility with admin REST clients)

@app.get("/tenants", dependencies=[Depends(require_auth)])
async def list_tenants():
    return [
        {"id": t.id, "name": t.name, "admin_ids": t.admin_ids}
        for t in _tenants.values()
    ]


@app.get("/tenants/{tenant_id}/stats", dependencies=[Depends(require_auth)])
async def tenant_stats(tenant_id: str):
    db = get_db(tenant_id)
    return {
        "users_total": await db.count_users(),
        "users_today": await db.count_new_users_today(),
        "messages": await db.message_stats(),
        "orders": await db.count_orders_by_status(),
    }
