#!/usr/bin/env python3
"""
build_night_state.py - Election Night, one state at every level (Minnesota first): site/dev/night/<code>/.

    python build_night_state.py                       (Minnesota, into site/dev/night/mn/)
    python build_night_state.py --practice            (the same page with practice figures, into site/practice/; never published)
    python build_night_state.py --state mn --root site/dev

The page shows the official count of every race on the state's November 3 ballot, as the state's election office posts
it, each figure with its time: statewide offices and Congress, the Legislature, the courts, and every county, city,
township, school, hospital and other district. Routes (after #):
  ""                 home: the state of the count, your own ballot's results, the map, the top of the ballot, every level
  #statewide         the offices the whole state elects, and Congress
  #legislature       every Senate and House district, sortable, with a map of who is ahead in each
  #courts            the Supreme Court, the Court of Appeals and the district courts
  #county=053        every contest reaching a county, grouped by place
  #race=<race id>    one contest: its count, the map of its precincts, the figures of every precinct or county
  #map=<layer>:<id>  the home page with that shape on the map
  #mine              your own ballot's results (Use my location finds your precinct on this device)

What it writes: index.html (the shell), data/races.json (every race: id, level, office, place, counties, district,
partisan or not, the shape that draws it on the map, and its candidates as filed, in ballot order; nothing else from
the lists), mapkit.js (the ballot map, taken from the ballot pages by landmark, with Election Night's results kit) and
fonts/. The map's own files (the precinct and district lines) are not copied: the page fetches them from the ballot
page's folder (../../ballot/<code>/geo/), so the ballot page must be built first.

It reads build_ballot_state_dev.build() for the state and local races (read-only; it never writes the ballot
database), ballot_2026.sqlite read-only for the state's races for Congress, and, where they exist, the state's
registry and poll hours under election/. The live figures are not part of the page: the page reads them from the live
site (/night-live/, written by the updater), as night_common.py's account of their files says.

--practice writes the same page to site/practice/night/<code>/ and practice figures to site/practice/night-live/: the
2024 general election's official precinct results (the Secretary of State's own tables on the Minnesota Geospatial
Commons, already on disk) replayed onto this year's races, part of the state reported. Every practice page says so at
the top: "Practice: figures built from 2024's official results. Not 2026 results." No publish script copies site/practice/.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import night_common as N                                                  # noqa: E402
from states.places import place                                           # noqa: E402

FED_DB = os.path.join(HERE, "ballot_2026.sqlite")
GENERAL = "2026-11-03"
RIDER = '<script type="module" src="../../shell/rider.js" data-tca-rider></script>\n'
SHELL_LIMIT = 380_000          # the page's own shell (index.html); the races, the map and the figures are files of their own
COUNTY_FILE_BUDGET = 150_000   # a county's precinct rows (ARCHITECTURE.md 2.6)
STATE_FILE_BUDGET = 800_000    # a state's figures

# What the page says about each state that is not in the ballot databases, each with where it was read. Only a state
# named here gets a page.
STATES = {
    "MN": {
        "agency": "Minnesota Secretary of State",
        "results": "https://electionresults.sos.mn.gov/",      # the state's own results: linked, never requested
        "finder": "https://pollfinder.sos.mn.gov/",            # the state's own polling place finder: linked, never requested
        "polls": {"date": GENERAL, "open": "07:00", "close": "20:00", "tz": "America/Chicago"},
        "polls_note": "Polls are open from 7 a.m. to 8 p.m. A few small towns and unorganized areas may open as late as 10 a.m.",
        "cert": {"state": "2026-11-19", "county_from": "2026-11-06", "county_to": "2026-11-11"},
        "rules": [
            {"agency": "Minnesota Legislature, Office of the Revisor of Statutes", "title": "Minnesota Statutes, section 204C.05: hours for voting",
             "url": "https://www.revisor.mn.gov/statutes/cite/204C.05", "read": "2026-10-10", "kind": "statute"},
            {"agency": "Minnesota Legislature, Office of the Revisor of Statutes", "title": "Minnesota Statutes, section 204C.33: the county and state canvass",
             "url": "https://www.revisor.mn.gov/statutes/cite/204C.33", "read": "2026-10-10", "kind": "statute"}],
        "hand": True,
        "unit": "precinct",
        "tz": "America/Chicago",
    },
}

PRACTICE_LABEL = "Practice: figures built from 2024's official results. Not 2026 results."
PRACTICE_SOURCE = os.path.join(HERE, "states_cache", "mn_local", "sos_electionresults_2024.json")
PRACTICE_AT = "2026-11-04T03:42:00Z"       # 9:42 p.m. Central on election night: the time the practice figures are said to be from
PRACTICE_SAVED = "2026-11-04T03:44:00Z"
PRACTICE_NOW = "2026-11-04T03:52:00Z"


# ============================================================ the races

def surname(name):
    first = re.split(r"\s+(?:and|&|/)\s+", str(name), flags=re.I)[0]
    first = re.sub(r",?\s+(?:Jr\.?|Sr\.?|II|III|IV)$", "", first, flags=re.I).strip()
    return first.split()[-1].lower() if first.split() else ""


def in_order(cands):
    """The ballot order where the list gives one, then by surname: the order the ballot pages show, and the order every
    figure in the live files follows."""
    return sorted(cands, key=lambda c: (c.get("o") if isinstance(c.get("o"), int) else 10 ** 9, surname(c["n"]), c["n"]))


def seats_of(note):
    m = re.search(r"\bVoters choose (\d+)\b", str(note or ""))
    return int(m.group(1)) if m else 1


def congress_races(code):
    """The state's races for Congress, from the Congress ballot database (read-only): name as filed and party only."""
    if not os.path.exists(FED_DB):
        return []
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    out = []
    try:
        rows = con.execute("SELECT race_id, office, district, special FROM races WHERE state = ? AND level = 'federal' ORDER BY office DESC, race_id",
                           (code,)).fetchall()
        for rid, office, district, special in rows:
            cands = [{"n": n, "p": p or "", "pc": (pc or "O").upper(), "o": o, "wi": wi}
                     for n, p, pc, o, wi in con.execute("SELECT name, party, party_code, ballot_order, write_in FROM candidates WHERE race_id = ? AND election = 'general'",
                                                        (rid,))]
            senate = office == "U.S. Senate"
            d = str(int(district)) if district and str(district).isdigit() else (district or None)
            r = {"id": rid, "lv": "federal", "k": "us_senate" if senate else "us_house", "o": "U.S. Senator" if senate else "U.S. Representative",
                 "j": "" if senate else f"Congressional District {d}", "pt": 1, "g": f"state:{code}" if senate else f"cd:{d}"}
            if d and not senate:
                r["d"] = d
            if special:
                r["sp"] = 1
            r["cs"] = [[c["n"], c["p"], c["pc"] if c["pc"] in ("D", "R", "I", "L", "G", "O", "W") else "O"] + ([1] if c["wi"] else [])
                       for c in in_order(cands)]
            out.append(r)
    finally:
        con.close()
    return out


def races_for(code, say=print):
    """Every race of the state, as the page and the live files see them, with the state and local lists' own words.
    Returns (races.json as a dict, the map files from the ballot builder, the ballot page's words for the state)."""
    import build_ballot_state_dev as B
    data, st, warn, n_cand, X = B.build(B.DB, code, B.lines_for(code), None)
    races = []
    for r in data["races"]:
        out = {"id": r["id"], "lv": r["lv"], "k": r["k"], "o": r["o"]}
        for k in ("j", "c", "d", "s", "g", "gp"):
            if r.get(k):
                out[k] = r[k]
        if r.get("sp"):
            out["sp"] = 1
        out["pt"] = 1 if r.get("pt") else 0
        n = seats_of(r.get("note"))
        if n > 1:
            out["n"] = n
        cs = []
        for c in in_order(r["el"].get("general", [])):
            if out["pt"]:
                cs.append([c["n"], c.get("p") or "", c.get("pc") or "O"] + ([1] if c.get("wi") else []))
            else:
                cs.append([c["n"]] + (["", "N", 1] if c.get("wi") else []))
        out["cs"] = cs
        races.append(out)
    fed = congress_races(code)
    srcs = [{k: s.get(k) for k in ("kind", "agency", "title", "url", "fetched") if s.get(k)} for s in data["sources"].values()
            if str(s.get("kind") or "").startswith("official candidate list") and s.get("agency")]
    doc = {"generated": dt.date.today().isoformat(), "election": GENERAL, "state": code, "counties": data["counties"],
           "pshort": data.get("pshort") or {}, "races": fed + races, "sources": srcs}
    say(f"  {len(fed)} races for Congress and {len(races):,} state and local races ({sum(len(r['cs']) for r in fed + races):,} candidates on the lists)")
    return doc, X["geo"], st


# ============================================================ what the page knows about the state

def registry_words(code):
    """How the state counts, in its registry's own words for readers (election/registry/<code>.json, "how_counted"): one
    plain sentence or two, or nothing. Fields written for the updater (the count order it learns, its plans) are not read."""
    path = os.path.join(HERE, "election", "registry", f"{code.lower()}.json")
    try:
        v = json.load(open(path, encoding="utf-8")).get("how_counted")
    except (OSError, ValueError, AttributeError):
        return ""
    if isinstance(v, str) and 20 < len(v) < 400 and not N.kit_names(v) and not re.search(r"https?://|\bwww\.|\b\w+_\w+\b", v):
        return v.strip()
    return ""


def poll_hours(code, base):
    """The state's poll hours from the poll hours file (election/poll_hours.json: a state's zones, each with its opening and
    closing time and its time zone, and its official polling place lookup), where its entry for the state is well formed
    and has one zone for the whole state; else what is set out in STATES. Only times of the form HH:MM, known time zones
    and https addresses are taken from the file, and the sentence about voters in line when polls close."""
    P = dict(base["polls"])
    P["finder"] = base.get("finder")
    path = os.path.join(HERE, "election", "poll_hours.json")
    try:
        doc = json.load(open(path, encoding="utf-8"))
        e = (doc.get("states") or {}).get(code)
    except (OSError, ValueError, AttributeError):
        return P
    if not isinstance(e, dict):
        return P
    zones = [z for z in e.get("zones") or [] if isinstance(z, dict)]
    if len(zones) == 1 and all(re.fullmatch(r"\d\d:\d\d", str(zones[0].get(k) or "")) for k in ("opens", "closes")) \
            and re.fullmatch(r"[A-Za-z]+/[A-Za-z_]+", str(zones[0].get("tz") or "")):
        P.update({"open": zones[0]["opens"], "close": zones[0]["closes"], "tz": zones[0]["tz"]})
    look = e.get("lookup")
    url = look.get("url") if isinstance(look, dict) else look
    if isinstance(url, str) and url.startswith("https://"):
        P["finder"] = url
    line = e.get("in_line")
    if isinstance(line, str) and 10 < len(line) < 200 and not re.search(r"https?://|\b\w+_\w+\b", line):
        P["line"] = line.strip()
    return P


def ballot_geo(dev_root, code, geo):
    """What the page needs to fetch the ballot page's map files: their folder's cache key (the ballot page's own, read from
    its built shell, so both pages share the browser's copies) and what the files call their parts."""
    lc = code.lower()
    page = os.path.join(dev_root, "ballot", lc, "index.html")
    g = None
    if os.path.exists(page):
        text = open(page, encoding="utf-8").read()
        m = re.search(r"const BOOT\s*=\s*", text)
        if m:
            try:
                g = (json.JSONDecoder().raw_decode(text, m.end())[0] or {}).get("geo")
            except ValueError:
                g = None
    if not os.path.exists(os.path.join(dev_root, "ballot", lc, "geo", "index.json")):
        raise SystemExit(f"build_night_state: the map's files are fetched from the ballot page's folder, and {os.path.join('ballot', lc, 'geo')} "
                         f"has no index.json under {dev_root}. Build {code}'s ballot page first.")
    if not g:      # no built shell to read: a key of the files' own
        h = hashlib.sha1()
        for rel in ("index.json", "reader.js"):
            h.update(open(os.path.join(dev_root, "ballot", lc, "geo", rel), "rb").read())
        g = {"v": h.hexdigest()[:10], "kinds": [L["kind"] for L in (geo or {}).get("index", {}).get("layers", []) if L["kind"] != "state"]}
    return {k: g[k] for k in ("v", "kinds", "unit", "words", "ck") if g.get(k)}


# ============================================================ practice figures

def _h(*parts):
    return int(hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def _whole(shares, total):
    """Whole votes that add up to round(total), by largest remainders."""
    total = int(round(total))
    s = sum(shares) or 1.0
    raw = [total * x / s for x in shares]
    out = [int(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[:total - sum(out)]:
        out[i] += 1
    return out


ROLL = {"federal": .985, "statewide": .975, "legislature": .94, "court": .72, "county": .82, "soil_water": .62, "city": .86,
        "township": .8, "school": .78, "hospital": .7, "other": .7}


def practice_figures(code, doc, geo, live_root, say=print):
    """Practice figures in the live files' own layout: the 2024 general election's official precinct results (the
    Secretary of State's tables on the Minnesota Geospatial Commons) replayed onto this year's races. Each precinct's
    turnout and the parties' shares are its 2024 presidential vote; a partisan candidate takes their party's share; a
    nonpartisan race's shares are made up, the same on every build; write-ins are a small fixed share. Some counties have
    reported every precinct, some none, the rest part, so that the page shows each case. Returns a summary."""
    lc = code.lower()
    src = json.load(open(PRACTICE_SOURCE, encoding="utf-8"))
    past = {}
    for row in src["rows"]:
        tot = int(row.get("usprstotal") or 0)
        if tot > 0:
            past[str(row["vtdid"])] = (tot, int(row.get("usprsdfl") or 0) / tot, int(row.get("usprsr") or 0) / tot)
    precincts, by_county = {}, defaultdict(list)
    for c in geo["index"]["counties"]:
        f = json.load(open(os.path.join(geo["root"], c["file"]), encoding="utf-8"))
        for g in f["objects"]["precincts"]["geometries"]:
            p = g.get("properties") or {}
            precincts[g["id"]] = p
            by_county[str(p.get("county") or c["id"])].append(g["id"])
    # a precinct the 2024 tables do not have (redrawn since): its county's middle turnout and shares
    county_mid = {}
    for cty, ids in by_county.items():
        got = sorted(past[i] for i in ids if i in past)
        county_mid[cty] = got[len(got) // 2] if got else (500, .5, .45)
    base = {pid: past.get(pid) or county_mid[str(p.get("county"))] for pid, p in precincts.items()}
    # which precincts are in: a county's share, some none and some all
    progress = {}
    for cty in by_county:
        q = _h("progress", cty)
        progress[cty] = 0.0 if q < .12 else 1.0 if q > .86 else .25 + (q - .12) / .74 * .7
    reported = {pid for pid, p in precincts.items() if _h("in", pid) < progress[str(p.get("county"))]}
    # each kind of shape: the precincts it holds
    area = defaultdict(lambda: defaultdict(list))
    for pid, p in precincts.items():
        for kind in ("county", "com", "park", "house", "senate", "cd", "judicial", "swcd", "hospital"):
            v = p.get(kind)
            for x in (v if isinstance(v, list) else [v]):
                if x not in (None, ""):
                    area[kind][str(x)].append(pid)
        for x in set([p.get("mcd")] + list(p.get("mcd_all") or [])):
            if x:
                area["mcd"][str(x)].append(pid)
        for x in p.get("ward") or []:
            area["ward"][str(x)].append(pid)
        for x in p.get("school") or []:
            area["school"][str(x)].append(pid)
    every = sorted(precincts)

    def votes(r, pid):
        T, sd, sr = base[pid]
        n, cs = r.get("n", 1), r["cs"]
        ballots = T * ROLL.get(r["lv"], .75) * (.96 + .08 * _h("t", r["id"], pid))
        if r["pt"]:
            so = max(.01, 1 - sd - sr)
            ws = []
            for i, c in enumerate(cs):
                pc = c[2] if len(c) > 2 else "O"
                ws.append(sd if pc == "D" else sr if pc == "R" else so * (.3 + .7 * _h("o", r["id"], i)))
            if len(cs) == 1:
                ws = [.78]
            named = _whole(ws, ballots * .985 * (1 if len(cs) > 1 else .8))
        else:
            if len(cs) <= n:
                named = [int(round(ballots * (.8 + .12 * _h("u", r["id"], pid, i)))) for i in range(len(cs))]
            else:
                ws = [(.5 + _h("w", r["id"], i)) * (.75 + .5 * _h("j", r["id"], pid, i)) for i in range(len(cs))]
                named = _whole(ws, ballots * n * .86)
        return named + [int(round(ballots * .004 * n * (.5 + _h("x", r["id"], pid))))]

    from election import store
    fips = str(place(code).get("fips") or "")
    level = {r["id"]: r["lv"] for r in doc["races"]}

    def assemble(reported):
        """The state's file in its long form and each county's precinct rows ({county: {race: {precinct: votes}}}), with
        the precincts in `reported` in. The store's layout (election/store.py page_json and county_json): the list's
        candidates as the file's lines, in ballot order, each with its name as filed, and the write-in line last."""
        state_r, rows = {}, defaultdict(lambda: defaultdict(dict))
        for r in doc["races"]:
            if not r.get("g") or not r["cs"]:
                continue
            kind, _, sid = r["g"].partition(":")
            pids = every if kind == "state" else area.get(kind, {}).get(sid, [])
            if not pids:
                continue
            n = len(r["cs"])
            ch = [[store.slug(c[0]), c[0], (c[1] or None) if r["pt"] else None, 0, c[0]] for c in r["cs"]] + [["write-in", "WRITE-IN", None, 1, None]]
            v, inn, cty = [0] * (n + 1), 0, {}
            for pid in pids:
                c = str(precincts[pid].get("county"))
                ce = cty.setdefault(c, {"p": [0, 0], "v": [0] * (n + 1)})
                ce["p"][1] += 1
                if pid in reported:
                    row = votes(r, pid)
                    inn += 1
                    ce["p"][0] += 1
                    for i, x in enumerate(row):
                        v[i] += x
                        ce["v"][i] += x
                    rows[c][r["id"]][pid] = row
            e = {"t": PRACTICE_SAVED, "p": [inn, len(pids)], "ch": ch, "v": v}
            if len(cty) > 1:
                e["k"] = {fips + c: ce for c, ce in sorted(cty.items())}
            state_r[r["id"]] = e
        long = {"v": N.FORMAT_VERSION, "state": code, "at": PRACTICE_SAVED, "r": state_r, "practice": PRACTICE_LABEL}
        return long, rows

    def files_of(long, rows):
        """{file name in the snapshot folder: its text}, as published: the state's file written short, and both files of
        every county, even one none of whose precincts is in yet."""
        short = store.compact_page(long)
        problems = N.check_state_live(short, {r["id"]: [c[0] for c in r["cs"]] for r in doc["races"]})
        if problems:
            raise SystemExit("build_night_state: the practice figures do not fit the live files' account: " + "; ".join(problems[:5]))
        if store.expand_page(short) != long:
            raise SystemExit("build_night_state: the state's file written short does not read back whole")
        out = {f"{lc}.json": json.dumps(short, ensure_ascii=False, separators=(",", ":"))}
        lines = {rid: len(e["ch"]) for rid, e in long["r"].items()}
        for c in sorted(by_county):
            for part in store.COUNTY_PARTS:
                got = {rid: us for rid, us in rows.get(c, {}).items() if store.county_part(level[rid]) == part}
                body = store.encode_county(fips + c, part, PRACTICE_SAVED, sorted(by_county[c]), got)
                bad = N.check_county_live(body, lines, level)
                if bad or store.county_rows(body, lines) != got:
                    raise SystemExit(f"build_night_state: the practice figures for county {c} do not fit the live files' account: " + "; ".join(bad[:5] or ["they do not read back whole"]))
                out[store.county_file(code, fips + c, part)] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        return out

    long, rows = assemble(reported)
    # the practice snapshot folder the other practice builds use (night_common.practice_base), and now.json merged with
    # theirs: this build changes only its own state's entry, so the US page's practice states stay
    _seq, snap_base, snap, _old = N.practice_base(live_root)
    sizes = {name: N_write(os.path.join(snap, *name.split("/")), text) for name, text in files_of(long, rows).items()}
    sizes["now.json"] = N.practice_now(live_root, {code: {"s": "counting", "t": PRACTICE_AT, "f": f"{lc}.json", "by": "hand"}},
                                       "2026-11-04T03:50:00Z", "2026-11-04T04:00:00Z", PRACTICE_LABEL, say)
    # its races for Congress and its statewide offices go into the practice us.json too, as the updater's us.json carries them
    us_lv = {r["id"] for r in doc["races"] if r.get("lv") in N.US_LEVELS}
    sizes["us.json"] = N.practice_us_merge(live_root, {rid: e for rid, e in long["r"].items() if rid in us_lv})
    sizes["_base"] = snap_base
    # the files at their largest, every precinct in (measured, not written): the budgets must hold at the end of the night
    full = {name: len(text.encode("utf-8")) for name, text in files_of(*assemble(set(precincts))).items()}
    units = [len(reported), len(precincts)]
    for label, sz in (("now", {k: v for k, v in sizes.items() if k != "_base"}), ("with every precinct in", full)):
        cs = sorted((v, k) for k, v in sz.items() if "/c/" in k)
        say(f"  {'practice figures: ' + format(units[0], ',') + ' of ' + format(units[1], ',') + ' precincts in; ' + format(len(long['r']), ',') + ' races; ' if label == 'now' else ''}"
            f"{label}: state file {sz[f'{lc}.json'] / 1e3:,.0f} KB (budget {STATE_FILE_BUDGET / 1e3:,.0f}), county files {cs[0][0] / 1e3:,.0f} to {cs[-1][0] / 1e3:,.0f} KB "
            f"(largest {cs[-1][1]}; budget {COUNTY_FILE_BUDGET / 1e3:,.0f})")
        over = [(k, v) for v, k in cs if v > COUNTY_FILE_BUDGET] + ([(f"{lc}.json", sz[f"{lc}.json"])] if sz[f"{lc}.json"] > STATE_FILE_BUDGET else [])
        if over:
            say(f"  WARNING: {len(over)} file(s) over budget {label}: " + ", ".join(f"{k} {v / 1e3:,.0f} KB" for k, v in over))
    say(f"  {sum(1 for c in progress.values() if c == 0)} counties with none in, {sum(1 for c in progress.values() if c == 1)} with all in")
    return {"units": units, "races": len(long["r"]), "sizes": sizes, "full": full}


def N_write(path, text):
    """Writes a text file (only when it changed) and returns its size in bytes."""
    from build_ballot_state_dev import write_if_changed
    write_if_changed(path, text)
    return len(text.encode("utf-8"))


# ============================================================ the page

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Election Night: __NAME__ · The Civic Archive</title>
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
.seg2{display:inline-flex;border:1px solid var(--line-strong);border-radius:999px;padding:3px;gap:2px;background:var(--surface);flex-wrap:wrap}
.seg2 button{all:unset;cursor:pointer;font:600 13px var(--sans);padding:7px 13px;border-radius:999px;color:var(--muted);min-height:30px}
.seg2 button[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
.seg2 button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (max-width:860px){.nmapgrid{grid-template-columns:1fr}}
.where2{font-size:14px;color:var(--muted);margin:6px 0 0}
.mybar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0 0}
@media (max-width:640px){.mybar .pick{width:100%}}
.nempty{border:1px dashed var(--line-strong);border-radius:14px;padding:12px 14px;color:var(--muted);font-size:14px;margin-top:12px}
</style>
</head>
<body>
__BANNER__<div class="nbanner" id="nreh" hidden></div>
<div class="draftnote">A draft for feedback, not the finished site. <a href="https://thecivicarchive.github.io/">Go to the live site</a></div>
__TOPBAR__
<main id="app" class="bwrap" tabindex="-1"><p class="loading muted">Loading __NAME__&rsquo;s races&hellip;</p></main>
<footer class="bwrap bfoot">
  <p>Election Night, from The Civic Archive v__VERSION__. Generated on __GENERATED__. Every figure is an official count as __AGENCY__ posts it, with its time; the state&rsquo;s own results are the authority.</p>
  <p>__FOOTLINKS__</p>
</footer>
__CLBOX__
<script>
const BOOT = __BOOT__;
const CODE = BOOT.st.code;
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
/* ===== parts shared with the rest of the site (taken from their pages when this page is built) ===== */
__CHANGELOG__
__GRID__
__SOURCEFOLD__
/* ===== end of the shared parts ===== */
__NIGHT_JS__
__PAGE_JS__
</script>
</body>
</html>
"""

PAGE_JS = r"""
/* ---------- one state's results at every level ---------- */
const ST = BOOT.st, NM = esc(ST.name), UNIT = ST.unit || "precinct", app = $("#app");
let D = null, R = {}, LEGR = {house: {}, senate: {}}, MAP = null, SPEC = null, IDX = null, kitP = null, idxP = null, MINE = null, LASTPICK = null, TABLES = [];
const MKEY = "night:" + ST.lc;
const getJSON = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
const addScript = src => new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => no(new Error(src)); document.head.appendChild(s); });
const needKit = () => kitP || (kitP = addScript(BOOT.geo.base + "reader.js?v=" + BOOT.geo.v).then(() => addScript(BOOT.kit)).catch(e => { kitP = null; throw e; }));
const needIdx = () => IDX ? Promise.resolve(IDX) : (idxP || (idxP = getJSON(BOOT.geo.base + "index.json?v=" + BOOT.geo.v).then(d => (IDX = d), e => { idxP = null; throw e; })));
const isPreview = () => /^(127\.0\.0\.1|localhost)$/.test(location.hostname) && location.port === "8790";

/* ---------- words ---------- */
const LV = {federal: "Congress", statewide: "Statewide offices", legislature: "The Legislature", court: "Judges", county: "County offices",
  soil_water: "Soil and water conservation", city: "Cities", township: "Townships", school: "School districts", hospital: "Hospital districts", other: "Other districts"};
const ORDER = ["federal", "statewide", "legislature", "county", "soil_water", "city", "township", "school", "hospital", "other", "court"];      /* the ballot pages' order, Congress first */
/* what the state calls the places below it: [one, many, a heading, inside a sentence, what follows a place's name] */
const UW = ST.uw || ["county", "counties", "County by county", "county by county", " County"];
const cName = f => D.counties[f] ? `${D.counties[f]}${UW[4]}` : `${capital(UW[0])} ${f}`;
const counties = () => Object.keys(D.counties).sort((a, b) => D.counties[a].localeCompare(D.counties[b]));      /* (a code like "101" would otherwise come before "001": numeric keys go first in a script's objects) */
const pShort = p => (D.pshort || {})[p] || p;
const natural = d => { const m = /^(\d+)(\D*)$/.exec(String(d || "")); return m ? +m[1] * 100 + (m[2] ? m[2].charCodeAt(0) - 64 : 0) : 1e9; };
const shortDay = iso => fmtDay(iso).replace(/, \d{4}$/, "");
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return ""; } };
/* a party's primary (a rehearsal of a primary night) is a contest of its own, named for the race and the party */
function raceTitle(r) { const t = raceTitle0(r); return r.pp != null ? `${t}: ${primaryName(r)}` : t; }
const raceAt = id => R[id] || xRace(id);
function raceTitle0(r) {
  if (r.lv === "federal") return r.k === "us_senate" ? "U.S. Senator" : `U.S. Representative, District ${r.d}`;
  if (r.lv === "legislature") return `${r.o}, ${r.j}`;
  let t = r.o;
  if (r.lv === "court") return r.s ? `${t}, Seat ${r.s}` : t;
  if (r.d) t += /^\d+$/.test(r.d) ? `, District ${r.d}` : `, ${r.d}`;
  if (r.s && !/^at large$/i.test(r.s)) t += /^[A-Z0-9]{1,3}$/i.test(r.s) ? `, Seat ${r.s}` : `, ${r.s}`;
  return t + (r.sp ? " (special election)" : "");
}
function raceWhere(r) {
  if (r.lv === "federal") return r.k === "us_senate" ? ST.name : "";
  if (r.lv === "statewide") return ST.name;
  if (r.lv === "legislature") return "";
  if (r.lv === "court") return r.j === ST.name ? "Statewide" : r.j || "";
  return r.j || "";
}
const hrefRace = r => "#race=" + encodeURIComponent(r.id);
const ballotHref = r => (r.lv === "federal" ? BOOT.links.ballotUS : BOOT.links.ballot) + "#race=" + encodeURIComponent(r.base || r.id);
const kindOf = r => r && r.g ? r.g.slice(0, r.g.indexOf(":")) : "";
const idOf = r => r && r.g ? r.g.slice(r.g.indexOf(":") + 1) : "";

/* who certifies a race, by the state's canvass law (the sources below): the State Canvassing Board for federal offices and
   state offices voted on in more than one county; the county's board for county offices and state offices voted on within
   one county; a city's, a school district's or another district's own board for the rest */
function certOf(r) {
  const c = r.c || [], C = ST.cert || {};
  if (r.lv === "federal" || r.lv === "statewide" || ((r.lv === "legislature" || r.lv === "court") && c.length !== 1))
    return {body: "the State Canvassing Board", when: C.state ? `on ${shortDay(C.state)}` : ""};
  if (r.lv === "county" || r.lv === "legislature" || r.lv === "court")
    return {body: `the ${cName(c[0])} canvassing board`, when: C.county_from ? `between ${shortDay(C.county_from)} and ${shortDay(C.county_to)}` : ""};
  return {body: "the local canvassing board", when: "in the days after the election"};
}
function finalHTML(r, e) {
  const c = certOf(r);
  if (e && e.of) return `Certified by ${esc(c.body)}${e.ofd ? " on " + esc(shortDay(e.ofd)) : ""}.`;
  return `Not final: ${esc(c.body)} certifies these results${c.when ? " " + esc(c.when) : ""}.`;
}
/* every figure's time: a state saved by hand gives the time its files were saved from the state's site (they state no time of their own) */
const stampHTML = e => { const t = (e && e.t) || (LIVE.st && LIVE.st.t); return !t ? "" : ST.hand ? `As posted by the ${esc(ST.agency)}, saved from its site at ${esc(fmtTime(t))}.` : `As reported by the ${esc(ST.agency)} at ${esc(fmtTime(t))}.`; };
function repHTML(r, e) {
  if (!LIVE.st) return "No votes reported yet.";
  if (!e) return "This contest is not in the state&rsquo;s results file yet.";
  const a = (e.u || [])[0] || 0, b = (e.u || [])[1] || 0, U = n => n === 1 ? UNIT : UNIT + "s";
  if (!b) return "";
  if (b === 1) return a ? `Its one ${UNIT} has reported.` : `Its one ${UNIT} has not reported yet.`;
  return a >= b ? `All ${num(b)} ${U(b)} have reported.` : a ? `${num(a)} of ${num(b)} ${U(b)} have reported.` : `No ${UNIT} has reported yet (${num(b)} in all).`;
}
/* a count as the lines of one result: a precinct's row or a county's figures, in the race's own layout */
function entryOf(r, e, v, x, w) { return {v: v || [], x: ((e && e.x) || []).map((a, k) => [a[0], a[1], (x || [])[k] || 0]), w: w || 0}; }
function rowEntry(r, row) { const e = E(r.id), n = r.cs.length, nx = ((e && e.x) || []).length; return entryOf(r, e, row.slice(0, n), row.slice(n, n + nx), e && e.w ? row[n + nx] : 0); }
const named = (v, x) => (v || []).concat((x || []).map(a => Array.isArray(a) ? a[2] || 0 : a || 0));
function electedSet(r, L, e) { const nm = L.lines.filter(x => !x.wl); return new Set(Array.isArray(e.el) ? nm.filter(x => e.el.includes(x.i)) : nm.slice(0, seatsOf(r))); }
function linesHTML(r, e) {      // the marks (ahead, elected) only on the race's own count, never on a precinct's or a county's
  const own = e && e === E(r.id), L = lines(r, e), certified = own && !!e.of, ahead = own && !certified ? aheadSet(r, L) : new Set(), el = certified ? electedSet(r, L, e) : new Set();
  return `<div class="lns">${L.lines.map(x => {
    const share = L.total ? x.votes / L.total * 100 : 0;
    const badge = el.has(x) ? `<em class="badge el">Elected</em>` : ahead.has(x) ? `<em class="badge">Ahead in the count so far</em>` : "";
    const party = x.wl ? "" : r.pt ? ` <small>${esc(pShort(x.party) || "No party given")}</small>` : "";
    const fig = L.total ? `<b>${pct(x.votes, L.total)}</b> <span>${num(x.votes)}<span class="sr"> votes</span></span>` : x.wl ? "" : `<span>&ndash;</span>`;
    return `<div class="ln${x.wl ? " wl" : ""}"><span class="nm"><span class="nsw" style="--c:${x.c}" data-p="${x.p}" aria-hidden="true"></span>${esc(x.name)}${party}${badge ? " " + badge : ""}</span><span class="fig">${fig}</span>${L.total ? `<span class="nbar" aria-hidden="true"><i style="width:${share.toFixed(2)}%;--c:${x.c}" data-p="${x.p}"></i></span>` : ""}</div>`;
  }).join("")}</div>`;
}
/* a race with no figures of its own whose parties' primaries have them: each primary in its place */
const primaries = r => r.pp == null && !E(r.id) ? partsOf(r.id, "party") : [];
function resultHTML(r, o = {}) {
  const pr = primaries(r);
  if (pr.length) return pr.map(p => resultHTML(p, o)).join("");
  const e = E(r.id), n = seatsOf(r), unopp = r.cs.length <= n && r.pp == null, where = raceWhere(r);
  const head = o.link === false ? esc(raceTitle(r)) : `<a href="${hrefRace(r)}">${esc(raceTitle(r))}</a>`;
  const notes = [n > 1 ? `Voters choose ${num(n)}.` : "", unopp ? (r.cs.length === 1 ? "One candidate is on the ballot." : "As many candidates as seats are on the ballot.") : "", r.pt || r.pp != null ? "" : "Nonpartisan office.",
    r.pp != null ? "A party&rsquo;s primary, a contest of its own. Its candidates are shown as the state prints them." : ""].filter(Boolean).join(" ");
  return `<article class="res${o.small ? " small" : ""}" data-res="${esc(r.id)}" data-o="${esc(JSON.stringify(o))}"><h3>${head}</h3>${where && !o.noWhere ? `<p class="where">${esc(where)}</p>` : ""}
    <p class="nrep">${repHTML(r, e)}</p>${linesHTML(r, e)}${notes ? `<p class="one">${notes}</p>` : ""}
    ${LIVE.st && e ? `<p class="asof"><span class="tag fact">Fact</span> ${stampHTML(e)} ${finalHTML(r, e)}</p>` : ""}
    ${o.foot === false ? "" : `<div class="rfoot">${o.link === false ? "" : `<a href="${hrefRace(r)}">The map and every ${UNIT}</a>`}<a href="${esc(ballotHref(r))}">Who is running</a></div>`}</article>`;
}
function rowHTML(r, o = {}) {
  const pr = primaries(r);
  if (pr.length) return pr.map(p => rowHTML(p, o)).join("");
  const e = E(r.id), L = lines(r, e), nm = L.lines.filter(x => !x.wl), ah = aheadSet(r, L), n = seatsOf(r);
  const who = x => `<span class="nsw" style="--c:${x.c}" data-p="${x.p}" aria-hidden="true"></span><b>${esc(x.name)}</b>${r.pt && x.party ? ` (${esc(pShort(x.party))})` : ""} ${pct(x.votes, L.total)}`;
  let lead;
  if (!L.total) lead = r.cs.length <= n && r.pp == null ? `<small>${r.cs.length === 1 ? "One candidate on the ballot" : "As many candidates as seats"}${LIVE.st ? "; no votes yet" : ""}</small>` : `<small>No votes yet</small>`;
  else if (r.cs.length <= n && r.pp == null) lead = nm.filter(x => x.i < r.cs.length).map(who).join(", ") + `<small>${r.cs.length === 1 ? "the only candidate on the ballot" : "as many candidates as seats"}</small>`;
  else if (ah.size) lead = [...ah].map(who).join(", ") + `<small>ahead in the count so far</small>`;
  else lead = who(nm[0]) + `<small>${nm[1] && nm[1].votes === nm[0].votes ? "tied in the count so far" : "the count so far"}</small>`;
  const u = e && e.u && e.u[1] ? `${num(e.u[0])} of ${num(e.u[1])}<br>${UNIT}s in` : "";
  return `<a class="nrow" href="${hrefRace(r)}" data-row="${esc(r.id)}" data-o="${esc(JSON.stringify(o))}"><span class="t">${esc(raceTitle(r))}${o.where !== false && raceWhere(r) ? `<small>${esc(raceWhere(r))}</small>` : ""}</span><span class="l">${lead}</span><span class="u">${u}</span>${o.mine && LIVE.st ? `<span class="nmine" data-mine="${esc(r.id)}">Loading your ${UNIT}&rsquo;s figures&hellip;</span>` : ""}</a>`;
}

/* ---------- the state of the count ---------- */
/* The words follow the state's word in now.json (counting, done, official, held, stale, refused, link, none, wait) and
   whether the updates have paused (livePause: now.json's own "next" decides, never a fixed number of minutes). The block
   is redrawn after every look at now.json; the page's one announcement of new figures is NIGHTLIVE's, so the block is no
   live region of its own. */
function statusHTML() {
  const P = ST.polls, pn = pollsNow(P), st = LIVE.st, w = liveStatus(), pause = stale() ? livePause() : null;
  const own = `<a href="${esc(ST.results)}" target="_blank" rel="noopener">its own results</a>`, AG = esc(ST.agency);
  let word, body = "", small = [];
  if (st && st.units) {
    word = pause ? "stale" : w || "counting";
    const [a, b] = st.units;
    body = w === "official" ? "Certified results." : b && a >= b ? `All ${num(b)} ${UNIT}s have reported. Not final until certified.` : a ? `${num(a)} of ${num(b)} ${UNIT}s have reported.` : "No votes reported yet.";
    if (ST.hand && st.saved) small.push(`Copied from the ${AG}&rsquo;s results files, saved from the state&rsquo;s site at ${esc(fmtTime(st.saved))}. The state&rsquo;s own site is the authority: <a href="${esc(ST.results)}" target="_blank" rel="noopener">its results</a>.`);
    else body += " " + stampHTML(st);
    if (pause) small.push(`Updates have paused since ${esc(fmtTime(pause.since))}. The last figures stay, with their time. The state&rsquo;s own results: <a href="${esc(ST.results)}" target="_blank" rel="noopener">its site</a>.`);
    if (w === "stale") small.push(`The ${AG}&rsquo;s site has not answered since ${esc(fmtTime(st.t))}. The last figures stay, with their time. The state&rsquo;s own results: ${own}.`);
    if (w === "held") small.push(`The state&rsquo;s file changed tonight, so these are the last figures read cleanly, as of ${esc(fmtTime(st.t))}.`);
    if (w === "refused") small.push(`The ${AG}&rsquo;s site refused this site&rsquo;s requests tonight, so the figures here stop at ${esc(fmtTime(st.t))}. The state&rsquo;s own results: ${own}.`);
  } else if (isPreview() && LIVE.why) {
    word = "none"; body = "This preview serves the draft site alone, so there are no live figures here.";
    small.push("On election night the figures come from the live site beside the draft.");
  } else if (w === "link" || w === "refused") {
    word = w;
    body = w === "link" ? `${NM} does not publish a live count this site may read. The state&rsquo;s own results: ${own}. Official totals are added when the state certifies them.`
      : `The ${AG}&rsquo;s site refused this site&rsquo;s requests tonight, so its count is not read here. The state&rsquo;s own results: ${own}. Official totals are added when the state certifies them.`;
  } else {
    word = pn && pn.state === "open" ? "wait" : "none";
    body = !pn || pn.state === "closed" ? "No votes reported yet." : `No votes reported yet. Polls close at ${esc(fmtTime(pn.close, true))}. The state releases no results before then.`;
    if (pause && (!pn || pn.state === "closed")) small.push(`Updates have paused since ${esc(fmtTime(pause.since))}. The state&rsquo;s own results: ${own}.`);
  }
  if (ST.counting) small.push(esc(ST.counting));
  return `<div class="nstatus" data-nstat>${pollsHTML(P, ST.name)}<div class="nstat">${statusChip(word)}<p>${body}${small.map(t => `<small>${t}</small>`).join("")}</p></div></div>`;
}

/* ---------- the map: BallotMap, with the count painted on it ---------- */
const PIN = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="11" r="3"/><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/></svg>`;
const PIN_SVG = `<svg viewBox="0 0 26 34" aria-hidden="true"><path d="M13 33C13 33 2 20.6 2 12.4 2 6.1 6.9 1 13 1s11 5.1 11 11.4C24 20.6 13 33 13 33z"/><circle cx="13" cy="12.2" r="4.3"/></svg>`;
const FAR = ["county", "cd", "senate", "house", "judicial", "hospital", "park", "swcd"];      // layers light enough to paint whole when the view is far out
function mapHTML(top) {
  return `<div class="mapgrid nmapgrid" id="nmapsec"><div class="mapcol">
    <div class="mapbar">${top}<div class="zoom" role="group" aria-label="Zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">&minus;</button><button type="button" data-z="fit" aria-label="Show the whole state">&#10530;</button><button type="button" data-z="me" id="nme" aria-label="Go to my ${UNIT}" title="Go to my ${UNIT}" hidden>${PIN}</button></div></div>
    <div class="nmap" id="nmap" tabindex="0" role="group" aria-roledescription="map" aria-label="Map of ${NM}" aria-describedby="nmaphelp"><canvas aria-hidden="true"></canvas><div class="gpin" hidden aria-hidden="true">${PIN_SVG}</div><span class="gbusy" hidden>Loading lines&hellip;</span></div>
    <div class="nlegend" id="nlegend"></div>
    <p class="mnote" id="nline"></p>
    <p class="sr" id="nmaphelp">The map is a picture of the count; every figure on it is also in the lists on this page. With the map in focus the arrow keys move it, plus and minus zoom, zero shows the whole state, Enter names the place under the cross in the middle and Escape lets go of it.</p>
  </div><aside class="mapside" id="nside" aria-live="polite"><p class="held">Loading the map&hellip;</p></aside></div>`;
}
const side = html => { const s = $("#nside"); if (s) s.innerHTML = html; };
function inArea(r, p) {
  const k = kindOf(r), id = idOf(r);
  if (!k) return false;
  if (k === "state") return true;
  if (k === "mcd") return p.mcd === id || (p.mcd_all || []).includes(id);
  const v = p[k];
  return Array.isArray(v) ? v.includes(id) : v === id;
}
const countyIn = (r, c) => kindOf(r) === "state" || !r.c || r.c.includes(c);
function looksOf(r) {      // each named line's colour and pattern, read from the page's own tokens (they follow the theme and contrast)
  const e = E(r.id), n = r.cs.length + ((e && e.x) || []).length, cs = getComputedStyle(document.documentElement), out = {cols: [], pats: []}, pat = patterned();
  for (let i = 0; i < n; i++) { const c = r.cs[i], pc = c ? (c[2] || "O") : "O", k = PCODE.includes(pc) ? pc : "O";
    out.cols.push(cs.getPropertyValue(r.pt ? "--p" + k : "--n" + (i % 6 + 1)).trim()); out.pats.push(pat ? (r.pt ? PPAT[k] : NPAT[i % NPAT.length]) : ""); }
  return out;
}
function lookNow() {
  const cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim();
  return {tie: v("--muted") || "#777", empty: NightKit.rgba(v("--line-strong") || "#bbbbbb", .55), wait: v("--hatch-ink") || "#888", overlay: v("--nstripe") || "rgba(255,255,255,.6)",
    patterned: patterned(), edge: v("--surface") || "#fff"};
}
function paintSpec(kit) {
  if (!LIVE.st || !SPEC) return;
  const look = lookNow();
  if (SPEC.leg) {
    const key = SPEC.leg, memo = {};
    NightKit.paint(kit, key, did => { const r = LEGR[key][did]; if (!r) return null; const e = E(r.id); if (!e || !e.u || !e.u[0]) return "wait";
      const lk = memo[r.id] || (memo[r.id] = looksOf(r)); return {v: named(e.v, e.x), cols: lk.cols, pats: lk.pats}; }, look);
    return;
  }
  const r = SPEC.race; if (!r) return;
  const e = E(r.id), lk = looksOf(r), kind = kindOf(r), id = idOf(r), n = r.cs.length, nx = ((e && e.x) || []).length;
  if (kit.detail) {      // close in: each precinct of the race's area by its own count
    const part = partOf(r);      /* the county file this race is in: the judges' or the other */
    kit.counties.forEach(c => { if (!ctyHas(c, part) && countyIn(r, c)) liveCounty(c, part).then(() => { if (MAP) MAP.redraw(); }, () => {}); });
    NightKit.paint(kit, "precincts", (pid, p) => { if (!inArea(r, p)) return null; const f = ctyHas(p.county, part) && LIVE.cty[p.county]; if (!f) return null;
      const row = ((f.p || {})[r.id] || {})[pid]; return row ? {v: row.slice(0, n + nx), cols: lk.cols, pats: lk.pats} : "wait"; }, look);
  } else if (kind === "state" && e && e.c) {      // far out: a statewide race county by county
    NightKit.paint(kit, "county", cid => { const ce = e.c[cid]; return ce && ce.u && ce.u[0] ? {v: named(ce.v, ce.x), cols: lk.cols, pats: lk.pats} : "wait"; }, look);
  } else if (kind === "state") {
    NightKit.paint(kit, "state", () => e && e.u && e.u[0] ? {v: named(e.v, e.x), cols: lk.cols, pats: lk.pats} : "wait", look);
  } else if ((FAR.includes(kind) || kit.layer === kind) && kit.has(kind)) {      // far out: the race's own district or place, whole (its layer's file is in hand)
    NightKit.paint(kit, kind, sid => sid !== id ? null : !e || !e.u || !e.u[0] ? "wait" : {v: named(e.v, e.x), cols: lk.cols, pats: lk.pats}, look);
  }
}
function legendHTML() {
  if (!SPEC || !LIVE.st) return LIVE.st ? "" : `<span>The map is shaded once figures are in.</span>`;
  const items = [];
  if (SPEC.leg) {
    const seen = new Map();
    Object.values(LEGR[SPEC.leg]).forEach(r => lines(r, E(r.id)).lines.forEach(x => { if (!x.wl && !seen.has(x.c)) seen.set(x.c, [pShort(x.party) || "No party given", x.p]); }));
    seen.forEach(([w, p], c) => items.push(`<span><i class="lgsw" style="--c:${c}" data-p="${p}"></i>${esc(w)}</span>`));
  } else {
    const r = SPEC.race;
    lines(r, E(r.id)).lines.filter(x => !x.wl).sort((a, b) => a.i - b.i).forEach(x => items.push(`<span><i class="lgsw" style="--c:${x.c}" data-p="${x.p}"></i>${esc(x.name)}${r.pt && x.party ? ` (${esc(pShort(x.party))})` : ""}</span>`));
  }
  items.push(`<span><i class="lgsw wait"></i>Not reported yet</span>`, `<span><i class="lgsw shade"></i>Paler: ahead by under 5 points. Deeper: by 15 or more.</span>`);
  return items.join("");
}
function countySide(r, f) {      // a statewide race's figures in one county
  const e = E(r.id), ce = e && e.c && e.c[f];
  return `<span class="kick">${esc(cName(f))}</span><h3>${esc(raceTitle(r))}</h3>` + (!LIVE.st ? `<p class="held">No votes reported yet.</p>`
    : ce ? `<p class="held">${ce.u && ce.u[0] ? `${num(ce.u[0])} of ${plural(ce.u[1], UNIT)} in this county have reported.` : `No ${UNIT} in this county has reported yet.`}</p>${linesHTML(r, entryOf(r, e, ce.v, ce.x, ce.w))}<p class="asof"><span class="tag fact">Fact</span> ${stampHTML(e)}</p>`
    : `<p class="held">The state&rsquo;s file gives no county figures for this race.</p>`);
}
function sideHome() {
  if (!SPEC) return "";
  if (SPEC.leg) return `<span class="kick">The ${SPEC.leg === "house" ? esc(ST.loT) : esc(ST.upT)}</span><h3>Every district</h3><p class="held">${LIVE.st ? "Each district is the colour of the party ahead in its count so far. Tap a district for its race." : "Tap a district for its race."}</p>`;
  if (SPEC.county && kindOf(SPEC.race) === "state") return countySide(SPEC.race, SPEC.county) + `<p class="sidehint">Tap a ${UNIT} for its own figures.</p>`;
  return `<span class="kick">${esc(LV[SPEC.race.lv] || "")}</span>${resultHTML(SPEC.race, {small: true})}<p class="sidehint">${kindOf(SPEC.race) === "state" ? "Tap a county for its own figures." : "Tap the map for a place&rsquo;s own figures."} Zoom in and each ${UNIT} takes over.</p>`;
}
const BACK = `<p class="sidehint"><button type="button" class="linkbtn" data-side="home">Back to the whole race</button></p>`;
function precinctOf(pid) {      // a precinct's shape and properties, from the county file the map holds
  const c = String(pid).slice(2, 5), meta = IDX && IDX.counties.find(x => x.id === c);
  return meta && MAP ? MAP.load(meta.file).then(f => f.objects.precincts.geometries.find(g => g.id === pid) || null) : Promise.resolve(null);
}
function picked(p, again) {      // again: redrawn for new figures, not picked by the reader (so not read out again)
  const sd = $("#nside"); if (sd && !again) sd.setAttribute("aria-live", "polite");
  LASTPICK = p && !p.cleared && !p.loading ? p : null;
  if (p.cleared) { side(sideHome()); return; }
  if (p.loading) { side(`<p class="held">The lines for this part of the map are still loading. Tap again in a moment.</p>${BACK}`); return; }
  if (!SPEC) return;
  if (SPEC.leg) { const r = LEGR[SPEC.leg][p.id];
    side(r ? resultHTML(r, {small: true}) + BACK : `<p class="held">${p.id == null ? "No district at that spot." : "No race for this district is on the ballot this year."}</p>${BACK}`); return; }
  const r = SPEC.race;
  if (p.precinct) {
    const pid = p.precinct.id, c = String(pid).slice(2, 5);
    side(`<span class="kick">${esc(capital(UNIT))} &middot; ${esc(cName(c))}</span><h3>${esc(p.precinct.name)}</h3><p class="held">Loading its figures&hellip;</p>${BACK}`);
    Promise.all([precinctOf(pid), LIVE.st ? liveCounty(c, partOf(r)).catch(() => null) : null]).then(([g, f]) => {
      if (!$("#nside")) return;
      const inside = g && inArea(r, g.properties || {}), row = f && ((f.p || {})[r.id] || {})[pid];
      side(`<span class="kick">${esc(capital(UNIT))} &middot; ${esc(cName(c))}</span><h3>${esc(p.precinct.name)}</h3>`
        + (!inside ? `<p class="held">This ${UNIT} is not part of this contest&rsquo;s area.</p>` : !LIVE.st ? `<p class="held">No votes reported yet.</p>`
          : row ? `<p class="held">This ${UNIT}&rsquo;s own count for ${esc(raceTitle(r))}.</p>${linesHTML(r, rowEntry(r, row))}<p class="asof"><span class="tag fact">Fact</span> ${stampHTML({t: (f.tp || {})[partOf(r)] || f.t})}</p>`
          : `<p class="held">This ${UNIT} has not reported yet.</p>`) + BACK); });
    return;
  }
  if (p.kind === "county" && kindOf(r) === "state") {
    side(countySide(r, p.id) + `<p class="sidehint"><a href="#county=${esc(p.id)}">Every contest in ${esc(cName(p.id))}</a></p>${BACK}`);
    return;
  }
  side(p.id != null && p.kind === kindOf(r) && String(p.id) === idOf(r) ? sideHome() : `<p class="held">${p.id == null ? "Nothing of this race at that spot." : `${esc(p.name || "This place")} is not part of this contest&rsquo;s area.`}</p>${BACK}`);
}
function layerFor(spec, idx) {
  const have = new Set((idx.layers || []).map(L => L.kind));
  if (spec.leg) return spec.leg;
  const k = kindOf(spec.race);
  return k && k !== "state" && have.has(k) ? k : "county";
}
function mountMap(spec) {
  if (MAP) { MAP.destroy(); MAP = null; }
  SPEC = spec;
  const el = $("#nmap"); if (!el) return Promise.resolve(null);
  $("#nlegend").innerHTML = legendHTML();
  return Promise.all([needKit(), needIdx()]).then(([, idx]) => {
    if (!el.isConnected) return null;
    MAP = BallotMap(el, {index: idx, base: BOOT.geo.base, v: BOOT.geo.v, layer: layerFor(spec, idx), onPick: picked, paint: paintSpec,
      short: (kind, id, name) => kind === "county" ? String(name || "").replace(/ County$/, "") : ["house", "senate", "cd"].includes(kind) ? String(id) : String(name || ""),
      onView: v => { const n = $("#nline"); if (n) n.textContent = v.failed && !v.detail ? "Some of the map’s lines could not be loaded. Check your connection; the map asks again as you move it."
        : v.detail ? `Here each ${UNIT} is shaded by its own count.` : v.near ? `Loading this area’s ${UNIT} lines…` : (SPEC && SPEC.race && kindOf(SPEC.race) === "state" ? "Far out, each county is shaded by its own count; zoom in and each " + UNIT + " takes over." : "Zoom in and each " + UNIT + " is shaded by its own count."); }});
    const me = $("#nme"); if (me) me.hidden = !(MINE && MINE.p);
    if (MINE && MINE.p) MAP.setMine(mineIds(MINE));
    side(sideHome());
    return MAP;
  }).catch(() => { side(`<p class="held">The map could not be loaded. Check your connection and open the page again; every figure is also in the lists on this page.</p>`); return null; });
}
function wireMap() {
  const sec = $("#nmapsec"); if (!sec) return;
  sec.addEventListener("click", e => { const b = e.target.closest("button"); if (!b || !MAP) return;
    if (b.dataset.z === "in") MAP.zoomIn(); else if (b.dataset.z === "out") MAP.zoomOut(); else if (b.dataset.z === "fit") MAP.whole();
    else if (b.dataset.z === "me" && MINE && MINE.at) MAP.goTo(MINE.at[0], MINE.at[1], 13);
    else if (b.dataset.side === "home") { MAP.select(null); LASTPICK = null; const sd = $("#nside"); if (sd) sd.setAttribute("aria-live", "polite"); side(sideHome()); } });
}
const raceSpec = r => ({race: r});
function focusOn(kind, id, counties) { if (!MAP) return; MAP.focus(kind, id, counties).then(() => { if (MAP) MAP.select(null); }, () => {}); }

/* ---------- your ballot: the precinct, found on this device; the spot itself is never kept ---------- */
const LOC_BTN = `<button type="button" class="locbtn" id="yloc">${PIN}Use my location</button><button type="button" class="linkbtn" id="yforget" hidden>Forget my location</button>`;
function yoursHTML() {
  return `<section class="bsec" id="yours"><h2>Your ballot&rsquo;s results</h2>
    <p class="sub">Use your location and this device finds your ${UNIT}, then shows every contest on your ballot with the count so far and your own ${UNIT}&rsquo;s figures. Your location stays on this device; nothing is sent anywhere.</p>
    <div class="mybar">${LOC_BTN}<select class="pick" id="ycty" aria-label="Or pick your ${esc(UW[0])}"></select></div>
    <p class="ynote" id="ynote" aria-live="polite"></p><div id="yres"></div></section>`;
}
function readMine() { try { const m = JSON.parse(store.get(MKEY) || "null"); return m && m.p && m.c && D.counties[m.c] ? m : null; } catch (e) { return null; } }
const mineIds = z => ({c: z.c, p: z.p, at: z.at, ids: {county: z.c, mcd: z.m, ward: (z.w || [])[0], com: z.com, house: z.hd, senate: z.sd, cd: z.cd, judicial: z.jd, swcd: z.sw, hospital: z.ho, park: z.pk, school: (z.sch || [])[0]}});
function zonesOf(res) {
  const p = res.precinct.properties || {};
  const sch = res.school ? [res.school] : (p.school || []).slice();
  return {p: res.precinct.id, pn: p.name, c: p.county, at: p.c, m: res.mcd || p.mcd || "", w: p.ward || [], com: p.com || "", pk: p.park || "", hd: p.house || "",
    sd: p.senate || "", cd: p.cd || "", jd: p.judicial || "", sw: p.swcd || "", ho: p.hospital || "", sch, split: !res.school && sch.length > 1 ? 1 : 0};
}
function myRaces(z) {
  const keys = new Set(["state:" + ST.code, "county:" + z.c, z.com && "com:" + z.com, z.pk && "park:" + z.pk, z.m && "mcd:" + z.m, ...(z.w || []).map(w => "ward:" + w),
    z.hd && "house:" + z.hd, z.sd && "senate:" + z.sd, z.cd && "cd:" + z.cd, z.jd && "judicial:" + z.jd, z.sw && "swcd:" + z.sw, z.ho && "hospital:" + z.ho, ...(z.sch || []).map(s => "school:" + s)].filter(Boolean));
  return D.races.filter(r => r.g && keys.has(r.g));
}
function mineHTML(z) {
  const rs = myRaces(z), by = {};
  rs.forEach(r => (by[r.lv] = by[r.lv] || []).push(r));
  const notes = [z.split ? `Your ${UNIT} is split between school districts, and which one your spot is in could not be settled here: both are listed, and only one is on your ballot.` : "",
    rs.some(r => r.lv === "hospital" && r.s && !/^at large$/i.test(r.s)) ? "A hospital district seat named for one part of the district is voted on only there." : ""].filter(Boolean);
  return `<div class="lvl"><h3>Where you are</h3><p>${esc(capital(UNIT))} ${esc(z.pn)}, ${esc(cName(z.c))}. ${plural(rs.length, "contest")} on your ballot, level by level. Your county&rsquo;s sample ballot is the authority on your exact ballot.</p>${notes.map(t => `<p>${t}</p>`).join("")}</div>`
    + ORDER.filter(lv => by[lv]).map(lv => { const rows = `<div class="nrows">${by[lv].map(r => rowHTML(r, {mine: 1})).join("")}</div>`;
      return `<div class="lvl"><h3>${esc(LV[lv])}</h3>${by[lv].length > 6 ? `<details class="nfold"><summary>${plural(by[lv].length, "contest")}: show them</summary>${rows}</details>` : rows}</div>`; }).join("");      /* a long level (the judges, often) folded, so the rest of the ballot stays in reach */
}
function mineLine(r, row) {
  const L = lines(r, rowEntry(r, row)), nm = L.lines.filter(x => !x.wl);
  return L.total ? nm.slice(0, 4).map(x => `<b>${esc(x.name)}</b> ${pct(x.votes, L.total)} (${num(x.votes)})`).join(" &middot; ") + (nm.length > 4 ? ` &middot; and ${num(nm.length - 4)} more` : "") : "no votes for this contest here yet";
}
function fillMine(z) {
  if (!LIVE.st) return;
  liveCounty(z.c).then(f => $$("[data-mine]").forEach(s => { const r = R[s.dataset.mine], row = r && ((f.p || {})[r.id] || {})[z.p];
    s.innerHTML = !r ? "" : row ? `In your ${UNIT}: ${mineLine(r, row)}` : `Your ${UNIT} has not reported yet.`; }),
    () => $$("[data-mine]").forEach(s => { s.textContent = `Your ${UNIT}’s own figures could not be loaded just now.`; }));
}
function paintMine() {
  const out = $("#yres"), fb = $("#yforget"); if (!out) return;
  MINE = readMine();
  if (fb) fb.hidden = !MINE;
  out.innerHTML = MINE ? mineHTML(MINE) : "";
  if (MINE) fillMine(MINE);
  const me = $("#nme"); if (me) me.hidden = !(MINE && MINE.p);
}
function mountYours() {
  const sel = $("#ycty"), note = $("#ynote"), btn = $("#yloc"), fb = $("#yforget"); if (!sel) return;
  sel.innerHTML = `<option value="">Or pick your ${esc(UW[0])}</option>` + counties().map(f => `<option value="${esc(f)}">${esc(cName(f))}</option>`).join("");
  sel.addEventListener("change", () => { if (sel.value) location.hash = "county=" + sel.value; });
  fb.addEventListener("click", () => { [MKEY, "pin", "district", "sld:" + ST.lc, "ballot:" + ST.lc].forEach(k => store.del(k)); MINE = null;
    if (MAP) { MAP.setMine(null); MAP.setPin(null); MAP.whole(); }
    paintMine(); note.textContent = "Forgotten. Your location is no longer kept on this device, on this page or the site’s others."; });
  btn.addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn’t available in this browser. Pick your county instead."; return; }
    note.textContent = `Finding your ${UNIT}…`;
    navigator.geolocation.getCurrentPosition(pos => {
      const lat = pos.coords.latitude, lon = pos.coords.longitude;
      (MAP ? Promise.resolve(MAP) : mountMap(SPEC || raceSpec(topRace()))).then(map => map ? map.locate(lon, lat) : null).then(res => {
        if (!res) { note.textContent = `That spot isn’t inside ${ST.name} on the map. Pick your county instead.`; return; }
        const z = zonesOf(res);
        store.set(MKEY, JSON.stringify(z));      // the precinct and its districts; never the spot
        store.set("pin", JSON.stringify({st: ST.code, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(pos.coords.accuracy || 0)}));      // rounded, as the site's other pages keep it
        paintMine();
        if (MAP) { MAP.setMine(mineIds(z)); MAP.setPin([lon, lat]); const b = res.precinct.bbox;
          if (b) MAP.fitBox([Math.min(b[0], lon), Math.min(b[1], lat), Math.max(b[2], lon), Math.max(b[3], lat)], 15, 11); }
        note.textContent = `Worked out on this device; your location never leaves it. You are in ${UNIT} ${z.pn}, ${cName(z.c)}.`;
      }, () => { note.textContent = "Couldn’t load the map’s lines. Check your connection, or pick your county."; });
    }, () => { note.textContent = "Location wasn’t shared. Pick your county instead."; }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000});
  });
  paintMine();
}

/* ---------- where it comes from ---------- */
function sourcesHTML() { return `<div id="nsrc">${sourceFold("Where this comes from", sourceParts(), "sources")}</div>`; }
function srcItem(s, extra) {
  return {h: `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}<small><span class="tag fact">Fact</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(hostOf(s.url))}</a>` : ""}${s.read || s.fetched ? ` &middot; read ${esc(s.read || s.fetched)}` : ""}${extra ? ` &middot; ${extra}` : ""}</small>${s.use ? `<small><b>Its notice on use:</b> ${esc(s.use)}</small>` : ""}${s.disclaimer ? `<small><b>Its disclaimer, word for word:</b> ${esc(s.disclaimer)}</small>` : ""}</div>`};
}
function sourceParts() {
  const res = [srcItem({agency: ST.agency, title: "Election results files (the Media Files the results site offers), saved by hand from the state's site on election night, as often as the count changes", url: ST.results}, "the state&rsquo;s own site is the authority")];
  if (BOOT.practice) res.push(srcItem(BOOT.practice.source, "used here for practice only"));
  return {
    results: {items: res, notes: ["The state&rsquo;s results site asks people, not programs, to read it, so no program here asks it for anything: the files are saved by hand in a browser and read from there."]},
    lists: {items: (D.sources || []).map(s => srcItem(s))},
    rules: {items: (ST.rules || []).map(s => srcItem(s)), notes: [esc(ST.pollsNote || "")].filter(Boolean)},
    maps: {items: IDX ? (IDX.sources || []).map(s => srcItem({agency: s.agency, title: s.title, url: s.url, read: s.fetched, use: s.use, disclaimer: s.disclaimer})) : [], notes: IDX ? [] : ["The map&rsquo;s sources load with the map."]},
    page: {notes: ["Every figure is an official count as the state&rsquo;s results files give it, with the time they state. Nothing here is a forecast: until the canvass makes the results official, the page says only who is ahead in the count so far.",
      `A ${UNIT} counts as reported here once it is in the state&rsquo;s file with its figures. The map shades each county or ${UNIT} in the colour of the candidate ahead there: paler for a lead under 5 points, deeper for 15 points or more; hatching marks an area that has not reported. A party&rsquo;s colour is used only for that party&rsquo;s candidates; candidates for a nonpartisan office take neutral tones, in ballot order.`,
      `Use my location finds your ${UNIT} on this device and keeps only the ${UNIT} and its districts there (and a copy of your spot rounded to about half a mile, which the site&rsquo;s other pages share) until you tap Forget. Nothing is sent anywhere.`]}};
}
function refreshSources() { needIdx().then(() => { const s = $("#nsrc"); if (s && !s.querySelector("details[open]")) s.innerHTML = sourceFold("Where this comes from", sourceParts(), "sources"); }, () => {}); }

/* ---------- pages ---------- */
const topRace = () => D.races.find(r => r.k === "governor") || D.races.find(r => r.lv === "statewide") || D.races[0];
function heroHTML(kick, title, lede) { return `<section class="bhero nhero"><span class="eyebrow">${kick}</span><h1>${title}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</section>`; }
function crumbs(list) { return `<nav class="crumbs" aria-label="Where you are"><a href="#">${NM} results</a>${list.map(x => ` &rsaquo; ${x}`).join("")}</nav>`; }
const topOfBallot = () => D.races.filter(r => r.lv === "statewide").concat(D.races.filter(r => r.k === "us_senate"));
function mapChooser() {
  const sw = topOfBallot(), house = D.races.filter(r => r.k === "us_house");
  return `<select class="pick" id="nrace" aria-label="What the map shows">${sw.map(r => `<option value="r:${esc(r.id)}">${esc(raceTitle(r))}</option>`).join("")}
    <option value="leg:senate">${esc(ST.upT)}: every district</option><option value="leg:house">${esc(ST.loT)}: every district</option>
    ${house.map(r => `<option value="r:${esc(r.id)}">${esc(raceTitle(r))}</option>`).join("")}</select>`;
}
function wireChooser() {
  const sel = $("#nrace"); if (!sel) return;
  const set = v => { const spec = v.startsWith("leg:") ? {leg: v.slice(4)} : raceSpec(R[v.slice(2)]);
    SPEC = spec; $("#nlegend").innerHTML = legendHTML();
    if (MAP && IDX) { MAP.setLayer(layerFor(spec, IDX)); MAP.redraw(); side(sideHome());
      if (spec.race && kindOf(spec.race) !== "state") focusOn(kindOf(spec.race), idOf(spec.race), spec.race.c); else MAP.whole(); } };
  sel.value = SPEC && SPEC.race ? "r:" + SPEC.race.id : SPEC && SPEC.leg ? "leg:" + SPEC.leg : sel.value;
  sel.addEventListener("change", () => set(sel.value));
}
function levelCards() {
  const n = lv => D.races.filter(r => r.lv === lv).length, local = D.races.filter(r => !["federal", "statewide", "legislature", "court"].includes(r.lv)).length;
  const card = (href, b, span) => `<a class="lvcard" href="${href}"><b>${b}</b><span>${span}</span><span class="go">Open &rsaquo;</span></a>`;
  return [card("#statewide", "Statewide and Congress", `${plural(n("statewide"), "statewide office")} and ${plural(n("federal"), "race")} for Congress`),
    card("#legislature", "The Legislature", `${plural(n("legislature"), "race")}: every ${esc(ST.upT)} and ${esc(ST.loT)} district`),
    card("#courts", "Judges", `${plural(n("court"), "seat")} on the ${NM} courts`),
    card("#counties", esc(UW[2]), `${plural(local, UW[0] + " and local contest")}: ${esc(UW[0])} offices, cities, townships, school boards and more`)].join("");
}
function countyCards() {
  const c = {}; D.races.forEach(r => (r.c || []).forEach(f => { c[f] = (c[f] || 0) + 1; }));
  return counties().map(f => `<a class="scard2" href="#county=${esc(f)}"><b>${esc(cName(f))}</b><span>${plural(c[f] || 0, "contest")}${countyRep(f)}</span></a>`).join("");
}
function countyRep(f) { const e = E(topRace().id), ce = e && e.c && e.c[f]; return `<span data-crep="${esc(f)}">${ce && ce.u && ce.u[1] ? ` &middot; ${num(ce.u[0])} of ${num(ce.u[1])} ${UNIT}s in` : ""}</span>`; }
function countyLede(f) { const t = topRace(), te = E(t.id), ce = te && te.c && te.c[f]; return `<span data-clede="${esc(f)}">${ce && ce.u ? ` ${num(ce.u[0])} of ${num(ce.u[1])} ${UNIT}s in the county have reported.` : ""}</span>`; }
function home(focus) {
  document.title = `Election Night: ${ST.name} · The Civic Archive`;
  const top = topOfBallot();
  app.innerHTML = heroHTML(`Election Night &middot; ${NM}`, `${NM} results`, `Every race on ${NM}&rsquo;s November 3 ballot, from the governor to the school boards, counted as the ${esc(ST.agency)} posts the figures. Official counts only, each with its time.`)
    + statusHTML() + yoursHTML()
    + `<section class="bsec" id="map"><h2>The map</h2><p class="sub">Who is ahead in the count so far, county by county, and ${UNIT} by ${UNIT} as you zoom in. Pick a race; tap a place for its own figures.</p>${mapHTML(mapChooser())}</section>`
    + `<section class="bsec" id="top"><h2>At the top of the ballot</h2><div class="rgrid2">${top.map(r => resultHTML(r, {small: true})).join("")}</div></section>`
    + `<section class="bsec" id="levels"><h2>Every level</h2><div class="lvgrid">${levelCards()}</div></section>`
    + `<section class="bsec" id="counties"><h2>${esc(UW[2])}</h2><p class="sub">Every ${esc(UW[0])}, city, township, school and other district contest, ${esc(UW[3])}.</p><div class="sgrid">${countyCards()}</div></section>`
    + sourcesHTML();
  const m = /^(\w+):(.+)$/.exec(focus || "");
  const legAt = m && (m[1] === "house" || m[1] === "senate");
  const fr = m && !legAt ? D.races.find(r => r.g === m[1] + ":" + m[2]) : null;
  wireMap(); mountYours();
  mountMap(legAt ? {leg: m[1]} : raceSpec(fr || topRace())).then(() => { wireChooser(); if (m && MAP) focusOn(m[1], m[2]); refreshSources(); });
  if (focus === "mine") { const y = $("#yours"); if (y) y.scrollIntoView(); }
}
function statewide() {
  document.title = `Election Night: ${ST.name}, statewide and Congress · The Civic Archive`;
  const sw = D.races.filter(r => r.lv === "statewide"), fed = D.races.filter(r => r.lv === "federal"), courts = D.races.filter(r => r.lv === "court" && r.g === "state:" + ST.code);
  app.innerHTML = crumbs(["Statewide and Congress"]) + heroHTML(`Election Night &middot; ${NM}`, "Statewide and Congress", `The offices the whole state elects, and ${NM}&rsquo;s races for Congress.`) + statusHTML()
    + `<section class="bsec"><h2>Statewide offices</h2><div class="rgrid2">${sw.map(r => resultHTML(r)).join("")}</div></section>`
    + `<section class="bsec"><h2>Congress</h2><div class="rgrid2">${fed.map(r => resultHTML(r)).join("")}</div></section>`
    + (courts.length ? `<section class="bsec"><h2>Judges the whole state elects</h2><div class="rgrid2">${courts.map(r => resultHTML(r, {small: true})).join("")}</div></section>` : "")
    + sourcesHTML();
  refreshSources();
}
function legislature() {
  document.title = `Election Night: ${ST.name}'s Legislature · The Civic Archive`;
  const table = key => `<section class="bsec" id="leg-${key}"><h2>${esc(key === "senate" ? ST.upT : ST.loT)}</h2><div class="tblwrap" id="tbl-${key}"></div></section>`;
  app.innerHTML = crumbs(["The Legislature"]) + heroHTML(`Election Night &middot; ${NM}`, "The Legislature", `Every ${esc(ST.upT)} and ${esc(ST.loT)} race, district by district. Sort by any column; the closest races rise to the top when sorted by lead.`) + statusHTML()
    + `<section class="bsec"><h2>The map</h2>${mapHTML(`<div class="seg2" role="group" aria-label="Which chamber the map shows"><button type="button" data-leg="senate" aria-pressed="false">${esc(ST.upT)}</button><button type="button" data-leg="house" aria-pressed="true">${esc(ST.loT)}</button></div>`)}</section>`
    + table("senate") + table("house") + sourcesHTML();
  wireMap();
  mountMap({leg: "house"}).then(() => refreshSources());
  $$("[data-leg]").forEach(b => b.addEventListener("click", () => { $$("[data-leg]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    SPEC = {leg: b.dataset.leg}; $("#nlegend").innerHTML = legendHTML(); if (MAP) { MAP.setLayer(b.dataset.leg); MAP.redraw(); side(sideHome()); } }));
  ["senate", "house"].forEach(key => {
    const build = () => Object.values(LEGR[key]).map(r => { const e = E(r.id), L = lines(r, e), nm = L.lines.filter(x => !x.wl);
      return {id: r.id, r, d: r.d, e, L, top: L.total ? nm[0] : null, lead: L.total && nm[1] ? (nm[0].votes - nm[1].votes) / L.total * 100 : L.total ? 100 : null}; });
    const cols = [{key: "d", label: "District", val: x => natural(x.d), html: x => `<a href="${hrefRace(x.r)}">${esc(x.d)}</a>`},
        {key: "who", label: "Ahead in the count so far", val: x => x.top ? x.top.name : null, html: x => x.top ? `<span class="nsw" style="--c:${x.top.c}" data-p="${x.top.p}" aria-hidden="true"></span>${esc(x.top.name)}${x.top.party ? ` <small class="muted">${esc(pShort(x.top.party))}</small>` : ""}` : `<span class="muted">${x.r.cs.length <= 1 ? "One candidate" : "No votes yet"}</span>`},
        {key: "lead", label: "Lead", num: true, first: "asc", val: x => x.lead == null ? null : Math.round(x.lead * 10) / 10, html: x => x.lead == null ? "" : x.r.cs.length <= 1 ? "Unopposed" : x.lead.toFixed(1) + " pts"},
        {key: "rep", label: `${capital(UNIT)}s in`, num: true, val: x => x.e && x.e.u && x.e.u[1] ? x.e.u[0] / x.e.u[1] : null, html: x => x.e && x.e.u ? `${num(x.e.u[0])} of ${num(x.e.u[1])}` : ""}];
    const host = $("#tbl-" + key);
    TABLES.push({host, cols, build, grid: gridTable(host, {rows: build(), page: 70, sort: [{key: "d", dir: "asc"}], rowId: x => x.id, cols,
      count: rs => `${plural(rs.length, "district")}`})});
  });
}
function courts() {
  document.title = `Election Night: ${ST.name}'s judges · The Civic Archive`;
  const all = D.races.filter(r => r.lv === "court"), state = all.filter(r => r.g === "state:" + ST.code), by = {};
  all.filter(r => !state.includes(r)).forEach(r => (by[r.j || "Other courts"] = by[r.j || "Other courts"] || []).push(r));
  const keys = Object.keys(by).sort((a, b) => natural(a) - natural(b) || a.localeCompare(b));
  app.innerHTML = crumbs(["Judges"]) + heroHTML(`Election Night &middot; ${NM}`, "Judges", `Every seat on the ${NM} courts on this ballot. Judges are elected without a party.`) + statusHTML()
    + `<section class="bsec"><h2>The Supreme Court and the Court of Appeals</h2><div class="rgrid2">${state.map(r => resultHTML(r, {small: true})).join("")}</div></section>`
    + `<section class="bsec"><h2>District courts</h2>${keys.map(k => `<div class="lvl"><h3>${esc(k)}</h3><div class="nrows">${by[k].sort((a, b) => natural(a.s) - natural(b.s)).map(r => rowHTML(r, {where: false})).join("")}</div></div>`).join("")}</section>`
    + sourcesHTML();
  refreshSources();
}
function countyIndex() { home(); const c = $("#counties"); if (c) c.scrollIntoView(); }
function countyPage(f) {
  if (!D.counties[f]) { app.innerHTML = crumbs([]) + `<p class="nempty">No county with the code ${esc(f)} is on this page.</p>`; return; }
  document.title = `Election Night: ${cName(f)}, ${ST.name} · The Civic Archive`;
  const rs = D.races.filter(r => (r.c || []).includes(f) && r.lv !== "federal" && r.lv !== "statewide"), by = {};
  rs.forEach(r => (by[r.lv] = by[r.lv] || []).push(r));
  const group = (lv, list) => {
    if (["city", "township", "school", "hospital", "other"].includes(lv)) {
      const places = {}; list.forEach(r => (places[r.j || "Other"] = places[r.j || "Other"] || []).push(r));
      return Object.keys(places).sort((a, b) => a.localeCompare(b)).map(p => `<div class="grp"><h4>${esc(p)}</h4><div class="nrows">${places[p].map(r => rowHTML(r, {where: false})).join("")}</div></div>`).join("");
    }
    return `<div class="nrows">${list.sort((a, b) => natural(a.d) - natural(b.d) || natural(a.s) - natural(b.s)).map(r => rowHTML(r, {where: lv !== "county"})).join("")}</div>`;
  };
  const t = topRace();
  app.innerHTML = crumbs([`<a href="#counties">${esc(UW[2])}</a>`, esc(cName(f))]) + heroHTML(`Election Night &middot; ${NM}`, esc(cName(f)), `${plural(rs.length, "contest")} reaching ${esc(cName(f))}, from the Legislature to the school boards.${countyLede(f)}`) + statusHTML()
    + `<section class="bsec"><h2>The map</h2><p class="sub">${esc(raceTitle(t))}, ${UNIT} by ${UNIT}. Pick another race on the home page&rsquo;s map.</p>${mapHTML(`<span class="kick">${esc(raceTitle(t))}</span>`)}</section>`
    + ORDER.filter(lv => by[lv]).map(lv => `<section class="bsec"><h2>${esc(LV[lv])}</h2>${group(lv, by[lv])}</section>`).join("") + sourcesHTML();
  wireMap();
  mountMap({race: t, county: f}).then(() => { if (MAP) MAP.focus("county", f).then(() => { if (!MAP) return; MAP.select(null); if (MAP.view().z < 11) MAP.zoomIn(); }, () => {}); refreshSources(); });
}
function racePage(id) {
  const r = raceAt(id);
  if (!r) { app.innerHTML = crumbs([]) + `<p class="nempty">No race with that address is on this page. <a href="#">See every race</a>.</p>`; return; }
  document.title = `${raceTitle(r)}: Election Night, ${ST.name} · The Civic Archive`;
  const k = kindOf(r), wide = k === "state" || !r.c || r.c.length > 8;
  app.innerHTML = crumbs([esc(LV[r.lv] || ""), esc(raceTitle(r))]) + `<h1 class="sr">${esc(raceTitle(r))}, ${esc(ST.name)}</h1>` + statusHTML()
    + `<section class="bsec">${resultHTML(r, {link: false})}</section>`
    + (r.g ? `<section class="bsec"><h2>The map</h2><p class="sub">${k === "state" ? "County by county; zoom in and each " + UNIT + " takes over." : `Each ${UNIT} of the contest&rsquo;s area, shaded by its own count.`}</p>${mapHTML(`<span class="kick">${esc(raceTitle(r))}</span>`)}</section>` : `<p class="nempty">The map has no lines for this contest&rsquo;s area.</p>`)
    + `<section class="bsec"><h2>${wide ? esc(UW[2]) : `Every ${UNIT}`}</h2><div class="tblwrap" id="ntbl"><p class="held" style="padding:14px">Loading&hellip;</p></div></section>` + sourcesHTML();
  if (r.g) { wireMap(); mountMap(raceSpec(r)).then(() => { if (k !== "state") focusOn(k, idOf(r), r.c); refreshSources(); }); }
  tableFor(r, wide);
}
/* a race's table: county by county for a wide race, else every precinct of its area. tableRows gives {msg} or {rows, cols,
   opt}, so that new figures can be put into the table already on show (refreshTables) */
function tableRows(r, wide) {
  const e = E(r.id), msg = t => Promise.resolve({msg: `<p class="held" style="padding:14px">${t}</p>`});
  if (!LIVE.st) return msg("No votes reported yet.");
  if (!e) return msg("This contest is not in the state&rsquo;s results file yet.");
  const L0 = lines(r, e), heads = L0.lines.filter(x => !x.wl).slice(0, 4), cols0 = (unitName, val, html) => [{key: "n", label: unitName, val, html}]
    .concat(heads.map(x => ({key: "c" + x.i, label: x.name, num: true, val: o => o.L ? (o.L.lines.find(y => y.i === x.i) || {}).votes || 0 : null, html: o => o.L ? num((o.L.lines.find(y => y.i === x.i) || {}).votes || 0) : ""})))
    .concat([{key: "t", label: "All votes", num: true, val: o => o.L ? o.L.total : null, html: o => o.L ? num(o.L.total) : ""},
      {key: "s", label: "Reported", val: o => o.in ? 1 : 0, html: o => o.in ? "Yes" : `<span class="muted">Not yet</span>`}]);
  if (wide) {
    if (!e.c) return msg(`The state&rsquo;s file gives no ${esc(UW[0])} figures for this race.`);
    const rows = counties().filter(f => !r.c || r.c.includes(f)).map(f => { const ce = e.c[f];
      return {id: f, f, name: cName(f), L: ce ? lines(r, entryOf(r, e, ce.v, ce.x, ce.w)) : null, in: !!(ce && ce.u && ce.u[0]), u: ce && ce.u}; });
    const cols = cols0(capital(UW[0]), o => o.name, o => `<a href="#county=${esc(o.f)}">${esc(o.name)}</a>`);
    cols[cols.length - 1] = {key: "s", label: `${capital(UNIT)}s in`, num: true, val: o => o.u && o.u[1] ? o.u[0] / o.u[1] : null, html: o => o.u ? `${num(o.u[0])} of ${num(o.u[1])}` : ""};
    return Promise.resolve({rows, cols, opt: {page: 100, sort: [{key: "n", dir: "asc"}], count: rs => plural(rs.length, UW[0], UW[1])}});
  }
  return Promise.all([needIdx(), needKit()]).then(([idx]) => {
    const cs = (r.c || []).filter(c => idx.counties.some(x => x.id === c));
    const geoFile = c => { const meta = idx.counties.find(x => x.id === c); return MAP ? MAP.load(meta.file) : getJSON(BOOT.geo.base + meta.file + "?v=" + BOOT.geo.v); };
    return Promise.all(cs.map(c => Promise.all([geoFile(c), liveCounty(c, partOf(r)).catch(() => null)]).then(([g, f]) => [c, g, f])));
  }).then(list => {
    const rows = [];
    list.forEach(([c, g, f]) => g.objects.precincts.geometries.forEach(p => { if (!inArea(r, p.properties || {})) return;
      const row = f && ((f.p || {})[r.id] || {})[p.id];
      rows.push({id: c + ":" + p.id, c, name: (p.properties || {}).name || p.id, L: row ? lines(r, rowEntry(r, row)) : null, in: !!row}); }));
    const multi = new Set(rows.map(x => x.c)).size > 1;
    const cols = cols0(capital(UNIT), o => o.name, o => esc(o.name) + (multi ? ` <small class="muted">${esc(D.counties[o.c] || "")}</small>` : ""));
    return {rows, cols, opt: {page: 60, sort: [{key: "n", dir: "asc"}], count: rs => `${plural(rs.length, UNIT)}; ${num(rs.filter(x => x.in).length)} reported`}};
  }, () => ({msg: `<p class="held" style="padding:14px">The ${UNIT} figures could not be loaded just now.</p>`}));
}
function tableFor(r, wide) {
  const host = $("#ntbl"); if (!host) return;
  host._race = [r, wide];
  tableRows(r, wide).then(t => {
    if (!host.isConnected) return;
    NIGHTLIVE.ready(host);
    TABLES = TABLES.filter(T => T.host !== host);
    if (t.msg) { host.innerHTML = t.msg; return; }
    /* a table with the same columns as before keeps the reader's sort */
    TABLES.push({host, cols: t.cols, race: r, wide, build: () => tableRows(r, wide).then(x => x.rows ? x : null),
      grid: gridTable(host, Object.assign({rows: t.rows, cols: t.cols, rowId: x => x.id}, t.opt))});
  });
}
/* New figures into a table on show: in place when its order under the reader's sort stays the same, else behind "New
   figures are ready: show them" (a list must not re-sort under the reader). The comparison is the table's own. */
function orderOf(rows, sort, cols) {
  const col = Object.fromEntries(cols.map(c => [c.key, c]));
  const cmp = (a, b) => { for (const s of sort) { const c = col[s.key]; if (!c) continue; const x = c.val(a), y = c.val(b);
      if (x == null || y == null) { if (x == null && y == null) continue; return x == null ? 1 : -1; }
      const d = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "en", {numeric: true, sensitivity: "base"});
      if (d) return s.dir === "desc" ? -d : d; } return 0; };
  return (sort.length ? rows.slice().sort(cmp) : rows).map(x => x.id).join("\n");
}
function refreshTables() {
  TABLES = TABLES.filter(T => T.host.isConnected);
  TABLES.forEach(T => Promise.resolve(T.build()).then(nu => {
    if (!nu || !T.host.isConnected || !TABLES.includes(T)) return;
    if (nu.cols && nu.cols.map(c => c.key + c.label).join("|") !== T.cols.map(c => c.key + c.label).join("|")) { NIGHTLIVE.ready(T.host, () => tableFor(T.race, T.wide)); return; }      /* other candidates head the columns now */
    const rows = nu.rows || nu, cur = T.grid.rows, by = new Map(rows.map(x => [x.id, x]));
    const same = cur.length === rows.length && cur.every(x => by.has(x.id));
    const apply = () => { if (same) { cur.forEach(x => Object.assign(x, by.get(x.id))); T.grid.redraw(); } else T.grid.setRows(rows); };
    if (same && orderOf(cur.map(x => by.get(x.id)), T.grid.sort, T.cols) === cur.map(x => x.id).join("\n")) { NIGHTLIVE.ready(T.host); apply(); }
    else NIGHTLIVE.ready(T.host, apply);
  }, () => {}));
}

/* ---------- new figures, put in place (NIGHTLIVE calls refresh for a new snapshot, refreshStatus after every other look) ----------
   Nothing is drawn again from the top: each result, row, count and table on show is swapped for its new self, the map
   keeps its view and repaints, the side panel keeps what the reader picked, open folds stay open and the reader's focus
   stays where it was. */
const FOCUSABLE = "a[href],button,summary,select,input,[tabindex]";
function swap(el, html) {
  const a = document.activeElement, inside = !!a && a !== document.body && el.contains(a);
  const k = inside ? [...el.querySelectorAll(FOCUSABLE)].indexOf(a) : -1, open = [...el.querySelectorAll("details")].map(d => d.open);
  const t = document.createElement("template"); t.innerHTML = html.trim();
  const n = t.content.firstElementChild; if (!n) return el;
  [...n.querySelectorAll("details")].forEach((d, i) => { if (open[i] != null) d.open = open[i]; });
  el.replaceWith(n); n._h = html;
  if (inside) { const f = k < 0 ? n : [...n.querySelectorAll(FOCUSABLE)][k] || n; try { f.focus({preventScroll: true}); } catch (e) {} }
  return n;
}
function refreshStatus() {
  $$("[data-nstat]").forEach(el => { const h = statusHTML(); if (el._h !== h) swap(el, h); });
}
function refresh() {
  if (!D) return;
  if (LIVE.rehearsal) { const b = $("#nreh"); if (b) b.innerHTML = `<b>Rehearsal:</b> replayed figures from ${esc((LIVE.now && LIVE.now.label) || "a past election")}. Not 2026 results.`; }
  refreshStatus();
  $$("[data-res]", app).forEach(el => { const r = raceAt(el.dataset.res); if (r && !el.closest("#nside")) swap(el, resultHTML(r, JSON.parse(el.dataset.o || "{}"))); });
  $$("[data-row]", app).forEach(el => { const r = raceAt(el.dataset.row); if (r) swap(el, rowHTML(r, JSON.parse(el.dataset.o || "{}"))); });
  $$("[data-crep]", app).forEach(el => { el.outerHTML = countyRep(el.dataset.crep); });
  $$("[data-clede]", app).forEach(el => { el.outerHTML = countyLede(el.dataset.clede); });
  const lg = $("#nlegend"); if (lg && SPEC) lg.innerHTML = legendHTML();
  if (MAP) MAP.redraw();
  const sd = $("#nside");
  if (sd && SPEC) { sd.setAttribute("aria-live", "off");      /* the one announcement is NIGHTLIVE's; the panel is not read out again */
    if (LASTPICK) picked(LASTPICK, true); else side(sideHome()); }
  if (MINE && $("#yres")) fillMine(MINE);
  const h = $("#ntbl"); if (h && h._race && !TABLES.some(T => T.host === h)) tableFor(h._race[0], h._race[1]);
  refreshTables();
}

/* ---------- the address ---------- */
function route() {
  if (MAP) { MAP.destroy(); MAP = null; }
  SPEC = null; LASTPICK = null; TABLES = [];
  const h = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (!h || h === "mine" || h === "yours") home(h);
  else if (h === "statewide") statewide();
  else if (h === "legislature") legislature();
  else if (h === "courts") courts();
  else if (h === "counties") countyIndex();
  else if (h.startsWith("county=")) countyPage(h.slice(7).replace(/\D/g, "").padStart(3, "0").slice(-3));
  else if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("map=")) home(h.slice(4));
  else home();
  if (!/^(mine|yours|counties)$/.test(h)) window.scrollTo(0, 0);
  try { app.focus({preventScroll: true}); } catch (e) {}
}
if (LIVE.rehearsal) { const b = $("#nreh"); if (b) b.hidden = false; }
Promise.all([getJSON(BOOT.data), liveFetch()]).then(([d]) => {
  D = d; D.races.forEach(r => { R[r.id] = r; if (r.k === "state_house") LEGR.house[r.d] = r; else if (r.k === "state_senate") LEGR.senate[r.d] = r; });
  liveReady(id => R[id]);
  if (LIVE.rehearsal) { const b = $("#nreh"); if (b) b.innerHTML = `<b>Rehearsal:</b> replayed figures from ${esc((LIVE.now && LIVE.now.label) || "a past election")}. Not 2026 results.`; }
  route();
  addEventListener("hashchange", route);
  document.addEventListener("night:look", () => { if (MAP) MAP.redraw(); const l = $("#nlegend"); if (l) l.innerHTML = legendHTML(); });
  NIGHTLIVE.start({onNew: refresh, onTick: refreshStatus});
}, () => { app.innerHTML = `<p class="nempty">${NM}&rsquo;s races could not be loaded. Check your connection and open the page again.</p>`; });
"""


def page_html(code, P, boot, practice, prefix, generated, version):
    """The page's shell, every borrowed part in place."""
    st = boot["st"]
    nav = "".join(f'<a href="{h}">{w}</a>' for h, w in (("#statewide", "Statewide"), ("#legislature", "Legislature"), ("#courts", "Judges"),
                                                          ("#counties", "Counties"), ("#mine", "Your ballot")))
    record = boot["links"].get("record")
    foot = " &middot; ".join(x for x in (
        f'<a href="{boot["links"]["night"]}">Election Night: every state</a>',
        f'<a href="{boot["links"]["ballot"]}">{st["name"]} on the ballot</a>',
        f'<a href="{record}">{st["name"]}&rsquo;s Legislature on the record side</a>' if record else "",
        f'<a href="{prefix}">The Civic Archive front door</a>') if x)
    desc = (f"{st['name']}'s official results on election night, race by race, from the governor to the school boards, "
            f"as the {st['agency']} posts them, each figure with its time.")
    lc = code.lower()
    page = PAGE
    for key, value in (("__CSS__", P["CSS"]), ("__BALLOT_CSS__", P["BALLOT_CSS"]), ("__NIGHT_CSS__", N.NIGHT_CSS), ("__FONTS__", N.fonts_css()),
                       ("__HEADSCRIPT__", N.head_script()), ("__CHANGELOG__", P["CHANGELOG"]), ("__GRID__", P["GRID"]), ("__SOURCEFOLD__", P["SOURCEFOLD"]),
                       ("__NIGHT_JS__", N.NIGHT_JS), ("__PAGE_JS__", PAGE_JS),
                       ("__TOPBAR__", N.top_bar(f"Election Night: {st['name']}", nav, door_href=boot["links"]["night"])),
                       ("__CLBOX__", N.changelog_box()),
                       ("__BANNER__", f'<div class="nbanner" role="note"><b>{PRACTICE_LABEL.split(".")[0]}.</b> Not 2026 results.</div>\n' if practice else ""),
                       ("__BRAND__", N.brand_tags(boot["links"]["icons"], f"Election Night: {st['name']} · The Civic Archive", desc, "results.png", f"night/{lc}/")),
                       ("__FOOTLINKS__", foot)):
        if page.count(key) != 1:
            raise SystemExit(f"build_night_state: the page should hold {key} exactly once (it holds it {page.count(key)} times)")
        page = page.replace(key, value)
    page = (page.replace("__NAME__", N_esc(st["name"])).replace("__DESC__", N_esc(desc)).replace("__AGENCY__", "the " + N_esc(st["agency"]))
            .replace("__VERSION__", N_esc(version)).replace("__GENERATED__", generated))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    return page


def N_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build(dev_root, version=None, practice=None, say=print, code="MN"):
    """One state's Night page (and, with practice, its practice figures). Returns {path written: bytes}."""
    from build_ballot_state_dev import copy_fonts, slim_js, slim_page, SlimError, write_if_changed
    from build_site_dev import read_changelog
    code = code.upper()
    if code not in STATES:
        raise SystemExit(f"build_night_state: no Night page is set up for {code} yet (STATES holds {', '.join(sorted(STATES))}).")
    lc, S = code.lower(), STATES[code]
    dev_root = os.path.abspath(dev_root)
    changelog = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = version or ((changelog[0].get("version") if changelog else "") or "")
    if practice:
        root = N.practice_root(dev_root)
        out_dir = os.path.join(root, "night", lc)
        prefix, live, geo_base, icons = "../../../dev/", "../../night-live/", f"../../../dev/ballot/{lc}/geo/", "../../../dev/"
        night_home = "../../../dev/night/"
    else:
        out_dir = os.path.join(dev_root, "night", lc)
        prefix, live, geo_base, icons, night_home = "../../", "../../../night-live/", f"../../ballot/{lc}/geo/", "../../", "../"
    say(f"Election Night, {code}{' (practice)' if practice else ''}: building {os.path.relpath(out_dir, HERE)}")
    doc, geo, words = races_for(code, say)
    if not geo:
        raise SystemExit(f"build_night_state: {code} has no map files (ballot_geo/{lc}/); its Night page draws its results on them.")
    g = ballot_geo(dev_root, code, geo)
    written = {}
    races_text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    bad = N.kit_names(races_text)
    if bad:
        raise SystemExit(f"build_night_state: the races file would name the kit's own files: {bad}")
    write_if_changed(os.path.join(out_dir, "data", "races.json"), races_text)
    written[os.path.join(out_dir, "data", "races.json")] = len(races_text.encode("utf-8"))
    kit = N.mapkit()
    try:
        kit = slim_js(kit)
    except SlimError as e:
        say(f"  note: the map's script was written with its comments ({e})")
    write_if_changed(os.path.join(out_dir, "mapkit.js"), kit)
    written[os.path.join(out_dir, "mapkit.js")] = len(kit.encode("utf-8"))
    copy_fonts(out_dir)
    polls = poll_hours(code, S)
    record = os.path.exists(os.path.join(dev_root, lc, "index.html"))
    st = {"code": code, "lc": lc, "name": place(code)["name"], "agency": S["agency"], "results": S["results"],
          "polls": polls, "pollsNote": S.get("polls_note", ""), "cert": S["cert"], "rules": S["rules"], "hand": 1 if S.get("hand") else 0, "unit": S.get("unit", "precinct"),
          "upT": words.get("upT") or "Senate", "loT": words.get("loT") or "House", "counting": registry_words(code), "uw": N.unit_words(code)}
    boot = {"st": st, "data": f"data/races.json?v={N.sha10(races_text)}", "kit": f"mapkit.js?v={N.sha10(kit)}",
            "geo": {"base": geo_base, **g}, "live": {"base": live, "dir": f"{lc}/", "fips": str(place(code).get("fips") or "")}, "changelog": changelog,
            "links": {"night": night_home, "ballot": f"{prefix}ballot/{lc}/", "ballotUS": f"{prefix}ballot/us/", "record": f"{prefix}{lc}/" if record else "",
                      "icons": icons}}
    summary = None
    if practice:
        boot["practice"] = {"label": PRACTICE_LABEL, "now": PRACTICE_NOW,
                            "source": {"agency": "Minnesota Secretary of State, on the Minnesota Geospatial Commons", "title": "General Election Results By Precinct 2024",
                                       "url": "https://gisdata.mn.gov/", "read": "2026-10-01"}}
        summary = practice_figures(code, doc, geo, os.path.join(N.practice_root(dev_root), "night-live"), say)
    P = N.parts()
    page = page_html(code, P, boot, practice, prefix, N.generated(), version)
    whole = len(page.encode("utf-8"))
    page = slim_page(page, f"Election Night {code}")
    page = N.quiet(page)
    checks = N.page_checks(f"night/{lc}/index.html", page, SHELL_LIMIT, say)
    if not practice and os.path.exists(os.path.join(dev_root, "shell", "rider.js")):
        i = page.rfind("</body>")
        page = page[:i] + RIDER + page[i:]      # the companion and the page guide, as build_shell.ride() puts them on every page with its own top bar
    write_if_changed(os.path.join(out_dir, "index.html"), page)
    written[os.path.join(out_dir, "index.html")] = checks["bytes"]
    say(f"  wrote index.html {checks['bytes'] / 1e3:,.0f} KB ({whole / 1e3:,.0f} KB before slimming; budget {SHELL_LIMIT / 1e3:,.0f} KB), "
        f"data/races.json {written[os.path.join(out_dir, 'data', 'races.json')] / 1e3:,.0f} KB, mapkit.js {written[os.path.join(out_dir, 'mapkit.js')] / 1e3:,.0f} KB; "
        f"the map's lines from {geo_base} (cache key {g['v']})")
    if summary:
        live_root = os.path.join(N.practice_root(dev_root), "night-live")
        snap = os.path.join(live_root, *summary["sizes"]["_base"].strip("/").split("/"))
        for k, v in summary["sizes"].items():
            if k != "_base":
                written[os.path.join(snap, *k.split("/")) if k != "now.json" else os.path.join(live_root, k)] = v
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="mn", help="the state (only Minnesota is set up so far)")
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's root (default site/dev)")
    ap.add_argument("--practice", action="store_true", help="practice figures, into site/practice/ (never published)")
    a = ap.parse_args()
    build(a.root, practice="2024" if a.practice else None, code=a.state)


if __name__ == "__main__":
    main()
