"""Routes ReplyKeyboard button taps and free-text to the right handler.

Telegram has no built-in "match this text to a button" — every tap is just a
text message. We resolve the action by looking up the tapped text in every
language's MENU_LABELS, then dispatch.

Order of precedence (registered in `bot.py`):
1. Order ConversationHandler (consumes 'order' text in any language)
2. This router (handles loyalty, branches, menu, contact, language)
3. AI chat catch-all (anything else)
"""
from __future__ import annotations

import json
import logging

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import get_webapp_url
from core.database import Database
from core.tenant import Tenant
from utils.helpers import branches_keyboard, language_keyboard, main_reply_keyboard

logger = logging.getLogger(__name__)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def _user_lang(db: Database, user_id: int, default: str) -> str:
    row = await db.get_user(user_id)
    return (row or {}).get("language") or default


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None or not update.message.text:
        return
    tenant = _tenant(context)
    db = _db(context)
    text = update.message.text.strip()
    user = update.effective_user
    lang = await _user_lang(db, user.id, tenant.default_language)

    # Universal "back to main menu" button — accept the label in any language.
    from utils.helpers import is_home_button_text
    if is_home_button_text(text):
        from utils.helpers import admin_reply_keyboard
        is_admin = tenant.is_admin(user.id) and not context.user_data.get("user_view")
        kb = admin_reply_keyboard(tenant, lang, user_id=user.id) if is_admin else main_reply_keyboard(tenant, lang, user_id=user.id)
        await update.message.reply_text(tenant.t(lang, "main_menu"), reply_markup=kb)
        return

    # Skip admin-keyboard taps ONLY when the user is actually an active admin
    # (i.e., admin_panel's router will handle it at group=2). For regular users
    # AND for admins in 'user view' mode, we must still process texts that
    # happen to coincide with an admin label (e.g., '🏠 Filiallar' appears in
    # both user and admin keyboards).
    is_admin_active = tenant.is_admin(user.id) and not context.user_data.get("user_view", False)
    if is_admin_active and tenant.admin_action_from_label(text):
        return
    action = tenant.action_from_label(text)
    if action is None:
        return  # let next handler (AI chat) handle it

    user = update.effective_user
    lang = await _user_lang(db, user.id, tenant.default_language)

    # Dispatch only to handlers we own here. The following are owned elsewhere:
    #   - 'order'    -> order ConversationHandler (group=1)
    #   - 'geo'      -> features.geo_handler (LOCATION filter, group=0)
    #   - 'feedback' -> features ConversationHandler (group=1)
    if action == "branches":
        await _show_branches(update, context, tenant, db, lang)
    elif action == "loyalty_qr":
        from handlers.features import loyalty_qr_handler
        await loyalty_qr_handler(update, context)
    elif action == "points":
        from handlers.features import points_handler
        await points_handler(update, context)
    elif action == "addresses":
        from handlers.features import addresses_handler
        await addresses_handler(update, context)
    elif action == "settings":
        from handlers.features import settings_handler
        await settings_handler(update, context)
    elif action == "about":
        await _show_about(update, context, tenant, db, lang)
    elif action == "back":
        await update.message.reply_text(
            tenant.t(lang, "main_menu"),
            reply_markup=main_reply_keyboard(tenant, lang, user_id=user.id),
        )


# ----------------------------------------------------------------- actions

async def _show_loyalty(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    user = update.effective_user
    row = await db.get_user(user.id)
    orders_count = 0
    async with db.conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE tenant_id=? AND user_id=?",
        (tenant.id, user.id),
    ) as cur:
        r = await cur.fetchone()
        if r:
            orders_count = int(r["n"])
    points = orders_count * 50  # 50 points per order; tweak per business rules
    text = tenant.t(
        lang, "loyalty_info",
        name=(row or {}).get("name") or user.first_name or "-",
        phone=(row or {}).get("phone") or "-",
        user_id=user.id,
        points=points,
        orders=orders_count,
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )


async def _show_about(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    """User-side 'Kompaniya haqida' — render fields the admin saved via the
    Biz haqimizda WebApp, falling back to tenant config defaults."""
    async def _get(key: str) -> str:
        v = await db.get_setting(f"company.{key}", "")
        return v or str(tenant.get(key, "") or "")

    name      = await _get("name")     or tenant.name
    tagline   = await _get("tagline")
    about     = await _get("about")
    phone     = await _get("phone")
    address   = await _get("address")
    hours     = await _get("working_hours")

    headers = {
        "uz": ("🏢", "📝 Tavsif:", "📞 Telefon:", "📍 Manzil:", "🕐 Ish vaqti:",
               "Ma'lumot hozircha qo'shilmagan."),
        "en": ("🏢", "📝 Description:", "📞 Phone:", "📍 Address:", "🕐 Hours:",
               "No info added yet."),
        "ru": ("🏢", "📝 Описание:", "📞 Телефон:", "📍 Адрес:", "🕐 Режим работы:",
               "Информация ещё не добавлена."),
    }.get(lang, None) or ({}, "", "", "", "", "")
    h_emoji, lbl_desc, lbl_phone, lbl_addr, lbl_hours, fallback = headers

    lines = [f"{h_emoji} *{name}*"]
    if tagline:
        lines.append(f"_{tagline}_")
    if about:
        lines.append("")
        lines.append(f"{lbl_desc}\n{about}")
    if phone:
        lines.append("")
        lines.append(f"{lbl_phone} {phone}")
    if address:
        lines.append(f"{lbl_addr} {address}")
    if hours:
        lines.append(f"{lbl_hours} {hours}")
    if len(lines) == 1 and not (tagline or about or phone or address or hours):
        lines.append("")
        lines.append(f"_{fallback}_")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )


async def _show_branches(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    branches = await db.list_branches()
    if not branches:
        await update.message.reply_text("Filiallar topilmadi.")
        return
    webapp_url = get_webapp_url()
    if webapp_url:
        url = f"{webapp_url}/webapp/branches?tenant={tenant.id}&lang={lang}"
        btn_label = {
            "uz": "🏪 Filiallarni ko'rish",
            "en": "🏪 View branches",
            "ru": "🏪 Посмотреть филиалы",
        }.get(lang, "🏪 Filiallarni ko'rish")
        intro = {
            "uz": "🏪 Pastdagi tugmani bosing — filiallar sahifasi ochiladi.\n"
                  "Yoki 🏠 Bosh menyu tugmasi bilan qayting.",
            "en": "🏪 Tap the button below — the branches page will open.\n"
                  "Or use 🏠 Main menu to return.",
            "ru": "🏪 Нажмите кнопку ниже — откроется страница филиалов.\n"
                  "Или вернитесь в 🏠 Главное меню.",
        }.get(lang)
        from utils.helpers import home_button_label
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton(text=btn_label, web_app=WebAppInfo(url=url))],
                [KeyboardButton(text=home_button_label(lang))],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(intro, reply_markup=kb)
        return
    header = tenant.t(lang, "branches_header", count=len(branches))
    await update.message.reply_text(
        header,
        reply_markup=branches_keyboard(branches),
    )


async def _show_menu(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    products = await db.list_products()
    text = tenant.t(
        lang, "menu_header",
        services_formatted=tenant.services_formatted(products),
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )


async def _show_contact(update, context, tenant: Tenant, lang: str) -> None:
    await update.message.reply_text(
        tenant.t(lang, "contact_info", phone=tenant.get("phone", "")),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )


# ---------------------------------------------------- branch inline tap

async def branch_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped an inline branch button -> show full branch info + location."""
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = await _user_lang(db, update.effective_user.id, tenant.default_language)
    try:
        branch_id = int(query.data.split(":", 1)[1])
    except ValueError:
        return
    branch = await db.get_branch(branch_id)
    if branch is None:
        await query.message.reply_text("Filial topilmadi.")
        return
    hours_block = Tenant.format_branch_hours(branch.get("hours_json"))
    text = tenant.t(
        lang, "branch_info",
        name=branch["name"],
        address=branch["address"],
        hours_block=hours_block,
        phone=branch.get("phone", ""),
        maps_url=branch.get("maps_url", "") or "",
    )
    await query.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False,
    )
    if branch.get("lat") and branch.get("lon"):
        try:
            await context.bot.send_location(
                chat_id=query.message.chat_id,
                latitude=float(branch["lat"]),
                longitude=float(branch["lon"]),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("send_location failed: %s", exc)


# ---------------------------------------------------- handler registration

def register(app: Application) -> None:
    from telegram.ext import CallbackQueryHandler

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router),
        group=5,
    )
    app.add_handler(CallbackQueryHandler(branch_view_callback, pattern=r"^branch:\d+$"))
