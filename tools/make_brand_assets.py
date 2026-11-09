#!/usr/bin/env python3
"""Generates every Ray Launcher brand asset (logos, icons, illustrations, backgrounds).

    python3 tools/make_brand_assets.py            # run from the repository root
    pip install pillow                            # the only dependency

The artwork is original to Ray. The pixel lightning bolt and the navy palette are the ones
Ray Client uses in-game, so the launcher and the client read as one product. Text in the
banner/DMG images is rendered with Pixelify Sans (SIL OFL, see tools/assets/).
"""
import os
import random
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'packages', 'rayclient_app')
ASSETS = os.path.join(APP, 'assets')
ICONS = os.path.join(APP, 'icons')
FONT = os.path.join(ROOT, 'tools', 'assets', 'PixelifySans.ttf')

# --- palette (Ray Client's Theme.java) --------------------------------------------------
BG_DEEP = (5, 6, 11)
BG = (10, 13, 22)
PANEL = (15, 19, 32)
PANEL_TOP = (21, 26, 44)
CARD = (21, 26, 42)
HOVER = (31, 39, 64)
STROKE = (37, 44, 68)
TEXT = (240, 243, 251)
DIM = (154, 165, 194)
MUTE = (97, 108, 136)
ACCENT = (76, 141, 255)
ACC_LIGHT = (156, 194, 255)
ACC_DARK = (42, 91, 215)
YELLOW = (255, 216, 74)


def hexc(c):
    return '#%02X%02X%02X' % c


# --- the pixel bolt (14 x 15), same bitmap as Ray Client's Brand.BOLT --------------------
BOLT = [
    '.........###..',
    '........###...',
    '.......###....',
    '......####....',
    '.....####.....',
    '....#########.',
    '...##########.',
    '...#########..',
    '..#########...',
    '......#####...',
    '......###.....',
    '.....###......',
    '.....##.......',
    '.....#........',
    '....#.........',
]
BW, BH = len(BOLT[0]), len(BOLT)


def bolt_has(x, y):
    return 0 <= y < BH and 0 <= x < BW and BOLT[y][x] == '#'


# --- 5x7 pixel letters for the wordmark -------------------------------------------------
GLYPHS = {
    'R': ['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#'],
    'A': ['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'U': ['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'N': ['#...#', '##..#', '#.#.#', '#..##', '#...#', '#...#', '#...#'],
    'C': ['.###.', '#...#', '#....', '#....', '#....', '#...#', '.###.'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'E': ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
}


def text_cells(text):
    cells, x = [], 0
    for ch in text:
        if ch == ' ':
            x += 3
            continue
        g = GLYPHS[ch]
        for y, row in enumerate(g):
            for gx, c in enumerate(row):
                if c == '#':
                    cells.append((x + gx, y))
        x += 6
    return cells, x - 1


def runs(cells):
    """merge horizontally adjacent cells into (x, y, w) runs"""
    by_row = {}
    for x, y in cells:
        by_row.setdefault(y, []).append(x)
    out = []
    for y, xs in sorted(by_row.items()):
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
                continue
            out.append((start, y, prev - start + 1))
            start = prev = x
        out.append((start, y, prev - start + 1))
    return out


def path_d(cells, dx=0, dy=0):
    return ' '.join('M%g %gh%gv1h-%gz' % (x + dx, y + dy, w, w) for x, y, w in runs(cells))


def write(path, data, mode='w'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf8'})) as f:
        f.write(data)
    print('  wrote', os.path.relpath(path, ROOT))


BOLT_CELLS = [(x, y) for y in range(BH) for x in range(BW) if bolt_has(x, y)]


# ============================== SVG assets ================================================
def svg_logos():
    d = path_d(BOLT_CELLS)
    # compact logo, tinted by the app through currentColor (square box, 1 cell margin)
    compact = ('<svg width="80" height="80" viewBox="-1 -1 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" '
               'shape-rendering="crispEdges">\n<path d="%s" fill="currentColor"/>\n</svg>\n' % d)
    write(os.path.join(ASSETS, 'icons', 'icon-logo.svg'), compact)
    # pixel-theme variant: the app swaps to icons/pixel/* and snaps to the viewBox width
    pixel = ('<svg width="24" height="24" viewBox="-1 -1 16 16" fill="currentColor" xmlns="http://www.w3.org/2000/svg" '
             'shape-rendering="crispEdges"><path d="%s"/></svg>' % d)
    write(os.path.join(ASSETS, 'icons', 'pixel', 'icon-logo.svg'), pixel)

    cells, w = text_cells('RAY LAUNCHER')
    word = ('<svg width="%d" height="14" viewBox="0 0 %d 7" fill="none" xmlns="http://www.w3.org/2000/svg" '
            'shape-rendering="crispEdges">\n<path d="%s" fill="currentColor"/>\n</svg>\n' % (w * 2, w, path_d(cells)))
    write(os.path.join(ASSETS, 'logo.svg'), word)

    # layered mark for the macOS Icon Composer bundle (flat colors, the OS adds the glass)
    layers = []
    for (x, y) in BOLT_CELLS:
        col = ACCENT
        if not bolt_has(x, y - 1) or not bolt_has(x - 1, y):
            col = ACC_LIGHT
        if not bolt_has(x, y + 1) or not bolt_has(x + 1, y):
            col = ACC_DARK if col == ACCENT else col
        layers.append((col, x, y))
    body = []
    for col in (ACC_DARK, ACCENT, ACC_LIGHT):
        cs = [(x, y) for c, x, y in layers if c == col]
        if cs:
            body.append('<path d="%s" fill="%s"/>' % (path_d(cs), hexc(col)))
    mark = ('<svg width="175" height="188" viewBox="0 0 %d %d" fill="none" xmlns="http://www.w3.org/2000/svg" '
            'shape-rendering="crispEdges">\n%s\n</svg>\n' % (BW, BH, '\n'.join(body)))
    write(os.path.join(ICONS, 'RayLauncher.icon', 'Assets', 'rayclient-mark.svg'), mark)


def read_pixel_icon(name):
    s = open(os.path.join(ASSETS, 'icons', 'pixel', name + '.svg'), encoding='utf8').read()
    return re.findall(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"/>', s)


def pixel_rects(rects, fill, ox, oy, scale):
    return '<g fill="%s" transform="translate(%g %g) scale(%g)">%s</g>' % (
        fill, ox, oy, scale, ''.join('<rect x="%s" y="%s" width="%s" height="%s"/>' % r for r in rects))


TILE_OUTER = 'M4 0H60V4H64V60H60V64H4V60H0V4H4Z'
TILE_INNER = 'M5 2H59V5H62V59H59V62H5V59H2V5H5Z'


def illustration(name, icon, bolt_hero=False):
    stars = [(8, 9), (52, 8), (11, 50), (55, 47), (47, 14), (14, 18), (50, 55), (9, 30), (56, 28)]
    parts = [
        '<path d="%s" fill="%s"/>' % (TILE_OUTER, hexc(STROKE)),
        '<path d="%s" fill="%s"/>' % (TILE_INNER, hexc(CARD)),
        '<rect x="5" y="2" width="54" height="1" fill="%s"/>' % hexc(HOVER),
        '<rect x="5" y="59" width="54" height="3" fill="%s"/>' % hexc(PANEL),
    ]
    for i, (x, y) in enumerate(stars):
        parts.append('<rect x="%d" y="%d" width="1" height="1" fill="%s"/>' % (x, y, hexc(DIM if i % 3 == 0 else MUTE)))
    if bolt_hero:
        ox, oy, sc = 11, 9, 3
        sh = pixel_rects([(x, y, 1, 1) for x, y in BOLT_CELLS], hexc(BG_DEEP), ox + 1.5, oy + 1.5, sc)
        lt = pixel_rects([(x, y, 1, 1) for x, y in BOLT_CELLS], hexc(ACC_LIGHT), ox - 0.5, oy - 0.5, sc)
        mn = pixel_rects([(x, y, 1, 1) for x, y in BOLT_CELLS], hexc(ACCENT), ox, oy, sc)
        parts += [sh, lt, mn]
        for (sx, sy) in [(8, 12), (53, 40), (50, 10)]:
            parts.append('<path d="M%d %dh3v1h-3zM%d %dh1v3h-1zM%d %dh1v3h-1z" fill="%s"/>' % (
                sx - 1, sy + 1, sx, sy - 1, sx, sy + 1, hexc(YELLOW)))
    else:
        rects = read_pixel_icon(icon)
        parts += [pixel_rects(rects, hexc(BG_DEEP), 17.5, 17.5, 3),
                  pixel_rects(rects, hexc(ACC_LIGHT), 15.5, 15.5, 3),
                  pixel_rects(rects, hexc(ACCENT), 16, 16, 3)]
        parts.append('<path d="M50 9h3v1h-3zM51 8h1v3h-1z" fill="%s"/>' % hexc(YELLOW))
    svg = ('<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" '
           'shape-rendering="crispEdges">\n%s\n</svg>\n' % '\n'.join(parts))
    write(os.path.join(ASSETS, 'icons', 'onboarding-%s.svg' % name), svg)


def svg_illustrations():
    illustration('account', 'users-01')
    illustration('language', 'globe-01')
    illustration('folder', 'folder')
    illustration('migration', 'folder-download')
    illustration('terms', 'clipboard-check')
    illustration('preferences', 'sliders-04')
    illustration('complete', None, bolt_hero=True)


# ============================== raster helpers ============================================
def draw_bolt(draw, ox, oy, cell, base=ACCENT, light=ACC_LIGHT, dark=ACC_DARK):
    t = max(1, cell // 6)
    for (x, y) in BOLT_CELLS:
        x0, y0 = ox + x * cell, oy + y * cell
        draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=base)
        if not bolt_has(x, y - 1):
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + t - 1], fill=light)
        if not bolt_has(x - 1, y):
            draw.rectangle([x0, y0, x0 + t - 1, y0 + cell - 1], fill=light)
        if not bolt_has(x, y + 1):
            draw.rectangle([x0, y0 + cell - t, x0 + cell - 1, y0 + cell - 1], fill=dark)
        if not bolt_has(x + 1, y):
            draw.rectangle([x0 + cell - t, y0, x0 + cell - 1, y0 + cell - 1], fill=dark)


def vgradient(size, stops):
    """stops = [(t, (r,g,b)), ...] top to bottom"""
    w, h = size
    img = Image.new('RGB', size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / max(1e-9, t1 - t0)
                col = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
        else:
            col = stops[-1][1]
        for x in range(w):
            px[x, y] = col
    return img


def night_scene(w, h, seed=7):
    """a navy voxel night: stars, pixel moon, blocky ridges, a lake and a soft glow"""
    rnd = random.Random(seed)
    s = h / 900.0
    img = vgradient((w, h), [(0, (4, 6, 15)), (0.42, (10, 18, 44)), (0.66, (30, 62, 132)), (1, (8, 12, 28))]).convert('RGBA')

    def blend(draw_fn, blur=0):
        """draw translucent shapes on their own layer, then composite (PIL overwrites alpha otherwise)"""
        nonlocal img
        layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer))
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        img = Image.alpha_composite(img, layer)

    # glow behind the horizon
    blend(lambda g: g.ellipse([w * 0.12, h * 0.46, w * 0.88, h * 1.0], fill=(70, 125, 245, 150)), blur=h * 0.09)

    # stars
    def stars(g):
        for _ in range(int(260 * w / 1600)):
            x, y = rnd.randrange(w), int(rnd.random() ** 1.6 * h * 0.62)
            sz = rnd.choice([2, 2, 2, 3, 4]) * max(1, round(s))
            g.rectangle([x, y, x + sz - 1, y + sz - 1], fill=(200, 215, 255, rnd.randint(70, 230)))
        for _ in range(int(14 * w / 1600)):
            x, y = rnd.randrange(w), int(rnd.random() * h * 0.45)
            c = max(2, round(3 * s))
            g.rectangle([x, y, x + c - 1, y + c - 1], fill=(235, 242, 255, 255))
            for dx, dy in ((-c, 0), (c, 0), (0, -c), (0, c)):
                g.rectangle([x + dx, y + dy, x + dx + c - 1, y + dy + c - 1], fill=(200, 215, 255, 110))
    blend(stars)

    # pixel moon with a soft halo
    mc = max(6, round(12 * s))
    mx, my = int(w * 0.80), int(h * 0.15)
    blend(lambda g: g.rectangle([mx - mc, my - mc, mx + 11 * mc, my + 11 * mc], fill=(120, 160, 255, 85)), blur=mc * 3)
    shape = ['..XXXXXX..', '.XXXXXXXX.', 'XXXXXXXXXX', 'XXXXXXXXXX', 'XXXXXXXXXX',
             'XXXXXXXXXX', 'XXXXXXXXXX', 'XXXXXXXXXX', '.XXXXXXXX.', '..XXXXXX..']
    craters = {(2, 2), (3, 2), (6, 4), (7, 4), (6, 5), (3, 7), (4, 7), (7, 7)}
    d = ImageDraw.Draw(img)
    for r, row in enumerate(shape):
        for c, ch in enumerate(row):
            if ch == 'X':
                col = (176, 190, 226, 255) if (c, r) in craters else (226, 234, 255, 255)
                d.rectangle([mx + c * mc, my + r * mc, mx + (c + 1) * mc - 1, my + (r + 1) * mc - 1], fill=col)

    # blocky clouds (very faint)
    cc = max(8, round(22 * s))

    def clouds(g):
        for _ in range(int(6 * w / 1600) + 2):
            cx, cy = rnd.randrange(-100, w), rnd.randint(int(h * 0.12), int(h * 0.40))
            for r in range(rnd.randint(1, 2)):
                for k in range(rnd.randint(4, 9)):
                    g.rectangle([cx + k * cc, cy + r * cc, cx + (k + 1) * cc - 1, cy + (r + 1) * cc - 1],
                                fill=(130, 165, 240, 22))
    blend(clouds)

    # voxel ridges, far to near; a sloping random walk so they read as mountains
    layers = [(int(h * 0.60), 34 * s, (22, 40, 92), 0.30), (int(h * 0.70), 26 * s, (13, 24, 60), 0.26),
              (int(h * 0.82), 20 * s, (8, 14, 36), 0.20)]
    d = ImageDraw.Draw(img)
    for base, colw, col, amp in layers:
        colw = max(6, int(colw))
        hgt, slope, x = base, 0, 0
        lo, hi = base - h * amp, base + h * 0.03
        while x < w:
            slope = max(-3, min(3, slope + rnd.choice([-1, 0, 0, 1])))
            hgt += slope * colw * 0.5
            if hgt < lo or hgt > hi:
                slope = -slope
                hgt = min(max(hgt, lo), hi)
            top = int(hgt // colw * colw)
            d.rectangle([x, top, x + colw - 1, h], fill=col + (255,))
            d.rectangle([x, top, x + colw - 1, top + max(2, colw // 7) - 1],
                        fill=tuple(min(255, v + 30) for v in col) + (255,))
            x += colw

    # lake band with pixel ripples
    ly = int(h * 0.80)

    def ripples(g):
        for _ in range(int(70 * w / 1600)):
            x, y = rnd.randrange(w), rnd.randint(ly, ly + int(h * 0.05))
            g.rectangle([x, y, x + rnd.randint(14, 60), y + max(1, round(2 * s))], fill=(90, 150, 255, rnd.randint(30, 90)))
    blend(ripples)

    # vignette
    vig = Image.new('L', (w, h), 0)
    ImageDraw.Draw(vig).ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(h * 0.12))
    dark = Image.new('RGBA', (w, h), (2, 3, 8, 255))
    return Image.composite(img, dark, vig.point(lambda v: 90 + v * 165 // 255)).convert('RGB')


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


# ============================== PNG / ICO / ICNS ==========================================
def icon_master(S=1024):
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    m = int(S * 0.045)
    tile = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    grad = vgradient((S, S), [(0, PANEL_TOP), (0.55, PANEL), (1, BG_DEEP)]).convert('RGBA')
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([m, m, S - m - 1, S - m - 1], radius=int(S * 0.20), fill=255)
    tile.paste(grad, (0, 0), mask)
    td = ImageDraw.Draw(tile)
    bw = max(2, S // 170)
    td.rounded_rectangle([m, m, S - m - 1, S - m - 1], radius=int(S * 0.20), outline=STROKE + (255,), width=bw)
    td.rounded_rectangle([m + bw, m + bw, S - m - bw - 1, S - m - bw - 1], radius=int(S * 0.20) - bw,
                         outline=(255, 255, 255, 14), width=max(1, bw // 2))
    rnd = random.Random(3)
    for _ in range(16):
        x, y = rnd.randint(m * 3, S - m * 3), rnd.randint(m * 3, S - m * 3)
        sz = max(2, S // 170)
        td.rectangle([x, y, x + sz, y + sz], fill=MUTE + (150,))
    img = Image.alpha_composite(img, tile)

    cell = S // 26
    ox, oy = (S - BW * cell) // 2, (S - BH * cell) // 2
    glow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (x, y) in BOLT_CELLS:
        gd.rectangle([ox + x * cell, oy + y * cell, ox + (x + 1) * cell, oy + (y + 1) * cell], fill=ACCENT + (170,))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.035))
    img = Image.alpha_composite(img, glow)
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw_bolt(ImageDraw.Draw(sh), ox + cell // 3, oy + cell // 3, cell, base=(0, 0, 0, 120), light=(0, 0, 0, 120), dark=(0, 0, 0, 120))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(S * 0.004)))
    draw_bolt(ImageDraw.Draw(img), ox, oy, cell)
    return img


def tray_icon():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cell = 4
    for (x, y) in BOLT_CELLS:
        d.rectangle([4 + x * cell, 2 + y * cell, 4 + (x + 1) * cell - 1, 2 + (y + 1) * cell - 1], fill=(255, 255, 255, 255))
    return img


def raster_icons():
    master = icon_master(1024)
    for name, size in (('32x32.png', 32), ('64x64.png', 64), ('128x128.png', 128), ('128x128@2x.png', 256),
                       ('512x512.png', 512), ('icon.png', 512), ('StoreLogo.png', 50)):
        p = os.path.join(ICONS, name)
        master.resize((size, size), Image.LANCZOS).save(p)
        print('  wrote', os.path.relpath(p, ROOT))
    tray_icon().save(os.path.join(ICONS, 'tray.png'))
    print('  wrote', os.path.relpath(os.path.join(ICONS, 'tray.png'), ROOT))
    ico = os.path.join(ICONS, 'icon.ico')
    master.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('  wrote', os.path.relpath(ico, ROOT))
    icns = os.path.join(ICONS, 'icon.icns')
    master.save(icns, format='ICNS')
    print('  wrote', os.path.relpath(icns, ROOT))


# ============================== backgrounds / banner / dmg ================================
def home_background():
    img = night_scene(1600, 900, seed=7)
    p = os.path.join(ASSETS, 'backgrounds', 'RayNight.jpg')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p, quality=90, optimize=True)
    print('  wrote', os.path.relpath(p, ROOT))


def repo_banner():
    W, H = 3000, 1000
    img = night_scene(W, H, seed=11).convert('RGBA')
    shade = Image.new('RGBA', (W, H), (4, 6, 14, 120))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    cell = 30
    f = font(190)
    title = 'RAY LAUNCHER'
    tw = d.textlength(title, font=f)
    gap = 90
    total = BW * cell + gap + tw
    x0 = (W - total) / 2
    oy = (H - BH * cell) // 2 - 40
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (x, y) in BOLT_CELLS:
        gd.rectangle([x0 + x * cell, oy + y * cell, x0 + (x + 1) * cell, oy + (y + 1) * cell], fill=ACCENT + (190,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(img)
    draw_bolt(d, int(x0), oy, cell)
    tx = x0 + BW * cell + gap
    ty = H / 2 - 140
    d.text((tx + 8, ty + 8), title, font=f, fill=(0, 0, 0, 160))
    d.text((tx, ty), title, font=f, fill=TEXT)
    d.text((tx + 6, ty + 215), 'Dark-blue, Minecraft-styled launcher for Ray Client', font=font(54), fill=DIM)
    p = os.path.join(ROOT, '.github', 'media', 'RepoBanner.png')
    img.convert('RGB').save(p, optimize=True)
    print('  wrote', os.path.relpath(p, ROOT))


def dmg_backgrounds():
    def render(scale):
        W, H = 600 * scale, 400 * scale
        img = vgradient((W, H), [(0, PANEL_TOP), (1, BG_DEEP)]).convert('RGBA')
        d = ImageDraw.Draw(img, 'RGBA')
        rnd = random.Random(5)
        for _ in range(60):
            x, y = rnd.randrange(W), rnd.randrange(H)
            d.rectangle([x, y, x + scale, y + scale], fill=(200, 215, 255, rnd.randint(40, 160)))
        f = font(30 * scale)
        t = 'Ray Launcher'
        d.text(((W - d.textlength(t, font=f)) / 2, 36 * scale), t, font=f, fill=TEXT)
        f2 = font(14 * scale)
        t2 = 'Drag Ray Launcher into Applications'
        d.text(((W - d.textlength(t2, font=f2)) / 2, 340 * scale), t2, font=f2, fill=DIM)
        # pixel arrow between the app (x=160) and Applications (x=440) drop targets, centred on y=190
        c = 5 * scale
        ay = 190 * scale
        ax = 250 * scale
        for i in range(10):
            d.rectangle([ax + i * c, ay - c // 2, ax + (i + 1) * c - 1, ay + c // 2], fill=ACCENT)
        for i in range(4):
            d.rectangle([ax + 10 * c + i * c, ay - (3 - i) * c - c // 2, ax + 10 * c + (i + 1) * c - 1, ay + (3 - i) * c + c // 2], fill=ACCENT)
        return img.convert('RGB')
    one, two = render(1), render(2)
    base = os.path.join(APP, 'distribution')
    one.save(os.path.join(base, 'dmg-background.png'))
    two.save(os.path.join(base, 'dmg-background@2x.png'))
    two.save(os.path.join(base, 'dmg-background.tiff'), dpi=(144, 144))
    print('  wrote packages/rayclient_app/distribution/dmg-background{.png,@2x.png,.tiff}')


if __name__ == '__main__':
    print('SVG logos');          svg_logos()
    print('illustrations');      svg_illustrations()
    print('raster icons');       raster_icons()
    print('home background');    home_background()
    print('repo banner');        repo_banner()
    print('dmg backgrounds');    dmg_backgrounds()
    print('done')
