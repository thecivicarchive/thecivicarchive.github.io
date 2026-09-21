#!/usr/bin/env python3
"""
build_state_dev.py
==================
The draft pages for one state legislature, in the same form as the federal draft (build_site_dev.py): a small
shell, and data that arrives when a page needs it.

    python build_state_dev.py --place mn --split site/dev/mn

It reads the state's own database (state_<code>.sqlite), its district file (state_<code>_districts.json) and
states/places.py, and writes index.html, data/*.json, data/member/<id>.json, data/donors/<id>.json and
photos/<id>.webp. It downloads nothing and never touches the federal database.

One look, one code path where it can be shared: the styles and the shared parts of the page (theme, motion,
portraits, sharing, the sortable table, the treemap, the map arithmetic behind "use my location", the changelog
badge and the help window) are taken from the federal page at build time, by the landmarks named in BORROWED.
If the federal page changes so that a landmark can no longer be found, this build stops and says which one;
nothing is guessed. After a change to the federal page's shared parts, look at a state page too.

What a state page shows today: who represents each district, the district map for both chambers, every member's
service, committees and Wikipedia paragraph (fenced off, as on the federal side), and the organizations that fund
their campaigns, with outside spending kept apart. Bills and recorded votes switch on when the bills stage has
loaded them; until then the page says they are coming.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_site_dev import TEMPLATE as FEDERAL, html_attr, read_changelog, state_paths      # noqa: E402
from states.money_views import build_state_money                                            # noqa: E402
from states.places import place                                                             # noqa: E402

# name -> (where the part begins, where it ends) in the federal page. The end landmark is not included.
BORROWED = {
    "CSS": ("<style>", "</style>"),
    "THEME": ("/* ---------- theme ---------- */", "/* ---------- pieces ---------- */"),
    "MOTION": ("/* ---------- motion preference:", "const photo = id =>"),
    "AVATAR": ("const photo = id =>", "const rvIO ="),
    "SHARE": ("const gcq = [];", "const shareTextBill"),
    "TOPBAR": ("/* ---------- top bar follows the dark map section ---------- */", "/* ---------- the chamber floor, in 3D ----------"),
    "ICONS": ("const ICO = {", "const contactRow ="),
    "GRID": ("/* ---------- a table a reader can sort ----------", "/* ---------- money: who gave to the campaign"),
    "MONEYFMT": ("const usd = n =>", "const fecLink ="),
    "SQUARIFY": ("/* a squarified treemap", "/* the member page's money section"),
    "GEO": ("  const conic = (parallels", "  function locate(lon, lat){"),
    "CHANGELOG": ("/* Changelog badge.", "/* Welcome-screen pick lists."),
    "HELP": ("/* Help modal:", "routeFromHash(false);"),
}


def borrow(name):
    start, end = BORROWED[name]
    if FEDERAL.count(start) != 1:
        raise SystemExit(f"build_state_dev: the federal page no longer has exactly one '{start}' (it has {FEDERAL.count(start)}). "
                         f"The state pages borrow the part called {name} from there; update BORROWED in build_state_dev.py to match.")
    i = FEDERAL.index(start)
    j = FEDERAL.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f"build_state_dev: could not find where the federal page's {name} part ends ('{end}'). Update BORROWED in build_state_dev.py.")
    return FEDERAL[i + (len(start) if name == "CSS" else 0):j]


def natural(d):
    m = re.match(r"^(\d+)(.*)$", str(d or ""))
    return (int(m.group(1)), m.group(2)) if m else (10 ** 9, str(d))


def gap_days(a, b):
    try:
        return (dt.date.fromisoformat(b[:10]) - dt.date.fromisoformat(a[:10])).days
    except ValueError:
        return 0


def collect(P, db_path, districts_path):
    """Everything the pages need, from the state's own database and district file."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    if not has("legislators"):
        raise SystemExit(f"No members in {os.path.basename(db_path)} yet. Run: python run_states.py {P['code'].lower()} people")
    key_of = {"Senate": "upper", "House": "lower", "Legislature": "upper"}

    legislators, names = {}, {}
    for m in con.execute("SELECT * FROM legislators WHERE is_current = 1"):
        bio = m["bioguide_id"]
        legislators[bio] = {"n": m["official_full"], "ln": m["last_name"] or "", "p": m["party"] or "I", "pn": m["party_name"] or "", "ch": m["chamber"],
                            "d": m["district"] or "", "f": "", "fq": "", "u": m["url"] or "", "em": m["email"] or "",      # f, fq: set from the seats on file, below
                            "ph": m["phone"] or "", "of": m["office"] or "", "cur": 1}
        names[bio] = {"n": m["official_full"], "first": m["first_name"] or "", "last": m["last_name"] or ""}

    profiles = {bio: {} for bio in legislators}
    if has("member_terms"):
        by = {}
        for t in con.execute("SELECT bioguide_id, type, start, end, district FROM member_terms ORDER BY bioguide_id, seq"):
            by.setdefault(t["bioguide_id"], []).append({"ch": "Senate" if t["type"] == "sen" else "House", "start": t["start"] or "", "end": t["end"] or "", "d": t["district"] or ""})
        unknown = 0
        for bio, ts in by.items():
            if bio not in profiles or not ts:
                continue
            run = [ts[-1]]                                   # the unbroken run of seats in the chamber they sit in now
            for t in reversed(ts[:-1]):
                if t["ch"] != run[0]["ch"] or (t["end"] and run[0]["start"] and gap_days(t["end"], run[0]["start"]) > 45):
                    break
                run.insert(0, t)
            earlier = [t for t in ts if t not in run]
            seat = key_of.get(run[0]["ch"], "upper")
            # The roster does not say when the longest-serving members began: their first seat on file has no start
            # date, or a 1 January date that marks where the file begins, not where the service did. Say only what
            # is known: "before 2023", "2009 or earlier". A year is never invented.
            floor = lambda t: t is ts[0] and (not t["start"] or t["start"][5:10] == "01-01")
            year_from = lambda t: "" if floor(t) else t["start"][:4]
            first, since, vague = run[0], "", ""
            if not floor(first):
                since = first["start"]
            elif first["start"]:
                vague = f"{first['start'][:4]} or earlier"
            else:
                edge = (first["end"] or (run[1]["start"] if len(run) > 1 else ""))[:4]
                vague = f"before {edge}" if edge else ""
            unknown += 0 if since else 1
            legislators[bio]["f"], legislators[bio]["fq"] = since, vague
            profiles[bio]["service"] = {
                "chamber": run[0]["ch"], "since": since, "vague": vague,
                "seats": [{"d": t["d"], "from": year_from(t), "to": t["end"][:4]} for t in run] if len({t["d"] for t in run}) > 1 else [],
                "earlier": [{"ch": t["ch"], "d": t["d"], "from": year_from(t), "to": t["end"][:4]} for t in earlier],
                "next": (P.get(seat) or {}).get("next")}
        if unknown:
            print(f"    service: the roster does not say when {unknown} member(s) began their current service; their pages say 'before <year>' or '<year> or earlier'")

    if has("member_committees"):
        for bio, name, chamber, title in con.execute("SELECT bioguide_id, name, chamber, title FROM member_committees ORDER BY rank"):
            if bio in profiles and name:
                profiles[bio].setdefault("committees", []).append({"name": name, "title": title or "", "ch": chamber or ""})
        for prof in profiles.values():
            if prof.get("committees"):
                prof["committees"].sort(key=lambda c: (not c["title"], c["name"]))

    if has("member_wikipedia"):
        for bio, title, extract, url in con.execute("SELECT bioguide_id, title, extract, url FROM member_wikipedia"):
            if bio in profiles and extract:
                profiles[bio]["wiki"] = {"title": title, "extract": extract, "url": url}

    money = build_state_money(con, {bio: dict(n, **{"n": names[bio]["n"]}) for bio, n in names.items()})
    for bio, m in money["profiles"].items():
        if bio in profiles:
            profiles[bio]["money"] = m

    photos = {}
    if has("photos"):
        for bio, blob in con.execute("SELECT bioguide_id, webp FROM photos WHERE webp IS NOT NULL"):
            if bio in legislators:
                photos[bio] = bytes(blob)

    shapes = json.load(open(districts_path, encoding="utf-8")) if os.path.exists(districts_path) else {"q": 400, "upper": {}, "lower": {}, "vintage": ""}
    outline = state_paths(os.path.join(HERE, "us_states_albers.json")).get(P["code"]) or {"d": "", "bbox": [0, 0, 975, 610]}
    chambers, vacant = {}, {}
    for ch, key in (("Senate", "upper"), ("House", "lower")):
        if not P.get(key):
            continue
        sitting = [L for L in legislators.values() if L["ch"] == ch]
        tally = {}
        for L in sitting:
            t = tally.setdefault(L["pn"] or L["p"], [L["pn"] or L["p"], L["p"], 0])
            t[2] += 1
        held = {L["d"] for L in sitting}
        vacant[key] = sorted((d for d in shapes.get(key, {}) if d not in held), key=natural)
        chambers[key] = {"name": P[key]["name"], "seats": P[key]["seats"], "filled": len(sitting),
                         "parties": sorted(tally.values(), key=lambda t: (-t[2], t[0])), "vacant": vacant[key]}
    seats = {key: sorted(shapes.get(key, {}), key=natural) for key in ("upper", "lower")}
    parties = {}
    for c in chambers.values():
        for label, code, n in c["parties"]:
            parties.setdefault(label, [label, code, 0])[2] += n
    stats = {"members": len(legislators), "districts": sum(len(v) for v in seats.values()), "chambers": chambers,
             "parties": sorted(parties.values(), key=lambda t: (-t[2], t[0])),
             "money": money["summary"], "portraits": len(photos), "wiki": sum(1 for p in profiles.values() if p.get("wiki")),
             "bills": con.execute("SELECT COUNT(*) FROM bills").fetchone()[0] if has("bills") else 0,
             "roll_calls": con.execute("SELECT COUNT(DISTINCT vote_id) FROM member_votes").fetchone()[0] if has("member_votes") else 0}
    for line in money["own_by_name"]:
        print(f"    money: treated as the member's own earlier committee (moved in, not a donor): {line}")
    return {"generated": dt.datetime.now().strftime("%B %d, %Y"), "legislators": legislators, "profiles": profiles, "donors": money["members"],
            "kinds": money["kinds"], "photos": photos, "stats": stats, "seats": seats, "vacant": vacant,
            "districts": {"q": shapes.get("q", 400), "upper": shapes.get("upper", {}), "lower": shapes.get("lower", {}),
                          "vintage": shapes.get("vintage", ""), "outline": {"d": outline["d"], "bbox": outline["bbox"]}},
            "changelog": read_changelog(os.path.join(HERE, "CHANGELOG.md"))}


def money_words(n):
    return f"${n / 1e6:,.1f}M" if n >= 1e6 else (f"${n / 1e3:,.0f}K" if n >= 1e3 else f"${n:,.0f}")


def kpis_html(P, st):
    rows = [f'<div><dd data-count="{st["members"]}">0</dd><dt>sitting legislators</dt></div>']
    for key in ("upper", "lower"):
        c = st["chambers"].get(key)
        if not c:
            continue
        split = "–".join(str(t[2]) for t in c["parties"][:2])
        who = " to ".join(t[0] for t in c["parties"][:2])
        empty = len(c["vacant"]) or max(0, c["seats"] - c["filled"])
        rows.append(f'<div><dd>{split}</dd><dt>{html_attr(c["name"])}: {html_attr(who)}{"; " + ("one seat" if empty == 1 else str(empty) + " seats") + " vacant" if empty else ""}</dt></div>')
    rows.append(f'<div><dd data-count="{st["districts"]}">0</dd><dt>districts on the map</dt></div>')
    m = st.get("money") or {}
    if m.get("from_orgs"):
        rows.append(f'<div><dd>{money_words(m["from_orgs"])}</dd><dt>given by {m["orgs"]:,} named organizations, {m["years"][0]}–{m["years"][1]}</dt></div>')
        rows.append(f'<div><dd>{money_words(m["outside_for"] + m["outside_against"])}</dd><dt>spent by outside groups, kept apart</dt></div>')
    return "\n        ".join(rows)


def render(P, data, version, base_url, analytics):
    st = data["stats"]
    boot = {"version": version, "generated": data["generated"], "base": base_url.rstrip("/"), "analytics": analytics,
            "place": {"code": P["code"], "name": P["name"], "legislature": P["legislature"], "session": P.get("session", ""),
                      "upper": P.get("upper"), "lower": P.get("lower"), "nested": bool(P.get("nested")), "zooms": P.get("zooms") or [],
                      "money_links": P.get("money_links") or {}, "money_agency": P.get("money_agency") or {}},
            "stats": st, "kinds": data["kinds"], "changelog": data["changelog"], "photo_ids": sorted(data["photos"]),
            "has_votes": bool(st["roll_calls"]), "inline": None}
    gc = analytics or ""
    tag = ('<script data-goatcounter="%s" data-goatcounter-settings=\'{"no_onload": true, "allow_frame": false}\' '
           'async src="https://gc.zgo.at/count.js" onload="if(window.__gcflush)__gcflush()"></script>' % html_attr(gc)) if gc else ""
    m = st.get("money") or {}
    foot = (f"Generated from <code>state_{P['code'].lower()}.sqlite</code> on {data['generated']}: {st['members']:,} sitting legislators, "
            f"{st['districts']:,} districts, {st['portraits']:,} portraits"
            + (f", and campaign money {m['years'][0]} through {m['years'][1]} for {m['members']:,} of them" if m.get("members") else "")
            + ". Bills and recorded votes are the next part to be added." + (f" Version {version}." if version else ""))
    if gc:
        foot += " Visits are counted by GoatCounter, which sets no cookies and keeps no personal data."
    name, fit = P["name"], min(1.0, 11.0 / max(1, len(P["name"]) + 1))
    agency = P.get("money_agency") or {}
    page = TEMPLATE
    for k in BORROWED:
        page = page.replace(f"__{k}__", borrow(k))
    payload = json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    both = " and ".join(P[k]["name"] for k in ("upper", "lower") if P.get(k))
    titles = " and one ".join(P[k]["title"].lower() for k in ("upper", "lower") if P.get(k))
    return (page.replace("__EXTRA_CSS__", EXTRA_CSS).replace("__BOOT__", payload).replace("__FOOTNOTE__", foot).replace("__VERSION__", version)
            .replace("__BASE__", base_url.rstrip("/")).replace("__ANALYTICS__", tag).replace("__KPIS__", kpis_html(P, st))
            .replace("__NAME__", html_attr(name)).replace("__LEGISLATURE__", html_attr(P["legislature"])).replace("__SESSION__", html_attr(P.get("session", "")))
            .replace("__CHAMBERS__", html_attr(both)).replace("__TITLES__", html_attr(titles)).replace("__H1FIT__", f"{fit:.2f}")
            .replace("__MEMBERS__", f"{st['members']:,}").replace("__GENERATED__", data["generated"])
            .replace("__VINTAGE__", html_attr(data["districts"].get("vintage") or "Census Bureau cartographic boundary files"))
            .replace("__AGENCY__", html_attr(agency.get("name") or "the state's campaign-finance agency"))
            .replace("__AGENCY_URL__", html_attr(agency.get("url") or "#"))
            .replace("__LEG_URL__", html_attr(P.get("url") or "#")))


def write_site(folder, html, data):
    """index.html plus data/ and photos/ under `folder`. The two subfolders are rebuilt from scratch."""
    folder = os.path.abspath(folder)
    for sub in ("data", "photos"):
        shutil.rmtree(os.path.join(folder, sub), ignore_errors=True)
    for sub in ("data/member", "data/donors", "photos"):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    sizes = {}

    def put(rel, text):
        with open(os.path.join(folder, rel), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        sizes[rel] = len(text.encode("utf-8"))

    put("index.html", html)
    put("data/members.json", dump({"legislators": data["legislators"], "seats": data["seats"], "vacant": data["vacant"]}))
    put("data/districts.json", dump(data["districts"]))
    n = 0
    for bio, prof in data["profiles"].items():
        put(f"data/member/{bio}.json", dump(prof))
        n += 1
    donor_bytes = 0
    for bio, d in data["donors"].items():
        text = dump(d)
        with open(os.path.join(folder, "data", "donors", bio + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        donor_bytes += len(text.encode("utf-8"))
    for bio, blob in data["photos"].items():
        with open(os.path.join(folder, "photos", bio + ".webp"), "wb") as fh:
            fh.write(blob)
    try:
        import share_cards
        share_cards.draw_icon(192, False).save(os.path.join(folder, "icon-192.png"), optimize=True)
    except Exception as e:  # noqa: BLE001
        print(f"    (no tab icon: {e})")
    return sizes, n, donor_bytes, sum(len(b) for b in data["photos"].values())


EXTRA_CSS = r"""
/* ---- only on the state pages ---- */
:root{--m-lobbyists:#F28DB2;--m-cand:#8BD17C;--m-loans:#C5C96A;--m-orgs:#E8B44A;--k-pcf:#F2994A}
.hero h1{font-size:calc(clamp(44px,16.2vw,118px) * var(--fit,1))}
@media (min-width:960px){.hero h1{font-size:calc(clamp(96px,11.2vw,148px) * var(--fit,1))}}
.hero::after{display:none}
.kpis dd{white-space:nowrap}
.herocols{display:grid;gap:26px;grid-template-columns:minmax(0,1fr)}
@media (min-width:960px){.herocols{grid-template-columns:minmax(0,46ch) minmax(0,1fr);gap:40px;align-items:center}}
.heromap{display:block;text-decoration:none;color:var(--muted);font-size:12.5px;text-align:center;animation:rise .9s .7s var(--ease) both}
.heromap[hidden]{display:none}
.heromap svg{display:block;width:100%;height:auto;max-height:430px;margin:0 auto 8px;overflow:visible}
@media (max-width:959px){.heromap svg{max-height:300px}}
.heromap path{stroke:var(--bg);stroke-width:.8;vector-effect:non-scaling-stroke;transition:filter .2s}
html.motion .heromap path{animation:hmin .7s var(--ease) both;animation-delay:calc(var(--i) * 14ms + .4s)}
@keyframes hmin{from{opacity:0}to{opacity:1}}
.heromap:hover path{filter:brightness(1.12)}.heromap:hover .cap{color:var(--ink)}
.heromap .cap::after{content:" \2192"}
.chambers{padding:26px 0 30px}
.chgrid{display:grid;gap:18px;grid-template-columns:1fr;margin-top:24px}
@media (min-width:900px){.chgrid{grid-template-columns:1fr 1fr}}
.chcard{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);padding:20px 22px}
.chcard h3{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}
.chcard h3 span{font-size:13px;font-weight:500;color:var(--muted)}
.chbar{display:flex;height:12px;border-radius:999px;overflow:hidden;background:var(--line);margin:14px 0 8px}
.chbar i{display:block;height:100%}
.chleg{display:flex;gap:6px 16px;flex-wrap:wrap;font-size:13px;color:var(--muted)}
.chleg span{display:inline-flex;align-items:center;gap:6px}.chleg i{width:10px;height:10px;border-radius:3px;display:inline-block}
.chleg b{color:var(--ink);font-weight:600}
.seats{display:flex;flex-wrap:wrap;gap:3px;margin-top:14px}
.seats a{width:11px;height:11px;border-radius:3px;background:var(--pc);display:block;transition:transform .12s}
.seats a:hover,.seats a:focus-visible{transform:scale(1.5);outline:none;box-shadow:0 0 0 2px var(--ink)}
.seats a.vac{background:none;border:1.5px dashed var(--line-strong);pointer-events:none}
.coming{padding:10px 0 60px}
.cgrid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));margin-top:24px}
.ccard{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:18px 20px;font-size:14.5px;line-height:1.55;color:var(--muted)}
.ccard h3{font-size:16px;margin:10px 0 6px;color:var(--ink)}
.ccard .pill.here{background:var(--teal-soft);color:var(--teal-ink)}.ccard .pill.soon{background:var(--amber-soft);color:var(--amber-ink)}
.ccard a{font-weight:600}
.dmapbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.dmapbar .selwrap{flex:1;min-width:200px;height:40px;border-radius:12px}
.dmapbar .selwrap select{width:100%;text-overflow:ellipsis;overflow:hidden;white-space:nowrap;min-width:0}
.dmapbar .chip[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.zoombar{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.zoombar .chip{height:32px}
.zoombar .chip.sq{width:32px;padding:0;justify-content:center;font-size:17px;font-weight:600}
svg.dmap{width:100%;height:auto;display:block;max-height:78vh;border-radius:var(--r-lg);background:radial-gradient(120% 90% at 50% 100%,#151A28 0%,#0E1118 55%,#0A0C11 100%);touch-action:pan-y;cursor:default;user-select:none;-webkit-user-select:none}
svg.dmap.zoomed{cursor:grab;touch-action:none}svg.dmap.grabbing{cursor:grabbing}
svg.dmap path{vector-effect:non-scaling-stroke}
svg.dmap .dd{stroke:#0C0E12;stroke-width:.8;cursor:pointer;transition:filter .15s}
svg.dmap .dd:hover,svg.dmap .dd.hl{stroke:#fff;stroke-width:2;filter:brightness(1.18)}
svg.dmap .dd:focus-visible{outline:none;stroke:#fff;stroke-width:2.5}
svg.dmap .dd.vac{fill:#2A2E36}
svg.dmap .dout{fill:none;stroke:rgba(255,255,255,.55);stroke-width:1.3;pointer-events:none}
svg.dmap .dmine{fill:none;stroke:#E0B040;stroke-width:3;pointer-events:none;filter:drop-shadow(0 0 4px rgba(224,176,64,.7))}
svg.dmap .dsel{fill:none;stroke:#fff;stroke-width:2.6;pointer-events:none}
svg.dmap .dpin path{fill:#E0B040;stroke:#3A2B0D;stroke-width:1.2}svg.dmap .dpin circle{fill:#3A2B0D}
svg.dmap .ycirc{fill:rgba(224,176,64,.20);stroke:#E0B040;stroke-width:1.6;pointer-events:none}
svg.dmap #dlabels{font-family:var(--sans);font-size:12px;font-weight:700;fill:#fff;stroke:rgba(12,14,18,.5);stroke-width:2.2px;paint-order:stroke;stroke-linejoin:round;text-anchor:middle;dominant-baseline:central;pointer-events:none;letter-spacing:.01em}
svg.dmap #dlabels text{vector-effect:none}
.mapside .ymem{width:100%;margin:8px 0}
.mapside .rep-top{justify-content:flex-start;padding-right:0;margin:10px 0 4px}
.mapside .inside{font-size:13.5px;color:var(--muted);margin:12px 0 0;line-height:1.5}
.mapside .inside button{all:unset;cursor:pointer;color:var(--ink);text-decoration:underline;text-underline-offset:2px}
#mpage .rep-top{justify-content:flex-start;padding-right:0;margin:0 0 18px}
.crumbs{margin:0 0 2px;font-size:13.5px}.crumbs a{color:var(--muted);text-decoration:none}.crumbs a:hover{color:var(--ink);text-decoration:underline}
.mapside .side-head>span{display:inline-flex;gap:6px;flex:none}
.roster{margin-top:26px}
.ymem .go{flex:none;font-size:12px;font-weight:600;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.ymem:hover .go{color:var(--ink);border-color:var(--ink)}
.yv-head .muted{font-size:13px}
.srcgrid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));margin-top:28px}
.gt-detail td{background:var(--bg)}
.pays{list-style:none;margin:0;padding:0;display:grid;gap:4px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));font-size:12.5px}
.pays li{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:3px 0}
.pays li span:last-child{color:var(--muted)}
a.chip{text-decoration:none}
"""


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__: The Civic Archive</title>
<meta name="description" content="Who represents every district in the __LEGISLATURE__, what they work on, and which organizations fund their campaigns, from public records.">
<meta name="version" content="__VERSION__">
<link rel="canonical" href="__BASE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Civic Archive">
<meta property="og:title" content="__NAME__, in plain words: The Civic Archive">
<meta property="og:description" content="Who represents every district in the __LEGISLATURE__, what they work on, and which organizations fund their campaigns, from public records.">
<meta property="og:url" content="__BASE__/">
<meta property="og:image" content="__BASE__/og/site.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__NAME__, in plain words: The Civic Archive">
<meta name="twitter:description" content="Who represents every district in the __LEGISLATURE__, what they work on, and which organizations fund their campaigns, from public records.">
<meta name="twitter:image" content="__BASE__/og/site.png">
<link rel="icon" href="icon-192.png" type="image/png">
__ANALYTICS__
<meta name="theme-color" content="#0C0E12">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"dark"}catch(e){document.documentElement.dataset.theme="dark"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>__CSS__</style>
<style>__EXTRA_CSS__</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<a class="skip" href="#yours">Skip to who represents you</a>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../" title="The front door: every level of government" aria-label="Back to the front door of The Civic Archive"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V5l10-2v18"/><path d="M14 6h6v15"/><path d="M2 21h20"/><path d="M10.5 12.5v.01"/></svg><span>All levels</span></a>
    <a class="brand" href="#top" aria-label="The Civic Archive, __NAME__, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections">
      <a href="#home" data-go="home">__NAME__</a><a href="#map" data-go="map">District map</a><a href="#members" data-go="members">Your legislators</a><a href="#sources" data-go="sources">Sources</a>
    </nav>
    <div class="tools">
      <button class="kbtn" id="palettebtn" aria-label="Search legislators and districts"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg><span>Search</span><kbd>⌘K</kbd></button>
      <button class="mtog" id="motion" aria-pressed="true" title="Living portraits and page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="helpbtn" aria-label="How to read this site" title="How to read this site"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.4-2.8 4"/><path d="M12 17.6h.01"/></svg></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>

<div class="page" id="pg-home" data-page="home">
<section class="hero" id="top">
  <div class="wrap">
    <aside class="kpirail" aria-label="Where the __LEGISLATURE__ stands">
      <div class="kpihead"><span class="tag fact">Fact</span><span>The __LEGISLATURE__<br>__SESSION__</span></div>
      <dl class="kpis">
        __KPIS__
      </dl>
      <p class="kpifoot">Counted from public records.<br>Updated __GENERATED__.</p>
    </aside>
    <div class="hero-copy">
      <h1 style="--fit:__H1FIT__" aria-label="__NAME__, in plain words."><span class="h1a">__NAME__,</span> <span class="h1b">in plain words.</span></h1>
      <div class="herocols">
        <div>
          <p class="lede">A state legislature writes much of the law closest to daily life: schools, roads, taxes, health care. Most of what reaches you about it arrives filtered &mdash; as a press release, a mailer, a headline.</p>
          <p class="lede">This place skips the filter. Who represents you, what they work on, and which organizations fund their campaigns, straight from public records &mdash; so you can decide for yourself what you think.</p>
          <div class="cta"><a class="btn primary" href="#yours">Who represents me?</a><a class="btn" href="#map">See the district map</a><a class="btn" href="#members">Browse all __MEMBERS__ legislators</a></div>
          <p class="nosell">No ads. No donors. No take to sell you.</p>
        </div>
        <a class="heromap" id="heromaplink" href="#map" hidden><svg id="heromap" role="img" aria-label="__NAME__'s upper-chamber districts, colored by party"></svg><span class="cap" id="heromapcap"></span></a>
      </div>
    </div>
  </div>
</section>

<section class="yours" id="yours">
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>Who represents you?</h2><p>Everyone in __NAME__ has one state __TITLES__. Find yours with your location, or pick your district if you know it. Your location is worked out on your device and never leaves it.</p></div>
    </div>
    <div class="yours-bar rv" style="--i:1">
      <button class="btn shimmer" id="yloc" type="button">Use my location</button>
      <label class="selwrap"><span id="ysdlab">Senate district</span><select id="ysd" aria-label="Your upper-chamber district"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
      <label class="selwrap"><span id="yhdlab">House district</span><select id="yhd" aria-label="Your lower-chamber district"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
      <span class="muted ynote" id="ynote"></span>
    </div>
    <div class="yours-list" id="ylist" hidden></div>
  </div>
</section>

<section class="chambers" id="chambers">
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>The two chambers</h2><p>Every seat in the __CHAMBERS__, one square each, colored by the party of the member who holds it. Tap a square for the member.</p></div>
    </div>
    <div class="chgrid" id="chgrid"></div>
    <p class="srcnote"><span class="tag fact">Fact</span> Seats and parties from the roster kept by the Open States project, which follows the legislature's own member pages. Parties are named the way __NAME__ names them.</p>
  </div>
</section>

<section class="coming" id="coming">
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>What is here, and what is coming</h2><p>The state side of The Civic Archive is being built in the open, __NAME__ first. It will carry the same record as the federal side.</p></div>
    </div>
    <div class="cgrid">
      <div class="ccard rv"><span class="pill here">Here now</span><h3>Who represents each district</h3>Every sitting member of the __CHAMBERS__, their district on the map, how long they have served and the committees they sit on. <a href="#members">Your legislators</a></div>
      <div class="ccard rv" style="--i:1"><span class="pill here">Here now</span><h3>Who funds each campaign</h3>The organizations that gave to each member's campaigns, from __AGENCY__. People who gave are counted in totals and never named; outside spending is kept apart. Open any member to see it.</div>
      <div class="ccard rv" style="--i:2"><span class="pill soon">Coming next</span><h3>Bills and recorded votes</h3>Every bill since January 2025 and every recorded floor vote, member by member, with the same vote map and the same "how did my members vote" as the federal side.</div>
      <div class="ccard rv" style="--i:3"><span class="pill soon">After that</span><h3>Follow the money, statewide</h3>One searchable list of every organization and the legislators it gave to, as on the federal <a href="../us/#money">Money</a> page.</div>
    </div>
  </div>
</section>
</div><!-- /home -->

<main>
  <div class="page" id="pg-map" data-page="map" hidden>
  <section class="theater block" id="map">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Every district, and who holds it</h2><p>Each district is colored by the party of the member who represents it. Switch between the two chambers, zoom in where the districts are small, and tap a district for its member.</p></div>
      </div>
      <div class="theater-grid">
        <div class="stage rv">
          <div class="mtip" id="mtip" role="tooltip"></div>
          <div class="dmapbar">
            <span id="dchips" role="group" aria-label="Which chamber's districts to show"></span>
            <label class="selwrap"><span class="sr-only">Jump to a district</span><select id="dsel" aria-label="Jump to a district"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
          </div>
          <div class="zoombar" id="zoombar" role="group" aria-label="Zoom the map"></div>
          <div class="mapframe">
            <svg class="dmap" id="dmap" role="img" aria-label="Map of __NAME__'s legislative districts, colored by the party of each district's member"></svg>
          </div>
          <div class="legend2" id="dlegend"></div>
        </div>
        <aside class="mapside rv" id="mapside" aria-live="polite" style="--i:2"><span class="muted">Tap a district to see who represents it.</span></aside>
      </div>
      <p class="note" id="mapnote">District lines: __VINTAGE__. When zoomed in, drag the map to move around.</p>
    </div>
  </section>
  </div><!-- /map -->

  <div class="page" id="pg-members" data-page="members" hidden>
  <section class="block" id="members">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Your legislators</h2><p>Every sitting member of the __LEGISLATURE__. Search by name or district, sort any column, and open a member to get to know them: their service, their committees and who funds their campaigns.</p></div>
      </div>
      <div class="roster rv" style="--i:1">
        <div class="gt-tools" id="rtools">
          <span id="rchips" role="group" aria-label="Narrow the list"></span>
          <label class="grow"><span class="sr-only">Filter by name or district</span><input id="rq" type="search" placeholder="Filter by name or district, for example 45A" autocomplete="off"></label>
        </div>
        <div id="rtable"><p class="muted loading">Loading the members&hellip;</p></div>
        <p class="know-rule" style="margin-top:12px">"In office since" is the start of the member's unbroken service in the chamber they sit in now, from the Open States roster. For some of the longest-serving members the roster does not record when that service began; those say only what it does record, such as "before 2023".</p>
      </div>
    </div>
  </section>
  </div><!-- /members -->

  <div class="page" id="pg-member" data-page="member" hidden>
  <section class="block" id="member">
    <div class="wrap"><div id="mpage"></div></div>
  </section>
  </div><!-- /member -->

  <div class="page" id="pg-sources" data-page="sources" hidden>
  <section class="block" id="sources">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Where this comes from</h2><p>Everything factual on these pages comes from public records, and each part says which. Nothing is edited by hand, and nobody is characterized: the pages show the record and leave the judging to you.</p></div>
      </div>
      <div class="srcgrid">
        <div class="labelcard rv"><span class="tag fact">Fact</span><h3>Members, service and committees</h3><p>The <a href="https://github.com/openstates/people" target="_blank" rel="noopener">Open States people project</a> (public domain), which follows the <a href="__LEG_URL__" target="_blank" rel="noopener">__LEGISLATURE__</a>'s own member pages. Portraits are the official ones the chambers publish.</p></div>
        <div class="labelcard rv" style="--i:1"><span class="tag fact">Fact</span><h3>District lines</h3><p>The U.S. Census Bureau's cartographic boundary files for the upper and lower chamber (__VINTAGE__), drawn on the same map projection as the federal pages. "Use my location" is worked out against these lines on your own device.</p></div>
        <div class="labelcard rv" style="--i:2"><span class="tag fact">Fact</span><h3>Campaign money</h3><p><a href="__AGENCY_URL__" target="_blank" rel="noopener">__AGENCY__</a>'s public downloads: gifts to candidates' committees, and independent spending for or against candidates. Organizations are named; people who gave, lobbyists included, are only ever counted in totals. Outside spending is always shown apart from donations, because the campaign never received it.</p></div>
        <div class="labelcard rv" style="--i:3"><span class="tag wiki">From Wikipedia</span><h3>Life before the legislature</h3><p>One paragraph, the opening of the member's Wikipedia article, fenced off and labelled wherever it appears. It is not an official record, anyone can edit it, and it is credited and linked every time (CC BY-SA 4.0).</p></div>
        <div class="labelcard rv" style="--i:4"><span class="tag analysis">Coming</span><h3>Bills and recorded votes</h3><p>Being added next, from LegiScan's weekly public datasets, which carry every bill and every roll call with each member's vote. When they arrive, each page will credit LegiScan as its terms ask.</p></div>
      </div>
      <p class="note">Found something wrong? The official source decides: every part of a page links to where it came from.</p>
    </div>
  </section>
  </div><!-- /sources -->
</main>

<footer>
  <div class="wrap">
    <div class="fgrid">
      <div class="rv">
        <a class="brand" href="#top"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
        <p>__FOOTNOTE__</p>
        <p><a href="../">All levels of government</a> &middot; <a href="../us/">The federal side</a></p>
      </div>
      <div class="rv" style="--i:1">
        <h4>Sources</h4>
        <ul>
          <li><a href="https://github.com/openstates/people" target="_blank" rel="noopener">Open States people</a>, public domain</li>
          <li><a href="https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html" target="_blank" rel="noopener">Census Bureau</a> district boundaries</li>
          <li><a href="__AGENCY_URL__" target="_blank" rel="noopener">__AGENCY__</a></li>
          <li>Wikipedia, one fenced paragraph per member</li>
        </ul>
      </div>
      <div class="rv" style="--i:2">
        <h4>Method</h4>
        <p>The pages show the record and never describe anyone's character or politics. Donors are organizations only; people are counted in totals and never named. Parties are named the way __NAME__ names them.</p>
      </div>
    </div>
    <p class="fineprint">Motion switch (top bar): on, portraits drift and tilt toward your pointer and the page animates; off, everything holds still. Keyboard: ⌘K or Ctrl+K to search, Esc to close.</p>
  </div>
</footer>
<nav class="tabbar" aria-label="Pages">
  <a href="#home" data-go="home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg><span>Home</span></a>
  <a href="#map" data-go="map"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/></svg><span>Map</span></a>
  <a href="#members" data-go="members"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5a5 5 0 0 1 6 5"/></svg><span>Legislators</span></a>
  <a href="#sources" data-go="sources"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.4-2.8 4"/><path d="M12 17.6h.01"/></svg><span>Sources</span></a>
</nav>
<div class="toast" id="toast" role="status"></div>
<button class="totop" id="totop" aria-label="Back to top"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>

<div class="hmodal" id="help" hidden>
  <div class="hm-back" id="helpback"></div>
  <div class="hm-card" role="dialog" aria-modal="true" aria-labelledby="helptitle">
    <button class="hm-x" id="helpx" aria-label="Close">&times;</button>
    <h2 id="helptitle">How to read this site</h2>
    <p class="hm-lede">Different kinds of claim appear here, and they are never mixed. Every one is labelled wherever it appears &mdash; so you always know whether you are looking at the record or at something worked out from it.</p>
    <div class="hm-grid">
      <div class="labelcard"><span class="tag fact">Fact</span><h3>From the record</h3><p>Members, districts, committees and campaign money, taken straight from public records. If we have it wrong, the official source will say so &mdash; and we link to it every time.</p></div>
      <div class="labelcard"><span class="tag analysis">Analysis</span><h3>Derived, and shown</h3><p>Anything added up or worked out from facts by a stated rule. The rule is always on the page so you can check it yourself.</p></div>
      <div class="labelcard"><span class="tag wiki">From Wikipedia</span><h3>Not an official record</h3><p>One paragraph about a member's life outside the legislature, fenced off, credited and linked. Anyone can edit Wikipedia.</p></div>
    </div>
    <p class="hm-foot">Nothing on this site is edited by hand, and nobody is characterized. The record is shown; the judging is yours.</p>
  </div>
</div>

<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel">
    <span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span>
  </button>
  <div class="cl-panel" id="clpanel" hidden>
    <div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div>
    <div class="cl-body" id="clbody"></div>
  </div>
</div>

<div class="palette" id="palette" hidden>
  <div class="pal-back"></div>
  <div class="pal" role="dialog" aria-modal="true" aria-label="Search legislators and districts">
    <label class="pal-in"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg><input id="palq" type="text" placeholder="Search a legislator's name, or a district like 45A" autocomplete="off" spellcheck="false"><kbd>esc</kbd></label>
    <ul class="pal-list" id="pallist" role="listbox" aria-label="Results"></ul>
    <div class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span></div>
  </div>
</div>

<script>
const BOOT = __BOOT__;
/* Data arrives when a page needs it, exactly as on the federal side: `need(name)` fetches data/<name>.json once
   and caches the promise. */
const P = BOOT.place, CH = {Senate: P.upper, House: P.lower || P.upper, Legislature: P.upper};
const KEYOF = {Senate: "upper", House: "lower", Legislature: "upper"}, CHOF = {upper: "Senate", lower: "House"};
const DATA = {legislators: {}, seats: {upper: [], lower: []}, vacant: {}, districts: null, at: {upper: {}, lower: {}}};
const PHOTO = new Set(BOOT.photo_ids || []);
const DATA_V = encodeURIComponent(BOOT.version || "0");
const loads = {};
let MEMBERS_READY = false;
function need(name){
  if (loads[name]) return loads[name];
  if (BOOT.inline) return loads[name] = Promise.resolve(BOOT.inline[name]);
  return loads[name] = fetch(`data/${name}.json?v=${DATA_V}`).then(r => { if (!r.ok) throw new Error(name + " " + r.status); return r.json(); })
    .catch(e => { delete loads[name]; throw e; });
}
function needMember(id){
  if (BOOT.inline) return Promise.resolve((BOOT.inline.profiles || {})[id] || {});
  const k = "_m_" + id; if (loads[k]) return loads[k];
  return loads[k] = fetch(`data/member/${encodeURIComponent(id)}.json?v=${DATA_V}`).then(r => r.ok ? r.json() : {}).catch(e => { delete loads[k]; throw e; });
}
function needDonors(id){
  if (BOOT.inline) return Promise.resolve(null);
  const k = "donors:" + id; if (loads[k]) return loads[k];
  return loads[k] = fetch(`data/donors/${encodeURIComponent(id)}.json?v=${DATA_V}`).then(r => r.ok ? r.json() : null).catch(e => { delete loads[k]; throw e; });
}
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtDate = d => d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", {year:"numeric", month:"short", day:"numeric"}) : "";
function toast(msg){ const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 2200); }
const store = {get(k){ try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v){ try { localStorage.setItem(k, v); } catch (e) {} }, del(k){ try { localStorage.removeItem(k); } catch (e) {} }};

/* ===== parts shared with the federal page (taken from it when this page is built) ===== */
__THEME__
__MOTION__
__AVATAR__
const SHARE_BASE = BOOT.base || location.href.split("#")[0].replace(/\/[^\/]*$/, "");
__SHARE__
__TOPBAR__
__ICONS__
ICO.map = '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/>';
__GRID__
__MONEYFMT__
__SQUARIFY__
__GEO__
/* ===== end of the shared parts ===== */

const rvIO = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in", "live"); rvIO.unobserve(e.target); } }), {threshold: .12, rootMargin: "0px 0px -6% 0px"});
const reveal = root => $$(".rv:not(.obs)", root || document).forEach(el => { el.classList.add("obs"); rvIO.observe(el); });

/* ---------- members ---------- */
const natural = d => { const m = String(d || "").match(/^(\d+)(.*)$/); return m ? [+m[1], m[2]] : [1e9, String(d)]; };
const byDistrict = (a, b) => { const x = natural(a), y = natural(b); return x[0] - y[0] || x[1].localeCompare(y[1]); };
const tone = p => p === "D" ? "var(--dem)" : (p === "R" ? "var(--rep)" : "var(--plum)");
const chName = ch => (CH[ch] || {}).name || ch;
const seatOf = L => `${(CH[L.ch] || {}).title || "Member"}, District ${L.d}`;
const upperOf = l => P.nested ? String(l).replace(/[A-Za-z]+$/, "") : null;
const lowersOf = u => P.nested ? DATA.seats.lower.filter(l => upperOf(l) === String(u)) : [];
const districtHash = (key, d) => `#district=${key === "upper" ? "S" : "H"}-${encodeURIComponent(d)}`;
function membersReady(){
  if (loads._members) return loads._members;
  return loads._members = need("members").then(M => {
    DATA.legislators = M.legislators || {}; DATA.seats = M.seats || {upper: [], lower: []}; DATA.vacant = M.vacant || {};
    for (const [id, L] of Object.entries(DATA.legislators)) { L.id = id; const k = KEYOF[L.ch]; if (k) DATA.at[k][L.d] = id; }
    MEMBERS_READY = true;
  }).catch(e => { delete loads._members; throw e; });
}
const memberAt = (key, d) => { const id = DATA.at[key][d]; return id ? DATA.legislators[id] : null; };
/* When service began: a year when the roster records one; otherwise only what it supports ("before 2023"). */
const sinceWords = L => L.f ? L.f.slice(0, 4) : (L.fq || "");
const titleLine = L => `${(CH[L.ch] || {}).title || "Member"} · ${L.pn}${sinceWords(L) ? " · in office since " + sinceWords(L) : ""}`;
const memBtn = (L, extra, cls) => `<button class="ymem${cls ? " " + cls : ""}" type="button" data-id="${esc(L.id)}">${avatar(L.id, L.p, "md")}<span><b>${esc(L.n)}</b><span class="muted">${esc(extra || `${seatOf(L)} · ${L.pn}`)}</span></span><span class="go">Profile</span></button>`;
document.addEventListener("click", e => { const b = e.target.closest("button.ymem[data-id]"); if (b) openMember(b.dataset.id); });

/* ---------- numbers that count up ---------- */
$$("[data-count]").forEach(el => {
  const target = Number(el.dataset.count), t0 = performance.now() + 500, dur = calm() ? 1 : 1400;
  const tick = now => { const p = Math.max(0, Math.min(1, (now - t0) / dur)), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(target * e).toLocaleString(); if (p < 1) requestAnimationFrame(tick); };
  if (calm()) el.textContent = target.toLocaleString(); else requestAnimationFrame(tick);
  setTimeout(() => { el.textContent = target.toLocaleString(); }, 2600);      // the count-up is decoration; the real number always lands
});

/* ---------- the state, drawn beside the welcome: the upper chamber's districts by party; a tap opens the map ---------- */
function drawHeroMap(){
  const link = $("#heromaplink"), svg = $("#heromap"); if (!link || !svg) return;
  Promise.all([membersReady(), need("districts")]).then(([, D]) => {
    DATA.districts = D; const names = DATA.seats.upper || [], b = D.outline.bbox, pad = (b[2] - b[0]) * .02; if (!names.length) return;
    svg.setAttribute("viewBox", `${(b[0] - pad).toFixed(2)} ${(b[1] - pad).toFixed(2)} ${(b[2] - b[0] + 2 * pad).toFixed(2)} ${(b[3] - b[1] + 2 * pad).toFixed(2)}`);
    svg.innerHTML = names.map((d, i) => { const s = shapeOf("upper", d), L = memberAt("upper", d); return s ? `<path d="${s.d}" style="--i:${i};fill:${L ? tone(L.p) : "var(--line-strong)"}"></path>` : ""; }).join("");
    $("#heromapcap").textContent = `${P.upper.name} districts, colored by the party of each ${P.upper.title.toLowerCase()}. Open the map`;
    link.hidden = false;
  }).catch(() => {});
}

/* ---------- the two chambers: one square a seat ---------- */
function renderChambers(){
  const host = $("#chgrid"); if (!host) return;
  membersReady().then(() => {
    host.innerHTML = ["upper", "lower"].filter(k => P[k]).map((k, i) => {
      const C = BOOT.stats.chambers[k], ch = CHOF[k], ms = Object.values(DATA.legislators).filter(L => L.ch === ch);
      const order = C.parties.map(t => t[0]);
      ms.sort((a, b) => (order.indexOf(a.pn) - order.indexOf(b.pn)) || byDistrict(a.d, b.d));
      const vac = (DATA.vacant[k] || []);
      return `<div class="chcard rv" style="--i:${i}"><h3>${esc(P[k].full || P[k].name)} <span>${C.filled} of ${C.seats} seats filled</span></h3>
        <div class="chbar" role="img" aria-label="${esc(C.parties.map(t => t[0] + " " + t[2]).join(", "))}">${C.parties.map(t => `<i style="width:${(100 * t[2] / C.seats).toFixed(2)}%;background:${tone(t[1])}"></i>`).join("")}</div>
        <div class="chleg">${C.parties.map(t => `<span><i style="background:${tone(t[1])}"></i>${esc(t[0])} <b>${t[2]}</b></span>`).join("")}${vac.length ? `<span><i style="border:1.5px dashed var(--line-strong)"></i>Vacant <b>${vac.length}</b> <span class="muted">(${vac.map(esc).join(", ")})</span></span>` : ""}</div>
        <div class="seats">${ms.map(L => `<a href="#member=${esc(L.id)}" style="--pc:${tone(L.p)}" title="${esc(L.n)}, District ${esc(L.d)} (${esc(L.pn)})" aria-label="${esc(L.n)}, District ${esc(L.d)}, ${esc(L.pn)}"></a>`).join("")}${vac.map(d => `<a class="vac" title="District ${esc(d)}: vacant"></a>`).join("")}</div></div>`;
    }).join("");
    reveal(host);
  }, () => { host.innerHTML = `<p class="muted">Couldn't load the members. Check your connection and try again.</p>`; });
}

/* ---------- district shapes ---------- */
const shapeCache = {upper: {}, lower: {}};
const ringsPath = rings => rings.map(r => "M" + r.map(pt => pt[0].toFixed(3) + "," + pt[1].toFixed(3)).join("L") + "Z").join("");
function shapeOf(key, d){
  const hit = shapeCache[key][d]; if (hit) return hit;
  const raw = DATA.districts && DATA.districts[key] && DATA.districts[key][d]; if (!raw) return null;
  const rings = raw.map(r => decodeRing(r, DATA.districts.q || 400)); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const r of rings) for (const [x, y] of r) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  /* where the district's number goes: the centre of gravity of its largest piece, and how much room there is around it */
  let best = null, bestA = 0;
  for (const r of rings) { let a = 0, cx = 0, cy = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const f = r[j][0] * r[i][1] - r[i][0] * r[j][1]; a += f; cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f; }
    if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = a ? [cx / (3 * a), cy / (3 * a)] : r[0]; } }
  let at = best || [(x0 + x1) / 2, (y0 + y1) / 2]; if (!inShape(at, rings)) at = [(x0 + x1) / 2, (y0 + y1) / 2];
  return shapeCache[key][d] = {rings, d: ringsPath(rings), bbox: [x0, y0, x1, y1], at, room: Math.sqrt(bestA / 2), inside: inShape(at, rings)};
}
function districtsAt(lon, lat){
  const pt = albersUsa(lon, lat), out = {upper: null, lower: null}; if (!pt) return out;
  for (const key of ["upper", "lower"]) for (const d of DATA.seats[key] || []) { const s = shapeOf(key, d); if (!s) continue; const b = s.bbox;
    if (pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) continue; if (inShape(pt, s.rings)) { out[key] = d; break; } }
  return out;
}
/* State districts are small, a few city blocks in places, so the circle is as small as the kept pin allows: the pin
   is rounded to about half a mile, and the circle never claims to know better than that. */
const pinMiles = pin => Math.max(.5, (pin.acc || 0) / 1609.34);
const milesWords = m => m < .75 ? "about half a mile" : (m < 1.5 ? "about a mile" : `${Math.round(m)} miles`);
const pinSVG = (pin, u, cls) => { const pt = pin && albersUsa(pin.lon, pin.lat); if (!pt) return "";
  const miles = pinMiles(pin), r = miles * (1300 / 3958.8), hgt = 30 * u;
  return `<circle class="ycirc" cx="${pt[0].toFixed(3)}" cy="${pt[1].toFixed(3)}" r="${r.toFixed(3)}"></circle><g class="${cls}" transform="translate(${pt[0].toFixed(3)} ${pt[1].toFixed(3)}) scale(${(hgt / 30).toFixed(5)})"><path d="M0 0C-7 -10 -10 -14 -10 -20a10 10 0 1 1 20 0c0 6 -3 10 -10 20z"></path><circle cx="0" cy="-20" r="3.6"></circle></g>`; };

/* ---------- who represents you: the shortest path from "where am I" to two names ----------
   The district a reader finds is kept on their device only. When it came from their location, a rounded pin
   (about half a mile) is kept beside it, under the same key the federal pages use, so "Forget my location"
   on either side forgets it everywhere. */
const YOURS = (function(){
  const selU = $("#ysd"), selL = $("#yhd"), list = $("#ylist"), note = $("#ynote"); if (!selU) return {};
  const KEY = "sld:" + P.code.toLowerCase();
  let mine = null, myPin = null;
  $("#ysdlab").textContent = P.upper.name + " district"; if (P.lower) $("#yhdlab").textContent = P.lower.name + " district"; else selL.closest(".selwrap").hidden = true;
  const save = () => { if (mine) store.set(KEY, JSON.stringify(mine)); else store.del(KEY); };
  function fill(){
    selU.innerHTML = `<option value="">Choose</option>` + DATA.seats.upper.map(d => `<option value="${esc(d)}">${esc(d)}</option>`).join("");
    selL.innerHTML = `<option value="">Choose</option>` + DATA.seats.lower.map(d => `<option value="${esc(d)}">${esc(d)}</option>`).join("");
  }
  function paint(){
    if (!mine || (!mine.u && !mine.l)) { list.hidden = true; return; }
    selU.value = mine.u || ""; selL.value = mine.l || "";
    const sen = mine.u ? memberAt("upper", mine.u) : null, rep = mine.l ? memberAt("lower", mine.l) : null, maybe = (!mine.l && mine.u) ? lowersOf(mine.u) : [];
    const block = (key, d, L, yours) => `<article class="yvote${yours ? " focus" : ""}"><div class="yv-head"><b>${esc(P[key].name)} District ${esc(d)}</b><div class="muted">${L ? "" : "This seat is vacant, or its member is not on file yet."}</div></div>${L ? `<div class="yv-members">${memBtn(L, titleLine(L), yours ? "mine shimmer" : "")}</div>` : ""}
      <div class="yv-acts"><a class="chip" href="${districtHash(key, d)}">Show District ${esc(d)} on the big map</a></div></article>`;
    list.hidden = false;
    const head = (mine.l && mine.u) ? "Your two legislators" : (mine.u ? `Your ${P.upper.title.toLowerCase()}${maybe.length ? `, and the ${P.lower.name} districts inside ${P.upper.name} District ${mine.u}` : ""}` : `Your ${P.lower.title.toLowerCase()}`);
    list.innerHTML = `<div class="yours-head"><h3>${esc(head)}</h3>${sen || rep ? `<button class="chip sharebtn" id="yshare" type="button">Share, so friends can find theirs</button>` : ""}</div>
      <div class="yours-cols"><div class="ymap" id="ymap"><div class="ymap-head" id="ymaphead"></div><svg class="ymap-svg" id="ymapsvg" role="img" aria-label="Your districts"></svg>
        <div class="ymap-key">${BOOT.stats.parties.map(t => `<span><i style="background:${tone(t[1])}"></i>${esc(t[0])}</span>`).join("")}<span><i class="ring"></i>you</span></div><p class="ymap-note" id="ymapnote"></p></div>
      <div class="yours-votes">${mine.u ? block("upper", mine.u, sen, true) : ""}${mine.l ? block("lower", mine.l, rep, true) : maybe.map(d => block("lower", d, memberAt("lower", d), false)).join("")}
        ${!mine.l && maybe.length ? `<p class="muted" style="font-size:13.5px">One of these ${maybe.length === 2 ? "two" : maybe.length} ${esc(P.lower.name)} districts is yours. Pick it above, or use your location.</p>` : ""}</div></div>`;
    const sb = $("#yshare"); if (sb) sb.addEventListener("click", e => {
      const who = [sen ? `${sen.n} (${P.upper.name} District ${mine.u})` : "", rep ? `${rep.n} (${P.lower.name} District ${mine.l})` : ""].filter(Boolean);
      share({title: `My ${P.name} legislators`, text: `My ${P.name} legislator${who.length === 1 ? " is" : "s are"} ${who.join(" and ")}. Find yours, and see who funds their campaigns:`, url: `${SHARE_BASE}/`, kind: "yours", key: P.code}, e.currentTarget); });
    need("districts").then(D => { DATA.districts = D; drawMini(); }, () => { const m = $("#ymap"); if (m) m.hidden = true; });
  }
  function drawMini(){
    const svg = $("#ymapsvg"); if (!svg || !mine) return;
    const upper = mine.u && shapeOf("upper", mine.u), lows = (mine.u && P.nested ? lowersOf(mine.u) : (mine.l ? [mine.l] : [])).map(d => [d, shapeOf("lower", d)]).filter(x => x[1]);
    const boxes = [upper, ...lows.map(x => x[1])].filter(Boolean).map(s => s.bbox); if (!boxes.length) { $("#ymap").hidden = true; return; }
    const x0 = Math.min(...boxes.map(b => b[0])), y0 = Math.min(...boxes.map(b => b[1])), x1 = Math.max(...boxes.map(b => b[2])), y1 = Math.max(...boxes.map(b => b[3]));
    const pad = Math.max(x1 - x0, y1 - y0) * .1, vbw = x1 - x0 + 2 * pad;
    svg.setAttribute("viewBox", `${(x0 - pad).toFixed(3)} ${(y0 - pad).toFixed(3)} ${vbw.toFixed(3)} ${(y1 - y0 + 2 * pad).toFixed(3)}`);
    const u = vbw / Math.max(240, svg.clientWidth || 420);
    let body = lows.map(([d, s]) => { const L = memberAt("lower", d); return `<path class="yd" d="${s.d}" fill="${L ? tone(L.p) : "var(--line-strong)"}" tabindex="0" role="button" data-d="${esc(d)}" aria-label="${esc(P.lower.name)} District ${esc(d)}${L ? ": " + esc(L.n) : ""}"><title>${esc(P.lower.name)} District ${esc(d)}${L ? ": " + esc(L.n) + " (" + esc(L.pn) + ")" : ": vacant"}</title></path>`; }).join("");
    if (!lows.length && upper) { const L = memberAt("upper", mine.u); body = `<path class="yd" d="${upper.d}" fill="${L ? tone(L.p) : "var(--line-strong)"}"></path>`; }
    if (upper) body += `<path class="yout" d="${upper.d}"></path>`;
    const me = mine.l && shapeOf("lower", mine.l); if (me) body += `<path class="ymine" d="${me.d}"></path>`;
    svg.innerHTML = body + (myPin ? pinSVG(myPin, u, "ypin") : "");
    $("#ymaphead").innerHTML = `<b>${esc(P.upper.name)} District ${esc(mine.u || "")}</b>${lows.length ? `<span class="muted"> · the ${esc(P.lower.name)} district${lows.length === 1 ? "" : "s"} inside it${lows.length > 1 ? ": " + lows.map(x => esc(x[0])).join(" and ") : ""}, each colored by its member's party.${mine.l ? " Yours is outlined in gold." : ""}</span>` : ""}`;
    const n = $("#ymapnote");
    n.innerHTML = myPin ? `The pin is your own device's estimate of where you are, with a circle reaching ${milesWords(pinMiles(myPin))} around it. It was worked out on this device and is kept only here, rounded to about half a mile. <button type="button" id="yforget">Forget my location</button>`
      : `Tap "Use my location" and your own spot is pinned here. It is worked out on your device and never sent anywhere. <button type="button" id="yforget">Forget my districts</button>`;
    $("#yforget").addEventListener("click", forget);
  }
  function forget(){ mine = null; myPin = null; ["pin", "district", KEY].forEach(k => store.del(k)); selU.value = ""; selL.value = ""; list.hidden = true; note.textContent = "Forgotten. Your location and your districts are no longer kept on this device."; if (window.mapMine) mapMine(); }
  list.addEventListener("click", e => { const p = e.target.closest(".yd[data-d]"); if (p && mine && !mine.l) { mine = {u: mine.u, l: p.dataset.d, from: "pick"}; save(); paint(); if (window.mapMine) mapMine(); } });
  selU.addEventListener("change", () => { myPin = null; mine = selU.value ? {u: selU.value, l: null, from: "pick"} : null; save(); note.textContent = ""; paint(); if (window.mapMine) mapMine(); });
  selL.addEventListener("change", () => { myPin = null; const l = selL.value; mine = l ? {u: upperOf(l) || (mine && mine.u) || null, l, from: "pick"} : (mine && mine.u ? {u: mine.u, l: null, from: "pick"} : null); save(); note.textContent = ""; paint(); if (window.mapMine) mapMine(); });
  $("#yloc").addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn't available in this browser. Pick your district instead."; return; }
    note.textContent = "Finding your districts…";
    navigator.geolocation.getCurrentPosition(pos => {
      Promise.all([membersReady(), need("districts")]).then(([, D]) => {
        DATA.districts = D; const hit = districtsAt(pos.coords.longitude, pos.coords.latitude);
        if (!hit.upper && !hit.lower) { note.textContent = `That spot isn't inside ${P.name} on our map. Pick your district from the lists instead.`; return; }
        mine = {u: hit.upper, l: hit.lower, from: "pin"};
        myPin = {st: P.code, lat: Math.round(pos.coords.latitude * 100) / 100, lon: Math.round(pos.coords.longitude * 100) / 100, acc: Math.round(pos.coords.accuracy || 0)};      // rounded: about half a mile
        store.set("pin", JSON.stringify(myPin)); store.set("state", P.code); save();
        note.textContent = `It looks like ${P.upper.name} District ${hit.upper || "?"}${hit.lower ? " and " + P.lower.name + " District " + hit.lower : ""}. Worked out on your device; your location never leaves it. Near a district line the guess can be off by one.${(pos.coords.accuracy || 0) > 3000 ? ` Your device could only place you within about ${Math.max(2, Math.round(pos.coords.accuracy / 1609.34))} miles, so treat the districts as a rough guess.` : ""}`;
        paint(); track("locate", {key: P.code}); if (window.mapMine) mapMine();
      }, () => { note.textContent = "Couldn't load the district lines. Check your connection, or pick your district."; });
    }, () => { note.textContent = "Location wasn't shared. Pick your district instead."; }, {timeout: 10000, maximumAge: 600000});
  });
  membersReady().then(() => {
    fill();
    try { const pj = JSON.parse(store.get("pin") || "null"); if (pj && pj.st === P.code && isFinite(pj.lat) && isFinite(pj.lon)) myPin = pj; } catch (e) {}
    try { mine = JSON.parse(store.get(KEY) || "null"); } catch (e) { mine = null; }
    if (mine && mine.from === "pin" && !myPin) { mine = null; store.del(KEY); }                       // the location was forgotten on another page
    if (mine) { paint(); return; }
    if (myPin) need("districts").then(D => {                                                          // a pin from the federal side: place it here too
      DATA.districts = D; const hit = districtsAt(myPin.lon, myPin.lat); if (!hit.upper && !hit.lower) return;
      mine = {u: hit.upper, l: hit.lower, from: "pin"}; save();
      note.textContent = "Placed from the rounded location this device already keeps (about half a mile). Near a district line it can be off; “Use my location” gives a closer fix.";
      paint(); if (window.mapMine) mapMine();
    }, () => {});
  }, () => {});
  return {get mine(){ return mine; }, get pin(){ return myPin; }};
})();

/* ---------- the district map ---------- */
let mapInit = null;
function mapReady(){ return mapInit || (mapInit = Promise.all([membersReady(), need("districts")]).then(([, D]) => { DATA.districts = D; initMap(); }).catch(e => { mapInit = null; $("#mapside").innerHTML = `<span class="muted">Couldn't load the map. Check your connection and try again.</span>`; throw e; })); }
function initMap(){
  const svg = $("#dmap"), tip = $("#mtip"), side = $("#mapside"), stage = svg.closest(".stage"), sel = $("#dsel"), OUT = DATA.districts.outline;
  const [bx0, by0, bx1, by1] = OUT.bbox, pad = Math.max(bx1 - bx0, by1 - by0) * .04;
  const HOME = {x: bx0 - pad, y: by0 - pad, w: bx1 - bx0 + 2 * pad, h: by1 - by0 + 2 * pad}, RATIO = HOME.w / HOME.h, MINW = HOME.w / 60;
  let view = Object.assign({}, HOME), key = "upper", picked = null, raf = 0;
  const fit = (x0, y0, x1, y1, k) => { let w = Math.max((x1 - x0) * k, 1e-6), h = Math.max((y1 - y0) * k, 1e-6); const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    if (w / h > RATIO) h = w / RATIO; else w = h * RATIO; if (w < MINW) { w = MINW; h = w / RATIO; } return {x: cx - w / 2, y: cy - h / 2, w, h}; };
  const clamp = v => { let w = Math.min(v.w, HOME.w), h = w / RATIO; if (w < MINW) { w = MINW; h = w / RATIO; }
    return {x: Math.max(HOME.x, Math.min(HOME.x + HOME.w - w, v.x)), y: Math.max(HOME.y, Math.min(HOME.y + HOME.h - h, v.y)), w, h}; };
  const zoomed = () => view.w < HOME.w * .999;
  /* District numbers: each appears once its district is large enough on screen to hold it, so the whole state shows
     the big rural districts' numbers and the cities' appear as the reader zooms in. */
  let labels = [];
  /* map units in one screen pixel; the map fits its frame by whichever side is tighter */
  const unitPx = () => { const box = svg.getBoundingClientRect(), wide = Math.max(240, box.width || svg.clientWidth || 600), tall = box.height || wide / RATIO; return Math.max(view.w / wide, view.h / tall); };
  function sizeLabels(){
    const px = unitPx();
    /* Browsers refuse to draw type below a minimum size, and in map units these numbers are a fraction of a pixel.
       So the type stays 12px and each number is scaled down to the map instead. */
    const k = (px * 13 / 12).toFixed(5);
    for (const L of labels) { const show = L.ok && L.room / px >= .9 * (8.5 * L.n + 8); L.el.style.display = show ? "" : "none"; if (show) L.el.setAttribute("transform", `translate(${L.x} ${L.y}) scale(${k})`); }
  }
  function apply(){ svg.setAttribute("viewBox", `${view.x.toFixed(4)} ${view.y.toFixed(4)} ${view.w.toFixed(4)} ${view.h.toFixed(4)}`); svg.classList.toggle("zoomed", zoomed()); drawPin(); sizeLabels();
    $$("#zoombar [data-z]").forEach(b => { if (b.dataset.z === "home") b.setAttribute("aria-pressed", !zoomed()); }); }
  function setView(v, animate){
    v = clamp(v); cancelAnimationFrame(raf);
    if (!animate || calm()) { view = v; apply(); return; }
    const from = view, t0 = performance.now(), dur = 520;
    const step = now => { const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      view = {x: from.x + (v.x - from.x) * e, y: from.y + (v.y - from.y) * e, w: from.w + (v.w - from.w) * e, h: from.h + (v.h - from.h) * e}; apply(); if (p < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
  }
  const zoomBy = k => { const cx = view.x + view.w / 2, cy = view.y + view.h / 2, w = view.w * k; setView({x: cx - w / 2, y: cy - w / RATIO / 2, w, h: w / RATIO}, true); };
  function zoomTo(k, d, animate){ const s = shapeOf(k, d); if (!s) return; setView(fit(s.bbox[0], s.bbox[1], s.bbox[2], s.bbox[3], 3.2), animate); }
  function drawPin(){ const g = $("#dpin", svg); if (!g) return; const pin = YOURS.pin; g.innerHTML = pin ? pinSVG(pin, unitPx(), "dpin") : ""; }
  function draw(){
    const names = DATA.seats[key] || [];
    svg.innerHTML = `<g id="dlayer">${names.map(d => { const s = shapeOf(key, d), L = memberAt(key, d); if (!s) return "";
      return `<path class="dd${L ? "" : " vac"}" d="${s.d}" ${L ? `fill="${tone(L.p)}"` : ""} tabindex="0" role="button" data-d="${esc(d)}" aria-label="${esc(P[key].name)} District ${esc(d)}: ${L ? esc(L.n) + ", " + esc(L.pn) : "vacant"}"></path>`; }).join("")}</g>
      <path class="dout" d="${OUT.d}"></path><g id="dminelayer"></g><g id="dsellayer"></g>
      <g id="dlabels" aria-hidden="true">${names.map(d => shapeOf(key, d) ? `<text class="dl" data-d="${esc(d)}" style="display:none">${esc(d)}</text>` : "").join("")}</g><g id="dpin"></g>`;
    labels = $$("#dlabels .dl", svg).map(el => { const s = shapeOf(key, el.dataset.d); return {el, n: el.dataset.d.length, room: s.room, ok: s.inside, x: s.at[0].toFixed(3), y: s.at[1].toFixed(3)}; });
    sel.innerHTML = `<option value="">Jump to a ${esc(P[key].name)} district…</option>` + names.map(d => { const L = memberAt(key, d); return `<option value="${esc(d)}">${esc(d)} · ${L ? esc(L.n) + " (" + esc(L.pn) + ")" : "vacant"}</option>`; }).join("");
    $$("#dchips [data-ch]").forEach(b => b.setAttribute("aria-pressed", b.dataset.ch === key));
    markMine(); apply();
  }
  function markMine(){ const g = $("#dminelayer", svg); if (!g) return; const m = YOURS.mine, d = m && (key === "upper" ? m.u : m.l), s = d && shapeOf(key, d); g.innerHTML = s ? `<path class="dmine" d="${s.d}"></path>` : ""; drawPin(); }
  window.mapMine = markMine;
  function select(d, opts){
    opts = opts || {}; picked = d; const s = d && shapeOf(key, d), L = d && memberAt(key, d);
    $("#dsellayer", svg).innerHTML = s ? `<path class="dsel" d="${s.d}"></path>` : ""; sel.value = d || "";
    if (!d) { side.innerHTML = `<span class="muted">Tap a district to see who represents it.</span>`; return; }
    const inside = key === "upper" ? lowersOf(d) : [], up = key === "lower" ? upperOf(d) : null, mineHere = YOURS.mine && (key === "upper" ? YOURS.mine.u : YOURS.mine.l) === d;
    side.innerHTML = `<div class="side-head"><h3>${esc(P[key].name)} District ${esc(d)}${mineHere ? ` <span class="ch-yours">yours</span>` : ""}</h3><span><button class="chip" type="button" data-zoomhere="1">Zoom here</button> <button class="chip sharebtn" type="button" data-sharedistrict="1">Share</button></span></div>
      ${L ? memBtn(L, titleLine(L)) + `<div class="rep-top">${L.u ? ract("web", "Website", L.u) : ""}${L.ph ? ract("phone", L.ph, "tel:" + L.ph, true) : ""}${L.em ? ract("mail", "Email", "mailto:" + L.em, true) : ""}</div>` : `<p class="muted">This seat is vacant, or its member is not on file yet.</p>`}
      ${inside.length ? `<p class="inside">${esc(P.lower.name)} districts inside it: ${inside.map(l => { const R = memberAt("lower", l); return `<button type="button" data-goto="lower:${esc(l)}">${esc(l)}</button>${R ? " (" + esc(R.n) + ")" : " (vacant)"}`; }).join(", ")}.</p>` : ""}
      ${up && shapeOf("upper", up) ? `<p class="inside">It sits inside ${esc(P.upper.name)} District <button type="button" data-goto="upper:${esc(up)}">${esc(up)}</button>${memberAt("upper", up) ? " (" + esc(memberAt("upper", up).n) + ")" : ""}.</p>` : ""}`;
    if (!opts.quiet) history.replaceState({page: "map"}, "", districtHash(key, d));
    if (s && (opts.zoom || (s.bbox[2] - s.bbox[0]) < view.w * .05)) zoomTo(key, d, true);
    if (opts.scroll && !matchMedia("(min-width:1000px)").matches) side.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"});
  }
  window.mapSelect = (k, d) => { if (k !== key) { key = k; draw(); } select(d, {zoom: true, quiet: true}); };
  $("#dchips").innerHTML = ["upper", "lower"].filter(k => P[k]).map(k => `<button class="chip" type="button" data-ch="${k}" aria-pressed="${k === key}">${esc(P[k].name)} districts</button>`).join(" ");
  $("#dchips").addEventListener("click", e => { const b = e.target.closest("[data-ch]"); if (!b || b.dataset.ch === key) return; const was = picked, wasKey = key; key = b.dataset.ch; draw();
    const next = was && (key === "upper" ? (wasKey === "lower" ? upperOf(was) : null) : null); select(next && shapeOf(key, next) ? next : null, {quiet: !next}); if (!next) history.replaceState({page: "map"}, "", "#map"); });
  const zooms = (P.zooms || []).map(z => { const c = [[z.box[0], z.box[1]], [z.box[2], z.box[1]], [z.box[0], z.box[3]], [z.box[2], z.box[3]]].map(p => albersUsa(p[0], p[1])).filter(Boolean); if (c.length < 2) return null;
    return {name: z.name, v: fit(Math.min(...c.map(p => p[0])), Math.min(...c.map(p => p[1])), Math.max(...c.map(p => p[0])), Math.max(...c.map(p => p[1])), 1)}; }).filter(Boolean);
  $("#zoombar").innerHTML = `<button class="chip" type="button" data-z="home" aria-pressed="true">Whole state</button>` + zooms.map((z, i) => `<button class="chip" type="button" data-z="${i}">${esc(z.name)}</button>`).join("")
    + `<button class="chip sq" type="button" data-z="in" aria-label="Zoom in" title="Zoom in">+</button><button class="chip sq" type="button" data-z="out" aria-label="Zoom out" title="Zoom out">−</button>`;
  $("#zoombar").addEventListener("click", e => { const b = e.target.closest("[data-z]"); if (!b) return; const z = b.dataset.z;
    if (z === "home") setView(HOME, true); else if (z === "in") zoomBy(.55); else if (z === "out") zoomBy(1 / .55); else if (zooms[+z]) setView(zooms[+z].v, true); });
  $("#dlegend").innerHTML = BOOT.stats.parties.map(t => `<span><i class="sw" style="background:${tone(t[1])}"></i> ${esc(t[0])}</span>`).join("") + `<span><i class="sw" style="background:#2A2E36"></i> Vacant</span><span><i class="sw" style="border:2px solid #E0B040;background:none"></i> Your district, if you have picked one</span>`;
  sel.addEventListener("change", () => { if (sel.value) select(sel.value, {zoom: true, scroll: true}); });
  side.addEventListener("click", e => { const z = e.target.closest("[data-zoomhere]"); if (z && picked) { zoomTo(key, picked, true); return; }
    const sd = e.target.closest("[data-sharedistrict]"); if (sd && picked) { const L = memberAt(key, picked);
      share({title: `${P.name} ${P[key].name} District ${picked}`, text: `${P.name} ${P[key].name} District ${picked} is ${L ? "represented by " + L.n + " (" + L.pn + ")" : "vacant"}. Every district on the map, and who funds each campaign:`, url: `${SHARE_BASE}/${districtHash(key, picked)}`, kind: "district", key: (key === "upper" ? "S-" : "H-") + picked}, sd); return; }
    const g = e.target.closest("[data-goto]"); if (g) { const [k, d] = g.dataset.goto.split(":"); key = k; draw(); select(d, {zoom: true}); } });
  /* pointer: a press that does not travel is a tap on a district; one that travels drags the map when it is zoomed in */
  let drag = null, dragged = false;
  svg.addEventListener("pointerdown", e => { drag = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false}; dragged = false; });
  svg.addEventListener("pointermove", e => {
    const p = e.target.closest && e.target.closest(".dd");
    if (p && !(drag && drag.moved)) { const L = memberAt(key, p.dataset.d), r = stage.getBoundingClientRect(); tip.innerHTML = `<b>${esc(p.dataset.d)}</b>${L ? esc(L.n) + " (" + esc(L.pn) + ")" : "vacant"}`; tip.style.left = (e.clientX - r.left) + "px"; tip.style.top = (e.clientY - r.top) + "px"; tip.classList.add("show"); }
    else tip.classList.remove("show");
    if (!drag || !zoomed()) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true; dragged = true; svg.classList.add("grabbing"); cancelAnimationFrame(raf); const k = view.w / (svg.getBoundingClientRect().width || 1);
    view = clamp({x: drag.vx - dx * k, y: drag.vy - dy * k, w: view.w, h: view.h}); apply();
  });
  const drop = () => { drag = null; svg.classList.remove("grabbing"); };
  addEventListener("pointerup", drop); addEventListener("pointercancel", drop);
  svg.addEventListener("pointerleave", () => tip.classList.remove("show"));
  svg.addEventListener("click", e => { if (dragged) { dragged = false; return; } const p = e.target.closest(".dd"); if (p) select(p.dataset.d, {scroll: true}); });
  svg.addEventListener("dblclick", e => { e.preventDefault(); const r = svg.getBoundingClientRect(), fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height, cx = view.x + fx * view.w, cy = view.y + fy * view.h, w = view.w * .5; setView({x: cx - w / 2, y: cy - w / RATIO / 2, w, h: w / RATIO}, true); });
  svg.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("dd")) { e.preventDefault(); select(e.target.dataset.d, {scroll: true}); } });
  window.mapResize = () => { drawPin(); sizeLabels(); };
  addEventListener("resize", () => { if (!$("#pg-map").hidden) mapResize(); });
  draw();
  window.mapStats = () => ({key, picked, view, zoomed: zoomed(), shapes: $$(".dd", svg).length});
}

/* ---------- the roster: every sitting member in one table ---------- */
let roster = null;
function renderRoster(){
  const host = $("#rtable"); if (!host || roster) return;
  membersReady().then(() => {
    const all = Object.values(DATA.legislators), f = {ch: "", pt: "", q: ""}, parties = BOOT.stats.parties.map(t => [t[1], t[0]]);
    const dkey = d => { const n = natural(d); return n[0] * 100 + (n[1] ? n[1].toUpperCase().charCodeAt(0) - 64 : 0); };
    const cols = [
      {key: "name", label: "Member", val: r => (r.ln || r.n) + " " + r.n, html: r => `<span class="pty" style="background:${tone(r.p)}"></span><a href="#member=${esc(r.id)}"><b>${esc(r.n)}</b></a>`},
      {key: "party", label: "Party", val: r => r.pn},
      {key: "chamber", label: "Chamber", val: r => chName(r.ch)},
      {key: "district", label: "District", num: true, first: "asc", val: r => dkey(r.d), html: r => `<a href="${districtHash(KEYOF[r.ch], r.d)}" title="Show it on the map">${esc(r.d)}</a>`},
      {key: "since", label: "In office since", num: true, first: "asc", val: r => r.f ? +r.f.slice(0, 4) : (r.fq ? (+(r.fq.match(/\d{4}/) || [0])[0] - .5 || null) : null), html: r => r.f ? esc(r.f.slice(0, 4)) : (r.fq ? `<span class="muted">${esc(r.fq)}</span>` : `<span class="muted">not on file</span>`)}];
    const rowsNow = () => { const q = f.q.trim().toLowerCase(); return all.filter(r => (!f.ch || r.ch === f.ch) && (!f.pt || r.p === f.pt) && (!q || r.n.toLowerCase().includes(q) || String(r.d).toLowerCase() === q || ("district " + r.d).toLowerCase() === q)); };
    $("#rchips").innerHTML = `<button class="chip" type="button" data-ch="" aria-pressed="true">Both chambers</button> ` + ["upper", "lower"].filter(k => P[k]).map(k => `<button class="chip" type="button" data-ch="${CHOF[k]}" aria-pressed="false">${esc(P[k].name)}</button>`).join(" ")
      + ` <button class="chip" type="button" data-pt="" aria-pressed="true">All parties</button> ` + parties.map(([c, n]) => `<button class="chip" type="button" data-pt="${esc(c)}" aria-pressed="false">${esc(n)}</button>`).join(" ");
    roster = gridTable(host, {cols, rows: rowsNow(), sort: [{key: "name", dir: "asc"}], page: 25, empty: "No member matches.", count: rows => `${rows.length.toLocaleString()} member${rows.length === 1 ? "" : "s"}`});
    $("#rtools").addEventListener("click", e => { const b = e.target.closest("button.chip"); if (!b) return; const kind = "ch" in b.dataset ? "ch" : "pt"; f[kind] = b.dataset[kind];
      $$(`#rtools button[data-${kind}]`).forEach(x => x.setAttribute("aria-pressed", x === b)); roster.setRows(rowsNow()); });
    $("#rq").addEventListener("input", e => { f.q = e.target.value; roster.setRows(rowsNow()); });
  }, () => { host.innerHTML = `<p class="muted">Couldn't load the member list. Check your connection and try again.</p>`; });
}

/* ---------- money: who gave to the campaign, and who spent on their own ----------
   Everything here is the state campaign-finance agency's public record, added up. Donors are organizations only.
   Money from people (lobbyists are people too) appears as a total, never as names. Outside spending is kept
   apart: the campaign never received it. Money is grouped in two-year election segments, named by the even year. */
const KINDW = BOOT.kinds || {}, MONEY = {};
const segLabel = s => `${+s - 1}–${String(s).slice(2)}`;
const donorLink = (k, id) => { const t = (P.money_links || {})[k]; return t ? t.replace("{id}", encodeURIComponent(id)) : ""; };
const donorName = (k, id, n, bold) => { const href = donorLink(k, id), t = bold ? `<b>${esc(n)}</b>` : esc(n); return href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${t}</a>` : t; };
const kindTag = k => `<span class="kd"><i style="background:var(--k-${esc(k)})"></i>${esc(KINDW[k] || k)}</span>`;
const AGENCY = (P.money_agency || {}).name || "the state's campaign-finance agency";
const SRC = [["people", "People", "individual donors. The agency publishes their names; this site shows only the total"], ["lobbyists", "Lobbyists", "registered lobbyists, who are people too: a total, never names"],
  ["orgs", "Committees and funds", "political committees and funds, the ones listed here by name"], ["party", "Party units", "party committees and caucuses, listed here by name"],
  ["cand", "Other candidates", "other candidates' campaign committees, listed here by name"], ["self", "Own money", "the candidate's own money"],
  ["moved", "Moved in", "money from the member's own earlier committee, for example a House account passed on to a Senate one. It was raised from donors there first"],
  ["loans", "Loans", "loans to the campaign"], ["other", "Other", "everything else the file lists"]];
function raceLine(M, view){
  if (view === "all") return `${M.cycles.length === 1 ? "One two-year election segment" : M.cycles.length + " two-year election segments"}, ${Math.min(...M.cycles) - 1} through ${Math.max(...M.cycles)}, added together.`;
  const o = (M.offices || {})[view] || [];
  return `${segLabel(view)}: gifts to the campaign committee${o.length ? " for the " + o.map(chName).join(" and the ") : ""}.`;
}
function sourceBar(M, view, big){
  const t = (M.totals || {})[view]; if (!t || !t.receipts) return "";
  const parts = SRC.map(([k, label, what]) => ({k, label, what, v: Math.max(0, t[k] || 0)})).filter(x => x.v > 0), sum = parts.reduce((a, b) => a + b.v, 0) || 1;
  return `<div class="mny-bar${big ? " big" : ""}" role="img" aria-label="Where the listed money came from">${parts.map(x => `<i style="width:${(100 * x.v / sum).toFixed(2)}%;background:var(--m-${x.k})" data-src="${x.k}" title="${esc(x.label)}: ${usd(x.v)}"></i>`).join("")}</div>
    <div class="mny-leg">${parts.map(x => `<span><i style="background:var(--m-${x.k})"></i>${esc(x.label)} <b>${usdShort(x.v)}</b> ${Math.round(100 * x.v / sum)}%</span>`).join("")}</div>`;
}
function moneyCardBody(id, view){
  const rec = MONEY[id]; if (!rec) return ""; const M = rec.M, top = (M.top || {})[view] || [], sum = (M.sum || {})[view] || [0, 0], out = (M.outside || {})[view] || [0, 0], max = top.length ? top[0][3] : 1, t = (M.totals || {})[view];
  return `<p class="mny-race">${raceLine(M, view)}</p>${t ? `<p style="margin:0 0 8px">The file lists <b>${usd(t.receipts)}</b> given to the campaign. Where it came from:</p>${sourceBar(M, view, false)}` : ""}
    ${top.length ? `<p class="know-sub">The ${top.length === 10 ? "ten" : top.length} organization${top.length === 1 ? "" : "s"} that gave the most${sum[1] > top.length ? `, of ${sum[1].toLocaleString()} that gave ${usd(sum[0])} in all` : ""}</p><ol class="mny-top">${top.map(d => `<li><span class="nm">${donorName(d[2], d[0], d[1])}${kindTag(d[2])}</span><span class="amt">${usd(d[3])}</span><span class="meter" style="width:calc((100% - 30px) * ${(d[3] / max).toFixed(3)})"></span></li>`).join("")}</ol>` : `<p class="muted">No organization's gift to this campaign is on file for ${view === "all" ? "these years" : "this segment"}.</p>`}
    ${(out[0] || out[1]) ? `<p class="mny-out">Separately, outside groups spent <b>${usd(out[0])}</b> to support and <b>${usd(out[1])}</b> to oppose. None of that went to the campaign.</p>` : ""}`;
}
const MONEY_RULE = `From ${esc(AGENCY)}'s public files. Campaigns list a giver once that giver passes $200 in a year; smaller gifts are reported as one sum, and the public subsidy the state pays campaigns is reported elsewhere, so neither is in this file and the totals here are lower than everything a campaign took in. Organizations are named: political committees and funds, party units and other candidates' committees. People who gave, lobbyists included, are counted in the totals and never named on this site. Money a member moved from an earlier committee of their own is shown as "moved in", not as a donor.`;
function moneyCard(id){
  const M = MONEY[id].M, views = ["all"].concat(M.cycles.map(String)).filter(v => (M.top || {})[v] || (M.totals || {})[v]), start = "all";
  return `<div class="know-b money" data-money="${esc(id)}"><h4><span class="tag fact">Fact</span> Who funds the campaign</h4>
    <div class="mny-views" role="group" aria-label="Election segment">${views.map(v => `<button class="chip" type="button" data-mview="${v}" aria-pressed="${v === start}">${v === "all" ? `${Math.min(...M.cycles) - 1}–${Math.max(...M.cycles)}` : segLabel(v)}</button>`).join("")}</div>
    <div class="mny-body">${moneyCardBody(id, start)}</div>
    <a class="chip mny-more" href="#member=${esc(id)}/money">Every organization, every payment, and outside spending</a>
    <p class="know-rule">${MONEY_RULE}</p></div>`;
}
document.addEventListener("click", e => {
  const c = e.target.closest("[data-mview]"), box = c && c.closest("[data-money]"); if (!box) return;
  $$("[data-mview]", box).forEach(b => b.setAttribute("aria-pressed", b === c)); $(".mny-body", box).innerHTML = moneyCardBody(box.dataset.money, c.dataset.mview);
});
/* the member page's money section: a picture of the money that talks to a table of it */
function renderMoney(id, M, L, show){
  const box = $("#mpmoney"); if (!box || !M) return;
  const last = L.ln || L.n.split(" ").slice(-1)[0], views = ["all"].concat(M.cycles.map(String));
  let view = "all", layout = "top", D = null, table = null, curRows = []; const off = new Set();
  layout = store.get("moneyLayout") === "side" ? "side" : "top";
  box.hidden = false;
  box.innerHTML = `<div class="mny-headrow"><div><h3>Money: who gave, and who spent</h3><p class="lead">The organizations that gave to ${esc(L.n)}'s campaigns, from ${esc(AGENCY)}'s public files. Pick a two-year segment, point at the picture, sort the table by any column (hold Shift for a second column), and open a row to see each payment.</p></div>
      <div class="mny-layout" role="group" aria-label="Where the picture sits"><button type="button" data-lay="top" aria-pressed="${layout === "top"}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="7" rx="1.5"/><rect x="3" y="14" width="18" height="7" rx="1.5"/></svg>Picture on top</button><button type="button" data-lay="side" aria-pressed="${layout === "side"}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="18" rx="1.5"/><rect x="14" y="3" width="7" height="18" rx="1.5"/></svg>Picture at the side</button></div></div>
    <div class="mny-views" role="group" aria-label="Election segment">${views.map(v => `<button class="chip" type="button" data-pv="${v}" aria-pressed="${v === view}">${v === "all" ? `All years, ${Math.min(...M.cycles) - 1}–${Math.max(...M.cycles)}` : segLabel(v)}</button>`).join("")}</div>
    <p class="mny-race" id="mnyrace"></p>
    <div class="mny-grid" id="mnygrid" data-layout="${layout}"><div class="mny-chart" id="mnychart"></div><div id="mnytablebox"><p class="muted loading">Loading the donors…</p></div></div>
    <div class="mny-outside" id="mnyoutside"></div>`;
  const shape = (list, v) => list.map(d => { const cs = v === "all" ? Object.values(d.c) : (d.c[v] ? [d.c[v]] : []); if (!cs.length) return null;
      const f = cs.map(c => c[2]).filter(x => x != null), l = cs.map(c => c[3]).filter(x => x != null);
      return Object.assign({}, d, {_t: cs.reduce((a, c) => a + c[0], 0), _n: cs.reduce((a, c) => a + c[1], 0), _f: f.length ? Math.min(...f) : null, _l: l.length ? Math.max(...l) : null, _ik: cs.reduce((a, c) => a + (c[4] || 0), 0)}); })
    .filter(d => d && d._t > 0).sort((a, b) => b._t - a._t).map((d, i) => (d._rank = i + 1, d));
  const pays = (d, v) => { const ps = (d.p || []).filter(x => v === "all" || String(x[2]) === v), href = donorLink(d.k, d.id);
    return `<ul class="pays">${ps.map(x => `<li><span>${esc(dayDate(x[0]) || "no date")} · <b>${usd(x[1])}</b></span><span>${x[3] ? "in kind · " : ""}${segLabel(x[2])}</span></li>`).join("")}</ul>${d.more && v === "all" ? `<p class="muted" style="margin:8px 0 0;font-size:12.5px">and ${d.more.toLocaleString()} earlier payment${d.more === 1 ? "" : "s"} not listed.</p>` : ""}
      <p class="muted" style="margin:8px 0 0;font-size:12.5px">Same-day payments are added together. "In kind" is a gift of goods or services rather than money.${href ? ` <a href="${esc(href)}" target="_blank" rel="noopener">This committee at the agency</a>` : ""}</p>`; };
  const colsFor = (v, who) => [
    {key: "rank", label: "#", num: true, first: "asc", val: r => r._rank},
    {key: "name", label: who, val: r => r.n, html: r => donorName(r.k, r.id, r.n, true)},
    {key: "kind", label: "Kind", val: r => KINDW[r.k] || r.k, html: r => kindTag(r.k)},
    {key: "total", label: v === "all" ? "Total" : "Total " + segLabel(v), num: true, val: r => r._t, html: r => `<b>${usd(r._t)}</b>`},
    {key: "inkind", label: "In kind", num: true, title: "The part of the total given as goods or services rather than money", val: r => r._ik || null, html: r => r._ik ? usd(r._ik) : ""},
    {key: "n", label: "Payments", num: true, val: r => r._n, html: r => `<button class="xbtn" type="button" data-x="1" title="Show each payment">${r._n.toLocaleString()}</button>`},
    {key: "first", label: "First", num: true, val: r => r._f, html: r => esc(dayDate(r._f))},
    {key: "last", label: "Latest", num: true, val: r => r._l, html: r => esc(dayDate(r._l))}];
  function drawChart(rows){
    const chart = $("#mnychart"), t = (M.totals || {})[view], shownRows = rows.filter(r => !off.has(r.k)), kinds = [...new Set(rows.map(r => r.k))];
    const max = Math.max(1, ...M.cycles.map(y => ((M.sum || {})[y] || [0])[0]));
    chart.innerHTML = `${t ? `<h4>Where the listed ${usdShort(t.receipts)} came from</h4>${sourceBar(M, view, true)}` : ""}
      <h4>The organizations, sized by what they gave</h4><div class="tmap" id="tmap" role="group" aria-label="Donors sized by amount"></div>
      <div class="mny-kinds" role="group" aria-label="Show or hide kinds of organization">${kinds.map(k => `<button class="chip" type="button" data-kind="${esc(k)}" aria-pressed="${!off.has(k)}"><i style="background:var(--k-${esc(k)})"></i>${esc(KINDW[k] || k)}</button>`).join("")}</div>
      <p class="mny-say" id="mnysay">Point at a block, or a part of the bar, to read it. Click a block to open its payments in the table.</p>
      <h4>Organizations' money, segment by segment</h4><div class="mny-years" role="group" aria-label="Pick a segment">${M.cycles.slice().reverse().map(y => { const v = ((M.sum || {})[y] || [0])[0]; return `<button type="button" data-pv="${y}" aria-pressed="${String(y) === view}"><span class="v">${usdShort(v)}</span><i style="height:${Math.max(2, Math.round(78 * v / max))}%"></i><span>${segLabel(y)}</span></button>`; }).join("")}</div>`;
    const tm = $("#tmap"), W = tm.clientWidth || 640, H = tm.clientHeight || 320, most = W < 420 ? 12 : (W < 760 ? 24 : 40), cells = squarify(shownRows.slice(0, most).map(r => ({v: r._t, r})), W, H);
    tm.innerHTML = cells.map(c => `<button type="button" data-id="${esc(c.item.r.id)}" style="left:${(100 * c.x / W).toFixed(3)}%;top:${(100 * c.y / H).toFixed(3)}%;width:${(100 * c.w / W).toFixed(3)}%;height:${(100 * c.h / H).toFixed(3)}%;background:var(--k-${esc(c.item.r.k)})" aria-label="${esc(c.item.r.n)}, ${usd(c.item.r._t)}">${c.w > 58 && c.h > 30 ? `${esc(c.item.r.n)}<b>${usdShort(c.item.r._t)}</b>` : ""}</button>`).join("") || `<p class="muted" style="padding:14px">Nothing to draw for this choice.</p>`;
    if (shownRows.length > most) $("#mnysay").innerHTML += ` The picture shows the ${most} largest of ${shownRows.length.toLocaleString()}.`;
  }
  function draw(){
    $$("[data-pv]", box).forEach(b => b.setAttribute("aria-pressed", b.dataset.pv === view));
    $("#mnyrace").innerHTML = raceLine(M, view);
    const host = $("#mnytablebox");
    if (!D) { host.innerHTML = `<p class="muted">The full list of donors is on the online site.</p>`; $("#mnychart").innerHTML = (M.totals || {})[view] ? `<h4>Where the listed money came from</h4>${sourceBar(M, view, true)}<p class="mny-say" id="mnysay"></p>` : ""; return; }
    const rows = shape(D.donors, view);
    curRows = rows; drawChart(rows);
    const cols = colsFor(view, "Organization").concat(view === "all" ? M.cycles.slice().reverse().map(y => ({key: "y" + y, label: segLabel(y), num: true, val: r => (r.c[y] || [0])[0] || null, html: r => r.c[y] ? usd(r.c[y][0]) : ""})) : []);
    const mv = view === "all" ? Object.values(D.moved || {}).reduce((a, b) => a + b, 0) : ((D.moved || {})[view] || 0);
    host.innerHTML = `<div id="mnytable"></div><p class="know-rule" style="margin-top:10px">${mv ? `Not counted as a donor: ${usd(mv)} moved in from ${esc(last)}'s own earlier committee. ` : ""}Every organization on file is listed; nothing is cut off. ${MONEY_RULE}</p>`;
    table = gridTable($("#mnytable"), {cols, rows: rows.filter(r => !off.has(r.k)), sort: [{key: "total", dir: "desc"}], page: 25, rowId: r => r.id, detail: r => pays(r, view), empty: "No organization's gift is on file for this choice.",
      count: rs => `${rs.length.toLocaleString()} organization${rs.length === 1 ? "" : "s"}, ${usd(rs.reduce((a, r) => a + r._t, 0))}`,
      onHover: r => { $$("#tmap button").forEach(b => b.classList.toggle("hot", !!r && b.dataset.id === r.id)); }});
    drawOutside();
  }
  function drawOutside(){
    const host = $("#mnyoutside"), f = shape(D.for || [], view), a = shape(D.against || [], view), o = (M.outside || {})[view] || [0, 0];
    if (!f.length && !a.length) { host.innerHTML = `<h4>Outside spending</h4><p class="muted">No outside group reported spending for or against ${esc(L.n)} ${view === "all" ? "in these years" : "in this segment"}.</p>`; return; }
    host.innerHTML = `<h4>Outside spending: not a donation</h4><p class="lead">Groups that spent on their own to help or hurt ${esc(L.n)}'s election: <b>${usd(o[0])}</b> to support, <b>${usd(o[1])}</b> to oppose. The campaign never received this money. It is independent spending, which by law may not be coordinated with the campaign; party units and political committees and funds both do it.</p>
      <div class="mny-two"><div><h5>Spent to support</h5><div id="mnyfor"></div></div><div><h5>Spent to oppose</h5><div id="mnyagainst"></div></div></div>`;
    const cols = v => colsFor(v, "Group").filter(c => c.key !== "inkind");
    const mk = (el, rows) => gridTable(el, {cols: cols(view), rows, sort: [{key: "total", dir: "desc"}], page: 10, rowId: r => r.id, detail: r => pays(r, view), empty: "None on file.",
      count: rs => `${rs.length.toLocaleString()} group${rs.length === 1 ? "" : "s"}, ${usd(rs.reduce((x, r) => x + r._t, 0))}`});
    mk($("#mnyfor"), f); mk($("#mnyagainst"), a);
  }
  box.addEventListener("click", e => {
    const pv = e.target.closest("[data-pv]"); if (pv) { view = pv.dataset.pv; draw(); return; }
    const lay = e.target.closest("[data-lay]"); if (lay) { layout = lay.dataset.lay; store.set("moneyLayout", layout); $("#mnygrid").dataset.layout = layout; $$("[data-lay]", box).forEach(b => b.setAttribute("aria-pressed", b === lay)); if (D) draw(); return; }
    const kd = e.target.closest("[data-kind]"); if (kd) { off.has(kd.dataset.kind) ? off.delete(kd.dataset.kind) : off.add(kd.dataset.kind); draw(); return; }
    const cell = e.target.closest("#tmap button"); if (cell && table) { table.openRow(cell.dataset.id); return; }
    const seg = e.target.closest(".mny-bar.big i"); if (seg) say(seg);
  });
  const say = el => { const t = (M.totals || {})[view], s = SRC.find(x => x[0] === el.dataset.src); if (!t || !s) return; $$(".mny-bar.big i", box).forEach(i => i.classList.toggle("on", i === el));
    $("#mnysay").innerHTML = `<b>${esc(s[1])}: ${usd(t[s[0]])}</b>, ${Math.round(100 * t[s[0]] / Math.max(1, t.receipts))}% of what the file lists. That is ${s[2]}.`; };
  box.addEventListener("pointerover", e => {
    const cell = e.target.closest("#tmap button"), seg = e.target.closest(".mny-bar.big i");
    if (seg) { say(seg); return; }
    if (cell && D) { const r = curRows.find(x => x.id === cell.dataset.id); if (!r) return; if (table) table.mark(x => x.id === r.id);
      $("#mnysay").innerHTML = `<b>${esc(r.n)}</b> · ${esc(KINDW[r.k] || r.k)}: <b>${usd(r._t)}</b> in ${r._n.toLocaleString()} payment${r._n === 1 ? "" : "s"}, ${esc(dayDate(r._f))}${r._l !== r._f ? " to " + esc(dayDate(r._l)) : ""}. Number ${r._rank} on the list.`; }
  });
  addEventListener("resize", () => { if (D && !box.hidden && document.body.contains(box) && $("#tmap")) drawChart(curRows); });
  needDonors(id).then(d => { D = d; draw(); if (show === "money") setTimeout(() => { box.scrollIntoView({block: "start", behavior: "auto"}); scrollBy(0, -70); }, 80); },
    () => { $("#mnytablebox").innerHTML = `<p class="muted">Couldn't load the donors. Check your connection and try again.</p>`; });
}

/* ---------- a member's own page ----------
   Who the member is, without characterising anyone: facts from the roster, the committees they sit on, the
   organizations that fund their campaigns, and one fenced paragraph from Wikipedia. Recorded votes join it when
   the state's bills and roll calls are loaded. */
function knowHTML(Pf, L, id){
  const S = Pf.service, C = Pf.committees || [], W = Pf.wiki, last = L.ln || L.n.split(" ").slice(-1)[0];
  const fact = `<span class="tag fact">Fact</span>`;
  const mon = d => d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", {month: "long", year: "numeric"}) : "";
  const years = d => d ? Math.max(0, Math.floor((Date.now() - new Date(d + "T12:00:00")) / 3.15576e10)) : null;
  const plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? "" : "s"}`;
  let h = "";
  if (S) {
    const span = s => s.from ? `${esc(s.from)} to ${s.to ? esc(s.to) : "now"}` : (s.to ? `until ${esc(s.to)}` : "dates not on file");
    const y = years(S.since), seats = (S.seats || []).map(s => `District ${esc(s.d)} (${span(s)})`).join(", then ");
    const earlier = (S.earlier || []).map(s => `${esc(chName(s.ch))} District ${esc(s.d)}, ${span(s)}`).join("; ");
    const began = S.since ? `In the ${esc(chName(S.chamber))} since <b>${esc(mon(S.since))}</b>${y != null ? `: ${plural(y, "year")}` : ""}.`
      : (S.vague ? `In the ${esc(chName(S.chamber))} since <b>${esc(S.vague)}</b>. The roster this page draws on does not record when this service began.` : `Sits in the ${esc(chName(S.chamber))}. The roster this page draws on does not record when this service began.`);
    h += `<div class="know-b"><h4>${fact} In office</h4><p>${began}${seats ? ` The district's number changed along the way: ${seats}.` : ""}${earlier ? ` Earlier seats on file: ${earlier}.` : ""}${S.next ? ` The seat is next on the ballot in <b>November ${esc(String(S.next))}</b>.` : ""}</p>${L.of ? `<p class="know-line">${ico("pin")}<span>${esc(L.of)}</span></p>` : ""}</div>`;
  }
  if (C.length) h += `<div class="know-b"><h4>${fact} Committees</h4><ul class="know-list">${C.map(c => `<li><b>${esc(c.name)}</b>${c.title ? `<span class="role">${esc(c.title)}</span>` : ""}${c.ch && c.ch !== L.ch ? ` <span class="muted">(${esc(chName(c.ch))})</span>` : ""}</li>`).join("")}</ul></div>`;
  if (Pf.money && Pf.money.cycles && Pf.money.cycles.length) { MONEY[id] = {M: Pf.money}; h += moneyCard(id); }
  if (W && W.extract) h += `<div class="know-b know-wiki"><h4><span class="tag wiki">From Wikipedia</span> Before the legislature, and beyond it</h4><p>${esc(W.extract)}</p><p class="know-rule">This is the opening of the Wikipedia article <a href="${esc(W.url)}" target="_blank" rel="noopener">${esc(W.title)}</a>. It is <b>not an official record</b>, and anyone can edit it. Text under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>.</p></div>`;
  return h;
}
function openMember(id, show){ history.pushState({page: "member"}, "", "#member=" + id + (show ? "/" + show : "")); routeFromHash(false); }
let mpSeq = 0;
function renderMemberPage(id, show){
  const token = ++mpSeq, box = $("#mpage"); if (!box) return;
  box.innerHTML = `<p class="muted loading">Loading…</p>`;
  Promise.all([membersReady(), needMember(id)]).then(([, Pf]) => {
    if (token !== mpSeq) return;
    const L = DATA.legislators[id];
    if (!L) { box.innerHTML = `<div class="empty">That member isn't in this record. <a href="#members">See all members</a></div>`; return; }
    const key = KEYOF[L.ch], up = key === "lower" ? upperOf(L.d) : null, other = up ? memberAt("upper", up) : null, insiders = key === "upper" ? lowersOf(L.d).map(d => memberAt("lower", d)).filter(Boolean) : [];
    pageview("/member/" + id, L.n); document.title = `${L.n}: The Civic Archive`;
    box.innerHTML = `<p class="crumbs"><a href="#members">← All ${BOOT.stats.members.toLocaleString()} legislators</a></p><div class="mp-head">${avatar(id, L.p, "xxl")}<div><h1 class="mp-name">${esc(L.n)}</h1><div class="seat"><b>${esc(L.pn)}</b>, ${esc((CH[L.ch] || {}).title || "Member")} for District ${esc(L.d)}, ${esc(P.name)}</div></div></div>
      <div class="rep-top">${L.u ? ract("web", "Website", L.u) : ""}${L.ph ? ract("phone", L.ph, "tel:" + L.ph, true) : ""}${L.em ? ract("mail", "Email", "mailto:" + L.em, true) : ""}${ract("map", "District " + L.d + " on the map", districtHash(key, L.d), true)}<button class="ract sharebtn" id="sharemp" type="button">${ico("share")}<span>Share this profile</span></button></div>
      <div class="mp-grid">
        <div class="know" id="mpknow"><h3>Get to know ${esc(L.n)}</h3>${knowHTML(Pf, L, id) || `<p class="muted">Nothing more on record for this member yet.</p>`}</div>
        <div class="mp-side">
          <div class="know-b"><h4><span class="tag fact">Fact</span> Every recorded vote</h4><p class="muted">Coming next. ${esc(P.name)}'s bills and recorded floor votes are the next part to be added; when they arrive, every vote ${esc(L.n)} cast will be listed here, as on the federal side.</p></div>
          ${other || insiders.length ? `<div class="know-b"><h4><span class="tag fact">Fact</span> The same voters' other legislator${insiders.length > 1 ? "s" : ""}</h4><p class="muted" style="margin-bottom:6px">${other ? `District ${esc(L.d)} sits inside ${esc(P.upper.name)} District ${esc(up)}.` : `The ${esc(P.lower.name)} districts inside ${esc(P.upper.name)} District ${esc(L.d)}.`}</p>${[other].concat(insiders).filter(Boolean).map(m => memBtn(m)).join("")}</div>` : ""}
        </div>
      </div>
      <div class="mny-page" id="mpmoney" hidden></div>`;
    if (Pf.money && Pf.money.cycles && Pf.money.cycles.length) renderMoney(id, Pf.money, L, show);
    $("#sharemp").addEventListener("click", e => share({title: `Get to know ${L.n}`, text: `${L.n}, ${seatOf(L)} in the ${P.legislature}: service, committees and who funds the campaign, from the public record:`, url: `${SHARE_BASE}/m/${id}.html`, kind: "member", key: id}, e.currentTarget));
  }, () => { if (token === mpSeq) box.innerHTML = `<div class="empty">Couldn't load this member. Check your connection and try again.</div>`; });
}

/* ---------- search ---------- */
(function(){
  const pal = $("#palette"), inp = $("#palq"), list = $("#pallist"); let items = [], idx = 0;
  const open = () => { pal.hidden = false; document.body.classList.add("noscroll"); inp.value = ""; run(""); requestAnimationFrame(() => inp.focus()); };
  const close = () => { pal.hidden = true; document.body.classList.remove("noscroll"); };
  const mark = () => { $$("li[data-i]", list).forEach(li => li.setAttribute("aria-selected", +li.dataset.i === idx)); const cur = $(`li[data-i="${idx}"]`, list); if (cur) cur.scrollIntoView({block: "nearest"}); };
  const go = i => { const it = items[i]; if (!it) return; close(); openMember(it.id); };
  function run(q){
    if (!MEMBERS_READY) { items = []; list.innerHTML = `<li class="none">Loading the members…</li>`; membersReady().then(() => { if (!pal.hidden) run(inp.value); }, () => { list.innerHTML = `<li class="none">Couldn't load the members. Check your connection and try again.</li>`; }); return; }
    q = q.trim().toLowerCase(); const dq = q.replace(/^district\s+/, "");
    const all = Object.values(DATA.legislators), mems = (q ? all.filter(m => m.n.toLowerCase().includes(q) || String(m.d).toLowerCase() === dq || (P.nested && upperOf(m.d) === dq)) : []).sort((a, b) => byDistrict(a.d, b.d) || a.n.localeCompare(b.n)).slice(0, 9);
    items = mems.map(m => ({id: m.id})); idx = 0; let n = 0;
    list.innerHTML = (mems.length ? `<li class="grp">Legislators</li>` + mems.map(m => `<li role="option" data-i="${n++}" style="--i:${n}">${avatar(m.id, m.p, "sm")}<span class="t">${esc(m.n)}</span><span class="s">${esc(seatOf(m))}, ${esc(m.pn)}</span></li>`).join("") : "")
      || `<li class="none">${q ? "Nothing matches. Try a last name, or a district like 45A." : "Type a legislator's name, or a district like 45A."}</li>`;
    mark();
  }
  $("#palettebtn").addEventListener("click", open);
  $(".pal-back").addEventListener("click", close);
  inp.addEventListener("input", () => run(inp.value));
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); idx = Math.min(items.length - 1, idx + 1); mark(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(0, idx - 1); mark(); }
    else if (e.key === "Enter") { e.preventDefault(); go(idx); }
  });
  list.addEventListener("click", e => { const li = e.target.closest("li[data-i]"); if (li) go(+li.dataset.i); });
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (pal.hidden) open(); else close(); return; }
    if (e.key === "Escape" && !pal.hidden) close();
  });
  if (!/Mac|iPhone|iPad/.test(navigator.platform || "")) $$(".kbtn kbd").forEach(k => k.textContent = "Ctrl K");
})();

/* --- pages: one document, one page visible at a time, the same hash addresses as the federal side --- */
const PAGES = ["home", "map", "members", "member", "sources"];
const BASE_TITLE = document.title;
let page = "home";
function showPage(name, push){
  if (!PAGES.includes(name)) name = "home";
  page = name;
  PAGES.forEach(p => { const el = $("#pg-" + p); if (el) el.hidden = p !== name; });
  $$(".nav a[data-go], .tabbar a[data-go]").forEach(a => a.setAttribute("aria-current", (a.dataset.go === name || (name === "member" && a.dataset.go === "members")) ? "page" : "false"));
  if (name !== "member") document.title = BASE_TITLE;
  document.body.dataset.page = name;
  pageview("/" + P.code.toLowerCase() + "/" + (name === "home" ? "" : name), P.name + ": " + name);
  if (name === "members") renderRoster();
  if (name === "map") mapReady().then(() => { if (window.mapResize) mapResize(); }, () => {});      // drawn while hidden, the map has no size to measure; measure it now
  if (push) { const h = "#" + name; if (location.hash !== h) history.pushState({page: name}, "", h); }
  scrollTo({top: 0, behavior: "auto"});
}
function routeFromHash(push){
  const h = (location.hash || "").replace(/^#/, "");
  const mem = h.match(/^member=([A-Za-z0-9_-]+)(?:\/(money))?$/);
  if (mem) { showPage("member", false); renderMemberPage(mem[1], mem[2]); return; }
  const dis = h.match(/^district=([SH])-(.+)$/);
  if (dis) { showPage("map", false); mapReady().then(() => { if (window.mapSelect) mapSelect(dis[1] === "S" ? "upper" : "lower", decodeURIComponent(dis[2])); }, () => {}); return; }
  if (h === "yours" || h === "chambers" || h === "coming" || h === "top" || h === "") { showPage("home", false); if (h && h !== "top") { const t = $("#" + h); if (t) setTimeout(() => t.scrollIntoView({behavior: "auto"}), 30); } return; }
  showPage(PAGES.includes(h) ? h : "home", false);
}
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#"]'); if (!a) return;
  const h = a.getAttribute("href").slice(1);
  if (h === "yours" || h === "chambers" || h === "coming") { e.preventDefault(); showPage("home", true); const t = $("#" + h); if (t) setTimeout(() => t.scrollIntoView({behavior: calm() ? "auto" : "smooth"}), 30); return; }
  if (h === "top") { e.preventDefault(); showPage("home", true); return; }
  if (PAGES.includes(h)) { e.preventDefault(); showPage(h, true); }
});
addEventListener("popstate", () => routeFromHash(false));
addEventListener("hashchange", () => { const h = location.hash.slice(1); if (/^(member|district)=/.test(h)) routeFromHash(false); });

__CHANGELOG__
__HELP__
$("#totop").addEventListener("click", () => scrollTo({top: 0, behavior: calm() ? "auto" : "smooth"}));
renderChambers();
reveal(document);
routeFromHash(false);
setTimeout(drawHeroMap, 200);
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True, help="two-letter code from states/places.py, for example mn")
    ap.add_argument("--split", default="", help="the folder to write the site into; default site/dev/<place>")
    ap.add_argument("--db", default="", help="default state_<place>.sqlite next to this script")
    ap.add_argument("--base-url", default="", help="where the site will live; default https://thecivicarchive.github.io/dev/<place>")
    ap.add_argument("--analytics", default="", help="GoatCounter endpoint; default: the one line of analytics.txt, if that file exists")
    args = ap.parse_args()
    P = place(args.place)
    code = P["code"].lower()
    db = args.db or os.path.join(HERE, f"state_{code}.sqlite")
    if not os.path.exists(db):
        raise SystemExit(f"No database for {P['name']} yet. Run: python run_states.py {code}")
    folder = args.split or os.path.join(HERE, "site", "dev", code)
    base = args.base_url or f"https://thecivicarchive.github.io/dev/{code}"
    if not args.analytics:
        cfg = os.path.join(HERE, "analytics.txt")
        if os.path.exists(cfg):
            args.analytics = open(cfg, encoding="utf-8").read().strip()
    data = collect(P, db, os.path.join(HERE, f"state_{code}_districts.json"))
    version = (data["changelog"][0].get("version") if data["changelog"] else "") or ""
    print(f"Version {version or '(none: no version in CHANGELOG.md)'}")
    html = render(P, data, version, base, args.analytics)
    left = sorted(set(re.findall(r"__[A-Z0-9_]{3,}__", html)))
    if left:
        raise SystemExit(f"build_state_dev: placeholders were left unfilled in the page: {', '.join(left)}")
    sizes, n_members, donor_bytes, photo_bytes = write_site(folder, html, data)
    from states import share_state                       # a pasted link shows a card: one small page and one image per member
    sh = share_state.write_share_pages(os.path.abspath(folder), P, data, base, os.path.join(HERE, "states_cache"))
    print(f"    Share pages: {sh['member_pages']:,} members; preview images {sh['cards_drawn']:,} drawn, {sh['cards_kept']:,} unchanged, {sh['cards_bytes'] / 1e6:,.1f} MB")
    st = data["stats"]
    print(f"Wrote {folder}: {P['name']}, {st['members']:,} members, {st['districts']:,} district shapes, {st['portraits']:,} portraits, {st['wiki']:,} Wikipedia paragraphs; "
          f"index.html {sizes['index.html'] / 1e3:,.0f} KB, districts {sizes['data/districts.json'] / 1e3:,.0f} KB, {n_members:,} member files, "
          f"donor files {donor_bytes / 1e6:,.1f} MB, portraits {photo_bytes / 1e6:,.1f} MB")
    for key, c in st["chambers"].items():
        print(f"    {c['name']}: {c['filled']} of {c['seats']} seats filled ({', '.join(f'{t[0]} {t[2]}' for t in c['parties'])})" + (f"; vacant: {', '.join(c['vacant'])}" if c["vacant"] else ""))


if __name__ == "__main__":
    main()
