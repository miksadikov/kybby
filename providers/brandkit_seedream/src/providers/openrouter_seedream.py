import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_KIT = (os.environ.get('KITYOURBRAND_PROJECT_ROOT') or '').strip()
if not _KIT:
    _KIT = str(Path(__file__).resolve().parents[4])
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)

from app.integrations.provider_http import request_with_retries


@dataclass
class SeedreamRequest:
    prompt: str
    negative_prompt: str = ""
    model: str = "bytedance-seed/seedream-4.5"
    n: int = 1
    timeout_secs: int = 180
    referer: Optional[str] = None
    title: Optional[str] = None


class OpenRouterSeedreamClient:
    """
    OpenRouter image generation client.
    """

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self, referer: Optional[str], title: Optional[str]) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if referer:
            h["HTTP-Referer"] = referer
        if title:
            h["X-Title"] = title
        return h

    @staticmethod
    def _extract_data_urls(resp_json: Dict) -> List[str]:
        urls: List[str] = []
        choices = resp_json.get("choices") or []
        if not choices:
            return urls

        msg = (choices[0] or {}).get("message") or {}
        images = msg.get("images") or []
        for im in images:
            image_url = im.get("image_url") or im.get("imageUrl") or {}
            url = image_url.get("url")
            if isinstance(url, str) and url.startswith("data:image/"):
                urls.append(url)
        return urls

    def generate(self, req: SeedreamRequest) -> Tuple[List[str], Dict]:
        payload = {
            "model": req.model,
            "messages": [{"role": "user", "content": req.prompt}],
            "modalities": ["image"],
            "stream": False,
        }
        if req.n and req.n > 1:
            payload["n"] = int(req.n)

        if req.negative_prompt:
            payload["messages"][0]["content"] = f"{req.prompt}\n\nNegative prompt: {req.negative_prompt}"

        r = request_with_retries(
            'POST',
            self.base_url,
            headers=self._headers(req.referer, req.title),
            json=payload,
            timeout=float(req.timeout_secs),
            label='openrouter.seedream',
        )
        if r.status_code >= 400:
            raise RuntimeError(f"OpenRouter error ({r.status_code}): {r.text[:1000]}")
        data = r.json()
        urls = self._extract_data_urls(data)
        return urls, data


def parse_data_url(data_url: str) -> Tuple[str, bytes]:
    if not data_url.startswith("data:image/"):
        raise ValueError("Not an image data URL")
    head, b64 = data_url.split("base64,", 1)
    mime = head.split("data:", 1)[1].split(";", 1)[0]
    raw = base64.b64decode(b64)
    return mime, raw


def mime_to_ext(mime: str) -> str:
    m = (mime or "").lower()
    if m == "image/png":
        return ".png"
    if m in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if m == "image/webp":
        return ".webp"
    return ".bin"
