"""ORM-модели схемы SQLite: пользователи, проекты, история генераций, стиль, ассеты, манифесты, лог ошибок."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    avatar_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # DEFAULT в DDL — чтобы INSERT из AuthService без этих полей оставался валидным.
    had_projects: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text('0'))
    auth_provider: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'local'"))
    is_active: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text('1'))
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    brand_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(sa.Text, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class GenerationJobHistory(Base):
    __tablename__ = 'generation_jobs_history'

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    project_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    project_slug: Mapped[str] = mapped_column(sa.Text, nullable=False)
    project_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    started_at: Mapped[str] = mapped_column(sa.Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error_hint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class StyleProfile(Base):
    """Версии / снимки профиля стиля (tokens и т.п.). Заполнение — позже из сервисов (sqlite3)."""

    __tablename__ = 'style_profiles'
    __table_args__ = (sa.Index('ix_style_profiles_project_created', 'project_id', 'created_at'),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(sa.Integer, sa.ForeignKey('projects.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text('1'))
    payload: Mapped[dict | list | None] = mapped_column(sa.JSON, nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)


class Asset(Base):
    """Метаданные ассета; файл хранится на диске, здесь — путь и описание."""

    __tablename__ = 'assets'
    __table_args__ = (sa.Index('ix_assets_project_kind', 'project_id', 'kind'),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(sa.Integer, sa.ForeignKey('projects.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    meta: Mapped[dict | list | None] = mapped_column(sa.JSON, nullable=True)
    generation_job_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)


class AssetManifest(Base):
    """Манифесты (например Figma): JSON и/или путь к экспорту."""

    __tablename__ = 'asset_manifests'
    __table_args__ = (sa.Index('ix_asset_manifests_project_kind', 'project_id', 'kind'),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(sa.Integer, sa.ForeignKey('projects.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(sa.JSON, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    generation_job_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)


class ErrorLog(Base):
    """Журнал ошибок приложения, генерации и провайдеров."""

    __tablename__ = 'error_logs'
    __table_args__ = (sa.Index('ix_error_logs_created', 'created_at'),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    project_id: Mapped[int | None] = mapped_column(sa.Integer, sa.ForeignKey('projects.id'), nullable=True)
    generation_job_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    source: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    detail: Mapped[dict | list | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(sa.Text, nullable=False)
