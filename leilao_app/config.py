from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
LOG_DIR = DATA_DIR / "logs"
INBOX_DIR = DATA_DIR / "inbox"
PROCESSED_DIR = DATA_DIR / "processed"
FAILED_DIR = DATA_DIR / "failed"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    INBOX_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str
    collect_interval_minutes: int
    request_timeout_seconds: int
    requests_per_domain_per_minute: int
    user_agent: str
    enable_selenium: bool
    geocoding_enabled: bool
    geocoding_sleep_seconds: float


def get_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    ensure_dirs()
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/leiloes.db"),
        app_env=os.getenv("APP_ENV", "local"),
        collect_interval_minutes=int(os.getenv("COLLECT_INTERVAL_MINUTES", "60")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        requests_per_domain_per_minute=int(os.getenv("REQUESTS_PER_DOMAIN_PER_MINUTE", "20")),
        user_agent=os.getenv(
            "USER_AGENT",
            "LeilaoLocalMonitor/1.0 (+local personal research; contact: configure@example.com)",
        ),
        enable_selenium=os.getenv("ENABLE_SELENIUM", "false").lower() == "true",
        geocoding_enabled=os.getenv("GEOCODING_ENABLED", "true").lower() == "true",
        geocoding_sleep_seconds=float(os.getenv("GEOCODING_SLEEP_SECONDS", "1.2")),
    )
