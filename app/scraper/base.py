from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
import urllib.robotparser

import httpx
from bs4 import BeautifulSoup

from ..config import settings


class RobotsPolicy:
    def __init__(self, base_url: str, user_agent: str) -> None:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self._rp = urllib.robotparser.RobotFileParser()
        self._rp.set_url(robots_url)
        try:
            self._rp.read()
        except Exception:
            # Be conservative if robots.txt fails to load
            self._rp = None
        self.user_agent = user_agent

    def can_fetch(self, url: str) -> bool:
        if self._rp is None:
            return False
        return self._rp.can_fetch(self.user_agent, url)

    def crawl_delay(self) -> Optional[float]:
        if self._rp is None:
            return None
        try:
            return self._rp.crawl_delay(self.user_agent)
        except Exception:
            return None


class TokenBucketRateLimiter:
    def __init__(self, rate_per_second: float, burst: Optional[int] = None) -> None:
        self.rate = max(rate_per_second, 0.1)
        self.capacity = burst if burst is not None else max(int(self.rate), 1)
        self.tokens = float(self.capacity)
        self.timestamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens < 1.0:
                # time to wait for 1 token
                to_wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(to_wait)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


@dataclass
class HttpClient:
    base_url: str
    user_agent: str
    timeout: float
    limiter: TokenBucketRateLimiter

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True,
        )

    def _absolutize(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urljoin(self.base_url, url)

    async def get_html(self, url: str) -> BeautifulSoup:
        absolute_url = self._absolutize(url)
        await self.limiter.acquire()
        resp = await self._client.get(absolute_url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    async def get_bytes(self, url: str) -> bytes:
        absolute_url = self._absolutize(url)
        await self.limiter.acquire()
        resp = await self._client.get(absolute_url)
        resp.raise_for_status()
        return resp.content

    async def aclose(self) -> None:
        await self._client.aclose()


class BaseScraper:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.base_url
        self.robots = RobotsPolicy(self.base_url, settings.user_agent)
        self.client = HttpClient(
            base_url=self.base_url,
            user_agent=settings.user_agent,
            timeout=settings.request_timeout_seconds,
            limiter=TokenBucketRateLimiter(settings.rate_limit_rps),
        )

    async def fetch_html(self, url: str) -> BeautifulSoup:
        absolute = self.client._absolutize(url)
        if not self.robots.can_fetch(absolute):
            raise PermissionError(f"Blocked by robots.txt: {absolute}")
        delay = self.robots.crawl_delay() or 0.0
        if delay > 0:
            await asyncio.sleep(delay)
        return await self.client.get_html(absolute)

    async def download_image(self, url: str, dest: Path) -> Path:
        absolute = self.client._absolutize(url)
        if not self.robots.can_fetch(absolute):
            raise PermissionError(f"Blocked by robots.txt: {absolute}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await self.client.get_bytes(absolute)
        dest.write_bytes(content)
        return dest

    async def close(self) -> None:
        await self.client.aclose()