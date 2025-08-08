from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class Series(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str
    slug: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    chapters: list["Chapter"] = Relationship(back_populates="series")


class Chapter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: int = Field(foreign_key="series.id")
    title: str
    url: str
    slug: str
    number: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    series: Series = Relationship(back_populates="chapters")
    pages: list["Page"] = Relationship(back_populates="chapter")


class Page(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chapter_id: int = Field(foreign_key="chapter.id")
    index: int
    url: str
    local_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    chapter: Chapter = Relationship(back_populates="pages")