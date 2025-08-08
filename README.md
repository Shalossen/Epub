# Japscan Scraper

A robust CLI scraper for japscan.si (and mirrors) to fetch series, chapters, images, and support bulk downloads.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## CLI

```bash
python -m japscan_scraper --help
```

Examples:

- List series (catalog):
  ```bash
  python -m japscan_scraper catalog --limit 50 --json catalog.json
  ```
- Get series info and chapters:
  ```bash
  python -m japscan_scraper series "one-piece" --json one-piece.json
  ```
- List chapter pages (image URLs):
  ```bash
  python -m japscan_scraper chapter "one-piece" 846 --json one-piece-846.json
  ```
- Download a chapter:
  ```bash
  python -m japscan_scraper download "one-piece" 846 --out ./downloads/one-piece
  ```
- Bulk download entire series:
  ```bash
  python -m japscan_scraper bulk "one-piece" --out ./downloads/one-piece --workers 8
  ```

## Notes
- Respects basic rate limiting and retries. Configure with env vars or CLI flags.
- Supports multiple mirrors and attempts automatic domain failover.
- If the site changes markup, adjust selectors in `japscan_scraper/parser.py`.
