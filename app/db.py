from contextlib import contextmanager
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

from .config import settings

DB_PATH = Path(settings.data_dir) / "app.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    from . import models  # noqa: F401 ensure models are imported
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Session:
    with Session(engine) as session:
        yield session