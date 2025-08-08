# Japscan.si Scraper & Admin Panel (Compliant)

This project provides a modular, configurable scraping and ingestion service with a small admin panel to manage queueing tasks (series, chapters, images, and bulk operations).

Important: This tool is designed to operate ethically and compliantly:
- Respects `robots.txt` and per-domain crawl delays
- Implements rate limiting and retries
- Does not attempt to bypass Cloudflare or other protections
- Encourages first-party APIs/exports for data access when possible

If you own the target site, prefer first-party integrations: create export endpoints, allowlist a service account, or adjust bot protections in your own Cloudflare dashboard rather than attempting to bypass them.

## Features
- Configurable selectors via YAML for series index, chapters, and images
- FastAPI admin panel to enqueue scraping jobs and inspect results
- SQLite persistence via SQLModel
- Pluggable scraper class (`JapscanScraper`) with generic parsing based on selectors
- Robots.txt compliance and polite rate limiting

## Quickstart
1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Open the admin panel at `http://localhost:8000/`.

## Configuration
- Base settings are in `app/config.py` (domain, user agent, concurrency, timeouts, storage paths).
- Site-specific CSS selectors live in `config/japscan_selectors.yaml`. Fill these in using your site’s markup.

Example (fill in real selectors for your site):

```yaml
base_url: "https://japscan.si"
series_index:
  start_urls:
    - "https://japscan.si/mangas/"
  series_card_selector: "div.series-card"
  series_link_selector: "a.series-link"
  next_page_selector: "a[rel=next]"
series_page:
  title_selector: "h1.series-title"
  chapters_container_selector: "ul.chapters"
  chapter_link_selector: "li a"
chapter_page:
  image_selector: "img.page-image"
  image_attr: "src"
```

If your pages are rendered client-side, consider adding a first-party JSON endpoint or server-rendered variant. Headless browsing can be added but is not included by default.

## Data Storage
- SQLite database at `data/app.db`
- Downloaded images at `data/images/<series_slug>/<chapter_slug>/<page_index>.ext`

## API Overview
- `GET /health`: health check
- `GET /series`: list series
- `GET /chapters?series_id=...`: list chapters for a series
- `GET /pages?chapter_id=...`: list pages for a chapter
- `POST /scrape/series-index`: enqueue indexing of all series
- `POST /scrape/series`: enqueue scraping chapters for a series URL
- `POST /scrape/chapter`: enqueue scraping images for a chapter URL
- `POST /scrape/bulk`: enqueue multiple series/chapter URLs

## Notes on Compliance
- This project will not and should not attempt to bypass Cloudflare or similar protections.
- If you own the site, perform owner-side actions (allowlists, API keys, or export endpoints) to grant access.

## License
MIT
