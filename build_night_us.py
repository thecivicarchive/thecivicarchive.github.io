#!/usr/bin/env python3
"""
build_night_us.py - Election Night, results across the country: site/dev/night/us/.

    python build_night_us.py                  (into site/dev/night/us/)
    python build_night_us.py --practice       (the same page with practice figures, into site/practice/; never published)
    python build_night_us.py --root site/dev

The page shows every state's races for Congress, governor and the other statewide offices, counted as each state's own
election office posts the figures, each figure with its time. Routes (after #):
  ""                       home: the count across the country, the map (Senate, Governor, House, What is counted
                           here), your own ballot's results, the Senate and governors' races, every state
  #map #senate #governors #house #counted #states #mine
                           the home, at that part (and the map showing that view)
  #state=MN                one state: its count, its map (county by county where the state's file gives counties,
                           district by district for the House), its races for Congress and its statewide offices
  #race=<race id>          one race: its count, its map and its figures county by county

What it writes beside index.html:
  data/races.json          every race for Congress (from the Congress ballot database) and every statewide office (from
                           the state and local ballot database), read only: id, state, office, district, seat, partisan
                           or not, and its candidates as filed (name, party, ballot order, write-in), nothing else from
                           the lists; and each state's own words: how this page reads it, its own results page, who
                           certifies the results and when, how it counts, its poll hours and its polling place lookup
  data/map.json            the states' shapes (us-atlas, in the Albers frame every map of the site uses)
  data/counties/<code>.json  county lines (Census Bureau, cb_2024_us_county_500k) for each state whose feed is read and
                           reports by county or precinct, projected as the site's other county maps are
  fonts/                   the site's own type
The House district lines are not copied: the page fetches the Congress ballot page's own file
(../../ballot/us/data/districts.json), so that page must be built first. The live figures are not part of the page: it
reads now.json, then us.json and, for a state's counties, the state's own file, from the live site (/night-live/), as
night_common.py's account of the live figures sets out.

--practice writes the same page to site/practice/night/us/ and practice figures beside Minnesota's in
site/practice/night-live/: the 2024 presidential vote county by county, from each state's own official results (the
records of past votes the ballot pages keep, ballot/lean/), replayed onto this year's races in ten states whose feeds are
read; a House district takes its state's 2024 shares moved by a fixed made-up amount. Minnesota's own practice figures,
when they are there, are read as they are. Every practice page says so at the top. No publish script copies site/practice/.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import night_common as N                                                  # noqa: E402

FED_DB = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL_DB = os.path.join(HERE, "ballot_local_2026.sqlite")
POLL_HOURS = os.path.join(HERE, "election", "poll_hours.json")
STATES_TOPO = N.US_STATES_TOPO
COUNTY_ZIP = N.US_COUNTY_ZIP
COUNTY_URL = N.US_COUNTY_URL
LEAN = os.path.join(HERE, "ballot", "lean")
GENERAL = "2026-11-03"
NASS = "https://www.nass.org/can-I-vote"
SHELL_LIMIT = 380_000            # the page's own shell (index.html); the races, the shapes and the figures are files of their own
DATA_LIMIT = 400_000             # data/races.json
COUNTIES_LIMIT = 3_000_000       # every county file together (Night's static files: 25 MB in all, ARCHITECTURE.md 2.6)
COUNTY_METHOD = N.US_COUNTY_METHOD    # bump it there to redraw every county file
COUNTY_UNITS = ("county", "parish", "precinct")     # a feed by these units can give a statewide race's figures county by county

PRACTICE_LABEL = "Practice: replayed 2024 figures. Not 2026 results."
PRACTICE_NOW = "2026-11-04T03:52:00Z"       # 9:52 p.m. Central on election night, as on Minnesota's practice page
PRACTICE_AT = "2026-11-04T03:50:00Z"
PRACTICE_NEXT = "2026-11-04T04:00:00Z"
# The practice states: each with a feed this page reads (live, care or by hand) and an official 2024 count by county on
# disk; the state of each count is set so that the page shows every case. Minnesota's own practice figures (written by its
# page's builder) are read as they are, when there.
PRACTICE_PLAN = {"AR": ("counting", "2026-11-04T03:48:00Z"), "CO": ("counting", "2026-11-04T03:47:00Z"),
                 "IA": ("done", "2026-11-04T03:41:00Z"), "MT": ("counting", "2026-11-04T03:46:00Z"),
                 "ND": ("counting", "2026-11-04T03:49:00Z"), "NE": ("counting", "2026-11-04T03:45:00Z"),
                 "OK": ("counting", "2026-11-04T03:38:00Z"), "SD": ("held", "2026-11-04T03:31:00Z"),
                 "UT": ("counting", "2026-11-04T03:44:00Z"), "WY": ("stale", "2026-11-04T03:20:00Z")}
PRACTICE_REFUSED = ("AL",)       # a state whose site refused this page's requests tonight (practice only)

RULES = ("plurality", "top_two", "majority_runoff", "open_primary", "ranked_choice", "majority_or_legislature")
NEVER_IN_WORDS = re.compile(r"\bscout|\bregistry\b|\breader\b|\bN\d{1,2}\b|https?://|\bwww\.|\b\w+_\w+\b")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def sha10(text):
    return N.sha10(text)


def _surname(name):
    first = re.split(r"\s+(?:and|&|/)\s+", str(name), flags=re.I)[0]
    first = re.sub(r",?\s+(?:Jr\.?|Sr\.?|II|III|IV)$", "", first, flags=re.I).strip()
    return first.split()[-1].lower() if first.split() else ""


def in_order(cands):
    """The ballot order where the list gives one, then by surname: the order the ballot pages show."""
    return sorted(cands, key=lambda c: (c["o"] if isinstance(c.get("o"), int) else 10 ** 9, _surname(c["n"]), c["n"]))


def _order(v):
    return v if isinstance(v, int) else (int(v) if str(v or "").isdigit() else None)


PCS = ("D", "R", "I", "L", "G", "O", "W")


# ============================================================ the races

def congress_races(guard, say=print):
    """Every race for Congress (ballot_2026.sqlite, read only): name as filed, party and order, the November contest
    (the general election, or Louisiana's open primary on November 3)."""
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    try:
        gaps = {rid: why for rid, why in con.execute("SELECT race_id, reason FROM list_gaps")}
        cands = defaultdict(lambda: defaultdict(list))
        for rid, el, name, party, pc, order, wi, outcome in con.execute(
                "SELECT race_id, election, name, party, party_code, ballot_order, write_in, outcome FROM candidates "
                "WHERE election IN ('general', 'open-primary')"):
            name = guard.ok(name, rid, "candidate names (the candidate is left out)")
            if not name:
                continue
            cands[rid][el].append({"n": name, "p": (party or "").strip(), "pc": (pc or "O").strip().upper(), "o": _order(order),
                                   "wi": 1 if wi else 0, "un": (outcome or "").lower() == "unopposed"})
        out = []
        for rid, office, st, district, special in con.execute(
                "SELECT race_id, office, state, district, special FROM races WHERE level = 'federal' ORDER BY state, office DESC, district"):
            senate = office == "U.S. Senate"
            els = cands.get(rid, {})
            key = "general" if els.get("general") else "open-primary" if els.get("open-primary") else None
            cs = in_order(els.get(key, [])) if key else []
            r = {"id": rid, "st": st, "k": "us_senate" if senate else "us_house", "o": "U.S. Senator" if senate else "U.S. Representative"}
            if not senate:
                r["d"] = str(int(district)) if str(district or "").isdigit() else str(district or "")
            if special:
                r["sp"] = 1
            r["pt"] = 1
            if key == "open-primary":
                r["op"] = 1
            if any(c["un"] for c in cs):
                r["un"] = 1
            r["cs"] = [[c["n"], c["p"], c["pc"] if c["pc"] in PCS else "O"] + ([1] if c["wi"] else []) for c in cs]
            if not cs:
                r["nl"] = 1
                why = guard.ok(gaps.get(rid), rid, "list notes")
                if why and not NEVER_IN_WORDS.search(why) and nodomain(why):
                    r["why"] = nodomain(why)
            out.append(r)
    finally:
        con.close()
    return out


def statewide_races(guard, say=print):
    """Every statewide office on the November 3 ballot (ballot_local_2026.sqlite, read only), with the same fields the
    state ballot pages may show of state candidates (ballot/found_local/RULES.md): name as filed, party or "Nonpartisan
    office", ballot order, write-in."""
    import build_ballot_state_dev as B
    from ballot.common import party_code
    con = sqlite3.connect(f"file:{LOCAL_DB}?mode=ro", uri=True)
    out = []
    try:
        cands = defaultdict(lambda: defaultdict(list))
        for rid, el, name, party, pc, order, wi, outcome in con.execute(
                "SELECT c.race_id, c.election, c.name, c.party, c.party_code, c.ballot_order, c.write_in, c.outcome FROM sl_candidates c "
                "JOIN sl_races r ON r.race_id = c.race_id WHERE r.level = 'statewide' AND c.election IN ('general', 'open-primary')"):
            name = guard.ok(name, rid, "candidate names (the candidate is left out)")
            if not name:
                continue
            cands[rid][el].append({"n": name, "p": (party or "").strip(), "pc": (pc or "").strip().upper(), "o": _order(order),
                                   "wi": 1 if wi else 0, "un": (outcome or "").lower() == "unopposed"})
        rows = con.execute("SELECT race_id, state, office_kind, office, district, seat, special, partisan FROM sl_races "
                           "WHERE level = 'statewide' ORDER BY state, race_id").fetchall()
        rank = {}
        for rid, st, kind, office, district, seat, special, partisan in rows:
            els = cands.get(rid, {})
            key = "general" if els.get("general") else "open-primary" if els.get("open-primary") else None
            pt = 1 if partisan else 0
            title = guard.ok(office, rid, "office titles") or (kind or "office").replace("_", " ").title()
            d = str(district).strip() if district not in (None, "") else ""
            s = str(seat).strip() if seat not in (None, "") else ""
            if d:
                title += f", District {d}" if re.fullmatch(r"\d+[A-Z]?", d) else f", {d}"
            if s and s.lower() not in title.lower():
                title += f", {s}"
            if special:
                title += " (special election)"
            cs = []
            for c in in_order(els.get(key, [])) if key else []:
                if pt:
                    p = (B.MN_PARTY.get(c["p"], c["p"]) if st == "MN" else c["p"]) or ("Write-in" if c["wi"] else "")
                    pc = c["pc"] if c["pc"] in PCS else party_code(p)
                    cs.append([c["n"], p, pc] + ([1] if c["wi"] else []))
                else:
                    cs.append([c["n"], "Nonpartisan office", "N"] + ([1] if c["wi"] else []))
            r = {"id": rid, "st": st, "k": kind or "statewide", "o": title, "pt": pt, "cs": cs}
            if d or re.match(r"(?i)district\b", s):
                r["dx"] = 1          # elected by the voters of one district of the state, not the whole state
            if special:
                r["sp"] = 1
            if key == "open-primary":
                r["op"] = 1
            if any(c["un"] for c in els.get(key, []) if key):
                r["un"] = 1
            if not cs:
                r["nl"] = 1
            rank[rid] = (B.kind_rank("statewide", kind or ""), 1 if r.get("dx") else 0, d.zfill(4), s, rid)
            out.append(r)
        out.sort(key=lambda r: (r["st"], rank[r["id"]]))
    finally:
        con.close()
    return out


CROSSWALK_DIR = os.path.join(HERE, "election", "crosswalk")
NIGHT_ONLY_ID = re.compile(r"2026-[A-Z]{2}-[A-Z][A-Z0-9]{1,23}")


def night_only_races(known, say=print):
    """Races no ballot database lists (the District of Columbia's: no ballot list carries the District), shown on this page
    only, and only when a state's crosswalk names them under "night_only", so that its reader ties the feed's contests to
    the same ids: {"2026-DC-DELEGATE": {"office": "Delegate to the U.S. House", "partisan": 1, "seats": 1}, ...}. The
    office's words come from the feed's own contest list; no candidate list is loaded for them, so the figures are shown
    as the feed prints them. A crosswalk is read, never written."""
    out = []
    for path in sorted(os.listdir(CROSSWALK_DIR)) if os.path.isdir(CROSSWALK_DIR) else []:
        if not re.fullmatch(r"[a-z]{2}\.json", path):
            continue
        try:
            doc = json.load(open(os.path.join(CROSSWALK_DIR, path), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        code = path[:2].upper()
        for rid, r in sorted(((doc or {}).get("night_only") or {}).items()):
            office = plain_words(r.get("office"), 3, 120) if isinstance(r, dict) else ""
            if not (NIGHT_ONLY_ID.fullmatch(rid) and rid[5:7] == code and office) or rid in known:
                say(f"  night-only race {rid!r} in {path} left out: it needs a 2026-{code}-<OFFICE> id of its own and an office title")
                continue
            race = {"id": rid, "st": code, "k": "night_only", "o": office, "pt": 1 if r.get("partisan") else 0, "cs": [], "nl": 1, "ni": 1,
                    "why": "no ballot list carries this race; the figures are shown as the state's file prints them"}
            if int(r.get("seats") or 1) > 1:
                race["n"] = int(r["seats"])
            out.append(race)
    return out


def all_races(say=print):
    import build_ballot_state_dev as B
    guard = B.Guard()
    fed = congress_races(guard, say)
    sw = statewide_races(guard, say)
    extra = night_only_races({r["id"] for r in fed + sw}, say)
    if extra:
        say(f"  {len(extra)} night-only races (no ballot list carries them): " + ", ".join(r["id"] for r in extra))
        sw += extra
    for what, ids in sorted(guard.dropped.items()):
        say(f"  privacy check: left out {len(ids)} {what} that looked like contact details")
    return fed, sw


# ============================================================ what the page says of each state

DOMAIN = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|us|gov|edu|info|biz)\b,?\s*", re.I)


def nodomain(v):
    """Words with any site name taken out ("Georgia.gov, Election Day" reads "Election Day"): addresses live in links,
    never in a page's words."""
    return re.sub(r"\s{2,}", " ", DOMAIN.sub("", str(v))).strip(" ,;:-")


def plain_words(v, lo=20, hi=400):
    """A registry sentence for readers, or "" when it carries anything that is not for a reader (an address, a name of
    the kit's files or its people, a code word). "wins a majority" reads "has a majority": the pages never say wins."""
    if not isinstance(v, str) or not (lo < len(v) < hi) or N.kit_names(v) or NEVER_IN_WORDS.search(v):
        return ""
    v = nodomain(v)
    return re.sub(r"\bwins a majority\b", "has a majority", v.strip()) if len(v) > lo else ""


def rules_of(entry):
    """How each kind of race on this page is decided, from the registry's decision rules: {"s": Senate, "h": House,
    "w": the statewide offices}, only where it is not a plurality. A rule whose words name none of them is left out."""
    dec = (entry or {}).get("decision") or {}
    out = {}
    default = dec.get("default") if dec.get("default") in RULES else "plurality"
    if default != "plurality":
        out = {"s": default, "h": default, "w": default}
    for rule in dec.get("rules") or []:
        r, a = rule.get("rule"), str(rule.get("applies") or "").lower()
        if r not in RULES:
            continue
        hit = set()
        if re.search(r"\bevery\b|\bpartisan offices\b|voter-nominated", a):
            hit = {"s", "h", "w"}
        else:
            if re.search(r"federal|congress", a):
                hit |= {"s", "h"}
            if re.search(r"u\.s\. senate", a):
                hit.add("s")
            if re.search(r"u\.s\. house", a):
                hit.add("h")
            if re.search(r"\bstate (?:and local )?offices?\b|\bstate office\b|statewide|governor", a):
                hit.add("w")
        for k in hit:
            out[k] = r
    return {k: v for k, v in out.items() if v != "plurality"}


def poll_words(code, P):
    """A state's poll hours, from the poll hours file: each zone's time zone, opening and closing time (and the latest,
    where places set their own), and where it applies; the state's own polling place lookup; the sentence about voters in
    line. Only well-formed times, known time zones and https addresses are taken."""
    e = (P.get("states") or {}).get(code) or {}
    zones = []
    for z in e.get("zones") or []:
        tz, c, o, lt = str(z.get("tz") or ""), str(z.get("closes") or ""), str(z.get("opens") or ""), str(z.get("latest") or "")
        if not re.fullmatch(r"[A-Za-z_]+(?:/[A-Za-z_]+){1,2}", tz) or not re.fullmatch(r"\d\d:\d\d", c):
            continue
        zz = {"tz": tz, "c": c}
        if re.fullmatch(r"\d\d:\d\d", o):
            zz["o"] = o
        if re.fullmatch(r"\d\d:\d\d", lt):
            zz["l"] = lt
        w = z.get("where")
        if isinstance(w, str) and w.strip() and w.strip().lower() != "statewide" and not NEVER_IN_WORDS.search(w) and len(w) < 120 and nodomain(w):
            zz["w"] = nodomain(w)
        zones.append(zz)
    out = {"z": zones}
    look = e.get("lookup")
    url = look.get("url") if isinstance(look, dict) else look
    if isinstance(url, str) and url.startswith("https://"):
        out["f"] = url
    line = e.get("in_line")
    if isinstance(line, str) and 10 < len(line) < 200 and not NEVER_IN_WORDS.search(line) and nodomain(line):
        out["ln"] = nodomain(line)
    src = e.get("source") or {}
    if isinstance(src, dict) and str(src.get("url") or "").startswith("https://"):
        out["src"] = {"title": nodomain(str(src.get("title") or ""))[:160] or "its poll hours", "url": src["url"], "read": src.get("checked") or ""}
    return out


def county_counts():
    """How many counties (or county equivalents) each state has (night_common.us_county_counts)."""
    return N.us_county_counts()


def states_meta(dev_root, races, polls, ncounties):
    """Each state's words, from its registry file (election/registry/<code>.json) and the poll hours file."""
    from election import registry
    from election.live import partial_source
    have = defaultdict(int)
    for r in races:
        have[r["st"]] += 1
    out = {}
    for code, name in registry.STATES.items():
        e = registry.load(code) or {}
        rp = e.get("results_page") or {}
        url = rp.get("url") if str(rp.get("url") or "").startswith("https://") else None
        c = e.get("certify") or {}
        status = e.get("status") if e.get("status") in registry.STATUSES else "link"
        s = {"n": name, "s": status, "o": plain_words(e.get("office"), 4, 120) or f"the {name} election office"}
        if url:
            s["url"] = url
            lab = plain_words(rp.get("label"), 4, 160)
            if lab:
                s["lab"] = lab
        hc = plain_words(e.get("how_counted"))
        if hc:
            s["hc"] = hc
        body = plain_words(c.get("body"), 4, 140)
        if body:
            short = body.split(",")[0].strip()      # "the Alaska Division of Elections, after the state ballot counting review": the body alone
            s["cb"] = short
            cw = registry.certify_words(e)
            if cw and not NEVER_IN_WORDS.search(cw):
                s["cw"] = cw.replace(body, short, 1)
        if c.get("date") and re.fullmatch(r"\d{4}-\d\d-\d\d", str(c["date"])):
            s["cd"] = c["date"]
        units = str(e.get("units") or "").lower()
        if units in ("county", "parish", "precinct", "town"):
            s["u"] = units
        s["uw"] = N.unit_words(code)          # what the state calls the places its count is given for
        ps = partial_source(e)
        if ps:                                # one county's own count read where the state publishes none: a labelled part
            s["pt"] = {"n": ps["name"], "c": ps["county"]}
            pu = str((ps.get("results_page") or {}).get("url") or "")
            if pu.startswith("https://"):
                s["pt"]["url"] = pu
                s["pt"]["lab"] = plain_words((ps.get("results_page") or {}).get("label"), 4, 120) or f"{ps['name']}'s own results"
        rl = rules_of(e)
        if rl:
            s["rl"] = rl
        if ncounties.get(code):
            s["nc"] = ncounties[code]
        s["p"] = poll_words(code, polls)
        if os.path.exists(os.path.join(dev_root, "night", code.lower(), "index.html")):
            s["pg"] = 1                       # the state has a Night page of its own, every level
        if os.path.exists(os.path.join(dev_root, "ballot", code.lower(), "index.html")):
            s["bal"] = 1                      # its On The Ballot page, for who is running in its statewide races
        if not have.get(code):
            s["none"] = 1                     # no race of this page's kinds on the lists
        out[code] = s
    return out


# ============================================================ the map's files

def map_doc():
    return N.us_map_doc()


def county_codes(states):
    """The states whose county lines the page needs: a feed this page reads (live, care or by hand) that reports by
    county, parish or precinct, in a state of more than one county."""
    return sorted(c for c, s in states.items() if s["s"] in ("live", "care", "hand") and s.get("u") in COUNTY_UNITS and (s.get("nc") or 0) > 1)


def county_files(out_dir, codes, bbox, say=print):
    """data/counties/<code>.json for each state named (night_common.us_county_files)."""
    return N.us_county_files(out_dir, codes, bbox, say)


def districts_vintage(dev_root):
    """What the Congress ballot page's district lines are (its own file says), for the sources."""
    try:
        d = json.load(open(os.path.join(dev_root, "ballot", "us", "data", "districts.json"), encoding="utf-8"))
        return str(d.get("vintage") or "")
    except (OSError, ValueError):
        return ""


# ============================================================ the size of us.json at its largest

def us_file_at_largest(races):
    """us.json as the updater would write it with every race on this page counted (every candidate's line, a write-in
    line, seven-figure counts): its size against the budget (ARCHITECTURE.md 2.6)."""
    from election import store
    doc = {"v": N.FORMAT_VERSION, "state": "US", "at": "2026-11-04T05:40:00Z", "r": {}}
    for i, r in enumerate(races):
        ch = [[store.slug(c[0]), c[0], (c[1] or None) if r["pt"] else None, 1 if len(c) > 3 and c[3] else 0, c[0]] for c in r["cs"]]
        ch.append(["write-in", "WRITE-IN", None, 1, None])
        doc["r"][r["id"]] = {"t": "2026-11-04T05:3%d:00Z" % (i % 10), "p": [1234, 2345], "ch": ch, "v": [1234567 + j for j in range(len(ch))]}
    text = json.dumps(store.compact_page(doc), ensure_ascii=False, separators=(",", ":"))
    return len(text.encode("utf-8"))


# ============================================================ practice figures

def _h(*parts):
    return int(hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def _whole(shares, total):
    total = int(round(total))
    s = sum(shares) or 1.0
    raw = [total * x / s for x in shares]
    out = [int(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[:total - sum(out)]:
        out[i] += 1
    return out


def _past(code):
    """The 2024 presidential vote of each county of a state, from the ballot pages' record of past official results:
    ({county unit: (total, Democratic share, Republican share)}, the source), or (None, None)."""
    path = os.path.join(LEAN, f"{code.lower()}_place_votes.json")
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    contest = next((c for c in doc.get("contests") or [] if c.get("id") == "2024-president"), None)
    if not contest:
        return None, None
    out = {}
    for unit, p in ((doc.get("places") or {}).get("county") or {}).items():
        v = (p.get("votes") or {}).get("2024-president") or {}
        t = int(v.get("total") or 0)
        if t > 0 and re.fullmatch(r"\d{5}", str(unit)):
            out[str(unit)] = (t, int(v.get("dem", v.get("dfl", 0)) or 0) / t, int(v.get("rep", 0) or 0) / t)
    src = next((s for s in doc.get("sources") or [] if s.get("id") == contest.get("table")), None) or {}
    source = {"agency": nodomain(src.get("agency") or ""), "title": nodomain(src.get("title") or ""),
              "url": src.get("url") if str(src.get("url") or "").startswith("https://") else "", "read": src.get("fetched") or ""}
    return out, source


ROLL = {"us_senate": .985, "us_house": .975, "governor": .98}


def _shares(r, sd, sr, *salt):
    """Each line's share of a count: a partisan candidate takes their party's 2024 share (the other parties share the
    rest); a nonpartisan race's shares are made up, the same on every build; a write-in line takes a small fixed share."""
    cs = r["cs"]
    if r["pt"]:
        so = max(.01, 1 - sd - sr)
        ws = [sd if c[2] == "D" else sr if c[2] == "R" else so * (.3 + .7 * _h("o", r["id"], i)) for i, c in enumerate(cs)]
        if len(cs) == 1:
            ws = [1.0]
    else:
        ws = [(.5 + _h("w", r["id"], i)) for i in range(len(cs))]
    return ws


def practice_state(code, races, past, plan_at, part, say=print):
    """One practice state's figures in the store's long form ({race: entry}) and its precinct count: every county's
    precincts in, part in or none (a state whose count is done: all), each race's lines as the store writes them."""
    from election import store
    counties = sorted(past)
    n_prec = {c: max(2, int(round(past[c][0] / 1100))) for c in counties}
    prog = {}
    for c in counties:
        q = _h("progress", code, c)
        prog[c] = 1.0 if part >= 1 else (0.0 if q < .14 else 1.0 if q > .78 else .2 + (q - .14) / .64 * .7) * min(1.0, part / .8)
    inn = {c: int(round(n_prec[c] * prog[c])) for c in counties}
    tot_all = sum(past[c][0] for c in counties)
    sd_state = sum(past[c][0] * past[c][1] for c in counties) / tot_all
    sr_state = sum(past[c][0] * past[c][2] for c in counties) / tot_all
    house = [r for r in races if r["k"] == "us_house"]
    out = {}
    for r in races:
        if not r["cs"] or r.get("un") or r.get("dx"):
            continue      # a seat elected by one district of the state is left out: the practice has no district lines for it
        ch = [[store.slug(c[0]), c[0], (c[1] or None) if r["pt"] else None, 0, c[0]] for c in r["cs"] if not (len(c) > 3 and c[3])]
        if not ch:
            continue
        ch.append(["write-in", "WRITE-IN", None, 1, None])
        named = [c for c in r["cs"] if not (len(c) > 3 and c[3])]
        rr = dict(r, cs=named)
        roll = ROLL.get(r["k"], .95 if r.get("dx") else .965)
        if r["k"] == "us_house" and len(house) > 1:
            # a district: its state's 2024 shares moved by a fixed made-up amount, its count a share of the state's
            k = len(house)
            swing = (_h("swing", r["id"]) - .5) * .24
            all_p = max(1, int(round(sum(n_prec.values()) / k)))
            frac = sum(inn.values()) / max(1, sum(n_prec.values()))
            ballots = tot_all / k * roll * frac
            ws = _shares(rr, min(.95, max(.03, sd_state + swing)), min(.95, max(.03, sr_state - swing)))
            v = _whole(ws, ballots * .996) + [int(round(ballots * .004))]
            out[r["id"]] = {"t": plan_at, "p": [int(round(all_p * frac)), all_p], "ch": ch, "v": v}
            continue
        v = [0] * len(ch)
        k_ = {}
        for c in counties:
            t, sd, sr = past[c]
            ballots = t * roll * prog[c] * (.96 + .08 * _h("t", r["id"], c))
            if r["pt"]:
                ws = _shares(rr, sd, sr)
            else:
                ws = [w * (.8 + .4 * _h("j", r["id"], c, i)) for i, w in enumerate(_shares(rr, sd, sr))]
            row = _whole(ws, ballots * .996) + [int(round(ballots * .004))] if ballots else [0] * len(ch)
            for i, x in enumerate(row):
                v[i] += x
            k_[c] = {"p": [inn[c], n_prec[c]], "v": row}
        out[r["id"]] = {"t": plan_at, "p": [sum(inn.values()), sum(n_prec.values())], "ch": ch, "v": v, "k": k_}
    return out, (sum(inn.values()), sum(n_prec.values()))


def practice_figures(races, states, polls, live_root, say=print):
    """Practice figures in the live files' own layout, beside Minnesota's: now.json (merged with the one there, so that
    Minnesota's entry stays), and in the snapshot folder it names, a file for each practice state and us.json.
    Returns {file: bytes}."""
    from election import store
    from build_ballot_state_dev import write_if_changed
    by_state = defaultdict(list)
    for r in races:
        by_state[r["st"]].append(r)
    page_races = {r["id"]: [c[0] for c in r["cs"]] for r in races}
    seq, base, snap, now_old = N.practice_base(live_root)
    sizes, sources, us_r, st_entries = {}, [], {}, {}
    for code, (word, at) in sorted(PRACTICE_PLAN.items()):
        past, src = _past(code)
        if not past or not by_state.get(code):
            say(f"  practice: no 2024 county figures for {code}; left out")
            continue
        part = {"done": 1.0, "held": .55, "stale": .7}.get(word, .3 + .5 * _h("part", code))
        long_r, units = practice_state(code, by_state[code], past, at, part, say)
        long = {"v": N.FORMAT_VERSION, "state": code, "at": at, "r": long_r, "practice": PRACTICE_LABEL}
        short = store.compact_page(long)
        if store.expand_page(short) != long:
            raise SystemExit(f"build_night_us: the practice file for {code} does not read back whole")
        bad = N.check_state_live(short, page_races)
        if bad:
            raise SystemExit(f"build_night_us: the practice figures for {code} do not fit the live files' account: " + "; ".join(bad[:5]))
        text = json.dumps(short, ensure_ascii=False, separators=(",", ":"))
        sizes[f"{code.lower()}.json"] = N_write(os.path.join(snap, f"{code.lower()}.json"), text)
        for rid, e in long_r.items():
            us_r[rid] = {k: v for k, v in e.items() if k != "k"}
        by = "hand" if states[code]["s"] == "hand" else "feed"
        st_entries[code] = {"s": word, "t": at, "f": f"{code.lower()}.json", "by": by}
        if src and src.get("url"):
            sources.append(dict(src, state=states[code]["n"]))
    # Minnesota's own practice figures, when its page's builder has written them: its races for Congress and its
    # statewide offices go into us.json exactly as they are
    mn_entry = ((now_old or {}).get("st") or {}).get("MN")
    mn_path = os.path.join(snap, "mn.json")
    if mn_entry and mn_entry.get("f") and os.path.exists(mn_path):
        mn = store.expand_page(json.load(open(mn_path, encoding="utf-8")))
        n = 0
        for rid, e in mn["r"].items():
            if rid in page_races:
                us_r[rid] = {k: v for k, v in e.items() if k != "k"}
                n += 1
        st_entries["MN"] = mn_entry
        say(f"  practice: Minnesota's own practice figures read as they are ({n} of its races are on this page)")
    else:
        say("  practice: Minnesota's practice figures are not there yet (its page's builder writes them); Minnesota is left out")
    at_us = max((e["t"] for e in us_r.values() if e.get("t")), default=PRACTICE_AT)
    us = {"v": N.FORMAT_VERSION, "state": "US", "at": at_us, "r": us_r}
    us_short = store.compact_page(us)
    bad = N.check_state_live(us_short, page_races)
    if bad:
        raise SystemExit("build_night_us: the practice us.json does not fit the live files' account: " + "; ".join(bad[:5]))
    sizes["us.json"] = N_write(os.path.join(snap, "us.json"), json.dumps(us_short, ensure_ascii=False, separators=(",", ":")))
    # every other state: what the updater would say of it at 9:52 p.m. Central (the poll hours file's own UTC times)
    for code, s in states.items():
        if code in st_entries:
            continue
        if code in PRACTICE_REFUSED and s["s"] != "link":
            st_entries[code] = {"s": "refused"}
        elif s["s"] == "link":
            st_entries[code] = {"s": "link"}
        else:
            e = (polls.get("states") or {}).get(code) or {}
            last = max([str(z.get("latest_utc") or z.get("closes_utc") or "") for z in e.get("zones") or []] + [str(e.get("last_close_utc") or "")])
            st_entries[code] = {"s": "wait" if last and PRACTICE_NOW < last else "none"}
    # merged with the practice now.json already there: a state this build says nothing of keeps its entry
    sizes["now.json"] = N.practice_now(live_root, st_entries, PRACTICE_AT, PRACTICE_NEXT, PRACTICE_LABEL, say)
    st = json.load(open(os.path.join(live_root, "now.json"), encoding="utf-8"))["st"]
    words = defaultdict(list)
    for code, e in sorted(st.items()):
        words[e["s"]].append(code)
    say("  practice figures: " + "; ".join(f"{w} {', '.join(c)}" if len(c) < 8 else f"{w} {len(c)} states" for w, c in sorted(words.items())))
    say(f"  practice us.json {sizes['us.json'] / 1e3:,.1f} KB ({len(us_r)} races); state files " +
        ", ".join(f"{k} {v / 1e3:,.0f} KB" for k, v in sorted(sizes.items()) if k not in ("us.json", "now.json")))
    return sizes, sources, seq


def N_write(path, text):
    from build_ballot_state_dev import write_if_changed
    write_if_changed(path, text)
    return len(text.encode("utf-8"))


# ============================================================ the page

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Election Night: results across the country · The Civic Archive</title>
<meta name="description" content="__DESC__">
<meta name="version" content="__VERSION__">
__BRAND__
__HEADSCRIPT__
<style>
__FONTS__
</style>
<style>__CSS__</style>
<style>__BALLOT_CSS__</style>
<style>__NIGHT_CSS__
.nhero{padding:28px 0 4px}
.nhero h1{font-family:var(--serif);font-weight:400;font-size:clamp(38px,6vw,72px);line-height:1;margin:10px 0 0}
.nhero .lede{color:var(--muted);max-width:68ch;font-size:clamp(15px,1.5vw,18px);margin:12px 0 0}
.draftnote{background:var(--brass-soft);color:var(--ink);padding:6px 16px;font:600 12.5px/1.4 var(--sans);text-align:center;border-bottom:1px solid var(--line)}
.draftnote a{color:inherit}
.mybar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0 0}
@media (max-width:640px){.mybar .pick{width:100%}}
.nempty{border:1px dashed var(--line-strong);border-radius:14px;padding:12px 14px;color:var(--muted);font-size:14px;margin-top:12px}
.seg{flex-wrap:wrap;border-radius:20px}
.seg button{min-height:30px;display:inline-flex;align-items:center}
@media (pointer:coarse){.seg button,.zoom button{min-height:44px;min-width:44px}.seg button{justify-content:center}}
__USMAP_CSS__
.npart{border-top:1px dashed var(--line-strong);margin-top:12px;padding-top:10px}
.npart .nrep b{color:var(--ink)}
.stw.part{color:var(--st-live);border-color:var(--st-live);border-style:dashed}
.nusum{display:grid;gap:6px;margin:10px 0 0;padding:0;list-style:none;font-size:14px}
.nusum li{display:flex;gap:9px;align-items:center}
.nusum i{width:14px;height:14px;border-radius:4px;flex:none;border:1px solid var(--line)}
.nucard{display:flex;flex-direction:column;gap:6px;min-height:44px}
.nucard .stw{align-self:flex-start}
.newbar{display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-left:5px solid var(--brass);background:var(--surface);border-radius:14px;padding:6px 14px;margin-top:14px;max-width:96ch}
.newbar button{all:unset;cursor:pointer;color:var(--accent-ink);font-weight:700;min-height:36px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px}
.newbar button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rulebox{font-size:14px;color:var(--ink);border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:10px 14px;margin-top:12px;max-width:96ch;line-height:1.5}
.rulebox b{font-weight:700}
.rlinks{display:flex;gap:6px 18px;flex-wrap:wrap;margin-top:14px;font-size:14px}
.rlinks a{color:var(--accent-ink);font-weight:600;min-height:32px;display:inline-flex;align-items:center}
.ylist{margin-top:10px}
.lnmore{font-size:12.5px;color:var(--muted);margin:2px 0 0}
</style>
</head>
<body>
__BANNER__<div class="nbanner" id="nreh" hidden></div>
<div class="draftnote">A draft for feedback, not the finished site. <a href="https://thecivicarchive.github.io/">Go to the live site</a></div>
__TOPBAR__
<main id="app" class="bwrap" tabindex="-1"><p class="loading muted">Loading the races&hellip;</p></main>
<p class="sr" id="nlive" aria-live="polite"></p>
<footer class="bwrap bfoot">
  <p>Election Night, from The Civic Archive v__VERSION__. Generated on __GENERATED__. Every figure is an official count as each state&rsquo;s own election office posts it, with its time; each state&rsquo;s own results are the authority.</p>
  <p>__FOOTLINKS__</p>
</footer>
__CLBOX__
<script>
const BOOT = __BOOT__;
const CODE = "US";
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
/* ===== parts shared with the rest of the site (taken from their pages when this page is built) ===== */
__CHANGELOG__
__GRID__
__SOURCEFOLD__
__GEO__
/* ===== end of the shared parts ===== */
__NIGHT_JS__
__NIGHTMAP_JS__
__USMAP_JS__
__PAGE_JS__
</script>
</body>
</html>
"""

PAGE_JS = r"""
/* ---------- results across the country ---------- */
const app = $("#app");
let D = null, MAPD = null, R = {}, BY = {}, DIST = null, distP = null, SFILE = {}, MINE = null, mapOff = null;
const VIEWS = [["senate", "Senate"], ["governor", "Governor"], ["house", "House"], ["counted", "What is counted here"]];
const VIEWW = {senate: "U.S. Senate", governor: "Governor", house: "U.S. House", counted: "What is counted here"};
let VIEW = (() => { const v = store.get("night:usview"); return VIEWS.some(x => x[0] === v) ? v : "senate"; })();
const PICK = {};      // what each state's map shows: a race id or "house"
const getJSON = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
const isPreview = () => /^(127\.0\.0\.1|localhost)$/.test(location.hostname) && location.port === "8790";
const NM = st => (D.states[st] || {}).n || st;
const IN = st => st === "DC" ? "the District of Columbia" : NM(st);      /* a state's name inside a sentence */
const S_ = st => D.states[st] || {};
const byName = (a, b) => NM(a).localeCompare(NM(b));
const codes = () => Object.keys(D.states).sort(byName);
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return ""; } };
const NOVOTES = "No votes reported yet.";
const PIN = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="11" r="3"/><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/></svg>`;

/* ---------- the races ---------- */
function index() {
  D.races.forEach(r => { R[r.id] = r; const b = BY[r.st] || (BY[r.st] = {sen: [], gov: [], sw: [], house: []});
    (r.k === "us_senate" ? b.sen : r.k === "us_house" ? b.house : r.k === "governor" ? b.gov : b.sw).push(r); });
  Object.values(BY).forEach(b => { b.house.sort((x, y) => (+x.d || 0) - (+y.d || 0)); b.sen.sort((x, y) => (x.sp || 0) - (y.sp || 0)); });
}
const byOf = st => BY[st] || {sen: [], gov: [], sw: [], house: []};
const allOf = st => { const b = byOf(st); return b.sen.concat(b.gov, b.sw, b.house); };
/* a race's title; a party's primary (rehearsals) and one county's own count (a partial source) say which they are */
function raceTitle(r) {
  const t = r.k === "us_senate" ? "U.S. Senator" + (r.sp ? " (special election)" : "")
    : r.k === "us_house" ? (+r.d ? `U.S. Representative, District ${+r.d}` : "U.S. Representative, at large") : r.o;
  return r.pp != null ? `${t}: ${primaryName(r)}` : r.pa ? `${t}: ${(S_(r.st).pt || {}).n || "one county"} only` : t;
}
const raceAt = id => R[id] || xRace(id);
const hrefRace = r => "#race=" + encodeURIComponent(r.id);
const baseId = r => r.base || r.id;
const ballotHref = r => r.ni ? "" : r.k === "us_senate" || r.k === "us_house" ? BOOT.links.ballot + "us/#race=" + encodeURIComponent(baseId(r))
  : S_(r.st).bal ? BOOT.links.ballot + r.st.toLowerCase() + "/#race=" + encodeURIComponent(baseId(r)) : "";
const nightHref = r => S_(r.st).pg ? BOOT.links.night + r.st.toLowerCase() + "/#race=" + encodeURIComponent(baseId(r)) : "";
/* what a state calls the places its count is given for: [one, many, a heading, inside a sentence] */
const UW = st => S_(st).uw || ["county", "counties", "County by county", "county by county"];
const linesChanged = st => (D.lines.changed || []).includes(st);
const seatsN = r => r.n || 1;
function ruleOf(r) { const rl = S_(r.st).rl || {}; return rl[r.k === "us_senate" ? "s" : r.k === "us_house" ? "h" : "w"] || "plurality"; }
const RULE_WORDS = {
  majority_runoff: "A candidate needs more than half the votes. If no one has a majority, the top two meet again in a runoff.",
  open_primary: "An open primary: every candidate, of every party, on one ballot. A candidate with more than half the votes is elected; if no one has a majority, the top two meet again in a runoff.",
  top_two: "The two candidates who came through the state&rsquo;s top-two primary. They can be of the same party.",
  ranked_choice: "Ranked choice. The figures here are first choices. The state counts the later rounds after the election.",
  majority_or_legislature: "A candidate needs more than half the votes. If no one has a majority, the state&rsquo;s legislature chooses."};
/* certified results name the elected only where the count itself decides: never from first choices, and in a race that
   needs a majority only when the first has one */
function electedOK(r, L) {
  const rule = ruleOf(r); if (rule === "ranked_choice") return false;
  if (rule === "plurality" || rule === "top_two") return true;
  const nm = L.lines.filter(x => !x.wl); return !!(L.total && nm[0] && nm[0].votes * 2 > L.total);
}

/* ---------- the count: every line, coloured by the list's party; a line the list does not have, by its printed party ---------- */
const pcOf = p => { const t = String(p || "").trim().toLowerCase(); if (!t) return "O"; if (/write/.test(t)) return "W";
  if (/democrat/.test(t) || ["dem", "d", "dfl"].includes(t)) return "D"; if (/republican/.test(t) || ["rep", "r", "gop"].includes(t)) return "R";
  if (/libertarian/.test(t) || ["lib", "l", "lpf"].includes(t)) return "L"; if (/green/.test(t) || ["grn", "g", "gp"].includes(t)) return "G";
  if (/no party|independent|nonpartisan/.test(t) || ["npp", "npa", "ind", "i", "una", "unaffiliated", "none"].includes(t)) return "I"; return "O"; };
function linesUS(r, e) {
  const L = lines(r, e);
  if (r.pt) L.lines.forEach(x => { if (x.x) { const k = pcOf(x.party); x.c = `var(--p${k})`; x.p = PPAT[k]; } });
  return L;
}
const sumv = e => e ? (e.v || []).reduce((t, x) => t + (x || 0), 0) + ((e.x || []).reduce((t, a) => t + (a[2] || 0), 0)) + (e.w || 0) : 0;
/* a county's figures in a race's own layout: the state file's county entry holds the unmatched lines' votes alone, in the
   order of the race's own unmatched lines (their names and parties) */
const cEntry = (se, c) => ({u: c.u, v: c.v || [], x: (se.x || []).map((a, k) => [a[0], a[1], (c.x || [])[k] || 0]), w: c.w || 0});
const hasCount = e => !!(e && ((e.u && e.u[0]) || sumv(e)));
function unitWord(r, n, county) {      // what a race's reporting figures count: the state's towns, its counties (in its own word), or precincts
  const S = S_(r.st), raw = LIVE.raw && LIVE.raw.r && LIVE.raw.r[r.id.slice((LIVE.raw.pre || "").length)];
  let w = raw && raw.uk ? String(raw.uk) : null;
  if (!w) w = r.pa ? "precinct" : county ? (S.u === "town" ? "town" : "precinct") : S.u === "town" ? "town" : n && S.nc && n === S.nc ? "@area" : "precinct";
  if (w === "@area" || ((w === "county" || w === "parish") && S.uw)) return n === 1 ? UW(r.st)[0] : UW(r.st)[1];
  const many = {county: "counties", parish: "parishes", precinct: "precincts", town: "towns", ward: "wards", locality: "localities"}[w] || w + "s";
  return n === 1 ? w : many;
}

/* ---------- the live figures: now.json, then us.json (NIGHTLIVE, night_common's poller), and a state's own file only
   for its counties ---------- */
const liveRaces = id => R[id] || null;
/* a state's own file, for its figures county by county: fetched only for a state or race page that draws counties */
function stateFile(st) {
  const s = LIVE.now && LIVE.now.st && LIVE.now.st[st];
  if (!s || !s.f || !LIVE.base) return Promise.resolve(null);
  const seq = LIVE.seq, key = st + "|" + seq;
  if (SFILE[key] === undefined) SFILE[key] = fetch(LIVE.base + s.f, {cache: "force-cache"}).then(r => r.ok ? r.json() : null)
    .then(raw => raw && LIVE.seq === seq ? normState(raw, liveRaces) : null, () => null);
  return SFILE[key];
}
const paused = () => !!livePause();      /* now.json's own "next" decides (night_common), never a number of minutes of this page's */
const stLive = st => (LIVE.now && LIVE.now.st && LIVE.now.st[st]) || null;
/* a race's figures, or those of its parties' primaries in a rehearsal of a primary night */
const anyCount = r => hasCount(E(r.id)) || partsOf(r.id, "party").some(p => hasCount(E(p.id)));
const stateHas = st => !!LIVE.st && allOf(st).some(anyCount);
const stateDone = st => allOf(st).every(r => { const e = E(r.id); return !e || (e.u && e.u[1] && e.u[0] >= e.u[1]); });
/* a state the page reads only in part (one county's own count, where the state publishes none) */
const partial = st => !!S_(st).pt;
const partCount = r => { const p = partsOf(r.id, "county")[0]; return p && hasCount(E(p.id)) ? p : null; };
function stWord(st) {      // the state of a state's count tonight, in one word ("part": one county's own figures are in)
  const S = S_(st), s = stLive(st);
  let w = s && s.s;
  if (partial(st)) {      /* the state's own count is not read: its word is "link", or "part" once the county's figures are in */
    if (["refused", "stale", "held"].includes(w)) return w;
    return ["counting", "done", "official"].includes(w) || allOf(st).some(partCount) ? "part" : "link";
  }
  if (!w) { if (S.s === "link") w = "link"; else if (stateHas(st)) w = stateDone(st) ? "done" : "counting"; else { const I = pollsInfo(st); w = I && I.state === "open" ? "wait" : "none"; } }
  if (w === "counting" && paused()) w = "stale";
  return w;
}
const notRead = w => w === "link" || w === "part";

/* a state's word as a chip; "wait" is the updater's word for the whole day before the polls close, so before they open the
   chip says so */
function chipFor(st) {
  const w = stWord(st);
  if (w === "part") return `<span class="stw part"><i aria-hidden="true"></i>Partly read</span>`;
  if (w === "wait") { const I = pollsInfo(st); if (I && (I.state === "today" || I.state === "before")) return `<span class="stw wait"><i aria-hidden="true"></i>${I.state === "today" ? "Polls open later today" : "No votes yet"}</span>`; }
  return statusChip(w);
}
/* ---------- polls: still open, not open yet, closed (John's words, his veto) ---------- */
function pollsInfo(st) {
  const P = S_(st).p; if (!P || !(P.z || []).length) return null;
  const day = D.election, now = NOW();
  const zs = P.z.map(z => ({z, open: zoned(day, z.o || "00:00", z.tz), close: zoned(day, z.l || z.c, z.tz), first: zoned(day, z.c, z.tz)}));
  const open = new Date(Math.min(...zs.map(x => +x.open))), close = new Date(Math.max(...zs.map(x => +x.close)));
  const state = now >= close ? "closed" : now >= open ? "open" : now.toDateString() === open.toDateString() ? "today" : "before";
  return {zs, open, close, state, P};
}
const whereW = w => !w || /^rest of the state$/i.test(w) ? "the rest of the state" : w.charAt(0).toLowerCase() + w.slice(1);
function closeWords(st) {
  const I = pollsInfo(st); if (!I) return "";
  if (I.zs.length === 1) { const x = I.zs[0]; return x.z.l ? `Polls in ${IN(st)} close between ${fmtTime(x.first)} and ${fmtTime(x.close)}, as each place sets them.` : `Polls in ${IN(st)} close at ${fmtTime(x.close)}.`; }
  return "Polls close at " + I.zs.map(x => `${fmtTime(x.close)} in ${whereW(x.z.w)}`).join(" and ") + ".";
}
const findLink = st => `<a href="${esc((st && S_(st).p && S_(st).p.f) || BOOT.links.nass)}" target="_blank" rel="noopener">Find your polling place</a>`;
function pollsStateHTML(st) {
  const I = pollsInfo(st); if (!I) return "";
  if (I.state === "open") return `<div class="pollsopen" role="note"><b>Polls are still open here. If you haven&rsquo;t voted, your vote still counts.</b>${esc(closeWords(st))}${I.P.ln ? " " + esc(I.P.ln) : ""} ${findLink(st)}.</div>`;
  if (I.state === "today") return `<div class="pollsopen" role="note"><b>Election Day is today.</b>Polls in ${esc(IN(st))} open at ${esc(fmtTime(I.open))}. ${esc(closeWords(st))} ${findLink(st)}.</div>`;
  return "";
}
function pollsUSHTML() {
  const mine = MINE && MINE.st && D.states[MINE.st] ? MINE.st : null;
  if (mine) { const h = pollsStateHTML(mine); if (h) return h; }
  const info = codes().map(st => [st, pollsInfo(st)]).filter(x => x[1]);
  const open = info.filter(x => x[1].state === "open");
  if (open.length) {
    const dc = open.some(x => x[0] === "DC"), n = open.length - (dc ? 1 : 0), last = info.reduce((a, b) => b[1].close > a[1].close ? b : a);
    const where = `${n ? `${n} ${n === 1 ? "state" : "states"}` : ""}${dc ? `${n ? " and " : ""}the District of Columbia` : ""}`;
    return `<div class="pollsopen" role="note"><b>Polls are still open in ${where}. If you haven&rsquo;t voted, your vote still counts.</b>The last polls close at ${esc(fmtTime(last[1].close))}, in ${esc(NM(last[0]))}. Pick your state below for its closing time, or ${findLink(null).replace(">Find", ">find")}.</div>`;
  }
  if (info.some(x => x[1].state === "today")) {
    const t = new Date(Math.min(...info.map(x => Math.min(...x[1].zs.map(z => +z.first)))));
    return `<div class="pollsopen" role="note"><b>Election Day is today.</b>The first polls close at ${esc(fmtTime(t))}. ${findLink(mine)}.</div>`; }
  return "";
}

/* ---------- the words of a count ---------- */
function stampHTML(r, e) {
  const S = S_(r.st), t = (e && e.t) || (LIVE.raw && LIVE.raw.at);
  if (!t) return "";
  return S.s === "hand" ? `Copied from ${esc(S.o)}&rsquo;s results files, saved from the state&rsquo;s site at ${esc(fmtTime(t))}. The state&rsquo;s own site is the authority.`
    : `As reported by ${esc(S.o)} at ${esc(fmtTime(t))}.`;
}
function finalHTML(r, e) {
  const S = S_(r.st);
  if (e && e.of) return `Certified by ${esc(S.cb || "the state")}.`;
  return S.cw ? `Not final: ${esc(S.cw)}.` : "Not final until the state certifies the results.";
}
function notReadHTML(st) {
  const S = S_(st);
  return `${esc(capital(IN(st)))} does not publish a live count this site may read. ${S.url ? `Its own results: <a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.lab || hostOf(S.url))}</a>.` : ""} Official totals are added when the state certifies them.`
    + (S.pt ? ` One county&rsquo;s own figures are read here: ${esc(S.pt.n)}&rsquo;s, shown as that county&rsquo;s part of a race, never as ${esc(IN(st))}&rsquo;s count.` : "");
}
/* a race of a state read in part: the county's own figures, labelled as that county's alone */
function partHTML(r) {
  const S = S_(r.st); if (!S.pt || r.pa || r.un) return "";
  const p = partCount(r), own = S.pt.url ? ` <a href="${esc(S.pt.url)}" target="_blank" rel="noopener">${esc(S.pt.lab || hostOf(S.pt.url))}</a>.` : "";
  if (!p) return `<p class="one">${esc(S.pt.n)}&rsquo;s own figures for this race are shown here once the county posts them: one county&rsquo;s count, not ${esc(IN(r.st))}&rsquo;s.</p>`;
  const e = E(p.id);
  return `<div class="npart"><p class="nrep"><b>${esc(S.pt.n)} only.</b> ${repHTML(p, e)} One county&rsquo;s own figures, not ${esc(IN(r.st))}&rsquo;s count.</p>${linesHTML(p, e)}
    <p class="asof"><span class="tag fact">Fact</span> As reported by ${esc(S.pt.n)} at ${esc(fmtTime(e.t || (LIVE.raw && LIVE.raw.at)))}. Not final: ${S.cw ? esc(S.cw) : "the state certifies the results"}.${own}</p></div>`;
}
function repHTML(r, e) {
  const S = S_(r.st), w = stWord(r.st);
  if (r.un) return "Unopposed: the office is not on the ballot, and the candidate takes it without a vote.";
  if (!hasCount(e)) {
    if (notRead(w) || w === "refused") return w === "refused" ? `The state&rsquo;s site refused this site&rsquo;s request tonight. ${S.url ? `Its own results: <a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.lab || hostOf(S.url))}</a>.` : ""}` : notReadHTML(r.st);
    const I = pollsInfo(r.st);
    if (I && (I.state === "open" || I.state === "today")) return `${NOVOTES} ${esc(closeWords(r.st))} The state releases no results before then.`;
    return stateHas(r.st) ? "This race is not in the state&rsquo;s results file yet." : NOVOTES;
  }
  const a = (e.u || [])[0] || 0, b = (e.u || [])[1] || 0;
  if (!b) return "";
  const U = unitWord(r, b);
  if (b === 1) return a ? `Its one ${U} has reported.` : `Its one ${U} has not reported yet.`;
  return a >= b ? `All ${num(b)} ${U} have reported.` : a ? `${num(a)} of ${num(b)} ${U} have reported.` : `None of its ${num(b)} ${U} has reported yet.`;
}
function linesHTML(r, e, top) {      // the marks (ahead, elected) only on the race's own count, never a county's
  const own = e && e === E(r.id) && !r.pa, L = linesUS(r, e), certified = own && !!e.of, ahead = own && !certified ? aheadSet(r, L) : new Set();
  const el = certified && electedOK(r, L) ? new Set(L.lines.filter(x => !x.wl).slice(0, seatsN(r))) : new Set();
  const shown = top ? L.lines.filter(x => !x.wl).slice(0, top) : L.lines, more = top ? L.lines.filter(x => !x.wl).length - shown.length : 0;
  return `<div class="lns">${shown.map(x => {
    const share = L.total ? x.votes / L.total * 100 : 0;
    const badge = el.has(x) ? `<em class="badge el">Elected</em>` : ahead.has(x) ? `<em class="badge">Ahead in the count so far</em>` : "";
    const party = x.wl ? "" : r.pt ? ` <small>${esc(x.party || "No party given")}</small>` : "";
    const fig = L.total ? `<b>${pct(x.votes, L.total)}</b> <span>${num(x.votes)}<span class="sr"> votes</span></span>` : x.wl ? "" : `<span>&ndash;</span>`;
    return `<div class="ln${x.wl ? " wl" : ""}"><span class="nm"><span class="nsw" style="--c:${x.c}" data-p="${x.p}" aria-hidden="true"></span>${esc(x.name)}${party}${badge ? " " + badge : ""}</span><span class="fig">${fig}</span>${L.total ? `<span class="nbar" aria-hidden="true"><i style="width:${share.toFixed(2)}%;--c:${x.c}" data-p="${x.p}"></i></span>` : ""}</div>`;
  }).join("")}</div>${more > 0 ? `<p class="lnmore">and ${plural(more, "more candidate")}</p>` : ""}`;
}
function noListHTML(r) { return r.nl ? `<p class="one">The state&rsquo;s official candidate list is not loaded here yet${r.why ? `: ${esc(r.why)}` : ""}. Figures, when the state posts them, are shown as the state prints them.</p>` : ""; }
/* a race with no figures of its own whose parties' primaries have them (a rehearsal of a primary night): each primary
   in its place, a contest of its own */
const primaries = r => r.pp == null && !r.pa && !E(r.id) ? partsOf(r.id, "party") : [];
function resultHTML(r, o = {}) {
  const pr = primaries(r);
  if (pr.length) return pr.map(p => resultHTML(p, o)).join("");
  const e = E(r.id), n = seatsN(r), unopp = r.cs.length > 0 && r.cs.filter(c => !c[3]).length <= n && !r.un;
  const head = o.link === false ? esc(raceTitle(r)) : `<a href="${hrefRace(r)}">${esc(raceTitle(r))}</a>`;
  const notes = [n > 1 ? `Voters choose ${num(n)}.` : "", unopp ? (r.cs.length === 1 ? "One candidate is on the ballot." : "As many candidates as seats are on the ballot.") : "",
    r.pt || r.pp != null ? "" : "Nonpartisan office.", r.dx ? "Elected by the voters of one district of the state." : "",
    r.pp != null ? "A party&rsquo;s primary, a contest of its own. Its candidates are shown as the state prints them." : ""].filter(Boolean).join(" ");
  const links = [o.link === false ? "" : `<a href="${hrefRace(r)}">The race, ${esc(UW(r.st)[3])}</a>`, ballotHref(r) ? `<a href="${esc(ballotHref(r))}">Who is running</a>` : ""].filter(Boolean);
  return `<article class="res${o.small ? " small" : ""}"><h3>${head}</h3>${o.where === false ? "" : `<p class="where">${esc(NM(r.st))}</p>`}
    <p class="nrep">${repHTML(r, e)}</p>${r.un ? "" : linesHTML(r, e, o.top)}${notes ? `<p class="one">${notes}</p>` : ""}${r.pp != null ? "" : noListHTML(r)}
    ${hasCount(e) ? `<p class="asof"><span class="tag fact">Fact</span> ${stampHTML(r, e)} ${finalHTML(r, e)}</p>` : ""}${partHTML(r)}
    ${o.foot === false || !links.length ? "" : `<div class="rfoot">${links.join("")}</div>`}</article>`;
}
function rowHTML(r, o = {}) {
  const pr = primaries(r);
  if (pr.length) return pr.map(p => rowHTML(p, Object.assign({}, o, o.sub ? {sub: raceTitle(p)} : {}))).join("");
  const e = E(r.id), L = linesUS(r, e), nm = L.lines.filter(x => !x.wl), ah = aheadSet(r, L), n = seatsN(r);
  const who = x => `<span class="nsw" style="--c:${x.c}" data-p="${x.p}" aria-hidden="true"></span><b>${esc(x.name)}</b>${r.pt && x.party ? ` (${esc(x.party)})` : ""} ${pct(x.votes, L.total)}`;
  let lead, w = stWord(r.st);
  if (r.un) lead = `<small>Unopposed: not on the ballot</small>`;
  else if (!L.total) lead = `<small>${notRead(w) ? (partCount(r) ? `Not read here; ${esc(S_(r.st).pt.n)}&rsquo;s own figures are inside` : "Not read here: the state&rsquo;s own results are linked") : w === "refused" ? "The state&rsquo;s site refused this site&rsquo;s request" : r.nl && !r.cs.length ? "No votes yet; the candidate list is not loaded here" : r.cs.length && r.cs.length <= n ? (r.cs.length === 1 ? "One candidate on the ballot" : "As many candidates as seats") : "No votes yet"}</small>`;
  else if (ah.size) lead = [...ah].map(who).join(", ") + `<small>ahead in the count so far</small>`;
  else lead = who(nm[0]) + `<small>${nm[1] && nm[1].votes === nm[0].votes ? "tied in the count so far" : e && e.of ? "certified" : "the count so far"}</small>`;
  const u = e && e.u && e.u[1] ? `${num(e.u[0])} of ${num(e.u[1])}<br>${unitWord(r, e.u[1])} in` : "";
  return `<a class="nrow" href="${hrefRace(r)}"><span class="t">${esc(o.title || raceTitle(r))}${o.sub ? `<small>${esc(o.sub)}</small>` : ""}</span><span class="l">${lead}</span><span class="u">${u}</span></a>`;
}

/* ---------- the state of the count across the country ---------- */
function nstat(word, body, small, chip) { return `<div class="nstat" role="status">${chip || statusChip(word)}<p>${body}${(small || []).map(t => `<small>${t}</small>`).join("")}</p></div>`; }
function usStatusHTML() {
  if (!LIVE.now) {
    if (isPreview()) return nstat("none", "This preview serves the draft site alone, so there are no live figures here.", ["On election night the figures come from the live site beside the draft."]);
    return nstat("none", NOVOTES, ["Each state&rsquo;s figures appear here as its own election office posts them, with the time on every number."]);
  }
  const cs = codes(), withFig = cs.filter(stateHas), words = cs.map(stWord), n = w => words.filter(x => x === w).length;
  const small = [];
  let word = "none", body = NOVOTES;
  if (withFig.length) {
    word = paused() ? "stale" : "counting";
    const done = cs.filter(st => stateHas(st) && ["done", "official"].includes(stWord(st))).length;
    body = `Figures are in from ${plural(withFig.length, "state")}${done ? `; ${done === 1 ? "one has" : num(done) + " have"} reported from every county or precinct` : ""}.${LIVE.raw && LIVE.raw.at ? ` The newest were posted at ${esc(fmtTime(LIVE.raw.at))}.` : ""}`;
  }
  if (paused()) small.push(`Updates have paused since ${esc(fmtTime(LIVE.now.at))}. The last figures stay, with their time; each state&rsquo;s own results are linked from its page.`);
  if (n("held")) small.push(n("held") === 1 ? "One state&rsquo;s file changed tonight, so its last figures read cleanly are shown, with their time."
    : `${num(n("held"))} states&rsquo; files changed tonight, so their last figures read cleanly are shown, with their time.`);
  const off = n("link") + n("refused") + n("part");
  if (off) small.push(`${off === 1 ? "One state publishes" : `${num(off)} states publish`} no live count this site may read${n("refused") ? ", or refused its requests tonight" : ""}; ${off === 1 ? "its" : "their"} own results are linked, and official totals are added when ${off === 1 ? "it certifies them" : "they certify them"}.`);
  const parts = cs.filter(partial);
  if (parts.length) small.push(`${andList(parts.map(st => `${esc(NM(st))} is partly read: only ${esc(S_(st).pt.n)}&rsquo;s own figures, shown as that county&rsquo;s, never as the state&rsquo;s count`))}. The state&rsquo;s own page has the rest.`);
  small.push("Nothing here is final until each state certifies its results. Until then the page says only who is ahead in the count so far.");
  return nstat(word, body, small);
}
const usStatusBlock = () => `<div data-usstat>${usStatusHTML()}</div>`;
function refreshStatus() { $$("[data-usstat]").forEach(el => { const h = usStatusHTML(); if (el._h !== h) { el.innerHTML = h; el._h = h; } }); }

/* ---------- maps: the states, a state's counties, a state's districts ---------- */
const STEP = m => (NightKit.STEPS.find(s => m < s[0]) || NightKit.STEPS[NightKit.STEPS.length - 1])[1];
function fillOf(r, e) {      // a race's look on a map: {c, op, p} for the line ahead, or {cls, f} for the rest
  if (!r) return {cls: "nr"};
  if (r.un) return {cls: "un"};
  const w = stWord(r.st);
  if (!hasCount(e)) return notRead(w) || w === "refused" ? {f: "link"} : {f: "wait"};
  const L = linesUS(r, e), nm = L.lines.filter(x => !x.wl);
  if (!L.total || !nm.length) return {f: "wait"};
  if (nm[1] && nm[0].votes === nm[1].votes) return {cls: "tie"};
  return {c: nm[0].c, op: STEP((nm[0].votes - (nm[1] ? nm[1].votes : 0)) / L.total * 100), p: nm[0].p};
}
/* the map's patterns (defsHTML) and shapes (shapeHTML) are night_common's US map parts */
function legendHTML(kind, races, extra) {      // kind: race (one race's candidates), party (the parties ahead on the map), counted
  const items = [];
  if (kind === "counted") {
    items.push(`<span><i class="lgsw" style="background:var(--verd)"></i>Read live from the state&rsquo;s own results</span>`,
      `<span><i class="lgsw" style="background:radial-gradient(var(--nstripe) 1.6px,transparent 2px) 0 0/6px 6px,var(--verd)"></i>Read where the state&rsquo;s site allows</span>`,
      `<span><i class="lgsw" style="background:repeating-linear-gradient(45deg,var(--nstripe) 0 2px,transparent 2px 6px),var(--brass)"></i>Copied from files saved by hand from the state&rsquo;s site</span>`,
      `<span><i class="lgsw" style="background:radial-gradient(var(--hatch-ink) 1.4px,transparent 1.8px) 0 0/6px 6px,var(--surface)"></i>Not read here: the state&rsquo;s own results are linked</span>`);
    if (codes().some(partial)) items.push(`<span><i class="lgsw" style="background:repeating-linear-gradient(135deg,var(--verd) 0 2px,var(--surface) 2px 6px)"></i>Partly read: one county&rsquo;s own figures; the state&rsquo;s own results for the rest</span>`);
    if (codes().some(st => ["refused", "stale", "held"].includes(stWord(st))))
      items.push(`<span><i class="lgsw" style="background:var(--surface);border:2px dashed var(--st-hold)"></i>Dashed: tonight the state&rsquo;s site refused or stopped answering, or its file changed and figures are held</span>`);
    return items.join("");
  }
  const seen = new Map(), PARTYW = {D: "Democratic", R: "Republican", I: "Independent or no party", L: "Libertarian", G: "Green", O: "Another party", W: "Write-in"};
  races.forEach(r => { const L = linesUS(r, E(r.id)), named = L.lines.filter(x => !x.wl);
    /* one race's key names its candidates; a map of many races names only the parties of the candidates ahead on it */
    (kind === "race" ? named : L.total && named[0] && !(named[1] && named[1].votes === named[0].votes) ? [named[0]] : []).forEach(x => {
      const pk = (/--p([A-Z])\b/.exec(x.c) || [])[1], key = kind === "race" ? x.name : x.c;
      if (!seen.has(key)) seen.set(key, [x.c, x.p, kind === "race" ? x.name + (r.pt && x.party ? ` (${x.party})` : "") : r.pt ? PARTYW[pk] || "Another party" : "Nonpartisan office"]); }); });
  if (kind === "party") { const order = ["D", "R", "I", "L", "G", "O", "W"], pk = c => order.indexOf((/--p([A-Z])\b/.exec(c) || [])[1]);
    const keep = [...seen].sort((a, b) => (pk(a[0]) < 0 ? 99 : pk(a[0])) - (pk(b[0]) < 0 ? 99 : pk(b[0]))).slice(0, 8); seen.clear(); keep.forEach(([k, v]) => seen.set(k, v)); }
  seen.forEach(([c, p, w]) => items.push(`<span><i class="lgsw" style="--c:${c}" data-p="${p}"></i>${esc(w)}${kind === "race" ? "" : " ahead"}</span>`));
  items.push(`<span><i class="lgsw wait"></i>No votes reported yet</span>`);
  if (races.some(r => ["link", "refused", "part"].includes(stWord(r.st))))
    items.push(`<span><i class="lgsw" style="background:radial-gradient(var(--hatch-ink) 1.4px,transparent 1.8px) 0 0/6px 6px,var(--surface)"></i>Not read here: the state&rsquo;s own results</span>`);
  if (extra === "newlines") items.push(`<span><i class="lgsw" style="background:repeating-linear-gradient(90deg,var(--line-strong) 0 1px,var(--surface) 1px 5px)"></i>New lines for 2026: not drawn by district</span>`);
  if (kind === "race" ? races.some(r => hasCount(E(r.id))) : seen.size) items.push(`<span><i class="lgsw shade"></i>Paler: ahead by under 5 points. Deeper: by 15 or more.</span>`);
  return items.join("");
}

/* the country */
function viewRaces(st, v) { const b = byOf(st); return v === "senate" ? b.sen : v === "governor" ? b.gov : v === "house" ? b.house : []; }
function usMapHTML() {
  return `<section class="bsec" id="map"><h2>The map</h2><p class="sub" id="ussub"></p>
    <div class="usmapgrid"><div class="mapcol">
      <div class="mapbar"><div class="seg" role="group" aria-label="What the map shows" id="useg">${VIEWS.map(([k, w]) => `<button type="button" data-v="${k}" aria-pressed="${k === VIEW}">${w}</button>`).join("")}</div></div>
      <div class="usbox"><svg class="usvg" id="usmap" viewBox="0 0 975 610" role="group" aria-label="Map of the states" aria-describedby="usmaphelp"></svg></div>
      <div class="nlegend" id="uslegend"></div><p class="mnote" id="usnote"></p>
      <p class="sr" id="usmaphelp">The map is a picture of the count; every figure on it is also in the lists on this page.</p>
    </div><aside class="mapside" id="usside" aria-live="polite"></aside></div></section>`;
}
const SUB = {senate: "Each state with a Senate race, in the colour of the candidate ahead in the count so far. Tap a state for its count.",
  governor: "Each state with a governor&rsquo;s race, in the colour of the candidate ahead in the count so far. Tap a state for its count.",
  house: "Every House district, in the colour of the candidate ahead in the count so far. Tap a district for its count.",
  counted: "How this site reads each state&rsquo;s count tonight. Tap a state for its own results page and how it counts."};
const needDist = () => DIST ? Promise.resolve(DIST) : (distP || (distP = usDistricts(BOOT.links.districts).then(d => (DIST = d), e => { distP = null; throw e; })));
function houseRace(st, n) { return byOf(st).house.find(r => +r.d === +n) || null; }
function drawUS() {
  const svg = $("#usmap"); if (!svg) return;
  const v = VIEW, body = [defsHTML("us", 7)];
  const sts = Object.keys(MAPD.d).filter(st => D.states[st]);
  if (v === "house") {
    sts.forEach(st => {
      const hs = byOf(st).house, d = MAPD.d[st];
      if (hs.length === 1 && !linesChanged(st)) body.push(shapeHTML(d, fillOf(hs[0], E(hs[0].id)), "us", `data-st="${st}" data-r="${esc(hs[0].id)}"`));
      else if (linesChanged(st) || !DIST || !DIST.paths[st]) body.push(shapeHTML(d, linesChanged(st) ? {f: "newl"} : {f: "wait"}, "us", `data-st="${st}"`));
      else Object.entries(DIST.paths[st]).forEach(([n, pd]) => { const r = houseRace(st, n); body.push(shapeHTML(pd, fillOf(r, r && E(r.id)), "us", `data-st="${st}"${r ? ` data-r="${esc(r.id)}"` : ""}`)); });
    });
    sts.forEach(st => body.push(`<path class="out" d="${MAPD.d[st]}"/>`));
  } else if (v === "counted") {
    sts.forEach(st => { const s = S_(st).s; body.push(shapeHTML(MAPD.d[st], s === "live" ? {c: "var(--verd)", op: .85} : s === "care" ? {f: "care"} : s === "hand" ? {f: "hand"} : partial(st) ? {f: "part"} : {f: "link"}, "us", `data-st="${st}"`)); });
    /* tonight's trouble on top: a state whose site refused, stopped answering, or whose file changed (figures held) */
    sts.filter(st => ["refused", "stale", "held"].includes(stWord(st))).forEach(st => body.push(`<path class="trouble" d="${MAPD.d[st]}"/>`));
  } else {
    sts.forEach(st => { const rs = viewRaces(st, v), r = rs[0]; body.push(shapeHTML(MAPD.d[st], fillOf(r, r && E(r.id)), "us", `data-st="${st}"${r ? ` data-r="${esc(r.id)}"` : ""}`)); });
  }
  if (US_SEL && MAPD.d[US_SEL]) body.push(`<path class="sel" d="${MAPD.d[US_SEL]}"/>`);
  svg.innerHTML = body.join("");
  svg.setAttribute("aria-label", `Map of the states: ${VIEWW[v]}`);
  $("#ussub").innerHTML = SUB[v];
  const all = v === "counted" ? [] : sts.flatMap(st => viewRaces(st, v));
  $("#uslegend").innerHTML = legendHTML(v === "counted" ? "counted" : "party", all, v === "house" && (D.lines.changed || []).length ? "newlines" : "");
  $("#usnote").innerHTML = v === "house" ? houseNote() : v === "counted" ? "Tonight&rsquo;s state of each count is in the list of every state below." : "";
  $$("#useg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
  if (!US_SEL) usSide(null);
}
function houseNote() {
  const ch = (D.lines.changed || []).filter(st => D.states[st]).sort(byName);
  return `${DIST ? `District lines: ${esc(DIST.vintage || "the current lines")}.` : DIST === null && distP ? "Loading the district lines&hellip;" : ""} ${ch.length ? `${andList(ch.map(NM))} drew new congressional lines for 2026; their districts are listed on their own pages, not drawn here, since the old lines would be the wrong districts.` : ""}`;
}
let US_SEL = null;
function usSummary(v) {
  if (v === "counted") {
    const n = s => codes().filter(st => S_(st).s === s && !(s === "link" && partial(st))).length, np = codes().filter(partial).length;
    return `<span class="kick">${VIEWW[v]}</span><h3>Every state</h3><ul class="nusum"><li><i style="background:var(--verd)"></i>${plural(n("live"), "state")} read live</li><li><i style="background:var(--verd);opacity:.55"></i>${plural(n("care"), "state")} read where the site allows</li><li><i style="background:var(--brass)"></i>${plural(n("hand"), "state")} by hand</li>${np ? `<li><i style="background:repeating-linear-gradient(135deg,var(--verd) 0 2px,var(--surface) 2px 6px)"></i>${plural(np, "state")} partly read: one county&rsquo;s own figures</li>` : ""}<li><i style="background:var(--surface)"></i>${plural(n("link"), "state")} linked, not read here</li></ul><p class="sidehint">Tap a state for its own results page.</p>`;
  }
  const rs = codes().flatMap(st => viewRaces(st, v)), inn = rs.filter(r => hasCount(E(r.id))), by = {};
  inn.forEach(r => { const L = linesUS(r, E(r.id)), nm = L.lines.filter(x => !x.wl); if (!nm[0] || (nm[1] && nm[1].votes === nm[0].votes)) return; const k = r.pt ? pcOf(nm[0].party) : "N"; by[k] = (by[k] || 0) + 1; });
  const PW = {D: "a Democrat", R: "a Republican", I: "an independent", L: "a Libertarian", G: "a Green", O: "another party&rsquo;s candidate", W: "a write-in", N: "a nonpartisan candidate"};
  const rows = Object.entries(by).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<li><i style="background:var(--p${k === "N" ? "O" : k})"></i>${num(n)} with ${PW[k] || "a candidate"} ahead in the count so far</li>`);
  return `<span class="kick">${VIEWW[v]}</span><h3>${plural(rs.length, v === "house" ? "House race" : v === "senate" ? "Senate race" : "governor&rsquo;s race")}</h3>
    <p class="held">${inn.length ? `Figures are in for ${num(inn.length)} of them.` : NOVOTES}</p>${rows.length ? `<ul class="nusum">${rows.join("")}</ul>` : ""}
    <p class="sidehint">${matchMedia("(hover: hover)").matches ? "Point at a state to see its count; click to keep it here." : "Tap a state to see its count."}</p>`;
}
function usSide(st, rid) {
  const side = $("#usside"); if (!side) return;
  if (!st) { side.innerHTML = usSummary(VIEW); return; }
  const v = VIEW, S = S_(st), w = stWord(st);
  let body;
  if (v === "counted") body = `<p class="held">${S.pt ? `Partly read: only ${esc(S.pt.n)}&rsquo;s own figures are read here, shown as that county&rsquo;s, never as the state&rsquo;s count. The state&rsquo;s own results page has the rest.`
      : ({live: "Read live from the state&rsquo;s own results.", care: "Read from the state&rsquo;s own results where its site allows.", hand: "Copied from files saved by hand from the state&rsquo;s own site.", link: "Not read here: the state&rsquo;s own results are linked."}[S.s] || "")}</p>${S.hc ? `<p class="held">${esc(S.hc)}</p>` : ""}${S.url ? `<p class="held"><a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.lab || hostOf(S.url))}</a></p>` : ""}${S.pt && S.pt.url ? `<p class="held"><a href="${esc(S.pt.url)}" target="_blank" rel="noopener">${esc(S.pt.lab || hostOf(S.pt.url))}</a></p>` : ""}`;
  else if (rid && R[rid]) body = resultHTML(R[rid], {small: true, top: 3, where: false});
  else if (v === "house") body = linesChanged(st) ? `<p class="held">${esc(NM(st))} drew new congressional lines for 2026, so its ${plural(byOf(st).house.length, "district")} are listed on its page, not drawn here.</p>` : `<p class="held">${plural(byOf(st).house.length, "House race")}.</p>`;
  else body = `<p class="held">No ${v === "senate" ? "Senate" : "governor&rsquo;s"} race in ${esc(IN(st))} this year.</p>`;
  side.innerHTML = `<span class="kick">${esc(NM(st))} &middot; ${VIEWW[v]}</span><p class="held">${chipFor(st)}</p>${body}<p class="sidehint"><a class="rpgo" href="#state=${st}">Open ${esc(NM(st))} &rsaquo;</a></p>`;
}
function mountUS() {
  const svg = $("#usmap"); if (!svg) return;
  const hover = matchMedia("(hover: hover)").matches;
  drawUS();
  if (VIEW === "house") needDist().then(() => { if (svg.isConnected && VIEW === "house") drawUS(); }, () => { const n = $("#usnote"); if (n) n.textContent = "The district lines could not be loaded. Check your connection and open the page again."; });
  svg.addEventListener("click", e => { const p = e.target.closest("path.s[data-st]"); if (!p) return; US_SEL = p.dataset.st; drawUS(); usSide(p.dataset.st, p.dataset.r);
    const side = $("#usside"); if (!hover && side && side.getBoundingClientRect().top > innerHeight - 80) side.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); });
  if (hover) {
    svg.addEventListener("pointerover", e => { const p = e.target.closest("path.s[data-st]"); if (!p) return; $$("path.s.hl", svg).forEach(x => x.classList.remove("hl")); p.classList.add("hl"); usSide(p.dataset.st, p.dataset.r); });
    svg.addEventListener("pointerleave", () => { $$("path.s.hl", svg).forEach(x => x.classList.remove("hl")); usSide(US_SEL, null); });
  }
  $$("#useg button").forEach(b => b.addEventListener("click", () => { VIEW = b.dataset.v; store.set("night:usview", VIEW); US_SEL = null; drawUS();
    if (VIEW === "house") needDist().then(() => { if (svg.isConnected && VIEW === "house") drawUS(); }, () => {}); }));
}

/* a state: its counties for a statewide race, its districts for the House */
const needCounties = st => usCounties(BOOT.links.counties + st.toLowerCase() + ".json?v=" + (BOOT.ckeys[st] || ""));
function stMapHTML(st, choose) {
  return `<div class="mapgrid usmapgrid" id="stmapsec"><div class="mapcol">
    <div class="mapbar">${choose}<div class="zoom" role="group" aria-label="Zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">&minus;</button><button type="button" data-z="fit" aria-label="Show the whole state">&#10530;</button></div></div>
    <div class="usbox" id="stbox"><svg class="usvg" id="stmap" role="group" aria-label="Map of ${esc(NM(st))}" aria-describedby="stmaphelp"></svg></div>
    <div class="nlegend" id="stlegend"></div><p class="mnote" id="stnote"></p>
    <p class="sr" id="stmaphelp">The map is a picture of the count; every figure on it is also in the lists and the table on this page.</p>
  </div><aside class="mapside" id="stside" aria-live="polite"></aside></div>`;
}
/* spec: {st, race (a race id) or house: 1, fixed: a race page's own race} */
async function mountStMap(spec) {
  const svg = $("#stmap"), side = $("#stside"), box = $("#stbox"), note = $("#stnote"); if (!svg) return;
  const st = spec.st, B = MAPD.b[st]; if (!B) return;
  const vb0 = fitBox(B, aspectOf(B), 1.06), W = UW(st);
  let sel = null, selC = null, pz = null;
  const race = spec.race ? raceAt(spec.race) : null, house = spec.house || (race && race.k === "us_house");
  side.innerHTML = `<p class="held">Loading the map&hellip;</p>`;
  let mode = "whole", cty = null, sf = null, list = null;
  if (house && !linesChanged(st) && byOf(st).house.length > 1) { try { await needDist(); list = DIST.paths[st] ? DIST : null; } catch (e) { list = null; } }
  if (race && S_(st).cf) {      /* the state's own file, for the race's figures county by county, where it gives them */
    sf = await stateFile(st);
    const se = sf && sf.r && sf.r[race.id];
    if (se && se.c) { try { cty = await needCounties(st); mode = "county"; } catch (e) { cty = null; } }
  }
  if (!svg.isConnected) return;
  if (mode !== "county" && house && list) mode = race ? "district" : "districts";
  function relabel(s) {
    if (!DIST || !DIST.cent || !DIST.cent[st]) return;
    $$("text.dlab", svg).forEach(t => { const c = DIST.cent[st][t.dataset.d]; if (!c) return;
      t.setAttribute("transform", `translate(${c[0][0].toFixed(2)} ${c[0][1].toFixed(2)}) scale(${s.toFixed(4)})`);
      t.classList.toggle("tiny", c[1] / (s * s) < 650 && t.dataset.d !== String(sel)); });
  }
  const ce = c => { const se = sf && sf.r && race ? sf.r[race.id] : null; return se && se.c && se.c[c] ? cEntry(se, se.c[c]) : null; };
  function draw() {
    const body = [defsHTML("sm", vb0[2] / 90)];
    if (mode === "county") {
      const part = race.k === "us_house" || race.dx;      /* a district's race: a county the state's file gives no line for is outside it */
      Object.entries(cty.paths).forEach(([c, d]) => { const x = ce(c); body.push(shapeHTML(d, x && hasCount(x) ? fillOf(race, x) : !x && part ? {cls: "nr"} : {f: "wait"}, "sm", x || !part ? `data-c="${c}"` : "")); });
      body.push(`<path class="out" d="${MAPD.d[st]}"/>`);
      if (race.k === "us_house" && DIST && DIST.paths[st] && DIST.paths[st][String(+race.d)]) body.push(`<path class="sel" d="${DIST.paths[st][String(+race.d)]}"/>`);
      if (selC && cty.paths[selC]) body.push(`<path class="sel" d="${cty.paths[selC]}"/>`);
      note.innerHTML = `${esc(W[2])}, as the state&rsquo;s file gives them. Tap a ${esc(W[0])} for its own figures.${race.k === "us_house" ? " The district&rsquo;s own lines are drawn on top." : ""}`;
    } else if (mode === "districts" || mode === "district") {
      Object.entries(list.paths[st]).forEach(([n, d]) => { const r = houseRace(st, n), mine = race && +race.d === +n;
        body.push(shapeHTML(d, mode === "district" && !mine ? {cls: "nr"} : fillOf(r, r && E(r.id)), "sm", `data-d="${n}"${r ? ` data-r="${esc(r.id)}" tabindex="0" role="button" aria-label="${esc(raceTitle(r))}"` : ""}`)); });
      Object.keys(list.paths[st]).forEach(n => body.push(`<text class="dlab" data-d="${n}" dy=".36em">${n}</text>`));
      body.push(`<path class="out" d="${MAPD.d[st]}"/>`);
      if (sel != null && list.paths[st][String(sel)]) body.push(`<path class="sel" d="${list.paths[st][String(sel)]}"/>`);
      if (race && list.paths[st][String(+race.d)]) body.push(`<path class="sel" d="${list.paths[st][String(+race.d)]}"/>`);
      note.innerHTML = `District lines: ${esc(DIST.vintage || "the current lines")}.${mode === "district" ? " Tap another district for its race." : " Tap a district for its race."}`;
    } else {
      const r = race || (house ? byOf(st).house[0] : null), e = r ? E(r.id) : null;
      body.push(shapeHTML(MAPD.d[st], r ? fillOf(r, e) : {cls: "nr"}, "sm", ""));
      const B2 = MAPD.b[st];
      if (house && linesChanged(st)) body.push(`<text class="big" transform="translate(${((B2[0] + B2[2]) / 2).toFixed(1)} ${((B2[1] + B2[3]) / 2).toFixed(1)}) scale(${pz.upp().toFixed(4)})" dy=".35em">New district lines for 2026</text>`);
      note.innerHTML = race && race.un ? "Unopposed: the office is not on the ballot, so there is no count to draw."
        : house && linesChanged(st) ? `${esc(NM(st))} drew new congressional lines for 2026. The new map is not drawn here, so each district&rsquo;s count is in the list below; the old lines would be the wrong districts.`
        : house && byOf(st).house.length > 1 ? "The district lines could not be loaded. Check your connection and open the page again; every count is in the list below."
        : race && race.pa ? `${esc(S_(st).pt.n)}&rsquo;s own figures are one county&rsquo;s part of the race; the map shows the state, whose own count is not read here.`
        : race && race.k !== "us_house" && !S_(st).cf ? `The whole state, by its total: this site does not read the state&rsquo;s figures ${esc(W[3])}.`
        : race && hasCount(e) && race.k !== "us_house" ? `The whole state, by its total: the state&rsquo;s file gives no ${esc(W[0])} figures for this race.` : race && race.dx ? "Elected by one district of the state; its lines are not drawn here." : "The whole state votes for this seat.";
    }
    svg.innerHTML = body.join("");
    pz.set(pz.vb);
  }
  function rest() {
    if (mode === "districts") { side.innerHTML = `<span class="kick">${esc(NM(st))} &middot; U.S. House</span><h3>${plural(byOf(st).house.length, "district")}</h3><p class="sidehint">Tap a district for its count.</p>`; return; }
    if (spec.fixed) {      /* a race's own page: its count is above the map, so the side says what the map can add */
      const e = E(race.id), se = sf && sf.r && sf.r[race.id], n = se && se.c ? Object.keys(se.c).length : 0, inn = se && se.c ? Object.values(se.c).filter(c => c.u && c.u[1] && c.u[0] >= c.u[1]).length : 0;
      side.innerHTML = `<span class="kick">${esc(NM(st))}</span><h3>${esc(raceTitle(race))}</h3><p class="held">${mode === "county" ? `${num(inn)} of ${plural(n, W[0], W[1])} ${n === 1 ? "has" : "have"} every precinct in.` : hasCount(e) ? repHTML(race, e) : repHTML(race, null)}</p>`
        + `<p class="sidehint">${mode === "county" ? `Tap a ${esc(W[0])} for its own figures.` : mode === "district" ? "Tap another district for its race." : ""}</p>`;
      return; }
    const r = race || byOf(st).house[0]; side.innerHTML = r ? resultHTML(r, {small: true, top: 4, where: false}) : ""; }
  function pick(t) {
    if (mode === "county") { const c = t.dataset.c, x = ce(c), name = (cty.n || {})[c] || c;
      selC = c; draw();
      side.innerHTML = `<span class="kick">${esc(name)}</span><h3>${esc(raceTitle(race))}</h3>` + (x && hasCount(x) ? `<p class="held">${x.u && x.u[1] ? `${num(x.u[0])} of ${num(x.u[1])} ${unitWord(race, x.u[1], true)} in this ${esc(W[0])} have reported.` : ""}</p>${linesHTML(race, x)}<p class="asof"><span class="tag fact">Fact</span> ${stampHTML(race, E(race.id))}</p>`
        : `<p class="held">No votes reported from this ${esc(W[0])} yet.</p>`) + `<p class="sidehint"><button type="button" class="linkbtn" data-back="1">Back to the whole race</button></p>`;
      return; }
    if (t.dataset.r && R[t.dataset.r]) {
      if (spec.fixed && t.dataset.r !== race.id) { location.hash = "race=" + encodeURIComponent(t.dataset.r); return; }
      sel = +t.dataset.d; draw(); side.innerHTML = resultHTML(R[t.dataset.r], {small: true, top: 4, where: false}) + (mode === "districts" ? `<p class="sidehint"><button type="button" class="linkbtn" data-back="1">Back to every district</button></p>` : ""); }
  }
  if (mapOff) mapOff.abort();      // the window's listeners from the last map opened go with it
  mapOff = new AbortController();
  pz = svgPanZoom(svg, box, vb0, {signal: mapOff.signal, buttons: $("#stmapsec .zoom"), onView: (_vb, upp) => relabel(upp)});
  svg.addEventListener("click", e => { if (pz.wasDrag()) return; const t = e.target.closest("path.s[data-c], path.s[data-r]"); if (t) pick(t); });
  svg.addEventListener("keydown", e => { if (e.key !== "Enter" && e.key !== " ") return; const t = e.target.closest("path.s[data-r]"); if (t) { e.preventDefault(); pick(t); } });
  side.addEventListener("click", e => { if (e.target.closest("[data-back]")) { sel = null; selC = null; draw(); rest(); } });
  const lg = $("#stlegend");
  if (lg) lg.innerHTML = race && race.un ? "" : mode === "districts" ? legendHTML("party", byOf(st).house) : legendHTML("race", race ? [race] : byOf(st).house.slice(0, 1));
  draw(); rest();
  return {mode};
}

/* ---------- your ballot: the state and district, worked out on this device; the spot itself is never kept ---------- */
const stateRings = {};
function locateUS(lon, lat) {      // {st, d}: d is null where the lines are not this year's or are not loaded
  const pt = albersUsa(lon, lat); if (!pt) return null;
  let st = null;
  for (const s of Object.keys(MAPD.d)) { const b = MAPD.b[s]; if (!D.states[s] || pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) continue;
    if (inShape(pt, stateRings[s] || (stateRings[s] = pathRings(MAPD.d[s])))) { st = s; break; } }
  if (!st) return null;
  const hs = byOf(st).house; let d = null;
  if (hs.length === 1) d = hs[0].d;
  else if (!linesChanged(st) && DIST && DIST.states[st]) for (const [n, rings] of Object.entries(DIST.states[st])) { if (inShape(pt, rings.map(rg => decodeRing(rg, DIST.q || 50)))) { d = String(+n); break; } }
  return {st, d};
}
function readMine() {
  const ok = m => m && m.st && D.states[m.st] ? {st: m.st, d: m.d != null && m.d !== "" ? String(+m.d) : null} : null;
  try { return ok(JSON.parse(store.get("night:us") || "null")) || ok(JSON.parse(store.get("ballot:mine") || "null")) || ok({st: store.get("state")}); } catch (e) { return null; }
}
function yoursHTML() {
  return `<section class="bsec" id="yours"><h2>Your ballot&rsquo;s results</h2>
    <p class="sub">Use your location, or pick your state and district, and the count of your races for Congress, governor and the other statewide offices appears here. Your location is worked out on this device and never sent anywhere.</p>
    <div class="mybar"><button type="button" class="locbtn" id="yloc">${PIN}Use my location</button><select class="pick" id="yst" aria-label="Your state"><option value="">Or pick your state</option>${codes().map(st => `<option value="${st}">${esc(NM(st))}</option>`).join("")}</select><select class="pick" id="ydi" aria-label="Your district" hidden></select><button type="button" class="linkbtn" id="yforget" hidden>Forget my location</button></div>
    <p class="ynote" id="ynote" aria-live="polite"></p><div id="yres"></div></section>`;
}
function mineHTML(m) {
  const b = byOf(m.st), hr = m.d != null ? b.house.find(r => +r.d === +m.d) : null, S = S_(m.st);
  const statewide = b.sw.filter(r => !r.dx), dx = b.sw.filter(r => r.dx);
  const rows = b.sen.concat(b.gov, statewide).map(r => rowHTML(r)).join("") + (hr ? rowHTML(hr) : "");
  const house = hr ? "" : b.house.length ? `<p class="ynote">${linesChanged(m.st) ? `${esc(NM(m.st))} drew new congressional lines for 2026, so your district cannot be worked out from your location here. Pick it above.` : "Pick your district above to add its House race."}</p>` : "";
  const more = [S.pg ? `<a class="rpgo" href="${esc(BOOT.links.night + m.st.toLowerCase() + "/#mine")}">Every contest on your ballot in ${esc(NM(m.st))}, down to the school board &rsaquo;</a>` : "",
    `<a class="rpgo" href="#state=${m.st}">${esc(NM(m.st))}&rsquo;s page &rsaquo;</a>`].filter(Boolean).join(" ");
  return `${pollsStateHTML(m.st)}${rows ? `<div class="nrows ylist">${rows}</div>` : `<p class="nempty">No race for Congress, governor or a statewide office from ${esc(IN(m.st))} is on this page&rsquo;s lists.${S.url ? ` Its own results: <a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.lab || hostOf(S.url))}</a>.` : ""}</p>`}${house}
    ${dx.length ? `<p class="ynote">${plural(dx.length, "statewide board seat")} in ${esc(NM(m.st))} ${dx.length === 1 ? "is" : "are"} elected by district; ${dx.length === 1 ? "it is" : "they are"} on the state&rsquo;s page.</p>` : ""}<p class="rlinks">${more}</p>`;
}
function paintMine() {
  const out = $("#yres"), fb = $("#yforget"), sel = $("#yst"), di = $("#ydi"); if (!out) return;
  if (fb) fb.hidden = !MINE;
  if (sel) sel.value = MINE ? MINE.st : "";
  if (di) { const hs = MINE ? byOf(MINE.st).house : [];
    di.innerHTML = hs.length > 1 ? `<option value="">Your district</option>` + hs.map(r => `<option value="${esc(String(+r.d))}">${esc(raceTitle(r).replace(/^U\.S\. Representative, /, ""))}</option>`).join("") : "";
    di.hidden = hs.length <= 1; di.value = MINE && MINE.d != null ? String(+MINE.d) : ""; }
  out.innerHTML = MINE ? mineHTML(MINE) : "";
}
function keepMine(m) { MINE = m; store.set("night:us", JSON.stringify({st: m.st, d: m.d})); store.set("state", m.st); }
function mountYours() {
  const sel = $("#yst"), di = $("#ydi"), note = $("#ynote"), btn = $("#yloc"), fb = $("#yforget"); if (!sel) return;
  sel.addEventListener("change", () => { note.textContent = ""; if (!sel.value) return; const hs = byOf(sel.value).house; keepMine({st: sel.value, d: hs.length === 1 ? String(+hs[0].d) : null}); paintMine(); });
  di.addEventListener("change", () => { if (!MINE) return; keepMine({st: MINE.st, d: di.value || null}); paintMine(); });
  fb.addEventListener("click", () => { ["night:us", "pin", "state", "district", "ballot:mine"].forEach(k => store.del(k)); MINE = null; paintMine();
    note.textContent = "Forgotten. Your location and your choices are no longer kept on this device, on this page or the site’s others."; });
  btn.addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn’t available in this browser. Pick your state instead."; return; }
    note.textContent = "Finding your state and district…";
    navigator.geolocation.getCurrentPosition(pos => needDist().catch(() => null).then(() => {
      const lat = pos.coords.latitude, lon = pos.coords.longitude, acc = pos.coords.accuracy || 0, hit = locateUS(lon, lat);
      if (!hit) { note.textContent = "That spot isn’t inside a state on the map. Pick your state instead."; return; }
      keepMine(hit);
      store.set("pin", JSON.stringify({st: hit.st, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(acc)}));      // rounded, about half a mile: the same kept pin the other pages use
      paintMine();
      const hs = byOf(hit.st).house;
      const where = hit.d != null && hs.length > 1 ? `${NM(hit.st)}, and it looks like district ${+hit.d}` : NM(hit.st);
      note.textContent = `${where}. Worked out on this device; your location never leaves it.${hit.d != null && hs.length > 1 ? " Near a district line the guess can be off by one." : hit.d == null && hs.length > 1 ? (linesChanged(hit.st) ? " The state drew new lines for 2026: pick your district." : " Pick your district.") : ""}${acc > 8000 ? ` Your device could only place you within about ${Math.round(acc / 1609.34)} miles, so treat the district as a rough guess.` : ""}`;
    }), () => { note.textContent = "Location wasn’t shared. Pick your state instead."; }, {timeout: 15000, maximumAge: 600000});
  });
  paintMine();
}

/* ---------- where it comes from ---------- */
function srcItem(s, extra) {
  return {a: s.a || "", h: `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>${s.title ? `: ${esc(s.title)}` : ""}<small><span class="tag ${s.secondary ? "analysis" : "fact"}">${s.secondary ? "Secondary" : "Fact"}</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(hostOf(s.url))}</a>` : ""}${s.read ? ` &middot; read ${esc(s.read)}` : ""}${extra ? ` &middot; ${extra}` : ""}</small></div>`};
}
function sourceParts(st) {
  const cs = st ? [st] : codes();
  const res = cs.filter(c => S_(c).url).map(c => srcItem({a: NM(c), agency: NM(c), title: S_(c).lab || "its own election results", url: S_(c).url},
    {live: "read live", care: "read where its site allows", hand: "copied from files saved by hand", link: "linked, not read here"}[S_(c).s] || ""));
  const polls = cs.filter(c => S_(c).p && S_(c).p.src).map(c => srcItem({a: NM(c), agency: NM(c), title: "Poll hours: " + S_(c).p.src.title, url: S_(c).p.src.url, read: S_(c).p.src.read}));
  const looks = cs.filter(c => S_(c).p && S_(c).p.f).map(c => srcItem({a: NM(c), agency: NM(c), title: "Its own polling place lookup (linked, never asked by this site)", url: S_(c).p.f}));
  const parts = cs.filter(c => S_(c).pt && S_(c).pt.url).map(c => srcItem({a: NM(c), agency: S_(c).pt.n, title: (S_(c).pt.lab || "its own election results") + ": one county's own figures, read as its part of a race, never as the state's count", url: S_(c).pt.url},
    "read live, this county only"));
  const prac = BOOT.practice ? (BOOT.practice.sources || []).filter(s => !st || s.state === NM(st)).map(s => srcItem({a: s.state, agency: s.agency, title: s.title, url: s.url, read: s.read}, "used here for practice only")) : [];
  return {
    results: {items: res.concat(parts, prac), notes: ["Every figure is an official count as the state&rsquo;s own election office posts it, with the time it states. Nothing here is a forecast: until a state certifies its results, the page says only who is ahead in the count so far.",
      "A state this site does not read is linked to its own results; its official totals are added when it certifies them."]},
    lists: {items: [], notes: [`Who is on each ballot comes from each state&rsquo;s official candidate list, as the On The Ballot pages read them; each race&rsquo;s page there names its source. <a href="${esc(BOOT.links.ballot)}us/">On The Ballot: Congress</a>.`]},
    rules: {items: polls.concat(looks), notes: D.sources.cert ? [`When each state certifies comes from each state&rsquo;s own law, as NCSL&rsquo;s summary of certification deadlines sets it out (secondary): <a href="${esc(D.sources.cert)}" target="_blank" rel="noopener">${esc(hostOf(D.sources.cert))}</a>.`] : []},
    maps: {items: D.sources.maps.map(s => srcItem(s)), notes: [`House district lines: ${esc(D.lines.vintage || "the current lines")}, from the Congress ballot page&rsquo;s own file. A state that drew new lines for 2026 is not drawn by district.`]},
    page: {notes: ["The map shades each state, district or county in the colour of the candidate ahead there in the count so far: paler for a lead under 5 points, deeper for 15 points or more; hatching marks a place with no votes reported yet. A party&rsquo;s colour is used only for that party&rsquo;s candidates; candidates for a nonpartisan office take neutral tones.",
      "Use my location works out your state, and your district where this year&rsquo;s lines are drawn, on this device, and keeps only those there (and a copy of your spot rounded to about half a mile, which the site&rsquo;s other pages share) until you tap Forget my location. Nothing is sent anywhere.",
      "Times are shown in your own time zone, worked out on this device."]}};
}
function sourcesHTML(st) { return `<div id="nsrc">${sourceFold("Where this comes from", sourceParts(st), "sources")}</div>`; }

/* ---------- pages ---------- */
function heroHTML(kick, title, lede) { return `<section class="bhero nhero"><span class="eyebrow">${kick}</span><h1>${title}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</section>`; }
function crumbs(list) { return `<nav class="crumbs" aria-label="Where you are"><a href="#">Results across the country</a>${list.map(x => ` &rsaquo; ${x}`).join("")}</nav>`; }
function listSection(id, title, sub, rs, o) { return `<section class="bsec" id="${id}"><h2>${title}</h2>${sub ? `<p class="sub">${sub}</p>` : ""}<div class="nrows">${rs.map(r => rowHTML(r, o ? o(r) : {})).join("")}</div></section>`; }
function stateCards() {
  return codes().map(st => { const n = allOf(st).length, w = stWord(st), S = S_(st);
    return `<a class="scard2 nucard" href="#state=${st}"><b>${esc(NM(st))}</b>${chipFor(st)}<span>${n ? plural(n, "race") + " on this page" : "No race of these kinds on this page"}${S.pt ? ` &middot; partly read: ${esc(S.pt.n)} only` : S.s === "link" ? " &middot; its own results are linked" : ""}</span></a>`; }).join("");
}
function home(h) {
  document.title = "Election Night: results across the country · The Civic Archive";
  const sen = codes().flatMap(st => byOf(st).sen), gov = codes().flatMap(st => byOf(st).gov);
  const nFed = D.races.filter(r => r.k === "us_house" || r.k === "us_senate").length, nSw = D.races.length - nFed;
  app.innerHTML = heroHTML("Election Night &middot; United States", "Results across the country",
      `Every state&rsquo;s races for Congress, governor and the other statewide offices: ${num(nFed)} for Congress and ${num(nSw)} statewide, counted as each state&rsquo;s own election office posts the figures. Official counts only, each with its time.`)
    + pollsUSHTML() + usStatusBlock() + usMapHTML() + yoursHTML()
    + listSection("senlist", "The Senate races", `${plural(sen.length, "seat")}, state by state.`, sen, r => ({title: NM(r.st), sub: raceTitle(r)}))
    + listSection("govlist", "The governors&rsquo; races", `${plural(gov.length, "state")} elect a governor this year.`, gov, r => ({title: NM(r.st), sub: raceTitle(r)}))
    + `<section class="bsec" id="states"><h2>Every state</h2><p class="sub">Each state&rsquo;s count tonight, its races for Congress and its statewide offices, and its own results page.</p><div class="sgrid">${stateCards()}</div></section>`
    + sourcesHTML();
  mountUS(); mountYours();
  const at = {mine: "yours", yours: "yours", states: "states", senate: "senlist", governors: "govlist", governor: "govlist", map: "map", house: "map", counted: "map"}[h];
  if (at) { const el = $("#" + at); if (el) el.scrollIntoView(); }
}
/* one state's count tonight: its word, how much is in and when, and what the reader should know (full: the state's own page) */
function stateStatusHTML(st, full) {
  const S = S_(st), w = stWord(st), rs = allOf(st), have = rs.filter(anyCount);
  const t = have.reduce((m, r) => [r].concat(partsOf(r.id, "party")).reduce((m2, x) => { const e = E(x.id), tt = e && e.t; return tt && (!m2 || tt > m2) ? tt : m2; }, m), null);
  const own = S.url ? `<a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.lab || hostOf(S.url))}</a>` : "";
  let body;
  if (notRead(w)) body = notReadHTML(st);
  else if (w === "refused") body = `The state&rsquo;s site refused this site&rsquo;s request tonight, so its count is not read here.${own ? ` Its own results: ${own}.` : ""}`;
  else if (!have.length) { const I = pollsInfo(st); body = I && (I.state === "open" || I.state === "today") ? `${NOVOTES} ${esc(closeWords(st))} The state releases no results before then.` : NOVOTES; }
  else body = (full ? `Figures are in for ${num(have.length)} of its ${plural(rs.length, "race")} on this page.` : "")
    + (t ? (full ? " " : "") + (S.s === "hand" ? `Copied from ${esc(S.o)}&rsquo;s results files, saved from the state&rsquo;s site at ${esc(fmtTime(t))}. The state&rsquo;s own site is the authority.` : `As reported by ${esc(S.o)} at ${esc(fmtTime(t))}.`) : "");
  const small = [];
  if (w === "held") small.push(`The state&rsquo;s file changed tonight, so these are the last figures read cleanly, with their time.`);
  if (w === "stale") small.push(`The state&rsquo;s site has not answered lately, or updates have paused. The last figures stay, with their time.${own ? ` Its own results: ${own}.` : ""}`);
  if (full && S.hc) small.push(esc(S.hc));
  if (full && !notRead(w) && S.cw) small.push(`Not final: ${esc(S.cw)}.`);
  if (full && own && !["link", "part", "refused", "stale"].includes(w)) small.push(`The state&rsquo;s own results: ${own}.`);
  if (w === "part") small.push(`${esc(S.pt.n)}&rsquo;s own figures are in: each race below shows them as that county&rsquo;s part, never as ${esc(IN(st))}&rsquo;s count.${S.pt.url ? ` Its own results: <a href="${esc(S.pt.url)}" target="_blank" rel="noopener">${esc(S.pt.lab || hostOf(S.pt.url))}</a>.` : ""}`);
  return nstat(w, body, small, chipFor(st));
}
function statePage(st) {
  if (!D.states[st]) { app.innerHTML = crumbs([]) + `<p class="nempty">No state with the code ${esc(st)} is on this page. <a href="#">See every state</a>.</p>`; return; }
  const S = S_(st), b = byOf(st), w = stWord(st);
  document.title = `Election Night: ${NM(st)}, Congress and statewide · The Civic Archive`;
  const rs = allOf(st);
  const opts = b.sen.concat(b.gov, b.sw).map(r => `<option value="${esc(r.id)}">${esc(raceTitle(r))}</option>`).join("") + (b.house.length ? `<option value="house">U.S. House: ${b.house.length === 1 ? "the seat" : "every district"}</option>` : "");
  const first = PICK[st] && (PICK[st] === "house" || R[PICK[st]]) ? PICK[st] : (b.sen[0] || b.gov[0] || b.sw[0] || {}).id || (b.house.length ? "house" : "");
  app.innerHTML = crumbs([esc(NM(st))]) + heroHTML("Election Night &middot; " + esc(NM(st)), esc(NM(st)),
      rs.length ? `${b.sen.length + b.house.length ? plural(b.sen.length + b.house.length, "race") + " for Congress" : ""}${b.sen.length + b.house.length && b.gov.length + b.sw.length ? " and " : ""}${b.gov.length + b.sw.length ? plural(b.gov.length + b.sw.length, "statewide office") : ""}, counted as ${esc(S.o)} posts the figures.` : `No race for Congress, governor or a statewide office from ${esc(IN(st))} is on this page&rsquo;s lists.`)
    + (S.pg ? `<p class="rlinks"><a class="rpgo" href="${esc(BOOT.links.night + st.toLowerCase() + "/")}">Every race in ${esc(NM(st))}, down to the school boards &rsaquo;</a></p>` : "")
    + pollsStateHTML(st) + stateStatusHTML(st, true)
    + (rs.length ? `<section class="bsec" id="statemap"><h2>The map</h2><p class="sub">Pick a race. ${S.cf ? `A statewide race is drawn ${esc(UW(st)[3])} where the state&rsquo;s file gives ${esc(UW(st)[0])} figures.` : "The whole state is drawn by its total."} The House is drawn district by district where this year&rsquo;s lines are drawn.</p>${stMapHTML(st, rs.length ? `<select class="pick" id="stpick" aria-label="What the map shows">${opts}</select>` : "")}</section>` : "")
    + (b.sen.length ? `<section class="bsec"><h2>U.S. Senate</h2><div class="rgrid2">${b.sen.map(r => resultHTML(r, {where: false})).join("")}</div></section>` : "")
    + (b.gov.length + b.sw.length ? `<section class="bsec"><h2>Governor and the statewide offices</h2><div class="rgrid2">${b.gov.concat(b.sw).map(r => resultHTML(r, {small: true, where: false})).join("")}</div></section>` : "")
    + (b.house.length ? `<section class="bsec"><h2>U.S. House</h2><div class="nrows">${b.house.map(r => rowHTML(r)).join("")}</div></section>` : "")
    + sourcesHTML(st);
  const sel = $("#stpick");
  if (sel) { sel.value = first; const go = () => { PICK[st] = sel.value; mountStMap(sel.value === "house" ? {st, house: 1} : {st, race: sel.value}); };
    sel.addEventListener("change", go); go(); }
}
function racePage(id) {
  const r = raceAt(id);
  if (!r) { app.innerHTML = crumbs([]) + `<p class="nempty">No race with that address is on this page. <a href="#">See every race</a>.</p>`; return; }
  const S = S_(r.st), e = E(r.id), rule = ruleOf(r);
  document.title = `${raceTitle(r)}, ${NM(r.st)} · Election Night · The Civic Archive`;
  const links = [ballotHref(r) ? `<a href="${esc(ballotHref(r))}">Who is running</a>` : "", nightHref(r) ? `<a href="${esc(nightHref(r))}">${esc(NM(r.st))}&rsquo;s own Election Night page, precinct by precinct</a>` : "",
    S.url ? `<a href="${esc(S.url)}" target="_blank" rel="noopener">The state&rsquo;s own results</a>` : ""].filter(Boolean);
  const rules = [rule !== "plurality" ? RULE_WORDS[rule] : "", r.op && rule !== "open_primary" ? RULE_WORDS.open_primary : ""].filter(Boolean);
  const box = (rules.length ? `<b>How this race is decided.</b> ${rules.join(" ")} ` : "") + (S.hc ? `<b>How ${esc(IN(r.st))} counts.</b> ${esc(S.hc)}` : "");
  app.innerHTML = crumbs([`<a href="#state=${r.st}">${esc(NM(r.st))}</a>`, esc(raceTitle(r))]) + `<div id="newfig"></div>` + pollsStateHTML(r.st)
    + (["held", "stale"].includes(stWord(r.st)) ? stateStatusHTML(r.st, false) : "")
    + `<section class="bsec">${resultHTML(r, {link: false, foot: false})}${box ? `<div class="rulebox">${box}</div>` : ""}<p class="rlinks">${links.join("")}</p></section>`
    + `<section class="bsec"><h2>The map</h2>${stMapHTML(r.st, `<span class="kick">${esc(raceTitle(r))}</span>`)}</section>`
    + `<section class="bsec"><h2>${esc(UW(r.st)[2])}</h2><div class="tblwrap" id="ntbl"><p class="held" style="padding:14px">Loading&hellip;</p></div></section>` + sourcesHTML(r.st);
  mountStMap({st: r.st, race: r.id, fixed: 1});
  tableFor(r);
}
function tableFor(r) {
  const host = $("#ntbl"); if (!host) return;
  const msg = t => { host.innerHTML = `<p class="held" style="padding:14px">${t}</p>`; };
  if (!hasCount(E(r.id))) { msg(repHTML(r, null)); return; }
  const W = UW(r.st);
  if (r.pa) { msg(`These are ${esc(S_(r.st).pt.n)}&rsquo;s own figures, given for the county as a whole; the total is above.`); return; }
  if (!S_(r.st).cf) { msg(`This site does not read this state&rsquo;s figures ${esc(W[3])}; the race&rsquo;s total is above.`); return; }
  Promise.all([stateFile(r.st), needCounties(r.st).catch(() => null)]).then(([sf, cty]) => {
    if (!$("#ntbl")) return;
    const se = sf && sf.r && sf.r[r.id];
    if (!se || !se.c) { msg(`The state&rsquo;s file gives no ${esc(W[0])} figures for this race.`); return; }
    const L0 = linesUS(r, E(r.id)), heads = L0.lines.filter(x => !x.wl).slice(0, 4);
    const rows = Object.entries(se.c).map(([c, ce]) => ({c, name: (cty && cty.n && cty.n[c]) || c, L: linesUS(r, cEntry(se, ce)), u: ce.u}));
    const val = (o, x) => (o.L.lines.find(y => y.i === x.i) || {}).votes || 0;
    gridTable(host, {rows, page: 100, sort: [{key: "n", dir: "asc"}], rowId: o => o.c,
      cols: [{key: "n", label: capital(W[0]), val: o => o.name, html: o => esc(o.name)}]
        .concat(heads.map(x => ({key: "c" + x.i, label: x.name, num: true, val: o => val(o, x), html: o => o.L.total ? `${num(val(o, x))} <small class="muted">${pct(val(o, x), o.L.total)}</small>` : ""})))
        .concat([{key: "t", label: "All votes", num: true, val: o => o.L.total, html: o => num(o.L.total)},
          {key: "s", label: "Reported", num: true, val: o => o.u && o.u[1] ? o.u[0] / o.u[1] : null, html: o => o.u && o.u[1] ? `${num(o.u[0])} of ${num(o.u[1])}` : ""}]),
      count: rs => plural(rs.length, W[0], W[1])});
  }, () => msg(`The ${esc(W[0])} figures could not be loaded just now.`));
}

/* ---------- the address, and new figures ---------- */
function route(keep) {
  if (mapOff) { mapOff.abort(); mapOff = null; }
  const y = scrollY, h = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (h.startsWith("state=")) statePage(h.slice(6).toUpperCase().replace(/[^A-Z]/g, "").slice(0, 2));
  else if (h.startsWith("race=")) racePage(h.slice(5));
  else { const v = {senate: "senate", governors: "governor", governor: "governor", house: "house", counted: "counted"}[h]; if (v && !keep) { VIEW = v; US_SEL = null; } home(keep ? "" : h); }
  if (keep) window.scrollTo(0, y);
  else { if (!/^(mine|yours|states|senate|governors|governor|house|counted|map)$/.test(h)) window.scrollTo(0, 0); try { app.focus({preventScroll: true}); } catch (e) {} }
}
function newFigures() {
  SFILE = {};
  const h = location.hash;
  if (/^#race=/.test(h)) { const n = $("#newfig"); if (n) { n.innerHTML = `<div class="newbar" role="status">New figures are ready: <button type="button" id="nshow">show them</button></div>`; $("#nshow").addEventListener("click", () => route()); } }
  else route(true);
}
if (LIVE.rehearsal) { const b = $("#nreh"); if (b) b.hidden = false; }
Promise.all([getJSON(BOOT.data), getJSON(BOOT.map), isPreview() ? null : liveFetch("us.json")]).then(([d, m]) => {
  D = d; MAPD = m; index(); liveReady(liveRaces); MINE = readMine();
  if (LIVE.rehearsal) { const b = $("#nreh"); if (b) b.innerHTML = `<b>Rehearsal:</b> replayed figures from ${esc((LIVE.now && LIVE.now.label) || "a past election")}. Not 2026 results.`; }
  route();
  addEventListener("hashchange", () => route());
  document.addEventListener("night:look", () => route(true));
  NIGHTLIVE.start({get: () => liveGet("us.json"), onNew: newFigures, onTick: refreshStatus});
}, () => { app.innerHTML = `<p class="nempty">The races could not be loaded. Check your connection and open the page again.</p>`; });
"""


def page_html(P, boot, practice, generated, version, links):
    nav = "".join(f'<a href="{h}"{c}>{w}</a>' for h, w, c in (("#map", "Map", ' class="x"'), ("#senate", "Senate", ""), ("#governors", "Governors", ""),
                                                               ("#house", "House", ' class="x"'), ("#states", "Every state", ""), ("#mine", "Your ballot", "")))
    foot = " &middot; ".join(x for x in (
        f'<a href="{links["night"]}">Election Night</a>',
        f'<a href="{links["night"]}mn/">Minnesota at every level</a>' if links.get("mn") else "",
        f'<a href="{links["ballot"]}us/">On The Ballot: Congress</a>',
        f'<a href="{links["front"]}">The Civic Archive front door</a>') if x)
    desc = ("Every state's races for Congress, governor and the other statewide offices on election night, counted as each "
            "state's own election office posts the figures, each with its time.")
    page = PAGE
    for key, value in (("__CSS__", P["CSS"]), ("__BALLOT_CSS__", P["BALLOT_CSS"]), ("__NIGHT_CSS__", N.NIGHT_CSS), ("__FONTS__", N.fonts_css()),
                       ("__HEADSCRIPT__", N.head_script()), ("__CHANGELOG__", P["CHANGELOG"]), ("__GRID__", P["GRID"]), ("__SOURCEFOLD__", P["SOURCEFOLD"]),
                       ("__GEO__", P["GEO"]), ("__NIGHT_JS__", N.NIGHT_JS), ("__NIGHTMAP_JS__", N.NIGHTMAP_JS), ("__USMAP_JS__", N.USMAP_JS),
                       ("__USMAP_CSS__", N.USMAP_CSS), ("__PAGE_JS__", PAGE_JS),
                       ("__TOPBAR__", N.top_bar("Election Night: results across the country", nav, door_href=links["night"])),
                       ("__CLBOX__", N.changelog_box()),
                       ("__BANNER__", f'<div class="nbanner" role="note"><b>{PRACTICE_LABEL.split(".")[0]}.</b> Not 2026 results.</div>\n' if practice else ""),
                       ("__BRAND__", N.brand_tags(links["icons"], "Election Night: results across the country · The Civic Archive", desc, "results.png", "night/us/")),
                       ("__FOOTLINKS__", foot)):
        if page.count(key) != 1:
            raise SystemExit(f"build_night_us: the page should hold {key} exactly once (it holds it {page.count(key)} times)")
        page = page.replace(key, value)
    page = page.replace("__DESC__", esc(desc)).replace("__VERSION__", esc(version)).replace("__GENERATED__", generated)
    return page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


RIDER = '<script type="module" src="../../shell/rider.js" data-tca-rider></script>\n'


def build(dev_root, version=None, practice=None, say=print):
    """The US page (and, with practice, its practice figures). Returns {path written: bytes}."""
    from build_ballot_state_dev import copy_fonts, slim_page, write_if_changed
    from build_site_dev import read_changelog
    from build_state_dev import borrow
    from election.livejson import BUDGET
    dev_root = os.path.abspath(dev_root)
    changelog = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = version or ((changelog[0].get("version") if changelog else "") or "")
    if practice:
        root = N.practice_root(dev_root)
        out_dir = os.path.join(root, "night", "us")
        links = {"night": "../../../dev/night/", "ballot": "../../../dev/ballot/", "front": "../../../dev/", "icons": "../../../dev/"}
        live = "../../night-live/"
    else:
        out_dir = os.path.join(dev_root, "night", "us")
        links = {"night": "../", "ballot": "../../ballot/", "front": "../../", "icons": "../../"}
        live = "../../../night-live/"
    links["mn"] = os.path.exists(os.path.join(dev_root, "night", "mn", "index.html"))
    say(f"Election Night, across the country{' (practice)' if practice else ''}: building {os.path.relpath(out_dir, HERE)}")
    if not os.path.exists(os.path.join(dev_root, "ballot", "us", "data", "districts.json")):
        say("  WARNING: the Congress ballot page's district lines (ballot/us/data/districts.json) are not built yet; the House is drawn by state "
            "until they are")
    fed, sw = all_races(say)
    races = fed + sw
    with open(POLL_HOURS, encoding="utf-8") as fh:
        polls = json.load(fh)
    ncounties = county_counts()
    states = states_meta(dev_root, races, polls, ncounties)
    mp = map_doc()
    written = {}
    ccodes = county_codes(states)
    cw, cinfo = county_files(out_dir, ccodes, mp["b"], say)
    written.update(cw)
    for code in cinfo.get("keys", {}):
        states[code]["cf"] = 1
    changed = []
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    try:
        changed = sorted(st for (st,) in con.execute("SELECT state FROM state_notes WHERE lines_changed = 1"))
    finally:
        con.close()
    sources = {"maps": [
        {"agency": "U.S. Census Bureau, through the us-atlas project", "title": "State outlines (public domain), in the Albers projection every map of this site uses",
         "url": "https://github.com/topojson/us-atlas"},
        {"agency": "U.S. Census Bureau", "title": "Cartographic boundary file, counties, 1:500,000 (2024)" + (f"; SHA-256 {cinfo['sha'][:16]}..." if cinfo.get("sha") else ""),
         "url": COUNTY_URL}]}
    certs = set()
    from election import registry
    for code in registry.STATES:
        src = str(((registry.load(code) or {}).get("certify") or {}).get("source") or "")
        m = re.search(r"www\.ncsl\.org/elections-and-campaigns/certification-deadlines", src)
        if m:
            certs.add("https://" + m.group(0))
    if certs:
        sources["cert"] = sorted(certs)[0]
    doc = {"generated": dt.date.today().isoformat(), "election": GENERAL, "races": races, "states": states,
           "lines": {"changed": changed, "vintage": districts_vintage(dev_root)}, "sources": sources}
    races_text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    bad = N.kit_names(races_text)
    if bad:
        raise SystemExit(f"build_night_us: the races file would name the kit's own files: {bad}")
    write_if_changed(os.path.join(out_dir, "data", "races.json"), races_text)
    written[os.path.join(out_dir, "data", "races.json")] = len(races_text.encode("utf-8"))
    map_text = json.dumps(mp, ensure_ascii=False, separators=(",", ":"))
    write_if_changed(os.path.join(out_dir, "data", "map.json"), map_text)
    written[os.path.join(out_dir, "data", "map.json")] = len(map_text.encode("utf-8"))
    copy_fonts(out_dir)
    boot = {"data": f"data/races.json?v={sha10(races_text)}", "map": f"data/map.json?v={sha10(map_text)}", "ckeys": cinfo.get("keys", {}),
            "live": {"base": live, "dir": ""}, "changelog": changelog,
            "links": {"night": links["night"], "ballot": links["ballot"], "counties": "data/counties/", "nass": NASS,
                      "districts": links["ballot"] + "us/data/districts.json"}}
    practice_note = None
    if practice:
        sizes, psources, seq = practice_figures(races, states, polls, os.path.join(N.practice_root(dev_root), "night-live"), say)
        boot["practice"] = {"label": PRACTICE_LABEL, "now": PRACTICE_NOW,
                            "sources": [{"state": s["state"], "agency": s["agency"], "title": s["title"], "url": s["url"], "read": s["read"]} for s in psources]}
        for k, v in sizes.items():
            written[os.path.join(N.practice_root(dev_root), "night-live", *(["s", f"{seq:06d}"] if k != "now.json" else []), k)] = v
        practice_note = sizes
    P = N.parts()
    P["GEO"] = borrow("GEO")
    page = page_html(P, boot, practice, N.generated(), version, links)
    whole = len(page.encode("utf-8"))
    page = slim_page(page, "Election Night US")
    page = N.quiet(page)
    checks = N.page_checks("night/us/index.html", page, SHELL_LIMIT, say)
    if not practice and os.path.exists(os.path.join(dev_root, "shell", "rider.js")):
        i = page.rfind("</body>")
        page = page[:i] + RIDER + page[i:]      # the companion and the page guide, as build_shell.ride() puts them on every page with its own top bar
    write_if_changed(os.path.join(out_dir, "index.html"), page)
    written[os.path.join(out_dir, "index.html")] = len(page.encode("utf-8"))
    ctotal = sum(v for k, v in written.items() if os.sep + "counties" + os.sep in k)
    largest = us_file_at_largest([r for r in races if states.get(r["st"], {}).get("s") != "link"])      # a state only linked to never sends figures
    every = us_file_at_largest(races)
    say(f"  {len(fed)} races for Congress and {len(sw)} statewide offices in {len({r['st'] for r in sw})} states "
        f"({sum(len(r['cs']) for r in races):,} candidates on the lists; {sum(1 for r in races if r.get('nl'))} races whose list is not loaded)")
    say(f"  wrote index.html {checks['bytes'] / 1e3:,.0f} KB ({whole / 1e3:,.0f} KB before slimming; budget {SHELL_LIMIT / 1e3:,.0f} KB), "
        f"data/races.json {written[os.path.join(out_dir, 'data', 'races.json')] / 1e3:,.0f} KB (budget {DATA_LIMIT / 1e3:,.0f}), "
        f"data/map.json {written[os.path.join(out_dir, 'data', 'map.json')] / 1e3:,.0f} KB, county lines for {len(cinfo.get('keys', {}))} states "
        f"{ctotal / 1e3:,.0f} KB (budget {COUNTIES_LIMIT / 1e3:,.0f})")
    say(f"  us.json with every race of the states read counted would be {largest / 1e3:,.0f} KB, and with every state's {every / 1e3:,.0f} KB "
        f"(budget {BUDGET['us'] / 1e3:,.0f} KB)")
    for what, n, limit in (("data/races.json", written[os.path.join(out_dir, "data", "races.json")], DATA_LIMIT), ("the county lines", ctotal, COUNTIES_LIMIT),
                           ("us.json at its largest", largest, BUDGET["us"])):
        if n > limit:
            say(f"  WARNING: {what} is {n / 1e3:,.0f} KB, over its {limit / 1e3:,.0f} KB budget")
    rules = {c: s["rl"] for c, s in states.items() if s.get("rl")}
    if rules:
        say("  decision rules read from the registry (not plurality): " + "; ".join(f"{c} {v}" for c, v in sorted(rules.items())))
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's root (default site/dev)")
    ap.add_argument("--practice", action="store_true", help="practice figures, into site/practice/ (never published)")
    a = ap.parse_args()
    build(a.root, practice="2024" if a.practice else None)


if __name__ == "__main__":
    main()
