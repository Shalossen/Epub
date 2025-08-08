from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class Selectors:
    catalog_series_links: str
    series_title: str
    series_chapter_links: str
    chapter_page_images: str


@dataclass
class SiteConfig:
    site_id: str
    base_url: str
    catalog_url: str
    user_agent: str = "MangaScraperBot/1.0"
    rate_limit_seconds: float = 1.0
    respect_robots_txt: bool = True
    selectors: Selectors | None = None
    extra_headers: Dict[str, str] | None = None

    @staticmethod
    def config_dir() -> Path:
        return Path("sites").absolute()

    @classmethod
    def load(cls, site_id: str) -> "SiteConfig":
        path = cls.config_dir() / f"{site_id}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        selectors = data.get("selectors") or {}
        return cls(
            site_id=data["site_id"],
            base_url=data["base_url"],
            catalog_url=data["catalog_url"],
            user_agent=data.get("user_agent", "MangaScraperBot/1.0"),
            rate_limit_seconds=float(data.get("rate_limit_seconds", 1.0)),
            respect_robots_txt=bool(data.get("respect_robots_txt", True)),
            selectors=Selectors(
                catalog_series_links=selectors.get("catalog_series_links", "a"),
                series_title=selectors.get("series_title", "h1"),
                series_chapter_links=selectors.get("series_chapter_links", "a"),
                chapter_page_images=selectors.get("chapter_page_images", "img"),
            ),
            extra_headers=(data.get("extra_headers") or None),
        )

    def save(self) -> Path:
        SiteConfig.config_dir().mkdir(parents=True, exist_ok=True)
        path = SiteConfig.config_dir() / f"{self.site_id}.yaml"
        doc: Dict[str, object] = {
            "site_id": self.site_id,
            "base_url": self.base_url,
            "catalog_url": self.catalog_url,
            "user_agent": self.user_agent,
            "rate_limit_seconds": self.rate_limit_seconds,
            "respect_robots_txt": self.respect_robots_txt,
            "selectors": {
                "catalog_series_links": self.selectors.catalog_series_links if self.selectors else "a",
                "series_title": self.selectors.series_title if self.selectors else "h1",
                "series_chapter_links": self.selectors.series_chapter_links if self.selectors else "a",
                "chapter_page_images": self.selectors.chapter_page_images if self.selectors else "img",
            },
        }
        if self.extra_headers:
            doc["extra_headers"] = dict(self.extra_headers)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        return path