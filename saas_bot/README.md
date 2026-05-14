# SaaS Telegram Bot Platform

Production-ready multi-tenant Telegram bot platform powered by **Claude** (Anthropic).
One codebase, many businesses: each business gets its own bot token, system prompt,
menu, services, admin panel and SQLite database — all driven by a per-tenant config file.

---

## 1. Setup

```bash
# 1. Clone / enter project
cd saas_bot

# 2. Virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# then edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
#   TENANT_001_TOKEN=<telegram bot token from @BotFather>
#   TENANT_002_TOKEN=<another token>
```

## 2. Run

```bash
python bot.py
```

All tenants whose `bot_token` is set start concurrently. Tenants with an empty
token are skipped with a warning. Each tenant gets its own SQLite file under
`data/<tenant_id>.db`.

Stop with `Ctrl+C` — every tenant shuts down cleanly.

## 3. Adding a new tenant

1. Copy an existing config:
   ```bash
   cp config/tenants/tenant_001.py config/tenants/tenant_003.py
   ```
2. Edit the new file — update `id`, `name`, `services`, `address`, `phone`,
   `admin_ids`, `system_prompt` and message templates.
3. Add the bot token to `.env`:
   ```
   TENANT_003_TOKEN=123456:ABC...
   ```
4. Restart `python bot.py`. The new tenant is auto-discovered.

> No code changes required to onboard a new business — just a config file + token.

## 4. Project structure

```
saas_bot/
├── bot.py                  # Entry point: discovers tenants, runs all bots concurrently
├── config/
│   ├── settings.py         # Global env-driven settings
│   └── tenants/
│       ├── tenant_001.py   # Beauty salon (sample)
│       └── tenant_002.py   # Dental clinic (sample)
├── core/
│   ├── ai.py               # Async Anthropic SDK wrapper
│   ├── database.py         # aiosqlite data layer (per-tenant DB file)
│   └── tenant.py           # Tenant loader + helpers
├── handlers/
│   ├── start.py            # /start, main menu, quick replies
│   ├── chat.py             # Claude-powered AI chat (catch-all text handler)
│   ├── order.py            # 5-state ConversationHandler for bookings
│   └── admin.py            # /admin, /stats, /orders + inline order moderation
├── utils/
│   └── helpers.py          # Keyboards, phone validation, markdown utils
└── data/                   # Auto-created SQLite files (one per tenant)
```

### How a request flows

1. User sends `/start` → `handlers/start.py` saves them in the tenant DB, renders
   the inline menu from `CONFIG['menu_buttons']`.
2. User taps `AI Chat` and writes a message → `handlers/chat.py` loads the last 10
   messages from SQLite, builds a system prompt from the tenant config, and calls
   `core/ai.py::AIClient.reply` (Anthropic SDK, async).
3. User taps `Order` → `handlers/order.py` runs the 5-state flow
   (name → phone → service → date → confirm), saves the order, and notifies every
   admin id with inline `Confirm / Cancel` buttons.
4. Admin sends `/admin` → `handlers/admin.py` returns counts; `/stats` returns
   top customers and recent orders; `/orders` lists pending bookings.

### Database schema (per tenant)

```sql
users     (id, tenant_id, name, username, created_at, last_seen)
messages  (id, tenant_id, user_id, role, content, created_at)
orders    (id, tenant_id, user_id, full_name, phone, service,
           preferred_time, status, created_at)
```

Tenant_id is stored on every row so the schema can later be migrated to a single
shared database without changing application code.

## 5. Suggested pricing tiers (for selling to businesses)

| Tier        | Monthly price       | Features                                                          |
|-------------|---------------------|-------------------------------------------------------------------|
| **Starter** | 500,000 so'm        | AI chat + menu + quick replies                                    |
| **Pro**     | 1,000,000 so'm      | Everything in Starter + order flow + admin panel + statistics     |
| **Premium** | 2,000,000 so'm      | Everything in Pro + custom branding, priority support, custom integrations |

A single VPS (~2 vCPU / 2 GB RAM) comfortably runs 20-30 small-business tenants
in long-polling mode. For higher scale, switch the runner to webhooks via FastAPI
(the dependency is already pinned).

## 6. Admin REST API (optional)

A FastAPI server in [api/server.py](api/server.py) exposes per-tenant data over HTTP.

```bash
# in .env, set:
API_TOKEN=some-long-random-string

# run:
uvicorn api.server:app --host 0.0.0.0 --port 8080
```

Endpoints (all require `Authorization: Bearer <API_TOKEN>` except `/health`):

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/health` | liveness probe |
| GET    | `/tenants` | list loaded tenants |
| GET    | `/tenants/{id}/stats` | users / messages / orders counts |
| GET    | `/tenants/{id}/orders?status=pending` | recent orders |
| POST   | `/tenants/{id}/orders/{order_id}/status` | update status (`{"status":"confirmed"}`) |

## 7. Docker

```bash
docker-compose up -d --build   # starts both bot and api containers
docker-compose logs -f bot
```

The compose file mounts `./data` and `./config/tenants` so tenant configs and
SQLite files persist across container rebuilds.

## 8. systemd (bare-metal)

Service units live in [deploy/](deploy/). Install with:

```bash
sudo cp deploy/saas-bot.service /etc/systemd/system/
sudo cp deploy/saas-bot-api.service /etc/systemd/system/
sudo mkdir -p /var/log/saas_bot && sudo chown botuser:botuser /var/log/saas_bot
sudo systemctl daemon-reload
sudo systemctl enable --now saas-bot saas-bot-api
```

## 9. Tests

```bash
pip install pytest pytest-asyncio
pytest
```

Covers database round-trips, tenant template rendering, and helper utilities.

## 10. Admin commands recap

| Command | Who | Effect |
|---------|-----|--------|
| `/start`, `/menu` | anyone | show main menu |
| `/order` | anyone | start order flow (also via menu button) |
| `/cancel` | anyone | abort current order flow |
| `/admin` | admin_ids | dashboard summary |
| `/stats` | admin_ids | top users, recent orders, revenue estimate |
| `/orders` | admin_ids | pending orders with inline Confirm/Cancel |
| `/broadcast <text>` | admin_ids | fan-out message to every known user |

## 11. Production checklist

- Set `ANTHROPIC_API_KEY` and every `TENANT_xxx_TOKEN` in real env vars (not `.env`).
- Run under a process supervisor (`systemd`, `pm2`, Docker) with auto-restart.
- Back up `data/*.db` daily (`sqlite3 file.db ".backup ..."`).
- Monitor logs for `[<tenant_id>] Claude API error` — that is the failure to watch.
- Rotate Anthropic / Telegram tokens periodically.
- Future: add webhooks via FastAPI for higher throughput and an admin web UI.
