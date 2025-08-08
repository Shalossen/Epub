from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print

from .config import Selectors, SiteConfig
from .db import init_db, list_series
from .downloader import add_series, sync_series, download_missing, download_chapter, export_cbz_for_chapter

app = typer.Typer(add_completion=False, help="Compliant manga/manhwa scraper CLI")


@app.command()
def init_db_cmd():
    init_db()
    print("[green]Database initialized[/green]")


@app.command()
def init_site(
    site_id: str = typer.Option(..., help="Identifier for the site config"),
    base_url: str = typer.Option(...),
    catalog_url: str = typer.Option(...),
    user_agent: str = typer.Option("MangaScraperBot/1.0", help="Contactable UA"),
):
    cfg = SiteConfig(
        site_id=site_id,
        base_url=base_url,
        catalog_url=catalog_url,
        user_agent=user_agent,
        selectors=Selectors(
            catalog_series_links="a.series-link",
            series_title="h1",
            series_chapter_links="ul.chapters a",
            chapter_page_images="div.reader img",
        ),
    )
    path = cfg.save()
    print(f"[green]Wrote[/green] {path}")


@app.command()
def add_series_cmd(
    site_id: str = typer.Option(...),
    series_url: str = typer.Option(...),
    use_browser: bool = typer.Option(False, help="Fetch series page via headless browser"),
):
    cfg = SiteConfig.load(site_id)
    added = add_series(cfg, series_url, use_browser=use_browser)
    print(json.dumps({"series_id": added.series_id, "slug": added.slug, "title": added.title}, indent=2))


@app.command()
def sync_series_cmd(
    site_id: str = typer.Option(...),
    series_slug: str = typer.Option(...),
    use_browser: bool = typer.Option(False),
):
    cfg = SiteConfig.load(site_id)
    count = sync_series(cfg, series_slug, use_browser=use_browser)
    print(f"[green]Synced chapters:[/green] {count}")


@app.command()
def list_series_cmd(site_id: str = typer.Option(...)):
    rows = list_series(site_id)
    for r in rows:
        print(f"- {r['slug']}: {r['title']} ({r['url']})")


@app.command()
def download_missing_cmd(
    site_id: str = typer.Option(...),
    series_slug: Optional[str] = typer.Option(None),
    use_browser: bool = typer.Option(False),
    limit: Optional[int] = typer.Option(None),
):
    cfg = SiteConfig.load(site_id)
    paths = download_missing(cfg, series_slug=series_slug, use_browser=use_browser, limit=limit)
    for p in paths:
        print(f"[green]Downloaded:[/green] {p}")


@app.command()
def download_range(
    site_id: str = typer.Option(...),
    series_slug: str = typer.Option(...),
    from_ch: str = typer.Option(..., "--from"),
    to_ch: str = typer.Option(..., "--to"),
    use_browser: bool = typer.Option(False),
):
    cfg = SiteConfig.load(site_id)
    # naive inclusive loop assuming numeric
    import math

    def frange(a: float, b: float):
        n = int((b - a) * 10) + 1 if not a.is_integer() or not b.is_integer() else int(b - a) + 1
        step = (b - a) / max(n - 1, 1)
        for i in range(n):
            yield round(a + i * step, 1)

    start = float(from_ch)
    end = float(to_ch)
    for num in frange(start, end):
        download_chapter(cfg, series_slug, f"{num}", use_browser=use_browser)
        print(f"[green]Downloaded chapter[/green] {num}")


@app.command()
def export_cbz(
    site_id: str = typer.Option(...),
    series_slug: str = typer.Option(...),
    chapter_number: str = typer.Option(...),
):
    chapter_dir = Path("downloads") / site_id / series_slug / chapter_number
    if not chapter_dir.exists():
        raise typer.BadParameter(f"Not found: {chapter_dir}")
    out = export_cbz_for_chapter(site_id, series_slug, chapter_dir)
    print(f"[green]Wrote CBZ:[/green] {out}")


if __name__ == "__main__":
    app()