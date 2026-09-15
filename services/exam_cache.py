"""
exam_cache.py
-------------
Small dependency-free TTL cache plus a per-domain rate limiter, used by
document_discovery.py so that:
  - the same official archive page isn't re-scraped on every user request
    (cache key: exam + authority + document_type [+ year [+ paper]])
  - we never hammer a single government domain with concurrent requests

This is intentionally simple (in-memory, per-process) — good enough for a
single Render web service instance. Swappable for Redis later without
changing the calling code, since callers only see get/set/wait.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional
from urllib.parse import urlparse


class TTLCache:
    def __init__(self, default_ttl_seconds: int = 6 * 60 * 60):
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_seconds

    def make_key(self, *parts: Any) -> str:
        return "|".join(str(p) for p in parts if p is not None)

    def get(self, key: str) -> Optional[Any]:
        hit = self._store.get(key)
        if not hit:
            return None
        ts, value, ttl = hit[0], hit[1], hit[2] if len(hit) > 2 else self.default_ttl
        if time.time() - ts > ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        self._store[key] = (time.time(), value, ttl_seconds or self.default_ttl)

    def clear(self) -> None:
        self._store.clear()


class DomainRateLimiter:
    """Ensures at least `min_interval` seconds between requests to the same domain."""

    def __init__(self, min_interval_seconds: float = 1.5):
        self.min_interval = min_interval_seconds
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        domain = urlparse(url).netloc
        async with self._lock:
            last = self._last_request.get(domain, 0.0)
            now = time.time()
            wait_for = self.min_interval - (now - last)
            self._last_request[domain] = max(now, last) + (max(wait_for, 0.0))
        if wait_for > 0:
            await asyncio.sleep(wait_for)


# Shared singletons for the whole process
page_cache = TTLCache(default_ttl_seconds=6 * 60 * 60)      # raw archive-page scrape results
doc_cache = TTLCache(default_ttl_seconds=6 * 60 * 60)       # classified/verified document results
rate_limiter = DomainRateLimiter(min_interval_seconds=1.5)
