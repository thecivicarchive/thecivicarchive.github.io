"""
ballot/state_local_wv.py - West Virginia's state races on the November 3, 2026 ballot: the State Senate seats up this
year, all 100 seats of the House of Delegates, and the judicial vacancies the Secretary of State lists for November,
with the May 12 party primaries that chose the legislative nominees; and, from the same list's county level, the
county, school board and town offices on that ballot (see "The local pass" below). Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), West Virginia's rows only.

Sources, all the Secretary of State's own (the same two the federal loader, ballot/lists/wv.py, reads):
  * the 2026 candidate listing (candidates.wvsos.gov), read through the listing's own data service
    (candidate-web-api/candidates, a JSON POST with the page's own filters): the election ("11/03/2026 - GENERAL 2026"
    and "05/12/2026 - PRIMARY 2026"), the office level STATE RACE, and the tab (R Regular Candidates, W Write-In
    Candidates). Every page is counted against the service's own total. Each row also carries the candidate's e-mail,
    telephones, residential and mailing addresses, town, website and committee; none of those is ever read into the
    loader's own structures, printed or kept. Only these fields are taken from each row as it arrives: the election and
    its date, the office, its level, the district name and division number, the party code and party, the name as
    printed on the ballot (candidateBallotName) and the tab. The cached copy on disk holds nothing else.
  * the official results of the May 12, 2026 primary, from the Secretary's results site (hosted by Clarity
    Elections): the detail report (one Contest per office and party, each candidate's total, and the same votes county
    by county) and the summary report as a control. ballot/lists/wv.py fetches and checks them (headed "Official
    Results", every county completely reported); this loader reads the state contests from the same files.

What is on the November ballot: the listing's STATE RACE offices for the general election are "STATE SENATE - DISTRICT
n" (one seat in each of the 17 senatorial districts), "STATE SENATE - UNEXPIRED - DISTRICT n" (a second seat in a
district, for the rest of a term), "HOUSE OF DELEGATES - DISTRICT n" (1 to 100, one delegate each) and two kinds of
judicial vacancy ("CIRCUIT COURT JUDGE - UNEXPIRED - DISTRICT n" and "FAMILY COURT JUDGE - UNEXPIRED - DISTRICT n", with
a division number), which are nonpartisan. West Virginia elects its Governor and the other executive offices in
presidential years, and the listing has none for 2026. The Supreme Court of Appeals and the Intermediate Court of
Appeals were elected on the May 12 ballot, in nonpartisan elections that decide the seat; they are not on November's
listing, so they are not stored here.

The listing gives no ballot positions, so ballot_order is left empty. Declared write-in candidates (the Write-In tab)
are stored with write_in 1, no ballot position and party_code W; the party is the one the tab gives, where it gives
one, else "Write-in". The listing has no status column: a candidate
who withdrew or was removed is no longer listed. Names are printed in capitals; they are shown in ordinary capitals (a
sitting member as the Open States roster spells the same letters), and the race note says so.

The primary: a party's primary is stored as a field only when two or more candidates were on its ballot. The listing's
May rows say who was on each party's ballot and how the names are printed; the votes come from the detail report,
whose candidates must be the listing's for that office and party (names matched on letters only). Every candidate's
county votes must add up to the total, and the summary report must give the same totals. The results site reports no
write-in votes for these contests, so a field's total is the sum of its candidates' votes. West Virginia nominates the
leader (outcome "advanced"); a leader who is not the party's candidate on the November listing is noted, and so is a
November candidate who was not on the party's May ballot. A candidate the results count who is no longer on the
listing (withdrawn since) is kept in a field with a note, and reported.

Who holds each seat today comes from state_wv.sqlite (the Open States roster the state pages use): names, parties,
districts and start dates only. A House of Delegates seat has one member. A senatorial district has two senators,
elected in alternate even years, and the roster does not say whose seat is on the ballot, so the holder is worked out
only where the record allows: an unexpired-term seat is the one held by the district's only senator who joined
mid-term (a roster start other than 1 December of an even year or the first two weeks of January after it), and the
district's other senator then holds the full-term seat; elsewhere, the district's one sitting senator who is a
candidate for this seat (on the May or November list) is taken as its holder. Otherwise both senators are given and the
race note says why. A candidate is marked as the incumbent only when the name fits exactly one sitting member of the
same chamber and district. The roster carries no judges.

County codes: the detail report lists the counties taking part in each contest; a district's county_ids are those
counties (Census GEOIDs, from the Bureau's cartographic county file), for the legislative districts and any judicial
circuit that also had a May contest.

The local pass (county, school board and town offices; John, 2026-09-30)
------------------------------------------------------------------------
The listing's office level COUNTY carries the county offices on the November ballot (County Commission in every
county, and unexpired terms of County Clerk, Circuit Clerk, Prosecuting Attorney, Sheriff, Assessor, Magistrate and the
county Board of Education) and, under seven counties, town offices (Mayor, Recorder, Council Member, Municipal Judge).
It is read through the listing's own CSV export (candidate-web-api/candidates/export, a JSON POST with the page's
filters: the election, the office level COUNTY and the tab, R or W), one request a tab; the JSON service used above
carries no county for these rows except inside the candidate's address, which is never opened. The export's columns
are Name, Legal Name, Party, County, Race, District/Circuit, Division, Magisterial, City, State, Residence County,
MailingAddress, Filing Date, CampaignPhoneNumber and Email. Only Name (the name as printed on the ballot: the same
words, row for row, as the JSON service's candidateBallotName), Party, County, Race, District/Circuit, Division and
Magisterial are taken, by their headings, as the file is parsed; every other cell is dropped there and is never
printed, kept or stored. The SHA-256 of each export's bytes as they arrived and its row count are kept beside the
cut-down rows in ballot_cache/wv/local/wv_2026_local_general_list.json; the file itself is not kept.

The Magisterial column is free text. For a county commission or school board candidate it is the magisterial district
the candidate lives in (the ballot prints it, because no two commissioners and no more than two board members may
come from one district). That is where a person lives, so it is dropped as the file is parsed, with two exceptions
where it is the office's own place and not a person's: for a town office it is the town's name (or a ward, or a
term), and where a county's commission seats are themselves named by district it is the seat's name. The second is
accepted only on the word of the county's own page of the Secretary's results site for the May 12 primary (the
summary report: contest titles, candidates and votes, nothing else): Jefferson County's contests are titled "COUNTY
COMMISSIONER - HARPERS FERRY DIST" and "- KABLETOWN DIST", so its two seats are two races with a district.

What the list gets wrong, and what is done about it (nothing is guessed):
  * a row entered twice (every cell read is the same) is kept once and counted;
  * two candidates of one party under one county commission office: the county's primary page is read. If the office
    was put to the voters as "Vote For 2" (Berkeley), the race says "Voters choose 2."; if as seats named by district
    (Jefferson), each seat is a race; otherwise (Brooke: the primary was for one seat and the second Republican was
    not in it) the race keeps both names and its note says what the two records show;
  * a county with no commission candidate (Webster, whose primary did nominate candidates) goes in sl_gaps;
  * town rows that do not name their town. A county's town races are loaded only when every town row filed under it
    names a town that is exactly one incorporated place of that county in the Census Bureau's place list (Pax, Cowen,
    North Hills); otherwise none is, and the county goes in sl_gaps. Kanawha's rows mostly say only "WARD 4", and the
    official primary results show both Charleston and South Charleston have a Ward 4 (and show contests the list
    lacks altogether), so no race there can be told apart from the list.

Levels and keys: county offices are level "county" under the county's 5-digit code (a magistrate too: these seats are
new to this database, so they are not filed under "court"); a county board of education is level "school" under the
county's school district as the Census Bureau names and codes it (WV-S-<7-digit code>; a West Virginia school district
is its county); a town office is level "city" under the Census place code (WV-M-<5-digit code>). Race ids are
2026-WV-<place key>-<office kind>[-<district or division>][-S], -S for an unexpired term. A board of education seat on
a November ballot is always for the rest of a term (W. Va. Code 18-5-1b, 18-5-2), whether or not the list says so.
Ballot order is drawn by lot in each county (W. Va. Code 3-5-13a) and is not in the list. Nothing is matched to the
legislative roster and no holder is given for a local office.

sl_gaps and sl_notes (ballot/check_local.py's EXTRA_SCHEMA) are rewritten for West Virginia on every run: what could
not be loaded and why, a "local_calendar" note (which local offices are on this ballot and which are elected at
another time, from the state code) and a "local_coverage" note.

The privacy rule: only office, district, name, party, ballot order, status and votes are read from any list. Nothing
else is printed, logged, cached or stored, and no photos, ages, websites, biographies or money are stored in this
phase.

Usage: python -m ballot.state_local_wv <database file> [cache folder]
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
import xml.etree.ElementTree as ET

from urllib.error import URLError
from urllib.request import Request, urlopen

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA
from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.lists.tx import proper
from ballot.lists.wv import API, CLARITY, DONE, RESULTS_PAGE, RESULT_CODES, SITE, fetch_results, post, unzip_json
from ballot.match import fits
from states import net

STATE, NAME, FIPS = "WV", "West Virginia", "54"
GENERAL, PRIMARY = "2026-11-03", "2026-05-12"
ELECTIONS = {"general": ("11/03/2026 - GENERAL 2026", "11/03/2026"), "primary": ("05/12/2026 - PRIMARY 2026", "05/12/2026")}
LEVEL = "STATE RACE"
KEEP = ("candidateType", "electionName", "electionDate", "officeName", "officeDescription", "candidateDistrictName",
        "divisionNumber", "partyCode", "partyDescription", "candidateBallotName")
PAGE_SIZE = 100
ROSTER = os.path.join(HERE, "state_wv.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
LIST_CODES = {"R": "REP", "D": "DEM", "L": "LIB", "M": "MTN", "C1": "CON"}   # listing party code -> primary election code
NONPARTISAN = "Nonpartisan office"
CAPS = "West Virginia's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Declared write-in candidate: the name is not printed on the ballot."
NO_ORDER = "The Secretary of State's listing gives no ballot positions."
OFF_LIST = "Not on the party's May 12 primary ballot."
SRC_GEN, SRC_PRI = "wv-sos-2026-sl-general-list", "wv-sos-2026-sl-primary-list"
SRC_RES, SRC_SUM = "wv-sos-2026-sl-primary-results", "wv-sos-2026-sl-primary-summary"
SRC_COUNTY, SRC_ROSTER = "wv-census-2024-counties", "wv-openstates-roster"

# the local pass: county, school board and town offices (see the docstring)
LOCAL_LEVEL = "COUNTY"
EXPORT = API + "/export"
CLARITY_WV = "https://results.enr.clarityelections.com/WV/"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st54_wv_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
UNSD_URL = "https://www2.census.gov/geo/tiger/TIGER2024/UNSD/tl_2024_54_unsd.zip"
CODE_URL = "https://code.wvlegislature.gov/3-1-17/"
LOCAL_READ = {"name": "Name", "party": "Party", "county": "County", "race": "Race", "circuit": "District/Circuit",
              "division": "Division", "place": "Magisterial"}                    # the only cells of the export ever taken
LOCAL_COUNTY = {                                                                  # the list's title -> kind, plain title, partisan
    "COUNTY COMMISSION": ("county_commissioner", "County Commissioner", 1),
    "COUNTY CLERK": ("county_clerk", "County Clerk", 1),
    "CIRCUIT CLERK": ("clerk_of_court", "Circuit Clerk", 1),
    "PROSECUTING ATTORNEY": ("county_attorney", "Prosecuting Attorney", 1),
    "SHERIFF": ("sheriff", "Sheriff", 1),
    "ASSESSOR": ("county_assessor", "Assessor", 1),
    "MAGISTRATE": ("magistrate", "Magistrate", 0),
}
LOCAL_SCHOOL = {"BOARD OF EDUCATION": ("school_board", "Board of Education Member")}
LOCAL_TOWN = {"MAYOR": ("mayor", "Mayor"), "RECORDER": ("city_recorder", "Recorder"), "COUNCIL MEMBER": ("council", "Council Member"),
              "MUNICIPAL JUDGE": ("municipal_judge", "Municipal Judge")}
PARTY_LINES = {"REPUBLICAN", "DEMOCRAT", "LIBERTARIAN", "MOUNTAIN", "CONSTITUTION"}     # each nominates one candidate a seat
TITLE_PARTY = {"REP": "REPUBLICAN", "DEM": "DEMOCRAT", "MTN": "MOUNTAIN", "LBN": "LIBERTARIAN", "LIB": "LIBERTARIAN",
               "CST": "CONSTITUTION", "CON": "CONSTITUTION"}                         # a results title's prefix -> the list's party
SRC_LOCAL, SRC_LOCAL_W = "wv-sos-2026-local-general-list", "wv-sos-2026-local-general-write-ins"
SRC_PLACES, SRC_SCHOOLS, SRC_PAGES = "wv-census-2020-places", "wv-census-2024-school-districts", "wv-sos-2026-primary-county-pages"
UNEXPIRED = "An election for the rest of a term, as the Secretary of State's list titles it (\"unexpired\")."
NO_PARTY_PRINTED = "{} are elected on a nonpartisan ballot: no party is printed."
BOARD_TERM = ("State law elects full terms at the May primary, so a board seat on the November ballot is for the rest of a term; "
              "the Secretary of State's list does not title this one \"unexpired\".")
BOARD_BOTH = ("State law elects full terms at the May primary, so a board seat on the November ballot is for the rest of a term; "
              "the Secretary of State's list titles the office \"unexpired\" for some of these candidates and not for others.")
HOW_MANY = "The Secretary of State's list does not say how many seats are being filled."
NO_DIVISION = "The Secretary of State's list gives no division number for this seat."

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def norm(text):
    """Letters and digits only, for comparing a district name with the office it belongs to."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def join(*parts):
    return " ".join(p for p in parts if p) or None


# ---------------------------------------------------------------- the candidate listing: allowed fields only

def read_tab(election, ctype):
    """Every STATE RACE row of one election on one tab (R regular, W write-in), the allowed fields only."""
    rows, page, meta = [], 0, {}
    while True:
        got = post({"page": page, "size": PAGE_SIZE, "candidateType": ctype, "electionName": election, "officeDescription": [LEVEL]})
        if got.get("error") or not isinstance(got.get("data"), dict):
            raise SystemExit(f"West Virginia: the candidate listing's service answered with an error ({got.get('message')!r})")
        meta = got.get("meta") or {}
        rows += [{k: c.get(k) for k in KEEP} for c in got["data"].get("candidates") or []]   # the other fields are never kept
        if meta.get("last", True):
            break
        page += 1
        time.sleep(1.5)
    if len(rows) != meta.get("totalElements", len(rows)):
        raise SystemExit(f"West Virginia: the listing counts {meta.get('totalElements')} rows for {election} ({ctype}); {len(rows)} were read")
    if any(r["officeDescription"] != LEVEL or r["electionName"] != election for r in rows):
        raise SystemExit(f"West Virginia: the listing's service did not apply its own filters ({election}, {ctype})")
    return rows


def read_list(kind, path, max_age_days, say):
    """The STATE RACE rows of one election, both tabs, kept on disk (allowed fields only)."""
    if os.path.exists(path) and (max_age_days is None or time.time() - os.path.getmtime(path) < max_age_days * 86400):
        return json.load(open(path, encoding="utf-8"))
    net.patient_lookups()
    election, date = ELECTIONS[kind]
    regular = read_tab(election, "R")
    time.sleep(1.5)
    write_in = read_tab(election, "W")
    for r in regular + write_in:
        if r["electionDate"] != date:
            raise SystemExit(f"West Virginia: a row of {election} is dated {r['electionDate']}")
    kept = {"election": election, "url": SITE, "service": API, "level": LEVEL, "fields": list(KEEP),
            "regular": regular, "write_in": write_in}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {election}: {len(regular)} regular and {len(write_in)} write-in rows at the STATE RACE level")
    return kept


# ---------------------------------------------------------------- races

def race_for(row):
    """The race a listing row belongs to, or None for an office that is not stored (party committees, the Greater
    Huntington park board, the May judicial elections). Raises for an office this loader does not know."""
    office = re.sub(r"\s+", " ", row["officeName"] or "").strip().upper()
    dname = norm(row.get("candidateDistrictName"))
    m = re.fullmatch(r"STATE SENATE( - UNEXPIRED)? - DISTRICT (\d+)", office)
    if m:
        d, special = str(int(m.group(2))), 1 if m.group(1) else 0
        if norm(f"{ordinal(d)} senatorial district") != dname:
            raise SystemExit(f"West Virginia: {office} is listed under the district {row.get('candidateDistrictName')!r}")
        return {"race_id": f"2026-{STATE}-SS{d}" + ("-UNEXP" if special else ""), "level": "legislature",
                "office_kind": "state_senate", "office": "State Senator", "jurisdiction": f"{ordinal(d)} Senatorial District",
                "jurisdiction_id": d, "district": d, "seat": "Unexpired term" if special else None, "special": special,
                "partisan": 1, "chamber": "Senate", "place": ("senate", f"{STATE}-{d}", f"{ordinal(d)} Senatorial District"),
                "note": ("An election for the rest of a term, as the Secretary of State's list titles it (\"unexpired\"): the "
                         "district's second seat. The district's other seat is also on this ballot, for a full term."
                         if special else None)}
    m = re.fullmatch(r"HOUSE OF DELEGATES - DISTRICT (\d+)", office)
    if m:
        d = str(int(m.group(1)))
        if norm(f"{ordinal(d)} delegate district") != dname:
            raise SystemExit(f"West Virginia: {office} is listed under the district {row.get('candidateDistrictName')!r}")
        return {"race_id": f"2026-{STATE}-SH{d}", "level": "legislature", "office_kind": "state_house",
                "office": "Member of the House of Delegates", "jurisdiction": f"{ordinal(d)} Delegate District",
                "jurisdiction_id": d, "district": d, "seat": None, "special": 0, "partisan": 1, "chamber": "House",
                "place": ("house", f"{STATE}-{d}", f"{ordinal(d)} Delegate District"), "note": None}
    m = re.fullmatch(r"(CIRCUIT|FAMILY) COURT JUDGE - UNEXPIRED - DISTRICT (\d+)", office)
    if m:
        court, d, div = m.group(1).title(), str(int(m.group(2))), (row.get("divisionNumber") or "").strip()
        if not div.isdigit():
            raise SystemExit(f"West Virginia: {office} is listed without a division number")
        want = norm(f"{ordinal(d)} {court} court district {ordinal(div)} division")
        if want != dname:
            raise SystemExit(f"West Virginia: {office}, division {div}, is listed under {row.get('candidateDistrictName')!r}")
        key = "CC" if court == "Circuit" else "FC"
        return {"race_id": f"2026-{STATE}-{key}-{d}-{div}", "level": "court",
                "office_kind": "circuit_court" if court == "Circuit" else "family_court", "office": f"{court} Court Judge",
                "jurisdiction": f"{ordinal(d)} {court} Court District", "jurisdiction_id": f"{STATE}-{key}{d}", "district": d,
                "seat": f"Division {div}", "special": 1, "partisan": 0, "chamber": None,
                "place": ("judicial" if court == "Circuit" else "family_court", f"{STATE}-{key}{d}", f"{ordinal(d)} {court} Court District"),
                "note": ("An election for the rest of a term, as the Secretary of State's list titles it (\"unexpired\"). "
                         "Judges in West Virginia are elected on a nonpartisan ballot: no party is printed. The roster used "
                         "here carries no judges, so today's holder is not shown.")}
    if re.fullmatch(r"STATE EXECUTIVE COMMITTEE - (FE)?MALE - DISTRICT \d+", office) or office.startswith("GREATER HUNTINGTON PARK"):
        return None
    raise SystemExit(f"West Virginia: the listing names a state office this loader does not know: {office!r}")


def contest_of(text):
    """(race_id, election code) for a state legislative contest of the results report, or None for other contests."""
    t = re.sub(r"\s+", " ", text).strip()
    m = re.fullmatch(r"STATE SENATOR, (\d+)(?:st|nd|rd|th) Senatorial District - ([A-Z]+)( - UNEXPIRED TERM)?", t)
    if m:
        race, party = f"2026-{STATE}-SS{int(m.group(1))}" + ("-UNEXP" if m.group(3) else ""), m.group(2)
    else:
        m = re.fullmatch(r"HOUSE OF DELEGATES, (\d+)(?:st|nd|rd|th) District - ([A-Z]+)", t)
        if not m:
            if t.upper().startswith(("STATE SENATOR", "HOUSE OF DELEGATES")):
                raise SystemExit(f"West Virginia: a legislative contest in the results that is not read ({t!r})")
            return None
        race, party = f"2026-{STATE}-SH{int(m.group(1))}", m.group(2)
    if party not in RESULT_CODES:
        raise SystemExit(f"West Virginia: a party in the results that is not read ({party!r}, {t})")
    return race, RESULT_CODES[party]


def circuit_of(text):
    """The judicial place of a May judicial contest ("... CIRCUIT COURT JUDGE - UNEXPIRED TERM, 7th"), or None."""
    m = re.search(r"(CIRCUIT|FAMILY) COURT JUDGE - UNEXPIRED TERM, (\d+)(?:st|nd|rd|th)$", re.sub(r"\s+", " ", text).strip())
    return f"{STATE}-{'CC' if m.group(1) == 'CIRCUIT' else 'FC'}{int(m.group(2))}" if m else None


# ---------------------------------------------------------------- the primary results

PLACEHOLDER = "no candidate filed"
COURT = re.compile(r"COURT JUDGE", re.I)


def primary_votes(detail, summary, meta):
    """({(race, code): (field, placeholders)}, {race or judicial place: {county names}}) for every state legislative
    party primary: field is [(name as reported, votes)]. Every check is made; nothing but names and votes is read."""
    if meta["election"] != "2026 Primary" or meta["date"] != "5/12/2026":
        raise SystemExit(f"West Virginia: the results site is for {meta['election']} {meta['date']}, not the 2026 primary")
    behind = {c: s for c, s in meta["counties"].items() if s not in DONE.values()}
    if len(meta["counties"]) != 55 or behind:
        raise SystemExit(f"West Virginia: not every county has completely reported ({len(meta['counties'])} counties; {behind})")
    root = ET.fromstring(zipfile.ZipFile(detail).read("detail.xml"))
    if root.findtext("ElectionName") != "2026 Primary" or root.findtext("ElectionDate") != "5/12/2026":
        raise SystemExit("West Virginia: the detail report is not the 2026 primary's")
    out, counties = {}, {}
    for c in root.findall("Contest"):
        text = c.get("text", "")
        key = contest_of(text)
        place = circuit_of(text)
        if key is None and place is None:
            continue
        taking_part = {cc.get("name") for cc in c.findall("ParticipatingCounties/County") if int(cc.get("precinctsParticipating") or 0) > 0}
        counties.setdefault(key[0] if key else place, set()).update(taking_part)
        if key is None:
            continue
        if c.get("precinctsReported") != c.get("precinctsParticipating") or c.get("countiesReported") != c.get("countiesParticipating"):
            raise SystemExit(f"West Virginia: {text} is not completely reported in the detail report")
        if c.get("voteFor") != "1":
            raise SystemExit(f"West Virginia: {text} votes for {c.get('voteFor')}, not one")
        field, empty = [], 0
        for ch in c.findall("Choice"):
            total = int(ch.get("totalVotes"))
            by_type = sum(int(vt.get("votes")) for vt in ch.findall("VoteType"))
            by_county = sum(int(cc.get("votes")) for vt in ch.findall("VoteType") for cc in vt.findall("County"))
            if by_type != total or by_county != total:
                raise SystemExit(f"West Virginia: a choice's votes in {text} do not add up ({total}, by type {by_type}, by county {by_county})")
            name = re.sub(r"\s+", " ", ch.get("text", "")).strip()
            if fold(name) == PLACEHOLDER:
                if total:
                    raise SystemExit(f"West Virginia: {text}'s \"no candidate filed\" line carries {total} votes")
                empty += 1
                continue
            if re.search(r"write[- ]?in", name, re.I):
                raise SystemExit(f"West Virginia: {text} reports write-in votes; read how they are reported")
            if RESULT_CODES.get(ch.get("party")) != key[1]:
                raise SystemExit(f"West Virginia: a candidate of {text} is reported under the party {ch.get('party')}")
            field.append((name, total))
        if key in out:
            raise SystemExit(f"West Virginia: {text} appears twice in the detail report")
        out[key] = (field, empty)
    # control: the summary report gives the same totals
    rows = list(csv.reader(io.StringIO(zipfile.ZipFile(summary).read("summary.csv").decode("utf-8-sig", "replace"))))
    head = rows[0]
    ci, ni, vi = head.index("contest name"), head.index("choice name"), head.index("total votes")
    seen = {}
    for r in rows[1:]:
        if not r:
            continue
        key = contest_of(re.sub(r" \(Vote For \d+\)$", "", r[ci]))
        if key and fold(r[ni]) != PLACEHOLDER:
            seen.setdefault(key, {})[fold(r[ni])] = int(r[vi])
    for key, (field, _e) in out.items():
        if {fold(n): v for n, v in field} != seen.get(key, {}):
            raise SystemExit(f"West Virginia: the summary report's totals for {key} differ from the detail report's")
    if {k for k, (f, _e) in out.items() if f} != set(seen):
        raise SystemExit("West Virginia: the summary and detail reports list different state legislative contests")
    return out, counties


# ---------------------------------------------------------------- who holds each seat

def roster(path=ROSTER):
    """Sitting legislators: id, chamber, district, names, party and start date only."""
    if not os.path.exists(path):
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "start"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, term_start "
        "FROM legislators WHERE is_current = 1 AND state = 'WV'")]
    con.close()
    return members


def letters(text):
    """Letters only, no spaces: J.B. Akers and JB AKERS are the same letters."""
    return fold(text).replace(" ", "")


def name_fits(name, person):
    """The family name the same and one given name that fits, any of the ballot's given names (FREDERICK "HAPPY" JOE
    PARSONS for Joe Parsons, D.R. BUCK JENNINGS for Buck Jennings) or its initials run together (JB for J.B.)."""
    given, family = name_parts(name)
    initials = "".join(w for w in given if len(w) == 1)
    tries = [given] + [[w] for w in given[2:]] + ([[initials]] if len(initials) > 1 else [])
    for reg in (([w for w in fold(person["first"]).split()], " ".join(fold(person["last"]).split())), name_parts(person["full"])):
        reg_given = reg[0] + ([reg[0][0] + reg[0][1]] if len(reg[0]) > 1 and all(len(w) == 1 for w in reg[0][:2]) else [])
        if any(fits((g, family), (reg_given, reg[1])) for g in tries):
            return True
    return False


def one_fit(name, people):
    """The one person the name fits, else None."""
    hits = [p for p in people if name_fits(name, p)]
    return hits[0] if len(hits) == 1 else None


def mid_term(member):
    """True when the roster's start date is not the beginning of a term (1 December of an even year, or the first two
    weeks of January after it, where the roster gives the session's opening instead)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", member["start"] or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return not ((y % 2 == 0 and mo == 12 and d == 1) or (y % 2 == 1 and mo == 1 and d <= 14))


# ---------------------------------------------------------------- counties

def county_codes(path=COUNTY_ZIP):
    """{folded county name: (GEOID, "Barbour County")} for West Virginia from the Census Bureau's cartographic file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 55:
        raise SystemExit(f"West Virginia: the county file gives {len(out)} counties, not 55")
    return out


# ---------------------------------------------------------------- county, school board and town offices (the local pass)

def slug(text):
    """Lower-case letters and digits joined by hyphens, for race ids."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def count_word(n):
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}.get(n, str(n))


def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def post_bytes(url, payload, accept):
    """One POST with the same honest User-Agent, returning the bytes as they arrive. The host leaves its issuer's
    certificate out of the handshake; this repairs that the way states/net.get does, and no less strictly."""
    req = Request(url, data=json.dumps(payload).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/json", "Accept": accept})
    try:
        with urlopen(req, timeout=120) as r:
            return r.read()
    except URLError as e:
        if getattr(getattr(e, "reason", None), "verify_code", None) != 20:   # 20: the server left out its issuer's certificate
            raise
        ctx = net._context_with_issuer(req.host)
        if ctx is None:
            raise
        with urlopen(req, timeout=120, context=ctx) as r:
            return r.read()


def export_bytes(tab, say):
    """The listing's CSV export of one tab at the county level, or None when the service does not give it: the first
    try and at most two more, then the host is left alone."""
    payload = {"candidateType": tab, "electionName": ELECTIONS["general"][0], "officeDescription": [LOCAL_LEVEL]}
    for attempt in range(3):
        try:
            return post_bytes(EXPORT, payload, "text/csv, */*")
        except (URLError, OSError) as e:
            say(f"      the candidate list's export did not answer ({type(e).__name__} {getattr(e, 'code', '')}); try {attempt + 1} of 3")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    return None


def cut_export(raw, tab):
    """The export's rows cut down, as they are parsed, to the cells named in LOCAL_READ, found by their headings. The
    rest of each row (legal name, city, state, residence county, mailing address, filing date, telephone, e-mail) is
    dropped here and goes nowhere else. Returns (the column names, the rows), or None when the bytes are not the
    export. A row that does not fit stops the loader, which names the row number and the check, never the row."""
    table = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    head = [h.strip() for h in table[0]] if table else []
    if any(head.count(c) != 1 for c in LOCAL_READ.values()):
        return None
    idx = {k: head.index(c) for k, c in LOCAL_READ.items()}
    rows = []
    for n, cells in enumerate(table[1:], 2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) != len(head):
            raise SystemExit(f"West Virginia: row {n} of the county-level export (tab {tab}) has {len(cells)} cells, not the "
                             f"heading's {len(head)}; stopping (the row is not printed)")
        row = {k: re.sub(r"\s+", " ", cells[i]).strip() for k, i in idx.items()}
        if not row["name"] or not row["race"] or not row["county"]:
            raise SystemExit(f"West Virginia: row {n} of the county-level export (tab {tab}) lacks a name, an office or a county; "
                             "stopping (the row is not printed)")
        row["tab"], row["row"] = tab, n
        rows.append(row)
    del table
    return head, rows


def office_of(text):
    """("COUNTY COMMISSION", True) for "COUNTY COMMISSION - UNEXPIRED"; ("MAYOR", False) for "MAYOR"."""
    t = re.sub(r"\s+", " ", text or "").strip().upper()
    m = re.fullmatch(r"(.+?) - UNEXPIRED", t)
    return (m.group(1), True) if m else (t, False)


def crowded(rows):
    """{party: how many} for the parties with more than one candidate on the Regular tab among these rows. A party
    nominates one candidate a seat, so this means more than one seat, or a fault in the list."""
    n = collections.Counter(r["party"] for r in rows if r["tab"] == "R" and r["party"] in PARTY_LINES)
    return {p: k for p, k in n.items() if k > 1}


DISTRICT_WORDS = re.compile(r"\b(MAGISTERIAL|DISTRICT|DISTRIC|DISTRI|DISTR|DIST|DIS)\b\.?", re.I)


def district_key(text):
    """Letters and digits with the kind word set aside: HARPERS FERRY and HARPERS FERRY DIST are the same district."""
    return re.sub(r"[^a-z0-9]+", "", DISTRICT_WORDS.sub(" ", text or "").lower())


def site_heading(settings):
    """The heading a results page shows ("Official Results"), as ballot/lists/wv.py reads the statewide page's."""
    heads = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "header" and isinstance(v, str) and v.strip():
                    heads.append(re.sub(r"<[^>]+>", "", v).strip())
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(settings)
    return heads[0] if len(set(heads)) == 1 else " / ".join(heads)


def county_pages(folder, version):
    """{county: its election number on the Secretary's results site}, from the statewide page's own list of the counties
    taking part in the May 12 primary. Kept on disk: the primary is over."""
    path = os.path.join(folder, "wv_2026_primary_county_pages.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8")), path
    url = f"{CLARITY}{version}/json/en/electionsettings.json"
    raw = net.get(url)
    lines = unzip_json(raw)["settings"]["electiondetails"].get("participatingcounties") or []
    pages = {}
    for line in lines:
        parts = line.split("|")
        if len(parts) < 2 or not parts[1].isdigit():
            raise SystemExit("West Virginia: the results site's list of counties is not laid out as name|number|...")
        pages[parts[0]] = parts[1]
    if len(pages) != 55:
        raise SystemExit(f"West Virginia: the results site lists {len(pages)} counties, not 55")
    kept = {"url": url, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "counties": pages}
    os.makedirs(folder, exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(1)
    return kept, path


def county_results(folder, county, version, say):
    """One county's own page of the Secretary's results site for the May 12, 2026 primary: (contests, what the page says
    of itself, the file), or None when it cannot be read. contests is {contest title: [(choice, party, votes)]} from the
    page's summary report, which holds offices, candidates' names and votes and nothing else. Kept on disk."""
    key = re.sub(r"[^a-z]", "", county.lower())
    zpath = os.path.join(folder, f"wv_2026_primary_summary_{key}.zip")
    mpath = zpath[:-4] + ".json"
    try:
        if not (os.path.exists(zpath) and os.path.exists(mpath)):
            pages, _path = county_pages(folder, version)
            name = next((n for n in pages["counties"] if fold(n) == fold(county)), None)
            if not name:
                return None
            base = f"{CLARITY_WV}{name}/{pages['counties'][name]}/"
            ver = net.get(base + "current_ver.txt").decode("ascii", "replace").strip()
            if not ver.isdigit():
                return None
            time.sleep(1)
            settings = unzip_json(net.get(f"{base}{ver}/json/en/electionsettings.json"))
            time.sleep(1)
            details = settings["settings"]["electiondetails"]
            meta = {"county": name, "version": ver, "heading": site_heading(settings), "updated": settings.get("websiteupdatedat"),
                    "election": details.get("internalname"), "date": details.get("electiondate"), "url": f"{base}{ver}/reports/summary.zip"}
            net.download(meta["url"], zpath, max_age_days=0, tries=3, say=say)
            if open(zpath, "rb").read(2) != b"PK":
                os.remove(zpath)
                return None
            json.dump(meta, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        meta = json.load(open(mpath, encoding="utf-8"))
        if meta["election"] != "2026 Primary" or meta["date"] != "5/12/2026":
            return None
        table = list(csv.reader(io.StringIO(zipfile.ZipFile(zpath).read("summary.csv").decode("utf-8-sig", "replace"))))
        head = table[0]
        ci, ni, pi, vi = head.index("contest name"), head.index("choice name"), head.index("party name"), head.index("total votes")
        contests = collections.defaultdict(list)
        for r in table[1:]:
            if r:
                contests[re.sub(r"\s+", " ", r[ci]).strip()].append((re.sub(r"\s+", " ", r[ni]).strip(), r[pi].strip(), int(r[vi])))
        return dict(contests), meta, zpath
    except (URLError, OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile) as e:
        say(f"      {county} County's page of the results site could not be read ({type(e).__name__})")
        return None


COMMISSION = re.compile(r"^(?:([A-Z]{3}) FOR )?COUNTY COMMISSION(?:ER)?\b(.*?)\s*\(Vote For (\d+)\)$", re.I)


def commission_seats(contests):
    """A county's May primary contests for County Commissioner, one for each party and seat: the party, whether it is
    an unexpired term, the district the title names (if any), how many to vote for, and the field."""
    out = []
    for title, choices in contests.items():
        m = COMMISSION.match(title)
        if not m:
            continue
        rest = m.group(2)
        district = re.sub(r"\s+", " ", re.sub(r"\(?\bUNEXP\w*(\s+TERM)?\)?", " ", rest, flags=re.I)).strip(" -,")
        out.append({"party": TITLE_PARTY.get((m.group(1) or "").upper(), ""), "unexpired": bool(re.search(r"UNEXP", rest, re.I)),
                    "district": district, "vote_for": int(m.group(3)),
                    "field": sorted(((n, v) for n, _p, v in choices if fold(n) != PLACEHOLDER), key=lambda nv: -nv[1])})
    return out


def seat_districts(rows, seats):
    """{district key: the district in plain words} when the county's primary put the office to the voters as separate
    seats named by district, and the list's district for every candidate is one of them with no party twice in a
    district; else None. Only then is a commission candidate's magisterial district the seat's name."""
    named = {district_key(s["district"]) for s in seats if s["district"]} - {""}
    if len(named) < 2 or any(not s["district"] for s in seats):
        return None
    out = {}
    for r in rows:
        k = district_key(r["place"])
        if k not in named:
            return None
        out[k] = proper(re.sub(r"\s+", " ", DISTRICT_WORDS.sub(" ", r["place"])).strip().upper()) + " District"
    if any(crowded([r for r in rows if district_key(r["place"]) == k]) for k in out):
        return None
    return out


def local_list(folder, version, say, max_age_days=2):
    """The county-level rows of the November list, both tabs, cut down to what this loader may read and kept on disk
    as JSON (asked afresh after two days). Returns (the kept rows and what is known of the files, the path), or
    (None, path) when the service gives nothing and there is no copy on disk."""
    path = os.path.join(folder, "wv_2026_local_general_list.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8")), path
    net.patient_lookups()
    files, rows = {}, []
    for tab in ("R", "W"):
        raw = export_bytes(tab, say)
        cut = cut_export(raw, tab) if raw is not None else None
        if cut is None:
            if os.path.exists(path):
                say("      the candidate list's county-level export could not be read; the copy on disk is used")
                return json.load(open(path, encoding="utf-8")), path
            return None, path
        files[tab] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "rows": len(cut[1]), "columns": cut[0]}
        del raw
        rows += cut[1]
        time.sleep(1.5)

    # a row entered twice (every cell read is the same) is kept once
    seen, kept, twice = set(), [], []
    for r in rows:
        key = tuple(r[k] for k in ("tab", "race", "county", "circuit", "division", "name", "party", "place"))
        if key in seen:
            twice.append({"race": r["race"], "county": r["county"]})
            continue
        seen.add(key)
        kept.append(r)

    # a commission candidate's magisterial district becomes the seat's district only where the county's own primary
    # contests were titled by district (see seat_districts); everywhere else it is where the candidate lives, and goes
    groups = collections.defaultdict(list)
    for r in kept:
        if office_of(r["race"])[0] == "COUNTY COMMISSION":
            groups[(r["county"], r["race"])].append(r)
    for (county, title), rs in sorted(groups.items()):
        if not crowded(rs):
            continue
        got = county_results(folder, county, version, say)
        seats = [s for s in commission_seats(got[0]) if s["unexpired"] == office_of(title)[1]] if got else []
        names = seat_districts([r for r in rs if r["tab"] == "R"], seats)
        for r in rs:
            r["district"] = (names or {}).get(district_key(r["place"]), "")
    for r in kept:
        place = r.pop("place")
        if office_of(r["race"])[0] in LOCAL_TOWN:
            r["town"] = place                        # a town office: the town's name, a ward or a term, as the list has it
    out = {"election": ELECTIONS["general"][0], "url": SITE, "service": EXPORT, "level": LOCAL_LEVEL,
           "fetched": dt.date.today().isoformat(), "read": list(LOCAL_READ.values()), "files": files, "entered_twice": twice, "rows": kept}
    os.makedirs(folder, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {ELECTIONS['general'][0]}: {files['R']['rows']} regular and {files['W']['rows']} write-in rows at the COUNTY level"
        + (f"; {len(twice)} entered twice" if twice else ""))
    return out, path


def census_places(folder, say):
    """West Virginia's incorporated places from the Census Bureau's 2020 place codes file: code, name with its kind
    word ("Pax town"), and the counties each lies in. The file holds places only and is kept whole."""
    path = os.path.join(folder, "st54_wv_place2020.txt")
    net.download(PLACE_URL, path, max_age_days=3650, tries=3, say=say)
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            cells = line.rstrip("\r\n").split("|")
            if n == 1:
                if cells != PLACE_HEAD:
                    raise SystemExit("West Virginia: the Census place file's heading is not the one this loader was checked against")
                continue
            if len(cells) != len(PLACE_HEAD):
                raise SystemExit(f"West Virginia: line {n} of the Census place file has {len(cells)} cells")
            if cells[5] == "INCORPORATED PLACE":
                out.append({"fp": cells[2], "name": cells[4], "counties": [c.strip() for c in cells[8].split("~~~")]})
    return out, path


def town_of(text, county_label, places):
    """(the place, whether a compass letter was spelled out) for the town a list row names, or None. The words must be
    the whole name of exactly one incorporated place of that county: "TOWN OF PAX" is Pax town, "COWEN" is Cowen town,
    and a leading compass letter is read as the word ("TOWN N. HILLS" is North Hills town). A ward, a term or an empty
    cell names no town."""
    t = re.sub(r"^(TOWN|CITY|VILLAGE)( OF)? ", "", re.sub(r"\s+", " ", text or "").strip().upper())
    here = [p for p in places if county_label in p["counties"]]

    def same(words):
        key = letters(words)
        out = []
        for p in here:
            bare = re.sub(r" (city|town|village|corporation)$", "", p["name"])
            inside = re.search(r"^(.*?) \((.*?)\)$", bare)
            if key and key in {letters(bare)} | ({letters(inside.group(1)), letters(inside.group(2))} if inside else set()):
                out.append(p)
        return out

    hit = same(t)
    if len(hit) == 1:
        return hit[0], False
    m = re.match(r"^([NSEW])\.? (.+)$", t)
    if m and not hit:
        hit = same({"N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST"}[m.group(1)] + " " + m.group(2))
        if len(hit) == 1:
            return hit[0], True
    return None


def school_districts(folder, geo, say):
    """{county GEOID: (the district's Census GEOID, its name as the Census Bureau writes it)}: a West Virginia school
    district is its county (W. Va. Code 18-1-1), and the Bureau's file names all 55."""
    import shapefile                                   # pyshp
    path = os.path.join(folder, "tl_2024_54_unsd.zip")
    net.download(UNSD_URL, path, max_age_days=3650, tries=3, say=say)
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        name = str(rec["NAME"]).strip()
        m = re.fullmatch(r"(.+?)(?: County)? School District", name)
        hit = geo.get(fold(m.group(1))) if m else None
        if not hit or hit[0] in out:
            raise SystemExit("West Virginia: a school district in the Census file is not one county's")
        out[hit[0]] = (str(rec["GEOID"]), name)
    if len(out) != 55:
        raise SystemExit(f"West Virginia: the Census school district file gives {len(out)} districts, not 55")
    return out, path


def seat_note(rows, seats, official, shown):
    """What a reader is told when the list shows more than one candidate of a party under one county commission
    office: the office is filled several at a time (the primary's own "Vote For" number), or the list does not explain
    it and the primary's result is given."""
    many = crowded(rows)
    seats = [s for s in seats if not s["district"]]
    votes_for = {s["vote_for"] for s in seats}
    if seats and len(votes_for) == 1 and min(votes_for) >= 2 and max(many.values()) <= min(votes_for):
        n = min(votes_for)
        return f"Voters choose {n}. The official results of the May 12 primary put this office to the voters as \"Vote For {n}\".", n
    out = []
    for party, k in sorted(many.items()):
        mine = [s for s in seats if s["party"] == party]
        said = f"The Secretary of State's list shows {count_word(k)} {proper(party)} candidates under this office"
        if len(mine) != 1:
            out.append(said + " and does not say whether more than one seat is on the ballot.")
            continue
        n, field = mine[0]["vote_for"], mine[0]["field"]
        said += f", but the May 12 primary was for {count_word(n)} seat{'s' if n > 1 else ''} (the official results say \"Vote For {n}\")."
        clear = official and (len(field) <= n or field[n - 1][1] > field[n][1])

        def among(name, people):                      # the same letters, or the same family name and a given name that fits
            return any(letters(name) == letters(p) or fits(name_parts(name), name_parts(p)) for p, _v in people)
        facts = []
        for r in rows:
            if r["tab"] == "R" and r["party"] == party:
                facts.append((0, f"{shown(r['name'])} won that primary") if clear and among(r["name"], field[:n]) else
                             (1, f"{shown(r['name'])} ran in that primary") if among(r["name"], field) else
                             (2, f"{shown(r['name'])} was not in it"))
        out.append(f"{said} {'; '.join(text for _i, text in sorted(facts))}. The list does not say whether another seat, such as an "
                   "unexpired term, is on the ballot.")
    return " ".join(out), None


def local_rows(folder, geo, version, shown, say):
    """The local pass: county offices, county boards of education and town offices from the listing's county level.
    Returns the rows for sl_races, sl_candidates, sl_places, sl_sources, sl_gaps and sl_notes, and what to report."""
    races, cands, places, sources, gaps, notes, checks = {}, [], {}, [], [], [], []
    stats = collections.Counter()
    by_fips = {geoid: label for geoid, label in geo.values()}
    calendar = (STATE, "local_calendar",
                "On November 3, 2026 every West Virginia county elects a county commissioner, and voters fill any unexpired terms of county "
                "clerk, circuit clerk, prosecuting attorney, sheriff, assessor, magistrate and county board of education; some cities and "
                "towns elect their officers that day too. Full terms of sheriff, prosecuting attorney, assessor and surveyor are elected "
                "in presidential years and both clerks every six years (all next in 2028), while magistrates (next in 2028), county boards "
                "of education and conservation district supervisors are elected on the nonpartisan ballot at the May primary, held May 12 "
                "this year. Other cities and towns voted with the May primary or vote on their own dates (the Secretary of State publishes "
                "calendars for town elections on June 2 and June 9, 2026); state law has every one of them move to a statewide primary or "
                "general election day by July 1, 2032.",
                "W. Va. Code sections 3-1-17, 18-5-1b, 18-5-2, 19-21A-6, 3-1-31 and 8-5-5 (West Virginia Legislature); the Secretary of "
                "State's 2026 municipal election calendars", CODE_URL)

    def gap(scope, place_id, place, what, reason):
        gaps.append((STATE, scope, place_id, place, what, reason, SITE))

    def done(coverage):
        notes.extend([calendar, (STATE, "local_coverage", coverage,
                                 "West Virginia Secretary of State, 2026 General Candidate Listing (county-level offices)", SITE)])
        return {"races": [], "cands": cands, "places": [], "sources": sources, "gaps": gaps, "notes": notes, "checks": checks, "stats": stats}

    lst, lpath = local_list(folder, version, say) if geo else (None, None)
    if lst is None:
        why = ("The Secretary of State's candidate list did not give its county-level rows when this was loaded, so no county, school "
               "board or town race could be read from it." if geo else
               "The Census Bureau's county file was not on this machine when this was loaded, so the list's counties could not be coded.")
        gap("state", STATE, NAME, "county, school board and town races", why)
        return done("Nothing is loaded yet for county, school board or town races: " + why[0].lower() + why[1:])

    rows = lst["rows"]
    stats["rows in"] = sum(f["rows"] for f in lst["files"].values())
    stats["entered twice"] = len(lst["entered_twice"])
    towns = schools = ppath = spath = None
    try:
        towns, ppath = census_places(folder, say)
    except (URLError, OSError) as e:
        checks.append(f"the Census place list could not be fetched ({type(e).__name__}); town offices are left out")
    try:
        schools, spath = school_districts(folder, geo, say)
    except (URLError, OSError, zipfile.BadZipFile) as e:
        checks.append(f"the Census school district file could not be fetched ({type(e).__name__}); boards of education are left out")
    results = {}

    def primary(county):
        """A county's own May primary results page, read once ("BERKELEY" and "Berkeley" are one county)."""
        if fold(county) not in results:
            results[fold(county)] = county_results(folder, county, version, say)
        return results[fold(county)]

    def race(rid, row, **fields):
        if rid not in races:
            races[rid] = dict(fields, race_id=rid, rows=[], labels=set())
        elif any(races[rid][k] != v for k, v in fields.items()):
            raise SystemExit(f"West Virginia: two different contests share the race key {rid}")
        races[rid]["rows"].append(row)
        races[rid]["labels"].add(office_of(row["race"])[1])
        return races[rid]

    # a county whose commission seats are named by district: a candidate the list gives no such district cannot be placed
    split = {(r["county"], r["race"]) for r in rows if r.get("district")}
    no_district = collections.Counter((r["county"], r["race"]) for r in rows if (r["county"], r["race"]) in split and not r.get("district"))
    for county, _title in sorted(split):
        primary(county)                                 # the page that named the seats is one of this load's sources

    town_rows, unknown = collections.defaultdict(list), collections.Counter()
    for r in rows:
        if (r["county"], r["race"]) in split and not r.get("district"):
            continue
        base, unexp = office_of(r["race"])
        hit = geo.get(fold(r["county"]))
        if not hit:
            raise SystemExit(f"West Virginia: row {r['row']} of the county-level list (tab {r['tab']}) names a county the Census file "
                             "does not have; stopping (the row is not printed)")
        fips, clabel = hit
        seat = join(f"Division {r['division']}" if r["division"] else None, r["circuit"] or None)
        if base in LOCAL_COUNTY:
            kind, title, partisan = LOCAL_COUNTY[base]
            district = r.get("district") or None
            rid = "-".join(x for x in (f"2026-{STATE}-{fips}", slug(kind), slug(district), slug(seat), "S" if unexp else "") if x)
            race(rid, r, level="county", office_kind=kind, office=title, jurisdiction=clabel, jurisdiction_id=fips, county_ids=[fips],
                 district=district, seat=seat, special=1 if unexp else 0, partisan=partisan, base=base, county=r["county"])
        elif base in LOCAL_SCHOOL:
            if not schools:
                stats["not placed: no school district list"] += 1
                continue
            kind, title = LOCAL_SCHOOL[base]
            geoid, sname = schools[fips]
            sid = f"{STATE}-S-{geoid}"
            rid = "-".join(x for x in (f"2026-{sid}", slug(kind), slug(seat), "S") if x)
            race(rid, r, level="school", office_kind=kind, office=title, jurisdiction=sname, jurisdiction_id=sid, county_ids=[fips],
                 district=None, seat=seat, special=1, partisan=0, base=base, county=r["county"])
            places[("school", sid)] = (sname, [fips], SRC_SCHOOLS)
        elif base in LOCAL_TOWN:
            town_rows[fips].append(r)
        else:
            unknown[base] += 1

    # town offices: a county's are loaded only when every one of its town rows names its town
    named_towns = {}
    for fips, rs in sorted(town_rows.items()):
        clabel = by_fips[fips]
        hits = [town_of(r.get("town"), clabel, towns) if towns else None for r in rs]
        offices = and_list(sorted({LOCAL_TOWN[office_of(r["race"])[0]][1].lower() for r in rs}))
        if not all(hits):
            found = sorted({h[0]["name"] for h in hits if h})
            stats["not placed: town not named" if towns else "not placed: no list of towns"] += len(rs)
            n = len(rs)
            if not towns:
                why = (f"The Secretary of State's list files {n} candidate{'s' if n != 1 else ''} for {offices} under {clabel}, but the Census "
                       "Bureau's list of towns could not be fetched to place them.")
            elif found:
                why = (f"The Secretary of State's list files {n} candidates for {offices} under {clabel} but names the town for only "
                       f"{sum(1 for h in hits if h)} of them ({and_list(found)}); the others carry a ward, a term or nothing where the town "
                       "should be, so the list cannot say which town each is running in, and none of the county's town races is shown. "
                       "The county's sample ballots will show them.")
            else:
                why = (f"The Secretary of State's list files {n} candidate{'s' if n != 1 else ''} for {offices} under {clabel} without "
                       "naming the town for any of them, so it cannot say which town each is running in. The county's sample ballots "
                       "will show them.")
            gap("county", fips, clabel, "city and town races", why)
            continue
        for r, (place, spelled_out) in zip(rs, hits):
            base, unexp = office_of(r["race"])
            kind, title = LOCAL_TOWN[base]
            pid = f"{STATE}-M-{place['fp']}"
            cids = sorted({geo[fold(re.sub(r" County$", "", c))][0] for c in place["counties"]} | {fips})
            seat = join(f"Division {r['division']}" if r["division"] else None, r["circuit"] or None)
            rid = "-".join(x for x in (f"2026-{pid}", slug(kind), slug(seat), "S" if unexp else "") if x)
            rc = race(rid, r, level="city", office_kind=kind, office=title, jurisdiction=place["name"], jurisdiction_id=pid, county_ids=cids,
                      district=None, seat=seat, special=1 if unexp else 0, base=base)
            if spelled_out:
                rc["town_words"] = r["town"]
            places[("mcd", pid)] = (place["name"], cids, SRC_PLACES)
            named_towns[pid] = place["name"]

    # counties with no commission candidate on the list
    have = {rc["jurisdiction_id"] for rc in races.values() if rc["office_kind"] == "county_commissioner" and not rc["special"]}
    for fips in sorted(set(by_fips) - have):
        clabel = by_fips[fips]
        got = primary(re.sub(r" County$", "", clabel))
        ran = sorted({proper(s["party"]) for s in commission_seats(got[0]) if not s["unexpired"] and s["field"] and s["party"]}) if got else []
        gap("county", fips, clabel, "county commissioner race",
            "State law has every county elect a commissioner at each general election, "
            + (f"and the official results of the May 12 primary show {and_list(ran)} candidates for the office in {clabel}, " if ran else "")
            + f"but the Secretary of State's November list carries no candidate for County Commission {'there' if ran else 'in ' + clabel}, "
              "so the race cannot be shown yet.")
    for (county, title), n in sorted(no_district.items()):
        hit = geo[fold(county)]
        stats["not placed: no district"] += n
        gap("race", f"2026-{STATE}-{hit[0]}-county-commissioner" + ("-S" if office_of(title)[1] else ""), hit[1],
            f"{count_word(n)} candidate{'s' if n != 1 else ''} for county commissioner",
            f"{hit[1]} elects its commissioners to seats named by district, and the Secretary of State's list gives no district that "
            f"matches one for {count_word(n)} of its candidates, who cannot be placed in a race.")
    if stats["not placed: no school district list"]:
        n = stats["not placed: no school district list"]
        gap("state", STATE, NAME, "county board of education races",
            f"The Secretary of State's list files {n} candidate{'s' if n != 1 else ''} for county boards of education, but the Census "
            "Bureau's list of school districts could not be fetched when this was loaded, so they could not be filed under their districts.")
    for title, n in sorted(unknown.items()):
        stats["not placed: office not known"] += n
        gap("state", STATE, NAME, f"{title.lower()} races",
            f"The Secretary of State's list files {n} candidate{'s' if n != 1 else ''} under the county-level office \"{title}\", "
            "a title this loader has not been taught to read, so they are not shown.")
        checks.append(f"an office title the local pass does not know: {title!r} ({n} rows)")

    # the races, their notes and their candidates
    race_rows = []
    for rid, rc in sorted(races.items()):
        listed = rc["rows"]
        regular = [r for r in listed if r["tab"] == "R"]
        if "partisan" not in rc:                        # a town office: as the list's own rows have it
            flags = {r["party"] == "NON-PARTISAN" for r in regular} or {False}
            rc["partisan"] = 0 if flags == {True} else 1
            if len(flags) > 1:
                checks.append(f"{rid}: the list gives some candidates a party and others none")
        note = [f"The Secretary of State's list writes the town as \"{rc['town_words']}\"."] if rc.get("town_words") else []
        if rc["level"] == "county" and rc["district"]:
            note.append(f"{rc['jurisdiction']} elects its commissioners to seats named for its magisterial districts, as the official "
                        "results of the May 12 primary title them; this is one of them.")
        many = crowded(listed)
        if many and rc["base"] == "COUNTY COMMISSION":
            got = primary(rc["county"])
            seats = [s for s in commission_seats(got[0]) if s["unexpired"] == bool(rc["special"])] if got else []
            said, chosen = seat_note(listed, seats, bool(got) and got[1]["heading"] == "Official Results", shown)
            note.append(said)
            if not chosen:
                checks.append(f"{rid}: more than one candidate of a party, and the May primary was not for that many seats; noted on the race")
        elif many and rc["office_kind"] != "council":
            note.append(" ".join(f"The Secretary of State's list shows {count_word(k)} {proper(p)} candidates under this office and does "
                                 "not explain it." for p, k in sorted(many.items())))
            checks.append(f"{rid}: more than one candidate of a party; noted on the race")
        if rc["level"] == "school":
            note += [NO_PARTY_PRINTED.format("County boards of education"),
                     UNEXPIRED if rc["labels"] == {True} else BOARD_TERM if rc["labels"] == {False} else BOARD_BOTH, HOW_MANY]
            if len(rc["labels"]) > 1:
                checks.append(f"{rid}: the list titles the office \"unexpired\" for some candidates and not for others; kept as one race")
        else:
            if rc["special"]:
                note.append(UNEXPIRED)
            if rc["office_kind"] == "magistrate":
                note.append(NO_PARTY_PRINTED.format("Magistrates"))
                if not rc["seat"]:
                    note.append(NO_DIVISION)
            elif not rc["partisan"]:
                note.append("The Secretary of State's list gives no party for this office.")
            if rc["office_kind"] == "council":
                note.append(HOW_MANY)
        seen = set()
        for r in listed:
            name = shown(r["name"])
            if name in seen:
                stats["same name twice in a race, kept once"] += 1
                checks.append(f"{rid}: one name is listed twice (the Regular and Write-In tabs, or two entries that differ); kept once")
                continue
            seen.add(name)
            write_in = 1 if r["tab"] == "W" else 0
            if not rc["partisan"]:
                party, code = NONPARTISAN, "N"
                if r["party"] not in ("NON-PARTISAN", ""):
                    checks.append(f"{rid}: the list gives a party on a nonpartisan office; not shown")
            elif write_in:
                party, code = (proper(r["party"]) if r["party"] else "Write-in"), "W"
            else:
                party = proper(r["party"]) if r["party"] else "No party given"
                code = party_code(party)
                if r["party"] in ("", "NON-PARTISAN"):
                    checks.append(f"{rid}: a candidate for a partisan office is listed without a party")
            cands.append((rid, "general", GENERAL, name, party, code, None, 0, write_in, None, None, None, None,
                          SRC_LOCAL_W if write_in else SRC_LOCAL, WRITE_IN if write_in else None))
            stats["placed"] += 1
        race_rows.append((rid, STATE, rc["level"], rc["office_kind"], rc["office"], rc["jurisdiction"], rc["jurisdiction_id"],
                          json.dumps(rc["county_ids"]), rc["district"], rc["seat"], rc["special"], rc["partisan"], None, None, None,
                          GENERAL, join(*note, CAPS, NO_ORDER)))

    # what was read
    f = lst["files"]
    for sid, tab, label in ((SRC_LOCAL, "R", "Regular Candidates"), (SRC_LOCAL_W, "W", "Write-In Candidates")):
        sources.append((sid, STATE, "official candidate list", "West Virginia Secretary of State",
                        f"2026 General Candidate Listing: 11/03/2026 - GENERAL 2026, county-level offices, {label} (CSV export)",
                        SITE, "", lst["fetched"], f[tab]["sha256"], f[tab]["rows"],
                        "The listing's own CSV export (candidate-web-api/candidates/export under the listing's address, a POST with the page's "
                        f"filters: the election, the office level {LOCAL_LEVEL} and the {label} tab). The fingerprint is of the file as it "
                        "arrived; the file itself is not kept. Read, by their headings: Name (the name as printed on the ballot), Party, "
                        "County, Race, District/Circuit, Division and Magisterial. Never read: Legal Name, City, State, Residence County, "
                        "MailingAddress, Filing Date, CampaignPhoneNumber and Email. The Magisterial cell is kept only where it names a "
                        "town office's place or the district a commission seat is named for; for any other candidate it is the magisterial "
                        "district the candidate lives in, and it is dropped as the file is parsed. The list gives no ballot positions and "
                        "has no status column (a candidate who withdrew is no longer listed)."
                        + (f" Rows entered twice and kept once: {len(lst['entered_twice'])}." if tab == "R" and lst["entered_twice"] else "")))
    if ppath:
        sources.append((SRC_PLACES, STATE, "official place codes", "U.S. Census Bureau",
                        "2020 place codes, West Virginia (st54_wv_place2020.txt)", PLACE_URL, "", day_of(ppath), sha_of(ppath), len(towns),
                        "Names and codes of West Virginia's incorporated places and the counties each lies in: a town the candidate list "
                        "names is matched to the one place of that name in its county. The file holds places only."))
    if spath:
        sources.append((SRC_SCHOOLS, STATE, "boundaries", "U.S. Census Bureau",
                        "TIGER/Line 2024, unified school districts, West Virginia (tl_2024_54_unsd)", UNSD_URL, "", day_of(spath),
                        sha_of(spath), len(schools),
                        "Names and codes only: West Virginia's 55 school districts are its counties, and a county board of education's "
                        "race is filed under the district as the Bureau names it."))
    read_pages = [(c, got) for c, got in sorted(results.items()) if got]
    if read_pages:
        pages, pages_path = county_pages(folder, version)
        sources.append((SRC_PAGES, STATE, "official results", "West Virginia Secretary of State",
                        "2026 Primary Election (May 12, 2026): the results site's list of the counties' own pages", pages["url"], "",
                        pages["fetched"], pages["sha256"], len(pages["counties"]),
                        "The statewide results page's settings, read only for each county's election number on the same site."))
    for county, (contests, meta, zpath) in read_pages:
        sources.append((f"wv-sos-2026-primary-summary-{slug(county)}", STATE, "official results", "West Virginia Secretary of State",
                        f"2026 Primary Election (May 12, 2026), {meta['county']} County: summary report (CSV)", meta["url"], "", day_of(zpath),
                        sha_of(zpath), len(commission_seats(contests)),
                        f"{meta['county']} County's own page of the Secretary's results site, headed \"{meta['heading']}\", version "
                        f"{meta['version']}, last updated {meta['updated']}. Read only for the County Commissioner contests: how each was put "
                        "to the voters (its title and \"Vote For\" number) and who won it, where the November list shows more than one "
                        "candidate of a party or no candidate at all. No primary votes are stored from it."))

    # the summary a reader gets
    kinds = collections.Counter(r[2] for r in race_rows)
    commission = [r for r in race_rows if r[3] == "county_commissioner" and not r[10]]
    unexpired = sum(1 for r in race_rows if r[2] == "county" and r[10])
    left = [g for g in gaps if g[1] == "county" and g[4] == "city and town races"]
    n_left = stats["not placed: town not named"] + stats["not placed: no list of towns"]
    missing = [g[3] for g in gaps if g[4] == "county commissioner race"]
    coverage = (f"Loaded from the Secretary of State's 2026 General Candidate Listing at the county level: {len(commission)} county commission "
                f"races in {len({r[6] for r in commission})} of the 55 counties, {unexpired} unexpired terms of county offices and magistrate, "
                f"{kinds['school']} county board of education race{'s' if kinds['school'] != 1 else ''}"
                + (f" and {kinds['city']} town races in {and_list(sorted(named_towns.values()))}" if kinds["city"] else "")
                + f": {stats['placed']} candidates, {sum(1 for c in cands if c[8])} of them declared write-ins. Left out: "
                + (f"{n_left} candidates for town offices that the list files under {and_list([g[3].replace(' County', '') for g in left])} "
                   f"{'counties' if len(left) != 1 else 'County'} "
                   + ("without naming the town; " if towns else "and that could not be placed in a town; ") if left else "")
                + (f"the county commission race in {and_list(missing)}, where the list has no candidate; " if missing else "")
                + "towns that are not on the Secretary's list at all; ballot questions and levies; and party committee seats. The list gives "
                  "no ballot order and no longer lists anyone who withdrew, and the magisterial district that the ballot prints beside "
                  "commission and school board candidates (it is where the candidate lives) is not shown.")
    gap("state", STATE, NAME, "city and town races that are not on the Secretary of State's list",
        "Cities and towns take their own candidate filings, and the Secretary of State's list carries town offices under "
        + (f"only {count_word(len(town_rows))} {'counties' if len(town_rows) != 1 else 'county'}" if town_rows else "no county")
        + ", so a town that votes on November 3 without appearing there is not here.")
    out = done(coverage)
    out["races"] = race_rows
    out["places"] = [(kind, pid, name, json.dumps(cids), src) for (kind, pid), (name, cids, src) in sorted(places.items())
                     if any(r[6] == pid for r in race_rows)]
    out["lpath"] = lpath
    return out


# ---------------------------------------------------------------- load

def load(db_path, say=print, cache=CACHE, roster_path=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "wv")
    gpath, ppath = os.path.join(folder, "wv_2026_sl_general_list.json"), os.path.join(folder, "wv_2026_sl_primary_list.json")
    gen = read_list("general", gpath, 2, say)           # asked afresh after two days
    pri = read_list("primary", ppath, None, say)        # the primary is over: the copy on disk is kept
    detail, summary, meta = fetch_results(folder, say)
    votes, contest_counties = primary_votes(detail, summary, meta)
    members = roster(roster_path)
    geo = county_codes() if os.path.exists(COUNTY_ZIP) else {}

    spelled = {}                                        # the roster's capitals, where its words are the same letters
    for m in members:
        for form in (m["full"], f"{m['first']} {m['last']}"):
            if form:
                spelled.setdefault(letters(form), form)

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps or "").strip()
        if letters(caps) in spelled:
            return spelled[letters(caps)]
        out = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\.", lambda m: f"{m.group(1)}.{m.group(2).upper()}.", out)   # D.R., not D.r.

    def party_of(r):
        if r["partyCode"] == "NON":
            return NONPARTISAN, "N"
        if not r["partyDescription"]:
            raise SystemExit(f"West Virginia: a candidate for {r['officeName']} with no party on the listing")
        p = proper(r["partyDescription"])
        return p, party_code(p)

    races, listed, places, problems, skipped = {}, collections.defaultdict(list), {}, [], collections.Counter()
    read = {"general": 0, "general_write_in": 0, "primary": 0}
    for r in gen["regular"] + gen["write_in"]:
        race = race_for(r)
        if race is None:
            skipped[("general", re.sub(r"\d+", "n", r["officeName"]))] += 1
            continue
        read["general_write_in" if r["candidateType"] == "W" else "general"] += 1
        rid = race["race_id"]
        if rid in races and races[rid]["office"] != race["office"]:
            raise SystemExit(f"West Virginia: two offices share the race key {rid}")
        races.setdefault(rid, race)
        listed[rid].append(r)
        places[race["place"][:2]] = race["place"]
    if gen["write_in"] and any(r["candidateType"] != "W" for r in gen["write_in"]):
        raise SystemExit("West Virginia: the Write-In tab returned a row that is not a write-in")

    filed = collections.defaultdict(dict)               # (race, code) -> {folded name: printed name}
    for r in pri["regular"]:
        race = None if COURT.search(r["officeName"] or "") else race_for(r)   # May's judicial elections: not a primary
        if race is None:
            skipped[("primary", re.sub(r"\d+", "n", r["officeName"]))] += 1
            continue
        read["primary"] += 1
        if r["partyCode"] not in LIST_CODES:
            raise SystemExit(f"West Virginia: a primary candidate for {r['officeName']} of a party that is not read ({r['partyCode']})")
        key = (race["race_id"], LIST_CODES[r["partyCode"]])
        if fold(r["candidateBallotName"]) in filed[key]:
            raise SystemExit(f"West Virginia: a name is listed twice in the {key} primary")
        filed[key][fold(r["candidateBallotName"])] = (r["candidateBallotName"], party_of(r))
        if race["race_id"] not in races:
            problems.append(f"{race['race_id']} had a May primary but is not on the November listing")
    if any(not COURT.search(r["officeName"] or "") and race_for(r) for r in pri["write_in"]):
        raise SystemExit("West Virginia: the primary listing names write-in candidates for the Legislature; read how the results report them")

    # the listing's primaries and the results' contests must be the same, candidate for candidate
    with_names = {k for k, (f, _e) in votes.items() if f}
    if with_names != set(filed):
        problems.append(f"party primaries on the listing but not in the results, or the reverse: {sorted(with_names ^ set(filed))}")
    ballots = {}                                        # (race, code) -> [(name as the listing prints it, party, votes, note)]
    extra_in_results = []
    for key in sorted(set(filed) | with_names):
        field = votes.get(key, ([], 0))[0]
        entries, used = [], set()
        for folded, (printed, (party, _pc)) in filed.get(key, {}).items():
            hit = [i for i, (n, _v) in enumerate(field) if fold(n) == folded] or \
                  [i for i, (n, _v) in enumerate(field) if fits(name_parts(printed), name_parts(n))]
            if len(hit) != 1 or hit[0] in used:
                problems.append(f"{key}: {shown(printed)} is not found once in the official results")
                entries.append((printed, party, None, None))
                continue
            used.add(hit[0])
            entries.append((printed, party, field[hit[0]][1], None))
        for i, (n, v) in enumerate(field):
            if i not in used:                           # on the ballot and counted, but no longer on the listing
                extra_in_results.append((key, n, v))
                entries.append((n, "Republican" if key[1] == "REP" else "Democrat", v,
                                "In the official results, but no longer on the Secretary of State's candidate listing."))
        ballots[key] = entries

    # who holds each seat
    def people_of(race):
        return [m for m in members if m["chamber"] == race["chamber"] and m["district"] == race["district"]] if race["chamber"] else []

    def candidates_named(rid, people):
        out = set()
        names = [r["candidateBallotName"] for r in listed.get(rid, [])]
        names += [n for (race_id, _c), d in filed.items() if race_id == rid for n, _p in d.values()]
        for n in names:
            who = one_fit(n, people)
            if who:
                out.add(who["id"])
        return out

    held = {}
    for rid, race in races.items():
        people = people_of(race)
        if race["chamber"] == "House" or not race["chamber"]:
            held[rid] = (people, None)
            continue
        unexp = f"2026-{STATE}-SS{race['district']}-UNEXP"
        mid = [m for m in people if mid_term(m)]
        if unexp in races and len(people) == 2 and len(mid) == 1:
            held[rid] = (mid if race["special"] else [m for m in people if m is not mid[0]],
                         "The unexpired seat is taken to be the one held by the district's only senator who joined mid-term, "
                         "by the roster's dates; the other senator holds the full-term seat.")
            continue
        if not race["special"] and unexp not in races:
            running = candidates_named(rid, people)
            if len(people) == 2 and len(running) == 1:
                held[rid] = ([m for m in people if m["id"] in running],
                             "The district has two senators, elected in alternate even years; the one who is a candidate "
                             "for this seat is given as its holder.")
                continue
        held[rid] = (people, "The district has two senators, elected in alternate even years, and the roster used here "
                             "does not say which of them holds the seat on this ballot, so both are given." if len(people) > 1 else None)

    # November rows
    cands, nominee = [], {}
    for rid, rows in sorted(listed.items()):
        race = races[rid]
        people = people_of(race)
        holders, why = held[rid]
        holders = sorted(holders, key=lambda m: m["last"])
        race["holder_id"] = "; ".join(m["id"] for m in holders) or None
        race["holder_name"] = "; ".join(m["full"] for m in holders) or None
        race["holder_party"] = "; ".join(m["party"] or "" for m in holders) or None
        race["note"] = join(race["note"], why, CAPS, NO_ORDER)
        if race["chamber"] and not holders:
            race["note"] = join(race["note"], "The roster used here lists nobody in this seat today.")
        cids = sorted(geo[fold(c)][0] for c in contest_counties.get(rid if race["chamber"] else race["jurisdiction_id"], ()) if fold(c) in geo)
        race["county_ids"] = json.dumps(cids) if cids else None
        seen = set()
        for r in rows:
            name = shown(r["candidateBallotName"])
            if name in seen:
                raise SystemExit(f"West Virginia: {rid} lists the same name twice")
            seen.add(name)
            who = one_fit(r["candidateBallotName"], people) if people else None
            if r["candidateType"] == "W":
                party = proper(r["partyDescription"]) if r["partyDescription"] else "Write-in"
                cands.append((rid, "general", GENERAL, name, party, "W", None, 1 if who else 0, 1, None, None, None,
                              who["id"] if who else None, SRC_GEN, WRITE_IN))
                continue
            party, code = party_of(r)
            note = None
            if race["partisan"] and r["partyCode"] in ("R", "D"):
                key = (rid, LIST_CODES[r["partyCode"]])
                nominee[key] = fold(r["candidateBallotName"])
                if fold(r["candidateBallotName"]) not in {fold(e[0]) for e in ballots.get(key, [])}:
                    note = OFF_LIST
            cands.append((rid, "general", GENERAL, name, party, code, None, 1 if who else 0, 0, None, None, None,
                          who["id"] if who else None, SRC_GEN, note))

    # the primary fields
    fields, uncontested, leaders_off, ties = 0, 0, [], []
    for key, entries in sorted(ballots.items()):
        rid, code = key
        if len(entries) < 2:
            uncontested += 1
            continue
        if rid not in races:
            continue                                    # reported above: a May primary with no November race
        fields += 1
        people = people_of(races[rid])
        complete = all(v is not None for _n, _p, v, _x in entries)
        total = sum(v for _n, _p, v, _x in entries if v is not None)
        top = max((v for _n, _p, v, _x in entries if v is not None), default=None)
        leaders = [n for n, _p, v, _x in entries if v == top] if complete else []
        if len(leaders) > 1:
            ties.append(f"{rid} {code}")
        won = nominee.get(key)
        for printed, party, v, note in sorted(entries, key=lambda e: -(e[2] if e[2] is not None else -1)):
            who = one_fit(printed, people) if people else None
            outcome = None
            if complete and len(leaders) == 1:
                outcome = "advanced" if printed == leaders[0] else "lost"
                if printed == leaders[0] and won != fold(printed):
                    note = join(note, "Not on the November list.")
                    leaders_off.append(f"{rid} {code}: {shown(printed)}")
            cands.append((rid, f"primary-{code}", PRIMARY, shown(printed), party, party_code(party), None, 1 if who else 0, 0, v,
                          round(100 * v / total, 1) if v is not None and total else None, outcome,
                          who["id"] if who else None, SRC_RES if v is not None else SRC_PRI, note))

    # CHECKS: every seat that should be on the ballot is, and every row read is stored
    senate = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate" and not r["special"])
    house = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    for label, got, want in (("State Senate", senate, range(1, 18)), ("House of Delegates", house, range(1, 101))):
        missing = [d for d in want if d not in got]
        if missing:
            problems.append(f"{label}: districts with no candidate on the November listing: {missing}")
    gen_rows = sum(1 for c in cands if c[1] == "general")
    if gen_rows != read["general"] + read["general_write_in"]:
        problems.append(f"November: {read['general'] + read['general_write_in']} rows read, {gen_rows} stored")
    pri_rows = sum(len(d) for d in filed.values())
    if pri_rows != read["primary"]:
        problems.append(f"primary: {read['primary']} rows read, {pri_rows} placed in a party primary")
    for key, n, v in extra_in_results:
        problems.append(f"{key}: the results name {shown(n)} ({v} votes), who is no longer on the Secretary of State's listing "
                        + ("(stored in the field with a note)" if len(ballots[key]) > 1 else
                           "(the only candidate, so no field is stored; not on the November listing either)"
                           if key not in nominee or nominee[key] != fold(n) else "(the only candidate, so no field is stored)"))

    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                  r.get("county_ids"), r["district"], r["seat"], r["special"], r["partisan"], r.get("holder_id"),
                  r.get("holder_name"), r.get("holder_party"), GENERAL, r["note"]) for r in races.values()]
    place_rows = []
    for (kind, pid), (_k, _i, pname) in sorted(places.items()):
        here = [r for r in races.values() if r["place"][:2] == (kind, pid)]
        race = next((r for r in here if not (r["chamber"] and r["special"])), here[0])
        place_rows.append((kind, pid, pname, race.get("county_ids"), SRC_GEN))
    for folded, (geoid, label) in sorted(geo.items(), key=lambda kv: kv[1][0]):
        place_rows.append(("county", geoid, label, json.dumps([geoid]), SRC_COUNTY))
    unknown_counties = sorted({c for cs in contest_counties.values() for c in cs if fold(c) not in geo})
    if unknown_counties:
        problems.append(f"counties in the results that the Census file does not name: {unknown_counties}")

    by_kind = collections.Counter(r["office_kind"] + ("_unexpired" if r["special"] and r["chamber"] else "") for r in races.values())
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", meta["updated"] or "")
    updated = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    write_ins = sum(1 for c in cands if c[1] == "general" and c[8])
    sources = [
        (SRC_GEN, STATE, "official candidate list", "West Virginia Secretary of State",
         "2026 General Candidate Listing: 11/03/2026 - GENERAL 2026, state races (Regular and Write-In Candidates)",
         SITE, "", day_of(gpath), sha_of(gpath), len(gen["regular"]) + len(gen["write_in"]),
         f"Read through the listing's own data service ({API}, office level {LEVEL}), every page counted against its total. "
         "Only the office, district name and division, party, name as printed on the ballot and tab are kept; e-mail, "
         "phones, addresses, town, website and committee are never read, printed or kept. The listing gives no ballot "
         "positions and no status column (a candidate who withdrew is no longer listed). It lists no statewide executive "
         "office for 2026 and no Supreme Court seat. "
         f"Declared write-ins (Write-In Candidates tab): {write_ins}."),
        (SRC_PRI, STATE, "official candidate list", "West Virginia Secretary of State",
         "2026 Candidate Listing: 05/12/2026 - PRIMARY 2026, State Senate and House of Delegates",
         SITE, "", day_of(ppath), sha_of(ppath), read["primary"],
         "Used for who was on each party's primary ballot and how the names are printed; the results' candidates must be "
         f"exactly these. The same kept fields only. Party primaries with a field (two or more candidates): {fields}; "
         f"with one candidate: {uncontested}. The May 12 ballot also carried the nonpartisan elections of the Supreme Court "
         "of Appeals, the Intermediate Court of Appeals and some circuit and family court seats, which decided those seats "
         "in May; they are not stored here. Party executive committee seats are not stored either."),
        (SRC_RES, STATE, "official results", "West Virginia Secretary of State",
         "2026 Primary Election (May 12, 2026), Official Results: detail report (XML), State Senate and House of Delegates",
         meta["detail_url"], updated, day_of(detail), sha_of(detail), sum(1 for e in ballots.values() for x in e if x[2] is not None),
         f"The Secretary's results site ({RESULTS_PAGE}, hosted by Clarity Elections), headed \"{meta['heading']}\", "
         f"version {meta['version']}, last updated {meta['updated']}. All 55 counties completely reported. Every "
         "candidate's county votes add up to the total. The report prints \"NO CANDIDATE FILED\" where a party had no "
         "candidate; those lines carry no votes and are not stored. No write-in votes are reported for these contests, "
         "so a field's total is its candidates' votes. The counties taking part in each contest give the district's "
         "county_ids."),
        (SRC_SUM, STATE, "official results", "West Virginia Secretary of State",
         "2026 Primary Election (May 12, 2026), Official Results: summary report (CSV)",
         meta["summary_url"], updated, day_of(summary), sha_of(summary), len(with_names),
         "Control: every state legislative party primary's totals here match the detail report's."),
    ]
    if geo:
        sources.append((SRC_COUNTY, STATE, "boundaries", "U.S. Census Bureau",
                        "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "",
                        day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(geo),
                        "West Virginia's 55 counties: names and GEOIDs only, to turn the results' county names into codes."))
    if members:
        sources.append((SRC_ROSTER, STATE, "roster", "Open States (people project, CC0)",
                        "West Virginia legislators serving now (state_wv.sqlite, from the Open States people project)",
                        "https://github.com/openstates/people", "", day_of(roster_path), "", len(members),
                        "Used only to say who holds each seat today and to mark incumbents: names, parties, districts and start "
                        "dates. Not an official record."))

    # the local pass: county offices, county boards of education and town offices (nothing above is changed by it)
    local = local_rows(os.path.join(folder, "local"), geo, meta["version"], shown, say)
    clash = {r[0] for r in local["races"]} & {r[0] for r in race_rows}
    if clash:
        raise SystemExit(f"West Virginia: a local race shares its key with a state race ({sorted(clash)[:3]})")

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executescript(EXTRA_SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'wv-%'")
            con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources + local["sources"])
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
            con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
            con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    finally:
        con.close()

    counts = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
    say(f"    West Virginia: {len(races)} state races on the November ballot ({counts}), {gen_rows} candidates "
        f"({write_ins} declared write-in); {fields} party primaries with a field, votes from the official results; "
        f"{sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched")
    for p in problems:
        say(f"      CHECK {p}")
    for t in ties:
        say(f"      CHECK the {t} primary is tied at the top; no outcome stored")
    for x in leaders_off:
        say(f"      note: a primary leader not on the November listing: {x}")
    st = local["stats"]
    levels = collections.Counter(r[2] for r in local["races"])
    left = {k[len("not placed: "):]: v for k, v in st.items() if k.startswith("not placed: ")}
    say(f"    West Virginia local: {len(local['races'])} races ({', '.join(f'{k} {v}' for k, v in sorted(levels.items())) or 'none'}), "
        f"{len(local['cands'])} candidates ({sum(1 for c in local['cands'] if c[8])} declared write-in), in "
        f"{len({c for r in local['races'] for c in json.loads(r[7])})} of 55 counties; {len(local['gaps'])} gaps recorded")
    say(f"      the list's county-level rows: {st['rows in']} read = {st['placed']} placed, each in one race"
        + (f" + {st['entered twice']} entered twice" if st["entered twice"] else "")
        + "".join(f" + {v} not placed ({k})" for k, v in sorted(left.items()))
        + (f" + {st['same name twice in a race, kept once']} a second copy of a name" if st["same name twice in a race, kept once"] else ""))
    if st["rows in"] != st["placed"] + st["entered twice"] + sum(left.values()) + st["same name twice in a race, kept once"]:
        say("      CHECK the county-level rows read and the rows accounted for differ")
    for c in local["checks"]:
        say(f"      CHECK {c}")
    return {"races": len(races), "candidates": gen_rows, "by_kind": dict(by_kind), "fields": fields, "uncontested": uncontested,
            "problems": problems, "ties": ties, "leaders_off": leaders_off, "read": read, "skipped": dict(skipped),
            "local_races": len(local["races"]), "local_candidates": len(local["cands"]), "local_levels": dict(levels),
            "local_gaps": len(local["gaps"]), "local_stats": dict(st), "local_checks": local["checks"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_wv <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
