from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.paths import OUT_DIR
from app.db import project_service
from app.services.generation_jobs import generation_jobs

router = APIRouter(prefix='/api/projects', tags=['api-results'])


def _require_user_id(request: Request) -> int:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Требуется авторизация.')
    return int(user_id)


def _palette_items_from_tokens(tokens: dict) -> list[dict]:
    generation_cfg = tokens.get('generation') if isinstance(tokens.get('generation'), dict) else {}
    active_keys = generation_cfg.get('active_palette_keys') if isinstance(generation_cfg.get('active_palette_keys'), list) else []
    active_keys = [key for key in active_keys if isinstance(key, str)]

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
                assets.append(
                    {
                        'provider': provider,
                        'name': file_path.stem,
                        'filename': file_path.name,
                        'url': f'/assets/{brand_id}/{provider}/{section}/{file_path.name}',
                    }
                )
    return assets


@router.get('/{project_slug}/results')
def get_project_results(request: Request, project_slug: str) -> JSONResponse:
    user_id = _require_user_id(request)
    project = project_service.get_project(user_id, project_slug)
    if project is None:
        raise HTTPException(status_code=404, detail='Проект не найден.')

    tokens = project_service.load_tokens(user_id, project_slug)
    brand_id = (tokens.get('brand_id') or project.brand_id or '').strip()
    if not brand_id:
        return JSONResponse({'ok': False, 'error': 'У проекта не указан brand_id.'}, status_code=400)

    active_job = generation_jobs.get_active_job_for_project(user_id=user_id, project_slug=project_slug)

    return JSONResponse(
        {
            'ok': True,
            'project': {
                'slug': project.slug,
                'name': project.name,
                'brand_id': brand_id,
            },
            'palette_items': _palette_items_from_tokens(tokens),
            'assets': {
                'logos': _scan_asset_group(brand_id, 'logos', ('.png', '.svg', '.jpg', '.jpeg')),
                'icons': _scan_asset_group(brand_id, 'icons', ('.png', '.svg', '.jpg', '.jpeg')),
                'patterns': _scan_asset_group(brand_id, 'patterns', ('.png', '.svg', '.jpg', '.jpeg')),
                'illustrations': _scan_asset_group(brand_id, 'illustrations', ('.png', '.svg', '.jpg', '.jpeg')),
            },
            'active_generation_job_id': (active_job or {}).get('id') if active_job else '',
        }
    )
