"""Единая точка доступа к SQLite `app.db` и сервисам поверх неё."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import settings
from app.services.auth_service import AuthService
from app.services.project_service import ProjectService

APP_DB_PATH: Path = settings.data_dir / 'app.db'
PROJECTS_DATA_DIR: Path = settings.data_dir / 'projects'

auth_service = AuthService(APP_DB_PATH)
project_service = ProjectService(APP_DB_PATH, PROJECTS_DATA_DIR)


def init_database() -> None:
    """Создаёт файл БД и таблицы (идемпотентно)."""
    from app.db.models import Base
    from app.db.session import engine

    Base.metadata.create_all(bind=engine)
    auth_service.init_db()
    project_service.init_db()


__all__ = [
    'APP_DB_PATH',
    'PROJECTS_DATA_DIR',
    'auth_service',
    'init_database',
    'project_service',
]

init_database()
