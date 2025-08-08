from __future__ import annotations

import os
from typing import List

DEFAULT_BASE_URLS: List[str] = [
    "https://www.japscan.si",
    "https://www.japscan.me",
    "https://www.japscan.lol",
]

USER_AGENT = (
    os.environ.get(
        "JAPSCAN_USER_AGENT",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36",
    )
)

REQUEST_TIMEOUT_S: float = float(os.environ.get("JAPSCAN_TIMEOUT", "20"))
MAX_RETRIES: int = int(os.environ.get("JAPSCAN_MAX_RETRIES", "4"))
RETRY_BACKOFF_S: float = float(os.environ.get("JAPSCAN_RETRY_BACKOFF", "1.5"))
CONCURRENT_WORKERS: int = int(os.environ.get("JAPSCAN_WORKERS", "6"))
RATE_LIMIT_DELAY_S: float = float(os.environ.get("JAPSCAN_RATELIMIT_DELAY", "0.5"))

CATALOG_PATHS = [
    "/mangas",
    "/catalogue",
]

HOME_PATHS = [
    "/",
    "/updates",
    "/derniers-chapitres",
    "/recent",
]

SERIES_PATH_PREFIXES = [
    "/manga/",
    "/serie/",
]

READER_PATH_PREFIXES = [
    "/lecture-en-ligne/",
    "/lecture/",
    "/lire/",
]

HEADERS_BASE = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.8,en-US;q=0.6,en;q=0.4",
    "Cache-Control": "no-cache",
}

COOKIE_STRING = os.environ.get("JAPSCAN_COOKIES", "")


def configured_base_urls() -> List[str]:
    env = os.environ.get("JAPSCAN_BASE_URLS", "")
    urls = [u.strip() for u in env.split(",") if u.strip()]
    return urls or DEFAULT_BASE_URLS