"""SQLAlchemy engine для SQLite (`data/app.db`)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings


def _sqlite_url(path: Path) -> str:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f'sqlite:///{path.as_posix()}'


engine = create_engine(
    _sqlite_url(settings.data_dir / 'app.db'),
    connect_args={'check_same_thread': False},
)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
