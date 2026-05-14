"""/start onboarding: language -> phone -> branch -> main reply keyboard."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.database import Database
from core.tenant import Tenant
from utils.helpers import (
    admin_reply_keyboard,
    is_valid_phone,
    language_keyboard,
    main_reply_keyboard,
    normalize_phone,
    phone_request_keyboard,
    register_branch_keyboard,
)


def _keyboard_for(tenant, user_id: int, lang: str):
    """Return the admin keyboard if user is admin and not in user-view mode, else main."""
    return admin_reply_keyboard(tenant, lang) if tenant.is_admin(user_id) else main_reply_keyboard(tenant, lang)

logger = logging.getLogger(__name__)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def _send_phone_prompt(message_or_chat, context, tenant: Tenant, lang: str) -> None:
    share_label = tenant.t(lang, "phone_share_btn")
    if hasattr(message_or_chat, "reply_text"):
        await message_or_chat.reply_text(
            tenant.t(lang, "phone_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=phone_request_keyboard(share_label),
        )
    else:
        await context.bot.send_message(
            chat_id=message_or_chat,
            text=tenant.t(lang, "phone_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=phone_request_keyboard(share_label),
        )


async def _send_branch_prompt(chat_id: int, context, tenant: Tenant, db: Database, lang: str) -> None:
    """Deprecated: branch selection now happens per-order based on user location.

    Kept as a thin shim that just sends the main menu.
    """
    await _send_main_menu_for(chat_id, context, tenant, lang)


async def _send_main_menu_for(chat_id: int, context, tenant: Tenant, lang: str) -> None:
    user_id = context._user_id if hasattr(context, "_user_id") else None
    user_view = context.user_data.get("user_view", False)
    is_admin = tenant.is_admin(user_id) and not user_view
    if is_admin:
        text = tenant.admin_t(lang, "admin_welcome")
        kb = admin_reply_keyboard(tenant, lang)
    else:
        text = tenant.t(lang, "registered")
        kb = main_reply_keyboard(tenant, lang)
    await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
    )


# =================================================================== /start

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.message is None:
        return
    tenant = _tenant(context)
    db = _db(context)
    await db.upsert_user(user.id, user.full_name or "", user.username)

    row = await db.get_user(user.id)
    lang = (row or {}).get("language")
    phone = (row or {}).get("phone")
    branch_id = (row or {}).get("branch_id")

    if not lang:
        await update.message.reply_text(
            tenant.t(tenant.default_language, "lang_prompt"),
            reply_markup=language_keyboard(tenant.languages),
        )
        return

    if not phone:
        await update.message.reply_text(
            tenant.t(lang, "welcome"), parse_mode=ParseMode.MARKDOWN
        )
        await _send_phone_prompt(update.message, context, tenant, lang)
        return

    # Fully onboarded -> main menu (admin or user keyboard).
    user_view = context.user_data.get("user_view", False)
    is_admin = tenant.is_admin(user.id) and not user_view
    if is_admin:
        await update.message.reply_text(
            tenant.admin_t(lang, "admin_welcome"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_reply_keyboard(tenant, lang),
        )
    else:
        await update.message.reply_text(
            tenant.t(lang, "welcome"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_reply_keyboard(tenant, lang),
        )


# ============================================================= language

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or query.data is None or user is None:
        return
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = query.data.split(":", 1)[1]
    if lang not in tenant.languages:
        return
    await db.set_language(user.id, lang)

    row = await db.get_user(user.id)
    phone = (row or {}).get("phone")

    await query.edit_message_text(
        tenant.t(lang, "welcome"), parse_mode=ParseMode.MARKDOWN
    )
    chat_id = query.message.chat_id
    if not phone:
        await _send_phone_prompt(chat_id, context, tenant, lang)
    else:
        kb = admin_reply_keyboard(tenant, lang) if tenant.is_admin(user.id) and not context.user_data.get("user_view") else main_reply_keyboard(tenant, lang)
        await context.bot.send_message(
            chat_id=chat_id,
            text=tenant.t(lang, "language_changed"),
            reply_markup=kb,
        )


async def change_language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    tenant = _tenant(context)
    await update.message.reply_text(
        tenant.t(tenant.default_language, "lang_prompt"),
        reply_markup=language_keyboard(tenant.languages),
    )


# ============================================================ phone

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captures phone during onboarding.

    Triggered by both:
    - the 'request_contact' KeyboardButton (filters.CONTACT)
    - typed phone-shaped text (filters.TEXT)

    Early-exits silently for already-registered users so other handlers can
    process the message.
    """
    if update.message is None or update.effective_user is None:
        return
    msg = update.message
    user = update.effective_user
    tenant = _tenant(context)
    db = _db(context)

    is_contact = bool(msg.contact and msg.contact.user_id == user.id)
    looks_like_phone = bool(msg.text and is_valid_phone(msg.text))
    # If it's neither a contact share nor phone-shaped text, leave it alone.
    if not is_contact and not looks_like_phone:
        return

    row = await db.get_user(user.id)
    if row and row.get("phone"):
        # User already onboarded - don't capture again, but also don't echo
        # a "phone saved" message. Let other handlers (chat AI) process.
        return
    lang = (row or {}).get("language") or tenant.default_language

    phone = normalize_phone(msg.contact.phone_number) if is_contact else normalize_phone(msg.text)
    if not phone:
        await msg.reply_text(
            tenant.t(lang, "phone_invalid"), parse_mode=ParseMode.MARKDOWN
        )
        # Stop propagation so chat.py doesn't also reply.
        raise ApplicationHandlerStop()

    await db.set_phone(user.id, phone)
    await _send_main_menu_for(msg.chat_id, context, tenant, lang)
    # Stop further handlers from processing this message.
    raise ApplicationHandlerStop()


# ============================================================ branch

async def register_branch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or query.data is None or user is None:
        return
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = await _user_lang(db, user.id, tenant.default_language)
    try:
        branch_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    branch = await db.get_branch(branch_id)
    if branch is None:
        return
    await db.set_user_branch(user.id, branch_id)
    await query.edit_message_text(
        tenant.t(lang, "register_branch_saved", branch=branch["name"]),
        parse_mode=ParseMode.MARKDOWN,
    )
    kb = admin_reply_keyboard(tenant, lang) if tenant.is_admin(user.id) and not context.user_data.get("user_view") else main_reply_keyboard(tenant, lang)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=tenant.t(lang, "main_menu"),
        reply_markup=kb,
    )


async def _user_lang(db: Database, user_id: int, default: str) -> str:
    row = await db.get_user(user_id)
    return (row or {}).get("language") or default


# ================================================================ register

def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:[a-z_]+$"))
    # Legacy: register_branch_callback no longer wired - branch selection is per-order.
    # IMPORTANT: phone_handler must NOT catch every TEXT update, otherwise it
    # will block sibling group=0 handlers (addproduct/addbranch entry points)
    # since PTB only invokes one handler per group per update.
    # We restrict it to phone-shaped text (+998..., 12-15 digits) so normal
    # admin button taps fall through to their own handlers.
    phone_regex = filters.Regex(r"^\s*\+?[\d\s\-\(\)]{9,18}\s*$")
    app.add_handler(
        MessageHandler(filters.CONTACT | phone_regex, phone_handler),
        group=0,
    )
