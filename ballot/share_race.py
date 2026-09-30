"""
ballot/share_race.py - a share page for every race with an official list (r/<race>.html beside the ballot page) and its
1200 by 630 preview image (og/r/<race>.png), drawn in the site's own type and colours (share_cards.py): the race and
its day, each candidate on the list with their party's colour, who holds the seat today, and the district picked out
on its state. A pasted link shows the card; a person who follows it lands on the race. Images are redrawn only when
what they show has changed. Where a state drew new lines for 2026, the state is drawn plain, as on the page.
"""

import hashlib
import html
import json
import os

from PIL import Image

import share_cards as sc

BASE = "https://thecivicarchive.github.io/dev/ballot/us"
ORD = lambda n: f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
COLOR = {"D": sc.DEM, "R": sc.REP}


def decode(rings, q):
    out = []
    for ring in rings:
        x = y = 0
        pts = []
        for i in range(0, len(ring), 2):
            x += ring[i]
            y += ring[i + 1]
            pts.append((x / q, y / q))
        out.append(pts)
    return out


def draw_race(inp, state_rings, dist_rings):
    im, d = sc.base_canvas()
    sc.brand(d)
    d.text((60, 104), inp["kick"].upper(), font=sc.font("sans", 22, 700), fill=sc.ACCENT)
    y = 138
    for line in sc.wrap(d, inp["title"], sc.font("serif", 60), 680, 2):
        d.text((60, y), line, font=sc.font("serif", 60), fill=sc.INK)
        y += 66
    d.text((60, y + 6), inp["sub"], font=sc.font("sans", 24), fill=sc.MUTED)
    y += 58
    rows = inp["cands"][:4] if len(inp["cands"]) <= 4 else inp["cands"][:3]      # the fourth line says how many more
    for name, code, party, inc in rows:
        d.rectangle((60, y + 4, 68, y + 46), fill=COLOR.get(code, sc.IND))
        d.text((84, y), name, font=sc.font("sans", 32, 600), fill=sc.INK)
        d.text((84, y + 38), party + (" · serves in this seat today" if inc else ""), font=sc.font("sans", 20), fill=sc.MUTED)      # the type has no star
        y += 72
    if len(inp["cands"]) > len(rows):
        d.text((84, y + 4), f"and {len(inp['cands']) - len(rows)} more on the ballot", font=sc.font("sans", 26, 600), fill=sc.MUTED)
    xs = [p[0] for r in state_rings for p in r]
    ys = [p[1] for r in state_rings for p in r]
    if xs:      # the state, and the district picked out on it
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        bx0, by0, bx1, by1 = 790, 110, 1140, 520
        k = min((bx1 - bx0) / max(1e-6, x1 - x0), (by1 - by0) / max(1e-6, y1 - y0))
        ox, oy = bx0 + ((bx1 - bx0) - (x1 - x0) * k) / 2, by0 + ((by1 - by0) - (y1 - y0) * k) / 2
        tf = lambda r: [(ox + (x - x0) * k, oy + (y - y0) * k) for x, y in r]
        for r in state_rings:
            d.polygon(tf(r), fill=sc.LINE, outline=sc.MUTED)
        for r in dist_rings:
            d.polygon(tf(r), fill=COLOR.get(inp["holder"], sc.ACCENT), outline=sc.INK)
    sc.footer(d)
    return im


def write(folder, boot, say=print):
    """r/, og/r/ and sitemap.xml under the ballot page's folder, for every race with an official list."""
    os.makedirs(os.path.join(folder, "r"), exist_ok=True)
    os.makedirs(os.path.join(folder, "og", "r"), exist_ok=True)
    cache_path = os.path.join(folder, "og", "cards.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    dist = json.load(open(os.path.join(folder, "data", "districts.json"), encoding="utf-8"))
    names, drawn, kept, urls = boot["names"], 0, 0, [BASE + "/"]
    for r in boot["races"]:
        g = r["el"].get("general") or []
        if not g:
            continue
        g = sorted(g, key=lambda c: (c.get("o") if c.get("o") is not None else 1e9, c["n"].split()[-1].lower()))
        st, n = r["st"], int(r["d"] or 0)
        title = f"U.S. Senate, {names[st]}" if r["o"] == "S" else (f"{names[st]}, at large" if n == 0 else f"{names[st]}'s {ORD(n)} District")
        holder = r["h"]
        code = {"Democrat": "D", "Democratic": "D", "Republican": "R"}.get(holder[2], "I") if holder else ""
        sub = "November 3, 2026" + (f" · held today by {holder[1]} ({code})" if holder else " · the seat is vacant")
        cands = [[c["n"], c.get("pc") or "O", c.get("p") or "", bool(c.get("inc"))] for c in g]
        kick = "On The Ballot · " + ("U.S. Senate" if r["o"] == "S" else "U.S. House") + (" · special election" if r.get("sp") else "")
        inp = {"title": title, "sub": sub, "cands": cands, "kick": kick, "holder": code, "v": 3}
        state_rings = sc.rings_of(boot["map"].get(st, ""))
        raw = (dist["states"].get(st) or {}).get(str(n)) if r["o"] == "H" else None
        dist_rings = state_rings if r["o"] == "S" or (r["o"] == "H" and n == 0 and st not in dist["states"]) else (decode(raw, dist.get("q", 50)) if raw else [])
        rel = f"og/r/{r['id']}.png"
        h = hashlib.sha1(json.dumps([inp, len(dist_rings)], sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        if cache.get(rel) == h and os.path.exists(os.path.join(folder, rel)):
            kept += 1
        else:
            im = draw_race(inp, state_rings, dist_rings).quantize(colors=128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
            im.save(os.path.join(folder, rel), optimize=True)
            cache[rel] = h
            drawn += 1
        url = f"{BASE}/r/{r['id']}.html"
        desc = f"{len(cands)} on the November 3, 2026 ballot: " + ", ".join(f"{c[0]} ({c[2]})" for c in cands[:4]) + (" and more" if len(cands) > 4 else "") + \
            ". From the state's official list, with the money behind each campaign."
        body = f"<h1>{html.escape(title)}</h1><p>{html.escape(sub)}</p><p>{html.escape(desc)}</p>"
        with open(os.path.join(folder, "r", r["id"] + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(sc.stub(f"{title}: who is on the ballot", desc, url, f"{BASE}/{rel}", f"../#race={r['id']}", body))
        urls.append(url)
    with open(cache_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cache, fh, indent=0, sort_keys=True)
    with open(os.path.join(folder, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + "".join(f"<url><loc>{html.escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    say(f"    Share pages: {len(urls) - 1} races; {drawn} preview images drawn, {kept} unchanged")
