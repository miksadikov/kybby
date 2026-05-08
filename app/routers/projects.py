from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.schemas.palette import PaletteSuggestRequest, PaletteSuggestResponse
from app.core.paths import OUT_DIR
from app.core.settings import settings
from app.db import project_service
from app.services.generation_service import GenerationService
from app.services.generation_jobs import generation_jobs
from app.services.palette_service import PaletteService

router = APIRouter()
generation_service = GenerationService(project_service)
palette_service = PaletteService()


def require_auth(request: Request) -> int:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return int(user_id)


def redirect_auth(request: Request):
    if not request.session.get('user_id'):
        return RedirectResponse(url='/app/login', status_code=status.HTTP_303_SEE_OTHER)
    return None


def redirect_to_react(request: Request, path: str) -> RedirectResponse:
    query = request.url.query
    url = f'/app{path}'
    if query:
        url = f'{url}?{query}'
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def project_or_404(user_id: int, project_slug: str):
    project = project_service.get_project(user_id, project_slug)
    if project is None:
        raise HTTPException(status_code=404, detail='Проект не найден.')
    return project

def _palette_items_from_tokens(tokens: dict) -> list[dict]:
    generation_cfg = tokens.get('generation') if isinstance(tokens.get('generation'), dict) else {}
    active_keys = generation_cfg.get('active_palette_keys') if isinstance(generation_cfg.get('active_palette_keys'), list) else []
    active_keys = [k for k in active_keys if isinstance(k, str)]

    palette_slots = tokens.get('palette_slots') if isinstance(tokens.get('palette_slots'), dict) else {}
    palette = tokens.get('palette') if isinstance(tokens.get('palette'), dict) else {}
    source = palette_slots or palette

    if not active_keys:
        active_keys = list(source.keys())[:6]

    labels = {
        'primary': 'Primary',
        'secondary': 'Secondary',
        'accent': 'Accent',
        'tertiary': 'Tertiary',
        'neutral': 'Neutral',
        'extra': 'Extra',
    }

    items = []
    for key in active_keys:
        value = source.get(key) or palette.get(key)
        if not value:
            continue
        items.append({'key': key, 'label': labels.get(key, key.title()), 'value': str(value).upper()})
    return items


def _scan_asset_group(brand_id: str, section: str, suffixes: tuple[str, ...]) -> list[dict]:
    provider_roots = [
        ('recraft', OUT_DIR / 'recraft' / brand_id / section),
        ('seedream', OUT_DIR / 'seedream' / brand_id / section),
        ('flux', OUT_DIR / 'flux' / brand_id / section),
    ]
    assets = []
    for provider, root in provider_roots:
        if not root.exists():
            continue
        for file_path in sorted(root.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in suffixes:
                assets.append({
                    'provider': provider,
                    'name': file_path.stem,
                    'filename': file_path.name,
                    'url': f'/assets/{brand_id}/{provider}/{section}/{file_path.name}',
                })
    return assets

def _build_download_zip(user_id: int, project_slug: str, brand_id: str, kind: str) -> Path:
    exports_dir = project_service.exports_dir(user_id, project_slug)
    exports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = exports_dir / f'{project_slug}_{kind}.zip'

    section_map = {
        'logos': ['logos'],
        'icons': ['icons'],
        'patterns': ['patterns'],
        'illustrations': ['illustrations'],
        'all': ['logos', 'icons', 'patterns', 'illustrations'],
    }
    if kind not in section_map:
        raise HTTPException(status_code=404, detail='Неизвестный тип экспорта.')

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for provider in ('recraft', 'seedream', 'flux'):
            for section in section_map[kind]:
                section_dir = OUT_DIR / provider / brand_id / section
                if not section_dir.exists():
                    continue
                for file_path in sorted(section_dir.iterdir()):
                    if file_path.is_file():
                        zf.write(file_path, arcname=f'{provider}/{section}/{file_path.name}')

        if kind == 'all':
            meta_dir = OUT_DIR / '_meta' / brand_id
            if meta_dir.exists():
                for file_path in sorted(meta_dir.iterdir()):
                    if file_path.is_file():
                        zf.write(file_path, arcname=f'_meta/{file_path.name}')
            tokens_path = project_service.tokens_path(user_id, project_slug)
            if tokens_path.exists():
                zf.write(tokens_path, arcname='tokens.json')

    return zip_path


@router.get('/projects/{project_slug}')
async def project_editor_page(request: Request, project_slug: str) -> RedirectResponse:
    auth_redirect = redirect_auth(request)
    if auth_redirect:
        return auth_redirect
    project_or_404(int(request.session['user_id']), project_slug)
    return redirect_to_react(request, f'/projects/{project_slug}')


@router.post('/projects/{project_slug}/save')
async def save_project(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    data = await request.json()
    try:
        saved = project_service.save_tokens(user_id, project_slug, data)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'tokens': saved})


@router.post('/projects/{project_slug}/palette/suggest')
async def suggest_palette(
    request: Request,
    project_slug: str,
    payload: PaletteSuggestRequest,
) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    try:
        seed_color = palette_service.normalize_hex(payload.seed_color)
        variants = palette_service.suggest_variants(seed_color)
    except ValueError as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)

    response = PaletteSuggestResponse(
        seed_color=seed_color,
        seed_role=payload.seed_role,
        variants=variants,
    )
    return JSONResponse(response.model_dump())


@router.get('/projects/{project_slug}/download')
async def download_project(request: Request, project_slug: str):
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    path = project_service.tokens_path(user_id, project_slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail='tokens.json не найден.')
    return FileResponse(path, filename='tokens.json', media_type='application/json')


@router.post('/projects/{project_slug}/reset')
async def reset_project(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    try:
        tokens = project_service.reset_tokens(user_id, project_slug)
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'tokens': tokens})


@router.post('/projects/{project_slug}/upload-refs')
async def upload_refs(request: Request, project_slug: str, files: list[UploadFile] = File(...)) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
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


@router.get('/projects/{project_slug}/list-refs')
async def list_refs(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    tokens = project_service.load_tokens(user_id, project_slug)
    return JSONResponse({'ok': True, 'images': tokens.get('references', {}).get('style_images', [])})


@router.post('/projects/{project_slug}/delete-ref')
async def delete_ref(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    data = await request.json()
    try:
        images = project_service.delete_ref(user_id, project_slug, str(data.get('path', '')))
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
    return JSONResponse({'ok': True, 'images': images})


@router.get('/projects/{project_slug}/refs/{filename}')
async def serve_ref(request: Request, project_slug: str, filename: str):
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    path = project_service.uploads_dir(user_id, project_slug) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail='Файл не найден.')
    return FileResponse(path)


@router.post('/projects/{project_slug}/generate-figma')
async def generate_figma(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)

    try:
        data = await request.json()
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    tokens = project_service.load_tokens(user_id, project_slug)
    brand_id = (data.get('brand_id') or tokens.get('brand_id') or '').strip()
    if not brand_id:
        return JSONResponse({'ok': False, 'error': 'Укажите brand_id.'}, status_code=400)

    base_host = str(request.base_url).rstrip('/').replace('127.0.0.1', 'localhost')
    try:
        manifest, counts, export_path = generation_service.build_and_save_figma_manifest(
            user_id,
            project_slug,
            brand_id,
            base_host,
        )
        try:
            export_rel = str(export_path.relative_to(project_service.project_dir(user_id, project_slug)))
        except ValueError:
            export_rel = export_path.name
        project_service.record_figma_asset_manifest(
            user_id,
            project_slug,
            manifest=manifest,
            export_rel_path=export_rel,
            job_id=None,
        )
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)

    return JSONResponse({
        'ok': True,
        'brand_id': brand_id,
        'counts': counts,
        'manifest_url': f'/assets/{brand_id}/figma_plugin_manifest.json',
        'download_url': f'/projects/{project_slug}/exports/{export_path.name}',
        'production_url': f'https://brand.kit/assets/{brand_id}/logos|icons|patterns|illustrations',
        'local_url': f'{base_host}/assets/{brand_id}/...',
    })


@router.get('/projects/{project_slug}/exports/{filename}')
async def download_export(request: Request, project_slug: str, filename: str):
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    path = project_service.exports_dir(user_id, project_slug) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail='Файл не найден.')
    return FileResponse(path, filename=filename)


@router.post('/projects/{project_slug}/generate/start')
async def start_generate_assets(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    data = await request.json()
    job = generation_jobs.create_job(user_id=user_id, project_slug=project_slug)
    project_service.record_generation_job(user_id=user_id, job_id=job['id'], project_slug=project_slug)
    generation_jobs.start_generation(
        job_id=job['id'],
        generation_service=generation_service,
        user_id=user_id,
        project_slug=project_slug,
        payload=data,
        base_host=str(request.base_url).rstrip('/'),
        project_service=project_service,
    )
    return JSONResponse({'ok': True, 'job_id': job['id']})


@router.get('/generation-jobs/{job_id}')
async def get_generation_job(request: Request, job_id: str) -> JSONResponse:
    user_id = require_auth(request)
    job = generation_jobs.get_job(job_id)
    if not job or int(job['user_id']) != user_id:
        raise HTTPException(status_code=404, detail='Задача не найдена.')
    return JSONResponse({'ok': True, 'job': job})


@router.post('/generation-jobs/{job_id}/cancel')
async def cancel_generation_job(request: Request, job_id: str) -> JSONResponse:
    user_id = require_auth(request)
    ok = generation_jobs.request_cancel(job_id, user_id)
    if not ok:
        return JSONResponse({'ok': False, 'error': 'Задача не найдена или уже завершена.'}, status_code=400)
    return JSONResponse({'ok': True})


@router.get('/projects/{project_slug}/generation/active')
async def get_active_generation_job_for_project(request: Request, project_slug: str) -> JSONResponse:
    user_id = require_auth(request)
    project_or_404(user_id, project_slug)
    job = generation_jobs.get_active_job_for_project(user_id=user_id, project_slug=project_slug)
    return JSONResponse({'ok': True, 'job': job})


@router.api_route('/assets/{brand_id}/{relpath:path}', methods=['GET', 'OPTIONS'])
async def serve_assets(brand_id: str, relpath: str):
    if relpath.startswith('recraft/'):
        base_dir = OUT_DIR / 'recraft' / brand_id
        rel = relpath[len('recraft/'):]
    elif relpath.startswith('seedream/'):
        base_dir = OUT_DIR / 'seedream' / brand_id
        rel = relpath[len('seedream/'):]
    elif relpath.startswith('flux/'):
        base_dir = OUT_DIR / 'flux' / brand_id
        rel = relpath[len('flux/'):]
    elif relpath.startswith(('logos/', 'icons/', 'patterns/', 'illustrations/')):
        base_dir = OUT_DIR / 'recraft' / brand_id
        rel = relpath
    else:
        base_dir = OUT_DIR / '_meta' / brand_id
        rel = relpath
    file_path = (base_dir / rel).resolve()
    if not str(file_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=403, detail='Forbidden')
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail='Файл не найден.')
    return FileResponse(file_path, headers=headers)

@router.get('/projects/{project_slug}/results')
async def project_results_page(request: Request, project_slug: str) -> RedirectResponse:
    auth_redirect = redirect_auth(request)
    if auth_redirect:
        return auth_redirect

    project_or_404(int(request.session['user_id']), project_slug)
    return redirect_to_react(request, f'/projects/{project_slug}/results')


@router.get('/projects/{project_slug}/downloads/{kind}')
async def download_generated_assets(request: Request, project_slug: str, kind: str):
    user_id = require_auth(request)
    project = project_or_404(user_id, project_slug)
    tokens = project_service.load_tokens(user_id, project_slug)
    brand_id = (tokens.get('brand_id') or project.brand_id or '').strip()
    if not brand_id:
        raise HTTPException(status_code=400, detail='У проекта не указан brand_id.')

    zip_path = _build_download_zip(user_id, project_slug, brand_id, kind)
    return FileResponse(zip_path, filename=zip_path.name, media_type='application/zip')
