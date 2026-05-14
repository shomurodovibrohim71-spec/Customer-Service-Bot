"""Validate Telegram Mini App `initData` strings.

Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

The Mini App sends `window.Telegram.WebApp.initData` (a urlencoded string) to
your backend. To trust it (verify it came from Telegram and not forged), we
compute an HMAC of the data using a secret derived from the bot token. If the
hash matches the `hash` field, the data is authentic.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)


def verify_init_data(init_data: str, bot_token: str) -> dict | None:
    """Return parsed initData fields if signature is valid, else None.

    The returned dict contains at minimum a `user` sub-dict (decoded from JSON)
    when the user opened the WebApp themselves.
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    except ValueError:
        return None
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None
    # Build data_check_string: sorted "key=value" lines joined by \n.
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        logger.warning("initData hash mismatch")
        return None
    # Decode the user JSON for convenience.
    if "user" in data:
        try:
            data["user"] = json.loads(data["user"])
        except (json.JSONDecodeError, ValueError):
            pass
    return data
