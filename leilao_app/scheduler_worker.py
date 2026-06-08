from __future__ import annotations

import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .db import init_db
from .logging_config import configure_logging
from .services.collector import run_collection
from .services.apify_importer import DEFAULT_URLS, import_from_apify

logger = logging.getLogger(__name__)


def run_scheduled_collection() -> None:
    run_collection()
    if os.getenv("APIFY_TOKEN"):
        import_from_apify(DEFAULT_URLS)


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    init_db()
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_scheduled_collection,
        "interval",
        minutes=settings.collect_interval_minutes,
        id="hourly_collection",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("scheduler_started interval_minutes=%s", settings.collect_interval_minutes)
    return scheduler


def main() -> None:
    configure_logging()
    scheduler = start_scheduler()
    logger.info("running_initial_collection")
    run_scheduled_collection()
    try:
        while scheduler.running:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
