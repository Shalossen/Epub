from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import re

import yaml
from bs4 import BeautifulSoup

from ..config import settings
from .base import BaseScraper


SELECTORS_PATH = Path("config/japscan_selectors.yaml")


@dataclass
class SeriesResult:
    title: str
    url: str
    slug: str


@dataclass
class ChapterResult:
    title: str
    url: str
    slug: str
    number: Optional[float]


@dataclass
class ImageResult:
    index: int
    url: str


class JapscanScraper(BaseScraper):
    def __init__(self, base_url: Optional[str] = None) -> None:
        super().__init__(base_url)
        if not SELECTORS_PATH.exists():
            raise FileNotFoundError(
                f"Selectors config not found: {SELECTORS_PATH}. Please fill it out."
            )
        self.selectors = yaml.safe_load(SELECTORS_PATH.read_text())

    async def iter_series(self) -> Iterable[SeriesResult]:
        cfg = self.selectors.get("series_index", {})
        start_urls: list[str] = cfg.get("start_urls", [])
        card_sel: str = cfg.get("series_card_selector")
        link_sel: str = cfg.get("series_link_selector")
        next_sel: Optional[str] = cfg.get("next_page_selector")
        if not (start_urls and card_sel and link_sel):
            raise ValueError("Missing series_index selectors in YAML config")

        for start_url in start_urls:
            url = start_url
            while url:
                soup = await self.fetch_html(url)
                for card in soup.select(card_sel):
                    a = card.select_one(link_sel)
                    if not a or not a.get("href"):
                        continue
                    href = a.get("href")
                    title = a.get_text(strip=True) or href.rstrip("/").split("/")[-1]
                    slug = self._slugify(title)
                    yield SeriesResult(title=title, url=href, slug=slug)
                if next_sel:
                    next_link = soup.select_one(next_sel)
                    url = next_link.get("href") if next_link and next_link.get("href") else None
                else:
                    url = None

    async def iter_chapters(self, series_url: str) -> Iterable[ChapterResult]:
        cfg = self.selectors.get("series_page", {})
        container_sel: str = cfg.get("chapters_container_selector")
        link_sel: str = cfg.get("chapter_link_selector")
        if not (container_sel and link_sel):
            raise ValueError("Missing series_page selectors in YAML config")

        soup = await self.fetch_html(series_url)
        container = soup.select_one(container_sel) or soup
        for a in container.select(link_sel):
            href = a.get("href")
            if not href:
                continue
            title = a.get_text(strip=True) or href.rstrip("/").split("/")[-1]
            number = self._extract_number(title)
            slug = self._slugify(title)
            yield ChapterResult(title=title, url=href, slug=slug, number=number)

    async def iter_images(self, chapter_url: str) -> Iterable[ImageResult]:
        cfg = self.selectors.get("chapter_page", {})
        img_sel: str = cfg.get("image_selector")
        img_attr: str = cfg.get("image_attr", "src")
        if not img_sel:
            raise ValueError("Missing chapter_page image_selector in YAML config")

        soup = await self.fetch_html(chapter_url)
        images = soup.select(img_sel)
        for idx, img in enumerate(images, start=1):
            src = img.get(img_attr)
            if not src:
                continue
            yield ImageResult(index=idx, url=src)

    @staticmethod
    def _slugify(text: str) -> str:
        value = text.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-+", "-", value).strip("-")
        return value or "item"

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None