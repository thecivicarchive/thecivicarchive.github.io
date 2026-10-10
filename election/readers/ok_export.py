"""election/readers/ok_export.py - Oklahoma, from the two files John saves by hand on election night (ARCHITECTURE.md
2.5 and 5.3; John's answer D3, 2026-10-10).

The State Election Board's results site (results.okelections.us, OKER) refuses scripts at its load balancer, so no
program asks it anything: the host is on Oklahoma's never list. On the night John opens the site in his own browser,
uses its Export menu and saves two files into ballot_cache/ok/results/20261103/:

  <yyyymmdd>_StateResults.csv          one row per candidate per contest, statewide figures
  <yyyymmdd>_CountyResults_csv.zip     the same, county by county (one CSV inside)
  (<yyyymmdd>_PrecinctResults_csv.zip  the same, precinct by precinct: read too if he saves it, never required)

Every file is recognised by its first line, never by its name; a file saved twice ("name (1).csv") is handled by the
updater, which reads the newest copy. The columns are taken by name, and only these (an allowlist; the exports carry
no contact details, but nothing else is read anyway):
  elec_date, county | precinct, entity_description, race_number, race_description, race_party, tot_race_prec,
  race_prec_reporting, cand_name, cand_party, cand_absmail_votes, cand_early_votes, cand_elecday_votes,
  cand_tot_votes, race_county_owner
The same layout was seen in the exports of the 2022 and 2024 general elections and the 2026 primary and runoff.

Checks made here, beyond the store's:
  - each row's absentee-by-mail, early and Election Day votes add up to its total (a problem holds the snapshot);
  - the file is the export of the election the folder is for (a file for another date holds the snapshot);
  - county rows add up to the state file's figures when as many precincts are in; when the two files were saved at
    different moments the county figures of that contest are left out for this snapshot and the reason is noted;
  - precinct rows (when saved) add up to the county rows on the same terms.

Contests are tied to the ballot databases' races through election/crosswalk/ok.json (built from the ballot databases,
read only: `python -m election.readers.ok_export --crosswalk`): the office and district in the contest's title, the
county that owns it, and the candidates' family names, which must be exactly the list's. A contest that fits no race,
or more than one, is listed with the reason and never shown. Oklahoma prints only contested races (26 O.S. 6-102).

    python -m election.readers.ok_export --crosswalk     (re)build the crosswalk from the ballot databases
    python -m election.readers.ok_export --selftest      the fixture (2026 runoff, three contests)
    python -m election.readers.ok_export --replay        the 2026 primary and runoff, and the 2024 and 2022 generals
"""

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE = "OK"
FIPS = "40"
FEED = "ok-export"
FAMILY = "ok_export"
ELECTION = "2026-11-03"
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "ok.json")
FIXTURE = os.path.join(HERE, "election", "fixtures", "ok", "20260825")
SAVED = os.path.join(HERE, "ballot_cache", "ok", "results")
PAST = os.path.join(HERE, "ballot_cache", "ok", "place_votes")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")

COMMON = ("elec_date", "entity_description", "race_number", "race_description", "race_party", "tot_race_prec",
          "race_prec_reporting", "cand_name", "cand_party", "cand_absmail_votes", "cand_early_votes",
          "cand_elecday_votes", "cand_tot_votes", "race_county_owner")
TYPES = (("cand_absmail_votes", "mail"), ("cand_early_votes", "early"), ("cand_elecday_votes", "election_day"))
VOTE_TYPE_WORDS = {"mail": "absentee by mail", "early": "early", "election_day": "Election Day"}
# 2026's elections in Oklahoma, by the date the exports carry (the State Election Board's calendar).
ELECTIONS = {"2026-06-16": "primary", "2026-08-25": "runoff", "2026-11-03": "general"}
STATEWIDE = {
    "GOVERNOR": "governor", "LIEUTENANT GOVERNOR": "lieutenant_governor", "ATTORNEY GENERAL": "attorney_general",
    "STATE TREASURER": "state_treasurer", "SUPERINTENDENT OF PUBLIC INSTRUCTION": "superintendent_of_public_instruction",
    "COMMISSIONER OF LABOR": "labor_commissioner", "INSURANCE COMMISSIONER": "insurance_commissioner",
    "CORPORATION COMMISSIONER": "corporation_commissioner", "STATE AUDITOR AND INSPECTOR": "state_auditor",
}
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}


# ============================================================================================== names and titles

def fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def family(name):
    """The family name of a printed or filed name, as a key: 'GENTNER DRUMMOND' and 'Gentner Drummond' -> 'DRUMMOND';
    a ticket ('A | B') is keyed by its first name; 'Last, First' is understood; quotes and suffixes set aside."""
    n = fold(name).split("|")[0]
    n = re.sub(r'"[^"]*"|\([^)]*\)|“[^”]*”', " ", n)
    if "," in n:
        head, tail = n.split(",", 1)
        if re.sub(r"[^A-Za-z]", "", tail).upper() not in SUFFIX:
            n = head
    toks = [re.sub(r"[^A-Za-z'-]", "", t).upper() for t in n.split()]
    toks = [t for t in toks if t and t.strip(".") not in SUFFIX]
    return re.sub(r"[^A-Z]", "", toks[-1]) if toks else ""


def slug(name):
    s = fold(name).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "unnamed"


def title_class(title):
    """(class, district, special) of a contest title; class None for a ballot question, 'retention' for a judge's
    retention, 'president' for the electors, 'other' for anything tied by names alone."""
    t = " ".join(fold(title).upper().split())
    special = 1 if "UNEXPIRED" in t else 0
    t0 = re.sub(r"^FOR\s+", "", t)
    t0 = re.sub(r"\s*\(UNEXPIRED TERM\)", "", t0)
    if re.match(r"(STATE QUESTION|PROPOSITION)", t0):
        return None, None, special
    if t0.startswith("ELECTORS FOR PRESIDENT"):
        return "president", None, special
    if re.match(r"(SUPREME COURT|COURT OF CRIMINAL APPEALS|COURT OF CIVIL APPEALS)\b", t0):
        return "retention", None, special
    m = re.fullmatch(r"UNITED STATES SENATOR", t0)
    if m:
        return "us_senate", None, special
    m = re.fullmatch(r"UNITED STATES REPRESENTATIVE DISTRICT (\d+)", t0)
    if m:
        return "us_house", int(m.group(1)), special
    m = re.fullmatch(r"STATE SENATOR DISTRICT (\d+)", t0)
    if m:
        return "state_senate", int(m.group(1)), special
    m = re.fullmatch(r"STATE REPRESENTATIVE DISTRICT (\d+)", t0)
    if m:
        return "state_house", int(m.group(1)), special
    if t0 in STATEWIDE:
        return STATEWIDE[t0], None, special
    return "other", None, special


# ============================================================================================== the crosswalk (offline)

def build_crosswalk(path=CROSSWALK, say=print):
    """Oklahoma's 2026 races from the ballot databases (read only), with what ties a contest to each: the class, the
    district, the special mark, the counties, and the candidates' names as filed for every 2026 election."""
    races = {}
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    for rid, office, district, special in us.execute("SELECT race_id, office, district, special FROM races WHERE state=?", (STATE,)):
        cls = "us_senate" if office == "U.S. Senate" else "us_house"
        races[rid] = {"cls": cls, "district": int(district) if district and district.isdigit() else None, "special": int(special or 0),
                      "level": "congress", "office": office, "counties": None, "names": {}}
    for rid, el, name, party, order, wi in us.execute("SELECT race_id, election, name, party, ballot_order, write_in FROM candidates "
                                                      "WHERE race_id LIKE ?", (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, order, int(wi or 0)])
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    for rid, level, kind, office, district, special, cids in loc.execute(
            "SELECT race_id, level, office_kind, office, district, special, county_ids FROM sl_races WHERE state=?", (STATE,)):
        if level == "statewide":
            cls = kind
        elif kind in ("state_senate", "state_house"):
            cls = kind
        else:
            cls = "other"
        counties = None
        if cids:
            counties = json.loads(cids) if cids.strip().startswith("[") else [c.strip() for c in cids.split(",") if c.strip()]
        races[rid] = {"cls": cls, "district": int(district) if cls in ("state_senate", "state_house") and str(district or "").isdigit() else None,
                      "special": int(special or 0), "level": level, "office": office, "counties": counties, "names": {}}
    for rid, el, name, party, order, wi in loc.execute("SELECT race_id, election, name, party, ballot_order, write_in FROM sl_candidates "
                                                       "WHERE race_id LIKE ?", (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, order, int(wi or 0)])
    counties = {}
    for cid, name in loc.execute("SELECT id, name FROM sl_places WHERE kind='county' AND id LIKE ?", (FIPS + "___",)):
        counties[re.sub(r"\s+COUNTY$", "", fold(name).upper()).replace(" ", "")] = cid
    doc = {"_about": "Oklahoma's 2026 races (Congress from ballot_2026.sqlite, state and local from ballot_local_2026.sqlite, both read "
                     "only) and what ties a contest of the State Election Board's exports to each: the office class and district in "
                     "the title, the special (unexpired term) mark, the counties, and the candidates' names as filed for each 2026 "
                     "election. County keys are the export's county names without spaces.",
           "state": STATE, "built": dt.date.today().isoformat(), "races": races, "counties": counties}
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path)
    say(f"    crosswalk: {len(races)} races, {len(counties)} counties -> {os.path.relpath(path, HERE)}")
    return doc


_CW = {"mtime": None, "doc": None}


def crosswalk(path=CROSSWALK):
    m = os.path.getmtime(path)
    if _CW["mtime"] != m:
        _CW["doc"], _CW["mtime"] = json.load(open(path, encoding="utf-8")), m
    return _CW["doc"]


# ============================================================================================== reading the files

def _text(raw):
    return raw.decode("utf-8-sig", "replace") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8", "replace")


def sniff_csv(raw):
    """'state', 'county', 'precinct' or None, from a CSV's first line."""
    head = _text(raw[:600]).splitlines()[0] if raw else ""
    cells = [c.strip().lower() for c in head.split(",")]
    if not all(k in cells for k in COMMON):
        return None
    if "county" in cells:
        return "county"
    if "precinct" in cells:
        return "precinct"
    return "state"


def sniff(name, raw):
    """[(kind, csv bytes)] found in one saved file (a zip may hold one CSV)."""
    if raw[:2] == b"PK":
        out = []
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return []
        for n in z.namelist():
            if n.lower().endswith(".csv"):
                b = z.read(n)
                k = sniff_csv(b)
                if k:
                    out.append((k, b))
        return out
    k = sniff_csv(raw)
    return [(k, raw)] if k else []


def rows_of(raw, kind, problems, label):
    """The allowlisted cells of every row of one CSV."""
    rd = csv.reader(io.StringIO(_text(raw)))
    heads = [h.strip().lower() for h in next(rd)]
    unit_col = {"county": "county", "precinct": "precinct"}.get(kind)
    need = COMMON + ((unit_col,) if unit_col else ())
    idx = {k: heads.index(k) for k in need}
    out = []
    for n, r in enumerate(rd, 2):
        if not r or not any(x.strip() for x in r):
            continue
        if len(r) < len(heads) - 1:
            problems.append(f"{label} line {n}: {len(r)} cells, not the export's layout")
            continue
        c = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
        try:
            for k in ("tot_race_prec", "race_prec_reporting", "cand_absmail_votes", "cand_early_votes", "cand_elecday_votes", "cand_tot_votes"):
                c[k] = int(c[k] or 0)
        except ValueError:
            problems.append(f"{label} line {n}: a count cell is not a whole number")
            continue
        if c["cand_absmail_votes"] + c["cand_early_votes"] + c["cand_elecday_votes"] != c["cand_tot_votes"]:
            problems.append(f"{label} line {n}: absentee, early and Election Day votes do not add up to the row's total")
        if c["race_prec_reporting"] > c["tot_race_prec"]:
            problems.append(f"{label} line {n}: more precincts reporting than the contest has")
        out.append(c)
    return out


def elec_day(s):
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def county_fips(cw, name, number=None):
    if number is not None:
        return f"{FIPS}{2 * int(number) - 1:03d}"         # counties numbered 01-77 in alphabetical order, as the FIPS codes are
    return cw["counties"].get(re.sub(r"[^A-Z]", "", fold(name).upper()))


class Matcher:
    """Ties one contest to one race."""

    def __init__(self, cw):
        self.cw = cw
        self.by_cls = collections.defaultdict(list)
        for rid, e in cw["races"].items():
            self.by_cls[e["cls"]].append(rid)

    def resolve(self, election, title, party, owner_fips, names):
        """(race id or None, why). election: 'general', 'primary', 'runoff' or 'past'."""
        cls, dist, special = title_class(title)
        if cls is None:
            return None, "a ballot question, not a contest between people"
        if cls == "president":
            return None, "not on the 2026 ballot"
        if cls == "retention":
            return None, "a judge's retention question; Oklahoma's ballot list for it is not loaded"
        fams = sorted(family(n) for n in names if n.upper() not in ("YES", "NO"))
        if election == "past":
            if cls == "other":
                return None, "a past election's local contest, with no 2026 race to show it under"
            got = [r for r in self.by_cls.get(cls, []) if self.cw["races"][r]["district"] == dist]
            got = [r for r in got if self.cw["races"][r]["special"] == special] or got
            return (got[0], "") if len(got) == 1 else (None, f"{len(got)} 2026 races of this office")
        el = "general" if election == "general" else f"{election}-{party or 'NP'}"
        if cls == "other":
            pool = [r for r in self.by_cls["other"] if not owner_fips or not self.cw["races"][r]["counties"]
                    or owner_fips in self.cw["races"][r]["counties"]]
        else:
            pool = [r for r in self.by_cls.get(cls, []) if self.cw["races"][r]["district"] == dist]
            pool = [r for r in pool if self.cw["races"][r]["special"] == special] or pool

        def fits(rid):
            listed = sorted(family(n) for n, _p, _o, wi in self.cw["races"][rid]["names"].get(el, []) if not wi)
            return listed == fams

        fit = [r for r in pool if fits(r)]
        if len(fit) == 1:
            return fit[0], ""
        if len(fit) > 1:
            return None, f"{len(fit)} races fit its title and names"
        if cls != "other" and len(pool) == 1 and election == "general":
            return pool[0], ""                           # the office is certain; a name off the list is shown as printed
        return None, ("no race on the 2026 lists has this office and these candidates" if pool or cls == "other"
                      else "no 2026 race of this office is on the lists")


def read_files(files, folder_day=None, cw=None):
    """files: [(name, bytes)]. Returns the reading and notes."""
    cw = cw or crosswalk()
    problems, notes = [], []
    parts = collections.defaultdict(list)            # kind -> [rows]
    for name, raw in files:
        found = sniff(name, raw)
        if not found:
            notes.append(f"{os.path.basename(name)}: not one of the Export menu's results files; left aside")
        for kind, b in found:
            if parts[kind]:
                notes.append(f"{os.path.basename(name)}: a second {kind} file; both are read and must agree")
            parts[kind].extend(rows_of(b, kind, problems, os.path.basename(name)))
    if not parts:
        return None, notes
    days = {elec_day(r["elec_date"]) for rows in parts.values() for r in rows}
    days.discard(None)
    if len(days) != 1:
        problems.append(f"the files are exports of {len(days)} different elections ({', '.join(sorted(days))})")
    day = min(days) if days else None
    if folder_day and day and day != folder_day:
        problems.append(f"the saved files are the export of the {day} election, not of {folder_day}: save the export for "
                        f"{folder_day} (the site's election menu) into this folder")
    election = ELECTIONS.get(day, "past")
    m = Matcher(cw)

    contests = {}                                     # race number -> {...}
    for kind in ("state", "county", "precinct"):
        for r in parts.get(kind, []):
            c = contests.setdefault(r["race_number"], {"title": r["race_description"], "party": r["race_party"],
                                                       "owner": r["race_county_owner"], "entity": r["entity_description"],
                                                       "state": {}, "county": collections.defaultdict(dict),
                                                       "precinct": collections.defaultdict(dict), "rep": {}})
            if kind == "state":
                c["state"][r["cand_name"]] = r
                c["rep"]["all"] = (r["race_prec_reporting"], r["tot_race_prec"])
            elif kind == "county":
                cu = county_fips(cw, r["county"])
                if not cu:
                    problems.append(f"a county the crosswalk does not know: {r['county']!r}")
                    continue
                c["county"][cu][r["cand_name"]] = r
                c["rep"][cu] = (r["race_prec_reporting"], r["tot_race_prec"])
            else:
                p = r["precinct"]
                if not re.fullmatch(r"\d{6}", p) or not 1 <= int(p[:2]) <= 77:
                    problems.append(f"a precinct number out of the export's layout: {p!r}")
                    continue
                c["precinct"][p][r["cand_name"]] = r
                c["prep"] = (r["race_prec_reporting"], r["tot_race_prec"])       # a precinct row carries the contest's own counts

    out, unmatched, seen = [], [], {}
    for num, c in sorted(contests.items()):
        names = list(dict.fromkeys(list(c["state"]) + [n for d in c["county"].values() for n in d] +
                                   [n for d in c["precinct"].values() for n in d]))
        owner = county_fips(cw, c["owner"]) if c["owner"] else None
        rid, why = m.resolve(election, c["title"], c["party"], owner, names)
        if not rid:
            unmatched.append({"key": num, "office": c["title"] + (f" ({c['party']})" if c["party"] else ""), "why": why})
            continue
        race = cw["races"].get(rid) or {}
        if election in ("primary", "runoff"):
            rid = f"{rid}-{(c['party'] or 'np').lower()}-{election}"       # a rehearsal's own id: one race, several primaries
        if rid in seen:
            unmatched.append({"key": num, "office": c["title"], "why": f"a second contest tied to the race of contest {seen[rid]}"})
            continue
        seen[rid] = num
        el = "general" if election in ("general", "past") else f"{election}-{c['party'] or 'NP'}"
        filed = {}
        for n, p, o, wi in race.get("names", {}).get(el, []) if election != "past" else []:
            filed.setdefault(family(n), []).append((n, o))
        choices, keys = [], {}
        for i, n in enumerate(names):
            k = slug(n)
            keys[n] = k
            f = filed.get(family(n)) or []
            party = None
            for src in [c["state"]] + list(c["county"].values()) + list(c["precinct"].values()):
                if n in src:
                    party = src[n]["cand_party"] or None
                    break
            choices.append({"key": k, "name": n, "party": party, "ballot_name": f[0][0] if len(f) == 1 else None, "write_in": False,
                            "order": (f[0][1] if len(f) == 1 and f[0][1] is not None else None)})
        if len(set(keys.values())) != len(keys):
            problems.append(f"contest {num}: two candidate lines make the same key")
        units, rows, reporting = [], [], []

        def put(unit, by_name):
            for n, r in by_name.items():
                rows.append({"unit": unit, "choice": keys[n], "type": "total", "votes": r["cand_tot_votes"]})
                for col, vt in TYPES:
                    rows.append({"unit": unit, "choice": keys[n], "type": vt, "votes": r[col]})

        def sums(groups):
            s = collections.Counter()
            for by_name in groups:
                for n, r in by_name.items():
                    s[n] += r["cand_tot_votes"]
            return s

        state_rows = c["state"]
        county_ok = bool(c["county"])
        if county_ok and state_rows:
            c_in = sum(c["rep"][cu][0] for cu in c["county"])
            if c_in == c["rep"]["all"][0]:
                if sums(c["county"].values()) != collections.Counter({n: r["cand_tot_votes"] for n, r in state_rows.items()}):
                    problems.append(f"contest {num} ({c['title']}): the county rows do not add up to the state file's figures "
                                    f"with the same {c_in:,} precincts in")
            else:
                county_ok = False
                notes.append(f"contest {num}: county figures left out of this snapshot (the county file has {c_in:,} precincts in, "
                             f"the state file {c['rep']['all'][0]:,}: saved at different moments)")
        if not state_rows and c["county"]:                # no state file: the whole contest is the counties' sum
            agg = collections.defaultdict(lambda: {"cand_tot_votes": 0, **{col: 0 for col, _vt in TYPES}})
            for by_name in c["county"].values():
                for n, r in by_name.items():
                    for k in ["cand_tot_votes"] + [col for col, _vt in TYPES]:
                        agg[n][k] += r[k]
            state_rows = dict(agg)
            c["rep"]["all"] = (sum(c["rep"][cu][0] for cu in c["county"]), sum(c["rep"][cu][1] for cu in c["county"]))
        precinct_ok = bool(c["precinct"])
        if precinct_ok:
            p_in = c["prep"][0]
            if p_in == c["rep"]["all"][0]:
                if sums(c["precinct"].values()) != collections.Counter({n: r["cand_tot_votes"] for n, r in state_rows.items()}):
                    problems.append(f"contest {num} ({c['title']}): the precinct rows do not add up to the contest's figures")
            else:
                precinct_ok = False
                notes.append(f"contest {num}: precinct figures left out of this snapshot (saved at a different moment)")
        units.append({"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None})
        put("all", state_rows)
        reporting.append({"unit": "all", "in": c["rep"]["all"][0], "all": c["rep"]["all"][1]})
        if county_ok:
            for cu, by_name in sorted(c["county"].items()):
                units.append({"id": cu, "kind": "county", "name": None, "parent": STATE, "map_id": cu})
                put(cu, by_name)
                reporting.append({"unit": cu, "in": c["rep"][cu][0], "all": c["rep"][cu][1]})
        if precinct_ok:
            for p, by_name in sorted(c["precinct"].items()):
                pid = f"{FIPS}-{p}"
                units.append({"id": pid, "kind": "precinct", "name": None, "parent": county_fips(cw, None, int(p[:2])), "map_id": None})
                put(pid, by_name)
                reporting.append({"unit": pid, "in": 1, "all": 1})          # a precinct is listed once it has reported
        out.append({"race_id": rid, "key": num, "office": c["title"], "level": race.get("level"), "district": race.get("district"),
                    "seats": 1, "rule": "plurality" if election in ("general", "past") else "majority_runoff" if election == "primary" else "plurality",
                    "rcv": False, "unit_kind": "precinct" if precinct_ok else "county" if county_ok else "race",
                    "units_all": c["rep"]["all"][1], "choices": choices, "units": units, "rows": rows, "reporting": reporting,
                    "stated": [], "controls": []})
    reading = {"state": STATE, "feed": FEED, "source_time": None, "source_version": None, "election_day": day,
               "election_kind": election, "contests": out, "unmatched": unmatched, "problems": problems}
    return reading, notes


def read_folder(folder):
    """One reading from the files John saved together. (reading, info): info names the files read, their SHA-256 over all
    of them, the newest file's time (the exports state no time of their own, so a figure's time is when John saved it)."""
    names = sorted(n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n)))
    files, used = [], []
    for n in names:
        raw = open(os.path.join(folder, n), "rb").read()
        if sniff(n, raw):
            files.append((n, raw))
            used.append(n)
    base = os.path.basename(os.path.normpath(folder))
    folder_day = f"{base[:4]}-{base[4:6]}-{base[6:]}" if re.fullmatch(r"\d{8}", base) else None
    reading, notes = read_files(files, folder_day) if files else (None, [f"{n}: not one of the Export menu's results files" for n in names])
    h = hashlib.sha256()
    newest = None
    for n, raw in files:
        h.update(n.encode("utf-8") + b"\0" + raw)
        t = dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(folder, n)), dt.timezone.utc)
        newest = t if newest is None or t > newest else newest
    at = newest.isoformat(timespec="seconds").replace("+00:00", "Z") if newest else None
    if reading is None:
        reading = {"state": STATE, "feed": FEED, "contests": [], "unmatched": [], "problems": []}
    reading["source_time"] = at
    info = {"files": used, "sha256": h.hexdigest() if files else None, "saved_at": at, "notes": notes}
    return reading, info


# ============================================================================================== tests

def _check_reading(reading, say, label):
    from election import store
    con = store.connect(":memory:")
    checks = store.run_checks(con, reading)
    for n, p, d in checks:
        say(f"      {'ok  ' if p else 'FAIL'} {label}: {n}: {d[:160]}")
    return all(p for n, p, _d in checks if n in store.HARD), con


def make_fixture(say=print):
    """Three contests of the 2026 runoff (a statewide, a county and a city contest), cut from John's saved exports."""
    src = os.path.join(SAVED, "20260825")
    keep = {"12001", "12453", "41601"}
    os.makedirs(FIXTURE, exist_ok=True)
    for name in ("20260825_StateResults.csv", "20260825_CountyResults_csv.zip"):
        raw = open(os.path.join(src, name), "rb").read()
        for kind, b in sniff(name, raw):
            lines = _text(b).splitlines(True)
            cut = [lines[0]] + [ln for ln in lines[1:] if next(csv.reader([ln]))[3 if kind == "county" else 2] in keep]
            body = "".join(cut).encode("utf-8")
            if name.endswith(".zip"):
                bio = io.BytesIO()
                with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(name.replace("_csv.zip", ".csv"), body)
                body = bio.getvalue()
            open(os.path.join(FIXTURE, name), "wb").write(body)
    say(f"    fixture written: {os.path.relpath(FIXTURE, HERE)}")


def selftest(say=print):
    """No network. The fixture reads cleanly, ties its statewide contest to the Governor's race, holds a file that does not
    add up, and holds the export of another election saved into the night's folder."""
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    reading, info = read_folder(FIXTURE)
    expect(len(info["files"]) == 2, f"both saved files recognised by their first line ({info['files']})")
    good, _con = _check_reading(reading, say, "fixture")
    expect(good, "the fixture passes the store's hard checks")
    ids = {c["race_id"] for c in reading["contests"]}
    expect("2026-OK-GOV-rep-runoff" in ids, f"the Governor's runoff is tied to its race ({sorted(ids)})")
    gov = next((c for c in reading["contests"] if c["race_id"] == "2026-OK-GOV-rep-runoff"), None)
    if gov:
        tot = {r["choice"]: r["votes"] for r in gov["rows"] if r["unit"] == "all" and r["type"] == "total"}
        cty = collections.Counter()
        for r in gov["rows"]:
            if r["unit"] != "all" and r["type"] == "total":
                cty[r["choice"]] += r["votes"]
        expect(tot == dict(cty) and len([u for u in gov["units"] if u["kind"] == "county"]) == 77,
               "77 counties add up to the state file's totals")
        expect(all(ch["ballot_name"] for ch in gov["choices"]), "each line carries the name as filed")
    files = [(n, open(os.path.join(FIXTURE, n), "rb").read()) for n in sorted(os.listdir(FIXTURE))]
    bad = [(n, b.replace(b",FOR GOVERNOR\",REP,1984,1984,1,", b",FOR GOVERNOR\",REP,1984,1984,1,").replace(b"\r\n", b"\n")) for n, b in files]
    st = next(i for i, (n, _b) in enumerate(bad) if n.endswith("StateResults.csv"))
    lines = _text(bad[st][1]).splitlines()
    cells = next(csv.reader([lines[1]]))
    cells[13] = str(int(cells[13]) + 5)                                       # the total no longer adds up
    lines[1] = ",".join(f'"{x}"' for x in cells)
    bad[st] = (bad[st][0], ("\n".join(lines) + "\n").encode("utf-8"))
    r2, _n = read_files(bad, "2026-08-25")
    expect(any("do not add up" in p for p in r2["problems"]), "a row whose parts do not add up is a problem (held)")
    r3, _n = read_files(files, "2026-11-03")
    expect(any("not of 2026-11-03" in p for p in r3["problems"]), "another election's export in the night's folder is held")
    return ok


def _official(el, rid):
    out = {}
    for db, table in ((BALLOT_US, "candidates"), (BALLOT_LOCAL, "sl_candidates")):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for name, votes in con.execute(f"SELECT name, votes FROM {table} WHERE race_id=? AND election=?", (rid, el)):
            if votes is not None:
                out[family(name)] = votes
    return out


def replay_test(say=print):
    """The 2026 primary and runoff exports (John's saves of 2026-10-03, after certification): every contest tied to a race
    has statewide totals equal to the official figures the ballot loader stored for that race and election (themselves
    the State Election Board's final export: the source's own final totals); every county file adds up to the state
    file. The 2024 and 2022 general exports (county and precinct files): precincts add up to counties in every contest."""
    ok = True
    for day in ("20260616", "20260825"):
        folder = os.path.join(SAVED, day)
        reading, info = read_folder(folder)
        good, _con = _check_reading(reading, lambda s: None, day)
        compared = same = 0
        diffs = []
        for c in reading["contests"]:
            base, party, kind = re.match(r"(.+)-([a-z]+)-(primary|runoff)$", c["race_id"]).groups()
            off = _official(f"{kind}-{party.upper()}", base)
            if not off:
                continue
            tot = {}
            for r in c["rows"]:
                if r["unit"] == "all" and r["type"] == "total":
                    name = next(ch["name"] for ch in c["choices"] if ch["key"] == r["choice"])
                    tot[family(name)] = r["votes"]
            compared += 1
            if tot == off:
                same += 1
            else:
                diffs.append(c["race_id"])
        line = (f"    {day}: {len(info['files'])} files; {len(reading['contests'])} contests tied, {len(reading['unmatched'])} listed; "
                f"store checks {'pass' if good else 'FAIL'}; {same} of {compared} contests equal the official figures stored"
                + (f"; differ: {', '.join(diffs[:6])}" if diffs else "") + (f"; problems: {reading['problems'][:3]}" if reading["problems"] else ""))
        say(line)
        why = collections.Counter(u["why"] for u in reading["unmatched"])
        for w, n in why.most_common():
            say(f"        listed, not shown: {n} x {w}")
        ok = ok and good and not diffs and not reading["problems"] and compared > 0
    for day in ("20241105", "20221108"):
        folder = os.path.join(PAST, day)
        if not os.path.isdir(folder):
            continue
        reading, info = read_folder(folder)
        good, _con = _check_reading(reading, lambda s: None, day)
        n_prec = sum(1 for c in reading["contests"] if c["unit_kind"] == "precinct")
        say(f"    {day} (general): {len(info['files'])} files; {len(reading['contests'])} contests tied to a 2026 race of the same office, "
            f"{len(reading['unmatched'])} listed; precincts add up to counties in {n_prec} of {len(reading['contests'])}; store checks "
            f"{'pass' if good else 'FAIL'}" + (f"; problems: {reading['problems'][:3]}" if reading["problems"] else ""))
        ok = ok and good and not reading["problems"]
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crosswalk", action="store_true")
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--replay", action="store_true")
    a = ap.parse_args(argv)
    good = True
    if a.crosswalk:
        build_crosswalk()
    if a.fixture:
        make_fixture()
    if a.selftest:
        say = print
        say("    Oklahoma reader self-test")
        good = selftest() and good
    if a.replay:
        print("    Oklahoma replay test")
        good = replay_test() and good
    print("    PASS" if good else "    FAIL")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
