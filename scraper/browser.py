import os
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async

BASE_URL = os.environ.get("JAPSCAN_BASE_URL", "https://www.japscan.si")


@asynccontextmanager
async def get_browser(headless: bool = True) -> AsyncIterator[Browser]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def get_context(browser: Browser) -> AsyncIterator[BrowserContext]:
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1365, "height": 900},
        java_script_enabled=True,
        ignore_https_errors=True,
    )
    # Basic stealth
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    try:
        yield context
    finally:
        await context.close()


async def new_stealth_page(context: BrowserContext) -> Page:
    page = await context.new_page()
    await stealth_async(page)
    return page


def _is_cf_challenge_title(title: str) -> bool:
    return title.strip().lower() in {"just a moment...", "attention required!"}


async def wait_for_cloudflare_challenge(page: Page, timeout: float = 30.0):
    try:
        # If CF interstitial, give time and wait for navigation away
        title = (await page.title()) or ""
        if _is_cf_challenge_title(title):
            # CF script usually redirects within a few seconds
            await page.wait_for_timeout(6000)
            # Wait for title to change or network to be idle
            try:
                await page.wait_for_function(
                    "document.title.toLowerCase() !== 'just a moment...' && document.title.toLowerCase() !== 'attention required!'",
                    timeout=timeout * 1000,
                )
            except Exception:
                pass
            await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
        else:
            # Also check for known CF DOM markers
            if await page.locator("text=Enable JavaScript and cookies to continue").count() > 0:
                await page.wait_for_timeout(6000)
                await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
    except Exception:
        return