#!/usr/bin/env python3
"""
brand.py - the one mark of The Civic Archive and the one look of its share cards (John, 2026-10-07: "a really cool
image/thumbnail when it's open in a tab or saved to the bookmark bar, and when people share the link ... something to
really symbolize archive and civic with this too for the image + coloring").

The emblem: a civic hall, pediment over columns, whose columns are books standing on a plinth: the civic building that
is also an archive. Colours are the site's own chrome, never party colours: verdigris (the patina of civic bronze),
brass (the plaque and the label on a spine) and parchment (the paper of the record).

    python brand.py preview <folder>     draws every icon size, the SVG and a sample card into <folder> to look at

Every builder calls into here, so the tab icon, the bookmark icon, the installed-app icon and every page's share image
come from one drawing:
    icon_files(folder)                     writes favicon.ico, icon.svg, icon-32.png, apple-touch-icon.png, icon-192.png,
                                           icon-512.png and icon-512-maskable.png into folder; returns the names written
    site_card(title, lead, line, ...)      a 1200 x 630 share image in the house look
    head_tags(root, base, title, desc)     the <link rel=icon ...> and og:/twitter: tags a page's head needs
"""

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

# the palette: verdigris, brass, parchment, ink. Red and blue are kept for party data and appear nowhere here.
FIELD = "#1E4A41"          # deep verdigris, the icon's ground
VERD = "#2F6B5E"           # the site's verdigris
VERD_INK = "#255A4E"
BRASS = "#C8963A"          # bright brass, for small sizes
BRASS_INK = "#8C6420"
PAPER = "#F6F3EC"          # the site's paper
PARCH = "#F3EBDA"          # the emblem's parchment on the dark field
INK = "#1A1C20"
INK_2 = "#545961"
LINE = "#DDD7CA"

SITE_HOST = "thecivicarchive.github.io"
W, H = 1200, 630

_fonts = {}


def font(kind, size, weight=400):
    key = (kind, size, weight)
    if key not in _fonts:
        if kind == "serif":
            f = ImageFont.truetype(os.path.join(FONTS, "InstrumentSerif-Regular.ttf"), size)
        elif kind == "serif-italic":
            f = ImageFont.truetype(os.path.join(FONTS, "InstrumentSerif-Italic.ttf"), size)
        else:
            f = ImageFont.truetype(os.path.join(FONTS, "InstrumentSans-Variable.ttf"), size)
            try:
                f.set_variation_by_axes([100, weight])
            except Exception:
                pass
        _fonts[key] = f
    return _fonts[key]


# ============================== the emblem ==============================
# Everything is laid out in a unit square (0..1) so the same geometry draws the PNG icons, the SVG and the cards.
# `detail` 0 is for 16 px (three books, no labels), 1 for 32 and 48 (five books), 2 for everything larger (labels,
# the seal in the pediment, the steps of the plinth).

def emblem_shapes(detail=2):
    """[(kind, colour-role, coords)] in unit coordinates, back to front. kind: rect (x0,y0,x1,y1), poly [(x,y)...],
    ellipse (x0,y0,x1,y1). Roles: parch, brass, field."""
    S = []
    # the plinth: two steps
    S.append(("rect", "parch", (0.10, 0.84, 0.90, 0.90)))
    if detail >= 2:
        S.append(("rect", "parch", (0.16, 0.78, 0.84, 0.84)))
    else:
        S.append(("rect", "parch", (0.10, 0.78, 0.90, 0.84)))
    # the books, standing on the plinth as columns: widths vary a little, the way spines do
    top, bottom = 0.40, 0.78
    if detail == 0:
        books = [(0.19, 0.35), (0.40, 0.60), (0.65, 0.81)]
    else:
        books = [(0.17, 0.27), (0.30, 0.42), (0.45, 0.55), (0.58, 0.70), (0.73, 0.83)]
    for i, (x0, x1) in enumerate(books):
        S.append(("rect", "parch", (x0, top + (0.012 if detail >= 2 and i % 2 else 0), x1, bottom)))
        if detail >= 2:
            # a brass label near the head of each spine, as archive volumes carry
            S.append(("rect", "brass", (x0 + 0.012, top + 0.045 + (0.012 if i % 2 else 0), x1 - 0.012, top + 0.085 + (0.012 if i % 2 else 0))))
    # the entablature the books carry
    S.append(("rect", "parch", (0.12, 0.33, 0.88, 0.40)))
    # the pediment, in brass
    S.append(("poly", "brass", [(0.08, 0.33), (0.50, 0.08), (0.92, 0.33)]))
    if detail >= 2:
        # the seal in the tympanum: a parchment disc with a brass centre
        S.append(("ellipse", "parch", (0.445, 0.195, 0.555, 0.305)))
        S.append(("ellipse", "brass", (0.475, 0.225, 0.525, 0.275)))
    return S


def draw_emblem(d, x, y, size, colours, detail=2):
    """Draws the emblem into box (x, y, size, size) with ImageDraw d. colours: {"parch": .., "brass": ..}."""
    px = lambda u: x + u * size
    py = lambda u: y + u * size
    for kind, role, c in emblem_shapes(detail):
        col = colours[role]
        if kind == "rect":
            d.rectangle((px(c[0]), py(c[1]), px(c[2]), py(c[3])), fill=col)
        elif kind == "poly":
            d.polygon([(px(a), py(b)) for a, b in c], fill=col)
        else:
            d.ellipse((px(c[0]), py(c[1]), px(c[2]), py(c[3])), fill=col)


def emblem_svg(size=100, field=True, detail=2, colours=None):
    """The emblem as an SVG document (the vector favicon modern browsers prefer; it is also what a bookmark bar keeps)."""
    colours = colours or {"parch": PARCH, "brass": BRASS}
    n = lambda v: f"{v * size:.2f}".rstrip("0").rstrip(".")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    if field:
        out.append(f'<rect width="{size}" height="{size}" rx="{n(0.22)}" fill="{FIELD}"/>')
    for kind, role, c in emblem_shapes(detail):
        col = colours[role]
        if kind == "rect":
            out.append(f'<rect x="{n(c[0])}" y="{n(c[1])}" width="{n(c[2] - c[0])}" height="{n(c[3] - c[1])}" fill="{col}"/>')
        elif kind == "poly":
            out.append(f'<polygon points="{" ".join(f"{n(a)},{n(b)}" for a, b in c)}" fill="{col}"/>')
        else:
            cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
            out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n((c[2] - c[0]) / 2)}" ry="{n((c[3] - c[1]) / 2)}" fill="{col}"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def draw_icon(size, maskable=False, scale=4):
    """The app and tab icon: the emblem on its verdigris field, rounded unless maskable (which keeps a safe margin).
    Drawn at `scale` times the size and shrunk, so edges are smooth; 16 px gets the plainest drawing."""
    detail = 0 if size <= 16 else (1 if size <= 48 else 2)
    s = size * scale
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if maskable:
        d.rectangle((0, 0, s, s), fill=FIELD)
        m = s * 0.20
    else:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=FIELD)
        m = s * (0.10 if detail == 0 else 0.09)
    draw_emblem(d, m, m, s - 2 * m, {"parch": PARCH, "brass": BRASS}, detail)
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im.convert("RGB") if maskable else im


def icon_files(folder):
    """Writes the whole icon set into folder; returns the file names. The .ico carries 16, 32 and 48, each drawn for
    its own size (a browser tab and a bookmark bar take the 16 or 32)."""
    os.makedirs(folder, exist_ok=True)
    names = []
    for name, size, mask in (("icon-32.png", 32, False), ("apple-touch-icon.png", 180, False), ("icon-192.png", 192, False),
                             ("icon-512.png", 512, False), ("icon-512-maskable.png", 512, True)):
        draw_icon(size, mask).save(os.path.join(folder, name), optimize=True)
        names.append(name)
    # the largest frame first: the ICO writer drops any size bigger than the image it is given
    frames = [draw_icon(s) for s in (48, 32, 16)]
    frames[0].save(os.path.join(folder, "favicon.ico"), format="ICO", sizes=[(48, 48), (32, 32), (16, 16)], append_images=frames[1:])
    names.append("favicon.ico")
    with open(os.path.join(folder, "icon.svg"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(emblem_svg())
    names.append("icon.svg")
    return names


# ============================== the share card ==============================

def paper(w=W, h=H, seed=7):
    """Parchment with a faint grain, the same every time."""
    im = Image.new("RGB", (w, h), PAPER)
    px = im.load()
    rnd = random.Random(seed)
    base = tuple(int(PAPER[i:i + 2], 16) for i in (1, 3, 5))
    for _ in range(w * h // 9):
        x, y = rnd.randrange(w), rnd.randrange(h)
        k = rnd.choice((-5, -4, -3, 3, 4))
        px[x, y] = tuple(max(0, min(255, v + k)) for v in base)
    return im


def wrap(d, text, f, max_w, max_lines):
    words, lines, cur = str(text or "").split(), [], []
    for wd in words:
        if not cur or d.textlength(" ".join(cur + [wd]), font=f) <= max_w:
            cur.append(wd)
        else:
            lines.append(" ".join(cur))
            cur = [wd]
            if len(lines) == max_lines:
                break
    else:
        if cur:
            lines.append(" ".join(cur))
        return lines
    last = lines[-1]
    while last and d.textlength(last + "…", font=f) > max_w:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    lines[-1] = last + "…"
    return lines


def site_card(title, lead, line="", foot="Official records, in plain words. No ads, no donors.", host=SITE_HOST, kicker="The Civic Archive"):
    """A 1200 x 630 share image: the emblem on parchment, the title in the site's serif, a lead in italic verdigris,
    one line of plain facts, a brass rule and the site's address. Every page's card is this drawing with its own words."""
    im = paper()
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 10), fill=BRASS)                      # the brass rule at the head
    d.rectangle((0, H - 14, W, H), fill=VERD)                   # the verdigris band at the foot
    # the words, laid out first so the block can sit in the middle of the card
    x0, right = 430, W - 72
    if kicker and kicker.strip().lower() == title.strip().lower():
        kicker = ""                                             # the home card: the title is the name already
    tf = font("serif", 78 if len(title) <= 22 else 66)
    lf = font("serif-italic", 40)
    sf = font("sans", 27, 450)
    rows = []                                                   # (y offset, text, font, colour)
    y = 0
    if kicker:
        rows.append((y, kicker, font("sans", 24, 650), VERD_INK)); y += 44
    for ln in wrap(d, title, tf, right - x0, 2):
        rows.append((y, ln, tf, INK)); y += int(tf.size * 1.02)
    y += 14
    for ln in wrap(d, lead, lf, right - x0, 2):
        rows.append((y, ln, lf, VERD_INK)); y += int(lf.size * 1.12)
    if line:
        y += 18
        for ln in wrap(d, line, sf, right - x0, 3):
            rows.append((y, ln, sf, INK_2)); y += int(sf.size * 1.3)
    block = y
    top = max(48, (H - 100 - block) // 2)                       # centred between the brass rule and the foot
    for dy, text, f, col in rows:
        d.text((x0, top + dy), text, font=f, fill=col)
    # the emblem, large, drawn straight on the paper in verdigris and brass, its middle on the words' middle
    es = 300
    draw_emblem(d, 72, max(40, int(top + block / 2 - es / 2)), es, {"parch": VERD, "brass": BRASS}, 2)
    # the foot: a brass hairline, then the two lines
    d.rectangle((72, H - 92, W - 72, H - 90), fill=BRASS)
    ff = font("sans", 22, 450)
    d.text((72, H - 72), foot, font=ff, fill=INK_2)
    hw = d.textlength(host, font=font("sans", 22, 600))
    d.text((W - 72 - hw, H - 72), host, font=font("sans", 22, 600), fill=VERD_INK)
    return im


def save_card(im, path):
    """Saves a card small: 96 colours are plenty for flat drawing and type on paper."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.quantize(colors=128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)


# ============================== what a page's head needs ==============================

def head_tags(root, base, title, desc, image, url=None, icons_root=None, theme=True):
    """The icon links and the share tags. `root` is the way from the page to the folder that holds the icons (icon_files
    wrote them there); `base` the absolute address of that folder's site; `image` the card's absolute address. A page
    with a dark look of its own passes theme=False and keeps its own theme colour."""
    import html as H_
    e = lambda s: H_.escape(str(s or ""), quote=True)
    ir = icons_root if icons_root is not None else root
    url = url or base
    return "\n".join([
        f'<link rel="icon" href="{ir}favicon.ico" sizes="16x16 32x32 48x48">',
        f'<link rel="icon" href="{ir}icon.svg" type="image/svg+xml">',
        f'<link rel="apple-touch-icon" href="{ir}apple-touch-icon.png">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="The Civic Archive">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(image)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="The Civic Archive emblem, a hall of books with a brass pediment, beside the words {e(title)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(desc)}">',
        f'<meta name="twitter:image" content="{e(image)}">']
        + ([f'<meta name="theme-color" content="{FIELD}">'] if theme else []))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "preview":
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        names = icon_files(out)
        # zoomed copies of the small sizes, so the drawing can be judged at the size a tab shows it
        for s in (16, 32, 48):
            draw_icon(s).resize((s * 8, s * 8), Image.Resampling.NEAREST).save(os.path.join(out, f"zoom-{s}.png"))
        save_card(site_card("The Civic Archive", "The public record, for everyone.",
                            "Every bill and recorded vote in Congress, the fifty state legislatures, and who is on your November ballot."),
                  os.path.join(out, "card-home.png"))
        save_card(site_card("On The Ballot", "Meet everyone asking for your vote.",
                            "470 races for Congress and every state, county and local race on the November 3, 2026 ballot, from the official lists.",
                            kicker="The Civic Archive · On The Ballot"), os.path.join(out, "card-ballot.png"))
        print("wrote", ", ".join(names), "+ zoom-16/32/48.png, card-home.png, card-ballot.png to", out)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
