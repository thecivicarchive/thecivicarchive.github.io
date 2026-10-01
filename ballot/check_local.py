"""
ballot/check_local.py - the checks every state's county and local ballot rows must pass before they are loaded for real.

    python -m ballot.check_local --code nd --db <a trial copy of ballot_local_2026.sqlite> [--real ballot_local_2026.sqlite]

It reads two databases and writes nothing. Against the real database it checks that the state's rows already there (its
statewide offices, legislature and courts) are still there, unchanged. In the trial database it checks the local rows'
shape (levels, ids, counties, places, parties), that every gap and note is in plain words, and that no text looks like
contact details. A failed check names the table, the column and the race or place id, never the text itself.

The local conventions (John, 2026-09-30; Minnesota's own rows keep their older, shorter ids and are not checked here):
  sl_races.level         county, soil_water, city, township, school, hospital, other (local judges stay under court)
  sl_races.jurisdiction_id / sl_places.id
                         county: the 5-digit county FIPS code; a city, town, village or township: <ST>-M-<key>;
                         a school district: <ST>-S-<key>; a hospital district: <ST>-H-<key>; any other district:
                         <ST>-X-<key>. A key is letters, digits and hyphens.
  sl_races.county_ids    a JSON list of the 5-digit county FIPS codes the contest reaches (never empty for a local race)
  sl_places.kind         county, mcd, school, hospital, special; source_id begins with the state's code and a hyphen
  sl_gaps                what could not be loaded, with a reason a reader can follow
  sl_notes               key local_calendar: which local offices are on this ballot and which are elected another time
"""

import argparse
import collections
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.join(HERE, "ballot_local_2026.sqlite")

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_gaps (state TEXT NOT NULL, scope TEXT NOT NULL, place_id TEXT NOT NULL, place TEXT, what TEXT NOT NULL,
  reason TEXT NOT NULL, url TEXT, PRIMARY KEY (state, scope, place_id, what));
CREATE TABLE IF NOT EXISTS sl_notes (state TEXT NOT NULL, key TEXT NOT NULL, text TEXT NOT NULL, source TEXT, url TEXT, PRIMARY KEY (state, key));
"""

FIPS = {"AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13", "HI": "15",
        "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26",
        "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37",
        "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
        "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"}
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
PLACE_KINDS = ("county", "mcd", "school", "hospital", "special")
GAP_SCOPES = ("state", "county", "place", "race")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|"
                    r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")
POBOX = re.compile(r"\bP\.?\s?O\.?\s+Box\b", re.I)


def contact_like(text, strict):
    t = str(text)
    if EMAIL.search(t) or PHONE.search(t) or WEB.search(t) or POBOX.search(t):
        return True
    return bool(strict and (STREET.search(t) or ZIP.search(t)))


def check(code, db, real=REAL, say=print):
    ST = code.upper()
    lc = code.lower()
    fips = FIPS[ST]
    fails, warns = collections.defaultdict(list), collections.defaultdict(list)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for t in ("sl_races", "sl_candidates", "sl_sources", "sl_places", "sl_gaps", "sl_notes"):
        if t not in tables:
            fails[f"table {t} is missing"].append(t)
    if fails:
        return report(ST, fails, warns, say)

    # ---- 1. what the real database already holds for this state is still there, unchanged
    if real and os.path.exists(real) and os.path.abspath(real) != os.path.abspath(db):
        rcon = sqlite3.connect(f"file:{real}?mode=ro", uri=True)
        old = {r[0]: r for r in rcon.execute("SELECT * FROM sl_races WHERE state = ?", (ST,))}
        new = {r[0]: r for r in con.execute("SELECT * FROM sl_races WHERE state = ?", (ST,))}
        for rid, row in old.items():
            if row[2] in LOCAL_LEVELS:
                continue                                    # local rows may be rebuilt
            if rid not in new:
                fails["a state-level race in the real database is gone"].append(rid)
            elif new[rid] != row:
                fails["a state-level race changed"].append(rid)
        oc, nc = collections.defaultdict(set), collections.defaultdict(set)
        for r in rcon.execute("SELECT c.* FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ?", (ST,)):
            oc[r[0]].add(r)
        for r in con.execute("SELECT c.* FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ?", (ST,)):
            nc[r[0]].add(r)
        for rid in old:
            if old[rid][2] not in LOCAL_LEVELS and rid in new and oc[rid] != nc[rid]:
                fails["a state-level race's candidates changed"].append(rid)
        for kind, pid, name in rcon.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE ?", (lc + "-%",)):
            got = con.execute("SELECT name FROM sl_places WHERE kind = ? AND id = ?", (kind, pid)).fetchone()
            if not got:
                fails["a place in the real database is gone"].append(f"{kind} {pid}")
            elif got[0] != name:
                warns["a place's name changed"].append(f"{kind} {pid}")
        for (sid,) in rcon.execute("SELECT source_id FROM sl_sources WHERE state = ?", (ST,)):
            if not con.execute("SELECT 1 FROM sl_sources WHERE source_id = ?", (sid,)).fetchone():
                warns["a source in the real database is gone"].append(sid)
        say(f"    {ST}: {sum(1 for r in old.values() if r[2] not in LOCAL_LEVELS):,} state-level races compared with the real database")
        rcon.close()
    else:
        warns["not compared with the real database"].append(ST)

    # ---- 2. the local rows' shape
    cols = [r[1] for r in con.execute("PRAGMA table_info(sl_races)")]
    races = [dict(zip(cols, r)) for r in con.execute("SELECT * FROM sl_races WHERE state = ?", (ST,))]
    local = [r for r in races if r["level"] in LOCAL_LEVELS]
    places = {(k, i): (n, c, s) for k, i, n, c, s in con.execute("SELECT kind, id, name, county_ids, source_id FROM sl_places WHERE source_id LIKE ?", (lc + "-%",))}
    counties = {i for (k, i) in places if k == "county"}
    all_ids = {i for (_k, i) in places}
    pat = {"city": rf"{ST}-M-[A-Za-z0-9-]+", "township": rf"{ST}-M-[A-Za-z0-9-]+", "school": rf"{ST}-S-[A-Za-z0-9-]+",
           "hospital": rf"{ST}-H-[A-Za-z0-9-]+", "county": rf"{fips}\d{{3}}", "soil_water": rf"{fips}\d{{3}}|{ST}-X-[A-Za-z0-9-]+",
           "other": rf"{fips}\d{{3}}|{ST}-[MSHX]-[A-Za-z0-9-]+"}
    for r in races:
        rid = r["race_id"]
        if not re.fullmatch(rf"2026-{ST}-[A-Za-z0-9.-]+", rid or ""):
            fails["race id is not 2026-<ST>-letters, digits, hyphens"].append(rid)
        if r["election_date"] != "2026-11-03" and not r["special"] and r["level"] in LOCAL_LEVELS:
            warns["a local race not dated 2026-11-03"].append(rid)
    for r in local:
        rid = r["race_id"]
        if not (r["jurisdiction"] or "").strip():
            fails["local race with no jurisdiction name"].append(rid)
        if not re.fullmatch(pat[r["level"]], r["jurisdiction_id"] or ""):
            fails[f"jurisdiction_id does not fit the {r['level']} pattern"].append(rid)
        elif r["jurisdiction_id"] not in all_ids:
            fails["jurisdiction_id has no sl_places row"].append(rid)
        try:
            cids = json.loads(r["county_ids"] or "[]")
        except ValueError:
            cids = None
        if not isinstance(cids, list) or not cids or any(not re.fullmatch(rf"{fips}\d{{3}}", str(c)) for c in cids):
            fails["county_ids is not a JSON list of this state's 5-digit county codes"].append(rid)
        elif any(c not in counties for c in cids):
            fails["a county id with no county row in sl_places"].append(rid)
        if r["partisan"] not in (0, 1):
            fails["partisan is not 0 or 1"].append(rid)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", r["office_kind"] or ""):
            fails["office_kind is not lower_snake_case"].append(rid)
    for (k, i), (n, c, s) in places.items():
        if k in PLACE_KINDS and k != "county" and not re.fullmatch(rf"{ST}-[MSHX]-[A-Za-z0-9-]+", i):
            fails["a local place id does not fit <ST>-M/S/H/X-key"].append(f"{k} {i}")
        if k == "county" and not re.fullmatch(rf"{fips}\d{{3}}", i):
            fails["a county place id is not the 5-digit code"].append(i)
        if not (n or "").strip():
            fails["a place with no name"].append(f"{k} {i}")

    # ---- 3. candidates
    ccols = [r[1] for r in con.execute("PRAGMA table_info(sl_candidates)")]
    cands = collections.defaultdict(list)
    for r in con.execute("SELECT c.* FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ?", (ST,)):
        cands[r[0]].append(dict(zip(ccols, r)))
    orphans = con.execute("SELECT COUNT(*) FROM sl_candidates WHERE race_id LIKE ? AND race_id NOT IN (SELECT race_id FROM sl_races)", (f"2026-{ST}-%",)).fetchone()[0]
    if orphans:
        fails["candidates whose race is missing"].append(str(orphans))
    for r in local:
        rid, cs = r["race_id"], cands.get(r["race_id"], [])
        if not cs and not (r["note"] or "").strip():
            fails["a local race with no candidate and no note saying why"].append(rid)
        for c in cs:
            if not (c["name"] or "").strip():
                fails["a candidate with no name"].append(rid)
            if not (c["party"] or "").strip():
                fails["a candidate with no party words (a nonpartisan office says 'Nonpartisan office')"].append(rid)
            if not r["partisan"] and (c["party"] != "Nonpartisan office" or c["party_code"] != "N"):
                fails["a nonpartisan race whose candidate is not 'Nonpartisan office' / N"].append(rid)
            if r["partisan"] and c["party"] == "Nonpartisan office":
                fails["a partisan race with a 'Nonpartisan office' candidate"].append(rid)
            if c["election"] == "general" and c["votes"] is not None:
                fails["November votes stored before the election"].append(rid)
            if c["incumbent"] and not c["state_member_id"]:
                warns["incumbent marked on a local candidate (the local pages do not show it)"].append(rid)

    # ---- 4. gaps and notes
    for scope, pid, what, reason in con.execute("SELECT scope, place_id, what, reason FROM sl_gaps WHERE state = ?", (ST,)):
        if scope not in GAP_SCOPES:
            fails["a gap whose scope is not state, county, place or race"].append(f"{scope} {pid}")
        if len((reason or "").strip()) < 20:
            fails["a gap without a reason a reader can follow"].append(f"{scope} {pid}")
        if scope == "county" and not re.fullmatch(rf"{fips}\d{{3}}", pid or ""):
            fails["a county gap whose place_id is not the 5-digit code"].append(str(pid))
    if not con.execute("SELECT 1 FROM sl_notes WHERE state = ? AND key = 'local_calendar'", (ST,)).fetchone():
        fails["no sl_notes row with key local_calendar"].append(ST)

    # ---- 5. nothing that looks like contact details (addresses of sources live only in url columns)
    scan = [("sl_races", "race_id", ["office", "jurisdiction", "district", "seat", "note", "holder_name"], "state = ?", (ST,), True),
            ("sl_candidates", "race_id", ["name", "party", "note"], "race_id LIKE ?", (f"2026-{ST}-%",), True),
            ("sl_places", "id", ["name"], "source_id LIKE ?", (lc + "-%",), True),
            ("sl_gaps", "place_id", ["place", "what", "reason"], "state = ?", (ST,), False),
            ("sl_notes", "key", ["text", "source"], "state = ?", (ST,), False),
            ("sl_sources", "source_id", ["title", "note", "agency"], "state = ?", (ST,), False)]
    # A hit in a local race, its candidates or a place fails the check. A hit in a state-level race that was loaded before
    # (a note naming an agency's site) is only noted: those rows must stay as they are, and the page's own guard drops them.
    local_ids = {r["race_id"] for r in local}
    for table, key, columns, where, args, strict in scan:
        for row in con.execute(f"SELECT {key}, {', '.join(columns)} FROM {table} WHERE {where}", args):
            for col, v in zip(columns, row[1:]):
                if v not in (None, "") and contact_like(v, strict):
                    hard = table == "sl_places" or (table in ("sl_races", "sl_candidates") and row[0] in local_ids)
                    (fails if hard else warns)[f"text that looks like contact details in {table}.{col}"].append(str(row[0]))

    # ---- what is there
    by_level = collections.Counter(r["level"] for r in races)
    by_kind = collections.Counter(r["office_kind"] for r in local)
    reached = {c for r in local for c in json.loads(r["county_ids"] or "[]")} if not any("county_ids" in k for k in fails) else set()
    say(f"    {ST}: races by level: " + ", ".join(f"{k} {v:,}" for k, v in sorted(by_level.items())))
    say(f"    {ST}: local office kinds: " + ", ".join(f"{k} {v:,}" for k, v in by_kind.most_common()))
    say(f"    {ST}: {len(local):,} local races, {sum(len(cands.get(r['race_id'], [])) for r in local):,} candidates; "
        f"{len(reached)} of {len(counties)} counties have a local race; partisan {sum(1 for r in local if r['partisan']):,}, nonpartisan {sum(1 for r in local if not r['partisan']):,}")
    say(f"    {ST}: places: " + ", ".join(f"{k} {v:,}" for k, v in sorted(collections.Counter(k for (k, _i) in places).items())))
    gaps = collections.Counter(r[0] for r in con.execute("SELECT scope FROM sl_gaps WHERE state = ?", (ST,)))
    say(f"    {ST}: gaps: " + (", ".join(f"{k} {v:,}" for k, v in sorted(gaps.items())) or "none"))
    con.close()
    return report(ST, fails, warns, say)


def report(ST, fails, warns, say):
    for what, ids in sorted(warns.items()):
        say(f"    {ST} note: {what}: {len(ids):,} (e.g. {', '.join(sorted(set(ids))[:4])})")
    for what, ids in sorted(fails.items()):
        say(f"    {ST} FAIL: {what}: {len(ids):,} (e.g. {', '.join(sorted(set(ids))[:4])})")
    say(f"    {ST}: " + ("PASS" if not fails else f"FAIL ({len(fails)} kinds of problem)"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="Checks one state's county and local ballot rows in a trial database")
    ap.add_argument("--code", required=True, help="two-letter state code")
    ap.add_argument("--db", required=True, help="the trial database (a copy of ballot_local_2026.sqlite the loader was run against)")
    ap.add_argument("--real", default=REAL, help="the real database, opened read-only, to check nothing already loaded changed")
    a = ap.parse_args(argv)
    sys.exit(0 if check(a.code, os.path.abspath(a.db), os.path.abspath(a.real)) else 1)


if __name__ == "__main__":
    main()
