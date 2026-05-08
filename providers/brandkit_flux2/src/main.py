#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from dotenv import load_dotenv

from providers.openrouter_flux2_flex import (
    FluxFlexRequest,
    OpenRouterFluxFlexClient,
    mime_to_ext,
    parse_data_url,
)

try:
    from PIL import Image  # optional
    from io import BytesIO

    PIL_OK = True
except Exception:
    PIL_OK = False

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)

def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "item"


def build_prompts(tokens: Dict, kind: str, name: str) -> Tuple[str, str]:
    """Returns (prompt, negative). Negative is kept for meta/debug; FLUX may ignore it."""
    style = tokens.get("style", {}) or {}
    style_prompt = (style.get("prompt") or "").strip()
    negative = (style.get("negative") or "").strip()

    palette = tokens.get("palette") or {}
    pal_txt = ""
    if palette:
        parts = []
        for k in ("primary", "secondary", "accent"):
            if palette.get(k):
                parts.append(f"{k}:{palette[k]}")
        if parts:
            pal_txt = "Palette: " + ", ".join(parts) + "."

    icon_cfg = tokens.get("icon") or {}

    if kind == "logos":
        prompt = (
            f"Create a brand logo concept for: {name}. "
            f"{style_prompt} {pal_txt} "
            f"Centered logo mark, clean geometry, minimal details, vector-like style. "
            f"No text, no watermark, no mockup."
        )
        if icon_cfg:
            prompt += f" Logo details: {json.dumps(icon_cfg, ensure_ascii=False)}."
        return prompt.strip(), negative

    # Важно: FLUX (и многие модели) могут интерпретировать 'negative prompt' как обычный текст.
    # Поэтому все ограничения формулируем позитивно: что должно быть в кадре.

    if kind == "icons":
        prompt = (
            f"Design a simple UI icon for: {name}. "
            f"{style_prompt} {pal_txt} "
            f"Centered composition, high contrast, clean silhouette. "
            f"Flat vector-like look, minimal details. "
            f"Transparent background if possible. "
            f"No letters, no words, no watermark."
        )
        if icon_cfg:
            prompt += f" Icon details: {json.dumps(icon_cfg, ensure_ascii=False)}."
        return prompt.strip(), negative

    if kind == "patterns":
        prompt = (
            f"Create a seamless repeating pattern: {name}. "
            f"{style_prompt} {pal_txt} "
            f"Tileable, seamless edges, minimal, clean. "
            f"No text, no watermark."
        )
        return prompt.strip(), negative

    prompt = (
        f"Create a brand illustration for UI: {name}. "
        f"{style_prompt} {pal_txt} "
        f"Modern, friendly, clean composition. "
        f"No text, no watermark."
    )
    return prompt.strip(), negative


def save_image_bytes(raw: bytes, mime: str, out_path_base: str, force_png: bool = False) -> str:
    ext = mime_to_ext(mime)
    out_path = out_path_base + ext

    if force_png and PIL_OK and ext != ".png":
        try:
            img = Image.open(BytesIO(raw)).convert("RGBA")
            out_path = out_path_base + ".png"
            img.save(out_path, format="PNG")
            return out_path
        except Exception:
            pass

    with open(out_path, "wb") as f:
        f.write(raw)
    return out_path


def take_n(items: List[str], n: int, fallback_prefix: str) -> List[str]:
    if n <= 0:
        return []
    items = items or []
    if len(items) >= n:
        return items[:n]
    out = list(items)
    for i in range(len(items) + 1, n + 1):
        out.append(f"{fallback_prefix}-{i:02d}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="BrandKit CLI generator via OpenRouter FLUX.2 [flex]")
    ap.add_argument("--tokens", required=True, help="Path to tokens.json")
    ap.add_argument("--out", default="out", help="Output root directory (default: out)")
    ap.add_argument("--brand-id", default="", help="Brand ID subfolder inside out/")
    ap.add_argument("--logos", type=int, default=0, help="How many logos to generate")
    ap.add_argument("--icons", type=int, default=0, help="How many icons to generate")
    ap.add_argument("--patterns", type=int, default=0, help="How many patterns to generate")
    ap.add_argument("--illustrations", type=int, default=0, help="How many illustrations to generate")

    ap.add_argument("--model", default="", help="Override model (default from tokens.openrouter.model)")
    ap.add_argument("--n", type=int, default=1, help="How many images per prompt (if supported)")
    ap.add_argument("--timeout", type=int, default=0, help="Request timeout seconds (override)")

    ap.add_argument("--aspect-ratio", default="", help="OpenRouter image_config.aspect_ratio (e.g., 1:1, 16:9)")
    ap.add_argument("--image-size", default="", help="OpenRouter image_config.image_size (1K, 2K, 4K)")
    ap.add_argument("--seed", type=int, default=None, help="Best-effort seed (some providers may ignore)")

    ap.add_argument(
        "--steps",
        type=int,
        default=None,
        help="Best-effort num_inference_steps passthrough (may be ignored by provider)",
    )
    ap.add_argument(
        "--guidance",
        type=float,
        default=None,
        help="Best-effort guidance_scale passthrough (may be ignored by provider)",
    )

    ap.add_argument(
        "--append-negative",
        action="store_true",
        help="Append tokens.style.negative into prompt as plain text (NOT recommended for FLUX)",
    )
    ap.add_argument("--force-png", action="store_true", help="Try to convert outputs to PNG (needs Pillow)")

    args = ap.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("ERROR: set OPENROUTER_API_KEY env var", file=sys.stderr)
        return 2

    tokens = load_json(args.tokens)
    or_cfg = tokens.get("openrouter") or {}

    model = (args.model or or_cfg.get("model") or "black-forest-labs/flux.2-flex").strip()
    timeout_secs = args.timeout or int(or_cfg.get("timeout_secs") or 240)

    referer = os.getenv("OPENROUTER_REFERER", "").strip() or or_cfg.get("referer")
    title = os.getenv("OPENROUTER_TITLE", "").strip() or or_cfg.get("title")

    # image_config defaults from tokens, can be overridden by CLI
    img_cfg = (or_cfg.get("image_config") or {}) if isinstance(or_cfg.get("image_config"), dict) else {}
    aspect_ratio = (args.aspect_ratio or img_cfg.get("aspect_ratio") or "").strip() or None
    image_size = (args.image_size or img_cfg.get("image_size") or "").strip() or None

    steps = args.steps
    if steps is None:
        steps = or_cfg.get("num_inference_steps")
        if steps is None:
            steps = or_cfg.get("steps")
    guidance = args.guidance
    if guidance is None:
        guidance = or_cfg.get("guidance_scale")
        if guidance is None:
            guidance = or_cfg.get("guidance")

    client = OpenRouterFluxFlexClient(api_key=api_key)

    brand_folder = args.out
    if args.brand_id:
        brand_folder = os.path.join(args.out, args.brand_id)

    logos_dir = os.path.join(brand_folder, "logos")
    icons_dir = os.path.join(brand_folder, "icons")
    patterns_dir = os.path.join(brand_folder, "patterns")
    illustrations_dir = os.path.join(brand_folder, "illustrations")
    ensure_dir(logos_dir)
    ensure_dir(icons_dir)
    ensure_dir(patterns_dir)
    ensure_dir(illustrations_dir)

    prompts = tokens.get("prompts") or {}
    logo_names = take_n(prompts.get("logos") or [], args.logos, "logo")
    icon_names = take_n(prompts.get("icons") or [], args.icons, "icon")
    pattern_names = take_n(prompts.get("patterns") or [], args.patterns, "pattern")
    ill_names = take_n(prompts.get("illustrations") or [], args.illustrations, "illustration")

    meta = {
        "provider": "openrouter",
        "model": model,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "image_config": {"aspect_ratio": aspect_ratio, "image_size": image_size},
        "seed": args.seed,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "outputs": {"logos": [], "icons": [], "patterns": [], "illustrations": []},
    }

    def gen(kind: str, names: List[str], out_dir: str):
        for name in names:
            print(f"[{kind}] generating: {name}")
            prompt, neg = build_prompts(tokens, kind, name)
            if args.append_negative and neg:
                prompt = f"{prompt}\n\nNegative prompt: {neg}"

            req = FluxFlexRequest(
                prompt=prompt,
                model=model,
                n=max(1, int(args.n)),
                timeout_secs=timeout_secs,
                referer=referer,
                title=title,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=args.seed,
                num_inference_steps=steps,
                guidance_scale=guidance,
            )

            urls, raw_resp = client.generate(req)
            if not urls:
                raise RuntimeError(f"No images in response for {kind}:{name}.")

            for j, data_url in enumerate(urls, start=1):
                mime, raw = parse_data_url(data_url)
                base_name = slugify(name)
                if len(urls) > 1:
                    base_name = f"{base_name}-{j:02d}"
                out_base = os.path.join(out_dir, base_name)
                saved_path = save_image_bytes(raw, mime, out_base, force_png=args.force_png)

                meta["outputs"][kind].append(
                    {
                        "name": name,
                        "prompt": prompt,
                        "negative": neg,
                        "file": os.path.relpath(saved_path, brand_folder),
                        "mime": mime,
                    }
                )

    if args.logos:
        gen("logos", logo_names, logos_dir)
    if args.icons:
        gen("icons", icon_names, icons_dir)
    if args.patterns:
        gen("patterns", pattern_names, patterns_dir)
    if args.illustrations:
        gen("illustrations", ill_names, illustrations_dir)

    meta_path = os.path.join(brand_folder, "openrouter_flux2_flex_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("[ok] done")
    print("[ok] output:", os.path.abspath(brand_folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
