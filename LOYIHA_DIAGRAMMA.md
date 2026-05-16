# 🍽️ Customer Service Bot — Loyiha Diagrammasi

> **Maqsad:** Restoran uchun Telegram orqali buyurtma qabul qilish, boshqarish va mijozlarga xizmat ko'rsatish tizimi.

---

## 🏗️ Tizim Arxitekturasi

```mermaid
graph TD
    A[👤 Mijoz\nTelegram] -->|Buyurtma| B[🤖 Telegram Bot]
    A -->|Mini App| C[📱 WebApp\nport 8080]
    B --> D[⚡ FastAPI Server]
    C --> D
    D --> E[(🗄️ SQLite DB)]
    D -->|Bildirishnoma| A
    D -->|Yangi buyurtma| F[👑 Admin\nTelegram]
    F -->|Tasdiqlash + narx| D
    G[☁️ Cloudflared] -->|HTTPS tunnel| D
```

---

## 📱 Mijoz (User) Oqimi

```mermaid
flowchart LR
    U1[Bot'ni ochish] --> U2[Til tanlash\nUZ / EN / RU]
    U2 --> U3[Buyurtma berish\ntugmasi]
    U3 --> U4[Yetkazib berish\nyoki Olib ketish]
    U4 --> U5[Manzil kiritish\n📍 GPS yoki qo'lda]
    U5 --> U6[Menyu ko'rish\nkategoriyalar]
    U6 --> U7[Mahsulot tanlash\n+ Qo'shish]
    U7 --> U8{Savatcha}
    U8 --> U9[➕ Qo'shimchalar\nIchimlik Non Salat]
    U9 --> U10[Checkout\nTo'lov usuli]
    U10 --> U11[Buyurtma yuborildi\n✅]
    U11 --> U12[Status bildirishnomalar\n⏳→👨‍🍳→🚗→📦]
```

---

## 👑 Admin Oqimi

```mermaid
flowchart LR
    A1[Yangi buyurtma\n🔔 Bildirishnoma] --> A2[Admin Panel\nWebApp]
    A2 --> A3{Buyurtmani ko'rish}
    A3 --> A4[Taksi narxi kiritish\n🚗 10 000 so'm]
    A4 --> A5[✅ Tasdiqlash]
    A5 --> A6[Mijozga bildirishnoma\nJami narx bilan]
    A3 --> A7[❌ Bekor qilish\nSabab bilan]
    A7 --> A6
    A5 --> A8[👨‍🍳 Tayyorlanmoqda]
    A8 --> A9[🚗 Yo'lda]
    A9 --> A10[📦 Yetkazildi]
    A10 --> A6
```

---

## 🗄️ Ma'lumotlar Bazasi Strukturasi

```mermaid
erDiagram
    USERS {
        int id
        string name
        string username
        string phone
        string language
        datetime last_seen
    }
    ORDERS {
        int id
        int user_id
        string status
        int amount
        int delivery_fee
        string address
        string branch
        string payment_method
        datetime created_at
    }
    PRODUCTS {
        int id
        string name
        string category
        int price_value
        string image_url
        int in_stock
        int is_active
    }
    BRANCHES {
        int id
        string name
        string address
        float lat
        float lon
        int is_open
        int is_active
    }
    FEEDBACK {
        int id
        int user_id
        string content
        string category
        string status
    }
    ORDERS }o--|| USERS : "belongs to"
    ORDERS }o--|| BRANCHES : "from branch"
```

---

## 🔄 Buyurtma Statuslari

```mermaid
stateDiagram-v2
    [*] --> Kutilmoqda: Buyurtma yuborildi
    Kutilmoqda --> Tasdiqlandi: Admin taksi narxi + tasdiqlash
    Kutilmoqda --> BekorQilindi: Admin/Mijoz
    Tasdiqlandi --> Tayyorlanmoqda: Admin
    Tayyorlanmoqda --> Yolda: Admin
    Yolda --> Yetkazildi: Admin
    Tasdiqlandi --> BekorQilindi: Admin
    Yetkazildi --> [*]
    BekorQilindi --> [*]
```

---

## 🧩 Funksiyalar Ro'yxati

### 👤 Mijoz uchun
| # | Funksiya | Tavsif |
|---|----------|--------|
| 1 | **Til tanlash** | UZ / EN / RU — to'liq tarjima |
| 2 | **GPS manzil** | Joylashuvni avtomatik aniqlash |
| 3 | **Yetkazib berish / Olib ketish** | Ikki xil usul |
| 4 | **Menyu + Rasmlar** | 32 ta Uzbek milliy taom, haqiqiy fotolar |
| 5 | **Savatcha** | Ko'p mahsulot, miqdor o'zgartirish |
| 6 | **Qo'shimchalar (Upsell)** | Yandex Eats uslubida, kategoriya chiplari |
| 7 | **Promokod** | Chegirma kodi qo'llash |
| 8 | **Karta / Naqd to'lov** | Karta raqamini ko'rish va nusxa olish |
| 9 | **Buyurtma holati** | Real-vaqt bildirishnomalar |
| 10 | **Buyurtma tarixi** | O'tgan buyurtmalarni ko'rish |
| 11 | **Buyurtmani bekor qilish** | 2 daqiqa ichida |
| 12 | **Murojaat yuborish** | Savol / Shikoyat / Taklif |
| 13 | **Qayta buyurtma** | Oldingi buyurtmani bir tugmada takrorlash |

### 👑 Admin uchun
| # | Funksiya | Tavsif |
|---|----------|--------|
| 1 | **Buyurtmalar boshqaruvi** | Real-vaqt, status o'zgartirish |
| 2 | **Taksi narxi kiritish** | Har buyurtma uchun alohida yetkazib berish narxi |
| 3 | **Mahsulotlar CRUD** | Qo'shish, tahrirlash, o'chirish |
| 4 | **Tugadi belgisi** | Mahsulotni bir tugmada yashirish |
| 5 | **Filiallar boshqaruvi** | Yoqish / O'chirish, ish vaqti |
| 6 | **Filial yopish** | Yopiq filialdan buyurtma qabul qilinmaydi |
| 7 | **Kunlik hisobot** | 23:00 da Telegram'ga avtomatik |
| 8 | **Statistika** | Daromad, top taomlar, grafik |
| 9 | **Murojaatlar** | Javob berish, kategoriyalash |
| 10 | **Promokodlar** | Yaratish, chegirma turi, muddat |
| 11 | **Kompaniya sozlamalari** | Karta raqami, Click, Payme, Alif |
| 12 | **Reklama yuborish** | Barcha mijozlarga xabar |

---

## 🚫 Hal Qilingan Muammolar

```mermaid
mindmap
  root((Muammolar))
    Buyurtma
      Yopiq filialdan buyurtma
        Yechim: is_open tekshiruvi
      Noto'g'ri filial tanlash
        Yechim: get_branch is_active filter
      Minimal buyurtma chegarasi
        Yechim: min_order validatsiya
    To'lov
      Karta raqami ko'rinmaydi
        Yechim: Admin company sozlamalar
      Taksi narxi noma'lum
        Yechim: Admin modal + bildirishnoma
    Menyu
      Rasmlar yo'q
        Yechim: Wikimedia + Unsplash CDN
      Tugagan mahsulot buyurtilib qoladi
        Yechim: in_stock toggle
    Tizim
      Bot to'xtab qoladi
        Yechim: Supervisor + autostart
      DB lock muammosi
        Yechim: WAL mode + timeout
    Murojaatlar
      Shikoyatlar ko'rinmaydi
        Yechim: Qayta klassifikatsiya + qo'lda o'zgartirish
```

---

## 💰 Biznes Qiymati

| Muammo (Oldingi) | Yechim (Hozir) | Natija |
|------------------|----------------|--------|
| Telefon orqali buyurtma — vaqt yo'qotish | Telegram bot + WebApp 24/7 | **3x tez buyurtma** |
| Taksi narxini hisoblash — noto'g'riliklar | Admin modal — har buyurtmaga narx | **Aniq hisob-kitob** |
| Mijoz buyurtma holatini bilmaydi | Real-vaqt 5 bosqich bildirishnoma | **Kamroq qo'ng'iroq** |
| Tugagan mahsulot buyuriladi | In-stock toggle, grayout | **Nol noto'g'ri buyurtma** |
| Tun bo'yi monitoring | Kunlik hisobot 23:00 da | **Avtomatik nazorat** |
| Qo'shimcha taomlar sotilmaydi | Upsell kategoriya chiplari | **O'rtacha chek +20-30%** |

---

## 🔧 Texnik Stack

| Qism | Texnologiya |
|------|-------------|
| Bot | Python + python-telegram-bot |
| API | FastAPI + uvicorn |
| DB | SQLite (WAL mode) |
| Frontend | Vanilla JS + Telegram Mini App |
| Tunnel | Cloudflare Tunnel (HTTPS) |
| AI | Anthropic Claude (murojaatlar klassifikatsiyasi) |
| Hosting | Windows kompyuter (autostart) |
| CDN | Wikimedia Commons + Unsplash |

---

*Diagramma Obsidian + Mermaid plugin bilan to'liq ko'rinadi.*
