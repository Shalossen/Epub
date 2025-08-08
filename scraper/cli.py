import os
import asyncio
import re
import click
from rich import print
from typing import Optional, List, Tuple
from .browser import get_browser, get_context, new_stealth_page, wait_for_cloudflare_challenge
from . import db
from . import japscan
from .downloader import download_images

BASE_URL = os.environ.get("JAPSCAN_BASE_URL", "https://www.japscan.si")


@click.group()
def cli():
    pass


@cli.command()
@click.option("--alpha", default=None, help="Optional alphabet section to fetch (e.g., A, B, ...)")
@click.option("--limit", default=0, type=int, help="Limit series added")
def catalog(alpha: Optional[str], limit: int):
    """Scan the catalog and cache series in the DB."""
    async def run():
        added = 0
        path = "/mangas/" if not alpha else f"/mangas/{alpha.upper()}/"
        async with get_browser(headless=True) as browser:
            async with get_context(browser) as context:
                page = await new_stealth_page(context)
                await page.goto(BASE_URL, wait_until="domcontentloaded")
                await wait_for_cloudflare_challenge(page)
                html = await page.content()
                # Navigate to catalog
                await page.goto(BASE_URL + path, wait_until="domcontentloaded")
                await wait_for_cloudflare_challenge(page)
                html = await page.content()
                items = await japscan.parse_catalog_page(html)
                for title, url in items:
                    slug = japscan.series_slug_from_url(url)
                    series_id = db.upsert_series(slug, title, url)
                    added += 1
                    if limit and added >= limit:
                        break
        print(f"[green]Catalog cached[/green]. {added} series updated.")
    asyncio.run(run())


@cli.command()
@click.option("--series", "series_name", required=True, help="Series title or slug")
@click.option("--max", "max_chapters", default=0, type=int, help="Max chapters to sync from the series page")
def sync(series_name: str, max_chapters: int):
    """Fetch a series page and update chapters list in DB."""
    async def run():
        # Resolve series from DB or treat input as slug/path
        row = next((s for s in db.list_all_series() if series_name.lower() in (s[2].lower(), s[1].lower())), None)
        if not row:
            # Allow direct URL/slug
            if series_name.startswith("http"):
                url = series_name
                slug = japscan.series_slug_from_url(series_name)
                title = slug.replace("-", " ")
            else:
                slug = series_name
                url = f"{BASE_URL}/manga/{slug}/"
                title = slug.replace("-", " ")
            series_id = db.upsert_series(slug, title, url)
        else:
            series_id, slug, title, url = row
        async with get_browser(headless=True) as browser:
            async with get_context(browser) as context:
                page = await new_stealth_page(context)
                await page.goto(url, wait_until="domcontentloaded")
                await wait_for_cloudflare_challenge(page)
                html = await page.content()
                chapters = await japscan.extract_series_chapters(html)
                if max_chapters:
                    chapters = chapters[-max_chapters:]
                for number, ctitle, curl in chapters:
                    db.upsert_chapter(db.get_series_by_slug(slug)[0], number, ctitle, curl)
        print(f"[green]Synced[/green] {title}: {len(chapters)} chapters cached.")
    asyncio.run(run())


@cli.command()
@click.option("--series", "series_name", required=True, help="Series title or slug")
def missing(series_name: str):
    """List missing (not downloaded) chapters for a series."""
    row = next((s for s in db.list_all_series() if series_name.lower() in (s[2].lower(), s[1].lower())), None)
    if not row:
        print("[red]Series not found in DB. Run catalog or sync first.[/red]")
        return
    series_id, slug, title, url = row
    miss = db.get_missing_chapters(series_id)
    for cid, number, ctitle, curl in miss:
        print(f"- {title} ch.{number} :: {curl}")
    print(f"[bold]{len(miss)}[/bold] missing chapters.")


@cli.command()
@click.option("--series", "series_name", required=True)
@click.option("--from", "from_ch", default=None, help="Start chapter number (inclusive) or 'latest' or exact number")
@click.option("--to", "to_ch", default=None, help="End chapter number (inclusive) or 'latest'")
@click.option("--only", "only_ch", default=None, help="Comma-separated chapter numbers to download")
@click.option("--headful/--headless", default=False, help="Run browser headful for debugging")
def download(series_name: str, from_ch: Optional[str], to_ch: Optional[str], only_ch: Optional[str], headful: bool):
    """Download chapters. If not cached, sync series page first."""
    async def run():
        row = next((s for s in db.list_all_series() if series_name.lower() in (s[2].lower(), s[1].lower())), None)
        if not row:
            print("[yellow]Series not found in DB; attempting to sync...[/yellow]")
            # Trigger sync to populate
            await asyncio.to_thread(lambda: None)
        # Re-fetch row
        row2 = next((s for s in db.list_all_series() if series_name.lower() in (s[2].lower(), s[1].lower())), None)
        if not row2:
            print("[red]Series not available. Run catalog/sync first.[/red]")
            return
        series_id, slug, title, url = row2

        chapters = db.get_series_chapters(series_id)
        numbers = [c[2] for c in chapters]
        def to_float(n: str) -> float:
            try:
                return float(n.replace("-", ".").replace("v", ""))
            except Exception:
                return 0.0
        selected: List[Tuple[int, str, Optional[str], str]] = []
        if only_ch:
            wanted = {x.strip() for x in only_ch.split(",")}
            for cid, sid, num, ctitle, curl, dl in chapters:
                if num in wanted:
                    selected.append((cid, num, ctitle, curl))
        else:
            start = None
            end = None
            if from_ch == "latest" or from_ch is None:
                start = max(numbers, key=to_float) if numbers else None
            else:
                start = from_ch
            if to_ch == "latest" or to_ch is None:
                end = max(numbers, key=to_float) if numbers else None
            else:
                end = to_ch
            if start is None or end is None:
                print("[red]No chapters available to select.[/red]")
                return
            lo, hi = sorted([to_float(start), to_float(end)])
            for cid, sid, num, ctitle, curl, dl in chapters:
                fv = to_float(num)
                if lo <= fv <= hi:
                    selected.append((cid, num, ctitle, curl))
        if not selected:
            print("[yellow]No matching chapters found.[/yellow]")
            return

        async with get_browser(headless=not headful) as browser:
            async with get_context(browser) as context:
                page = await new_stealth_page(context)
                for cid, num, ctitle, curl in selected:
                    print(f"[cyan]Opening[/cyan] ch.{num}: {curl}")
                    await page.goto(curl, wait_until="domcontentloaded")
                    await wait_for_cloudflare_challenge(page)
                    await page.wait_for_timeout(1000)
                    image_urls = await japscan.extract_chapter_pages(page)
                    if not image_urls:
                        # Try scroll to trigger lazy load
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(1500)
                        image_urls = await japscan.extract_chapter_pages(page)
                    if not image_urls:
                        print(f"[red]No images found for chapter {num}[/red]")
                        continue
                    saved = await download_images(title, f"{num}", image_urls)
                    for idx, path in enumerate(saved, start=1):
                        db.upsert_page(cid, idx, image_urls[idx-1], path, status="saved")
                    db.mark_chapter_downloaded(cid)
                    print(f"[green]Saved[/green] {len(saved)} pages for ch.{num}")
    asyncio.run(run())


if __name__ == "__main__":
    cli()