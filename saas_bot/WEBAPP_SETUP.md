# Telegram Mini App (WebApp) — Setup Guide

Bu hujjat **"Buyurtma berish"** sahifasini Telegram ichida ochiladigan to'liq HTML/CSS/JS ilovasi sifatida ishga tushirishni tushuntiradi.

## Arxitektura

```
[Telegram] ──▶ [WebApp button] ──▶ HTTPS public URL ──▶ [Cloudflared tunnel]
                                                              │
                                                              ▼
                                                    [Lokal PC: uvicorn :8080]
                                                              │
                                                              ├─ GET /webapp        → index.html
                                                              ├─ GET /api/menu      → mahsulotlar JSON
                                                              └─ POST /api/order    → buyurtmani qabul qiladi
```

3 ta server kerak:

1. **Bot** (`python bot.py`) — Telegramda xabarlarga javob beradi
2. **FastAPI** (`uvicorn api.server:app --port 8080`) — WebApp ni va API endpointlarini xizmat qiladi
3. **Cloudflared tunnel** — lokal `:8080` ni HTTPS public URL bilan internetga chiqaradi

---

## 1-qadam: Cloudflared'ni o'rnatish (Windows)

Bepul, ro'yxat shart emas. PowerShell ni administrator sifatida ochib:

```powershell
winget install --id Cloudflare.cloudflared
```

Yoki [GitHub releases](https://github.com/cloudflare/cloudflared/releases/latest) sahifasidan `cloudflared-windows-amd64.exe` ni yuklab oling va `cloudflared.exe` deb nomlang.

Tekshirish:
```
cloudflared --version
```

## 2-qadam: 3 ta terminalni oching

**Terminal 1 — Bot:**
```powershell
cd "c:\Users\user\Desktop\Customer Service Bot\saas_bot"
.venv\Scripts\activate
python bot.py
```

**Terminal 2 — FastAPI:**
```powershell
cd "c:\Users\user\Desktop\Customer Service Bot\saas_bot"
.venv\Scripts\activate
uvicorn api.server:app --host 0.0.0.0 --port 8080
```

**Terminal 3 — Tunnel:**
```powershell
cloudflared tunnel --url http://localhost:8080
```

Cloudflared ekranida quyidagiga o'xshash URL chiqadi:
```
INF +--------------------------------------------------------------------------+
INF | Your quick Tunnel has been created! Visit it at (it may take some time   |
INF | to be reachable):                                                         |
INF |   https://random-words-12345.trycloudflare.com                            |
INF +--------------------------------------------------------------------------+
```

## 3-qadam: `.env` ga URLni qo'shing

`.env` faylini oching va `WEBAPP_URL` ga shu URLni qo'ying (oxiriga `/` qo'ymang):

```
WEBAPP_URL=https://random-words-12345.trycloudflare.com
```

## 4-qadam: Botni qayta ishga tushiring

Terminal 1 ni `Ctrl+C` bilan to'xtatib qaytadan `python bot.py` ishga tushiring. `.env` o'zgarganda WebApp URLi yangidan o'qiladi.

## 5-qadam: BotFather'da WebApp ni yoqing (bir martalik)

WebApp tugmasi ishlashi uchun bot'ni BotFather'da WebApp uchun tasdiqlash kerak:

1. [@BotFather](https://t.me/BotFather) ga `/setdomain` yuboring
2. Botni tanlang
3. Cloudflared URLning **domeni**ni yuboring: `random-words-12345.trycloudflare.com`

Faqat **bir marta** sozlash kifoya — keyin har cloudflared restartda domen o'zgaradi va siz `setdomain` ni qayta qilishingiz kerak. (Doimiy URL uchun pastdagi "Production" bo'limini ko'ring.)

## 6-qadam: Sinash

Telegram'da botingizga `/start` yuboring → `👨‍🍳 Buyurtma berish` ni bosing.

Pastda bitta yangi tugma chiqadi: **🛒 Buyurtma berish** — buni bossangiz **Telegram ichida WebApp ochiladi**:

- Yuqorida manzil tugmasi (📍 Geolokatsiya so'rash)
- Toifa tablari (Burger, Hot-dog, Pitsa, ...)
- Mahsulotlar grid'i — har birida **+ Qo'shish** tugmasi
- Pastda yorqin **"Savatcha"** chizig'i (jami narx bilan)
- Tap qilsangiz savatchaga o'tasiz, keyin checkout
- ✅ Tasdiqlash → buyurtma saqlandi, sizga (admin) Telegramga xabar keladi, WebApp yopiladi

---

## Production (doimiy domain)

Tezkor tunnel URL har safar o'zgaradi. Doimiy URL uchun:

```
cloudflared tunnel login                       # brauzer orqali Cloudflare hisobiga kiring
cloudflared tunnel create burger-house
cloudflared tunnel route dns burger-house webapp.example.com
cloudflared tunnel run burger-house
```

Yoki **VPS** ga deploy qiling — `WEBAPP_URL` to'g'ridan-to'g'ri sizning serveringizga ishora qiladi, tunnel kerak emas.

---

## Muammolarni bartaraf etish

| Belgi | Sabab | Yechim |
|---|---|---|
| Tugma bossam hech narsa chiqmaydi | BotFather'da domen sozlanmagan | `/setdomain` qiling |
| "Buyurtma berish" bosganda eski oqim chiqadi | `.env` da `WEBAPP_URL` bo'sh yoki bot restart qilinmagan | URLni qo'shib, botni qayta ishga tushiring |
| WebApp ochiladi lekin ma'lumot yuklanmaydi | uvicorn ishlamayapti yoki cloudflared offline | 2 va 3-terminal ishlayotganini tekshiring |
| ✅ Tasdiqlash bosganda 401 | `init_data` HMAC bilan tasdiqlanmadi | Tugmani BotFather emas, **WebApp keyboard button** orqali ochish kerak (bot.py shunday qilyapti) |

## API endpointlari

Tunneldagi URL'da:

- `GET  /webapp?tenant=tenant_001` — HTML sahifa
- `GET  /api/menu?tenant=tenant_001` — toifalar + mahsulotlar + filiallar (public read)
- `POST /api/order` — `init_data` HMAC bilan tasdiqlanadi, buyurtma yaratadi va adminni xabardor qiladi
- `GET  /health` — liveness probe
