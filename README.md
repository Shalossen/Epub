# Japscan Scraper

Features:
- Detect missing chapters per series vs local DB
- Manual selection of series/chapters to download
- Headless browser (Playwright) with Cloudflare challenge handling
- Saves images to downloads/ and tracks state in SQLite

Quick start:
1. python3 -m venv .venv && source .venv/bin/activate
2. pip install -r requirements.txt
3. python -m playwright install --with-deps
4. python -m scraper.cli catalog  # list series
5. python -m scraper.cli missing --series "Solo Leveling"  # show missing
6. python -m scraper.cli download --series "Solo Leveling" --from 21 --to latest

Environment:
- JAPSCAN_BASE_URL (default: https://www.japscan.si)

Storage:
- SQLite at .data/japscan.db
- Images at downloads/<series>/<chapter>/<page>.jpg
