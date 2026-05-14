"""Reverse geocoder using Nominatim (OpenStreetMap).

Free service, 1 req/sec rate limit. Required headers: a real User-Agent.
Returns a human-readable address or an empty string on failure.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "SaaSBotPlatform/1.0 (telegram-bot)"


_LANG_MAP = {
    "uz": "uz",
    "en": "en",
    "ru": "ru",
}


async def reverse_geocode(lat: float, lon: float, lang: str = "uz") -> str:
    """Convert coordinates to a human-readable address. Returns "" on failure."""
    accept_lang = _LANG_MAP.get(lang, "uz")
    params = {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "format": "jsonv2",
        "accept-language": accept_lang,
        "zoom": "18",  # building-level detail
        "addressdetails": "1",
    }
    headers = {"User-Agent": USER_AGENT, "Accept-Language": accept_lang}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(NOMINATIM_URL, params=params, headers=headers)
        if r.status_code != 200:
            logger.warning("Nominatim returned %s for %s,%s", r.status_code, lat, lon)
            return ""
        data = r.json()
        # Prefer a compact composed address rather than the full display_name.
        addr = data.get("address") or {}
        parts: list[str] = []
        for key in ("road", "neighbourhood", "suburb", "city_district", "city", "town", "village"):
            v = addr.get(key)
            if v and v not in parts:
                parts.append(v)
                if len(parts) >= 3:
                    break
        # Include house number if present.
        house = addr.get("house_number")
        if house:
            if parts:
                parts[0] = f"{parts[0]} {house}"
            else:
                parts.append(f"{house}")
        if parts:
            return ", ".join(parts)
        return data.get("display_name", "")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("reverse_geocode failed: %s", exc)
        return ""
