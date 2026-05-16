"""Tenant configuration: Burger House (Mini Food-style multi-branch fast food)."""
from __future__ import annotations

import os

# Supported languages -> human label for the menu button.
LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
}

ADMIN_LABELS = {
    "uz": {
        "add_product":   "➕ Mahsulot qo'shish",
        "list_products": "📦 Mahsulotlar",
        "add_branch":    "🏪 Filial qo'shish",
        "list_branches": "🏠 Filiallar",
        "orders":        "🛒 Buyurtmalar",
        "stats":         "📊 Statistika",
        "feedback_list": "📧 Murojaatlar",
        "about_us":      "ℹ️ Biz haqimizda",
        "promos":        "🎟 Promokodlar",
        "broadcast":     "📢 Reklama yuborish",
        "user_view":     "👤 User rejimi",
    },
    "en": {
        "add_product":   "➕ Add product",
        "list_products": "📦 Products",
        "add_branch":    "🏪 Add branch",
        "list_branches": "🏠 Branches",
        "orders":        "🛒 Orders",
        "stats":         "📊 Statistics",
        "feedback_list": "📧 Feedback",
        "about_us":      "ℹ️ About us",
        "promos":        "🎟 Promo codes",
        "broadcast":     "📢 Broadcast",
        "user_view":     "👤 User view",
    },
    "ru": {
        "add_product":   "➕ Добавить продукт",
        "list_products": "📦 Продукты",
        "add_branch":    "🏪 Добавить филиал",
        "list_branches": "🏠 Филиалы",
        "orders":        "🛒 Заказы",
        "stats":         "📊 Статистика",
        "feedback_list": "📧 Обращения",
        "about_us":      "ℹ️ О нас",
        "promos":        "🎟 Промокоды",
        "broadcast":     "📢 Рассылка",
        "user_view":     "👤 Режим клиента",
    },
}

ADMIN_TEXTS = {
    "uz": {
        "admin_welcome":  "👑 *Admin panel*\n\nQuyidagi tugmalardan foydalaning:",
        "user_view_on":   "👤 *User rejimi yoqildi.*\nQaytish uchun /admin yuboring.",
        "admin_view_on":  "👑 Admin panelga qaytdingiz.",
        "about_current":  "ℹ️ *Hozirgi \"Biz haqimizda\":*\n\n{about}\n\nO'zgartirish uchun yangi matnni yuboring yoki /cancel.",
        "about_empty":    "ℹ️ *\"Biz haqimizda\" bo'sh.*\n\nKompaniyangiz haqida matn yuboring:",
        "about_saved":    "✅ *Saqlandi.*",
        "stats_header":   "📊 *Statistika*",
        "feedback_empty": "📭 Murojaatlar yo'q.",
        "feedback_header":"📧 *So'nggi murojaatlar ({count} ta):*\n",
        "broadcast_ask":  "📢 Reklama matnini kiriting:\n\n_/cancel bilan bekor qilish_",
        "broadcast_done": "✅ Yuborildi: {sent}\n❌ Xato: {failed}\n📊 Jami: {total}",
        "orders_empty":   "✅ Kutilayotgan buyurtmalar yo'q.",
        "about_default":  "Biz haqimizdagi ma'lumot hozircha qo'shilmagan.",
    },
    "en": {
        "admin_welcome":  "👑 *Admin panel*\n\nUse the buttons below:",
        "user_view_on":   "👤 *User mode enabled.*\nSend /admin to return.",
        "admin_view_on":  "👑 Back to admin panel.",
        "about_current":  "ℹ️ *Current About us:*\n\n{about}\n\nSend new text or /cancel.",
        "about_empty":    "ℹ️ *About us is empty.*\n\nSend a company description:",
        "about_saved":    "✅ *Saved.*",
        "stats_header":   "📊 *Statistics*",
        "feedback_empty": "📭 No feedback yet.",
        "feedback_header":"📧 *Recent feedback ({count}):*\n",
        "broadcast_ask":  "📢 Enter the broadcast text:\n\n_Use /cancel to abort_",
        "broadcast_done": "✅ Sent: {sent}\n❌ Failed: {failed}\n📊 Total: {total}",
        "orders_empty":   "✅ No pending orders.",
        "about_default":  "No company information has been added yet.",
    },
    "ru": {
        "admin_welcome":  "👑 *Админ панель*\n\nИспользуйте кнопки:",
        "user_view_on":   "👤 *Режим клиента.*\nОтправьте /admin для возврата.",
        "admin_view_on":  "👑 Возврат в админ-панель.",
        "about_current":  "ℹ️ *Текст О нас:*\n\n{about}\n\nОтправьте новый текст или /cancel.",
        "about_empty":    "ℹ️ *О нас пусто.*\n\nОтправьте описание компании:",
        "about_saved":    "✅ *Сохранено.*",
        "stats_header":   "📊 *Статистика*",
        "feedback_empty": "📭 Нет обращений.",
        "feedback_header":"📧 *Последние ({count}):*\n",
        "broadcast_ask":  "📢 Введите текст рассылки:\n\n_/cancel для отмены_",
        "broadcast_done": "✅ Отправлено: {sent}\n❌ Ошибок: {failed}\n📊 Всего: {total}",
        "orders_empty":   "✅ Нет ожидающих заказов.",
        "about_default":  "Информация о компании ещё не добавлена.",
    },
}

# Main reply-keyboard labels (must match exactly so handlers can dispatch on text).
# Keys are language codes, values are dicts of canonical_action -> label.
MENU_LABELS = {
    "uz": {
        "order":      "👨‍🍳 Buyurtma berish",
        "geo":        "📍 Geolokatsiyani yuborish",
        "loyalty_qr": "⭐ Sodiqlik QR",
        "points":     "🎁 Mening ballarim",
        "branches":   "🏠 Filiallar",
        "addresses":  "🏘 Manzillarim",
        "feedback":   "📧 Taklif va shikoyatlar",
        "about":      "ℹ️ Kompaniya haqida",
        "settings":   "⚙️ Sozlamalar",
        "back":       "⬅ Orqaga",
    },
    "en": {
        "order":      "👨‍🍳 Order",
        "geo":        "📍 Send Geolocation",
        "loyalty_qr": "⭐ Loyalty QR",
        "points":     "🎁 My Points",
        "branches":   "🏠 Branches",
        "addresses":  "🏘 My Addresses",
        "feedback":   "📧 Feedback",
        "about":      "ℹ️ About us",
        "settings":   "⚙️ Settings",
        "back":       "⬅ Back",
    },
    "ru": {
        "order":      "👨‍🍳 Заказать",
        "geo":        "📍 Отправить геолокацию",
        "loyalty_qr": "⭐ QR лояльности",
        "points":     "🎁 Мои баллы",
        "branches":   "🏠 Филиалы",
        "addresses":  "🏘 Мои адреса",
        "feedback":   "📧 Жалобы и предложения",
        "about":      "ℹ️ О компании",
        "settings":   "⚙️ Настройки",
        "back":       "⬅ Назад",
    },
}

# All user-visible text, keyed by language.
TEXTS = {
    "uz": {
        "lang_prompt":       "🌐 Tilni tanlang / Choose language / Выберите язык",
        "welcome":           (
            "👋 Salom hurmatli mijoz!\n\n"
            "Bot qo'shimcha qulaylik yaratish va buyurtmangizni to'laqonli "
            "amalga oshirishda yordam berish maqsadida faoliyat yuritadi.\n\n"
            "Buyurtma uchun botdan foydalaning yoki operator bilan bog'laning."
        ),
        "phone_prompt":      (
            "📞 Ro'yxatdan o'tish uchun telefon raqamingizni kiriting.\n\n"
            "Raqamni `+998XXXXXXXXX` shaklida yuboring yoki pastdagi "
            "*\"📱 Mening raqamim\"* tugmasini bosing."
        ),
        "phone_share_btn":   "📱 Mening raqamim",
        "phone_invalid":     "⚠️ Noto'g'ri raqam. Iltimos, `+998901234567` ko'rinishida yuboring.",
        "registered":        "✅ Ro'yxatdan o'tdingiz!\n\nQuyidagi menyudan kerakli bo'limni tanlang 👇",
        "geo_onboarding_hint": "📍 Lokatsiyangizni saqlang — keyingi buyurtmalarda manzilingiz avtomatik to'ldiriladi.\n_Pastdagi *📍 Geolokatsiyani yuborish* tugmasini bosing._",
        "geo_required_prompt": (
            "📍 *Joylashuvingizni yuboring*\n\n"
            "Yetkazib berish xizmatidan foydalanish uchun joylashuvingiz kerak.\n"
            "Pastdagi tugmani bosing 👇"
        ),
        "geo_share_btn":       "📍 Joylashuvimni yuborish",
        "geo_saved_onboarding": "✅ Manzil saqlandi: *{address}*\n\nEndi buyurtma bera olasiz! 👇",
        "order_start":       "Boshlaymiz 👨‍🍳\n\nQuyidagidan taom tanlang:",
        "order_ask_name":    "📝 Iltimos, ismingizni kiriting:",
        "order_ask_branch":  "🏪 Qaysi filialdan olmoqchisiz?",
        "order_ask_address": "📍 Yetkazib berish manzilingizni yuboring (matn yoki lokatsiya):",
        "order_ask_time":    "🕐 Qachon kerak? _Masalan: \"hozir\" yoki \"19:00\"_",
        "order_confirm":     (
            "✅ *Buyurtmangiz:*\n\n"
            "👤 Ism: {full_name}\n"
            "📞 Telefon: {phone}\n"
            "🏪 Filial: {branch}\n"
            "🍔 Taom: {service}\n"
            "📍 Manzil: {address}\n"
            "🕐 Vaqt: {preferred_time}\n\n"
            "Tasdiqlaysizmi?"
        ),
        "order_success":     "🎉 Buyurtma qabul qilindi! #{order_id}\nTez orada operator bog'lanadi 🚗",
        "order_cancel":      "❌ Buyurtma bekor qilindi.",
        "branches_header":   "Bizning filiallar: {count}",
        "branch_info":       (
            "*{name}*\n\n"
            "📍 {address}\n\n"
            "{hours_block}\n\n"
            "☎️ Telefon: {phone}\n\n"
            "{maps_url}"
        ),
        "loyalty_info":      (
            "⭐ *Sodiqlik dasturi*\n\n"
            "👤 Ism: {name}\n"
            "📞 Telefon: {phone}\n"
            "🆔 ID: `{user_id}`\n\n"
            "💎 Ballaringiz: *{points}*\n"
            "🎁 Buyurtmalar soni: *{orders}*\n\n"
            "_Har bir buyurtma uchun 5% qaytib keladi!_"
        ),
        "menu_header":       "🍔 *Bizning menyu:*\n\n{services_formatted}",
        "contact_info":      "📞 *Aloqa:*\n\nTelefon: {phone}\nAdmin: @minifoodadmin",
        "language_changed":  "✅ Til o'zgartirildi.",
        "not_admin":         "🚫 Sizda admin huquqlari yo'q.",
        "main_menu":         "🏠 Asosiy menyu:",
        "unknown":           "🤔 Tushunmadim. Iltimos, pastdagi menyudan tanlang.",
        # New features
        "geo_prompt":        "📍 Geolokatsiyangizni yuboring (yangi manzil sifatida saqlanadi):",
        "geo_saved":         "✅ Manzilingiz saqlandi:\n📍 {address}",
        "geo_not_location":  "⚠️ Iltimos, pastdagi tugma orqali lokatsiya yuboring.",
        "qr_caption":        "Sizning ID: {phone_digits}",
        "points_info":       "🎁 Mening ballarim: *{points:.2f}*",
        "addresses_empty":   "🏘 Saqlangan manzillaringiz yo'q.\n\nYangi manzil qo'shish uchun '📍 Geolokatsiyani yuborish' tugmasini bosing.",
        "addresses_list":    "🏘 *Mening manzillarim:*\n\n{lines}",
        "address_deleted":   "✅ Manzil o'chirildi.",
        "feedback_prompt":   "📧 Taklif yoki shikoyatingizni yozib qoldiring:",
        "feedback_saved":    "✅ Rahmat! Murojaatingiz qabul qilindi.",
        "feedback_admin":    "📧 *Yangi taklif/shikoyat*\n\n👤 {user_name} (@{username})\n📞 {phone}\n\n{content}",
        "settings_header":   "⚙️ *Sozlamalar*\n\nTil: {lang_label}\nTelefon: {phone}\n\nQuyidagilardan birini tanlang:",
        "settings_lang_btn": "Til",
        "settings_phone_btn":"Telefon",
        "phone_change_prompt":"📞 Yangi telefon raqamingizni kiriting yoki *'📱 Mening raqamim'* tugmasini bosing:",
        "phone_changed":     "✅ Telefon raqami yangilandi: {phone}",
        # New: cart-based order flow
        "order_confirm_address": "Shu manzilga buyurtma berilsinmi?\n\n📍 {address}",
        "order_no_address":  "📍 Avval manzil qo'shing.\n\nPastdagi *'📍 Geolokatsiyani yuborish'* tugmasini bosing yoki manzilingizni matn bilan yozing:",
        "order_pick_category": "🍔 *Toifani tanlang:*",
        "order_pick_product": "*{category}* mahsulotlari:",
        "order_added_toast": "✅ Savatchaga qo'shildi",
        "cart_empty":        "🛒 Savatcha bo'sh.\n\nMahsulot qo'shish uchun toifani tanlang.",
        "cart_header":       "🛒 *Sizning savatchangiz:*\n\n{lines}\n\n💰 *Jami:* {total:,} so'm",
        "cart_btn":          "🛒 Savatcha ({count})",
        "back_to_categories":"⬅ Toifalar",
        "checkout_btn":      "✅ Buyurtma berish",
        "clear_cart_btn":    "🗑 Tozalash",
        "order_ask_time_v2": "🕐 Yetkazib berish vaqti?\n\n_Masalan: \"hozir\" yoki \"19:30\"_",
        "order_summary":     (
            "✅ *Buyurtma ma'lumotlari:*\n\n"
            "📍 Manzil: {address}\n"
            "🚚 Usul: {delivery_label}\n"
            "🏪 Filial: {branch}\n"
            "🕐 Vaqt: {preferred_time}\n\n"
            "🛒 *Mahsulotlar:*\n{lines}\n\n"
            "💰 *Jami:* {total:,} so'm\n\n"
            "Tasdiqlaysizmi?"
        ),
        # Branch selection during onboarding
        "register_pick_branch":  "🏪 Asosiy filialingizni tanlang:\n_(buyurtma berishda asos bo'ladi)_",
        "register_branch_saved": "✅ Filial saqlandi: *{branch}*\n\nQuyidagi menyudan foydalaning 👇",
        # Delivery method
        "delivery_method_prompt": (
            "🎉 *Ajoyib!* Buyurtma berishni boshlaymiz!\n\n"
            "Avval qaysi usulni tanlang:\n\n"
            "🚚 *Yetkazib berish* - Manzilingizga yetkazamiz (30-40 daqiqa)\n"
            "🚶 *Olib ketish* - Filialdan o'zingiz olib ketasiz (15-20 daqiqa)\n\n"
            "Qaysi birini afzal ko'rasiz? 😊🍔"
        ),
        "btn_delivery":          "🚚 Yetkazib berish",
        "btn_pickup":            "🚶 Olib ketish",
        "pickup_ask_branch":     "🏪 Qaysi filialdan olib ketasiz?",
        "pickup_branch_set":     "✅ Filial: *{branch}*",
        "branch_closed_msg":     "🚫 Bu filial hozir yopiq. Boshqa filial tanlang.",
        "delivery_label_value":  "Yetkazib berish",
        "pickup_label_value":    "Olib ketish",
        # Reverse-geocoded confirm
        "geo_address_confirm": "📍 Manzilingiz: *{address}*\n\nTo'g'rimi?",
        "geo_address_yes":     "✅ Ha, to'g'ri",
        "geo_address_no":      "✏ Yo'q, qo'lda yozaman",
        "geo_type_address":    "📝 Manzilni qo'lda yozing:",
        "geo_detecting":       "📍 Manzilni aniqlayapman...",
        # Distance-based branch picking
        "pickup_nearest_header": "🏪 *Sizga eng yaqin filiallar:*",
        "pickup_no_coords":      "🏪 Filialni tanlang:",
        "branch_distance_btn":   "{name} — {dist:.1f} km",
        "show_all_branches":     "🔽 Boshqa filiallarni ko'rish",
        "delivery_auto_branch":  "🏪 Sizga yaqin filial avtomatik tanlandi:\n*{branch}* ({dist:.1f} km)",
        "delivery_no_branch":    "🏪 Filial: avtomatik tanlanadi",
        # Common button labels
        "btn_back":              "⬅ Orqaga",
        "btn_cancel":            "❌ Bekor qilish",
        "btn_yes":               "✅ Ha",
        "btn_no":                "❌ Yo'q",
        "btn_add_to_cart":       "➕ Qo'shish",
        "btn_confirm_order":     "✅ Tasdiqlash",
        "time_asap":             "⚡ Hoziroq",
        "time_asap_value":       "Imkon qadar tez",
    },
    "en": {
        'lang_prompt': '🌐 Choose language / Tilni tanlang / Выберите язык',
        'welcome': '👋 Hello, dear customer!\n\nThis bot is designed to help you place orders conveniently.\n\nUse the bot to order or contact the operator.',
        'phone_prompt': '📞 To register, please enter your phone number.\n\nSend it in `+998XXXXXXXXX` format or tap the *"📱 My Number"* button below.',
        'phone_share_btn': '📱 My Number',
        'phone_invalid': '⚠️ Invalid number. Please send in `+998901234567` format.',
        'registered': "✅ You're registered!\n\nChoose an option from the menu 👇",
        'geo_onboarding_hint': "📍 Save your location — your address will be auto-filled in future orders.\n_Tap *📍 Send Geolocation* below._",
        'geo_required_prompt': (
            "📍 *Share your location*\n\n"
            "We need your location to deliver orders to you.\n"
            "Tap the button below 👇"
        ),
        'geo_share_btn':       "📍 Share my location",
        'geo_saved_onboarding': "✅ Address saved: *{address}*\n\nYou can now place orders! 👇",
        'order_start': "Let's begin 👨\u200d🍳\n\nChoose a dish:",
        'order_ask_name': '📝 Please enter your name:',
        'order_ask_branch': '🏪 Which branch?',
        'order_ask_address': '📍 Send your delivery address (text or location):',
        'order_ask_time': '🕐 When do you need it? _e.g., "now" or "19:00"_',
        'order_confirm': '✅ *Your order:*\n\n👤 Name: {full_name}\n📞 Phone: {phone}\n🏪 Branch: {branch}\n🍔 Item: {service}\n📍 Address: {address}\n🕐 Time: {preferred_time}\n\nConfirm?',
        'order_success': '🎉 Order received! #{order_id}\nOperator will contact you soon 🚗',
        'order_cancel': '❌ Order cancelled.',
        'branches_header': 'Our branches: {count}',
        'branch_info': '*{name}*\n\n📍 {address}\n\n{hours_block}\n\n☎️ Phone: {phone}\n\n{maps_url}',
        'loyalty_info': '⭐ *Loyalty program*\n\n👤 Name: {name}\n📞 Phone: {phone}\n🆔 ID: `{user_id}`\n\n💎 Your points: *{points}*\n🎁 Orders: *{orders}*\n\n_5% cashback on every order!_',
        'menu_header': '🍔 *Our menu:*\n\n{services_formatted}',
        'contact_info': '📞 *Contact:*\n\nPhone: {phone}\nAdmin: @minifoodadmin',
        'language_changed': '✅ Language changed.',
        'not_admin': "🚫 You don't have admin rights.",
        'main_menu': '🏠 Main menu:',
        'unknown': "🤔 I didn't understand. Please choose from the menu below.",
        'geo_prompt': '📍 Send your location (will be saved as a new address):',
        'geo_saved': '✅ Address saved:\n📍 {address}',
        'geo_not_location': '⚠️ Please send a location via the button below.',
        'qr_caption': 'Your ID: {phone_digits}',
        'points_info': '🎁 My points: *{points:.2f}*',
        'addresses_empty': "🏘 No saved addresses.\n\nTap '📍 Send Geolocation' to add one.",
        'addresses_list': '🏘 *My addresses:*\n\n{lines}',
        'address_deleted': '✅ Address deleted.',
        'feedback_prompt': '📧 Write your feedback or complaint:',
        'feedback_saved': '✅ Thanks! Your message has been received.',
        'feedback_admin': '📧 *New feedback*\n\n👤 {user_name} (@{username})\n📞 {phone}\n\n{content}',
        'settings_header': '⚙️ *Settings*\n\nLanguage: {lang_label}\nPhone: {phone}\n\nChoose:',
        'settings_lang_btn': 'Language',
        'settings_phone_btn': 'Phone',
        'phone_change_prompt': "📞 Enter a new phone or tap *'📱 My Number'*:",
        'phone_changed': '✅ Phone updated: {phone}',
        'order_confirm_address': 'Deliver to this address?\n\n📍 {address}',
        'order_no_address': "📍 First add an address.\n\nTap *'📍 Send Geolocation'* or type the address:",
        'order_pick_category': '🍔 *Choose a category:*',
        'order_pick_product': 'Products in *{category}*:',
        'order_added_toast': '✅ Added to cart',
        'cart_empty': '🛒 Cart is empty.',
        'cart_header': '🛒 *Your cart:*\n\n{lines}\n\n💰 *Total:* {total:,} UZS',
        'cart_btn': '🛒 Cart ({count})',
        'back_to_categories': '⬅ Categories',
        'checkout_btn': '✅ Checkout',
        'clear_cart_btn': '🗑 Clear',
        'order_ask_time_v2': '🕐 Delivery time?\n\n_e.g., "now" or "19:30"_',
        'order_summary': '✅ *Order details:*\n\n📍 Address: {address}\n🚚 Method: {delivery_label}\n🏪 Branch: {branch}\n🕐 Time: {preferred_time}\n\n🛒 *Items:*\n{lines}\n\n💰 *Total:* {total:,} UZS\n\nConfirm?',
        'register_pick_branch': '🏪 Choose your main branch:',
        'register_branch_saved': '✅ Branch saved: *{branch}*',
        'delivery_method_prompt': "🎉 *Great!* Let's start your order!\n\nChoose a method:\n\n🚚 *Delivery* (30-40 min)\n🚶 *Pickup* (15-20 min)\n\nWhich one do you prefer? 😊🍔",
        'btn_delivery': '🚚 Delivery',
        'btn_pickup': '🚶 Pickup',
        'pickup_ask_branch': '🏪 From which branch?',
        'pickup_branch_set': '✅ Branch: *{branch}*',
        'branch_closed_msg': '🚫 This branch is currently closed. Please select another.',
        'delivery_label_value': 'Delivery',
        'pickup_label_value': 'Pickup',
        'geo_address_confirm': '📍 Your address: *{address}*\n\nIs this correct?',
        'geo_address_yes': '✅ Yes, correct',
        'geo_address_no': "✏ No, I'll type it",
        'geo_type_address': '📝 Type the address manually:',
        'geo_detecting': '📍 Detecting address...',
        'pickup_nearest_header': '🏪 *Branches nearest to you:*',
        'pickup_no_coords': '🏪 Choose a branch:',
        'branch_distance_btn': '{name} — {dist:.1f} km',
        'show_all_branches': '🔽 Show other branches',
        'delivery_auto_branch': '🏪 Nearest branch auto-selected:\n*{branch}* ({dist:.1f} km)',
        'delivery_no_branch': '🏪 Branch: auto-selected',
        # Common button labels
        'btn_back':          '⬅ Back',
        'btn_cancel':        '❌ Cancel',
        'btn_yes':           '✅ Yes',
        'btn_no':            '❌ No',
        'btn_add_to_cart':   '➕ Add',
        'btn_confirm_order': '✅ Confirm order',
        'time_asap':         '⚡ ASAP',
        'time_asap_value':   'As soon as possible',
    },
        "ru": {
        "lang_prompt":       "Botni tilni tanlang\n-----\nВыберите язык бота.",
        "welcome":           (
            "👋 Здравствуйте, уважаемый клиент!\n\n"
            "Бот создан для удобного оформления ваших заказов.\n\n"
            "Используйте бот для заказа или свяжитесь с оператором."
        ),
        "phone_prompt":      (
            "📞 Для регистрации введите ваш номер телефона.\n\n"
            "Отправьте номер в формате `+998XXXXXXXXX` или нажмите "
            "кнопку *\"📱 Мой номер\"* ниже."
        ),
        "phone_share_btn":   "📱 Мой номер",
        "phone_invalid":     "⚠️ Неверный номер. Отправьте в формате `+998901234567`.",
        "registered":        "✅ Вы зарегистрированы!\n\nВыберите раздел из меню 👇",
        "geo_onboarding_hint": "📍 Сохраните геолокацию — адрес автоматически подставится в следующих заказах.\n_Нажмите *📍 Отправить геолокацию* ниже._",
        "geo_required_prompt": (
            "📍 *Отправьте ваше местоположение*\n\n"
            "Для получения доставки нам нужен ваш адрес.\n"
            "Нажмите кнопку ниже 👇"
        ),
        "geo_share_btn":       "📍 Отправить геолокацию",
        "geo_saved_onboarding": "✅ Адрес сохранён: *{address}*\n\nТеперь можете делать заказы! 👇",
        "order_start":       "Начинаем 👨‍🍳\n\nВыберите блюдо:",
        "order_ask_name":    "📝 Введите ваше имя:",
        "order_ask_branch":  "🏪 Из какого филиала?",
        "order_ask_address": "📍 Отправьте адрес доставки (текст или локация):",
        "order_ask_time":    "🕐 Когда нужно? _Например: \"сейчас\" или \"19:00\"_",
        "order_confirm":     (
            "✅ *Ваш заказ:*\n\n"
            "👤 Имя: {full_name}\n"
            "📞 Телефон: {phone}\n"
            "🏪 Филиал: {branch}\n"
            "🍔 Блюдо: {service}\n"
            "📍 Адрес: {address}\n"
            "🕐 Время: {preferred_time}\n\n"
            "Подтверждаете?"
        ),
        "order_success":     "🎉 Заказ принят! #{order_id}\nОператор скоро свяжется с вами 🚗",
        "order_cancel":      "❌ Заказ отменён.",
        "branches_header":   "Наши филиалы: {count}",
        "branch_info":       (
            "🏪 *{name}*\n\n"
            "📍 Адрес: {address}\n"
            "🕐 Часы работы: {hours}\n"
            "📞 Телефон: {phone}"
        ),
        "loyalty_info":      (
            "⭐ *Программа лояльности*\n\n"
            "👤 Имя: {name}\n"
            "📞 Телефон: {phone}\n"
            "🆔 ID: `{user_id}`\n\n"
            "💎 Баллы: *{points}*\n"
            "🎁 Заказов: *{orders}*\n\n"
            "_5% возвращается с каждого заказа!_"
        ),
        "menu_header":       "🍔 *Наше меню:*\n\n{services_formatted}",
        "contact_info":      "📞 *Контакты:*\n\nТелефон: {phone}\nАдмин: @minifoodadmin",
        "language_changed":  "✅ Язык изменён.",
        "not_admin":         "🚫 У вас нет прав администратора.",
        "main_menu":         "🏠 Главное меню:",
        "unknown":           "🤔 Не понял. Выберите из меню ниже.",
        "geo_prompt":        "📍 Отправьте вашу геолокацию (будет сохранена как новый адрес):",
        "geo_saved":         "✅ Адрес сохранён:\n📍 {address}",
        "geo_not_location":  "⚠️ Пожалуйста, отправьте локацию через кнопку ниже.",
        "qr_caption":        "Ваш ID: {phone_digits}",
        "points_info":       "🎁 Мои баллы: *{points:.2f}*",
        "addresses_empty":   "🏘 Сохранённых адресов нет.\n\nЧтобы добавить новый, нажмите '📍 Отправить геолокацию'.",
        "addresses_list":    "🏘 *Мои адреса:*\n\n{lines}",
        "address_deleted":   "✅ Адрес удалён.",
        "feedback_prompt":   "📧 Напишите ваше предложение или жалобу:",
        "feedback_saved":    "✅ Спасибо! Ваше обращение принято.",
        "feedback_admin":    "📧 *Новое обращение*\n\n👤 {user_name} (@{username})\n📞 {phone}\n\n{content}",
        "settings_header":   "⚙️ *Настройки*\n\nЯзык: {lang_label}\nТелефон: {phone}\n\nВыберите:",
        "settings_lang_btn": "Язык",
        "settings_phone_btn":"Телефон",
        "phone_change_prompt":"📞 Введите новый номер или нажмите *'📱 Мой номер'*:",
        "phone_changed":     "✅ Номер обновлён: {phone}",
        "order_confirm_address": "Доставить на этот адрес?\n\n📍 {address}",
        "order_no_address":  "📍 Сначала добавьте адрес.\n\nНажмите *'📍 Отправить геолокацию'* или напишите адрес:",
        "order_pick_category": "🍔 *Выберите категорию:*",
        "order_pick_product": "Продукты в категории *{category}*:",
        "order_added_toast": "✅ Добавлено в корзину",
        "cart_empty":        "🛒 Корзина пуста.",
        "cart_header":       "🛒 *Ваша корзина:*\n\n{lines}\n\n💰 *Итого:* {total:,} сум",
        "cart_btn":          "🛒 Корзина ({count})",
        "back_to_categories":"⬅ Категории",
        "checkout_btn":      "✅ Оформить заказ",
        "clear_cart_btn":    "🗑 Очистить",
        "order_ask_time_v2": "🕐 Когда доставить?\n\n_Например: \"сейчас\" или \"19:30\"_",
        "order_summary":     (
            "✅ *Детали заказа:*\n\n"
            "📍 Адрес: {address}\n"
            "🚚 Способ: {delivery_label}\n"
            "🏪 Филиал: {branch}\n"
            "🕐 Время: {preferred_time}\n\n"
            "🛒 *Продукты:*\n{lines}\n\n"
            "💰 *Итого:* {total:,} сум\n\n"
            "Подтверждаете?"
        ),
        "register_pick_branch":  "🏪 Выберите ваш основной филиал:",
        "register_branch_saved": "✅ Филиал сохранён: *{branch}*",
        "delivery_method_prompt": (
            "🎉 *Отлично!* Начинаем оформление!\n\n"
            "Выберите способ:\n\n"
            "🚚 *Доставка* (30-40 минут)\n"
            "🚶 *Самовывоз* (15-20 минут)\n\n"
            "Что предпочитаете? 😊🍔"
        ),
        "btn_delivery":          "🚚 Доставка",
        "btn_pickup":            "🚶 Самовывоз",
        "pickup_ask_branch":     "🏪 Из какого филиала?",
        "pickup_branch_set":     "✅ Филиал: *{branch}*",
        "branch_closed_msg":     "🚫 Этот филиал сейчас закрыт. Выберите другой филиал.",
        "delivery_label_value":  "Доставка",
        "pickup_label_value":    "Самовывоз",
        "geo_address_confirm": "📍 Ваш адрес: *{address}*\n\nВерно?",
        "geo_address_yes":     "✅ Да, верно",
        "geo_address_no":      "✏ Нет, напишу вручную",
        "geo_type_address":    "📝 Напишите адрес вручную:",
        "geo_detecting":       "📍 Определяю адрес...",
        'pickup_nearest_header': '🏪 *Ближайшие к вам филиалы:*',
        'pickup_no_coords': '🏪 Выберите филиал:',
        'branch_distance_btn': '{name} — {dist:.1f} км',
        'show_all_branches': '🔽 Показать другие филиалы',
        'delivery_auto_branch': '🏪 Ближайший филиал выбран автоматически:\n*{branch}* ({dist:.1f} км)',
        'delivery_no_branch': '🏪 Филиал: автоматически',
        # Common button labels
        "btn_back":          "⬅ Назад",
        "btn_cancel":        "❌ Отменить",
        "btn_yes":           "✅ Да",
        "btn_no":            "❌ Нет",
        "btn_add_to_cart":   "➕ Добавить",
        "btn_confirm_order": "✅ Подтвердить заказ",
        "time_asap":         "⚡ Как можно скорее",
        "time_asap_value":   "Как можно скорее",
    },
}

CONFIG = {
    "id": "tenant_001",
    "bot_token": os.getenv("TENANT_001_TOKEN", ""),
    "name": "Burger House",
    "tagline": "Eng mazali burgerlar Toshkent bo'ylab!",
    "default_language": "uz",
    "languages": LANGUAGES,
    "menu_labels": MENU_LABELS,
    "admin_labels": ADMIN_LABELS,
    "texts": TEXTS,
    "admin_texts": ADMIN_TEXTS,
    "system_prompt": {
        "uz": (
            "Siz {name} fast food restoranining AI ma'lumot yordamchisisiz. "
            "Sizning vazifangiz — FAQAT savollarga javob berish: menyu, narxlar, "
            "filiallar, ish vaqti, mahsulotlar tarkibi va shu kabi ma'lumotlar.\n\n"
            "MUHIM QOIDALAR:\n"
            "1. SIZ BUYURTMA QABUL QILMAYSIZ. Hech qachon mijozdan buyurtma so'ramang, "
            "savatga mahsulot qo'shmang, manzil yoki to'lov ma'lumotini olmang.\n"
            "2. Mijoz biror mahsulot buyurtma qilmoqchi bo'lsa, har doim "
            "'👨‍🍳 Buyurtma berish' tugmasini bosishni taklif qiling. "
            "Boshqa hech qanday usul taklif qilmang.\n"
            "3. Mijoz buyurtmasini chatda yozsa (masalan: '2 ta burger'), "
            "javob bering: 'Buyurtma berish uchun pastdagi 👨‍🍳 Buyurtma berish "
            "tugmasini bosing — u yerda menyudan tanlaysiz.'\n"
            "4. FAQAT O'ZBEK TILIDA javob bering.\n"
            "5. Qisqa, samimiy va emojili javob bering.\n\n"
            "MA'LUMOT BAZASI:\n"
            "Menyu: {services}\nFiliallar: {branches}\nIsh vaqti: {working_hours}"
        ),
        "en": (
            "You are the AI information assistant of the {name} fast-food restaurant. "
            "Your role is to ANSWER QUESTIONS ONLY — about the menu, prices, "
            "branches, hours, ingredients, and similar info.\n\n"
            "IMPORTANT RULES:\n"
            "1. YOU DO NOT ACCEPT ORDERS. Never ask for an order, never add items "
            "to a cart, never collect address or payment details.\n"
            "2. If a customer wants to order something, ALWAYS direct them to tap "
            "the '👨‍🍳 Order' button. Do not suggest any other path.\n"
            "3. If a customer types an order in chat (e.g. '2 burgers'), reply: "
            "'To place an order, tap the 👨‍🍳 Order button below — you can pick "
            "items from the menu there.'\n"
            "4. REPLY IN ENGLISH ONLY.\n"
            "5. Keep replies short, friendly and use emojis.\n\n"
            "KNOWLEDGE BASE:\n"
            "Menu: {services}\nBranches: {branches}\nHours: {working_hours}"
        ),
        "ru": (
            "Вы — ИИ-ассистент фастфуд-ресторана {name}, отвечающий только на вопросы. "
            "Ваша задача — ОТВЕЧАТЬ НА ВОПРОСЫ о меню, ценах, филиалах, режиме "
            "работы, составе блюд и подобной информации.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. ВЫ НЕ ПРИНИМАЕТЕ ЗАКАЗЫ. Никогда не спрашивайте заказ, не добавляйте "
            "товары в корзину, не собирайте адрес или данные оплаты.\n"
            "2. Если клиент хочет что-то заказать, ВСЕГДА направляйте его нажать "
            "кнопку '👨‍🍳 Заказать'. Не предлагайте никаких других способов.\n"
            "3. Если клиент пишет заказ в чате (напр.: «2 бургера»), отвечайте: "
            "«Чтобы оформить заказ, нажмите кнопку 👨‍🍳 Заказать внизу — там "
            "выберете блюда из меню.»\n"
            "4. ОТВЕЧАЙТЕ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.\n"
            "5. Кратко, дружелюбно и с эмодзи.\n\n"
            "БАЗА ЗНАНИЙ:\n"
            "Меню: {services}\nФилиалы: {branches}\nРежим работы: {working_hours}"
        ),
    },
    # Categories shown in the order flow (ordering matches Mini Food vibe).
    "categories": [
        "🍔 Burger",
        "🌭 Hot-dog",
        "🥙 Lavash",
        "🍕 Pitsa",
        "🍟 Garnirlar",
        "🍗 Tovuq",
        "🥤 Sovuq ichimliklar",
        "🍦 Desert",
    ],
    "services": [
        # Burger
        {"category": "🍔 Burger", "name": "Klassik Burger", "price": "35,000 so'm", "price_value": 35000,
         "description": "Mol go'shti, pomidor, salat, maxsus sous",
         "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800"},
        {"category": "🍔 Burger", "name": "Chizburger", "price": "40,000 so'm", "price_value": 40000,
         "description": "Qo'shimcha cheddar pishloq bilan",
         "image_url": "https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=800"},
        {"category": "🍔 Burger", "name": "Double Burger", "price": "55,000 so'm", "price_value": 55000,
         "description": "Ikkita kotleta, ikkita pishloq",
         "image_url": "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=800"},
        # Hot-dog
        {"category": "🌭 Hot-dog", "name": "Klassik Hot-Dog", "price": "25,000 so'm", "price_value": 25000,
         "description": "Issiq non, sosiska, sous",
         "image_url": "https://images.unsplash.com/photo-1612392062798-2e5edf3e1afa?w=800"},
        {"category": "🌭 Hot-dog", "name": "Hot-Dog Kanada", "price": "30,000 so'm", "price_value": 30000,
         "description": "Karamellangan piyoz, gorchitsa",
         "image_url": "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=800"},
        # Lavash
        {"category": "🥙 Lavash", "name": "Tovuqli Lavash", "price": "32,000 so'm", "price_value": 32000,
         "description": "Tovuq go'shti, salat, sous",
         "image_url": "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=800"},
        {"category": "🥙 Lavash", "name": "Go'shtli Lavash", "price": "38,000 so'm", "price_value": 38000,
         "description": "Mol go'shti, ko'katlar",
         "image_url": "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=800"},
        # Pitsa
        {"category": "🍕 Pitsa", "name": "Pepperoni (30cm)", "price": "75,000 so'm", "price_value": 75000,
         "description": "Klassik italyancha pepperoni",
         "image_url": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800"},
        {"category": "🍕 Pitsa", "name": "Marg'arita (30cm)", "price": "65,000 so'm", "price_value": 65000,
         "description": "Mozarella va pomidor",
         "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=800"},
        # Garnirlar
        {"category": "🍟 Garnirlar", "name": "Free Fri (katta)", "price": "20,000 so'm", "price_value": 20000,
         "description": "Tuzli karton kartoshka",
         "image_url": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=800"},
        {"category": "🍟 Garnirlar", "name": "Onion Rings", "price": "22,000 so'm", "price_value": 22000,
         "description": "Qovurilgan piyoz halqalari",
         "image_url": "https://images.unsplash.com/photo-1639024471283-03518883512d?w=800"},
        # Tovuq
        {"category": "🍗 Tovuq", "name": "Tovuq qanotlari (6 dona)", "price": "45,000 so'm", "price_value": 45000,
         "description": "BBQ yoki achchiq sous bilan",
         "image_url": "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=800"},
        {"category": "🍗 Tovuq", "name": "Naggets (9 dona)", "price": "35,000 so'm", "price_value": 35000,
         "description": "Tovuq filesidan",
         "image_url": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800"},
        # Sovuq ichimliklar
        {"category": "🥤 Sovuq ichimliklar", "name": "Coca-Cola 0.5L", "price": "10,000 so'm", "price_value": 10000,
         "description": "Sovuq", "image_url": "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=800"},
        {"category": "🥤 Sovuq ichimliklar", "name": "Fanta 0.5L", "price": "10,000 so'm", "price_value": 10000,
         "description": "Sovuq", "image_url": "https://images.unsplash.com/photo-1624552184280-9e9631bbeee9?w=800"},
        {"category": "🥤 Sovuq ichimliklar", "name": "Sprite 0.5L", "price": "10,000 so'm", "price_value": 10000,
         "description": "Sovuq", "image_url": "https://images.unsplash.com/photo-1625772299848-391b6a87d7b3?w=800"},
        # Desert
        {"category": "🍦 Desert", "name": "Muzqaymoq", "price": "15,000 so'm", "price_value": 15000,
         "description": "Vanil, shokolad, qulupnay",
         "image_url": "https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=800"},
        {"category": "🍦 Desert", "name": "Milkshake", "price": "25,000 so'm", "price_value": 25000,
         "description": "Shokolad, vanil yoki qulupnay",
         "image_url": "https://images.unsplash.com/photo-1577805947697-89e18249d767?w=800"},
    ],
    # Each branch: name, address, phone, lat/lon (for Telegram location), maps_url (for link preview),
    # and a 7-day hours dict.
    "branches": [
        {
            "name": "🍔 Burger House | Chilonzor",
            "address": "Toshkent, Chilonzor tumani, Bunyodkor 12",
            "phone": "+998901111101",
            "lat": 41.2755, "lon": 69.2034,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Yunusobod",
            "address": "Toshkent, Yunusobod tumani, Amir Temur sh. 15",
            "phone": "+998901111102",
            "lat": 41.3645, "lon": 69.2891,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Mirzo Ulug'bek",
            "address": "Toshkent, Mirzo Ulug'bek tumani, Buyuk Ipak Yo'li 5",
            "phone": "+998901111103",
            "lat": 41.3290, "lon": 69.3429,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Sergeli",
            "address": "Toshkent, Sergeli tumani, Yangi Sergeli 8",
            "phone": "+998901111104",
            "lat": 41.2237, "lon": 69.2228,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-22:00","Seshanba":"10:00-22:00","Chorshanba":"10:00-22:00","Payshanba":"10:00-22:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-22:00"},
        },
        {
            "name": "🍔 Burger House | Yashnobod",
            "address": "Toshkent, Yashnobod tumani, Mustaqillik sh. 21",
            "phone": "+998901111105",
            "lat": 41.3066, "lon": 69.3216,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Shayxontohur",
            "address": "Toshkent, Shayxontohur tumani, Navoiy sh. 33",
            "phone": "+998901111106",
            "lat": 41.3260, "lon": 69.2401,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Olmazor",
            "address": "Toshkent, Olmazor tumani, Olmazor 7",
            "phone": "+998901111107",
            "lat": 41.3505, "lon": 69.2025,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-23:00","Seshanba":"10:00-23:00","Chorshanba":"10:00-23:00","Payshanba":"10:00-23:00","Juma":"10:00-23:00","Shanba":"10:00-23:00","Yakshanba":"10:00-23:00"},
        },
        {
            "name": "🍔 Burger House | Bektemir",
            "address": "Toshkent, Bektemir tumani, Bektemir 19",
            "phone": "+998901111108",
            "lat": 41.2245, "lon": 69.3608,
            "maps_url": "https://yandex.uz/maps/-/CLAvNH4U",
            "hours": {"Dushanba":"10:00-22:00","Seshanba":"10:00-22:00","Chorshanba":"10:00-22:00","Payshanba":"10:00-22:00","Juma":"10:00-22:00","Shanba":"10:00-22:00","Yakshanba":"10:00-22:00"},
        },
    ],
    "working_hours": "Har kuni 10:00 - 23:00",
    "phone": "+998901234567",
    "admin_username": "minifoodadmin",
    "admin_ids": [int(x) for x in os.getenv("TENANT_001_ADMINS", "").split(",") if x.strip().isdigit()] or [123456789],
    # Delivery fee config
    "min_order":           30000,   # Minimum order amount (so'm). 0 = no minimum.
    "delivery_fee_base":   10000,   # Base delivery fee (so'm).
    "delivery_fee_per_km": 2000,    # Extra fee per km beyond free_km.
    "delivery_free_km":    3,       # First N km included in base fee.
    "delivery_free_from":  150000,  # Free delivery if order >= this amount.
}
