from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from .db import init_db, get_session
from .models import Series, Chapter, Page
from .tasks import task_index_series, task_fetch_chapters, task_fetch_images

app = FastAPI(title="Japscan.si Scraper (Compliant)")

init_db()

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def admin_index(request: Request):
    with get_session() as session:
        series_list = session.exec(select(Series).order_by(Series.created_at.desc()).limit(50)).all()
        chapters_list = session.exec(select(Chapter).order_by(Chapter.created_at.desc()).limit(50)).all()
        pages_list = session.exec(select(Page).order_by(Page.created_at.desc()).limit(50)).all()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "series": series_list,
            "chapters": chapters_list,
            "pages": pages_list,
        },
    )


@app.post("/scrape/series-index")
async def scrape_series_index(background_tasks: BackgroundTasks):
    background_tasks.add_task(task_index_series)
    return {"enqueued": True}


@app.post("/scrape/series")
async def scrape_series(series_url: str = Form(...), background_tasks: BackgroundTasks = None):
    background_tasks.add_task(task_fetch_chapters, series_url)
    return {"enqueued": True, "series_url": series_url}


@app.post("/scrape/chapter")
async def scrape_chapter(chapter_url: str = Form(...), background_tasks: BackgroundTasks = None):
    background_tasks.add_task(task_fetch_images, chapter_url)
    return {"enqueued": True, "chapter_url": chapter_url}


@app.get("/series")
async def list_series():
    with get_session() as session:
        rows = session.exec(select(Series).order_by(Series.title)).all()
    return rows


@app.get("/chapters")
async def list_chapters(series_id: int):
    with get_session() as session:
        rows = session.exec(select(Chapter).where(Chapter.series_id == series_id).order_by(Chapter.number)).all()
    return rows


@app.get("/pages")
async def list_pages(chapter_id: int):
    with get_session() as session:
        rows = session.exec(select(Page).where(Page.chapter_id == chapter_id).order_by(Page.index)).all()
    return rows