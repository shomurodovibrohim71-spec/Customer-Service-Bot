"""Geographic helpers: distance calculations and nearest-branch ranking."""
from __future__ import annotations

import math
from typing import Any, Iterable


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometers."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_branches(
    branches: Iterable[dict[str, Any]],
    user_lat: float | None,
    user_lon: float | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return branches sorted by distance to user. If user coords missing, return
    them in their natural order. Each returned dict gets an extra `distance_km` key
    (None if it could not be computed).
    """
    decorated: list[tuple[float, dict[str, Any]]] = []
    for b in branches:
        b = dict(b)
        blat = b.get("lat")
        blon = b.get("lon")
        if user_lat is not None and user_lon is not None and blat is not None and blon is not None:
            d = haversine_km(user_lat, user_lon, float(blat), float(blon))
            b["distance_km"] = d
            decorated.append((d, b))
        else:
            b["distance_km"] = None
            decorated.append((float("inf"), b))
    decorated.sort(key=lambda t: t[0])
    return [b for _, b in decorated[:limit]]
