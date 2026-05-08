from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import auth_service, project_service
from app.services.project_service import ProjectRecord

router = APIRouter(prefix='/api/projects', tags=['api-projects'])


class CreateProjectPayload(BaseModel):
    name: str = 'Новый проект'


class DeleteRefPayload(BaseModel):
    path: str = ''


def _require_user_id(request: Request) -> int:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Требуется авторизация.')
    return int(user_id)


def _project_payload(project: ProjectRecord) -> dict:
    return {
        'id': project.id,
        'slug': project.slug,
        'name': project.name,
        'brand_id': project.brand_id,
        'created_at': project.created_at,
        'updated_at': project.updated_at,
        'results_url': f'/app/projects/{project.slug}/results',
        'editor_url': f'/app/projects/{project.slug}',
    }


def _project_or_404(user_id: int, project_slug: str) -> ProjectRecord:
    project = project_service.get_project(user_id, project_slug)
    if project is None:
        raise HTTPException(status_code=404, detail='Проект не найден.')
    return project


def _show_generation_history(user_id: int, projects: list[ProjectRecord]) -> bool:
    user_row = auth_service.get_user_by_id(user_id)
    had_projects = bool(int(user_row['had_projects'])) if user_row and 'had_projects' in user_row.keys() else False
    return had_projects or bool(projects)


@router.get('')
def list_projects(request: Request) -> JSONResponse:
    user_id = _require_user_id(request)
    projects = project_service.list_projects(user_id)

    return JSONResponse(
        {
            'ok': True,
            'projects': [_project_payload(project) for project in projects],
            'show_generation_history': _show_generation_history(user_id, projects),
        }
    )


@router.post('')
def create_project(request: Request, payload: CreateProjectPayload) -> JSONResponse:
    user_id = _require_user_id(request)
    project = project_service.create_project(user_id, payload.name)

    return JSONResponse(
        {
            'ok': True,
            'project': _project_payload(project),
            'redirect_url': f'/app/projects/{project.slug}?new=1',
        }
    )


@router.post('/{project_slug}/delete')
def delete_project(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    if not project_service.delete_project(user_id, project_slug):
        raise HTTPException(status_code=404, detail='Проект не найден.')
    return JSONResponse({'ok': True})


@router.post('/{project_slug}/restore')
def restore_project(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    if not project_service.restore_project(user_id, project_slug):
        raise HTTPException(status_code=404, detail='Проект не найден или уже активен.')
    return JSONResponse({'ok': True})


@router.get('/{project_slug}/editor')
def get_project_editor(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    project = _project_or_404(user_id, project_slug)
    tokens = project_service.load_tokens(user_id, project_slug)
    refs = tokens.get('references', {}).get('style_images', [])

    return JSONResponse(
        {
            'ok': True,
            'project': _project_payload(project),
            'tokens': tokens,
            'refs': refs if isinstance(refs, list) else [],
            'is_new_project_flow': request.query_params.get('new') == '1',
        }
    )


@router.post('/{project_slug}/editor/save')
async def save_project_editor(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    _project_or_404(user_id, project_slug)
    data = await request.json()
    try:
        saved = project_service.save_tokens(user_id, project_slug, data)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'tokens': saved})


@router.post('/{project_slug}/editor/reset')
def reset_project_editor(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    _project_or_404(user_id, project_slug)
    try:
        tokens = project_service.reset_tokens(user_id, project_slug)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'tokens': tokens})


@router.get('/{project_slug}/editor/refs')
def list_project_editor_refs(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    _project_or_404(user_id, project_slug)
    tokens = project_service.load_tokens(user_id, project_slug)
    refs = tokens.get('references', {}).get('style_images', [])
    return JSONResponse({'ok': True, 'images': refs if isinstance(refs, list) else []})


@router.post('/{project_slug}/editor/refs')
async def upload_project_editor_refs(request: Request, project_slug: str, files: list[UploadFile] = File(...)) -> JSONResponse:
    user_id = _require_user_id(request)
    _project_or_404(user_id, project_slug)
    if not files:
        return JSONResponse({'ok': False, 'error': 'Файлы не переданы.'}, status_code=400)

    payload = []
    for file in files:
        payload.append((file.filename or '', await file.read()))

    try:
        images = project_service.upload_refs(user_id, project_slug, payload)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'images': images})


@router.post('/{project_slug}/editor/refs/delete')
def delete_project_editor_ref(request: Request, project_slug: str, payload: DeleteRefPayload) -> JSONResponse:
    user_id = _require_user_id(request)
    _project_or_404(user_id, project_slug)
    try:
        images = project_service.delete_ref(user_id, project_slug, payload.path)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'images': images})
