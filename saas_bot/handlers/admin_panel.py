"""Admin reply-keyboard router + 'About us' company-info editor.

This is the admin-only UI. It dispatches taps from the admin reply keyboard
(➕ Mahsulot qo'shish, 📦 Mahsulotlar, 🛒 Buyurtmalar, 📊 Statistika,
📧 Murojaatlar, ℹ️ Biz haqimizda, 📢 Reklama yuborish, 👤 User rejimi)
to the right handler. Existing slash commands (/addproduct etc.) still work
and are reused as the underlying flow where possible.
"""
from __future__ import annotations

import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from core.database import Database
from core.tenant import Tenant
from utils.helpers import (
    about_us_edit_keyboard,
    admin_reply_keyboard,
    main_reply_keyboard,
    order_admin_keyboard,
    delete_items_keyboard,
)

logger = logging.getLogger(__name__)

# Editable company-info fields. Keys are stored in tenant_settings.
COMPANY_FIELDS = [
    "about", "name", "tagline", "phone", "address", "working_hours",
    "card_number", "alif_phone",
    "click_merchant_id", "click_service_id", "payme_merchant_id",
]
FIELD_LABELS = {
    "uz": {
        "about":             "Tavsif (Biz haqimizda)",
        "name":              "Kompaniya nomi",
        "tagline":           "Slogan",
        "phone":             "Telefon",
        "address":           "Asosiy manzil",
        "working_hours":     "Ish vaqti",
        "card_number":       "Karta raqami (mijozga ko'rsatish uchun)",
        "alif_phone":        "Alif Mobile telefon raqami",
        "click_merchant_id": "Click merchant_id",
        "click_service_id":  "Click service_id",
        "payme_merchant_id": "Payme merchant_id",
    },
    "en": {
        "about":             "Description (About us)",
        "name":              "Company name",
        "tagline":           "Tagline",
        "phone":             "Phone",
        "address":           "Main address",
        "working_hours":     "Working hours",
        "card_number":       "Card number (shown to customers)",
        "alif_phone":        "Alif Mobile phone",
        "click_merchant_id": "Click merchant_id",
        "click_service_id":  "Click service_id",
        "payme_merchant_id": "Payme merchant_id",
    },
    "ru": {
        "about":             "Описание (О нас)",
        "name":              "Название компании",
        "tagline":           "Слоган",
        "phone":             "Телефон",
        "address":           "Главный адрес",
        "working_hours":     "Часы работы",
        "card_number":       "Номер карты (показывается клиенту)",
        "alif_phone":        "Телефон Alif Mobile",
        "click_merchant_id": "Click merchant_id",
        "click_service_id":  "Click service_id",
        "payme_merchant_id": "Payme merchant_id",
    },
}

EDIT_FIELD = 0     # state for company-info-field edit conversation
BCAST_WAIT = 1     # state for broadcast text-capture conversation


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def _user_lang(db: Database, user_id: int, default: str) -> str:
    row = await db.get_user(user_id)
    return (row or {}).get("language") or default


def _is_admin_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    tenant = _tenant(context)
    user = update.effective_user
    if not tenant.is_admin(user.id if user else None):
        return False
    return not context.user_data.get("user_view", False)


async def _get_field(db: Database, tenant: Tenant, field: str) -> str:
    """Get a company-info field: prefer DB tenant_settings, fall back to tenant config."""
    val = await db.get_setting(f"company.{field}", "")
    if val:
        return val
    # Fallback to original tenant config values.
    return str(tenant.get(field, "") or "")


# ================================================== Router: admin button taps

async def admin_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None or not update.message.text:
        return
    if not _is_admin_active(update, context):
        return
    tenant = _tenant(context)
    db = _db(context)
    text = update.message.text.strip()
    action = tenant.admin_action_from_label(text)
    if action is None:
        return  # not an admin button, let other handlers process

    user = update.effective_user
    lang = await _user_lang(db, user.id, tenant.default_language)

    # Actions handled by ConversationHandler / MessageHandler in group=0 are
    # skipped here to avoid double-dispatch.
    if action in ("add_product", "add_branch", "list_products", "list_branches"):
        return
    if action == "orders":
        await _open_admin_webapp(update, context, tenant, "orders", lang)
    elif action == "stats":
        await _open_stats_webapp(update, context, tenant, lang)
    elif action == "promos":
        await _open_promos_webapp(update, context, tenant, lang)
    elif action == "feedback_list":
        await _open_admin_webapp(update, context, tenant, "feedback", lang)
    elif action == "about_us":
        await _open_admin_webapp(update, context, tenant, "company", lang)
    elif action == "users":
        await _open_admin_webapp(update, context, tenant, "users", lang)
    elif action == "couriers":
        await _open_admin_webapp(update, context, tenant, "couriers", lang)
    elif action == "broadcast":
        # Entry point for the broadcast conversation - see register().
        # Sending the prompt here in case the conversation isn't triggered.
        pass
    elif action == "user_view":
        context.user_data["user_view"] = True
        await update.message.reply_text(
            tenant.admin_t(lang, "user_view_on"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_reply_keyboard(tenant, lang, user_id=user.id),
        )


# ============================================================== WebApp openers

_ADMIN_WEBAPP_LABELS = {
    "stats": {
        "uz": ("📊 Statistikani ochish", "📊 Pastdagi tugmani bosing — statistika sahifasi ochiladi."),
        "en": ("📊 Open statistics",    "📊 Tap the button below — the statistics page will open."),
        "ru": ("📊 Открыть статистику",  "📊 Нажмите кнопку ниже — откроется страница статистики."),
    },
    "promos": {
        "uz": ("🎟 Promokodlarni boshqarish", "🎟 Pastdagi tugmani bosing — promokodlar sahifasi ochiladi."),
        "en": ("🎟 Manage promo codes",       "🎟 Tap the button below — the promo codes page will open."),
        "ru": ("🎟 Управление промокодами",   "🎟 Нажмите кнопку ниже — откроется страница промокодов."),
    },
    "company": {
        "uz": ("ℹ️ Biz haqimizda — tahrirlash", "ℹ️ Pastdagi tugmani bosing — kompaniya ma'lumotlari sahifasi ochiladi."),
        "en": ("ℹ️ Edit company info",          "ℹ️ Tap the button below — the company-info page will open."),
        "ru": ("ℹ️ Редактировать «О нас»",       "ℹ️ Нажмите кнопку ниже — откроется страница информации о компании."),
    },
    "feedback": {
        "uz": ("📧 Murojaatlar paneli", "📧 Pastdagi tugmani bosing — murojaatlar dashboard ochiladi."),
        "en": ("📧 Feedback dashboard",  "📧 Tap the button below — the feedback dashboard will open."),
        "ru": ("📧 Панель обращений",    "📧 Нажмите кнопку ниже — откроется панель обращений."),
    },
    "orders": {
        "uz": ("🛒 Buyurtmalar paneli",   "🛒 Pastdagi tugmani bosing — buyurtmalar dashboard ochiladi."),
        "en": ("🛒 Orders dashboard",     "🛒 Tap the button below — the orders dashboard will open."),
        "ru": ("🛒 Панель заказов",       "🛒 Нажмите кнопку ниже — откроется панель заказов."),
    },
    "users": {
        "uz": ("👥 Mijozlar bazasi",       "👥 Pastdagi tugmani bosing — mijozlar ro'yxati ochiladi."),
        "en": ("👥 Customer database",     "👥 Tap the button below — the customer list will open."),
        "ru": ("👥 База клиентов",         "👥 Нажмите кнопку ниже — откроется список клиентов."),
    },
    "couriers": {
        "uz": ("🚗 Kuryerlar paneli",      "🚗 Pastdagi tugmani bosing — kuryerlar boshqaruvi ochiladi."),
        "en": ("🚗 Couriers panel",        "🚗 Tap the button below — the couriers panel will open."),
        "ru": ("🚗 Панель курьеров",       "🚗 Нажмите кнопку ниже — откроется панель управления курьерами."),
    },
}
_NO_WEBAPP = {
    "uz": "⚠️ WebApp URL hali sozlanmagan. Tunnel ishga tushgach qayta urinib ko'ring.",
    "en": "⚠️ WebApp URL is not configured yet. Try again once the tunnel is up.",
    "ru": "⚠️ URL WebApp ещё не настроен. Попробуйте после запуска туннеля.",
}


async def _open_admin_webapp(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    tenant: Tenant, path: str, lang: str,
) -> None:
    """Reply with a WebApp keyboard pointing at /webapp/admin/{path}.

    Falls back to a text hint if WEBAPP_URL is not yet configured."""
    from config.settings import get_webapp_url
    from utils.helpers import home_button_label
    webapp_url = get_webapp_url()
    uid = update.effective_user.id if update.effective_user else 0
    if not webapp_url:
        await update.message.reply_text(_NO_WEBAPP.get(lang, _NO_WEBAPP["uz"]))
        return
    url = f"{webapp_url}/webapp/admin/{path}?tenant={tenant.id}&uid={uid}&lang={lang}"
    button_label, intro = _ADMIN_WEBAPP_LABELS[path].get(
        lang, _ADMIN_WEBAPP_LABELS[path]["uz"]
    )
    kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton(text=button_label, web_app=WebAppInfo(url=url))],
            [KeyboardButton(text=home_button_label(lang))],
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(intro, reply_markup=kb)


async def _open_stats_webapp(update, context, tenant: Tenant, lang: str) -> None:
    await _open_admin_webapp(update, context, tenant, "stats", lang)


async def _open_promos_webapp(update, context, tenant: Tenant, lang: str) -> None:
    await _open_admin_webapp(update, context, tenant, "promos", lang)


# ============================================================== Pending orders

async def _show_pending_orders(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    pending = await db.pending_orders(20)
    if not pending:
        await update.message.reply_text(tenant.admin_t(lang, "orders_empty"))
        return
    for o in pending:
        text = (
            f"🛒 *Buyurtma* #{o['id']}\n\n"
            f"👤 {o.get('full_name', '-')}\n"
            f"📞 {o.get('phone', '-')}\n"
            f"🏪 Filial: {o.get('branch') or '-'}\n"
            f"📍 {o.get('address') or '-'}\n"
            f"🍔 {o.get('service', '-')}\n"
            f"🕐 {o.get('preferred_time', '-')}\n"
            f"📅 {o.get('created_at', '-')}"
        )
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=order_admin_keyboard(o["id"]),
        )


# ================================================================ Feedback

async def _show_feedback_list(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    rows = await db.recent_feedback(20)
    if not rows:
        await update.message.reply_text(tenant.admin_t(lang, "feedback_empty"))
        return
    header = tenant.admin_t(lang, "feedback_header", count=len(rows))
    lines = [header]
    for r in rows:
        u = await db.get_user(r["user_id"])
        name = (u or {}).get("name") or "-"
        phone = (u or {}).get("phone") or "-"
        lines.append(f"\n📩 *#{r['id']}* · {r['created_at']}\n👤 {name} | 📞 {phone}\n{r['content']}")
    text = "\n".join(lines)
    # Telegram limits message size to 4096 chars - chunk if needed.
    if len(text) <= 3900:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)
        for r in rows:
            u = await db.get_user(r["user_id"])
            name = (u or {}).get("name") or "-"
            phone = (u or {}).get("phone") or "-"
            await update.message.reply_text(
                f"📩 *#{r['id']}* · {r['created_at']}\n👤 {name} | 📞 {phone}\n{r['content']}",
                parse_mode=ParseMode.MARKDOWN,
            )


# ================================================== About us / company info

async def _show_about_panel(update, context, tenant: Tenant, db: Database, lang: str) -> None:
    """Display all current company-info fields with edit buttons."""
    labels = FIELD_LABELS.get(lang, FIELD_LABELS[tenant.default_language])
    lines = ["ℹ️ *Kompaniya ma'lumotlari:*\n"] if lang == "uz" else (
        ["ℹ️ *Company info:*\n"] if lang == "en" else ["ℹ️ *Информация о компании:*\n"]
    )
    for field in COMPANY_FIELDS:
        val = await _get_field(db, tenant, field)
        display = val if val else "_—_"
        lines.append(f"*{labels[field]}:*\n{display}\n")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN,
        reply_markup=about_us_edit_keyboard(labels),
    )


async def edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped 'edit <field>' inline -> ask for new value."""
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return ConversationHandler.END
    tenant = _tenant(context)
    if not _is_admin_active(update, context):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    if query.data == "editfield_close":
        await query.edit_message_reply_markup(reply_markup=None)
        return ConversationHandler.END
    field = query.data.split(":", 1)[1]
    if field not in COMPANY_FIELDS:
        return ConversationHandler.END
    db = _db(context)
    lang = await _user_lang(db, update.effective_user.id, tenant.default_language)
    labels = FIELD_LABELS.get(lang, FIELD_LABELS[tenant.default_language])
    current = await _get_field(db, tenant, field)
    context.user_data["edit_field"] = field
    prompt = (
        f"✏ *{labels[field]}*\n\n"
        f"Hozirgi: {current or '_bo''sh_'}\n\n"
        f"Yangi qiymatni yuboring (/cancel - bekor qilish)."
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=prompt, parse_mode=ParseMode.MARKDOWN,
    )
    return EDIT_FIELD


async def edit_field_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return EDIT_FIELD
    field = context.user_data.pop("edit_field", None)
    if not field:
        return ConversationHandler.END
    tenant = _tenant(context)
    db = _db(context)
    user = update.effective_user
    lang = await _user_lang(db, user.id if user else 0, tenant.default_language)
    new_val = update.message.text.strip()
    await db.set_setting(f"company.{field}", new_val)
    await update.message.reply_text(
        tenant.admin_t(lang, "about_saved"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_reply_keyboard(tenant, lang, user_id=user.id if user else None),
    )
    return ConversationHandler.END


# ================================================================ Broadcast

async def broadcast_start_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: admin tapped the '📢 Reklama yuborish' button."""
    if not _is_admin_active(update, context):
        return ConversationHandler.END
    tenant = _tenant(context)
    db = _db(context)
    user = update.effective_user
    lang = await _user_lang(db, user.id if user else 0, tenant.default_language)
    await update.message.reply_text(
        tenant.admin_t(lang, "broadcast_ask"), parse_mode=ParseMode.MARKDOWN,
    )
    return BCAST_WAIT


async def broadcast_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return BCAST_WAIT
    tenant = _tenant(context)
    db = _db(context)
    user = update.effective_user
    lang = await _user_lang(db, user.id if user else 0, tenant.default_language)
    text = update.message.text.strip()

    async with db.conn.execute(
        "SELECT id FROM users WHERE tenant_id=?", (tenant.id,)
    ) as cur:
        rows = await cur.fetchall()
    user_ids = [int(r["id"]) for r in rows]
    sent = failed = 0
    status = await update.message.reply_text(f"📤 0 / {len(user_ids)}")
    for i, uid in enumerate(user_ids, start=1):
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Forbidden:
            failed += 1
        except TelegramError:
            failed += 1
        if i % 20 == 0:
            try:
                await status.edit_text(f"📤 {i} / {len(user_ids)}")
            except TelegramError:
                pass
        await asyncio.sleep(0.05)
    await status.edit_text(
        tenant.admin_t(lang, "broadcast_done", sent=sent, failed=failed, total=len(user_ids))
    )
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("❌ Bekor qilindi.")
    context.user_data.pop("edit_field", None)
    return ConversationHandler.END


# ===================================================== /admin command toggle

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin restores the admin keyboard for admin users (used after 'User rejimi')."""
    if update.message is None or update.effective_user is None:
        return
    tenant = _tenant(context)
    if not tenant.is_admin(update.effective_user.id):
        await update.message.reply_text(tenant.t(tenant.default_language, "not_admin"))
        return
    db = _db(context)
    lang = await _user_lang(db, update.effective_user.id, tenant.default_language)
    context.user_data["user_view"] = False
    await update.message.reply_text(
        tenant.admin_t(lang, "admin_view_on"),
        reply_markup=admin_reply_keyboard(tenant, lang, user_id=update.effective_user.id),
    )


# ================================================================ Register

def register(app: Application, tenant: Tenant) -> None:
    # /admin command toggles back to admin view.
    app.add_handler(CommandHandler("admin", admin_command), group=0)

    # Broadcast conversation - entry is the admin button text.
    bcast_texts = [labels.get("broadcast") for labels in tenant.admin_labels.values() if labels.get("broadcast")]
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text(bcast_texts) & ~filters.COMMAND, broadcast_start_button)],
        states={BCAST_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_capture)]},
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="bcast_button_flow",
        per_message=False,
    ), group=0)

    # Edit-field conversation.
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_field_callback, pattern=r"^editfield:")],
        states={EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_capture)]},
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="editfield_flow",
        per_message=False,
    ), group=0)
    app.add_handler(CallbackQueryHandler(edit_field_callback, pattern=r"^editfield_close$"))

    # Admin router (group=2: after order conv at group=1, before menu_router at group=5).
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_router), group=2,
    )
