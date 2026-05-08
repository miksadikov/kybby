from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import project_service
from app.services.generation_jobs import generation_jobs

router = APIRouter(prefix='/api/generation-history', tags=['api-generation-history'])

GENERATION_HISTORY_PER_PAGE = 10
MSK_TZ = timezone(timedelta(hours=3))


class HistoryDeletePayload(BaseModel):
    job_ids: list[str]


def _require_user_id(request: Request) -> int:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Требуется авторизация.')
    return int(user_id)


def _format_history_datetime(iso: str | None) -> str:
    if not iso:
        return '—'
    raw = str(iso).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        s = raw.replace('T', ' ')
        if '+00:00' in s:
            s = s.replace('+00:00', '').strip()
        elif s.endswith('Z'):
            s = s[:-1].strip()
        return s[:16] if len(s) >= 16 else s

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MSK_TZ).strftime('%Y-%m-%d %H:%M')


def _format_history_duration(sec: float | None) -> str:
    if sec is None:
        return '—'
    try:
        s = float(sec)
    except (TypeError, ValueError):
        return '—'
    if s >= 60:
        minutes = int(s // 60)
        rest = s - minutes * 60
        if rest < 0.05:
            return f'{minutes} мин'
        txt = f'{minutes} мин {rest:.1f} сек'
        return txt.replace('.0 сек', ' сек')
    txt = f'{s:.1f} сек'
    return txt.replace('.0 сек', ' сек')


def _enrich_generation_history_rows(raw: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for r in raw:
        live = generation_jobs.get_job(str(r['job_id']))
        db_status = str(r['db_status'])
        project_deleted = bool(r['project_deleted'])
        in_memory_running = bool(
            live and str(live.get('status') or '') not in ('completed', 'failed')
        )
        db_inflight = db_status in ('pending', 'running')
        ui_running = db_inflight and in_memory_running
        interrupted = db_inflight and not in_memory_running

        if ui_running:
            status_key = 'running'
            action = 'cancel'
        elif db_status == 'success' and not interrupted:
            status_key = 'success'
            action = 'restore' if project_deleted else 'open'
        else:
            status_key = 'error'
            action = 'restore' if project_deleted else 'repeat'

        slug = str(r['project_slug'])
        rows.append(
            {
                'job_id': r['job_id'],
                'started_display': _format_history_datetime(r.get('started_at')),
                'project_name': r.get('project_name') or slug,
                'project_slug': slug,
                'status_key': status_key,
                'duration_display': _format_history_duration(r.get('duration_seconds')),
                'action': action,
                'results_url': f'/app/projects/{slug}/results',
                'editor_url': f'/app/projects/{slug}',
                'error_message': (r.get('error_message') or '').strip(),
                'error_hint': (r.get('error_hint') or '').strip(),
                'interrupted': interrupted,
            }
        )
    return rows


@router.get('')
def get_generation_history(request: Request, page: int = Query(1, ge=1)) -> JSONResponse:
    user_id = _require_user_id(request)
    per_page = GENERATION_HISTORY_PER_PAGE
    stats = project_service.generation_history_stats(user_id)
    total = int(stats['total'])
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    raw_rows, _ = project_service.list_generation_history_page(user_id, page=page, per_page=per_page)
    avg = stats.get('avg_duration')
    showing_from = (page - 1) * per_page + 1 if total else 0
    showing_to = min(page * per_page, total)

    return JSONResponse(
        {
            'ok': True,
            'rows': _enrich_generation_history_rows(raw_rows),
            'stats': stats,
            'stats_avg_display': _format_history_duration(float(avg)) if avg is not None else '—',
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1,
            'next_page': page + 1,
            'showing_from': showing_from,
            'showing_to': showing_to,
        }
    )


@router.post('/delete-selected')
def delete_generation_history_selected(request: Request, payload: HistoryDeletePayload) -> JSONResponse:
    user_id = _require_user_id(request)
    if len(payload.job_ids) > 500:
        return JSONResponse({'ok': False, 'error': 'Слишком много записей для удаления за один запрос.'}, status_code=400)

    deleted, skipped = project_service.delete_generation_history_selected(
        user_id,
        [str(job_id) for job_id in payload.job_ids],
    )
    return JSONResponse({'ok': True, 'deleted': deleted, 'skipped': skipped})


@router.post('/clear')
def clear_generation_history(request: Request) -> JSONResponse:
    user_id = _require_user_id(request)
    deleted, skipped = project_service.delete_generation_history_all(user_id)
    return JSONResponse({'ok': True, 'deleted': deleted, 'skipped': skipped})
