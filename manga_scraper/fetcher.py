from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
import urllib.robotparser as robotparser

import httpx
from playwright.sync_api import sync_playwright, Browser, Page

from .config import SiteConfig


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: Optional[str] = None
    content: Optional[bytes] = None
    final_url: Optional[str] = None


class RobotsGuardian:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config
        self._rp: Optional[robotparser.RobotFileParser] = None

    def _load(self) -> None:
        if self._rp is not None:
            return
        robots_url = urljoin(self.config.base_url, "/robots.txt")
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            # Fail-open: if robots cannot be loaded, treat as allowed
            rp = None
        self._rp = rp

    def is_allowed(self, url: str) -> bool:
        if not self.config.respect_robots_txt:
            return True
        self._load()
        if self._rp is None:
            return True
        return self._rp.can_fetch(self.config.user_agent, url)


class HttpFetcher:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config
        self.guard = RobotsGuardian(config)
        self._last_request_ts = 0.0
        self._client = httpx.Client(headers={"User-Agent": config.user_agent}, follow_redirects=True, timeout=30.0)

    def _throttle(self) -> None:
        now = time.time()
        delta = now - self._last_request_ts
        if delta < self.config.rate_limit_seconds:
            time.sleep(self.config.rate_limit_seconds - delta)
        self._last_request_ts = time.time()

    def get_text(self, url: str) -> FetchResult:
        if not self.guard.is_allowed(url):
            raise PermissionError(f"robots.txt disallows access to {url}")
        self._throttle()
        resp = self._client.get(url)
        return FetchResult(url=url, status_code=resp.status_code, text=resp.text, final_url=str(resp.url))

    def get_binary(self, url: str) -> FetchResult:
        if not self.guard.is_allowed(url):
            raise PermissionError(f"robots.txt disallows access to {url}")
        self._throttle()
        resp = self._client.get(url)
        return FetchResult(url=url, status_code=resp.status_code, content=resp.content, final_url=str(resp.url))


class BrowserFetcher:
    def __init__(self, config: SiteConfig, headless: bool = True) -> None:
        self.config = config
        self.guard = RobotsGuardian(config)
        self.headless = headless
        self._play = None
        self._browser: Optional[Browser] = None

    def __enter__(self) -> "BrowserFetcher":
        self._play = sync_playwright().start()
        self._browser = self._play.chromium.launch(headless=self.headless)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._play:
                self._play.stop()

    def get_page_content(self, url: str) -> FetchResult:
        if not self.guard.is_allowed(url):
            raise PermissionError(f"robots.txt disallows access to {url}")
        assert self._browser is not None
        context = self._browser.new_context(user_agent=self.config.user_agent)
        page: Page = context.new_page()
        page.set_default_timeout(30000)
        page.goto(url, wait_until="domcontentloaded")
        html = page.content()
        final_url = page.url
        context.close()
        return FetchResult(url=url, status_code=200, text=html, final_url=final_url)

    def download_binary(self, url: str) -> FetchResult:
        if not self.guard.is_allowed(url):
            raise PermissionError(f"robots.txt disallows access to {url}")
        assert self._browser is not None
        context = self._browser.new_context(user_agent=self.config.user_agent)
        page: Page = context.new_page()
        with page.expect_download() as dwn:
            page.goto(url)
        download = dwn.value
        content = download.content()
        context.close()
        return FetchResult(url=url, status_code=200, content=content, final_url=url)