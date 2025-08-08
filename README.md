# Manga/Manhwa Scraper (Compliant)

This toolkit lets you maintain your own manga/manhwa library by:

- Discovering chapters you’re missing vs what you already downloaded
- Downloading selected series/chapters on demand
- Resuming interrupted downloads and exporting CBZ
- Respecting `robots.txt`, applying throttling, and identifying with a custom user-agent

Important: Only use this against websites you own/control or where you have explicit permission to crawl and download content. This project will not bypass site protections nor assist in doing so.

## Quick start

1) Python 3.11+

2) Create venv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium | cat
```

3) Initialize the database:

```bash
python -m manga_scraper.cli init-db
```

4) Create a site config (YAML) under `sites/` and register it:

```bash
python -m manga_scraper.cli init-site --site-id japscan-si --base-url https://www.example.com \
  --catalog-url https://www.example.com/catalogue \
  --user-agent "MyLibraryBot/1.0 (+contact@example.com)"
```

Then edit `sites/japscan-si.yaml` to fill CSS selectors for catalog, series, chapters, and pages.

5) Add a series and sync its chapters:

```bash
python -m manga_scraper.cli add-series --site-id japscan-si --series-url https://www.example.com/lecture-en-ligne/solo-leveling/
python -m manga_scraper.cli sync-series --site-id japscan-si --series-slug solo-leveling
```

6) Download missing chapters:

```bash
python -m manga_scraper.cli download-missing --site-id japscan-si --concurrency 3
```

7) Download a specific range:

```bash
python -m manga_scraper.cli download-range --site-id japscan-si --series-slug solo-leveling --from 21 --to 60
```

## Site config (YAML)

Placed in `sites/<site-id>.yaml`:

```yaml
site_id: japscan-si
base_url: https://www.example.com
catalog_url: https://www.example.com/catalogue
user_agent: MyLibraryBot/1.0 (+contact@example.com)
rate_limit_seconds: 1.0
selectors:
  # CSS selectors; update to your site structure
  catalog_series_links: "a.series-link"
  series_title: "h1.series-title"
  series_chapter_links: "ul.chapters a"
  chapter_page_images: "div.reader img"
```

## Legal & ethical

- Obey robots.txt and site terms
- Throttle requests; avoid heavy crawling
- Only download content you’re authorized to obtain
- This tool won’t provide or include any protection bypass

## Notes

- If a site serves content dynamically, enable browser fetching: `--use-browser`
- Images are saved under `downloads/<site_id>/<series_slug>/<chapter_number>/`
- CBZ export: `export-cbz --site-id <id> --series-slug <slug>`
