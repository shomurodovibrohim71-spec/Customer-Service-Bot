# Loyihani avtomatik ishga tushirish

## Hozirgi holat

Loyiha **3 ta alohida servis** sifatida ishlaydi:

1. **`bot.py`** — Telegram bot (long polling)
2. **`uvicorn api.server:app --port 8080`** — FastAPI + WebApp serveri
3. **`cloudflared tunnel --url http://localhost:8080`** — public HTTPS URL beradi

Hozir ular avtomatik emas — qo'lda ishga tushiriladi.

---

## Eng tez yo'l: `start_all.bat`

Loyihani **tez ishga tushirish** uchun:

1. `start_all.bat` faylini **2 marta bosing** (Windows Explorer'da)
2. 3 ta cmd oyna ochiladi:
   - **FastAPI :8080**
   - **Cloudflared tunnel**
   - **Telegram bot**
3. Cloudflared oynasidan **yangi URL**ni nusxalang (masalan `https://xyz.trycloudflare.com`)
4. `.env` ni oching va `WEBAPP_URL=` qatoriga yangi URLni qo'ying
5. Bot oynasini yoping va qaytadan ishga tushiring (yoki `start_all.bat`'ni qayta bosing)

**To'xtatish:** `stop_all.bat` ni bosing — hamma servis to'xtaydi.

---

## To'liq avtomatik ishga tushirish (PC yoqilganda)

### Variant A — Windows Startup folder (eng sodda)

1. `Win + R` bosing → `shell:startup` yozing → Enter
2. Ochilgan oynaga `start_all.bat` faylining **shortcut**ini qo'ying (drag bilan o'ng tugma → "Create shortcut here")
3. PC qayta yoqilganda 3 ta servis avtomatik ishga tushadi

### Variant B — Task Scheduler (mukammalroq)

1. `Task Scheduler`ni oching (Start → "Task Scheduler" qidirib)
2. **Create Basic Task** → "SaaS Bot Auto-start"
3. Trigger: **At log on** (yoki **At startup** — admin huquqi kerak)
4. Action: **Start a program** → `start_all.bat` ga ko'rsating
5. Saqlang

---

## ⚠️ Muhim: cloudflared URL har safar o'zgaradi

`cloudflared tunnel --url ...` (free quick tunnel) har safar **yangi tasodifiy URL** beradi:
- Birinchi marta: `https://abc-words-1.trycloudflare.com`
- Ikkinchi marta: `https://xyz-other-2.trycloudflare.com`

Bu URL **`.env`'da va BotFather**'da ham bo'lishi kerak. Har restartda yangilanishi kerak.

### Doimiy URL uchun — Variant 1: Cloudflare named tunnel (bepul)

Cloudflare account oching → permanent tunnel sozlang:

```cmd
cd "C:\Users\user\Desktop\Customer Service Bot\saas_bot\tools"
cloudflared.exe tunnel login        REM Cloudflare hisobiga kirish (bir martalik)
cloudflared.exe tunnel create burger
cloudflared.exe tunnel route dns burger webapp.example.com
```

`start_all.bat`'da `--url http://localhost:8080` o'rniga `run burger` ishlatasiz. URL doimiy bo'ladi.

### Variant 2 — VPS (eng yaxshi)

Loyihani Hetzner/DigitalOcean serverga ko'chiring (5$/oy). Server o'zining doimiy IP/domeniga ega bo'ladi:
- Tunnel kerak emas
- `WEBAPP_URL=https://yourdomain.com`
- 24/7 ishlaydi
- Kompyuteringizni o'chirish mumkin

---

## Tez ishga tushirish (TL;DR)

```
1. start_all.bat ni bosing
2. Cloudflared oynadagi URLni .env ga ko'chiring
3. BotFather → /setdomain → shu domenni kiriting (faqat domain, https yo'q)
4. Bot oynasini qayta ishga tushiring
5. Telegramda /start
```

Loyiha **ushbu chat ochiq turganda** ham avtomatik ishlaydi — men 3 ta servisni background'da ushlab turaman.
