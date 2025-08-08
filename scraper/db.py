import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, Iterable, Tuple, List

DB_PATH = os.environ.get("JAPSCAN_DB_PATH", os.path.abspath(".data/japscan.db"))

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS series (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id INTEGER NOT NULL,
  number TEXT NOT NULL,
  title TEXT,
  url TEXT NOT NULL,
  downloaded INTEGER NOT NULL DEFAULT 0,
  UNIQUE(series_id, number),
  FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chapter_id INTEGER NOT NULL,
  idx INTEGER NOT NULL,
  image_url TEXT,
  local_path TEXT,
  status TEXT,
  UNIQUE(chapter_id, idx),
  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);
"""

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

with get_conn() as c:
    c.executescript(SCHEMA)
    c.commit()


def upsert_series(slug: str, title: str, url: str) -> int:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO series(slug, title, url) VALUES(?,?,?) ON CONFLICT(slug) DO UPDATE SET title=excluded.title, url=excluded.url",
            (slug, title, url),
        )
        c.commit()
        cur.execute("SELECT id FROM series WHERE slug=?", (slug,))
        return cur.fetchone()[0]


def get_series_by_slug(slug: str) -> Optional[Tuple[int, str, str, str]]:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, slug, title, url FROM series WHERE slug=?", (slug,))
        return cur.fetchone()


def list_all_series() -> List[Tuple[int, str, str, str]]:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, slug, title, url FROM series ORDER BY title COLLATE NOCASE")
        return cur.fetchall()


def upsert_chapter(series_id: int, number: str, title: Optional[str], url: str) -> int:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO chapters(series_id, number, title, url) VALUES(?,?,?,?) ON CONFLICT(series_id, number) DO UPDATE SET title=coalesce(excluded.title, chapters.title), url=excluded.url",
            (series_id, number, title, url),
        )
        c.commit()
        cur.execute("SELECT id FROM chapters WHERE series_id=? AND number=?", (series_id, number))
        return cur.fetchone()[0]


def mark_chapter_downloaded(chapter_id: int):
    with get_conn() as c:
        c.execute("UPDATE chapters SET downloaded=1 WHERE id=?", (chapter_id,))
        c.commit()


def get_series_chapters(series_id: int) -> List[Tuple[int, int, str, Optional[str], str, int]]:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, series_id, number, title, url, downloaded FROM chapters WHERE series_id=? ORDER BY CAST(replace(replace(number,'-','.'),'v','') AS REAL), number", (series_id,))
        return cur.fetchall()


def get_missing_chapters(series_id: int) -> List[Tuple[int, str, Optional[str], str]]:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT id, number, title, url FROM chapters WHERE series_id=? AND downloaded=0 ORDER BY number",
            (series_id,),
        )
        return cur.fetchall()


def upsert_page(chapter_id: int, idx: int, image_url: Optional[str] = None, local_path: Optional[str] = None, status: Optional[str] = None):
    with get_conn() as c:
        c.execute(
            "INSERT INTO pages(chapter_id, idx, image_url, local_path, status) VALUES(?,?,?,?,?) ON CONFLICT(chapter_id, idx) DO UPDATE SET image_url=coalesce(excluded.image_url, pages.image_url), local_path=coalesce(excluded.local_path, pages.local_path), status=coalesce(excluded.status, pages.status)",
            (chapter_id, idx, image_url, local_path, status),
        )
        c.commit()


def list_pages(chapter_id: int) -> List[Tuple[int, int, int, Optional[str], Optional[str], Optional[str]]]:
    with get_conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, chapter_id, idx, image_url, local_path, status FROM pages WHERE chapter_id=? ORDER BY idx", (chapter_id,))
        return cur.fetchall()