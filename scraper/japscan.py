import re
import os
from typing import List, Dict, Tuple, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import Page

BASE_URL = os.environ.get("JAPSCAN_BASE_URL", "https://www.japscan.si")


def series_slug_from_url(url: str) -> str:
    # Examples: /manga/solo-leveling/ or /manga/One-Piece/
    m = re.search(r"/manga/([^/]+)/?", url)
    return m.group(1) if m else re.sub(r"\W+", "-", url.strip("/"))


def chapter_number_from_text(text: str) -> str:
    # Try to normalize 'Chapitre 203', '203', '203.5', etc.
    m = re.search(r"(\d+(?:[\.-]\d+)?)", text)
    return m.group(1) if m else text.strip()


async def parse_catalog_page(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    results: List[Tuple[str, str]] = []
    # Catalog links are likely under "/manga/<slug>/"
    for a in soup.select('a[href^="/manga/"]'):
        href = a.get("href")
        title = a.get_text(strip=True)
        # Filter noise like navbar /manga/ vs series entries: keep ones beyond simple nav
        if href and href.startswith("/manga/") and title and len(title) > 2:
            results.append((title, urljoin(BASE_URL, href)))
    # Deduplicate by URL keeping longest title
    seen: Dict[str, str] = {}
    for title, url in results:
        if url not in seen or len(title) > len(seen[url]):
            seen[url] = title
    return [(v, k) for k, v in seen.items()]


async def navigate_and_get_html(page: Page, path: str) -> str:
    url = urljoin(BASE_URL, path)
    await page.goto(url, wait_until="domcontentloaded")
    # Some pages lazy load; ensure ready
    await page.wait_for_timeout(500)
    return await page.content()


async def extract_series_chapters(html: str) -> List[Tuple[str, Optional[str], str]]:
    soup = BeautifulSoup(html, "lxml")
    chapters: List[Tuple[str, Optional[str], str]] = []
    # Typical chapter list under .chapter-list or list-group with links to /lecture-en-ligne/
    for a in soup.select('a[href*="/lecture"]'):
        href = a.get("href")
        text = a.get_text(" ", strip=True)
        if not href:
            continue
        number = chapter_number_from_text(text)
        title: Optional[str] = text
        chapters.append((number, title, urljoin(BASE_URL, href)))
    # Fallback: look for anchors that include series slug + number-like endings
    if not chapters:
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/lecture" in href:
                text = a.get_text(" ", strip=True)
                number = chapter_number_from_text(text)
                chapters.append((number, text, urljoin(BASE_URL, href)))
    # Deduplicate by number keep latest URL
    dedup: Dict[str, Tuple[str, Optional[str], str]] = {}
    for number, title, url in chapters:
        dedup[number] = (number, title, url)
    # Sort numerically where possible
    def chapter_key(n: str):
        try:
            return float(n.replace("-", ".").replace("v", ""))
        except Exception:
            return 0.0
    return sorted(dedup.values(), key=lambda t: chapter_key(t[0]))


async def extract_chapter_pages(page: Page) -> List[str]:
    # On a chapter page, images may be present or need clicking. Try to collect all images.
    # Strategy: look for images within #chapters or main container; also check data-src attributes.
    imgs = await page.eval_on_selector_all(
        "img",
        "elements => elements.map(e => e.getAttribute('data-src') || e.getAttribute('src'))",
    )
    urls = [u for u in imgs if u and (u.startswith("http") or u.startswith("/"))]
    # Normalize to absolute URLs
    abs_urls = [u if u.startswith("http") else urljoin(BASE_URL, u) for u in urls]
    # Filter CDN/image paths
    abs_urls = [u for u in abs_urls if any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])]
    # Deduplicate preserving order
    seen = set()
    ordered: List[str] = []
    for u in abs_urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered