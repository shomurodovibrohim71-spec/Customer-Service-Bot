"""Admin /broadcast command: send a message to every user of the tenant."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from core.database import Database
from core.tenant import Tenant

logger = logging.getLogger(__name__)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/broadcast <message>` - admin-only fanout to all known users.

    Sends with a small inter-message delay to stay within Telegram's ~30 msg/sec
    global limit; users who blocked the bot are silently skipped.
    """
    if update.message is None:
        return
    tenant = _tenant(context)
    user = update.effective_user
    if user is None or user.id not in tenant.admin_ids:
        await update.message.reply_text(tenant.msg("not_admin"))
        return

    if not context.args:
        await update.message.reply_text(
            "📢 Foydalanish: `/broadcast <xabar matni>`",
            parse_mode="Markdown",
        )
        return

    text = " ".join(context.args).strip()
    db = _db(context)
    async with db.conn.execute(
        "SELECT id FROM users WHERE tenant_id=?", (tenant.id,)
    ) as cur:
        rows = await cur.fetchall()
    user_ids = [int(r["id"]) for r in rows]

    if not user_ids:
        await update.message.reply_text("⚠️ Foydalanuvchilar topilmadi.")
        return

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(
        f"📤 Yuborilmoqda... 0/{len(user_ids)}"
    )
    for i, uid in enumerate(user_ids, start=1):
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Forbidden:
            failed += 1
        except TelegramError as exc:
            failed += 1
            logger.warning("[%s] broadcast to %s failed: %s", tenant.id, uid, exc)
        if i % 25 == 0:
            try:
                await status_msg.edit_text(f"📤 Yuborilmoqda... {i}/{len(user_ids)}")
            except TelegramError:
                pass
        await asyncio.sleep(0.05)  # ~20 msg/s, safe under 30 msg/s limit

    await status_msg.edit_text(
        f"✅ Yuborildi: {sent}\n❌ Xatolik: {failed}\n📊 Jami: {len(user_ids)}"
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("broadcast", broadcast_command))
