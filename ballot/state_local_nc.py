"""
ballot/state_local_nc.py - North Carolina's state and local races on the November 3, 2026 ballot.

State offices: all 50 seats of the State Senate and all 120 seats of the State House (both chambers serve two-year terms,
so every seat is up in every even year), the one Supreme Court seat (Associate Justice, Seat 1) and the three Court of
Appeals seats (Seats 1, 2 and 3) on the ballot, with each party's March 3 primary field and its official votes. North
Carolina elects its Governor and the rest of its Council of State in presidential years (2024, 2028), so no statewide
executive office is on the 2026 ballot; the Board's list carries none.

County and local offices, from the same list (the "local part" below): every contest it carries for November 3 that is
neither federal nor one of the state contests above. County offices (boards of commissioners, sheriff, clerk of superior
court, register of deeds, coroner, tax collector), boards of education, soil and water conservation district
supervisors, the cities, towns and villages that vote in even years, sanitary districts, and the district offices the
state part used to count without reading: district attorneys and superior and district court judges (filed under level
"court", with the counties their districts reach). What a contest is comes from its name, by the rules in classify();
a name no rule fits is never guessed: the contest is left out and written to sl_gaps.
  - The county is the county board of elections whose rows carry the contest (county_name), matched to the Census
    Bureau's 2024 county file. A contest carried by several county boards (a city on a county line, a court district)
    must be listed the same by each: the same names, parties and order.
  - A city, town or village is the one incorporated place of that name in the Census Bureau's 2020 place codes for North
    Carolina (st37_nc_place2020.txt), which gives its five-digit place code and its name with the kind word ("Raleigh
    city"); the longest place name the contest name begins with is taken, so "TOWN OF FOREST CITY COMMISSIONER" is Forest
    City's commissioner and "CITY OF SALUDA CITY COMMISSIONER" is Saluda's city commissioner. Towns and villages are
    incorporated municipalities here (North Carolina's townships elect nobody), so all are level "city".
  - A board of education is named as the list names it ("Wake County Board of Education", "Asheville City Schools Board of
    Education"); the list carries no school district code, so its key is the county's three-digit code and the name.
  - Nonpartisan or partisan comes from the list's own is_partisan column, and an unexpired term from is_unexpired.
  - Local primaries, ballot questions and write-in candidates are not loaded. The list has a row only for candidates,
    so an office nobody filed for is not in it, and it has no status column, so nobody withdrawn can be counted.
  - Local candidates carry nothing but the name as filed, the office, the place, the party or "Nonpartisan office": no
    incumbent mark, no link, no ballot order (the list states none).
Tables written besides the four the state part writes: sl_gaps (what could not be loaded, and why) and sl_notes
(local_calendar, local_coverage), created with ballot.check_local.EXTRA_SCHEMA; only North Carolina's rows are rewritten.

Sources, every one the State Board of Elections' own (the same files the federal loader, ballot/lists/nc.py, reads):
  - "Candidate Listing 2026" (dl.ncsbe.gov/Elections/2026/Candidate Filing/Candidate_Listing_2026.csv): every candidate for
    every office in the March 3 primary and the November 3 general election, one row per county the contest reaches. The
    rows dated 11/03/2026 for NC STATE SENATE DISTRICT nn, NC HOUSE OF REPRESENTATIVES DISTRICT nnn, NC SUPREME COURT
    ASSOCIATE JUSTICE SEAT nn and NC COURT OF APPEALS JUDGE SEAT nn are the November ballot. Every county's list of a
    contest must agree, name for name and party for party. The list gives no ballot order (its order follows no party
    rule: Republican first in some contests, Democratic first in others, while G.S. 163-165.6 sets the printed order by
    party), so ballot_order is left empty; it has no status column, and a candidate who withdraws is taken out of the file.
    The counties a district reaches are the counties whose rows carry it (Census codes from the Bureau's 2024 county file).
    District attorney, superior court and district court contests are on the same list; they are district offices, not
    statewide ones, and are read by the local part. The same fetch gives the local part its rows: the November rows that
    are neither federal nor the state contests, cut down to county_name, contest_name, name_on_ballot, party_candidate,
    is_partisan, is_unexpired and vote_for, in ballot_cache/nc/local/sl_nc_candidate_listing_2026_local.json. The two
    cut-down copies must carry the same SHA-256; when they do not, the list is read once more and both are cut again.
  - The Board's candidate-lists page (ncsbe.gov/results-data/candidate-lists), read only for whether it still says the
    November lists are not final; the finding and the page's SHA-256 are kept, never the page.
  - The Census Bureau's 2020 place codes for North Carolina (no personal details; kept whole in ballot_cache/nc/local/).
  - The precinct results of the March 3 primary (dl.ncsbe.gov/ENRS/2026_03_03/results_pct_20260303.zip, the federal
    loader's cached copy): summed over every precinct, administrative ones included; each row's four voting methods must
    add to its total. A field is a party's primary with two candidates or more (North Carolina prints a party primary only
    when it is contested; the results carry no write-in line for these contests). The leader advanced.
  - The Board's results site (er.ncsbe.gov/enr/): elections.txt (no election between March 3 and November 3, 2026, so no
    second primary), 20260303/data/county.txt (every county and the state titled OFFICIAL, every precinct reporting) and
    20260303/data/results_0.txt (each candidate's statewide total, which must equal the precinct sum exactly). Kept fields
    only, for the state contests read here, in sl_nc_2026_primary_enr_state.json.
  - The Board's party key in its voter statistics layout (layout_voter_stats.txt): parties written out by it.
  - Holders from the Open States roster in state_nc.sqlite (legislators, is_current = 1). The roster carries no judges.

Privacy. The candidate listing also carries each candidate's street address, city, state, ZIP code, three telephone numbers,
e-mail and filing date. Columns are taken by name from the header and only these are ever turned into kept text:
election_dt, county_name (the county board whose ballot carries the contest), contest_name, name_on_ballot, party_contest,
party_candidate, has_primary, is_unexpired and vote_for, and is_partisan for the local rows. The CSV is never saved; the
kept cells of the state rows go to sl_nc_candidate_listing_2026_state.json and those of the local rows to
local/sl_nc_candidate_listing_2026_local.json, each with the whole file's SHA-256. A name cell that holds a digit, "@", a
web address or a post-office box stops the loader, which names the contest and the row number, never the text. Nothing
but name, office, district, party and incumbency is stored; no photos, ages, websites, biographies or money. In the
local rows a name cell that is not a name (a digit, "@", a web address, or anything ballot.check_local reads as contact
details) does not stop the loader: the cell is dropped where it is read, the candidate is left out, the race says so,
and sl_gaps names the race and the row the contest begins at, never the text.

    python ballot/state_local_nc.py --db <path to a test database> [--cache <folder for this loader's own kept files>]
                                    [--local-cache <folder for the local part's kept files, default <cache>/local>]
"""

import collections
import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists import nc as fed  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "NC", "37"
GENERAL, PRIMARY = "2026-11-03", "2026-03-03"
GENERAL_DT, PRIMARY_DT = fed.GENERAL_DT, fed.PRIMARY_DT
FED = os.path.join(HERE, "ballot_cache", "nc")
ROSTER = os.path.join(HERE, "state_nc.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
LIST_FILE = "sl_nc_candidate_listing_2026_state.json"
ENR_FILE = "sl_nc_2026_primary_enr_state.json"
ZIP_NAME = "results_pct_20260303.zip"
SRC_LIST, SRC_PCT, SRC_ENR = "nc-sbe-2026-candidate-listing", "nc-sbe-2026-primary-results", "nc-sbe-2026-primary-enr"
SRC_KEY, SRC_COUNTY, SRC_ROSTER = "nc-sbe-party-key", "nc-census-2024-county-codes", "nc-openstates-roster"
SENATE_SEATS, HOUSE_SEATS = 50, 120
COURT_SEATS = {"SC": [1], "COA": [1, 2, 3]}
RUNOFF_SHARE = fed.RUNOFF_SHARE

# the local part's own files and sources
LOCAL_LIST_FILE = "sl_nc_candidate_listing_2026_local.json"
PAGE_FILE = "sl_nc_candidate_lists_page.json"
PLACE_FILE = "census_st37_nc_place2020.txt"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st37_nc_place2020.txt"
LISTS_PAGE = "https://www.ncsbe.gov/results-data/candidate-lists"
STATUTES = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_163/GS_163-1.html"
SRC_LOCAL, SRC_PLACE, SRC_PAGE = "nc-sbe-2026-candidate-listing-local", "nc-census-2020-place-codes", "nc-sbe-candidate-lists-page"
LOCAL_KEEP = ("election_dt", "county_name", "contest_name", "name_on_ballot", "party_candidate", "is_partisan", "is_unexpired", "vote_for")
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT,
  special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT,
  election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL,
  party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0,
  votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT,
  published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

SENATE_NOTE = "North Carolina's senators serve two-year terms, so all 50 Senate seats are on the ballot in 2026."
HOUSE_NOTE = "North Carolina's representatives serve two-year terms, so all 120 House seats are on the ballot in 2026."
COURT_NOTE = ("A partisan office: North Carolina prints the candidates' parties for its appellate courts. The term is eight years "
              "(N.C. Constitution, Article IV, Section 16); the seat number is the one the State Board of Elections gives it. The "
              "member roster used here (Open States) does not carry judges, so today's holder is not shown.")
ORDER_NOTE = ("The Board's candidate list gives no ballot order, so none is shown; the printed ballot sets the parties' order by "
              "law (G.S. 163-165.6).")
CAPS = "North Carolina's list prints this name in capitals; it is shown here in ordinary capitals."


class ListError(SystemExit):
    pass


# ---------------------------------------------------------------- the race a contest names

def race_of(contest):
    """(race id, special) for a state contest this loader reads, or (None, False). The party a results contest carries
    after the name ('... DISTRICT 007 (REP)', '... DISTRICT 007 - REP (VOTE FOR 1)') is set aside. A Senate, House or
    appellate-court contest written some other way stops the loader rather than being dropped."""
    c = re.sub(r"\s*(\((?:[A-Z]{3})\)|- [A-Z]{3} \(VOTE FOR \d+\))\s*$", "", (contest or "").strip().upper())
    special = bool(re.search(r"\(UNEXPIRED\)\s*$", c))
    c = re.sub(r"\s*\(UNEXPIRED\)\s*$", "", c)
    tail = "-S" if special else ""
    m = re.fullmatch(r"NC STATE SENATE DISTRICT (\d{1,2})", c)
    if m:
        return f"2026-{STATE}-SS{int(m.group(1))}{tail}", special
    m = re.fullmatch(r"NC HOUSE OF REPRESENTATIVES DISTRICT (\d{1,3})", c)
    if m:
        return f"2026-{STATE}-SH{int(m.group(1))}{tail}", special
    m = re.fullmatch(r"NC SUPREME COURT ASSOCIATE JUSTICE SEAT (\d{1,2})", c)
    if m:
        return f"2026-{STATE}-SC{int(m.group(1))}{tail}", special
    if c == "NC SUPREME COURT CHIEF JUSTICE":
        return f"2026-{STATE}-SC-CJ{tail}", special
    m = re.fullmatch(r"NC COURT OF APPEALS JUDGE SEAT (\d{1,2})", c)
    if m:
        return f"2026-{STATE}-COA{int(m.group(1))}{tail}", special
    if re.match(r"NC (STATE SENATE|HOUSE OF REP|SUPREME COURT|COURT OF APPEALS)", c):
        raise ListError(f"North Carolina: a state contest the loader does not read ({c!r})")
    return None, False


def district_office(contest):
    """The district-level state offices on the same list (counted, not read, in this phase)."""
    c = (contest or "").upper()
    if c.startswith("DISTRICT ATTORNEY"):
        return "district attorney"
    if c.startswith("NC SUPERIOR COURT JUDGE"):
        return "superior court judge"
    if c.startswith("NC DISTRICT COURT JUDGE"):
        return "district court judge"
    return None


def kind_of(rid):
    key = rid.split(f"-{STATE}-", 1)[1]
    return re.match(r"SS|SH|SC|COA", key).group(0)


# ---------------------------------------------------------------- names: only a name ever leaves the reader

MARK = re.compile(r"\s+-\s+DECEASED\s*$", re.I)
NOT_A_NAME = re.compile(r"\d|@|www|\.com|\.org|\.net|\bbox\b|\bp\.?\s?o\.?\s", re.I)


def checked_name(raw, where):
    name = re.sub(r"\s+", " ", str(raw or "").replace(" ", " ")).strip()
    if not name or NOT_A_NAME.search(name):
        raise ListError(f"North Carolina: {where} holds something other than a name (the text is not shown); the file may have changed")
    return name


def shown(raw):
    return fed.shown(raw)


# ---------------------------------------------------------------- the files

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


_CSV = {}


def csv_bytes():
    """The Board's candidate listing as fetched: asked for once in a run (a failure is remembered too) and held in memory
    only, so the state rows and the local rows are cut from the same bytes. Never written anywhere."""
    if "error" in _CSV:
        raise _CSV["error"]
    if "data" not in _CSV:
        try:
            _CSV["data"] = net.get(fed.url(fed.LISTING), accept="text/csv,*/*")
        except OSError as e:
            _CSV["error"] = e
            raise
        time.sleep(1.0)
    return _CSV["data"]


def listing(folder, say, refresh=False):
    """The candidate listing's state rows (Senate, House, Supreme Court, Court of Appeals), the kept columns only, as
    JSON; fetched afresh after two days. The CSV itself is never written anywhere."""
    path = os.path.join(folder, LIST_FILE)
    if fresh(path, 2) and not refresh:
        return path
    try:
        data = csv_bytes()
    except OSError as e:
        if os.path.exists(path):
            say(f"      could not refresh the candidate listing ({e}); using the copy read earlier")
            return path
        raise
    text = data.decode("utf-8-sig")
    if not text.lstrip('"').startswith("election_dt"):
        raise ListError("North Carolina: the candidate listing did not come back as the Board's CSV")
    reader = csv.reader(io.StringIO(text))
    head = [h.strip() for h in next(reader)]
    missing = [k for k in fed.KEEP if k not in head]
    if missing:
        raise ListError(f"North Carolina: the candidate listing's columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in fed.KEEP}
    total, rows, left = 0, [], collections.Counter()
    for n, r in enumerate(reader, start=2):
        total += 1
        if len(r) <= max(idx.values()):
            raise ListError(f"North Carolina: row {n} of the candidate listing is short")
        contest = r[idx["contest_name"]].strip()
        rid, _special = race_of(contest)
        if rid:
            row = {k: r[i].strip() for k, i in idx.items()}
            row["name_on_ballot"] = checked_name(row["name_on_ballot"], f"row {n} ({contest})")
            rows.append(row)
        elif district_office(contest) and r[idx["election_dt"]].strip() == GENERAL_DT:
            left[district_office(contest), contest] += 1
    del text
    contests = collections.Counter(k for k, _c in left)
    meta = {"url": fed.url(fed.LISTING), "sha256": hashlib.sha256(data).hexdigest(), "published": fed.published(fed.LISTING),
            "read": dt.date.today().isoformat(), "rows_in_file": total, "columns_kept": list(fed.KEEP),
            "district_offices_not_read": dict(contests), "rows": rows}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return path


def enr_control(folder, say, refresh=False):
    """The results site's own word on the primary and its statewide totals for the state contests, kept fields only."""
    path = os.path.join(folder, ENR_FILE)
    if fresh(path, 30) and not refresh:
        return path, json.load(open(path, encoding="utf-8"))
    get = lambda name: json.loads(net.get(fed.ENR + name, accept="application/json").decode("utf-8-sig"))
    elections = [e["edt"] for e in get("elections.txt")]
    counties = [{k: c.get(k) for k in ("cid", "cnm", "tle", "prt", "ptl", "imp")} for c in get("20260303/data/county.txt")]
    results = [{k: r.get(k) for k in ("cnm", "gid", "bnm", "pty", "vct", "prt", "ptl")}
               for r in get("20260303/data/results_0.txt") if race_of(r.get("cnm"))[0]]
    keep = {"read": dt.date.today().isoformat(), "elections": elections, "counties": counties, "results": results}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, keep


def precinct_totals(path):
    """{(race, party): {choice: votes}}, {(race, party): {county: votes}} and the number of rows read, for the state
    contests; every row's voting methods must add to its total."""
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if n.lower().endswith(".txt")]
    if len(names) != 1:
        raise ListError(f"North Carolina: the results zip holds {len(names)} text files, not one")
    reader = csv.reader(io.StringIO(z.read(names[0]).decode("utf-8-sig")), delimiter="\t")
    head = [h.strip() for h in next(reader)]
    missing = [k for k in fed.RESULT_KEEP if k not in head]
    if missing:
        raise ListError(f"North Carolina: the precinct results' columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in fed.RESULT_KEEP}
    votes = collections.defaultdict(lambda: collections.defaultdict(int))
    by_county = collections.defaultdict(lambda: collections.defaultdict(int))
    bad, dates, nrows = [], set(), 0
    for r in reader:
        if not r or len(r) <= max(idx.values()):
            continue
        contest = r[idx["Contest Name"]]
        rid, _special = race_of(contest)
        if not rid:
            continue
        m = re.search(r"\(([A-Z]{3})\)\s*$", contest)
        if not m:
            raise ListError(f"North Carolina: a state primary contest names no party ({contest!r})")
        nrows += 1
        key = (rid, m.group(1))
        dates.add(r[idx["Election Date"]])
        n = int(r[idx["Total Votes"]])
        if sum(int(r[idx[k]] or 0) for k in fed.METHODS) != n:
            bad.append((r[idx["County"]], contest))
        choice = checked_name(r[idx["Choice"]], f"a choice in {contest}")
        votes[key][choice] += n
        by_county[key][r[idx["County"]].strip().upper()] += n
    if dates != {PRIMARY_DT}:
        raise ListError(f"North Carolina: the precinct results are for {sorted(dates)}, not {PRIMARY_DT}")
    if bad:
        raise ListError(f"North Carolina: {len(bad)} precinct rows whose voting methods do not add to their total, e.g. {bad[0]}")
    return votes, by_county, nrows


# ---------------------------------------------------------------- roster, counties, matching

def roster(path=ROSTER):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = collections.defaultdict(list)
    for mid, full, first, last, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1"):
        members[(chamber, str(int(district)))].append(
            dict(id=mid, name=full or f"{first} {last}", first=first or "", last=last or "", other=other or "", party=party))
    con.close()
    return members


def census_counties(path=COUNTY_ZIP):
    """{folded county name: (GEOID, name)} for North Carolina's counties."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {fold(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def member_forms(m):
    forms = [(fold(m["first"]).split(), fold(m["last"]))] if m.get("last") else []
    forms.append(name_parts(m["name"]))
    for o in (m.get("other") or "").split(";"):
        o = o.strip()
        if o and not re.search(r"\b[A-Z]\.$|^[A-Z]\.|^\w+, [A-Z]\.$", o):
            forms.append(name_parts(o))
    return forms


def ballot_parts(name):
    """(given names, family name), with a nickname in parentheses or quotes counted among the given names."""
    nick = re.findall(r"[\(\"“]([^\)\"”]+)[\)\"”]", name)
    given, family = name_parts(re.sub(r"[\(\"“][^\)\"”]+[\)\"”]", " ", name))
    return given + [w for n in nick for w in fold(n).split()], family


def incumbent_hits(names, member):
    forms = member_forms(member) if member else []
    return {n for n in names if any(fits(ballot_parts(n), f) for f in forms)}


def find_incumbent(names, member):
    """The one name that fits the sitting member, or None."""
    hits = incumbent_hits(names, member)
    return next(iter(hits)) if len(hits) == 1 else None


def same_person(a, b):
    return fits(ballot_parts(a), ballot_parts(b)) or fold(a) == fold(b)


# ================================================================ the county and local part

def local_listing(folder, say, refresh=False):
    """The candidate listing's November rows for every contest that is neither federal nor one of the state contests
    read above: the kept columns only, as JSON, with the whole file's SHA-256 and the counts that reconcile it. A name
    cell that is not a name is dropped here (the row keeps its place, with no name). Read afresh after two days, or cut
    again from the bytes this run already holds, so both cut-down copies come from one fetch."""
    path = os.path.join(folder, LOCAL_LIST_FILE)
    if fresh(path, 2) and not refresh and "data" not in _CSV:
        return path
    try:
        data = csv_bytes()
    except OSError as e:
        if os.path.exists(path):
            say(f"      could not refresh the candidate listing ({e}); using the local rows read earlier")
            return path
        raise
    text = data.decode("utf-8-sig")
    if not text.lstrip('"').startswith("election_dt"):
        raise ListError("North Carolina: the candidate listing did not come back as the Board's CSV")
    reader = csv.reader(io.StringIO(text))
    head = [h.strip() for h in next(reader)]
    missing = [k for k in LOCAL_KEEP if k not in head]
    if missing:
        raise ListError(f"North Carolina: the candidate listing's columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in LOCAL_KEEP}
    count, rows = collections.Counter(), []
    for n, r in enumerate(reader, start=2):
        if len(r) != len(head):
            raise ListError(f"North Carolina: row {n} of the candidate listing has {len(r)} cells, not the {len(head)} its header names")
        count["file"] += 1
        if r[idx["election_dt"]].strip() != GENERAL_DT:
            continue
        count["general"] += 1
        contest = re.sub(r"\s+", " ", r[idx["contest_name"]]).strip()
        if contest.upper().startswith("US "):
            count["federal"] += 1
            continue
        if race_of(contest)[0]:
            count["state"] += 1
            continue
        row = {k: re.sub(r"\s+", " ", r[i]).strip() for k, i in idx.items() if k != "election_dt"}
        row["contest_name"], row["row"] = contest, n
        row["name_on_ballot"] = local_name(row["name_on_ballot"])      # "" when the cell is not a name: dropped here, said on the race
        count["names_dropped"] += not row["name_on_ballot"]
        rows.append(row)
    del text
    meta = {"url": fed.url(fed.LISTING), "sha256": hashlib.sha256(data).hexdigest(), "published": fed.published(fed.LISTING),
            "read": dt.date.today().isoformat(), "rows_in_file": count["file"], "general_rows": count["general"],
            "federal_rows": count["federal"], "state_rows": count["state"], "names_dropped": count["names_dropped"],
            "columns_kept": [k for k in LOCAL_KEEP if k != "election_dt"], "rows": rows}
    os.makedirs(folder, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=0)
    os.replace(path + ".part", path)
    return path


LOCAL_NOT_A_NAME = re.compile(r"\d|@|www\.|\.(?:com|org|net)\b", re.I)


def local_name(raw):
    """A local candidate's name as filed, or "" when the cell holds something other than a name: a digit, "@", a web
    address, or anything ballot.check_local reads as contact details (a post-office box, a street, a ZIP code). The
    state part's rule (NOT_A_NAME) also refuses the bare words "box" and "po", which are people's names too; here a
    refused cell leaves one candidate out, so the rule is the exact one."""
    name = re.sub(r"\s+", " ", str(raw or "").replace(" ", " ")).strip()
    return "" if not name or LOCAL_NOT_A_NAME.search(name) or contact_like(name, True) else name


def lists_page(folder, say, refresh=False):
    """Whether the Board's candidate-lists page still says the November lists are not final: the finding, the day and the
    page's SHA-256, never the page itself. None when the page cannot be read and no earlier finding is kept."""
    path = os.path.join(folder, PAGE_FILE)
    if fresh(path, 2) and not refresh:
        return json.load(open(path, encoding="utf-8"))
    try:
        time.sleep(1.0)
        data = net.get(LISTS_PAGE, accept="text/html")
    except OSError as e:
        if os.path.exists(path):
            say(f"      could not read the Board's candidate-lists page again ({e}); using the earlier finding")
            return json.load(open(path, encoding="utf-8"))
        say(f"      could not read the Board's candidate-lists page ({e}); nothing is said about whether its lists are final")
        return None
    words = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", data.decode("utf-8", "replace"))))
    keep = {"url": LISTS_PAGE, "read": dt.date.today().isoformat(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "names_2026_list": bool(re.search(r"2026 Candidate List Spreadsheet", words, re.I)),
            "not_final": bool(re.search(r"lists for the November election are not yet final", words, re.I)),
            "green_pending": bool(re.search(r"Green Party still has time to submit", words, re.I))}
    del words
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=1)
    return keep


def census_places(path):
    """({name as spelled for matching: [(place code, name with its kind word, kind word)]}, how many) for North
    Carolina's incorporated cities, towns and villages, from the Census Bureau's 2020 place codes."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].split("|")[:8] != ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT"]:
        raise ListError(f"North Carolina: {os.path.basename(path)} does not begin with the header this loader was checked against")
    out, n = collections.defaultdict(list), 0
    for ln in lines[1:]:
        f = ln.split("|")
        if len(f) < 8 or f[1] != FIPS or not f[5].upper().startswith("INCORPORATED"):
            continue
        base, _, kind = f[4].rpartition(" ")
        if kind not in ("city", "town", "village") or not re.fullmatch(r"\d{5}", f[2]):
            continue
        out[spell(base)].append((f[2], f[4], kind))
        n += 1
    return out, n


ROMAN = re.compile(r"(?=[IVX])X{0,2}(?:IX|IV|V?I{0,3})")
UNEXPIRED = re.compile(r"\s*\(UNEXPIRED\)\s*$")
MUNI = re.compile(r"(CITY|TOWN|VILLAGE) OF (.+)")
MUNI_OFFICE = re.compile(r"(?P<office>MAYOR|(?:(?:CITY|TOWN|VILLAGE) )?COUNCIL(?: MEMBERS?)?|COUNCILM[AE]N|(?:(?:CITY|TOWN|VILLAGE) )?COMMISSIONERS?|"
                         r"BOARD OF COMMISSIONERS|BOARD OF ALDERMEN|ALDERM[AE]N)(?: (?P<tail>.+))?")
COUNTY_OFFICES = {"CLERK OF SUPERIOR COURT": ("clerk_of_court", "Clerk of Superior Court"), "SHERIFF": ("sheriff", "Sheriff"),
                  "REGISTER OF DEEDS": ("register_of_deeds", "Register of Deeds"), "CORONER": ("coroner", "Coroner"),
                  "TAX COLLECTOR": ("tax_collector", "Tax Collector")}
KNOWN_KINDS = {"county_commissioner", "sheriff", "soil_water", "mayor", "council", "school_board", "sanitary_board", "district_court"}      # kinds the pages already know


def spell(text):
    """A place name as it is compared: capitals, a hyphen as a space, no other punctuation."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", "", (text or "").upper().replace("-", " "))).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def plain(text):
    """The list's capitals in ordinary capitals: 'MOUNT AIRY CITY SCHOOLS' -> 'Mount Airy City Schools', 'SWAN QUARTER
    TWP' -> 'Swan Quarter Township', 'DISTRICT III' -> 'District III', '(NORTH)' -> '(North)', '02' -> '2'."""
    out = []
    for i, w in enumerate((text or "").split()):
        lead, core, trail = re.fullmatch(r"(\(?)(.*?)(\)?)", w).groups()
        if core.isdigit():
            core = str(int(core))
        elif re.fullmatch(r"\d+[A-Z]", core):
            core = core.lstrip("0")                          # a court district: 06B -> 6B
        elif ROMAN.fullmatch(core) or len(core) == 1 or core in ("NC", "US"):
            pass                                             # III, IV; District A
        elif core in ("TWP", "TWP."):
            core = "Township"
        elif core in ("OF", "AND", "THE") and i:
            core = core.lower()
        else:
            core = "-".join(re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p.capitalize()) for p in core.split("-"))
        out.append(lead + core + trail)
    return " ".join(out)


def dist_words(tok):
    """A district as the list numbers it: '03' -> '3' (the page writes District 3), 'III' -> 'District III',
    'A' -> 'District A'."""
    t = tok.strip()
    return str(int(t)) if t.isdigit() else "District " + plain(t)


def where_words(tail):
    """(district, seat, role) from what follows the office in a contest name, in the list's own words."""
    t = re.sub(r"\s+", " ", tail or "").strip()
    if t in ("", "MEMBER", "MEMBERS"):
        return None, None, None
    if t in ("CHAIRMAN", "CHAIR", "CHAIRPERSON"):
        return None, None, plain(t)
    if re.fullmatch(r"(?:MEMBERS? )?AT[- ]LARGE", t):
        return None, "At Large", None
    m = re.fullmatch(r"AT[- ]LARGE SEAT (\d+)", t)
    if m:
        return None, f"At Large, Seat {int(m.group(1))}", None
    if t in ("COUNTY-WIDE", "COUNTYWIDE", "COUNTY WIDE"):
        return None, "County-wide", None
    m = re.fullmatch(r"(?:DISTRICT|DIST\.?) (\w+)(?: SEAT (\d+))?", t)
    if m:
        return dist_words(m.group(1)), (str(int(m.group(2))) if m.group(2) else None), None
    m = re.fullmatch(r"WARD (\w+)", t)
    if m:
        return "Ward " + plain(m.group(1)), None, None
    m = re.fullmatch(r"SEAT (\d+)(?: \(([^()]+)\))?", t)
    if m:
        return None, (f"Seat {int(m.group(1))} ({plain(m.group(2))})" if m.group(2) else str(int(m.group(1)))), None
    return plain(t), None, None                              # a named district, ward or township, as the list words it


def _municipal(hit, office):
    code, name, kind = hit
    base = name[:-len(kind) - 1]
    district, seat, role = where_words(office.group("tail"))
    return dict(level="city", kind="mayor" if office.group("office") == "MAYOR" else "council", office=plain(office.group("office")),
                jur=base if base.lower().endswith(" " + kind) else name,      # "Chimney Rock Village", not "... Village village"
                jtype="mcd", code=code, district=district, seat=seat, role=role)


def classify(contest, county_names, places):
    """What one contest name of the list is: level, office kind, the office in plain words, the jurisdiction and the
    district, seat or role, or None when no rule here fits (the caller leaves the contest out and says so; nothing is
    guessed). county_names are the counties in capitals as the list writes them; places is census_places()."""
    c = UNEXPIRED.sub("", re.sub(r"\s+", " ", (contest or "").upper()).strip())

    # district offices: trial judges and district attorneys
    m = re.fullmatch(r"NC (DISTRICT|SUPERIOR) COURT JUDGE DISTRICT 0*(\d+[A-Z]?) SEAT 0*(\d+)", c)
    if m:
        court, d = m.group(1).title(), m.group(2)
        return dict(level="court", kind="district_court" if court == "District" else "superior_court", office=f"{court} Court Judge",
                    jur=f"{court} Court District {d}", jtype="judicial", jkey=("DC-" if court == "District" else "SUP-") + d,
                    district=d if d.isdigit() else f"District {d}", seat=m.group(3), role=None)
    m = re.fullmatch(r"DISTRICT ATTORNEY DISTRICT 0*(\d+[A-Z]?)", c)
    if m:
        d = m.group(1)
        return dict(level="court", kind="district_attorney", office="District Attorney", jur=f"Prosecutorial District {d}",
                    jtype="judicial", jkey="DA-" + d, district=d if d.isdigit() else f"District {d}", seat=None, role=None)
    if re.match(r"NC (DISTRICT|SUPERIOR) COURT|DISTRICT ATTORNEY", c):
        return None

    # boards of education, named as the list names them
    m = re.fullmatch(r"(.+?) BOARD OF EDUCATION(?: (.+))?", c)
    if m:
        district, seat, role = where_words(m.group(2))
        return dict(level="school", kind="school_board", office=f"{role}, Board of Education" if role else "Board of Education Member",
                    jur=f"{plain(m.group(1))} Board of Education", jtype="school", district=district, seat=seat, role=role)

    # soil and water conservation districts: one contest in each county of a district
    m = re.fullmatch(r"(.+?) SOIL AND WATER CONSERVATION DISTRICT(?: SUPERVISORS?)?", c)
    if m:
        left, dash, right = m.group(1).partition(" - ")
        name = right if dash and left in county_names else m.group(1)
        return dict(level="soil_water", kind="soil_water", office="Soil and Water Conservation District Supervisor",
                    jur=f"{plain(name)} Soil and Water Conservation District", jtype="soil", district=None, seat=None, role=None)

    # sanitary districts
    m = re.fullmatch(r"(.+?) SANITARY (LAND DISTRICT|DISTRICT|BOARD)(?: (SUPERVISORS?|BOARD MEMBERS?|COMMISSIONERS?|MEMBERS?))?", c)
    if m:
        left, dash, right = m.group(1).partition(" - ")
        name = right if dash and left in county_names else m.group(1)
        title = {"S": "Supervisor", "C": "Commissioner"}.get((m.group(3) or "B")[0], "Board Member")
        return dict(level="other", kind="sanitary_board", office=f"Sanitary District {title}",
                    jur=f"{plain(name)} Sanitary {'Land District' if m.group(2) == 'LAND DISTRICT' else 'District'}", jtype="special",
                    district=None, seat=None, role=None)

    # county offices
    for cn in sorted(county_names, key=len, reverse=True):
        if not c.startswith(cn + " COUNTY "):
            continue
        rest = c[len(cn) + 8:]
        m = re.fullmatch(r"(?:BOARD|BD\.?) OF COMMISSIONERS(?: (.+))?", rest)
        if m:
            district, seat, role = where_words(m.group(1))
            return dict(level="county", kind="county_commissioner", office=f"{role}, Board of Commissioners" if role else "County Commissioner",
                        county=cn, jtype="county", district=district, seat=seat, role=role)
        if rest in COUNTY_OFFICES:
            kind, office = COUNTY_OFFICES[rest]
            return dict(level="county", kind=kind, office=office, county=cn, jtype="county", district=None, seat=None, role=None)
        return None

    # cities, towns and villages: the longest incorporated place name the contest begins with, then a municipal office
    m = MUNI.fullmatch(c)
    toks = (m.group(2) if m else c).split()
    for n in range(len(toks) - 1, 0, -1):
        hits = places.get(spell(" ".join(toks[:n])), [])
        if m and len(hits) > 1:
            hits = [h for h in hits if h[2] == m.group(1).lower()]
        office = MUNI_OFFICE.fullmatch(" ".join(toks[n:]))
        if len(hits) == 1 and office:
            return _municipal(hits[0], office)
    if m:      # a municipality the Census list does not have: taken only when one split leaves a municipal office
        splits = [(n, MUNI_OFFICE.fullmatch(" ".join(toks[n:]))) for n in range(1, len(toks))]
        splits = [(n, o) for n, o in splits if o]
        if len(splits) == 1:
            n, office = splits[0]
            kind = m.group(1).lower()
            return _municipal((None, f"{plain(' '.join(toks[:n]))} {kind}", kind), office)
    return None


def local_part(loc, counties, party_name, places, page, say):
    """The list's local contests -> the rows to write (races, candidates, places, gaps, notes) and the counts that
    reconcile them with the list. Nothing is written here."""
    upper = {name.upper(): (geoid, name) for geoid, name in counties.values()}
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    attrs = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in loc["rows"]:
        county = r["county_name"].upper()
        if fold(county) not in counties:
            raise ListError(f"North Carolina: row {r['row']} of the candidate listing names a county the Census file does not have")
        upper.setdefault(county, counties[fold(county)])
        by[r["contest_name"]][county].append((local_name(r["name_on_ballot"]), r["party_candidate"]))      # checked again on the way in
        for k in ("is_partisan", "is_unexpired", "vote_for"):
            attrs[r["contest_name"]][k].add(r[k])

    gaps, checks, left_rows = [], [], 0

    def leave(contest, what, reason):
        nonlocal left_rows
        left_rows += sum(len(v) for v in by[contest].values())
        gaps.append((STATE, "race", "contest-" + slug(contest), plain(contest), what, reason, fed.url(fed.LISTING)))

    # 1. what each contest is
    found = {}
    for contest in sorted(by):
        a = attrs[contest]
        lists = {tuple(v) for v in by[contest].values()}
        entries = next(iter(lists))
        named = [n for n, _p in entries if n]
        if any(len(v) != 1 for v in a.values()) or not next(iter(a["vote_for"])).isdigit() or next(iter(a["is_partisan"])) not in ("TRUE", "FALSE"):
            leave(contest, "a contest whose rows disagree",
                  "The rows of this contest in the State Board's list do not agree on, or do not say, whether it is partisan, how many to "
                  "vote for or whether the term is unexpired, so it is not loaded until they do.")
        elif len(lists) != 1:
            leave(contest, "a contest the county boards list differently",
                  "The county boards whose ballots carry this contest do not list the same candidates in the same order in the State "
                  "Board's list, so it is not loaded until they agree.")
        elif len(set(named)) != len(named):
            leave(contest, "a contest listing one name twice",
                  "The State Board's list gives the same name twice in this contest, so it is not loaded until the list is corrected.")
        elif next(iter(a["is_partisan"])) == "TRUE" and any(n and not p for n, p in entries):
            leave(contest, "a partisan contest with a candidate whose party is blank",
                  "The State Board's list marks this contest partisan but gives one of its candidates no party, so it is not loaded "
                  "until the list is corrected.")
        else:
            c = classify(contest, set(upper), places)
            if c is None:
                leave(contest, "a contest this loader has no rule for",
                      "The State Board's list names this contest in a way this loader has no rule for yet; it is left out rather than "
                      "guessed at.")
            else:
                found[contest] = c

    # 2. jurisdictions: the counties whose boards list each one's contests, then its id
    reach = collections.defaultdict(set)
    for contest, c in found.items():
        c["cids"] = sorted(upper[k][0] for k in by[contest])
        if c["jtype"] == "county":
            geoid, name = upper[c["county"]]
            if geoid not in c["cids"]:
                checks.append(f"{plain(contest)}: listed by another county's board ({', '.join(sorted(by[contest]))}); filed under the county it names")
                c["cids"] = sorted(set(c["cids"]) | {geoid})
            c["jur"], c["jid"] = f"{name} County", geoid
        elif c["jtype"] == "soil" and len(c["cids"]) == 1:
            c["jid"] = c["cids"][0]                         # the district's election in this county (G.S. 139-6)
        elif c["jtype"] == "judicial":
            c["jid"] = f"{STATE}-{c['jkey']}"
        elif c["jtype"] == "mcd" and c.get("code"):
            c["jid"] = f"{STATE}-M-{c['code']}"
        else:
            reach[(c["jtype"], c["jur"])].update(c["cids"])
    for contest, c in found.items():
        if "jid" not in c:                                  # no official code: the county's three digits and the name
            letter = {"mcd": "M", "school": "S"}.get(c["jtype"], "X")
            c["jid"] = f"{STATE}-{letter}-{min(reach[(c['jtype'], c['jur'])])[2:]}-{slug(c['jur'])}"
    for name in sorted({c["jur"] for c in found.values() if c["jtype"] == "mcd" and not c.get("code")}):
        checks.append(f"{name}: not in the Census Bureau's 2020 place codes; named as the Board's list writes it, with no place code")

    # 3. races and candidates
    races, cands, ids, place_reach, place_name = [], [], {}, collections.defaultdict(set), {}
    placed_rows = dropped_names = 0
    for contest in sorted(found):
        c, a = found[contest], attrs[contest]
        entries = next(iter(by[contest].values()))
        special = int(a["is_unexpired"] == {"TRUE"})
        if bool(special) != bool(UNEXPIRED.search(contest.upper())):
            checks.append(f"{plain(contest)}: the name and the list's unexpired column disagree; the column is followed")
        partisan = int(a["is_partisan"] == {"TRUE"})
        vote_for = int(next(iter(a["vote_for"])))
        if c["level"] == "court":
            rid = f"2026-{STATE}-{c['jkey']}" + (f"-{c['seat']}" if c["seat"] else "") + ("-S" if special else "")
        else:
            where = [("d" + c["district"] if c["district"].isdigit() else slug(c["district"])) if c["district"] else "",
                     ("seat" + c["seat"] if c["seat"].isdigit() else slug(c["seat"])) if c["seat"] else "", slug(c["role"] or "")]
            jkey = c["jid"][len(STATE) + 1:] if c["jid"].startswith(STATE + "-") else c["jid"]
            rid = "-".join(b for b in [f"2026-{STATE}", jkey, c["kind"].replace("_", "-")] + where if b) + ("-S" if special else "")
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise ListError(f"North Carolina: a race id that is not letters, digits and hyphens ({rid!r})")
        if rid in ids:
            raise ListError(f"North Carolina: two contests of the list share the race id {rid}: {ids[rid]!r} and {contest!r}")
        ids[rid] = contest
        named = [(n, p) for n, p in entries if n]
        note = []
        if vote_for > 1:
            note.append(f"Voters choose {vote_for}.")
        if special:
            note.append("An election for the rest of an unexpired term.")
        lost = len(entries) - len(named)
        if lost:
            dropped_names += lost
            first = min(r["row"] for r in loc["rows"] if r["contest_name"] == contest)
            note.append(("One name" if lost == 1 else f"{lost} names") + " on the Board's list for this contest could not be read as a name and "
                        + ("is" if lost == 1 else "are") + " left out.")
            gaps.append((STATE, "race", rid, f"{c['office']}, {c['jur']}", "a candidate whose name cell could not be read",
                         "A name cell for this contest in the State Board's list held something other than a name, so that candidate is "
                         f"left out until the list is corrected (the contest begins at row {first} of the file).", fed.url(fed.LISTING)))
        elif len(named) < vote_for:
            note.append(f"The Board's list has {len(named)} candidate{'' if len(named) == 1 else 's'} for these {vote_for} seats.")
        if "(Special)" in (c["seat"] or "") + (c["district"] or "") and not special:
            note.append('The word "Special" is part of this seat\'s name on the Board\'s list, which marks the contest as a regular term, '
                        "not an unexpired one.")
        if not partisan and any(p for _n, p in entries):
            checks.append(f"{plain(contest)}: a nonpartisan contest whose rows carry a party; the party is not shown")
        races.append([rid, STATE, c["level"], c["kind"], c["office"], c["jur"], c["jid"], json.dumps(c["cids"]), c["district"], c["seat"],
                      special, partisan, None, None, None, GENERAL, " ".join(note) or None])
        for raw, code in named:
            name, caps = shown(raw)
            party = party_name(code) if partisan else "Nonpartisan office"
            cands.append([rid, "general", GENERAL, name, party, party_code(party) if partisan else "N", None, 0, 0, None, None, None, None,
                          SRC_LOCAL, CAPS if caps else None])
        placed_rows += len(entries) * len(by[contest])
        if c["jtype"] != "county":
            place_reach[c["jid"]].update(c["cids"])
            place_name[c["jid"]] = (c["jtype"], c["jur"], c.get("code"))
    keys = [(c[0], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise ListError("North Carolina: two local candidate rows share a race and a name")
    if placed_rows + left_rows != len(loc["rows"]):
        raise ListError(f"North Carolina: {len(loc['rows'])} local rows read but {placed_rows} placed and {left_rows} left out")

    # 4. places: every jurisdiction the races use that is not a county (a soil and water contest is filed under its county)
    kind_of_place = {"mcd": "mcd", "school": "school", "special": "special", "soil": "special", "judicial": "judicial"}
    place_rows = [(kind_of_place[jtype], jid, name, json.dumps(sorted(place_reach[jid])), SRC_PLACE if code else SRC_LOCAL)
                  for jid, (jtype, name, code) in sorted(place_name.items()) if not re.fullmatch(rf"{FIPS}\d{{3}}", jid)]

    # 5. the counts, the notes and the gaps
    local = [r for r in races if r[2] in LOCAL_LEVELS]
    court = [r for r in races if r[2] == "court"]
    lids, cids_ = {r[0] for r in local}, {r[0] for r in court}
    by_level = collections.Counter(r[2] for r in local)
    by_kind = collections.Counter(r[3] for r in races)
    with_kind = collections.defaultdict(set)
    for r in races:
        with_kind[r[3]].update(json.loads(r[7]))
    reached = {g for r in local for g in json.loads(r[7])}
    n_muni = sum(1 for (jtype, _n, _c) in place_name.values() if jtype == "mcd")
    n_coded = sum(1 for (jtype, _n, code) in place_name.values() if jtype == "mcd" and code)
    n_san = len({r[6] for r in local if r[3] == "sanitary_board"})
    n_lcands, n_ccands = sum(1 for c in cands if c[0] in lids), sum(1 for c in cands if c[0] in cids_)
    day = lambda iso: f"{dt.date.fromisoformat(iso):%B} {dt.date.fromisoformat(iso).day}, {dt.date.fromisoformat(iso).year}"
    not_final = bool(page and page.get("names_2026_list") and page.get("not_final"))
    if not_final:
        gaps.append((STATE, "state", STATE, "North Carolina", "local contests added to the list after it was read",
                     f"On {day(page['read'])} the State Board of Elections' candidate-lists page said its November lists were not yet final, "
                     "because some local contests had not yet filed" + (" and the Green Party could still name candidates" if page.get("green_pending") else "")
                     + "; this loader reads the Board's list again each time it runs.", LISTS_PAGE))
    gaps.append((STATE, "state", STATE, "North Carolina", "offices nobody filed for",
                 "The State Board of Elections' candidate list has a row for each candidate, so an office that drew no candidate does not "
                 "appear in it; a county's own sample ballot is the place to check for one.", LISTS_PAGE))
    total = len(counties)
    cnt = lambda kind: f"all {total}" if len(with_kind[kind]) == total else str(len(with_kind[kind]))
    calendar = (
        f"On November 3, 2026, of North Carolina's {total} counties, {cnt('sheriff')} elect a sheriff, {cnt('clerk_of_court')} a clerk of superior "
        f"court, {cnt('county_commissioner')} county commissioners and {cnt('register_of_deeds')} a register of deeds; soil and water conservation "
        "district supervisors, district attorneys and superior and district court judges are on the same ballot (G.S. 163-1, 139-6). Cities, "
        "towns, villages and sanitary districts hold their regular elections in odd-numbered years (G.S. 163-279, 130A-50), next in 2027; the "
        f"{n_muni} {'municipality' if n_muni == 1 else 'municipalities'} and {n_san} sanitary district{'' if n_san == 1 else 's'} on this list "
        "vote in even years instead. The general law elects county boards of education at the March primary (G.S. 115C-37); the list has "
        f"November contests for boards of education in {cnt('school_board')} counties.")
    coverage = (
        f"Loaded from the State Board of Elections' candidate list as read on {day(loc['read'])}: every November 3 contest in it for county "
        "offices, boards of education, soil and water conservation districts, cities, towns and villages, sanitary districts, district "
        f"attorneys and superior and district court judges, {len(races):,} contests and {len(cands):,} candidates, with a local contest in "
        + (f"all {total} counties" if len(reached) == total else f"{len(reached)} of the {total} counties")
        + ". The list states no ballot order, has a row only for candidates (an office nobody filed for is not in it) and no mark for anyone "
        "who withdrew; ballot questions, write-in candidates and local primaries are not loaded."
        + (f" On {day(page['read'])} the Board's page said its November lists were not yet final." if not_final else "")
        + (f" {sum(1 for g in gaps if g[1] == 'race')} contests could not be read in full and are listed as gaps." if any(g[1] == "race" for g in gaps) else ""))
    notes = [(STATE, "local_calendar", calendar,
              "N.C. General Statutes 163-1, 163-279, 139-6, 115C-37 and 130A-50 (N.C. General Assembly); counts from the State Board of "
              "Elections' Candidate Listing 2026", STATUTES),
             (STATE, "local_coverage", coverage, "North Carolina State Board of Elections, Candidate Listing 2026 (Candidate_Listing_2026.csv)",
              fed.url(fed.LISTING))]
    for row in races:                                        # the last look: nothing that reads like contact details is stored
        if any(v and contact_like(v, True) for v in (row[4], row[5], row[8], row[9], row[16])):
            raise ListError(f"North Carolina: a stored cell of {row[0]} failed the contact-detail check (not shown)")
    for c in cands:
        if not local_name(c[3]):
            raise ListError(f"North Carolina: a stored name in {c[0]} failed the contact-detail check (not shown)")
    return dict(races=races, cands=cands, places=place_rows, gaps=gaps, notes=notes, checks=checks, local=len(local), court=len(court),
                local_cands=n_lcands, court_cands=n_ccands, by_level=dict(by_level), by_kind=dict(by_kind), reached=len(reached),
                counties=total, placed_rows=placed_rows, left_rows=left_rows, left_contests=len(by) - len(found),
                dropped_names=dropped_names, municipalities=n_muni, coded=n_coded, sanitary=n_san, not_final=not_final,
                partisan=sum(1 for r in local if r[11]), new_kinds=sorted(set(by_kind) - KNOWN_KINDS))


# ---------------------------------------------------------------- the load

def load(db_path, say=print, cache=FED, roster_db=ROSTER, county_zip=COUNTY_ZIP, refresh=False, local_cache=None):
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    local_cache = local_cache or os.path.join(cache, "local")
    os.makedirs(local_cache, exist_ok=True)
    _CSV.clear()                                            # one fetch of the list at most, and never an earlier run's bytes
    problems, checks = [], []

    key_folder = next((f for f in (cache, FED) if os.path.exists(os.path.join(f, "nc_party_key.json"))), cache)
    key = fed.party_names(key_folder)
    key_path = os.path.join(key_folder, "nc_party_key.json")

    def party_name(code):
        if code not in key:
            raise ListError(f"North Carolina: party code {code!r} is not in the Board's party key ({fed.url(fed.PARTY_KEY)})")
        return key[code]

    lpath = listing(cache, say, refresh)
    lst = json.load(open(lpath, encoding="utf-8"))
    locpath = local_listing(local_cache, say, refresh)
    loc = json.load(open(locpath, encoding="utf-8"))
    if loc["sha256"] != lst["sha256"]:      # the two cut-down copies come from different copies of the list: cut both from one fetch
        lpath = listing(cache, say, True)
        lst = json.load(open(lpath, encoding="utf-8"))
        locpath = local_listing(local_cache, say, True)
        loc = json.load(open(locpath, encoding="utf-8"))
        if loc["sha256"] != lst["sha256"]:
            checks.append("the state rows and the local rows were cut from different copies of the Board's list (it could not be read "
                          "again); run again with --refresh")
    zpath = os.path.join(FED, ZIP_NAME) if os.path.exists(os.path.join(FED, ZIP_NAME)) else os.path.join(cache, ZIP_NAME)
    net.download(fed.url(fed.RESULTS), zpath, max_age_days=30, say=say)
    if open(zpath, "rb").read(2) != b"PK":
        raise ListError("North Carolina: the precinct results address did not give a zip file")
    epath, enr = enr_control(cache, say, refresh)

    # control: the results site calls the primary official, everywhere, with every precinct in; no second primary
    unofficial = [c["cnm"] for c in enr["counties"]
                  if "OFFICIAL PRIMARY" not in (c["tle"] or "").upper() or "UNOFFICIAL" in (c["tle"] or "").upper()]
    short_ = [c["cnm"] for c in enr["counties"] if c["prt"] != c["ptl"]]
    if unofficial or short_:
        raise ListError(f"North Carolina: the March 3 results are not official everywhere (not official: {unofficial}; "
                        f"precincts missing: {short_})")
    state_row = next(c for c in enr["counties"] if c["cid"] == "0")
    later = [e for e in enr["elections"] if e.endswith("/2026") and e not in (PRIMARY_DT, GENERAL_DT)
             and ("03", "03") < (e[:2], e[3:5]) < ("11", "03")]
    if later:
        raise ListError(f"North Carolina: the results site holds a later 2026 election ({later}); a second primary is not read yet")
    when = re.match(r"([A-Z][a-z]+ \d{1,2}, \d{4})", state_row.get("imp") or "")
    certified_on = dt.datetime.strptime(when.group(1), "%B %d, %Y").date().isoformat() if when else ""

    # 1. the November ballot: every county's list of a contest must agree
    counties = census_counties(county_zip)
    by_contest = collections.defaultdict(lambda: collections.defaultdict(list))
    primary_listed = collections.defaultdict(set)
    primary_counties = collections.defaultdict(set)
    special_of = {}
    for r in lst["rows"]:
        rid, special = race_of(r["contest_name"])
        special_of[rid] = special
        county = r["county_name"].strip().upper()
        if fold(county) not in counties:
            raise ListError(f"North Carolina: the list names a county the Census file does not have ({county})")
        if r["vote_for"] not in ("1", ""):
            problems.append(f"{rid}: the list says vote for {r['vote_for']}; only single-seat contests are read")
        if r["election_dt"] == GENERAL_DT:
            by_contest[rid][county].append((r["name_on_ballot"], r["party_candidate"]))
        elif r["election_dt"] == PRIMARY_DT:
            primary_listed[(rid, r["party_contest"])].add(r["name_on_ballot"])
            primary_counties[rid].add(county)
        else:
            raise ListError(f"North Carolina: a state row for an election the loader does not read ({r['election_dt']})")
    november, reach = {}, {}
    for rid in sorted(by_contest):
        lists = {tuple(v) for v in by_contest[rid].values()}
        if len(lists) != 1:
            raise ListError(f"North Carolina: the counties' lists of {rid} differ")
        entries = next(iter(lists))
        if len(set(entries)) != len(entries):
            raise ListError(f"North Carolina: {rid} lists a candidate twice")
        november[rid] = entries
        reach[rid] = sorted(counties[fold(c)][0] for c in by_contest[rid])
        if primary_counties.get(rid) and primary_counties[rid] != set(by_contest[rid]):
            checks.append(f"{rid}: the primary rows reach {len(primary_counties[rid])} counties, the November rows {len(by_contest[rid])}")

    # the seats that must be there
    expected = ([f"2026-{STATE}-SS{d}" for d in range(1, SENATE_SEATS + 1)] + [f"2026-{STATE}-SH{d}" for d in range(1, HOUSE_SEATS + 1)]
                + [f"2026-{STATE}-SC{s}" for s in COURT_SEATS["SC"]] + [f"2026-{STATE}-COA{s}" for s in COURT_SEATS["COA"]])
    for rid in expected:
        if rid not in november:
            problems.append(f"{rid}: no November candidates on the Board's list")
    extra = sorted(set(november) - set(expected))
    if extra:
        checks.append(f"races on the list beyond the regular seats: {extra} (read as they are)")
    all_races = expected + [r for r in extra if r not in expected]

    # 2. the primary fields, from the precinct results, checked against the listing and the results site
    votes, by_county, pct_rows = precinct_totals(zpath)
    site = collections.defaultdict(dict)
    for r in enr["results"]:
        m = re.search(r"- ([A-Z]{3}) \(VOTE FOR", r["cnm"])
        site[(race_of(r["cnm"])[0], m.group(1) if m else "")][r["bnm"]] = int(r["vct"])
        if r["prt"] != r["ptl"]:
            raise ListError(f"North Carolina: {r['cnm']} is not fully reported on the results site")
    mismatch, differ = [], []
    for k in sorted(set(votes) | set(site) | set(primary_listed)):
        if dict(votes.get(k, {})) != site.get(k, {}):
            mismatch.append(f"{k[0]} {k[1]}")
        listed = {fold(re.sub(MARK, "", n)): n for n in primary_listed.get(k, set())}
        counted = {fold(re.sub(MARK, "", n)): n for n in votes.get(k, {})}
        if set(listed) != set(counted):
            differ.append(f"{k[0]} {k[1]}: list only {sorted(listed[n] for n in set(listed) - set(counted))}, "
                          f"results only {sorted(counted[n] for n in set(counted) - set(listed))}")
    if mismatch:
        raise ListError("North Carolina: the precinct sums differ from the results site's official statewide totals for " + "; ".join(mismatch))
    for k, cs in by_county.items():
        if sum(cs.values()) != sum(votes[k].values()):
            raise ListError(f"North Carolina: county sums of {k} do not add to the statewide total")
        outside = sorted(set(cs) - set(by_contest.get(k[0], {})))
        if outside:
            checks.append(f"{k[0]} {k[1]}: primary votes counted in counties the November list does not reach: {outside}")
    for d in differ:
        checks.append(f"the candidate listing and the primary results differ: {d}")

    # 3. the races
    members = roster(roster_db)
    race_rows, holders = {}, {}
    for rid in all_races:
        k = kind_of(rid)
        num = re.search(r"(\d+)", rid.split(f"-{STATE}-", 1)[1])
        n = num.group(1) if num else None
        special = special_of.get(rid, False)
        note, holder, district, seat, cids = [], None, None, None, None
        if k in ("SS", "SH"):
            chamber = "Senate" if k == "SS" else "House"
            level, kind = "legislature", ("state_senate" if k == "SS" else "state_house")
            office = "State Senator" if k == "SS" else "State Representative"
            district = n
            jur, jur_id = f"{chamber} District {n}", n
            sitting = members.get((chamber, n), [])
            if len(sitting) == 1:
                holder = sitting[0]
            elif not sitting:
                note.append("No sitting member for this seat on the Open States roster used here (the seat is vacant, or the "
                            "roster has not caught up).")
            else:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster")
            note.append(SENATE_NOTE if k == "SS" else HOUSE_NOTE)
            cids = json.dumps(reach[rid]) if rid in reach else None
        else:
            level = "court"
            kind = "supreme_court" if k == "SC" else "court_of_appeals"
            office = "Associate Justice of the Supreme Court" if k == "SC" else "Judge of the Court of Appeals"
            if rid.endswith("SC-CJ"):
                office = "Chief Justice of the Supreme Court"
            seat = f"Seat {n}" if n else None
            jur, jur_id = "North Carolina", FIPS
            note.append(COURT_NOTE)
        if special:
            note.append("An election for the rest of an unexpired term.")
        if rid in november and len(november[rid]) == 1:
            note.append("One candidate is on the Board's November list for this seat.")
        note.append(ORDER_NOTE)
        holders[rid] = holder
        race_rows[rid] = [rid, STATE, level, kind, office, jur, jur_id, cids, district, seat, int(special), 1,
                          holder["id"] if holder else None, holder["name"] if holder else None, holder["party"] if holder else None,
                          GENERAL, " ".join(note)]

    # 4. November candidates
    cands = []
    for rid, entries in sorted(november.items()):
        holder = holders.get(rid)
        inc = find_incumbent([n for n, _c in entries], holder) if holder else None
        if holder and len(incumbent_hits([n for n, _c in entries], holder)) > 1:
            checks.append(f"{rid}: more than one name fits the sitting member; none is marked")
        for raw, code in entries:
            name, caps = shown(raw)
            party = party_name(code)
            is_inc = int(raw == inc)
            cands.append([rid, "general", GENERAL, name, party, party_code(party), None, is_inc, 0, None, None, None,
                          holder["id"] if is_inc else None, SRC_LIST, CAPS if caps else None])

    # 5. primary fields
    nfields, gone, low, unrun = 0, [], [], []
    for (rid, code), field in sorted(votes.items()):
        party = party_name(code)
        wins = [c for c in field if not re.match(r"(?i)write", c)]
        if len(wins) < 2:
            continue
        if rid not in race_rows:
            problems.append(f"{rid}: a {party} primary field for a race not on the November list")
            continue
        total = sum(field.values())
        if total == 0:
            marked = [shown(re.sub(MARK, "", c))[0] for c in wins if re.search(MARK, c)]
            on_list = [shown(n)[0] for n, c in november.get(rid, ()) if c == code]
            race_rows[rid][16] += (f" The Board's results carry a {party} primary for this seat with no votes counted"
                                   + (f" (the results mark {' and '.join(marked)} as deceased)" if marked else "")
                                   + (f"; the party's candidate on the November list is {' and '.join(on_list)}." if on_list else "."))
            unrun.append(f"{rid} {code}")
            continue
        nfields += 1
        ranked = sorted(wins, key=lambda c: -field[c])
        if field[ranked[0]] == field[ranked[1]]:
            problems.append(f"{rid} {party}: a tie at the top of the primary")
        leader = ranked[0]
        share = 100 * field[leader] / total if total else 0
        on_list = [n for n, c in november.get(rid, ()) if c == code]
        holder = holders.get(rid)
        inc = find_incumbent(list(field), holder) if holder else None
        replaced = bool(on_list) and not any(same_person(n, leader) for n in on_list)
        if replaced or not on_list:
            instead = (" The Board's November list names " + " and ".join(shown(n)[0] for n in on_list) + f" as the {party} candidate.") if on_list else ""
            race_rows[rid][16] += f" The {party} primary's winner ({shown(leader)[0]}) is not on the Board's November list.{instead}"
            gone.append(f"{shown(leader)[0]} ({rid} {code})")
        for c in ranked:
            name, caps = shown(re.sub(MARK, "", c))
            notes = [CAPS if caps else "", "The Board's results mark this candidate as deceased." if re.search(MARK, c) else ""]
            if c == leader:
                if share <= RUNOFF_SHARE:
                    notes.append("Led with 30 percent or less; no second primary was held, so the leader is the nominee.")
                    low.append(f"{rid} {code}")
                if replaced or not on_list:
                    notes.append("Won the primary but is not on the Board's November list.")
            is_inc = int(c == inc)
            cands.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, is_inc, 0, field[c],
                          round(100 * field[c] / total, 1) if total else None, "advanced" if c == leader else "lost",
                          holder["id"] if is_inc else None, SRC_PCT, " ".join(n for n in notes if n) or None])

    # 6. the last look at every stored text: no contact detail can reach the database
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        problems.append("two candidate rows share race, election and name")
    for c in cands:
        if NOT_A_NAME.search(c[3]) or (c[14] and re.search(r"@|www|\d{3}", c[14])):
            raise ListError(f"North Carolina: a stored cell for {c[0]} failed the contact-detail check (not shown)")

    # 7. places
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid in all_races:
        k = kind_of(rid)
        if k in ("SS", "SH") and rid in reach and not special_of.get(rid):
            d = race_rows[rid][8]
            place_rows.append(("senate" if k == "SS" else "house", f"{STATE}-{d}", race_rows[rid][5], json.dumps(reach[rid]), SRC_LIST))

    # 7b. the county and local part: the same list's other November contests (county offices, boards of education, soil and
    # water, cities and towns, sanitary districts, district attorneys and trial judges)
    ppath = os.path.join(local_cache, PLACE_FILE)
    net.download(PLACE_URL, ppath, max_age_days=3650, say=say)
    places, n_places = census_places(ppath)
    page = lists_page(local_cache, say, refresh)
    local = local_part(loc, counties, party_name, places, page, say)
    clash = sorted(set(race_rows) & {r[0] for r in local["races"]})
    if clash:
        raise ListError(f"North Carolina: a local race id is also a state race id ({clash[:3]})")
    n_local_rows = len(loc["rows"])
    if loc["general_rows"] != loc["federal_rows"] + loc["state_rows"] + n_local_rows:
        raise ListError(f"North Carolina: the list's {loc['general_rows']} November rows are not its {loc['federal_rows']} federal, "
                        f"{loc['state_rows']} state and {n_local_rows} other rows")

    # 8. write
    left = lst.get("district_offices_not_read", {})
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [race_rows[r] for r in all_races] + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
        src = lambda *row: con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
        src(SRC_LIST, STATE, "official candidate list", "North Carolina State Board of Elections",
            "Candidate Listing 2026 (Candidate_Listing_2026.csv): the March 3 primary and the November 3 general election, county by county",
            lst["url"], lst["published"], lst["read"], lst["sha256"], len(lst["rows"]),
            f"The SHA-256 is the whole CSV's as fetched ({lst['rows_in_file']} rows, every office); only the kept cells of the "
            f"State Senate, State House, Supreme Court and Court of Appeals rows are saved. Columns taken by name: "
            f"{', '.join(fed.KEEP)}; addresses, telephones, e-mail and filing dates are never read. The rows dated {GENERAL_DT} "
            "are the November ballot; every county's list of a contest agrees, and the counties a district reaches are those "
            "whose rows carry it. The list gives no ballot order and no status column (a candidate who withdraws is taken out "
            f"of the file). The rows dated {PRIMARY_DT} were used to check the primary results: "
            + ("every candidate agrees." if not differ else "differences: " + "; ".join(differ) + ".")
            + f" The district attorney, superior court and district court contests on the same list are read with the local "
              f"contests ({SRC_LOCAL}).")
        src(SRC_PCT, STATE, "official results", "North Carolina State Board of Elections",
            "Precinct results, March 3, 2026 primary election (results_pct_20260303.zip)", fed.url(fed.RESULTS),
            fed.published(fed.RESULTS), fetched(zpath), sha(zpath), pct_rows,
            "State Senate, State House and Court of Appeals primaries summed over every precinct (administrative precincts "
            "included) by county, then statewide; each row's four voting methods add to its total. The results carry no "
            "write-in line for these contests, so a field's total is the sum of its candidates' votes. Every candidate's "
            "statewide sum equals the results site's official total.")
        src(SRC_ENR, STATE, "official results", "North Carolina State Board of Elections",
            f"Election results site: {state_row['tle']}", fed.ENR + "20260303/data/results_0.txt", certified_on, enr["read"],
            sha(epath), len(enr["results"]),
            f"Control only (from {fed.ENR_SITE}): every county and the state are titled OFFICIAL, with {state_row['prt']} of "
            f"{state_row['ptl']} precincts reporting; the statewide totals match the precinct file exactly. The site lists no "
            "election between March 3 and November 3, 2026, so no second primary was held. Kept fields only.")
        src(SRC_KEY, STATE, "party key", "North Carolina State Board of Elections",
            "Party codes in the voter statistics layout (layout_voter_stats.txt)", fed.url(fed.PARTY_KEY), "",
            fetched(key_path), sha(key_path), len(key), "Party codes written out: " + ", ".join(f"{c} {n}" for c, n in sorted(key.items())) + ".")
        src(SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
            COUNTY_URL, "2024", fetched(county_zip), sha(county_zip), len(counties),
            "Five-digit county codes (GEOID) for North Carolina's 100 counties, matched by name to the candidate list's county boards.")
        src(SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_nc.sqlite",
            "Sitting North Carolina legislators", "https://github.com/openstates/people", "", fetched(roster_db), "",
            sum(len(v) for v in members.values()),
            "Who holds each seat today and which candidate is the sitting member (same chamber and district, the name fits, one "
            "fit only); names, party and ids only. The roster carries no judges.")
        # the local part's sources, after the state part's own
        src(SRC_LOCAL, STATE, "official candidate list", "North Carolina State Board of Elections",
            "Candidate Listing 2026 (Candidate_Listing_2026.csv): the November 3 general election's county, school, soil and water, "
            "municipal, sanitary district, district attorney and trial court contests, county by county",
            loc["url"], loc["published"], loc["read"], loc["sha256"], n_local_rows,
            f"The SHA-256 is the whole CSV's as fetched ({loc['rows_in_file']:,} rows, every office, both elections). Of its "
            f"{loc['general_rows']:,} rows dated {GENERAL_DT}, {loc['federal_rows']:,} are federal (left to the federal pages), "
            f"{loc['state_rows']:,} are the State Senate, State House and appellate court rows ({SRC_LIST}) and {n_local_rows:,} are read "
            "here: one row for each candidate on each county board's ballot. Columns taken by name: "
            f"{', '.join(LOCAL_KEEP)}; the name parts, street address, city, state, ZIP code, telephones, e-mail and filing "
            "date columns are never read, and only the kept cells are saved. Every county board's list of a contest agrees, name for "
            f"name and in the same order: the {local['placed_rows']:,} rows placed are {len(local['cands']) + local['dropped_names']:,} "
            f"candidacies in {len(local['races']):,} contests, each row in exactly one"
            + (f"; {local['left_rows']:,} rows of {local['left_contests']} contests are left out and listed as gaps" if local["left_rows"] else "")
            + (f"; {local['dropped_names']} name cells that did not hold a name were dropped" if local["dropped_names"] else "")
            + ". The list gives no ballot order and no status column (a candidate who withdraws is taken out of the file), and it has "
            "a row only for candidates, so an office nobody filed for is not in it.")
        src(SRC_PLACE, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, North Carolina (st37_nc_place2020.txt)",
            PLACE_URL, "2020", fetched(ppath), sha(ppath), n_places,
            f"Names and five-digit place codes of North Carolina's {n_places} incorporated cities, towns and villages. Each municipality "
            f"on the candidate list is the one place of the same name ({local['coded']} of {local['municipalities']} matched); the file "
            "holds no personal details.")
        if page:
            src(SRC_PAGE, STATE, "official notice", "North Carolina State Board of Elections", "Candidate Lists (web page)", LISTS_PAGE, "",
                page["read"], page["sha256"], 1,
                "Read only for whether it says the November candidate lists are final; the finding and the page's SHA-256 are kept, not "
                "the page, which links the list files and carries no candidate details. "
                + ("It said the November lists were not yet final, because some local contests had not yet filed."
                   if local["not_final"] else "It did not say the November lists were unfinished."))
    con.close()

    # 9. say what happened
    gen = [c for c in cands if c[1] == "general"]
    by = {k: sum(1 for c in gen if kind_of(c[0]) == k) for k in ("SS", "SH", "SC", "COA")}
    seats = {k: sum(1 for r in november if kind_of(r) == k) for k in ("SS", "SH", "SC", "COA")}
    say(f"    North Carolina state offices: {len(race_rows)} races; {seats['SS']} of 50 Senate seats, {seats['SH']} of 120 House "
        f"seats, {seats['SC']} Supreme Court and {seats['COA']} Court of Appeals seats on the Board's November list; {len(gen)} "
        f"candidates ({by['SS']} Senate, {by['SH']} House, {by['SC'] + by['COA']} courts; {sum(1 for c in gen if c[7])} sitting "
        f"members); {nfields} party primaries with a field, official votes reconciled to the results site; no second primary")
    if gone:
        say(f"      primary winners not on the November list: {', '.join(gone)}")
    if low:
        say(f"      led with 30 percent or less (no second primary held): {', '.join(low)}")
    if unrun:
        say(f"      primaries in the results with no votes counted (not shown as fields): {', '.join(unrun)}")
    lv = local["by_level"]
    say(f"    North Carolina county and local offices: {local['local']:,} races ("
        + ", ".join(f"{k.replace('_', ' ')} {lv[k]:,}" for k in LOCAL_LEVELS if lv.get(k)) + f"), {local['local_cands']:,} candidates, a local "
        f"contest in {local['reached']} of {local['counties']} counties; {local['partisan']:,} partisan and {local['local'] - local['partisan']:,} "
        f"nonpartisan; under courts, {local['court']:,} district attorney, superior court and district court contests with "
        f"{local['court_cands']:,} candidates")
    say(f"      the list's {loc['general_rows']:,} November rows: {loc['federal_rows']:,} federal, {loc['state_rows']:,} state, {n_local_rows:,} "
        f"read here; {local['placed_rows']:,} placed, each in exactly one race ({len(local['cands']) + local['dropped_names']:,} candidacies; "
        f"a contest on several counties' ballots has a row for each), {local['left_rows']:,} left out")
    say(f"      municipalities matched to a Census place code: {local['coded']} of {local['municipalities']}; sanitary districts: "
        f"{local['sanitary']}; office kinds: " + ", ".join(f"{k} {v:,}" for k, v in sorted(local["by_kind"].items())))
    if local["new_kinds"]:
        say(f"      office kinds the pages do not know yet: {', '.join(local['new_kinds'])}")
    for g in local["gaps"]:
        say(f"      gap ({g[1]}): {g[3]}: {g[4]}")
    for c in checks + local["checks"]:
        say(f"      check: {c}")
    for p in problems:
        say(f"      CHECK {p}")
    return dict(races=len(race_rows), general=len(gen), by_chamber=by, seats=seats, fields=nfields, gone=gone, low=low, unrun=unrun,
                checks=checks + local["checks"], problems=problems, left_out=left,
                local={k: v for k, v in local.items() if k not in ("races", "cands", "places", "gaps", "notes", "checks")},
                local_gaps=[g[:5] for g in local["gaps"]])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write North Carolina's rows into")
    ap.add_argument("--cache", default=FED, help="where this loader keeps its own cut-down copies (default ballot_cache/nc)")
    ap.add_argument("--local-cache", default=None, help="where the local part keeps its files (default: the folder 'local' inside --cache)")
    ap.add_argument("--refresh", action="store_true", help="fetch the candidate listing, the Board's page and the results site again")
    a = ap.parse_args()
    load(a.db, cache=a.cache, refresh=a.refresh, local_cache=a.local_cache)
