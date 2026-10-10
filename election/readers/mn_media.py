"""election/readers/mn_media.py - Minnesota's results, from the Secretary of State's "media results" files that John
saves by hand.

The Secretary's results sites show this computer a CAPTCHA, so no program here ever asks them for anything (the never
list in election/source.py refuses every *.sos.mn.gov address). On election night John saves every text file on the
election's Media Files page into states_cache/mn_local/sos/20261103/results/ (any extension; his earlier saves were
.md). This reader looks at whatever is there, decides what each file is from its first lines, never from its name,
and turns the set into one reading for election/store.py.

The results layout (the Secretary's media file description, as states/load_local_results.py and OpenElections'
Minnesota readers have it; to be confirmed on the first real file John saves), one line per candidate per area,
semicolon-separated:

   0 state (MN)          1 county ID (1-87 alphabetical; 88 or blank: statewide or several counties)
   2 precinct code (blank on summary lines)    3 office ID (four digits)    4 office name    5 district
   6 candidate order code    7 candidate name    8 suffix    9 incumbent code    10 party abbreviation
  11 precincts reporting    12 precincts voting for the office    13 votes for the candidate
  14 percent    15 total votes for the office in the area

Every cell is a public result; none is a contact detail. Reference tables the same page offers (the precinct table:
county ID; precinct code; precinct name; districts ...; the county table: county ID; name; precincts) are recognised
and used only to cross-check precinct codes; the candidate files in the parent folder are never read here.

A precinct's map id is its VTDID: 27 + (2 x county ID - 1, three digits) + precinct code (four digits). The
crosswalk (election/crosswalk/mn_precincts.json) holds every precinct on the ballot map, so a precinct the files name
that the map lacks is reported, never guessed.

A contest is tied to the ballot database's race id (election/crosswalk/mn.json) by its office ID and office name, then
the district cell, the county, and the candidates' names, in that order; a contest that does not tie to exactly one race
is listed with the reason and never shown.

    python -m election.readers.mn_media --crosswalk          rebuild both crosswalk files (reads the ballot databases and
                                                             the candidate files' allowed cells; downloads nothing)
    python -m election.readers.mn_media --check              the role's checks (crosswalk coverage, precincts reachable,
                                                             the fixture adds up, the never list)
    python -m election.readers.mn_media --read <folder> [--db election_2026.sqlite]   one snapshot from a folder
"""

import argparse
import collections
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold  # noqa: E402
from election import store  # noqa: E402

STATE = "MN"
FEED = "mn-media"
FAMILY = "mn_media"
ELECTION = "2026-11-03"
SOS_DIR = os.path.join(HERE, "states_cache", "mn_local", "sos")
NIGHT_DIR = os.path.join(SOS_DIR, "20261103", "results")
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "mn.json")
PRECINCTS = os.path.join(HERE, "election", "crosswalk", "mn_precincts.json")
FIXTURES = os.path.join(HERE, "election", "fixtures", "mn")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
GEO = os.path.join(HERE, "ballot_geo", "mn")
SOS_PRECINCT_TABLE = os.path.join(HERE, "states_cache", "mn_local", "sos_votingdistricts_attributes.json")
RESULTS_2024 = os.path.join(HERE, "states_cache", "mn_local", "sos_electionresults_2024.json")

RESULT_CELLS = 16
WRITE_IN = re.compile(r"^\s*write[- ]?ins?\b", re.I)
SKIP_EXT = {".zip", ".pdf", ".xlsx", ".xls", ".png", ".jpg", ".gif", ".json", ".part", ".crdownload", ".tmp"}


# ============================================================================================== small helpers

def norm_title(t):
    t = (t or "").replace("&", " and ").replace("Lt.", "Lieutenant").replace("Lt ", "Lieutenant ")
    return " ".join(re.sub(r"[^a-z0-9#()]+", " ", t.lower()).split())


def norm_code(c):
    """'00172' -> '172', 'ISD0001' -> 'ISD1', '10A' -> '10A', 'Ward 2' -> 'WARD2'."""
    c = re.sub(r"[^A-Za-z0-9]", "", str(c or "")).upper()
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", c)


def name_key(n):
    return " ".join(fold(n).split())


def choice_key(name):
    if WRITE_IN.match(name or ""):
        return "write-in"
    k = re.sub(r"[^a-z0-9]+", "-", name_key(name)).strip("-")
    return k[:48] or "unnamed"


def county_fips(cid):
    """The Secretary's county ID (1-87, alphabetical) -> the county FIPS code (three digits)."""
    return f"{2 * int(cid) - 1:03d}"


def vtdid(cid, code):
    return "27" + county_fips(cid) + str(code).strip().zfill(4)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================================== the crosswalks

def build_precinct_crosswalk(say=print):
    """Every precinct on the ballot map (ballot_geo/mn/precincts/*.json) by its VTDID, with the county ID and precinct
    code the Secretary's files use, checked against the Secretary's own precinct table (county ID -> FIPS) and listed
    against the 2024 official precinct results (precincts that have changed since)."""
    rows, problems = {}, []
    for path in sorted(glob.glob(os.path.join(GEO, "precincts", "27*.json"))):
        doc = json.load(open(path, encoding="utf-8"))
        for g in doc["objects"]["precincts"]["geometries"]:
            vid, p = g["id"], g.get("properties") or {}
            if not re.fullmatch(r"27\d{7}", vid):
                problems.append(f"{vid}: not a nine-digit VTDID")
                continue
            fips = vid[2:5]
            if int(fips) % 2 == 0:
                problems.append(f"{vid}: even county FIPS, no Secretary county ID fits")
                continue
            cid = (int(fips) + 1) // 2
            code = vid[5:]
            if vtdid(cid, code) != vid:
                problems.append(f"{vid}: the formula does not give it back")
            rows[vid] = [cid, code, p.get("name") or "", p.get("mcd") or ""]
    table = json.load(open(SOS_PRECINCT_TABLE, encoding="utf-8"))
    sos_ids = {}
    for r in table["rows"]:
        sos_ids[r["vtdid"]] = (int(r["countycode"]), r["countyfips"])
    disagree = [v for v, (cid, fips) in sos_ids.items() if v in rows and (rows[v][0] != cid or county_fips(cid) != fips)]
    only_map = sorted(set(rows) - set(sos_ids))
    only_sos = sorted(set(sos_ids) - set(rows))
    r24 = {r["vtdid"]: r["pctname"] for r in json.load(open(RESULTS_2024, encoding="utf-8"))["rows"]}
    counties = {}
    for vid, (cid, code, name, mcd) in rows.items():
        c = counties.setdefault(str(cid), {"fips": "27" + county_fips(cid), "precincts": 0})
        c["precincts"] += 1
    doc = {
        "_about": ("Every precinct on the ballot map (the Secretary of State's voting districts as of June 26, 2026, from the "
                   "Minnesota Geospatial Commons) by VTDID, with the Secretary's county ID and precinct code. The results files "
                   "give a county ID and a precinct code; the VTDID is worked out from them and must be a key here."),
        "formula": "VTDID = 27 + (2 x county ID - 1, three digits) + precinct code (four digits)",
        "built": dt.date.today().isoformat(),
        "sources": {"map": "ballot_geo/mn/precincts/*.json",
                    "secretary_table": {"file": os.path.relpath(SOS_PRECINCT_TABLE, HERE).replace("\\", "/"), "fetched": table.get("fetched"),
                                        "sha256": sha256_file(SOS_PRECINCT_TABLE)},
                    "results_2024": {"file": os.path.relpath(RESULTS_2024, HERE).replace("\\", "/"), "sha256": sha256_file(RESULTS_2024)}},
        "checks": {"map_precincts": len(rows), "counties": len(counties), "formula_failures": problems,
                   "county_id_disagrees_with_secretary_table": disagree, "on_map_not_in_secretary_table": only_map,
                   "in_secretary_table_not_on_map": only_sos,
                   "on_map_not_in_2024_results": sorted(set(rows) - set(r24)),
                   "in_2024_results_not_on_map": sorted(set(r24) - set(rows))},
        "counties": dict(sorted(counties.items(), key=lambda kv: int(kv[0]))),
        "precincts": {v: rows[v] for v in sorted(rows)},
        "fields": ["county ID", "precinct code", "precinct name (the map's)", "MCD FIPS"],
    }
    os.makedirs(os.path.dirname(PRECINCTS), exist_ok=True)
    with open(PRECINCTS, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    say(f"    precinct crosswalk: {len(rows):,} map precincts in {len(counties)} counties; formula failures {len(problems)}; "
        f"county ID disagreements {len(disagree)}; map only {len(only_map)}, Secretary's table only {len(only_sos)}")
    return doc


def _candidate_rows():
    """The candidate files' allowed cells only (ballot/state_local_mn.py's own readers drop everything else on the
    spot): office ID, office title, county ID, MCD, school district number, jurisdiction code and name."""
    from ballot import state_local_mn as S
    _p, grows = S.read_general_state()
    _p, lrows = S.read_general_local()
    out = []
    for r in grows:
        out.append({"file": "S", "line": r["line"], "oid": r["office_id"], "title": r["title"], "county": r["county"], "mcd": "", "sd": "",
                    "jcode": "", "name": r["name"], "congress": S.is_congress(r["title"])})
    for r in lrows:
        out.append({"file": "L", "line": r["line"], "oid": r["office_id"], "title": r["title"], "county": r["county"], "mcd": r["mcd"],
                    "sd": r["sd"], "jcode": r["jcode"], "name": r["name"], "congress": False})
    return out


def build_crosswalk(say=print):
    """crosswalk/mn.json: for every 2026 Minnesota race (state and local from ballot_local_2026.sqlite, Congress from
    ballot_2026.sqlite) the office ID, the office titles as the Secretary writes them, the counties, the codes a
    results line may carry in its district cell, and the candidates' names as filed; every race the candidate files do
    not tie to it is listed with the reason."""
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    races = {}
    for rid, level, kind, office, jid, cids, district, seat, special, partisan, note in loc.execute(
            "SELECT race_id, level, office_kind, office, jurisdiction_id, county_ids, district, seat, special, partisan, note "
            "FROM sl_races WHERE state='MN'"):
        m = re.search(r"Voters choose (\d+)", note or "")
        races[rid] = {"oid": rid.split("-")[2], "level": level, "kind": kind, "office": office, "jid": jid, "district": district, "seat": seat,
                      "special": special, "partisan": partisan, "seats": int(m.group(1)) if m else 1,
                      "fips": json.loads(cids) if cids else [], "names": [], "titles": set(), "sos_counties": set(), "codes": set()}
    for rid, name, party in loc.execute("SELECT c.race_id, c.name, c.party FROM sl_candidates c JOIN sl_races r USING (race_id) "
                                        "WHERE r.state='MN' AND c.election='general' ORDER BY c.race_id, c.ballot_order, c.name"):
        races[rid]["names"].append([name, party])
    for rid, level, office, district, seat_class, special in us.execute(
            "SELECT race_id, level, office, district, seat_class, special FROM races WHERE state='MN'"):
        races[rid] = {"oid": None, "level": "congress", "kind": "us_senate" if office == "U.S. Senate" else "us_house", "office": office,
                      "jid": "MN", "district": district, "seat": None, "special": special, "partisan": 1, "seats": 1, "fips": [],
                      "names": [], "titles": set(), "sos_counties": set(), "codes": set()}
    for rid, name, party in us.execute("SELECT race_id, name, party FROM candidates WHERE race_id LIKE '2026-MN-%' AND election='general' "
                                       "ORDER BY race_id, ballot_order, name"):
        races[rid]["names"].append([name, party])

    by_prefix = collections.defaultdict(list)
    for rid in races:
        p = rid.split("-")
        if p[2].isdigit():
            by_prefix[(p[2], rid.endswith("-S"))].append(rid)
    rows = _candidate_rows()
    unlinked = []
    for r in rows:
        special = r["title"].lower().startswith("special election for")
        if r["congress"]:
            m = re.match(r"U\.?\s?S\.?\s+Representative District (\d+)", r["title"], re.I)
            rid = f"2026-MN-H{int(m.group(1)):02d}" if m else None
            if rid is None and re.match(r"U\.?\s?S\.?\s+Senator", r["title"], re.I):
                sen = [k for k in races if re.fullmatch(r"2026-MN-S\d", k) and races[k]["special"] == (1 if special else 0)]
                rid = sen[0] if len(sen) == 1 else None
            hits = [rid] if rid in races else []
        else:
            nk = name_key(r["name"])
            hits = [rid for rid in by_prefix.get((r["oid"], special), []) if any(name_key(n) == nk for n, _p in races[rid]["names"])]
            if len(hits) > 1:
                want = set()
                if r["file"] == "S" and r["county"] != "88":
                    want.add(county_fips(r["county"]))
                if r["file"] == "S" and r["county"] == "88":
                    want.add("MN")
                for v in (r["mcd"], r["jcode"]):
                    if v:
                        want.add(v)
                if r["sd"]:
                    want |= {f"ISD{r['sd']}", f"SSD{r['sd']}"}
                narrowed = [h for h in hits if any(f"-{w}" in h for w in want)]
                hits = narrowed or hits
        if len(hits) != 1:
            unlinked.append({"file": "state, federal and county list" if r["file"] == "S" else "local list", "line": r["line"],
                             "title": r["title"], "why": "no race in the ballot databases has this candidate under this office"
                             if not hits else f"{len(hits)} races fit"})
            continue
        e = races[hits[0]]
        if e["oid"] is None:
            e["oid"] = r["oid"]
        e["titles"].add(r["title"])
        if r["county"] and r["county"] != "88":
            e["sos_counties"].add(int(r["county"]))
        for v in (r["mcd"], r["jcode"], r["sd"]):
            if v:
                e["codes"].add(norm_code(v))
    for rid, e in races.items():
        for v in (e["jid"], e["district"]):
            if v:
                e["codes"].add(norm_code(v))
        if e["jid"] and re.fullmatch(r"(ISD|SSD|CSD|HD)\d+", e["jid"]):
            e["codes"].add(norm_code(re.sub(r"^[A-Z]+", "", e["jid"])))
        for f in e["fips"]:
            if f.isdigit() and int(f) % 2 == 1:
                e["sos_counties"].add((int(f) + 1) // 2)
                e["codes"].add(norm_code(f))
    missing = [{"race": rid, "why": "no line of the Secretary's candidate files ties to this race, so its office title is not known"}
               for rid, e in sorted(races.items()) if not e["titles"]]
    out_races = {}
    for rid, e in sorted(races.items()):
        out_races[rid] = {"oid": e["oid"], "titles": sorted(e["titles"]), "level": e["level"], "kind": e["kind"], "office": e["office"],
                          "district": e["district"], "seat": e["seat"], "seats": e["seats"], "special": e["special"], "partisan": e["partisan"],
                          "counties": sorted(e["sos_counties"]), "codes": sorted(c for c in e["codes"] if c),
                          "names": e["names"]}
    doc = {
        "_about": ("Minnesota's 2026 contests (state and local from ballot_local_2026.sqlite, Congress from ballot_2026.sqlite) with "
                   "what ties a line of the Secretary of State's results files to each: the office ID, the office titles as the "
                   "Secretary's candidate files write them, the Secretary's county IDs, the codes a district cell may carry (MCD "
                   "FIPS, school district, hospital or other district, legislative or commissioner district), and the candidates' "
                   "names as filed. Built from the candidate files' allowed cells only."),
        "election": ELECTION,
        "built": dt.date.today().isoformat(),
        "order": ["office ID and office name", "district cell", "county", "candidates' names"],
        "counts": {"races": len(out_races), "state_and_local": sum(1 for r in out_races if not re.fullmatch(r"2026-MN-[HS]\d+", r)),
                   "congress": sum(1 for r in out_races if re.fullmatch(r"2026-MN-[HS]\d+", r)),
                   "with_titles": sum(1 for v in out_races.values() if v["titles"]),
                   "candidate_lines": len(rows), "candidate_lines_not_tied": len(unlinked)},
        "races": out_races,
        "not_tied": missing,
        "candidate_lines_not_tied": unlinked,
    }
    os.makedirs(os.path.dirname(CROSSWALK), exist_ok=True)
    with open(CROSSWALK, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0, separators=(",", ":"))
    say(f"    contest crosswalk: {doc['counts']['races']:,} races ({doc['counts']['state_and_local']:,} state and local, "
        f"{doc['counts']['congress']} Congress); {doc['counts']['with_titles']:,} tied to the Secretary's titles; "
        f"{len(missing)} listed; candidate lines not tied: {len(unlinked)}")
    return doc


class Matcher:
    """Ties (office ID, office name, district cell, county ID, names) to one race id, or says why not."""

    def __init__(self, crosswalk=None):
        cw = crosswalk if isinstance(crosswalk, dict) else json.load(open(crosswalk or CROSSWALK, encoding="utf-8"))
        self.races = cw["races"]
        self.by_title = collections.defaultdict(list)
        self.by_oid = collections.defaultdict(list)
        for rid, e in self.races.items():
            if e.get("oid"):
                self.by_oid[e["oid"]].append(rid)
            for t in e["titles"]:
                self.by_title[(e["oid"], norm_title(t))].append(rid)
        self._names = {rid: {name_key(n) for n, _p in e["names"]} for rid, e in self.races.items()}
        self._codes = {rid: set(e["codes"]) for rid, e in self.races.items()}
        self._cache = {}

    def resolve(self, oid, title, district="", county="", names=()):
        key = (oid, norm_title(title), norm_code(district), str(county or "").strip(), tuple(sorted({name_key(n) for n in names})))
        if key in self._cache:
            return self._cache[key]
        cands = list(self.by_title.get((oid, key[1]), []))
        how = "office ID and name"
        if not cands:
            cands = list(self.by_oid.get(oid, []))
            how = "office ID"
            if title and cands:
                special = title.lower().startswith("special election for")
                cands = [c for c in cands if bool(self.races[c]["special"]) == special] or cands
        if len(cands) > 1 and key[2]:
            n = [c for c in cands if key[2] in self._codes[c]]
            if n:
                cands, how = n, how + ", district"
        if len(cands) > 1 and key[3] and key[3] != "88" and key[3].isdigit():
            n = [c for c in cands if int(key[3]) in self.races[c]["counties"]]
            if n:
                cands, how = n, how + ", county"
        if len(cands) > 1 and key[4]:
            real = [k for k in key[4] if k and not WRITE_IN.match(k)]
            score = {c: len(set(real) & self._names[c]) for c in cands}
            best = max(score.values()) if score else 0
            top = [c for c in cands if score[c] == best]
            if best > 0 and len(top) == 1:
                cands, how = top, how + ", names"
        if len(cands) == 1:
            out = (cands[0], how, None)
        elif not cands:
            out = (None, how, "no 2026 race has this office ID" + (" and name" if title else ""))
        else:
            out = (None, how, f"{len(cands)} races fit and nothing in the line tells them apart")
        self._cache[key] = out
        return out


# ============================================================================================== reading the files

def _lines(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return raw, [ln for ln in text.splitlines() if ln.strip()]


def sniff(lines):
    """What a file is, from its first lines: 'results', 'precinct_table', 'county_table', 'candidates' (never read
    here), 'web_page' (saved as a page, not as text) or 'other'."""
    head = lines[:5]
    if not head:
        return "other"
    if head[0].lstrip().lower().startswith(("<!doctype", "<html")):
        return "web_page"
    cells = [ln.split(";") for ln in head]
    first = cells[0]
    if 14 <= len(first) <= 18 and first[0].strip() == "MN" and re.fullmatch(r"\d{4}", first[3].strip()):
        return "results"          # every line is then checked one by one; a bad line holds the snapshot
    if all(len(c) in (18, 20, 21) for c in cells):
        return "candidates"
    if all(8 <= len(c) <= 12 and re.fullmatch(r"\d{1,2}", c[0].strip()) and re.fullmatch(r"[0-9A-Za-z]{1,4}", c[1].strip()) for c in cells):
        return "precinct_table"
    if all(2 <= len(c) <= 4 and re.fullmatch(r"\d{1,2}", c[0].strip()) and re.fullmatch(r"[A-Za-z .'-]+", c[1].strip()) for c in cells):
        return "county_table"
    return "other"


def folder_files(folder):
    """(results files, reference files, other files listed) in a folder, each as (path, kind, raw bytes, lines)."""
    results, refs, others = [], [], []
    for path in sorted(glob.glob(os.path.join(folder, "*"))):
        if not os.path.isfile(path) or os.path.splitext(path)[1].lower() in SKIP_EXT:
            continue
        raw, lines = _lines(path)
        kind = sniff(lines)
        item = (path, kind, raw, lines)
        (results if kind == "results" else refs if kind in ("precinct_table", "county_table") else others).append(item)
    return results, refs, others


def read_folder(folder, crosswalk=None, precincts=None, practice=False):
    """One reading from every results file in a folder (one snapshot: the files John saved together).

    Returns (reading, info): info carries the files read, their SHA-256 over all of them, the newest file's time (when
    John saved it: the files state no time of their own) and notes."""
    matcher = crosswalk if isinstance(crosswalk, Matcher) else Matcher(crosswalk)
    pc = precincts if isinstance(precincts, dict) else json.load(open(precincts or PRECINCTS, encoding="utf-8"))
    map_precincts = pc["precincts"]
    results, refs, others = folder_files(folder)
    problems, notes = [], []
    for path, kind, _raw, _lines_ in others:
        if kind == "web_page":
            problems.append(f"{os.path.basename(path)} was saved as a web page, not as text: save the file itself (right-click, Save link as)")
        elif kind != "candidates":
            notes.append(f"{os.path.basename(path)}: not a results file; left aside")
    ref_codes = set()
    for path, kind, _raw, lines in refs:
        if kind == "precinct_table":
            for ln in lines:
                c = ln.split(";")
                if c[0].strip().isdigit() and c[1].strip():
                    ref_codes.add(vtdid(int(c[0]), c[1].strip()))
    h = hashlib.sha256()
    newest = None
    for path, _k, raw, _l in results:
        h.update(os.path.basename(path).encode("utf-8") + b"\0" + raw)
        t = dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc)
        newest = t if newest is None or t > newest else newest

    # ---- every line, allowed cells only (all sixteen are public results)
    groups = collections.defaultdict(list)          # (oid, title, district, county) -> [row]
    for path, _k, _raw, lines in results:
        base = os.path.basename(path)
        mtime = os.path.getmtime(path)
        for n, ln in enumerate(lines, 1):
            c = [x.strip() for x in ln.split(";")]
            if len(c) < 14 or c[0] != "MN":
                problems.append(f"{base} line {n}: {len(c)} cells, not the results layout")
                continue
            c = (c + [""] * RESULT_CELLS)[:RESULT_CELLS]
            try:
                row = {"file": base, "mtime": mtime, "line": n, "county": c[1], "precinct": c[2], "oid": c[3], "title": c[4], "district": c[5],
                       "order": c[6], "name": (c[7] + (" " + c[8] if c[8] else "")).strip(), "party": c[10],
                       "in": int(c[11] or 0), "all": int(c[12] or 0), "votes": int(c[13] or 0),
                       "total": int(c[15]) if c[15].isdigit() else None}
            except ValueError:
                problems.append(f"{base} line {n}: a count cell is not a whole number")
                continue
            if not re.fullmatch(r"\d{4}", row["oid"]) or not (row["county"] == "" or (row["county"].isdigit() and 1 <= int(row["county"]) <= 88)):
                problems.append(f"{base} line {n}: office ID or county ID out of range")
                continue
            groups[(row["oid"], row["title"], row["district"], row["county"])].append(row)

    # ---- tie each group to a race
    by_race = collections.defaultdict(list)
    unmatched = {}
    for (oid, title, district, county), rows in groups.items():
        rid, how, why = matcher.resolve(oid, title, district, county, [r["name"] for r in rows])
        if rid is None:
            k = f"{oid}|{title}|{district}"
            u = unmatched.setdefault(k, {"key": k, "office": title, "why": why, "lines": 0})
            u["lines"] += len(rows)
            continue
        for r in rows:
            by_race[rid].append(r)

    contests = []
    not_on_map = set()
    for rid, rows in sorted(by_race.items()):
        e = matcher.races[rid]
        filed = {name_key(n): (n, p) for n, p in e["names"]}
        choices, ckeys = {}, {}
        for r in rows:
            k = choice_key(r["name"])
            if k not in choices:
                f = filed.get(name_key(r["name"]))
                choices[k] = {"key": k, "name": r["name"], "party": r["party"] or None, "ballot_name": f[0] if f else None,
                              "write_in": k == "write-in", "order": int(r["order"]) if r["order"].isdigit() else None}
            ckeys[(r["name"])] = k
        units, vals, rep, stated, controls = {}, {}, {}, {}, []
        summary = collections.defaultdict(list)
        for r in rows:
            if r["precinct"]:
                cid = int(r["county"]) if r["county"].isdigit() else 0
                if not 1 <= cid <= 87:
                    problems.append(f"{r['file']} line {r['line']}: a precinct line with county ID {r['county'] or 'blank'}")
                    continue
                vid = vtdid(cid, r["precinct"])
                if vid not in map_precincts:
                    not_on_map.add(vid)
                units[vid] = {"id": vid, "kind": "precinct", "name": map_precincts.get(vid, [None, None, None])[2] or None,
                              "parent": "27" + county_fips(cid), "map_id": vid if vid in map_precincts else None}
                _put(vals, rep, stated, problems, vid, r, ckeys[r["name"]])
            else:
                summary[r["county"]].append(r)
        if summary:
            keys = sorted(summary)
            if len(keys) == 1:
                tot_key, parts = keys[0], []
            elif "88" in summary or "" in summary:
                tot_key = "88" if "88" in summary else ""
                parts = [k for k in keys if k != tot_key]
            else:
                tot_key, parts = None, keys
            for k in parts:
                cu = "27" + county_fips(int(k))
                units[cu] = {"id": cu, "kind": "county", "name": None, "parent": "MN", "map_id": cu}
                for r in summary[k]:
                    _put(vals, rep, stated, problems, cu, r, ckeys[r["name"]])
            if tot_key is not None:
                units["all"] = {"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}
                for r in summary[tot_key]:
                    _put(vals, rep, stated, problems, "all", r, ckeys[r["name"]])
                    if any(u["kind"] == "precinct" for u in units.values()):
                        controls.append({"choice": ckeys[r["name"]], "votes": r["votes"], "in": r["in"], "from": r["file"]})
        n_prec = sum(1 for u in units.values() if u["kind"] == "precinct")
        contests.append({
            "race_id": rid, "key": f"{e['oid']}|{rows[0]['title']}|{rows[0]['district']}", "office": rows[0]["title"], "level": e["level"],
            "district": e.get("district"), "seats": e.get("seats") or 1, "rule": "plurality", "rcv": False,
            "unit_kind": "precinct" if n_prec else "county" if any(u["kind"] == "county" for u in units.values()) else "race",
            "units_all": rep.get("all", {}).get("all") or (n_prec or None),
            "choices": sorted(choices.values(), key=lambda c: (c["write_in"], c["order"] if c["order"] is not None else 9999, c["name"])),
            "units": list(units.values()),
            "rows": [{"unit": u, "choice": ck, "type": "total", "votes": v} for (u, ck), v in sorted(vals.items())],
            "reporting": [{"unit": u, "in": x["in"], "all": x["all"], "ballots": None, "registered": None} for u, x in sorted(rep.items())],
            "stated": [{"unit": u, "total": t} for u, t in sorted(stated.items()) if t is not None],
            "controls": controls,
        })
    if not_on_map:
        notes.append(f"{len(not_on_map)} precinct(s) in the files are not on the ballot map (kept, not drawn): " + ", ".join(sorted(not_on_map)[:10]))
    if ref_codes:
        missing = sorted(set(map_precincts) - ref_codes)
        notes.append(f"the Secretary's precinct table names {len(ref_codes):,} precincts; {len(missing)} map precincts are not in it")
    reading = {"state": STATE, "feed": FEED, "source_time": newest.isoformat(timespec="seconds").replace("+00:00", "Z") if newest else None,
               "source_version": None, "contests": contests, "unmatched": list(unmatched.values()), "problems": problems,
               "practice": bool(practice)}
    info = {"files": [os.path.basename(p) for p, *_ in results], "sha256": h.hexdigest() if results else None,
            "saved_at": reading["source_time"], "notes": notes, "rows": sum(len(v) for v in groups.values())}
    return reading, info


def _put(vals, rep, stated, problems, unit, r, ck):
    """One line into a unit. The same line twice (two files carry it) must agree; when they do not, the line with more
    precincts in is the newer and wins, and a true disagreement (same precincts in, different votes) is a problem."""
    k = (unit, ck)
    old = rep.get(unit)
    if k in vals:
        if vals[k] == r["votes"] and old and old["in"] == r["in"]:
            return
        if old and r["in"] != old["in"]:
            if r["in"] < old["in"]:
                return
        elif vals[k] != r["votes"]:
            problems.append(f"{r['file']} line {r['line']}: disagrees with another file for the same contest and area")
            return
    vals[k] = r["votes"]
    rep[unit] = {"in": r["in"], "all": r["all"]}
    if r["total"] is not None:
        if unit in stated and stated[unit] is not None and stated[unit] != r["total"] and old and old["in"] == r["in"]:
            problems.append(f"{r['file']} line {r['line']}: two different contest totals for one area")
        stated[unit] = r["total"]


def load_folder(con, folder, test=False, practice=False, crosswalk=None, precincts=None, say=print):
    """One snapshot from a folder into the store. Returns (snapshot id, status, info)."""
    store.ensure_election(con, STATE, certifying_body="Minnesota State Canvassing Board",
                          note="The county canvassing boards meet Nov 6 to 11; the State Canvassing Board on Thu Nov 19, 2026 (Minn. Stat. 204C.33).")
    store.ensure_feed(con, STATE, FEED, FAMILY, "John's saves into states_cache/mn_local/sos/20261103/results/", "hand")
    reading, info = read_folder(folder, crosswalk, precincts, practice)
    if not info["files"]:
        say(f"    MN: no results files in {folder} yet")
        return None, "failed", info
    sid, status = store.begin_snapshot(con, STATE, FEED, info["sha256"], raw_path=folder, source_time=info["saved_at"],
                                       note="; ".join(info["notes"])[:2000] or None, test=test)
    if status == "same":
        store.end_snapshot(con, sid, "same", rows=0)
        return sid, "same", info
    status, checks = store.record(con, sid, reading)
    if test and status == "ok":
        store.end_snapshot(con, sid, "test")
        status = "test"
    store.feed_outcome(con, STATE, FEED, status in ("ok", "test", "same"), None if status != "held" else "a check failed")
    info["checks"] = checks
    info["unmatched"] = reading["unmatched"]
    return sid, status, info


# ============================================================================================== the fixture

FIXTURE_COUNTIES = ("001", "031", "077")          # Aitkin, Cook, Lake of the Woods: small, and far apart
FIXTURE_SENATE = (("ussenr", "03", "Royce White", "R"), ("ussendfl", "04", "Amy Klobuchar", "DFL"),
                  ("ussenlib", "11", "Rebecca Whiting", "LIB"), ("ussenia", "12", "Joyce Lacey", "IA"),
                  ("ussenwi", "90", "WRITE-IN", "WI"))


def make_fixture(say=print):
    """fixtures/mn/night/: the 2024 U.S. Senate count in three counties, written in the media file layout from the
    Secretary of State's official 2024 precinct results (Minnesota Geospatial Commons, already on disk). A test file:
    the figures are official, the office ID and order codes are the layout's, and the three counties stand in for the
    state on the summary lines."""
    src = json.load(open(RESULTS_2024, encoding="utf-8"))
    pc = json.load(open(PRECINCTS, encoding="utf-8"))
    rows = sorted((r for r in src["rows"] if r["countyfips"] in FIXTURE_COUNTIES), key=lambda r: r["vtdid"])
    folder = os.path.join(FIXTURES, "night")
    os.makedirs(folder, exist_ok=True)
    prec, summ, table = [], [], []
    tot = collections.Counter()
    for r in rows:
        cid = (int(r["countyfips"]) + 1) // 2
        code = r["vtdid"][5:]
        total = r["ussentotal"]
        for col, order, name, party in FIXTURE_SENATE:
            v = r[col] or 0
            tot[col] += v
            pct = f"{100.0 * v / total:.2f}" if total else "0.00"
            prec.append(f"MN;{cid};{code};0102;U.S. Senator;;{order};{name};;;{party};1;1;{v};{pct};{total}")
        tot["total"] += total
        if r["vtdid"] not in pc["precincts"]:
            say(f"      note: {r['vtdid']} (2024) is not on the 2026 map")
        # the congressional district and soil and water cells are left blank: the 2024 results file does not carry them
        table.append(f"{cid};{code};{r['pctname']};;{r['mnlegdist']};{r['ctycomdist']};{r['juddist']};;{r['mcdfips']};")
    n = len(rows)
    for col, order, name, party in FIXTURE_SENATE:
        pct = f"{100.0 * tot[col] / tot['total']:.2f}"
        summ.append(f"MN;88;;0102;U.S. Senator;;{order};{name};;;{party};{n};{n};{tot[col]};{pct};{tot['total']}")
    files = {"ussenate_precincts.txt": prec, "ussenate_summary.txt": summ, "precinct_table.txt": table,
             "county_table.txt": [f"{(int(f) + 1) // 2};{({'001': 'Aitkin', '031': 'Cook', '077': 'Lake of the Woods'})[f]};"
                                  f"{sum(1 for r in rows if r['countyfips'] == f)}" for f in FIXTURE_COUNTIES]}
    for name, lines in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("\n".join(lines) + "\n")
    say(f"    fixture: {n} precincts in {len(FIXTURE_COUNTIES)} counties, {len(prec)} precinct lines, written to {folder}")
    return {"precincts": n, "totals": dict(tot), "source_sha256": sha256_file(RESULTS_2024), "source_fetched": src.get("fetched")}


# ============================================================================================== checks

def check_crosswalk(say=print, cw=None):
    """Every race tied to the Secretary's titles or listed; every race found again from a line made of its own office
    ID, title, county and names, with the district cell blank and with each code it carries."""
    cw = cw or json.load(open(CROSSWALK, encoding="utf-8"))
    m = Matcher(cw)
    races = cw["races"]
    listed = {x["race"] for x in cw["not_tied"]}
    uncovered = [r for r, e in races.items() if not e["titles"] and r not in listed]
    lost = []
    tried = 0
    for rid, e in races.items():
        if not e["titles"]:
            continue
        names = [n for n, _p in e["names"]]
        counties = [str(c) for c in e["counties"]] or ["88"]
        for title in e["titles"]:
            for district in [""] + list(e["codes"])[:3]:
                for county in counties[:2]:
                    tried += 1
                    got, _how, why = m.resolve(e["oid"], title, district, county, names)
                    if got != rid:
                        lost.append(f"{rid} ({title}; district '{district}'; county {county}): {why or 'tied to ' + str(got)}")
    st_local = cw["counts"]["state_and_local"]
    congress = cw["counts"]["congress"]
    ok = not uncovered and not lost
    say(f"    crosswalk: {st_local:,} state and local + {congress} Congress races; {len(listed)} listed with a reason; "
        f"{len(uncovered)} neither tied nor listed; {tried:,} made-up lines tried, {len(lost)} not found again")
    for x in lost[:10]:
        say(f"      not found again: {x}")
    return ok, {"state_and_local": st_local, "congress": congress, "listed": len(listed), "uncovered": uncovered, "lost": lost}


def check_precincts(say=print, pc=None):
    pc = pc or json.load(open(PRECINCTS, encoding="utf-8"))
    bad = [v for v, (cid, code, _n, _m) in pc["precincts"].items() if vtdid(cid, code) != v]
    ch = pc["checks"]
    ok = not bad and not ch["formula_failures"] and not ch["county_id_disagrees_with_secretary_table"] and len(pc["precincts"]) == ch["map_precincts"]
    say(f"    precincts: {len(pc['precincts']):,} map precincts, every one reachable from a county ID and precinct code: "
        f"{'yes' if not bad else 'no (' + str(len(bad)) + ')'}; county IDs agree with the Secretary's table: "
        f"{'yes' if not ch['county_id_disagrees_with_secretary_table'] else 'no'}; changed since 2024: "
        f"{len(ch['on_map_not_in_2024_results'])} new, {len(ch['in_2024_results_not_on_map'])} gone")
    return ok


def check_fixture(say=print):
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="mn_media_")
    try:
        con = store.connect(os.path.join(tmp, "t.sqlite"))
        folder = os.path.join(FIXTURES, "night")
        sid, status, info = load_folder(con, folder, practice=True, say=lambda *_: None)
        c = {n: (p, d) for n, p, d in info.get("checks", [])}
        ok = status == "ok" and c.get("units_add_up", (0,))[0]
        say(f"    fixture ({', '.join(info['files'])}): {status}; precinct rows add up to each office's total: "
            f"{'yes' if c.get('units_add_up', (0,))[0] else 'no'} ({c.get('units_add_up', (0, ''))[1][:160]})")
        con.close()
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_never(say=print):
    from election.source import Refused, Source
    calls = []
    src = Source(replay=lambda url: calls.append(url) or (200, b"", {}), log=lambda *_: None, never_extra=(), stopped_file=None)
    refused = 0
    for url in ("https://electionresults.sos.mn.gov/", "https://electionresultsfiles.sos.mn.gov/20261103/ussenate.txt",
                "https://candidates.sos.mn.gov/", "https://www.sos.mn.gov/", "https://sos.mn.gov/", "http://pollfinder.sos.mn.gov/"):
        try:
            src.get(url)
        except Refused:
            refused += 1
    ok = refused == 6 and not calls
    say(f"    never list: {refused} of 6 Minnesota Secretary of State addresses refused before any request; requests made: {len(calls)}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crosswalk", action="store_true", help="rebuild both crosswalk files")
    ap.add_argument("--check", action="store_true", help="run the checks")
    ap.add_argument("--read", metavar="FOLDER", help="read one folder of saved files into the store")
    ap.add_argument("--db", default=store.DB)
    ap.add_argument("--practice", action="store_true")
    ap.add_argument("--make-fixture", action="store_true", help="rewrite fixtures/mn/night/ from the official 2024 precinct results")
    a = ap.parse_args(argv)
    if a.crosswalk:
        build_precinct_crosswalk()
        build_crosswalk()
    if a.make_fixture:
        print(json.dumps(make_fixture(), indent=1))
    if a.check:
        print("    Minnesota reader checks")
        results = [store.selftest(say=lambda *_: None), check_crosswalk()[0], check_precincts(), check_fixture(), check_never()]
        print("    store self-test: " + ("PASS" if results[0] else "FAIL"))
        print("    " + ("PASS" if all(results) else "FAIL"))
        return 0 if all(results) else 1
    if a.read:
        con = store.connect(a.db)
        sid, status, info = load_folder(con, a.read, practice=a.practice)
        print(f"    MN snapshot {sid}: {status}; {len(info['files'])} files, {info['rows']:,} lines; "
              f"{len(info.get('unmatched') or [])} contests listed, not shown")
        for n, p, d in info.get("checks", []):
            print(f"      {'ok  ' if p else 'FAIL'} {n}: {d[:200]}")
        for n in info["notes"]:
            print(f"      note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
