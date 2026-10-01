"""
ballot/state_local_vt.py - Vermont's state races on the November 3, 2026 ballot: the six statewide offices (Governor,
Lieutenant Governor, State Treasurer, Secretary of State, Auditor of Accounts and Attorney General, each elected on its
own for two years) and every seat of the General Assembly (all 30 senators from 16 senate districts and all 150
representatives from 109 house districts, all with two-year terms, so the whole Legislature is on every November
ballot), with each party's August 11 primary field and its official votes. From the same list it also loads the local
offices on that ballot: the five county offices of each of the 14 counties and the justices of the peace of every town
and city (see "The local level" below).

Sources, all the Secretary of State's (Elections Division), the same files the federal loader reads (ballot/lists/vt.py):
  - "2026 General Election Candidate Listing/Financial Disclosure" (candidates/2026_general_election_qualified_candidates
    .xlsx, the Candidates page): one row per qualified candidate for every office on the ballot. Columns are taken by
    name, and only Contest, District Name, Name On Ballot, Party and Vote for Count are ever read. Districts are written
    in the Secretary's codes (ADD 1, CHI SE 1, WDR ORA 1); each is turned into the Legislature's own district name
    (Addison, Chittenden Southeast, Windsor-Orange-1) through the county abbreviations below, and must name exactly one
    district of the Open States roster, with the same number of seats. The list gives no ballot positions; Vermont
    prints each office's candidates in alphabetical order by surname (17 V.S.A. 2472(b)(2)), which is the list's own
    order: the loader checks it and stores it as the ballot order.
  - "2026 Primary Election Candidate Listing/Financial Disclosure" (2026_statewide_primary_qualified_candidates.xlsx):
    who was printed on each party's primary ballot (DEMOCRATIC, PROGRESSIVE and REPUBLICAN sheets, the same five
    columns) and the REGISTERED WRITE-IN sheet (office, the two district columns and the three name columns only).
  - The Secretary's official results for the August 11 primary, "2026 August Primary Election Results" on
    electionresults.vermont.gov (marked official), read from the files that site's own page fetches from
    static.electionresults.vermont.gov: the election list, the election's index, and its statewide, senate and house
    files. Every town's candidates, write-ins, blank votes and spoiled ballots add up to its total, and the towns add up
    to the district-wide (or statewide) row, which is the one kept. The results carry write-in names as the towns
    reported them; a write-in name is kept only when it won the nomination (the results then list it among the
    candidates) or fits a registered write-in candidate for that office and district and was recorded in one party's
    primary only (the registration names no party). Every other write-in name is added into one figure at once and is
    never cached, printed or stored.
  - Controls: the "2026 August Primary Winner Listing" (xlsx: Winner, Name on Ballot, Party, Office Name, District,
    Votes and Percent(%) only) must give every candidate the same votes and winner mark as the results, and the
    canvassing committee's report that opens the "2026 August Primary Official Canvass - Town by Town" (PDF, results
    only, kept by the federal loader) must give the statewide offices the same figures.
Holders come from the Open States roster in state_vt.sqlite (legislators with is_current = 1 by chamber and district;
the officials table for Governor, Lieutenant Governor, Secretary of State and Attorney General). The roster does not
carry the Treasurer or the Auditor, and the list names no incumbents, so those two races carry no holder.
Which counties each district reaches comes from the results' own town table, named by the Census Bureau's county file.

Privacy: the candidate workbooks also carry town of residence, mailing address, city, state, ZIP, phones, e-mail, website
and financial disclosure, and the winner listing carries addresses and a phone. Workbooks are read in memory and never
saved; the header row is found by its first cell, columns are taken by name from it, and only the columns named above
are read. What is cached (ballot_cache/vt/vt_2026_sl_*.json) is those columns of the state-office rows, the results'
kept figures and each file's SHA-256. Nothing is printed while loading but counts, race ids, and the names of candidates
(a match to a sitting member, or a check that needs reading); never a write-in name that is not shown.

A primary is a field when more candidates were on the party's primary than it nominates (two or more for one seat).
A field's total is its candidates' votes plus every write-in vote (blank votes and spoiled ballots left out), as on the
federal page; the Secretary's winner listing prints percentages of all votes counted, blanks included, so the two differ.

The local level (county offices and justices of the peace), from the same November list
---------------------------------------------------------------------------------------
Vermont's November ballot carries two kinds of local office, both with parties (Vermont Constitution, chapter II,
sections 43 and 50 to 52): in each of the 14 counties two Assistant Judges, a Probate Judge, a State's Attorney and a
Sheriff (four years) and a High Bailiff (two years); and in each of the 247 towns and cities its Justices of the Peace
(two years; from three to fifteen seats, one race per town with "Voters choose N."). Selectboards, town clerks, city
councils, mayors, village trustees and school boards are chosen at annual meetings in March or spring (17 V.S.A. 2640,
2646; 16 V.S.A. 423) and are not on this ballot; sl_notes says so, and sl_gaps names what cannot be seen from here.
  - The candidates come from the same workbook the state rows do. Its county and town rows are cut down in memory to
    six cells found by their headings (Contest, District Name, Name On Ballot, Party, Vote for Count, Term Length(Years))
    and only that cut-down copy is kept, as JSON, in ballot_cache/vt/local/, with the SHA-256 of the workbook as it came.
    It is cut from the very workbook the state rows were (same SHA-256): if the list has changed since the state rows'
    copy was made, both copies are made again from one download.
  - The contests come from the Secretary's election results site, which already lists the November 3 general election
    (no votes yet): its election list, the election's index (the town table: each town's county) and its county and town
    files, read as the page's own script reads them. They carry no contact details; only each contest's office, county
    or town, number to elect and the names and parties under it are kept. This second route is the control (every
    contest, name, party and number to elect must agree with the list; a difference is reported and filed in sl_gaps,
    never patched) and the reason a town with no candidate still has its race (kept, with a note). Ballot questions in
    the town file are counted and never read. A town election a clerk has listed for the same day (Danby, with nothing
    posted on 2026-09-30) is named in sl_gaps.
  - Places: a county office is filed under the county's five-digit code; a town or city under VT-M-<code>, the Census
    Bureau's county subdivision code from its 2024 cartographic boundary file (attribute table only), matched within
    the town's county by name (SAINT for St., CITY or TOWN where two places share a name) and only when exactly one
    fits. Vermont towns are the township tier (level township); the ten cities are level city.
  - Names are shown in ordinary capitals as on the state rows. No ballot order is stored: the list states none, and
    although the ballot is printed alphabetically by surname (17 V.S.A. 2472(b)(2)) the Secretary's two publications
    order two candidates of one surname differently in places. The ten justice candidates whose party cell reads
    UNKNOWN are shown as "Party not given". A local candidate is never matched to the roster: no member link, no
    incumbent mark. Nothing is printed while loading but counts and race ids; a stop names the file, the row's number
    and the check that failed, never the row.

    python -m ballot.state_local_vt <path to a test database> [cache folder] [local cache folder]
"""

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
from collections import Counter, defaultdict

from urllib.error import HTTPError, URLError

import openpyxl

from ballot.check_local import EXTRA_SCHEMA, contact_like
from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.match import fits
from ballot.pdftext import PDF, page_runs
from states import net
from states.places import place

STATE, FIPS = "VT", "50"
GENERAL, PRIMARY = "2026-11-03", "2026-08-11"
CANDIDATES_PAGE = "https://sos.vermont.gov/elections/election-info-resources/candidates/"
RESULTS_PAGE = "https://sos.vermont.gov/elections/election-info-resources/elections-results-data/"
FILES = "https://outside.vermont.gov/dept/sos/Elections_Division/election_info_resources/"
GENERAL_XLSX = FILES + "candidates/2026_general_election_qualified_candidates.xlsx"
PRIMARY_XLSX = FILES + "candidates/2026_statewide_primary_qualified_candidates.xlsx"
WINNERS_XLSX = FILES + "elections_results_data/2026-august-primary-winner-listing.xlsx"
CANVASS_PDF = FILES + "elections_results_data/2026-august-primary-official-canvass-town-by-town.pdf"
ENR_SITE = "https://electionresults.vermont.gov/"
ENR_STATIC = "https://static.electionresults.vermont.gov/"
ENR_LIST = ENR_STATIC + "elections/elections.json"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
ROSTER = os.path.join(HERE, "state_vt.sqlite")

SRC_GEN, SRC_PRI, SRC_ENR = "vt-sos-2026-state-general-list", "vt-sos-2026-state-primary-list", "vt-sos-2026-state-primary-results"
SRC_WIN, SRC_CANVASS = "vt-sos-2026-state-primary-winners", "vt-sos-2026-state-primary-canvass"
SRC_ROSTER, SRC_COUNTY = "vt-openstates-roster", "vt-census-2024-county-codes"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0,
  partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT,
  party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL,
  outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT,
  fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

# The Secretary's contest names: (race suffix, office_kind, office as shown, roster office).
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer", None),
    "SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "AUDITOR OF ACCOUNTS": ("AUD", "state_auditor", "Auditor of Accounts", None),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
}
SENATE, HOUSE = "STATE SENATOR", "STATE REPRESENTATIVE"
LEGISLATURE = {SENATE: ("SS", "state_senate", "State Senator", "Senate"), HOUSE: ("SH", "state_house", "State Representative", "House")}
FEDERAL = ("REPRESENTATIVE TO CONGRESS",)
NOT_LOADED = ("PROBATE JUDGE", "ASSISTANT JUDGE", "STATE'S ATTORNEY", "SHERIFF", "HIGH BAILIFF", "JUSTICE OF THE PEACE")
WRITE_OFFICE = {"GOVERNOR": "GOVERNOR", "LIEUTENANT GOVERNOR": "LIEUTENANT GOVERNOR", "STATE TREASURER": "STATE TREASURER",
                "SECRETARY OF STATE": "SECRETARY OF STATE", "AUDITOR OF ACCOUNTS": "AUDITOR OF ACCOUNTS", "ATTORNEY GENERAL": "ATTORNEY GENERAL",
                "STATE SENATE": SENATE, "STATE SENATOR": SENATE, "STATE REPRESENTATIVE": HOUSE}

KEEP = ("Contest", "District Name", "Name On Ballot", "Party", "Vote for Count")
WRITE_KEEP = ("OFFICE", "SENATE DISTRICT", "REPRESENTATIVE (HOUSE) DISTRICT", "FIRST NAME", "MIDDLE NAME", "LAST NAME")
WIN_KEEP = ("Winner", "Name on Ballot", "Party", "Office Name", "District", "Votes", "Percent(%)")
PARTY_SHEETS = ("DEMOCRATIC", "PROGRESSIVE", "REPUBLICAN")
CODE = {"DEMOCRATIC": "DEM", "REPUBLICAN": "REP", "PROGRESSIVE": "PRO"}          # primary-DEM, primary-REP, primary-PRO, as the federal loader
SHORT = {"DEM": "Democratic", "REP": "Republican", "PROG": "Progressive"}          # the list's short forms in joint nominations
PARTY_CODE = {"Democratic": "DEM", "Republican": "REP", "Progressive": "PRO"}      # a party as written out -> its primary's code
COUNT = {"ONE": 1, "TWO": 2, "THREE": 3}

# The Secretary's county abbreviations in district codes, and the words after a senate district's county.
COUNTY_ABBR = {"ADD": "Addison", "BEN": "Bennington", "CAL": "Caledonia", "CHI": "Chittenden", "ESX": "Essex", "FRA": "Franklin",
               "GI": "Grand Isle", "LAM": "Lamoille", "ORA": "Orange", "ORL": "Orleans", "RUT": "Rutland", "WAS": "Washington",
               "WDH": "Windham", "WDR": "Windsor"}
SENATE_PART = {"CT": "Central", "N": "North", "SE": "Southeast"}
LABEL = {"WRITE-IN": "Write-In", "OVERVOTES": "Overvotes", "BLANK VOTES": "Blank votes", "TOTAL VOTES COUNTED": "Total"}
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")

# ---- the local level: county offices and justices of the peace (see the docstring)
SRC_L_LIST, SRC_L_ELECTIONS = "vt-sos-2026-local-general-list", "vt-sos-2026-local-results-election-list"
SRC_L_INDEX, SRC_L_COUNTY, SRC_L_TOWN = "vt-sos-2026-local-november-index", "vt-sos-2026-local-november-county-contests", "vt-sos-2026-local-november-town-contests"
SRC_L_COUSUB, SRC_L_OTHER = "vt-census-2024-county-subdivisions", "vt-sos-2026-local-town-election-"
LOCAL_LAYOUT = 1                                   # of the two cut-down copies; a copy of another layout is made again
LOCAL_MAX_AGE = 2                                  # days the November contests are used again (the list's own copy follows the state rows')
LOCAL_LIST_FILE, NOV_FILE = "vt_2026_local_general_list.json", "vt_2026_local_november_contests.json"
LOCAL_SHEET, LOCAL_FIRST = "Candidate Listing", "Contest"
LOCAL_KEEP = ("Contest", "District Name", "Name On Ballot", "Party", "Vote for Count", "Term Length(Years)")
LIST_NAME = "2026_general_election_qualified_candidates.xlsx"
COUSUB_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_50_cousub_500k.zip"
COUSUB_FILE = "cb_2024_50_cousub_500k.zip"
CONSTITUTION = "https://legislature.vermont.gov/statutes/constitution-of-the-state-of-vermont/"
PAUSE = 1.2                                        # seconds between two requests to one host
JP, JP_KIND, JP_OFFICE = "JUSTICE OF THE PEACE", "justice_of_the_peace", "Justice of the Peace"
# the list's contest -> (office_kind, the office as a ballot prints it, the term the Constitution or the list gives it), in ballot order
COUNTY_OFFICES = {"PROBATE JUDGE": ("probate_judge", "Probate Judge", "4"), "ASSISTANT JUDGE": ("assistant_judge", "Assistant Judge", "4"),
                  "STATE'S ATTORNEY": ("county_attorney", "State's Attorney", "4"), "SHERIFF": ("sheriff", "Sheriff", "4"),
                  "HIGH BAILIFF": ("high_bailiff", "High Bailiff", "2")}
JP_TERM = "2"
SEATS = {w: i for i, w in enumerate("ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN".split(), start=1)}
PLACE_CELL = re.compile(r"[A-Z][A-Z .'&-]{0,40}")                    # a county's or a town's name as the Secretary writes it
PARTY_CELL = re.compile(r"[A-Z][A-Z .'&/-]{0,60}")
OFFICE_CELL = re.compile(r"[A-Z][A-Z0-9 .'&/-]{0,60}")
GUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
NO_PARTY, NO_PARTY_WORDS = "UNKNOWN", "Party not given"
NO_PARTY_NOTE = "The Secretary of State's list prints \"UNKNOWN\" where this candidate's party would be."
EMPTY = ("No candidate is listed: the Secretary of State's candidate list has no name for this office here, and the Secretary's results site "
         "shows the contest with none.")
# the page builder's own last check is a little wider than the trial check's (it also stops at Court and Place)
BUILDER_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                            r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)

CAPS = "Vermont's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_WON = "Write-in candidate: the name was not printed on this party's primary ballot; the write-in votes won the nomination."
WRITE_WON_REG = ("Registered write-in candidate: the name was not printed on this party's primary ballot; the write-in votes won the "
                 "nomination.")
WRITE_REG = "Registered write-in candidate: the name was not printed on the primary ballot."
WRITE_NOV = "Registered write-in candidate: the name is not printed on the November ballot."


def squash(value):
    return re.sub(r"\s+", " ", str(value if value is not None else "").replace("\xa0", " ")).strip()


def dkey(text):
    """A district's spelling for comparison only: letters and digits, lower case, nothing else."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def today():
    return dt.date.today().isoformat()


# ------------------------------------------------------------------------------------------------ the workbooks

_BOOKS = {}                                                                    # a workbook is asked for once in a run


def book(url):
    """A workbook of the Secretary's, read in memory (it carries contact columns, so it is never saved), with its
    fingerprint. Within one run a workbook is downloaded once, so the state rows and the local rows are cut from the
    same bytes; load() forgets it when it ends."""
    if url not in _BOOKS:
        raw = net.get(url)
        if raw[:2] != b"PK":
            raise SystemExit(f"Vermont: {url} is not a workbook")
        _BOOKS[url] = (openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True), sha(raw))
    return _BOOKS[url]


def sheet_rows(ws, keep, first):
    """The rows under a sheet's header row (the first row whose first cell is `first`): the kept columns only, by name.
    No other cell of a row is ever read."""
    rows = ws.iter_rows(values_only=True)
    for r in rows:
        if r and squash(r[0]) == first:
            head = [squash(h) for h in r]
            break
    else:
        raise SystemExit(f"Vermont: no header row beginning {first!r} on the sheet {ws.title!r}")
    missing = [k for k in keep if k not in head]
    if missing:
        raise SystemExit(f"Vermont: the sheet {ws.title!r} no longer has the columns {missing}")
    idx = {k: head.index(k) for k in keep}
    out = []
    for r in rows:
        row = {k: squash(r[i]) if i < len(r) else "" for k, i in idx.items()}
        if any(row.values()):
            out.append(row)
    return out


def updated(wb, sheet):
    """The "Last Updated: M/D/YYYY" line of a workbook's criteria sheet as YYYY-MM-DD; nothing else on it is kept."""
    if sheet not in wb.sheetnames:
        return ""
    for r in wb[sheet].iter_rows(values_only=True):
        for c in r:
            m = re.fullmatch(r"Last Updated:\s*(\d{1,2})/(\d{1,2})/(\d{4})", squash(c))
            if m:
                return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def filled(rows):
    """A contest is named once, on its first row; the rows below it carry it on."""
    contest = ""
    for r in rows:
        contest = r["Contest"] = r["Contest"] or contest
    return rows


def known(contest, where):
    c = contest.upper()
    if c in STATEWIDE or c in LEGISLATURE or c in NOT_LOADED or c.replace("U.S. ", "") in FEDERAL:
        return c in STATEWIDE or c in LEGISLATURE
    raise SystemExit(f"Vermont: an office this loader does not know is on the {where}: {contest!r}")


def write_in_rows(wb, where):
    """State-office rows of the registered write-in sheets: office, the two district columns, the three name columns."""
    out = []
    for name in wb.sheetnames:
        if "WRITE-IN" in name.upper():
            for r in sheet_rows(wb[name], WRITE_KEEP, "OFFICE"):
                office = r["OFFICE"].upper().replace("U.S. ", "")
                if office in FEDERAL or office in NOT_LOADED:
                    continue
                if office not in WRITE_OFFICE:
                    raise SystemExit(f"Vermont: a registered write-in for an office this loader does not know on the {where}: {office!r}")
                out.append(r)
    return out


def kept(path, max_age_days, fetch):
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def general_list():
    wb, digest = book(GENERAL_XLSX)
    sheet = "Candidate Listing"
    if sheet not in wb.sheetnames:
        raise SystemExit(f"Vermont: the general list has no {sheet!r} sheet ({wb.sheetnames})")
    for s in wb.sheetnames:
        if s not in (sheet, "Selection Criteria") and "WRITE-IN" not in s.upper():
            raise SystemExit(f"Vermont: the general list has a sheet that is not read ({s!r})")
    rows = filled(sheet_rows(wb[sheet], KEEP, "Contest"))
    others = Counter(r["Contest"] for r in rows if not known(r["Contest"], "general list"))
    return {"url": GENERAL_XLSX, "sha256": digest, "fetched": today(), "updated": updated(wb, "Selection Criteria"),
            "rows_read": len(rows), "state": [r for r in rows if known(r["Contest"], "general list")], "others": dict(others),
            "write_in": write_in_rows(wb, "general list")}


def primary_list():
    wb, digest = book(PRIMARY_XLSX)
    parties = {}
    for sheet in wb.sheetnames:
        if sheet.upper() in PARTY_SHEETS:
            rows = filled(sheet_rows(wb[sheet], KEEP, "Contest"))
            parties[sheet.upper()] = [r for r in rows if known(r["Contest"], f"primary list ({sheet})")]
        elif "WRITE-IN" not in sheet.upper() and sheet != "Last Updated":
            raise SystemExit(f"Vermont: the primary list has a sheet that is not read ({sheet!r})")
    if set(parties) != set(PARTY_SHEETS):
        raise SystemExit(f"Vermont: the primary list's party sheets changed ({sorted(parties)})")
    return {"url": PRIMARY_XLSX, "sha256": digest, "fetched": today(), "updated": updated(wb, "Last Updated"), "parties": parties,
            "write_in": write_in_rows(wb, "primary list")}


def winner_listing():
    wb, digest = book(WINNERS_XLSX)
    rows = sheet_rows(wb["Winner Listing"], WIN_KEEP, "Winner")
    crit = {}
    if "Selection Criteria" in wb.sheetnames:
        for r in wb["Selection Criteria"].iter_rows(values_only=True):
            cells = [squash(c) for c in r if c is not None]
            if len(cells) == 2 and cells[0].endswith(":"):
                crit[cells[0].rstrip(":")] = cells[1]
    state = [r for r in rows if known(r["Office Name"], "winner listing")]
    return {"url": WINNERS_XLSX, "sha256": digest, "fetched": today(), "criteria": crit, "rows": state}


# ---------------------------------------------------------------------------------------- the official results

def enr_results(registered):
    """The August 11 primary from the Secretary's results site: for every party, office and district, the district-wide
    (statewide) figures, after every town has been added up and checked. `registered` is [(office, district key or '',
    (given, family))] for the registered write-in candidates: only their write-in names, and write-ins that won, are
    kept; every other write-in name is added into `other_write_in` here and goes no further."""
    elections = json.loads(net.get(ENR_LIST))
    mine = [e for e in elections if str(e.get("electionDate", "")).startswith(PRIMARY) and e.get("isStateWideElection")
            and e.get("electionTypeCode") == "P"]
    if len(mine) != 1:
        raise SystemExit(f"Vermont: the results site lists {len(mine)} statewide primaries on {PRIMARY}")
    guid = mine[0]["electionGuid"]
    index_raw = net.get(f"{ENR_STATIC}elections/{guid}.json")
    index = json.loads(index_raw)
    det = index["electionDetails"]
    if not det.get("isOfficial") or det.get("electionName") != "AUGUST PRIMARY":
        raise SystemExit(f"Vermont: the results site's {PRIMARY} primary is not marked official ({det.get('electionName')!r})")
    files = {"index": {"url": f"{ENR_STATIC}elections/{guid}.json", "sha256": sha(index_raw)}}
    contests, problems, won_in = [], [], defaultdict(set)
    for part in ("stateWide", "senate", "house"):
        url = ENR_STATIC + index[part]["path"].replace("\\", "/")
        raw = net.get(url)
        files[part] = {"url": url, "sha256": sha(raw)}
        for p in json.loads(raw)["d"]:
            pn = p["pn"]
            if pn not in PARTY_SHEETS:
                raise SystemExit(f"Vermont: the results carry a party that is not read ({pn!r})")
            for o in p["o"]:
                on, dc = squash(o["on"]), squash(o.get("dc") or "")
                if on not in STATEWIDE and on not in LEGISLATURE:
                    raise SystemExit(f"Vermont: the {part} results carry an office that is not read ({on!r})")
                where = f"{pn} {on} {dc}".strip()
                wide = [c for c in o["cs"] if c["tid"] == 0]
                towns = [c for c in o["cs"] if c["tid"] != 0]
                if len(wide) != 1 or not towns:
                    raise SystemExit(f"Vermont: {where}: {len(wide)} district-wide rows and {len(towns)} town rows")
                w = wide[0]

                def total(c):
                    return sum(x["vc"] for x in c["rc"]) + sum(x["vc"] for x in c["wc"]) + c["bv"] + c["sv"]
                for c in o["cs"]:
                    if total(c) != c["sc"]:
                        problems.append(f"{where}: a row's candidates, write-ins, blanks and spoiled ballots do not add up to its total")
                for k in ("sc", "bv", "sv"):
                    if sum(c[k] for c in towns) != w[k]:
                        problems.append(f"{where}: the towns do not add up to the district-wide {k}")
                summed, wideset = Counter(), Counter()
                for c in towns:
                    for x in c["rc"] + c["wc"]:
                        summed[(x["cid"], squash(x["cn"]))] += x["vc"]
                for x in w["rc"] + w["wc"]:
                    wideset[(x["cid"], squash(x["cn"]))] += x["vc"]
                if +summed != +wideset:
                    problems.append(f"{where}: the towns' candidate and write-in votes do not add up to the district-wide row")
                printed = [[squash(x["cn"]), x["vc"], bool(x["isWinner"]), bool(x["isWriteIn"])] for x in w["rc"]]
                reg = [(g, f) for off, dk, (g, f) in registered if off == on and (on in STATEWIDE or dk == dkey(dc))]
                for x in w["rc"]:                                            # a registered write-in who won this party's nomination
                    hit = [i for i, (g, f) in enumerate(reg) if fits(name_parts(squash(x["cn"])), (g, f)) and name_parts(squash(x["cn"]))[1] == f]
                    if x["isWriteIn"] and len(hit) == 1:
                        won_in[(on, dc, hit[0])].add(pn)
                writes, other = defaultdict(lambda: [0, 0, False]), 0
                for x in w["wc"]:
                    name = squash(x["cn"])
                    hit = [i for i, (g, f) in enumerate(reg) if x["cid"] and fits(name_parts(name), (g, f)) and name_parts(name)[1] == f]
                    if x["isWinner"] or len(hit) == 1:
                        k = hit[0] if len(hit) == 1 else name
                        writes[k][0] += x["vc"]
                        writes[k][1] += 1
                        writes[k][2] = writes[k][2] or bool(x["isWinner"])
                    else:
                        other += x["vc"]
                kept_w = [[i if isinstance(i, int) else None, (squash(i) if isinstance(i, str) else None), v, n, won]
                          for i, (v, n, won) in writes.items()]
                contests.append({"party": pn, "office": on, "dc": dc, "vf": o["vf"], "towns": len(towns), "total": w["sc"], "blank": w["bv"],
                                 "spoiled": w["sv"], "printed": printed, "write_ins": kept_w, "other_write_in": other,
                                 "write_in_all": sum(x["vc"] for x in w["wc"])})
    if problems:
        raise SystemExit("Vermont: the official results do not reconcile:\n  " + "\n  ".join(problems[:20]))
    # The registration names no party: a registered write-in recorded in two parties' primaries is named in neither.
    parties_of = defaultdict(set, {k: set(v) for k, v in won_in.items()})
    for c in contests:
        for w in c["write_ins"]:
            if w[0] is not None:
                parties_of[(c["office"], c["dc"], w[0])].add(c["party"])
    two = {k for k, v in parties_of.items() if len(v) > 1}
    for c in contests:
        keep = []
        for w in c["write_ins"]:
            if w[0] is not None and (c["office"], c["dc"], w[0]) in two and not w[4]:
                c["other_write_in"] += w[2]
            else:
                keep.append(w)
        c["write_ins"] = keep
    counties = defaultdict(set)
    for t in index["townDistricts"]:
        counties[("house", squash(t["repDistrictCode"]))].add(squash(t["countyName"]))
        counties[("senate", squash(t["senDistrictCode"]))].add(squash(t["countyName"]))
    return {"guid": guid, "election": det["electionDateWithName"], "official": det["isOfficial"], "updated": index.get("lastUpdatedDate", ""),
            "towns_reporting": index.get("townsReporting", ""), "fetched": today(), "files": files, "contests": contests,
            "registered_in_two_parties": len(two),
            "counties": {f"{k[0]}|{k[1]}": sorted(v) for k, v in counties.items()}}


def committee_report(path):
    """The canvassing committee's figures for the statewide offices: {office: {party: {label: votes}}} and the starred
    winners {(office, party, label)}. Only the report's pages are read (they come before the town tabulation)."""
    raw = open(path, "rb").read()
    if raw[:5] != b"%PDF-":
        raise SystemExit("Vermont: the canvass is not a PDF")
    pdf = PDF(raw)
    out, stars, office, party, attested = {}, set(), None, None, False
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        if any(re.fullmatch(r"Page \d+ of \d+", r[3].strip()) for r in runs):
            break                                                            # the town-by-town tabulation begins
        text = " ".join(r[3] for r in runs)
        attested = attested or ("17 V.S.A. 2368-2371" in text and "08/11/2026 - AUGUST PRIMARY" in text)
        # The report is printed turned on its side: each column is one printed line, x fixed, read along y. A long name runs
        # on in a second piece on the same line (H. / BROOKE PAIGE), and the winner's star follows the name's end.
        events = [(r[0], "office", r[3].strip()) for r in runs if 115 <= r[1] <= 125 and r[3].strip().startswith("FOR ")]
        for r in runs:
            if 165 <= r[1] <= 175:
                more = [s for s in runs if abs(s[0] - r[0]) <= 1 and 175 < s[1] < 410 and s[3].strip() not in ("*", "")]
                events.append((r[0], "column", " ".join(s[3].strip() for s in sorted([r] + more, key=lambda s: s[1]))))
        for x, kind, label in sorted(events):
            if kind == "office":
                office, party = label[4:], None
                continue
            if office not in STATEWIDE:
                continue
            if label.endswith(" PARTY"):
                party = label[:-6]
                out.setdefault(office, {}).setdefault(party, {})
                continue
            vals = [NUMBER.fullmatch(r[3].strip()) for r in runs if 415 <= r[1] <= 425 and abs(r[0] - x) <= 3]
            vals = [int(m.group(0).replace(",", "")) for m in vals if m]
            if party is None or len(vals) != 1:
                raise SystemExit(f"Vermont: canvass page {n}: the committee's column {label!r} is not read")
            out[office][party][LABEL.get(label, label)] = vals[0]
            if any(r[3].strip() == "*" and 175 < r[1] < 410 and abs(r[0] - x) <= 3 for r in runs):
                stars.add((office, party, LABEL.get(label, label)))
    if not attested:
        raise SystemExit("Vermont: the canvass does not open with the canvassing committee's report of the August 11 primary")
    return out, stars


# ------------------------------------------------------------------------------------------------- districts

def district_name(code, chamber):
    """The Secretary's district code as the Legislature names the district: ADD 1 -> Addison (Senate) or Addison-1
    (House); CHI SE 1 -> Chittenden Southeast; WDR ORA 1 -> Windsor-Orange-1; GI CHI -> Grand Isle-Chittenden."""
    words = code.split()
    if chamber == "Senate":
        if not words or words[0] not in COUNTY_ABBR or words[-1] != "1" or len(words) > 3:
            raise SystemExit(f"Vermont: a senate district code that is not read: {code!r}")
        mid = words[1:-1]
        if mid and mid[0] not in SENATE_PART:
            raise SystemExit(f"Vermont: a senate district code that is not read: {code!r}")
        return " ".join([COUNTY_ABBR[words[0]]] + [SENATE_PART[m] for m in mid])
    parts = []
    for w in words:
        if w in COUNTY_ABBR:
            parts.append(COUNTY_ABBR[w])
        elif w.isdigit():
            parts.append(w)
        else:
            raise SystemExit(f"Vermont: a house district code that is not read: {code!r}")
    return "-".join(parts)


def race_id(contest, district=None):
    if contest in STATEWIDE:
        return f"2026-{STATE}-{STATEWIDE[contest][0]}"
    return f"2026-{STATE}-{LEGISLATURE[contest][0]}{district.upper().replace(' ', '-')}"


# ------------------------------------------------------------------------------------------------- the roster

def roster(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district FROM legislators WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def person_forms(p):
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return [f for f in forms if f[1]]


def person_fits(name, p):
    cand = name_parts(name)
    return any(fits(cand, f) for f in person_forms(p))


def as_person(name):
    given, family = name_parts(name)
    return {"first": " ".join(given), "last": family, "other": ""}


def parties_meet(label, roster_party):
    a = {w for w in re.split(r"[/ ]+", (label or "").lower()) if w}
    b = {w for w in re.split(r"[/ ]+", (roster_party or "").lower()) if w}
    return bool(a & b)


def surname_order(names):
    """True when the names can be read as alphabetical by surname: each name's surname is taken as its last word or its
    last words (Ram Hinsdale, St Marthe, Allen-Pennebaker), and some choice of them must never go backwards."""
    prev = ""
    for n in names:
        words = [w for w in re.sub(r'"[^"]*"', " ", n).upper().replace(".", " ").split() if w not in ("JR", "SR", "II", "III", "IV")]
        options = sorted(" ".join(words[i:]) for i in range(1, len(words))) or [" ".join(words)]
        ok = [o for o in options if o >= prev]
        if not ok:
            return False
        prev = ok[0]
    return True


def ordinary(caps):
    """A name printed in capitals in ordinary capitals: each word and each part of a hyphened word begins with a capital
    (Van Oort, Bos-Lun), McLaren, O'Brien, initials stay capitals (A.M.), Jr. and Sr. as words, II and III kept."""
    out = []
    for i, w in enumerate(squash(caps).split()):
        if re.fullmatch(r"(JR|SR)\.?", w):
            out.append(w.title())
        elif i and re.fullmatch(r"[IVX]+", w):
            out.append(w)
        elif re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?", w):
            out.append(w)
        else:
            parts = []
            for p in w.split("-"):
                p2 = p[:1] + p[1:].lower()
                p2 = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p2)
                p2 = re.sub(r"^([\"'(]?)([a-z])", lambda m: m.group(1) + m.group(2).upper(), p2)
                p2 = re.sub(r"^([\"'(]?)O'([a-z])", lambda m: m.group(1) + "O'" + m.group(2).upper(), p2)
                parts.append(p2)
            out.append("-".join(parts))
    return " ".join(out)


def party_words(label):
    """DEMOCRATIC -> Democratic; REP/DEM -> Republican/Democratic; WOMEN'S LIBERATION VEGI-ARYAN -> Women's Liberation Vegi-Aryan."""
    out = []
    for p in (label or "").split("/"):
        p = p.strip()
        if p in SHORT:
            out.append(SHORT[p])
            continue
        words = []
        for i, w in enumerate(p.split()):
            if i and w in ("AND", "OF", "THE", "FOR"):
                words.append(w.lower())
            else:
                words.append("-".join(x[:1] + x[1:].lower() for x in w.split("-")))
        out.append(" ".join(words))
    return "/".join(out)


def census_counties(path):
    import shapefile                                                        # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {r["NAME"].upper(): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def file_facts(path):
    raw = open(path, "rb").read()
    return sha(raw), dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ the local level

def reads_like_contact(text):
    """The trial check's test and the page builder's slightly wider one, on one piece of text."""
    return bool(text) and (contact_like(text, True) or bool(BUILDER_STREET.search(str(text))))


def local_name(caps):
    """A name printed in capitals in ordinary capitals, by ordinary()'s rules, with the marks around a nickname set
    aside first, so that initials inside them stay capitals ("J.J."), and a capital after D' or L' as after O'."""
    out = []
    for i, w in enumerate(squash(caps).split()):
        lead, core, trail = re.fullmatch(r"([\"'(]*)(.*?)([\"'),]*)", w).groups()
        if i and re.fullmatch(r"[IVX]+", core):
            shown = core
        else:
            shown = ordinary(core) if core else ""
            shown = "-".join(re.sub(r"^([A-Z])'([a-z])", lambda m: m.group(1) + "'" + m.group(2).upper(), p) for p in shown.split("-"))
        out.append(lead + shown + trail)
    return " ".join(out)


def local_cut(wb, digest):
    """The county and town rows of the general workbook, cut down in memory to six cells found by their headings
    (LOCAL_KEEP), each with the number of the sheet row it came from. No other cell of any row is read, and the state
    and federal rows are only counted. A name that reads like contact details is never kept (it is blanked and counted);
    any other cell that is not what its column holds stops the loader, which names the row, never the cell."""
    if LOCAL_SHEET not in wb.sheetnames:
        raise SystemExit(f"Vermont: {LIST_NAME} has no {LOCAL_SHEET!r} sheet")
    idx, contest, rows, other, blanked, read = None, "", [], Counter(), 0, 0
    for n, r in enumerate(wb[LOCAL_SHEET].iter_rows(values_only=True), start=1):
        if idx is None:
            if r and squash(r[0]) == LOCAL_FIRST:
                head = [squash(h) for h in r]
                missing = [k for k in LOCAL_KEEP if k not in head]
                if missing:
                    raise SystemExit(f"Vermont: {LIST_NAME}, sheet row {n}: the heading row no longer has the columns {missing}")
                idx = {k: head.index(k) for k in LOCAL_KEEP}
            continue
        cell = {k: squash(r[i]) if i < len(r) else "" for k, i in idx.items()}
        if not any(cell.values()):
            continue
        read += 1
        contest = cell["Contest"] or contest                                  # a contest is named on its first row
        c = contest.upper()
        where = f"Vermont: {LIST_NAME}, sheet row {n}"
        if c not in COUNTY_OFFICES and c != JP:
            if c in STATEWIDE or c in LEGISLATURE:
                other["state"] += 1
            elif c.replace("U.S. ", "") in FEDERAL:
                other["federal"] += 1
            else:
                raise SystemExit(f"{where}: an office this loader does not know; stopping (the row is not shown)")
            continue
        district, name, party, seats, term = (cell[k] for k in LOCAL_KEEP[1:])
        if not PLACE_CELL.fullmatch(district) or reads_like_contact(district):
            raise SystemExit(f"{where}: the District Name cell is not a county's or a town's name; stopping (the row is not shown)")
        if not PARTY_CELL.fullmatch(party) or reads_like_contact(party):
            raise SystemExit(f"{where}: the Party cell is not a party's name; stopping (the row is not shown)")
        if seats not in SEATS and not (seats.isdigit() and 1 <= int(seats) <= 30):
            raise SystemExit(f"{where}: the Vote for Count cell is not a number this loader reads; stopping (the row is not shown)")
        if term and not re.fullmatch(r"\d{1,2}", term):
            raise SystemExit(f"{where}: the Term Length(Years) cell is not a number of years; stopping (the row is not shown)")
        if not name or len(name) > 80 or reads_like_contact(name):
            name, blanked = "", blanked + 1                                   # never kept, never shown; counted
        rows.append([n, c, district, name, party, SEATS.get(seats) or int(seats), term])
    if idx is None:
        raise SystemExit(f"Vermont: {LIST_NAME}: no heading row beginning {LOCAL_FIRST!r} on the sheet {LOCAL_SHEET!r}")
    write_ins = 0                # a registered write-in for a county or town office (17 V.S.A. 2472(b)(5) asks registration of state and federal ones only)
    for sheet in wb.sheetnames:
        if "WRITE-IN" in sheet.upper():
            for r in sheet_rows(wb[sheet], ("OFFICE",), "OFFICE"):
                write_ins += r["OFFICE"].upper() in COUNTY_OFFICES or r["OFFICE"].upper().startswith(JP)
    return {"layout": LOCAL_LAYOUT, "url": GENERAL_XLSX, "sha256": digest, "fetched": today(), "updated": updated(wb, "Selection Criteria"),
            "rows_read": read, "other": dict(other), "blanked": blanked, "write_ins": int(write_ins),
            "kept": "of each county or town row: the sheet row's number, contest, district name, name on ballot, party, number to elect, term in years; "
                    "no other cell of the workbook",
            "rows": rows}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)


def local_list(folder, state_sha):
    """The cut-down copy of the list's county and town rows: the one on disk when it was cut from the same workbook the
    state rows were (the same SHA-256, and no workbook read in this run), else cut now from the run's one download.
    Returns (the copy, True when it was cut in this run)."""
    path = os.path.join(folder, LOCAL_LIST_FILE)
    if GENERAL_XLSX not in _BOOKS and os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
        except ValueError:
            old = {}
        if old.get("layout") == LOCAL_LAYOUT and old.get("sha256") == state_sha:
            return old, False
    cut = local_cut(*book(GENERAL_XLSX))
    write_json(path, cut)
    return cut, True


def site_json(url):
    """One file of the results site, asked for as its own page asks: (what it holds, its address, fingerprint and size)."""
    raw = net.get(url)
    return json.loads(raw), {"url": url, "sha256": sha(raw), "bytes": len(raw)}


def site_path(index, part):
    """The address of one of an election's files, from the path its index gives (elections\\<id>-cty-<time>.json)."""
    path = str((index.get(part) or {}).get("path") or "")
    if not re.fullmatch(r"elections[\\/]" + GUID.pattern + r"-[a-z]+-\d{6,20}\.json", path):
        raise SystemExit(f"Vermont: the results site's index gives its {part} file a path that is not read; stopping")
    return ENR_STATIC + path.replace("\\", "/")


def site_names(rows, where):
    """[name, party] of each candidate row under a contest on the results site, with how many names were blanked
    because they read like contact details and how many rows were write-ins (counted, not kept)."""
    names, blanked, written = [], 0, 0
    for x in rows or []:
        if x.get("isWriteIn"):
            written += 1
            continue
        name, party = squash(x.get("cn")), squash(x.get("pn"))
        if party and (not PARTY_CELL.fullmatch(party) or reads_like_contact(party)):
            raise SystemExit(f"Vermont: {where}: a party cell that is not a party's name; stopping (the row is not shown)")
        if not name or len(name) > 80 or reads_like_contact(name):
            name, blanked = "", blanked + 1
        names.append([name, party])
    return names, blanked, written


def office_words(text):
    """An office's name from the results site, kept only when it is plainly office words."""
    t = squash(text).upper()
    return t if OFFICE_CELL.fullmatch(t) and not reads_like_contact(t) else ""


def november_fetch():
    """The November 3 general election as the Secretary's results site lists it before any vote is counted: the town
    table, and every county and town contest with its number to elect and the names and parties under it. Cut down
    as it is read; votes, ids and ballot questions' words are never kept."""
    elections, f_list = site_json(ENR_LIST)
    day = [e for e in elections if str(e.get("electionDate", "")).startswith(GENERAL)]
    mine = [e for e in day if e.get("isStateWideElection") and e.get("electionTypeCode") == "G"]
    if len(mine) != 1:
        raise SystemExit(f"Vermont: the results site lists {len(mine)} statewide general elections on {GENERAL}")
    guid = str(mine[0].get("electionGuid") or "")
    if not GUID.fullmatch(guid):
        raise SystemExit("Vermont: the results site's id for the general election is not read; stopping")
    time.sleep(PAUSE)
    index, f_index = site_json(f"{ENR_STATIC}elections/{guid}.json")
    det = index["electionDetails"]
    if not str(det.get("electionDate", "")).startswith(GENERAL) or not det.get("isGeneralElection"):
        raise SystemExit("Vermont: the results site's index is not the November 3 general election's; stopping")
    towns = {}
    for n, t in enumerate(index["townDistricts"], start=1):
        town, county = squash(t.get("townName")), squash(t.get("countyName"))
        if not PLACE_CELL.fullmatch(town) or not PLACE_CELL.fullmatch(county) or towns.setdefault(town, county) != county:
            raise SystemExit(f"Vermont: the results site's town table, entry {n}: a town or county name that is not read, or a town in two counties; stopping")
    if {squash(t.get("townName")) for t in index.get("towns") or []} != set(towns):
        raise SystemExit("Vermont: the results site's town list and its town table do not name the same towns; stopping")
    for part in ("county", "town"):
        if not (index.get(part) or {}).get("isEnable"):
            raise ValueError(f"the results site has not posted the {part} contests")
    files, blanked, written = {"elections": f_list, "index": f_index}, 0, 0

    time.sleep(PAUSE)
    data, files["county"] = site_json(site_path(index, "county"))
    if len(data["d"]) != 1:
        raise SystemExit("Vermont: the results site's county file is not laid out as one block; stopping")
    county = []
    for n, c in enumerate(data["d"][0]["co"], start=1):
        wide = [x for x in c.get("cs") or [] if x.get("tid") == 0]
        cname = squash(c.get("ctyn"))
        if len(wide) != 1 or not PLACE_CELL.fullmatch(cname):
            raise SystemExit(f"Vermont: the results site's county file, contest {n}: no county name, or not exactly one county-wide row; stopping")
        names, b, w = site_names(wide[0].get("rc"), f"the results site's county file, contest {n}")
        blanked, written = blanked + b, written + w
        county.append({"county": cname, "office": office_words(c.get("on")), "vote_for": int(c.get("vf") or 0), "candidates": names})

    time.sleep(PAUSE)
    data, files["town"] = site_json(site_path(index, "town"))
    if len(data["d"]) != 1:
        raise SystemExit("Vermont: the results site's town file is not laid out as one block; stopping")
    town, questions = [], Counter()
    for n, c in enumerate(data["d"][0]["o"], start=1):
        tname = squash(c.get("tn"))
        if tname not in towns:
            raise SystemExit(f"Vermont: the results site's town file, contest {n}: a town that is not in its town table; stopping")
        if c.get("otc") == "BQ" or c.get("bq"):
            questions[tname] += 1                                             # a ballot question: counted, its words never read
            continue
        rows = c.get("cs") or []
        if len(rows) != 1 or rows[0].get("tid") != c.get("tid"):
            raise SystemExit(f"Vermont: the results site's town file, contest {n}: not exactly one row for the town; stopping")
        names, b, w = site_names(rows[0].get("rc"), f"the results site's town file, contest {n}")
        blanked, written = blanked + b, written + w
        town.append({"town": tname, "office": office_words(c.get("on")), "district": bool(c.get("ld")), "vote_for": int(c.get("vf") or 0),
                     "candidates": names})

    others = []                                                               # any other election a clerk has listed for the same day
    for e in day:
        if e is mine[0]:
            continue
        g, tname = str(e.get("electionGuid") or ""), squash(e.get("town")).upper()
        info = {"statewide": bool(e.get("isStateWideElection")), "town": tname if PLACE_CELL.fullmatch(tname) else "", "county": "",
                "posted": False, "offices": 0, "questions": 0, "index": None}
        if GUID.fullmatch(g):
            time.sleep(PAUSE)
            index2, info["index"] = site_json(f"{ENR_STATIC}elections/{g}.json")
            where = {squash(t.get("townName")): squash(t.get("countyName")) for t in index2.get("townDistricts") or []}
            info["county"] = where.get(info["town"], "") if PLACE_CELL.fullmatch(where.get(info["town"], "")) else ""
            info["posted"] = any((index2.get(p) or {}).get("isEnable") for p in ("federal", "stateWide", "senate", "house", "county", "town"))
            path = str((index2.get("town") or {}).get("path") or "")
            if re.fullmatch(r"elections[\\/]" + GUID.pattern + r"-[a-z]+-\d{6,20}\.json", path):
                time.sleep(PAUSE)
                try:
                    data2, info["town_file"] = site_json(ENR_STATIC + path.replace("\\", "/"))
                    for block in (data2.get("d") or []) if isinstance(data2, dict) else []:
                        for c in block.get("o") or []:
                            info["questions" if (c.get("otc") == "BQ" or c.get("bq")) else "offices"] += 1
                except HTTPError:
                    pass                                                      # nothing posted under that path
        others.append(info)

    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", squash(index.get("lastUpdatedDate")))
    return {"layout": LOCAL_LAYOUT, "fetched": today(), "guid": guid, "election": squash(det.get("electionDateWithName")),
            "official": bool(det.get("isOfficial")), "updated": f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else "",
            "files": files, "towns": towns, "unorganized": len(index.get("unorganisedTowns") or []), "county": county, "town": town,
            "questions": dict(questions), "others": others, "blanked": blanked, "write_in_rows": written,
            "kept": "the town table (town and county names); of each county and town contest the office, the county or town, the number to "
                    "elect and the names and parties under it; how many ballot questions each town has; no vote, no id, no question's words"}


def november(folder, refresh=False, say=print):
    """The cut-down copy of the November contests: the one on disk while it is fresh (and the list was not cut again in
    this run), else read now. If the site cannot be read and an older copy is on disk, that copy is used, and said."""
    path, old = os.path.join(folder, NOV_FILE), None
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
        except ValueError:
            old = None
        if old and old.get("layout") != LOCAL_LAYOUT:
            old = None
    if old and not refresh and time.time() - os.path.getmtime(path) < LOCAL_MAX_AGE * 86400:
        return old
    try:
        cut = november_fetch()
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as err:
        if old:
            say(f"      Vermont: the results site could not be read ({type(err).__name__}); using the copy of {old['fetched']} on disk for the November contests")
            return old
        raise SystemExit(f"Vermont: the results site could not be read ({type(err).__name__}: {err}) and no copy is on disk, so the county and "
                         "town races cannot be filed; run again later")
    write_json(path, cut)
    return cut


def cousub_file(folder, say=print):
    """The Census Bureau's county subdivision file for Vermont: the kit's copy if it has one, else the local folder's,
    downloaded once."""
    kit = os.path.join(HERE, "states_cache", "census", COUSUB_FILE)
    if os.path.exists(kit):
        return kit
    path = os.path.join(folder, COUSUB_FILE)
    net.download(COUSUB_URL, path, 3650, say=say)
    return path


def census_cousubs(path):
    """Vermont's towns, cities, gores and grant from the attribute table of the Census Bureau's county subdivision file
    (no shapes are read): county code, five-digit code, name, name with its kind word, kind word."""
    import shapefile                                                        # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = [n for n in z.namelist() if n.lower().endswith(".dbf")]
    if len(dbf) != 1:
        raise SystemExit("Vermont: the Census county subdivision file does not hold exactly one attribute table")
    out = []
    for rec in shapefile.Reader(dbf=io.BytesIO(z.read(dbf[0]))).iterRecords():
        r = rec.as_dict()
        if str(r.get("STATEFP")) != FIPS:
            continue
        name, label = squash(r["NAME"]), squash(r["NAMELSAD"])
        out.append({"county": FIPS + str(r["COUNTYFP"]), "code": str(r["COUSUBFP"]), "name": name, "label": label,
                    "kind": label[len(name):].strip() if label.startswith(name) else ""})
    codes = [c["code"] for c in out]
    if not out or len(set(codes)) != len(codes) or any(not re.fullmatch(r"\d{5}", c) for c in codes):
        raise SystemExit("Vermont: the Census county subdivision file's codes are not five digits, or one is used twice")
    return out


def town_fold(name):
    """A town's name for comparison only: capitals, SAINT for ST., letters and spaces."""
    t = re.sub(r"\bST\.?(?= )", "SAINT", squash(name).upper())
    return re.sub(r"[^A-Z ]", "", t)


def town_place(town, county, cousubs):
    """The Census county subdivision a town of the Secretary's lists is: the one of that county with the same name
    (ADDISON, SAINT GEORGE), or, where the list says which of two places it means (BARRE CITY, BARRE TOWN), the one of
    that name and kind. None unless exactly one fits; nothing is guessed."""
    key, here = town_fold(town), [c for c in cousubs if c["county"] == county]
    hits = [c for c in here if town_fold(c["name"]) == key]
    if len(hits) != 1:
        m = re.fullmatch(r"(.+) (CITY|TOWN)", key)
        hits = [c for c in here if m and town_fold(c["name"]) == m.group(1) and c["kind"] == m.group(2).lower()]
    return hits[0] if len(hits) == 1 and hits[0]["kind"] in ("town", "city") else None


def county_labels(path):
    """{five-digit code: the county's name with its kind word (Addison County)} from the Census county file."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    out = {}
    for r in (x.as_dict() for x in shapefile.Reader(dbf=io.BytesIO(z.read(base))).iterRecords()):
        if r["STATEFP"] == FIPS:
            out[str(r["GEOID"])] = squash(r.get("NAMELSAD") or f"{r['NAME']} County")
    return out


def words_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def local_level(loc, nov, counties, labels, cousubs, cousub_path, colours):
    """Vermont's county offices and justices of the peace as rows ready to write (races, candidates, places, sources,
    gaps, notes) with the counts behind them. Nothing here touches the database, and nothing is printed."""
    by_county = {name: geoid for name, (geoid, _n) in counties.items()}                # ADDISON -> 50001
    if len(labels) != 14 or set(labels) != set(by_county.values()):
        raise SystemExit(f"Vermont: the Census county file gives {len(labels)} counties for the state, not 14")
    problems, gaps, contests = [], [], {}

    def gap(scope, pid, place, what, reason, url):
        """One row for sl_gaps, its key (scope, place id, what) kept unique: a second gap of the same words is numbered."""
        words, n = what, 1
        while any(g[1:3] == (scope, pid) and g[4] == words for g in gaps):
            n += 1
            words = f"{what} ({n})"
        gaps.append((STATE, scope, pid, place, words, reason, url))

    def new(kind, office, geoid, place):
        return {"kind": kind, "office": office, "county": geoid, "place": place, "site": None, "rows": [], "seats": set(), "terms": set()}

    def town_of(town, where):
        geoid = by_county.get(nov["towns"].get(town, ""))
        place = town_place(town, geoid, cousubs) if geoid else None
        if place is None:
            raise SystemExit(f"Vermont: {where}: a town that the results site's town table and the Census Bureau's county subdivisions do not "
                             "place in exactly one town or city; stopping")
        return geoid, place

    # ---- every contest the results site lists, so that a contest with no candidate is kept
    unknown = Counter()
    for n, c in enumerate(nov["county"], start=1):
        geoid = by_county.get(c["county"])
        if not geoid:
            raise SystemExit(f"Vermont: the results site's county file, contest {n}: a county the Census Bureau's county file does not have; stopping")
        if c["office"] not in COUNTY_OFFICES:
            unknown[("county", geoid, c["office"])] += 1
            continue
        key = ("county", geoid, c["office"])
        if key in contests:
            raise SystemExit(f"Vermont: the results site's county file lists a county's contest twice (contest {n}); stopping")
        contests[key] = new("county", c["office"], geoid, None)
        contests[key]["site"] = c
    for n, c in enumerate(nov["town"], start=1):
        geoid, place = town_of(c["town"], f"the results site's town file, contest {n}")
        if not c["office"].startswith(JP) or c["district"]:
            unknown[("place", place["code"], c["office"])] += 1
            continue
        key = ("town", place["code"], JP)
        if key in contests:
            raise SystemExit(f"Vermont: the results site's town file lists a town's justices twice (contest {n}); stopping")
        contests[key] = new("town", JP, geoid, place)
        contests[key]["site"] = c

    # ---- the candidate list's rows, each into exactly one contest
    not_on_site = set()
    for n, contest, district, name, party, seats, term in loc["rows"]:
        where = f"{LIST_NAME}, sheet row {n}"
        if contest in COUNTY_OFFICES:
            geoid = by_county.get(district)
            if not geoid:
                raise SystemExit(f"Vermont: {where}: a county office filed under a name that is not one of the 14 counties; stopping")
            key, fresh = ("county", geoid, contest), new("county", contest, geoid, None)
        else:
            if district not in nov["towns"]:
                raise SystemExit(f"Vermont: {where}: a town that is not in the results site's town table; stopping")
            geoid, place = town_of(district, where)
            key, fresh = ("town", place["code"], JP), new("town", JP, geoid, place)
        if key not in contests:
            not_on_site.add(key)
        c = contests.setdefault(key, fresh)
        c["rows"].append((n, name, party))
        c["seats"].add(seats)
        c["terms"].add(term)

    # ---- races and candidates
    def colour(label):
        return colours.get(label) or party_code(label.split("/")[0])

    order = {k: i for i, k in enumerate(COUNTY_OFFICES)}
    races, cands, places, n_blank, n_diff, n_seat_diff, n_empty, levels, kinds, parties = [], [], {}, 0, 0, 0, 0, Counter(), Counter(), Counter()
    stored = Counter()                                                        # candidates stored for county offices, and for towns' justices
    for key in sorted(contests, key=lambda k: (k[0] != "county", contests[k]["county"], order.get(k[2], 9), k[1])):
        c = contests[key]
        if c["kind"] == "county":
            kind, office, usual = COUNTY_OFFICES[c["office"]]
            level, jur, jid = "county", labels[c["county"]], c["county"]
            rid = f"2026-{STATE}-{c['county']}-{kind.replace('_', '-')}"
        else:
            kind, office, usual, p = JP_KIND, JP_OFFICE, JP_TERM, c["place"]
            level, jur, jid = ("city" if p["kind"] == "city" else "township"), p["label"], f"{STATE}-M-{p['code']}"
            rid = f"2026-{STATE}-M-{p['code']}-{kind.replace('_', '-')}"
            places[jid] = ("mcd", jid, jur, json.dumps([c["county"]]), SRC_L_COUSUB)
        if len(c["seats"]) > 1:
            raise SystemExit(f"Vermont: {rid}: the list gives two numbers to elect for one contest; stopping")
        listed, site = next(iter(c["seats"]), None), (c["site"] or {}).get("vote_for") or None
        seats = listed or site
        note = []
        if seats and seats > 1:
            note.append(f"Voters choose {seats}.")
        if listed and site and listed != site:
            n_seat_diff += 1
            problems.append(f"{rid}: the candidate list elects {listed}, the results site {site}; the candidate list's number is shown")
            gap("race", rid, jur, "how many are elected",
                f"The Secretary of State's candidate list says voters choose {listed} for this office and the Secretary's results site says {site}; "
                "the candidate list's number is shown until the two agree.", ENR_SITE)
        odd = sorted(t for t in c["terms"] if t and t != usual)
        if odd:
            note.append(f"The Secretary of State's list gives this contest a term of {words_list(odd)} years.")
            problems.append(f"{rid}: the list gives a term of {words_list(odd)} years, not the usual {usual}")
        if key in not_on_site:
            problems.append(f"{rid}: on the candidate list but not among the contests the results site lists")
        # the control: the same names and parties by the second route
        if c["site"] is not None:
            a, b = [(nm, pt) for _n, nm, pt in c["rows"]], [(nm, pt) for nm, pt in c["site"]["candidates"]]
            blanks = any(not nm for nm, _pt in a + b)                         # a name that was never kept cannot be compared: only the numbers are
            if (len(a) != len(b)) if blanks else (Counter(a) != Counter(b)):
                n_diff += 1
                both = sum((Counter(a) & Counter(b)).values())
                problems.append(f"{rid}: the candidate list has {len(a)} names and the results site {len(b)}"
                                + ("" if blanks else f", {both} in both with the same party"))
                gap("race", rid, jur, "a difference between the Secretary's two lists",
                    f"The Secretary of State's candidate list names {len(a)} for this office and the Secretary's results site {len(b)}"
                    + ("" if blanks else f"; the two lists share {both} of those names with the same party")
                    + ". The candidate list is the one shown.", ENR_SITE)
        shown, hidden = [], 0
        for _n, name, party in c["rows"]:
            if not name:
                hidden += 1
                continue
            if party == NO_PARTY:
                label, code, cnote = NO_PARTY_WORDS, "O", NO_PARTY_NOTE
            else:
                label, cnote = party_words(party), None
                code = colour(label)
            parties[label] += 1
            shown.append((rid, "general", GENERAL, local_name(name), label, code, None, 0, 0, None, None, None, None, SRC_L_LIST, cnote))
        if len({x[3] for x in shown}) != len(shown):
            raise SystemExit(f"Vermont: {rid}: a name is on the list twice in one contest; stopping")
        stored["county" if c["kind"] == "county" else "town"] += len(shown)
        if hidden:
            n_blank += hidden
            words = "One name" if hidden == 1 else f"{hidden} names"
            problems.append(f"{rid}: {plural(hidden, 'name')} on the list for this office did not read as a name and {'was' if hidden == 1 else 'were'} not kept")
            gap("race", rid, jur, "a candidate who cannot be shown",
                f"{words} on the Secretary of State's list for this office could not be read as a name, so "
                f"{'it is' if hidden == 1 else 'they are'} not shown.", CANDIDATES_PAGE)
            note.append(f"{words} on the Secretary of State's list for this office could not be read as a name and {'is' if hidden == 1 else 'are'} not shown.")
        if not c["rows"]:
            n_empty += 1
            listed_there = len(c["site"]["candidates"]) if c["site"] else 0
            note.append(EMPTY if not listed_there else
                        f"The Secretary of State's candidate list has no name for this office here; the Secretary's results site lists {listed_there}, "
                        "not shown until the candidate list carries them.")
        elif shown:
            note.append(CAPS)
        races.append((rid, STATE, level, kind, office, jur, jid, json.dumps([c["county"]]), None, None, 0, 1, None, None, None, GENERAL,
                      " ".join(note) or None))
        cands += shown
        levels[level] += 1
        kinds[kind] += 1
    if len({r[0] for r in races}) != len(races):
        raise SystemExit("Vermont: two county or town contests share a race id; stopping")

    # ---- what is not here
    for (scope, where, office), n in sorted(unknown.items()):
        pid = where if scope == "county" else f"{STATE}-M-{where}"
        pname = labels[where] if scope == "county" else next(p["label"] for p in cousubs if p["code"] == where)
        problems.append(f"{pid}: the results site lists {plural(n, 'contest')} this loader does not know; not loaded")
        gap(scope, pid, pname, "a contest this loader does not read" + (f": {office.title()}" if office else ""),
            "The Secretary of State's results site lists this contest for November 3 beside the county offices and justices of the peace; "
            "it is not an office this loader has been taught to read, so it is not shown.", ENR_SITE)
    for geoid in sorted(labels):
        for office in COUNTY_OFFICES:
            if ("county", geoid, office) not in contests:
                problems.append(f"{geoid}: no contest for {COUNTY_OFFICES[office][1]} on either list")
                gap("county", geoid, labels[geoid], f"{COUNTY_OFFICES[office][1]} race",
                    "Every county elects this office in November 2026, but neither the Secretary of State's candidate list nor the Secretary's "
                    "results site shows the contest for this county, so it cannot be shown.", ENR_SITE)
    if loc.get("write_ins"):
        n_w = loc["write_ins"]
        problems.append(f"{plural(n_w, 'registered write-in row')} for county or town offices on the list; not loaded")
        gap("state", STATE, "Vermont", "registered write-in candidates for county and town offices",
            f"The Secretary of State's workbook lists {plural(n_w, 'registered write-in candidate')} for county or town offices on a sheet "
            f"that does not say which county or town in a column this loader reads, so {'that candidate is' if n_w == 1 else 'they are'} not shown.",
            CANDIDATES_PAGE)
    for o in nov["others"]:
        hit = town_place(o["town"], by_county.get(o["county"], ""), cousubs) if o["town"] and o["county"] else None
        scope, pid, pname = ("place", f"{STATE}-M-{hit['code']}", hit["label"]) if hit else ("state", STATE, "Vermont")
        what_there = (f"{plural(o['offices'], 'contest for an office', 'contests for an office')} and {plural(o['questions'], 'question')} are posted for "
                      "it, but this loader reads only the general election's contests, so they are not shown" if o["offices"] or o["questions"] else
                      "no office or question has been posted for it yet, so nothing can be shown and it cannot be said whether an office is being filled")
        gap(scope, pid, pname, "a town election set for the same day" if hit else "another election set for the same day",
            f"The Secretary of State's results site lists {'a town election in ' + hit['name'] if hit else 'another election'} for November 3, 2026, "
            f"apart from the general election; {what_there}.", ENR_SITE)
    gap("state", STATE, "Vermont", "offices filled at a special town, city or school district meeting on November 3",
        "A town, city, village or school district can warn a special meeting for November 3 to fill an office; those elections are run by the "
        "local clerk and are not on the Secretary of State's candidate list, so only the ones a clerk has entered on the Secretary's results "
        "site can be seen from here.", ENR_SITE)

    # ---- counts: every county or town row of the list is one candidate in one race
    n_rows, n_county, n_town = len(loc["rows"]), sum(1 for r in loc["rows"] if r[1] in COUNTY_OFFICES), sum(1 for r in loc["rows"] if r[1] == JP)
    if n_rows != n_county + n_town or len(cands) + n_blank != n_rows or loc["rows_read"] != n_rows + sum(loc["other"].values()):
        raise SystemExit(f"Vermont: {loc['rows_read']} rows read from the list, {n_rows} county and town rows, {len(cands)} candidates stored and "
                         f"{n_blank} left out; the counts do not add up; stopping")
    if len({(x[0], x[3]) for x in cands}) != len(cands):
        raise SystemExit("Vermont: a candidate is stored twice in one county or town race; stopping")
    site_county, site_town = sum(len(c["candidates"]) for c in nov["county"]), sum(len(c["candidates"]) for c in nov["town"])
    jp_races = [r for r in races if r[3] == JP_KIND]
    n_cities, n_towns = sum(1 for r in jp_races if r[2] == "city"), sum(1 for r in jp_races if r[2] == "township")
    reached = {f for r in races for f in json.loads(r[7])}
    q_contests, q_towns = sum(nov["questions"].values()), len(nov["questions"])
    seat_numbers = sorted({int(re.match(r"Voters choose (\d+)", r[16]).group(1)) for r in jp_races if r[16] and r[16].startswith("Voters choose")})
    place_rows = [("county", g, labels[g], json.dumps([g]), SRC_COUNTY) for g in sorted(labels)] + [places[k] for k in sorted(places)]

    agree = ("the two agree on every contest, name, party and number to elect" if not (n_diff or n_seat_diff or not_on_site) else
             f"they differ in {n_diff + n_seat_diff + len(not_on_site)} places, which are named among the gaps or in the run's report")
    notes = [
        (STATE, "local_calendar",
         "On November 3, 2026 each of Vermont's 14 counties elects two assistant judges, a probate judge, a state's attorney and a sheriff for four years "
         "and a high bailiff for two, and every town and city elects its justices of the peace for two years; all are on the general election ballot "
         "with party names. Selectboards, town clerks and treasurers, listers, constables, city councils, mayors, village trustees and school boards are "
         "not on it: they are chosen at annual town, city, village and school district meetings, held on the first Tuesday of March in most places "
         "(March 3 this year) and in April or May in a few.",
         "Vermont Constitution, chapter II, sections 43 and 50 to 52; 17 V.S.A. 2640 and 2646 and 16 V.S.A. 423 (annual meetings); the Secretary of "
         "State's list of 2026 elections on its results site; term lengths as the Secretary's candidate list gives them", CONSTITUTION),
        (STATE, "local_coverage",
         f"Loaded from the Secretary of State's 2026 General Election Candidate Listing (updated {loc['updated'] or 'on a date it does not give'}): "
         f"{levels['county']} county contests in {'all 14' if len({r[6] for r in races if r[2] == 'county'}) == 14 else len({r[6] for r in races if r[2] == 'county'})} "
         f"counties (assistant judge, probate judge, state's attorney, sheriff and high bailiff) with {stored['county']:,} candidates, and the justice of "
         f"the peace contest of {len(jp_races)} towns and cities with {stored['town']:,} candidates; {n_empty} of those contests have no candidate on the "
         "list and are shown with none" + (f", and {plural(n_blank, 'name')} on the list could not be read as a name and {'is' if n_blank == 1 else 'are'} "
                                           "not shown" if n_blank else "")
         + ". The contests, including the ones with no candidate, each town's county and the number to elect also come from the Secretary's "
         f"election results site, which already lists the November 3 contests, and {agree}. Left out: the {q_contests} ballot questions in {q_towns} "
         f"towns; the {nov['unorganized']} unorganized towns and gores, for which no justice of the peace contest is listed; and anything a town, city or "
         "school district decides at a meeting of its own. The list has no status column, so a candidate who withdrew is simply absent and cannot be "
         "counted, and it states no ballot order: the ballot prints each office's names alphabetically by surname, and names are shown here by surname.",
         "Vermont Secretary of State, Elections Division: 2026 General Election Candidate Listing/Financial Disclosure and the 2026 General Election on "
         "the election results site; 17 V.S.A. 2472 (how the ballot lists names)", CANDIDATES_PAGE),
    ]

    cs_sha, cs_date = file_facts(cousub_path)
    f = nov["files"]

    def stamped(part):
        """The site serves a contest file under a name that changes at every refresh, and the old name stops answering
        within the hour: the source's address is the site's own page, and the name as read is said in words."""
        name = f[part]["url"].rsplit("/", 1)[-1]
        return (f"The site serves this file under a name that changes each time it is refreshed (as read: {name}, {f[part]['bytes']:,} bytes), found "
                "through the election's index, so the address given is the site's own page; the fingerprint is of the copy read.")

    sources = [
        (SRC_L_LIST, STATE, "official candidate list", "Vermont Secretary of State, Elections Division",
         "2026 General Election Candidate Listing/Financial Disclosure (qualified candidates): county offices and justices of the peace",
         GENERAL_XLSX, loc["updated"], loc["fetched"], loc["sha256"], n_rows,
         "The workbook the state races are read from, read in memory and never saved. Six columns are read, by their headings: Contest, District Name "
         "(the county or the town), Name On Ballot, Party, Vote for Count and Term Length(Years); only those cells of the county and town rows are kept "
         "on disk. Town of residence, addresses, phones, e-mail, websites and financial disclosures are never read. "
         f"Of the workbook's {loc['rows_read']:,} rows, {n_county:,} are for county offices and {n_town:,} for justices of the peace, each one candidate "
         f"in one race; the other {sum(loc['other'].values()):,} are state and federal offices. The list states no ballot order and has no status column."
         + (f" {n_blank} name(s) that read like contact details were not kept." if n_blank else "")),
        (SRC_L_ELECTIONS, STATE, "official results site", "Vermont Secretary of State, Elections Division", "Vermont Election Results: the list of elections",
         f["elections"]["url"], "", nov["fetched"], f["elections"]["sha256"], 1 + len(nov["others"]),
         f"Read to find the November 3, 2026 general election and any other election a clerk has listed for the same day ({len(nov['others'])}). "
         "Election dates, kinds and towns only; the file carries no contact details."),
        (SRC_L_INDEX, STATE, "official results site", "Vermont Secretary of State, Elections Division",
         "2026 General Election (November 3, 2026) on the election results site: the election's index and town table",
         f["index"]["url"], nov["updated"], nov["fetched"], f["index"]["sha256"], len(nov["towns"]),
         f"The town table: each of the {len(nov['towns'])} towns and cities with its county, which is how a town's justices are filed under a county; "
         f"{nov['unorganized']} unorganized towns and gores are listed apart. No contact details in the file. The date given as published is the "
         "site's own last-updated stamp, on Vermont's clock."),
        (SRC_L_COUNTY, STATE, "official results site", "Vermont Secretary of State, Elections Division",
         "2026 General Election (November 3, 2026) on the election results site: county contests",
         ENR_SITE, nov["updated"], nov["fetched"], f["county"]["sha256"], site_county,
         f"Before any vote is counted the file already lists each county contest with the number to elect and the names and parties under it: "
         f"{len(nov['county'])} contests, {site_county:,} names. Read as a second route to the candidate list; only the office, county, number to elect, "
         f"names and parties are kept, no vote. {stamped('county')}"),
        (SRC_L_TOWN, STATE, "official results site", "Vermont Secretary of State, Elections Division",
         "2026 General Election (November 3, 2026) on the election results site: town contests",
         ENR_SITE, nov["updated"], nov["fetched"], f["town"]["sha256"], site_town,
         f"Each town's justice of the peace contest with the number to elect and the names and parties under it: {len(nov['town'])} contests, "
         f"{site_town:,} names, {sum(1 for c in nov['town'] if not c['candidates'])} contests with no name. The {q_contests} ballot questions in "
         f"{q_towns} towns are counted and their words never read. Only the office, town, number to elect, names and parties are kept, no vote. "
         f"{stamped('town')}"),
        (SRC_L_COUSUB, STATE, "official boundaries (attributes)", "U.S. Census Bureau",
         "Cartographic boundary file, county subdivisions, Vermont, 2024 (1:500,000)", COUSUB_URL, "2024", cs_date, cs_sha, len(cousubs),
         "Names with their kind word (Addison town, Barre city) and five-digit codes of Vermont's towns and cities, read from the file's attribute "
         "table; no shapes are read. A town on the Secretary's lists is matched within its county by name (SAINT for St., and CITY or TOWN where two "
         "places share a name) and only when exactly one fits."),
    ]
    for o in nov["others"]:
        if o.get("index"):
            ident = o["index"]["url"].rsplit("/", 1)[-1].rsplit(".", 1)[0]          # the election's id on the site; its first eight characters unless taken
            sid = SRC_L_OTHER + (ident[:8] if all(s[0] != SRC_L_OTHER + ident[:8] for s in sources) else ident)
            posted = ("nothing is posted yet." if not (o["offices"] or o["questions"]) else
                      f"{plural(o['offices'], 'contest for an office', 'contests for an office')} and {plural(o['questions'], 'question')} are posted "
                      "and not read.")
            sources.append((sid, STATE, "official results site", "Vermont Secretary of State, Elections Division",
                            "Another election listed for November 3, 2026 on the election results site: its index", o["index"]["url"], "", nov["fetched"],
                            o["index"]["sha256"], 1,
                            "Read to see whether a town's own election on the same day has an office posted (the town, its county and the address of "
                            "its town file only); " + posted))
            if o.get("town_file"):
                tf = o["town_file"]
                sources.append((sid + "-town-file", STATE, "official results site", "Vermont Secretary of State, Elections Division",
                                "Another election listed for November 3, 2026 on the election results site: its town file", ENR_SITE, "", nov["fetched"],
                                tf["sha256"], o["offices"] + o["questions"],
                                "Only counted: how many contests for an office and how many questions it holds; " + posted + " The site serves the "
                                f"file under a name that changes each time it is refreshed (as read: {tf['url'].rsplit('/', 1)[-1]}, {tf['bytes']:,} "
                                "bytes), so the address given is the site's own page; the fingerprint is of the copy read."))

    # ---- the last look before anything is written: nothing that reads like contact details, by the trial check's test and the page builder's
    for table, strict, items in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in races]),
                                 ("sl_candidates", True, [(x[0], (x[3], x[4], x[14])) for x in cands]),
                                 ("sl_places", True, [(p[1], (p[2],)) for p in place_rows]),
                                 ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                                 ("sl_notes", False, [(x[1], (x[2], x[3])) for x in notes]),
                                 ("sl_sources", False, [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(t and (contact_like(t, strict) or (strict and BUILDER_STREET.search(str(t)))) for t in texts):
                raise SystemExit(f"Vermont: a text for {table} ({ident}) reads like contact details; stopping (the text is not printed)")

    return {"races": races, "cands": cands, "places": place_rows, "sources": sources, "gaps": gaps, "notes": notes, "problems": problems,
            "levels": dict(levels), "kinds": dict(kinds), "parties": dict(parties), "counties": len(reached), "empty": n_empty, "blanked": n_blank,
            "differences": n_diff + n_seat_diff + len(not_on_site), "rows_read": loc["rows_read"], "other_rows": dict(loc["other"]), "rows": n_rows,
            "county_rows": n_county,
            "town_rows": n_town, "site_county": site_county, "site_town": site_town, "site_contests": len(nov["county"]) + len(nov["town"]),
            "towns": n_towns, "cities": n_cities, "questions": q_contests, "question_towns": q_towns, "seat_numbers": seat_numbers,
            "updated": loc["updated"], "fetched": loc["fetched"], "site_fetched": nov["fetched"]}


# ---------------------------------------------------------------------------------------------------- loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, county_zip=COUNTY_ZIP, local_cache=None):
    """Vermont's rows into the database at db_path: the state races, then the county and town ones. local_cache is the
    folder the local level's cut-down copies are kept in (ballot_cache/vt/local unless another is given)."""
    try:
        return _load(db_path, say, cache, roster_db, county_zip, local_cache)
    finally:
        _BOOKS.clear()                                                         # the workbooks carry contact columns: none is held past the run


def _load(db_path, say, cache, roster_db, county_zip, local_cache):
    net.patient_lookups()
    folder = os.path.join(cache, "vt")
    gpath = os.path.join(folder, "vt_2026_sl_general_list.json")
    ppath = os.path.join(folder, "vt_2026_sl_primary_list.json")
    wpath = os.path.join(folder, "vt_2026_sl_primary_winner_listing.json")
    epath = os.path.join(folder, "vt_2026_sl_primary_results.json")
    cpath = os.path.join(folder, "vt_2026_primary_official_canvass_town_by_town.pdf")      # the federal loader's copy; results only
    gen = kept(gpath, 2, general_list)
    # the county and town rows of the same workbook, cut from the same bytes as the state rows, and the November contests
    lfolder = local_cache or os.path.join(folder, "local")
    loc, cut_now = local_list(lfolder, gen["sha256"])
    if loc["sha256"] != gen["sha256"]:                                         # the list changed since the state rows' copy was made:
        gen = general_list()                                                   # make that copy again, from the run's one download
        write_json(gpath, gen)
    by_office = Counter(r[1] for r in loc["rows"])
    if (gen["sha256"] != loc["sha256"] or gen.get("rows_read") != loc["rows_read"] or len(gen["state"]) != loc["other"].get("state", 0)
            or any(by_office.get(k.upper(), 0) != v for k, v in gen["others"].items() if k.upper() in NOT_LOADED)):
        raise SystemExit("Vermont: the state rows' copy and the county and town rows' copy of the candidate list do not hold the same workbook; "
                         "delete ballot_cache/vt/local/" + LOCAL_LIST_FILE + " and run again")
    nov_site = november(lfolder, refresh=cut_now, say=say)
    cousub_path = cousub_file(lfolder, say)
    pri = kept(ppath, 30, primary_list)
    win = kept(wpath, 30, winner_listing)
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    report = []

    # ---- districts: the list's codes, the roster's names, seats
    seats = defaultdict(list)
    for p in legs:
        seats[(p["chamber"], p["district"])].append(p)
    by_key = {(ch, dkey(d)): d for ch, d in seats}

    def district_of(contest, code):
        chamber = LEGISLATURE[contest][3]
        name = district_name(code, chamber)
        d = by_key.get((chamber, dkey(name)))
        if d is None:
            raise SystemExit(f"Vermont: the list's {chamber} district {code!r} ({name}) is not a district of the roster")
        return d

    # registered write-ins: office, district key, name parts
    def reg_district(r, office):
        if office in STATEWIDE:
            return ""
        chamber = LEGISLATURE[office][3]
        text = r["SENATE DISTRICT"] if office == SENATE else r["REPRESENTATIVE (HOUSE) DISTRICT"]
        hits = {d for (ch, k), d in by_key.items() if ch == chamber and k == dkey(text)}
        if len(hits) != 1:
            raise SystemExit(f"Vermont: a registered write-in's {chamber} district is not read ({text!r})")
        return hits.pop()

    registered = []                                                            # (office, roster district, shown name, parts)
    for r in pri["write_in"]:
        office = WRITE_OFFICE[r["OFFICE"].upper()]
        d = reg_district(r, office)
        caps = " ".join(x for x in (r["FIRST NAME"], r["MIDDLE NAME"], r["LAST NAME"]) if x)
        registered.append((office, d, caps, (fold(r["FIRST NAME"]).split(), " ".join(fold(r["LAST NAME"]).split()))))

    code_of = {}                                                               # roster district -> the Secretary's code (for the results)

    def enr_fetch():
        # The results carry districts by the Secretary's codes; a registered write-in's district is keyed by that code.
        reg = []
        for office, d, _caps, parts in registered:
            reg.append((office, "" if office in STATEWIDE else dkey(code_of[(office, d)]), parts))
        return enr_results(reg)

    # ---- the November list
    groups = {}                                                                # (contest, district or None) -> [rows in list order]
    for r in gen["state"]:
        contest = r["Contest"].upper()
        if contest in STATEWIDE:
            if r["District Name"] not in ("N/A", ""):
                raise SystemExit(f"Vermont: a statewide office row names a district ({r['District Name']!r})")
            key = (contest, None)
        else:
            d = district_of(contest, r["District Name"])
            prev = code_of.setdefault((contest, d), r["District Name"])
            if prev != r["District Name"]:
                raise SystemExit(f"Vermont: two codes on the list for the {contest} district {d}")
            key = (contest, d)
        if r["Vote for Count"] not in COUNT:
            raise SystemExit(f"Vermont: a Vote for Count that is not read ({r['Vote for Count']!r})")
        groups.setdefault(key, []).append(r)
    for (ch, d), members in seats.items():
        contest = SENATE if ch == "Senate" else HOUSE
        if (contest, d) not in code_of:
            report.append(f"{race_id(contest, d)}: no candidate on the November list for this district")
    # the primary list's codes for districts nobody filed for in November
    for sheet, rows in pri["parties"].items():
        for r in rows:
            c = r["Contest"].upper()
            if c in LEGISLATURE:
                code_of.setdefault((c, district_of(c, r["District Name"])), r["District Name"])
    for r in win["rows"]:
        c = r["Office Name"].upper()
        if c in LEGISLATURE:
            code_of.setdefault((c, district_of(c, r["District"])), r["District"])
    for office, d, _caps, _parts in registered:
        if office in LEGISLATURE and (office, d) not in code_of:
            raise SystemExit(f"Vermont: a registered write-in's district ({d}) is on none of the Secretary's lists")

    enr = kept(epath, 30, enr_fetch)

    missing = [c for c in STATEWIDE if (c, None) not in groups]
    if missing:
        raise SystemExit(f"Vermont: statewide offices missing from the November list: {missing}")
    sen_d = sorted(d for c, d in groups if c == SENATE)
    house_d = sorted(d for c, d in groups if c == HOUSE)
    all_sen = sorted(d for ch, d in seats if ch == "Senate")
    all_house = sorted(d for ch, d in seats if ch == "House")
    if sum(len(seats[("Senate", d)]) for d in all_sen) != 30 or sum(len(seats[("House", d)]) for d in all_house) != 150:
        report.append("the roster does not seat 30 senators and 150 representatives")

    # names as shown: the roster's own capitals where its words are the same words
    fixed = {}
    for p in legs + list(offs.values()):
        for form in (p["full"], f"{p['first']} {p['last']}"):
            if form:
                fixed[fold(form)] = form

    def shown(caps):
        caps = squash(caps)
        if fold(caps) in fixed:
            return fixed[fold(caps)]
        return ordinary(caps)

    colours = {k: v[0] for k, v in (place(STATE).get("parties") or {}).items()}

    def colour(label):
        """The one-letter colour code the state pages give the party (states/places.py), else the kit's own rule."""
        return colours.get(label) or party_code(label.split("/")[0])

    def holders(contest, d):
        if contest in STATEWIDE:
            rk = STATEWIDE[contest][3]
            return [offs[rk]] if rk and rk in offs else []
        return sorted(seats.get((LEGISLATURE[contest][3], d), []), key=lambda p: (fold(p["last"] or ""), fold(p["first"] or "")))

    def identify(contest, d, name, party):
        """(incumbent, state_member_id, note) for one listed name."""
        here = [h for h in holders(contest, d) if person_fits(name, h)]
        if len(here) == 1:
            return 1, here[0]["id"], None
        if len(here) > 1:
            report.append(f"{race_id(contest, d)}: {name} fits more than one holder; no member is linked")
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and parties_meet(party, p["party"])]
        pool += [p for p in offs.values() if person_fits(name, p) and parties_meet(party, p["party"])]
        if len(pool) == 1:
            p = pool[0]
            where = (f"the {p['chamber']} ({p['district']})" if p in legs else f"the office of {p['office'].replace('_', ' ').replace('lt ', 'lieutenant ')}")
            return 0, p["id"], f"Serves today in {where}."
        return 0, None, None

    races, cands, general_n = {}, [], Counter()
    for (contest, d), rows in groups.items():
        rid = race_id(contest, d)
        vf = {COUNT[r["Vote for Count"]] for r in rows}
        if len(vf) != 1:
            raise SystemExit(f"Vermont: {rid} has two Vote for Counts on the list")
        vf = vf.pop()
        hs = holders(contest, d)
        note = []
        if contest in STATEWIDE:
            okind, office = STATEWIDE[contest][1:3]
            level, jur, jid, cids, dist = "statewide", "Vermont", FIPS, None, None
            if vf != 1:
                raise SystemExit(f"Vermont: {rid} elects {vf} on the list")
            if not hs:
                note.append("The roster used here does not list who holds this office today.")
        else:
            okind, office, chamber = LEGISLATURE[contest][1:]
            level, dist = "legislature", d
            jur = f"{d} {'Senate' if chamber == 'Senate' else 'House'} District"
            jid = f"{STATE}-{d.upper().replace(' ', '-')}"
            names = enr["counties"].get(f"{'senate' if chamber == 'Senate' else 'house'}|{code_of[(contest, d)]}", [])
            bad = [n for n in names if n not in counties]
            if not names or bad:
                raise SystemExit(f"Vermont: {rid}: the results' town table gives no counties, or names a county not in the Census file ({bad})")
            cids = ",".join(sorted(counties[n][0] for n in names))
            if len(hs) != vf:
                report.append(f"{rid}: the list elects {vf}; the roster seats {len(hs)} here today")
            if vf > 1:
                word = {2: "two", 3: "three"}[vf]
                title = "senators" if chamber == "Senate" else "representatives"
                note.append(f"{word.capitalize()} seats: the district elects {word} {title}, each voter may vote for {word}, and the {word} "
                            "with the most votes win.")
            if not hs:
                note.append("The roster used here lists nobody in this district today.")
        races[rid] = {"row": [rid, STATE, level, okind, office, jur, jid, cids, dist, None, 0, 1,
                              "; ".join(h["id"] for h in hs) or None, "; ".join(h["full"] for h in hs) or None,
                              "; ".join(h["party"] or "" for h in hs) or None, GENERAL, None],
                      "note": note, "contest": contest, "d": d, "vf": vf, "hs": hs}
        if len(rows) < vf:
            report.append(f"{rid}: {len(rows)} candidate(s) on the November list for {vf} seat(s)")
        ordered = surname_order([r["Name On Ballot"] for r in rows])
        if not ordered:
            report.append(f"{rid}: the list's names are not in alphabetical order by surname; no ballot order is stored")
        for i, r in enumerate(rows, start=1):
            if not r["Party"]:
                raise SystemExit(f"Vermont: a candidate in {rid} has no party on the list")
            party = party_words(r["Party"])
            name = shown(r["Name On Ballot"])
            incb, mid, n2 = identify(contest, d, name, party)
            cands.append([rid, "general", GENERAL, name, party, colour(party), i if ordered else None, incb, 0,
                          None, None, None, mid, SRC_GEN, " ".join(x for x in (CAPS, n2) if x)])
            general_n[okind] += 1
    for r in gen["write_in"]:                                                    # none on the list today; kept if one appears
        office = WRITE_OFFICE[r["OFFICE"].upper()]
        d = reg_district(r, office)
        rid = race_id(office, d if office in LEGISLATURE else None)
        if rid not in races:
            raise SystemExit(f"Vermont: a registered November write-in for a race with nobody on the list ({rid})")
        caps = " ".join(x for x in (r["FIRST NAME"], r["MIDDLE NAME"], r["LAST NAME"]) if x)
        cands.append([rid, "general", GENERAL, shown(caps), "Write-in", "W", None, 0, 1, None, None, None, None, SRC_GEN,
                      f"{WRITE_NOV} {CAPS}"])

    # ---- the August 11 primary
    printed = defaultdict(list)                                                # (party, contest, district or None) -> [printed names]
    for sheet, rows in pri["parties"].items():
        for r in rows:
            c = r["Contest"].upper()
            d = None if c in STATEWIDE else district_of(c, r["District Name"])
            printed[(sheet, c, d)].append(r["Name On Ballot"])
    listing = defaultdict(dict)
    for r in win["rows"]:
        c = r["Office Name"].upper()
        d = None if c in STATEWIDE else district_of(c, r["District"])
        listing[(r["Party"], c, d)][fold(r["Name on Ballot"])] = (int(r["Votes"].replace(",", "")), bool(r["Winner"]))
    if win["criteria"].get("Election Name") != "08/11/2026 - AUGUST PRIMARY":
        raise SystemExit(f"Vermont: the winner listing is for {win['criteria'].get('Election Name')!r}")

    committee, stars = committee_report(cpath) if os.path.exists(cpath) else ({}, set())
    if not committee:
        report.append("the canvass PDF is not in the cache (the federal loader keeps it); the statewide figures were not compared with it")

    fields, primary_rows, checked, placed_reg = Counter(), 0, 0, Counter()
    reg_seen = Counter()
    visited = set()
    for c in enr["contests"]:
        contest, pn = c["office"], c["party"]
        d = None if contest in STATEWIDE else district_of(contest, c["dc"])
        rid = race_id(contest, d)
        where = f"{rid} {pn.title()} primary"
        visited.add((pn, contest, d))
        if rid not in races:
            if c["printed"] or c["write_ins"]:
                report.append(f"{where}: in the results, but the race has nobody on the November list")
            continue
        if c["vf"] != races[rid]["vf"]:
            raise SystemExit(f"Vermont: {where}: the results elect {c['vf']}, the November list {races[rid]['vf']}")
        on_ballot = {fold(n) for n in printed.get((pn, contest, d), [])}
        in_results = {fold(n) for n, _v, _w, wi in c["printed"] if not wi}
        if on_ballot != in_results:
            raise SystemExit(f"Vermont: {where}: the results' printed candidates are not the primary list's")
        # control: the winner listing
        lst = listing.get((pn, contest, d), {})
        mine = {fold(n): (v, w) for n, v, w, _wi in c["printed"]}
        if lst != mine:
            diff = sorted(set(lst) ^ set(mine)) or sorted(k for k in mine if lst.get(k) != mine[k])
            raise SystemExit(f"Vermont: {where}: the winner listing and the results differ ({len(diff)} names)")
        checked += 1
        # control: the canvassing committee (statewide offices)
        if contest in STATEWIDE and committee:
            cm = committee.get(contest, {}).get(pn)
            if cm is None:
                raise SystemExit(f"Vermont: {where}: not in the canvassing committee's report")
            want = {fold(n): v for n, v, _w, _wi in c["printed"]}
            got = {fold(k): v for k, v in cm.items() if k not in ("Write-In", "Overvotes", "Blank votes", "Total")}
            if want != got or cm.get("Write-In") != c["write_in_all"] or cm.get("Overvotes") != c["spoiled"] \
                    or cm.get("Blank votes") != c["blank"] or cm.get("Total") != c["total"]:
                raise SystemExit(f"Vermont: {where}: the canvassing committee's figures differ from the results")
            starred = {fold(k) for (o, p, k) in stars if o == contest and p == pn}
            if starred != {fold(n) for n, _v, w, _wi in c["printed"] if w}:
                raise SystemExit(f"Vermont: {where}: the committee's starred winners are not the results' winners")
        # the field: the results' candidate rows (printed names and write-ins who won), then registered write-ins
        regs_here = [r for r in registered if r[0] == contest and (contest in STATEWIDE or r[1] == d)]
        people = []                                                          # (name, votes, won, write-in, entries, registered)
        for n, v, w, wi in c["printed"]:
            reg = None
            if wi:
                hits = [r for r in regs_here if fits(name_parts(n), r[3]) and name_parts(n)[1] == r[3][1]]
                reg = hits[0] if len(hits) == 1 else None
            people.append((reg[2] if reg else n, v, w, bool(wi), None, reg))
        for idx, name, v, n_entries, won in c["write_ins"]:
            if idx is None:                                                  # a write-in winner outside the candidate rows: not expected
                report.append(f"{where}: a winning write-in not among the results' candidates; left out")
                continue
            reg = regs_here[idx]
            if any(p[5] is not None and p[5][:3] == reg[:3] for p in people):
                report.append(f"{where}: a registered write-in who won has more write-in entries besides the winner's row; they are left out")
                continue
            people.append((reg[2], v, won, True, n_entries, reg))
        pool = sum(p[1] for p in people if p[4] is None) + c["write_in_all"]         # candidates' rows plus every write-in vote
        winners = [p for p in people if p[2]]
        if len(winners) > c["vf"]:
            raise SystemExit(f"Vermont: {where}: {len(winners)} winners for {c['vf']} seats")
        if len(people) <= c["vf"]:
            continue
        fields[races[rid]["row"][3]] += 1
        nov = [x for x in cands if x[0] == rid and x[1] == "general"]
        code = CODE[pn]
        for name, v, won, wi, n_entries, reg in sorted(people, key=lambda p: -p[1]):
            if reg is not None:
                reg_seen[reg[:3]] += 1
            label = party_words(pn)
            if wi:
                same = [x[3] for x in nov if person_fits(x[3], as_person(name))]
                nm = same[0] if len(same) == 1 else shown(name)                 # as the November list prints it, else as filed or counted
            else:
                nm = shown(next((x for x in printed.get((pn, contest, d), []) if fold(x) == fold(name)), name))
            incb, mid, n2 = identify(contest, d, nm, label)
            note = [CAPS]
            if wi and n_entries is None:
                note.insert(0, WRITE_WON_REG if reg is not None else WRITE_WON)
            elif wi:
                note.insert(0, WRITE_REG + (f" Votes added from {n_entries} entries in the results, where towns reported the name "
                                            "under the same or a fitting spelling." if n_entries > 1 else ""))
            if won:
                on_nov = [x for x in nov if person_fits(x[3], as_person(nm)) and code in {PARTY_CODE.get(p) for p in x[4].split("/")}]
                if not on_nov:
                    note.insert(0, f"Won the primary; not on the November list as the {label} candidate.")
                    report.append(f"{where}: {nm} won but is not on the November list as the {label} candidate")
            if n2:
                note.append(n2)
            cands.append([rid, f"primary-{code}", PRIMARY, nm, label, colour(label), None, incb, int(wi), v,
                          round(100 * v / pool, 1) if pool else None, "advanced" if won else "lost", mid, SRC_ENR, " ".join(note)])
            primary_rows += 1
    unread = [k for k in listing if k not in visited]
    if unread:
        raise SystemExit(f"Vermont: the winner listing has {len(unread)} party primaries the results do not carry")
    for office, d, caps, _parts in registered:
        if not reg_seen[(office, d, caps)]:
            placed_reg["not named"] += 1
        else:
            placed_reg["named"] += 1

    # every November candidate of a party that held a primary field should be among that field
    for x in cands:
        if x[1] != "general":
            continue
        for part in x[4].split("/"):
            code = PARTY_CODE.get(part)
            if not code:
                continue
            field = [y for y in cands if y[0] == x[0] and y[1] == f"primary-{code}"]
            if field and not any(fits(name_parts(y[3]), name_parts(x[3])) and y[11] == "advanced" for y in field):
                report.append(f"{x[0]}: {x[3]} ({part}) is on the November list but did not win that party's primary field")

    seen = set()
    for x in cands:
        k = (x[0], x[1], x[3])
        if k in seen:
            raise SystemExit(f"Vermont: {x[3]} is listed twice in {x[0]} {x[1]}")
        seen.add(k)

    # ---- the roster's party for a holder against the party the November list prints for the same person
    for rid, race in races.items():
        for h in race["hs"]:
            same = [x for x in cands if x[0] == rid and x[1] == "general" and x[12] == h["id"]]
            for x in same:
                if not parties_meet(x[4], h["party"]):
                    report.append(f"{rid}: the roster gives {h['full']} the party {h['party']!r}; the November list prints {x[4]!r}")

    for rid, race in races.items():
        race["row"][16] = " ".join(race["note"]) or None
    general = [x for x in cands if x[1] == "general"]
    # the county and town level: its races and candidates, the counties (named with their kind word) and the towns and cities
    local = local_level(loc, nov_site, counties, county_labels(county_zip), census_cousubs(cousub_path), cousub_path, colours)
    place_rows = list(local["places"])
    for rid, race in sorted(races.items()):
        r = race["row"]
        if r[2] == "legislature":
            place_rows.append(("senate" if r[3] == "state_senate" else "house", r[6], r[5], r[7], SRC_ENR))

    gen_sha, pri_sha, win_sha = gen["sha256"], pri["sha256"], win["sha256"]
    roster_sha, roster_date = file_facts(roster_db)
    county_sha, county_date = file_facts(county_zip)
    enr_sha = "; ".join(f"{k} {v['sha256']}" for k, v in enr["files"].items())
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", enr.get("updated", ""))
    enr_published = f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""
    sources = [
        (SRC_GEN, STATE, "official candidate list", "Vermont Secretary of State, Elections Division",
         "2026 General Election Candidate Listing/Financial Disclosure (qualified candidates): statewide offices and the General Assembly",
         GENERAL_XLSX, gen["updated"], gen["fetched"], gen_sha, len(general),
         f"Linked from the Candidates page ({CANDIDATES_PAGE}). Workbook read in memory, never saved; columns taken by name, only Contest, "
         "District Name, Name On Ballot, Party and Vote for Count. Town of residence, addresses, phones, e-mail, websites and financial "
         "disclosures never read. The list gives no ballot positions; its order, alphabetical by surname as 17 V.S.A. 2472(b)(2) prints the "
         "ballot, is stored as the ballot order. No status column, so a withdrawn candidate, no longer listed, cannot be counted. The "
         "Secretary's district codes are shown as the Legislature's district names. Other offices on the list: "
         + ", ".join(f"{k.title()} ({v})" for k, v in sorted(gen["others"].items()) if k.upper() not in NOT_LOADED)
         + ", left to the federal pages; and the county offices and justices of the peace ("
         + f"{sum(v for k, v in gen['others'].items() if k.upper() in NOT_LOADED):,} rows), loaded as local races from the same workbook."),
        (SRC_PRI, STATE, "official candidate list", "Vermont Secretary of State, Elections Division",
         "2026 Primary Election Candidate Listing/Financial Disclosure (qualified candidates): statewide offices and the General Assembly",
         PRIMARY_XLSX, pri["updated"], pri["fetched"], pri_sha, sum(len(v) for v in pri["parties"].values()) + len(pri["write_in"]),
         "Who was printed on each party's August 11 primary ballot (the results' printed candidates must be exactly these) and the registered "
         f"write-in candidates ({len(pri['write_in'])} for these offices; the registration names no party). The same five columns only, and "
         "the write-in sheet's office, district and name columns."),
        (SRC_ENR, STATE, "official results", "Vermont Secretary of State, Elections Division",
         "2026 August Primary Election Results (official), statewide offices, State Senate and State Representative",
         ENR_SITE, enr_published, enr["fetched"], enr_sha, primary_rows,
         f"Linked from the Elections Results & Data page ({RESULTS_PAGE}); read from the files the results site's own page fetches "
         f"({ENR_STATIC}elections/...), marked official, {enr.get('towns_reporting', '')} towns reporting. Every town's candidates, write-ins, "
         "blank votes and spoiled ballots add up to its total, and the towns to the district-wide and statewide rows. A field is a party "
         "primary with more candidates than seats; its total is the candidates' votes plus every write-in vote (blanks and spoiled ballots "
         "left out). Write-in names are shown only for a write-in who won the nomination, or a registered write-in candidate recorded in "
         "one party's primary for that office and district; every other write-in is counted in the total and never named "
         f"({enr.get('registered_in_two_parties', 0)} registered write-ins were recorded in more than one party's primary, so in neither "
         "is the name shown). The results' town table gives the counties each district reaches."),
        (SRC_WIN, STATE, "official results", "Vermont Secretary of State, Elections Division",
         "2026 August Primary Winner Listing", WINNERS_XLSX, "", win["fetched"], win_sha, len(win["rows"]),
         f"Control: every candidate's votes and winner mark agree with the results ({checked} party primaries compared). Workbook read in "
         "memory, never saved; Winner, Name on Ballot, Party, Office Name, District, Votes and Percent(%) only; addresses and phones never "
         "read. Its percentages are of all votes counted, blank votes included."),
    ]
    if committee:
        c_sha, c_date = file_facts(cpath)
        sources.append((SRC_CANVASS, STATE, "official results", "Vermont Secretary of State, Elections Division",
                        "2026 August Primary Official Canvass - Town by Town: the Official Report of the Canvassing Committee (17 V.S.A. 2368-2371)",
                        CANVASS_PDF, "", c_date, c_sha, sum(len(v) for v in committee.values()),
                        "Control for the six statewide offices: every candidate's votes, the write-in, overvote, blank and total figures and the "
                        "starred winners equal the results site's statewide rows. Only the committee's report pages are read."))
    sources += [
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_vt.sqlite",
         "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", roster_date, roster_sha, len(legs) + len(offs),
         "Who holds each seat today, and which candidates serve now. The roster does not carry the State Treasurer or the Auditor of Accounts."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
         "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "2024", county_date, county_sha, len(counties),
         "Five-digit county codes (GEOID) for Vermont's fourteen counties, named as the results' town table names them."),
    ]

    # Vermont's rows only, in one transaction: its races and candidates by state and race id, its sources, gaps and notes by
    # state, its places by their vt- source ids (the counties' codes begin 50, so the id cannot pick them out)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executescript(EXTRA_SCHEMA)
        mine_src = [s[0] for s in sources] + [SRC_CANVASS] + [s[0] for s in local["sources"]]
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
            con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute(f"DELETE FROM sl_places WHERE source_id IN ({','.join('?' * len(mine_src))})", mine_src)
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'vt-%'")
            con.execute("DELETE FROM sl_places WHERE id LIKE ?", (f"{STATE}-%",))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [r["row"] for r in races.values()] + local["races"])
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources + local["sources"])
            con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
            con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    finally:
        con.close()

    n_sw = sum(1 for r in races.values() if r["row"][2] == "statewide")
    say(f"    Vermont: {len(races)} races ({len(sen_d)} Senate districts, {len(house_d)} House districts, {n_sw} statewide); "
        f"{len(general)} candidates on the November list (Senate {general_n['state_senate']}, House {general_n['state_house']}, statewide "
        f"{len(general) - general_n['state_senate'] - general_n['state_house']}); primary fields: Senate {fields['state_senate']}, House "
        f"{fields['state_house']}, statewide {sum(v for k, v in fields.items() if k not in ('state_senate', 'state_house'))}; "
        f"{primary_rows} primary rows ({placed_reg['named']} of {len(registered)} registered write-in candidates named in a field); "
        f"{checked} party primaries checked against the winner listing")
    for x in cands:
        if x[12]:
            say(f"      matched: {x[0]} {x[1]}: {x[3]} -> {x[12]}{' (holds this seat)' if x[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    lv = local["levels"]
    say(f"    Vermont: {len(local['races'])} county and town races in {local['counties']} of 14 counties (county offices {lv.get('county', 0)}; justices "
        f"of the peace in {local['towns']} towns and {local['cities']} cities), {len(local['cands']):,} candidates, {local['empty']} contests with no "
        f"candidate; {local['questions']} ballot questions in {local['question_towns']} towns left out; list updated {local['updated']}, read "
        f"{local['fetched']}; results site read {local['site_fetched']}")
    say(f"      check: {local['rows_read']:,} rows in the list = {sum(local['other_rows'].values()):,} state and federal + {local['rows']:,} county and "
        f"town ({local['county_rows']:,} + {local['town_rows']:,}), each one candidate in one race"
        + (f", {local['blanked']} left out" if local["blanked"] else "")
        + f"; the results site lists {local['site_contests']} contests with {local['site_county']:,} + {local['site_town']:,} names: "
        + ("every contest, name, party and number to elect agrees" if not local["differences"] else f"{local['differences']} differences"))
    for line in local["problems"]:
        say(f"      CHECK {line}")
    return {"races": len(races), "general": len(general), "by_kind": dict(general_n), "fields": dict(fields), "primary_rows": primary_rows,
            "report": report,
            "local": {k: local[k] for k in ("levels", "kinds", "parties", "counties", "empty", "blanked", "differences", "rows_read", "other_rows", "rows",
                                            "county_rows", "town_rows", "site_county", "site_town", "site_contests", "towns", "cities", "questions",
                                            "question_towns", "seat_numbers", "updated", "fetched", "site_fetched", "problems")}
                     | {"races": len(local["races"]), "candidates": len(local["cands"]), "gaps": len(local["gaps"])}}


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3, 4):
        raise SystemExit("usage: python -m ballot.state_local_vt <database> [cache folder] [local cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE, local_cache=sys.argv[3] if len(sys.argv) > 3 else None)
