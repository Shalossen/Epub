from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from .config import settings
from .db import get_session
from .models import Series, Chapter, Page
from .scraper.japscan import JapscanScraper


async def task_index_series() -> int:
    scraper = JapscanScraper()
    count = 0
    try:
        async for item in scraper.iter_series():
            with get_session() as session:
                existing = session.exec(select(Series).where(Series.url == item.url)).first()
                if existing:
                    continue
                series = Series(title=item.title, url=item.url, slug=item.slug)
                session.add(series)
                session.commit()
            count += 1
    finally:
        await scraper.close()
    return count


async def task_fetch_chapters(series_url: str) -> int:
    scraper = JapscanScraper()
    created = 0
    try:
        # ensure series exists or create
        with get_session() as session:
            series = session.exec(select(Series).where(Series.url == series_url)).first()
            if not series:
                # Fetch series title via last path segment
                slug = series_url.rstrip("/").split("/")[-1]
                series = Series(title=slug, url=series_url, slug=slug)
                session.add(series)
                session.commit()
                session.refresh(series)

        async for chap in scraper.iter_chapters(series_url):
            with get_session() as session:
                existing = session.exec(select(Chapter).where(Chapter.url == chap.url)).first()
                if existing:
                    continue
                chapter = Chapter(
                    series_id=series.id,
                    title=chap.title,
                    url=chap.url,
                    slug=chap.slug,
                    number=chap.number,
                )
                session.add(chapter)
                session.commit()
            created += 1
    finally:
        await scraper.close()
    return created


async def task_fetch_images(chapter_url: str) -> int:
    scraper = JapscanScraper()
    downloaded = 0
    try:
        with get_session() as session:
            chapter = session.exec(select(Chapter).where(Chapter.url == chapter_url)).first()
            if not chapter:
                # Chapter must be created via chapters fetch first
                raise ValueError("Chapter not found. Fetch chapters for the series first.")
            series = session.get(Series, chapter.series_id)
            assert series is not None

        base_dir = settings.data_dir / settings.images_dir_name / series.slug / chapter.slug

        async for img in scraper.iter_images(chapter_url):
            dest = base_dir / f"{img.index:04d}{_guess_ext(img.url)}"
            await scraper.download_image(img.url, dest)
            with get_session() as session:
                existing = session.exec(
                    select(Page).where(Page.chapter_id == chapter.id, Page.index == img.index)
                ).first()
                if existing:
                    continue
                page = Page(chapter_id=chapter.id, index=img.index, url=img.url, local_path=str(dest))
                session.add(page)
                session.commit()
            downloaded += 1
    finally:
        await scraper.close()
    return downloaded


def _guess_ext(url: str) -> str:
    lower = url.lower()
    if lower.endswith(".png"):
        return ".png"
    if lower.endswith(".webp"):
        return ".webp"
    return ".jpg"