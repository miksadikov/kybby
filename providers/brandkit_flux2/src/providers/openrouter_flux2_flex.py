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
class FluxFlexRequest:
    prompt: str
    model: str = "black-forest-labs/flux.2-flex"
    n: int = 1
    timeout_secs: int = 240
    referer: Optional[str] = None
    title: Optional[str] = None
    # OpenRouter image_config (if supported by the model)
    aspect_ratio: Optional[str] = None
    image_size: Optional[str] = None
    # OpenRouter chat-completions seed (best-effort; some providers may ignore)
    seed: Optional[int] = None
    # Provider-specific (best-effort passthrough): common names across many image providers
    # These may be ignored depending on the routed provider.
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None


class OpenRouterFluxFlexClient:
    """OpenRouter image generation client for FLUX.2 [flex]."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self, referer: Optional[str], title: Optional[str]) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Optional OpenRouter attribution headers
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

    def generate(self, req: FluxFlexRequest) -> Tuple[List[str], Dict]:
        payload: Dict = {
            "model": req.model,
            "messages": [{"role": "user", "content": req.prompt}],
            # FLUX models are image-only on OpenRouter
            "modalities": ["image"],
            "stream": False,
        }
        if req.n and req.n > 1:
            payload["n"] = int(req.n)

        # Best-effort seed support
        if req.seed is not None:
            payload["seed"] = int(req.seed)

        # Provider-specific params passthrough (best-effort)
        if req.num_inference_steps is not None:
            payload["num_inference_steps"] = int(req.num_inference_steps)
        if req.guidance_scale is not None:
            payload["guidance_scale"] = float(req.guidance_scale)

        # Image config options (if supported by the selected model)
        image_config: Dict[str, str] = {}
        if req.aspect_ratio:
            image_config["aspect_ratio"] = str(req.aspect_ratio)
        if req.image_size:
            image_config["image_size"] = str(req.image_size)
        if image_config:
            payload["image_config"] = image_config

        r = request_with_retries(
            'POST',
            self.base_url,
            headers=self._headers(req.referer, req.title),
            json=payload,
            timeout=float(req.timeout_secs),
            label='openrouter.flux_flex',
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
