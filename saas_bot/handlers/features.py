"""User-side features matching the Mini Food bot layout.

Implements: geolocation save, QR code generation, my points, saved addresses,
feedback intake, and a settings sub-menu (language + phone change).
"""
from __future__ import annotations

import io
import logging
import re

import qrcode
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
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
    addresses_list_keyboard,
    back_reply_keyboard,
    is_valid_phone,
    language_keyboard,
    main_reply_keyboard,
    normalize_phone,
    phone_request_keyboard,
    settings_inline_keyboard,
)

logger = logging.getLogger(__name__)

# Conversation states for feedback intake, phone-change, and address edit.
FB_WAIT, PH_WAIT, ADDR_EDIT = range(3)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def _lang(db: Database, user_id: int, default: str) -> str:
    row = await db.get_user(user_id)
    return (row or {}).get("language") or default


# ============================================================ GEOLOCATION

async def geo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered when user shares a location via the 'Geolokatsiya' KB button.

    The button has request_location=True so taps produce a Location message,
    not text. We save it as a new address.

    NOTE: if the user is currently inside the order flow (ASK_ADDRESS state),
    don't capture here — let the order handler consume it.
    """
    msg = update.message
    user = update.effective_user
    if msg is None or user is None or msg.location is None:
        return
    if (context.user_data or {}).get("order"):
        return  # active order flow owns the location
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    loc = msg.location
    # Reverse-geocode to a human-readable address so the saved entry is useful.
    from core.geocoder import reverse_geocode
    address_text = await reverse_geocode(loc.latitude, loc.longitude, lang) \
        or f"GPS {loc.latitude:.5f}, {loc.longitude:.5f}"
    await db.add_address(
        user_id=user.id, text=address_text, label="geo",
        lat=loc.latitude, lon=loc.longitude,
    )
    await msg.reply_text(
        tenant.t(lang, "geo_saved", address=address_text),
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )


# ============================================================ QR CODE

def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


async def loyalty_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a PNG QR encoding the user's phone digits and send as document."""
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    row = await db.get_user(user.id)
    phone_raw = (row or {}).get("phone") or ""
    digits = _phone_digits(phone_raw) or str(user.id)

    img = qrcode.make(digits)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = f"{digits}.png"

    await context.bot.send_document(
        chat_id=msg.chat_id,
        document=buf,
        filename=f"{digits}.png",
        caption=tenant.t(lang, "qr_caption", phone_digits=digits),
    )


# ============================================================ POINTS

async def points_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    pts = await db.get_points(user.id)
    await msg.reply_text(
        tenant.t(lang, "points_info", points=pts),
        parse_mode=ParseMode.MARKDOWN,
    )


# ============================================================ ADDRESSES

def _addresses_text(addrs: list[dict], lang: str) -> str:
    """Build the formatted address list message."""
    header = {
        "uz": "🏠 Mening manzillarim",
        "en": "🏠 My addresses",
        "ru": "🏠 Мои адреса",
    }.get(lang, "🏠 Mening manzillarim")
    count_label = {
        "uz": f"{len(addrs)} ta manzil",
        "en": f"{len(addrs)} address(es)",
        "ru": f"{len(addrs)} адрес(а)",
    }.get(lang, f"{len(addrs)} ta manzil")
    hint = {
        "uz": "📌 Tahrirlash yoki o'chirish uchun pastdagi tugmalardan foydalaning:",
        "en": "📌 Use the buttons below to edit or delete an address:",
        "ru": "📌 Используйте кнопки ниже для редактирования или удаления:",
    }.get(lang, "📌 Tahrirlash yoki o'chirish uchun pastdagi tugmalardan foydalaning:")
    lines = "\n\n".join(f"*{i}.* 📍 {a['text']}" for i, a in enumerate(addrs, start=1))
    return f"*{header}* ({count_label})\n\n{lines}\n\n{hint}"


async def addresses_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    addrs = await db.list_addresses(user.id)
    if not addrs:
        await msg.reply_text(tenant.t(lang, "addresses_empty"))
        return
    await msg.reply_text(
        _addresses_text(addrs, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=addresses_list_keyboard(addrs),
    )


async def delete_address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, update.effective_user.id, tenant.default_language)
    try:
        addr_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    await db.delete_address(addr_id, update.effective_user.id)
    addrs = await db.list_addresses(update.effective_user.id)
    if not addrs:
        await query.edit_message_text(tenant.t(lang, "addresses_empty"))
        return
    await query.edit_message_text(
        _addresses_text(addrs, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=addresses_list_keyboard(addrs),
    )


async def edit_address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return ConversationHandler.END
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, update.effective_user.id, tenant.default_language)
    try:
        addr_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return ConversationHandler.END
    context.user_data["editing_addr_id"] = addr_id
    cancel_label = {"uz": "❌ Bekor", "en": "❌ Cancel", "ru": "❌ Отмена"}.get(lang, "❌ Bekor")
    await query.message.reply_text(
        {"uz": "📝 Yangi manzil matnini yozing:", "en": "📝 Enter new address text:", "ru": "📝 Введите новый адрес:"}
        .get(lang, "📝 Yangi manzil matnini yozing:"),
        reply_markup=back_reply_keyboard(cancel_label),
    )
    return ADDR_EDIT


async def addr_edit_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None or not msg.text:
        return ADDR_EDIT
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    cancel_labels = {"❌ Bekor", "❌ Cancel", "❌ Отмена"}
    if msg.text.strip() in cancel_labels:
        addrs = await db.list_addresses(user.id)
        if addrs:
            await msg.reply_text(
                _addresses_text(addrs, lang),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=addresses_list_keyboard(addrs),
            )
        else:
            await msg.reply_text(tenant.t(lang, "addresses_empty"),
                                 reply_markup=main_reply_keyboard(tenant, lang, user_id=user.id))
        context.user_data.pop("editing_addr_id", None)
        return ConversationHandler.END
    addr_id = context.user_data.get("editing_addr_id")
    if not addr_id:
        return ConversationHandler.END
    new_text = msg.text.strip()
    await db.update_address(addr_id, user.id, new_text)
    context.user_data.pop("editing_addr_id", None)
    addrs = await db.list_addresses(user.id)
    saved_msg = {"uz": "✅ Manzil yangilandi!", "en": "✅ Address updated!", "ru": "✅ Адрес обновлён!"}.get(lang, "✅ Manzil yangilandi!")
    await msg.reply_text(
        f"{saved_msg}\n\n" + _addresses_text(addrs, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=addresses_list_keyboard(addrs),
    )
    return ConversationHandler.END


# ============================================================ FEEDBACK

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return ConversationHandler.END
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    back_label = tenant.label(lang, "back")
    await msg.reply_text(
        tenant.t(lang, "feedback_prompt"),
        reply_markup=back_reply_keyboard(back_label),
    )
    return FB_WAIT


async def feedback_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None or not msg.text:
        return FB_WAIT
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)

    # "⬅ Orqaga" -> back to main menu.
    if tenant.action_from_label(msg.text) == "back":
        await msg.reply_text(
            tenant.t(lang, "main_menu"),
            reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
        )
        return ConversationHandler.END

    content = msg.text.strip()
    # AI classification + draft answer (best-effort; failures fall back gracefully).
    ai = context.bot_data.get("ai")
    category, ai_reply = await _classify_and_answer(ai, content, lang) if ai else ("question", "")

    fb_id = await db.add_feedback(
        user_id=user.id, content=content,
        username=user.username or "",
        category=category, ai_response=ai_reply,
    )
    row = await db.get_user(user.id)

    # First reply to the customer: confirmation + the AI's draft answer.
    confirm = tenant.t(lang, "feedback_saved")
    if ai_reply:
        full = f"{confirm}\n\n🤖 {ai_reply}"
    else:
        full = confirm
    await msg.reply_text(full, reply_markup=main_reply_keyboard(tenant, lang, user_id=user.id))

    # Notify admins.
    cat_emoji = {"complaint": "📢", "question": "❓", "suggestion": "💡"}.get(category, "📧")
    admin_text = tenant.t(
        lang, "feedback_admin",
        user_name=user.full_name or "-",
        username=user.username or "-",
        phone=(row or {}).get("phone") or "-",
        content=content,
    )
    admin_text = f"{cat_emoji} *#{fb_id}*\n" + admin_text
    if ai_reply:
        admin_text += f"\n\n🤖 *AI javobi:*\n{ai_reply}"
    for admin_id in tenant.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=admin_text, parse_mode=ParseMode.MARKDOWN
            )
        except TelegramError as exc:
            logger.warning("[%s] feedback notify failed: %s", tenant.id, exc)
    return ConversationHandler.END


async def _classify_and_answer(ai, content: str, lang: str) -> tuple[str, str]:
    """Ask Claude to classify the feedback AND draft a polite reply in one call.

    Returns (category, reply). Category is one of: complaint | question | suggestion.
    Falls back to ('question', '') on any error so the flow never blocks."""
    if not ai or not content:
        return "question", ""
    lang_name = {"uz": "uzbek", "en": "english", "ru": "russian"}.get(lang, "uzbek")
    system = (
        "You triage and answer customer feedback for a fast-food bot. "
        "Given the customer message, output STRICTLY this format on two lines:\n"
        "CATEGORY: <complaint|question|suggestion>\n"
        "REPLY: <a short, polite answer in " + lang_name + ", max 2 sentences, with 1 emoji>\n\n"
        "Rules:\n"
        "- 'complaint' = expressing dissatisfaction or a problem.\n"
        "- 'question' = asking for information or clarification.\n"
        "- 'suggestion' = proposing an improvement or new idea.\n"
        "- Never accept orders or promise specific compensation.\n"
        "- If unsure, default to 'question'."
    )
    try:
        raw = await ai.reply(system_prompt=system, history=[], user_message=content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI classify failed: %s", exc)
        return "question", ""
    category = "question"
    reply = ""
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith("category:"):
            val = low.split(":", 1)[1].strip()
            if val in ("complaint", "question", "suggestion"):
                category = val
        elif low.startswith("reply:"):
            reply = stripped.split(":", 1)[1].strip()
    if not reply:
        # AI deviated from format — keep classification, leave reply empty.
        reply = ""
    return category, reply


# ============================================================ SETTINGS

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)
    row = await db.get_user(user.id)
    lang_label = tenant.languages.get(lang, lang)
    phone = (row or {}).get("phone") or "-"
    await msg.reply_text(
        tenant.t(lang, "settings_header", lang_label=lang_label, phone=phone),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=settings_inline_keyboard(
            tenant.t(lang, "settings_lang_btn"),
            tenant.t(lang, "settings_phone_btn"),
        ),
    )


async def settings_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    tenant = _tenant(context)
    await query.edit_message_text(
        tenant.t(tenant.default_language, "lang_prompt"),
        reply_markup=language_keyboard(tenant.languages),
    )


async def settings_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or update.effective_user is None:
        return ConversationHandler.END
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, update.effective_user.id, tenant.default_language)
    share_label = tenant.t(lang, "phone_share_btn")
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=tenant.t(lang, "phone_change_prompt"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=phone_request_keyboard(share_label),
    )
    return PH_WAIT


async def phone_change_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None:
        return PH_WAIT
    tenant = _tenant(context)
    db = _db(context)
    lang = await _lang(db, user.id, tenant.default_language)

    phone: str | None = None
    if msg.contact and msg.contact.user_id == user.id:
        phone = normalize_phone(msg.contact.phone_number)
    elif msg.text and is_valid_phone(msg.text):
        phone = normalize_phone(msg.text)
    if not phone:
        await msg.reply_text(
            tenant.t(lang, "phone_invalid"), parse_mode=ParseMode.MARKDOWN
        )
        return PH_WAIT

    await db.set_phone(user.id, phone)
    await msg.reply_text(
        tenant.t(lang, "phone_changed", phone=phone),
        reply_markup=main_reply_keyboard(tenant, lang, user_id=(update.effective_user.id if update.effective_user else None)),
    )
    return ConversationHandler.END


# ============================================================ REGISTER

def register(app: Application, tenant: Tenant) -> None:
    # Location messages always go to geo_handler (group=0, before order conv).
    app.add_handler(MessageHandler(filters.LOCATION, geo_handler), group=0)

    # Feedback conversation - entry is the localized 'feedback' label.
    fb_texts = [labels.get("feedback") for labels in tenant.menu_labels.values() if labels.get("feedback")]
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text(fb_texts) & ~filters.COMMAND, feedback_start)],
        states={FB_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_capture)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        name="feedback_flow",
        per_message=False,
    ), group=1)

    # Phone-change conversation - entry is the inline 'set_phone' callback.
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(settings_phone_callback, pattern=r"^set_phone$")],
        states={PH_WAIT: [
            MessageHandler(filters.CONTACT, phone_change_capture),
            MessageHandler(filters.TEXT & ~filters.COMMAND, phone_change_capture),
        ]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        name="phone_change_flow",
        per_message=False,
    ), group=1)

    # Settings inline lang button -> re-show language picker.
    app.add_handler(CallbackQueryHandler(settings_lang_callback, pattern=r"^set_lang$"))
    # Address delete callback.
    app.add_handler(CallbackQueryHandler(delete_address_callback, pattern=r"^deladdr:\d+$"))
    # Address edit conversation - entry is the inline 'editaddr:N' callback.
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_address_callback, pattern=r"^editaddr:\d+$")],
        states={ADDR_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addr_edit_capture)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        name="addr_edit_flow",
        per_message=False,
    ), group=1)
