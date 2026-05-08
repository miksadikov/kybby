from PIL import Image

def _build_palette_bytes(palette_hex):
    pal = []
    for h in palette_hex:
        h = h.lstrip('#')
        pal.extend([int(h[i:i+2],16) for i in (0,2,4)])
    while len(pal) < 768:
        pal.extend(pal[:min(3,len(pal))] or [0,0,0])
    return pal[:768]

def quantize_to_palette(path_in: str, palette_hex, out_path: str):
    if not palette_hex: return
    img = Image.open(path_in).convert('RGBA')
    pal_img = Image.new('P', (1,1))
    pal_img.putpalette(_build_palette_bytes(palette_hex))
    q = img.convert('RGB').quantize(palette=pal_img, dither=0).convert('RGBA')
    q.save(out_path)
