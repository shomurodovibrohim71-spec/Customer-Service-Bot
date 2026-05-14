"""Keyboard builders, phone validation, and small utilities."""
from __future__ import annotations

import re
from typing import Iterable

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

PHONE_RE = re.compile(r"^\+?\d{9,15}$")


def is_valid_phone(text: str) -> bool:
    cleaned = re.sub(r"[\s\-()]", "", text or "")
    return bool(PHONE_RE.match(cleaned))


def normalize_phone(text: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", text or "")
    if cleaned and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


# ----------------------------------------------------------------- inline KB

def build_menu_keyboard(
    buttons: Iterable[dict[str, str]], columns: int = 2
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for btn in buttons:
        row.append(InlineKeyboardButton(btn["text"], callback_data=btn["callback"]))
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


# Localized labels for the "🏠 Main menu" button used across the bot.
HOME_BTN = {
    "uz": "🏠 Bosh menyu",
    "en": "🏠 Main menu",
    "ru": "🏠 Главное меню",
}
# Inline variant text (used in a few places); same labels but for inline keyboards.
HOME_INLINE = {
    "uz": "🏠 Asosiy menyu",
    "en": "🏠 Main menu",
    "ru": "🏠 Главное меню",
}


def home_button_label(lang: str | None) -> str:
    """Return the reply-keyboard '🏠 Main menu' label for the given language."""
    return HOME_BTN.get((lang or "uz").lower(), HOME_BTN["uz"])


def is_home_button_text(text: str) -> bool:
    """True if `text` matches the home button in any supported language."""
    return text in HOME_BTN.values() or text in HOME_INLINE.values()


def back_to_menu_keyboard(label: str | None = None, lang: str | None = None) -> InlineKeyboardMarkup:
    """Inline 'home' button. Pass `lang` to pick the localized label, or override with `label`."""
    txt = label or HOME_INLINE.get((lang or "uz").lower(), HOME_INLINE["uz"])
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(txt, callback_data="main_menu")]]
    )


def language_keyboard(languages: dict[str, str]) -> InlineKeyboardMarkup:
    """Inline keyboard for language selection: one row, all langs."""
    row = [
        InlineKeyboardButton(label, callback_data=f"lang:{code}")
        for code, label in languages.items()
    ]
    return InlineKeyboardMarkup([row])


def branches_keyboard(branches: list[dict]) -> InlineKeyboardMarkup:
    """2-column inline keyboard listing branches by id."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for b in branches:
        row.append(InlineKeyboardButton(b["name"], callback_data=f"branch:{b['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    """One product per row, with a final Cancel button."""
    rows = [
        [InlineKeyboardButton(f"{p['name']} — {p['price']}", callback_data=f"svc:{p['id']}")]
        for p in products
    ]
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="order_confirm"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel"),
        ]]
    )


def order_admin_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_confirm:{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"adm_cancel:{order_id}"),
        ]]
    )


def delete_items_keyboard(items: list[dict], prefix: str) -> InlineKeyboardMarkup:
    """List items with a 🗑 prefix button per row for deletion."""
    rows = [
        [InlineKeyboardButton(f"🗑 {it.get('name','?')}", callback_data=f"{prefix}:{it['id']}")]
        for it in items
    ]
    rows.append([InlineKeyboardButton("❌ Yopish", callback_data=f"{prefix}_close")])
    return InlineKeyboardMarkup(rows)


# --------------------------------------------------------------- reply KB

def main_reply_keyboard(tenant, lang: str) -> ReplyKeyboardMarkup:
    """4-row x 2-column reply keyboard matching the Mini Food layout."""
    L = lambda action: tenant.label(lang, action)  # noqa: E731
    rows = [
        [KeyboardButton(L("order")), KeyboardButton(L("geo"), request_location=True)],
        [KeyboardButton(L("loyalty_qr")), KeyboardButton(L("points"))],
        [KeyboardButton(L("branches")), KeyboardButton(L("addresses"))],
        [KeyboardButton(L("feedback")), KeyboardButton(L("settings"))],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_reply_keyboard(tenant, lang: str) -> ReplyKeyboardMarkup:
    """Admin-only reply keyboard. Product add/edit/delete all live inside the
    📦 Mahsulotlar WebApp - no separate 'add product' button is shown."""
    L = lambda action: tenant.admin_label(lang, action)  # noqa: E731
    rows = [
        [KeyboardButton(L("list_products")), KeyboardButton(L("list_branches"))],
        [KeyboardButton(L("add_branch")),    KeyboardButton(L("orders"))],
        [KeyboardButton(L("stats")),         KeyboardButton(L("promos"))],
        [KeyboardButton(L("feedback_list")), KeyboardButton(L("about_us"))],
        [KeyboardButton(L("broadcast")),     KeyboardButton(L("user_view"))],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def about_us_edit_keyboard(field_labels: dict[str, str]) -> InlineKeyboardMarkup:
    """Inline buttons for editing each company-info field.

    field_labels: {field_key: display_label}
    """
    rows = [[InlineKeyboardButton(f"✏ {label}", callback_data=f"editfield:{key}")]
            for key, label in field_labels.items()]
    rows.append([InlineKeyboardButton("⬅ Yopish", callback_data="editfield_close")])
    return InlineKeyboardMarkup(rows)


def back_reply_keyboard(label: str) -> ReplyKeyboardMarkup:
    """Single '⬅ Orqaga' button for transient flows (feedback, etc.)."""
    return ReplyKeyboardMarkup([[KeyboardButton(label)]], resize_keyboard=True)


def delivery_method_reply_keyboard(delivery_label: str, pickup_label: str) -> ReplyKeyboardMarkup:
    """Two-button bottom keyboard for choosing delivery vs pickup."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(delivery_label), KeyboardButton(pickup_label)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def geo_confirm_keyboard(yes_label: str, no_label: str) -> InlineKeyboardMarkup:
    """Confirm/edit buttons for a reverse-geocoded address."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data="geo_yes"),
        InlineKeyboardButton(no_label, callback_data="geo_no"),
    ]])


def register_branch_keyboard(branches: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for picking a branch during onboarding."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for b in branches:
        row.append(InlineKeyboardButton(b["name"], callback_data=f"regbranch:{b['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def pickup_branch_keyboard(branches: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for choosing a pickup branch during the order flow."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for b in branches:
        row.append(InlineKeyboardButton(b["name"], callback_data=f"pickbranch:{b['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("⬅ Orqaga", callback_data="back_to_delivery"),
        InlineKeyboardButton("❌ Bekor", callback_data="order_cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def settings_inline_keyboard(lang_label: str, phone_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(lang_label, callback_data="set_lang"),
            InlineKeyboardButton(phone_label, callback_data="set_phone"),
        ]]
    )


def addresses_list_keyboard(addresses: list[dict]) -> InlineKeyboardMarkup:
    """One delete button per saved address."""
    rows = [
        [InlineKeyboardButton(f"🗑 {a['text'][:40]}", callback_data=f"deladdr:{a['id']}")]
        for a in addresses
    ]
    return InlineKeyboardMarkup(rows) if rows else InlineKeyboardMarkup([])


def phone_request_keyboard(label: str) -> ReplyKeyboardMarkup:
    """Reply keyboard with a single contact-share button."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(label, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
