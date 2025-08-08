from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class Series(BaseModel):
    slug: str
    title: str
    url: str
    alt_titles: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class Chapter(BaseModel):
    series_slug: str
    number: str
    name: Optional[str] = None
    url: str
    date: Optional[str] = None


class Page(BaseModel):
    index: int
    image_url: str
    referer: Optional[str] = None


class ChapterPages(BaseModel):
    chapter: Chapter
    pages: List[Page]


class SeriesWithChapters(BaseModel):
    series: Series
    chapters: List[Chapter]