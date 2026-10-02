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

Two things start folded (John, 2026-10-01). Under each candidate, "The ads themselves" is one closed fold whose summary
says how many ads and of what kinds; its list is fetched when it is first opened and shown five ads at a time, each
five a closed fold of its own headed by its numbers and dates. And every page's sources ("Where this comes from",
"Sources and methods") are one closed fold with a closed fold inside it for each kind of source the page has, the
page's own rules filed under the kind they are about. The script that draws those folds sits between the
"source folds" landmarks in PAGE, and build_ballot_state_dev.py takes it from there, so the state pages fold the same way.

Data: ballot_2026.sqlite (run_ballot.py), congress_119.sqlite for who holds each seat, and the draft site's member
files (site/dev/us/data/member/) for a sitting member's record, so both sides say the same thing. The page takes
the site's stylesheet and a few shared script parts from build_site_dev.py by the landmarks build_state_dev.py uses.
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.parse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ballot.common import DB, GENERAL, STATE_NAMES                              # noqa: E402
from build_site_dev import read_changelog, state_paths                          # noqa: E402
from build_state_dev import borrow                                              # noqa: E402
from money_views import KIND_LABELS, PAC_LIMIT, committee_kind, tidy_name       # noqa: E402

ELECTION_NAMES = {"general": "General election", "open-primary": "Open primary", "primary": "Top-two primary", "primary-DEM": "Democratic primary", "primary-LMN": "Legal Marijuana NOW primary",
                  "primary-REP": "Republican primary", "primary-LPF": "Libertarian primary", "primary-LIB": "Libertarian primary", "primary-GRE": "Green primary",
                  "primary-DFL": "Democratic-Farmer-Labor primary",
                  "runoff-REP": "Republican primary runoff", "runoff-DEM": "Democratic primary runoff",
                  "primary-AZI": "Arizona Independent Party primary", "primary-NL": "No Labels primary",
                  "special-primary-REP": "Special Republican primary", "special-runoff-REP": "Special Republican primary runoff",
                  "special-primary-DEM": "Special Democratic primary", "special-runoff-DEM": "Special Democratic primary runoff",
                  "primary-NP": "Nonpartisan primary", "primary-CON": "Conservative primary", "primary-WOR": "Working Families primary"}


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


AD_TYPES = {"VIDEO": "video", "IMAGE": "image", "TEXT": "text"}


def dollars(a):
    """John's style for the label sentences: $6.0M from a million up, whole dollars below."""
    a = round(a or 0)
    return f"${a / 1e6:.1f}M" if a >= 1e6 else f"${a:,}"


def and_list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def ad_library(con, races, out_dir):
    """The ads themselves, as Google's ad library holds them (ballot/adlibrary.py): for each race with a November list,
    one file, data/ads/<race>.json, fetched only when the race page opens. For each candidate on the list: their
    campaign's own ads and the outside ads tied to them, newest first, each labelled from the record only. A campaign's
    ad says "Paid for by their campaign". An outside group's ad quotes the group's own sworn FEC filings in this race
    (the independent expenditures it reported for or against each candidate); which candidate a particular ad is about
    is in neither record and is never guessed. The page carries only each candidate's counts."""
    folder = os.path.join(out_dir, "data", "ads")
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {"ad_library", "ad_links"} <= tables:
        return {"races": {}}
    cols = {r[1] for r in con.execute("PRAGMA table_info(ad_links)")}
    lib = {r[0]: r for r in con.execute(
        "SELECT ad_id, url, ad_type, advertiser, first_shown, last_shown, spend_low, spend_high, states FROM ad_library")}
    names, races_of = defaultdict(dict), defaultdict(set)      # race -> {fec: the name as the state's list prints it}
    for race, fec, name in con.execute("SELECT race_id, fec_id, name FROM candidates WHERE fec_id IS NOT NULL ORDER BY election <> 'general'"):
        names[race].setdefault(fec, name)
        races_of[fec].add(race)
    fec_name = dict(con.execute("SELECT cand_id, name FROM fec26_candidates"))
    decl, when, spender_name = defaultdict(lambda: defaultdict(float)), defaultdict(set), {}
    if "ad_spenders" in tables:
        for cand, sp, name, stance, election, amt in con.execute("SELECT cand_id, spender, name, stance, election, amount FROM ad_spenders"):
            for race in races_of.get(cand, ()):
                decl[(sp, race)][(cand, stance)] += amt or 0
                when[(sp, race)].add(election)
            spender_name[sp] = name or ""
    from ballot.adlibrary import norm

    def said_by(sp, race, advertiser):
        items = sorted(decl.get((sp, race), {}).items(), key=lambda kv: -kv[1])
        items = [(c, s, a) for (c, s), a in items if a >= 1]
        # names exactly as Google and the FEC write them (a tidier would turn DLGA into Dlga); the FEC's where it differs
        known = f", which, as {spender_name[sp]}," if spender_name.get(sp) and norm(spender_name[sp]) != norm(advertiser) else ", which"
        if not items:
            return f"Paid for by {advertiser}{known} reported independent spending in this race to the FEC"
        parts = [f"{dollars(a)} {s} {names[race].get(c) or tidy_name(fec_name.get(c, '')) or c}" for c, s, a in items[:4]]
        if len(items) > 4:
            parts.append(f"{len(items) - 4} smaller amount{'s' if len(items) > 5 else ''} for or against others")
        el = when[(sp, race)]
        tail = "in this race's primary" if el == {"primary"} else "in this race's general election" if el == {"general"} else "in this race"
        return f"Paid for by {advertiser}{known} reported to the FEC spending {and_list(parts)} {tail}"

    listed = {}
    for r in races:
        g = r["el"].get("general") or r["el"].get("open-primary") or []
        fecs = [c["fec"] for c in g if c.get("fec")]
        if fecs:
            listed[r["id"]] = fecs
    links = defaultdict(list)
    q = "SELECT ad_id, cand_id, race_id, relation, " + ("spender" if "spender" in cols else "NULL") + " FROM ad_links"
    for ad, cand, race, rel, sp in con.execute(q):
        links[cand].append((ad, race, rel, sp))
    os.makedirs(folder, exist_ok=True)
    counts, written = {}, set()
    for race, fecs in listed.items():
        body = {}
        for fec in fecs:
            items = []
            for ad, link_race, rel, sp in links.get(fec, ()):
                if ad not in lib or (rel == "outside" and link_race != race):
                    continue
                _, url, kind, advertiser, first, last, lo, hi, states = lib[ad]
                label = "Paid for by their campaign" if rel == "campaign" else said_by(sp, race, advertiser)
                items.append({"type": AD_TYPES.get(kind, (kind or "").lower()), "first": first, "last": last, "lo": lo, "hi": hi,
                              "by": advertiser, "rel": rel, "label": label, "states": states, "url": url})
            if not items:
                continue
            items.sort(key=lambda a: (a["last"] or "", a["first"] or "", a["url"]), reverse=True)
            body[fec] = items
            n = [sum(1 for a in items if a["rel"] == "campaign"), sum(1 for a in items if a["rel"] == "outside")]
            counts.setdefault(race, {})[fec] = n + [sum(1 for a in items if a["type"] == t) for t in ("video", "image", "text")]
        if not body:
            continue
        text = json.dumps({"race": race, "cands": body}, ensure_ascii=False, separators=(",", ":"))
        path = os.path.join(folder, f"{race}.json")
        written.add(os.path.basename(path))
        if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
    for old in os.listdir(folder):      # a race whose ads are gone from the library: its old file goes too
        if old.endswith(".json") and old not in written:
            os.remove(os.path.join(folder, old))
    return {"races": counts}


def state_ballots(ballot_root):
    """The states whose own ballot pages (state and local races) are built beside this one: site/dev/ballot/<code>/."""
    return sorted(st for st in STATE_NAMES if os.path.exists(os.path.join(ballot_root, st.lower(), "index.html")))


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
    found(con, out)
    return out


FOUND_KINDS = ("official", "campaign", "secondary")
FOUND_MARK = "Found on the open web"      # ballot/found.py's mark on a website the sweep found


def found_source(source, url):
    """A short name for the page that states a found fact, from the sweep's own note about it: who publishes the page,
    cut off before the note goes on to say what the page says. When the note does not begin with a name short enough
    to print, the page's own host stands in."""
    host = re.sub(r"^www\.", "", urllib.parse.urlsplit(url or "").netloc.lower())
    if host.endswith("wikipedia.org"):
        return "Wikipedia"
    s = re.sub(r"\s+", " ", str(source or "")).strip()
    cut = re.search(r",|;|:| \(| - | – | — |[\"“”]| '|‘|['’]s? | (?:member|legislator|official|web)?\s*(?:page|site|website|list|listing|biography|profile|article|report|story|release)\b"
                    r"| (?:lists?|names?|says|states|gives|shows|reports?|reported|confirms?|biography of|profile of) ", s)
    name = (s[:cut.start()] if cut else s).strip(" .")
    name = re.sub(r"^The ", "the ", name)
    if not 3 <= len(name) <= 60 or re.match(r"(?i)^(his|her|their|the candidate|campaign)\b", name):
        return host or "the page linked"
    return name


def found(con, out):
    """What the open-web sweep found (ballot/found.py), added to a person only where the official records are blank:
    a birth year, earlier offices, and a mark on a website the sweep found. Each carries who states it, the page's
    address and the kind of source. Nothing else in found_facts is read; a kind outside the three is ignored."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'found_facts'").fetchone():
        return
    key_of = {}
    for race, name, fec in con.execute("SELECT race_id, name, fec_id FROM candidates"):
        key_of[(race, name)] = fec or f"{race}|{name}"
    for race, name, field, year, date, office, y0, y1, source, url, kind in con.execute(
            "SELECT race_id, name, field, year, date, office, from_year, to_year, source, url, kind FROM found_facts "
            "ORDER BY race_id, name, from_year IS NULL, from_year, office"):
        key = key_of.get((race, name))
        if not key or kind not in FOUND_KINDS or not re.match(r"(?i)^https?://", url or ""):
            continue
        p = out.setdefault(key, {})
        who = found_source(source, url)
        if field == "born" and year and not p.get("dob") and "fb" not in p:
            full = date if date and re.fullmatch(rf"{year}-\d\d-\d\d", str(date)) else ""
            p["fb"] = [int(year), full, who, url, kind]
        elif field == "office" and office and not p.get("off"):
            y1 = "now" if str(y1 or "").lower() == "now" else (int(y1) if str(y1 or "").isdigit() else None)
            p.setdefault("fo", []).append([office, int(y0) if str(y0 or "").isdigit() else None, y1, who, url, kind])
    for (person,) in con.execute("SELECT person FROM websites WHERE source LIKE ?", (FOUND_MARK + "%",)):
        if out.get(person, {}).get("web"):
            out[person]["wf"] = 1


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
    sources = {r[0]: {"state": r[2], "kind": r[3], "agency": r[4], "title": r[5], "url": r[6], "pub": r[7], "fetched": r[8], "sha": r[9], "rows": r[10], "note": r[11]}
               for r in con.execute("SELECT * FROM ballot_sources")}
    listed = {race.split("-")[1] for race, els in cands.items() if els.get("general") or els.get("open-primary")}      # a November list, not a primary alone (Indiana, 2026-09-30)
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
            "adlib": ad_library(con, races, out_dir), "stateBallots": state_ballots(os.path.dirname(out_dir)),
            "odds": json.load(open(os.path.join(HERE, "ballot_cache", "odds", "odds_2026.json"), encoding="utf-8"))
                    if os.path.exists(os.path.join(HERE, "ballot_cache", "odds", "odds_2026.json")) else {},
            "issues": {p: [u, json.loads(t)] for p, u, t in con.execute("SELECT person, url, topics FROM issues")}
                      if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'issues'").fetchone() else {},
            "gaps": {r[0]: r[1] for r in con.execute("SELECT race_id, reason FROM list_gaps")},
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
:root{--pR:var(--rep);--pD:var(--dem);--pL:#B07C00;--pG:#2F8F4E;--pI:#6E62A8;--pO:#646B76;--pW:#7C828C;--gold:#B8860B;--gold-ink:#7A5806;
  --night:#0B1030;--night2:#070A1C;--cream:#F4F1E8}
:root[data-theme="dark"]{--pL:#E3B53A;--pG:#5CC98A;--pI:#A99CE0;--pO:#9AA3AF;--pW:#9AA0A8;--gold:#E0B040;--gold-ink:#E0B040}
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
/* your ballot (John, 2026-10-01): a location button, and the contests for Congress laid out as a ballot would print them */
.locbtn{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 16px;border-radius:999px;background:var(--ink);color:var(--bg);font:700 14.5px var(--sans)}
.locbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.locbtn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.mybar .forget{all:unset;cursor:pointer;font:600 13px var(--sans);color:var(--muted);text-decoration:underline;text-underline-offset:3px;padding:4px 2px}
.mybar .forget:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.locnote{font-size:13px;color:var(--muted);margin:8px 0 0;max-width:70ch;min-height:1em}
.paper{max-width:720px;border:1px solid var(--line-strong);border-radius:8px;background:var(--surface);box-shadow:0 14px 30px -24px rgba(0,0,0,.5);overflow:hidden}
.paper .phead{background:var(--ink);color:var(--bg);padding:14px 18px;text-align:center}
.paper .phead b{display:block;font-size:14px;letter-spacing:.2em;text-transform:uppercase}.paper .phead span{display:block;font-size:12px;opacity:.82;margin-top:4px;letter-spacing:.05em}
.paper .pnote{font-size:12.5px;color:var(--muted);padding:10px 18px;margin:0;border-bottom:1px solid var(--line);line-height:1.45}
.contest{padding:14px 18px;border-bottom:1px solid var(--line)}
.contest .ct{display:flex;justify-content:space-between;gap:6px 12px;align-items:baseline;flex-wrap:wrap}
.contest .ct b{font-size:13.5px;letter-spacing:.08em;text-transform:uppercase}.contest .ct span{font-size:12px;color:var(--muted)}
.contest .ct a{font-size:13px;font-weight:600;color:var(--accent-ink);margin-left:auto}
.contest .vf{font-size:12.5px;font-weight:700;margin:4px 0 8px}
.contest ol{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.contest li{display:grid;grid-template-columns:30px 1fr;gap:10px;align-items:center;padding:7px 10px;border:1px solid var(--line);border-radius:6px;border-left:4px solid var(--pc,var(--line-strong))}
.contest .oval{width:22px;height:13px;border:2px solid var(--ink);border-radius:50%;display:block;box-sizing:border-box}
.contest li b{font-size:14.5px}.contest li small{display:block;font-size:12px;color:var(--muted);margin-top:1px}
.contest .wline{border-style:dashed}.contest .wline b{font-weight:600;color:var(--muted)}
.contest .pnone{font-size:13px;color:var(--muted);margin:6px 0 0;line-height:1.45}
.paper .pfoot{padding:14px 18px;font-size:13.5px;color:var(--muted)}
/* folded listings (John, 2026-10-01): the Senate races and every state's races start closed, each summary saying what is inside */
.fold{border:1px solid var(--line);border-radius:20px;background:var(--surface);padding:0 18px;margin-top:22px}
.fold>summary{cursor:pointer;list-style:none;display:flex;gap:6px 14px;align-items:baseline;flex-wrap:wrap;padding:16px 0}
.fold>summary::-webkit-details-marker{display:none}
.fold>summary::before{content:"\25B8";color:var(--muted);font-size:20px;line-height:1;align-self:center;flex:none}.fold[open]>summary::before{content:"\25BE"}
.fold>summary h2{font-family:var(--serif);font-weight:400;font-size:clamp(26px,3vw,36px);margin:0;line-height:1.05}
.fold>summary .fsum{font-size:13.5px;color:var(--muted);margin-left:auto}
.fold>summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:12px}
.fold>.fbody{padding:0 0 18px}.fold>.fbody>.sub{margin:0 0 6px}
.sfold{border-top:1px solid var(--line)}
.sfold>summary{cursor:pointer;list-style:none;display:flex;gap:6px 10px;align-items:baseline;flex-wrap:wrap;padding:12px 0}
.sfold>summary::-webkit-details-marker{display:none}
.sfold>summary::before{content:"\25B8";color:var(--muted);align-self:center}.sfold[open]>summary::before{content:"\25BE"}
.sfold>summary b{font-size:15.5px}.sfold>summary span{font-size:13px;color:var(--muted)}.sfold>summary .pill2{margin-left:auto}
.sfold>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}
.sfold .fbody{padding:0 0 14px}.sfold .rlist,.sfold .rgrid{margin-top:6px}.sfold .notebox{margin-top:0;margin-bottom:10px}
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
/* polls and betting markets as tabs above the arena (John, 2026-10-01): both closed to start; a click pulls one down */
.rtabs{margin:18px 0 0}
.rtabs .tabrow{display:flex;gap:8px;flex-wrap:wrap}
.rtab{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:6px 16px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);font:700 14px var(--sans);color:var(--ink)}
.rtab small{font:500 12.5px var(--sans);color:var(--muted)}
.rtab::after{content:"\25BE";color:var(--muted);font-size:12px}.rtab[aria-expanded="true"]::after{content:"\25B4"}
.rtab[aria-expanded="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}.rtab[aria-expanded="true"] small,.rtab[aria-expanded="true"]::after{color:var(--bg);opacity:.8}
.rtab:hover{border-color:var(--ink)}.rtab:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rtabpanel{margin-top:10px;border:1px solid var(--line);border-radius:18px;padding:4px 18px 16px;background:var(--surface)}
.rtabpanel[hidden]{display:none}
.rtabpanel .bsec{padding:10px 0 0}.rtabpanel .bsec h2{font-size:clamp(22px,2.6vw,30px)}
:root:not(.calm) .rtabpanel{animation:pull .25s var(--ease) both}
@keyframes pull{from{opacity:0;transform:translateY(-6px)}}
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
/* the ads themselves: links to Google's ad library, labelled from the record only. One closed fold under each candidate, its
   summary saying how many ads and of what kinds; inside it the ads five at a time, each five a closed fold of its own (John, 2026-10-01) */
.adlib{margin-top:12px;border-top:1px solid var(--line);padding-top:4px}
.adlib.none{padding-top:10px}
.adlib h4{margin:0 0 4px;font-size:14.5px}
.adlib>summary,.adgrp>summary{cursor:pointer;list-style:none;position:relative;padding:8px 0 8px 20px;font-size:12.5px;line-height:1.45;color:var(--muted)}
.adlib>summary::-webkit-details-marker,.adgrp>summary::-webkit-details-marker{display:none}
.adlib>summary::before,.adgrp>summary::before{content:"\25B8";position:absolute;left:0;top:8px;font-size:18px;line-height:1.05;color:var(--ink)}
.adlib[open]>summary::before,.adgrp[open]>summary::before{content:"\25BE"}
.adlib>summary h4{display:inline;margin:0 6px 0 0;color:var(--ink)}
.adlib>summary:focus-visible,.adgrp>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}
.adlib .adn{font-size:13px;color:var(--muted);margin:0}
.adgroups{margin-top:8px}
.adgrp{border-top:1px solid var(--line)}.adgrp:last-of-type{border-bottom:1px solid var(--line)}
.adgrp>summary b{font-size:13px;color:var(--ink);margin-right:6px}
.adgrp>.adlist{margin:0 0 10px}
.adlist{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:7px}
.adlist li{font-size:13px;line-height:1.45;padding:8px 10px;border:1px solid var(--line);border-radius:10px;overflow-wrap:anywhere}
.adlist li small{display:block;color:var(--muted);font-size:12px;margin-top:3px}
.adlist a{font-weight:600;color:var(--accent)}
.adall{all:unset;box-sizing:border-box;cursor:pointer;margin-top:8px;font-size:13px;font-weight:700;border:1px solid var(--line-strong);border-radius:999px;padding:6px 14px}
.adall:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fnote{font-size:12.5px;color:var(--muted);margin:10px 0 0}
.sgrid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));margin-top:14px}
.scard2{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface)}
.scard2 b{display:block}.scard2 span{font-size:12.5px;color:var(--muted)}.scard2 .pill2{display:inline-block;margin-top:6px;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;background:var(--accent-soft,rgba(15,122,106,.12));color:var(--accent)}
.scard2 .pill2.no{background:none;border:1px dashed var(--line-strong);color:var(--muted)}
.notebox{border:1px solid var(--line);border-left:4px solid var(--gold);background:var(--surface);border-radius:12px;padding:12px 14px;margin-top:12px;font-size:14px}
.notebox .src{display:block;color:var(--muted);font-size:12.5px;margin-top:4px}
.holder{margin:10px 0 0;color:var(--muted);font-size:15px}
.holder b{color:var(--ink)}
/* the arena: the general election, candidates face to face. A few shades off the page's own background, so it follows
   light and dark with the rest of the page (John, 2026-10-01); the gold is kept for the lines and the "vs" */
.arena{position:relative;border-radius:30px;padding:30px clamp(12px,3vw,34px) 24px;margin:20px 0 6px;overflow:hidden;isolation:isolate;color:var(--ink);
  background:color-mix(in srgb,var(--ink) 7%,var(--bg));box-shadow:inset 0 0 0 1px var(--line),0 24px 50px -40px rgba(0,0,0,.35)}
.arena::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(34% 70% at 22% -6%,color-mix(in srgb,var(--gold) 14%,transparent),transparent 70%),radial-gradient(34% 70% at 78% -6%,color-mix(in srgb,var(--gold) 14%,transparent),transparent 70%)}
.arena::after{content:"";position:absolute;left:6%;right:6%;bottom:40px;height:46%;border-radius:50%;z-index:-1;border:1px solid color-mix(in srgb,var(--gold) 38%,transparent);background:radial-gradient(closest-side,color-mix(in srgb,var(--gold) 8%,transparent),transparent)}
.arena .ahead{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.arena .ahead b{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-ink)}.arena .ahead span{font-size:13px;color:var(--muted)}
.acards{display:flex;justify-content:center;align-items:center;gap:clamp(8px,2.4vw,28px);perspective:1100px;flex-wrap:wrap}
.vs{font-family:var(--serif);font-style:italic;font-size:clamp(30px,4.6vw,54px);color:var(--gold-ink);line-height:1;flex:none}
.bcard{--pc:var(--pO);position:relative;width:clamp(148px,22vw,220px);aspect-ratio:5/7.2;border-radius:18px;overflow:hidden;display:flex;flex-direction:column;
  background:var(--surface);color:var(--ink);box-shadow:0 18px 36px -22px rgba(0,0,0,.5),0 0 0 1px var(--line);transition:transform .35s var(--ease)}
.acards[data-n="2"] .bcard:first-child{transform:rotateY(12deg)}.acards[data-n="2"] .bcard:last-child{transform:rotateY(-12deg)}
.bcard .band{background:var(--pc);color:#fff;font:700 10.5px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;padding:9px 11px;display:flex;justify-content:space-between;gap:6px}
:root[data-theme="dark"] .bcard .band{color:#0F1114}      /* the dark theme's party colours are paler, so the band's type goes dark */
.bcard .band span:last-child{opacity:.85}
.bcard .mono{flex:1;display:grid;place-items:center;min-height:0;background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--pc) 9%,transparent) 0 7px,transparent 7px 14px)}
.bcard .mono span{width:min(40%,78px);aspect-ratio:1;border-radius:50%;display:grid;place-items:center;font-family:var(--serif);font-size:clamp(24px,3vw,34px);color:var(--pc);border:2px solid var(--pc);background:var(--surface)}
.bcard .mono .ph{width:min(46%,88px);overflow:hidden;box-shadow:0 6px 16px -8px rgba(0,0,0,.45)}
.bcard .mono .ph img{width:100%;height:100%;object-fit:cover;object-position:50% 18%;display:block}
.bcard .who{padding:9px 11px 6px}.bcard .who b{display:block;font-family:var(--serif);font-weight:400;font-size:clamp(17px,1.9vw,21px);line-height:1.06}
.bcard .who small{display:block;color:var(--muted);font-size:11.5px;margin-top:2px}
.bcard dl{margin:0;padding:7px 11px 10px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:11.5px;border-top:1px solid var(--line)}
.bcard dt{color:var(--muted)}.bcard dd{margin:0;text-align:right;font-weight:600}
.bcard .flag{position:absolute;top:34px;right:7px;font:700 9.5px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;border-radius:999px;background:var(--ink);color:var(--bg)}
.bcard.wi{border:2px dashed var(--line-strong)}
.bcard.solo{width:clamp(170px,26vw,240px)}
/* a reader's own arrangement (John, 2026-10-01): hide a card, move it with the arrows, or drag it; kept on their device only */
.bcard[draggable="true"]{cursor:grab}.bcard.dragging{opacity:.45}.bcard.over{outline:3px dashed var(--gold);outline-offset:3px}
.ctl{position:absolute;top:33px;left:7px;display:flex;gap:3px}
.ctl button,.colctl button{all:unset;box-sizing:border-box;cursor:pointer;width:24px;height:24px;display:grid;place-items:center;border-radius:50%;border:1px solid var(--line-strong);font:700 14px/1 var(--sans);color:var(--ink);background:var(--surface)}
.ctl button:hover,.colctl button:hover{border-color:var(--ink)}
.ctl button:disabled,.colctl button:disabled{opacity:.35;cursor:default;border-color:var(--line-strong)}
.ctl button:focus-visible,.colctl button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.hidbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:center;margin:14px auto 0;font-size:13px;color:var(--muted)}
.hidbar button{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;gap:7px;align-items:center;font:600 13px var(--sans);color:var(--ink);border:1px solid var(--line-strong);border-radius:999px;padding:5px 12px;background:var(--surface)}
.hidbar button:hover{border-color:var(--ink)}.hidbar button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.hidbar button i{width:9px;height:9px;border-radius:50%;background:var(--pc,var(--line-strong))}
.aopen{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:8px;margin:20px auto 0;height:44px;padding:0 20px;border-radius:999px;border:1px solid var(--gold);color:var(--ink);font-weight:700;font-size:14.5px;width:max-content}
.aopen:hover,.aopen:focus-visible{background:color-mix(in srgb,var(--gold) 14%,transparent)}
.aopen svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2}
.anote{font-size:12.5px;color:var(--muted);text-align:center;margin:12px auto 0;max-width:70ch}
@media (max-width:640px){      /* on a phone the cards stand in a column, each laid on its side, with "vs" between */
  .acards{flex-direction:column;gap:6px}.acards .bcard,.acards[data-n="2"] .bcard:first-child,.acards[data-n="2"] .bcard:last-child{transform:none}
  .bcard,.bcard.solo{width:min(100%,360px);aspect-ratio:auto;flex-direction:row;flex-wrap:wrap}
  .bcard .band{width:100%}.bcard .mono{flex:0 0 88px;min-height:88px}.bcard .mono span{width:58px;font-size:24px}
  .bcard .who{flex:1;min-width:0;align-self:center}.bcard dl{width:100%}.bcard .flag{top:40px}
  .ctl{top:3px;left:50%;transform:translateX(-50%)}      /* on a phone the card lies on its side, so the controls sit in the band's empty middle, clear of the portrait */
  .vs{font-size:30px}}
:root:not(.calm) .arena.deal .bcard{animation:deal .85s var(--ease) both;animation-delay:calc(var(--k) * .14s)}
:root:not(.calm) .arena.deal .vs{animation:vspop .6s .5s cubic-bezier(.3,1.7,.5,1) both}
@keyframes deal{from{opacity:0;transform:translateY(46px) rotateX(38deg) scale(.82)}}
@keyframes vspop{from{opacity:0;transform:scale(.2) rotate(-24deg)}to{opacity:1;transform:none}}
.cmp{margin-top:18px;overflow-x:auto;border-radius:18px;background:var(--surface);box-shadow:inset 0 0 0 1px var(--line)}
.cmp table{border-collapse:collapse;width:100%;min-width:560px;font-size:13.5px}
.cmp th,.cmp td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
.cmp thead th{font-family:var(--serif);font-weight:400;font-size:19px;color:var(--ink);border-bottom:2px solid var(--pc)}
.cmp tbody th{color:var(--muted);font-weight:600;font-size:12.5px;white-space:nowrap;width:1%}
.cmp td small{display:block;color:var(--muted);font-size:12px;margin-top:3px}
.cmp a{color:var(--accent-ink)}
.cmp .soon{color:var(--muted);font-style:italic}
.cmp tr[hidden]{display:none}
.cmp .grp th{padding:0;border-bottom-color:color-mix(in srgb,var(--gold) 38%,transparent)}
.cmp .gbtn{all:unset;box-sizing:border-box;cursor:pointer;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;width:100%;padding:14px 12px 10px;color:var(--gold-ink);font:700 11px var(--sans);letter-spacing:.14em;text-transform:uppercase}
.cmp .gbtn::before{content:"\25B8";font-size:13px;letter-spacing:0}.cmp .gbtn[aria-expanded="true"]::before{content:"\25BE"}
.cmp .gbtn small{font:500 12px var(--sans);letter-spacing:0;text-transform:none;color:var(--muted)}
.cmp .gbtn:hover{background:color-mix(in srgb,var(--gold) 8%,transparent)}.cmp .gbtn:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.cmp .colctl{display:flex;gap:4px;margin-top:8px}
.cmpbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:12px 12px 0;font-size:13px;color:var(--muted)}
.cmpbar button{all:unset;box-sizing:border-box;cursor:pointer;font:600 13px var(--sans);color:var(--ink);border:1px solid var(--line-strong);border-radius:999px;padding:5px 12px;background:var(--surface)}
.cmpbar button:hover{border-color:var(--ink)}.cmpbar button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.cmp .empty{padding:18px 14px;font-size:14px;color:var(--muted)}
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
.srcitem small{display:block;color:var(--muted);margin-top:4px;overflow-wrap:anywhere}      /* a long address breaks where it must; ordinary words are left whole */
.method li{margin:6px 0}
/* sources, folded (John, 2026-10-01): one closed fold for a page's sources, a closed fold inside it for each kind of source,
   and a long list broken up again; the page's own rules sit in the fold of the kind they are about */
.srcfold{margin-top:30px}
.fold{scroll-margin-top:78px}      /* a fold the menu goes to ("Sources", "Senate races") lands below the page's fixed header, not under it */
.srcfold .sfold .srclist{margin-top:0}
.srcfold .sfold .sfold{margin-left:16px}.srcfold .sfold .sfold>summary b{font-size:14.5px}
.srcfold .srcitem{background:var(--bg)}
.srcfold .method{margin:0 0 12px;padding-left:20px;color:var(--muted);font-size:14.5px;line-height:1.5;max-width:86ch}
.srcfold .method b{color:var(--ink)}
.tag.note{background:none;color:var(--muted);border:1px dashed var(--line-strong)}
.bfoot{border-top:1px solid var(--hair,var(--line));margin-top:40px;padding:20px 0 90px;color:var(--muted);font-size:13px}
.bfoot a{color:inherit}
@media (max-width:1220px){.bfoot{padding-left:20px;padding-right:20px}}      /* on a narrow screen the footer's words keep off the edge, as the page's do */
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
  <p>On The Ballot, from The Civic Archive v__VERSION__. Who is running comes only from each state's official candidate list, loaded one state at a time; campaign money from the Federal Election Commission's bulk files; the ads themselves are linked where Google's public ad library holds them. No scores, no ratings of any person, no advertising of its own, no donors. Built __GENERATED__.</p>
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
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
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
const listed = new Set(BOOT.listed), GAPS = BOOT.gaps || {}, TOPN = {AK: "four"};      // Alaska's open primary sends four on
const hasList = r => listed.has(r.st) && !GAPS[r.id];      // a state's list can be loaded with a race still missing (Ohio, 2026-09-30)
const notLoaded = r => GAPS[r.id] ? `The official candidate list for this race is not loaded yet: ${esc(GAPS[r.id])}.` : `The official candidate list for ${esc(NAMES[r.st])} is not loaded yet.`;
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
const general = r => r.el && (r.el.general || r.el["open-primary"]) ? inOrder(r.el.general || r.el["open-primary"]) : [];      // Louisiana's House: the Nov 3 ballot is an open primary
const openPrimary = r => !!(r.el && !r.el.general && r.el["open-primary"]);
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
/* found on the open web (ballot/found.py): a birth year [year, date, who states it, address, kind] and offices
   [office, from, to, who, address, kind], shown only where the official records give none, each labelled by its kind of
   source (official: a government's own page; campaign: the candidate's own site; secondary: Wikipedia or a named news
   organization) and linked to the page that states it */
const fAge = fb => fb ? (fb[1] ? String(ageOf(fb[1])) : "about " + (new Date().getFullYear() - fb[0])) : null;
const fSrc = (who, url, kind) => { const a = t => `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">${t}</a>`;
  return kind === "campaign" ? `according to ${a("their campaign")}` : kind === "official" ? `according to ${a(esc(who))}` : `as reported by ${a(esc(who))}`; };
const fYears = o => o[2] === "now" ? (o[1] ? `, since ${o[1]}` : ", held today") : o[1] && o[2] ? (o[1] === o[2] ? `, ${o[1]}` : `, ${o[1]} to ${o[2]}`) : o[1] ? `, from ${o[1]}` : o[2] ? `, until ${o[2]}` : "";
const F_KIND = {official: "government pages", campaign: "the candidate's own campaign site", secondary: "Wikipedia or news reports"};
const fNow = c => (P(c).fo || []).find(o => o[2] === "now" && o[5] === "official") || null;
const days = () => { const [y, m, d] = BOOT.election.split("-").map(Number), n = new Date(); return Math.round((new Date(y, m - 1, d) - new Date(n.getFullYear(), n.getMonth(), n.getDate())) / 864e5); };
const dayWords = () => { const n = days(); return n > 1 ? `Election Day in ${n} days` : n === 1 ? "Election Day is tomorrow" : n === 0 ? "Election Day is today" : `Election Day was ${fmtDate(BOOT.election)}`; };

/* ---------- small pieces ---------- */
const chip = c => `<span class="chip${c.inc ? " inc" : ""}" style="--pc:${pcVar(c)}" title="${esc(shortParty(c))}${c.inc ? ", serves in this chamber today" : ""}"><i></i>${esc(c.n)}</span>`;
function raceCard(r){
  const g = general(r);
  return `<a class="rcard" href="#race=${esc(r.id)}"><div class="rt"><b>${esc(r.o === "S" ? NAMES[r.st] : raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${esc(r.o === "S" ? "U.S. Senate" : NAMES[r.st])}</span></div>
    ${g.length ? `<div class="rchips">${g.map(chip).join("")}</div>` : `<div class="soon">${hasList(r) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</div>`}</a>`;
}
function raceRow(r){
  const g = general(r);
  return `<a class="rrow" href="#race=${esc(r.id)}"><span class="rl">${esc(raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</span><span class="rc">${g.length ? g.map(chip).join("") : `<span class="muted">${hasList(r) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</span>`}</span><span class="go" aria-hidden="true">&rsaquo;</span></a>`;
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
/* ---------- a reader's own arrangement of a race (John, 2026-10-01): cards hidden and an order of their own, kept on their
   device only. The page's own order stays the official list's; one control puts it back. The cards and the comparison's
   columns share the one arrangement, so a card moved is a column moved. ---------- */
const ARR = {};
const arrKey = r => "ballot:arr:" + r.id;
function arrOf(r){      // {o: every candidate's key in the reader's order, h: the keys hidden}; the official order when nothing is kept
  if (ARR[r.id]) return ARR[r.id];
  const keys = general(r).map(c => c.k); let saved = null;
  try { saved = JSON.parse(store.get(arrKey(r)) || "null"); } catch (e) { saved = null; }
  const o = saved && Array.isArray(saved.o) ? saved.o.filter(k => keys.includes(k)) : [];
  keys.forEach(k => { if (!o.includes(k)) o.push(k); });      // a name added to the list since goes last
  return ARR[r.id] = {o, h: new Set(saved && Array.isArray(saved.h) ? saved.h.filter(k => keys.includes(k)) : [])};
}
const arrOrderChanged = r => { const a = arrOf(r), def = general(r).map(c => c.k); return a.o.some((k, i) => k !== def[i]); };
const arrChanged = r => arrOf(r).h.size > 0 || arrOrderChanged(r);
const arrSave = r => { const a = arrOf(r); if (arrChanged(r)) store.set(arrKey(r), JSON.stringify({o: a.o, h: [...a.h]})); else store.del(arrKey(r)); };
const arrList = r => { const by = Object.fromEntries(general(r).map(c => [c.k, c])); return arrOf(r).o.map(k => by[k]).filter(Boolean); };      // everyone, in the reader's order
const arrShown = r => arrList(r).filter(c => !arrOf(r).h.has(c.k));
const arrHidden = r => arrList(r).filter(c => arrOf(r).h.has(c.k));
function arrMove(r, k, toKey){      // the moved one takes the other's place: after it when moving later, before it when moving earlier
  const a = arrOf(r), i = a.o.indexOf(k), j = a.o.indexOf(toKey); if (i < 0 || j < 0 || i === j) return;
  a.o.splice(i, 1); a.o.splice(j, 0, k); arrSave(r);
}
function arrHide(r, k, hide){ const a = arrOf(r); if (hide) a.h.add(k); else a.h.delete(k); arrSave(r); }
function arrReset(r){ delete ARR[r.id]; store.del(arrKey(r)); }
const ctlBtns = (c, pos, n, attr) => `<button type="button" data-${attr}="-1" data-k="${esc(c.k)}" aria-label="Move ${esc(c.n)} earlier" title="Move earlier"${pos === 0 ? " disabled" : ""}>&lsaquo;</button><button type="button" data-${attr}="1" data-k="${esc(c.k)}" aria-label="Move ${esc(c.n)} later" title="Move later"${pos >= n - 1 ? " disabled" : ""}>&rsaquo;</button><button type="button" data-${attr === "mv" ? "hide" : "chide"}="${esc(c.k)}" aria-label="Hide ${esc(c.n)}${attr === "mv" ? "'s card" : "'s column"}" title="Hide">&times;</button>`;

function card(c, r, k, n){
  const M = money(c), pp = P(c), age = ageOf(pp.dob), sv = service(c);
  const flag = c.out === "unopposed" ? "Unopposed" : c.wi ? "Write-in" : c.inc ? "Incumbent" : "";
  const fn = sv ? null : fNow(c);
  const rows = [["Age", age != null ? String(age) : (fAge(pp.fb) || "Not on record")],
    ["In office now", sv && sv.now ? `${esc(shortOffice(sv.now.office))}, ${yWords(sv.now.years, sv.now.unsure)}` : fn ? `${esc(fn[0])}${fn[1] ? `, since ${fn[1]}` : ""}` : "No office on record"]];
  if (sv && sv.total != null && (!sv.now || sv.total - (sv.now.years || 0) >= 1)) rows.push(["Years in office", `${yWords(sv.total, sv.unsure)}, all offices`]);
  rows.push(["Raised, 2026", M && M.r != null ? usdShort(M.r) : (c.fec ? "Not yet reported" : "No FEC filing")]);
  return `<article class="bcard${c.wi ? " wi" : ""}${n === 1 ? " solo" : ""}" style="--pc:${pcVar(c)};--k:${k}" aria-label="${esc(c.n)}, ${esc(shortParty(c))}" data-k="${esc(c.k)}" draggable="true">
    <div class="band"><span>${esc(shortParty(c))}</span><span>${esc(r.o === "S" ? "Senate" : r.st + "-" + (+r.d || "AL"))}</span></div>
    <div class="ctl" role="group" aria-label="Arrange ${esc(c.n)}'s card">${ctlBtns(c, k, n, "mv")}</div>
    ${flag ? `<span class="flag">${esc(flag)}</span>` : ""}
    <div class="mono">${pp.ph ? `<span class="ph"><img src="${esc(pp.ph)}" alt="" loading="lazy" decoding="async"></span>` : `<span aria-hidden="true">${esc(initials(c.n).toUpperCase())}</span>`}</div>
    <div class="who"><b>${esc(c.n)}</b><small>${esc(c.p || "")}</small></div>
    <dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`;
}
function headWords(r){
  const g = general(r), shown = arrShown(r), op = openPrimary(r);
  if (g.length === 1) return "One name for this office";
  return `${g.length} candidates${shown.length < g.length ? `, ${g.length - shown.length} hidden by you` : ""}, ${arrOrderChanged(r) ? "in an order you chose on this device" : "in the order the state's list gives, or by surname"}${op ? ". Every party on one ballot: more than half the votes wins the seat; otherwise the top two meet on December 12" : ""}`;
}
function arenaCards(r){      // the cards in the reader's arrangement, and the bars beneath: the hidden names, and the way back to the official order
  const shown = arrShown(r), hidden = arrHidden(r), parts = [];
  shown.forEach((c, i) => { if (i) parts.push(`<span class="vs" aria-hidden="true">vs</span>`); parts.push(card(c, r, i, shown.length)); });
  const hid = hidden.length ? `<div class="hidbar"><span>Hidden by you:</span>${hidden.map(c => `<button type="button" data-show="${esc(c.k)}" style="--pc:${pcVar(c)}" aria-label="Show ${esc(c.n)}'s card again"><i aria-hidden="true"></i>${esc(c.n)}</button>`).join("")}</div>` : "";
  const reset = arrChanged(r) ? `<div class="hidbar"><button type="button" data-reset>Put back the official order${hidden.length ? " and show everyone" : ""}</button></div>` : "";
  return {cards: parts.join("") || `<p class="anote">Every card is hidden. Show them again below.</p>`, bars: hid + reset, n: shown.length};
}
function arena(r){
  const g = general(r); if (!g.length) return "";
  const op = openPrimary(r), when = op ? g[0].date : r.date, A = arenaCards(r);
  return `<section class="arena deal" id="arena" aria-label="The ${op ? "open primary" : "general election"}, ${esc(fmtDate(when))}">
    <div class="ahead"><b>${op ? "Open primary" : "General election"} &middot; ${esc(fmtDate(when))}</b><span id="ahead">${headWords(r)}</span></div>
    <div class="acards" data-n="${A.n}">${A.cards}</div>
    <div id="abars">${A.bars}</div>
    <button class="aopen" id="aopen" type="button" aria-expanded="false" aria-controls="cmp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M12 4l8 8-8 8"/></svg><span>Step into the arena: compare them side by side</span></button>
    <div class="cmp" id="cmp" hidden></div>
    <p class="anote">Every card is the same size. The cards show what the records hold: age, the office a candidate holds now and for how long, their years in any office on record, and the money their campaign reported to the FEC. No score or grade of any person.${g.some(c => !P(c).dob && P(c).fb || !service(c) && fNow(c)) ? " Where no official record gives a birth year, an age that reads &ldquo;about&rdquo; comes from a year stated on a government page, the campaign's own site, Wikipedia or a news organization; the comparison below names and links the page." : ""}${g.length > 1 ? " You can hide a card (&times;) or move the cards about (drag one, or use its arrows). That arrangement is yours alone, kept on this device; the state's own order is unchanged, and this site ranks no one." : ""}</p>
  </section>`;
}
let CMP_OPEN = new Set();      // the comparison's sections a reader has opened on this page; every section starts closed
function compare(r){
  const g = arrShown(r), n = g.length, all = general(r);
  if (!n) return `<p class="empty">Every candidate is hidden. Show them again above to compare them.</p>`;
  const cell = (fn) => g.map(c => `<td>${fn(c)}</td>`).join("");
  const M = c => money(c) || {}, mem = c => (c.bio && BOOT.members[c.bio]) || null;
  const soon = t => `<span class="soon">${t}</span>`;
  let curG = "";
  const row = (label, fn) => `<tr data-g="${curG}"${CMP_OPEN.has(curG) ? "" : " hidden"}><th scope="row">${label}</th>${cell(fn)}</tr>`;
  const groups = [];
  const grp = (id, label, rows) => { curG = id; const body = rows.map(([l, fn]) => row(l, fn)).join("");
    groups.push(`<tr class="grp"><th colspan="${n + 1}"><button class="gbtn" type="button" data-g="${id}" aria-expanded="${CMP_OPEN.has(id) ? "true" : "false"}">${label}<small>${rows.map(x => x[0]).join(" &middot; ")}</small></button></th></tr>${body}`); };
  const orgs = c => { const o = M(c).orgs || []; return o.length ? o.map(x => `${esc(x[0])} <small>${esc(BOOT.kinds[x[1]] || "")}: ${usd(x[2])}</small>`).join("") : (c.fec ? "None itemized yet" : "&ndash;"); };
  const side = (c, s) => { const m = M(c), t = m[s] || 0, w = m[s === "for" ? "forw" : "agw"] || []; return t ? `${usd(t)}${w.map(x => `<small>${esc(x[0])}: ${usd(x[1])}</small>`).join("")}` : "None reported"; };
  grp("ballot", "On the ballot", [
    ["Party, as printed", c => esc(c.p || "") + (c.wi ? "<small>Write-in: the name is not printed on the ballot</small>" : "")],
    ["Notes from the list", c => c.note ? esc(c.note) : "&ndash;"]]);
  grp("who", "Who they are", [
    ["Age", c => { const p = P(c), a = ageOf(p.dob); return a != null ? `${a}<small>Born ${esc(p.dob.slice(0, 4))}, according to ${esc(SRC_NAME[p.ds] || p.ds)}</small>`
        : p.fb ? `${fAge(p.fb)}<small>Born ${p.fb[0]}, ${fSrc(p.fb[2], p.fb[3], p.fb[4])}. No official record this site holds gives a birth date${p.fb[1] ? "" : "; the age is worked out from the year alone"}.</small>`
        : "Not on record<small>No official record this site holds gives a birth date</small>"; }],
    ["Offices on record", c => { const sv = service(c), fo = P(c).fo || [];
        if (!sv && fo.length) return fo.map(o => `${esc(o[0])}${fYears(o)}<small>${fSrc(o[3], o[4], o[5])}</small>`).join("")
          + `<small><b>Years not counted:</b> ${fo.length === 1 ? "this comes" : "these come"} from ${[...new Set(fo.map(o => F_KIND[o[5]]))].join(" and ")}, not from the official records this site holds, and the years given are often incomplete.</small>`;
        if (!sv) return "None<small>The records here cover Congress, state legislatures and statewide offices. City, county and school offices are not in them yet.</small>";
        return sv.list.map(o => `${esc(o.office)}, ${o.start ? esc(o.start.slice(0, 4)) : "start not on record"}&ndash;${o.end ? esc(o.end.slice(0, 4)) : "now"}<small>${yWords(yearsBetween(o.start, o.end), o.unsure || !o.start)}${o.terms ? `, ${o.terms} terms` : ""}; ${esc(SRC_NAME[o.src] || o.src)}</small>`).join("")
          + (sv.total != null ? `<small><b>All offices together: ${yWords(sv.total, sv.unsure)}</b></small>` : ""); }],
    ["Photo", c => { const p = P(c); return p.ph ? `${esc(p.pc || "")}${p.pu ? `<small><a href="${esc(p.pu)}" target="_blank" rel="noopener">Where it comes from</a></small>` : ""}` : "None yet<small>Initials stand in until a photo from an official record or the campaign's own site is found</small>"; }],
    ["In their own words", c => { const I = (BOOT.issues || {})[c.k];
      if (I) return `<span class="topics">${I[1].map(t => `<span>${esc(t)}</span>`).join("")}</span><a href="${esc(I[0])}" target="_blank" rel="noopener nofollow">Read them in their own words</a><small>The topics their campaign's issues page lists, as headings; nothing is summarized${P(c).wf ? ". The address is the campaign's own website, found on the open web and checked against the race it names" : ""}</small>`;
      return P(c).web ? `<a href="${esc(P(c).web)}" target="_blank" rel="noopener nofollow">Their campaign's website</a><small>${P(c).wf ? "The campaign's own website, found on the open web and checked against the race it names" : "The address the campaign gave the FEC or the state's candidate list"}</small>` : soon("A link to their campaign's own website"); }]]);
  grp("office", "In office", [
    ["In Congress today", c => { const m = mem(c); return m ? `${m.ch === "Senate" ? "U.S. Senator" : "U.S. Representative"}${m.since ? `, since ${m.since}` : ""}${m.terms ? `<small>${m.terms} term${m.terms === 1 ? "" : "s"}</small>` : ""}` : "No"; }],
    ["Votes this Congress", c => { const m = mem(c); return m && m.elig ? `Voted on ${Number(m.cast).toLocaleString()} of ${Number(m.elig).toLocaleString()}${m.split ? `<small>Voted against most of their party on ${m.breaks || 0} of the ${m.split} votes that split the parties</small>` : ""}` : "&ndash;"; }],
    ["Bills this Congress", c => { const m = mem(c); return m && m.spon != null ? `Sponsored ${m.spon}${m.laws ? `, ${m.laws} became law` : ""}` : "&ndash;"; }],
    ["Their full record", c => c.bio && mem(c) ? `<a href="../../us/#member=${esc(c.bio)}">Open their page on the record side</a>` : `&ndash;<small>No record in Congress. Records of state and local offices come later.</small>`]]);
  grp("money", "Campaign money, 2026 (FEC)", [
    ["Raised", c => M(c).r != null ? `${usd(M(c).r)}${M(c).end ? `<small>Through ${esc(fmtDate(M(c).end))}</small>` : ""}` : (c.fec ? "Not yet reported" : "No FEC filing")],
    ["From people", c => M(c).ind != null ? `${usd(M(c).ind)}<small>A total; people who give are never named here</small>` : "&ndash;"],
    ["From organizations", c => M(c).cmte != null ? `${usd(M(c).cmte)}${M(c).passed ? `<small>${usd(M(c).passed)} of it passed along from people who earmarked it</small>` : ""}` : "&ndash;"],
    ["Largest organizations", orgs],
    ["From the party", c => M(c).pty != null ? usd(M(c).pty) : "&ndash;"],
    ["From the candidate", c => M(c).self != null ? usd(M(c).self) + "<small>Their own gifts and loans</small>" : "&ndash;"],
    ["Cash on hand", c => M(c).coh != null ? usd(M(c).coh) : "&ndash;"],
    ["FEC filings", c => c.fec ? `<a href="https://www.fec.gov/data/candidate/${esc(c.fec)}/" target="_blank" rel="noopener">${esc(c.fec)}</a>` : "No registration found"]]);
  grp("outside", "Outside spending, 2026 (never received by the campaign)", [
    ["Spent to support", c => side(c, "for")],
    ["Spent to oppose", c => side(c, "against")]]);
  grp("ads", "Ads, 2026 (spending reported to the FEC)", [
    ["Their campaign's ads", c => adCell(c, A => A.c)],
    ["Outside ads for them", c => adCell(c, A => adMerge(A.o["for-general"], A.o["for-primary"]))],
    ["Outside ads against them", c => adCell(c, A => adMerge(A.o["against-general"], A.o["against-primary"]))],
    ["See the ads", c => { const t = adCount(adN(r, c));
      return `${t ? `<a href="#race=${esc(r.id)}" data-jump="adlib-${esc(c.fec)}">${t.toLocaleString("en-US")} ad${t === 1 ? "" : "s"} in Google's library</a>` : (c.fec ? "No ad in Google's library tied to them" : "&ndash;")}<small><a href="${metaSearch(c.n)}" target="_blank" rel="noopener">Search Meta's ad library</a>: Meta's ads are not in Google's data</small>`; }]]);
  grp("polls", "Polls (Transparency Initiative members only)", [
    ["Latest poll", c => pollCell(r, c, "latest")],
    ["Our average", c => pollCell(r, c, "average")]]);
  const hidden = arrHidden(r);
  const bar = `<div class="cmpbar"><button type="button" data-gall="1">Open every section</button><button type="button" data-gall="0">Close every section</button>
    ${all.length > 1 ? `<span>Each section opens on a click. The arrows under a name move its column; &times; hides it.</span>` : ""}
    ${hidden.length ? `<span>Hidden by you:</span>${hidden.map(c => `<button type="button" data-show="${esc(c.k)}" aria-label="Show ${esc(c.n)}'s column again">${esc(c.n)}</button>`).join("")}` : ""}
    ${arrChanged(r) ? `<button type="button" data-reset>Put back the official order${hidden.length ? " and show everyone" : ""}</button>` : ""}</div>`;
  return `${bar}<table><thead><tr><th></th>${g.map((c, i) => `<th scope="col" style="--pc:${pcVar(c)}" data-k="${esc(c.k)}">${esc(c.n)}${all.length > 1 ? `<div class="colctl" role="group" aria-label="Arrange ${esc(c.n)}'s column">${ctlBtns(c, i, n, "cmv")}</div>` : ""}</th>`).join("")}</tr></thead><tbody>${groups.join("")}</tbody></table>`;
}

/* ---------- a primary, and its field ---------- */
function field(r, key){
  const list = r.el[key] || []; if (!list.length) return "";
  const votes = list.some(c => c.v != null), max = Math.max(1, ...list.map(c => c.pct || 0));
  const rows = [...list].sort((a, b) => votes ? (b.v || 0) - (a.v || 0) : surname(a.n).localeCompare(surname(b.n)));
  const date = list[0].date, topTwo = key === "primary";
  const src = BOOT.sources[list[0].src];
  return `<section class="field run"><div class="fh"><b>${esc(topTwo && TOPN[r.st] ? `Top-${TOPN[r.st]} primary` : BOOT.elections[key] || key)} &middot; ${esc(fmtDate(date))}</b><span>${list.length} candidates${topTwo ? `, every party on one ballot; the ${TOPN[r.st] || "two"} with the most votes advance` : ""}</span></div>
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
const adMerge = (...parts) => { const out = {}; parts.filter(Boolean).forEach(p => Object.entries(p).forEach(([k, v]) => { out[k] = (out[k] || 0) + v; })); return out; };
function adCell(c, pick){      // the compare table: a total, then the kinds, largest first
  const A = c.fec && BOOT.ads[c.fec]; if (!A) return c.fec ? "None reported" : "&ndash;<small>No FEC registration found</small>";
  const k = Object.entries(pick({c: A.c || {}, o: A.o || {}}) || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  if (!k.length) return "None reported";
  const total = k.reduce((t, [, v]) => t + v, 0);
  return `${usdShort(total)}<small>${k.slice(0, 3).map(([m, v]) => `${esc(((AD_KINDS.find(x => x[0] === m) || [])[1]) || m)} ${usdShort(v)}`).join(" &middot; ")}</small>`;
}
function pollCell(r, c, what){      // the compare table: this candidate's share in the qualifying polls of this race
  const P0 = (BOOT.polls || {})[r.id]; const polls = P0 && P0.polls ? [...P0.polls].sort((a, b) => b.end.localeCompare(a.end)) : [];
  const key = p => Object.keys(p.shares).find(n => surname(n).toLowerCase() === surname(c.n).toLowerCase());
  const mine = polls.filter(p => key(p) != null);
  if (!mine.length) return polls.length ? "Not asked about<small>in the qualifying polls</small>" : (P0 ? "No qualifying poll yet" : "&ndash;");
  if (what === "latest") { const p = mine[0]; return `${p.shares[key(p)]}%<small>${esc(p.pollster)}, ${esc(fmtDate(p.end))}</small>`; }
  const ten = mine.slice(0, 10), v = ten.map(p => p.shares[key(p)]);
  return ten.length > 1 ? `${(v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)}%<small>of the ${ten.length} most recent; the arithmetic is under the Polls tab above</small>` : "&ndash;<small>One qualifying poll so far</small>";
}
/* ---------- the ads themselves: Google's ad library, tied to the candidates by the record only (ballot/adlibrary.py) ---------- */
const ADL = BOOT.adlib || {races: {}};
const adN = (r, c) => (c && c.fec && (ADL.races[r.id] || {})[c.fec]) || null;      // [their campaign's, outside, videos, images, text ads]
const adCount = n => n ? n[0] + n[1] : 0;
const metaSearch = n => `https://www.facebook.com/ads/library/?active_status=all&ad_type=political_and_issue_ads&country=US&q=${encodeURIComponent(n)}&search_type=keyword_unordered`;
const num = n => Number(n).toLocaleString("en-US");
const monDay = (y, m, d) => new Date(y, m - 1, d).toLocaleDateString("en-US", {month: "short", day: "numeric"});
function adSpan(a){      // "Jul 8 to Aug 12, 2026"
  if (!a.first) return "dates not given";
  const [y1, m1, d1] = a.first.split("-").map(Number), [y2, m2, d2] = (a.last || a.first).split("-").map(Number);
  if (!a.last || a.first === a.last) return `${monDay(y1, m1, d1)}, ${y1}`;
  return y1 === y2 ? `${monDay(y1, m1, d1)} to ${monDay(y2, m2, d2)}, ${y2}` : `${monDay(y1, m1, d1)}, ${y1} to ${monDay(y2, m2, d2)}, ${y2}`;
}
const adSpend = a => a.lo == null && a.hi == null ? "spending not given" : a.hi == null ? `over ${usd(a.lo)}` : !a.lo ? `up to ${usd(a.hi)}` : `${usd(a.lo)} to ${usd(a.hi)}`;
const adWhere = s => s === "US" ? "Aimed at the whole country, in Google's targeting" : s ? `Aimed at ${s.split(",").map(x => NAMES[x] || x).join(", ")}, in Google's targeting` : "";
const AD_WORDS = {video: ["Video", "Watch it"], image: ["Image", "See it"], text: ["Text ad", "Read it"]};
function adItem(a){
  const [kind, verb] = AD_WORDS[a.type] || [a.type || "Ad", "See it"], where = adWhere(a.states);
  const small = [a.rel === "campaign" && a.by ? `Advertiser in Google's library: ${a.by}` : "", where].filter(Boolean).map(esc).join(" &middot; ");
  return `<li><b>${esc(kind)}</b>, ${esc(adSpan(a))}, ${esc(adSpend(a))} &middot; ${esc(a.label)} &middot; ${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${verb} in Google's ad library</a>` : "Google gives no page for it"}${small ? `<small>${small}</small>` : ""}</li>`;
}
function adLibBlock(r, c){
  const n = adN(r, c), t = adCount(n);
  const kinds = n ? [[n[2], "video", "videos"], [n[3], "image", "images"], [n[4], "text ad", "text ads"]].filter(x => x[0]).map(x => `${num(x[0])} ${x[0] === 1 ? x[1] : x[2]}`) : [];
  const OUT = "reported spending in this race for or against them";
  const whose = !n ? "" : n[0] && n[1] ? `Of these, ${num(n[0])} ${n[0] === 1 ? "is" : "are"} their campaign's own and ${num(n[1])} ${n[1] === 1 ? "is" : "are"} by outside groups that ${OUT}.`
    : n[0] ? (t === 1 ? "It is their campaign's own." : "All are their campaign's own.")
    : (t === 1 ? `It is by an outside group that ${OUT}.` : `All are by outside groups that ${OUT}.`);
  const meta = `<p class="adlinks"><a href="${metaSearch(c.n)}" target="_blank" rel="noopener">Search Meta's ad library for ${esc(c.n)}</a>: Meta's ads are not in Google's data.</p>`;
  if (!t) return `<div class="adlib none" id="adlib-${esc(c.fec)}"><h4>The ads themselves</h4><p class="adn">Google's ad library holds no ad tied to them.</p>${meta}</div>`;
  /* one closed fold (John, 2026-10-01): its summary says how many ads and of what kinds; the list inside is fetched when it is first opened */
  return `<details class="adlib" id="adlib-${esc(c.fec)}" data-k="${esc(c.fec)}"><summary><h4>The ads themselves</h4> <span>${num(t)} ad${t === 1 ? "" : "s"} in Google's ad library: ${kinds.join(", ")}</span></summary>
    <p class="adn">${whose} ${t > AD_RUN ? "Newest first, five at a time: each group is headed by the dates its ads ran between." : t > 1 ? "Newest first." : ""}</p>
    <div class="adgroups"><p class="adn">Loading the list&hellip;</p></div>
    ${meta}</details>`;
}
const AD_RUN = 5, AD_BATCH = 10;      // five ads to a group; where a list is long, ten groups at a time
const adFiles = {};
function mountAdLib(r){      // a race's list of ads is one file, fetched the first time a reader opens a candidate's ads
  $$("details.adlib[data-k]").forEach(b => b.addEventListener("toggle", () => {
    if (!b.open || b.dataset.filled) return;
    const f = adFiles[r.id] || (adFiles[r.id] = fetch(`data/ads/${encodeURIComponent(r.id)}.json?v=${encodeURIComponent(BOOT.generated)}`).then(x => x.ok ? x.json() : Promise.reject(x.status)));
    f.then(d => { if (b.isConnected && !b.dataset.filled) fillAdList(b, (d.cands || {})[b.dataset.k] || []); },
      () => { delete adFiles[r.id];      // not marked as filled: opening the fold again asks again
        const box = $(".adgroups", b); if (box) box.innerHTML = `<p class="adn">The list could not be loaded just now. <a href="https://adstransparency.google.com/political?region=US" target="_blank" rel="noopener">Open Google's ad library</a> and search the name.</p>`; });
  }));
}
function adGroup(list, i){      // five ads, closed, under their numbers and the dates they ran between: "Ads 6 to 10: Sep 2 to Sep 29, 2026"
  const part = list.slice(i, i + AD_RUN), first = part.map(a => a.first).filter(Boolean).sort()[0], last = part.map(a => a.last || a.first).filter(Boolean).sort().pop();
  return `<details class="adgrp"><summary><b>${part.length === 1 ? `Ad ${num(i + 1)}` : `Ads ${num(i + 1)} to ${num(i + part.length)}`}:</b> <span>${esc(adSpan({first, last}))}</span></summary><ul class="adlist">${part.map(adItem).join("")}</ul></details>`;
}
function fillAdList(b, list){
  const box = $(".adgroups", b); if (!box) return;
  b.dataset.filled = "1";
  if (!list.length) { box.innerHTML = `<p class="adn">None found in the list.</p>`; return; }
  if (list.length <= AD_RUN) { box.innerHTML = `<ul class="adlist">${list.map(adItem).join("")}</ul>`; return; }      // five or fewer: the one fold is enough
  const groups = Math.ceil(list.length / AD_RUN), take = left => left <= AD_BATCH + 2 ? left : AD_BATCH; let shown = 0;
  const more = () => {      // the next groups, each closed; a long list comes ten groups at a time
    const from = shown, n = take(groups - shown); let h = "";
    for (let g = from; g < from + n; g++) h += adGroup(list, g * AD_RUN);
    shown += n;
    const old = $(".adall", box); if (old) old.remove();
    box.insertAdjacentHTML("beforeend", h);
    if (shown < groups) { const next = take(groups - shown), btn = document.createElement("button");
      btn.type = "button"; btn.className = "adall";
      btn.textContent = `Show the ${next === groups - shown ? "last" : "next"} ${next === 1 ? "group" : next + " groups"}: ads ${num(shown * AD_RUN + 1)} to ${num(Math.min(list.length, (shown + next) * AD_RUN))} of ${num(list.length)}`;
      btn.addEventListener("click", () => { const at = shown; more(); const s = $$("details.adgrp > summary", box)[at]; if (s) s.focus(); });
      box.appendChild(btn); }
  };
  box.innerHTML = ""; more();
}
document.addEventListener("click", e => {      // "N ads in Google's library" in the comparison: to that candidate's ads, opened, without changing the page
  const a = e.target.closest("a[data-jump]"); if (!a) return;
  const t = document.getElementById(a.dataset.jump); if (!t) return;
  e.preventDefault();
  const fold = t.tagName === "DETAILS", f = fold ? $("summary", t) : t;
  if (fold) t.open = true; else t.setAttribute("tabindex", "-1");
  t.scrollIntoView({block: "start", behavior: calm() ? "auto" : "smooth"}); if (f) f.focus({preventScroll: true});
});
const adSrcItem = () => { const s = BOOT.sources["google-political-ads"]; if (!s) return "";
  return `<div class="srcitem"><b>Google</b>: Political Ads Transparency Report, data bundle. Google's public record of the election ads run on its services: each ad's advertiser and the FEC number or other registration Google verified it under, its kind (video, image or text), the dates it ran, its spending and impressions as ranges, and the places it was aimed at. ${num(s.rows || 0)} of its ads are tied to 2026 candidates here, each linked to its own page in Google's Ads Transparency Center (adstransparency.google.com); nothing is copied.<small><span class="tag fact">Fact</span> <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>${s.pub ? ` &middot; updated by Google ${esc(fmtDate(String(s.pub).slice(0, 10)))}` : ""} &middot; fetched ${esc(s.fetched)} &middot; SHA-256 ${esc((s.sha || "").slice(0, 16))}&hellip;</small></div>`; };
function adsHTML(r){
  const g = general(r).filter(c => c.fec && (BOOT.ads[c.fec] || adCount(adN(r, c)))); if (!g.length) return "";
  const last = g.map(c => (BOOT.ads[c.fec] || {}).last || "").sort().pop();
  const withLib = g.some(c => adCount(adN(r, c)));
  const blocks = g.map(c => { const A = BOOT.ads[c.fec] || {c: {}, o: {}, sp: []}, o = A.o || {};
    const rows = [adBar(A.c, "Their campaign's own ads"), adBar(o["for-general"], "Outside, for them, since the primary"), adBar(o["against-general"], "Outside, against them, since the primary"),
      adBar(o["for-primary"], "Outside, for them, in the primary"), adBar(o["against-primary"], "Outside, against them, in the primary")].filter(Boolean).join("");
    const sp = (A.sp || []).filter(s => s[3] >= 1000).map(s => `<li>${s[0] ? esc(s[0]) : "People and groups filing on their own (not named here)"}: <b>${usdShort(s[3])}</b> ${s[1]}${s[2] === "primary" ? ", in the primary" : ""}</li>`).join("");
    return `<div class="adcard" style="--pc:${pcVar(c)}"><h3>${esc(c.n)} <small>${esc(shortParty(c))}</small></h3>${rows || `<p class="held">No ad spending reported to the FEC yet.</p>`}
      ${sp ? `<details class="adsp"><summary>Who spent the most, apart from the campaign</summary><ul>${sp}</ul></details>` : ""}
      ${adLibBlock(r, c)}</div>`; }).join("");
  return `<section class="bsec" id="ads"><h2>Ads and the money behind them</h2><p class="sub">What each campaign reported spending on ads, by kind, and what others spent for and against them on their own; then the ads themselves, as Google's ad library holds them. Outside spending is not the campaign's money: the campaign never received it, and does not control it.</p>
    <div class="adgrid">${blocks}</div>
    ${last ? `<p class="fnote">The spending is from the Federal Election Commission's filings through ${esc(fmtDate(last))}. Each expense's kind is read from the purpose its spender wrote ("digital ads", "direct mail"); "medium not stated" means exactly that. An expense reported twice, in a quick 24- or 48-hour report and again later, is counted once. Outside spenders are named only when they are committees.</p>` : ""}
    ${withLib ? `<p class="fnote">The ads themselves are Google's, and each opens on Google's own page, where a video plays; nothing is copied here. An ad is listed under a candidate only on the record: Google verified its advertiser as the candidate's campaign committee, or as a committee that reported to the FEC spending in this race for or against them. <b>Google's data does not tell which candidate an outside group's ad is about, or what it says.</b> So an outside group's ad appears under each candidate the group reported spending on, and its label says only what the group itself reported to the FEC. Dates, spending ranges and targeting are Google's${BOOT.sources["google-political-ads"] && BOOT.sources["google-political-ads"].pub ? `, as of Google's update of ${esc(fmtDate(String(BOOT.sources["google-political-ads"].pub).slice(0, 10)))}` : ""}. Meta's ads are not in Google's data; the search link opens Meta's own library.</p>` : ""}</section>`;
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
  MT: ["Montana Council on Problem Gambling's 24-hour helpline (listed by the Montana Department of Justice)", "1-888-900-9979", "tel:18889009979", "https://dojmt.gov/gaming/compulsive-gambling/"],
  TN: ["Tennessee REDLINE (Department of Mental Health and Substance Abuse Services)", "800-889-9789, call or text", "tel:18008899789", "https://www.tn.gov/behavioral-health/substance-abuse-services/treatment/problem-gambling-programs.html"],
  NC: ["North Carolina Problem Gambling Helpline (NCDHHS)", "877-718-5543, or text morethanagamenc to 53342", "tel:18777185543", "https://www.ncdhhs.gov/divisions/mental-health-developmental-disabilities-and-substance-use-services/nc-problem-gambling-program"],
  VA: ["Virginia Problem Gambling Help Line (DBHDS)", "888-532-3500", "tel:18885323500", "https://dbhds.virginia.gov/problem-gambling-support/"],
  WA: ["Washington State Problem Gambling Helpline (Health Care Authority)", "1-800-547-6133, call or text", "tel:18005476133", "https://www.hca.wa.gov/health-care-services-supports/behavioral-health-recovery/problem-gambling"],
  AZ: ["Arizona Department of Gaming's helpline (named by the Attorney General)", "1-800-NEXT-STEP (1-800-639-8783), or text NEXTSTEP to 53342", "tel:18006398783", "https://www.azag.gov/press-release/attorney-general-mayes-warns-against-sports-betting-scams-ahead-super-bowl"],
  MD: ["Maryland's problem gambling helpline (Maryland Department of Health)", "1-800-GAMBLER, answered in Maryland by its Center of Excellence on Problem Gambling", "tel:18004262537", "https://health.maryland.gov/bha/pages/gambling.aspx"],
  LA: ["Louisiana Problem Gamblers Help Line (listed by the Gaming Control Board)", "1-877-770-7867", "tel:18777707867", "https://lgcb.dps.louisiana.gov/problem-gambling/"],
  OR: ["Oregon's Problem Gambling Helpline (Oregon Health Authority)", "1-877-MY-LIMIT (1-877-695-4648); in Spanish 1-844-TU-VALES", "tel:18776954648", "https://www.oregon.gov/oha/hsd/problem-gambling/pages/index.aspx"],
  NM: ["New Mexico Council on Problem Gambling crisis helpline (listed by the Gaming Control Board)", "1-800-572-1142", "tel:18005721142", "https://www.gcb.nm.gov/compulsive-and-problem-gambling/help-is-available/"],
  MA: ["Massachusetts Problem Gambling Helpline (Department of Public Health)", "1-800-327-5050, or text GAMB to 800-327-5050", "tel:18003275050", "https://www.mass.gov/info-details/resources-to-get-help-for-problem-gambling"],
  NJ: ["New Jersey's helpline, answered by the Council on Compulsive Gambling of New Jersey (DMHAS)", "1-800-GAMBLER", "tel:18004262537", "https://www.nj.gov/humanservices/dmhas/crisis/gambling"],
  SC: ["S.C. Gambling Helpline (Behavioral Health and Developmental Disabilities)", "1-877-452-5155", "tel:18774525155", "https://bhdd.sc.gov/office-substance-use-services/services/treatment/gambling-addiction-services"],
  CT: ["Connecticut's problem gambling help line (DMHAS)", "888-789-7777", "tel:18887897777", "https://portal.ct.gov/dmhas/programs-and-services/problem-gambling/do-i-need-help"],
  DE: ["Delaware Gambling Helpline (Division of Gaming Enforcement)", "(888) 850-8888", "tel:18888508888", "https://dge.delaware.gov/help/index.shtml"],
  ME: ["211 Maine, a general help line the Maine CDC names for gambling help", "211, or text your ZIP code to 898-211", "tel:211", "https://www.maine.gov/dhhs/mecdc/healthy-living/substance-use-and-behavioral-health/problem-gambling"],
  CA: ["California Problem Gambling Helpline (Department of Public Health)", "1-800-GAMBLER (1-800-426-2537), or text SUPPORT to 53342", "tel:18004262537", "https://www.cdph.ca.gov/Programs/OPG/Pages/helpline-numbers.aspx"],
  NY: ["HOPEline, for gambling harms and substance use (NYS Office of Addiction Services and Supports)", "1-877-8-HOPENY (1-877-846-7369), or text HOPENY (467369)", "tel:18778467369", "https://oasas.ny.gov/hopeline"],
  PA: ["Pennsylvania's Gambling Helpline (Department of Drug and Alcohol Programs)", "1-800-426-2537, or text 800GAM", "tel:18004262537", "https://www.pa.gov/agencies/ddap/treatment-and-support/problem-gambling-services"],
  IL: ["Illinois's gambling helpline (Department of Human Services)", "1-800-GAMBLER, or text ILGAMB to 833234", "tel:18004262537", "https://www.dhs.state.il.us/page.aspx?item=117443"],
  FL: ["Florida's Dedicated Problem Gambling Helpline (Gaming Control Commission)", "1-833-PLAYWISE (1-833-752-9947)", "tel:18337529947", "https://flgaming.gov/gamblingresources/"]};
      // National line only, by the state's own page: WY (health.wyo.gov), CO (the Colorado Lottery), KY (CHFS), OK (ODMHSAS), AR (DFA Casino Gaming),
      // KS (KDADS), WV (Bureau for Behavioral Health), GA (DBHDD), AL (ADMH), NV (Gaming Control Board notice), MS (the state portal names only a
      // Gamblers Anonymous line), VT, RI, NH, AK, HI (no state line on an official page), TX (the Lottery points to the national line). Idaho's lottery page names the 2-1-1 CareLine, a general referral line open weekdays only, so Idaho is left national too.
function oddsHTML(r){
  const O = (BOOT.odds || {})[r.id]; if (!O || !(O.polymarket || O.kalshi)) return "";
  const block = (key, name) => { const M = O[key]; if (!M || !M.rows.length) return "";
    return `<div class="mkt"><div class="mh"><b>${name}</b><span>${esc(M.title || "")}</span></div>${M.rows.map(([label, p]) => `<div class="mrowo"><span>${esc(label)}</span><span class="mbar"><i style="width:${(100 * p).toFixed(1)}%"></i></span><b>${Math.round(100 * p)}&cent;</b></div>`).join("")}
      <p class="fnote">${Number(M.volume).toLocaleString()} ${M.unit === "contracts" ? "contracts" : "dollars"} traded in all. A price of 60&cent; means a contract paying $1 if that happens trades at 60&cent;.</p>
      <button type="button" class="mgo" data-url="${esc(M.url)}" data-name="${name}">Go to ${name}&hellip;</button></div>`; };
  const at = new Date(O.at), shown = ["polymarket", "kalshi"].filter(k => O[k] && (O[k].rows || []).length).length;      // the count is of the markets shown below
  return `<section class="bsec" id="odds"><h2>What bettors are paying</h2><p class="sub">Prices on ${shown === 1 ? "one prediction market" : "two prediction markets"}, as information only. Not a poll, not a forecast and not an official record.</p>
    <div class="mgrid">${block("polymarket", "Polymarket")}${block("kalshi", "Kalshi")}</div>
    <p class="fnote">Read from each market's public data on ${esc(at.toLocaleString("en-US", {month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"}))}. Prices move all day; the markets' own pages have the current ones. The Civic Archive takes no money from either market and uses no referral links.</p></section>`;
}
/* the two tabs above the arena (John, 2026-10-01): polls, and what bettors are paying. Both closed to start; a click pulls one down, and pulls the other up */
function raceTabs(r){
  const tabs = [], P0 = (BOOT.polls || {})[r.id], O = (BOOT.odds || {})[r.id];
  if (P0) { const n = (P0.polls || []).length; tabs.push({id: "polls", label: "Polls", sum: n ? `${n} qualifying ${n === 1 ? "poll" : "polls"}` : "none that qualifies yet", body: pollsHTML(r)}); }
  if (O && (O.polymarket || O.kalshi)) { const m = ["polymarket", "kalshi"].filter(k => O[k] && O[k].rows && O[k].rows.length).length; tabs.push({id: "odds", label: "What bettors are paying", sum: `${m === 1 ? "one market" : m + " markets"}; bets, not polls`, body: oddsHTML(r)}); }
  if (!tabs.length) return "";
  return `<div class="rtabs" id="rtabs"><div class="tabrow">${tabs.map(t => `<button type="button" class="rtab" id="tab-${t.id}" aria-expanded="false" aria-controls="panel-${t.id}">${t.label}<small>${esc(t.sum)}</small></button>`).join("")}</div>
    ${tabs.map(t => `<div class="rtabpanel" id="panel-${t.id}" role="region" aria-labelledby="tab-${t.id}" hidden>${t.body}</div>`).join("")}</div>`;
}
function wireTabs(){
  const box = $("#rtabs"); if (!box) return;
  box.addEventListener("click", e => { const b = e.target.closest(".rtab"); if (!b) return;
    const open = b.getAttribute("aria-expanded") !== "true";
    $$(".rtab", box).forEach(x => { x.setAttribute("aria-expanded", "false"); $("#" + x.getAttribute("aria-controls")).hidden = true; });
    if (open) { b.setAttribute("aria-expanded", "true"); $("#" + b.getAttribute("aria-controls")).hidden = false; } });
}
function marketNotice(url, name, st){
  const d = document.createElement("dialog"), H = HELPLINES[st];
  d.className = "mnotice";
  d.innerHTML = `<h3>You are leaving for ${esc(name)}</h3>
    <p>${esc(name)} is a market where people bet money on outcomes, including elections. Prices there are bets, not facts, and anyone can lose what they put in.</p>
    <ul><li>You must be at least 18 to use it; some places set a higher age.</li><li>Whether these markets are allowed where you live is disputed in some states. Check your state's law before you use one.</li></ul>
    <p class="mnh">If gambling is causing you or someone close to you harm, free and confidential help is there:<br>
      <b>National Problem Gambling Helpline</b>, day and night: call or text <a href="tel:18006973738">1-800-MY-RESET</a>, or <a href="https://www.ncpgambling.org/help-treatment/" target="_blank" rel="noopener">chat online</a>.${H ? `<br><b>${esc(H[0])}</b>: <a href="${H[2]}">${esc(H[1])}</a> (<a href="${H[3]}" target="_blank" rel="noopener">about it</a>)` : ""}</p>
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
const pendingHTML = (list, also) => (list || []).length ? `<p class="fnote">${also ? "Also by members" : list.length > 1 ? "By members" : "By a member"}, found but not counted until checked against the pollster's own release: ${list.map(x => `${esc(x.pollster)} (ending ${esc(fmtDate(x.end))}; ${esc(x.why)})`).join("; ")}.</p>` : "";
function pollsHTML(r){
  const P0 = (BOOT.polls || {})[r.id]; if (!P0) return "";
  if (!(P0.polls || []).length) { const L0 = P0.left_out || {}, none = !L0.n && !(P0.pending || []).length;
    return `<section class="bsec" id="polls"><h2>Polls</h2><p class="sub">We show polls only from pollsters in the American Association for Public Opinion Research's ${TI_LINK}, who publish how each poll was done. ${none ? "No poll of this race has been published by anyone, as far as we could find" + (L0.checked ? ` (checked ${esc(fmtDate(L0.checked))})` : "") + "." : "None of them has published a poll of this race that we could check yet."}</p>
    ${pendingHTML(P0.pending)}${leftOutHTML(L0, false)}</section>`; }
  const polls = [...P0.polls].sort((a, b) => b.end.localeCompare(a.end)), seen = new Set(), latest = [];
  for (const p of polls) if (!seen.has(p.pollster) && latest.length < 5) { seen.add(p.pollster); latest.push(p); }
  const names = [...new Set(polls.flatMap(p => Object.keys(p.shares)))];
  const range = p => p.start.slice(0, 7) === p.end.slice(0, 7) ? esc(fmtDate(p.end)).replace(/ (\d+),/, (_m, d) => ` ${+p.start.slice(8)}&ndash;${d},`) : `${fmtDate(p.start).replace(/, \d{4}$/, "")}&ndash;${esc(fmtDate(p.end))}`;
  const rows = latest.map(p => `<tr><td><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.pollster)}</a><small>${range(p)} &middot; ${p.sample ? esc(p.sample) : `${Number(p.n).toLocaleString()} ${esc(p.pop)}, &plusmn;${p.moe}`}</small></td>${names.map(n => `<td>${p.shares[n] != null ? p.shares[n] + "%" : "&ndash;"}</td>`).join("")}<td>${p.rest != null ? p.rest + "%" : ""}</td></tr>`).join("");
  const ten = polls.slice(0, 10);
  const avg = ten.length > 1 ? `<p class="pavg"><b>Our average of the ${ten.length} most recent:</b> ${names.map(n => { const v = ten.filter(p => p.shares[n] != null).map(p => p.shares[n]); return v.length ? `${esc(n)} (${v.join(" + ")}) &divide; ${v.length} = <b>${(v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)}%</b>` : ""; }).filter(Boolean).join("; ")}.</p>`
    : `<p class="pavg">Only one poll qualifies so far, so there is no average yet; ours will take the ten most recent from these pollsters.</p>`;
  const L = P0.left_out, notes = polls.filter(p => p.note).map(p => `<li>${esc(p.pollster)}, ${range(p)}: ${esc(p.note)}</li>`).join("");
  return `<section class="bsec" id="polls"><h2>Polls</h2><p class="sub">Only from pollsters in the American Association for Public Opinion Research's ${TI_LINK}, who publish how each poll was done. The latest from up to five of them, each checked against the pollster's own release.</p>
    <div class="ptable"><table><thead><tr><th>Pollster and dates</th>${names.map(n => `<th>${esc(n)}</th>`).join("")}<th>Someone else or undecided</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${avg}${notes ? `<ul class="pnotes">${notes}</ul>` : ""}
    ${pendingHTML(P0.pending, true)}
    ${leftOutHTML(L, true)}
    <p class="fnote">A poll is a measure of opinion when it was taken, with a margin of error, not a forecast.</p></section>`;
}
/* ---------- maps: the districts on the ballot, drawn as on the Vote map (John, 2026-09-30) ---------- */
let DIST = null, mapOff = null;
const needDist = () => DIST ? Promise.resolve(DIST) : fetch(BOOT.dist.url).then(r => r.ok ? r.json() : Promise.reject(r.status))
  .then(d => (DIST = d), () => (DIST = {q: 50, states: {}, failed: true}));
/* the Albers projection and the point-in-polygon test, borrowed from the record side (build_site_dev.py's GEO block), so a
   reader's location is placed on this page's own map lines, on their device; it defines conic, albersUsa, inRing, inShape, pathRings and decodeRing */
__GEO__
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
  if (!hasList(r)) return "unknown";
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
    : `<p class="held">${hasList(r) ? "No candidate for this race is on the state's list." : notLoaded(r)}</p>`;
  return `<span class="kick">${r.o === "S" ? "U.S. Senate" : "U.S. House"}${r.sp ? " &middot; special election" : ""}</span>
    <h3>${r.o === "H" ? `<span class="dnum" style="--pc:${h ? PVAR[h] : "var(--line-strong)"}">${+r.d || "AL"}</span>` : ""}${esc(r.o === "S" ? NAMES[r.st] : raceShort(r))}</h3>
    <p class="held">${seatWords(r)}</p>${who}<a class="rpgo" href="#race=${esc(r.id)}">Open the race &rsaquo;</a>`;
}
function sideSummary(st, view){
  if (view === "S") { const s = senateOf(st)[0]; return s ? preview(s) : `<p class="held">No Senate seat from ${esc(NAMES[st])} is on the ballot in 2026.</p>`; }
  const hs = houseOf(st), n = {D: 0, R: 0, I: 0}; let open = 0, vac = 0;
  let unknown = 0;
  hs.forEach(r => { const h = HOLD(r); if (h) n[h]++; else vac++; const ss = seatState(r); if (ss === "open") open++; if (ss === "unknown") unknown++; });
  const rows = ["D", "R", "I"].filter(k => n[k]).map(k => `<li><i style="background:${PVAR[k]}"></i>${n[k]} held by ${n[k] === 1 ? ONE[k] : MANY[k]}</li>`);
  if (vac) rows.push(`<li><i style="background:var(--line-strong)"></i>${vac} vacant</li>`);
  if (listed.has(st)) rows.push(`<li><i style="background:repeating-linear-gradient(45deg,var(--muted) 0 2px,transparent 2px 5px)"></i>${open ? `${open} open ${open === 1 ? "seat" : "seats"}: the member who holds it is not on its ballot` : unknown ? "No open seat among the districts whose lists are loaded" : "No open seat: every member is on the ballot again"}${open && unknown ? ` (${unknown} ${unknown === 1 ? "district's list is" : "districts' lists are"} not loaded yet)` : ""}</li>`);
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

/* ---------- where the reader is (John, 2026-10-01): the state from this page's own state shapes, the district from the lines the maps draw,
   all on the device; nothing is sent anywhere. In a state whose congressional lines changed for 2026 the reader is placed in the state only. ---------- */
const stateRings = {};
function locate(lon, lat){      // {st, d: the district number, or null where the lines are not the 2026 ballot's or are not loaded}
  const pt = albersUsa(lon, lat); if (!pt) return null; let st = null;
  for (const s of Object.keys(BOOT.map)) { const b = BOOT.sbox[s]; if (!NAMES[s] || !b || pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) continue;
    if (inShape(pt, stateRings[s] || (stateRings[s] = pathRings(BOOT.map[s])))) { st = s; break; } }
  if (!st) return null;
  const list = districtsOf(st), q = (DIST && DIST.q) || 50; let d = null;
  if (list) for (const D of list) { if (D.whole) { d = 0; break; } const raw = DIST.states[st] && DIST.states[st][String(D.n)]; if (raw && inShape(pt, raw.map(rg => decodeRing(rg, q)))) { d = D.n; break; } }
  return {st, d};
}
/* the reader's own ballot for Congress, as a ballot would print it: the office, "Vote for one", each name as filed with its party and an
   oval beside it. A preview from the official list, not for marking; the county's sample ballot is the authority. */
function ballotHTML(st, d){
  const sen = [...senateOf(st)].sort((a, b) => (a.sp ? 1 : 0) - (b.sp ? 1 : 0)), hs = houseOf(st), hr = d !== "" ? hs.find(r => r.d === d) : null;
  const contest = r => {
    const g = general(r), printed = g.filter(c => !c.wi && c.out !== "unopposed"), wi = g.filter(c => c.wi), un = g.filter(c => c.out === "unopposed"), op = openPrimary(r);
    const title = r.o === "S" ? `United States Senator${r.sp ? " (special election, for the rest of the term)" : ""}` : `United States Representative${+r.d ? `, District ${+r.d}` : ""}`;
    let body;
    if (!hasList(r)) body = `<p class="pnone">${notLoaded(r)}</p>`;
    else if (!g.length) body = `<p class="pnone">No candidate for this office is on the state's list.</p>`;
    else body = `${printed.length ? `<p class="vf">Vote for one</p><ol>${printed.map(c => `<li style="--pc:${pcVar(c)}"><span class="oval" aria-hidden="true"></span><span><b>${esc(c.n)}</b><small>${esc(c.p || shortParty(c))}</small></span></li>`).join("")}${wi.length ? `<li class="wline"><span class="oval" aria-hidden="true"></span><span><b>Write-in</b><small>Declared write-in ${wi.length === 1 ? "candidate" : "candidates"}, not printed: ${wi.map(c => esc(c.n)).join(", ")}</small></span></li>` : ""}</ol>` : ""}
      ${un.length ? `<p class="pnone">${un.map(c => esc(c.n)).join(", ")}: unopposed, so the office is not printed on the ballot and the candidate takes it without a vote.</p>` : ""}`;
    return `<section class="contest"><div class="ct"><b>${esc(title)}</b>${op ? `<span>An open primary: every party on one ballot; the runoff, if one is needed, is December 12</span>` : ""}<a href="#race=${esc(r.id)}">Open this race &rsaquo;</a></div>${body}</section>`;
  };
  const house = hr ? contest(hr) : `<section class="contest"><div class="ct"><b>United States Representative</b></div><p class="pnone">${linesChanged(st) ? `${esc(NAMES[st])} drew new congressional lines for 2026, so your district cannot be worked out from your location here; the state has ${hs.length} districts. Pick yours above.` : "Pick your district above to see this contest."}</p></section>`;
  const local = (BOOT.stateBallots || []).includes(st) ? `<a class="rpgo" href="../${esc(st.toLowerCase())}/">State and local contests: ${esc(NAMES[st])}&rsquo;s ballot page <span aria-hidden="true">&rsaquo;</span></a>` : `The state and local contests for ${esc(NAMES[st])} are coming.`;
  return `<div class="paper" role="region" aria-label="Your ballot for Congress: a preview"><div class="phead"><b>Your ballot: a preview</b><span>General election &middot; November 3, 2026 &middot; ${esc(NAMES[st])}${hr && +hr.d ? `, District ${+hr.d}` : ""}</span></div>
    <p class="pnote">The contests for Congress, from ${esc(NAMES[st])}'s official candidate list, in the order it gives. Not for marking. Your county's sample ballot is the authority on what your own ballot shows, including the order of names where the state rotates them.</p>
    ${sen.map(contest).join("")}${house}
    <div class="pfoot">${local}</div></div>`;
}
const foldSum = rs => { const n = rs.reduce((t, r) => t + general(r).length, 0), L = rs.filter(hasList).length;
  return `${rs.length} ${rs.length === 1 ? "race" : "races"} &middot; ${n ? `${n.toLocaleString("en-US")} candidates listed${L < rs.length ? ` in ${L} of them` : ""}` : "official lists coming"}`; };

/* ---------- pages ---------- */
function home(anchor){
  const H = BOOT.races.filter(r => r.o === "H").length, S = BOOT.races.filter(r => r.o === "S");
  const cands = BOOT.races.reduce((n, r) => n + general(r).length, 0);
  const mine = JSON.parse(store.get("ballot:mine") || "null") || {st: store.get("state") || "", d: ""};
  const states = Object.keys(NAMES).sort((a, b) => NAMES[a].localeCompare(NAMES[b]));
  const opts = states.map(s => `<option value="${s}"${s === mine.st ? " selected" : ""}>${esc(NAMES[s])}</option>`).join("");
  const stateSum = s => { const rs = byState[s] || [], h = rs.filter(r => r.o === "H").length, n = rs.reduce((t, r) => t + general(r).length, 0);
    return `${h} House ${h === 1 ? "seat" : "seats"}${rs.some(r => r.o === "S") ? ", a Senate race" : ""}${BOOT.notes[s] && BOOT.notes[s].changed ? ", new district lines" : ""}${n ? ` &middot; ${n.toLocaleString("en-US")} candidates listed` : ""}`; };
  $("#app").innerHTML = `<section class="bhero"><span class="eyebrow">On The Ballot &middot; U.S. Congress</span>
    <h1>Who&rsquo;s running for <em>Congress</em></h1>
    <p class="lede">Every House seat and 35 Senate seats are on the November 3, 2026 ballot. Who is running comes from each state&rsquo;s own official list of candidates, added one state at a time; the primaries that chose them come from the official results.</p>
    <span class="countdown"><i></i>${esc(dayWords())}</span>
    <div class="kchips"><div class="kchip"><b>${H}</b><span>House races</span></div><div class="kchip"><b>${S.length}</b><span>Senate races</span></div><div class="kchip"><b>${listed.size} of 50</b><span>states' lists loaded</span></div><div class="kchip"><b>${cands.toLocaleString("en-US")}</b><span>candidates listed so far</span></div></div></section>
  <section class="bsec" id="states"><h2>Every state</h2><p class="sub">Filled states have their official candidate list loaded. The rest are coming, largest first. Switch the map to see the Senate seats on the ballot; tap a state to open its races.</p>
    <div class="mapbar" style="margin-top:12px"><div class="seg" role="group" aria-label="What the map shows" id="useg"><button type="button" data-u="lists" aria-pressed="true">Official lists</button><button type="button" data-u="senate" aria-pressed="false">Senate races</button></div></div>
    <svg class="usballot" id="usballot" viewBox="0 0 975 610" role="img" aria-label="Map of the states"><defs><pattern id="bhatch" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--surface)"/><rect width="2.5" height="7" fill="var(--accent)" opacity=".35"/></pattern></defs>${openDefs("us", 7)}
      ${Object.entries(BOOT.map).map(([s, d]) => NAMES[s] ? `<path class="${listed.has(s) ? "on" : "off"}" d="${d}" data-st="${s}"><title>${esc(NAMES[s])}: ${listed.has(s) ? "list loaded" : "list coming"}</title></path>` : "").join("")}</svg>
    <div class="mkey" id="ukey"></div></section>
  <section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Use your location, or pick your state and your congressional district, and the contests for Congress appear here the way a ballot prints them. Your location is worked out on this device and never sent anywhere; the choice stays on this device too.</p>
    <div class="mybar"><button type="button" class="locbtn" id="yloc"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.3-6-11a6 6 0 0 1 12 0c0 5.7-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>Use my location</button>
      <select id="mst" aria-label="Your state"><option value="">Your state</option>${opts}</select><select id="mdi" aria-label="Your district" hidden></select><button type="button" class="forget" id="yforget" hidden>Forget my choices</button></div>
    <p class="locnote" id="locnote" role="status"></p>
    <div class="mine" id="minelist"></div></section>
  <details class="fold" id="senate"><summary><h2>The Senate races</h2><span class="fsum">${foldSum(S)}</span></summary><div class="fbody"><p class="sub">Thirty-three seats whose terms end in January, and ${S.filter(r => r.sp).length} special elections for the rest of a term. Open a state to see who is running.</p>
    ${S.map(r => { const g = general(r); return `<details class="sfold"><summary><b>${esc(NAMES[r.st])}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${g.length ? `${g.length} candidates` : hasList(r) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</span></summary><div class="fbody"><div class="rlist">${raceRow(r)}</div></div></details>`; }).join("")}</div></details>
  <details class="fold" id="races"><summary><h2>Every race, state by state</h2><span class="fsum">${H} House and ${S.length} Senate races &middot; ${listed.size} of 50 states' lists loaded</span></summary><div class="fbody"><p class="sub">Open a state for its races, or its name for its page with the district map.</p>
    ${states.map(s => `<details class="sfold" data-st="${s}"><summary><b>${esc(NAMES[s])}</b><span>${stateSum(s)}</span><span class="pill2${listed.has(s) ? "" : " no"}">${listed.has(s) ? "List loaded" : "Coming"}</span></summary><div class="fbody"></div></details>`).join("")}</div></details>
  ${sourcesHTML()}`;
  const mst = $("#mst"), mdi = $("#mdi"), note = $("#locnote"), forget = $("#yforget");
  const fill = () => { const st = mst.value, hs = (byState[st] || []).filter(r => r.o === "H");
    mdi.innerHTML = hs.length > 1 ? `<option value="">Your district</option>` + hs.map(r => `<option value="${esc(r.d)}"${r.d === mine.d ? " selected" : ""}>${esc(raceShort(r))}</option>`).join("") : "";
    mdi.hidden = !st || hs.length <= 1; forget.hidden = !st; showMine(); };
  const showMine = () => { const st = mst.value; if (!st) { $("#minelist").innerHTML = ""; return; }
    const hs = (byState[st] || []).filter(r => r.o === "H"), d = hs.length === 1 ? hs[0].d : mdi.value;
    mine.st = st; mine.d = d; store.set("ballot:mine", JSON.stringify({st, d}));
    $("#minelist").innerHTML = `${stateNote(st)}${ballotHTML(st, d)}`; };
  mst.addEventListener("change", () => { mine.d = ""; note.textContent = ""; fill(); }); mdi.addEventListener("change", showMine); fill();
  forget.addEventListener("click", () => { mine.st = ""; mine.d = ""; ["ballot:mine", "pin", "state"].forEach(k => store.del(k)); mst.value = ""; fill(); note.textContent = "Forgotten. Your location and your choices are no longer kept on this device."; });
  $("#yloc").addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn't available in this browser. Pick your state instead."; return; }
    note.textContent = "Finding your district…";
    navigator.geolocation.getCurrentPosition(pos => needDist().then(() => {
      const lat = pos.coords.latitude, lon = pos.coords.longitude, acc = pos.coords.accuracy || 0, hit = locate(lon, lat);
      if (!hit) { note.textContent = "That spot isn't inside a state on our map. Pick your state instead."; return; }
      const hs = houseOf(hit.st), r = hit.d != null ? raceOfD(hit.st, hit.d) : null;
      mine.st = hit.st; mine.d = r ? r.d : ""; mst.value = hit.st; fill();
      store.set("pin", JSON.stringify({st: hit.st, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(acc)})); store.set("state", hit.st);      // rounded, about half a mile: the same kept pin the other pages use
      const where = r ? `${NAMES[hit.st]}, and it looks like ${+r.d ? raceShort(r) : "its one district, at large"}` : NAMES[hit.st];
      const why = r ? "" : linesChanged(hit.st) ? ` ${NAMES[hit.st]} drew new congressional lines for 2026, so your district cannot be worked out from the lines here: pick it from the list.` : DIST && DIST.failed ? " The district lines could not be loaded, so pick your district from the list." : hs.length > 1 ? " Pick your district from the list." : "";
      note.textContent = `${where}.${why} Worked out on your device; your location never leaves it.${r && hs.length > 1 ? " Near a district line the guess can be off by one." : ""}${acc > 8000 ? ` Your device could only place you within about ${Math.round(acc / 1609.34)} miles, so treat the district as a rough guess.` : ""}`;
      $("#minelist").scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"});
    }), () => { note.textContent = "Location wasn't shared. Pick your state instead."; }, {timeout: 10000, maximumAge: 600000});
  });
  /* arriving from "Insights on my location" (the bar at the top of every ballot page): the mark it left is followed once */
  try { const m = +sessionStorage.getItem("insights"); if (m) { sessionStorage.removeItem("insights"); if (Date.now() - m < 120000) setTimeout(() => { const y = $("#yloc"), s = $("#yours"); if (y) { if (s) s.scrollIntoView({block: "start"}); y.click(); } }, 0); } } catch (e) {}
  $("#races").addEventListener("toggle", e => {      // a state's races are drawn the first time its fold opens
    const d = e.target.closest(".sfold[data-st]"); if (!d || !d.open || d.dataset.filled) return;
    const s = d.dataset.st, rs = byState[s] || []; d.dataset.filled = "1";
    $(".fbody", d).innerHTML = `${stateNote(s)}<div class="rlist">${rs.filter(r => r.o === "S").map(raceRow).join("")}${rs.filter(r => r.o === "H").map(raceRow).join("")}</div><p style="margin:12px 0 0"><a class="rpgo" href="#state=${s}">${esc(NAMES[s])}&rsquo;s page, with the district map <span aria-hidden="true">&rsaquo;</span></a></p>`;
  }, true);
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
  if (anchor && $("#" + anchor)) { const t = $("#" + anchor); if (t.tagName === "DETAILS") t.open = true; t.scrollIntoView(); }
}
function statePage(st){
  const rs = byState[st] || []; if (!rs.length) { home(); return; }
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><span>${esc(NAMES[st])}</span></nav>
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${esc(NAMES[st])}</span><h1>${esc(NAMES[st])}</h1>
    <p class="lede">${rs.filter(r => r.o === "H").length} House ${rs.filter(r => r.o === "H").length === 1 ? "seat" : "seats"}${rs.some(r => r.o === "S") ? " and a Senate seat" : ""} on the November 3 ballot. ${listed.has(st) ? "Candidates from the state's official list." : "The state's official candidate list is not loaded yet; each race says who holds the seat today."}</p>
    ${(BOOT.stateBallots || []).includes(st) ? `<p style="margin:16px 0 0"><a class="rpgo" href="../${esc(st.toLowerCase())}/">State and local races on ${esc(NAMES[st])}&rsquo;s ballot <span aria-hidden="true">&rsaquo;</span></a></p>` : ""}
    ${stateNote(st)}</section>
  ${stateMapHTML(st)}
  ${rs.some(r => r.o === "S") ? `<details class="fold"><summary><h2>Senate</h2><span class="fsum">${foldSum(rs.filter(r => r.o === "S"))}</span></summary><div class="fbody"><div class="rlist">${rs.filter(r => r.o === "S").map(raceRow).join("")}</div></div></details>` : ""}
  <details class="fold"><summary><h2>House</h2><span class="fsum">${foldSum(rs.filter(r => r.o === "H"))}</span></summary><div class="fbody"><div class="rlist">${rs.filter(r => r.o === "H").map(raceRow).join("")}</div></div></details>
  ${stateSources(st)}`;
  mountStateMap(st);
}
function holderLine(r){
  if (!r.h) return `<p class="holder">The seat is vacant today.</p>`;
  const [bio, name, party] = r.h, g = general(r), runs = BOOT.runs[bio] || [];
  let tail = "";
  if (hasList(r)) {
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
  const prim = Object.keys(r.el || {}).filter(k => k !== "general" && k !== "open-primary").sort();
  CMP_OPEN = new Set();
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><a href="#state=${r.st}">${esc(NAMES[r.st])}</a><span>&rsaquo;</span><span>${esc(raceShort(r))}</span></nav>
  <section class="bhero withloc"><div><span class="eyebrow">${r.o === "S" ? "U.S. Senate" : "U.S. House"} &middot; ${esc(fmtDate(r.date))}</span><h1>${esc(raceName(r))}</h1>
    ${holderLine(r)}${r.note ? `<p class="holder">${esc(r.note)}</p>` : ""}${general(r).length ? `<button type="button" class="rshare" id="rshare">Share this race</button>` : ""}</div>${locatorHTML()}</section>
  ${raceTabs(r)}
  ${general(r).length ? arena(r) : `<div class="notebox">${hasList(r) ? "No candidate for this race is on the state's list." : `${notLoaded(r)} We add each state from its own election office, largest first.`}</div>`}
  ${adsHTML(r)}
  ${prim.length ? `<section class="bsec"><h2>How they got here</h2><p class="sub">${prim.length === 1 && prim[0] === "primary" ? `${esc(NAMES[r.st])}'s primary is top-${TOPN[r.st] || "two"}: every candidate, of every party preference, on one ballot, and the ${TOPN[r.st] || "two"} with the most votes go on to November${r.st === "AK" ? ", where the vote is counted by ranked choice" : ""}.` : "Each party chose its nominee in its own primary. A party with a single candidate held none."}</p>${prim.map(k => field(r, k)).join("")}</section>` : ""}
  ${raceSources(r)}`;
  mountLocator(r);
  mountAdLib(r);
  wireTabs();
  wireArena(r);
  const sh = $("#rshare");
  if (sh) sh.addEventListener("click", async () => {      // the share page carries the preview card; it opens the race
    const url = `https://thecivicarchive.github.io/dev/ballot/us/r/${r.id}.html`, title = `${raceName(r)}: who is on the ballot`;
    try { if (navigator.share) { await navigator.share({title, url}); return; } await navigator.clipboard.writeText(url); sh.textContent = "Link copied"; }
    catch (e) { if (e && e.name !== "AbortError") { sh.textContent = url; } }
  });
}
function wireArena(r){      // the comparison's open button; the cards' and columns' arrows, hides and shows; the sections' folds; dragging a card
  const A = $("#arena"); if (!A) return;
  const b = $("#aopen"), cmp = $("#cmp"), box = $(".acards", A);
  b.addEventListener("click", () => { if (cmp.hidden) { cmp.innerHTML = compare(r); cmp.hidden = false; b.setAttribute("aria-expanded", "true"); b.querySelector("span").textContent = "Close the comparison"; cmp.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); }
    else { cmp.hidden = true; b.setAttribute("aria-expanded", "false"); b.querySelector("span").textContent = "Step into the arena: compare them side by side"; } });
  const sel = k => `[data-k="${CSS.escape(k)}"]`;
  function redraw(){
    A.classList.remove("deal");      // the cards were dealt once; a rearrangement does not deal them again
    const parts = arenaCards(r); box.innerHTML = parts.cards; box.dataset.n = parts.n; $("#abars", A).innerHTML = parts.bars; $("#ahead", A).textContent = headWords(r);
    if (!cmp.hidden) cmp.innerHTML = compare(r);
  }
  const focusOn = (...cands) => { const f = cands.map(s => $(s, A)).find(x => x && !x.disabled); if (f) f.focus(); };
  A.addEventListener("click", e => {
    const t = e.target.closest("button"); if (!t) return;
    const mv = t.dataset.mv || t.dataset.cmv;
    if (mv) {      // along the shown cards only: a hidden one is skipped over, not jumped behind
      const k = t.dataset.k, shown = arrShown(r), i = shown.findIndex(c => c.k === k), j = i + (+mv); if (i < 0 || j < 0 || j >= shown.length) return;
      arrMove(r, k, shown[j].k); redraw();
      if (t.dataset.mv) focusOn(`.bcard${sel(k)} [data-mv="${mv}"]`, `.bcard${sel(k)} [data-hide]`); else focusOn(`#cmp th${sel(k)} [data-cmv="${mv}"]`, `#cmp th${sel(k)} [data-chide]`);
    }
    else if (t.dataset.hide != null || t.dataset.chide != null) { const k = t.dataset.hide != null ? t.dataset.hide : t.dataset.chide; arrHide(r, k, true); redraw(); focusOn(`${t.dataset.hide != null ? "#abars" : "#cmp"} [data-show="${CSS.escape(k)}"]`, `[data-show="${CSS.escape(k)}"]`, "#aopen"); }
    else if (t.dataset.show != null) { const k = t.dataset.show; arrHide(r, k, false); redraw(); focusOn(`${t.closest("#cmp") ? "#cmp th" : ".bcard"}${sel(k)} [data-chide], .bcard${sel(k)} [data-hide]`); }
    else if (t.hasAttribute("data-reset")) { arrReset(r); redraw(); b.focus(); }
    else if (t.classList.contains("gbtn")) { const g = t.dataset.g, open = t.getAttribute("aria-expanded") !== "true"; t.setAttribute("aria-expanded", String(open)); $$(`tr[data-g="${g}"]`, cmp).forEach(tr => { tr.hidden = !open; }); if (open) CMP_OPEN.add(g); else CMP_OPEN.delete(g); }
    else if (t.dataset.gall != null) { const open = t.dataset.gall === "1"; $$(".gbtn", cmp).forEach(x => { x.setAttribute("aria-expanded", String(open)); if (open) CMP_OPEN.add(x.dataset.g); else CMP_OPEN.delete(x.dataset.g); }); $$("tr[data-g]", cmp).forEach(tr => { tr.hidden = !open; }); }
  });
  /* dragging a card onto another: it takes that card's place. The browser's own drag and drop, so nothing captures the pointer;
     on a touch screen the arrows do the same */
  let dragK = null;
  box.addEventListener("dragstart", e => { const c = e.target.closest(".bcard[data-k]"); if (!c) return; dragK = c.dataset.k; c.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", c.dataset.k); } catch (x) {} });
  box.addEventListener("dragend", () => { dragK = null; $$(".bcard.dragging, .bcard.over", box).forEach(x => x.classList.remove("dragging", "over")); });
  box.addEventListener("dragover", e => { if (!dragK) return; const c = e.target.closest(".bcard[data-k]"); if (!c) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; if (c.dataset.k !== dragK && !c.classList.contains("over")) { $$(".bcard.over", box).forEach(x => x.classList.remove("over")); c.classList.add("over"); } });
  box.addEventListener("dragleave", e => { const c = e.target.closest(".bcard[data-k]"); if (c && !c.contains(e.relatedTarget)) c.classList.remove("over"); });
  box.addEventListener("drop", e => { const c = e.target.closest(".bcard[data-k]"); if (!dragK || !c) return; e.preventDefault(); if (c.dataset.k !== dragK) { arrMove(r, dragK, c.dataset.k); redraw(); } dragK = null; });
}
const srcItem = s => `<div class="srcitem"><b>${esc(s.agency)}</b>: ${esc(s.title)}<small><span class="tag fact">Fact</span> <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a> &middot; fetched ${esc(s.fetched)} &middot; ${Number(s.rows || 0).toLocaleString()} rows &middot; SHA-256 ${esc((s.sha || "").slice(0, 16))}&hellip;${s.note ? " &middot; " + esc(s.note) : ""}</small></div>`;
const srcRow = s => ({h: srcItem(s), g: NAMES[s.state] || "", a: s.agency || ""});      // with the state it belongs to: a long list is folded state by state
const srcHost = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "the page"; } };
const T_FACT = `<span class="tag fact">Fact</span>`, T_SEC = `<span class="tag analysis">Secondary</span>`, tagNote = words => `<span class="tag note">${words}</span>`;
const ext = (u, words, nofollow) => `<a href="${esc(u)}" target="_blank" rel="noopener${nofollow ? " nofollow" : ""}">${words}</a>`;
const srcBox = (who, what, small) => `<div class="srcitem"><b>${who}</b>: ${what}<small>${small}</small></div>`;
/* ---------- the page's own rules, each with the kind of source it is about: it is shown in that kind's fold, above the sources ---------- */
const METHODS = [
  ["lists", `<b>Who is running</b> comes only from each state's own election office: its certified list of candidates, or its official results where the list is the result of a primary. A state appears once its list is loaded; until then its races say who holds the seat today and nothing more.`],
  ["lists", `<b>Order.</b> Candidates appear in the order the state's list gives them, or by surname where the list gives no ballot order. Never by money, polls or party.`],
  ["lists", `<b>Parties</b> are printed exactly as the official list prints them. Colours are for telling the cards apart only.`],
  ["results", `<b>Primaries.</b> Each primary shows everyone who was on its ballot and who went on to November. Votes are shown only as certified in the state's official results; where they are not loaded yet, the race says so, and who went on comes from the state's candidate list.`],
  ["money", `<b>Money</b> is the 2026 cycle from the Federal Election Commission's bulk files: what each campaign reported, organizations named, people only as a total. A candidate's own fundraising committees and joint fundraising committees are moved in, not donors. Outside spending is kept apart, because the campaign never received it.`],
  ["people", `<b>Age and offices held</b> come from official records only: the Biographical Directory of the U.S. Congress for anyone who serves or served there, and the Open States roster for state legislators and statewide officials. Years in office count every office on record once, however they overlap; "at least" means a record lacks a start date. Where no record gives a birth date or an office, the card says so; nothing is estimated.`],
  ["web", `<b>Found on the open web.</b> Where no official record gives a candidate's birth year or earlier offices, the page shows what a government's own page, the campaign's own website, Wikipedia or a named news organization states. Each is labelled by which of those it is ("according to" a government page or the campaign, "as reported by" Wikipedia or a news organization) and linked to the page that states it, and each was checked twice: found by one reader and confirmed against its source by a second. An age from a birth year alone reads "about", and offices found this way are listed but their years are not added up. A campaign website found the same way is marked as such. Never an address, family, or anything about a person's views.`],
  ["people", `<b>Photos</b> are shown to help you recognise people: official portraits for members of Congress (public domain) and state legislators (their legislature's own, via Open States). Where no official photo exists, initials stand in; photos from candidates' own campaign websites, credited and linked, are being added.`],
  ["own", `<b>Campaign websites.</b> A candidate's website is the address the campaign gave the FEC or the state's candidate list, or the campaign's own site found on the open web and checked against the race it names; the comparison says which.`],
  ["own", `<b>In their own words.</b> The topics a campaign's issues page lists are shown as headings, with a link to the page; nothing is summarized.`],
  ["maps", `<b>Maps.</b> District lines are the Census Bureau's cartographic boundary file for the 119th Congress: the lines on the 2026 ballot in every state that did not draw new ones. Where a state drew new lines for 2026, its districts are listed but not drawn until its new lines are loaded, because the old ones would be the wrong districts. A seat's colour is the party of the member who holds it today; striped means that member is not on the seat's November ballot. The colours say who holds a seat, never who will win it.`],
  ["ads", `<b>The ads themselves</b> are Google's: each one opens on its own page in Google's Ads Transparency Center, where a video plays; nothing is copied here. An ad is tied to a candidate only on the record: Google verified its advertiser under the candidate's campaign committee (or, where Google gives no FEC number the FEC's files know, the advertiser's name is the committee's own), or under the FEC number of a committee that reported spending in the race. A campaign's own ad is labelled "Paid for by their campaign", with no word about its tone. An outside group's ad is labelled with what the group itself swore to the FEC: how much it spent for and against each candidate in the race. Google's data does not tell which candidate an outside ad is about, or what it says, and this page never guesses. Meta's ads are not in Google's data; a link searches Meta's own library by name.`],
  ["ads", `<b>Ad spending</b> is from the Federal Election Commission's filings: what each campaign reported spending on ads, and what others spent for and against it on their own. Each expense's kind is read from the purpose its spender wrote ("digital ads", "direct mail"); "medium not stated" means exactly that. An expense reported twice, in a quick 24- or 48-hour report and again later, is counted once. Outside spenders are named only when they are committees.`],
  ["polls", `<b>Polls</b> are shown only from pollsters in the American Association for Public Opinion Research's Transparency Initiative, who publish how each poll was done: the latest from up to five of them, each checked against the pollster's own release, and our own average of the ten most recent, with the arithmetic shown. Polls by other pollsters are counted and named, not shown. A poll is a measure of opinion when it was taken, with a margin of error, not a forecast.`],
  ["polls", `<b>Betting markets.</b> Prices on two prediction markets, Polymarket and Kalshi, are shown as information only: not a poll, not a forecast and not an official record. They are read from each market's public data, and prices move all day. A notice comes before any link to a market. The Civic Archive takes no money from either market and uses no referral links.`],
  ["page", `<b>Nobody is scored or graded.</b> The cards show the record; the judging is yours.`],
  ["page", `<b>Still to come:</b> vote counts for primaries where only the winner is loaded, and the remaining states' lists.`]];
/* ---------- where a page's facts come from, source by source; the folds themselves are drawn by the block after this one ---------- */
const FEC_BULK = () => ext("https://www.fec.gov/data/browse-data/?tab=bulk-data", "fec.gov/data/browse-data/?tab=bulk-data");
const SRC = {      // the sources that read the same on every page
  fec: () => srcBox("Federal Election Commission", "bulk data files for the 2025&ndash;2026 cycle (candidates, committees, campaign totals, committee payments)", `${T_FACT} ${FEC_BULK()}`),
  fecAds: () => srcBox("Federal Election Commission", "independent expenditure reports and the campaigns' own operating expenditures, 2025&ndash;2026: what each campaign, and others for and against it, reported spending on ads, by kind", `${T_FACT} ${FEC_BULK()}`),
  aapor: () => srcBox("American Association for Public Opinion Research", "the Transparency Initiative's members, who publish how each poll was done: only their polls are shown", `${T_FACT} ${ext("https://aapor.org/standards-and-ethics/transparency-initiative/", "aapor.org/standards-and-ethics/transparency-initiative")}`),
  roster: () => srcBox("The congress-legislators project", "the roster of members of Congress, keyed to the Biographical Directory of the U.S. Congress: who holds each seat today, and members' birth dates and terms", `${T_FACT} ${ext("https://github.com/unitedstates/congress-legislators", "github.com/unitedstates/congress-legislators")} &middot; public domain`),
  portraits: () => srcBox("The unitedstates/images project", "official portraits of members of Congress", `${T_FACT} ${ext("https://github.com/unitedstates/images", "github.com/unitedstates/images")} &middot; public domain`),
  openstates: () => srcBox("Open States", "its roster of state legislators and statewide officials: the offices they hold and have held, birth dates where it has them, and each legislature's own portraits", `${T_FACT} ${ext("https://github.com/openstates/people", "github.com/openstates/people")} &middot; public domain (CC0)`),
  record: () => srcBox("The Civic Archive", "the record of the 119th Congress on this site: a sitting member's votes and bills, from the Government Publishing Office's Bill Status data and the House Clerk's and the Senate's roll calls", `${T_FACT} <a href="../../us/">The record of the 119th Congress</a>`),
  lines: () => srcBox("U.S. Census Bureau", "cartographic boundary file of the congressional districts: the lines on the 2026 ballot in every state that did not draw new ones", `${T_FACT} ${ext("https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html", "census.gov cartographic boundary files")}${BOOT.dist.vintage ? ` &middot; ${esc(BOOT.dist.vintage)}` : ""}`),
  outlines: () => srcBox("U.S. Census Bureau", "the states' outlines, from the us-atlas project's copy of the Bureau's cartographic boundary files", `${T_FACT} ${ext("https://github.com/topojson/us-atlas", "github.com/topojson/us-atlas")}`)};
const srcDay = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}); };
const pollSrc = p => srcBox(esc(p.pollster), `its poll ending ${esc(fmtDate(p.end))}`, `${T_FACT} ${ext(p.url, esc(srcHost(p.url)))}${p.checked ? ` &middot; checked against the release ${esc(fmtDate(p.checked))}` : ""}`);
const wikiPollSrc = L => srcBox("Wikipedia", "its list of this race's polls, used only to find them and to count those by pollsters outside the Initiative", `${T_SEC} ${ext(L.found_in, esc(srcHost(L.found_in)))}${L.checked ? ` &middot; checked ${esc(fmtDate(L.checked))}` : ""}`);
const marketSrc = (name, M, at) => srcBox(name, `the market's own public data${M.title ? `: &ldquo;${esc(M.title)}&rdquo;` : ""}`, `${tagNote("Bets, not facts")}${srcDay(at) ? ` read ${esc(srcDay(at))} &middot;` : ""} the way to the market is under &ldquo;What bettors are paying&rdquo;, behind a notice`);
function noteSrc(n, st){      // the source of a state's note on new district lines: "Agency, what it published"
  const t = String(n.st || ""), i = t.indexOf(", "), who = i > 0 ? t.slice(0, i) : t, what = i > 0 ? t.slice(i + 2) : "";
  return srcBox(esc(who), `${what ? esc(what) + ": " : ""}${st ? `the note on ${esc(NAMES[st])}'s district lines` : "the notes on new district lines"}`, `${/^National Conference of State Legislatures/.test(t) ? T_SEC : T_FACT} ${ext(n.su, esc(srcHost(n.su)))}`);
}
function peopleSources(cands, record){      // the official records behind these candidates' ages, offices and portraits: only the ones used
  const uses = f => cands.some(c => f(P(c), c));
  const roster = uses((p, c) => p.ds === "Congress" || (p.off || []).some(o => o.src === "Congress") || !!(c.bio && BOOT.members[c.bio]));
  const items = [];
  if (roster) items.push(SRC.roster());
  if (uses(p => p.ps === "Congress")) items.push(SRC.portraits());
  if (uses(p => p.ds === "State roster" || p.ps === "State roster" || (p.off || []).some(o => o.src === "State roster"))) items.push(SRC.openstates());
  if (record && uses((p, c) => !!(c.bio && BOOT.members[c.bio]))) items.push(SRC.record());
  return {items, roster};
}
function campaignSites(cands){      // each campaign's own website, with what the page takes from it: the address, the issue headings, a photograph
  return cands.map(c => { const p = P(c), I = (BOOT.issues || {})[c.k], web = p.web || (I && I[0]), photo = p.ps === "Campaign"; if (!web && !photo) return null;
    const what = [p.web ? "its website" : "", I ? "the issue headings on its issues page" : "", photo ? "the photograph" : ""].filter(Boolean).join(", ");
    const links = [web ? ext(web, esc(srcHost(web)), true) : "", I && I[0] !== p.web ? ext(I[0], "the issues page", true) : "", photo && p.pu ? ext(p.pu, "the photograph", true) : ""].filter(Boolean).join(" &middot; ");
    const how = !p.web ? "" : p.wf ? "found on the open web and checked against the race it names" : "the address the campaign gave the FEC or the state's candidate list";
    return {h: srcBox(`${esc(c.n)}'s campaign`, what, `${tagNote("The campaign's own")} ${links}${how ? ` &middot; ${how}` : ""}`)}; }).filter(Boolean);
}
function foundPages(pairs){      // every page the open-web sweep is quoted from for these candidates: who states it, where, which kind of source, and what
  const by = new Map();
  const put = (c, r, who, url, kind, what) => { const x = by.get(url) || {who, url, kind, st: r.st, by: new Map()}; by.set(url, x); if (!x.by.has(c.n)) x.by.set(c.n, new Set()); x.by.get(c.n).add(what); };
  pairs.forEach(([c, r]) => { const p = P(c);
    if (!p.dob && p.fb) put(c, r, p.fb[2], p.fb[3], p.fb[4], "birth year");
    if (!service(c)) (p.fo || []).forEach(o => put(c, r, o[3], o[4], o[5], "public offices held")); });
  const tag = k => k === "official" ? T_FACT : k === "campaign" ? tagNote("The campaign's own site") : T_SEC;
  return [...by.values()].sort((a, b) => (NAMES[a.st] || "").localeCompare(NAMES[b.st] || "") || String(a.who).localeCompare(String(b.who)))
    .map(x => ({h: srcBox(esc(x.who), [...x.by].map(([n, f]) => `${esc(n)}: ${[...f].join(" and ")}`).join("; "), `${tag(x.kind)} ${ext(x.url, esc(srcHost(x.url)), true)}`), g: NAMES[x.st] || "", a: x.who}));
}
function raceSources(r){      // a race page: the kinds of source this race has, and no others
  const g = general(r), parts = {}, add = (k, x) => { (parts[k] = parts[k] || {items: []}).items.push(x); };
  [...new Set(Object.values(r.el || {}).flat().map(c => c.src))].map(s => BOOT.sources[s]).filter(Boolean).forEach(s => add(sourceKind(s), srcRow(s)));
  if (g.length) add("money", {h: SRC.fec()});
  if (g.some(c => c.fec && BOOT.ads[c.fec])) add("ads", {h: SRC.fecAds()});
  if (ADL.races[r.id] && adSrcItem()) add("ads", {h: adSrcItem()});
  const P0 = (BOOT.polls || {})[r.id], O = (BOOT.odds || {})[r.id];
  if (P0) { add("polls", {h: SRC.aapor()}); (P0.polls || []).forEach(p => add("polls", {h: pollSrc(p)})); if (P0.left_out && P0.left_out.found_in) add("polls", {h: wikiPollSrc(P0.left_out)}); }
  if (O) [["polymarket", "Polymarket"], ["kalshi", "Kalshi"]].forEach(([k, name]) => { if (O[k] && (O[k].rows || []).length) add("polls", {h: marketSrc(name, O[k], O.at)}); });
  const who = peopleSources(g, true);
  who.items.forEach(h => add("people", {h}));
  if (r.h && !who.roster) { add("holders", {h: SRC.roster()}); parts.holders.label = "Who holds the seat today"; }
  campaignSites(g).forEach(x => add("own", x));
  foundPages(g.map(c => [c, r])).forEach(x => add("web", x));
  if (r.o === "H" && (BOOT.dist.states || []).includes(r.st)) add("maps", {h: SRC.lines()});
  add("maps", {h: SRC.outlines()});
  if (r.o === "H" && BOOT.notes[r.st] && BOOT.notes[r.st].su) add("maps", {h: noteSrc(BOOT.notes[r.st], r.st)});
  return sourceFold("Where this comes from", parts);
}
function stateSources(st){      // a state's page: its lists and results, who holds its seats, and the lines its map draws
  const rs = byState[st] || [], cands = rs.flatMap(general), parts = {}, add = (k, x) => { (parts[k] = parts[k] || {items: []}).items.push(x); };
  Object.values(BOOT.sources).filter(s => s.state === st).forEach(s => add(sourceKind(s), srcRow(s)));
  const who = peopleSources(cands, false);
  who.items.forEach(h => add("people", {h}));
  if (rs.some(r => r.h) && !who.roster) add("holders", {h: SRC.roster()});
  const photos = cands.filter(c => P(c).ps === "Campaign").length;
  if (photos) add("own", {h: srcBox("The campaigns' own websites", photos === 1 ? "the photograph of one candidate, credited and linked on that race's page" : `the photographs of ${num(photos)} candidates, each credited and linked on its race's page`, tagNote("The campaigns' own")), n: photos});
  if (houseOf(st).length > 1 && (BOOT.dist.states || []).includes(st)) add("maps", {h: SRC.lines()});
  add("maps", {h: SRC.outlines()});
  if (BOOT.notes[st] && BOOT.notes[st].su) add("maps", {h: noteSrc(BOOT.notes[st], st)});
  return sourceFold("Where this comes from", parts);
}
function sourcesHTML(){      // the home page: every source, kind by kind, each kind under the rules of the page that are about it
  const parts = {}, add = (k, x) => { (parts[k] = parts[k] || {items: []}).items.push(x); };
  Object.entries(BOOT.sources).filter(([id]) => id !== "google-political-ads").map(([, s]) => s)
    .sort((a, b) => (NAMES[a.state] || a.state || "").localeCompare(NAMES[b.state] || b.state || "")).forEach(s => add(sourceKind(s), srcRow(s)));
  const pairs = BOOT.races.flatMap(r => general(r).map(c => [c, r])), cands = pairs.map(x => x[0]);
  add("money", {h: SRC.fec()});
  add("ads", {h: SRC.fecAds()}); if (adSrcItem()) add("ads", {h: adSrcItem()});
  const polled = Object.values(BOOT.polls || {}), nPolls = polled.reduce((t, p) => t + (p.polls || []).length, 0), nRaces = polled.filter(p => (p.polls || []).length).length, nWiki = polled.filter(p => p.left_out && p.left_out.found_in).length;
  if (polled.length) { add("polls", {h: SRC.aapor()});
    if (nPolls) add("polls", {h: srcBox("The pollsters' own releases", `${num(nPolls)} ${nPolls === 1 ? "poll" : "polls"} of ${num(nRaces)} ${nRaces === 1 ? "race" : "races"}, each checked against its release and linked from its race's Polls tab`, T_FACT), n: nPolls});
    if (nWiki) add("polls", {h: srcBox("Wikipedia", `its lists of the polls of ${num(nWiki)} ${nWiki === 1 ? "race" : "races"}, used only to find polls and to count those by pollsters outside the Initiative`, `${T_SEC} each list is linked from its race's Polls tab`), n: nWiki}); }
  const odds = Object.values(BOOT.odds || {}), at = odds.map(o => o.at || "").sort().pop();
  [["polymarket", "Polymarket"], ["kalshi", "Kalshi"]].forEach(([k, name]) => { const n = odds.filter(o => o[k] && (o[k].rows || []).length).length;
    if (n) add("polls", {h: srcBox(name, `the market's own public data, for ${num(n)} ${n === 1 ? "race" : "races"}`, `${tagNote("Bets, not facts")}${srcDay(at) ? ` read ${esc(srcDay(at))} &middot;` : ""} the way to a market is on its race's page, behind a notice`)}); });
  peopleSources(cands, true).items.forEach(h => add("people", {h}));
  const sites = cands.filter(c => P(c).web).length, issues = cands.filter(c => (BOOT.issues || {})[c.k]).length, photos = cands.filter(c => P(c).ps === "Campaign").length;
  if (sites) add("own", {h: srcBox("The campaigns' own websites", `${num(sites)} of them${issues ? `, with the issue headings of ${num(issues)}` : ""}${photos ? ` and the photographs of ${num(photos)} candidates` : ""}; each is linked on its candidate's race page`, tagNote("The campaigns' own")), n: sites});
  foundPages(pairs).forEach(x => add("web", x));
  add("maps", {h: SRC.lines()}); add("maps", {h: SRC.outlines()});
  const noted = new Map(); Object.entries(BOOT.notes || {}).forEach(([st, n]) => { if (n.st && n.su) noted.set(n.st, (noted.get(n.st) || []).concat([[st, n]])); });
  noted.forEach(list => add("maps", {h: noteSrc(list[0][1], list.length === 1 ? list[0][0] : "")}));
  METHODS.forEach(([k, m]) => { const p = parts[k] = parts[k] || {items: []}; (p.notes = p.notes || []).push(m); });
  return sourceFold("Sources and methods", parts, "sources");
}

/* ---------- source folds (John, 2026-10-01): every "Where this comes from" and "Sources and methods" is one closed fold, and
   inside it a closed fold for each kind of source the page has, its summary saying how many it holds. A long list is broken
   up again: under the state or the office its sources carry, otherwise ten at a time. The state ballot pages take this block
   as it stands, so every ballot page folds its sources the same way; all it asks of a page is esc(). ---------- */
const SOURCE_KINDS = [      // [key, what the fold is called, the words a source's own "kind" uses for it]; the folds appear in this order
  ["lists", "The candidate lists", /candidate (list|filing)|\bballots?\b|certification|contest list|pamphlet|party (key|list)/],
  ["results", "Official results", /result|canvass/],
  ["rules", "Laws, notices and calendars", /statute|\blaw\b|\brule\b|constitution|notice|calendar|schedule|guide|manual|history|proclamation|release|procedure|setup|\bpage\b/],
  ["money", "Campaign money", /money|finance/],
  ["ads", "Ads", /^ads?$|ad library/],
  ["polls", "Polls and markets", /\bpolls?\b|market/],
  ["people", "Who the candidates are", /biograph|portrait|photo/],
  ["own", "The campaigns' own websites", /campaign|website/],
  ["web", "Found on the open web", /open web/],
  ["holders", "Who holds each seat today", /roster/],
  ["places", "Places and their names", /\bcodes?\b|place names|geography|precinct table|district list|directory|election authorities/],
  ["maps", "Maps and lines", /boundar|\blines\b|\bmaps?\b/],
  ["other", "Other sources", null],
  ["page", "How this page works", null]];
function sourceKind(s){      // which fold a source belongs in: the fold it names itself, or else what its own "kind" says (and, for a certification, what its title says it certifies)
  if (s && s.fold && SOURCE_KINDS.some(x => x[0] === s.fold)) return s.fold;
  const k = String((s && s.kind) || "").toLowerCase(), t = String((s && s.title) || "");
  if (/certification|procedure/.test(k)) return /canvass|returns|results/i.test(t) ? "results" : /certification/.test(k) || /ballot|candidate|nominee/i.test(t) ? "lists" : "rules";
  const hit = SOURCE_KINDS.find(x => x[2] && x[2].test(k));
  return hit ? hit[0] : "other";
}
const sourceCount = items => items.reduce((t, x) => t + (x.n || 1), 0);      // a line that stands for many sources carries their number
const sourceWords = (n, one) => `${Number(n).toLocaleString("en-US")} ${one}${n === 1 ? "" : "s"}`;
function sourceRuns(items){      // a kind's sources: as they are when few; when many, under the state or office they carry, otherwise ten at a time
  const list = part => `<div class="srclist">${part.map(x => x.h).join("")}</div>`;
  if (items.length <= 12) return list(items);
  const fold = (label, sub, body) => `<details class="sfold"><summary><b>${label}</b>${sub ? `<span>${sub}</span>` : ""}</summary><div class="fbody">${body}</div></details>`;
  const by = new Map(); items.forEach(x => { const g = x.g || ""; if (!by.has(g)) by.set(g, []); by.get(g).push(x); });
  if (by.size > 1 && !by.has("")) return [...by].sort((x, y) => x[0].localeCompare(y[0])).map(([g, part]) => fold(esc(g), sourceWords(sourceCount(part), "source"), sourceRuns(part.map(x => ({...x, g: "", a: x.a === g ? "" : x.a}))))).join("");
  let out = "";
  for (let i = 0; i < items.length; i += 10) { const part = items.slice(i, i + 10), a = part[0].a || "", b = part[part.length - 1].a || "";
    out += fold(part.length === 1 ? `Source ${i + 1}` : `Sources ${i + 1} to ${i + part.length}`, a && b && a !== b ? `${esc(a)} to ${esc(b)}` : esc(a || b), list(part)); }
  return out;
}
function sourceFold(title, parts, id){      // parts: {kind: {items: [{h: the source as HTML, n, g, a}], notes: [HTML], label}}; nothing at all when a page has no source
  const kinds = SOURCE_KINDS.map(x => [x[0], x[1], parts[x[0]]]).filter(x => x[2] && ((x[2].items || []).length || (x[2].notes || []).length));
  if (!kinds.length) return "";
  const total = kinds.reduce((t, x) => t + sourceCount(x[2].items || []), 0), withSources = kinds.filter(x => (x[2].items || []).length).length;
  return `<details class="fold srcfold"${id ? ` id="${id}"` : ""}><summary><h2>${title}</h2><span class="fsum">${sourceWords(total, "source")} &middot; ${sourceWords(withSources, "kind")}</span></summary><div class="fbody">${kinds.map(([k, label, p]) => {
    const items = p.items || [], notes = p.notes || [], n = sourceCount(items);
    return `<details class="sfold" data-kind="${k}"><summary><b>${p.label || label}</b><span>${n ? sourceWords(n, "source") : sourceWords(notes.length, "note")}</span></summary><div class="fbody">${notes.length ? `<ul class="method">${notes.map(m => `<li>${m}</li>`).join("")}</ul>` : ""}${items.length ? sourceRuns(items) : ""}</div></details>`; }).join("")}</div></details>`;
}
/* ---------- end of source folds ---------- */

/* ---------- the address decides the page ---------- */
function route(){
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("state=")) statePage(h.slice(6).toUpperCase());
  else { home(h.replace(/[^\w-]/g, "")); if (!h) scrollTo(0, 0); return; }
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
    page = PAGE.replace("__CSS__", borrow("CSS")).replace("__MONEYFMT__", borrow("MONEYFMT")).replace("__CHANGELOG__", borrow("CHANGELOG")).replace("__GEO__", borrow("GEO"))
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    import page_extras      # "Take a break" in the header, and the "Insights on my location" bar every ballot page carries
    page = page_extras.add(page, root="../../", ballot="../", here="us")
    page_extras.write_where(os.path.join(site_root, "ballot"))
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    from ballot.share_race import write as write_share      # a share page and preview image for every race with a list
    write_share(os.path.dirname(args.out), boot)
    loaded = sum(1 for r in boot["races"] if r["el"].get("general") or r["el"].get("open-primary"))
    print(f"Version {version}")
    print(f"Wrote {args.out}: {len(boot['races'])} races ({loaded} with the official list loaded), "
          f"{len(boot['listed'])} states listed, {len(boot['money'])} campaigns' money, {len(boot['members'])} members' records, "
          f"{len(page.encode('utf-8')) / 1e3:,.0f} KB")


if __name__ == "__main__":
    main()
