from __future__ import annotations

import json
import os
import sys
from typing import Optional, List
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.table import Table

from .config import configured_base_urls, CATALOG_PATHS, CONCURRENT_WORKERS, RATE_LIMIT_DELAY_S, HOME_PATHS
from .client import HttpClient
from .parser import parse_catalog, parse_series, HREF_SERIES_RE
from .models import SeriesWithChapters
from .downloader import fetch_chapter_pages, download_chapter, sanitize_filename
from .browser import fetch_page_sync

console = Console()


def resolve_base_url(preferred: Optional[str] = None) -> str:
    candidates: List[str] = []
    if preferred:
        candidates.append(preferred.rstrip("/"))
    candidates.extend([u.rstrip("/") for u in configured_base_urls()])

    for base in candidates:
        try:
            client = HttpClient(base, rate_limit_delay_s=RATE_LIMIT_DELAY_S)
            client.get("/")
            return base
        except Exception:
            continue
    return candidates[0]


def extract_series_slug_from_url(url: str) -> Optional[str]:
    try:
        path = urlparse(url).path
        m = HREF_SERIES_RE.match(path)
        if m:
            return m.group(2)
    except Exception:
        return None
    return None


@click.group()
@click.option("--base-url", envvar="JAPSCAN_BASE_URL", default=None, help="Base URL, e.g. https://www.japscan.si")
@click.option("--rate", envvar="JAPSCAN_RATELIMIT_DELAY", default=RATE_LIMIT_DELAY_S, type=float, help="Rate-limit delay seconds")
@click.option("--engine", envvar="JAPSCAN_HTTP_ENGINE", default="auto", type=click.Choice(["auto","cloudscraper","curl","requests"]), help="HTTP engine")
@click.option("--browser", is_flag=True, help="Use headless browser to fetch protected pages (Playwright)")
@click.pass_context
def main(ctx: click.Context, base_url: Optional[str], rate: float, engine: str, browser: bool):
    base = resolve_base_url(base_url)
    ctx.ensure_object(dict)
    ctx.obj["client"] = HttpClient(base_url=base, rate_limit_delay_s=rate, engine=engine)
    ctx.obj["base"] = base
    ctx.obj["use_browser"] = browser


@main.command()
@click.argument("url")
@click.option("--out", "out_path", type=click.Path(dir_okay=False), help="Write HTML to file (optional)")
@click.pass_context
def browser_html(ctx: click.Context, url: str, out_path: Optional[str]):
    _, html, cookies = fetch_page_sync(url)
    # warm cookies into the client
    client: HttpClient = ctx.obj["client"]
    client.update_cookies(cookies)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        console.print(f"Wrote HTML -> {out_path}")
    else:
        console.print(html[:5000])


@main.command()
@click.option("--limit", default=0, type=int, help="Limit number of results")
@click.option("--json", "json_out", type=click.Path(dir_okay=False), help="Write JSON output to file")
@click.pass_context
def catalog(ctx: click.Context, limit: int, json_out: Optional[str]):
    client: HttpClient = ctx.obj["client"]
    base: str = ctx.obj["base"]

    items = []
    tried_paths = []
    for path in CATALOG_PATHS + HOME_PATHS:
        if path in tried_paths:
            continue
        tried_paths.append(path)
        try:
            _, html = client.get(path)
            items = parse_catalog(html, base)
            if items:
                break
        except Exception:
            continue

    if limit > 0:
        items = items[:limit]

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump([s.model_dump() for s in items], f, ensure_ascii=False, indent=2)
        console.print(f"Wrote {len(items)} series -> {json_out}")
    else:
        table = Table(title=f"Catalog ({len(items)}) @ {base}")
        table.add_column("Slug")
        table.add_column("Title")
        for s in items:
            table.add_row(s.slug, s.title)
        console.print(table)


@main.command()
@click.argument("series_or_url")
@click.option("--json", "json_out", type=click.Path(dir_okay=False), help="Write JSON to file")
@click.pass_context
def series(ctx: click.Context, series_or_url: str, json_out: Optional[str]):
    client: HttpClient = ctx.obj["client"]
    base: str = ctx.obj["base"]
    use_browser: bool = ctx.obj.get("use_browser", False)

    last_exc: Optional[Exception] = None
    swc: Optional[SeriesWithChapters] = None

    def fetch_with_browser_then_client(url: str) -> str:
        # Use browser to get HTML and cookies, then inject cookies into client and re-fetch via HTTP
        _, html, cookies = fetch_page_sync(url)
        client.update_cookies(cookies)
        _, html2 = client.get(url)
        return html2 or html

    if series_or_url.startswith("http://") or series_or_url.startswith("https://"):
        url = series_or_url
        slug = extract_series_slug_from_url(url) or sanitize_filename(urlparse(url).path.rsplit("/", 1)[-1])
        try:
            if use_browser:
                html = fetch_with_browser_then_client(url)
            else:
                _, html = client.get(url)
            swc = parse_series(html, base, slug)
        except Exception as exc:
            last_exc = exc
    else:
        series_slug = series_or_url
        for prefix in ["/manga/", "/serie/"]:
            try:
                url = f"{base}{prefix}{series_slug}"
                if use_browser:
                    html = fetch_with_browser_then_client(url)
                else:
                    _, html = client.get(f"{prefix}{series_slug}")
                swc = parse_series(html, base, series_slug)
                if swc and swc.chapters:
                    break
            except Exception as exc:
                last_exc = exc
                continue

    if not swc:
        raise click.ClickException(f"Series not found: {series_or_url} ({last_exc})")

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "series": swc.series.model_dump(),
                    "chapters": [c.model_dump() for c in swc.chapters],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        console.print(f"Wrote series -> {json_out}")
    else:
        table = Table(title=f"{swc.series.title} ({len(swc.chapters)} chapters)")
        table.add_column("#")
        table.add_column("Name")
        table.add_column("URL")
        for ch in swc.chapters:
            table.add_row(ch.number, ch.name or "", ch.url)
        console.print(table)


@main.command()
@click.argument("url")
@click.option("--out", "out_path", type=click.Path(dir_okay=False), help="Write HTML to file (optional)")
@click.pass_context
def debug_html(ctx: click.Context, url: str, out_path: Optional[str]):
    client: HttpClient = ctx.obj["client"]
    _, html = client.get(url)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        console.print(f"Wrote HTML -> {out_path}")
    else:
        console.print(html[:5000])


@main.command()
@click.argument("series_slug")
@click.argument("chapter_number")
@click.option("--json", "json_out", type=click.Path(dir_okay=False), help="Write JSON to file")
@click.pass_context
def chapter(ctx: click.Context, series_slug: str, chapter_number: str, json_out: Optional[str]):
    client: HttpClient = ctx.obj["client"]
    base: str = ctx.obj["base"]

    ch_url = f"/lecture-en-ligne/{series_slug}/{chapter_number}"
    from .models import Chapter as ChapterModel

    ch = ChapterModel(series_slug=series_slug, number=str(chapter_number), url=f"{base}{ch_url}")
    cp = fetch_chapter_pages(client, ch)

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump({"chapter": cp.chapter.model_dump(), "pages": [p.model_dump() for p in cp.pages]}, f, ensure_ascii=False, indent=2)
        console.print(f"Wrote chapter -> {json_out}")
    else:
        table = Table(title=f"{series_slug} {chapter_number} ({len(cp.pages)} pages)")
        table.add_column("Index")
        table.add_column("Image URL")
        for p in cp.pages:
            table.add_row(str(p.index), p.image_url)
        console.print(table)


@main.command()
@click.argument("series_slug")
@click.argument("chapter_number")
@click.option("--out", "out_dir", required=True, type=click.Path(file_okay=False))
@click.option("--workers", default=CONCURRENT_WORKERS, show_default=True, type=int)
@click.pass_context
def download(ctx: click.Context, series_slug: str, chapter_number: str, out_dir: str, workers: int):
    client: HttpClient = ctx.obj["client"]
    base: str = ctx.obj["base"]

    from .models import Chapter as ChapterModel

    ch_url = f"/lecture-en-ligne/{series_slug}/{chapter_number}"
    ch = ChapterModel(series_slug=series_slug, number=str(chapter_number), url=f"{base}{ch_url}")
    series_dir = os.path.join(out_dir, sanitize_filename(series_slug))
    os.makedirs(series_dir, exist_ok=True)
    chapter_dir = os.path.join(series_dir, sanitize_filename(str(chapter_number)))
    os.makedirs(chapter_dir, exist_ok=True)

    paths = download_chapter(client, ch, chapter_dir, workers=workers)
    console.print(f"Downloaded {len(paths)} files to {chapter_dir}")


@main.command()
@click.argument("series_slug")
@click.option("--out", "out_dir", required=True, type=click.Path(file_okay=False))
@click.option("--start", default=None, type=str, help="Start from chapter number (inclusive)")
@click.option("--end", default=None, type=str, help="End at chapter number (inclusive)")
@click.option("--workers", default=CONCURRENT_WORKERS, show_default=True, type=int)
@click.pass_context
def bulk(ctx: click.Context, series_slug: str, out_dir: str, start: Optional[str], end: Optional[str], workers: int):
    client: HttpClient = ctx.obj["client"]
    base: str = ctx.obj["base"]

    swc: Optional[SeriesWithChapters] = None
    last_exc: Optional[Exception] = None
    for prefix in ["/manga/", "/serie/"]:
        try:
            _, html = client.get(f"{prefix}{series_slug}")
            swc = parse_series(html, base, series_slug)
            if swc and swc.chapters:
                break
        except Exception as exc:
            last_exc = exc
            continue

    if not swc:
        raise click.ClickException(f"Series not found: {series_slug} ({last_exc})")

    chapters = swc.chapters

    def as_float(x: str) -> float:
        import re
        try:
            return float(re.sub(r"[^0-9.]+", "", x))
        except Exception:
            return float("inf")

    if start:
        chapters = [c for c in chapters if as_float(c.number) >= as_float(start)]
    if end:
        chapters = [c for c in chapters if as_float(c.number) <= as_float(end)]

    series_dir = os.path.join(out_dir, sanitize_filename(series_slug))
    os.makedirs(series_dir, exist_ok=True)

    for ch in chapters:
        if ch.url.startswith("http"):
            ch_url = ch.url
        else:
            ch_url = f"{base}{ch.url}"
        from .models import Chapter as ChapterModel
        ch_model = ChapterModel(series_slug=series_slug, number=ch.number, url=ch_url)
        chapter_dir = os.path.join(series_dir, sanitize_filename(str(ch.number)))
        try:
            download_chapter(client, ch_model, chapter_dir, workers=workers)
        except Exception as exc:
            console.print(f"[yellow]Failed chapter {ch.number}: {exc}")


if __name__ == "__main__":
    main()