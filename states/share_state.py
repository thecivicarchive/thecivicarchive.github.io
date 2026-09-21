#!/usr/bin/env python3
"""
states/share_state.py
=====================
Share pages and preview images for a state's pages, the way share_cards.py makes them for the federal side. The
site draws everything on the fly, which the services that build link previews cannot run; so for every member the
build writes a small page whose only job is to carry the preview and send a person straight on:

    m/<id>.html   ->  ../#member=<id>

Each has a 1200 by 630 image in the site's own type and colours: the member's portrait, seat and committees, the
campaign money on file, and where their district sits in the state. og/site.png is the card for the state's
front page: its name and the upper chamber's districts coloured by party. Images are drawn again only when what
they show has changed (a hash of the inputs is kept in og/cards.json).

Everything on a card is a fact from the record; nothing on it describes anyone.
"""

import hashlib
import html
import io
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import share_cards as sc                     # noqa: E402

W, H = sc.W, sc.H
VACANT = "#2A2E36"


def footer(d, line):
    f = sc.font("sans", 22)
    d.text((60, H - 62), line, font=f, fill=sc.MUTED)
    tw = d.textlength(sc.SITE_HOST, font=f)
    d.text((W - 60 - tw, H - 62), sc.SITE_HOST, font=f, fill=sc.ACCENT)


def decode(rings, q):
    out = []
    for ring in rings:
        x = y = 0
        pts = []
        for i in range(0, len(ring) - 1, 2):
            x += ring[i]
            y += ring[i + 1]
            pts.append((x / q, y / q))
        if len(pts) >= 3:
            out.append(pts)
    return out


def draw_districts(im, shapes, q, fills, box, highlight=None, ring_color=None, scale=3):
    """The state's districts inside `box` (x, y, w, h), each filled with fills[name]; drawn large and brought down
    in size so the edges are smooth. A highlighted district too small to see gets a ring around it."""
    bx, by, bw, bh = box
    decoded = {name: decode(r, q) for name, r in shapes.items()}
    xs = [p[0] for rs in decoded.values() for r in rs for p in r]
    ys = [p[1] for rs in decoded.values() for r in rs for p in r]
    if not xs:
        return
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    k = min(bw / (x1 - x0), bh / (y1 - y0))
    ox, oy = bx + (bw - (x1 - x0) * k) / 2, by + (bh - (y1 - y0) * k) / 2
    big = Image.new("RGB", (int(bw * scale), int(bh * scale)), sc.BG)
    bd = ImageDraw.Draw(big)
    place = lambda p: ((ox - bx + (p[0] - x0) * k) * scale, (oy - by + (p[1] - y0) * k) * scale)
    for name, rs in decoded.items():
        for r in rs:
            bd.polygon([place(p) for p in r], fill=fills.get(name, VACANT), outline=sc.BG)
    small = False
    if highlight and highlight in decoded:
        hx = [p[0] for r in decoded[highlight] for p in r]
        hy = [p[1] for r in decoded[highlight] for p in r]
        small = max(max(hx) - min(hx), max(hy) - min(hy)) * k < 26          # a few city blocks at this size
        if not small:
            for r in decoded[highlight]:
                bd.line([place(p) for p in r] + [place(r[0])], fill=sc.INK, width=scale * 2)
    im.paste(big.resize((int(bw), int(bh)), Image.LANCZOS), (int(bx), int(by)))
    if small:                                                                # too small to see: point it out with a ring
        cx, cy = ox + ((min(hx) + max(hx)) / 2 - x0) * k, oy + ((min(hy) + max(hy)) / 2 - y0) * k
        ImageDraw.Draw(im).ellipse((cx - 20, cy - 20, cx + 20, cy + 20), outline=sc.INK, width=3)


def party_fills(legislators, chamber):
    """District -> colour. A two-member district split between parties gets the colour halfway between theirs."""
    by = {}
    for L in legislators.values():
        if L["ch"] == chamber:
            by.setdefault(L["d"], []).append(sc.party_color(L["p"]))
    return {d: (cs[0] if len(set(cs)) == 1 else sc.mix(cs[0], next(c for c in cs if c != cs[0]), .5)) for d, cs in by.items()}


def draw_site(P, stats, districts, legislators):
    im, d = sc.base_canvas()
    sc.brand(d)
    tf = sc.font("serif", 96)
    d.text((60, 150), f"{P['name']},", font=tf, fill=sc.INK)
    d.text((60, 250), "in plain words.", font=tf, fill=sc.INK)
    f1, f2 = sc.font("sans", 30), sc.font("sans", 26)
    line = (f"All {stats['members']:,} legislators, all {stats['districts']:,} districts on the map, and who funds each campaign." if stats.get("has_money")
            else f"All {stats['members']:,} legislators and all {stats['districts']:,} districts on the map: who represents you, and what they work on.")
    y = 400
    for ln in sc.wrap(d, line, f1, 720, 2):
        d.text((60, y), ln, font=f1, fill=sc.SOFT)
        y += 40
    d.text((60, y + 10), "From public records. No ads, no donors.", font=f2, fill=sc.MUTED)
    if districts.get("upper"):
        draw_districts(im, districts["upper"], districts.get("q", 400), party_fills(legislators, "Senate" if P.get("lower") else "Legislature"), (810, 96, 330, 410))
    footer(d, "Who represents you, and who funds their campaigns" if stats.get("has_money") else "Who represents you, from public records")
    return im


def money_words(n):
    return f"${n:,.0f}"


def month_year(date):
    import datetime as dt
    try:
        return dt.date.fromisoformat((date or "")[:10]).strftime("%B %Y")
    except ValueError:
        return (date or "")[:4]


def member_inputs(P, bio, L, prof, has_photo):
    key = "lower" if L["ch"] == "House" else "upper"                    # a one-chamber legislature files its members under "Legislature"
    ch = P.get(key) or {}
    S, M = prof.get("service") or {}, prof.get("money") or {}
    since = (S.get("since") or "")[:4] or S.get("vague") or ""
    line = f"{L['pn']} · {ch.get('title', 'Member')} for District {L['d']}, {P['name']}" + (f" · in the {ch.get('name', L['ch'])} since {since}" if since else "")
    comms = [c["name"] + (f" ({c['title']})" if c.get("title") else "") for c in (prof.get("committees") or [])]
    money = ""
    if M.get("cycles"):
        total, n = (M.get("sum") or {}).get("all") or [0, 0]
        out = (M.get("outside") or {}).get("all") or [0, 0]
        span = f"{min(M['cycles']) - 1}–{max(M['cycles'])}"
        bits = []
        if n:
            bits.append(f"{money_words(total)} from {n:,} named organization{'' if n == 1 else 's'}")
        if out[0] or out[1]:
            bits.append(f"outside groups spent {money_words(out[0])} to support and {money_words(out[1])} to oppose")
        money = (f"{span}: " + "; ".join(bits) + ".") if bits else ""
    return {"name": L["n"], "party": L["p"], "line": line, "committees": comms, "money": money, "photo": bool(has_photo),
            "chamber": key, "district": L["d"]}


def draw_member(inp, photo_blob, districts, fills, label):
    im, d = sc.base_canvas()
    sc.brand(d)
    sc.pill_right(d, W - 60, 40, label, sc.font("sans", 20), ink=sc.SOFT)
    x, color = 60, sc.party_color(inp["party"])
    if photo_blob:
        try:
            ph = Image.open(io.BytesIO(photo_blob)).convert("RGB")
            side = min(ph.size)
            left, top = (ph.width - side) // 2, max(0, int((ph.height - side) * .12))
            ph = ph.crop((left, top, left + side, top + side)).resize((150, 150), Image.LANCZOS)
            mask = Image.new("L", (450, 450), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 449, 449), fill=255)
            im.paste(ph, (60, 122), mask.resize((150, 150), Image.LANCZOS))
            d.ellipse((53, 115, 217, 279), outline=color, width=4)
            x = 250
        except Exception:                                   # noqa: BLE001  an unreadable portrait: draw the card without it
            x = 60
    shapes = districts.get(inp["chamber"]) or {}
    right = W - 60
    if shapes:
        dim = {k: sc.mix(v, sc.BG, .72) for k, v in fills.items()}       # everyone else's district, quietly; theirs in full colour
        if inp["district"]:
            dim[inp["district"]] = color
        draw_districts(im, shapes, districts.get("q", 400), dim, (W - 60 - 220, 100, 220, 262), highlight=inp["district"] or None, ring_color=color)
        right = W - 60 - 220 - 36
    nf, y = sc.font("serif", 76), 118
    for line in sc.wrap(d, inp["name"], nf, right - x, 2):
        d.text((x, y), line, font=nf, fill=sc.INK)
        y += 80
    sf = sc.font("sans", 28)
    for line in sc.wrap(d, inp["line"], sf, right - x, 3):
        d.text((x, y + 4), line, font=sf, fill=sc.SOFT)
        y += 36
    y = max(y + 26, 384 if shapes else 330)
    lf, tf = sc.font("sans", 19, 700), sc.font("sans", 26)
    for label, text, lines in (("THE TERM", inp.get("term", ""), 2), ("COMMITTEES", " · ".join(inp["committees"]), 1), ("CAMPAIGN MONEY ON FILE", inp["money"], 2)):
        if not text or y > H - 150:
            continue
        d.text((60, y), label, font=lf, fill=sc.MUTED)
        y += 27
        for ln in sc.wrap(d, text, tf, W - 120, lines):
            if y > H - 112:                                  # the footer's line sits at H - 62; leave it air
                break
            d.text((60, y), ln, font=tf, fill=sc.SOFT)
            y += 33
        y += 10
    footer(d, "A statewide office, from public records" if inp.get("official") else
           ("Service, committees and campaign money, from public records" if inp.get("has_money") else "Service and committees, from public records"))
    return im


def original_photo(cache_dir, code, bio):
    """The portrait as the chamber published it, which the people stage keeps; the small copy in the database is
    the fallback."""
    path = os.path.join(cache_dir, "photos", code, bio)
    try:
        return open(path, "rb").read() if os.path.getsize(path) > 0 else None
    except OSError:
        return None


def write_share_pages(folder, P, data, base_url, cache_dir):
    """Write m/, og/ and sitemap.xml under `folder`. Returns a summary dict."""
    base, code = base_url.rstrip("/"), P["code"].lower()
    shutil.rmtree(os.path.join(folder, "m"), ignore_errors=True)
    for sub in ("m", "og/m"):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    cache_path = os.path.join(folder, "og", "cards.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    seen, drawn, kept = set(), 0, 0

    def card(rel, inputs, draw):
        nonlocal drawn, kept
        h = hashlib.sha1(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        path = os.path.join(folder, rel)
        seen.add(rel)
        if cache.get(rel) == h and os.path.exists(path):
            kept += 1
            return
        im = draw().quantize(colors=128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        im.save(path, optimize=True)
        cache[rel] = h
        drawn += 1

    legislators, districts, st = data["legislators"], data["districts"], data["stats"]
    seats = {bio: [L["ch"], L["d"], L["p"]] for bio, L in legislators.items()}
    shape_mark = hashlib.sha1(json.dumps([districts.get("vintage"), len(districts.get("upper", {})), len(districts.get("lower", {}))]).encode()).hexdigest()[:8]
    fills = {"upper": party_fills(legislators, "Senate" if P.get("lower") else "Legislature"), "lower": party_fills(legislators, "House")}
    card("og/site.png", {"name": P["name"], "members": st["members"], "districts": st["districts"], "seats": sorted(seats.values()), "shapes": shape_mark,
                         "money": bool(st.get("has_money")), "v": 1},
         lambda: draw_site(P, st, districts, legislators))
    urls = [base + "/"]
    for bio, L in legislators.items():
        prof = data["profiles"].get(bio) or {}
        blob = original_photo(cache_dir, code, bio) or data["photos"].get(bio)
        inp = member_inputs(P, bio, L, prof, bool(blob))
        inp["has_money"] = bool(st.get("has_money"))
        chamber_mark = sorted(v for v in seats.values() if v[0] == L["ch"])
        card(f"og/m/{bio}.png", dict(inp, shapes=shape_mark, chamber_seats=hashlib.sha1(json.dumps(chamber_mark).encode()).hexdigest()[:8], v=2),
             lambda inp=inp, blob=blob: draw_member(inp, blob, districts, fills[inp["chamber"]], P["legislature"]))
        url, title = f"{base}/m/{bio}.html", f"Get to know {inp['name']}"
        desc = " ".join(x for x in (inp["line"] + ".", ("Committees: " + ", ".join(inp["committees"][:4]) + ".") if inp["committees"] else "",
                                    "Service, committees and who funds the campaign, from public records." if inp["has_money"] else "Service and committees, from public records.") if x)
        body = f"<h1>{html.escape(inp['name'])}</h1><p>{html.escape(inp['line'])}</p><p>{html.escape(desc)}</p>"
        with open(os.path.join(folder, "m", bio + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(sc.stub(title, desc, url, f"{base}/og/m/{bio}.png", f"../#member={bio}", body))
        urls.append(url)
    # statewide officials: the same card, led by the office; the state is drawn plain, since no district is theirs alone
    for O in data.get("officials") or []:
        blob = original_photo(cache_dir, code, O["id"]) or data["photos"].get(O["id"])
        since = (O.get("since") or "")[:4]
        inp = {"name": O["n"], "party": O["p"], "line": f"{O['pn']} \u00b7 {O['office']} of {P['name']}" + (f" \u00b7 since {since}" if since else ""),
               "committees": [], "money": "", "photo": bool(blob), "chamber": "upper", "district": "", "has_money": False, "official": True,
               "term": " ".join(x for x in (f"Runs to {month_year(O.get('until'))}." if O.get("until") else "",
                                            f"The office is next on the ballot in November {O['next']}." if O.get("next") else "") if x)}
        card(f"og/m/{O['id']}.png", dict(inp, shapes=shape_mark, v=2), lambda inp=inp, blob=blob: draw_member(inp, blob, districts, {}, f"State of {P['name']}"))
        url, title = f"{base}/m/{O['id']}.html", f"{O['n']}, {O['office']} of {P['name']}"
        desc = f"{inp['line']}. The office, the term and the record, from public sources."
        body = f"<h1>{html.escape(O['n'])}</h1><p>{html.escape(inp['line'])}</p>"
        with open(os.path.join(folder, "m", O["id"] + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(sc.stub(title, desc, url, f"{base}/og/m/{O['id']}.png", f"../#official={O['id']}", body))
        urls.append(url)
    for rel in [r for r in cache if r not in seen]:             # forget cards that no longer exist
        cache.pop(rel, None)
        try:
            os.remove(os.path.join(folder, rel))
        except OSError:
            pass
    with open(cache_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cache, fh, indent=0, sort_keys=True)
    with open(os.path.join(folder, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + "".join(f"<url><loc>{html.escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    og_bytes = sum(os.path.getsize(os.path.join(folder, r)) for r in seen if os.path.exists(os.path.join(folder, r)))
    return {"member_pages": len(legislators) + len(data.get("officials") or []), "cards_drawn": drawn, "cards_kept": kept, "cards_bytes": og_bytes}
