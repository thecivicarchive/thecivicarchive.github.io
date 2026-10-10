#!/usr/bin/env python3
"""
build_night_forecasts.py - Election Night's forecasts page: site/dev/night/forecasts/.

    python build_night_forecasts.py                 (into site/dev/night/forecasts/)
    python build_night_forecasts.py --practice      (the same page into site/practice/night/forecasts/; never published)

Every race the model has a forecast for: each candidate's chance (of winning, or of a seat where several are elected)
and a likely range for their share of the vote, always labelled Analysis; the trend across every run of the model, with
the start of each new method version marked; the inputs; the three blind spots (count order, roll-off, ballot position)
in plain words; the backtest report; the method. Routes (after #):
  ""                 the states with forecasts, the closest races in the model, the polls-open notice where polls are open
  #state=MN          one state's forecasts, by level, with a search and two orders
  #race=<race id>    one race: chances and ranges, the trend, the inputs, the blind spots, links to its results and ballot
  #track             the backtest report (and, after November 3, how each forecast did against the certified count)
  #method            how a forecast is made

What it reads, read only: the model's runs, through election/model/runs.py (page_json, history, track_json: the same
files the updater publishes as live figures, fc/<code>.json and h/<code>/<race>.json, so the page reads the static copy
and the live copy alike); the races and candidates as filed (build_night_state.races_for for Minnesota,
build_night_us.all_races for every other state); the poll hours file and the registry. Only states that have runs on
file are shown; nothing is said of the rest.

What it writes: index.html (the shell), data/fc/<code>.json (the forecasts, as runs.page_json gives them), data/meta/
<code>.json (each race's title, place, level and its candidates' parties, the blind spots' words, the inputs),
data/h/<code>/<0-f>.json (each race's run history, in 16 files a state), data/track/<code>.json (the backtest report),
fonts/.

FORECASTS_PUBLIC (in election/model/__init__.py, read by the updater too): the first public forecasts wait for John's yes
(ARCHITECTURE.md 5.3, phase 5). Until it is set True, a
build into site/dev writes the page with the method and the track record only, and removes any forecast files an earlier
build left there; a practice build (site/practice, never published) always shows the forecasts.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import night_common as N                                                  # noqa: E402
from states.places import place                                           # noqa: E402

GENERAL = "2026-11-03"
from election.model import FORECASTS_PUBLIC                                # noqa: E402  John's yes, kept in one place for this page and the updater
SHELL_LIMIT = 380_000            # the page's own shell (index.html)
FC_BUDGET = 300_000              # a state's forecasts file (ARCHITECTURE.md 2.6)
STATIC_BUDGET = 25_000_000       # every Night static file together (ARCHITECTURE.md 2.6)
BUCKETS = 16                     # each state's run history is split into this many files
PRACTICE_LABEL = "Practice page, not published."
NASS = "https://www.nass.org/can-I-vote"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def bucket(rid):
    """Which of a state's history files holds a race (the page works it out the same way)."""
    h = 0
    for ch in rid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % BUCKETS


def quiet_say(*a, **k):
    pass


# ============================================================ the model's runs

def model_db():
    from election.model import DB
    return DB


def model_states(db):
    """(states with a pre-election or night run on file, states with a backtest on file), each a sorted list of codes."""
    if not os.path.exists(db):
        return [], []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        def one(q):
            try:
                return sorted(s for (s,) in con.execute(q) if s and re.fullmatch(r"[A-Z]{2}", s))
            except sqlite3.Error:
                return []
        fc = one("SELECT DISTINCT state FROM runs WHERE kind IN ('pre', 'live') AND rehearsal = 0 AND ended IS NOT NULL")
        bt = one("SELECT DISTINCT state FROM runs WHERE kind = 'backtest' AND ended IS NOT NULL")
    finally:
        con.close()
    return fc, bt


KIND_WORDS = {"official": "Official record", "secondary": "Secondary source", "party": "A party's own publication",
              "poll": "Polls by members of AAPOR's Transparency Initiative only", "derived": "Worked out here", "census": "Census Bureau figures", "prior": "A starting assumption"}


def plain(text):
    """Words bound for the page: any name of the kit's files taken out with the brackets around it, and nothing that
    reads like an address on a computer."""
    t = re.sub(r"\s*\([^()]*\b[\w./\\-]+\.(?:py|sqlite|bat|ps1|js|json|md)\b[^()]*\)", "", str(text or ""))
    t = re.sub(r"\b[\w./\\-]+\.(?:py|sqlite|bat|ps1|js|json|md)\b", "", t)
    t = re.sub(r"[A-Za-z]:\\\S*", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;")
    return t[:1].upper() + t[1:] if t else ""


def run_inputs(db, code):
    """The newest public run's inputs, in plain words: [[what it is, its kind, as of, the first 12 of its SHA-256]]."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT run, note FROM runs WHERE state = ? AND kind IN ('pre', 'live') AND rehearsal = 0 AND ended IS NOT NULL "
                          "ORDER BY started DESC, run DESC LIMIT 1", (code,)).fetchone()
        if not row:
            return []
        out = []
        for name, note, sha, as_of, kind in con.execute("SELECT input, note, sha256, as_of, kind FROM run_inputs WHERE run = ? ORDER BY kind, input", (row[0],)):
            if kind == "frame":
                continue
            if name == "params":
                words = "The model's settings, sized by its backtests on past elections"
            elif name == "polls-us":
                words = "Polls of the U.S. Senate races in every state, to gauge the year's mood"
            elif re.fullmatch(r"polls-[a-z]{2}", name or ""):
                words = f"Polls of {place(name[-2:].upper())['name']}'s statewide races"
            else:
                words = plain(note) or plain(name.replace("-", " "))
            words = re.sub(r"\s*\(read only\)", "", words)
            if not words or N.kit_names(words):
                continue
            out.append([words, KIND_WORDS.get(kind, plain(kind or "")), (as_of or "")[:10] if re.match(r"\d{4}-\d\d-\d\d", str(as_of or "")) else "",
                        (sha or "")[:12]])
        return out
    finally:
        con.close()


# ============================================================ the races, as filed

LV_ORDER = ["federal", "statewide", "legislature", "court", "county", "soil_water", "city", "township", "school", "hospital", "other"]


def mn_title(r):
    lv, k, o = r.get("lv"), r.get("k"), r.get("o") or ""
    if lv == "federal":
        if k == "us_senate":
            return "U.S. Senator" + (" (special election)" if r.get("sp") else "")
        return f"U.S. Representative, District {r.get('d')}"
    if lv == "legislature":
        return f"{o}, {r.get('j')}"
    t = o
    if lv == "court":
        return f"{t}, Seat {r['s']}" if r.get("s") else t
    d, s = r.get("d"), r.get("s")
    if d:
        t += f", District {d}" if re.fullmatch(r"\d+", str(d)) else f", {d}"
    if s and not re.fullmatch(r"(?i)at large", str(s)):
        t += f", Seat {s}" if re.fullmatch(r"(?i)[A-Z0-9]{1,3}", str(s)) else f", {s}"
    return t + (" (special election)" if r.get("sp") else "")


def mn_where(r, name):
    lv = r.get("lv")
    if lv == "federal":
        return name if r.get("k") == "us_senate" else ""
    if lv == "statewide":
        return name
    if lv == "legislature":
        return ""
    if lv == "court":
        return "Statewide" if r.get("j") == name else r.get("j") or ""
    return r.get("j") or ""


_US = None


def us_races():
    global _US
    if _US is None:
        import build_night_us as U
        fed, sw = U.all_races(quiet_say)
        _US = fed + sw
    return _US


def races_of(code):
    """{race id: {lv, k, title, where, pt, cs: [[name as filed, party (short), party code]], seats}} for one state."""
    name = place(code)["name"]
    out = {}
    if code == "MN":
        import build_night_state as S
        doc, _geo, _w = S.races_for(code, quiet_say)
        short = doc.get("pshort") or {}
        for r in doc["races"]:
            pt = 1 if r.get("pt") else 0
            cs = [[c[0], short.get(c[1], c[1]) if pt and len(c) > 1 else "", (c[2] if pt and len(c) > 2 else "")] for c in r.get("cs") or []]
            out[r["id"]] = {"lv": r.get("lv") or "other", "k": r.get("k") or "", "title": mn_title(r), "where": mn_where(r, name), "pt": pt, "cs": cs,
                            "seats": r.get("n") or 1}
        return out
    for r in us_races():
        if r.get("st") != code:
            continue
        k = r.get("k") or ""
        if k == "us_senate":
            title, where, lv = "U.S. Senator" + (" (special election)" if r.get("sp") else ""), name, "federal"
        elif k == "us_house":
            d = str(r.get("d") or "")
            title = "U.S. Representative, at large" if d in ("", "0", "00") else f"U.S. Representative, District {d}"
            where, lv = "", "federal"
        else:
            title, where, lv = r.get("o") or "Statewide office", ("" if r.get("dx") else name), "statewide"
        pt = 1 if r.get("pt") else 0
        cs = [[c[0], (c[1] if pt and len(c) > 1 else ""), (c[2] if pt and len(c) > 2 else "")] for c in r.get("cs") or []]
        out[r["id"]] = {"lv": lv, "k": k, "title": title, "where": where, "pt": pt, "cs": cs, "seats": 1}
    return out


# ============================================================ races left out, and why

def left_title(rid, filed):
    """A left-out race's name as the page shows it: the ballot list's title, else read from its id."""
    r = filed.get(rid)
    if r:
        return r["title"] + (f" ({r['where']})" if r.get("where") and r["lv"] not in ("federal", "statewide") else "")
    m = re.fullmatch(r"\d{4}-[A-Z]{2}-H(\d+)", rid)
    if m:
        return "U.S. Representative, at large" if int(m.group(1)) == 0 else f"U.S. Representative, District {int(m.group(1))}"
    if re.fullmatch(r"\d{4}-[A-Z]{2}-S\d*", rid):
        return "U.S. Senator"
    return re.sub(r"^\d{4}-[A-Z]{2}-", "", rid).replace("-", " ")


def left_groups(left, filed):
    """[[the reason, in plain words, [race titles]]], the commonest reason first (the model's own planning says why)."""
    groups = {}
    for rid, why in sorted(left.items()):
        groups.setdefault(plain(why), []).append(left_title(rid, filed))
    return [[w, sorted(ts, key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])]
            for w, ts in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])) if w]


def nothing_to_forecast(shown):
    """The states the model planned and found nothing to forecast in: [{c, n, total, why: [[reason, races]]}]."""
    path = os.path.join(HERE, "election_cache", "model", "us", "left_out.json")
    try:
        with open(path, encoding="utf-8") as fh:
            states = json.load(fh).get("states") or {}
    except (OSError, ValueError):
        return []
    out = []
    for code, v in sorted(states.items()):
        left = (v or {}).get("left_out") or {}
        if code in shown or not left or not re.fullmatch(r"[A-Z]{2}", code):
            continue
        if any(k.startswith("forecast") and n for k, n in ((v.get("counts") or {}).items())):
            continue                  # it has races to forecast; its run is simply not on file yet
        why = {}
        for _rid, w in left.items():
            w = plain(w)
            why[w] = why.get(w, 0) + 1
        out.append({"c": code, "n": place(code)["name"], "total": len(left),
                    "why": [[w, n] for w, n in sorted(why.items(), key=lambda kv: (-kv[1], kv[0])) if w]})
    return out


# ============================================================ the three blind spots, in plain words

MN_ORDER = ("Minnesota reports each precinct once, when its whole count is in, absentee ballots included. Absentee ballots "
            "that reach the county after 3 p.m. on Election Day are added later, county by county, and each county posts how "
            "many it still has to count. The precincts that come in first may not be typical, so the model never assumes "
            "they are: it estimates the precincts still to come from their own past votes.")
MN_ROTATED = ("Minnesota rotates the order of names from precinct to precinct, so each candidate is printed first for about "
              "the same number of voters, and any edge for being listed first mostly cancels out across the race. The model "
              "works out each name's share of first places from the state's rotation rule; that is an estimate, because each "
              "county draws the starting order by lot and the draw is not on file.")
MN_TOWN = ("Town ballots list names alphabetically by surname, so the same name is printed first on every ballot in this "
           "race. Studies elsewhere found that being listed first is worth from 1 to 4 points in races like this; the model "
           "allows for an edge of that size, since Minnesota's own has not been measured.")
OTHER_POSITION = ("The order of names on this state's ballots is not measured here, so the model gives no candidate an "
                  "edge for being listed first.")
OTHER_ORDER = "Early figures often move: each state counts some kinds of ballots before others."

ROLL_KEYS = {"U.S. Senate": "the U.S. Senate race", "U.S. House": "their U.S. House race", "Governor": "the governor's race",
             "Attorney General": "the attorney general's race", "State Senate": "their state Senate race",
             "State House": "their state House race", "Judges": "the judges' races", "County commissioner": "their county commissioner race",
             "County offices": "their county offices", "Soil and water": "their soil and water races"}
ROLL_UNTESTED = ("Not every voter marks every race. How many skip races like this one has not been measured: no past "
                 "results for them are on file, so the model borrows the figures of county races.")
ROLL_GENERIC = "Not every voter marks every race. How many are likely to skip this one is part of the model's expected vote."


def roll_key(lv, k, have):
    want = None
    if lv == "federal":
        want = "U.S. Senate" if k == "us_senate" else "U.S. House"
    elif lv == "statewide":
        want = "Governor" if k == "governor" else "Attorney General"
    elif lv == "legislature":
        want = "State Senate" if k == "state_senate" else "State House"
    elif lv == "court":
        want = "Judges"
    elif lv == "county":
        want = "County commissioner" if "commissioner" in (k or "") else "County offices"
    elif lv == "soil_water":
        want = "Soil and water"
    if not want:
        return None
    hits = sorted((label for label in have if re.fullmatch(re.escape(want) + r" \d{4}", label)), reverse=True)
    return hits[0] if hits else None


def pct_words(x):
    p = round(x * 100)
    if x <= 0:
        return "none"
    return "under 1%" if p < 1 else f"{p}%"


def roll_sentence(label, rec, state_name):
    year = label[-4:]
    what = ROLL_KEYS.get(label[:-5], "races like this one")
    src = "official results" if str(rec.get("source") or "").startswith("official") else \
        "a secondary copy of the official results, from the MIT Election Data and Science Lab"
    m, lo, hi = rec.get("median") or 0, rec.get("p10") or 0, rec.get("p90") or 0
    s = (f"Not every voter marks every race. In {year} the typical {state_name} precinct saw {pct_words(m)} of its voters skip "
         f"{what}, and most precincts between {pct_words(lo)} and {pct_words(hi)} ({src}).")
    if m < 0.03:
        return s + " Few voters skip races like this one."
    return s + " The model expects about as many to skip this race, so fewer people decide it than decide the top of the ballot."


def blind_spots(code, races, track):
    """The words for each race's three blind spots: {"order": text, "roll": [sentences], "pos": [sentences]} and, for each
    race, the index of its roll-off and ballot-position sentence."""
    name = place(code)["name"]
    rolloff = ((track or {}).get("about") or {}).get("rolloff") or {}
    rolloff = {k: v for k, v in rolloff.items() if isinstance(v, dict) and re.fullmatch(r".+ \d{4}", k)}
    roll, pos, idx = [], [], {}

    def at(lst, s):
        if s not in lst:
            lst.append(s)
        return lst.index(s)
    for rid, r in races.items():
        if code == "MN":
            key = roll_key(r["lv"], r["k"], rolloff)
            rs = roll_sentence(key, rolloff[key], name) if key else (ROLL_UNTESTED if r["lv"] in ("city", "township", "school", "hospital", "other") else ROLL_GENERIC)
            ps = MN_TOWN if r["lv"] == "township" else MN_ROTATED
        else:
            rs, ps = ROLL_GENERIC, OTHER_POSITION
        idx[rid] = (at(roll, rs), at(pos, ps))
    if code == "MN":
        order = MN_ORDER
    else:
        # the state's own way of counting and what the night's model does about it (the model's own words, from the state's
        # registry note on its count order)
        from election.model import night_us as NU
        order = NU.order_words(code, NU.feed_gives_kinds(code)) or OTHER_ORDER
    for s in roll + pos + [order]:
        if N.kit_names(s):
            raise SystemExit(f"build_night_forecasts: a blind-spot sentence names the kit's own files: {N.kit_names(s)}")
    return {"order": order, "roll": roll, "pos": pos}, idx


# ============================================================ poll hours and links

def polls_of(code):
    import build_night_us as U
    try:
        with open(U.POLL_HOURS, encoding="utf-8") as fh:
            P = json.load(fh)
    except (OSError, ValueError):
        return {"z": []}
    return U.poll_words(code, P)


# ============================================================ the page

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Election Night: forecasts · The Civic Archive</title>
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
.nhero h1{font-family:var(--serif);font-weight:400;font-size:clamp(38px,6vw,72px);line-height:1;margin:10px 0 0;overflow-wrap:break-word}
.nhero .lede{color:var(--muted);max-width:68ch;font-size:clamp(15px,1.5vw,18px);margin:12px 0 0}
.nhero .bkick{font:700 12px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.fsub{font:700 16.5px var(--sans);margin:24px 0 0}
.draftnote{background:var(--brass-soft);color:var(--ink);padding:6px 16px;font:600 12.5px/1.4 var(--sans);text-align:center;border-bottom:1px solid var(--line)}
.draftnote a{color:inherit}
.nempty{border:1px dashed var(--line-strong);border-radius:14px;padding:12px 14px;color:var(--muted);font-size:14px;margin-top:12px;max-width:96ch}
.abox{border:1px solid var(--brass);border-left-width:5px;background:var(--surface);border-radius:14px;padding:12px 16px;margin-top:16px;max-width:96ch;font-size:14.5px;line-height:1.5}
.abox p{margin:6px 0 0}.abox p:first-child{margin-top:0}
.fsec{margin-top:30px}
.fsec>h2{font-family:var(--serif);font-weight:400;font-size:clamp(26px,3.2vw,36px);line-height:1.1;margin:0}
.fsec>p,.fsec .fp{font-size:14.5px;line-height:1.55;max-width:80ch;margin:8px 0 0}
.fsec>.sub{color:var(--muted);font-size:13.5px}
.fbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px}
.fbar input[type=search]{height:44px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 16px;font:500 15px var(--sans);flex:1 1 240px;min-width:0;max-width:100%}
.fbar input[type=search]:focus-visible,.fbar select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fchips{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.fchips button{all:unset;box-sizing:border-box;cursor:pointer;min-height:36px;padding:0 13px;border-radius:999px;border:1px solid var(--line-strong);font:600 13.5px var(--sans);color:var(--ink);background:var(--surface);display:inline-flex;align-items:center;gap:6px}
.fchips button small{color:var(--muted);font-weight:500}
.fchips button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.fchips button[aria-pressed="true"] small{color:inherit;opacity:.8}
.fchips button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (pointer:coarse){.fchips button{min-height:44px}}
.fcount{font-size:13px;color:var(--muted);margin:10px 0 0}
.fmore{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;min-height:44px;margin-top:12px;padding:0 18px;border-radius:999px;border:1px solid var(--line-strong);font:700 14px var(--sans);color:var(--ink);background:var(--surface)}
.fmore:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nrow .l .nsw{vertical-align:-1px}
.fcards{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr));margin-top:14px}
.fcards .lvcard small{display:block;font-size:12.5px;color:var(--muted);margin-top:6px}
.eqnames{list-style:none;margin:0;padding:0;display:grid;gap:6px 18px;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr));font-weight:600;font-size:14.5px}
.eqnames small{font-weight:400;color:var(--muted)}
.eqline{font-size:14.5px;margin:12px 0 0}
.ln .rg{grid-column:1/-1;font-size:12.5px;color:var(--muted);margin-top:-1px}
.ln .fig b{font-size:16px}
.fmeta{font-size:13px;color:var(--muted);margin:10px 0 0;line-height:1.5;max-width:96ch}
.fmeta b{color:var(--ink);font-weight:600}
.fearly{border:1px solid var(--line);border-left:5px solid var(--brass);background:var(--surface);border-radius:12px;padding:9px 14px;margin-top:12px;font-size:14px;max-width:96ch}
.fgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));margin-top:14px}
.fcard{border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:12px 16px;min-width:0}
.fcard h3{font:700 15.5px var(--sans);margin:0}
.fcard p{font-size:14px;line-height:1.5;margin:6px 0 0}
.fcard .kick{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.trend{margin-top:14px;border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:12px 14px;max-width:820px}
.trend svg{display:block;width:100%;height:auto;overflow:visible}
.trend .ax{stroke:var(--line);stroke-width:1;vector-effect:non-scaling-stroke}
.trend .seg{stroke:var(--ink);stroke-width:1.2;stroke-dasharray:4 4;vector-effect:non-scaling-stroke;opacity:.7}
.trend text{font:var(--fs,12px) var(--sans);fill:var(--muted)}
.trend text.sl{fill:var(--ink);font-weight:600}
.trend .tl{fill:none;stroke-width:2.6;vector-effect:non-scaling-stroke;stroke-linejoin:round;stroke-linecap:round}
.trend .tl.p-hatch{stroke-dasharray:7 3}.trend .tl.p-dots{stroke-dasharray:1.5 4}.trend .tl.p-cross{stroke-dasharray:10 3 2 3}.trend .tl.p-rows{stroke-dasharray:4 2}.trend .tl.p-cols{stroke-dasharray:12 5}.trend .tl.p-back{stroke-dasharray:2 2}
.trend .lg{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--muted);margin-top:8px}
.trend .lg span{display:inline-flex;align-items:center;gap:6px}
.trend .lg .mk{width:14px;height:14px;flex:none;overflow:visible}
.ftbl{width:100%;min-width:560px;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.ftbl th,.ftbl td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}
.ftbl th:first-child,.ftbl td:first-child{text-align:left}
.ftbl thead th{font:700 12px var(--sans);letter-spacing:.04em;color:var(--muted)}
.ftbl caption{text-align:left;font-size:13px;color:var(--muted);padding:8px 10px}
.calsvg{display:block;width:100%;max-width:340px;height:auto;margin-top:10px;overflow:visible}
.calsvg .ax{stroke:var(--line);stroke-width:1}
.calsvg .dg{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4}
.calsvg circle{fill:var(--brass);stroke:var(--ink);stroke-width:.8}
.calsvg text{font:var(--fs,12px) var(--sans);fill:var(--muted)}
.inlist{margin:10px 0 0;padding:0;list-style:none;display:grid;gap:8px;max-width:96ch}
.inlist li{font-size:14px;line-height:1.45;border-bottom:1px dashed var(--line);padding-bottom:7px}
.inlist small{display:block;color:var(--muted);font-size:12.5px}
.flinks{display:flex;gap:6px 18px;flex-wrap:wrap;margin-top:16px;font-size:14px}
.flinks a{color:var(--accent-ink);font-weight:600;min-height:32px;display:inline-flex;align-items:center}
</style>
</head>
<body>
__BANNER__<div class="nbanner" id="nreh" hidden></div>
<div class="draftnote">A draft for feedback, not the finished site. <a href="https://thecivicarchive.github.io/">Go to the live site</a></div>
__TOPBAR__
<main id="app" class="bwrap" tabindex="-1"><p class="loading muted">Loading the forecasts&hellip;</p></main>
<footer class="bwrap bfoot">
  <p>Election Night, from The Civic Archive v__VERSION__. Generated on __GENERATED__. Every forecast on this page is Analysis: a computer model&rsquo;s estimate, never a result. The official count decides, and each state&rsquo;s own results are the authority.</p>
  <p>__FOOTLINKS__</p>
</footer>
__CLBOX__
<script>
const BOOT = __BOOT__;
const CODE = "";
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
/* ===== parts shared with the rest of the site (taken from their pages when this page is built) ===== */
__CHANGELOG__
/* ===== end of the shared parts ===== */
__NIGHT_JS__
__PAGE_JS__
</script>
</body>
</html>
"""

PAGE_JS = r"""
/* ---------- Election Night: the forecasts ---------- */
const app = $("#app"), FC = {}, META = {}, TRACK = {}, HIST = {}, FCLIVE = {seq: null, used: {}};
const SBY = Object.fromEntries(BOOT.states.map(s => [s.c, s]));
const getJSON = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
const LVW = {federal: "Congress", statewide: "Statewide offices", legislature: "The Legislature", court: "Judges", county: "County offices",
  soil_water: "Soil and water", city: "Cities", township: "Townships", school: "School districts", hospital: "Hospital districts", other: "Other districts"};
const LVO = ["federal", "statewide", "legislature", "court", "county", "soil_water", "city", "township", "school", "hospital", "other"];
const KINDW = {pre: "before Election Day", live: "on election night", replay: "in a replay", backtest: "in a backtest"};
const ANALYSIS = `<span class="tag analysis">Analysis</span>`;
const ABOUT_LINE = "A computer model&rsquo;s estimate from past official results, Census figures, polls by members of AAPOR&rsquo;s Transparency Initiative, campaign money on file and the votes counted so far, each where the model uses it (every race lists its own inputs). Not a result: the official count decides.";
const chanceText = c => c === ">99" ? "over 99%" : c === "<1" ? "under 1%" : (c == null || c === "" ? "" : `${c}%`);
const chanceNum = c => c === ">99" ? 99.5 : c === "<1" ? 0.5 : (+c || 0);
const shareText = t => t == null ? "" : t <= 0 ? "under 0.1%" : t >= 1000 ? "over 99.9%" : `${(t / 10).toFixed(1)}%`;
const rangeText = (lo, hi) => `${shareText(lo)} to ${shareText(hi)}`;
const stateOfRace = rid => (/^\d{4}-([A-Z]{2})-/.exec(rid) || [])[1] || "";
const hbucket = rid => { let h = 0; for (let i = 0; i < rid.length; i++) h = (h * 31 + rid.charCodeAt(i)) >>> 0; return h % BOOT.buckets; };
/* a count of voters to two significant figures; an end of a range is rounded outward rather than onto the middle
   estimate, so "about 200 (likely 100 to 200)" never happens unless the two really are equal */
const sigStep = n => Math.pow(10, Math.max(0, Math.floor(Math.log10(Math.max(1, Math.abs(n)))) - 1));
const sig2 = n => { const s = sigStep(n); return Math.round(n / s) * s; };
function votersText(v) {
  const mid = sig2(v[1]); let lo = sig2(v[0]), hi = sig2(v[2]);
  if (lo >= mid && v[0] < v[1]) lo = Math.floor(v[0] / sigStep(v[0])) * sigStep(v[0]);
  if (hi <= mid && v[2] > v[1]) hi = Math.ceil(v[2] / sigStep(v[2])) * sigStep(v[2]);
  if (lo >= mid && v[0] < v[1]) lo = Math.floor(v[0]);
  if (hi <= mid && v[2] > v[1]) hi = Math.ceil(v[2]);
  return `The model expects about <b>${num(mid)}</b> people to vote in this race (likely ${num(lo)} to ${num(hi)}).`;
}
/* the races the model leaves out, and why, in folds by reason */
function leftHTML(groups, c) {
  if (!groups || !groups.length) return "";
  const n = groups.reduce((a, g) => a + g[1].length, 0);
  return `<details class="nfold"><summary>${plural(n, "race")} left out of the model, and why</summary>` + groups.map(([why, ts]) =>
    `<p class="fp"><b>${esc(why)}</b></p><p class="fmeta">${ts.map(esc).join("; ")}.</p>`).join("") + `</details>`;
}
let TOKEN = 0, TRENDNOW = null, TRENDW = 0;
/* the trend is drawn at the width it is shown at, so that its 12px type stays 12px on a phone */
document.addEventListener("night:look", () => { const el = $("#ftrend"); if (el && TRENDNOW) el.innerHTML = trendHTML(TRENDNOW[0], TRENDNOW[1]); fitLabels(document); });
addEventListener("resize", () => { clearTimeout(TRENDW); TRENDW = setTimeout(() => { const el = $("#ftrend"); if (el && TRENDNOW) el.innerHTML = trendHTML(TRENDNOW[0], TRENDNOW[1]); fitLabels(document); }, 200); });

/* ---------- loading a state's forecasts (the live copy once the updater publishes one) ---------- */
function loadState(c) {
  const s = SBY[c]; if (!s) return Promise.reject(new Error("no state"));
  return Promise.all([FC[c] ? null : getJSON(s.fc).then(d => { if (!FC[c]) FC[c] = d; }), META[c] ? null : getJSON(s.meta).then(d => { META[c] = d; })]);
}
const loadAll = () => Promise.all(BOOT.states.map(s => loadState(s.c)));
function metaOf(rid) {
  const c = stateOfRace(rid), M = META[c]; if (!M) return null;
  const e = M.r[rid.slice(M.pre.length)] || M.r[rid]; if (!e) return null;
  return {lv: e[0], title: e[1], where: e[2], pt: e[3], cs: e[4], ri: e[5], pi: e[6], seats: e[7] || 1};
}
function fcOf(rid) {
  const c = stateOfRace(rid), d = FC[c]; if (!d) return null;
  const pre = d.pre || "", f = d.r[rid.startsWith(pre) ? rid.slice(pre.length) : rid] || d.r[rid];
  return f ? {d, f} : null;
}
function raceIds(c) {      /* every race with a forecast, as a full race id, and with its title on file */
  const d = FC[c]; if (!d) return [];
  return Object.keys(d.r).map(k => k.startsWith("20") && /^\d{4}-[A-Z]{2}-/.test(k) ? k : (d.pre || "") + k).filter(rid => metaOf(rid));
}
/* each candidate's line: name, party, chance, median and range, colour (a party's in a partisan race; a neutral tone in
   ballot order otherwise) and pattern */
function cands(rid) {
  const F = fcOf(rid), m = metaOf(rid); if (!F || !m) return null;
  const f = F.f, eq = Array.isArray(f.eq) ? f.eq : null, cs = m.cs || [];
  const keys = cs.map(x => nameKey(x[0])), used = new Set();
  const L = (f.c || []).map((row, k) => {
    const nk = nameKey(row[0]); let i = keys.findIndex((x, j) => !used.has(j) && x === nk); if (i >= 0) used.add(i);
    const cand = cs[i] || [row[0], "", ""], pos = i >= 0 ? i : cs.length + k;
    const pc = m.pt ? (PCODE.includes(cand[2]) ? cand[2] : "O") : "";
    const v = eq || row.slice(1);
    return {name: row[0], party: m.pt ? cand[1] || "" : "", chance: v[0], med: v[1], lo: v[2], hi: v[3],
      c: m.pt ? `var(--p${pc})` : `var(--n${pos % 6 + 1})`, p: m.pt ? PPAT[pc] : NPAT[pos % NPAT.length]};
  });
  return {f, d: F.d, m, L, eq: !!eq, seats: f.s || m.seats || 1};
}
const topGap = X => X && !X.eq && X.seats === 1 && X.L.length > 1 ? Math.abs(chanceNum(X.L[0].chance) - 50) : 99;

/* ---------- the live copy: now.json every 2 minutes while the page is visible, then each shown state's forecasts file
   from that one snapshot (never two snapshots mixed); the static copy stays until then ---------- */
function fcGet() {
  const root = liveRoot();
  return fetch(root + "now.json", {cache: "no-store"}).then(r => { if (!r.ok) throw new Error("now " + r.status); return r.json(); }).then(now => {
    if (!now || now.v !== 1) throw new Error("now unreadable");
    if (!now.fc || !now.base) return {now, none: 1};
    if (FCLIVE.seq === now.seq) return {now, same: 1};
    const base = root + now.base;
    return Promise.all(BOOT.states.map(s => fetch(base + "fc/" + s.lc + ".json", {cache: "force-cache"}).then(r => r.ok ? r.json() : null, () => null)))
      .then(docs => ({now, docs, seq: now.seq}));
  });
}
function fcCommit(g) {
  LIVE.now = g.now;
  if (g.none || g.same) return false;
  let fresh = false;
  BOOT.states.forEach((s, i) => { const doc = g.docs[i];
    if (doc && doc.v === 1 && doc.r && (!FC[s.c] || !FC[s.c].t || doc.t >= FC[s.c].t)) { FC[s.c] = doc; FCLIVE.used[s.c] = 1; fresh = true; } });
  FCLIVE.seq = g.seq;
  return fresh;
}
const newestRun = () => BOOT.states.map(s => FC[s.c] && FC[s.c].t).filter(Boolean).sort().pop();
function pausedHTML() {
  if (!Object.keys(FCLIVE.used).length) return "";
  const p = livePause(); if (!p) return "";
  return `<p class="fearly" role="note">Updates have paused since ${esc(fmtTime(p.since))}. These are the last forecasts published.</p>`;
}

/* ---------- polls still open (John's words, his veto): first on the page wherever polls are open ---------- */
function pollState(c) {      /* {open: true, close} while any zone of the state is open; {today: true, open, close} before they open */
  const s = SBY[c] || BOOT.trackStates[c]; const z = s && s.polls && s.polls.z; if (!z || !z.length) return null;
  let open = null, close = null, any = false, before = false;
  z.forEach(Z => { const st = pollsNow({date: BOOT.election, open: Z.o || "07:00", close: Z.l || Z.c, tz: Z.tz}); if (!st) return;
    if (st.state === "open") { any = true; if (!close || st.close > close) close = st.close; }
    if (st.state === "today") { before = true; if (!open || st.open < open) open = st.open; if (!close || st.close > close) close = st.close; } });
  return any ? {open: true, close} : before ? {today: true, open, close} : null;
}
function pollsBlock(codes) {
  const out = [];
  codes.forEach(c => { const p = pollState(c); if (!p) return; const s = SBY[c], name = esc(s.n);
    const find = `<a href="${esc((s.polls && s.polls.f) || BOOT.links.nass)}" target="_blank" rel="noopener">Find your polling place</a>`;
    if (p.open) out.push(`<div class="pollsopen" role="note"><b>Polls are still open here. If you haven&rsquo;t voted, your vote still counts.</b>The last polls in ${name} close at ${esc(fmtTime(p.close))}.${s.polls && s.polls.ln ? " " + esc(s.polls.ln) : ""} ${find}.</div>`);
    else out.push(`<div class="pollsopen" role="note"><b>Election Day is today in ${name}.</b>Polls open from ${esc(fmtTime(p.open))} and the last close at ${esc(fmtTime(p.close))}. ${find}.</div>`); });
  return out.join("");
}

/* ---------- pieces ---------- */
const crumbs = parts => `<nav class="crumbs" aria-label="Where you are">${parts.map(([h, w]) => h ? `<a href="${h}">${w}</a>` : `<span>${w}</span>`).join(" &rsaquo; ")}</nav>`;
const hero = (kick, h1, lede) => `<div class="nhero"><div class="bkick">${kick}</div><h1>${h1}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</div>`;
const aboxHTML = extra => `<div class="abox" role="note"><p>${ANALYSIS} ${ABOUT_LINE}</p>${extra || ""}</div>`;
const swatch = L => `<span class="nsw" style="--c:${L.c}" data-p="${L.p}" aria-hidden="true"></span>`;
function countedNote(f) {
  const sc = f && f.sc; if (!sc) return "";
  const p = Math.max(1, Math.round(sc * 100));
  return sc < .25 ? `<p class="fearly" role="note">Based on ${p}% of the expected vote. Early figures often move.</p>`
    : `<p class="fmeta">Based on ${Math.min(99, p)}% of the expected vote.</p>`;
}
const statusNote = f => !f || !f.st ? "" : f.st === "official" ? `<p class="fmeta">The state has certified this race. The forecast is kept for the track record; <b>the certified count is the result</b>.</p>`
  : f.st === "done" ? `<p class="fmeta">Every part of this race has reported. The official canvass decides.</p>` : "";
function leadHTML(X) {
  if (X.eq) return `<b>Even</b><small>The record gives no reason to favour any candidate here.</small>`;
  if (X.seats > 1) return `<b>${X.seats} seats</b><small>Highest chances of a seat: ${X.L.slice(0, X.seats).map(L => `${esc(L.name)} ${chanceText(L.chance)}`).join(", ")}</small>`;
  const L = X.L[0]; if (!L) return "";
  return `${swatch(L)}<b>${esc(L.name)}</b> ${chanceText(L.chance)} chance<small>likely ${rangeText(L.lo, L.hi)} of the vote</small>`;
}
function rowHTML(rid) {
  const X = cands(rid); if (!X) return "";
  const u = X.f.sc ? `${Math.max(1, Math.round(X.f.sc * 100))}% counted` : (X.m.pt ? "Partisan" : "Nonpartisan");
  return `<a class="nrow" href="#race=${encodeURIComponent(rid)}"><span class="t">${esc(X.m.title)}${X.m.where ? `<small>${esc(X.m.where)}</small>` : ""}</span><span class="l">${leadHTML(X)}</span><span class="u">${esc(u)}</span></a>`;
}
/* the likely margin of the top two (the first two of the forecast's list), in plain words: "mg" is the first's share less
   the second's, [middle, 80% low, 80% high], in tenths of a point */
function marginHTML(X) {
  const mg = X && X.f && X.f.mg; if (!Array.isArray(mg) || mg.length < 3 || X.eq || X.seats > 1 || X.L.length < 2) return "";
  const A = esc(X.L[0].name), B = esc(X.L[1].name), [m, lo, hi] = mg;
  const pts = t => { const v = (Math.abs(t) / 10).toFixed(1); return `${v} ${v === "1.0" ? "point" : "points"}`; };
  const lead = t => t === 0 ? "level" : `${t > 0 ? A : B} ahead by ${pts(t)}`;
  let words;
  if (lo >= 0) words = `${lead(m)}; likely ${(lo / 10).toFixed(1)} to ${pts(hi)}`;
  else if (hi <= 0) words = `${lead(m)}; likely ${(Math.abs(hi) / 10).toFixed(1)} to ${pts(lo)}`;
  else words = `${lead(m)}; likely anywhere from ${lead(lo)} to ${lead(hi)}`;
  return `<p class="fmeta" id="fmargin">${ANALYSIS} <b>The likely margin of the top two:</b> ${words}. The middle 80% of the model&rsquo;s simulated elections, like the ranges above.</p>`;
}
/* the rule that decides the race, and (where the law asks for more than half the votes) the chance no one passes half */
function ruleHTML(rid, X, d) {
  const rules = (d && d.about && d.about.rules) || {}, words = rules[rid] || rules[rid.slice((d.pre || "").length)] || "";
  const ro = X && X.f && X.f.ro;
  let o = words ? `<p class="fmeta">${esc(plainW(words))}</p>` : "";
  if (ro != null && ro !== "") o += `<p class="fmeta">${ANALYSIS} The chance that no candidate passes half the votes: <b>${chanceText(ro)}</b>.</p>`;
  return o;
}
function runLine(d, f) {
  const t = (f && f.t) || d.t, m = (f && f.m) || d.m, k = (f && f.k) || d.k, ab = d.about || {};
  return `<p class="fmeta">Model run ${esc(KINDW[k] || "")}: <b>${esc(fmtTime(t, true))}</b>, method version <b>${esc(m || "")}</b>${ab.draws ? `, ${num(ab.draws)} simulated elections` : ""}.${ab.ran && ab.ran > t && fmtTime(ab.ran, true) !== fmtTime(t, true) && !f ? ` The model last ran ${esc(fmtTime(ab.ran, true))}; races whose inputs had not changed kept their forecast.` : ""}</p>`;
}

/* ---------- the home: every state with forecasts, the closest races ---------- */
function home() {
  const tok = ++TOKEN;
  let h = hero("Election Night", "Forecasts", "A computer model&rsquo;s chances for each race, with a likely range of the vote, the trend across every run, the inputs and the track record. Never a result: the official count decides.");
  if (!BOOT.public) {
    app.innerHTML = h + aboxHTML() + `<p class="nempty">Forecasts are not published yet. They appear here once the model&rsquo;s checks are finished and approved. Until then you can read <a href="#method">how the forecasts are made</a> and <a href="#track">how the method did on past elections</a>.</p>` + linksHTML();
    return;
  }
  if (!BOOT.states.length) { app.innerHTML = h + aboxHTML() + `<p class="nempty">No forecasts yet.</p>` + linksHTML(); return; }
  app.innerHTML = h + `<p class="loading muted">Loading&hellip;</p>`;
  loadAll().then(() => {
    if (tok !== TOKEN) return;
    let o = h + pollsBlock(BOOT.states.map(s => s.c)) + aboxHTML() + pausedHTML();
    o += `<section class="fsec" aria-labelledby="fst"><h2 id="fst">Forecasts by state</h2><div class="fcards">` + BOOT.states.map(s => { const d = FC[s.c], n = raceIds(s.c).length;
      return `<a class="lvcard" href="#state=${s.c}"><b>${esc(s.n)}</b><span>${num(n)} ${n === 1 ? "race" : "races"} with a forecast</span><small>Model run ${esc(fmtTime(d.t, true))}</small><span class="go">See ${esc(s.n)}&rsquo;s forecasts</span></a>`; }).join("") + `</div></section>`;
    const all = []; BOOT.states.forEach(s => raceIds(s.c).forEach(rid => { const X = cands(rid); const g = topGap(X); if (g < 99) all.push([g, rid]); }));
    all.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));
    if (all.length) o += `<section class="fsec" aria-labelledby="fcl"><h2 id="fcl">The closest races in the model</h2><p class="sub">Races with one seat where the model&rsquo;s chances are nearest even. ${ANALYSIS}</p><div class="nrows" id="fclose">${all.slice(0, 12).map(x => rowHTML(x[1])).join("")}</div></section>`;
    const none = BOOT.none || [];
    if (none.length) o += `<section class="fsec" aria-labelledby="fno"><h2 id="fno">States with nothing to forecast yet</h2><p class="sub">The model planned every 2026 race in these states and found none it could forecast. Here is why.</p><ul class="inlist">` +
      none.map(s => `<li><b>${esc(s.n)}</b>: ${s.why.map(([w, n]) => `${esc(w.replace(/\.$/, ""))} (${plural(n, "race")})`).join("; ")}.</li>`).join("") + `</ul></section>`;
    o += linksHTML();
    app.innerHTML = o;
  }, () => { if (tok === TOKEN) app.innerHTML = h + `<p class="nempty">The forecasts could not be loaded. Check your connection and open the page again.</p>`; });
}
function linksHTML(c) {
  const s = c && SBY[c];
  return `<div class="flinks">${s && s.res ? `<a href="${esc(s.res)}">${esc(s.n)}&rsquo;s results</a>` : ""}<a href="#track">The track record</a><a href="#method">How the forecasts are made</a><a href="${esc(BOOT.links.night)}">Election Night: every state</a></div>`;
}

/* ---------- one state ---------- */
const VIEW = {lv: "", q: "", sort: "office", shown: 60};
function statePage(c) {
  const tok = ++TOKEN, s = SBY[c];
  if (!s) { const z = (BOOT.none || []).find(x => x.c === c);
    app.innerHTML = crumbs([["#", "Forecasts"]]) + (z ? `<p class="nempty">The model has nothing to forecast in ${esc(z.n)} yet: ${z.why.map(([w, n]) => `${esc(w.replace(/\.$/, ""))} (${plural(n, "race")})`).join("; ")}.</p>`
      : `<p class="nempty">No forecasts for this state${BOOT.public ? "" : " are published yet"}.</p>`) + linksHTML(); return; }
  if (VIEW.c !== c) Object.assign(VIEW, {c, lv: "", q: "", sort: "office", shown: 60});
  app.innerHTML = crumbs([["#", "Forecasts"], ["", esc(s.n)]]) + `<p class="loading muted">Loading&hellip;</p>`;
  loadState(c).then(() => {
    if (tok !== TOKEN) return;
    const d = FC[c], ids = raceIds(c), byLv = {};
    ids.forEach(rid => { const lv = metaOf(rid).lv; (byLv[lv] = byLv[lv] || []).push(rid); });
    const un = (META[c].unopposed || 0);
    let o = crumbs([["#", "Forecasts"], ["", esc(s.n)]]) + hero("Forecasts", esc(s.n), `${num(ids.length)} ${ids.length === 1 ? "race has" : "races have"} a forecast.${un ? ` ${num(un)} more ${un === 1 ? "has" : "have"} one name for each seat and get none.` : ""}`);
    o += pollsBlock([c]) + aboxHTML(runLine(d)) + pausedHTML() + leftHTML(META[c].left, c);
    o += `<div class="fchips" role="group" aria-label="Which races">` + [["", "All", ids.length]].concat(LVO.filter(l => byLv[l]).map(l => [l, LVW[l], byLv[l].length]))
      .map(([l, w, n]) => `<button type="button" data-lv="${l}" aria-pressed="${VIEW.lv === l}">${esc(w)} <small>${num(n)}</small></button>`).join("") + `</div>`;
    o += `<div class="fbar"><label class="sr" for="fq">Find a race, a place or a candidate</label><input type="search" id="fq" placeholder="Find a race, a place or a candidate" value="${esc(VIEW.q)}" autocomplete="off">
      <label class="sr" for="fsort">Order</label><select class="pick" id="fsort"><option value="office"${VIEW.sort === "office" ? " selected" : ""}>By office</option><option value="close"${VIEW.sort === "close" ? " selected" : ""}>Closest first</option></select></div>`;
    o += `<p class="fcount" id="fcount" aria-live="polite"></p><div class="nrows" id="flist"></div><div id="fmorebox"></div>` + linksHTML(c);
    app.innerHTML = o;
    const draw = () => {
      const q = nameKey(VIEW.q);
      let list = (VIEW.lv ? byLv[VIEW.lv] || [] : ids).filter(rid => { if (!q) return true; const m = metaOf(rid), X = cands(rid);
        return nameKey(m.title + " " + m.where + " " + X.L.map(L => L.name).join(" ")).includes(q); });
      if (VIEW.sort === "close") list = list.map(rid => [topGap(cands(rid)), rid]).sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1])).map(x => x[1]);
      else list = list.slice().sort((a, b) => { const A = metaOf(a), B = metaOf(b);
        return LVO.indexOf(A.lv) - LVO.indexOf(B.lv) || (/^U\.S\. Senator/.test(B.title) - /^U\.S\. Senator/.test(A.title))
          || (A.where || "").localeCompare(B.where || "", "en", {numeric: true}) || A.title.localeCompare(B.title, "en", {numeric: true}); });
      $("#flist").innerHTML = list.slice(0, VIEW.shown).map(rowHTML).join("") || `<p class="nempty">No race matches.</p>`;
      $("#fcount").textContent = list.length > VIEW.shown ? `Showing ${num(VIEW.shown)} of ${num(list.length)} races.` : `${plural(list.length, "race")}.`;
      $("#fmorebox").innerHTML = list.length > VIEW.shown ? `<button type="button" class="fmore" id="fmore">Show ${num(Math.min(60, list.length - VIEW.shown))} more</button>` : "";
      const mb = $("#fmore"); if (mb) mb.onclick = () => { VIEW.shown += 60; draw(); };
    };
    $$(".fchips button").forEach(b => b.onclick = () => { VIEW.lv = b.dataset.lv; VIEW.shown = 60; $$(".fchips button").forEach(x => x.setAttribute("aria-pressed", String(x === b))); draw(); });
    $("#fq").oninput = e => { VIEW.q = e.target.value; VIEW.shown = 60; draw(); };
    $("#fsort").onchange = e => { VIEW.sort = e.target.value; VIEW.shown = 60; draw(); };
    draw();
  }, () => { if (tok === TOKEN) app.innerHTML = `<p class="nempty">${esc(s.n)}&rsquo;s forecasts could not be loaded. Check your connection and open the page again.</p>`; });
}

/* ---------- one race ---------- */
function racePage(rid) {
  TRENDNOW = null;
  const tok = ++TOKEN, c = stateOfRace(rid), s = SBY[c];
  if (!s) { app.innerHTML = crumbs([["#", "Forecasts"]]) + `<p class="nempty">There is no forecast for this race${BOOT.public ? "" : " published yet"}.</p>` + linksHTML(); return; }
  app.innerHTML = `<p class="loading muted">Loading&hellip;</p>`;
  loadState(c).then(() => {
    if (tok !== TOKEN) return;
    const X = cands(rid), m = metaOf(rid);
    const cr = crumbs([["#", "Forecasts"], [`#state=${c}`, esc(s.n)], ["", esc(m ? m.title : rid)]]);
    if (!X) { app.innerHTML = cr + `<p class="nempty">The model has no forecast for this race. A race with one name for each seat gets none.</p>` + linksHTML(c); return; }
    const f = X.f, d = X.d, M = META[c];
    let o = cr + hero(`Forecast &middot; ${esc(LVW[m.lv] || "")}`, esc(m.title), m.where ? esc(m.where) : "");
    o += pollsBlock([c]) + aboxHTML(runLine(d, f.t || f.m || f.k ? f : null)) + pausedHTML() + countedNote(f) + statusNote(f);
    /* the chances and ranges */
    o += `<section class="fsec" aria-labelledby="fch"><h2 id="fch">${X.seats > 1 ? "Each candidate&rsquo;s chance of a seat" : "Each candidate&rsquo;s chance"}</h2>`;
    if (X.eq) o += `<p>The record gives no reason to favour any candidate here, so the model gives each the same chance.</p>`;
    if (X.seats > 1) o += `<p class="sub">${X.seats} seats: the chance is of finishing among the ${X.seats} with the most votes.</p>`;
    if (X.eq) { const L0 = X.L[0] || {};
      o += `<div class="res"><ul class="eqnames">${X.L.map(L => `<li>${swatch(L)}${esc(L.name)}${L.party ? ` <small>${esc(L.party)}</small>` : ""}</li>`).join("")}</ul>
        <p class="eqline">Each: <b>${chanceText(L0.chance)}</b> chance${X.seats > 1 ? " of a seat" : ""}; likely ${rangeText(L0.lo, L0.hi)} of the vote, middle estimate ${shareText(L0.med)}.</p>`; }
    else o += `<div class="res"><div class="lns">` + X.L.map(L => `<div class="ln"><span class="nm">${swatch(L)}${esc(L.name)}${L.party ? ` <small>${esc(L.party)}</small>` : ""}</span>
      <span class="fig"><b>${chanceText(L.chance)}</b> chance</span><span class="nbar" aria-hidden="true"><i style="width:${chanceNum(L.chance)}%;--c:${L.c}" data-p="${L.p}"></i></span>
      <span class="rg">Likely ${rangeText(L.lo, L.hi)} of the vote; middle estimate ${shareText(L.med)}</span></div>`).join("") + `</div>`;
    o += `<p class="one">${ANALYSIS} Chances are whole percents and never 0 or 100 before the canvass. &ldquo;Likely&rdquo; is the middle 80% of the model&rsquo;s simulated elections: in about one race in five the result falls outside it.</p></div>`;
    o += marginHTML(X) + ruleHTML(rid, X, d);
    if (f.v) o += `<p class="fmeta">${votersText(f.v)}</p>`;
    const tested = f.x && d.tested && d.tested[f.x];
    if (tested) o += `<p class="fmeta">${/^untested/.test(tested) ? "<b>Not tested.</b> " + esc(capital(plainW(tested.replace(/^untested:\s*/, "")))) + "." : "<b>Tested</b> " + esc(tested.replace(/^tested\s*/, "")) + ". See the track record."}</p>`;
    o += `</section>`;
    o += `<section class="fsec" aria-labelledby="ftr"><h2 id="ftr">The trend across runs</h2><p class="sub">Every run of the model that changed this race&rsquo;s forecast. A dashed line marks where a new version of the method begins.</p><div id="ftrend"><p class="loading muted">Loading&hellip;</p></div></section>`;
    /* the three blind spots */
    const B = M.blind || {}, own = f.b && typeof f.b === "object" ? f.b : {};
    const roll = own.roll || (B.roll || [])[m.ri] || "", pos = own.position || (B.pos || [])[m.pi] || "", ord = own.order || B.order || "";
    o += `<section class="fsec" aria-labelledby="fbs"><h2 id="fbs">Three blind spots</h2><p class="sub">What any forecast of this race cannot see clearly, and what the model does about it.</p><div class="fgrid">
      <div class="fcard"><div class="kick">Count order</div><h3>Which votes come in first</h3><p>${esc(ord)}</p></div>
      <div class="fcard"><div class="kick">Roll-off</div><h3>Voters who skip this race</h3><p>${esc(roll)}</p></div>
      <div class="fcard"><div class="kick">Ballot position</div><h3>Whose name is printed first</h3><p>${esc(pos)}</p></div></div></section>`;
    /* the inputs */
    const polls = [];
    Object.entries(d.about || {}).forEach(([k, v]) => { if (/_?polls$/.test(k) && Array.isArray(v)) v.forEach(p => { if (p && p.race === rid && p.used !== false && p.pollster) polls.push(p); }); });
    o += `<section class="fsec" aria-labelledby="fin"><h2 id="fin">The inputs</h2><ul class="inlist">`;
    if (polls.length) o += polls.map(p => `<li>Poll by ${esc(p.pollster)}${p.ended ? `, finished ${esc(fmtDay(p.ended))}` : ""}<small>Polls: members of AAPOR&rsquo;s Transparency Initiative only</small></li>`).join("");
    o += (M.inputs || []).map(i => `<li>${esc(i[0])}<small>${esc(i[1])}${i[2] ? `, as of ${esc(fmtDay(i[2]))}` : ""}${i[3] ? ` &middot; fingerprint ${esc(i[3])}` : ""}</small></li>`).join("");
    o += `</ul><p class="fmeta">Every run is kept with the fingerprints of its inputs, so any run can be made again exactly. <a href="#method">How the forecasts are made</a>.</p></section>`;
    o += `<div class="flinks">${s.res ? `<a href="${esc(s.res)}#race=${encodeURIComponent(rid)}">This race&rsquo;s results</a>` : ""}${s.ballot ? `<a href="${esc(m.lv === "federal" ? s.ballotUS : s.ballot)}#race=${encodeURIComponent(rid)}">Who is on the ballot</a>` : ""}<a href="#state=${c}">${esc(s.n)}&rsquo;s forecasts</a><a href="#track">The track record</a><a href="#method">How the forecasts are made</a></div>`;
    app.innerHTML = o;
    const show = h => { if (tok !== TOKEN) return; TRENDNOW = [h, X]; $("#ftrend").innerHTML = trendHTML(h, X); fitLabels($("#ftrend")); };
    loadHistory(rid).then(show, () => show({p: [[f.t || d.t, f.m || d.m, f.k || d.k, f.sc || 0, X.L.map(L => [L.name, L.chance, L.med, L.lo, L.hi])]], segments: [[0, f.m || d.m]]}));
  }, () => { if (tok === TOKEN) app.innerHTML = `<p class="nempty">The forecasts could not be loaded. Check your connection and open the page again.</p>`; });
}
function loadHistory(rid) {
  const c = stateOfRace(rid), s = SBY[c];
  const fromStatic = () => { const b = hbucket(rid), key = c + b;
    return (HIST[key] ? Promise.resolve(HIST[key]) : getJSON(`${s.h}${b}.json?v=${s.hv[b] || ""}`).then(d => (HIST[key] = d))).then(d => d[rid] || Promise.reject(new Error("none"))); };
  if (FCLIVE.used[c] && !NIGHTLIVE.off()) return getJSON(`${liveRoot()}h/${s.lc}/${encodeURIComponent(rid)}.json`).then(d => d && d.p ? d : Promise.reject(new Error("bad")), fromStatic);
  return fromStatic();
}
/* a point on the trend: in the patterned looks each candidate (in ballot order) has a shape of its own, so the chart never
   rests on colour alone; a point that would sit on another's is drawn hollow and larger, so both stay in sight */
function marker(shape, cx, cy, near, c) {
  const s = 4.2 + 3 * near, st = near ? `fill:none;stroke:${c};stroke-width:2` : `fill:${c};stroke:var(--surface);stroke-width:1.5`, X = cx.toFixed(1), Y = cy.toFixed(1);
  const poly = pts => `<polygon points="${pts.map(([a, b]) => (cx + a * s).toFixed(1) + "," + (cy + b * s).toFixed(1)).join(" ")}" style="${st}"/>`;
  switch (shape % 5) {
    case 1: return `<rect x="${(cx - s * .9).toFixed(1)}" y="${(cy - s * .9).toFixed(1)}" width="${(s * 1.8).toFixed(1)}" height="${(s * 1.8).toFixed(1)}" style="${st}"/>`;
    case 2: return poly([[0, -1.2], [1.1, .8], [-1.1, .8]]);
    case 3: return poly([[0, -1.25], [1.15, 0], [0, 1.25], [-1.15, 0]]);
    case 4: return poly([[0, 1.2], [1.1, -.8], [-1.1, -.8]]);
    default: return `<circle cx="${X}" cy="${Y}" r="${s.toFixed(1)}" style="${st}"/>`;
  }
}
/* chart labels never smaller than 12 pixels: a chart drawn narrower than its viewBox gets its type scaled up to match */
function fitLabels(root) {
  $$("svg.calsvg, .trend > svg", root).forEach(svg => { const vb = svg.viewBox && svg.viewBox.baseVal, w = svg.getBoundingClientRect().width;
    if (vb && vb.width && w) svg.style.setProperty("--fs", (w < vb.width ? 12 * vb.width / w : 12).toFixed(1) + "px"); });
}
/* the trend: each candidate's chance at each run, runs evenly spaced, a new method version marked */
function trendHTML(h, X) {
  const P = (h && h.p) || []; if (!P.length) return `<p class="nempty">No runs on file yet.</p>`;
  const box = $("#ftrend"), W = Math.max(280, Math.min(760, ((box && box.clientWidth) || 640) - 30)), names = X.L.slice(0, 5), H = 220, l = 44, r = 16, t = 12, b = 34, n = P.length;
  const x = i => n === 1 ? l + (W - l - r) / 2 : l + (W - l - r) * i / (n - 1), y = v => t + (H - t - b) * (1 - v / 100);
  const val = (pt, L) => { const row = (pt[4] || []).find(rw => nameKey(rw[0]) === nameKey(L.name)); return row ? chanceNum(row[1]) : null; };
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="The chance of each candidate at each run of the model">`;
  [25, 50, 75].forEach(v => { svg += `<line class="ax" x1="${l}" x2="${W - r}" y1="${y(v)}" y2="${y(v)}"/><text x="${l - 6}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`; });
  ((h.segments || []).slice(1)).forEach(([i, mth]) => { const xx = n === 1 ? x(0) : (x(i) + x(i - 1)) / 2;
    svg += `<line class="seg" x1="${xx}" x2="${xx}" y1="${t}" y2="${H - b}"/><text class="sl" x="${xx + 4}" y="${t + 12}">method ${esc(mth)}</text>`; });
  const SEEN = {};
  names.forEach((L, li) => { const pts = P.map((pt, i) => [x(i), val(pt, L)]).filter(q => q[1] != null);
    if (pts.length > 1) svg += `<polyline class="tl${patterned() && L.p ? " p-" + L.p : ""}" style="stroke:${L.c}" points="${pts.map(q => q[0].toFixed(1) + "," + y(q[1]).toFixed(1)).join(" ")}"/>`;
    pts.forEach(q => { const k = q[0].toFixed(0), yy = y(q[1]), near = (SEEN[k] = SEEN[k] || []).filter(v => Math.abs(v - yy) < 7).length; SEEN[k].push(yy);
      svg += marker(patterned() ? li : 0, q[0], yy, near, L.c); }); });
  svg += `<text x="${l}" y="${H - 10}">${esc(fmtTime(P[0][0], true))}</text>` + (n > 1 ? `<text x="${W - r}" y="${H - 10}" text-anchor="end">${esc(fmtTime(P[n - 1][0], true))}</text>` : "") + `</svg>`;
  const lg = `<div class="lg">${names.map((L, li) => `<span>${patterned() ? `<svg class="mk" viewBox="-7 -7 14 14" aria-hidden="true">${marker(li, 0, 0, 0, L.c)}</svg>` : ""}${swatch(L)}${esc(L.name)}</span>`).join("")}${X.L.length > names.length ? `<span>and ${num(X.L.length - names.length)} more, in the table</span>` : ""}</div>`;
  const tbl = `<details class="nfold"><summary>Every run, as a table</summary><div class="tblwrap"><table class="ftbl"><thead><tr><th scope="col">Run</th><th scope="col">Method</th><th scope="col">Counted</th>${X.L.map(L => `<th scope="col">${esc(L.name)}</th>`).join("")}</tr></thead><tbody>` +
    P.map(pt => `<tr><td>${esc(fmtTime(pt[0], true))}<br><small>${esc(KINDW[pt[2]] || "")}</small></td><td>${esc(pt[1])}</td><td>${pt[3] ? Math.max(1, Math.round(pt[3] * 100)) + "%" : "&ndash;"}</td>${X.L.map(L => { const row = (pt[4] || []).find(rw => nameKey(rw[0]) === nameKey(L.name));
      return `<td>${row ? chanceText(row[1]) + `<br><small>${rangeText(row[3], row[4])}</small>` : "&ndash;"}</td>`; }).join("")}</tr>`).join("") + `</tbody></table></div></details>`;
  return `<div class="trend">${svg}${lg}${n === 1 ? `<p class="fmeta">One run so far. The trend draws itself as the model runs again.</p>` : ""}</div>${tbl}`;
}

/* ---------- the track record: the backtests on past elections ---------- */
const GROUPW = {mnleg: "State House", mnsen: "State Senate", usrep: "U.S. House", statewide: "Statewide offices", all: "All", county: "County offices",
  judicial: "Judges", soil_water: "Soil and water"};
/* the other states' backtest names its groups by office alone */
const GROUPW1 = {all: "All races", usrep: "U.S. House", ussen: "U.S. Senate", governor: "Governor", other: "Other statewide offices"};
function groupWords(g) {
  if (GROUPW1[g]) return GROUPW1[g];
  let m = /^(partisan|nonpartisan|reference night model)\s*(\S*)\s*(\d{4})?\s*(\(.*\))?$/.exec(g);
  if (!m) return capital(g.replace(/_/g, " "));
  if (m[1] === "reference night model") return "All partisan races" + ((m[3] || m[2]) ? `, ${m[3] || m[2]}` : "");
  let w = GROUPW[m[2]] || capital(m[2].replace(/_/g, " "));
  if (m[2] === "all") w = m[1] === "partisan" ? "All partisan races" : "All nonpartisan races";
  else if (m[1] === "nonpartisan") w += " (nonpartisan)";
  if (m[3]) w += `, ${m[3]}`;
  if (m[4]) w += m[4].includes("no holder") ? ", no officeholder running" : " " + m[4];
  return w;
}
const plainW = t => String(t || "").replace(/\s*\([^()]*\bJohn\b[^()]*\)/g, "").replace(/\bthe kit\b/gi, "this site").replace(/\bkit's\b/g, "this site's");
/* how often something happened in the backtests: "all" and "none" rather than 100% and 0%, so that no figure on this
   page reads as a certainty */
const pc0 = v => { if (v == null) return "&ndash;"; if (v >= 1) return "all"; if (v <= 0) return "none";
  const p = Math.round(v * 100); return p >= 100 ? "over 99%" : p <= 0 ? "under 1%" : `${p}%`; };
const sc3 = v => v == null ? "&ndash;" : Number(v).toFixed(3);
/* a measure's value; an older backtest of the other states kept some under other names, read here as a fallback */
const MVALIAS = {cover80: "range80_held", cover95: "range95_held", logloss: "log_loss"};
const mv = (G, k) => !G ? null : G[k] ? G[k][0] : MVALIAS[k] && G[MVALIAS[k]] ? G[MVALIAS[k]][0] : k === "races" && G.brier ? G.brier[1] : null;
function track() {
  const tok = ++TOKEN;
  let h = crumbs([["#", "Forecasts"], ["", "The track record"]]) + hero("Forecasts &middot; Analysis", "The track record", "How the method did on past elections, before the votes were counted and as they came in. After November 3 each 2026 forecast is scored here against the certified count.");
  const list = BOOT.track;
  if (!list.length) { app.innerHTML = h + `<p class="nempty">No backtest is on file yet.</p>` + linksHTML(); return; }
  app.innerHTML = h + `<p class="loading muted">Loading&hellip;</p>`;
  Promise.all(list.map(s => TRACK[s.c] ? TRACK[s.c] : getJSON(s.url).then(d => (TRACK[s.c] = d)))).then(() => {
    if (tok !== TOKEN) return;
    let o = h + aboxHTML(`<p>Scores here compare the method&rsquo;s chances with what happened. The Brier score runs from 0 (every chance right) upward: lower is better. &ldquo;80% ranges held&rdquo; is how often a candidate&rsquo;s share landed inside the likely range; it should be about 80%.</p>`);
    list.forEach(s => { const T = TRACK[s.c], M = T.measures || {}, A = T.about || {};
      o += `<section class="fsec" aria-labelledby="tk${s.c}"><h2 id="tk${s.c}">${esc(s.n)}</h2><p class="sub">Backtest run ${esc(fmtTime(T.t, true))}, method ${esc(T.method || "")}.</p>`;
      const pre = M.pre || {};
      if (Object.keys(pre).length) {
        o += `<h3 class="fsub">Before Election Day</h3><p class="fp">The method rebuilt as it would have stood before each election, using only what was known then, and every contested race forecast.</p>`;
        o += `<div class="tblwrap"><table class="ftbl"><caption>Each row is a group of past races. The plain rules are &ldquo;the officeholder keeps the seat&rdquo; and &ldquo;last time&rsquo;s result repeats&rdquo;, scored on the races where they apply.</caption><thead><tr><th scope="col">Races</th><th scope="col">How many</th><th scope="col">Favourite came first</th><th scope="col">80% ranges held</th><th scope="col">Brier score</th><th scope="col">Officeholder rule, same races</th><th scope="col">Last-time rule, same races</th></tr></thead><tbody>` +
          Object.keys(pre).sort().map(g => { const G = pre[g];
            const inc = mv(G, "incumbent_wins_brier") != null ? `${sc3(mv(G, "incumbent_wins_brier"))} <small>(model ${sc3(mv(G, "model_brier_on_incumbent_wins_races"))}, ${num(mv(G, "incumbent_wins_races"))} races)</small>` : "&ndash;";
            const last = mv(G, "last_time_repeats_brier") != null ? `${sc3(mv(G, "last_time_repeats_brier"))} <small>(model ${sc3(mv(G, "model_brier_on_last_time_repeats_races"))}, ${num(mv(G, "last_time_repeats_races"))} races)</small>` : "&ndash;";
            return `<tr><td>${esc(groupWords(g))}</td><td>${num(mv(G, "races"))}</td><td>${pc0(mv(G, "favourite_won"))}</td><td>${pc0(mv(G, "cover80"))}</td><td>${sc3(mv(G, "brier"))}</td><td>${inc}</td><td>${last}</td></tr>`; }).join("") + `</tbody></table></div>`;
        const gs = Object.keys(pre).filter(g => Object.keys(pre[g]).some(k => /^bin/.test(k)));
        if (gs.length) {
          o += `<h3 class="fsub">Were the chances right?</h3><p class="fp">Candidates grouped by the chance the method gave them, against how often candidates in that group came first. Points on the dashed line mean the chances were right; the size of each point is how many candidates it holds.</p>
            <label class="sr" for="cal${s.c}">Which races</label><select class="pick" id="cal${s.c}" data-st="${s.c}">${gs.map(g => `<option value="${esc(g)}"${/^(partisan all 2024|all)$/.test(g) ? " selected" : ""}>${esc(groupWords(g))}</option>`).join("")}</select><div id="calbox${s.c}"></div>`;
        }
      }
      const oracle = M.oracle || {};
      if (Object.keys(oracle).length) o += `<h3 class="fsub">With the statewide result known</h3><p class="fp">The same races forecast with the statewide result filled in afterwards, to test how the method spreads a statewide mood over districts.</p><div class="tblwrap"><table class="ftbl"><thead><tr><th scope="col">Races</th><th scope="col">How many</th><th scope="col">Favourite came first</th><th scope="col">80% ranges held</th><th scope="col">Brier score</th></tr></thead><tbody>` +
        Object.keys(oracle).sort().map(g => { const G = oracle[g]; return `<tr><td>${esc(groupWords(g))}</td><td>${num(mv(G, "races"))}</td><td>${pc0(mv(G, "favourite_won"))}</td><td>${pc0(mv(G, "cover80"))}</td><td>${sc3(mv(G, "brier"))}</td></tr>`; }).join("") + `</tbody></table></div>`;
      const rep = Object.keys(M).filter(k => /^replay:/.test(k));
      if (rep.length) {
        const orders = [...new Set(rep.map(k => k.split(":")[1]))], pcts = [...new Set(rep.map(k => +k.split(":")[2]))].sort((a, b) => a - b);
        const OW = {"random": "In a random order", "small-first": "Small precincts first", "metro-last": "Biggest metro counties last", "late-batch": "Late absentee batches held back"};
        const years = [...new Set(rep.flatMap(k => Object.keys(M[k])))].sort();
        o += `<h3 class="fsub">On the night: past counts replayed</h3><p class="fp">Past elections replayed precinct by precinct in several orders (the real order of a past night is not on record), with the night&rsquo;s method run at each stage. Each cell: how often the 80% ranges held, and how often the candidate ahead in the model at that point did not come first.</p>`;
        years.forEach(Y => {
          o += `<div class="tblwrap"><table class="ftbl"><caption>${esc(groupWords(Y))}</caption><thead><tr><th scope="col">Order counted</th>${pcts.map(p => `<th scope="col">${p}% counted</th>`).join("")}</tr></thead><tbody>` +
            orders.map(ord => `<tr><td>${esc(OW[ord] || capital(ord.replace(/-/g, " ")))}</td>${pcts.map(p => { const G = (M[`replay:${ord}:${p}`] || {})[Y];
              return `<td>${G ? `${pc0(mv(G, "cover80"))} held<br><small>${pc0(mv(G, "leader_wrong"))} ahead, not first</small>` : "&ndash;"}</td>`; }).join("")}</tr>`).join("") + `</tbody></table></div>`;
        });
      }
      o += nightHTML(T.night);
      const un = Array.isArray(A.untested) ? A.untested : [];
      if (un.length) o += `<h3 class="fsub">Not tested yet</h3><ul class="inlist">${un.map(u => `<li>${esc(capital(plainW(u)))}</li>`).join("")}</ul>`;
      if (A.position && A.position.finding) o += `<h3 class="fsub">Ballot position</h3><p class="fp">${esc(plainW(A.position.finding))}</p>`;
      o += `<h3 class="fsub">The 2026 forecasts</h3><p class="fp">Scored here against the certified count once ${s.c === "US" ? "each state" : esc(s.n)} certifies its results, including how the forecasts did as the count went on.</p></section>`;
    });
    app.innerHTML = o + linksHTML();
    $$("select[data-st]").forEach(sel => { const draw = () => { $("#calbox" + sel.dataset.st).innerHTML = calHTML((TRACK[sel.dataset.st].measures.pre || {})[sel.value]); fitLabels($("#calbox" + sel.dataset.st)); }; sel.onchange = draw; draw(); });
  }, () => { if (tok === TOKEN) app.innerHTML = h + `<p class="nempty">The track record could not be loaded. Check your connection and open the page again.</p>`; });
}
/* the election-night model replayed on past counts: the other states' (each state's own order), or Minnesota's (four
   orders); each cell how often the 80% ranges held and how often the candidate ahead at that point did not finish first */
const SNAME = c => (BOOT.names && BOOT.names[c]) || c;
function nightHTML(N) {
  if (!N) return "";
  const cell = (G, extra) => { if (!G) return "&ndash;";
    if (G.races === 1) {  /* one race: say what happened to it, not a percent of one */
      const one = [G.leader_wrong != null ? `the one ahead in the count ${G.leader_wrong ? "did not finish first" : "finished first"}` : "",
        extra && G.favourite_wrong != null ? `the model&rsquo;s favourite ${G.favourite_wrong ? "did not finish first" : "finished first"}` : ""].filter(Boolean);
      return `${G.cover80 >= 0.5 ? "held" : "missed"}${one.length ? `<br><small>${one.join("; ")}</small>` : ""}`; }
    const sm = [G.leader_wrong != null ? `${pc0(G.leader_wrong)} ahead in the count, not first` : "", extra && G.favourite_wrong != null ? `${pc0(G.favourite_wrong)} of the model&rsquo;s favourites, not first` : ""].filter(Boolean);
    return `${pc0(G.cover80)} held${sm.length ? `<br><small>${sm.join("; ")}</small>` : ""}`; };
  if (Array.isArray(N.states) && N.states.length) {
    const cps = (N.checkpoints || [10, 25, 50, 75, 90]).map(String);
    let o = `<h3 class="fsub">On the night: past counts replayed in each state&rsquo;s own order</h3><p class="fp">${esc(plainW(N.what || ""))} ${N.summary ? esc(capital(plainW(N.summary))) + "." : ""}</p>`;
    o += `<div class="tblwrap"><table class="ftbl"><caption>Each cell: how often the 80% ranges held; how often the candidate ahead in the count at that point did not finish first; and how often the model&rsquo;s favourite did not.</caption><thead><tr><th scope="col">State</th>${cps.map(p => `<th scope="col">${p}% counted</th>`).join("")}</tr></thead><tbody>` +
      N.states.map(s => `<tr><td>${esc(SNAME(s.c))}<br><small>${num(s.races)} ${s.races === 1 ? "race" : "races"}</small></td>${cps.map(p => `<td>${cell((s.cells || {})[p], 1)}</td>`).join("")}</tr>`).join("") +
      (N.all ? `<tr><td><b>All</b></td>${cps.map(p => `<td>${cell(N.all[p], 1)}</td>`).join("")}</tr>` : "") + `</tbody></table></div>`;
    o += `<details class="nfold"><summary>How each state counts, and how its count was replayed</summary>` + N.states.map(s =>
      `<p class="fp"><b>${esc(SNAME(s.c))}</b> ${esc(plainW(s.order || ""))}</p><p class="fmeta">${esc(plainW(s.label || ""))}. ${Object.keys(s.type_gaps || {}).length ? "In that count, against each county&rsquo;s whole vote: " + Object.entries(s.type_gaps).map(([k, v]) => `${esc(KINDB[k] || k)} ${v >= 0 ? "+" : "&minus;"}${Math.abs(v).toFixed(1)} points Democratic`).join("; ") + "." : ""}</p>`).join("") + `</details>`;
    if (Array.isArray(N.untested) && N.untested.length) o += `<details class="nfold"><summary>What these replays could not test</summary><ul class="inlist">${N.untested.map(u => `<li>${esc(capital(plainW(u)))}</li>`).join("")}</ul></details>`;
    return o;
  }
  const P = N.partisan && N.partisan.by_order;
  if (!P || !Object.keys(P).length) return "";
  const keys = Object.keys(P), orders = [...new Set(keys.map(k => k.replace(/ \d+%$/, "")))], cps = [...new Set(keys.map(k => +(/(\d+)%$/.exec(k) || [0, 0])[1]))].sort((a, b) => a - b);
  const OW = {"random": "In a random order", "small-first": "Small precincts first", "metro-last": "Biggest metro counties last", "late-batch": "Late absentee batches held back"};
  return `<h3 class="fsub">On the night: the night&rsquo;s own model, replayed</h3><p class="fp">${esc(plainW(N.what || ""))} ${N.summary ? esc(capital(plainW(N.summary))) + "." : ""}</p>` +
    `<div class="tblwrap"><table class="ftbl"><caption>Partisan races. Each cell: how often the 80% ranges held, and how often the candidate ahead in the count at that point did not finish first.</caption><thead><tr><th scope="col">Order counted</th>${cps.map(p => `<th scope="col">${p}% counted</th>`).join("")}</tr></thead><tbody>` +
    orders.map(ord => `<tr><td>${esc(OW[ord] || capital(ord.replace(/-/g, " ")))}</td>${cps.map(p => `<td>${cell(P[`${ord} ${p}%`])}</td>`).join("")}</tr>`).join("") + `</tbody></table></div>`;
}
const KINDB = {early: "early in-person ballots", mail: "mail ballots", election_day: "Election Day ballots", provisional: "provisional ballots", other: "other ballots"};
function calHTML(G) {
  if (!G) return "";
  const bins = Object.keys(G).filter(k => /^bin\d\d_\d+$/.test(k)).sort();
  const pts = bins.map(k => { const v = G[k], m = /predicted ([\d.]+)/.exec(v[2] || ""); return {pred: m ? +m[1] : null, obs: v[0], n: v[1], k}; }).filter(p => p.pred != null);
  const S = 300, l = 40, b = 34, t = 16, r = 16, X = v => l + (S - l - r) * v, Y = v => t + (S - t - b) * (1 - v), big = Math.max(1, ...pts.map(p => p.n));
  let svg = `<svg class="calsvg" viewBox="0 0 ${S} ${S}" role="img" aria-label="Chances given against how often they came true">`;
  [.25, .5, .75].forEach(v => { svg += `<line class="ax" x1="${X(0)}" x2="${X(1)}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${l - 4}" y="${Y(v) + 4}" text-anchor="end">${v * 100}%</text><text x="${X(v)}" y="${S - b + 16}" text-anchor="middle">${v * 100}%</text>`; });
  svg += `<rect class="ax" x="${X(0)}" y="${Y(1)}" width="${X(1) - X(0)}" height="${Y(0) - Y(1)}" fill="none"/>`;
  svg += `<line class="dg" x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}"/>`;
  pts.forEach(p => { svg += `<circle cx="${X(p.pred).toFixed(1)}" cy="${Y(p.obs).toFixed(1)}" r="${(3 + 7 * Math.sqrt(p.n / big)).toFixed(1)}" fill-opacity=".8"/>`; });
  svg += `<text x="${(l + S) / 2}" y="${S - 4}" text-anchor="middle">chance given</text></svg>`;
  const tbl = `<details class="nfold"><summary>The same, as a table</summary><div class="tblwrap"><table class="ftbl"><thead><tr><th scope="col">Chance given</th><th scope="col">On average</th><th scope="col">Came first</th><th scope="col">Candidates</th></tr></thead><tbody>` +
    pts.map(p => { const m = /bin(\d\d)_(\d+)/.exec(p.k); return `<tr><td>${+m[1] === 0 ? `under ${+m[2]}%` : +m[2] >= 100 ? `${+m[1]}% and over` : `${+m[1]}% to ${+m[2]}%`}</td><td>${pc0(p.pred)}</td><td>${pc0(p.obs)}</td><td>${num(p.n)}</td></tr>`; }).join("") + `</tbody></table></div></details>`;
  return svg + tbl;
}

/* ---------- the method ---------- */
const ABOUTW = {lean: "Past votes", environment: "The year&rsquo;s mood", district: "Districts", nonpartisan: "Nonpartisan races", turnout: "Who votes",
  position: "Ballot position", not_used: "Not used yet", untested: "Not tested", backtest: "Sized by the backtests",
  night: "On election night", night_now: "Tonight so far", count_order: "Count order", types_now: "Kinds of ballot tonight",
  turnout_night: "Turnout tonight", night_tested: "Sized by replays", rolloff_night: "Roll-off tonight", position_night: "Ballot position tonight",
  night_census: "Census figures on the night", early_lead: "How much an early lead means", statewide: "Statewide races", house: "The U.S. House",
  minor: "Smaller parties"};
function method() {
  const tok = ++TOKEN;
  let h = crumbs([["#", "Forecasts"], ["", "How the forecasts are made"]]) + hero("Forecasts &middot; Analysis", "How the forecasts are made", "A computer model, run again whenever its inputs change, every run kept.");
  const sec = (id, title, body) => `<section class="fsec" aria-labelledby="${id}"><h2 id="${id}">${title}</h2>${body}</section>`;
  let o = h + aboxHTML();
  o += sec("mw", "What a forecast says", `<p>For each candidate, the <b>chance</b> of coming first (or, where several are elected, of a seat) and a <b>likely range</b> for their share of the vote: the middle 80% of the model&rsquo;s simulated elections, so about one race in five lands outside it. Where one seat is filled, the <b>likely margin of the top two</b> as well: how far the first is likely to finish ahead of the second, a range that runs below zero when the second could finish ahead. Chances are whole percents and never 0 or 100 before the canvass: &ldquo;over 99%&rdquo; and &ldquo;under 1%&rdquo; instead.</p><p>No forecast is made for a race with one name for each seat. Where nothing on the record separates the candidates, the model gives them the same chance and says so.</p><p>A forecast is never a result and never a call. The official count decides, and each state&rsquo;s own results are the authority.</p>`);
  o += sec("mb", "Before Election Day", `<p>Each precinct&rsquo;s lean in past official results, added up to every district made of whole precincts; the year&rsquo;s mood, from polls by members of AAPOR&rsquo;s Transparency Initiative only; who is expected to vote; a sitting officeholder&rsquo;s edge where the backtests show one; and errors at the statewide, regional, district and precinct level. Nonpartisan races use only the record: who holds the seat, an earlier result, a party&rsquo;s own published endorsement, and where the name is printed. Then thousands of simulated elections give the chances and ranges.</p>`);
  o += sec("mn", "On election night", `<p>As precincts and counties report, each one is compared with what the model expected there. The differences are spread to the places still to come by region and past swing, pulled back toward the earlier forecast while few are in. In Minnesota, absentee ballots a county adds late are their own block, with an unknown lean until they are counted. Where a state&rsquo;s results give Election Day, early and mail ballots apart, each kind of ballot gets its own lean, learned as it is counted, and the ballots of each kind still to come are estimated kind by kind; where they give totals only, the ballots counted first in a county may lean apart from those counted last. Where the law asks for more than half the votes, the page gives the chance that no one passes half; for ranked-choice races it counts first choices on the night and says so. The model runs again after each new set of official figures, and every run is kept. Early in the count the page says how much of the expected vote is in, and that early figures often move.</p>`);
  o += sec("mbs", "Three blind spots", `<div class="fgrid"><div class="fcard"><div class="kick">Count order</div><h3>Which votes come in first</h3><p>Places and kinds of ballots are counted in different orders, so the first figures can lean one way and the last another. The model never treats the first figures as typical.</p></div><div class="fcard"><div class="kick">Roll-off</div><h3>Voters who skip a race</h3><p>Many voters skip races further down the ballot: from a few percent for Congress to half of the voters for some judges. The model expects the same skipping, precinct by precinct, where past results measure it.</p></div><div class="fcard"><div class="kick">Ballot position</div><h3>Whose name is printed first</h3><p>A name printed first can gain a little, most in races voters know least about. Where the state rotates names the edge mostly cancels out; where one name is first everywhere, the model allows for it.</p></div></div>`);
  o += sec("mk", "What it cannot know", `<p>How absentee voters voted until their county adds them; anything that happens late; write-in campaigns; recounts. Census figures describe places, never voters.</p>`);
  o += sec("mv", "Every run kept", `<p>Each run is stored with its method version, the fingerprints of every input, and the random seed it used, so it can be made again exactly. A race gets a new entry only when its inputs change. When a formula changes the method&rsquo;s version goes up, and each race&rsquo;s trend marks where the new version begins. <a href="#track">The track record</a> shows how the method did on past elections.</p>`);
  if (BOOT.public && BOOT.states.length) {
    app.innerHTML = o + `<p class="loading muted">Loading&hellip;</p>`;
    loadAll().then(() => {
      if (tok !== TOKEN) return;
      BOOT.states.forEach(s => { const A = FC[s.c].about || {}, M = META[s.c] || {};
        const ORD = Object.keys(ABOUTW), rank = k => ORD.includes(k) ? ORD.indexOf(k) : 50;
        const rows = Object.entries(A).filter(([k, v]) => typeof v === "string" && k !== "ran" && v.length > 20).sort((a, b) => rank(a[0]) - rank(b[0]));
        let b = rows.map(([k, v]) => `<div class="fcard"><h3>${ABOUTW[k] || esc(capital(k.replace(/_/g, " ")))}</h3><p>${esc(plainW(v))}</p></div>`).join("");
        b = (b ? `<div class="fgrid">${b}</div>` : "") + ((M.inputs || []).length ? `<h3 class="fsub">The inputs</h3><ul class="inlist">${M.inputs.map(i => `<li>${esc(i[0])}<small>${esc(i[1])}${i[2] ? `, as of ${esc(fmtDay(i[2]))}` : ""}${i[3] ? ` &middot; fingerprint ${esc(i[3])}` : ""}</small></li>`).join("")}</ul>` : "");
        o += sec("mst" + s.c, `${esc(s.n)}: the method in its own words`, `<p class="sub">Method version ${esc(FC[s.c].m || "")}. ${ANALYSIS}</p>` + b); });
      app.innerHTML = o + linksHTML();
    }, () => { if (tok === TOKEN) app.innerHTML = o + linksHTML(); });
    return;
  }
  app.innerHTML = o + linksHTML();
}

/* ---------- routes ---------- */
function route() {
  const h = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (h === "track" || h.startsWith("track=")) track();
  else if (h === "method") method();
  else if (h.startsWith("state=")) statePage(h.slice(6).toUpperCase().slice(0, 2));
  else if (h.startsWith("race=")) racePage(h.slice(5));
  else home();
  window.scrollTo(0, 0);
  try { app.focus({preventScroll: true}); } catch (e) {}
}
if (LIVE.rehearsal) { const b = $("#nreh"); if (b) { b.hidden = false; b.innerHTML = "<b>Rehearsal:</b> replayed figures. Not 2026 results."; } }
/* the first look at the live copy comes before the first drawing, so a reader never sees older forecasts replaced */
const LIVEON = BOOT.public && BOOT.states.length && !NIGHTLIVE.off();
(LIVEON ? fcGet().then(fcCommit).catch(() => false) : Promise.resolve()).then(() => { route(); addEventListener("hashchange", route); startLive(); });
const startLive = () => { if (LIVEON) NIGHTLIVE.start({get: fcGet, commit: fcCommit, when: newestRun,
  onNew: () => { const h = location.hash; if (/^#race=/.test(h)) route(); else { const host = $("#flist") || $("#fclose"); if (host) NIGHTLIVE.ready(host, route); else route(); }
    if (LIVE.rehearsal && LIVE.now && LIVE.now.label) { const b = $("#nreh"); if (b) b.innerHTML = `<b>Rehearsal:</b> replayed figures from ${esc(LIVE.now.label)}. Not 2026 results.`; } },
  onTick: () => {}}); };
"""


def page_html(P, boot, practice, generated, version, links):
    nav = "".join(f'<a href="{h}">{w}</a>' for h, w in (("#", "Every state"), ("#track", "Track record"), ("#method", "How it works")))
    foot = " &middot; ".join(x for x in (
        f'<a href="{links["night"]}">Election Night</a>',
        f'<a href="{links["night"]}us/">Results across the country</a>',
        f'<a href="{links["front"]}">The Civic Archive front door</a>') if x)
    desc = ("A computer model's chances for each race on election night, with a likely range of the vote, the trend across "
            "every run, its inputs and its track record. Labelled Analysis: the official count decides.")
    page = PAGE
    banner = (f'<div class="nbanner" role="note"><b>{PRACTICE_LABEL}</b> The model&rsquo;s runs on file, shown here before the forecasts are approved for the site.</div>\n'
              if practice else "")
    for key, value in (("__CSS__", P["CSS"]), ("__BALLOT_CSS__", P["BALLOT_CSS"]), ("__NIGHT_CSS__", N.NIGHT_CSS), ("__FONTS__", N.fonts_css()),
                       ("__HEADSCRIPT__", N.head_script()), ("__CHANGELOG__", P["CHANGELOG"]),
                       ("__NIGHT_JS__", N.NIGHT_JS), ("__PAGE_JS__", PAGE_JS),
                       ("__TOPBAR__", N.top_bar("Election Night: forecasts", nav, door_href=links["night"])),
                       ("__CLBOX__", N.changelog_box()), ("__BANNER__", banner),
                       ("__BRAND__", N.brand_tags(links["icons"], "Election Night: forecasts · The Civic Archive", desc, "forecasts.png", "night/forecasts/")),
                       ("__FOOTLINKS__", foot)):
        if page.count(key) != 1:
            raise SystemExit(f"build_night_forecasts: the page should hold {key} exactly once (it holds it {page.count(key)} times)")
        page = page.replace(key, value)
    page = page.replace("__DESC__", esc(desc)).replace("__VERSION__", esc(version)).replace("__GENERATED__", generated)
    return page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


RIDER = '<script type="module" src="../../shell/rider.js" data-tca-rider></script>\n'


# ============================================================ building

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def build(dev_root, version=None, practice=None, say=print):
    """The forecasts page. Returns {path written: bytes}."""
    from build_ballot_state_dev import copy_fonts, slim_page, write_if_changed
    from build_site_dev import read_changelog
    from election.model import runs
    dev_root = os.path.abspath(dev_root)
    changelog = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = version or ((changelog[0].get("version") if changelog else "") or "")
    show = bool(practice) or FORECASTS_PUBLIC
    if practice:
        out_dir = os.path.join(N.practice_root(dev_root), "night", "forecasts")
        links = {"night": "../../../dev/night/", "front": "../../../dev/", "icons": "../../../dev/", "dev": "../../../dev/"}
        live = "../../night-live/"
    else:
        out_dir = os.path.join(dev_root, "night", "forecasts")
        links = {"night": "../", "front": "../../", "icons": "../../", "dev": "../../"}
        live = "../../../night-live/"
    say(f"Election Night, forecasts{' (practice)' if practice else ''}: building {os.path.relpath(out_dir, HERE)}"
        + ("" if show else " (forecasts not public yet: method and track record only)"))
    db = model_db()
    fc_states, bt_states = model_states(db)
    written = {}
    data = os.path.join(out_dir, "data")
    if not show:
        for sub in ("fc", "meta", "h"):
            p = os.path.join(data, sub)
            if os.path.isdir(p):
                shutil.rmtree(p)
                say(f"  removed data/{sub}/ (forecasts are not public yet)")

    def put(rel, text):
        p = os.path.join(out_dir, *rel.split("/"))
        write_if_changed(p, text)
        written[p] = len(text.encode("utf-8"))
        return written[p]

    tracks = {}
    track_boot = []
    for code in bt_states:
        doc = runs.track_json(code, db)
        if not doc:
            continue
        tracks[code] = doc
        text = dumps(doc)
        bad = N.kit_names(text)
        if bad:
            raise SystemExit(f"build_night_forecasts: {code}'s track record would name the kit's own files: {bad}")
        put(f"data/track/{code.lower()}.json", text)
        # "US" is the backtest of every other state's races for Congress, governor and the other statewide offices
        name = "Congress, governors and statewide offices in the other states" if code == "US" else place(code)["name"]
        track_boot.append({"c": code, "n": name, "url": f"data/track/{code.lower()}.json?v={N.sha10(text)}"})
    states_boot, polls_all = [], {}
    if show:
        for code in fc_states:
            doc = runs.page_json(code, db)
            if not doc or not doc.get("r"):
                continue
            lc, name = code.lower(), place(code)["name"]
            filed = races_of(code)
            pre = doc.get("pre") or ""
            ids = [k if re.match(r"\d{4}-[A-Z]{2}-", k) else pre + k for k in doc["r"]]
            missing = [rid for rid in ids if rid not in filed]
            if missing:
                say(f"  {code}: {len(missing)} forecast race(s) are not on the ballot lists and are left out, e.g. {missing[:3]}")
            blind, idx = blind_spots(code, {rid: filed[rid] for rid in ids if rid in filed}, tracks.get(code))
            meta_r = {}
            for rid in ids:
                r = filed.get(rid)
                if not r:
                    continue
                ri, pi = idx[rid]
                key = rid[len(pre):] if pre and rid.startswith(pre) else rid
                meta_r[key] = [r["lv"], r["title"], r["where"], r["pt"], r["cs"], ri, pi] + ([r["seats"]] if r["seats"] > 1 else [])
            un = ((doc.get("about") or {}).get("races") or {}).get("unopposed") or 0
            meta = {"v": 1, "state": code, "pre": pre, "r": meta_r, "blind": blind, "inputs": run_inputs(db, code), "unopposed": un,
                    "left": left_groups((doc.get("about") or {}).get("left_out") or {}, filed)}
            fc_text, meta_text = dumps(doc), dumps(meta)
            for what, t in (("forecasts", fc_text), ("race list", meta_text)):
                bad = N.kit_names(t)
                if bad:
                    raise SystemExit(f"build_night_forecasts: {code}'s {what} file would name the kit's own files: {bad}")
            n_fc = put(f"data/fc/{lc}.json", fc_text)
            n_meta = put(f"data/meta/{lc}.json", meta_text)
            if n_fc > FC_BUDGET:
                say(f"  WARNING: {code}'s forecasts file is {n_fc / 1e3:,.0f} KB, over its {FC_BUDGET / 1e3:,.0f} KB budget")
            hist = runs.history(code, db)
            buckets = {b: {} for b in range(BUCKETS)}
            for rid, h in hist.items():
                if rid in filed:
                    buckets[bucket(rid)][rid] = {"p": h["p"], "segments": h["segments"]}
            hv = []
            hdir = os.path.join(data, "h", lc)
            n_hist = 0
            for b in range(BUCKETS):
                text = dumps(buckets[b])
                hv.append(N.sha10(text))
                n_hist += put(f"data/h/{lc}/{b}.json", text)
            pol = polls_of(code)
            polls_all[code] = pol
            res = ""
            if os.path.exists(os.path.join(dev_root, "night", lc, "index.html")):
                res = f"{links['night']}{lc}/"
            elif os.path.exists(os.path.join(dev_root, "night", "us", "index.html")):
                res = f"{links['night']}us/"
            ballot = f"{links['dev']}ballot/{lc}/" if os.path.exists(os.path.join(dev_root, "ballot", lc, "index.html")) else ""
            ballot_us = f"{links['dev']}ballot/us/" if os.path.exists(os.path.join(dev_root, "ballot", "us", "index.html")) else ballot
            states_boot.append({"c": code, "n": name, "lc": lc, "fc": f"data/fc/{lc}.json?v={N.sha10(fc_text)}", "meta": f"data/meta/{lc}.json?v={N.sha10(meta_text)}",
                                "h": f"data/h/{lc}/", "hv": hv, "res": res, "ballot": ballot or ballot_us, "ballotUS": ballot_us or ballot, "polls": pol})
            say(f"  {code}: {len(meta_r):,} races with a forecast ({un:,} with one name a seat get none); forecasts {n_fc / 1e3:,.0f} KB "
                f"(budget {FC_BUDGET / 1e3:,.0f}), race list {n_meta / 1e3:,.0f} KB, run history {n_hist / 1e3:,.0f} KB in {BUCKETS} files")
    none_boot = nothing_to_forecast({s["c"] for s in states_boot}) if show else []
    for s in none_boot:
        say(f"  {s['c']}: nothing to forecast ({s['total']:,} races left out; the page says why)")
    copy_fonts(out_dir)
    night_codes = sorted({s.get("c") for doc in tracks.values() for s in ((doc.get("night") or {}).get("states") or []) if s.get("c")})
    boot = {"public": show, "election": GENERAL, "buckets": BUCKETS, "states": states_boot, "none": none_boot, "track": track_boot,
            "trackStates": {}, "live": {"base": live, "dir": ""}, "changelog": changelog,
            "links": {"night": links["night"], "nass": NASS}, "names": {c: place(c)["name"] for c in night_codes}}
    if practice:
        boot["practice"] = {"label": PRACTICE_LABEL, "now": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    P = N.parts()
    page = page_html(P, boot, practice, N.generated(), version, links)
    whole = len(page.encode("utf-8"))
    page = slim_page(page, "Election Night forecasts")
    page = N.quiet(page)
    checks = N.page_checks("night/forecasts/index.html", page, SHELL_LIMIT, say)
    if not practice and os.path.exists(os.path.join(dev_root, "shell", "rider.js")):
        i = page.rfind("</body>")
        page = page[:i] + RIDER + page[i:]      # the companion and the page guide, as build_shell.ride() puts them on every page with its own top bar
    put("index.html", page)
    total = 0
    for base, _dirs, files in os.walk(out_dir):
        if os.sep + "fonts" in base:
            continue
        total += sum(os.path.getsize(os.path.join(base, f)) for f in files)
    say(f"  wrote index.html {checks['bytes'] / 1e3:,.0f} KB ({whole / 1e3:,.0f} KB before slimming; budget {SHELL_LIMIT / 1e3:,.0f} KB); "
        f"the page and its data {total / 1e6:,.2f} MB of Night's {STATIC_BUDGET / 1e6:,.0f} MB for static files; "
        f"{len(states_boot)} state(s) with forecasts shown, {len(track_boot)} with a track record")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's root (default site/dev)")
    ap.add_argument("--practice", action="store_true", help="into site/practice/ (never published), forecasts shown")
    a = ap.parse_args()
    build(a.root, practice="forecasts" if a.practice else None)


if __name__ == "__main__":
    main()
