"""Admin commands for dynamic menu + branch management.

All commands are admin-only (checked against tenant.admin_ids):

- /addproduct      -> conversation: name -> price -> description -> saved
- /delproduct      -> shows all active products with delete buttons
- /listproducts    -> dump products with id/name/price
- /addbranch       -> conversation: name -> address -> phone -> save
- /delbranch       -> shows active branches with delete buttons
- /listbranches    -> dump branches with id/name
"""
from __future__ import annotations

import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from utils.helpers import delete_items_keyboard

logger = logging.getLogger(__name__)

# Conversation states
P_NAME, P_CATEGORY, P_CATEGORY_NEW, P_PRICE, P_DESC, P_IMAGE = range(6)
B_NAME, B_ADDR, B_PHONE = range(6, 9)
E_VALUE = 9    # state for product-edit value capture
EB_VALUE = 10  # state for branch-edit value capture


def _tenant(context: ContextTypes.DEFAULT_TYPE) -> Tenant:
    return context.bot_data["tenant"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


def _is_admin(update: Update, tenant: Tenant) -> bool:
    return bool(update.effective_user and update.effective_user.id in tenant.admin_ids)


async def _admin_guard(
    update: Update, tenant: Tenant,
    context: ContextTypes.DEFAULT_TYPE | None = None,
) -> bool:
    """Allow only real admins, AND only when user_view is off.

    Silent on rejection. Several admin handlers fire on text labels that also
    appear in the user keyboard (e.g. '🏠 Filiallar'), so a vocal '🚫 Faqat
    admin' would double-message the customer. The user-side handler in a
    lower group will pick up the same update."""
    if not _is_admin(update, tenant):
        return False
    if context is not None and context.user_data.get("user_view"):
        return False
    return True


# ==================================================================== ADD PRODUCT

async def addproduct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _admin_guard(update, _tenant(context), context):
        return ConversationHandler.END
    await update.message.reply_text(
        "➕ *Yangi mahsulot qo'shish*\n\n1️⃣ Mahsulot nomini kiriting (emoji bilan):",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["new_product"] = {}
    return P_NAME


def _categories_picker_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    """One row per category: [name][🗑]. Final row is 'add new'."""
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([
            InlineKeyboardButton(cat, callback_data=f"pickcat:{cat[:50]}"),
            InlineKeyboardButton("🗑", callback_data=f"delcat:{cat[:50]}"),
        ])
    rows.append([InlineKeyboardButton("➕ Yangi toifa qo'shish", callback_data="pickcat:__new__")])
    return InlineKeyboardMarkup(rows)


def _delcat_confirm_keyboard(cat_payload: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, o'chir", callback_data=f"delcatok:{cat_payload}"),
        InlineKeyboardButton("❌ Yo'q", callback_data="delcatno"),
    ]])


async def addproduct_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return P_NAME
    context.user_data["new_product"]["name"] = update.message.text.strip()
    db = _db(context)
    existing = await db.list_categories()
    if existing:
        await update.message.reply_text(
            "2️⃣ *Toifani tanlang* (yoki yangisini qo'shing):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_categories_picker_keyboard(existing),
        )
    else:
        # No categories yet - ask for text directly.
        await update.message.reply_text(
            "2️⃣ *Birinchi toifani kiriting* (masalan: `🍔 Burger`):",
            parse_mode=ParseMode.MARKDOWN,
        )
        return P_CATEGORY_NEW
    return P_CATEGORY


async def addproduct_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the inline category-picker tap (callback). Supports pick / delete /
    confirm-delete / cancel-delete actions."""
    query = update.callback_query
    if query is None or query.data is None:
        return P_CATEGORY
    await query.answer()
    db = _db(context)
    data = query.data

    # --- Cancel delete: re-show the picker ---
    if data == "delcatno":
        cats = await db.list_categories()
        await query.edit_message_text(
            "2️⃣ *Toifani tanlang* (yoki yangisini qo'shing):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_categories_picker_keyboard(cats),
        )
        return P_CATEGORY

    # --- Confirm delete: soft-delete all products in this category, refresh ---
    if data.startswith("delcatok:"):
        payload = data.split(":", 1)[1]
        all_cats = await db.list_categories()
        matched = next((c for c in all_cats if c[:50] == payload), None)
        if matched:
            prods = await db.list_products_by_category(matched)
            for p in prods:
                await db.delete_product(p["id"])
            new_cats = await db.list_categories()
            if not new_cats:
                await query.edit_message_text(
                    f"✅ *{matched}* toifasi va undagi {len(prods)} ta mahsulot o'chirildi.\n\n"
                    "Toifa qolmadi. Yangi toifa nomini kiriting (emoji bilan):",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return P_CATEGORY_NEW
            await query.edit_message_text(
                f"✅ *{matched}* toifasi va undagi {len(prods)} ta mahsulot o'chirildi.\n\n"
                "Endi toifani tanlang:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_categories_picker_keyboard(new_cats),
            )
        return P_CATEGORY

    # --- Delete tap: show confirmation ---
    if data.startswith("delcat:"):
        payload = data.split(":", 1)[1]
        all_cats = await db.list_categories()
        matched = next((c for c in all_cats if c[:50] == payload), None)
        if matched is None:
            return P_CATEGORY
        prods = await db.list_products_by_category(matched)
        await query.edit_message_text(
            f"🗑 *{matched}* toifasini o'chirasizmi?\n\n"
            f"Bu toifadagi *{len(prods)} ta* mahsulot ham o'chiriladi.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_delcat_confirm_keyboard(payload),
        )
        return P_CATEGORY

    # --- pickcat: select category or open 'new category' text input ---
    if not data.startswith("pickcat:"):
        return P_CATEGORY
    payload = data.split(":", 1)[1]
    if payload == "__new__":
        await query.edit_message_text(
            "✏ Yangi toifa nomini kiriting (emoji bilan, masalan: `🥗 Salatlar`):",
            parse_mode=ParseMode.MARKDOWN,
        )
        return P_CATEGORY_NEW
    all_cats = await db.list_categories()
    matched = next((c for c in all_cats if c[:50] == payload), payload)
    context.user_data["new_product"]["category"] = matched
    await query.edit_message_text(
        f"✅ Toifa tanlandi: *{matched}*\n\n3️⃣ Narxini kiriting (masalan: `35,000 so'm`):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return P_PRICE


async def addproduct_category_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture a brand-new category name typed by admin."""
    if not update.message or not update.message.text:
        return P_CATEGORY_NEW
    cat = update.message.text.strip()
    context.user_data["new_product"]["category"] = cat
    await update.message.reply_text(
        f"✅ Yangi toifa: *{cat}*\n\n3️⃣ Narxini kiriting (masalan: `35,000 so'm`):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return P_PRICE


async def addproduct_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return P_PRICE
    context.user_data["new_product"]["price"] = update.message.text.strip()
    await update.message.reply_text(
        "4️⃣ Tavsifini kiriting (yoki `-`):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return P_DESC


async def addproduct_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return P_DESC
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""
    context.user_data["new_product"]["description"] = desc
    await update.message.reply_text(
        "5️⃣ Rasm URL kiriting (yoki `-`):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return P_IMAGE


async def addproduct_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return P_IMAGE
    image_url = update.message.text.strip()
    if image_url == "-":
        image_url = ""
    p = context.user_data.pop("new_product")
    p["image_url"] = image_url
    db = _db(context)
    pid = await db.add_product(
        name=p["name"], price=p["price"], description=p["description"],
        category=p.get("category", ""), image_url=image_url,
    )
    await update.message.reply_text(
        f"✅ Mahsulot qo'shildi! ID: `{pid}`\n\n"
        f"🍔 {p['name']}\n🗂 {p.get('category','-')}\n💰 {p['price']}\n"
        f"📝 {p['description'] or '_tavsifsiz_'}\n🖼 {image_url or '_rasm yoq_'}",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ==================================================================== DEL PRODUCT

# ==================================================================== EDIT PRODUCT

EDITABLE_PRODUCT_FIELDS = {
    "name":        "Nom",
    "price":       "Narx",
    "description": "Tavsif",
    "category":    "Toifa",
    "image_url":   "Rasm URL",
}


def _edit_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"✏ {label}", callback_data=f"editp:{product_id}:{key}")]
        for key, label in EDITABLE_PRODUCT_FIELDS.items()
    ]
    rows.append([
        InlineKeyboardButton("🗑 O'chirish", callback_data=f"delprod:{product_id}"),
        InlineKeyboardButton("◀ Yopish", callback_data="editp_close"),
    ])
    return InlineKeyboardMarkup(rows)


def _products_list_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"✏ {p['name']} — {p['price']}", callback_data=f"editpopen:{p['id']}")]
        for p in products
    ]
    rows.append([InlineKeyboardButton("◀ Yopish", callback_data="editp_close")])
    return InlineKeyboardMarkup(rows)


async def editproduct_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'📦 Mahsulotlar' button: open the admin WebApp page when WEBAPP_URL is set,
    otherwise fall back to the legacy inline list."""
    if not await _admin_guard(update, _tenant(context), context):
        return
    tenant = _tenant(context)
    db = _db(context)

    from config.settings import get_webapp_url
    from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
    webapp_url = get_webapp_url()
    if webapp_url and update.effective_user:
        lang = (await db.get_user(update.effective_user.id) or {}).get("language") or tenant.default_language
        url = f"{webapp_url}/webapp/admin/products?tenant={tenant.id}&uid={update.effective_user.id}&lang={lang}"
        labels = {
            "uz": ("📦 Mahsulotlar boshqaruvi", "📦 Pastdagi tugmani bosing — mahsulotlarni boshqarish sahifasi ochiladi."),
            "en": ("📦 Manage products",         "📦 Tap the button below — the product manager will open."),
            "ru": ("📦 Управление товарами",     "📦 Нажмите кнопку ниже — откроется страница управления товарами."),
        }
        btn, intro = labels.get(lang, labels["uz"])
        from utils.helpers import home_button_label
        kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton(text=btn, web_app=WebAppInfo(url=url))],
                [KeyboardButton(text=home_button_label(lang))],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(intro, reply_markup=kb)
        return

    products = await db.list_products()
    if not products:
        await update.message.reply_text("Mahsulotlar yo'q.")
        return
    await update.message.reply_text(
        f"📦 *Mahsulotlar ({len(products)} ta):*\nTahrirlash uchun ustiga bosing.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_products_list_keyboard(products),
    )


async def editproduct_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    if not _is_admin(update, _tenant(context)):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return
    await query.answer()
    if query.data == "editp_close":
        await query.edit_message_text("✅ Yopildi.")
        return
    try:
        pid = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    db = _db(context)
    product = await db.get_product(pid)
    if product is None:
        await query.edit_message_text("❌ Topilmadi.")
        return
    text = (
        f"🍔 *{product['name']}*\n"
        f"🗂 Toifa: {product.get('category') or '-'}\n"
        f"💰 Narx: {product.get('price', '-')}\n"
        f"📝 {product.get('description') or '_tavsifsiz_'}\n"
        f"🖼 {product.get('image_url') or '_rasmsiz_'}\n\n"
        "Qaysi maydonni tahrirlaysiz?"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=_edit_product_keyboard(pid),
    )


async def editproduct_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return ConversationHandler.END
    if not _is_admin(update, _tenant(context)):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3:
        return ConversationHandler.END
    pid, field = int(parts[1]), parts[2]
    if field not in EDITABLE_PRODUCT_FIELDS:
        return ConversationHandler.END
    db = _db(context)
    product = await db.get_product(pid)
    if product is None:
        return ConversationHandler.END
    current = product.get(field) or "_bo'sh_"
    context.user_data["edit_product"] = {"id": pid, "field": field}
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✏ *{EDITABLE_PRODUCT_FIELDS[field]}*\n\nHozirgi: {current}\n\nYangi qiymatni yuboring (/cancel - bekor).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return E_VALUE


async def editproduct_value_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return E_VALUE
    info = context.user_data.pop("edit_product", None)
    if not info:
        return ConversationHandler.END
    db = _db(context)
    val = update.message.text.strip()
    await db.update_product(info["id"], **{info["field"]: val})
    await update.message.reply_text("✅ Saqlandi.")
    return ConversationHandler.END


async def delproduct_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update, _tenant(context), context):
        return
    db = _db(context)
    products = await db.list_products()
    if not products:
        await update.message.reply_text("Mahsulotlar yo'q.")
        return
    await update.message.reply_text(
        f"🗑 *O'chirish uchun mahsulotni tanlang* (jami: {len(products)}):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=delete_items_keyboard(products, prefix="delprod"),
    )


async def delproduct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    tenant = _tenant(context)
    if not _is_admin(update, tenant):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return
    await query.answer()
    if query.data == "delprod_close":
        await query.edit_message_text("✅ Yopildi.")
        return
    try:
        pid = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    db = _db(context)
    product = await db.get_product(pid)
    ok = await db.delete_product(pid)
    if ok and product:
        await query.edit_message_text(f"✅ O'chirildi: {product['name']}")
    else:
        await query.edit_message_text("❌ Topilmadi.")


# ==================================================================== LIST PRODUCTS

async def listproducts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update, _tenant(context), context):
        return
    db = _db(context)
    products = await db.list_products()
    if not products:
        await update.message.reply_text("Mahsulotlar yo'q.")
        return
    lines = [f"🍔 *Mahsulotlar ({len(products)} ta):*\n"]
    for p in products:
        desc = f"\n   _{p['description']}_" if p.get("description") else ""
        lines.append(f"`#{p['id']}` *{p['name']}* — {p['price']}{desc}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ==================================================================== ADD BRANCH

async def addbranch_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _admin_guard(update, _tenant(context), context):
        return ConversationHandler.END
    await update.message.reply_text(
        "🏪 *Yangi filial qo'shish*\n\n1️⃣ Filial nomini kiriting:",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["new_branch"] = {}
    return B_NAME


async def addbranch_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return B_NAME
    context.user_data["new_branch"]["name"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Manzilini kiriting:")
    return B_ADDR


async def addbranch_addr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return B_ADDR
    context.user_data["new_branch"]["address"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ Telefon raqamini kiriting (yoki `-`):")
    return B_PHONE


async def addbranch_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return B_PHONE
    phone = update.message.text.strip()
    if phone == "-":
        phone = ""
    b = context.user_data.pop("new_branch")
    db = _db(context)
    # Default 7-day hours: Mon-Sun 10:00-23:00
    default_hours = {
        d: "10:00-23:00"
        for d in ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")
    }
    bid = await db.add_branch(
        name=b["name"],
        address=b["address"],
        phone=phone,
        hours_json=json.dumps(default_hours, ensure_ascii=False),
    )
    await update.message.reply_text(
        f"✅ Filial qo'shildi! ID: `{bid}`\n\n"
        f"🏪 {b['name']}\n📍 {b['address']}\n☎️ {phone or '-'}\n\n"
        f"_Vaqt jadvalini o'zgartirish uchun DB ni tahrirlang._",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ==================================================================== DEL BRANCH

async def delbranch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update, _tenant(context), context):
        return
    db = _db(context)
    branches = await db.list_branches()
    if not branches:
        await update.message.reply_text("Filiallar yo'q.")
        return
    await update.message.reply_text(
        f"🗑 *O'chirish uchun filialni tanlang* (jami: {len(branches)}):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=delete_items_keyboard(branches, prefix="delbranch"),
    )


async def delbranch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    tenant = _tenant(context)
    if not _is_admin(update, tenant):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return
    await query.answer()
    if query.data == "delbranch_close":
        await query.edit_message_text("✅ Yopildi.")
        return
    try:
        bid = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    db = _db(context)
    branch = await db.get_branch(bid)
    ok = await db.delete_branch(bid)
    if ok and branch:
        await query.edit_message_text(f"✅ O'chirildi: {branch['name']}")
    else:
        await query.edit_message_text("❌ Topilmadi.")


# ==================================================================== EDIT BRANCH (new UI)

EDITABLE_BRANCH_FIELDS = {
    "name":    "Nom",
    "address": "Manzil",
    "phone":   "Telefon",
}


def _branches_list_keyboard(branches: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for b in branches:
        rows.append([
            InlineKeyboardButton(f"✏ {b['name']}", callback_data=f"editbopen:{b['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"delbranchq:{b['id']}"),
        ])
    rows.append([InlineKeyboardButton("◀ Yopish", callback_data="editb_close")])
    return InlineKeyboardMarkup(rows)


def _delbranch_confirm_keyboard(branch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, o'chir", callback_data=f"delbranch:{branch_id}"),
        InlineKeyboardButton("❌ Yo'q", callback_data="editb_close"),
    ]])


def _edit_branch_keyboard(branch_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"✏ {label}", callback_data=f"editb:{branch_id}:{key}")]
        for key, label in EDITABLE_BRANCH_FIELDS.items()
    ]
    rows.append([
        InlineKeyboardButton("🗑 O'chirish", callback_data=f"delbranch:{branch_id}"),
        InlineKeyboardButton("◀ Yopish", callback_data="editb_close"),
    ])
    return InlineKeyboardMarkup(rows)


async def editbranch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open admin branches webapp."""
    if not await _admin_guard(update, _tenant(context), context):
        return
    tenant = _tenant(context)
    db = _db(context)

    from config.settings import get_webapp_url
    from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
    from utils.helpers import home_button_label
    webapp_url = get_webapp_url()
    if not webapp_url or not update.effective_user:
        await update.message.reply_text("⚠️ WEBAPP_URL sozlanmagan. .env faylini tekshiring.")
        return

    lang = (await db.get_user(update.effective_user.id) or {}).get("language") or tenant.default_language
    url = f"{webapp_url}/webapp/admin/branches?tenant={tenant.id}&uid={update.effective_user.id}&lang={lang}"
    btn_labels = {
        "uz": ("🏪 Filiallarni boshqarish", "🏪 Pastdagi tugmani bosing."),
        "en": ("🏪 Manage branches",         "🏪 Tap the button below."),
        "ru": ("🏪 Управление филиалами",    "🏪 Нажмите кнопку ниже."),
    }
    btn, intro = btn_labels.get(lang, btn_labels["uz"])
    kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton(text=btn, web_app=WebAppInfo(url=url))],
            [KeyboardButton(text=home_button_label(lang))],
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(intro, reply_markup=kb)


async def editbranch_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    if not _is_admin(update, _tenant(context)):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return
    await query.answer()
    if query.data == "editb_close":
        await query.edit_message_text("✅ Yopildi.")
        return
    # In-list delete tap -> show confirm screen
    if query.data.startswith("delbranchq:"):
        bid_str = query.data.split(":", 1)[1]
        try:
            bid = int(bid_str)
        except ValueError:
            return
        db = _db(context)
        branch = await db.get_branch(bid)
        if branch is None:
            await query.edit_message_text("❌ Topilmadi.")
            return
        await query.edit_message_text(
            f"🗑 *{branch['name']}* filialini o'chirasizmi?\n\n"
            f"📍 {branch.get('address') or '-'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_delbranch_confirm_keyboard(bid),
        )
        return
    try:
        bid = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    db = _db(context)
    branch = await db.get_branch(bid)
    if branch is None:
        await query.edit_message_text("❌ Topilmadi.")
        return
    text = (
        f"🏪 *{branch['name']}*\n\n"
        f"📍 {branch.get('address') or '-'}\n"
        f"☎️ {branch.get('phone') or '-'}\n\n"
        "Qaysi maydonni tahrirlaysiz?"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=_edit_branch_keyboard(bid),
    )


async def editbranch_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return ConversationHandler.END
    if not _is_admin(update, _tenant(context)):
        await query.answer("🚫 Faqat admin", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3:
        return ConversationHandler.END
    bid, field = int(parts[1]), parts[2]
    if field not in EDITABLE_BRANCH_FIELDS:
        return ConversationHandler.END
    db = _db(context)
    branch = await db.get_branch(bid)
    if branch is None:
        return ConversationHandler.END
    current = branch.get(field) or "_bo'sh_"
    context.user_data["edit_branch"] = {"id": bid, "field": field}
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✏ *{EDITABLE_BRANCH_FIELDS[field]}*\n\nHozirgi: {current}\n\nYangi qiymatni yuboring (/cancel).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return EB_VALUE


async def editbranch_value_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None or not update.message.text:
        return EB_VALUE
    info = context.user_data.pop("edit_branch", None)
    if not info:
        return ConversationHandler.END
    db = _db(context)
    val = update.message.text.strip()
    # Patch the column directly.
    await db.conn.execute(
        f"UPDATE branches SET {info['field']}=? WHERE id=? AND tenant_id=?",
        (val, info["id"], db.tenant_id),
    )
    await db.conn.commit()
    await update.message.reply_text("✅ Saqlandi.")
    return ConversationHandler.END


# ==================================================================== LIST BRANCHES

async def listbranches_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update, _tenant(context), context):
        return
    db = _db(context)
    branches = await db.list_branches()
    if not branches:
        await update.message.reply_text("Filiallar yo'q.")
        return
    lines = [f"🏪 *Filiallar ({len(branches)} ta):*\n"]
    for b in branches:
        lines.append(f"`#{b['id']}` *{b['name']}*\n   📍 {b['address']}\n   ☎️ {b.get('phone','-') or '-'}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ==================================================================== ADMIN HELP

async def adminhelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_guard(update, _tenant(context), context):
        return
    text = (
        "🛠 *Admin buyruqlar:*\n\n"
        "*📊 Statistika:*\n"
        "/admin - umumiy dashboard\n"
        "/stats - batafsil statistika\n"
        "/orders - kutilayotgan buyurtmalar\n\n"
        "*🍔 Mahsulotlar:*\n"
        "/addproduct - yangi mahsulot qo'shish\n"
        "/delproduct - mahsulot o'chirish\n"
        "/listproducts - barcha mahsulotlar\n\n"
        "*🏪 Filiallar:*\n"
        "/addbranch - yangi filial qo'shish\n"
        "/delbranch - filial o'chirish\n"
        "/listbranches - barcha filiallar\n\n"
        "*📢 Boshqa:*\n"
        "/broadcast <matn> - barchaga xabar\n"
        "/cancel - joriy amalni bekor qilish"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("❌ Bekor qilindi.")
    context.user_data.pop("new_product", None)
    context.user_data.pop("new_branch", None)
    return ConversationHandler.END


# ==================================================================== REGISTER

def register(app: Application, tenant: Tenant | None = None) -> None:
    # Build admin-button text filters so admin can ALSO enter the conversations
    # by tapping the reply-keyboard buttons (not just via /commands).
    addproduct_texts = []
    addbranch_texts = []
    editproduct_texts = []
    if tenant:
        addproduct_texts = [labels.get("add_product") for labels in tenant.admin_labels.values() if labels.get("add_product")]
        addbranch_texts = [labels.get("add_branch") for labels in tenant.admin_labels.values() if labels.get("add_branch")]
        editproduct_texts = [labels.get("list_products") for labels in tenant.admin_labels.values() if labels.get("list_products")]

    addproduct_entries = [CommandHandler("addproduct", addproduct_start)]
    if addproduct_texts:
        addproduct_entries.append(
            MessageHandler(filters.Text(addproduct_texts) & ~filters.COMMAND, addproduct_start)
        )

    addbranch_entries = [CommandHandler("addbranch", addbranch_start)]
    if addbranch_texts:
        addbranch_entries.append(
            MessageHandler(filters.Text(addbranch_texts) & ~filters.COMMAND, addbranch_start)
        )

    # Add-product conversation - 10 minute timeout to avoid stranded states.
    app.add_handler(ConversationHandler(
        entry_points=addproduct_entries,
        states={
            P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduct_name)],
            P_CATEGORY: [CallbackQueryHandler(addproduct_category, pattern=r"^pickcat:")],
            P_CATEGORY_NEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduct_category_new)],
            P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduct_price)],
            P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduct_desc)],
            P_IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduct_image)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="addproduct_flow",
        per_message=False,
        conversation_timeout=600,
    ), group=0)

    # Add-branch conversation
    app.add_handler(ConversationHandler(
        entry_points=addbranch_entries,
        states={
            B_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbranch_name)],
            B_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbranch_addr)],
            B_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbranch_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="addbranch_flow",
        per_message=False,
        conversation_timeout=600,
    ), group=0)

    # '📦 Mahsulotlar' admin button -> editproduct_command (shows list).
    if editproduct_texts:
        app.add_handler(
            MessageHandler(filters.Text(editproduct_texts) & ~filters.COMMAND, editproduct_command),
            group=0,
        )

    # Simple commands
    app.add_handler(CommandHandler("delproduct", delproduct_command))
    app.add_handler(CommandHandler("listproducts", listproducts_command))
    app.add_handler(CommandHandler("editproduct", editproduct_command))
    app.add_handler(CommandHandler("delbranch", delbranch_command))
    app.add_handler(CommandHandler("listbranches", listbranches_command))
    app.add_handler(CommandHandler("adminhelp", adminhelp_command))

    # Callbacks for delete buttons
    app.add_handler(CallbackQueryHandler(delproduct_callback, pattern=r"^delprod(:\d+|_close)$"))
    app.add_handler(CallbackQueryHandler(delbranch_callback, pattern=r"^delbranch(:\d+|_close)$"))
    # Edit product callbacks
    app.add_handler(CallbackQueryHandler(editproduct_open_callback, pattern=r"^(editpopen:\d+|editp_close)$"))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(editproduct_field_callback, pattern=r"^editp:\d+:[a-z_]+$")],
        states={E_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, editproduct_value_capture)]},
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="editproduct_flow",
        per_message=False,
        conversation_timeout=300,
    ), group=0)

    # Edit branch callbacks + conversation
    app.add_handler(CallbackQueryHandler(editbranch_open_callback, pattern=r"^(editbopen:\d+|delbranchq:\d+|editb_close)$"))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(editbranch_field_callback, pattern=r"^editb:\d+:[a-z_]+$")],
        states={EB_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, editbranch_value_capture)]},
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="editbranch_flow",
        per_message=False,
        conversation_timeout=300,
    ), group=0)

    # '🏠 Filiallar' admin button -> editbranch_command (new clean UI).
    editbranch_texts = []
    if tenant:
        editbranch_texts = [labels.get("list_branches") for labels in tenant.admin_labels.values() if labels.get("list_branches")]
    if editbranch_texts:
        app.add_handler(
            MessageHandler(filters.Text(editbranch_texts) & ~filters.COMMAND, editbranch_command),
            group=0,
        )
