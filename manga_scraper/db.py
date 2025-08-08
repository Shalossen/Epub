from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


DB_PATH = Path("data/manga.db").absolute()


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY,
                site_id TEXT NOT NULL,
                slug TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                UNIQUE(site_id, slug)
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY,
                series_id INTEGER NOT NULL,
                number TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                downloaded INTEGER NOT NULL DEFAULT 0,
                pages_count INTEGER,
                UNIQUE(series_id, number),
                FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                chapter_id INTEGER NOT NULL,
                page_index INTEGER NOT NULL,
                url TEXT,
                local_path TEXT,
                status TEXT,
                UNIQUE(chapter_id, page_index),
                FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            );
            """
        )


def upsert_series(site_id: str, slug: str, title: str, url: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO series(site_id, slug, title, url)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(site_id, slug) DO UPDATE SET title=excluded.title, url=excluded.url
            """,
            (site_id, slug, title, url),
        )
        # Fetch id
        row = conn.execute(
            "SELECT id FROM series WHERE site_id=? AND slug=?", (site_id, slug)
        ).fetchone()
        return int(row[0])


def get_series_by_slug(site_id: str, slug: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM series WHERE site_id=? AND slug=?", (site_id, slug)
        ).fetchone()


def add_or_update_chapter(series_id: int, number: str, title: str, url: str) -> int:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO chapters(series_id, number, title, url)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(series_id, number) DO UPDATE SET title=excluded.title, url=excluded.url
            """,
            (series_id, number, title, url),
        )
        row = conn.execute(
            "SELECT id FROM chapters WHERE series_id=? AND number=?", (series_id, number)
        ).fetchone()
        return int(row[0])


def mark_chapter_downloaded(chapter_id: int, pages_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE chapters SET downloaded=1, pages_count=? WHERE id=?",
            (pages_count, chapter_id),
        )


def list_missing_chapters(site_id: str, series_slug: Optional[str] = None) -> List[sqlite3.Row]:
    with get_conn() as conn:
        if series_slug:
            return conn.execute(
                """
                SELECT c.* FROM chapters c
                JOIN series s ON s.id=c.series_id
                WHERE s.site_id=? AND s.slug=? AND c.downloaded=0
                ORDER BY CAST(c.number as FLOAT), c.number
                """,
                (site_id, series_slug),
            ).fetchall()
        return conn.execute(
            """
            SELECT c.* FROM chapters c
            JOIN series s ON s.id=c.series_id
            WHERE s.site_id=? AND c.downloaded=0
            ORDER BY s.slug, CAST(c.number as FLOAT), c.number
            """,
            (site_id,),
        ).fetchall()


def upsert_page(chapter_id: int, page_index: int, url: str, local_path: Optional[str], status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pages(chapter_id, page_index, url, local_path, status)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(chapter_id, page_index) DO UPDATE SET url=excluded.url, local_path=excluded.local_path, status=excluded.status
            """,
            (chapter_id, page_index, url, local_path, status),
        )


def list_series(site_id: str) -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM series WHERE site_id=? ORDER BY slug", (site_id,)
        ).fetchall()