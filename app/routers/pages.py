from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.core.settings import settings

router = APIRouter()
PROFILE_AVATARS_DIR = settings.data_dir / 'profile_avatars'
PROFILE_AVATARS_DIR.mkdir(parents=True, exist_ok=True)


def require_auth(request: Request):
    if not request.session.get('user_id'):
        return RedirectResponse(url='/app/login', status_code=status.HTTP_303_SEE_OTHER)
    return None


def redirect_to_react(request: Request, path: str) -> RedirectResponse:
    query = request.url.query
    url = f'/app{path}'
    if query:
        url = f'{url}?{query}'
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get('/')
async def landing_page(request: Request) -> RedirectResponse:
    return redirect_to_react(request, '')


@router.get('/dashboard')
async def dashboard_page(request: Request) -> RedirectResponse:
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect

    return redirect_to_react(request, '/dashboard')


@router.get('/generation-history')
async def generation_history_page(request: Request) -> RedirectResponse:
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect

    return redirect_to_react(request, '/generation-history')


@router.get('/profile')
async def profile_page(request: Request) -> RedirectResponse:
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect

    return redirect_to_react(request, '/profile')


@router.get('/profile/avatar/{filename}')
async def profile_avatar(request: Request, filename: str):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    safe_name = Path(filename).name
    file_path = PROFILE_AVATARS_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        return RedirectResponse(url='/app/static/img/kybby-logo.png', status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(file_path)


@router.get('/login')
async def login_page(request: Request) -> RedirectResponse:
    if request.session.get('user_id'):
        return RedirectResponse(url='/app/dashboard', status_code=status.HTTP_303_SEE_OTHER)

    return redirect_to_react(request, '/login')


@router.get('/logout')
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url='/app', status_code=status.HTTP_303_SEE_OTHER)


@router.get('/register')
async def register_page(request: Request) -> RedirectResponse:
    if request.session.get('user_id'):
        return RedirectResponse(url='/app/dashboard', status_code=status.HTTP_303_SEE_OTHER)

    return redirect_to_react(request, '/register')
