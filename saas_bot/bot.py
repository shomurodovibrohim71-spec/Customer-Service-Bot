"""Multi-tenant Telegram bot runner."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import time as dt_time
from pathlib import Path

from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder, CallbackContext

from config.settings import BASE_DIR, LOG_LEVEL
from core.ai import AIClient
from core.database import Database
from core.seed import seed_tenant
from core.tenant import Tenant, load_tenants
from handlers import admin as admin_handler
from handlers import admin_menu as admin_menu_handler
from handlers import admin_panel as admin_panel_handler
from handlers import broadcast as broadcast_handler
from handlers import chat as chat_handler
from handlers import features as features_handler
from handlers import menu_router as menu_router_handler
from handlers import order as order_handler
from handlers import start as start_handler


def configure_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)


logger = logging.getLogger("saas_bot")


async def build_application(tenant: Tenant, ai: AIClient) -> tuple[Application, Database]:
    """Wire all handlers for one tenant. Handler groups matter:

      group=0: admin conversations and one-shot admin commands (must win)
      group=1: order ConversationHandler (consumes 'order' button)
      group=5: menu router (reply-keyboard button taps)
      group=10: AI chat catch-all
    """
    app = (
        ApplicationBuilder()
        .token(tenant.bot_token)
        .concurrent_updates(True)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(60.0)
        .build()
    )
    db = Database(tenant.id)
    await db.connect()
    await seed_tenant(db, tenant)

    app.bot_data["tenant"] = tenant
    app.bot_data["db"] = db
    app.bot_data["ai"] = ai

    start_handler.register(app)                # group default
    admin_panel_handler.register(app, tenant)  # admin reply-keyboard router (group=2)
    admin_handler.register(app)                # /admin (handled now by admin_panel) /stats /orders
    admin_menu_handler.register(app, tenant)   # /addproduct /delproduct /addbranch /delbranch + admin button entries
    broadcast_handler.register(app)            # /broadcast (legacy)
    features_handler.register(app, tenant)     # geo, qr, points, addresses, feedback, settings
    order_handler.register(app, tenant)        # order flow (group=1)
    menu_router_handler.register(app)          # reply-keyboard router (group=5)
    chat_handler.register(app)                 # AI catch-all (group=10)

    app.add_error_handler(_error_handler)

    # Schedule daily report at 23:00 local time (Tashkent UTC+5).
    if app.job_queue is not None:
        app.job_queue.run_daily(
            _daily_report_job,
            time=dt_time(18, 0, 0),  # 18:00 UTC = 23:00 Tashkent (UTC+5)
            name=f"daily_report_{tenant.id}",
        )
        logger.info("[%s] Daily report scheduled at 23:00 Tashkent", tenant.id)

    return app, db


async def _error_handler(update, context) -> None:
    tenant = context.bot_data.get("tenant")
    tag = tenant.id if tenant else "?"
    logger.error("[%s] Update %s caused error: %s", tag, update, context.error)


async def _daily_report_job(context: CallbackContext) -> None:
    """Sends a daily summary to all admin_ids at 23:00."""
    tenant: Tenant = context.bot_data["tenant"]
    db: Database = context.bot_data["db"]
    try:
        s = await db.today_summary()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] daily_report: db error: %s", tenant.id, exc)
        return

    top_lines = "\n".join(
        f"  {i+1}. {t['name']} — {t['qty']} ta" for i, t in enumerate(s.get("top", []))
    ) or "  —"

    revenue = s["revenue"]
    rev_fmt = f"{revenue:,}".replace(",", " ")
    msg = (
        f"📊 *Kunlik hisobot — {_today_date()}*\n\n"
        f"📦 Jami buyurtma: *{s['total']} ta*\n"
        f"💰 Tushum: *{rev_fmt} so'm*\n\n"
        f"✅ Tasdiqlangan: {s['confirmed']}\n"
        f"👨‍🍳 Tayyorlanmoqda: {s['preparing']}\n"
        f"🚗 Yo'lda: {s['on_the_way']}\n"
        f"📦 Yetkazilgan: {s['delivered']}\n"
        f"⏳ Kutilmoqda: {s['pending']}\n"
        f"❌ Bekor: {s['cancelled']}\n\n"
        f"🏆 *Top taomlar:*\n{top_lines}"
    )

    for admin_id in tenant.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=msg, parse_mode="Markdown",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] daily_report: send to %s failed: %s", tenant.id, admin_id, exc)


def _today_date() -> str:
    from datetime import date
    return date.today().strftime("%d.%m.%Y")


async def run_tenant(tenant: Tenant, ai: AIClient) -> None:
    app, db = await build_application(tenant, ai)
    logger.info("Starting bot for tenant %s (%s)", tenant.id, tenant.name)
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        stop_event = asyncio.Event()
        await stop_event.wait()
    except asyncio.CancelledError:
        logger.info("Stopping tenant %s", tenant.id)
        raise
    except TelegramError as exc:
        logger.error("[%s] Telegram error: %s", tenant.id, exc)
    finally:
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
            await app.shutdown()
        finally:
            await db.close()
            logger.info("Tenant %s shut down", tenant.id)


async def run_all() -> None:
    tenants_dir = BASE_DIR / "config" / "tenants"
    tenants = load_tenants(tenants_dir)
    if not tenants:
        logger.error("No tenants loaded. Check %s and ensure bot tokens are set.", tenants_dir)
        return

    ai = AIClient()
    loop = asyncio.get_running_loop()
    tasks = [asyncio.create_task(run_tenant(t, ai), name=f"bot-{t.id}") for t in tenants]

    def _signal_handler() -> None:
        logger.info("Shutdown signal received, cancelling tenants...")
        for task in tasks:
            task.cancel()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                pass

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        _signal_handler()
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
