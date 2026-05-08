"""Синхронные HTTP-вызовы к провайдерам: таймауты, повторы при 429/5xx, логи без секретов."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

log = logging.getLogger('kityourbrand.provider_http')

_REDACT_HEADER_NAMES = frozenset(
    {
        'authorization',
        'proxy-authorization',
        'x-api-key',
        'api-key',
        'cookie',
        'x-auth-token',
        'x-openrouter-key',
    }
)


def _settings():
    from app.core.settings import settings

    return settings


def sanitize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in _REDACT_HEADER_NAMES or lk.endswith('-key') or 'secret' in lk:
            out[k] = '***'
        else:
            out[k] = v
    return out


def sanitize_url(url: str) -> str:
    p = urlparse(url)
    if not p.query:
        return url
    sensitive = {'key', 'token', 'secret', 'password', 'api_key', 'apikey', 'access_token'}
    q: list[tuple[str, str]] = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        if k.lower() in sensitive or k.lower().endswith('_key'):
            q.append((k, '***'))
        else:
            q.append((k, v))
    return urlunparse(p._replace(query=urlencode(q)))


def _should_retry_status(code: int) -> bool:
    if code == 429:
        return True
    return code >= 500


def _rewind_files(files: Any) -> None:
    if not files:
        return
    if isinstance(files, dict):
        iterable = files.values()
    else:
        iterable = files
    for item in iterable:
        tup = item if isinstance(item, tuple) else None
        fobj = tup[1] if tup and len(tup) > 1 else item
        if hasattr(fobj, 'seek'):
            try:
                fobj.seek(0)
            except Exception:
                pass


def request_with_retries(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: Any | None = None,
    data: Any | None = None,
    files: Any | None = None,
    content: bytes | None = None,
    timeout: float | httpx.Timeout | None = None,
    stream: bool = False,
    label: str = 'provider_http',
    max_retries: int | None = None,
    backoff_base: float | None = None,
) -> httpx.Response:
    """
    Выполняет HTTP-запрос с повторными попытками при сетевых сбоях и ответах 429 / 5xx.

    Секреты в лог не пишутся (заголовки Authorization / *-key и похожие query-параметры).
    """
    settings = _settings()
    max_r = settings.provider_http_max_retries if max_retries is None else int(max_retries)
    back = settings.provider_http_retry_backoff_base if backoff_base is None else float(backoff_base)
    if isinstance(timeout, httpx.Timeout):
        timeout_cfg = timeout
    else:
        t = float(timeout if timeout is not None else settings.provider_http_timeout_seconds)
        timeout_cfg = httpx.Timeout(t, connect=min(30.0, t), pool=30.0)

    last_exc: BaseException | None = None
    method_u = method.upper()

    safe_url = sanitize_url(url)
    safe_h = sanitize_headers(headers)

    with httpx.Client(http2=False, follow_redirects=True) as client:
        for attempt in range(max_r + 1):
            try:
                resp = client.request(
                    method_u,
                    url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
                    content=content,
                    timeout=timeout_cfg,
                    stream=stream,
                )

                if _should_retry_status(resp.status_code) and attempt < max_r:
                    wait = back * (2**attempt) + random.uniform(0, 0.25 * back)
                    if resp.status_code == 429:
                        ra = resp.headers.get('Retry-After')
                        if ra:
                            try:
                                wait = max(wait, float(ra))
                            except ValueError:
                                pass
                    log.warning(
                        '[%s] %s %s -> HTTP %s; повтор %s/%s через %.1f с',
                        label,
                        method_u,
                        safe_url,
                        resp.status_code,
                        attempt + 1,
                        max_r,
                        wait,
                    )
                    try:
                        resp.close()
                    except Exception:
                        pass
                    time.sleep(wait)
                    _rewind_files(files)
                    continue

                if log.isEnabledFor(logging.DEBUG):
                    log.debug(
                        '[%s] %s %s -> %s headers=%s',
                        label,
                        method_u,
                        safe_url,
                        resp.status_code,
                        safe_h,
                    )
                return resp

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < max_r:
                    wait = back * (2**attempt) + random.uniform(0, 0.25 * back)
                    log.warning(
                        '[%s] %s %s сбой сети: %s; повтор %s/%s через %.1f с',
                        label,
                        method_u,
                        safe_url,
                        exc,
                        attempt + 1,
                        max_r,
                        wait,
                    )
                    time.sleep(wait)
                    _rewind_files(files)
                    continue
                log.error('[%s] %s %s окончательно не удалось: %s', label, method_u, safe_url, exc)
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError('request_with_retries: internal error')
