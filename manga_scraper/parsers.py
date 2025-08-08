from __future__ import annotations

from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Tuple
from urllib.parse import urljoin

from .config import SiteConfig


@dataclass
class SeriesLink:
    title: str
    url: str


@dataclass
class ChapterLink:
    title: str
    number: str
    url: str


class CatalogParser:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config

    def parse_series_links(self, html: str) -> List[SeriesLink]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.select(self.config.selectors.catalog_series_links):
            href = a.get("href")
            title = (a.get_text() or "").strip()
            if not href or not title:
                continue
            links.append(SeriesLink(title=title, url=urljoin(self.config.base_url, href)))
        return links


class SeriesParser:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config

    def parse_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        el = soup.select_one(self.config.selectors.series_title)
        return (el.get_text() if el else "").strip()

    def parse_chapters(self, html: str) -> List[ChapterLink]:
        soup = BeautifulSoup(html, "html.parser")
        chs: List[ChapterLink] = []
        for a in soup.select(self.config.selectors.series_chapter_links):
            href = a.get("href")
            raw_title = (a.get_text() or "").strip()
            if not href or not raw_title:
                continue
            # try to extract a chapter number from the title text
            number = self._extract_number(raw_title)
            chs.append(ChapterLink(title=raw_title, number=number, url=urljoin(self.config.base_url, href)))
        return chs

    @staticmethod
    def _extract_number(text: str) -> str:
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        return m.group(1) if m else text


class ChapterParser:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config

    def parse_image_urls(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []
        for img in soup.select(self.config.selectors.chapter_page_images):
            src = img.get("data-src") or img.get("src")
            if not src:
                continue
            urls.append(urljoin(self.config.base_url, src))
        return urls