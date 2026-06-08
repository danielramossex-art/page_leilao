from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict, deque
from dataclasses import dataclass

import requests
import requests_cache
from requests import Response
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import CACHE_DIR, get_settings

logger = logging.getLogger(__name__)


class RobotsBlockedError(RuntimeError):
    pass


@dataclass
class DomainLimiter:
    requests_per_minute: int

    def __post_init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def wait(self, domain: str) -> None:
        now = time.time()
        hits = self._hits[domain]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.requests_per_minute:
            sleep_for = 60 - (now - hits[0])
            if sleep_for > 0:
                logger.info("rate_limit domain=%s sleep=%.2fs", domain, sleep_for)
                time.sleep(sleep_for)
        hits.append(time.time())


class HttpClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests_cache.CachedSession(
            cache_name=str(CACHE_DIR / "http_cache"),
            backend="sqlite",
            expire_after=1800,
        )
        self.session.headers.update({"User-Agent": self.settings.user_agent})
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._limiter = DomainLimiter(self.settings.requests_per_domain_per_minute)

    def _domain(self, url: str) -> str:
        return urllib.parse.urlparse(url).netloc

    def _robots_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def can_fetch(self, url: str) -> bool:
        domain = self._domain(url)
        if domain not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(self._robots_url(url))
            try:
                parser.read()
            except Exception as exc:
                logger.warning("robots_fetch_failed domain=%s error=%s", domain, exc)
            self._robots[domain] = parser
        return self._robots[domain].can_fetch(self.settings.user_agent, url)

    @retry(
        retry=retry_if_exception_type((requests.RequestException, TimeoutError, ConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def get(self, url: str, **kwargs: object) -> Response:
        if not self.can_fetch(url):
            raise RobotsBlockedError(f"robots.txt bloqueia coleta em {url}")
        self._limiter.wait(self._domain(url))
        response = self.session.get(url, timeout=self.settings.request_timeout_seconds, **kwargs)
        response.raise_for_status()
        return response
