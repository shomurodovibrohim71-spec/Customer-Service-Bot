"""In-memory cart helpers.

Cart is stored in `context.user_data["cart"]` as `{product_id: qty}`.
It survives across messages within the bot process but is wiped on restart.
"""
from __future__ import annotations

from typing import Any


def get_cart(user_data: dict) -> dict[int, int]:
    cart = user_data.setdefault("cart", {})
    return cart


def cart_add(user_data: dict, product_id: int, qty: int = 1) -> int:
    cart = get_cart(user_data)
    cart[product_id] = cart.get(product_id, 0) + qty
    return cart[product_id]


def cart_set(user_data: dict, product_id: int, qty: int) -> None:
    cart = get_cart(user_data)
    if qty <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = qty


def cart_remove(user_data: dict, product_id: int) -> None:
    get_cart(user_data).pop(product_id, None)


def cart_clear(user_data: dict) -> None:
    user_data.pop("cart", None)


def cart_count(user_data: dict) -> int:
    return sum(get_cart(user_data).values())


def cart_total(user_data: dict, products_by_id: dict[int, dict]) -> int:
    total = 0
    for pid, qty in get_cart(user_data).items():
        product = products_by_id.get(pid)
        if product:
            total += int(product.get("price_value") or 0) * qty
    return total


def cart_lines(user_data: dict, products_by_id: dict[int, dict]) -> list[str]:
    lines: list[str] = []
    for pid, qty in get_cart(user_data).items():
        p = products_by_id.get(pid)
        if not p:
            continue
        price_val = int(p.get("price_value") or 0)
        lines.append(f"• {p['name']} × {qty} = {price_val * qty:,} so'm")
    return lines
