import os
import asyncio
import httpx
from typing import List, Optional
from retrying import retry

DOWNLOAD_ROOT = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)


def safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (" ", "-", "_", ".") else "_" for c in name).strip()


@retry(stop_max_attempt_number=3, wait_fixed=1000)
def _sync_fetch(url: str, headers: Optional[dict] = None) -> bytes:
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


async def download_images(series: str, chapter: str, image_urls: List[str]) -> List[str]:
    series_dir = os.path.join(DOWNLOAD_ROOT, safe_filename(series))
    chapter_dir = os.path.join(series_dir, safe_filename(chapter))
    os.makedirs(chapter_dir, exist_ok=True)

    saved: List[str] = []
    for idx, url in enumerate(image_urls, start=1):
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        path = os.path.join(chapter_dir, f"{idx:03d}{ext}")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            saved.append(path)
            continue
        # Use sync fetch within thread to benefit from retry decorator
        data = await asyncio.to_thread(_sync_fetch, url, {"Referer": os.environ.get("JAPSCAN_BASE_URL", "https://www.japscan.si")})
        with open(path, "wb") as f:
            f.write(data)
        saved.append(path)
        await asyncio.sleep(0.2)
    return saved