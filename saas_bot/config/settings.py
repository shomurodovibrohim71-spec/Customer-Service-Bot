"""Global application settings, loaded once from environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

DATA_DIR: Path = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Public HTTPS URL where the Telegram Mini App is served (without trailing slash).
# Example: https://abc123.trycloudflare.com  (paths /webapp + /api/* live there)
# Empty -> the bot falls back to the native Telegram-only order flow.
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "").rstrip("/")


_ENV_PATH = BASE_DIR / ".env"


def get_webapp_url() -> str:
    """Read WEBAPP_URL live from .env each call.

    The cloudflared supervisor rewrites .env when it gets a fresh tunnel URL,
    so handlers should call this instead of reading the cached module-level
    `WEBAPP_URL` constant.
    """
    if _ENV_PATH.exists():
        try:
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                if line.startswith("WEBAPP_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
        except OSError:
            pass
    return os.getenv("WEBAPP_URL", "").rstrip("/")

MAX_HISTORY_MESSAGES: int = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))
AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "1024"))
AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.7"))

FALLBACK_ERROR_MESSAGE: str = (
    "⚠️ Kechirasiz, hozir javob bera olmayman.\n\n"
    "Iltimos, biroz keyin urinib ko'ring yoki operator bilan bog'laning:\n"
    "📞 {phone}"
)
