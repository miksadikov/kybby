import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, List, Tuple
import json as _json

import httpx
import requests
from cli_log import info, warn, error, debug

_KIT = (os.environ.get('KITYOURBRAND_PROJECT_ROOT') or '').strip()
if not _KIT:
    _KIT = str(Path(__file__).resolve().parents[4])
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)

from app.integrations.provider_http import request_with_retries


class RecraftClient:
    """
    Официальный клиент Recraft API.

    Формат определяется по HTTP Content-Type и/или
    по сигнатуре первых байтов.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base = base_url or os.getenv("RECRAFT_BASE_URL", "https://external.api.recraft.ai/v1")
        self.key = api_key or os.getenv("RECRAFT_API_KEY")
        if not self.key:
            error("RECRAFT_API_KEY не задан — задайте ключ в .env или переменной окружения")
            raise RuntimeError("RECRAFT_API_KEY не задан")

        info("RecraftClient: base_url=%s, API key: %s", self.base, "***" if self.key else "(empty)")
        self.headers = {"Authorization": f"Bearer {self.key}"}

    def create_style(self, style: str, files: List[str]) -> str:
        url = f"{self.base}/styles"
        file_paths = list(files[:5])
        info("create_style: POST %s, style=%s, files=%s", url, style, [os.path.basename(p) for p in file_paths])

        mfiles = {}
        for i, path in enumerate(file_paths, 1):
            mfiles[f"file{i}"] = open(path, "rb")

        data = {"style": style}
        try:
            r = request_with_retries(
                'POST',
                url,
                headers=self.headers,
                files=mfiles,
                data=data,
                timeout=60.0,
                label='recraft.create_style',
            )
            try:
                r.raise_for_status()
            except Exception:
                self._debug_http_error(r, label="create_style", data=data, files=file_paths)
                raise

            style_id = r.json()["id"]
            info("create_style: OK, style_id=%s", style_id)
            return style_id
        finally:
            for f in mfiles.values():
                try:
                    f.close()
                except Exception:
                    pass

    def generate(
        self,
        prompt: str,
        model: str = "recraftv3",
        style_id: Optional[str] = None,
        style: Optional[str] = None,
        substyle: Optional[str] = None,
        n: int = 1,
        size: str = "1024x1024",
        controls: Optional[dict] = None,
    ) -> str:
        """Возвращает URL на сгенерированный ассет."""
        url = f"{self.base}/images/generations"
        body = {
            "prompt": prompt,
            "n": n,
            "model": model,
            "size": size,
        }

        if style_id:
            body["style_id"] = style_id
        if style and not style_id:
            body["style"] = style
        if substyle and not style_id:
            body["substyle"] = substyle
        if controls:
            body["controls"] = controls

        prompt_preview = (prompt[:200] + "…") if len(prompt) > 200 else prompt
        info(
            "generate: POST %s model=%s style_id=%s style=%s substyle=%s",
            url,
            model,
            style_id or "-",
            style or "-",
            substyle or "-",
        )
        debug("generate: prompt (preview): %s", prompt_preview)

        r = request_with_retries(
            'POST',
            url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=body,
            timeout=120.0,
            label='recraft.generate',
        )
        try:
            r.raise_for_status()
        except Exception:
            warn("generate: HTTP error status=%s", r.status_code)
            self._debug_http_error(r, label="generate", payload=body)
            raise

        js = r.json()
        asset_url = js["data"][0]["url"]
        info("generate: OK, asset URL получен (длина=%s)", len(asset_url))
        return asset_url

    @staticmethod
    def _detect_ext_and_mime(content_type: str, data: bytes) -> Tuple[str, str]:
        ct = (content_type or "").split(";", 1)[0].strip().lower()

        # 1) Header-based
        if ct in ("image/svg+xml", "image/svg"):
            return "svg", "image/svg+xml"
        if ct == "image/png":
            return "png", "image/png"
        if ct in ("image/jpeg", "image/jpg"):
            return "jpg", "image/jpeg"
        if ct == "image/webp":
            return "webp", "image/webp"

        # 2) Signature-based (на случай неверных/пустых заголовков)
        head = data[:64].lstrip()

        if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head:
            return "svg", "image/svg+xml"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png", "image/png"
        if data[:3] == b"\xff\xd8\xff":
            return "jpg", "image/jpeg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp", "image/webp"

        # fallback
        return "bin", ct or "application/octet-stream"

    @staticmethod
    def _parse_total_size_from_content_range(content_range: str) -> Optional[int]:
        """
        Пример:
        Content-Range: bytes 0-20479/1524206
        """
        if not content_range:
            return None

        m = re.match(r"bytes\s+\d+-\d+/(\d+)", content_range.strip(), re.IGNORECASE)
        if not m:
            return None

        try:
            return int(m.group(1))
        except Exception:
            return None

    def _debug_http_error(self, r, *, label: str, payload=None, files=None, data=None):
        """
        Печатает максимум полезной информации при ошибке HTTP.

        payload — dict для JSON (generate)
        data    — dict/str для form-data (create_style)
        files   — список путей (create_style), чтобы не печатать бинарь
        """
        try:
            error("[%s] HTTP ERROR", label)
            error("status: %s", r.status_code)
            error("url : %s", getattr(r.request, "url", r.url))

            rid = r.headers.get("x-request-id") or r.headers.get("x-trace-id") or r.headers.get("request-id")
            if rid:
                error("request-id: %s", rid)

            ct = r.headers.get("content-type", "")
            error("resp content-type: %s", ct)

            if payload is not None:
                try:
                    error("request json: %s", _json.dumps(payload, ensure_ascii=False)[:4000])
                except Exception:
                    error("request json: %s", str(payload)[:4000])

            if data is not None:
                try:
                    error("request data: %s", _json.dumps(data, ensure_ascii=False)[:4000])
                except Exception:
                    error("request data: %s", str(data)[:4000])

            if files is not None:
                error("request files: %s", files)

            txt = ""
            try:
                txt = r.text or ""
            except Exception:
                txt = ""

            if txt:
                error("response text (head): %s", txt[:4000])

            try:
                js = r.json()
                error("response json: %s", _json.dumps(js, ensure_ascii=False)[:8000])
            except Exception:
                pass

            error("[%s] end HTTP error dump", label)
        except Exception as ex:
            error("_debug_http_error: не удалось вывести детали: %s", ex)

    def _download_asset_stream_fallback(self, url: str, out_path_base: str) -> Tuple[str, str]:
        """
        Фолбэк: обычная потоковая загрузка без Range.
        Нужен на случай, если сервер неожиданно не поддержал Partial Content.
        """
        info("download_asset[fallback]: stream GET %s", url[:200] + ("…" if len(url) > 200 else ""))

        with requests.get(url, stream=True, timeout=(10, 180)) as r:
            try:
                r.raise_for_status()
            except Exception:
                warn("download_asset[fallback]: HTTP error status=%s", r.status_code)
                self._debug_http_error(
                    r,
                    label="download_asset_fallback",
                    data={"url": url, "out": out_path_base},
                )
                raise

            first_chunk = b""
            buffered = []

            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    first_chunk = chunk
                    buffered.append(chunk)
                    break

            if not first_chunk:
                raise RuntimeError("download_asset[fallback]: пустой ответ от сервера")

            ext, mime = self._detect_ext_and_mime(r.headers.get("Content-Type", ""), first_chunk)

            if out_path_base.lower().endswith("." + ext):
                out_path = out_path_base
            else:
                out_path = out_path_base + "." + ext

            part_path = out_path + ".part"
            total_written = 0

            with open(part_path, "wb") as f:
                for chunk in buffered:
                    f.write(chunk)
                    total_written += len(chunk)

                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_written += len(chunk)

            os.replace(part_path, out_path)
            info("download_asset[fallback]: сохранено %s (%s байт, mime=%s)", out_path, total_written, mime)
            return out_path, mime

    def download_asset(self, url: str, out_path_base: str) -> Tuple[str, str]:
        """
        Скачивает ассет и сохраняет с правильным расширением.

        Логика:
        1. Пытаемся скачать первый кусок через Range.
        2. Если сервер корректно отвечает 206 Partial Content и присылает Content-Range,
           переходим в кусочную загрузку крупными блоками.
        3. Если нет — откатываемся на обычную stream-загрузку
        """
        info("download_asset: GET %s", url[:200] + ("…" if len(url) > 200 else ""))

        # Small 20 KB chunks were too slow on some local/VPN connections and could
        # make Recraft hit the 5-minute provider timeout after successful generation.
        chunk_size = 512 * 1024
        max_retries_per_chunk = 3
        retry_sleep_sec = 1.5

        # Стартовый range-запрос: получаем первые байты и общий размер файла
        first_end = chunk_size - 1
        try:
            r0 = request_with_retries(
                'GET',
                url,
                headers={"Range": f"bytes=0-{first_end}"},
                timeout=httpx.Timeout(60.0, connect=10.0),
                label='recraft.download.range_init',
            )
        except Exception as e:
            warn("download_asset: стартовый range-запрос не удался, fallback: %s", e)
            return self._download_asset_stream_fallback(url, out_path_base)

        try:
            r0.raise_for_status()
        except Exception:
            warn("download_asset: стартовый range HTTP error status=%s", r0.status_code)
            self._debug_http_error(
                r0,
                label="download_asset_range_init",
                data={"url": url, "out": out_path_base},
            )
            raise

        if r0.status_code != 206:
            warn("download_asset: сервер не вернул 206 Partial Content (status=%s), fallback to stream", r0.status_code)
            return self._download_asset_stream_fallback(url, out_path_base)

        first_data = r0.content
        if not first_data:
            raise RuntimeError("download_asset: пустой первый range-кусок")

        total_size = self._parse_total_size_from_content_range(r0.headers.get("Content-Range", ""))
        if not total_size:
            warn("download_asset: не удалось определить total_size из Content-Range, fallback to stream")
            return self._download_asset_stream_fallback(url, out_path_base)

        ext, mime = self._detect_ext_and_mime(r0.headers.get("Content-Type", ""), first_data)

        if out_path_base.lower().endswith("." + ext):
            out_path = out_path_base
        else:
            out_path = out_path_base + "." + ext

        part_path = out_path + ".part"

        with open(part_path, "wb") as f:
            f.write(first_data)
            downloaded = len(first_data)

            info(
                "download_asset: range mode, total=%s bytes, first_chunk=%s bytes, mime=%s, out=%s",
                total_size,
                downloaded,
                mime,
                out_path,
            )

            while downloaded < total_size:
                start = downloaded
                end = min(start + chunk_size - 1, total_size - 1)

                last_exc = None
                for attempt in range(1, max_retries_per_chunk + 1):
                    try:
                        rr = request_with_retries(
                            'GET',
                            url,
                            headers={"Range": f"bytes={start}-{end}"},
                            timeout=httpx.Timeout(60.0, connect=10.0),
                            label='recraft.download.chunk',
                            max_retries=0,
                        )
                        rr.raise_for_status()

                        if rr.status_code != 206:
                            raise RuntimeError(f"ожидался 206, получен {rr.status_code}")

                        chunk = rr.content
                        expected_len = end - start + 1
                        if len(chunk) != expected_len:
                            raise RuntimeError(
                                f"неполный chunk: ожидалось {expected_len} байт, получено {len(chunk)}"
                            )

                        f.write(chunk)
                        downloaded += len(chunk)

                        info(
                            "download_asset: chunk ok %s-%s (%s bytes), progress=%s/%s",
                            start,
                            end,
                            len(chunk),
                            downloaded,
                            total_size,
                        )

                        last_exc = None
                        break

                    except Exception as e:
                        last_exc = e
                        warn(
                            "download_asset: chunk retry %s/%s failed for bytes=%s-%s: %s",
                            attempt,
                            max_retries_per_chunk,
                            start,
                            end,
                            e,
                        )
                        if attempt < max_retries_per_chunk:
                            time.sleep(retry_sleep_sec)

                if last_exc is not None:
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass

                    raise RuntimeError(
                        f"download_asset: не удалось скачать chunk bytes={start}-{end} "
                        f"after {max_retries_per_chunk} attempts"
                    ) from last_exc

        os.replace(part_path, out_path)
        info("download_asset: сохранено %s (%s байт, mime=%s)", out_path, total_size, mime)
        return out_path, mime
