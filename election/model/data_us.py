"""election/model/data_us.py - the past results, places and races the forecasts for the other states read (ARCHITECTURE.md
4.2; model.md 4). Owned by N18. Nothing here is a result of 2026; every figure is about a place, never a voter.

    python -m election.model.data_us --build             fetch what is missing (once) and summarise every file
    python -m election.model.data_us --check             the controls: MEDSL's sums against the Clerk's official totals
    python -m election.model.data_us --selftest          the readers on made-up text; reads no real file

WHAT IT READS (never writes any of them)
  The Clerk of the U.S. House, "Statistics of the Presidential and Congressional Election", 2020, 2022 and 2024 (PDF, the
    kit's own copies in ballot_cache/): every state's presidential, Senate and House votes. OFFICIAL.
  MEDSL (MIT Election Data and Science Lab), 2022 and 2024 precinct returns for every state (CC0; GitHub,
    MEDSL/2022-elections-official and MEDSL/2024-elections-official, individual_states/): governors and the other
    statewide offices, and each precinct's congressional district, so a statewide contest can be added up by district and
    by county. SECONDARY, labelled; checked against the Clerk's totals (--check). John's yes: D4, 2026-10-10.
  The Census Bureau's ACS 2020-2024 five-year tables already on disk (states_cache/acs2024/): county figures. John's yes:
    D5, 2026-10-10.
  ballot_2026.sqlite and ballot_local_2026.sqlite (read only): the 2026 races and their candidates as filed.
  congress_119.sqlite (read only): who sat in Congress on a past Election Day (the "sitting member" of the backtests).

WHAT IT WRITES: election_cache/model/us/ only (the downloads, kept whole and never published, and small JSON summaries
keyed by each source file's SHA-256). Every request goes through election/source.py.

PRIVACY: MEDSL's files name candidates and precincts only; fields are allowlisted (MEDSL_KEEP). The Clerk's statistics
name candidates. No address, telephone or e-mail is in any of these sources or kept.
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sqlite3
import sys
import time
import zipfile
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import CACHE_ROOT, load_json, save_json, sha_bytes, sha_file  # noqa: E402

DATA_METHOD = "data-us-1.4"
CACHE = os.path.join(CACHE_ROOT, "us")
FED_DB = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL_DB = os.path.join(HERE, "ballot_local_2026.sqlite")
RECORD_DB = os.path.join(HERE, "congress_119.sqlite")
ACS = os.path.join(HERE, "states_cache", "acs2024")
CLERK_PDF = {y: os.path.join(HERE, "ballot_cache", "ok", "place_votes", f"clerk_statistics{y}.pdf") for y in (2020, 2022, 2024)}
CLERK_URL = "https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf"
MEDSL_REPO = {2022: "https://raw.githubusercontent.com/MEDSL/2022-elections-official/main/individual_states/2022-{c}-local-precinct-general.zip",
              2024: "https://raw.githubusercontent.com/MEDSL/2024-elections-official/main/individual_states/{c}24.zip"}
MEDSL_KEEP = ("precinct", "office", "party_simplified", "party_detailed", "mode", "votes", "county_fips", "jurisdiction_fips", "candidate",
              "district", "stage", "special", "writein", "magnitude")
ELECTION_DAY = {2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}

STATES = {"ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA", "COLORADO": "CO",
          "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
          "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
          "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
          "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
          "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
          "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
          "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
          "WISCONSIN": "WI", "WYOMING": "WY"}
CODES = sorted(STATES.values())
NAME_OF = {v: k.title() for k, v in STATES.items()}
FIPS = {"AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
        "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
        "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
        "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
        "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"}
AT_LARGE = ("AK", "DE", "ND", "SD", "VT", "WY")
# states whose congressional lines changed between the 2022 and 2024 elections (court orders and new plans): their 2022
# House results do not describe the 2024 districts, so the 2024 House backtest leaves them out
LINES_CHANGED_2024 = ("AL", "GA", "LA", "NY", "NC", "OH")
SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}
NOT_CANDIDATES = re.compile(r"^([^A-Za-z]*|blanks?( votes)?|void|scatter(ing)?|over ?votes|under ?votes|"
                            r"write-?ins?( votes)?( \([^)]*\))?|total|"
                            r"none of these candidates|all others|others|miscellaneous|blank/void|no candidate|"
                            r"total votes( cast)?|total ballots( cast)?|continuing ballots?|exhausted ballots?|"
                            r"other write-?ins?|under ?votes?|over ?votes?)$", re.I)

# statewide offices by MEDSL's office names: the class the model gives each (governor; the rest are "other")
STATEWIDE_OFFICES = [
    ("governor", re.compile(r"^GOVERNOR( AND LIEUTENANT GOVERNOR)?$|^GOVERNOR/LIEUTENANT GOVERNOR$")),
    ("ussen", re.compile(r"^US SENATE$")),
    ("usprs", re.compile(r"^US PRESIDENT$")),
    ("other", re.compile(r"^(STATE )?(ATTORNEY GENERAL|SECRETARY OF STATE|(STATE )?TREASURER|(STATE )?AUDITOR( OF (PUBLIC )?ACCOUNTS| OF STATE)?|"
                         r"(STATE )?COMPTROLLER( OF PUBLIC ACCOUNTS)?|(STATE )?CONTROLLER|LIEUTENANT GOVERNOR|"
                         r"(STATE )?SUPERINTENDENT OF PUBLIC INSTRUCTION|COMMISSIONER OF AGRICULTURE( AND INDUSTRIES)?|"
                         r"AGRICULTURE COMMISSIONER|COMMISSIONER OF INSURANCE|INSURANCE COMMISSIONER|COMMISSIONER OF LABOR|"
                         r"LABOR COMMISSIONER|COMMISSIONER OF (PUBLIC|STATE) LANDS|LAND COMMISSIONER|COMMISSIONER OF THE GENERAL LAND OFFICE|"
                         r"RAILROAD COMMISSIONER|CORPORATION COMMISSIONER|TAX COMMISSIONER|CHIEF FINANCIAL OFFICER|STATE MINE INSPECTOR|"
                         r"COMMISSIONER OF SCHOOL AND PUBLIC LANDS|SECRETARY OF AGRICULTURE|COMPTROLLER GENERAL|STATE SUPERINTENDENT)$")),
]


def say_default(*a):
    print(*a, flush=True)


def cache_path(*parts):
    p = os.path.join(CACHE, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def expit(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def side(party):
    """D, R or O from a party label as the Clerk, MEDSL or the ballot lists print it."""
    p = str(party or "").strip().upper()
    if p in ("D", "DEM", "DFL") or p.startswith("DEMOCRAT"):
        return "D"
    if p in ("R", "REP") or p.startswith("REPUBLICAN"):
        return "R"
    return "O"


def person_tokens(name):
    n = re.split(r"\s+and\s+|\s*/\s*", str(name or ""), maxsplit=1, flags=re.I)[0]
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"|“[^”]*”|�[^�]*�", " ", n)
    if "," in n:                                   # "LAST, FIRST" and "Name, Jr."
        a, b = n.split(",", 1)
        n = a if re.sub(r"[^A-Za-z]", "", b).upper() in SUFFIXES else f"{b} {a}"
    toks = [t for t in re.sub(r"[^A-Z ]", " ", n.upper().replace("'", "")).split() if t not in SUFFIXES]
    return [t for t in toks if len(t) > 1] or toks


def same_person(a, b):
    ta, tb = person_tokens(a), person_tokens(b)
    if not ta or not tb or ta[-1] != tb[-1]:
        return False
    fa, fb = ta[0], tb[0]
    return fa == fb or (len(fa) >= 3 and len(fb) >= 3 and (fa.startswith(fb) or fb.startswith(fa))) or \
        any(t == fb for t in ta[:-1]) or any(t == fa for t in tb[:-1])


def two_party(cands):
    """(D votes, R votes, all votes, contested) for a contest's [name, party, votes] lines: contested means exactly one
    candidate of each big party."""
    d = [v for _n, p, v in cands if side(p) == "D" and v is not None]
    r = [v for _n, p, v in cands if side(p) == "R" and v is not None]
    tot = sum(v for _n, _p, v in cands if v is not None)
    return (sum(d), sum(r), tot, len(d) == 1 and len(r) == 1 and d[0] > 0 and r[0] > 0)


# ============================================================================================== the Clerk's statistics

TOTAL_ROW = re.compile(r"\bTOTALS?\b", re.I)
LINE = re.compile(r"^(.*?)\s*\.{3,}\s*([\d,]+|\(\d\))\s*$")


def parse_clerk_lines(lines):
    """{code: {"president": [[label, party, votes]], "senate": [{"term": ..., "cands": [...]}], "house": {district:
    {"cands": [[name, party, votes]], "unopposed": bool, "term": ...}}}} from the PDF's text lines (page, y, text).
    A line with a party alone and no name (New York's fusion lines) is added to the candidate above it."""
    out = {}
    state = section = None
    dist = None
    term = None
    recap = False
    for _p, _y, raw in lines:
        t = raw.strip()
        if not t:
            continue
        m = re.match(r"^([A-Z][A-Z .]+?)\W*CONTINUED$", t.upper())
        head = t.upper() if t.upper() in STATES else (m.group(1).strip() if m and m.group(1).strip() in STATES else None)
        if head:
            if state != STATES[head]:
                section, dist, term = None, None, None
            state, recap = STATES[head], False
            out.setdefault(state, {"president": [], "senate": [], "house": {}})
            continue
        if re.match(r"^[A-Z][A-Z .]+$", t) and t not in STATES and t not in ("AT LARGE",) and len(t) > 6 and \
                not t.startswith("FOR "):
            state = None                           # a territory's heading (AMERICAN SAMOA, GUAM ...)
            continue
        if state is None:
            continue
        if t.startswith("Recapitulation of Votes"):
            recap = True
            continue
        if recap:
            continue
        if t.upper().startswith("FOR "):
            s = re.sub(r"\W*CONTINUED$", "", t.upper()).strip()
            new = {"FOR PRESIDENTIAL ELECTORS": "president", "FOR UNITED STATES SENATOR": "senate",
                   "FOR UNITED STATES REPRESENTATIVE": "house"}.get(s, "other")
            if new != section:
                section, term = new, None
                if new == "senate":
                    out[state]["senate"].append({"term": None, "cands": []})
            continue
        if t.startswith("(For") or t.startswith("(To "):
            term = t.strip("()")
            if section == "senate":
                cur = out[state]["senate"][-1]
                if cur["cands"] or cur["term"]:
                    out[state]["senate"].append({"term": term, "cands": []})
                else:
                    cur["term"] = term
            continue
        if section == "house" and t.upper() in ("AT LARGE", "AT-LARGE"):
            dist = 0
            out[state]["house"].setdefault(dist, {"cands": [], "unopposed": False, "term": term})
            continue
        lm = LINE.match(t)
        if not lm or section not in ("president", "senate", "house"):
            continue
        label, num = lm.group(1).strip(), lm.group(2)
        if section == "house":
            dm = re.match(r"^(\d+)\.\s*(.*)$", label)
            if dm:
                dist = int(dm.group(1))
                label = dm.group(2).strip()
                if dist in out[state]["house"] and term:
                    dist = f"{dist}{'-special' if 'unexpired' in term.lower() or 'vacancy' in term.lower() else ''}"
                out[state]["house"].setdefault(dist, {"cands": [], "unopposed": False, "term": term})
            if dist is None:
                continue
        if re.match(r"^\d{4,},", num):
            # a footnote mark printed before a figure ("1146,142": Maine's 2022 ranked-choice second round): the digits
            # before a valid group of three are the mark
            num = re.sub(r"^\d+?(\d{1,3},)", r"\1", num)
        votes = None if num.startswith("(") else int(num.replace(",", ""))
        if section == "president":
            target = out[state]["president"]
            if NOT_CANDIDATES.match(label):
                continue
            target.append([label, label, votes])
            continue
        target = out[state]["senate"][-1]["cands"] if section == "senate" else out[state]["house"][dist]["cands"]
        if votes is None and section == "house":
            out[state]["house"][dist]["unopposed"] = True
        if "," in label:
            segs = [s.strip() for s in label.split(",")]
            k = 1
            while k < len(segs) and re.sub(r"[^A-Za-z]", "", segs[k]).upper() in SUFFIXES:
                k += 1
            if k >= len(segs):
                continue
            name = ", ".join(segs[:k])
            labels = segs[k:]                      # "Mark Coester, Republican, Libertarian": one name, two lines
            party = next((p for p in labels if side(p) != "O"), labels[0])
            if NOT_CANDIDATES.match(party) and party.lower().startswith("write"):
                party = "Write-in"
            target.append([name, party, votes])
        elif NOT_CANDIDATES.match(label):
            continue
        elif target:
            # a party line under the candidate above (fusion): the votes are that candidate's
            if votes is not None:
                target[-1][2] = (target[-1][2] or 0) + votes
        else:
            target.append([label, label, votes])
    return out


_MEMO = {}


def clerk(year, say=say_default):
    """The Clerk's statistics for a year, read once and cached against the PDF's SHA-256 (and kept in memory)."""
    if ("clerk", year) in _MEMO:
        return _MEMO[("clerk", year)]
    _MEMO[("clerk", year)] = doc = _clerk(year, say)
    return doc


def _clerk(year, say=say_default):
    path = CLERK_PDF[year]
    if not os.path.exists(path):
        raise SystemExit(f"    the Clerk's {year} statistics are not on disk ({path})")
    sha = sha_file(path)
    cache = cache_path(f"clerk_{year}.json")
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha and doc.get("method") == DATA_METHOD:
            return doc
    from ballot import pdftext
    parsed = parse_clerk_lines(pdftext.lines(path))
    doc = {"method": DATA_METHOD, "sha256": sha, "year": year, "source": CLERK_URL.format(y=year),
           "title": f"Clerk of the U.S. House, Statistics of the Presidential and Congressional Election of {year}",
           "kind": "official", "states": {}}
    for code, rec in parsed.items():
        house_total = sum(v or 0 for h in rec["house"].values() for _n, _p, v in h["cands"])
        senate = [s for s in rec["senate"] if s["cands"]]
        for s in senate:
            tot = sum(v or 0 for _n, _p, v in s["cands"])
            if house_total and tot > 1.6 * house_total:
                # a footnote mark printed before the figures (Georgia 2022: the runoff's figures, marked "1"): the contest
                # is kept with the mark noted and left out of every comparison and backtest
                s["footnoted"] = True
        doc["states"][code] = {"president": rec["president"], "senate": senate,
                               "house": {str(k): v for k, v in rec["house"].items()}}
    save_json(cache, doc)
    say(f"    the Clerk's {year} statistics read: {len(doc['states'])} states")
    return doc


def president(year):
    """{code: (D, R, all)} for 2020 or 2024 from the Clerk's statistics."""
    out = {}
    for code, rec in clerk(year)["states"].items():
        d = sum(v or 0 for lab, _p, v in rec["president"] if lab.lower().startswith("democrat"))
        r = sum(v or 0 for lab, _p, v in rec["president"] if lab.lower().startswith("republican"))
        out[code] = (d, r, sum(v or 0 for _l, _p, v in rec["president"]))
    return out


# ============================================================================================== MEDSL's precinct files

def medsl_url(year, code):
    return MEDSL_REPO[year].format(c=code.lower())


def medsl_file(year, code, say=say_default, fetch=True):
    """The state's MEDSL file for a year, fetched once (through election/source.py) into election_cache/model/us/medsl/."""
    url = medsl_url(year, code)
    path = cache_path("medsl", str(year), os.path.basename(url))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    if not fetch:
        return None
    from election.model import source
    t0 = time.time()
    r = source().get(url, state=code, accept="*/*", timeout=240)
    if r.refused:
        raise SystemExit(f"    {url}: refused ({r.why}); not asked again")
    if not r.ok:
        say(f"    {url}: answered {r.status}")
        return None
    with open(path + ".part", "wb") as fh:
        fh.write(r.body)
    os.replace(path + ".part", path)
    say(f"      fetched {os.path.basename(path)}: {len(r.body) / 1e6:,.1f} MB in {time.time() - t0:,.0f} s")
    return path


def office_class(office, district):
    o = re.sub(r"\s+", " ", str(office or "").upper()).strip()
    d = str(district or "").strip().upper()
    if d not in ("", "STATEWIDE", "AT-LARGE", "AT LARGE", "000", "0"):
        return None
    for cls, pat in STATEWIDE_OFFICES:
        if pat.match(o):
            return cls
    return None


def house_district(d):
    d = str(d or "").strip().upper()
    if d in ("AT-LARGE", "AT LARGE", "0", "00", "000", "STATEWIDE", ""):
        return 0
    m = re.match(r"^0*(\d+)$", d)
    return int(m.group(1)) if m else None


def _rows(path):
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if n.lower().endswith((".csv", ".tab", ".txt")) and "readme" not in n.lower()
             and not n.startswith("__MACOSX")]
    for name in names:
        with z.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
            first = text.readline()
            delim = "\t" if first.count("\t") > first.count(",") else ","
            fields = next(csv.reader([first], delimiter=delim))
            rd = csv.DictReader(text, fieldnames=fields, delimiter=delim)
            for r in rd:
                yield {k: r.get(k) for k in MEDSL_KEEP}


def summarise_medsl(year, code, say=say_default):
    """One state's MEDSL file reduced to what the model reads, cached against the file's SHA-256:
      contests: every statewide contest of a class above (and US HOUSE by district), each candidate's votes
      by_cd:    each statewide contest's votes by congressional district (precincts placed by their US HOUSE rows)
      cd_cover: the share of each statewide contest's votes so placed
      by_county: each statewide contest's votes by county (five-digit FIPS)
    Votes by kind of ballot are added together; where a county reports a TOTAL row beside kinds, only TOTAL is read."""
    path = medsl_file(year, code, say)
    if not path:
        return None
    sha = sha_file(path)
    cache = cache_path("medsl", str(year), f"summary_{code.lower()}.json")
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha and doc.get("method") == DATA_METHOD:
            return doc
    t0 = time.time()
    # first pass: keep only the rows the model reads (statewide contests and US HOUSE), with modes
    keep = []
    for r in _rows(path):
        if (r.get("stage") or "GEN").upper() not in ("GEN", ""):
            continue
        office = (r.get("office") or "").upper().strip()
        cls = "ushouse" if office == "US HOUSE" else office_class(office, r.get("district"))
        if not cls:
            continue
        try:
            v = int(float(r.get("votes") or 0))
        except ValueError:
            v = 0
        special = str(r.get("special") or "").upper() == "TRUE"
        wi = str(r.get("writein") or "").upper() == "TRUE"
        cand = (r.get("candidate") or "").strip()
        if not cand or NOT_CANDIDATES.match(cand) or cand.upper() in ("UNDERVOTES", "OVERVOTES", "WRITEIN", "WRITE-IN"):
            continue
        dist = house_district(r.get("district")) if cls == "ushouse" else None
        if cls == "ushouse" and dist is None:
            continue
        if TOTAL_ROW.search(r.get("precinct") or ""):
            continue                                # a county's own total beside its precincts (Idaho 2022): counted twice
        cf = (r.get("county_fips") or "").strip()
        cf = cf.zfill(5) if cf.isdigit() else ""
        party = r.get("party_simplified") or ""
        if side(party) == "O" and side(r.get("party_detailed")) != "O":
            party = r.get("party_detailed")         # North Dakota's Democratic-NPL, Nebraska's presidential lines
        keep.append((cls, office if cls != "ushouse" else f"US HOUSE {dist}", special, cand, party,
                     wi, (r.get("mode") or "TOTAL").upper().strip(), cf, (r.get("jurisdiction_fips") or "").strip(),
                     (r.get("precinct") or "").strip(), v, dist))
    # which (contest, county) report TOTAL beside other kinds: read TOTAL only there
    modes = defaultdict(set)
    major = {}
    for rec in keep:
        s = side(rec[4])
        if s != "O" and not rec[5]:
            major.setdefault((rec[1], rec[2], rec[3]), s)   # a candidate on a big party's line and others (fusion): that party's
    for rec in keep:
        modes[(rec[1], rec[2], rec[7])].add(rec[6])
    def counted(rec):
        m = modes[(rec[1], rec[2], rec[7])]
        return rec[6] == "TOTAL" or "TOTAL" not in m
    contests = defaultdict(lambda: defaultdict(int))
    parties = {}
    cls_of = {}
    counties = defaultdict(set)
    pct_cd = defaultdict(set)
    for rec in keep:
        cls, office, special, cand, party, wi, mode, cf, jf, pct, v, dist = rec
        if not counted(rec):
            continue
        key = f"{office}|{'special' if special else 'regular'}"
        if wi:
            cand, party = "Write-in", "WRITE-IN"
        else:
            party = {"D": "DEMOCRAT", "R": "REPUBLICAN"}.get(major.get((office, special, cand)), party)
        contests[key][cand] += v
        parties[(key, cand)] = party
        cls_of[key] = cls
        if cf:
            counties[key].add(cf)
        if cls == "ushouse" and not special:
            pct_cd[(cf, jf, pct, mode)].add(dist)
    all_counties = set().union(*counties.values()) if counties else set()
    by_cd = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    by_county = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    placed = defaultdict(int)
    total = defaultdict(int)
    for rec in keep:
        cls, office, special, cand, party, wi, mode, cf, jf, pct, v, dist = rec
        if cls == "ushouse" or not counted(rec):
            continue
        key = f"{office}|{'special' if special else 'regular'}"
        s = "O" if wi else (major.get((office, special, cand)) or side(party))
        i = 0 if s == "D" else 1 if s == "R" else 2
        total[key] += v
        if cf:
            c = by_county[key][cf]
            c[i] += v
            c[2] += v if i < 2 else 0
        ds = pct_cd.get((cf, jf, pct, mode))
        if ds and len(ds) == 1:
            d = next(iter(ds))
            c = by_cd[key][str(d)]
            c[i] += v
            c[2] += v if i < 2 else 0
            placed[key] += v
    doc = {"method": DATA_METHOD, "sha256": sha, "year": year, "state": code, "source": medsl_url(year, code),
           "title": f"MIT Election Data and Science Lab, {year} precinct returns, {NAME_OF.get(code, code)}",
           "licence": "CC0 1.0", "kind": "secondary", "counties_in_file": len(all_counties), "contests": {}, "by_cd": {},
           "cd_cover": {}, "by_county": {},
           "note": "by_cd and by_county hold [Democratic, Republican, the two together]"}
    for key, cands in contests.items():
        doc["contests"][key] = {"class": cls_of[key], "counties": len(counties[key]),
                                "cands": sorted([[c, parties[(key, c)], v] for c, v in cands.items()], key=lambda x: -x[2])}
        if cls_of[key] != "ushouse":
            doc["by_county"][key] = {k: v for k, v in sorted(by_county[key].items())}
            if by_cd.get(key):
                doc["by_cd"][key] = {k: v for k, v in sorted(by_cd[key].items(), key=lambda kv: int(kv[0]))}
                doc["cd_cover"][key] = round(placed[key] / total[key], 4) if total[key] else 0.0
    save_json(cache, doc)
    say(f"      MEDSL {year} {code}: {len(keep):,} rows read, {len(doc['contests'])} contests, {time.time() - t0:,.0f} s")
    return doc


def medsl(year, code, say=say_default):
    """The summary if the file is on disk (or can be fetched), else None (kept in memory)."""
    if ("medsl", year, code) in _MEMO:
        return _MEMO[("medsl", year, code)]
    try:
        doc = summarise_medsl(year, code, say)
    except zipfile.BadZipFile:
        say(f"    MEDSL {year} {code}: the file is not a readable zip")
        doc = None
    _MEMO[("medsl", year, code)] = doc
    return doc


def medsl_reliable(year, code, say=say_default):
    """Whether a state's MEDSL file for a year adds up to the Clerk's official figures: every House district contested in
    both (the Democrat's share of the two-party vote within 0.5 points in nine districts of ten, within 1 point in all
    but a stray one, and the House votes in all within 3 percent), and President or Senate the same way where the year
    has one. Returns (ok, words). Files that do not are not read for governors or district figures."""
    key = ("reliable", year, code)
    if key in _MEMO:
        return _MEMO[key]
    doc = medsl(year, code, say)
    if not doc:
        _MEMO[key] = (False, "no file")
        return _MEMO[key]
    ck = clerk(year)["states"].get(code, {})
    diffs, mt, ct = [], 0, 0
    for dkey, h in ck.get("house", {}).items():
        if not str(dkey).isdigit():
            continue
        c = doc["contests"].get(f"US HOUSE {int(dkey)}|regular")
        if not c:
            continue
        d1, r1, t1, ok1 = two_party(h["cands"])
        d2, r2, t2, ok2 = two_party(c["cands"])
        if ok1 and ok2:
            diffs.append(abs(d1 / (d1 + r1) - d2 / (d2 + r2)))
            mt += d2 + r2
            ct += d1 + r1
    tops = []
    if year == 2024:
        k = next((k for k in doc["contests"] if k.startswith("US PRESIDENT|")), None)
        cd, cr, _a = president(2024).get(code, (0, 0, 0))
        if k and cd and cr:
            d2, r2, _t, _o = two_party(doc["contests"][k]["cands"])
            tops.append(("President", cd, cr, d2, r2))
    for s in ck.get("senate", []):
        if s.get("footnoted"):
            continue
        special = bool(s.get("term") and "unexpired" in s["term"].lower())
        k = f"US SENATE|{'special' if special else 'regular'}"
        d1, r1, _t, ok1 = two_party(s["cands"])
        if ok1 and k in doc["contests"]:
            d2, r2, _t2, _o2 = two_party(doc["contests"][k]["cands"])
            tops.append(("Senate", d1, r1, d2, r2))
    problems = []
    if not diffs:
        if not tops:
            problems.append("nothing to compare: no House district or statewide race of the two big parties")
    else:
        diffs.sort()
        if diffs[int(0.9 * (len(diffs) - 1))] > 0.005 or (len(diffs) > 1 and diffs[-2] > 0.01) or (len(diffs) == 1 and diffs[0] > 0.01):
            problems.append(f"House shares differ (largest {diffs[-1] * 100:.1f} points)")
        if ct and not 0.97 <= mt / ct <= 1.03:
            problems.append(f"House votes {mt / ct * 100:.0f}% of the Clerk's")
    for what, d1, r1, d2, r2 in tops:
        if not (d2 > 0 and r2 > 0):
            problems.append(f"{what}: no Democratic or Republican votes")
            continue
        if abs(d1 / (d1 + r1) - d2 / (d2 + r2)) > 0.005:
            problems.append(f"{what} share differs by {abs(d1 / (d1 + r1) - d2 / (d2 + r2)) * 100:.1f} points")
        if not 0.97 <= (d2 + r2) / (d1 + r1) <= 1.03:
            problems.append(f"{what} votes {(d2 + r2) / (d1 + r1) * 100:.0f}% of the Clerk's")
    _MEMO[key] = (not problems, "; ".join(problems) or f"agrees with the Clerk ({len(diffs)} districts, {len(tops)} statewide)")
    return _MEMO[key]


def statewide_contests(year, code, say=say_default):
    """[{key, class, office, special, cands: [[name, party, votes]]}] for one state's statewide contests of a year:
    U.S. Senate and President from the Clerk (official), governors and the other offices from MEDSL (secondary), each
    contest a single seat elected by the whole state."""
    out = []
    ck = clerk(year)["states"].get(code, {})
    for k, s in enumerate(ck.get("senate", [])):
        if s.get("footnoted"):
            continue
        special = bool(s.get("term") and "unexpired" in s["term"].lower())
        out.append({"key": f"ussen|{'special' if special else 'regular'}|{k}", "class": "ussen", "office": "U.S. Senate",
                    "special": special, "cands": [c for c in s["cands"] if c[2] is not None],
                    "source": "clerk", "kind": "official"})
    doc = medsl(year, code, say)
    if doc and medsl_reliable(year, code, say)[0]:
        n_all = max(doc.get("counties_in_file") or 1, 1)
        for key, c in doc["contests"].items():
            if c["class"] not in ("governor", "other"):
                continue
            if c["counties"] < 0.9 * n_all:
                continue                            # not on every county's ballot: a district office
            cands = [[n, p, v] for n, p, v in c["cands"] if n != "Write-in"]
            out.append({"key": key, "class": c["class"], "office": key.split("|")[0].title(), "special": key.endswith("special"),
                        "cands": cands, "source": "medsl", "kind": "secondary"})
    return out


# ============================================================================================== Census county figures

ACS_TABLES = {"b01003": ["001"], "b01002": ["001"], "b19013": ["001"], "b25003": ["001", "002"],
              "b15003": ["001", "022", "023", "024", "025"], "b03002": ["001", "003", "004", "012"]}


def census_counties(say=say_default):
    """{five-digit county FIPS: {pop, median_age, median_income, owners, bachelors_plus, white_nh, black, hispanic}} from
    the ACS 2020-2024 national tables on disk (county rows, summary level 050). Shares are of the table's own total.
    Cached against the files' SHA-256."""
    files = {t: os.path.join(ACS, f"acsdt5y2024-{t}.dat") for t in ACS_TABLES}
    missing = [p for p in files.values() if not os.path.exists(p)]
    if missing:
        say(f"    Census tables missing: {', '.join(os.path.basename(p) for p in missing)}")
        return {}
    stamp = {t: [os.path.getsize(p), int(os.path.getmtime(p))] for t, p in files.items()}
    cache = cache_path("census_counties.json")
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("stamp") == stamp and doc.get("method") == DATA_METHOD:
            return doc["counties"]
    raw = defaultdict(dict)
    for t, cells in ACS_TABLES.items():
        with open(files[t], encoding="utf-8", errors="replace") as fh:
            head = fh.readline().rstrip("\n").split("|")
            idx = {c: head.index(f"{t.upper()}_E{c}") for c in cells}
            for line in fh:
                if not line.startswith("0500000US"):
                    continue
                p = line.rstrip("\n").split("|")
                fips = p[0][9:14]
                for c, i in idx.items():
                    try:
                        v = float(p[i])
                    except ValueError:
                        v = None
                    raw[fips][f"{t}_{c}"] = None if v is None or v <= -100000000 else v
    out = {}
    for fips, r in raw.items():
        def share(a, b):
            return round(a / b, 4) if a is not None and b else None
        bach = sum(r.get(f"b15003_{c}") or 0 for c in ("022", "023", "024", "025"))
        out[fips] = {"pop": r.get("b01003_001"), "median_age": r.get("b01002_001"), "median_income": r.get("b19013_001"),
                     "owners": share(r.get("b25003_002"), r.get("b25003_001")),
                     "bachelors_plus": share(bach, r.get("b15003_001")),
                     "white_nh": share(r.get("b03002_003"), r.get("b03002_001")),
                     "black": share(r.get("b03002_004"), r.get("b03002_001")),
                     "hispanic": share(r.get("b03002_012"), r.get("b03002_001"))}
    save_json(cache, {"method": DATA_METHOD, "stamp": stamp, "source": "ACS 2020-2024 5-year table-based summary files, county rows",
                      "kind": "census", "counties": out})
    say(f"    Census county figures: {len(out):,} counties")
    return out


def county_baseline(code, say=say_default):
    """What the election-night model can start from for a state reported by county: each county's Democratic and
    Republican votes for President in 2024 and for the 2022 top statewide contest (MEDSL, secondary), and its Census
    figures. {"counties": {fips: {"pres24": [D, R], "top22": [D, R], "census": {...}}}, "sources": [...]}."""
    out = defaultdict(dict)
    sources = []
    d24 = medsl(2024, code, say)
    if d24:
        k = next((k for k in d24["by_county"] if k.startswith("US PRESIDENT|regular")), None)
        if k:
            for f, (d, r, _t) in d24["by_county"][k].items():
                out[f]["pres24"] = [d, r]
            sources.append({"what": "President 2024 by county", "source": d24["source"], "sha256": d24["sha256"], "kind": "secondary"})
    d22 = medsl(2022, code, say)
    if d22:
        cands = [k for k in d22["by_county"] if k.split("|")[1] == "regular" and d22["contests"][k]["class"] in ("governor", "ussen")]
        if cands:
            k = sorted(cands, key=lambda k: (d22["contests"][k]["class"] != "governor", k))[0]
            for f, (d, r, _t) in d22["by_county"][k].items():
                out[f]["top22"] = [d, r]
            sources.append({"what": f"{k.split('|')[0].title()} 2022 by county", "source": d22["source"], "sha256": d22["sha256"],
                            "kind": "secondary"})
    cen = census_counties(say)
    for f in list(out):
        if f in cen:
            out[f]["census"] = cen[f]
    return {"state": code, "counties": dict(out), "sources": sources}


# ============================================================================================== who sat in Congress

def members_on(day, chamber):
    """{state: [(name, district)]} of the members of a chamber ("House" or "Senate") serving on a past day, from the
    roster's terms (current members' every term; former members' last term, which covers the day for anyone who left
    after it)."""
    if ("members", day, chamber) in _MEMO:
        return _MEMO[("members", day, chamber)]
    _MEMO[("members", day, chamber)] = out = _members_on(day, chamber)
    return out


def _members_on(day, chamber):
    con = sqlite3.connect(f"file:{RECORD_DB}?mode=ro", uri=True)
    typ = "rep" if chamber == "House" else "sen"
    out = defaultdict(list)
    seen = set()
    for bio, state, dist, first, last, full in con.execute(
            "SELECT t.bioguide_id, t.state, t.district, l.first_name, l.last_name, l.official_full FROM member_terms t "
            "JOIN legislators l USING (bioguide_id) WHERE t.type = ? AND t.start <= ? AND t.end >= ?", (typ, day, day)):
        out[state].append((full or f"{first} {last}", dist, f"{first} {last}"))
        seen.add(bio)
    for bio, state, dist, first, last, full in con.execute(
            "SELECT bioguide_id, state, district, first_name, last_name, official_full FROM legislators WHERE chamber = ? AND "
            "term_start <= ? AND term_end >= ?", (chamber, day, day)):
        if bio not in seen:
            out[state].append((full or f"{first} {last}", dist, f"{first} {last}"))
    con.close()
    return dict(out)


def sitting(name, state, members):
    """Whether a candidate's name is a member's of that state in `members` (members_on)."""
    return any(same_person(name, full) or same_person(name, short) for full, _d, short in members.get(state, []))


# ============================================================================================== the 2026 races

def lines_changed_2026():
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    out = {st: (bool(ch), note) for st, ch, note in con.execute("SELECT state, lines_changed, note FROM state_notes")}
    con.close()
    return out


SEATS_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5}


def races_2026(code):
    """Every 2026 race for Congress and every statewide office in a state, with its general-election candidates as filed
    (write-ins left out: their names are not printed). Read only."""
    code = code.upper()
    out = []
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    cands = defaultdict(list)
    lists = set()
    for rid, election, name, party, pcode, inc, wi, bio in con.execute(
            "SELECT race_id, election, name, party, party_code, incumbent, write_in, bioguide_id FROM candidates "
            "WHERE race_id LIKE ? AND election IN ('general', 'open-primary') ORDER BY race_id, name", (f"2026-{code}-%",)):
        lists.add((rid, election))
        if not wi:
            cands[(rid, election)].append({"name": name, "party": party, "p": side(pcode or party), "bio": bio})
    for rid, office, dist, special, holder, holder_party, note in con.execute(
            "SELECT race_id, office, district, special, holder, holder_party, note FROM races WHERE state = ? ORDER BY race_id", (code,)):
        election = "open-primary" if (rid, "open-primary") in lists else "general"
        cs = cands.get((rid, election), [])
        for c in cs:
            c["inc"] = 1 if holder and c.pop("bio") == holder else 0
        out.append({"race": rid, "level": "federal", "office_kind": "us_senate" if office == "U.S. Senate" else "us_house",
                    "office": office, "district": dist, "special": bool(special), "partisan": True, "seats": 1,
                    "election": election, "listed": (rid, election) in lists, "holder_party": holder_party, "cands": cs,
                    "statewide": office == "U.S. Senate", "jurisdiction_id": None, "seat": None, "note": note})
    con.close()
    con = sqlite3.connect(f"file:{LOCAL_DB}?mode=ro", uri=True)
    cands = defaultdict(list)
    lists = set()
    for rid, name, party, pcode, inc, wi in con.execute(
            "SELECT c.race_id, c.name, c.party, c.party_code, c.incumbent, c.write_in FROM sl_candidates c JOIN sl_races r USING (race_id) "
            "WHERE r.state = ? AND r.level = 'statewide' AND c.election = 'general' ORDER BY c.race_id, c.name", (code,)):
        lists.add(rid)
        if not wi:
            cands[rid].append({"name": name, "party": party, "p": side(pcode or party), "inc": 1 if inc else 0})
    for rid, kind, office, jur, jid, dist, seat, special, partisan, holder, holder_party, note in con.execute(
            "SELECT race_id, office_kind, office, jurisdiction, jurisdiction_id, district, seat, special, partisan, holder_name, "
            "holder_party, note FROM sl_races WHERE state = ? AND level = 'statewide' ORDER BY race_id", (code,)):
        m = re.search(r"\b(two|three|four|five|\d+)(?: at-large)? seats\b|up to (\d+)", note or "", re.I)
        seats = 1
        if m:
            w = (m.group(1) or m.group(2) or "1").lower()
            seats = SEATS_WORDS.get(w) or int(w)
        cs = cands.get(rid, [])
        for c in cs:
            if not c["inc"] and holder and same_person(c["name"], holder):
                c["inc"] = 1
        out.append({"race": rid, "level": "statewide", "office_kind": kind, "office": office, "district": dist, "seat": seat,
                    "jurisdiction_id": jid, "special": bool(special), "partisan": bool(partisan), "seats": seats,
                    "election": "general", "listed": rid in lists, "holder_party": holder_party, "cands": cs,
                    "statewide": dist in (None, ""), "note": note})
    con.close()
    return out


# ============================================================================================== build and check

def build(codes=None, say=say_default):
    """Fetch what is missing and summarise every file (each once)."""
    for y in (2020, 2022, 2024):
        clerk(y, say)
    for y in (2022, 2024):
        for code in codes or CODES:
            if y == 2022 and code == "NJ":
                pass
            medsl(y, code, say)
    census_counties(say)


def reliability(codes=None, say=say_default):
    """medsl_reliable for every state and year, printed and kept in election_cache/model/us/medsl_reliable.json."""
    out = {}
    for y in (2022, 2024):
        for code in codes or CODES:
            ok, why = medsl_reliable(y, code, say)
            out[f"{y}-{code}"] = [ok, why]
            if not ok:
                say(f"    MEDSL {y} {code}: not used ({why})")
    n = sum(1 for v in out.values() if v[0])
    say(f"    MEDSL files that add up to the Clerk's figures: {n} of {len(out)}")
    save_json(cache_path("medsl_reliable.json"), out)
    return out


def check(codes=None, say=say_default):
    """MEDSL's sums for President (2024) and U.S. Senate (2022, 2024) against the Clerk's official totals, state by state.
    Returns {year: {code: {contest: [MEDSL D, R; Clerk D, R; largest difference as a share]}}} and prints the misses."""
    res = {}
    for y in (2022, 2024):
        ck = clerk(y)["states"]
        res[y] = {}
        for code in codes or CODES:
            doc = medsl(y, code, say)
            if not doc:
                continue
            row = {}
            if y == 2024:
                k = next((k for k in doc["contests"] if k.startswith("US PRESIDENT|")), None)
                if k:
                    d, r, _t, _c = two_party(doc["contests"][k]["cands"])
                    cd, cr, _a = president(2024).get(code, (0, 0, 0))
                    row["president"] = [d, r, cd, cr, round(max(abs(d - cd) / max(cd, 1), abs(r - cr) / max(cr, 1)), 4)]
            sen_m = [k for k in doc["contests"] if k.startswith("US SENATE|")]
            for s in ck.get(code, {}).get("senate", []):
                cd, cr, _t, _c = two_party(s["cands"])
                best = None
                for k in sen_m:
                    d, r, _t2, _c2 = two_party(doc["contests"][k]["cands"])
                    miss = max(abs(d - cd) / max(cd, 1), abs(r - cr) / max(cr, 1))
                    if best is None or miss < best[-1]:
                        best = [d, r, cd, cr, round(miss, 4)]
                if best:
                    row[f"senate {s.get('term') or 'regular'}"] = best
            res[y][code] = row
            for k, v in row.items():
                if v[-1] > 0.01:
                    say(f"    {y} {code} {k}: MEDSL and the Clerk differ by {v[-1] * 100:.1f}% ({v[0]:,}/{v[1]:,} against {v[2]:,}/{v[3]:,})")
    save_json(cache_path("check_medsl_clerk.json"), res)
    return res


def selftest(say=print):
    ok = True

    def chk(what, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    lines = [(1, 0, t) for t in [
        "GEORGIA", "FOR PRESIDENTIAL ELECTORS", "Republican ........ 2,663,117", "Democratic ......... 2,548,017",
        "FOR UNITED STATES REPRESENTATIVE", "1. Earl Carter, Republican ....... 220,576", "Patti Hewitt, Democrat ....... 135,281",
        "2. Sanford D. Bishop, Jr., Democrat ...... 176,028", "Write-in ...... 12",
        "Recapitulation of Votes Cast in Georgia", "1st district ....... 220,576 135,281 ..... 355,857",
        "NEW YORK", "FOR UNITED STATES SENATOR", "Kirsten E. Gillibrand, Democrat ....... 4,318,903", "Working Families ....... 392,395",
        "Blank ...... 365,214", "FOR UNITED STATES REPRESENTATIVE", "3. Frank D. Lucas, Republican ..... (1)",
        "WYOMING", "FOR UNITED STATES REPRESENTATIVE", "AT LARGE", "Harriet Hageman, Republican ...... 132,206",
        "AMERICAN SAMOA", "FOR DELEGATE", "Someone, Republican ..... 6,637"]]
    p = parse_clerk_lines(lines)
    chk("president lines", p["GA"]["president"], [["Republican", "Republican", 2663117], ["Democratic", "Democratic", 2548017]])
    chk("a district's lines", p["GA"]["house"][1]["cands"], [["Earl Carter", "Republican", 220576], ["Patti Hewitt", "Democrat", 135281]])
    chk("a name with Jr.", p["GA"]["house"][2]["cands"], [["Sanford D. Bishop, Jr.", "Democrat", 176028]])
    chk("the recapitulation is not read", sorted(p["GA"]["house"]), [1, 2])
    chk("a fusion line is added to the candidate above", p["NY"]["senate"][0]["cands"], [["Kirsten E. Gillibrand", "Democrat", 4711298]])
    chk("(1) is a seat no votes were counted for", (p["NY"]["house"][3]["unopposed"], p["NY"]["house"][3]["cands"][0][2]), (True, None))
    chk("at large is district 0", p["WY"]["house"][0]["cands"], [["Harriet Hageman", "Republican", 132206]])
    chk("a territory is not a state", "AS" in p, False)
    chk("two-party arithmetic", two_party([["A", "Democrat", 60], ["B", "Republican", 40], ["C", "Green", 5]]), (60, 40, 105, True))
    chk("same person: initials and nicknames", same_person("Earl L. \"Buddy\" Carter", "Earl Carter"), True)
    chk("same person: last name first", same_person("CARTER, EARL", "Earl Carter"), True)
    chk("not the same person", same_person("Jane Doe", "John Doe"), False)
    chk("MEDSL's office classes", [office_class("GOVERNOR", ""), office_class("ATTORNEY GENERAL", "STATEWIDE"),
                                   office_class("STATE SENATE", "12"), office_class("US SENATE", "")], ["governor", "other", None, "ussen"])
    chk("house districts", [house_district("AT-LARGE"), house_district("007"), house_district("x")], [0, 7, None])
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--states", help="comma-separated codes (default: every state)")
    a = ap.parse_args(argv)
    codes = [c.strip().upper() for c in a.states.split(",")] if a.states else None
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.build:
        build(codes)
    if a.check:
        check(codes)
        reliability(codes)
    if not (a.build or a.check):
        ap.print_help()


if __name__ == "__main__":
    main()
