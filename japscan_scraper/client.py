from __future__ import annotations

import os
import time
from typing import Optional, Tuple

import requests
import cloudscraper
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from .config import HEADERS_BASE, REQUEST_TIMEOUT_S, MAX_RETRIES, RETRY_BACKOFF_S, COOKIE_STRING

try:
    from curl_cffi.requests import Session as CurlSession  # type: ignore
    HAS_CURL = True
except Exception:
    HAS_CURL = False


class HttpError(Exception):
    pass


class HttpClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[dict] = None,
        rate_limit_delay_s: float = 0.0,
        engine: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = {**HEADERS_BASE, **(headers or {})}
        self.rate_limit_delay_s = rate_limit_delay_s
        preferred_engine = engine or os.environ.get("JAPSCAN_HTTP_ENGINE", "auto")

        self.session = None
        self.engine = "requests"

        if preferred_engine in ("curl", "auto") and HAS_CURL:
            try:
                s = CurlSession(impersonate=os.environ.get("JAPSCAN_CF_IMPERSONATE", "chrome120"))
                self.session = s
                self.engine = "curl"
            except Exception:
                self.session = None
        if self.session is None:
            # Try cloudscraper
            try:
                self.session = cloudscraper.create_scraper()
                self.engine = "cloudscraper"
            except Exception:
                self.session = requests.Session()
                self.engine = "requests"

        # Default headers and same-origin hints
        default_headers = {
            **self.headers,
            "Referer": self.base_url + "/",
            "Origin": self.base_url,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
        }
        try:
            self.session.headers.update(default_headers)  # type: ignore[attr-defined]
        except Exception:
            # curl_cffi Session supports 'headers' dict too
            self.session.headers = {**getattr(self.session, "headers", {}), **default_headers}  # type: ignore[attr-defined]

        if COOKIE_STRING:
            try:
                jar = requests.cookies.RequestsCookieJar()
                for part in COOKIE_STRING.split(";"):
                    part = part.strip()
                    if not part or "=" not in part:
                        continue
                    name, value = part.split("=", 1)
                    jar.set(name.strip(), value.strip(), domain=self.base_url.split("//",1)[-1])
                # requests jar is compatible with curl_cffi's API
                self.session.cookies.update(jar)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _delay(self):
        if self.rate_limit_delay_s > 0:
            time.sleep(self.rate_limit_delay_s)

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential_jitter(initial=RETRY_BACKOFF_S, max=12),
        retry=retry_if_exception_type((requests.RequestException, HttpError)),
    )
    def get(self, path_or_url: str, *, allow_redirects: bool = True, referer: Optional[str] = None) -> Tuple[str, str]:
        self._delay()
        url = path_or_url
        if url.startswith("/"):
            url = f"{self.base_url}{url}"
        headers = {}
        if referer:
            headers["Referer"] = referer
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT_S, allow_redirects=allow_redirects, headers=headers)  # type: ignore[attr-defined]
        if getattr(resp, "status_code", 200) >= 400:
            raise HttpError(f"GET {url} -> {resp.status_code}")
        content_type = resp.headers.get("content-type", "").lower()
        if "html" in content_type or "xml" in content_type or content_type == "":
            text = resp.text
        else:
            text = resp.content.decode("utf-8", errors="ignore")
        return url, text

    @retry(
        reraise=True,
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential_jitter(initial=RETRY_BACKOFF_S, max=12),
        retry=retry_if_exception_type((requests.RequestException, HttpError)),
    )
    def get_bytes(self, url: str, referer: Optional[str] = None) -> bytes:
        self._delay()
        headers = {}
        if referer:
            headers["Referer"] = referer
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT_S, headers=headers, stream=True)  # type: ignore[attr-defined]
        if getattr(resp, "status_code", 200) >= 400:
            raise HttpError(f"GET {url} -> {resp.status_code}")
        return resp.content