#!/usr/bin/env python3
"""Share pages and preview images for the fast site.

When a link to a bill or a vote is pasted into a message or a feed, the
service fetches the page and looks for a title, a description and an image.
The site itself is one page that draws everything on the fly, which those
crawlers cannot run. So for every bill with a full record and every roll
call with member-level votes, the build writes a small page whose only job is
to carry that preview and send a person straight on to the site:

    b/hr1-119.html                    -> ../#bill=hr1-119
    v/hr1-119_H_2025-05-22_145.html   -> ../#vote=hr1-119_H_2025-05-22_145

Each has a 1200 by 630 image drawn in the site's own type and colours: a card
for a bill, or the vote map coloured the way the site colours it. Images are
drawn again only when what they show has changed (a hash of the inputs is
kept in og/cards.json), so a weekly rebuild stays quick and git stays small.

Everything here is derived from the record and says so on the card.
"""
import hashlib
import html
import io
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
W, H = 1200, 630

# the site's dark palette
BG, INK, MUTED, SOFT, LINE = "#0C0E12", "#ECEDE9", "#9BA1A9", "#C9CDD2", "#262A31"
ACCENT = "#4CC5B0"
DEM, REP, IND, NOVOTE, EMPTY = "#7E9BFF", "#FF7B72", "#B49BF2", "#3A3F48", "#20242B"
PASS_BG, PASS_INK, FAIL_BG, FAIL_INK = "#12302B", "#9FE3D6", "#44201D", "#FFB3AC"
SITE_LINE = "Every bill and every recorded vote, from the public record"
SITE_HOST = "thecivicarchive.github.io"

_fonts = {}


def font(kind, size, weight=400):
    key = (kind, size, weight)
    if key not in _fonts:
        if kind == "serif":
            f = ImageFont.truetype(os.path.join(FONTS, "InstrumentSerif-Regular.ttf"), size)
        else:
            f = ImageFont.truetype(os.path.join(FONTS, "InstrumentSans-Variable.ttf"), size)
            try:
                f.set_variation_by_axes([100, weight])
            except Exception:
                pass
        _fonts[key] = f
    return _fonts[key]


def wrap(draw, text, f, max_w, max_lines):
    """Word-wrap `text` to at most `max_lines` lines of `max_w` pixels; the last line gets an ellipsis if cut."""
    words, lines, cur = str(text or "").split(), [], []
    for w in words:
        if not cur or draw.textlength(" ".join(cur + [w]), font=f) <= max_w:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) == max_lines:
                break
    else:
        if cur:
            lines.append(" ".join(cur))
        return lines
    last = lines[-1]
    while last and draw.textlength(last + "…", font=f) > max_w:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    lines[-1] = last + "…"
    return lines


def mix(hex_a, hex_b, t):
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def fmt_date(d):
    import datetime as dt
    try:
        return dt.date.fromisoformat(d[:10]).strftime("%b %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return d or ""


def parse_split(s):
    """'D 36-11, R 50-1' -> [{'p': 'D', 'y': 36, 'n': 11}, ...], Democrats first."""
    out = []
    for m in re.finditer(r"\b([A-Z]+)\s+(\d+)\s*-\s*(\d+)", str(s or "")):
        out.append({"p": m.group(1)[0], "y": int(m.group(2)), "n": int(m.group(3))})
    order = {"D": 0, "I": 1, "R": 2}
    return sorted(out, key=lambda r: order.get(r["p"], 1))


def party_color(p):
    return REP if p == "R" else (DEM if p == "D" else IND)


def party_name(p, n=2):
    base = {"D": "Democrat", "R": "Republican"}.get(p, "Independent")
    return base + ("s" if n != 1 else "")


def passed(result):
    return bool(re.search(r"passed|agreed|invoked|adopted|confirmed", result or "", re.I))


def base_canvas():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 7), fill=ACCENT)
    return im, d


def brand(d, y=46):
    d.text((60, y), "The Civic Archive", font=font("serif", 34), fill=INK)


def footer(d):
    f = font("sans", 22)
    d.text((60, H - 62), SITE_LINE, font=f, fill=MUTED)
    tw = d.textlength(SITE_HOST, font=f)
    d.text((W - 60 - tw, H - 62), SITE_HOST, font=f, fill=ACCENT)


def pill(d, x, y, text, f, fill=None, ink=INK, outline=LINE, pad=(16, 8)):
    tw = d.textlength(text, font=f)
    box = (x, y, x + tw + pad[0] * 2, y + f.size + pad[1] * 2 + 2)
    d.rounded_rectangle(box, radius=999, fill=fill, outline=None if fill else outline, width=2)
    d.text((x + pad[0], y + pad[1]), text, font=f, fill=ink)
    return box


def pill_right(d, right, y, text, f, **kw):
    tw = d.textlength(text, font=f)
    return pill(d, right - tw - 32, y, text, f, **kw)


# --- bills ------------------------------------------------------------------

def status_line(b):
    o, s = b.get("outcome") or "", b.get("status") or ""
    votes = [v for v in (b.get("votes") or []) if v.get("yeas") is not None]
    last = votes[-1] if votes else None
    tally = f" {last['yeas']}–{last['nays']}" if last else ""
    when = fmt_date(b.get("latest_action_date"))
    if "became law" in o:
        return f"Became law · Public Law {b.get('law') or ''} · {when}".replace("  ", " ")
    if o.startswith("Vetoed"):
        return f"Vetoed · {when}"
    if o.startswith("Failed"):
        return f"Failed a floor vote{tally} · {when}"
    if "passed one chamber" in o:
        ch = "the House" if "House" in s else "the Senate"
        return f"Passed {ch}{tally} · {when}"
    if "passed both" in o:
        return f"Passed both chambers, not yet final · {when}"
    if "awaiting" in o:
        return f"Passed both chambers, waiting on the President · {when}"
    cos = (b.get("cosponsors") or {}).get("total") or 0
    who = f" · {cos} cosponsor{'s' if cos != 1 else ''}{', both parties' if b.get('bipartisan') else ''}" if cos else ""
    where = "Reported by committee" if s.startswith("Reported") else ("In committee" if s == "In committee" else "Introduced")
    return f"{where} · {when}{who}"


def bill_inputs(b):
    votes = b.get("votes") or []
    last = next((v for v in reversed(votes) if v.get("split")), None)
    nick, official = b.get("nick") or {}, b.get("short_title") or b.get("title") or ""
    out = {"id": b["id"], "title": nick["name"] if nick.get("lead") else official, "status": status_line(b),
           "split": (last or {}).get("split", ""), "law": b.get("law") or ""}
    if nick:                                   # only present when there is one, so other cards keep their hash
        out["aka"] = ("officially " + official) if nick.get("lead") else ("commonly called " + nick["name"])
    return out


def draw_bill(inp):
    im, d = base_canvas()
    brand(d)
    pill_right(d, W - 60, 40, inp["id"], font("sans", 26, 600))
    y = 130
    tf = font("serif", 66)
    for line in wrap(d, inp["title"], tf, W - 120, 3):
        d.text((60, y), line, font=tf, fill=INK)
        y += 76
    if inp.get("aka"):
        af = font("sans", 26)
        d.text((60, y + 8), wrap(d, inp["aka"], af, W - 120, 1)[0], font=af, fill=MUTED)
        y += 44
    y += 16
    d.text((60, y), inp["status"], font=font("sans", 30), fill=SOFT)
    y += 66
    rows = parse_split(inp["split"])
    if rows:
        total = sum(r["y"] + r["n"] for r in rows) or 1
        x, bar_w = 60, W - 120
        segs = []
        for r in rows:
            c = party_color(r["p"])
            segs.append((r["y"], c))
            segs.append((r["n"], mix(c, BG, .62)))
        for n, c in segs:
            w = bar_w * n / total
            if w > 0:
                d.rectangle((x, y, x + w, y + 22), fill=c)
            x += w
        y += 36
        text = " · ".join(f"{party_name(r['p'])} {r['y']} yes, {r['n']} no" for r in rows)
        d.text((60, y), text, font=font("sans", 24), fill=MUTED)
    footer(d)
    return im


# --- votes ------------------------------------------------------------------

def rings_of(path_d):
    """'M x,y L x,y ... Z M ... Z' -> list of point lists."""
    out = []
    for ring in path_d.split("M"):
        ring = ring.strip().rstrip("Z")
        if not ring:
            continue
        pts = []
        for pair in ring.split("L"):
            x, y = pair.split(",")
            pts.append((float(x), float(y)))
        if len(pts) >= 3:
            out.append(pts)
    return out


def members_by_state(v, mv, leg):
    C = mv.get("S" if v["chamber"] == "Senate" else "H") or {"ids": [], "votes": {}}
    s, po, out = C["votes"].get(v["vote_id"], ""), v.get("po") or {}, {}
    for i, pos in enumerate(s):
        if pos == ".":
            continue
        L = leg.get(C["ids"][i])
        if not L:
            continue
        out.setdefault(L["st"], []).append((pos, po.get(str(i)) or L["p"] or ""))
    return out


def order_key(m):
    pos, p = m
    base = {"R": 0, "D": 4, "I": 2}.get(p, 2)
    if pos == "Y":
        return base + (1 if p == "D" else 0)
    if pos == "N":
        return base + (0 if p == "D" else 1)
    return base + .5


def fill_for(pos, p):
    if pos in ("X", "P"):
        return NOVOTE
    c = party_color(p)
    return c if pos == "Y" else mix(c, BG, .62)


def draw_map(im, by_state, states, box):
    """Colour each state by its members' positions, in proportional vertical bands, inside `box` (x, y, w, h)."""
    bx, by, bw, bh = box
    sx, sy = bw / 975.0, bh / 610.0
    d = ImageDraw.Draw(im)
    for st, s in states.items():
        rings = [[(bx + x * sx, by + y * sy) for x, y in r] for r in rings_of(s["d"])]
        if not rings:
            continue
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
        mw, mh = max(1, x1 - x0), max(1, y1 - y0)
        mask = Image.new("L", (mw, mh), 0)
        md = ImageDraw.Draw(mask)
        for r in rings:
            md.polygon([(x - x0, y - y0) for x, y in r], fill=255)
        ms = sorted(by_state.get(st, []), key=order_key)
        band = Image.new("RGB", (mw, mh), EMPTY)
        if ms:
            bd = ImageDraw.Draw(band)
            fills = [fill_for(pos, p) for pos, p in ms]
            segs = []
            for f in fills:
                if segs and segs[-1][0] == f:
                    segs[-1][1] += 1
                else:
                    segs.append([f, 1])
            x = 0.0
            for f, n in segs:
                w = mw * n / len(ms)
                bd.rectangle((x, 0, x + w, mh), fill=f)
                x += w
        im.paste(band, (x0, y0), mask)
    for st, s in states.items():
        for r in rings_of(s["d"]):
            d.polygon([(bx + x * sx, by + y * sy) for x, y in r], outline=BG)


def vote_inputs(v, mv, leg):
    by = members_by_state(v, mv, leg)
    return {"vote_id": v["vote_id"], "bill": v["bill"], "title": v.get("title") or "", "chamber": v["chamber"],
            "category": v.get("category") or "", "date": v.get("date") or "", "yeas": v.get("yeas"), "nays": v.get("nays"),
            "result": v.get("result") or "", "split": v.get("split") or "",
            "by": {st: sorted(ms) for st, ms in by.items()}}


def draw_vote(inp, states):
    im, d = base_canvas()
    brand(d)
    # the tally
    y = 78
    big = font("serif", 150)
    yes, no = str(inp["yeas"] if inp["yeas"] is not None else "?"), str(inp["nays"] if inp["nays"] is not None else "?")
    d.text((56, y), yes, font=big, fill=INK)
    x = 56 + d.textlength(yes, font=big)
    d.text((x, y), "–", font=big, fill=MUTED)
    x += d.textlength("–", font=big)
    d.text((x, y), no, font=big, fill=INK)
    ok = passed(inp["result"])
    pill(d, 60, y + 170, inp["result"] or ("Passed" if ok else "Failed"), font("sans", 24, 600),
         fill=PASS_BG if ok else FAIL_BG, ink=PASS_INK if ok else FAIL_INK)
    # the bill
    y = 312
    d.text((60, y), inp["bill"], font=font("sans", 28, 600), fill=INK)
    y += 40
    tf = font("serif", 38)
    for line in wrap(d, inp["title"], tf, 480, 2):
        d.text((60, y), line, font=tf, fill=SOFT)
        y += 42
    y += 6
    d.text((60, y), f"{inp['chamber']} {inp['category'].lower()} · {fmt_date(inp['date'])}", font=font("sans", 24), fill=MUTED)
    y += 32
    rows = parse_split(inp["split"])
    if rows:
        sf = font("sans", 22)
        for line in wrap(d, " · ".join(f"{party_name(r['p'])} {r['y']} yes, {r['n']} no" for r in rows), sf, 480, 2):
            d.text((60, y), line, font=sf, fill=MUTED)
            y += 27
    # the map
    box = (570, 74, 590, 369)
    draw_map(im, inp["by"], states, box)
    d = ImageDraw.Draw(im)
    lf = font("sans", 19)
    lx, ly = 570, 470
    for c, label in ((REP, "Republican yes"), (mix(REP, BG, .62), "no"), (DEM, "Democrat yes"), (mix(DEM, BG, .62), "no"), (NOVOTE, "not voting")):
        d.rounded_rectangle((lx, ly + 3, lx + 16, ly + 19), radius=4, fill=c)
        d.text((lx + 24, ly), label, font=lf, fill=MUTED)
        lx += 24 + d.textlength(label, font=lf) + 22
    nf = font("sans", 18)
    for i, line in enumerate(wrap(d, "Each state is split by its members: Republicans, then independents, then Democrats.", nf, 590, 2)):
        d.text((570, 500 + i * 24), line, font=nf, fill=MUTED)
    footer(d)
    return im


def draw_site(stats):
    im, d = base_canvas()
    brand(d)
    tf = font("serif", 96)
    d.text((60, 150), "Congress,", font=tf, fill=INK)
    d.text((60, 250), "in plain words.", font=tf, fill=INK)
    line = f"{stats.get('measures', 0):,} bills and every recorded vote of the {stats.get('congress_label', '119th Congress')}, member by member."
    d.text((60, 400), line, font=font("sans", 30), fill=SOFT)
    d.text((60, 448), "Facts from the record, ratings with their evidence. No ads, no donors.", font=font("sans", 26), fill=MUTED)
    footer(d)
    return im


# --- members ------------------------------------------------------------------

def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def member_inputs(bio, L, P, state_name, has_photo):
    party = {"R": "Republican", "D": "Democrat"}.get(L.get("p"), "Independent")
    if L.get("ch") == "Senate":
        seat = f"Senator from {state_name}"
    else:
        seat = f"{state_name}'s {ordinal(int(L['d']))} district" if L.get("d") else f"{state_name}, at large"
    S, V = P.get("service") or {}, P.get("votes") or {}
    since = (S.get("since") or "")[:4]
    line = f"{party} \u00b7 {seat}" + (f" \u00b7 in the {S.get('chamber')} since {since}" if since else "")
    chair = next((f"{c['title']}, {c['name']}" for c in (P.get("committees") or []) if c.get("title")), "")
    return {"name": L.get("n") or bio, "party": L.get("p") or "", "line": line, "chair": chair, "photo": bool(has_photo),
            "votes": {k: V.get(k) for k in ("party", "cast", "split_n", "split_with", "missed", "eligible")} if V else {}}


def member_sentence(inp):
    V = inp["votes"]
    if V.get("split_n"):
        side = "Republicans" if V.get("party") == "R" else "Democrats"
        return f"Sided with {side} on {round(100 * V['split_with'] / V['split_n'])}% of the {V['split_n']:,} votes where the two parties split."
    if V.get("eligible"):
        return f"Cast {V.get('cast') or 0:,} recorded votes and missed {V.get('missed') or 0:,} of {V['eligible']:,} roll calls."
    return ""


def draw_member(inp, photo_blob=None):
    im, d = base_canvas()
    brand(d)
    x, color = 60, party_color(inp["party"])
    if photo_blob:
        try:
            ph = Image.open(io.BytesIO(photo_blob)).convert("RGB")
            side = min(ph.size)
            left, top = (ph.width - side) // 2, max(0, int((ph.height - side) * .2))
            ph = ph.crop((left, top, left + side, top + side)).resize((150, 150), Image.LANCZOS)
            mask = Image.new("L", (150, 150), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 149, 149), fill=255)
            im.paste(ph, (60, 122), mask)
            d.ellipse((53, 115, 217, 279), outline=color, width=4)
            x = 250
        except Exception:
            x = 60
    nf, y = font("serif", 76), 118
    for line in wrap(d, inp["name"], nf, W - x - 60, 2):
        d.text((x, y), line, font=nf, fill=INK)
        y += 80
    sf = font("sans", 28)
    for line in wrap(d, inp["line"], sf, W - x - 60, 2):
        d.text((x, y + 4), line, font=sf, fill=SOFT)
        y += 36
    V, y = inp["votes"], max(y + 36, 330)
    if V.get("split_n"):
        pct, big = round(100 * V["split_with"] / V["split_n"]), font("serif", 140)
        side = "Republicans" if V.get("party") == "R" else "Democrats"
        d.text((56, y - 24), f"{pct}%", font=big, fill=color)
        bx, cf = 56 + d.textlength(f"{pct}%", font=big) + 32, font("sans", 30)
        for i, line in enumerate(wrap(d, f"of the {V['split_n']:,} votes where the two parties split, sided with {side}", cf, W - bx - 60, 3)):
            d.text((bx, y + 8 + i * 40), line, font=cf, fill=SOFT)
        d.rounded_rectangle((60, y + 140, W - 60, y + 152), radius=6, fill=LINE)
        d.rounded_rectangle((60, y + 140, 60 + (W - 120) * pct / 100, y + 152), radius=6, fill=color)
        tail = f"Missed {V.get('missed') or 0:,} of {V.get('eligible') or 0:,} roll calls" + (f" \u00b7 {inp['chair']}" if inp["chair"] else "")
        tf = font("sans", 24)
        d.text((60, y + 170), wrap(d, tail, tf, W - 120, 1)[0], font=tf, fill=MUTED)
    else:
        tf = font("sans", 30)
        text = member_sentence(inp) or inp["chair"] or "How they vote and what they work on, from the record."
        for i, line in enumerate(wrap(d, text, tf, W - 120, 3)):
            d.text((60, y + i * 42), line, font=tf, fill=SOFT)
    footer(d)
    return im


# --- pages ------------------------------------------------------------------

def slug(vote_id):
    return vote_id.replace("|", "_")


def stub(title, description, url, image, target, body_html):
    t, dsc, u, i, tg = (html.escape(x, quote=True) for x in (title, description, url, image, target))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — The Civic Archive</title>
<meta name="description" content="{dsc}">
<link rel="canonical" href="{u}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The Civic Archive">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{dsc}">
<meta property="og:url" content="{u}">
<meta property="og:image" content="{i}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{dsc}">
<meta name="twitter:image" content="{i}">
<meta http-equiv="refresh" content="0; url={tg}">
<script>location.replace({json.dumps(target)});</script>
<style>body{{font:17px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;max-width:640px;margin:48px auto;padding:0 20px;color:#15171B}}a{{color:#0F7A6A}}</style>
</head>
<body>
{body_html}
<p><a href="{tg}">Open it on The Civic Archive</a></p>
</body>
</html>
"""


def bill_description(b):
    plain = ((b.get("ratings") or {}).get("plain_language") or {}).get("plain") or {}
    text = plain.get("one_sentence") or b.get("summary") or ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:160].rsplit(" ", 1)[0] + "…"
    st = status_line(b)
    return f"{st}. {text}".strip() if text else f"{st}. Who backed it and how every member voted, from the official record."


def write_share_pages(folder, data, base_url, states, photo_bytes=None):
    """Write b/, v/, og/, sitemap.xml and robots.txt under `folder`. Returns a summary dict."""
    import shutil
    base = base_url.rstrip("/")
    for sub in ("b", "v", "m"):
        shutil.rmtree(os.path.join(folder, sub), ignore_errors=True)
    for sub in ("b", "v", "m", "og/b", "og/v", "og/m"):
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
        im = draw().quantize(colors=96, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        im.save(path, optimize=True)
        cache[rel] = h
        drawn += 1

    urls = [base + "/"]
    card("og/site.png", {"stats": data["stats"], "v": 3}, lambda: draw_site(data["stats"]))
    for b in data["bills"]:
        inp = bill_inputs(b)
        card(f"og/b/{b['key']}.png", dict(inp, v=3), lambda inp=inp: draw_bill(inp))
        url = f"{base}/b/{b['key']}.html"
        title = f"{b['id']}: {inp['title']}"
        body = (f"<h1>{html.escape(inp['title'])}</h1><p><b>{html.escape(b['id'])}</b> · {html.escape(inp['status'])}</p>"
                f"<p>{html.escape(bill_description(b))}</p>")
        with open(os.path.join(folder, "b", b["key"] + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(stub(title, bill_description(b), url, f"{base}/og/b/{b['key']}.png", f"../#bill={b['key']}", body))
        urls.append(url)
    mv, leg = data.get("mv") or {}, data.get("legislators") or {}
    for v in data.get("vote_meta") or []:
        inp = vote_inputs(v, mv, leg)
        sl = slug(v["vote_id"])
        card(f"og/v/{sl}.png", dict(inp, v=4), lambda inp=inp: draw_vote(inp, states))
        url = f"{base}/v/{sl}.html"
        yes, no = v.get("yeas"), v.get("nays")
        title = f"{v['bill']}: {v['chamber']} {v.get('category', '').lower()}, {yes}–{no}"
        desc = (f"How every {v['chamber']} member voted on {v['bill']}, {inp['title']}, on {fmt_date(v.get('date'))}: "
                f"{yes} yes, {no} no, {v.get('result', '')}. State by state, from the official roll call.")
        body = (f"<h1>{html.escape(title)}</h1><p>{html.escape(inp['title'])}</p><p>{html.escape(desc)}</p>")
        with open(os.path.join(folder, "v", sl + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(stub(title, desc, url, f"{base}/og/v/{sl}.png", f"../#vote={sl}", body))
        urls.append(url)
    profiles, photo_bytes, n_members = data.get("_profiles") or {}, photo_bytes or {}, 0
    for bio, L in (data.get("legislators") or {}).items():
        inp = member_inputs(bio, L, profiles.get(bio) or {}, (states.get(L.get("st")) or {}).get("name") or L.get("st") or "", bio in photo_bytes)
        card(f"og/m/{bio}.png", dict(inp, v=1), lambda inp=inp, bio=bio: draw_member(inp, photo_bytes.get(bio)))
        url, title = f"{base}/m/{bio}.html", f"Get to know {inp['name']}"
        desc = " ".join(x for x in (inp["line"] + ".", member_sentence(inp), "Every recorded vote, from the public record.") if x)
        body = f"<h1>{html.escape(inp['name'])}</h1><p>{html.escape(inp['line'])}</p><p>{html.escape(desc)}</p>"
        with open(os.path.join(folder, "m", bio + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(stub(title, desc, url, f"{base}/og/m/{bio}.png", f"../#member={bio}", body))
        urls.append(url)
        n_members += 1
    # forget cards that no longer exist
    for rel in [r for r in cache if r not in seen]:
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
    with open(os.path.join(folder, "robots.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    og_bytes = sum(os.path.getsize(os.path.join(folder, r)) for r in seen if os.path.exists(os.path.join(folder, r)))
    return {"bill_pages": len(data["bills"]), "vote_pages": len(data.get("vote_meta") or []), "member_pages": n_members,
            "cards_drawn": drawn, "cards_kept": kept, "cards_bytes": og_bytes}

# --- the app icon -------------------------------------------------------------

def draw_icon(size, maskable=False):
    """A dome over a plinth, in the site's ink on its dark ground. Maskable icons keep a safe margin."""
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if maskable:
        d.rectangle((0, 0, s, s), fill=BG)
    else:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * .22), fill=BG)
    m = s * (.22 if maskable else .16)          # margin
    cx, w = s / 2, s - 2 * m
    base = s - m - w * .06
    d.rectangle((cx - w / 2, base - w * .10, cx + w / 2, base), fill=INK)            # plinth
    d.rectangle((cx - w * .30, base - w * .34, cx + w * .30, base - w * .10), fill=INK)   # drum
    d.pieslice((cx - w * .30, base - w * .64, cx + w * .30, base - w * .04), 180, 360, fill=INK)  # dome
    d.rectangle((cx - w * .03, base - w * .78, cx + w * .03, base - w * .60), fill=INK)  # finial
    d.rectangle((cx - w / 2, m, cx + w / 2, m + max(2, s * .035)), fill=ACCENT)      # the accent rule the cards carry
    return im.convert("RGB") if maskable else im
