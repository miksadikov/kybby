import os, re, unicodedata

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def slugify(value: str) -> str:
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii','ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value

def hex_to_rgb_triplet(hex_color: str):
    h = hex_color.lstrip('#')
    return [int(h[i:i+2],16) for i in (0,2,4)]
