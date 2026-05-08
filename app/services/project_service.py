from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_TOKENS = {
    "name": "Demo Brand",
    "brand_id": "demo-brand",
    "palette": {
        "primary": "#5B7C99",
        "secondary": "#E3E7ED",
        "accent": "#1E2A33",
    },
    "icon": {
        "strokeWidth": 2,
        "corner": "rounded",
        "fill": "outline",
    },
    "texture": {
        "motifs": [],
        "density": "low",
        "substyle": "seamless",
    },
    "illustration": {
        "vector": True,
        "raster": True,
        "prompt_suffix": "minimal, soft contrast",
    },
    "prompts": {
        "logos": [],
        "icons": [],
        "patterns": [],
        "illustrations": [],
    },
    "references": {
        "style_images": [],
    },
    "style_id": "",
}

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

logger = logging.getLogger('kityourbrand.project')


@dataclass(slots=True)
class ProjectRecord:
    id: int
    user_id: int
    slug: str
    name: str
    brand_id: str
    created_at: str
    updated_at: str


class ProjectService:
    def __init__(self, db_path: Path, storage_dir: Path) -> None:
        self.db_path = db_path
        self.storage_dir = storage_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
        return {str(r[1]) for r in rows}

    def init_db(self) -> None:
        with self._connect() as conn:
            cols = self._table_columns(conn, 'projects')
            if cols and 'deleted_at' not in cols:
                conn.execute('ALTER TABLE projects ADD COLUMN deleted_at TEXT')
            hist_cols = self._table_columns(conn, 'generation_jobs_history')
            if hist_cols:
                if 'error_message' not in hist_cols:
                    conn.execute('ALTER TABLE generation_jobs_history ADD COLUMN error_message TEXT')
                if 'error_hint' not in hist_cols:
                    conn.execute('ALTER TABLE generation_jobs_history ADD COLUMN error_hint TEXT')
            conn.commit()

    def _slugify(self, value: str) -> str:
        value = (value or '').strip().lower()
        value = re.sub(r'[^a-z0-9]+', '-', value)
        value = re.sub(r'-{2,}', '-', value).strip('-')
        return value or 'brand'

    def user_projects_dir(self, user_id: int) -> Path:
        path = self.storage_dir / str(user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def project_dir(self, user_id: int, slug: str) -> Path:
        path = self.user_projects_dir(user_id) / slug
        path.mkdir(parents=True, exist_ok=True)
        return path

    def tokens_path(self, user_id: int, slug: str) -> Path:
        return self.project_dir(user_id, slug) / 'tokens.json'

    def backup_path(self, user_id: int, slug: str) -> Path:
        return self.project_dir(user_id, slug) / 'tokens.original.json'

    def uploads_dir(self, user_id: int, slug: str) -> Path:
        path = self.project_dir(user_id, slug) / 'uploads' / 'refs'
        path.mkdir(parents=True, exist_ok=True)
        return path

    def exports_dir(self, user_id: int, slug: str) -> Path:
        path = self.project_dir(user_id, slug) / 'exports'
        path.mkdir(parents=True, exist_ok=True)
        return path

    def make_default_tokens(self, project_name: str) -> dict:
        data = json.loads(json.dumps(DEFAULT_TOKENS))
        safe_name = project_name.strip() or 'Новый проект'
        data['name'] = safe_name
        data['brand_id'] = self._slugify(safe_name)
        return data

    def create_project(self, user_id: int, name: str) -> ProjectRecord:
        project_name = (name or '').strip() or 'Новый проект'
        base_slug = self._slugify(project_name)
        slug = f'{base_slug}-{uuid.uuid4().hex[:6]}'
        now = datetime.now(timezone.utc).isoformat()
        tokens = self.make_default_tokens(project_name)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects (user_id, slug, name, brand_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, slug, project_name, tokens['brand_id'], now, now),
            )
            conn.execute(
                "UPDATE users SET had_projects = 1 WHERE id = ?",
                (user_id,),
            )
            project_id = int(cur.lastrowid)
            conn.commit()

        self.save_tokens(user_id, slug, tokens)
        shutil.copyfile(self.tokens_path(user_id, slug), self.backup_path(user_id, slug))
        return ProjectRecord(project_id, user_id, slug, project_name, tokens['brand_id'], now, now)

    def list_projects(self, user_id: int) -> list[ProjectRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, slug, name, brand_id, created_at, updated_at
                FROM projects
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [ProjectRecord(**dict(row)) for row in rows]

    def get_project(self, user_id: int, slug: str) -> Optional[ProjectRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, slug, name, brand_id, created_at, updated_at
                FROM projects
                WHERE user_id = ? AND slug = ? AND deleted_at IS NULL
                LIMIT 1
                """,
                (user_id, slug),
            ).fetchone()
        if row is None:
            return None
        return ProjectRecord(**dict(row))

    def delete_project(self, user_id: int, slug: str) -> bool:
        project = self.get_project(user_id, slug)
        if project is None:
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                'UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?',
                (now, now, project.id),
            )
            conn.commit()
        return True

    def restore_project(self, user_id: int, slug: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM projects
                WHERE user_id = ? AND slug = ? AND deleted_at IS NOT NULL
                LIMIT 1
                """,
                (user_id, slug),
            ).fetchone()
            if row is None:
                return False
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                'UPDATE projects SET deleted_at = NULL, updated_at = ? WHERE id = ?',
                (now, int(row['id'])),
            )
            conn.commit()
        self.ensure_project(user_id, slug)
        return True

    def record_generation_job(self, *, user_id: int, job_id: str, project_slug: str) -> None:
        project = self.get_project(user_id, project_slug)
        if project is None:
            return
        started = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO generation_jobs_history (
                    user_id, job_id, project_id, project_slug, project_name, status, started_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (user_id, job_id, project.id, project_slug, project.name, started),
            )
            conn.commit()

    def set_generation_job_running(self, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE generation_jobs_history SET status = 'running' WHERE job_id = ?",
                (job_id,),
            )
            conn.commit()

    def finalize_generation_job_record(
        self,
        job_id: str,
        outcome: str,
        *,
        error_message: str | None = None,
        error_hint: str | None = None,
    ) -> None:
        """outcome: success | failed"""
        status = 'success' if outcome == 'success' else 'failed'
        finished = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                'SELECT started_at FROM generation_jobs_history WHERE job_id = ?',
                (job_id,),
            ).fetchone()
            if row is None:
                return
            started_raw = str(row['started_at'])
            duration: float | None = None
            try:
                s = started_raw.replace('Z', '+00:00')
                t0 = datetime.fromisoformat(s)
                t1 = datetime.fromisoformat(finished.replace('Z', '+00:00'))
                duration = max(0.0, (t1 - t0).total_seconds())
            except (TypeError, ValueError):
                duration = None
            conn.execute(
                """
                UPDATE generation_jobs_history
                SET status = ?, finished_at = ?, duration_seconds = ?, error_message = ?, error_hint = ?
                WHERE job_id = ?
                """,
                (status, finished, duration, error_message, error_hint, job_id),
            )
            conn.commit()

    def mark_abandoned_generation_jobs(self) -> None:
        """After restart in-memory jobs are lost; pending/running rows become failed."""
        finished = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE generation_jobs_history
                SET status = 'failed', finished_at = ?, duration_seconds = NULL
                WHERE status IN ('pending', 'running')
                """,
                (finished,),
            )
            conn.commit()

    def generation_history_stats(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute(
                'SELECT COUNT(*) AS c FROM generation_jobs_history WHERE user_id = ?',
                (user_id,),
            ).fetchone()
            ok = conn.execute(
                "SELECT COUNT(*) AS c FROM generation_jobs_history WHERE user_id = ? AND status = 'success'",
                (user_id,),
            ).fetchone()
            avg = conn.execute(
                """
                SELECT AVG(duration_seconds) AS a
                FROM generation_jobs_history
                WHERE user_id = ? AND status = 'success' AND duration_seconds IS NOT NULL
                """,
                (user_id,),
            ).fetchone()
            projects_n = conn.execute(
                """
                SELECT COUNT(DISTINCT project_id) AS c
                FROM generation_jobs_history
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return {
            'total': int(total['c']) if total else 0,
            'successful': int(ok['c']) if ok else 0,
            'avg_duration': float(avg['a']) if avg and avg['a'] is not None else None,
            'projects_with_generations': int(projects_n['c']) if projects_n else 0,
        }

    def list_generation_history_page(
        self, user_id: int, *, page: int = 1, per_page: int = 10
    ) -> tuple[list[dict[str, Any]], int]:
        page = max(1, page)
        per_page = max(1, min(per_page, 50))
        offset = (page - 1) * per_page
        with self._connect() as conn:
            total_row = conn.execute(
                'SELECT COUNT(*) AS c FROM generation_jobs_history WHERE user_id = ?',
                (user_id,),
            ).fetchone()
            total = int(total_row['c']) if total_row else 0
            rows = conn.execute(
                """
                SELECT
                    h.job_id,
                    h.project_slug,
                    h.project_name,
                    h.status AS db_status,
                    h.started_at,
                    h.finished_at,
                    h.duration_seconds,
                    h.error_message,
                    h.error_hint,
                    CASE
                        WHEN p.id IS NULL THEN 1
                        WHEN p.deleted_at IS NOT NULL THEN 1
                        ELSE 0
                    END AS project_deleted
                FROM generation_jobs_history h
                LEFT JOIN projects p ON p.id = h.project_id
                WHERE h.user_id = ?
                ORDER BY datetime(h.started_at) DESC, h.id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, per_page, offset),
            ).fetchall()
        return [dict(row) for row in rows], total

    def delete_generation_history_all(self, user_id: int) -> tuple[int, int]:
        """Delete all terminal history rows for user. Returns (deleted, skipped_active)."""
        with self._connect() as conn:
            total_row = conn.execute(
                'SELECT COUNT(*) AS c FROM generation_jobs_history WHERE user_id = ?',
                (user_id,),
            ).fetchone()
            total = int(total_row['c']) if total_row else 0
            cur = conn.execute(
                """
                DELETE FROM generation_jobs_history
                WHERE user_id = ? AND status NOT IN ('pending', 'running')
                """,
                (user_id,),
            )
            deleted = int(cur.rowcount or 0)
            conn.commit()
        skipped = max(0, total - deleted)
        return deleted, skipped

    def delete_generation_history_selected(self, user_id: int, job_ids: list[str]) -> tuple[int, int]:
        """Delete selected terminal history rows for user. Returns (deleted, skipped_active_or_missing)."""
        normalized = [str(j).strip() for j in job_ids if str(j).strip()]
        unique_ids = list(dict.fromkeys(normalized))
        if not unique_ids:
            return 0, 0

        placeholders = ', '.join(['?'] * len(unique_ids))
        params: list[Any] = [user_id, *unique_ids]
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                DELETE FROM generation_jobs_history
                WHERE user_id = ?
                  AND job_id IN ({placeholders})
                  AND status NOT IN ('pending', 'running')
                """,
                params,
            )
            deleted = int(cur.rowcount or 0)
            conn.commit()
        skipped = max(0, len(unique_ids) - deleted)
        return deleted, skipped

    def ensure_project(self, user_id: int, slug: str) -> ProjectRecord:
        project = self.get_project(user_id, slug)
        if project is None:
            raise FileNotFoundError('Проект не найден.')
        path = self.tokens_path(user_id, slug)
        if not path.exists():
            tokens = self.normalize_tokens(self.make_default_tokens(project.name))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding='utf-8')
            backup = self.backup_path(user_id, slug)
            if not backup.exists():
                shutil.copyfile(path, backup)
        return project

    def load_tokens(self, user_id: int, slug: str) -> dict:
        self.ensure_project(user_id, slug)
        with self.tokens_path(user_id, slug).open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        return self.normalize_tokens(data)

    def normalize_tokens(self, data: dict) -> dict:
        data.setdefault('name', 'Brand')
        data['brand_id'] = (data.get('brand_id') or self._slugify(data.get('name', 'brand'))).strip()
        data.setdefault('style_id', '')
        data.setdefault('palette', {})
        data['palette'].setdefault('primary', '#5B7C99')
        data['palette'].setdefault('secondary', '#E3E7ED')
        data['palette'].setdefault('accent', '#1E2A33')
        data.setdefault('icon', {})
        data['icon'].setdefault('strokeWidth', 2)
        data['icon'].setdefault('corner', 'rounded')
        data['icon'].setdefault('fill', 'outline')
        data.setdefault('texture', {})
        data['texture'].setdefault('motifs', [])
        data['texture'].setdefault('density', 'low')
        data['texture'].setdefault('substyle', 'seamless')
        data.setdefault('illustration', {})
        data['illustration'].setdefault('vector', False)
        data['illustration'].setdefault('raster', True)
        data['illustration'].setdefault('prompt_suffix', '')
        data.setdefault('prompts', {})
        data['prompts'].setdefault('logos', [])
        data['prompts'].setdefault('icons', [])
        data['prompts'].setdefault('patterns', [])
        data['prompts'].setdefault('illustrations', [])
        data.setdefault('references', {})
        refs = data['references']
        refs.setdefault('style_images', [])
        refs['style_images'] = sorted(list(dict.fromkeys([str(x) for x in refs['style_images']])))
        return data

    def insert_style_profile_version(
        self,
        user_id: int,
        slug: str,
        tokens: dict[str, Any],
        *,
        snapshot_path: str | None = None,
    ) -> None:
        """Сохраняет снимок tokens.json в style_profiles (версия ++)."""
        try:
            project = self.get_project(user_id, slug)
            if project is None:
                return
            now = datetime.now(timezone.utc).isoformat()
            payload_txt = json.dumps(tokens, ensure_ascii=False)
            with self._connect() as conn:
                row = conn.execute(
                    'SELECT COALESCE(MAX(version), 0) AS v FROM style_profiles WHERE project_id = ?',
                    (project.id,),
                ).fetchone()
                ver = int(row['v'] if row else 0) + 1
                conn.execute(
                    """
                    INSERT INTO style_profiles (project_id, user_id, version, payload, snapshot_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (project.id, user_id, ver, payload_txt, snapshot_path, now),
                )
                conn.commit()
        except Exception as exc:
            logger.warning('style_profiles insert skipped: %s', exc)

    def record_generated_assets_for_brand(
        self,
        user_id: int,
        project_slug: str,
        brand_id: str,
        out_root: Path,
        *,
        job_id: str | None = None,
    ) -> int:
        """Индексирует файлы в out/<provider>/<brand_id>/... в таблицу assets."""
        try:
            project = self.get_project(user_id, project_slug)
            if not project or not brand_id:
                return 0
            now = datetime.now(timezone.utc).isoformat()
            scan_ext = {'.png', '.svg', '.jpg', '.jpeg', '.webp'}
            rows: list[tuple[Any, ...]] = []
            for provider in ('recraft', 'seedream', 'flux'):
                base = out_root / provider / brand_id
                for kind in ('logos', 'icons', 'patterns', 'illustrations'):
                    d = base / kind
                    if not d.is_dir():
                        continue
                    for fp in sorted(d.iterdir()):
                        if not fp.is_file() or fp.suffix.lower() not in scan_ext:
                            continue
                        storage = f'out/{provider}/{brand_id}/{kind}/{fp.name}'
                        meta_txt = json.dumps({'brand_id': brand_id, 'relative': storage}, ensure_ascii=False)
                        rows.append(
                            (project.id, user_id, kind, provider, storage, fp.name, meta_txt, job_id, now)
                        )
            if not rows:
                return 0
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO assets (
                        project_id, user_id, kind, provider, storage_path, filename, meta, generation_job_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
            return len(rows)
        except Exception as exc:
            logger.warning('assets batch insert skipped: %s', exc)
            return 0

    def record_figma_asset_manifest(
        self,
        user_id: int,
        project_slug: str,
        *,
        manifest: dict[str, Any],
        export_rel_path: str,
        job_id: str | None = None,
    ) -> None:
        try:
            project = self.get_project(user_id, project_slug)
            if not project:
                return
            now = datetime.now(timezone.utc).isoformat()
            payload_txt = json.dumps(manifest, ensure_ascii=False)
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO asset_manifests (
                        project_id, user_id, kind, payload, storage_path, generation_job_id, created_at
                    ) VALUES (?, ?, 'figma_plugin', ?, ?, ?, ?)
                    """,
                    (project.id, user_id, payload_txt, export_rel_path, job_id, now),
                )
                conn.commit()
        except Exception as exc:
            logger.warning('asset_manifests insert skipped: %s', exc)

    def record_error_log(
        self,
        *,
        user_id: int | None = None,
        project_slug: str | None = None,
        job_id: str | None = None,
        source: str,
        code: str | None = None,
        message: str,
        detail: dict[str, Any] | list | None = None,
    ) -> None:
        try:
            now = datetime.now(timezone.utc).isoformat()
            project_id: int | None = None
            if user_id is not None and project_slug:
                p = self.get_project(int(user_id), str(project_slug))
                if p:
                    project_id = p.id
            detail_txt = json.dumps(detail, ensure_ascii=False) if detail is not None else None
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO error_logs (
                        user_id, project_id, generation_job_id, source, code, message, detail, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, project_id, job_id, source, code, message, detail_txt, now),
                )
                conn.commit()
        except Exception as exc:
            logger.warning('error_logs insert skipped: %s', exc)

    def save_tokens(self, user_id: int, slug: str, data: dict) -> dict:
        project = self.ensure_project(user_id, slug)
        normalized = self.normalize_tokens(data)
        path = self.tokens_path(user_id, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                'UPDATE projects SET name = ?, brand_id = ?, updated_at = ? WHERE id = ?',
                (normalized['name'], normalized['brand_id'], now, project.id),
            )
            conn.commit()
        self.insert_style_profile_version(user_id, slug, normalized, snapshot_path='tokens.json')
        return normalized

    def reset_tokens(self, user_id: int, slug: str) -> dict:
        self.ensure_project(user_id, slug)
        backup = self.backup_path(user_id, slug)
        if not backup.exists():
            raise FileNotFoundError('Резервная копия проекта не найдена.')
        shutil.copyfile(backup, self.tokens_path(user_id, slug))
        return self.load_tokens(user_id, slug)

    def upload_refs(self, user_id: int, slug: str, files: list[tuple[str, bytes]]) -> list[str]:
        tokens = self.load_tokens(user_id, slug)
        uploads = self.uploads_dir(user_id, slug)
        added: list[str] = []
        for filename, content in files:
            ext = Path(filename or '').suffix.lower()
            if ext not in ALLOWED_EXT:
                raise ValueError(f'Недопустимый тип файла: {ext}')
            safe_name = f'{uuid.uuid4().hex}{ext}'
            dest = uploads / safe_name
            dest.write_bytes(content)
            rel = f'uploads/refs/{safe_name}'
            added.append(rel)
        tokens.setdefault('references', {}).setdefault('style_images', [])
        tokens['references']['style_images'].extend(added)
        self.save_tokens(user_id, slug, tokens)
        return sorted(list(dict.fromkeys(tokens['references']['style_images'])))

    def delete_ref(self, user_id: int, slug: str, rel_path: str) -> list[str]:
        tokens = self.load_tokens(user_id, slug)
        if not rel_path.startswith('uploads/refs/'):
            raise ValueError('Некорректный путь референса.')
        file_path = self.project_dir(user_id, slug) / rel_path
        if file_path.exists():
            file_path.unlink()
        images = [item for item in tokens.get('references', {}).get('style_images', []) if item != rel_path]
        tokens.setdefault('references', {})['style_images'] = images
        self.save_tokens(user_id, slug, tokens)
        return images
