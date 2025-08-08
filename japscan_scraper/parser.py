from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import Series, Chapter, Page, ChapterPages, SeriesWithChapters
from .config import SERIES_PATH_PREFIXES, READER_PATH_PREFIXES


HREF_SERIES_RE = re.compile(r"^/(manga|mangas|serie)/([a-z0-9-_.]+)/?$")
HREF_CHAPTER_RE = re.compile(r"^/(lecture-en-ligne|lecture|lire)/([a-z0-9-_.]+)/([^/]+)/?$")
HREF_PAGE_RE = re.compile(r"^/(lecture-en-ligne|lecture|lire)/([a-z0-9-_.]+)/([^/]+)/([0-9]+)(?:\.(?:html|x?htm))?$")


def _text(el) -> str:
    return (el.get_text(" ", strip=True) if el else "").strip()


def _path(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return urlparse(href).path or ""
    return href


def parse_catalog(html: str, base_url: str) -> List[Series]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Series] = []
    for a in soup.select("a"):
        href_raw = a.get("href") or ""
        href = _path(href_raw)
        m = HREF_SERIES_RE.match(href)
        if not m:
            continue
        slug = m.group(2)
        title = _text(a)
        if not title:
            title = a.get("title") or slug.replace("-", " ")
        url = f"{base_url}{m.group(0)}"
        items.append(Series(slug=slug, title=title, url=url))
    # de-dup while keeping first title
    seen = {}
    result: List[Series] = []
    for s in items:
        if s.slug in seen:
            continue
        seen[s.slug] = True
        result.append(s)

    if not result:
        # Fallback: scan for known blocks with /manga/ links
        series_paths = set()
        for a in soup.find_all("a", href=True):
            href = _path(a["href"])
            if href.startswith("/manga/"):
                m = re.match(r"^/manga/([a-z0-9-_.]+)/?$", href)
                if m:
                    series_paths.add(m.group(0))
        result = [Series(slug=p.split("/")[2], title=p.split("/")[2].replace("-", " "), url=f"{base_url}{p}") for p in sorted(series_paths)]

    return result


def parse_series(html: str, base_url: str, series_slug: str) -> SeriesWithChapters:
    soup = BeautifulSoup(html, "html.parser")
    # Series title
    title_el = soup.select_one("h1, h2, .series-title, .manga-title")
    title = _text(title_el) or series_slug.replace("-", " ")

    # Description
    desc_el = soup.select_one(".summary, .description, .manga-description, .synopsis")
    description = _text(desc_el) or None

    # Alt titles
    alt_titles: List[str] = []
    for label in soup.select(".alt-names, .alternative, .alt-title"):
        t = _text(label)
        if t:
            alt_titles.extend([p.strip() for p in re.split(r"[,;]| / ", t) if p.strip()])

    # Authors
    authors: List[str] = []
    for lab in soup.find_all(string=re.compile(r"(Auteur|Author)s?\s*:?", flags=re.I)):
        parent = lab.parent
        if parent:
            authors_text = _text(parent)
            parts = re.split(r"[,;/]", authors_text)
            for p in parts:
                pt = p.strip()
                if pt and not re.search(r"Auteur|Author", pt, flags=re.I):
                    authors.append(pt)

    # Genres
    genres: List[str] = []
    for g in soup.select(".genres a, .genre a, a.genre"):
        gt = _text(g)
        if gt:
            genres.append(gt)

    # Status
    status: Optional[str] = None
    for lab in soup.find_all(string=re.compile(r"Statu[st]\s*:?", flags=re.I)):
        val = _text(lab.parent)
        status = re.sub(r"(?i)Statu[st]\s*:?\s*", "", val).strip()
        if status:
            break

    series = Series(
        slug=series_slug,
        title=title,
        url=f"{base_url}/manga/{series_slug}",
        alt_titles=alt_titles,
        status=status,
        authors=list(dict.fromkeys(authors)),
        genres=list(dict.fromkeys(genres)),
        description=description,
    )

    chapters: List[Chapter] = []
    for a in soup.select("a"):
        href_raw = a.get("href") or ""
        href = _path(href_raw)
        m = HREF_CHAPTER_RE.match(href)
        if not m:
            continue
        slug = m.group(2)
        if slug != series_slug:
            continue
        chapter_key = m.group(3)
        chapter_number = chapter_key
        name = _text(a) or None
        url = f"{base_url}{m.group(0)}"
        chapters.append(
            Chapter(series_slug=series_slug, number=chapter_number, name=name, url=url)
        )

    unique = {}
    for ch in chapters:
        unique[ch.number] = ch

    def ch_sort_key(num: str):
        try:
            return float(re.sub(r"[^0-9.]+", "", num))
        except Exception:
            return num

    ordered = sorted(unique.values(), key=lambda c: ch_sort_key(c.number))

    return SeriesWithChapters(series=series, chapters=ordered)


def parse_chapter_pages(html: str, base_url: str) -> List[Page]:
    soup = BeautifulSoup(html, "html.parser")

    page_links: List[Tuple[int, str]] = []
    for a in soup.select("a"):
        href_raw = a.get("href") or ""
        href = _path(href_raw)
        m = HREF_PAGE_RE.match(href)
        if not m:
            continue
        page_str = m.group(4)
        try:
            idx = int(page_str)
        except Exception:
            continue
        page_links.append((idx, href))

    if not page_links:
        for opt in soup.select("option"):
            val_raw = opt.get("value") or ""
            val = _path(val_raw)
            m = HREF_PAGE_RE.match(val)
            if not m:
                continue
            try:
                idx = int(m.group(4))
            except Exception:
                continue
            page_links.append((idx, val))

    page_links = sorted(set(page_links), key=lambda x: x[0])

    pages: List[Page] = []
    if page_links:
        for idx, href in page_links:
            pages.append(Page(index=idx, image_url=href))
        return pages

    img = soup.select_one("#image, .img-responsive, .reader-image, .page-image, img#image, img.manga-page, figure img")
    if img:
        src = img.get("data-src") or img.get("src") or ""
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("/"):
            src = f"{base_url}{src}"
        if src:
            return [Page(index=1, image_url=src)]

    return []