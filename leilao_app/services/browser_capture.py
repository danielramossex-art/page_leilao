from __future__ import annotations

import re
import time
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..config import INBOX_DIR
from ..sources import CAPTURE_SOURCE_URLS
from .importer import import_inbox


DEFAULT_CAPTURE_URLS = CAPTURE_SOURCE_URLS
logger = logging.getLogger(__name__)


def _safe_name(url: str) -> str:
    name = re.sub(r"^https?://", "", url)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return name[:120] or "captura"


def capture_url_to_inbox(url: str, wait_seconds: int = 60, headless: bool = False) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, wait_seconds).until(
                lambda browser: "Imóveis Encontrados" in browser.page_source
                or "imóveis em leilão" in browser.page_source.lower()
                or "Enable JavaScript and cookies" not in browser.page_source
            )
        except Exception:
            pass
        time.sleep(4)
        path = INBOX_DIR / f"{_safe_name(url)}.html"
        path.write_text(driver.page_source, encoding="utf-8")
        return path
    finally:
        driver.quit()


def capture_and_import(urls: list[str], wait_seconds: int = 60, headless: bool = False) -> dict[str, int]:
    captured = 0
    capture_failed = 0
    for url in urls:
        try:
            capture_url_to_inbox(url, wait_seconds=wait_seconds, headless=headless)
            captured += 1
        except Exception as exc:
            logger.warning("capture_failed url=%s error=%s", url, exc)
            capture_failed += 1
    result = import_inbox()
    result["captured"] = captured
    result["capture_failed"] = capture_failed
    return result
