from lxml import etree

def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _closest_color(hex_color, palette):
    if not palette: return hex_color
    import math
    r1,g1,b1 = _hex_to_rgb(hex_color)
    best, best_d = None, 10**9
    for p in palette:
        r2,g2,b2 = _hex_to_rgb(p)
        d = ((r1-r2)**2 + (g1-b2)**2 + (b1-b2)**2) ** 0.5
        if d < best_d: best_d, best = d, p
    return best

def normalize_svg_palette_and_stroke(svg_path: str, target_palette, target_stroke_width=2):
    from lxml import etree
    parser = etree.XMLParser(remove_comments=True)
    with open(svg_path, 'rb') as f: tree = etree.parse(f, parser)
    root = tree.getroot()
    for el in root.iter():
        style = el.attrib.get('style')
        if style:
            items = dict(s.split(':',1) for s in style.split(';') if ':' in s)
            if 'stroke-width' in items: items['stroke-width'] = str(float(target_stroke_width))
            if 'stroke' in items and items['stroke'].startswith('#'):
                items['stroke'] = _closest_color(items['stroke'], target_palette)
            if 'fill' in items and items['fill'].startswith('#'):
                items['fill'] = _closest_color(items['fill'], target_palette)
            el.attrib['style'] = ';'.join(f"{k}:{v}" for k,v in items.items())
        if 'stroke-width' in el.attrib: el.attrib['stroke-width'] = str(float(target_stroke_width))
        if 'stroke' in el.attrib and el.attrib['stroke'].startswith('#'):
            el.attrib['stroke'] = _closest_color(el.attrib['stroke'], target_palette)
        if 'fill' in el.attrib and el.attrib['fill'].startswith('#'):
            el.attrib['fill'] = _closest_color(el.attrib['fill'], target_palette)
    tree.write(svg_path, encoding='utf-8', xml_declaration=True)
