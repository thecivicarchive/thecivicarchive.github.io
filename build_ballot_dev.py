#!/usr/bin/env python3
"""
build_ballot_dev.py - On The Ballot, the Congress pages: site/dev/ballot/us/index.html.

    python build_ballot_dev.py

One page, routed by its address: the home page (your ballot, the Senate races, every state), a page per state
(#state=FL) and a page per race (#race=2026-FL-H07). A race page shows the November general election as an arena of
cards, one per candidate on the ballot, and the primaries that chose them as fields, one lane per candidate. The
arena opens into a side-by-side comparison: what each candidate is on the ballot as, their record in Congress if
they serve there today, and their campaign money from the FEC (organizations named, people as a total, outside
spending kept apart).

Rules the page keeps, as the rest of the site does: every card is the same size; candidates are shown in the order
the state's list gives, or by surname where the list gives no ballot order, never by money or polls; no score or
grade of any person; parties are printed exactly as the official list prints them. Nothing is shown for a state
until its official list is loaded; the page says which states are still to come.

Data: ballot_2026.sqlite (run_ballot.py), congress_119.sqlite for who holds each seat, and the draft site's member
files (site/dev/us/data/member/) for a sitting member's record, so both sides say the same thing. The page takes
the site's stylesheet and a few shared script parts from build_site_dev.py by the landmarks build_state_dev.py uses.
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ballot.common import DB, GENERAL, STATE_NAMES                              # noqa: E402
from build_site_dev import read_changelog, state_paths                          # noqa: E402
from build_state_dev import borrow                                              # noqa: E402
from money_views import KIND_LABELS, PAC_LIMIT, committee_kind, tidy_name       # noqa: E402

ELECTION_NAMES = {"general": "General election", "primary": "Top-two primary", "primary-DEM": "Democratic primary",
                  "primary-REP": "Republican primary", "primary-LPF": "Libertarian primary", "primary-GRE": "Green primary",
                  "primary-DFL": "Democratic-Farmer-Labor primary"}


def money(con, ids):
    """Each campaign's 2026 money as the FEC's files report it, for the candidates on a loaded list."""
    out = {}
    ids = sorted(i for i in ids if i)
    if not ids:
        return out
    q = ",".join("?" * len(ids))
    for r in con.execute(f"SELECT * FROM fec26_totals WHERE cand_id IN ({q})", ids):
        cid, receipts, indiv, cmte, party, self_, cloan, oloan, transfers, disb, coh, end = r
        out[cid] = {"r": receipts, "ind": indiv, "cmte": cmte, "pty": party, "self": (self_ or 0) + (cloan or 0), "coh": coh,
                    "end": end, "orgs": [], "moved": 0.0, "passed": 0.0, "for": 0.0, "against": 0.0, "forw": [], "agw": []}
    cm = {r[0]: r[1:] for r in con.execute("SELECT cmte_id, name, designation, type, party, org_type, connected_org, cand_id FROM fec26_committees")}
    gifts = defaultdict(lambda: defaultdict(float))
    per_election = defaultdict(float)
    outside = defaultdict(lambda: defaultdict(float))
    for cmte_id, cid, kind, election, amount, earmark in con.execute(
            f"SELECT cmte_id, cand_id, kind, election, amount, earmark FROM fec26_gifts WHERE cand_id IN ({q})", ids):
        m = out.setdefault(cid, {"r": None, "ind": None, "cmte": None, "pty": None, "self": None, "coh": None, "end": None, "orgs": [],
                                 "moved": 0.0, "passed": 0.0, "for": 0.0, "against": 0.0, "forw": [], "agw": []})
        name, dsgn, tp, _pty, org, _conn, owner = cm.get(cmte_id, ("", "", "", "", "", "", ""))
        k = committee_kind(tp, dsgn, org)
        if kind == "gift":
            if k == "joint" or (owner and owner == cid):      # the candidate's own fundraising passing through: moved in, not a donor
                m["moved"] += amount
                continue
            gifts[cid][cmte_id] += amount
            if earmark:
                m["passed"] += amount
            elif k not in ("party", "cand"):
                per_election[(cid, cmte_id, election)] += amount
        elif kind in ("for", "against", "talk_for", "talk_against"):
            side = "for" if kind in ("for", "talk_for") else "against"
            m[side] += amount
            outside[(cid, side)][cmte_id] += amount
    for (cid, cmte_id, election), total in per_election.items():      # the money_views rule: over $5,000 an election was passed along
        if total > PAC_LIMIT:
            out[cid]["passed"] += total - PAC_LIMIT
    for cid, by in gifts.items():
        top = sorted(by.items(), key=lambda kv: -kv[1])[:6]
        out[cid]["orgs"] = [[tidy_name(cm.get(c, ("",))[0]) or c, committee_kind(*[cm.get(c, ("",) * 7)[i] for i in (2, 1, 4)]), round(a)] for c, a in top]
    for (cid, side), by in outside.items():
        out[cid]["forw" if side == "for" else "agw"] = [[tidy_name(cm.get(c, ("",))[0]) or c, round(a)] for c, a in sorted(by.items(), key=lambda kv: -kv[1])[:3]]
    for m in out.values():
        for k in ("moved", "passed", "for", "against"):
            m[k] = round(m[k])
    return out


def ads(con, ids):
    """Ad spending by kind for each candidate on a loaded list (ballot/ads.py): the campaign's own over the cycle, and
    outside spending for and against by election, with the largest spenders that are committees."""
    ids = sorted(i for i in ids if i)
    if not ids or not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'ad_money'").fetchone():
        return {}
    q, out = ",".join("?" * len(ids)), {}
    for cid, who, stance, el, med, amt, _n, last in con.execute(f"SELECT * FROM ad_money WHERE cand_id IN ({q})", ids):
        a = out.setdefault(cid, {"c": {}, "o": {}, "sp": [], "last": ""})
        if who == "campaign":
            a["c"][med] = round(amt)
        else:
            a["o"].setdefault(f"{stance}-{el}", {})[med] = round(amt)
        a["last"] = max(a["last"], last or "")
    for cid, name, stance, el, amt in con.execute(f"SELECT cand_id, name, stance, election, amount FROM ad_spenders WHERE cand_id IN ({q}) ORDER BY amount DESC", ids):
        a = out.get(cid)
        if a is not None and sum(1 for s in a["sp"] if s[1] == stance) < 5:
            a["sp"].append([name, stance, el, round(amt)])
    return out


def member_facts(bios, site_root):
    """A sitting member's record, read from the draft site's own member files so both sides say the same thing."""
    out = {}
    for bio in sorted(b for b in bios if b):
        p = os.path.join(site_root, "us", "data", "member", f"{bio}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        s, v, f = d.get("service") or {}, d.get("votes") or {}, d.get("focus") or {}
        out[bio] = {"ch": s.get("chamber"), "since": (s.get("since") or "")[:4], "terms": s.get("terms"),
                    "cast": v.get("cast"), "elig": v.get("eligible"), "split": v.get("split_n"), "breaks": v.get("breaks_n"),
                    "spon": f.get("sponsored"), "laws": f.get("laws")}
    return out


def people(con, out_dir):
    """Age, offices held and a photo for each candidate (ballot/people.py); photos are written as files beside the page."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'people'").fetchone():
        return {}
    import hashlib
    os.makedirs(os.path.join(out_dir, "photos"), exist_ok=True)
    out = {}
    for key, dob, dob_src, offices, photo, photo_src, credit, url, website in con.execute(
            "SELECT person, dob, dob_src, offices, photo, photo_src, photo_credit, photo_url, website FROM people"):
        p = {}
        if dob:
            p["dob"], p["ds"] = dob, dob_src
        if offices:
            p["off"] = json.loads(offices)
        if photo:
            name = (key if key[:1] in "HSP" and "|" not in key else hashlib.sha1(key.encode()).hexdigest()[:14]) + ".webp"
            path = os.path.join(out_dir, "photos", name)
            if not os.path.exists(path) or open(path, "rb").read() != photo:
                open(path, "wb").write(photo)
            p["ph"], p["ps"], p["pc"], p["pu"] = f"photos/{name}", photo_src, credit, url
        if website:
            p["web"] = website
        if p:
            out[key] = p
    return out


def build(db, record_db, site_root, out_dir):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rec = sqlite3.connect(f"file:{record_db}?mode=ro", uri=True)
    party_of = dict(rec.execute("SELECT bioguide_id, party FROM legislators WHERE is_current = 1"))
    chamber_of = dict(rec.execute("SELECT bioguide_id, chamber FROM legislators WHERE is_current = 1"))
    cands = defaultdict(lambda: defaultdict(list))
    runs = defaultdict(list)
    fec_ids, bios = set(), set()
    for (race, election, date, name, party, code, order, inc, wi, votes, pct, outcome, fec, bio, src, note) in con.execute(
            "SELECT race_id, election, election_date, name, party, party_code, ballot_order, incumbent, write_in, votes, pct, outcome, "
            "fec_id, bioguide_id, source_id, note FROM candidates"):
        office = "H" if "-H" in race else "S"
        sitting = int(bool(bio) and chamber_of.get(bio) == ("House" if office == "H" else "Senate"))
        c = {"n": name, "p": party, "pc": code, "inc": int(bool(inc) or sitting), "wi": wi, "o": order, "v": votes, "pct": pct,
             "out": outcome, "fec": fec, "bio": bio, "note": note, "src": src, "date": date, "k": fec or f"{race}|{name}"}
        cands[race][election].append(c)
        fec_ids.add(fec)
        if bio:
            bios.add(bio)
            runs[bio].append([race, election, outcome])
    notes = {r[0]: {"changed": r[1], "note": r[2], "st": r[3], "su": r[4], "asof": r[5]} for r in con.execute("SELECT * FROM state_notes")}
    sources = {r[0]: {"state": r[2], "kind": r[3], "agency": r[4], "title": r[5], "url": r[6], "fetched": r[8], "sha": r[9], "rows": r[10], "note": r[11]}
               for r in con.execute("SELECT * FROM ballot_sources")}
    listed = {s["state"] for s in sources.values()}
    races = []
    for race, _level, office, st, dist, cls, special, holder, hname, hparty, gdate, note in con.execute(
            "SELECT * FROM races WHERE level = 'federal' ORDER BY state, office DESC, district"):
        if holder:
            bios.add(holder)
        races.append({"id": race, "st": st, "o": "H" if office == "U.S. House" else "S", "d": dist, "cls": cls, "sp": special,
                      "h": [holder, hname, hparty] if holder else None, "note": note, "date": gdate,
                      "el": {e: v for e, v in cands.get(race, {}).items()}})
    shapes = state_paths(os.path.join(HERE, "us_states_albers.json"))
    boot = {"election": GENERAL, "generated": dt.date.today().isoformat(), "names": STATE_NAMES, "notes": notes, "sources": sources,
            "listed": sorted(listed), "races": races, "money": money(con, fec_ids), "members": member_facts(bios, site_root),
            "runs": runs, "kinds": KIND_LABELS, "elections": ELECTION_NAMES, "party": party_of, "people": people(con, out_dir),
            "map": {k: v["d"] for k, v in shapes.items()}, "sbox": {k: v["bbox"] for k, v in shapes.items()},
            "dist": district_file(out_dir, {st for st, n in notes.items() if n["changed"]}), "ads": ads(con, fec_ids),
            "odds": json.load(open(os.path.join(HERE, "ballot_cache", "odds", "odds_2026.json"), encoding="utf-8"))
                    if os.path.exists(os.path.join(HERE, "ballot_cache", "odds", "odds_2026.json")) else {},
            "issues": {p: [u, json.loads(t)] for p, u, t in con.execute("SELECT person, url, topics FROM issues")}
                      if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'issues'").fetchone() else {},
            "polls": json.load(open(os.path.join(HERE, "ballot", "polls", "polls_2026.json"), encoding="utf-8"))["races"]
                     if os.path.exists(os.path.join(HERE, "ballot", "polls", "polls_2026.json")) else {},
            "changelog": read_changelog(os.path.join(HERE, "CHANGELOG.md"))}
    return boot


def district_file(out_dir, changed):
    """The House district lines the maps draw, in a file of their own beside the page (fetched only when a map is
    opened). Only states whose lines on the 2026 ballot are the current ones: where a state drew new lines for 2026,
    the old lines would be the wrong districts, so none are written and its maps say so."""
    src = json.load(open(os.path.join(HERE, "us_districts_albers.json"), encoding="utf-8"))
    kept = {st: rings for st, rings in src["states"].items() if st not in changed}
    body = json.dumps({"q": src.get("q", 50), "vintage": src.get("vintage", ""), "states": kept}, separators=(",", ":"))
    path = os.path.join(out_dir, "data", "districts.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path) or open(path, encoding="utf-8").read() != body:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
    return {"url": "data/districts.json", "vintage": src.get("vintage", ""), "states": sorted(kept)}


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>On The Ballot: Congress · The Civic Archive</title>
<meta name="description" content="Every House and Senate race on the November 3, 2026 ballot: who is running, from each state's official list, the primaries that chose them, and who funds them.">
<meta name="version" content="__VERSION__">
<meta name="theme-color" content="#0C0E12">
<link rel="icon" href="../../us/icon-192.png" type="image/png">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light";if(localStorage.getItem("motion")==="off")document.documentElement.classList.add("calm")}catch(e){document.documentElement.dataset.theme="light"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>__CSS__</style>
<style>
:root{--pR:var(--rep);--pD:var(--dem);--pL:#B07C00;--pG:#2F8F4E;--pI:#6E62A8;--pO:#646B76;--pW:#7C828C;--gold:#B8860B;
  --night:#0B1030;--night2:#070A1C;--cream:#F4F1E8}
:root[data-theme="dark"]{--pL:#E3B53A;--pG:#5CC98A;--pI:#A99CE0;--pO:#9AA3AF;--pW:#9AA0A8;--gold:#E0B040}
.bwrap{max-width:1180px;margin:0 auto;padding:0 20px}
.crumbs{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:13.5px;color:var(--muted);margin:22px 0 6px}
.crumbs a{color:var(--muted);text-decoration:none;border-bottom:1px solid var(--line-strong)}
.bhero{padding:34px 0 8px}
.bhero .eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.bhero h1{font-family:var(--serif);font-weight:400;font-size:clamp(40px,6.4vw,78px);line-height:1;margin:10px 0 0;letter-spacing:-.01em}
.bhero h1 em{color:var(--accent)}
.bhero .lede{color:var(--muted);max-width:66ch;font-size:clamp(15px,1.5vw,18px);margin:14px 0 0}
.kchips{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 0}
.kchip{border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:10px 14px;min-width:120px}
.kchip b{display:block;font-family:var(--serif);font-weight:400;font-size:28px;line-height:1}.kchip span{font-size:12px;color:var(--muted)}
.countdown{display:inline-flex;align-items:center;gap:8px;margin-top:16px;padding:6px 12px;border-radius:999px;background:var(--night);color:#FFF4D6;font-size:13px;font-weight:600}
.countdown i{width:8px;height:8px;border-radius:50%;background:#FFD86B;box-shadow:0 0 10px #FFD86B}
.bsec{padding:30px 0 6px}
.bsec h2{font-family:var(--serif);font-weight:400;font-size:clamp(28px,3.4vw,40px);margin:0;line-height:1.05}
.bsec .sub{color:var(--muted);max-width:70ch;margin:8px 0 0}
.mybar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0 0}
.mybar select{height:44px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 14px;font:600 14.5px var(--sans)}
.mine{display:grid;gap:12px;margin-top:14px}
.chip{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:999px;border:1px solid var(--line);background:var(--surface);font-size:12.5px;font-weight:600;white-space:nowrap}
.chip i{width:9px;height:9px;border-radius:50%;background:var(--pc)}
.chip.inc::after{content:"\2605";color:var(--gold);font-size:11px}
.rgrid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));margin-top:14px}
.rcard{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;transition:border-color .15s,transform .15s var(--ease)}
.rcard:hover{border-color:var(--line-strong);transform:translateY(-1px)}
.rcard .rt{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.rcard .rt b{font-size:16px}.rcard .rt span{font-size:12px;color:var(--muted)}
.rcard .rchips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.rcard .soon{font-size:13px;color:var(--muted);margin-top:8px}
.tagsp{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;background:rgba(184,134,11,.14);color:var(--gold);margin-left:6px}
.rlist{display:grid;gap:8px;margin-top:12px}
.rrow{display:grid;grid-template-columns:150px 1fr auto;gap:12px;align-items:center;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:10px 14px}
.rrow:hover{border-color:var(--line-strong)}.rrow .rl{font-weight:700;font-size:14px}.rrow .rc{display:flex;gap:6px;flex-wrap:wrap}.rrow .go{color:var(--muted)}
@media (max-width:640px){.rrow{grid-template-columns:1fr auto}.rrow .rc{grid-column:1/-1;order:3}}
.usballot{width:100%;height:auto;display:block;margin-top:10px}
.usballot path{fill:var(--surface);stroke:var(--line-strong);stroke-width:.8;cursor:pointer;transition:fill .15s}
.usballot path.on{fill:var(--accent)}.usballot path.off{fill:url(#bhatch)}.usballot path:hover{filter:brightness(1.12)}
.mkey{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:8px 0 0}.mkey span{display:inline-flex;gap:7px;align-items:center}.mkey i{width:13px;height:13px;border-radius:3px;display:inline-block;border:1px solid var(--line-strong)}
.usballot path.sen{stroke:var(--surface)}.usballot path.sen.unk{opacity:.55}.usballot path.none{fill:var(--line)}
/* the maps (John, 2026-09-30): the districts on the ballot, drawn as on the Vote map */
.seg{display:inline-flex;border:1px solid var(--line-strong);border-radius:999px;padding:3px;gap:2px;background:var(--surface)}
.seg button{all:unset;cursor:pointer;font:600 13px var(--sans);padding:6px 13px;border-radius:999px;color:var(--muted)}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--bg)}.seg button:disabled{opacity:.4;cursor:default}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.mapgrid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(270px,1fr);gap:16px;align-items:start;margin-top:14px}
@media (max-width:860px){.mapgrid{grid-template-columns:1fr}}
.mapcol{border:1px solid var(--line);background:var(--surface);border-radius:20px;padding:12px 12px 10px;min-width:0}
.mapbar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.zoom{display:inline-flex;gap:5px}
.zoom button{all:unset;cursor:pointer;width:32px;height:32px;display:grid;place-items:center;border:1px solid var(--line-strong);border-radius:50%;font:700 16px/1 var(--sans);color:var(--ink);background:var(--surface)}
.zoom button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.svgbox{position:relative;border-radius:14px;overflow:hidden;background:var(--bg);touch-action:pan-y}
.svgbox.zoomed{touch-action:none;cursor:grab}.svgbox.drag{cursor:grabbing}
.bstate{width:100%;height:auto;display:block;user-select:none;-webkit-user-select:none}
.bstate path.dist{stroke:var(--surface);stroke-width:1.1;vector-effect:non-scaling-stroke;cursor:pointer;transition:filter .15s,opacity .15s}
.bstate path.dist.unk{opacity:.5}.bstate path.dist.vac{fill:var(--line-strong)}
.bstate path.dist:hover,.bstate path.dist.hl{filter:brightness(1.2) saturate(1.1)}
.bstate path.dist:focus{outline:none}.bstate path.dist:focus-visible{stroke:var(--accent);stroke-width:3}
.bstate path.ring{fill:none;stroke:var(--ink);stroke-width:3;vector-effect:non-scaling-stroke;pointer-events:none}
.bstate path.sout{fill:none;stroke:var(--ink);stroke-width:1.3;vector-effect:non-scaling-stroke;pointer-events:none;opacity:.6}
.bstate path.whole{stroke:var(--surface);stroke-width:1.1;vector-effect:non-scaling-stroke;cursor:pointer}
.bstate path.nolines{fill:var(--line);cursor:default}
.bstate text{pointer-events:none;text-anchor:middle}
.bstate text.dlab{font:700 12px var(--sans);fill:#fff;paint-order:stroke;stroke:rgba(10,12,18,.6);stroke-width:3px;stroke-linejoin:round}
.bstate text.dlab.tiny{display:none}
.bstate text.big{font:700 13px var(--sans);fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}
.mnote{font-size:12.5px;color:var(--muted);margin:8px 2px 0;line-height:1.45}
.mapside{border:1px solid var(--line);background:var(--surface);border-radius:20px;padding:14px 16px 16px;min-height:200px}
.mapside .kick{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.mapside h3{font-family:var(--serif);font-weight:400;font-size:25px;line-height:1.05;margin:4px 0 6px}
.mapside .held{font-size:13.5px;color:var(--muted);margin:0 0 10px}.mapside .held b{color:var(--ink)}
.tally{display:grid;gap:6px;margin:10px 0 12px;padding:0;list-style:none}
.tally li{display:flex;gap:9px;align-items:center;font-size:14px}.tally i{width:14px;height:14px;border-radius:4px;flex:none}
.plist{display:grid;gap:8px;margin:8px 0 12px;padding:0;list-style:none}
.plist li{display:grid;grid-template-columns:40px 1fr;gap:10px;align-items:center;border:1px solid var(--line);border-radius:14px;padding:7px 10px 7px 7px;border-left:4px solid var(--pc)}
.plist .av{width:40px;height:40px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:color-mix(in srgb,var(--pc) 14%,var(--surface));color:var(--pc);font:600 15px var(--serif)}
.plist .av img{width:100%;height:100%;object-fit:cover;object-position:50% 18%}
.plist b{display:block;font-size:14.5px;line-height:1.2}.plist small{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.plist .star{color:var(--gold);font-size:12px;margin-left:4px}
.rpgo{display:inline-flex;align-items:center;gap:6px;height:38px;padding:0 16px;border-radius:999px;background:var(--ink);color:var(--bg);text-decoration:none;font-weight:700;font-size:14px}
.sidehint{font-size:13px;color:var(--muted);margin:10px 0 0}
.dnum{display:inline-grid;place-items:center;min-width:28px;height:28px;padding:0 6px;border-radius:9px;background:var(--pc,var(--line-strong));color:#fff;font:700 13px var(--sans);margin-right:8px;vertical-align:middle}
.bhero.withloc{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:22px;align-items:start}
@media (max-width:720px){.bhero.withloc{grid-template-columns:1fr}.bhero.withloc .loc{width:min(300px,100%)}}
.loc{margin:0;width:260px;border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:10px}
.loc svg{width:100%;height:auto;display:block}
.loc path.lst{fill:var(--line);stroke:none}.loc path.lot{fill:var(--line);stroke:var(--surface);stroke-width:.9;vector-effect:non-scaling-stroke;cursor:pointer}
.loc path.lot:hover{fill:var(--line-strong)}.loc path.lme{stroke:var(--ink);stroke-width:1.8;vector-effect:non-scaling-stroke}
.loc path.lout{fill:none;stroke:var(--ink);stroke-width:1;vector-effect:non-scaling-stroke;opacity:.55;pointer-events:none}
.loc figcaption{font-size:12.5px;color:var(--muted);margin:8px 2px 0;line-height:1.4}
.rshare{all:unset;cursor:pointer;margin-top:12px;display:inline-flex;align-items:center;height:36px;padding:0 16px;border-radius:999px;border:1px solid var(--line-strong);font-weight:700;font-size:14px}
.rshare:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* betting markets: apart, quiet, behind a notice */
.oddswrap{border:1px dashed var(--line-strong);border-radius:18px;padding:12px 16px;background:var(--surface)}
.oddswrap summary{cursor:pointer;list-style:none}.oddswrap summary::-webkit-details-marker{display:none}
.oddswrap summary h2{display:inline;font-size:clamp(22px,2.6vw,30px)}.oddswrap summary span{display:block;font-size:13.5px;color:var(--muted);margin-top:4px}
.oddswrap summary h2::after{content:" \25BE";font-size:.6em;color:var(--muted)}.oddswrap[open] summary h2::after{content:" \25B4"}
.mgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));margin-top:12px}
.mkt{border:1px solid var(--line);border-radius:14px;padding:10px 12px}.mh{display:flex;justify-content:space-between;gap:8px;font-size:13px;margin-bottom:6px}.mh span{color:var(--muted)}
.mrowo{display:grid;grid-template-columns:1fr 90px 44px;gap:8px;align-items:center;font-size:13.5px;margin:5px 0}
.mbar{height:8px;border-radius:4px;background:var(--line);overflow:hidden}.mbar i{display:block;height:100%;background:var(--muted)}
.mgo{all:unset;cursor:pointer;margin-top:8px;font-size:13px;font-weight:700;color:var(--ink);border:1px solid var(--line-strong);border-radius:999px;padding:6px 12px}
.mnotice{max-width:520px;width:calc(100% - 32px);border:1px solid var(--line-strong);border-radius:18px;padding:20px 22px;background:var(--surface);color:var(--ink)}
.mnotice::backdrop{background:rgba(10,12,18,.55)}.mnotice h3{font-family:var(--serif);font-weight:400;font-size:26px;margin:0 0 8px}
.mnotice p,.mnotice li{font-size:14px;line-height:1.5}.mnotice .mnh{color:var(--muted);font-style:italic;font-size:13px;border-top:1px solid var(--line);padding-top:10px}
.mnotice .mnh b{font-style:normal;color:var(--ink)}
.mbtns{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}.mbtns .stay{all:unset;cursor:pointer;font-weight:700;padding:9px 16px;border-radius:999px;background:var(--ink);color:var(--bg)}
.mbtns .goext{padding:9px 16px;border-radius:999px;border:1px solid var(--line-strong);color:var(--muted);text-decoration:none;font-weight:600}
.topics{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px}.topics span{font-size:11.5px;border:1px solid var(--line);border-radius:999px;padding:2px 8px;background:var(--surface)}
/* polls */
.ptable{overflow-x:auto;margin-top:12px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
.ptable table{border-collapse:collapse;width:100%;font-size:14px}.ptable th,.ptable td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}
.ptable th{font-size:12px;color:var(--muted);font-weight:700}.ptable td small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.ptable td:not(:first-child){font-variant-numeric:tabular-nums;font-weight:700}
.pavg{margin:10px 0 0;font-size:14px}.pnotes{margin:8px 0 0;padding-left:18px;font-size:13px;color:var(--muted)}
/* ads by kind */
.adgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));margin-top:14px}
.adcard{border:1px solid var(--line);border-top:4px solid var(--pc);background:var(--surface);border-radius:16px;padding:12px 14px}
.adcard h3{font-family:var(--serif);font-weight:400;font-size:21px;margin:0 0 8px}.adcard h3 small{font:600 12px var(--sans);color:var(--muted)}
.adrow{margin:10px 0}.adl{display:flex;justify-content:space-between;font-size:13px}.adl span{font-weight:700}
.adbar{display:flex;height:12px;border-radius:6px;overflow:hidden;background:var(--line);margin:5px 0}.adbar i{display:block;min-width:2px}
.adk{display:flex;flex-wrap:wrap;gap:3px 10px;font-size:11.5px;color:var(--muted)}.adk span{display:inline-flex;gap:4px;align-items:center}.adk i{width:9px;height:9px;border-radius:2px;display:inline-block}
.k-tv{background:#3A5BA0}.k-digital{background:#2F9E8F}.k-print{background:#C08A3E}.k-radio{background:#8E5BA8}.k-texts{background:#6B8E23}
.k-doors{background:#B85C38}.k-buys{background:#8A8F98}.k-production{background:#C9B79C}
.adsp{margin-top:8px;font-size:13px}.adsp summary{cursor:pointer;color:var(--accent);font-weight:600}.adsp ul{margin:6px 0 0;padding-left:18px}
.adlinks{font-size:12.5px;color:var(--muted);margin:10px 0 0}
.fnote{font-size:12.5px;color:var(--muted);margin:10px 0 0}
.sgrid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));margin-top:14px}
.scard2{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface)}
.scard2 b{display:block}.scard2 span{font-size:12.5px;color:var(--muted)}.scard2 .pill2{display:inline-block;margin-top:6px;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;background:var(--accent-soft,rgba(15,122,106,.12));color:var(--accent)}
.scard2 .pill2.no{background:none;border:1px dashed var(--line-strong);color:var(--muted)}
.notebox{border:1px solid var(--line);border-left:4px solid var(--gold);background:var(--surface);border-radius:12px;padding:12px 14px;margin-top:12px;font-size:14px}
.notebox .src{display:block;color:var(--muted);font-size:12.5px;margin-top:4px}
.holder{margin:10px 0 0;color:var(--muted);font-size:15px}
.holder b{color:var(--ink)}
/* the arena: the general election, candidates face to face */
.arena{position:relative;border-radius:30px;padding:30px clamp(12px,3vw,34px) 24px;margin:20px 0 6px;overflow:hidden;isolation:isolate;color:var(--cream);
  background:radial-gradient(120% 95% at 50% 0%,#1D2856 0%,var(--night) 52%,var(--night2) 100%);box-shadow:inset 0 0 0 1px rgba(255,214,110,.25),0 30px 60px -40px rgba(0,0,0,.7)}
.arena::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(34% 70% at 22% -6%,rgba(255,236,170,.22),transparent 70%),radial-gradient(34% 70% at 78% -6%,rgba(255,236,170,.22),transparent 70%)}
.arena::after{content:"";position:absolute;left:6%;right:6%;bottom:40px;height:46%;border-radius:50%;z-index:-1;border:1px solid rgba(255,214,110,.26);background:radial-gradient(closest-side,rgba(255,214,110,.10),transparent)}
.arena .ahead{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.arena .ahead b{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#FFD86B}.arena .ahead span{font-size:13px;color:rgba(244,241,232,.72)}
.acards{display:flex;justify-content:center;align-items:center;gap:clamp(8px,2.4vw,28px);perspective:1100px;flex-wrap:wrap}
.vs{font-family:var(--serif);font-style:italic;font-size:clamp(30px,4.6vw,54px);color:#FFD86B;text-shadow:0 0 24px rgba(255,200,80,.6);line-height:1;flex:none}
.bcard{--pc:var(--pO);position:relative;width:clamp(148px,22vw,220px);aspect-ratio:5/7.2;border-radius:18px;overflow:hidden;display:flex;flex-direction:column;
  background:linear-gradient(165deg,#FFFFFF,#F3EFE4);color:#15171B;box-shadow:0 24px 44px -20px rgba(0,0,0,.85),0 0 0 1px rgba(255,255,255,.3);transition:transform .35s var(--ease)}
.acards[data-n="2"] .bcard:first-child{transform:rotateY(12deg)}.acards[data-n="2"] .bcard:last-child{transform:rotateY(-12deg)}
.bcard .band{background:var(--pc);color:#fff;font:700 10.5px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;padding:9px 11px;display:flex;justify-content:space-between;gap:6px}
.bcard .band span:last-child{opacity:.85}
.bcard .mono{flex:1;display:grid;place-items:center;min-height:0;background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--pc) 9%,transparent) 0 7px,transparent 7px 14px)}
.bcard .mono span{width:min(40%,78px);aspect-ratio:1;border-radius:50%;display:grid;place-items:center;font-family:var(--serif);font-size:clamp(24px,3vw,34px);color:var(--pc);border:2px solid var(--pc);background:#fff}
.bcard .mono .ph{width:min(46%,88px);overflow:hidden;box-shadow:0 6px 16px -8px rgba(0,0,0,.45)}
.bcard .mono .ph img{width:100%;height:100%;object-fit:cover;object-position:50% 18%;display:block}
.bcard .who{padding:9px 11px 6px}.bcard .who b{display:block;font-family:var(--serif);font-weight:400;font-size:clamp(17px,1.9vw,21px);line-height:1.06}
.bcard .who small{display:block;color:#5C6169;font-size:11.5px;margin-top:2px}
.bcard dl{margin:0;padding:7px 11px 10px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:11.5px;border-top:1px solid #E4E5E1}
.bcard dt{color:#5C6169}.bcard dd{margin:0;text-align:right;font-weight:600}
.bcard .flag{position:absolute;top:34px;right:9px;font:700 9.5px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;border-radius:999px;background:#15171B;color:#FFD86B}
.bcard.wi{border:2px dashed #9AA0A8}
.bcard.solo{width:clamp(170px,26vw,240px)}
.aopen{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:8px;margin:20px auto 0;height:44px;padding:0 20px;border-radius:999px;border:1px solid rgba(255,214,110,.6);color:#FFE9A8;font-weight:700;font-size:14.5px;width:max-content}
.aopen:hover,.aopen:focus-visible{background:rgba(255,214,110,.12)}
.aopen svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2}
.anote{font-size:12.5px;color:rgba(244,241,232,.7);text-align:center;margin:12px auto 0;max-width:70ch}
@media (max-width:640px){      /* on a phone the cards stand in a column, each laid on its side, with "vs" between */
  .acards{flex-direction:column;gap:6px}.acards .bcard,.acards[data-n="2"] .bcard:first-child,.acards[data-n="2"] .bcard:last-child{transform:none}
  .bcard,.bcard.solo{width:min(100%,360px);aspect-ratio:auto;flex-direction:row;flex-wrap:wrap}
  .bcard .band{width:100%}.bcard .mono{flex:0 0 88px;min-height:88px}.bcard .mono span{width:58px;font-size:24px}
  .bcard .who{flex:1;min-width:0;align-self:center}.bcard dl{width:100%}.bcard .flag{top:40px}
  .vs{font-size:30px}}
:root:not(.calm) .arena.deal .bcard{animation:deal .85s var(--ease) both;animation-delay:calc(var(--k) * .14s)}
:root:not(.calm) .arena.deal .vs{animation:vspop .6s .5s cubic-bezier(.3,1.7,.5,1) both}
@keyframes deal{from{opacity:0;transform:translateY(46px) rotateX(38deg) scale(.82)}}
@keyframes vspop{from{opacity:0;transform:scale(.2) rotate(-24deg)}to{opacity:1;transform:none}}
.cmp{margin-top:18px;overflow-x:auto;border-radius:18px;background:rgba(255,255,255,.04);box-shadow:inset 0 0 0 1px rgba(255,214,110,.18)}
.cmp table{border-collapse:collapse;width:100%;min-width:560px;font-size:13.5px}
.cmp th,.cmp td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top;text-align:left}
.cmp thead th{font-family:var(--serif);font-weight:400;font-size:19px;color:#fff;border-bottom:2px solid var(--pc)}
.cmp tbody th{color:rgba(244,241,232,.7);font-weight:600;font-size:12.5px;white-space:nowrap;width:1%}
.cmp td small{display:block;color:rgba(244,241,232,.62);font-size:12px;margin-top:3px}
.cmp a{color:#FFE9A8}
.cmp .soon{color:rgba(244,241,232,.55);font-style:italic}
.cmp .grp th{padding-top:16px;color:#FFD86B;font-size:11px;letter-spacing:.14em;text-transform:uppercase;border-bottom-color:rgba(255,214,110,.3)}
/* the field: a primary, every candidate in a lane */
.field{border:1px solid var(--line);border-radius:22px;padding:16px 18px 14px;background:var(--surface);margin:14px 0}
.field .fh{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline}
.field .fh b{font-size:15px}.field .fh span{font-size:12.5px;color:var(--muted)}
.lanes{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:7px}
.lane{--pc:var(--pO);display:grid;grid-template-columns:minmax(130px,1.1fr) 3fr minmax(110px,auto);gap:12px;align-items:center;padding:7px 10px;border-radius:12px;border-left:4px solid var(--pc);background:linear-gradient(90deg,color-mix(in srgb,var(--pc) 7%,transparent),transparent 60%)}
.lane .nm{font-weight:600;font-size:14px}.lane .nm small{display:block;font-weight:400;color:var(--muted);font-size:11.5px}
.lane .bar{height:12px;border-radius:6px;background:var(--line);overflow:hidden}.lane .bar i{display:block;height:100%;width:var(--w,0);background:var(--pc);border-radius:6px}
:root:not(.calm) .field.run .lane .bar i{animation:grow 1s var(--ease) both;animation-delay:calc(var(--k) * .06s)}
@keyframes grow{from{width:0}}
.lane .vv{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;color:var(--muted)}
.lane.won{box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--pc) 45%,transparent)}
.lane.won .nm::after{content:"\2713\00a0advanced";color:var(--accent);font-size:11.5px;font-weight:700;margin-left:6px}
.lane.nobar{grid-template-columns:1fr auto}.lane.nobar .bar{display:none}
@media (max-width:640px){.lane{grid-template-columns:1fr auto}.lane .bar{grid-column:1/-1;order:3}}
.fnote{font-size:12.5px;color:var(--muted);margin:10px 0 0}
.srclist{display:grid;gap:10px;margin-top:12px}
.srcitem{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface);font-size:14px}
.srcitem small{display:block;color:var(--muted);margin-top:4px;word-break:break-all}
.method li{margin:6px 0}
.bfoot{border-top:1px solid var(--hair,var(--line));margin-top:40px;padding:20px 0 90px;color:var(--muted);font-size:13px}
.bfoot a{color:inherit}
.backlink{display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:var(--muted);font-weight:600;font-size:14px}
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../" title="On The Ballot: every level" aria-label="Back to the On The Ballot door"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16v8H4z"/><path d="M8 12V5h8v7"/><path d="M10 8.6l1.5 1.5 2.8-2.9"/></svg><span>On The Ballot</span></a>
    <a class="brand" href="#" aria-label="On The Ballot: Congress, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections"><a href="#">Congress</a><a href="#senate">Senate races</a><a href="#states">States</a><a href="#sources">Sources</a></nav>
    <div class="tools">
      <button class="mtog" id="motion" aria-pressed="true" title="Page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="app" class="bwrap" tabindex="-1"></main>
<footer class="bwrap bfoot">
  <p>On The Ballot, from The Civic Archive v__VERSION__. Who is running comes only from each state's official candidate list, loaded one state at a time; campaign money from the Federal Election Commission's bulk files. No scores, no ratings of any person, no ads, no donors. Built __GENERATED__.</p>
  <p><a href="../">On The Ballot: every level</a> &middot; <a href="../../">The Civic Archive front door</a> &middot; <a href="../../us/">The record of the 119th Congress</a></p>
</footer>
<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel"><span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span></button>
  <div class="cl-panel" id="clpanel" hidden><div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div><div class="cl-body" id="clbody"></div></div>
</div>
<script>
const BOOT = __BOOT__;
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
__MONEYFMT__
__CHANGELOG__
/* ---------- the two switches, with the same saved choices as the rest of the site ---------- */
const calm = () => document.documentElement.classList.contains("calm");
const showMotion = () => $("#motion").setAttribute("aria-pressed", calm() ? "false" : "true");
showMotion();
$("#motion").addEventListener("click", () => { const off = !calm(); document.documentElement.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });

/* ---------- words ---------- */
const NAMES = BOOT.names, R = Object.fromEntries(BOOT.races.map(r => [r.id, r]));
const byState = {}; BOOT.races.forEach(r => (byState[r.st] = byState[r.st] || []).push(r));
const listed = new Set(BOOT.listed);
const ORD = n => n + (["th", "st", "nd", "rd"][((n % 100) - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");
const raceName = r => r.o === "S" ? `U.S. Senate, ${NAMES[r.st]}${r.sp ? " (special election)" : ""}` : (+r.d === 0 ? `${NAMES[r.st]}, at large` : `${NAMES[r.st]}'s ${ORD(+r.d)} District`);
const raceShort = r => r.o === "S" ? `Senate${r.sp ? ", special" : ""}` : (+r.d === 0 ? "At large" : `${ORD(+r.d)} District`);
const PARTY = {R: "Republican", D: "Democratic", L: "Libertarian", G: "Green", W: "Write-in"};
const bare = p => String(p || "").replace(/ Party of [A-Z][a-z]+( [A-Z][a-z]+)?$| Party$/, "");
const shortParty = c => PARTY[c.pc] || (c.pc === "I" ? (/preference/i.test(c.p) ? "No party preference" : /affiliation/i.test(c.p) ? "No party affiliation" : bare(c.p) || "Independent") : bare(c.p) || "Other");
const pcVar = c => `var(--p${c.pc || "O"})`;
const HOLDPARTY = {Republican: "R", Democrat: "D", Democratic: "D", Independent: "I"};
const fmtDate = iso => { const [y, m, d] = String(iso || "").split("-").map(Number); return y ? new Date(y, m - 1, d).toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}) : ""; };
const surname = n => String(n).replace(/\s+(Jr\.?|Sr\.?|II|III|IV)$/i, "").trim().split(/\s+/).pop().toLowerCase();
const inOrder = list => [...list].sort((a, b) => (a.o ?? 1e9) - (b.o ?? 1e9) || surname(a.n).localeCompare(surname(b.n)));
const initials = n => { const w = String(n).replace(/["“”].*?["“”]/g, "").replace(/\b(Jr|Sr|II|III|IV)\.?$/i, "").trim().split(/\s+/); return ((w[0] || "")[0] || "") + ((w.length > 1 ? w[w.length - 1] : "")[0] || ""); };
const general = r => r.el && r.el.general ? inOrder(r.el.general) : [];
/* who a candidate is: age, offices held and for how long, a photo (ballot/people.py) */
const P = c => (BOOT.people || {})[c.k] || {};
const YEAR_MS = 365.2425 * 864e5;
const ageOf = dob => { if (!dob) return null; const [y, m, d] = dob.split("-").map(Number), n = new Date(); let a = n.getFullYear() - y; if (n.getMonth() + 1 < m || (n.getMonth() + 1 === m && n.getDate() < d)) a--; return a; };
const yearsBetween = (s, e) => s ? Math.max(0, (Math.min(e ? new Date(e).getTime() : Date.now(), Date.now()) - new Date(s)) / YEAR_MS) : null;
function service(c){
  const off = P(c).off || []; if (!off.length) return null;
  const now = off.filter(o => !o.end).sort((a, b) => (b.start || "").localeCompare(a.start || ""))[0] || null;
  const iv = off.filter(o => o.start).map(o => [new Date(o.start).getTime(), o.end ? new Date(o.end).getTime() : Date.now()]).sort((a, b) => a[0] - b[0]);
  let total = 0, cur = null;      // every office on record, overlapping years counted once
  for (const [a, b] of iv) { if (!cur) cur = [a, b]; else if (a <= cur[1]) cur[1] = Math.max(cur[1], b); else { total += cur[1] - cur[0]; cur = [a, b]; } }
  if (cur) total += cur[1] - cur[0];
  return {now: now ? {office: now.office, years: yearsBetween(now.start), unsure: !!now.unsure || !now.start} : null, total: iv.length ? total / YEAR_MS : null, unsure: off.some(o => o.unsure || !o.start), list: off};
}
const yWords = (y, unsure) => y == null ? "years not on record" : (y < 1 ? (unsure ? "at least a few months" : "under a year") : `${unsure ? "at least " : ""}${Math.floor(y)} yr${Math.floor(y) === 1 ? "" : "s"}`);
const shortOffice = o => String(o || "").replace(/^U\.S\. /, "U.S. ").replace(/ House of Representatives$/, " House");
const SRC_NAME = {"Congress": "the Biographical Directory of the U.S. Congress (congress-legislators roster)", "State roster": "the Open States roster of state officials"};
const days = () => { const [y, m, d] = BOOT.election.split("-").map(Number), n = new Date(); return Math.round((new Date(y, m - 1, d) - new Date(n.getFullYear(), n.getMonth(), n.getDate())) / 864e5); };
const dayWords = () => { const n = days(); return n > 1 ? `Election Day in ${n} days` : n === 1 ? "Election Day is tomorrow" : n === 0 ? "Election Day is today" : `Election Day was ${fmtDate(BOOT.election)}`; };

/* ---------- small pieces ---------- */
const chip = c => `<span class="chip${c.inc ? " inc" : ""}" style="--pc:${pcVar(c)}" title="${esc(shortParty(c))}${c.inc ? ", serves in this chamber today" : ""}"><i></i>${esc(c.n)}</span>`;
function raceCard(r){
  const g = general(r);
  return `<a class="rcard" href="#race=${esc(r.id)}"><div class="rt"><b>${esc(r.o === "S" ? NAMES[r.st] : raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${esc(r.o === "S" ? "U.S. Senate" : NAMES[r.st])}</span></div>
    ${g.length ? `<div class="rchips">${g.map(chip).join("")}</div>` : `<div class="soon">${listed.has(r.st) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</div>`}</a>`;
}
function raceRow(r){
  const g = general(r);
  return `<a class="rrow" href="#race=${esc(r.id)}"><span class="rl">${esc(raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</span><span class="rc">${g.length ? g.map(chip).join("") : `<span class="muted">${listed.has(r.st) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</span>`}</span><span class="go" aria-hidden="true">&rsaquo;</span></a>`;
}
function stateNote(st){
  const n = BOOT.notes[st]; if (!n) return "";
  return `<div class="notebox">${esc(n.note)}<span class="src">Source: <a href="${esc(n.su)}" target="_blank" rel="noopener">${esc(n.st)}</a>. A secondary source; the state's own election office is the authority on its districts.</span></div>`;
}

/* ---------- a candidate's card, and the arena ---------- */
function money(c){ return c.fec ? BOOT.money[c.fec] : null; }
function officeNow(c){
  const m = c.bio && BOOT.members[c.bio]; if (!m) return null;
  return `${m.ch === "Senate" ? "U.S. Senator" : "U.S. Representative"}${m.since ? ` since ${m.since}` : ""}`;
}
function card(c, r, k, solo){
  const M = money(c), pp = P(c), age = ageOf(pp.dob), sv = service(c);
  const flag = c.out === "unopposed" ? "Unopposed" : c.wi ? "Write-in" : c.inc ? "Incumbent" : "";
  const rows = [["Age", age != null ? String(age) : "Not on record"],
    ["In office now", sv && sv.now ? `${esc(shortOffice(sv.now.office))}, ${yWords(sv.now.years, sv.now.unsure)}` : "No office on record"]];
  if (sv && sv.total != null && (!sv.now || sv.total - (sv.now.years || 0) >= 1)) rows.push(["Years in office", `${yWords(sv.total, sv.unsure)}, all offices`]);
  rows.push(["Raised, 2026", M && M.r != null ? usdShort(M.r) : (c.fec ? "Not yet reported" : "No FEC filing")]);
  return `<article class="bcard${c.wi ? " wi" : ""}${solo ? " solo" : ""}" style="--pc:${pcVar(c)};--k:${k}" aria-label="${esc(c.n)}, ${esc(shortParty(c))}">
    <div class="band"><span>${esc(shortParty(c))}</span><span>${esc(r.o === "S" ? "Senate" : r.st + "-" + (+r.d || "AL"))}</span></div>
    ${flag ? `<span class="flag">${esc(flag)}</span>` : ""}
    <div class="mono">${pp.ph ? `<span class="ph"><img src="${esc(pp.ph)}" alt="" loading="lazy" decoding="async"></span>` : `<span aria-hidden="true">${esc(initials(c.n).toUpperCase())}</span>`}</div>
    <div class="who"><b>${esc(c.n)}</b><small>${esc(c.p || "")}</small></div>
    <dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`;
}
function arena(r){
  const g = general(r); if (!g.length) return "";
  const parts = []; g.forEach((c, i) => { if (i) parts.push(`<span class="vs" aria-hidden="true">vs</span>`); parts.push(card(c, r, i, g.length === 1)); });
  const lone = g.length === 1;
  return `<section class="arena deal" id="arena" aria-label="The general election, ${esc(fmtDate(r.date))}">
    <div class="ahead"><b>General election &middot; ${esc(fmtDate(r.date))}</b><span>${lone ? "One name for this office" : `${g.length} candidates, in the order the state's list gives, or by surname`}</span></div>
    <div class="acards" data-n="${g.length}">${parts.join("")}</div>
    <button class="aopen" id="aopen" type="button" aria-expanded="false" aria-controls="cmp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M12 4l8 8-8 8"/></svg><span>Step into the arena: compare them side by side</span></button>
    <div class="cmp" id="cmp" hidden></div>
    <p class="anote">Every card is the same size. The cards show what the records hold: age, the office a candidate holds now and for how long, their years in any office on record, and the money their campaign reported to the FEC. No score or grade of any person.</p>
  </section>`;
}
function compare(r){
  const g = general(r), n = g.length;
  const cell = (fn) => g.map(c => `<td>${fn(c)}</td>`).join("");
  const M = c => money(c) || {}, mem = c => (c.bio && BOOT.members[c.bio]) || null;
  const soon = t => `<span class="soon">${t}</span>`;
  const row = (label, fn) => `<tr><th scope="row">${label}</th>${cell(fn)}</tr>`;
  const grp = label => `<tr class="grp"><th colspan="${n + 1}">${label}</th></tr>`;
  const orgs = c => { const o = M(c).orgs || []; return o.length ? o.map(x => `${esc(x[0])} <small>${esc(BOOT.kinds[x[1]] || "")}: ${usd(x[2])}</small>`).join("") : (c.fec ? "None itemized yet" : "&ndash;"); };
  const side = (c, s) => { const m = M(c), t = m[s] || 0, w = m[s === "for" ? "forw" : "agw"] || []; return t ? `${usd(t)}${w.map(x => `<small>${esc(x[0])}: ${usd(x[1])}</small>`).join("")}` : "None reported"; };
  const html = `<table><thead><tr><th></th>${g.map(c => `<th scope="col" style="--pc:${pcVar(c)}">${esc(c.n)}</th>`).join("")}</tr></thead><tbody>
    ${grp("On the ballot")}
    ${row("Party, as printed", c => esc(c.p || "") + (c.wi ? "<small>Write-in: the name is not printed on the ballot</small>" : ""))}
    ${row("Notes from the list", c => c.note ? esc(c.note) : "&ndash;")}
    ${grp("Who they are")}
    ${row("Age", c => { const p = P(c), a = ageOf(p.dob); return a != null ? `${a}<small>Born ${esc(p.dob.slice(0, 4))}, according to ${esc(SRC_NAME[p.ds] || p.ds)}</small>` : "Not on record<small>No official record this site holds gives a birth date</small>"; })}
    ${row("Offices on record", c => { const sv = service(c); if (!sv) return "None<small>The records here cover Congress, state legislatures and statewide offices. City, county and school offices are not in them yet.</small>";
        return sv.list.map(o => `${esc(o.office)}, ${o.start ? esc(o.start.slice(0, 4)) : "start not on record"}&ndash;${o.end ? esc(o.end.slice(0, 4)) : "now"}<small>${yWords(yearsBetween(o.start, o.end), o.unsure || !o.start)}${o.terms ? `, ${o.terms} terms` : ""}; ${esc(SRC_NAME[o.src] || o.src)}</small>`).join("")
          + (sv.total != null ? `<small><b>All offices together: ${yWords(sv.total, sv.unsure)}</b></small>` : ""); })}
    ${row("Photo", c => { const p = P(c); return p.ph ? `${esc(p.pc || "")}${p.pu ? `<small><a href="${esc(p.pu)}" target="_blank" rel="noopener">Where it comes from</a></small>` : ""}` : "None yet<small>Initials stand in until a photo from an official record or the campaign's own site is found</small>"; })}
    ${row("In their own words", c => { const I = (BOOT.issues || {})[c.k];
      if (I) return `<span class="topics">${I[1].map(t => `<span>${esc(t)}</span>`).join("")}</span><a href="${esc(I[0])}" target="_blank" rel="noopener nofollow">Read them in their own words</a><small>The topics their campaign's issues page lists, as headings; nothing is summarized</small>`;
      return P(c).web ? `<a href="${esc(P(c).web)}" target="_blank" rel="noopener nofollow">Their campaign's website</a><small>The address the campaign gave the FEC or the state's candidate list</small>` : soon("A link to their campaign's own website"); })}
    ${grp("In office")}
    ${row("In Congress today", c => { const m = mem(c); return m ? `${m.ch === "Senate" ? "U.S. Senator" : "U.S. Representative"}${m.since ? `, since ${m.since}` : ""}${m.terms ? `<small>${m.terms} term${m.terms === 1 ? "" : "s"}</small>` : ""}` : "No"; })}
    ${row("Votes this Congress", c => { const m = mem(c); return m && m.elig ? `Voted on ${Number(m.cast).toLocaleString()} of ${Number(m.elig).toLocaleString()}${m.split ? `<small>Voted against most of their party on ${m.breaks || 0} of the ${m.split} votes that split the parties</small>` : ""}` : "&ndash;"; })}
    ${row("Bills this Congress", c => { const m = mem(c); return m && m.spon != null ? `Sponsored ${m.spon}${m.laws ? `, ${m.laws} became law` : ""}` : "&ndash;"; })}
    ${row("Their full record", c => c.bio && mem(c) ? `<a href="../../us/#member=${esc(c.bio)}">Open their page on the record side</a>` : `&ndash;<small>No record in Congress. Records of state and local offices come later.</small>`)}
    ${grp("Campaign money, 2026 (FEC)")}
    ${row("Raised", c => M(c).r != null ? `${usd(M(c).r)}${M(c).end ? `<small>Through ${esc(fmtDate(M(c).end))}</small>` : ""}` : (c.fec ? "Not yet reported" : "No FEC filing"))}
    ${row("From people", c => M(c).ind != null ? `${usd(M(c).ind)}<small>A total; people who give are never named here</small>` : "&ndash;")}
    ${row("From organizations", c => M(c).cmte != null ? `${usd(M(c).cmte)}${M(c).passed ? `<small>${usd(M(c).passed)} of it passed along from people who earmarked it</small>` : ""}` : "&ndash;")}
    ${row("Largest organizations", orgs)}
    ${row("From the party", c => M(c).pty != null ? usd(M(c).pty) : "&ndash;")}
    ${row("From the candidate", c => M(c).self != null ? usd(M(c).self) + "<small>Their own gifts and loans</small>" : "&ndash;")}
    ${row("Cash on hand", c => M(c).coh != null ? usd(M(c).coh) : "&ndash;")}
    ${row("FEC filings", c => c.fec ? `<a href="https://www.fec.gov/data/candidate/${esc(c.fec)}/" target="_blank" rel="noopener">${esc(c.fec)}</a>` : "No registration found")}
    ${grp("Outside spending, 2026 (never received by the campaign)")}
    ${row("Spent to support", c => side(c, "for"))}
    ${row("Spent to oppose", c => side(c, "against"))}
    ${grp("Still to come")}
    ${row("Ads", c => soon("TV, radio, digital and mail spending for and against, and links to the public ad libraries"))}
    ${row("Polls", c => soon("From pollsters in AAPOR's Transparency Initiative"))}
  </tbody></table>`;
  return html;
}

/* ---------- a primary, and its field ---------- */
function field(r, key){
  const list = r.el[key] || []; if (!list.length) return "";
  const votes = list.some(c => c.v != null), max = Math.max(1, ...list.map(c => c.pct || 0));
  const rows = [...list].sort((a, b) => votes ? (b.v || 0) - (a.v || 0) : surname(a.n).localeCompare(surname(b.n)));
  const date = list[0].date, topTwo = key === "primary";
  const src = BOOT.sources[list[0].src];
  return `<section class="field run"><div class="fh"><b>${esc(BOOT.elections[key] || key)} &middot; ${esc(fmtDate(date))}</b><span>${list.length} candidates${topTwo ? ", every party on one ballot; the two with the most votes advance" : ""}</span></div>
    <ol class="lanes">${rows.map((c, i) => `<li class="lane${c.out === "advanced" ? " won" : ""}${votes ? "" : " nobar"}" style="--pc:${pcVar(c)};--k:${i}"><span class="nm">${esc(c.n)}<small>${esc(c.p || "")}${ageOf(P(c).dob) != null ? ` &middot; age ${ageOf(P(c).dob)}` : ""}${c.inc ? " &middot; serves in this chamber today" : ""}</small></span>
      <span class="bar"><i style="--w:${votes ? (100 * (c.pct || 0) / max).toFixed(1) : 0}%"></i></span>
      <span class="vv">${votes ? `${Number(c.v).toLocaleString()} &middot; ${(c.pct || 0).toFixed(1)}%` : (c.out === "advanced" ? "Won" : "Lost")}</span></li>`).join("")}</ol>
    <p class="fnote">${votes ? `Votes as certified in the official results (${esc(src ? src.agency : "the state")}).` : `The official vote counts for this primary are not loaded yet; who won comes from the candidate list of the ${esc(src ? src.agency : "state")}.`}</p></section>`;
}

/* ---------- ads: what each campaign, and everyone spending apart from it, reported spending, by kind (ballot/ads.py) ---------- */
const AD_KINDS = [["tv", "TV"], ["digital", "Digital and streaming"], ["print", "Print and mail"], ["radio", "Radio"], ["texts", "Texts and calls"],
  ["doors", "Door-knocking"], ["buys", "Media buys, medium not stated"], ["production", "Ad production"]];
const adTotal = m => AD_KINDS.reduce((t, [k]) => t + ((m || {})[k] || 0), 0);
function adBar(m, label){
  const tot = adTotal(m); if (!tot) return "";
  const parts = AD_KINDS.filter(([k]) => (m[k] || 0) > 0).sort((a, b) => m[b[0]] - m[a[0]]);
  return `<div class="adrow"><div class="adl"><b>${esc(label)}</b><span>${usdShort(tot)}</span></div>
    <div class="adbar" role="img" aria-label="${esc(label)}: ${parts.map(([k, w]) => `${w} ${usdShort(m[k])}`).join(", ")}">${parts.map(([k]) => `<i class="k-${k}" style="flex:${m[k]}" title="${esc(AD_KINDS.find(x => x[0] === k)[1])}: ${usdShort(m[k])}"></i>`).join("")}</div>
    <div class="adk">${parts.map(([k, w]) => `<span><i class="k-${k}"></i>${esc(w)} ${usdShort(m[k])}</span>`).join("")}</div></div>`;
}
function adsHTML(r){
  const g = general(r).filter(c => c.fec && BOOT.ads[c.fec]); if (!g.length) return "";
  const last = g.map(c => BOOT.ads[c.fec].last).sort().pop();
  const meta = n => `https://www.facebook.com/ads/library/?active_status=all&ad_type=political_and_issue_ads&country=US&q=${encodeURIComponent(n)}&search_type=keyword_unordered`;
  const blocks = g.map(c => { const A = BOOT.ads[c.fec], o = A.o || {};
    const rows = [adBar(A.c, "Their campaign's own ads"), adBar(o["for-general"], "Outside, for them, since the primary"), adBar(o["against-general"], "Outside, against them, since the primary"),
      adBar(o["for-primary"], "Outside, for them, in the primary"), adBar(o["against-primary"], "Outside, against them, in the primary")].filter(Boolean).join("");
    const sp = A.sp.filter(s => s[3] >= 1000).map(s => `<li>${s[0] ? esc(s[0]) : "People and groups filing on their own (not named here)"}: <b>${usdShort(s[3])}</b> ${s[1]}${s[2] === "primary" ? ", in the primary" : s[2] === "general" ? "" : ""}</li>`).join("");
    return `<div class="adcard" style="--pc:${pcVar(c)}"><h3>${esc(c.n)} <small>${esc(shortParty(c))}</small></h3>${rows || `<p class="held">No ad spending reported yet.</p>`}
      ${sp ? `<details class="adsp"><summary>Who spent the most, apart from the campaign</summary><ul>${sp}</ul></details>` : ""}
      <p class="adlinks">See the ads themselves: <a href="${meta(c.n)}" target="_blank" rel="noopener">Meta's ad library</a> &middot; <a href="https://adstransparency.google.com/political?region=US" target="_blank" rel="noopener">Google's political ads</a> (search the name)</p></div>`; }).join("");
  return `<section class="bsec" id="ads"><h2>Ads and the money behind them</h2><p class="sub">What each campaign reported spending on ads, by kind, and what others spent for and against them on their own. Outside spending is not the campaign's money: the campaign never received it, and does not control it.</p>
    <div class="adgrid">${blocks}</div>
    <p class="fnote">From the Federal Election Commission's filings through ${esc(fmtDate(last))}. Each expense's kind is read from the purpose its spender wrote ("digital ads", "direct mail"); "medium not stated" means exactly that. An expense reported twice, in a quick 24- or 48-hour report and again later, is counted once. Outside spenders are named only when they are committees.</p></section>`;
}
/* ---------- betting markets: information only, behind a calm notice (John's answers, 2026-09-29) ---------- */
const HELPLINES = {      // each from the state's own page; a state not listed shows the national line alone, which routes callers to local help
  MN: ["Minnesota Problem Gambling Helpline", "1-800-333-HOPE (4673)", "tel:18003334673", "https://mn.gov/dhs/people-we-serve/adults/services/gambling-problems/get-help/"],
  IA: ["Your Life Iowa (Iowa HHS)", "(855) 581-8111, or text (855) 895-8398", "tel:18555818111", "https://yourlifeiowa.org/gambling"],
  MI: ["Michigan Problem Gambling Helpline", "1-800-270-7117", "tel:18002707117", "https://www.michigan.gov/mdhhs/keep-mi-healthy/mentalhealth/gambling"],
  WI: ["Wisconsin's free helpline", "800-GAMBLE-5 (800-426-2535)", "tel:18004262535", "https://www.dhs.wisconsin.gov/disease/gambling-disorder.htm"],
  ND: ["GamblerND (North Dakota Health and Human Services)", "1-877-702-7848, or 711 (TTY)", "tel:18777027848", "https://www.hhs.nd.gov/news/march-problem-gambling-awareness-month-free-confidential-support-available-statewide"],
  SD: ["South Dakota's Problem Gambling Helpline", "1-888-781-HELP (4357)", "tel:18887814357", "https://lottery.sd.gov/responsible-play/"],
  OH: ["Problem Gambling Helpline of Ohio", "1-800-589-9966", "tel:18005899966", "https://dbh.ohio.gov/get-help/get-help-now/problem-gambling"],
  IN: ["Indiana Problem Gambling Referral Line", "800-994-8448", "tel:18009948448", "https://www.in.gov/fssa/dmha/addiction-services/problem-gambling"],
  NE: ["Nebraska Commission on Problem Gambling helpline", "1-833-238-6837, or text 402-806-7344", "tel:18332386837", "https://problemgambling.nebraska.gov/"],
  MT: ["Montana Council on Problem Gambling's 24-hour helpline (listed by the Montana Department of Justice)", "1-888-900-9979", "tel:18889009979", "https://dojmt.gov/gaming/compulsive-gambling/"]};
      // Wyoming's Department of Health points to the national helpline (health.wyo.gov/behavioralhealth/mhsa/problem-gambling/), so Wyoming shows that alone
function oddsHTML(r){
  const O = (BOOT.odds || {})[r.id]; if (!O || !(O.polymarket || O.kalshi)) return "";
  const block = (key, name) => { const M = O[key]; if (!M || !M.rows.length) return "";
    return `<div class="mkt"><div class="mh"><b>${name}</b><span>${esc(M.title || "")}</span></div>${M.rows.map(([label, p]) => `<div class="mrowo"><span>${esc(label)}</span><span class="mbar"><i style="width:${(100 * p).toFixed(1)}%"></i></span><b>${Math.round(100 * p)}&cent;</b></div>`).join("")}
      <p class="fnote">${Number(M.volume).toLocaleString()} ${M.unit === "contracts" ? "contracts" : "dollars"} traded in all. A price of 60&cent; means a contract paying $1 if that happens trades at 60&cent;.</p>
      <button type="button" class="mgo" data-url="${esc(M.url)}" data-name="${name}">Go to ${name}&hellip;</button></div>`; };
  const at = new Date(O.at);
  return `<section class="bsec" id="odds"><details class="oddswrap"><summary><h2>What bettors are paying</h2><span>Prices on two prediction markets, as information only. Not a poll, not a forecast and not an official record.</span></summary>
    <div class="mgrid">${block("polymarket", "Polymarket")}${block("kalshi", "Kalshi")}</div>
    <p class="fnote">Read from each market's public data on ${esc(at.toLocaleString("en-US", {month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"}))}. Prices move all day; the markets' own pages have the current ones. The Civic Archive takes no money from either market and uses no referral links.</p></details></section>`;
}
function marketNotice(url, name, st){
  const d = document.createElement("dialog"), H = HELPLINES[st];
  d.className = "mnotice";
  d.innerHTML = `<h3>You are leaving for ${esc(name)}</h3>
    <p>${esc(name)} is a market where people bet money on outcomes, including elections. Prices there are bets, not facts, and anyone can lose what they put in.</p>
    <ul><li>You must be at least 18 to use it; some places set a higher age.</li><li>Whether these markets are allowed where you live is disputed in some states. Check your state's law before you use one.</li></ul>
    <p class="mnh">If gambling is causing you or someone close to you harm, free and confidential help is there day and night:<br>
      <b>National Problem Gambling Helpline</b>: call or text <a href="tel:18006973738">1-800-MY-RESET</a>, or <a href="https://www.ncpgambling.org/help-treatment/" target="_blank" rel="noopener">chat online</a>.${H ? `<br><b>${esc(H[0])}</b>: <a href="${H[2]}">${esc(H[1])}</a> (<a href="${H[3]}" target="_blank" rel="noopener">about it</a>)` : ""}</p>
    <div class="mbtns"><button type="button" class="stay">Stay here</button><a class="goext" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Go to the market</a></div>`;
  document.body.appendChild(d);
  const close = () => { d.close(); d.remove(); };
  d.querySelector(".stay").addEventListener("click", close);
  d.querySelector(".goext").addEventListener("click", () => setTimeout(close, 50));
  d.addEventListener("cancel", e => { e.preventDefault(); close(); });
  d.showModal(); d.querySelector(".stay").focus();
}
document.addEventListener("click", e => { const b = e.target.closest(".mgo"); if (!b) return; const r = R[decodeURIComponent(location.hash.slice(6))]; marketNotice(b.dataset.url, b.dataset.name, r ? r.st : ""); });
/* ---------- polls: only pollsters in AAPOR's Transparency Initiative (John, 2026-09-29) ---------- */
const TI_LINK = `<a href="https://aapor.org/standards-and-ethics/transparency-initiative/" target="_blank" rel="noopener">Transparency Initiative</a>`;
const leftOutHTML = (L, other) => L && L.n ? `<p class="fnote">${L.n} ${other ? "other " : ""}published ${L.n === 1 ? "poll" : "polls"} of this race ${L.n === 1 ? "is" : "are"} from pollsters outside the Initiative and ${L.n === 1 ? "is" : "are"} not counted here: ${esc(L.pollsters.join(", "))}. Found in <a href="${esc(L.found_in)}" target="_blank" rel="noopener">Wikipedia's list of polls</a> (secondary), checked ${esc(fmtDate(L.checked))}.</p>` : "";
function pollsHTML(r){
  const P0 = (BOOT.polls || {})[r.id]; if (!P0) return "";
  if (!(P0.polls || []).length) return P0.left_out && P0.left_out.n ? `<section class="bsec" id="polls"><h2>Polls</h2><p class="sub">We show polls only from pollsters in the American Association for Public Opinion Research's ${TI_LINK}, who publish how each poll was done. None of them has published a poll of this race yet.</p>
    ${leftOutHTML(P0.left_out, false)}</section>` : "";
  const polls = [...P0.polls].sort((a, b) => b.end.localeCompare(a.end)), seen = new Set(), latest = [];
  for (const p of polls) if (!seen.has(p.pollster) && latest.length < 5) { seen.add(p.pollster); latest.push(p); }
  const names = [...new Set(polls.flatMap(p => Object.keys(p.shares)))];
  const range = p => p.start.slice(0, 7) === p.end.slice(0, 7) ? esc(fmtDate(p.end)).replace(/ (\d+),/, (_m, d) => ` ${+p.start.slice(8)}&ndash;${d},`) : `${fmtDate(p.start).replace(/, \d{4}$/, "")}&ndash;${esc(fmtDate(p.end))}`;
  const rows = latest.map(p => `<tr><td><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.pollster)}</a><small>${range(p)} &middot; ${Number(p.n).toLocaleString()} ${esc(p.pop)}, &plusmn;${p.moe}</small></td>${names.map(n => `<td>${p.shares[n] != null ? p.shares[n] + "%" : "&ndash;"}</td>`).join("")}<td>${p.rest != null ? p.rest + "%" : ""}</td></tr>`).join("");
  const ten = polls.slice(0, 10);
  const avg = ten.length > 1 ? `<p class="pavg"><b>Our average of the ${ten.length} most recent:</b> ${names.map(n => { const v = ten.filter(p => p.shares[n] != null).map(p => p.shares[n]); return v.length ? `${esc(n)} (${v.join(" + ")}) &divide; ${v.length} = <b>${(v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)}%</b>` : ""; }).filter(Boolean).join("; ")}.</p>`
    : `<p class="pavg">Only one poll qualifies so far, so there is no average yet; ours will take the ten most recent from these pollsters.</p>`;
  const L = P0.left_out, notes = polls.filter(p => p.note).map(p => `<li>${esc(p.pollster)}, ${range(p)}: ${esc(p.note)}</li>`).join("");
  return `<section class="bsec" id="polls"><h2>Polls</h2><p class="sub">Only from pollsters in the American Association for Public Opinion Research's ${TI_LINK}, who publish how each poll was done. The latest from up to five of them, each checked against the pollster's own release.</p>
    <div class="ptable"><table><thead><tr><th>Pollster and dates</th>${names.map(n => `<th>${esc(n)}</th>`).join("")}<th>Someone else or undecided</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${avg}${notes ? `<ul class="pnotes">${notes}</ul>` : ""}
    ${(P0.pending || []).length ? `<p class="fnote">Also by members, found but not counted until checked against the pollster's own release: ${P0.pending.map(x => `${esc(x.pollster)} (ending ${esc(fmtDate(x.end))}; ${esc(x.why)})`).join("; ")}.</p>` : ""}
    ${leftOutHTML(L, true)}
    <p class="fnote">A poll is a measure of opinion when it was taken, with a margin of error, not a forecast.</p></section>`;
}
/* ---------- maps: the districts on the ballot, drawn as on the Vote map (John, 2026-09-30) ---------- */
let DIST = null, mapOff = null;
const needDist = () => DIST ? Promise.resolve(DIST) : fetch(BOOT.dist.url).then(r => r.ok ? r.json() : Promise.reject(r.status))
  .then(d => (DIST = d), () => (DIST = {q: 50, states: {}, failed: true}));
const decodeRing = (ring, q) => { let x = 0, y = 0; const pts = []; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; pts.push([x / q, y / q]); } return pts; };
const pathOf = rings => rings.map(p => "M" + p.map(v => v[0].toFixed(2) + "," + v[1].toFixed(2)).join("L") + "Z").join("");
const areaOf = pts => { let a = 0; for (let i = 0, n = pts.length; i < n; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % n]; a += x0 * y1 - x1 * y0; } return Math.abs(a) / 2; };
const centroidOf = pts => { let a = 0, cx = 0, cy = 0; for (let i = 0, n = pts.length; i < n; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % n], f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f; } a *= .5; return a ? [cx / (6 * a), cy / (6 * a)] : pts[0]; };
const linesChanged = st => !!(BOOT.notes[st] && BOOT.notes[st].changed);
const houseOf = st => (byState[st] || []).filter(r => r.o === "H");
const senateOf = st => (byState[st] || []).filter(r => r.o === "S");
const raceOfD = (st, n) => houseOf(st).find(r => +r.d === +n);
const distCache = {};
function districtsOf(st){      // [{n, d, area, c}]; the whole state for an at-large seat; null where no lines are drawn
  if (!DIST) return null;
  if (distCache[st] !== undefined) return distCache[st];
  if (linesChanged(st)) return distCache[st] = null;      // new lines for 2026: the old ones would be the wrong districts
  const raw = DIST.states[st];
  if (!raw) {
    if (houseOf(st).length !== 1 || !BOOT.map[st]) return distCache[st] = null;
    const [x0, y0, x1, y1] = BOOT.sbox[st];
    return distCache[st] = [{n: 0, d: BOOT.map[st], area: (x1 - x0) * (y1 - y0), c: [(x0 + x1) / 2, (y0 + y1) / 2], whole: true}];
  }
  const q = DIST.q || 50;
  return distCache[st] = Object.entries(raw).map(([n, rings]) => {
    const pts = rings.map(r => decodeRing(r, q)), big = pts.reduce((m, r) => areaOf(r) > areaOf(m) ? r : m, pts[0]);
    return {n: +n, d: pathOf(pts), area: pts.reduce((t, r) => t + areaOf(r), 0), c: centroidOf(big)};
  }).sort((a, b) => a.n - b.n);
}
/* a seat's colour is the party that holds it today; striped when that member is not on the seat's November ballot */
const HOLD = r => r && r.h ? (HOLDPARTY[r.h[2]] || "I") : null;
const PVAR = {D: "var(--pD)", R: "var(--pR)", I: "var(--pI)"};
function seatState(r){
  if (!r || !r.h) return "vacant";
  if (!listed.has(r.st)) return "unknown";
  return general(r).some(c => c.bio === r.h[0]) ? "running" : "open";
}
const seatFill = (r, id) => { const h = HOLD(r); return !h ? "var(--line-strong)" : seatState(r) === "open" ? `url(#${id}-open-${h})` : PVAR[h]; };
const openDefs = (id, w) => `<defs>${["D", "R", "I"].map(h => `<pattern id="${id}-open-${h}" patternUnits="userSpaceOnUse" width="${w.toFixed(3)}" height="${w.toFixed(3)}" patternTransform="rotate(45)"><rect width="${w.toFixed(3)}" height="${w.toFixed(3)}" style="fill:${PVAR[h]};opacity:.28"/><rect width="${(w * .42).toFixed(3)}" height="${w.toFixed(3)}" style="fill:${PVAR[h]}"/></pattern>`).join("")}</defs>`;
const aspectOf = b => Math.min(1.75, Math.max(.8, (b[2] - b[0]) / Math.max(1, b[3] - b[1])));
const fitBox = (b, aspect, pad) => { let w = (b[2] - b[0]) * pad, h = (b[3] - b[1]) * pad; if (w / h > aspect) h = w / aspect; else w = h * aspect; return [(b[0] + b[2]) / 2 - w / 2, (b[1] + b[3]) / 2 - h / 2, w, h]; };
const ONE = {D: "a Democrat", R: "a Republican", I: "an independent"}, MANY = {D: "Democrats", R: "Republicans", I: "independents"};
function seatWords(r){
  const s = seatState(r); if (s === "vacant") return "The seat is vacant today.";
  const who = `Held today by <b>${esc(r.h[1])}</b> (${esc(r.h[2])})`;
  return s === "running" ? `${who}, who is on the ballot again.` : s === "open" ? `${who}, who is not on the ballot for it: an open seat.` : `${who}. The state's official list is not loaded yet.`;
}
const plain = html => String(html).replace(/<[^>]+>/g, "");
function preview(r){      // a race in the side panel: who holds it, who is running, and the way in
  const g = general(r), h = HOLD(r);
  const who = g.length ? `<ol class="plist">${g.map(c => { const pp = P(c), age = ageOf(pp.dob);
      return `<li style="--pc:${pcVar(c)}"><span class="av">${pp.ph ? `<img src="${esc(pp.ph)}" alt="" loading="lazy" decoding="async">` : esc(initials(c.n).toUpperCase())}</span><span><b>${esc(c.n)}${c.inc ? '<span class="star" title="Serves in this chamber today">&#9733;</span>' : ""}</b><small>${esc(shortParty(c))}${age != null ? ` &middot; age ${age}` : ""}</small></span></li>`; }).join("")}</ol>`
    : `<p class="held">${listed.has(r.st) ? "No candidate for this race is on the state's list." : `The official candidate list for ${esc(NAMES[r.st])} is not loaded yet.`}</p>`;
  return `<span class="kick">${r.o === "S" ? "U.S. Senate" : "U.S. House"}${r.sp ? " &middot; special election" : ""}</span>
    <h3>${r.o === "H" ? `<span class="dnum" style="--pc:${h ? PVAR[h] : "var(--line-strong)"}">${+r.d || "AL"}</span>` : ""}${esc(r.o === "S" ? NAMES[r.st] : raceShort(r))}</h3>
    <p class="held">${seatWords(r)}</p>${who}<a class="rpgo" href="#race=${esc(r.id)}">Open the race &rsaquo;</a>`;
}
function sideSummary(st, view){
  if (view === "S") { const s = senateOf(st)[0]; return s ? preview(s) : `<p class="held">No Senate seat from ${esc(NAMES[st])} is on the ballot in 2026.</p>`; }
  const hs = houseOf(st), n = {D: 0, R: 0, I: 0}; let open = 0, vac = 0;
  hs.forEach(r => { const h = HOLD(r); if (h) n[h]++; else vac++; if (seatState(r) === "open") open++; });
  const rows = ["D", "R", "I"].filter(k => n[k]).map(k => `<li><i style="background:${PVAR[k]}"></i>${n[k]} held by ${n[k] === 1 ? ONE[k] : MANY[k]}</li>`);
  if (vac) rows.push(`<li><i style="background:var(--line-strong)"></i>${vac} vacant</li>`);
  if (listed.has(st)) rows.push(`<li><i style="background:repeating-linear-gradient(45deg,var(--muted) 0 2px,transparent 2px 5px)"></i>${open ? `${open} open ${open === 1 ? "seat" : "seats"}: the member who holds it is not on its ballot` : "No open seat: every member is on the ballot again"}</li>`);
  return `<span class="kick">${esc(NAMES[st])} &middot; U.S. House</span><h3>${hs.length === 1 ? "One seat, at large" : `${hs.length} districts`}</h3>
    <ul class="tally">${rows.join("")}</ul><p class="sidehint">${matchMedia("(hover: hover)").matches ? "Point at a district to see who is running there; click to keep it here." : "Tap a district to see who is running there."}</p>`;
}
function stateMapHTML(st){
  const s = senateOf(st).length;
  return `<section class="bsec" id="mapsec"><h2>On the map</h2><p class="sub">Each district in the colour of the party that holds it today; striped where the member who holds it is not on the ballot for it. The colours say who holds a seat, never who will win it.</p>
    <div class="mapgrid"><div class="mapcol">
      <div class="mapbar"><div class="seg" role="group" aria-label="Which seats to show"><button type="button" data-v="H" aria-pressed="true">House districts</button><button type="button" data-v="S" aria-pressed="false"${s ? "" : ' disabled title="No Senate race in this state in 2026"'}>Senate seat</button></div>
        <div class="zoom" role="group" aria-label="Zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">&minus;</button><button type="button" data-z="fit" aria-label="Show the whole state">&#10530;</button></div></div>
      <div class="svgbox" id="svgbox"><svg class="bstate" id="bstate" role="group" aria-label="Map of ${esc(NAMES[st])}'s congressional districts"></svg></div>
      <p class="mnote" id="bnote"></p></div>
    <aside class="mapside" id="mapside" aria-live="polite"></aside></div></section>`;
}
async function mountStateMap(st){
  const svg = $("#bstate"), side = $("#mapside"), box = $("#svgbox"), note = $("#bnote"); if (!svg) return;
  side.innerHTML = sideSummary(st, "H");
  await needDist();
  if (!svg.isConnected) return;      // the reader moved on while the lines loaded
  const B = BOOT.sbox[st], vb0 = fitBox(B, aspectOf(B), 1.08), list = districtsOf(st), hover = matchMedia("(hover: hover)").matches;
  let vb = vb0.slice(), view = "H", sel = null, drag = null, moved = false;
  const byN = Object.fromEntries((list || []).map(D => [D.n, D]));
  const unitsPerPx = () => vb[2] / Math.max(1, svg.getBoundingClientRect().width || 640);
  function relabel(){
    const s = unitsPerPx();
    $$("text.dlab", svg).forEach(t => { const D = byN[t.dataset.d]; if (!D) return;
      t.setAttribute("transform", `translate(${D.c[0].toFixed(2)} ${D.c[1].toFixed(2)}) scale(${s.toFixed(4)})`);
      t.classList.toggle("tiny", D.area / (s * s) < 650 && +t.dataset.d !== sel); });
  }
  const setVB = v => { vb = v; svg.setAttribute("viewBox", v.map(x => x.toFixed(2)).join(" ")); box.classList.toggle("zoomed", v[2] < vb0[2] * .98); relabel(); };
  function ring(){
    $$("path.ring", svg).forEach(p => p.remove());
    const d = view === "S" ? BOOT.map[st] : sel != null && byN[sel] ? byN[sel].d : null;
    if (d && (view === "H" ? list && list.length > 1 : true)) svg.insertAdjacentHTML("beforeend", `<path class="ring" d="${d}"/>`);
  }
  function draw(){
    let body = openDefs("sm", vb0[2] / 90);
    if (view === "S") {
      const r = senateOf(st)[0];
      body += `<path class="whole" data-race="${esc(r.id)}" d="${BOOT.map[st]}" style="fill:${seatFill(r, "sm")}" tabindex="0" role="button" aria-label="${esc(raceName(r))}: ${esc(plain(seatWords(r)))}"/>`;
      note.innerHTML = `The whole state votes for this seat.`;
    } else if (!list) {
      body += `<path class="whole nolines" d="${BOOT.map[st]}"/><text class="big" transform="translate(${((B[0] + B[2]) / 2).toFixed(1)} ${((B[1] + B[3]) / 2).toFixed(1)}) scale(${unitsPerPx().toFixed(4)})" dy=".35em">${linesChanged(st) ? "New district lines for 2026" : "District lines not loaded"}</text>`;
      note.innerHTML = linesChanged(st) ? `${esc(NAMES[st])} drew new congressional lines for 2026${BOOT.notes[st].note ? ` (${esc(BOOT.notes[st].note.replace(/\.\s*$/, ""))})` : ""}. The new map is not drawn here yet, so the districts are listed below but not shown; the old lines would be the wrong districts.`
        : DIST.failed ? "The district lines could not be loaded. Check your connection and open the page again." : "";
    } else {
      body += list.map(D => { const r = raceOfD(st, D.n), s = seatState(r);
        return `<path class="dist${s === "unknown" ? " unk" : ""}${s === "vacant" ? " vac" : ""}" data-d="${D.n}" d="${D.d}" style="fill:${seatFill(r, "sm")}" tabindex="0" role="button" aria-label="${esc(r ? raceName(r) : "District " + D.n)}. ${esc(r ? plain(seatWords(r)) : "")}"/>`; }).join("");
      if (list.length > 1) body += list.map(D => `<text class="dlab" data-d="${D.n}" dy=".36em">${D.n}</text>`).join("");
      body += `<path class="sout" d="${BOOT.map[st]}"/>`;
      note.innerHTML = list[0].whole ? "The whole state is one district, elected at large." : `District lines: ${esc(DIST.vintage || "the current lines")}, the lines on ${esc(NAMES[st])}'s 2026 ballot.`;
    }
    svg.innerHTML = body;
    setVB(vb); ring();
  }
  function show(n, keep){
    const r = view === "S" ? senateOf(st)[0] : raceOfD(st, n); if (!r) return;
    if (keep) { sel = view === "S" ? null : +n; ring(); relabel(); }
    side.innerHTML = preview(r);
  }
  const rest = () => { side.innerHTML = view === "S" ? sideSummary(st, "S") : sel != null ? preview(raceOfD(st, sel)) : sideSummary(st, "H"); };
  const toUnits = e => { const b = svg.getBoundingClientRect(); return [vb[0] + (e.clientX - b.left) / b.width * vb[2], vb[1] + (e.clientY - b.top) / b.height * vb[3]]; };
  function zoomAt(f, at){
    const w = Math.min(vb0[2], Math.max(vb0[2] / 14, vb[2] / f)), k = w / vb[2], h = vb[3] * k, [px, py] = at || [vb[0] + vb[2] / 2, vb[1] + vb[3] / 2];
    setVB(clamp([px - (px - vb[0]) * k, py - (py - vb[1]) * k, w, h]));
  }
  const clamp = v => [Math.min(Math.max(v[0], vb0[0]), vb0[0] + vb0[2] - v[2]), Math.min(Math.max(v[1], vb0[1]), vb0[1] + vb0[3] - v[3]), v[2], v[3]];
  svg.addEventListener("click", e => {
    if (moved) { moved = false; return; }
    const p = e.target.closest("path.dist, path.whole"); if (!p || p.classList.contains("nolines")) return;
    show(p.dataset.d, true);
    if (!hover && side.getBoundingClientRect().top > innerHeight - 80) side.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"});
  });
  svg.addEventListener("keydown", e => { if (e.key !== "Enter" && e.key !== " ") return; const p = e.target.closest("path.dist, path.whole"); if (p && !p.classList.contains("nolines")) { e.preventDefault(); show(p.dataset.d, true); } });
  if (hover) {
    svg.addEventListener("pointerover", e => { const p = e.target.closest("path.dist"); if (!p || drag) return; $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")); p.classList.add("hl"); show(p.dataset.d, false); });
    svg.addEventListener("pointerleave", () => { $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")); rest(); });
  }
  if (mapOff) mapOff.abort();      // the window's listeners from the last map opened go with it
  mapOff = new AbortController();
  const sig = {signal: mapOff.signal};
  svg.addEventListener("dblclick", e => { e.preventDefault(); zoomAt(2, toUnits(e)); });
  svg.addEventListener("pointerdown", e => { moved = false; if (!box.classList.contains("zoomed") || e.button) return; drag = {x: e.clientX, y: e.clientY, vb: vb.slice()}; });
  addEventListener("pointermove", e => {      // no pointer capture: the map lets the page keep its clicks
    if (!drag || !svg.isConnected) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!moved && Math.hypot(dx, dy) < 4) return;
    moved = true; box.classList.add("drag"); const k = unitsPerPx(); setVB(clamp([drag.vb[0] - dx * k, drag.vb[1] - dy * k, vb[2], vb[3]]));
  }, sig);
  addEventListener("pointerup", () => { if (drag) { drag = null; box.classList.remove("drag"); } }, sig);
  $$(".zoom button", $("#mapsec")).forEach(b => b.addEventListener("click", () => { if (b.dataset.z === "fit") setVB(vb0.slice()); else zoomAt(b.dataset.z === "in" ? 1.8 : 1 / 1.8); }));
  $$(".seg button", $("#mapsec")).forEach(b => b.addEventListener("click", () => {
    if (b.disabled || b.dataset.v === view) return;
    view = b.dataset.v; sel = null; $$(".seg button", $("#mapsec")).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    draw(); rest();
  }));
  addEventListener("resize", () => { if (svg.isConnected) relabel(); }, sig);
  draw();
}
function locatorHTML(){ return `<figure class="loc"><svg id="locsvg" role="img" aria-label="Where this race is"></svg><figcaption id="loccap"></figcaption></figure>`; }
async function mountLocator(r){      // the race's own district picked out on its state; a tap on another district opens that race
  const svg = $("#locsvg"); if (!svg) return;
  await needDist(); if (!svg.isConnected) return;
  const st = r.st, B = BOOT.sbox[st], vb = fitBox(B, aspectOf(B), 1.06), list = r.o === "H" ? districtsOf(st) : null;
  let body = openDefs("lm", vb[2] / 60), cap = "";
  if (r.o === "S") { body += `<path class="lme" d="${BOOT.map[st]}" style="fill:${seatFill(r, "lm")}"/>`; cap = "The whole state votes for this seat."; }
  else if (list) {
    const me = list.find(D => D.n === +r.d);
    body += list.filter(D => D !== me).map(D => `<path class="lot" data-d="${D.n}" d="${D.d}"><title>${esc(raceShort({o: "H", d: D.n}))}</title></path>`).join("");
    if (me) body += `<path class="lme" d="${me.d}" style="fill:${seatFill(r, "lm")}"/>`;
    body += `<path class="lout" d="${BOOT.map[st]}"/>`;
    cap = me && me.whole ? "The whole state is one district." : me ? `District ${me.n} of ${list.length}${list.length > 1 ? ". Tap another district to open its race." : "."}` : "";
  } else { body += `<path class="lst" d="${BOOT.map[st]}"/>`; cap = linesChanged(st) ? "New district lines for 2026: the new map is not drawn here yet." : "District lines not available."; }
  svg.setAttribute("viewBox", vb.map(v => v.toFixed(2)).join(" ")); svg.innerHTML = body; $("#loccap").textContent = cap;
  svg.addEventListener("click", e => { const p = e.target.closest("path.lot"); const rr = p && raceOfD(st, p.dataset.d); if (rr) location.hash = "race=" + rr.id; });
}

/* ---------- pages ---------- */
function home(anchor){
  const H = BOOT.races.filter(r => r.o === "H").length, S = BOOT.races.filter(r => r.o === "S");
  const cands = BOOT.races.reduce((n, r) => n + general(r).length, 0);
  const mine = JSON.parse(store.get("ballot:mine") || "null") || {st: store.get("state") || "", d: ""};
  const opts = Object.keys(NAMES).sort((a, b) => NAMES[a].localeCompare(NAMES[b])).map(s => `<option value="${s}"${s === mine.st ? " selected" : ""}>${esc(NAMES[s])}</option>`).join("");
  $("#app").innerHTML = `<section class="bhero"><span class="eyebrow">On The Ballot &middot; U.S. Congress</span>
    <h1>Who&rsquo;s running for <em>Congress</em></h1>
    <p class="lede">Every House seat and 35 Senate seats are on the November 3, 2026 ballot. Who is running comes from each state&rsquo;s own official list of candidates, added one state at a time; the primaries that chose them come from the official results.</p>
    <span class="countdown"><i></i>${esc(dayWords())}</span>
    <div class="kchips"><div class="kchip"><b>${H}</b><span>House races</span></div><div class="kchip"><b>${S.length}</b><span>Senate races</span></div><div class="kchip"><b>${listed.size} of 50</b><span>states' lists loaded</span></div><div class="kchip"><b>${cands}</b><span>candidates listed so far</span></div></div></section>
  <section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Pick your state and your congressional district. The choice stays on this device.</p>
    <div class="mybar"><select id="mst" aria-label="Your state"><option value="">Your state</option>${opts}</select><select id="mdi" aria-label="Your district"></select></div>
    <div class="mine" id="minelist"></div></section>
  <section class="bsec" id="senate"><h2>The Senate races</h2><p class="sub">Thirty-three seats whose terms end in January, and ${S.filter(r => r.sp).length} special elections for the rest of a term.</p>
    <div class="rgrid">${S.map(raceCard).join("")}</div></section>
  <section class="bsec" id="states"><h2>Every state</h2><p class="sub">Filled states have their official candidate list loaded. The rest are coming, largest first. Switch the map to see the Senate seats on the ballot.</p>
    <div class="mapbar" style="margin-top:12px"><div class="seg" role="group" aria-label="What the map shows" id="useg"><button type="button" data-u="lists" aria-pressed="true">Official lists</button><button type="button" data-u="senate" aria-pressed="false">Senate races</button></div></div>
    <svg class="usballot" id="usballot" viewBox="0 0 975 610" role="img" aria-label="Map of the states"><defs><pattern id="bhatch" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--surface)"/><rect width="2.5" height="7" fill="var(--accent)" opacity=".35"/></pattern></defs>${openDefs("us", 7)}
      ${Object.entries(BOOT.map).map(([s, d]) => NAMES[s] ? `<path class="${listed.has(s) ? "on" : "off"}" d="${d}" data-st="${s}"><title>${esc(NAMES[s])}: ${listed.has(s) ? "list loaded" : "list coming"}</title></path>` : "").join("")}</svg>
    <div class="mkey" id="ukey"></div>
    <div class="sgrid">${Object.keys(NAMES).sort((a, b) => NAMES[a].localeCompare(NAMES[b])).map(s => `<a class="scard2" href="#state=${s}"><b>${esc(NAMES[s])}</b><span>${(byState[s] || []).filter(r => r.o === "H").length} House ${(byState[s] || []).filter(r => r.o === "H").length === 1 ? "seat" : "seats"}${(byState[s] || []).some(r => r.o === "S") ? ", a Senate race" : ""}${BOOT.notes[s] && BOOT.notes[s].changed ? ", new district lines" : ""}</span><br><span class="pill2${listed.has(s) ? "" : " no"}">${listed.has(s) ? "List loaded" : "Coming"}</span></a>`).join("")}</div></section>
  ${sourcesHTML()}`;
  const mst = $("#mst"), mdi = $("#mdi");
  const fill = () => { const st = mst.value, hs = (byState[st] || []).filter(r => r.o === "H");
    mdi.innerHTML = hs.length ? hs.map(r => `<option value="${esc(r.d)}"${r.d === mine.d ? " selected" : ""}>${esc(raceShort(r))}</option>`).join("") : `<option value="">District</option>`;
    mdi.hidden = !st || hs.length <= 1; showMine(); };
  const showMine = () => { const st = mst.value; if (!st) { $("#minelist").innerHTML = ""; return; }
    const d = (byState[st] || []).filter(r => r.o === "H").length === 1 ? "00" : mdi.value;
    store.set("ballot:mine", JSON.stringify({st, d}));
    const mineR = (byState[st] || []).filter(r => r.o === "S" || r.d === d);
    $("#minelist").innerHTML = `${stateNote(st)}<div class="rgrid">${mineR.map(raceCard).join("")}</div>`; };
  mst.addEventListener("change", () => { mine.d = ""; fill(); }); mdi.addEventListener("change", showMine); fill();
  $("#usballot").addEventListener("click", e => { const p = e.target.closest("path[data-st]"); if (p) location.hash = "state=" + p.dataset.st; });
  const usMode = mode => {      // the same map two ways: whose lists are loaded, and the Senate seats on the ballot
    $$("#usballot path[data-st]").forEach(p => { const st = p.dataset.st, s = senateOf(st)[0], t = p.querySelector("title");
      if (mode === "senate") { p.setAttribute("class", s ? `sen${seatState(s) === "unknown" ? " unk" : ""}` : "none"); p.style.fill = s ? seatFill(s, "us") : ""; t.textContent = `${NAMES[st]}: ${s ? plain(seatWords(s)) : "no Senate race in 2026"}`; }
      else { p.setAttribute("class", listed.has(st) ? "on" : "off"); p.style.fill = ""; t.textContent = `${NAMES[st]}: ${listed.has(st) ? "list loaded" : "list coming"}`; } });
    $("#ukey").innerHTML = mode === "senate"
      ? `<span><i style="background:var(--pD)"></i>Held by a Democrat</span><span><i style="background:var(--pR)"></i>Held by a Republican</span><span><i style="background:repeating-linear-gradient(45deg,var(--muted) 0 2px,var(--surface) 2px 6px)"></i>Open seat: the senator is not on the ballot for it</span><span><i style="background:var(--line)"></i>No Senate race in 2026</span><span>Paler: the state's list is not loaded yet, so an open seat is not marked</span>`
      : `<span><i style="background:var(--accent)"></i>Official list loaded</span><span><i style="background:repeating-linear-gradient(45deg,var(--accent) 0 2px,var(--surface) 2px 7px)"></i>Coming</span>`;
    $$("#useg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.u === mode)));
  };
  $$("#useg button").forEach(b => b.addEventListener("click", () => usMode(b.dataset.u)));
  usMode("lists");
  if (anchor && $("#" + anchor)) $("#" + anchor).scrollIntoView();
}
function statePage(st){
  const rs = byState[st] || []; if (!rs.length) { home(); return; }
  const src = Object.values(BOOT.sources).filter(s => s.state === st);
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><span>${esc(NAMES[st])}</span></nav>
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${esc(NAMES[st])}</span><h1>${esc(NAMES[st])}</h1>
    <p class="lede">${rs.filter(r => r.o === "H").length} House ${rs.filter(r => r.o === "H").length === 1 ? "seat" : "seats"}${rs.some(r => r.o === "S") ? " and a Senate seat" : ""} on the November 3 ballot. ${listed.has(st) ? "Candidates from the state's official list." : "The state's official candidate list is not loaded yet; each race says who holds the seat today."}</p>
    ${stateNote(st)}</section>
  ${stateMapHTML(st)}
  ${rs.some(r => r.o === "S") ? `<section class="bsec"><h2>Senate</h2><div class="rlist">${rs.filter(r => r.o === "S").map(raceRow).join("")}</div></section>` : ""}
  <section class="bsec"><h2>House</h2><div class="rlist">${rs.filter(r => r.o === "H").map(raceRow).join("")}</div></section>
  ${src.length ? `<section class="bsec"><h2>Where this comes from</h2><div class="srclist">${src.map(srcItem).join("")}</div></section>` : ""}`;
  mountStateMap(st);
}
function holderLine(r){
  if (!r.h) return `<p class="holder">The seat is vacant today.</p>`;
  const [bio, name, party] = r.h, g = general(r), runs = BOOT.runs[bio] || [];
  let tail = "";
  if (listed.has(r.st)) {
    if (g.some(c => c.bio === bio)) tail = ", who is on the ballot again";
    else { const lost = runs.find(x => x[0] === r.id && x[2] === "lost"), elsewhere = runs.find(x => x[0] !== r.id && x[1] === "general");
      const pn = lost ? (BOOT.elections[lost[1]] || "primary") : "", when = lost ? ((r.el[lost[1]] || [])[0] || {}).date : "";
      tail = lost ? `, who lost the ${esc(pn.startsWith("Top") ? pn.toLowerCase() : pn)}${when ? " on " + esc(fmtDate(when).replace(/, \d{4}$/, "")) : ""}`
        : elsewhere ? `, who is on the ballot for ${esc(raceName(R[elsewhere[0]]))} instead` : ", who is not on the November ballot for this seat"; }
  }
  const moved = r.o === "H" && BOOT.notes[r.st] && BOOT.notes[r.st].changed ? " The district's lines changed for 2026, so the seat numbered here may cover different ground." : "";
  return `<p class="holder">Held today by <b><a href="../../us/#member=${esc(bio)}">${esc(name)}</a></b> (${esc(party)})${tail}.${moved}</p>`;
}
function racePage(id){
  const r = R[id]; if (!r) { home(); return; }
  const prim = Object.keys(r.el || {}).filter(k => k !== "general").sort();
  const srcs = [...new Set(Object.values(r.el || {}).flat().map(c => c.src))].map(s => BOOT.sources[s]).filter(Boolean);
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><a href="#state=${r.st}">${esc(NAMES[r.st])}</a><span>&rsaquo;</span><span>${esc(raceShort(r))}</span></nav>
  <section class="bhero withloc"><div><span class="eyebrow">${r.o === "S" ? "U.S. Senate" : "U.S. House"} &middot; ${esc(fmtDate(r.date))}</span><h1>${esc(raceName(r))}</h1>
    ${holderLine(r)}${r.note ? `<p class="holder">${esc(r.note)}</p>` : ""}${general(r).length ? `<button type="button" class="rshare" id="rshare">Share this race</button>` : ""}</div>${locatorHTML()}</section>
  ${general(r).length ? arena(r) : `<div class="notebox">${listed.has(r.st) ? "No candidate for this race is on the state's list." : `The official candidate list for ${esc(NAMES[r.st])} is not loaded yet. We add each state from its own election office, largest first.`}</div>`}
  ${pollsHTML(r)}
  ${adsHTML(r)}
  ${oddsHTML(r)}
  ${prim.length ? `<section class="bsec"><h2>How they got here</h2><p class="sub">${prim.length === 1 && prim[0] === "primary" ? "California's primary is top-two: every candidate, of every party preference, on one ballot." : "Each party chose its nominee in its own primary. A party with a single candidate held none."}</p>${prim.map(k => field(r, k)).join("")}</section>` : ""}
  ${srcs.length ? `<section class="bsec"><h2>Where this comes from</h2><div class="srclist">${srcs.map(srcItem).join("")}</div></section>` : ""}`;
  mountLocator(r);
  const sh = $("#rshare");
  if (sh) sh.addEventListener("click", async () => {      // the share page carries the preview card; it opens the race
    const url = `https://thecivicarchive.github.io/dev/ballot/us/r/${r.id}.html`, title = `${raceName(r)}: who is on the ballot`;
    try { if (navigator.share) { await navigator.share({title, url}); return; } await navigator.clipboard.writeText(url); sh.textContent = "Link copied"; }
    catch (e) { if (e && e.name !== "AbortError") { sh.textContent = url; } }
  });
  const b = $("#aopen");
  if (b) b.addEventListener("click", () => { const c = $("#cmp"); if (c.hidden) { c.innerHTML = compare(r); c.hidden = false; b.setAttribute("aria-expanded", "true"); b.querySelector("span").textContent = "Close the comparison"; c.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); }
    else { c.hidden = true; b.setAttribute("aria-expanded", "false"); b.querySelector("span").textContent = "Step into the arena: compare them side by side"; } });
}
const srcItem = s => `<div class="srcitem"><b>${esc(s.agency)}</b>: ${esc(s.title)}<small><span class="tag fact">Fact</span> <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a> &middot; fetched ${esc(s.fetched)} &middot; ${Number(s.rows || 0).toLocaleString()} rows &middot; SHA-256 ${esc((s.sha || "").slice(0, 16))}&hellip;${s.note ? " &middot; " + esc(s.note) : ""}</small></div>`;
function sourcesHTML(){
  return `<section class="bsec" id="sources"><h2>Sources and methods</h2>
    <ul class="method sub">
      <li><b>Who is running</b> comes only from each state's own election office: its certified list of candidates, or its official results where the list is the result of a primary. A state appears once its list is loaded; until then its races say who holds the seat today and nothing more.</li>
      <li><b>Order.</b> Candidates appear in the order the state's list gives them, or by surname where the list gives no ballot order. Never by money, polls or party.</li>
      <li><b>Parties</b> are printed exactly as the official list prints them. Colours are for telling the cards apart only.</li>
      <li><b>Money</b> is the 2026 cycle from the Federal Election Commission's bulk files: what each campaign reported, organizations named, people only as a total. A candidate's own fundraising committees and joint fundraising committees are moved in, not donors. Outside spending is kept apart, because the campaign never received it.</li>
      <li><b>Age and offices held</b> come from official records only: the Biographical Directory of the U.S. Congress for anyone who serves or served there, and the Open States roster for state legislators and statewide officials. Years in office count every office on record once, however they overlap; "at least" means a record lacks a start date. Where no record gives a birth date or an office, the card says so; nothing is estimated.</li>
      <li><b>Photos</b> are shown to help you recognise people: official portraits for members of Congress (public domain) and state legislators (their legislature's own, via Open States). Where no official photo exists, initials stand in; photos from candidates' own campaign websites, credited and linked, are being added.</li>
      <li><b>Maps.</b> District lines are the Census Bureau's cartographic boundary file for the 119th Congress: the lines on the 2026 ballot in every state that did not draw new ones. Where a state drew new lines for 2026, its districts are listed but not drawn until its new lines are loaded, because the old ones would be the wrong districts. A seat's colour is the party of the member who holds it today; striped means that member is not on the seat's November ballot. The colours say who holds a seat, never who will win it.</li>
      <li><b>Nobody is scored or graded.</b> The cards show the record; the judging is yours.</li>
      <li><b>Still to come:</b> vote counts for primaries where only the winner is loaded, ads (spending by kind, for and against, and links to the public ad libraries), polls from pollsters in AAPOR's Transparency Initiative, each campaign's own issues page, and then state and local races.</li>
    </ul>
    <div class="srclist">${Object.values(BOOT.sources).sort((a, b) => NAMES[a.state].localeCompare(NAMES[b.state])).map(srcItem).join("")}
      <div class="srcitem"><b>Federal Election Commission</b>: bulk data files for the 2025&ndash;2026 cycle (candidates, committees, campaign totals, committee payments)<small><span class="tag fact">Fact</span> <a href="https://www.fec.gov/data/browse-data/?tab=bulk-data" target="_blank" rel="noopener">fec.gov/data/browse-data/?tab=bulk-data</a></small></div>
      <div class="srcitem"><b>National Conference of State Legislatures</b>: the notes on new district lines<small><span class="tag analysis">Secondary</span> <a href="https://www.ncsl.org/redistricting-and-census/changing-the-maps-tracking-mid-decade-redistricting" target="_blank" rel="noopener">Changing the Maps: Tracking Mid-Decade Redistricting</a>, updated September 11, 2026</small></div>
    </div></section>`;
}

/* ---------- the address decides the page ---------- */
function route(){
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("state=")) statePage(h.slice(6).toUpperCase());
  else { home(h); if (!h) scrollTo(0, 0); return; }
  scrollTo(0, 0);
}
addEventListener("hashchange", route);
route();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--record", default=os.path.join(HERE, "congress_119.sqlite"))
    ap.add_argument("--out", default=os.path.join(HERE, "site", "dev", "ballot", "us", "index.html"))
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit("No ballot database yet. Run: python run_ballot.py")
    site_root = os.path.join(HERE, "site", "dev")
    boot = build(args.db, args.record, site_root, os.path.dirname(args.out))
    version = (boot["changelog"][0].get("version") if boot["changelog"] else "") or ""
    page = PAGE.replace("__CSS__", borrow("CSS")).replace("__MONEYFMT__", borrow("MONEYFMT")).replace("__CHANGELOG__", borrow("CHANGELOG"))
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    from ballot.share_race import write as write_share      # a share page and preview image for every race with a list
    write_share(os.path.dirname(args.out), boot)
    loaded = sum(1 for r in boot["races"] if r["el"].get("general"))
    print(f"Version {version}")
    print(f"Wrote {args.out}: {len(boot['races'])} races ({loaded} with the official list loaded), "
          f"{len(boot['listed'])} states listed, {len(boot['money'])} campaigns' money, {len(boot['members'])} members' records, "
          f"{len(page.encode('utf-8')) / 1e3:,.0f} KB")


if __name__ == "__main__":
    main()
