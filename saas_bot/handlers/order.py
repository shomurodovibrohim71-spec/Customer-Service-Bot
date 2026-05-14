"""Cart-based order flow (Mini Food-style, all inside Telegram).

Flow:
1. User taps '👨‍🍳 Buyurtma berish'.
2. If user has a saved address, ask 'Deliver to <addr>? [Ha/Yo'q]'.
   - Yo'q -> ask to send geolocation or type new address.
   - No saved address -> same address-collection step.
3. Show categories (inline 2-col).
4. Tap category -> show each product as a photo card with '➕ Qo'shish' and the
   cart count button at the top.
5. Tap 'Qo'shish' -> increment cart, toast.
6. Tap '🛒 Savatcha' -> view cart, +/- per item, '✅ Buyurtma berish' to checkout.
7. Checkout: ask time, then confirm summary, then save order + notify admins.
"""
from __future__ import annotations

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

from config.settings import get_webapp_url
from core.database import Database
from core.geo import nearest_branches
from core.geocoder import reverse_geocode
from core.tenant import Tenant
from utils.cart import (
    cart_add,
    cart_clear,
    cart_count,
    cart_lines,
    cart_set,
    cart_total,
    get_cart,
)
from utils.helpers import (
    delivery_method_reply_keyboard,
    geo_confirm_keyboard,
    main_reply_keyboard,
    order_admin_keyboard,
    pickup_branch_keyboard,
)

logger = logging.getLogger(__name__)

# Conversation states
(ADDR_CONFIRM, ADDR_INPUT, GEO_CONFIRM, DELIVERY_METHOD,
 PICKUP_BRANCH, BROWSE, CART, ASK_TIME, CONFIRM) = range(9)


# ---------------------------------------------------------- helpers

def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def _user_lang(db: Database, user_id: int, default: str) -> str:
    row = await db.get_user(user_id)
    return (row or {}).get("language") or default


def _categories_keyboard(tenant: Tenant, lang: str, categories: list[str], cart_n: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cat in categories:
        row.append(InlineKeyboardButton(cat, callback_data=f"cat:{cat}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if cart_n > 0:
        rows.append([InlineKeyboardButton(
            tenant.t(lang, "cart_btn", count=cart_n),
            callback_data="cart_view",
        )])
    rows.append([
        InlineKeyboardButton("⬅ Orqaga", callback_data="back_to_delivery"),
        InlineKeyboardButton("❌ Bekor", callback_data="order_cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _product_keyboard(product_id: int, cat: str, in_cart: int, cart_n: int, tenant: Tenant, lang: str) -> InlineKeyboardMarkup:
    if in_cart == 0:
        first_row = [InlineKeyboardButton("➕ Qo'shish", callback_data=f"add:{product_id}:{cat}")]
    else:
        first_row = [
            InlineKeyboardButton("➖", callback_data=f"dec:{product_id}:{cat}"),
            InlineKeyboardButton(f"{in_cart}", callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"inc:{product_id}:{cat}"),
        ]
    rows = [first_row]
    if cart_n > 0:
        rows.append([InlineKeyboardButton(
            tenant.t(lang, "cart_btn", count=cart_n),
            callback_data="cart_view",
        )])
    rows.append([InlineKeyboardButton(tenant.t(lang, "back_to_categories"),
                                       callback_data="back_categories")])
    return InlineKeyboardMarkup(rows)


def _cart_keyboard(tenant: Tenant, lang: str, cart: dict[int, int], products_by_id: dict[int, dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for pid, qty in cart.items():
        p = products_by_id.get(pid)
        if not p:
            continue
        rows.append([
            InlineKeyboardButton(p["name"][:22], callback_data="noop"),
            InlineKeyboardButton("➖", callback_data=f"cdec:{pid}"),
            InlineKeyboardButton(str(qty), callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"cinc:{pid}"),
        ])
    rows.append([
        InlineKeyboardButton(tenant.t(lang, "back_to_categories"), callback_data="back_categories"),
        InlineKeyboardButton(tenant.t(lang, "clear_cart_btn"), callback_data="cart_clear"),
    ])
    if cart:
        rows.append([InlineKeyboardButton(tenant.t(lang, "checkout_btn"),
                                           callback_data="checkout")])
    return InlineKeyboardMarkup(rows)


def _addr_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha", callback_data="addr_yes"),
         InlineKeyboardButton("❌ Yo'q", callback_data="addr_no")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="order_cancel")],
    ])


def _time_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅ Orqaga", callback_data="back_to_cart"),
        InlineKeyboardButton("❌ Bekor", callback_data="order_cancel"),
    ]])


def _confirm_keyboard_with_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="order_confirm")],
        [InlineKeyboardButton("⬅ Orqaga", callback_data="back_to_time"),
         InlineKeyboardButton("❌ Bekor", callback_data="order_cancel")],
    ])


# ========================================================== Entry

def order_entry_filter(tenant: Tenant) -> filters.BaseFilter:
    texts = [labels.get("order") for labels in tenant.menu_labels.values() if labels.get("order")]
    return filters.Text(texts)


async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    tenant = _tenant(context)
    db = _db(context)
    user = update.effective_user
    lang = await _user_lang(db, user.id, tenant.default_language)

    row = await db.get_user(user.id)
    if not row or not row.get("phone"):
        await update.message.reply_text(
            tenant.t(lang, "phone_prompt"), parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # If a public Mini App URL is configured, send a WebApp keyboard button
    # and let the user place the order inside Telegram's WebApp container.
    webapp_url = get_webapp_url()
    if webapp_url:
        # uid is a fallback identity if Telegram's initData isn't available
        # (e.g., BotFather domain not set, older client, opened outside chat).
        url = f"{webapp_url}/webapp?tenant={tenant.id}&uid={user.id}&lang={lang}"
        btn_label = {
            "uz": "🛒 Buyurtma berish",
            "en": "🛒 Place an order",
            "ru": "🛒 Сделать заказ",
        }.get(lang, "🛒 Buyurtma berish")
        intro = {
            "uz": "🛒 Pastdagi tugmani bosing — buyurtma sahifasi ochiladi.\n"
                  "Yoki *🏠 Bosh menyu* bilan asosiy menyuga qayting.",
            "en": "🛒 Tap the button below — the order page will open.\n"
                  "Or use *🏠 Main menu* to go back.",
            "ru": "🛒 Нажмите кнопку ниже — откроется страница заказа.\n"
                  "Или вернитесь в *🏠 Главное меню*.",
        }.get(lang)
        from utils.helpers import home_button_label
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton(text=btn_label, web_app=WebAppInfo(url=url))],
                [KeyboardButton(text=home_button_label(lang))],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            intro, parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
        )
        return ConversationHandler.END

    context.user_data.setdefault("order", {})
    context.user_data["order"]["lang"] = lang
    context.user_data["order"]["full_name"] = row.get("name") or user.full_name or ""
    context.user_data["order"]["phone"] = row.get("phone")

    # Try the most recent saved address.
    addrs = await db.list_addresses(user.id)
    if addrs:
        latest = addrs[-1]
        context.user_data["order"]["address_candidate"] = latest["text"]
        await update.message.reply_text(
            tenant.t(lang, "order_confirm_address", address=latest["text"]),
            reply_markup=_addr_confirm_keyboard(),
        )
        return ADDR_CONFIRM

    await update.message.reply_text(
        tenant.t(lang, "order_no_address"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ADDR_INPUT


# ========================================================== Address

async def addr_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ADDR_CONFIRM
    await query.answer()
    tenant = _tenant(context)
    lang = context.user_data["order"]["lang"]
    if query.data == "addr_yes":
        context.user_data["order"]["address"] = context.user_data["order"]["address_candidate"]
        return await _ask_delivery_method(query, context, tenant, lang)
    # addr_no
    await query.edit_message_text(
        tenant.t(lang, "order_no_address"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ADDR_INPUT


async def addr_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Accept a location (-> reverse-geocode + confirm) or a typed address (use as is)."""
    if update.message is None:
        return ADDR_INPUT
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]

    if update.message.location:
        loc = update.message.location
        lat, lon = loc.latitude, loc.longitude
        # Show 'detecting...' immediately so the user sees feedback.
        await update.message.reply_text(tenant.t(lang, "geo_detecting"))
        address = await reverse_geocode(lat, lon, lang)
        if not address:
            address = f"GPS {lat:.5f}, {lon:.5f}"
        context.user_data["order"]["pending_address"] = address
        context.user_data["order"]["pending_lat"] = lat
        context.user_data["order"]["pending_lon"] = lon
        await update.message.reply_text(
            tenant.t(lang, "geo_address_confirm", address=address),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=geo_confirm_keyboard(
                tenant.t(lang, "geo_address_yes"),
                tenant.t(lang, "geo_address_no"),
            ),
        )
        return GEO_CONFIRM

    if update.message.text:
        addr_text = update.message.text.strip()
        context.user_data["order"]["address"] = addr_text
        user = update.effective_user
        if user:
            await db.add_address(user_id=user.id, text=addr_text)
        return await _ask_delivery_method(update.message, context, tenant, lang)
    return ADDR_INPUT


# -------------------------------------------------- Geocoded address confirm

async def geo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return GEO_CONFIRM
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    pending = context.user_data["order"].get("pending_address", "")
    lat = context.user_data["order"].get("pending_lat")
    lon = context.user_data["order"].get("pending_lon")
    user = update.effective_user

    if query.data == "geo_yes" and pending:
        context.user_data["order"]["address"] = pending
        context.user_data["order"]["address_lat"] = lat
        context.user_data["order"]["address_lon"] = lon
        if user:
            await db.add_address(user_id=user.id, text=pending, lat=lat, lon=lon)
        await query.edit_message_text(
            tenant.t(lang, "geo_address_confirm", address=pending),
            parse_mode=ParseMode.MARKDOWN,
        )
        return await _ask_delivery_method(query.message, context, tenant, lang)
    # geo_no - ask user to type manually.
    await query.edit_message_text(
        tenant.t(lang, "geo_type_address"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ADDR_INPUT


# ========================================================== Delivery method

async def _ask_delivery_method(message_or_query, context, tenant: Tenant, lang: str) -> int:
    """Show a two-button reply keyboard: Delivery vs Pickup."""
    text = tenant.t(lang, "delivery_method_prompt")
    kb = delivery_method_reply_keyboard(
        tenant.t(lang, "btn_delivery"),
        tenant.t(lang, "btn_pickup"),
    )
    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        chat_id = getattr(message_or_query, "chat_id", None) or message_or_query.message.chat_id
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
    return DELIVERY_METHOD


async def delivery_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped 🚚 Yetkazib berish or 🚶 Olib ketish reply button."""
    if update.message is None or not update.message.text:
        return DELIVERY_METHOD
    tenant = _tenant(context)
    db = _db(context)
    user = update.effective_user
    lang = context.user_data["order"]["lang"]
    text = update.message.text.strip()

    delivery_label = tenant.t(lang, "btn_delivery")
    pickup_label = tenant.t(lang, "btn_pickup")

    if text == delivery_label:
        context.user_data["order"]["delivery_type"] = "delivery"
        context.user_data["order"]["delivery_label"] = tenant.t(lang, "delivery_label_value")
        # Auto-pick the nearest branch to the user's address (if we have coords).
        branches = await db.list_branches()
        user_lat = context.user_data["order"].get("address_lat")
        user_lon = context.user_data["order"].get("address_lon")
        nearest = nearest_branches(branches, user_lat, user_lon, limit=1) if branches else []
        if nearest and nearest[0].get("distance_km") is not None:
            b = nearest[0]
            context.user_data["order"]["branch"] = b["name"]
            context.user_data["order"]["branch_id"] = b["id"]
            await update.message.reply_text(
                tenant.t(lang, "delivery_auto_branch", branch=b["name"], dist=b["distance_km"]),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif branches:
            # No coords - pick the first listed branch as default.
            b = branches[0]
            context.user_data["order"]["branch"] = b["name"]
            context.user_data["order"]["branch_id"] = b["id"]
        return await _enter_browse(update.message, context, tenant, lang)

    if text == pickup_label:
        context.user_data["order"]["delivery_type"] = "pickup"
        context.user_data["order"]["delivery_label"] = tenant.t(lang, "pickup_label_value")
        branches = await db.list_branches()
        if not branches:
            return await _enter_browse(update.message, context, tenant, lang)
        user_lat = context.user_data["order"].get("address_lat")
        user_lon = context.user_data["order"].get("address_lon")
        ranked = nearest_branches(branches, user_lat, user_lon, limit=5)
        # Show distance in button labels when available.
        rows = []
        for b in ranked:
            d = b.get("distance_km")
            if d is not None:
                label = tenant.t(lang, "branch_distance_btn", name=b["name"], dist=d)
            else:
                label = b["name"]
            rows.append([InlineKeyboardButton(label, callback_data=f"pickbranch:{b['id']}")])
        # If we trimmed the list, offer the full list.
        if len(branches) > len(ranked):
            rows.append([InlineKeyboardButton(
                tenant.t(lang, "show_all_branches"), callback_data="pickbranch_all"
            )])
        rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel")])
        header_key = "pickup_nearest_header" if (user_lat is not None and user_lon is not None) else "pickup_no_coords"
        await update.message.reply_text(
            tenant.t(lang, header_key),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return PICKUP_BRANCH

    # Anything else - re-prompt.
    await update.message.reply_text(
        tenant.t(lang, "delivery_method_prompt"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=delivery_method_reply_keyboard(delivery_label, pickup_label),
    )
    return DELIVERY_METHOD


async def pickup_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return PICKUP_BRANCH
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    if query.data == "order_cancel":
        return await _cancel(update, context)
    if query.data == "pickbranch_all":
        # Show the unfiltered list (no distance trim).
        branches = await db.list_branches()
        rows = [[InlineKeyboardButton(b["name"], callback_data=f"pickbranch:{b['id']}")]
                for b in branches]
        rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel")])
        await query.edit_message_text(
            tenant.t(lang, "pickup_no_coords"),
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return PICKUP_BRANCH
    try:
        bid = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return PICKUP_BRANCH
    branch = await db.get_branch(bid)
    if branch is None:
        return PICKUP_BRANCH
    context.user_data["order"]["branch"] = branch["name"]
    context.user_data["order"]["branch_id"] = branch["id"]
    await query.edit_message_text(
        tenant.t(lang, "pickup_branch_set", branch=branch["name"]),
        parse_mode=ParseMode.MARKDOWN,
    )
    return await _enter_browse(query, context, tenant, lang)


# ========================================================== Browse categories

async def _enter_browse(message_or_query, context, tenant: Tenant, lang: str) -> int:
    db = _db(context)
    categories = await db.list_categories()
    if not categories:
        # Fallback: list all products as a single "Menyu" category.
        categories = ["🍔 Menyu"]
    cart_n = cart_count(context.user_data)
    kb = _categories_keyboard(tenant, lang, categories, cart_n)

    if hasattr(message_or_query, "edit_message_text"):
        await message_or_query.edit_message_text(
            tenant.t(lang, "order_pick_category"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
    else:
        await message_or_query.reply_text(
            tenant.t(lang, "order_pick_category"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
    return BROWSE


async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return BROWSE
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    if query.data == "order_cancel":
        return await _cancel(update, context)
    if query.data == "cart_view":
        return await _show_cart(query, context, tenant, db, lang)
    if query.data == "back_categories":
        return await _enter_browse(query, context, tenant, lang)
    if not query.data.startswith("cat:"):
        return BROWSE
    cat = query.data.split(":", 1)[1]
    context.user_data["order"]["current_category"] = cat
    products = await db.list_products_by_category(cat)
    if not products:
        products = await db.list_products()  # fallback for default Menyu
    # Delete the categories prompt; send each product as a photo card.
    try:
        await query.delete_message()
    except TelegramError:
        pass
    cart_n = cart_count(context.user_data)
    cart = get_cart(context.user_data)
    chat_id = query.message.chat_id
    for p in products:
        in_cart = cart.get(p["id"], 0)
        caption = f"*{p['name']}*\n💰 {p['price']}\n\n_{p.get('description','')}_"
        kb = _product_keyboard(p["id"], cat, in_cart, cart_n, tenant, lang)
        if p.get("image_url"):
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=p["image_url"],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=kb,
                )
                continue
            except TelegramError as exc:
                logger.warning("send_photo failed for %s: %s", p["name"], exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
    return BROWSE


# ========================================================== Cart actions

async def cart_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inline taps on product cards: add/inc/dec."""
    query = update.callback_query
    if query is None or query.data is None:
        return BROWSE
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    parts = query.data.split(":")
    op = parts[0]
    pid = int(parts[1])
    cat = parts[2] if len(parts) > 2 else context.user_data["order"].get("current_category", "")

    if op == "add" or op == "inc":
        cart_add(context.user_data, pid, 1)
    elif op == "dec":
        get_cart(context.user_data)[pid] = get_cart(context.user_data).get(pid, 0) - 1
        if get_cart(context.user_data)[pid] <= 0:
            get_cart(context.user_data).pop(pid, None)

    await query.answer(tenant.t(lang, "order_added_toast") if op in ("add", "inc") else "—")

    # Refresh just this product's keyboard.
    cart = get_cart(context.user_data)
    in_cart = cart.get(pid, 0)
    cart_n = cart_count(context.user_data)
    kb = _product_keyboard(pid, cat, in_cart, cart_n, tenant, lang)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except TelegramError:
        pass
    return BROWSE


async def cart_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return BROWSE
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    return await _show_cart(query, context, tenant, db, lang)


async def _show_cart(query, context, tenant: Tenant, db: Database, lang: str) -> int:
    cart = get_cart(context.user_data)
    if not cart:
        await query.message.reply_text(tenant.t(lang, "cart_empty"))
        return BROWSE
    products = await db.list_products()
    by_id = {p["id"]: p for p in products}
    lines = "\n".join(cart_lines(context.user_data, by_id))
    total = cart_total(context.user_data, by_id)
    kb = _cart_keyboard(tenant, lang, cart, by_id)
    await query.message.reply_text(
        tenant.t(lang, "cart_header", lines=lines, total=total),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    return CART


async def cart_inline_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inside the cart view: +/- per item, clear, back, checkout."""
    query = update.callback_query
    if query is None or query.data is None:
        return CART
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    data = query.data

    if data == "back_categories":
        return await _enter_browse(query, context, tenant, lang)
    if data == "cart_clear":
        cart_clear(context.user_data)
        await query.edit_message_text(tenant.t(lang, "cart_empty"))
        # Re-render categories so user has somewhere to go.
        return await _enter_browse(query.message, context, tenant, lang)
    if data == "checkout":
        await query.edit_message_text(
            tenant.t(lang, "order_ask_time_v2"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_time_prompt_keyboard(),
        )
        return ASK_TIME
    if data.startswith("cinc:") or data.startswith("cdec:"):
        pid = int(data.split(":", 1)[1])
        delta = 1 if data.startswith("cinc:") else -1
        cur = get_cart(context.user_data).get(pid, 0)
        cart_set(context.user_data, pid, cur + delta)
        # Re-render
        cart = get_cart(context.user_data)
        if not cart:
            await query.edit_message_text(tenant.t(lang, "cart_empty"))
            return BROWSE
        products = await db.list_products()
        by_id = {p["id"]: p for p in products}
        lines = "\n".join(cart_lines(context.user_data, by_id))
        total = cart_total(context.user_data, by_id)
        kb = _cart_keyboard(tenant, lang, cart, by_id)
        try:
            await query.edit_message_text(
                tenant.t(lang, "cart_header", lines=lines, total=total),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb,
            )
        except TelegramError:
            pass
        return CART
    return CART


# ========================================================== Checkout

async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return ASK_TIME
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    context.user_data["order"]["preferred_time"] = update.message.text.strip()
    order = context.user_data["order"]
    products = await db.list_products()
    by_id = {p["id"]: p for p in products}
    lines = "\n".join(cart_lines(context.user_data, by_id))
    total = cart_total(context.user_data, by_id)
    order["total"] = total
    summary = tenant.t(
        lang, "order_summary",
        address=order["address"],
        preferred_time=order["preferred_time"],
        delivery_label=order.get("delivery_label", "-"),
        branch=order.get("branch", "-"),
        lines=lines,
        total=total,
    )
    await update.message.reply_text(
        summary,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_confirm_keyboard_with_back(),
    )
    return CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return CONFIRM
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data["order"]["lang"]
    user = update.effective_user

    if query.data == "order_cancel":
        return await _cancel(update, context)

    order = context.user_data["order"]
    products = await db.list_products()
    by_id = {p["id"]: p for p in products}
    lines = cart_lines(context.user_data, by_id)
    service_summary = "; ".join(lines) if lines else "-"

    order_id = await db.create_order(
        user_id=user.id,
        full_name=order.get("full_name", ""),
        phone=order.get("phone", ""),
        service=service_summary,
        preferred_time=order.get("preferred_time", ""),
        branch=order.get("branch", ""),
        address=order.get("address", ""),
    )
    # Award loyalty points (5% of total).
    total = int(order.get("total", 0))
    if total > 0:
        await db.add_points(user.id, total * 0.05)

    await query.edit_message_text(
        tenant.t(lang, "order_success", order_id=order_id),
        parse_mode=ParseMode.MARKDOWN,
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=tenant.t(lang, "main_menu"),
        reply_markup=main_reply_keyboard(tenant, lang),
    )
    await _notify_admins(context, tenant, order_id, order, user, lines, total)
    cart_clear(context.user_data)
    context.user_data.pop("order", None)
    return ConversationHandler.END


async def _notify_admins(context, tenant: Tenant, order_id: int, order: dict, user, lines: list[str], total: int):
    text = (
        f"🆕 *Yangi buyurtma* #{order_id}\n\n"
        f"👤 {order.get('full_name')} (@{user.username or '-'})\n"
        f"📞 {order.get('phone')}\n"
        f"🚚 Usul: {order.get('delivery_label', '-')}\n"
        f"🏪 Filial: {order.get('branch', '-')}\n"
        f"📍 {order.get('address')}\n"
        f"🕐 {order.get('preferred_time')}\n\n"
        f"🛒 *Mahsulotlar:*\n" + "\n".join(lines) + f"\n\n💰 *Jami:* {total:,} so'm"
    )
    for admin_id in tenant.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=order_admin_keyboard(order_id),
            )
        except TelegramError as exc:
            logger.warning("[%s] admin notify failed: %s", tenant.id, exc)


# ========================================================== Cancel

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tenant = _tenant(context)
    db = _db(context)
    lang = (context.user_data.get("order") or {}).get("lang", tenant.default_language)
    if update.effective_user:
        lang = await _user_lang(db, update.effective_user.id, lang)
    msg = tenant.t(lang, "order_cancel")
    if update.callback_query is not None:
        try:
            await update.callback_query.edit_message_text(msg)
        except TelegramError:
            pass
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=tenant.t(lang, "main_menu"),
            reply_markup=main_reply_keyboard(tenant, lang),
        )
    elif update.message is not None:
        await update.message.reply_text(msg, reply_markup=main_reply_keyboard(tenant, lang))
    cart_clear(context.user_data)
    context.user_data.pop("order", None)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _cancel(update, context)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()


# ============================================================== Back nav

async def back_to_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Re-prompt the delivery method (called from categories and pickup branch)."""
    query = update.callback_query
    if query is None:
        return BROWSE
    await query.answer()
    tenant = _tenant(context)
    lang = context.user_data.get("order", {}).get("lang", tenant.default_language)
    try:
        await query.delete_message()
    except TelegramError:
        pass
    return await _ask_delivery_method(query.message, context, tenant, lang)


async def back_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back from the time prompt to the cart view."""
    query = update.callback_query
    if query is None:
        return ASK_TIME
    await query.answer()
    tenant = _tenant(context)
    db = _db(context)
    lang = context.user_data.get("order", {}).get("lang", tenant.default_language)
    return await _show_cart(query, context, tenant, db, lang)


async def back_to_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back from confirmation to the time prompt."""
    query = update.callback_query
    if query is None:
        return CONFIRM
    await query.answer()
    tenant = _tenant(context)
    lang = context.user_data.get("order", {}).get("lang", tenant.default_language)
    await query.edit_message_text(
        tenant.t(lang, "order_ask_time_v2"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_time_prompt_keyboard(),
    )
    return ASK_TIME


# ========================================================== Register

def register(app: Application, tenant: Tenant) -> None:
    entry_filter = order_entry_filter(tenant)
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(entry_filter & ~filters.COMMAND, order_start),
            CommandHandler("order", order_start),
        ],
        states={
            ADDR_CONFIRM: [CallbackQueryHandler(addr_confirm, pattern=r"^addr_(yes|no)$")],
            ADDR_INPUT: [
                MessageHandler(filters.LOCATION, addr_input),
                MessageHandler(filters.TEXT & ~filters.COMMAND, addr_input),
            ],
            GEO_CONFIRM: [CallbackQueryHandler(geo_confirm, pattern=r"^geo_(yes|no)$")],
            DELIVERY_METHOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_method_handler),
            ],
            PICKUP_BRANCH: [
                CallbackQueryHandler(back_to_delivery, pattern=r"^back_to_delivery$"),
                CallbackQueryHandler(pickup_branch_handler, pattern=r"^(pickbranch:\d+|pickbranch_all|order_cancel)$"),
            ],
            BROWSE: [
                CallbackQueryHandler(back_to_delivery, pattern=r"^back_to_delivery$"),
                CallbackQueryHandler(pick_category, pattern=r"^(cat:.+|cart_view|back_categories|order_cancel)$"),
                CallbackQueryHandler(cart_action, pattern=r"^(add|inc|dec):\d+(:.+)?$"),
                CallbackQueryHandler(noop_callback, pattern=r"^noop$"),
            ],
            CART: [
                CallbackQueryHandler(cart_inline_action, pattern=r"^(cinc:\d+|cdec:\d+|cart_clear|checkout|back_categories)$"),
                CallbackQueryHandler(noop_callback, pattern=r"^noop$"),
            ],
            ASK_TIME: [
                CallbackQueryHandler(back_to_cart, pattern=r"^back_to_cart$"),
                CallbackQueryHandler(_cancel, pattern=r"^order_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time),
            ],
            CONFIRM: [
                CallbackQueryHandler(back_to_time, pattern=r"^back_to_time$"),
                CallbackQueryHandler(confirm_order, pattern=r"^(order_confirm|order_cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="order_flow_v3",
        per_message=False,
        conversation_timeout=900,
    )
    app.add_handler(conv, group=1)
