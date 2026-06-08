from __future__ import annotations

import logging
import time

from .http_client import HttpClient
from ..config import get_settings

logger = logging.getLogger(__name__)


def geocode(address: str | None, city: str | None, state: str | None, http: HttpClient | None = None) -> tuple[float | None, float | None]:
    settings = get_settings()
    if not settings.geocoding_enabled:
        return None, None
    if not address and not city:
        return None, None
    query = ", ".join(part for part in [address, city, state, "Brasil"] if part)
    if not query.strip():
        return None, None
    http = http or HttpClient()
    time.sleep(settings.geocoding_sleep_seconds)
    try:
        response = http.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "addressdetails": 0},
        )
        data = response.json()
        if not data:
            return None, None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        logger.warning("geocode_failed query=%s error=%s", query, exc)
        return None, None
