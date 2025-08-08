from __future__ import annotations

import asyncio
from typing import Optional, Tuple, Dict

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
)


async def _fetch_page(url: str, user_agent: Optional[str] = None, timeout_ms: int = 60000) -> Tuple[str, str, Dict[str, str]]:
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import stealth_async
    except Exception:
        stealth_async = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=user_agent or MOBILE_UA,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 390, "height": 780},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)

        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        # Try to ride out CF challenge with a short loop
        max_wait_ms = 90000
        waited = 0
        while waited < max_wait_ms:
            html = await page.content()
            title = await page.title()
            if "Just a moment" not in title and "/cdn-cgi/challenge-platform" not in html:
                break
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
            waited += 13000

        html = await page.content()
        cookies = await context.cookies()
        jar = {c.get("name"): c.get("value") for c in cookies}
        await context.close()
        await browser.close()
        return url, html, jar


@retry(reraise=True, stop=stop_after_attempt(2), wait=wait_exponential_jitter(initial=2, max=10))
async def fetch_page(url: str, user_agent: Optional[str] = None, timeout_ms: int = 60000) -> Tuple[str, str, Dict[str, str]]:
    return await _fetch_page(url, user_agent=user_agent, timeout_ms=timeout_ms)


def fetch_page_sync(url: str, user_agent: Optional[str] = None, timeout_ms: int = 60000) -> Tuple[str, str, Dict[str, str]]:
    return asyncio.get_event_loop().run_until_complete(fetch_page(url, user_agent=user_agent, timeout_ms=timeout_ms))