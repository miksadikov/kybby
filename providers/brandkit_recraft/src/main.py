import argparse, os, json, sys, traceback
from pathlib import Path
from dotenv import load_dotenv
from utils.file_utils import ensure_dir, slugify, hex_to_rgb_triplet
from utils.svg_tools import normalize_svg_palette_and_stroke
from utils.raster_tools import quantize_to_palette
from providers.recraft_official import RecraftClient
from cli_log import info, warn, error

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV)

def load_tokens(path): 
    with open(path,'r',encoding='utf-8') as f: 
        return json.load(f)

def build_prompt(base_prompt, tokens, kind):
    pal = tokens.get('palette', {})
    icon = tokens.get('icon', {})
    tex = tokens.get('texture', {})
    ill = tokens.get('illustration', {})
    parts = [base_prompt]
    if kind=='icon':
        parts += [f"outline, rounded corners, stroke {icon.get('strokeWidth',2)}",
                  f"brand palette {pal.get('primary','')}/{pal.get('secondary','')}/{pal.get('accent','')}"]
    elif kind=='pattern':
        parts += [f"seamless background, motifs: {', '.join(tex.get('motifs', []))}, density: {tex.get('density','medium')}",
                  f"brand palette {pal.get('primary','')}/{pal.get('secondary','')}/{pal.get('accent','')}"]
    else:
        parts += [f"{ill.get('prompt_suffix','minimal')}",
                  f"brand palette {pal.get('primary','')}/{pal.get('secondary','')}/{pal.get('accent','')}"]
    return '; '.join([p for p in parts if p])

def colors_control(tokens):
    pal = tokens.get('palette', {})
    rgb = []
    for k in ('primary','secondary','accent'):
        if pal.get(k):
            rgb.append({'rgb': hex_to_rgb_triplet(pal[k])})
    return {'colors': rgb} if rgb else None

def postprocess_dirs(out_logos, out_icons, out_patterns, out_ills, tokens):
    pal = tokens.get('palette', {})
    palette = [c for c in [pal.get('primary'), pal.get('secondary'), pal.get('accent')] if c]
    # SVG normalization
    for folder in (out_logos, out_icons):
        for fn in os.listdir(folder):
            if fn.lower().endswith('.svg'):
                try:
                    normalize_svg_palette_and_stroke(os.path.join(folder, fn),
                                                     target_palette=palette,
                                                     target_stroke_width=tokens.get('icon',{}).get('strokeWidth',2))
                except Exception as e:
                    warn('postprocess: svg normalize %s: %s', fn, e)
    # Raster quantization
    for folder in (out_patterns, out_ills):
        for fn in os.listdir(folder):
            if fn.lower().endswith(('.png','.jpg','.jpeg','.webp')):
                try:
                    quantize_to_palette(os.path.join(folder, fn), palette_hex=palette,
                                        out_path=os.path.join(folder, fn))
                except Exception as e:
                    warn('postprocess: raster quantize %s: %s', fn, e)

def main():
    parser = argparse.ArgumentParser(description='BrandKit (Recraft-only, fixed)')
    parser.add_argument('--tokens', default='config/tokens.json')
    parser.add_argument('--out', default='out')
    parser.add_argument('--build-style', action='store_true', help='Создать style_id из ./references')
    parser.add_argument('--style-base', default='icon', choices=['icon','vector_illustration','digital_illustration','realistic_image'])
    parser.add_argument('--style-id', default=None, help='Если уже есть готовый style_id')
    parser.add_argument('--logos', type=int, default=4)
    parser.add_argument('--icons', type=int, default=8)
    parser.add_argument('--patterns', type=int, default=4)
    parser.add_argument('--illustrations', type=int, default=4)
    parser.add_argument('--model', default='recraftv3', choices=['recraftv3','recraftv2'])
    args = parser.parse_args()

    load_dotenv()
    info('=== brandkit_recraft CLI ===')
    info('tokens=%s out=%s build_style=%s style_id=%s model=%s', args.tokens, args.out, args.build_style, args.style_id, args.model)
    info('counts: logos=%s icons=%s patterns=%s illustrations=%s style_base=%s', args.logos, args.icons, args.patterns, args.illustrations, args.style_base)

    client = RecraftClient()
    tokens = load_tokens(args.tokens)
    info('tokens.json загружен, brand keys: %s', list(tokens.keys())[:20])

    ensure_dir(args.out)
    out_logos = os.path.join(args.out, 'logos'); ensure_dir(out_logos)
    out_icons = os.path.join(args.out, 'icons'); ensure_dir(out_icons)
    out_patterns = os.path.join(args.out, 'patterns'); ensure_dir(out_patterns)
    out_ills = os.path.join(args.out, 'illustrations'); ensure_dir(out_ills)

    style_id = args.style_id
    if args.build_style:
        refs = [os.path.join('references', f) for f in os.listdir('references') if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        refs = refs[:5]
        if not refs:
            warn('Нет референсов в ./references — пропускаю создание стиля')
        else:
            info('Создание стиля из %s референсов (style_base=%s)', len(refs), args.style_base)
            style_id = client.create_style(style=args.style_base, files=refs)
            # Подстрока "created style_id:" нужна оркестратору (generation_service) для парсинга stdout
            info('[ok] created style_id: %s', style_id)

    controls = colors_control(tokens)
    if controls:
        info('colors_control: передан в API (%s цветов)', len(controls.get('colors') or []))
    else:
        info('colors_control: не задан (палитра пустая по primary/secondary/accent)')

    # LOGOS
    logo_prompts = tokens.get('prompts',{}).get('logos', [])
    n_logos = min(len(logo_prompts), args.logos)
    info('--- Логотипы: будет сгенерировано до %s (из %s промптов), model=%s ---', n_logos, len(logo_prompts), args.model)
    for idx, subj in enumerate(logo_prompts[:args.logos], 1):
        info('Логотип %s/%s: %s', idx, n_logos, subj)
        prompt = build_prompt(subj + ' logo mark', tokens, 'illustration')
        url = client.generate(prompt=prompt, model=args.model,
                              style_id=style_id if args.style_base=='vector_illustration' and style_id else None,
                              style='vector_illustration' if not style_id else None,
                              substyle=None,
                              n=1, size='1024x1024', controls=controls)
        client.download_asset(url, os.path.join(out_logos, f"logo-{idx:02d}"))

    # ICONS — Recraft V3 НЕ поддерживает стиль `icon` (см. Appendix), поэтому принудительно используем V2
    icon_prompts = tokens.get('prompts',{}).get('icons', [])
    n_icons = min(len(icon_prompts), args.icons)
    info('--- Иконки: будет сгенерировано до %s (из %s промптов), модель recraftv2 ---', n_icons, len(icon_prompts))
    for idx, subj in enumerate(icon_prompts[:args.icons], 1):
        info('Иконка %s/%s: %s', idx, n_icons, subj)
        prompt = build_prompt(subj + ' icon', tokens, 'icon')
        icon_model = 'recraftv2'
        url = client.generate(prompt=prompt, model=icon_model,
                                    style_id=style_id if args.style_base=='icon' and style_id else None,
                                    style='icon' if not style_id else None,
                                    substyle=None,
                                    n=1, size='1024x1024', controls=controls)
        client.download_asset(url, os.path.join(out_icons, f"{slugify(subj)}"))

    # PATTERNS (digital_illustration), можно оставить v3
    pat_prompts = tokens.get('prompts',{}).get('patterns', [])
    substyle = tokens.get('texture',{}).get('substyle')
    n_pat = min(len(pat_prompts), args.patterns)
    info('--- Паттерны: до %s (из %s промптов), model=%s substyle=%s ---', n_pat, len(pat_prompts), args.model, substyle)
    for i, base in enumerate(pat_prompts[:args.patterns], 1):
        info('Паттерн %s/%s: %s', i, n_pat, base)
        prompt = build_prompt(base, tokens, 'pattern')
        url = client.generate(prompt=prompt, model=args.model,
                                    style_id=style_id if args.style_base=='digital_illustration' and style_id else None,
                                    style='digital_illustration' if not style_id else None,
                                    substyle=substyle if not style_id else None,
                                    n=1, size='1024x1024', controls=controls)
        client.download_asset(url, os.path.join(out_patterns, f"pattern-{i:02d}"))

    # ILLUSTRATIONS
    ill_prompts = tokens.get('prompts',{}).get('illustrations', [])
    ill_cfg = tokens.get('illustration', {}) or {}
    ill_vector = bool(ill_cfg.get('vector', False))
    ill_raster = bool(ill_cfg.get('raster', True))
    if ill_vector and not ill_raster:
        ill_style = 'vector_illustration'
    elif ill_raster and not ill_vector:
        ill_style = 'digital_illustration'
    elif ill_vector and ill_raster:
        ill_style = 'digital_illustration'
    else:
        ill_style = 'digital_illustration'
    n_ill = min(len(ill_prompts), args.illustrations)
    info('--- Иллюстрации: до %s (из %s), vector=%s raster=%s ill_style=%s ---', n_ill, len(ill_prompts), ill_vector, ill_raster, ill_style)
    for i, base in enumerate(ill_prompts[:args.illustrations], 1):
        info('Иллюстрация %s/%s: %s', i, n_ill, base)
        prompt = build_prompt(base, tokens, 'illustration')
        url = client.generate(prompt=prompt, model=args.model,
                                    style_id=style_id if args.style_base==ill_style and style_id else None,
                                    style=ill_style if not style_id else None,
                                    substyle=None,
                                    n=1, size='1024x1024', controls=controls)
        client.download_asset(url, os.path.join(out_ills, f"illustration-{i:02d}"))

    info('Постобработка (SVG / растр)...')
    postprocess_dirs(out_logos, out_icons, out_patterns, out_ills, tokens)
    info('[ok] Done. Assets saved to: %s', args.out)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        error('Прервано пользователем (Ctrl+C)')
        sys.exit(130)
    except Exception as exc:
        error('Фатальная ошибка: %s', exc)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
