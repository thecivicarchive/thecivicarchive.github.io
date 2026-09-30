"""
ballot/state_local_nc.py - North Carolina's state races on the November 3, 2026 ballot: all 50 seats of the State Senate
and all 120 seats of the State House (both chambers serve two-year terms, so every seat is up in every even year), the one
Supreme Court seat (Associate Justice, Seat 1) and the three Court of Appeals seats (Seats 1, 2 and 3) on the ballot, with
each party's March 3 primary field and its official votes. North Carolina elects its Governor and the rest of its Council of
State in presidential years (2024, 2028), so no statewide executive office is on the 2026 ballot; the Board's list carries
none.

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
    statewide ones, and are counted, not read, in this phase.
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
party_candidate, has_primary, is_unexpired and vote_for. The CSV is never saved; the kept cells of the state rows go to
sl_nc_candidate_listing_2026_state.json with the whole file's SHA-256. A name cell that holds a digit, "@", a web address
or a post-office box stops the loader, which names the contest and the row number, never the text. Nothing but name,
office, district, party and incumbency is stored; no photos, ages, websites, biographies or money.

    python ballot/state_local_nc.py --db <path to a test database> [--cache <folder for this loader's own kept files>]
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
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

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


def listing(folder, say, refresh=False):
    """The candidate listing's state rows (Senate, House, Supreme Court, Court of Appeals), the kept columns only, as
    JSON; fetched afresh after two days. The CSV itself is never written anywhere."""
    path = os.path.join(folder, LIST_FILE)
    if fresh(path, 2) and not refresh:
        return path
    try:
        data = net.get(fed.url(fed.LISTING), accept="text/csv,*/*")
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


# ---------------------------------------------------------------- the load

def load(db_path, say=print, cache=FED, roster_db=ROSTER, county_zip=COUNTY_ZIP, refresh=False):
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
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

    # 8. write
    left = lst.get("district_offices_not_read", {})
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [race_rows[r] for r in all_races])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
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
            + (" District offices on the same list, not read in this phase: "
               + ", ".join(f"{v} {k} contests" for k, v in sorted(left.items())) + "." if left else ""))
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
    for c in checks:
        say(f"      check: {c}")
    for p in problems:
        say(f"      CHECK {p}")
    return dict(races=len(race_rows), general=len(gen), by_chamber=by, seats=seats, fields=nfields, gone=gone, low=low, unrun=unrun,
                checks=checks, problems=problems, left_out=left)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write North Carolina's rows into")
    ap.add_argument("--cache", default=FED, help="where this loader keeps its own cut-down copies (default ballot_cache/nc)")
    ap.add_argument("--refresh", action="store_true", help="fetch the candidate listing and the results site again")
    a = ap.parse_args()
    load(a.db, cache=a.cache, refresh=a.refresh)
