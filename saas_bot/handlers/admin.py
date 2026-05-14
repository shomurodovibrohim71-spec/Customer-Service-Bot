"""Admin-only commands: /admin, /stats, /orders."""
from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
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
from utils.helpers import order_admin_keyboard

logger = logging.getLogger(__name__)


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


def _is_admin(update: Update, tenant: Tenant) -> bool:
    user = update.effective_user
    return bool(user and user.id in tenant.admin_ids)


def _avg_price(tenant: Tenant) -> float:
    """Estimate average price from tenant config services (digits only)."""
    prices: list[float] = []
    for svc in tenant.get("services", []):
        digits = re.sub(r"[^\d]", "", svc.get("price", ""))
        if digits:
            prices.append(float(digits))
    return sum(prices) / len(prices) if prices else 0.0


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin - quick summary dashboard."""
    if update.message is None:
        return
    tenant = _tenant(context)
    if not _is_admin(update, tenant):
        await update.message.reply_text(tenant.msg("not_admin"))
        return
    db = _db(context)
    users_total = await db.count_users()
    users_today = await db.count_new_users_today()
    msg_stats = await db.message_stats()
    orders = await db.count_orders_by_status()
    pending = orders.get("pending", 0)
    text = (
        f"📊 *{tenant.name} - Admin panel*\n\n"
        f"👥 Foydalanuvchilar: *{users_total}* (bugun +{users_today})\n"
        f"💬 Xabarlar (bugun / hafta / jami): *{msg_stats['today']}* / *{msg_stats['week']}* / *{msg_stats['total']}*\n"
        f"🛒 Kutilayotgan buyurtmalar: *{pending}*\n\n"
        "*Buyruqlar:*\n"
        "📈 /stats - batafsil statistika\n"
        "📋 /orders - kutilayotgan buyurtmalar\n"
        "📢 /broadcast <matn> - barchaga xabar yuborish\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats - top users, recent orders, revenue estimate."""
    if update.message is None:
        return
    tenant = _tenant(context)
    if not _is_admin(update, tenant):
        await update.message.reply_text(tenant.msg("not_admin"))
        return
    db = _db(context)
    top = await db.top_users_by_messages(5)
    recent = await db.recent_orders(5)
    by_status = await db.count_orders_by_status()
    total_orders = sum(by_status.values())
    revenue = total_orders * _avg_price(tenant)

    lines = [f"📈 *{tenant.name} - Statistika*\n"]
    lines.append("🏆 *Eng faol mijozlar:*")
    if top:
        for i, row in enumerate(top, start=1):
            label = row.get("name") or row.get("username") or str(row["user_id"])
            lines.append(f"{i}. {label} - {row['n']} xabar")
    else:
        lines.append("_ma'lumot yo'q_")
    lines.append("\n🛒 *Oxirgi buyurtmalar:*")
    if recent:
        for o in recent:
            status_emoji = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌"}.get(o["status"], "•")
            lines.append(
                f"{status_emoji} #{o['id']} - {o['full_name']} - {o['service']}"
            )
    else:
        lines.append("_buyurtmalar yo'q_")
    lines.append(f"\n💰 *Daromad (taxminiy):* {revenue:,.0f} so'm")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/orders - list pending orders with action buttons."""
    if update.message is None:
        return
    tenant = _tenant(context)
    if not _is_admin(update, tenant):
        await update.message.reply_text(tenant.msg("not_admin"))
        return
    db = _db(context)
    pending = await db.pending_orders(20)
    if not pending:
        await update.message.reply_text("✅ Kutilayotgan buyurtmalar yo'q.")
        return
    for o in pending:
        text = (
            f"🛒 *Buyurtma* #{o['id']}\n\n"
            f"👤 Mijoz: {o['full_name']}\n"
            f"📞 Telefon: {o['phone']}\n"
            f"🍔 Taom: {o['service']}\n"
            f"🕐 Vaqt: {o['preferred_time']}\n"
            f"📅 Yaratilgan: {o['created_at']}"
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=order_admin_keyboard(o["id"]),
        )


async def order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Confirm / Cancel buttons attached to admin order messages.

    Simple flow: mark status, edit admin message, notify customer. No courier
    prompt - admin can message the customer directly if extra info is needed.
    """
    query = update.callback_query
    if query is None or query.data is None:
        return
    tenant = _tenant(context)
    user = update.effective_user
    if user is None or user.id not in tenant.admin_ids:
        await query.answer(tenant.msg("not_admin"), show_alert=True)
        return
    await query.answer()
    db = _db(context)
    action, _, raw_id = query.data.partition(":")
    try:
        order_id = int(raw_id)
    except ValueError:
        return
    new_status = "confirmed" if action == "adm_confirm" else "cancelled"
    await db.set_order_status(order_id, new_status)
    order = await db.get_order(order_id)
    if order is None:
        await query.edit_message_text(f"❌ Buyurtma #{order_id} topilmadi.")
        return
    emoji_suffix = "✅ TASDIQLANDI" if new_status == "confirmed" else "❌ BEKOR QILINDI"
    await query.edit_message_text(
        f"{emoji_suffix} #{order_id}\n\n"
        f"👤 {order['full_name']}\n📞 {order['phone']}\n"
        f"🍔 {order['service']}\n📍 {order.get('address') or '-'}\n"
        f"🕐 {order.get('preferred_time') or '-'}",
    )
    try:
        cust_row = await db.get_user(order["user_id"])
        cust_lang = (cust_row or {}).get("language") or tenant.default_language
        amount = int(order.get('amount') or 0)
        service = order.get('service', '-')
        addr = order.get('address') or '-'
        ptime = order.get('preferred_time') or '-'
        if new_status == "confirmed":
            if cust_lang == "ru":
                customer_text = (
                    f"✅ *Ваш заказ #{order_id} подтверждён!*\n\n"
                    f"🍔 {service}\n📍 {addr}\n🕐 {ptime}\n"
                    f"💰 Сумма: {amount:,} сум\n\nСкоро свяжемся 🚗"
                )
            elif cust_lang == "en":
                customer_text = (
                    f"✅ *Your order #{order_id} is confirmed!*\n\n"
                    f"🍔 {service}\n📍 {addr}\n🕐 {ptime}\n"
                    f"💰 Amount: {amount:,} so'm\n\nWe'll contact you soon 🚗"
                )
            else:
                customer_text = (
                    f"✅ *Buyurtmangiz #{order_id} tasdiqlandi!*\n\n"
                    f"🍔 {service}\n📍 {addr}\n🕐 {ptime}\n"
                    f"💰 Summa: {amount:,} so'm\n\nTez orada bog'lanamiz 🚗"
                )
        else:
            if cust_lang == "ru":
                customer_text = (
                    f"❌ Ваш заказ #{order_id} отменён.\n"
                    f"Пожалуйста, оформите заказ снова."
                )
            elif cust_lang == "en":
                customer_text = (
                    f"❌ Your order #{order_id} has been cancelled.\n"
                    f"Please place a new order."
                )
            else:
                customer_text = (
                    f"❌ Buyurtmangiz #{order_id} bekor qilindi.\n"
                    f"Iltimos qayta buyurtma bering."
                )
        await context.bot.send_message(
            chat_id=order["user_id"], text=customer_text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] customer notify failed: %s", tenant.id, exc)


def register(app: Application) -> None:
    """Wire admin commands and the order-action callback."""
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(
        CallbackQueryHandler(order_action_callback, pattern=r"^adm_(confirm|cancel):\d+$")
    )
