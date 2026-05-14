"""Free-form AI chat handler powered by Claude."""
from __future__ import annotations

import logging

import anthropic
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import FALLBACK_ERROR_MESSAGE, MAX_HISTORY_MESSAGES
from core.ai import AIClient
from core.database import Database
from core.tenant import Tenant
from utils.helpers import back_to_menu_keyboard

# Localized fallback when the AI fails — used until a tenant-specific translation
# is available in TEXTS.
_FALLBACK_BY_LANG = {
    "uz": "⚠️ Kechirasiz, hozir javob bera olmayman.\n\n"
          "Iltimos, biroz keyin urinib ko'ring yoki operator bilan bog'laning:\n📞 {phone}",
    "en": "⚠️ Sorry, I can't reply right now.\n\n"
          "Please try again later or contact our operator:\n📞 {phone}",
    "ru": "⚠️ Извините, сейчас я не могу ответить.\n\n"
          "Попробуйте позже или свяжитесь с оператором:\n📞 {phone}",
}

logger = logging.getLogger(__name__)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


def _ai(context: ContextTypes.DEFAULT_TYPE) -> AIClient:
    return context.bot_data["ai"]


async def ai_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle every free-text message that wasn't captured by another handler.

    Important: PTB dispatches the same update to every handler group. The order
    ConversationHandler (group=1) and the menu router (group=5) do not stop
    propagation, so without explicit skips this handler would also reply to:
      - menu button taps ("👨‍🍳 Buyurtma berish" etc.)
      - delivery / pickup labels picked while in the order flow
      - feedback / phone-change conversations
      - admin /addproduct, /addbranch flows
    """
    message = update.message
    user = update.effective_user
    if message is None or user is None or not message.text:
        return

    tenant = _tenant(context)
    user_text = message.text.strip()

    # Skip any localized menu-button label - those are owned by other handlers.
    if tenant.action_from_label(user_text):
        return
    if tenant.admin_action_from_label(user_text):
        return

    # Skip delivery/pickup reply-keyboard texts (consumed by the order conv).
    for lang_labels in tenant.menu_labels.values():
        pass  # already covered by action_from_label
    for lang in tenant.texts.values():
        if user_text in (lang.get("btn_delivery"), lang.get("btn_pickup"),
                          lang.get("phone_share_btn"), lang.get("settings_lang_btn"),
                          lang.get("settings_phone_btn")):
            return

    # Skip when a multi-step flow is active.
    if context.user_data.get("order"):
        return  # active order ConversationHandler
    if context.user_data.get("new_product") or context.user_data.get("new_branch"):
        return  # admin /addproduct or /addbranch flow

    db = _db(context)
    ai = _ai(context)

    # Skip if user hasn't completed onboarding (no language or no phone yet).
    # The dedicated onboarding handlers own those messages.
    row = await db.get_user(user.id)
    if not row or not row.get("language") or not row.get("phone"):
        return

    # Skip AI replies for active admins - they shouldn't see "Bosh menyu"
    # inline buttons under stray text. Admins use commands / admin keyboard.
    if tenant.is_admin(user.id) and not context.user_data.get("user_view", False):
        return

    await db.upsert_user(user.id, user.full_name or "", user.username)
    await db.save_message(user.id, "user", user_text)

    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id, action=ChatAction.TYPING
        )
    except Exception:  # noqa: BLE001
        pass

    history = await db.get_history(user.id, MAX_HISTORY_MESSAGES)
    history = [h for h in history if h["content"] != user_text or h["role"] != "user"]

    user_lang = (row or {}).get("language") or tenant.default_language
    products = await db.list_products()
    branches = await db.list_branches()
    try:
        reply = await ai.reply(
            system_prompt=tenant.render_system_prompt(
                products=products, branches=branches, lang=user_lang,
            ),
            history=history,
            user_message=user_text,
        )
    except anthropic.APIError as exc:
        logger.error("[%s] Claude API error: %s", tenant.id, exc)
        reply = _FALLBACK_BY_LANG.get(user_lang, _FALLBACK_BY_LANG["uz"]).format(phone=tenant.get("phone", ""))
        await message.reply_text(reply, reply_markup=back_to_menu_keyboard(lang=user_lang))
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Unexpected AI error", tenant.id, exc_info=exc)
        reply = _FALLBACK_BY_LANG.get(user_lang, _FALLBACK_BY_LANG["uz"]).format(phone=tenant.get("phone", ""))
        await message.reply_text(reply, reply_markup=back_to_menu_keyboard(lang=user_lang))
        return

    await db.save_message(user.id, "assistant", reply)

    try:
        await message.reply_text(
            reply,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_menu_keyboard(lang=user_lang),
        )
    except Exception:
        # Markdown parsing can fail on user-influenced replies; resend as plain text.
        await message.reply_text(reply, reply_markup=back_to_menu_keyboard(lang=user_lang))


def register(app: Application) -> None:
    """Wire the catch-all text handler. Must be registered LAST so other handlers win."""
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_message_handler),
        group=10,
    )
