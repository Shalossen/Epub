from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from tqdm import tqdm

from .client import HttpClient
from .models import Chapter, Page, ChapterPages
from .parser import parse_chapter_pages


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "file"


def fetch_chapter_pages(client: HttpClient, chapter: Chapter) -> ChapterPages:
    # Fetch the chapter landing page first
    _, html = client.get(chapter.url)
    pages_or_links = parse_chapter_pages(html, client.base_url)

    pages: List[Page] = []

    # If parse returned full image URLs, done; if they are page links, fetch each to find image
    are_links = any(p.image_url.startswith("/") or p.image_url.startswith(client.base_url) for p in pages_or_links)
    if are_links:
        # They might be page HTML links like /lecture-en-ligne/.../1.html
        page_items: List[Page] = []
        for p in pages_or_links:
            href = p.image_url
            if href.startswith("/"):
                href = f"{client.base_url}{href}"
            _, page_html = client.get(href)
            img_pages = parse_chapter_pages(page_html, client.base_url)
            # Expect single image per page
            for ip in img_pages:
                if ip.image_url.lower().startswith("http"):
                    page_items.append(Page(index=p.index, image_url=ip.image_url, referer=href))
        pages = sorted(page_items, key=lambda x: x.index)
    else:
        pages = sorted(pages_or_links, key=lambda x: x.index)

    return ChapterPages(chapter=chapter, pages=pages)


def download_chapter(client: HttpClient, chapter: Chapter, out_dir: str, workers: int = 6) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    cp = fetch_chapter_pages(client, chapter)

    def _download_one(page: Page) -> Optional[str]:
        ext = os.path.splitext(page.image_url.split("?")[0])[1] or ".jpg"
        filename = f"{sanitize_filename(chapter.number)}_{page.index:03d}{ext}"
        path = os.path.join(out_dir, filename)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        try:
            content = client.get_bytes(page.image_url, referer=page.referer or chapter.url)
            with open(path, "wb") as f:
                f.write(content)
            return path
        except Exception:
            return None

    results: List[str] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_download_one, p) for p in cp.pages]
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"Chapter {chapter.number}"):
            out = fut.result()
            if out:
                results.append(out)

    return sorted(results)