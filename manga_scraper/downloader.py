from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse

from tenacity import retry, wait_exponential, stop_after_attempt

from .config import SiteConfig
from .db import (
    add_or_update_chapter,
    get_series_by_slug,
    list_missing_chapters,
    mark_chapter_downloaded,
    upsert_page,
    upsert_series,
)
from .fetcher import BrowserFetcher, HttpFetcher
from .parsers import CatalogParser, SeriesParser, ChapterParser


DOWNLOADS_DIR = Path("downloads").absolute()


@dataclass
class AddedSeries:
    series_id: int
    slug: str
    title: str


def _slugify_from_url(series_url: str) -> str:
    # crude slug derivation: last non-empty path component
    parts = [p for p in Path(urlparse(series_url).path).parts if p and p != "/"]
    return parts[-1].strip("/") if parts else "series"


def add_series(config: SiteConfig, series_url: str, title_hint: Optional[str] = None, use_browser: bool = False) -> AddedSeries:
    slug = _slugify_from_url(series_url)
    if use_browser:
        with BrowserFetcher(config) as browser:
            res = browser.get_page_content(series_url)
            title = SeriesParser(config).parse_title(res.text or "") or title_hint or slug
    else:
        res = HttpFetcher(config).get_text(series_url)
        title = SeriesParser(config).parse_title(res.text or "") or title_hint or slug
    series_id = upsert_series(config.site_id, slug, title, series_url)
    return AddedSeries(series_id=series_id, slug=slug, title=title)


def sync_series(config: SiteConfig, series_slug: str, use_browser: bool = False) -> int:
    row = get_series_by_slug(config.site_id, series_slug)
    if row is None:
        raise ValueError(f"Series not found: {series_slug}")
    url = row["url"]
    html = (
        BrowserFetcher(config).__enter__().get_page_content(url).text
        if use_browser
        else HttpFetcher(config).get_text(url).text
    )
    if use_browser:
        # ensure browser context is closed
        BrowserFetcher(config).__exit__(None, None, None)
    parser = SeriesParser(config)
    chapters = parser.parse_chapters(html or "")
    added = 0
    for ch in chapters:
        add_or_update_chapter(series_id=int(row["id"]), number=ch.number, title=ch.title, url=ch.url)
        added += 1
    return added


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def _download_image(fetcher: HttpFetcher, url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    res = fetcher.get_binary(url)
    if res.status_code >= 400 or not res.content:
        raise RuntimeError(f"Failed to fetch image {url}: {res.status_code}")
    out_path.write_bytes(res.content)


def download_chapter(config: SiteConfig, series_slug: str, chapter_number: str, use_browser: bool = False) -> Path:
    # Locate chapter row
    from .db import get_conn

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT c.*, s.slug AS series_slug FROM chapters c
            JOIN series s ON s.id=c.series_id
            WHERE s.site_id=? AND s.slug=? AND c.number=?
            """,
            (config.site_id, series_slug, chapter_number),
        ).fetchone()
        if row is None:
            raise ValueError(f"Chapter not found: {series_slug} #{chapter_number}")
    ch_url = row["url"]

    # Fetch chapter page and parse image list
    if use_browser:
        with BrowserFetcher(config) as browser:
            html = browser.get_page_content(ch_url).text or ""
    else:
        html = HttpFetcher(config).get_text(ch_url).text or ""

    img_urls = ChapterParser(config).parse_image_urls(html)
    target_dir = DOWNLOADS_DIR / config.site_id / series_slug / str(chapter_number)

    fetcher = HttpFetcher(config)
    for idx, img_url in enumerate(img_urls, start=1):
        ext = Path(urlparse(img_url).path).suffix or ".jpg"
        out_path = target_dir / f"{idx:03d}{ext}"
        _download_image(fetcher, img_url, out_path)
        upsert_page(int(row["id"]), idx, img_url, str(out_path), status="downloaded")

    mark_chapter_downloaded(int(row["id"]), pages_count=len(img_urls))
    return target_dir


def download_missing(config: SiteConfig, series_slug: Optional[str] = None, use_browser: bool = False, limit: Optional[int] = None) -> List[Path]:
    rows = list_missing_chapters(config.site_id, series_slug)
    if limit is not None:
        rows = rows[:limit]
    paths: List[Path] = []
    for r in rows:
        paths.append(download_chapter(config, series_slug or "", r["number"], use_browser=use_browser))
    return paths


def export_cbz_for_chapter(site_id: str, series_slug: str, chapter_dir: Path) -> Path:
    out = chapter_dir.with_suffix(".cbz")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for img in sorted(chapter_dir.glob("*")):
            if img.is_file():
                zf.write(img, arcname=img.name)
    return out