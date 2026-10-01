"""
ballot/state_local_tx.py - Texas's state races on the November 3, 2026 ballot, with the March 3 party primaries and the
May 26 primary runoffs that chose the nominees, and every county's own county and precinct races on the same ballot
(see "The local rows" below), into ballot_local_2026.sqlite. The federal ballot database (ballot_2026.sqlite) is never
opened here, and U.S. Senator and U.S. Representative rows are left to the federal pages.

What is on the ballot, read from the certification itself, never assumed:
  - the Texas Senate: 16 of its 31 seats (four-year terms, staggered; in 2026 districts 1, 2, 3, 4, 5, 9, 11, 13, 18, 19,
    21, 22, 24, 26, 28 and 31);
  - the Texas House: all 150 seats (two-year terms);
  - the statewide executive offices up this year: Governor, Lieutenant Governor (elected separately), Attorney General,
    Comptroller of Public Accounts, Commissioner of the General Land Office, Commissioner of Agriculture and one
    Railroad Commissioner (the Secretary of State is appointed and is never on the ballot);
  - the State Board of Education districts up this year;
  - the courts the certification lists as state and district offices: the Supreme Court (Chief Justice and places),
    the Court of Criminal Appeals, the courts of appeals (chief justices and places), the district courts and the
    criminal district courts. Every one of these offices is partisan in Texas.
County and precinct offices, county courts, justices of the peace, district and criminal district attorneys and district
clerks are the local rows (see "The local rows" below).

Sources, all the Texas Secretary of State's own, the same files the federal loader (ballot/lists/tx.py) reads:

  Ballot Certification Report, 2026 November General Election (certified August 28, 2026; a PDF of 1,396 pages read
  with ballot/pdftext.py, from the federal loader's cached copy ballot_cache/tx_ballot_cert_2026.pdf). County by county,
  every office on that county's ballot and under it each candidate in ballot order with the party (REP, DEM, LIB, GRE,
  IND). It prints offices, names and parties only. An office heading this loader does not know stops it (the heading,
  an office title, is named). A race that spans several counties is listed once per county, and every county's list
  must agree, or the race's November candidates are left out and named. The counties that list a race are its
  county_ids (derived, and said so).

  Official Canvass Reports of the March 3, 2026 Republican and Democratic primaries and the May 26, 2026 runoffs, from
  the Secretary of State's election results system (goelect.txelections.civixapps.com), each marked official there;
  the four PDFs are the federal loader's cached copies in ballot_cache/tx/. Per office: each candidate's name as on the
  ballot (with "(I)", the report's incumbent mark), party, canvass votes and percent, then a Total line. Every Total
  line must equal its candidates' sum and every printed percent must match. An office heading may run onto a second
  line (PLACE 3, DISTRICT 2, - UNEXPIRED TERM) and a long name onto a second line; both are joined.
  The same system's election records (/api-ivis-system/api/s3/enr/election/<id>) carry each election's StateWide and
  Districted races; only race name, total, and each candidate's name, party and votes are kept (as JSON, in
  tx_2026_state_results_records.json), and their figures must equal the canvass report's, race by race.

  A field is a party primary with two candidates or more. A nominee needs a majority; a candidate with one advanced.
  Otherwise the two with the most votes met in the May 26 runoff: both advanced (noted), and the runoff, stored as its
  own election (runoff-REP, runoff-DEM), was won by the one with more votes. The runoff's pair must be the primary's top
  two. Where no one had a majority and the runoff canvass has no contest for the nomination, the leader advanced only
  if the November certification names the leader and not the runner-up, and both rows say so. Each nominee must be the
  party's candidate on the November certification; where not, the row says so plainly.

  Who holds each seat: the Open States roster in state_tx.sqlite (legislators with is_current = 1 by chamber and
  district; the officials table for Governor, Lieutenant Governor and Attorney General). Only id, name, party, chamber,
  district and office are selected. A candidate is the sitting member only when the name fits the roster's holder of
  that same seat and every fitting name in the race is the same person. For the offices the roster does not carry
  (the other statewide offices, the State Board of Education and the courts) the canvass's own incumbent mark "(I)" is
  used for the incumbent flag, with no member id, and the race says so. For seats the roster does carry, the canvass
  marks are compared with the roster and every difference is printed.

  County codes: the Census Bureau's 2024 county file (states_cache/census/cb_2024_us_county_500k.zip), names and GEOIDs.

Privacy. None of these files carries an address, telephone, e-mail, website or treasurer (checked: every line of the
certification is a header, a county, an office or "NAME PARTY"). Only office, district, name, party, ballot order,
votes and the incumbent mark are read; nothing is printed but counts, race keys and office titles; and before anything
is written every stored name and note is checked for anything that looks like a contact detail. (The Secretary's
candidate list, which the local rows use as a second source, does carry contact columns: see below how it is cut down.)

Names are printed in capitals and shown in ordinary capitals (a sitting member as the roster spells the name).

The local rows (levels county and other), from the same certification
----------------------------------------------------------------------
Under every county the certification also prints that county's own ballot: the county judge, the judges of the county
courts at law and probate courts, district clerk, county clerk (or the two as one office), county treasurer, county
surveyor, county commissioners, justices of the peace, constables, the unexpired terms of a sheriff, county attorney or
tax assessor-collector, Harris County's school trustees, and the criminal district attorneys and district attorneys.
Each is a heading followed by "NAME PARTY" lines, exactly like the state offices; every one is elected on party lines.
The Secretary's cover certifies the candidates for state and district offices; it does not say who certified the
county and precinct names printed in the same report, and the coverage note says so. A page never ends in the middle
of a contest (the state part stops if one does); a heading printed twice in one county would be left out and written to
the gaps, and a heading with no candidate under it kept with a note (neither occurs in the August 28 report).

  levels        county for an office of one county (jurisdiction_id the county's 5-digit code): county and precinct
                offices, the county's own courts, a criminal district attorney, Harris County's school trustees.
                other for an office several counties vote on: a district attorney (the place is the judicial district,
                TX-X-JD<number>) and a multicounty court at law (TX-X-multicounty-court-at-law-<number>); both are
                sl_places rows of kind special, with every county whose list prints the contest. A contest printed
                under several counties is one race, and every county's copy must agree or it is left out and written
                to sl_gaps. These offices are filed here, not under level court, because they are not among the court
                rows this loader already wrote (the Supreme Court down to the district courts), which stay as they are.
  race ids      2026-TX-<county code>-<the heading in small letters and hyphens>[-S];
                2026-TX-X-JD<number>-district-attorney[-S]; 2026-TX-X-multicounty-court-at-law-<number>-judge[-S].
                -S marks an unexpired term (special = 1).
  district      as the list words it: "Precinct 2", "Precinct 2 & 6", "No. 1"; seat: "Place 2", a court's "No. 3".
  ballot order  the list's own order, kept only where it is the order of the party columns (Election Code 52.091:
                Republican, Democratic, Libertarian, Green by the last vote for governor, then independents) with no
                two candidates under one label; otherwise none is stored and the report says which contest.
  names         in ordinary capitals, as the state rows (and two slips of that put right: D'Ann, not D'ann; a nickname
                in quotes starts with a capital). No local candidate is matched to any roster, and none carries a
                holder, a member id or an incumbent mark.

The Secretary of State's candidate list (the same system, live): its Candidate Information page asks one service for
every candidate of the November election, and this loader asks it the same question once, with the same honest
User-Agent. The answer carries contact columns (mailing address, e-mail, website) and an occupation, so it is cut down
in memory, before anything else touches it, to nine cells a row (office type, office number, county, office title,
the name as on the ballot, party, the two status codes and the kind of candidate), and only rows for the local offices
above are kept; any kept cell that looks like a contact detail is blanked and counted, and the name of anyone the list
no longer counts as a candidate is not kept (only the status, for the counts). That cut-down copy is the only
thing written (ballot_cache/tx/local/tx_2026_general_candidate_list.json, with the SHA-256 of the bytes as fetched),
and it is used for a week before the list is asked again. The list is the second route for the county-by-county
check: a contest is the list's office number; its status "Candidate in the General Election" (CG) means on the list;
party W is a declared write-in. From it come
  - the declared write-in candidates (write_in = 1, party "Write-in", no ballot order), and the contests where only a
    write-in declared, which the certification does not print;
  - a note on every race where the two lists differ: a candidate on one and not the other (each kept, each with a
    note saying which list carries the name), or a contest filed under another precinct number;
  - a contest whose only candidates are marked withdrawn, deceased or declared ineligible: kept with no candidate and
    a note. Those candidates themselves are left off and counted.
If the list cannot be reached and no kept copy exists, the local rows come from the certification alone and sl_gaps
says the declared write-in candidates are missing.

Also written: sl_gaps and sl_notes (ballot.check_local.EXTRA_SCHEMA). Cities, school districts and special districts
publish their November ballots county by county or one by one, and appraisal district directors file with each
county, so none of those is loaded; each is a gap with its reason. Ballot propositions are not loaded.

    python -m ballot.state_local_tx <path to a test database> [--keep <folder for the kept-cells JSON>] [--no-list]

--no-list loads the local rows from the certification alone (the candidate list is not asked or read).
"""

import base64
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
from collections import Counter
from urllib.request import Request, urlopen

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import tx as fed                                          # noqa: E402
from ballot.lists.tx import proper, same_person                             # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import lines                                            # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "TX", "48", "Texas"
GENERAL = "2026-11-03"
PRIMARY, RUNOFF = fed.PRIMARY, fed.RUNOFF
ROSTER_DB = os.path.join(HERE, "state_tx.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
CERT_PATH = os.path.join(CACHE, "tx_ballot_cert_2026.pdf")
FED_FOLDER = os.path.join(CACHE, "tx")
RECORDS_FILE = "tx_2026_state_results_records.json"
N_COUNTIES = 254

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

PARTIES = fed.PARTIES                  # REP Republican, DEM Democratic, LIB Libertarian, GRE Green, IND Independent, W-I Write-in
PRIMARY_PARTIES = ("REP", "DEM")
CAND_LINE = re.compile(r"^(.+?) (REP|DEM|LIB|GRE|IND|W-I)$")
CERT_STAMP = re.compile(r"^\d\d/\d\d/\d{4} \d\d:\d\d [AP]M Page (\d+) of (\d+)$")

# statewide executive offices as the certification and the canvass print them: (key, office_kind, office, roster office)
EXEC = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "COMPTROLLER OF PUBLIC ACCOUNTS": ("COMP", "comptroller", "Comptroller of Public Accounts", None),
    "COMMISSIONER OF THE GENERAL LAND OFFICE": ("GLO", "land_commissioner", "Commissioner of the General Land Office", None),
    "COMMISSIONER OF AGRICULTURE": ("AGR", "agriculture_commissioner", "Commissioner of Agriculture", None),
    "RAILROAD COMMISSIONER": ("RRC", "railroad_commissioner", "Railroad Commissioner", None),
}
ORD = r"(\d+)(?:ST|ND|RD|TH)"
# offices left to the federal pages or a later local phase: (pattern, the report's word for it)
SKIP = [
    (r"U\. ?S\. (SENATOR|REPRESENTATIVE)\b.*", "federal"),
    (r"(CRIMINAL )?DISTRICT ATTORNEY\b.*", "district attorney"),
    (r"JUSTICE OF THE PEACE\b.*", "justice of the peace"),
    (r"JUDGE, (COUNTY|PROBATE)\b.*|(JUDGE, )?PROBATE COURT\b.*|\d+(ST|ND|RD|TH) MULTICOUNTY COURT AT LAW\b.*", "county court"),
    (r"COUNTY\b.*|DISTRICT (AND COUNTY )?CLERK\b.*|SHERIFF\b.*|HARRIS COUNTY DEPARTMENT OF EDUCATION\b.*", "county office"),
    (r"PROPOSITION \d+|YES|NO", "party proposition"),
]

SRC_CERT = "tx-sos-2026-ballot-cert"
SRC_CANVASS = {("primary", "REP"): "tx-sos-2026-primary-rep-canvass", ("primary", "DEM"): "tx-sos-2026-primary-dem-canvass",
               ("runoff", "REP"): "tx-sos-2026-runoff-rep-canvass", ("runoff", "DEM"): "tx-sos-2026-runoff-dem-canvass"}
SRC_RECORDS = "tx-sos-2026-results-records"
SRC_ROSTER = "tx-openstates-roster"
SRC_COUNTIES = "tx-census-cb-2024-county"

NO_ROSTER = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
MARK_NOTE = "The incumbent mark on a candidate here is the Secretary of State's primary canvass's own \"(I)\"."
SPECIAL_NOTE = "An election for the rest of the term (the certification: unexpired term)."
CONTACT = re.compile(r"@|https?://|www\.|\.(com|org|net|gov|us)\b|\(\d{3}\)|\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{5}(-\d{4})?\b|\bP\.? ?O\.? BOX\b", re.I)

# ---- the local rows (county and precinct offices, county courts, district attorneys)
LOCAL_FOLDER = os.path.join(CACHE, "tx", "local")
SRC_CERT_LOCAL = "tx-sos-2026-ballot-cert-local"
SRC_LIST = "tx-sos-2026-candidate-list"
LOCAL_WORDS = ("district attorney", "justice of the peace", "county court", "county office")      # classify()'s words for what the state part leaves
LIST_PAGE = "https://goelect.txelections.civixapps.com/ivis-cbp-ui/candidate-information"       # the Secretary's Candidate Information page
LIST_SERVICE = "https://goelect.txelections.civixapps.com/api-ivis-cbp/api/cbp/findQualifiedCandidates"      # the call that page makes
LIST_ELECTION, LIST_ELECTION_NAME = 53815, "2026 NOVEMBER GENERAL ELECTION"
LIST_FILE = "tx_2026_general_candidate_list.json"
LIST_LAYOUT = 2           # the kept copy's layout; a copy written in another layout is asked again and written over
LIST_MAX_AGE_DAYS = 7
LIST_PARTY = {"R": "REP", "D": "DEM", "L": "LIB", "G": "GRE", "I": "IND", "W": "W-I"}      # the list's party letters as the certification's codes
ON_LIST = "CG"            # the list's filing status "Candidate in the General Election" (its own table of statuses, read 2026-09-30)
LIST_STATUS = {"WDE": "withdrawn", "D": "deceased", "DI": "declared ineligible", "R": "rejected", "P": "pending"}      # its declaration statuses
RANK = {"REP": 1, "DEM": 2, "LIB": 3, "GRE": 4, "IND": 5}      # the party columns' order (Election Code 52.091), then independents (52.065)
OFFICES_URL = "https://www.sos.texas.gov/elections/candidates/guide/2026/offices2026.shtml"
COUNTY_OFFICES_URL = "https://www.sos.texas.gov/elections/voter/county.shtml"
TAX_CODE_URL = "https://statutes.capitol.texas.gov/Docs/TX/htm/TX.6.htm"
PLIST = r"\d+(?:, \d+)*(?: & \d+)?"                         # "2", "1 & 2", "1, 5 & 6", "1, 2, 3": a precinct as the lists print it
NAME_OK = re.compile(r"[A-Za-z\u00c0-\u017f][A-Za-z\u00c0-\u017f .,'\"()\u2018\u2019\u201c\u201d-]+")
# county offices as both lists print them: heading -> (office_kind, office shown)
COUNTY_OFFICES = {
    "COUNTY JUDGE": ("county_judge", "County Judge"),
    "COUNTY ATTORNEY": ("county_attorney", "County Attorney"),
    "DISTRICT CLERK": ("clerk_of_court", "District Clerk"),
    "DISTRICT AND COUNTY CLERK": ("county_and_district_clerk", "District and County Clerk"),
    "COUNTY AND DISTRICT CLERK": ("county_and_district_clerk", "County and District Clerk"),
    "COUNTY CLERK": ("county_clerk", "County Clerk"),
    "SHERIFF": ("sheriff", "Sheriff"),
    "SHERIFF/COUNTY TAX ASSESSOR-COLLECTOR": ("sheriff_tax_assessor_collector", "Sheriff and County Tax Assessor-Collector"),
    "COUNTY TAX ASSESSOR-COLLECTOR": ("tax_assessor_collector", "County Tax Assessor-Collector"),
    "COUNTY TREASURER": ("county_treasurer", "County Treasurer"),
    "COUNTY SURVEYOR": ("county_surveyor", "County Surveyor"),
}
# a county's own courts: the court's name in the heading -> (office_kind, office shown); "NO. 3" becomes the seat
COUNTY_COURTS = {
    "COUNTY COURT AT LAW": ("county_court_at_law", "Judge, County Court at Law"),
    "COUNTY CRIMINAL COURT AT LAW": ("county_court_at_law", "Judge, County Criminal Court at Law"),
    "COUNTY CRIMINAL COURT": ("county_court_at_law", "Judge, County Criminal Court"),
    "COUNTY CIVIL COURT AT LAW": ("county_court_at_law", "Judge, County Civil Court at Law"),
    "COUNTY CRIMINAL COURT OF APPEALS": ("county_court_at_law", "Judge, County Criminal Court of Appeals"),
    "PROBATE COURT": ("probate_court", "Judge, Probate Court"),
    "PROBATE COURT AT LAW": ("probate_court", "Judge, Probate Court at Law"),
    "COUNTY PROBATE COURT AT LAW": ("probate_court", "Judge, County Probate Court at Law"),
}
# what the page's last check drops from a note: a number, then within a few words a street word (it reads "Court" and "Place" so)
PAGE_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                         r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
NOT_CHECKED = ("The Secretary of State's list prints this contest under a heading this site's loader has not been checked against, "
               "so it is not shown yet.")
SPECIAL_NOTE_LIST = "An election for the rest of the term (the candidate list: unexpired term)."
_CERT_LINES = {}


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def squash(name):
    return fold(name).replace(" ", "")


def strip_mark(raw):
    return re.sub(r"\s*\(I\)\s*$", "", re.sub(r"\s+", " ", raw)).strip()


def is_marked(raw):
    """The canvass's incumbent mark, "(I)" after the name."""
    return bool(re.search(r"\(I\)\s*$", raw))


# ---------- one key for every list: the certification, the canvass and the election records ----------

def classify(heading, cmap):
    """A race dict for a state office this loader keeps, ("skip", word) for one it leaves, or None if unknown. The
    heading is normalised first: spaces, and the canvass's ' - UNEXPIRED TERM' written as the certification's
    ' (UNEXPIRED TERM)'."""
    t = re.sub(r"\s+", " ", heading).strip().upper()
    t = re.sub(r"\s*-\s*\(?UNEXPIRED TERM\)?$", " (UNEXPIRED TERM)", t)
    special = t.endswith(" (UNEXPIRED TERM)")
    base = t[: -len(" (UNEXPIRED TERM)")].strip() if special else t
    suffix = "-UNEXP" if special else ""
    common = {"special": int(special), "partisan": 1, "chamber": None, "roster": None, "district": None, "seat": None,
              "place": None, "statewide": False}

    def race(key, level, kind, office, jur, jur_id, **kw):
        d = dict(common, race_id=f"2026-{STATE}-{key}{suffix}", level=level, office_kind=kind, office=office, jurisdiction=jur,
                 jurisdiction_id=jur_id)
        d.update(kw)
        return d

    if base in EXEC:
        key, kind, office, roster = EXEC[base]
        return race(key, "statewide", kind, office, NAME, STATE, roster=roster, statewide=True)
    if base == "CHIEF JUSTICE, SUPREME COURT":
        return race("SCCJ", "court", "supreme_court", "Chief Justice, Supreme Court", NAME, STATE, seat="Chief Justice", statewide=True)
    m = re.fullmatch(r"JUSTICE, SUPREME COURT, PLACE (\d+)", base)
    if m:
        p = str(int(m.group(1)))
        return race(f"SC{p}", "court", "supreme_court", "Justice, Supreme Court", NAME, STATE, seat=f"Place {p}", statewide=True)
    if base == "PRESIDING JUDGE, COURT OF CRIMINAL APPEALS":
        return race("CCAPJ", "court", "court_of_criminal_appeals", "Presiding Judge, Court of Criminal Appeals", NAME, STATE,
                    seat="Presiding Judge", statewide=True)
    m = re.fullmatch(r"JUDGE, COURT OF CRIMINAL APPEALS, PLACE (\d+)", base)
    if m:
        p = str(int(m.group(1)))
        return race(f"CCA{p}", "court", "court_of_criminal_appeals", "Judge, Court of Criminal Appeals", NAME, STATE, seat=f"Place {p}",
                    statewide=True)
    m = re.fullmatch(rf"CHIEF JUSTICE, {ORD} COURT OF APPEALS DISTRICT", base)
    if m:
        n = str(int(m.group(1)))
        return race(f"COA{n}-CJ", "court", "court_of_appeals", "Chief Justice, Court of Appeals", f"{ordinal(n)} Court of Appeals District",
                    f"{STATE}-COA{n}", district=n, seat="Chief Justice", place=("appeals", f"{STATE}-COA{n}", f"{ordinal(n)} Court of Appeals District"))
    m = re.fullmatch(rf"JUSTICE, {ORD} COURT OF APPEALS DISTRICT, PLACE (\d+)", base)
    if m:
        n, p = str(int(m.group(1))), str(int(m.group(2)))
        return race(f"COA{n}-{p}", "court", "court_of_appeals", "Justice, Court of Appeals", f"{ordinal(n)} Court of Appeals District",
                    f"{STATE}-COA{n}", district=n, seat=f"Place {p}", place=("appeals", f"{STATE}-COA{n}", f"{ordinal(n)} Court of Appeals District"))
    m = re.fullmatch(rf"DISTRICT JUDGE, {ORD} JUDICIAL DISTRICT", base) or re.fullmatch(r"DISTRICT JUDGE, JUDICIAL DISTRICT (\d+[A-Z]?)", base)
    if m:
        n = m.group(1) if not m.group(1).isdigit() else str(int(m.group(1)))
        jur = f"{ordinal(n)} Judicial District" if n.isdigit() else f"Judicial District {n}"
        return race(f"DC{n}", "court", "district_court", "District Judge", jur, f"{STATE}-JD{n}", district=n,
                    place=("judicial", f"{STATE}-JD{n}", jur))
    m = (re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? ([A-Z .']+?) COUNTY(?: NUMBER| NO\.?) ?#?(\d+)", base)
         or re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? #?(\d+),? ([A-Z .']+?) COUNTY", base)
         or re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? ([A-Z .']+?) COUNTY", base))
    if m:
        g = m.groups()
        county, n = (g[1], g[0]) if g[0].isdigit() else (g[0], g[1] if len(g) > 1 else None)
        hit = cmap.get(squash(county))
        if not hit:
            return None
        geoid, full = hit
        n = str(int(n)) if n else None
        return race(f"CDC{geoid[2:]}" + (f"-{n}" if n else ""), "court", "district_court", "Criminal District Judge", full, geoid,
                    seat=f"Number {n}" if n else None, fixed_counties=[geoid])
    m = re.fullmatch(r"MEMBER, STATE BOARD OF EDUCATION, DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SBOE{d}", "statewide", "state_board_of_education", "Member, State Board of Education",
                    f"State Board of Education District {d}", f"{STATE}-SBOE{d}", district=d,
                    place=("sboe", f"{STATE}-SBOE{d}", f"State Board of Education District {d}"))
    m = re.fullmatch(r"STATE SENATOR,? DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SS{d}", "legislature", "state_senate", "State Senator", f"Senate District {d}", f"{STATE}-{d}", district=d,
                    chamber="Senate", place=("senate", f"{STATE}-{d}", f"Senate District {d}"))
    m = re.fullmatch(r"STATE REPRESENTATIVE,? DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SH{d}", "legislature", "state_house", "State Representative", f"House District {d}", f"{STATE}-{d}", district=d,
                    chamber="House", place=("house", f"{STATE}-{d}", f"House District {d}"))
    for pat, word in SKIP:
        if re.fullmatch(pat, base):
            return ("skip", word)
    return None


# ---------- the certification ----------

def read_cert(path, cmap):
    """({race_id: race}, {(race_id, county GEOID): [(name, party code)]}, {kind of office left out: [county lists,
    candidate lines]}, facts)."""
    races, listed, left, left_heads = {}, {}, {}, set()
    county = office = None
    stamps, pages, cover = set(), 0, []
    for page, _y, text in report_lines(path):
        if page == 1:
            cover.append(text)
            continue
        m = CERT_STAMP.match(text)
        if m:
            stamps.add(int(m.group(1)))
            pages = int(m.group(2))
            continue
        if fed.HEADER.match(text):
            continue
        m = re.match(r"^County (.+)$", text)
        if m:
            hit = cmap.get(squash(m.group(1)))
            if not hit:
                raise SystemExit(f"Texas (state races): the certification names a county the Census file does not have (page {page})")
            county, office = hit[0], None
            continue
        m = CAND_LINE.match(text)
        if m:
            if office is None:
                raise SystemExit(f"Texas (state races): a candidate on page {page} of the certification comes before any office heading")
            if isinstance(office, tuple):
                left.setdefault(office[1], [0, 0])[1] += 1
                continue
            listed.setdefault((office["race_id"], county), []).append((m.group(1).strip(), m.group(2)))
            continue
        if county is None:
            raise SystemExit(f"Texas (state races): page {page} of the certification has text before its county line")
        office = classify(text, cmap)
        if office is None:
            raise SystemExit(f"Texas (state races): an office heading in the certification this loader does not know: {text!r} (page {page})")
        if isinstance(office, tuple):
            left_heads.add((office[1], text, county))
            continue
        races.setdefault(office["race_id"], office)
    joined = " ".join(cover)
    if "DO HEREBY" not in joined or "day of August, 2026" not in joined:
        raise SystemExit("Texas (state races): the certification's cover no longer reads as the August 2026 certification")
    signed = re.search(r"this (\d+)(?:st|nd|rd|th) day of August, 2026", joined)
    if pages != len(stamps) or stamps != set(range(1, pages + 1)):
        raise SystemExit(f"Texas (state races): the certification says {pages} report pages and {len(stamps)} were read")
    for word, _t, _c in left_heads:
        left.setdefault(word, [0, 0])[0] += 1
    return races, listed, left, {"pages": pages + 1, "signed": f"2026-08-{int(signed.group(1)):02d}" if signed else ""}


# ---------- the canvass ----------

def read_canvass(path, name, code, cmap):
    """({race_id: {"office", "cands": [[name as printed, votes]], "total"}} for the state offices this loader keeps,
    printed date, [differences], Counter of offices left out). Checked against its Total lines, its percents and its
    page count."""
    out, differ, left = {}, [], Counter()
    office = head = last = None
    printed, pages, seen = "", 0, set()
    got_title = got_name = False
    said_races, n_totals = None, 0

    def settle():
        nonlocal office
        if head is None:
            return
        c = classify(head["text"], cmap)
        if c is None:
            raise SystemExit(f"Texas (state races): an office in {os.path.basename(path)} this loader does not know: {head['text']!r}")
        if isinstance(c, tuple):
            left[c[1]] += 1
            office = "skip"
            return
        rid = c["race_id"]
        if rid in out:
            raise SystemExit(f"Texas (state races): {os.path.basename(path)} lists {rid} twice")
        out[rid] = {"office": head["text"], "cands": [], "total": None, "race": c}
        office = rid

    for page, y, text in lines(path):
        seen.add(page)
        m = fed.STAMP.match(text)
        if m:
            printed, pages = m.group(1), int(m.group(3))
            continue
        if fed.CANVASS_HEAD.match(text):
            got_title |= text == "Official Canvass Report"
            got_name |= text == name
            continue
        m = re.match(rf"^(.+?) ({code}) ([\d,]+) (\d+\.\d\d) %$", text)
        if m:
            if head is not None and office is None:
                settle()
            head = None
            if office is None:
                raise SystemExit(f"Texas (state races): a candidate in {os.path.basename(path)} (page {page}) comes before any office")
            last = [m.group(1).strip(), int(m.group(3).replace(",", "")), float(m.group(4)), page, y]
            if office != "skip":
                out[office]["cands"].append(last)
            continue
        m = re.match(r"^Total Races ([\d,]+)$", text)
        if m:
            said_races = int(m.group(1).replace(",", ""))
            office, head, last = None, None, None
            continue
        m = re.match(r"^Total ([\d,]+)$", text)
        if m:
            if head is not None and office is None:
                settle()
            head, last = None, None
            n_totals += 1
            if office is None:
                raise SystemExit(f"Texas (state races): a Total line in {os.path.basename(path)} (page {page}) comes before any office")
            if office != "skip":
                out[office]["total"] = int(m.group(1).replace(",", ""))
            continue
        m = re.match(r"^(.+?) ([\d,]+) (\d+\.\d\d) %$", text)
        if m:
            if head is not None and office is None:
                settle()
            office, last = None, None
            head = {"text": m.group(1).strip(), "page": page, "y": y}
            continue
        if head is not None and office is None and head["page"] == page and 0 < head["y"] - y < 16:
            head["text"] = f"{head['text']} {text.strip()}"          # an office heading's second line
            head["y"] = y
            continue
        if last and last[3] == page and 0 < last[4] - y < 16:      # the rest of a long name, on the line just below
            last[0] = last[0] + text.strip() if last[0].endswith("-") else f"{last[0]} {text.strip()}"     # CANTU- / CASTLE
            last[4] = y
            continue
        raise SystemExit(f"Texas (state races): a line in {os.path.basename(path)} (page {page}) the loader cannot place"
                         + (f" under {office}" if office and office != "skip" else ""))
    if head is not None and office is None:
        settle()
    if not (got_title and got_name):
        raise SystemExit(f"Texas (state races): {os.path.basename(path)} is not the Official Canvass Report of the {name}")
    if pages != len(seen):
        differ.append(f"{name}: the report says {pages} pages and {len(seen)} were read")
    if said_races != n_totals:
        differ.append(f"{name}: the report's closing line counts {said_races} races and {n_totals} Total lines were read")
    for rid, c in out.items():
        total = sum(v for _n, v, *_ in c["cands"])
        if c["total"] != total:
            differ.append(f"{name}, {rid}: Total {c['total']} is not the sum of its candidates ({total})")
        for n, v, pct, *_ in c["cands"]:
            if total and abs(100 * v / total - pct) > 0.006:
                differ.append(f"{name}, {rid}: a printed percent ({pct}) is not {100 * v / total:.2f}")
        c["cands"] = [(n, v) for n, v, *_ in c["cands"]]
    stamp = dt.datetime.strptime(printed, "%m/%d/%Y").strftime("%Y-%m-%d") if printed else ""
    return out, stamp, differ, left


def records(meta, keep_dir, say):
    """{"<kind>-<party>": {"id", "races": [{"N", "T", "C": [[name, party, votes]]}]}} from each election's record: the
    StateWide and Districted sections only, and of them only race name, total, candidate name, party and votes. Kept
    30 days in keep_dir (the results are canvassed)."""
    path = os.path.join(keep_dir, RECORDS_FILE)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        got = json.load(open(path, encoding="utf-8"))
        if all(k in got and got[k].get("id") == meta[k]["id"] for k in meta):
            return got, path
    got = {}
    for key, m in meta.items():
        time.sleep(1.0)
        rec = json.loads(net.get(f"{fed.API}/election/{m['id']}", accept="application/json"))
        home = json.loads(base64.b64decode(rec["Home"]))
        if home.get("ElecDate") != dt.date.fromisoformat(m["date"]).strftime("%m%d%Y"):
            raise SystemExit(f"Texas (state races): the results system dates election {m['id']} {home.get('ElecDate')}, not {m['date']}")
        races = []
        for sec in ("StateWide", "Districted"):
            for r in json.loads(base64.b64decode(rec[sec])).get("Races") or []:
                races.append({"N": re.sub(r"\s+", " ", r["N"]).strip(), "T": int(r["T"]),
                              "C": [[re.sub(r"\s+", " ", c["N"]).strip(), c["P"], int(c["V"])] for c in r.get("Candidates") or []]})
        got[key] = {"id": m["id"], "name": m["name"], "races": races}
    os.makedirs(keep_dir, exist_ok=True)
    json.dump(got, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    say(f"    Texas (state races): kept the four election records' state races ({sum(len(v['races']) for v in got.values())} races; "
        "names, parties and votes only)")
    return got, path


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row}, {roster office: row}, the roster's date, and the roster's own
    spelling of each sitting member's name. Only id, name, party, chamber, district and office are selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices, forms = {}, {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]).strip())
        if key in seats:
            raise SystemExit(f"Texas (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for h in list(seats.values()) + list(offices.values()):
        for form in (h["full"], f"{h['first']} {h['last']}"):
            if form:
                forms[squash(form)] = h["full"]
    return seats, offices, as_of, forms


def counties(path=COUNTY_ZIP):
    """{squashed county name: (GEOID, "Anderson County")} for Texas from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[squash(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != N_COUNTIES:
        raise SystemExit(f"Texas (state races): the county file gives {len(out)} Texas counties, not {N_COUNTIES}")
    return out


def holder_fits(name, h):
    """The name fits the roster's holder: as written without its nickname, or with the nickname in quotes or brackets
    as the given name (MARIA LUISA "LULU" FLORES for Lulu Flores)."""
    plain = re.sub(r'"[^"]*"|\([^)]*\)', " ", name)
    forms = [name_parts(plain)]
    family = forms[0][1]
    for nick in re.findall(r'"([^"]+)"|\(([^)]+)\)', name):
        nick = "".join(nick).strip()
        if nick and family:
            forms.append((fold(nick).split(), family))
    regs = [reg for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1]]
    return any(fits(cand, reg) for cand in forms for reg in regs)


def family_of(name):
    return name_parts(re.sub(r'"[^"]*"|\([^)]*\)', " ", name))[1]


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


def shown_with(forms):
    def shown(caps):
        """'JAMES "JIM" SMITH (I)' -> 'James "Jim" Smith'; initials written together stay capitals (TJ); a sitting
        member as the roster spells the name."""
        name = strip_mark(caps)
        if squash(name) in forms:
            return forms[squash(name)]
        words = proper(name).split()
        for i, w in enumerate(name.split()):
            if i < len(words) and re.fullmatch(r"[B-DF-HJ-NP-TV-XZ]{2,3}", w) and w not in ("JR", "SR"):
                words[i] = w
        t = re.sub(r"(^|\s)([\"\u201c(])([a-z])", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), " ".join(words))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)
    return shown


# ---------- the local rows: county and precinct offices, county courts and district attorneys ----------

def report_lines(path):
    """Every line of the certification, read once a run: [(page, y, text)]."""
    key = (os.path.abspath(path), os.path.getsize(path), os.path.getmtime(path))
    if key not in _CERT_LINES:
        _CERT_LINES.clear()
        _CERT_LINES[key] = list(lines(path))
    return _CERT_LINES[key]


def heading_of(text):
    """An office heading as the two lists are compared: capitals, single spaces, and the candidate list's
    ' - UNEXPIRED TERM' written as the certification's ' (UNEXPIRED TERM)'."""
    t = re.sub(r"\s+", " ", text or "").strip().upper()
    return re.sub(r"\s*-\s*\(?UNEXPIRED TERM\)?$", " (UNEXPIRED TERM)", t)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def day_words(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def heading_words(heading):
    """A heading this loader does not know, in ordinary capitals, for a gap's few words."""
    small = {"OF", "THE", "AND", "AT", "FOR"}
    return " ".join(w.lower() if i and w in small else (w if re.fullmatch(r"[IVX]+|\(?\d.*", w) else w.capitalize())
                    for i, w in enumerate(heading.split()))


def race_words(o):
    """The office with its precinct and place, as the page titles a contest."""
    return ", ".join(x for x in (o["office"], o["district"], o["seat"]) if x)


def page_would_drop(text):
    """True if ballot/check_local.py or the page's own last check would take this text for contact details."""
    return bool(text) and (contact_like(text, True) or bool(PAGE_STREET.search(text)))


def shown_local(shown):
    """The state rows' way of showing a name printed in capitals, with two small slips of capitals put right for the
    local rows: the letter after D' or L' (D'ANN -> D'Ann, not D'ann) and the first letter of a nickname in quotes or
    brackets wherever it opens ('LUPITA' -> 'Lupita'; A."JACK" -> A."Jack")."""
    def tidy(caps):
        t = re.sub(r"\b([DL])'([a-z])", lambda m: m.group(1) + "'" + m.group(2).upper(), shown(caps))
        return re.sub(r"(?<![A-Za-z\u00c0-\u017f])(['\"\u2018\u201c(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    return tidy


def local_office(heading, geoid, cmap, by_geoid):
    """What a county or district heading of the certification (or of the candidate list) is: the race's id, level,
    office_kind, office, jurisdiction, counties (None for a district: they come from the counties that print it),
    district, seat, special and place; None for a heading this loader has not been checked against. `geoid` is the
    county whose list prints the heading (None for the candidate list's district offices, which name no county)."""
    t = heading_of(heading)
    special = t.endswith(" (UNEXPIRED TERM)")
    base = t[: -len(" (UNEXPIRED TERM)")].strip() if special else t
    tail = "-S" if special else ""

    def county(kind, office, district=None, seat=None, g=geoid):
        if g is None or g not in by_geoid:
            return None
        return {"race_id": f"2026-{STATE}-{g}-{slug(base)}{tail}", "level": "county", "office_kind": kind, "office": office,
                "jurisdiction": by_geoid[g], "jurisdiction_id": g, "counties": [g], "district": district, "seat": seat,
                "special": int(special), "place": None, "judicial": None}

    def district_wide(key, kind, office, jur, pid, judicial=None):
        return {"race_id": f"2026-{STATE}-{key}{tail}", "level": "other", "office_kind": kind, "office": office, "jurisdiction": jur,
                "jurisdiction_id": pid, "counties": None, "district": None, "seat": None, "special": int(special),
                "place": ("special", pid, jur), "judicial": judicial}

    def named(name):
        """The county a heading names, which must be the county whose list prints it."""
        hit = cmap.get(squash(name))
        return hit[0] if hit and geoid in (None, hit[0]) else None

    if base in COUNTY_OFFICES:
        return county(*COUNTY_OFFICES[base])
    m = re.fullmatch(rf"COUNTY COMMISSIONER PRECINCT ({PLIST})", base)
    if m:
        return county("county_commissioner", "County Commissioner", district=f"Precinct {m.group(1)}")
    m = re.fullmatch(rf"COUNTY CONSTABLE(?: PRECINCT ({PLIST}))?", base)
    if m:
        return county("constable", "County Constable", district=f"Precinct {m.group(1)}" if m.group(1) else None)
    m = re.fullmatch(rf"JUSTICE OF THE PEACE(?: PRECINCT ({PLIST}))?(?:, PLACE (\d+))?", base)
    if m:
        return county("justice_of_the_peace", "Justice of the Peace", district=f"Precinct {m.group(1)}" if m.group(1) else None,
                      seat=f"Place {int(m.group(2))}" if m.group(2) else None)
    m = re.fullmatch(r"JUSTICE OF THE PEACE NO\. ?(\d+)", base)
    if m:
        return county("justice_of_the_peace", "Justice of the Peace", district=f"No. {int(m.group(1))}")
    m = re.fullmatch(r"(?:JUDGE, )?(" + "|".join(sorted(COUNTY_COURTS, key=len, reverse=True)) + r")(?: NO\. ?(\d+))?", base)
    if m:
        kind, office = COUNTY_COURTS[m.group(1)]
        return county(kind, office, seat=f"No. {int(m.group(2))}" if m.group(2) else None)
    m = re.fullmatch(r"([A-Z .']+?) COUNTY DEPARTMENT OF EDUCATION, PLACE (\d+)", base)
    if m:          # the county school trustees of Election Code 52.092(e)(13)
        g = named(m.group(1))
        return county("county_school_trustee", f"Trustee, {by_geoid[g]} Department of Education", seat=f"Place {int(m.group(2))}", g=g) if g else None
    m = re.fullmatch(r"(CRIMINAL )?DISTRICT ATTORNEY,? ([A-Z .']+?) COUNTY", base)
    if m:
        g = named(m.group(2))
        return county("district_attorney", "Criminal District Attorney" if m.group(1) else "District Attorney", g=g) if g else None
    m = re.fullmatch(rf"DISTRICT ATTORNEY,? {ORD} JUDICIAL DISTRICT", base)
    if m:
        n = str(int(m.group(1)))
        return district_wide(f"X-JD{n}-district-attorney", "district_attorney", "District Attorney", f"{ordinal(n)} Judicial District",
                             f"{STATE}-X-JD{n}", judicial=n)
    m = re.fullmatch(rf"{ORD} MULTICOUNTY COURT AT LAW", base)
    if m:
        n = str(int(m.group(1)))
        jur = f"{ordinal(n)} Multicounty Court at Law"
        return district_wide(f"X-multicounty-court-at-law-{n}-judge", "county_court_at_law", f"Judge, {jur}", jur,
                             f"{STATE}-X-multicounty-court-at-law-{n}")
    return None


def cert_local(path, cmap):
    """The certification's contests that the state part leaves to the local rows, in the report's order:
    [{"geoid", "heading", "page", "word", "cands": [(name as printed, party code)]}], and {classify()'s word:
    [headings, candidate lines]}, counted the way read_cert counts what it leaves (the two must agree)."""
    out, tally = [], {}
    county = cur = None
    for page, _y, text in report_lines(path):
        if page == 1 or CERT_STAMP.match(text) or fed.HEADER.match(text):
            continue
        m = re.match(r"^County (.+)$", text)
        if m:
            county, cur = cmap[squash(m.group(1))][0], None          # read_cert has already stopped on a county it does not know
            continue
        m = CAND_LINE.match(text)
        if m:
            if cur is not None:
                cur["cands"].append((m.group(1).strip(), m.group(2)))
                tally[cur["word"]][1] += 1
            continue
        c = classify(text, cmap)
        if isinstance(c, tuple) and c[1] in LOCAL_WORDS:
            cur = {"geoid": county, "heading": heading_of(text), "page": page, "word": c[1], "cands": []}
            out.append(cur)
            tally.setdefault(c[1], [0, 0])[0] += 1
        else:
            cur = None
    return out, tally


def cut_list(raw, cmap):
    """The candidate list's answer cut down, in memory, to what the local rows need: for each candidate of a county or
    precinct office, county court or district attorney, nine cells (t office type, id office number, c county, o office
    title, n the name as on the ballot, p party, d declaration status, f filing status, k kind of candidate). The
    mailing address, e-mail, website, occupation, filing date and the rest are never read. A kept cell that looks like
    a contact detail is blanked and counted, and the name of anyone the list no longer counts as a candidate is not
    kept at all (only the status, for the counts)."""
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) < 1000 or not all(isinstance(r, dict) for r in data):
        raise ValueError("the answer is not a list of candidates")
    rows, by_type, blanked, no_prefix = [], Counter(), 0, 0
    for r in data:
        if r.get("idElection") != LIST_ELECTION or heading_of(r.get("txElectionName")) != LIST_ELECTION_NAME:
            raise ValueError("the answer is not all the November 2026 general election")
        cut = {"t": str(r.get("cdOfficeType") or ""), "id": r.get("idOffice"), "c": heading_of(r.get("txCountyName")),
               "o": heading_of(r.get("txOfficeName")), "n": re.sub(r"\s+", " ", str(r.get("txFullNameBallot") or "")).strip(),
               "p": str(r.get("cdParty") or ""), "d": str(r.get("cdDeclarationStatus") or ""), "f": str(r.get("cdFilingStatus") or ""),
               "k": str(r.get("cdCandType") or "")}
        by_type[cut["t"]] += 1
        if cut["c"]:
            if cut["o"].startswith(cut["c"] + " - "):
                cut["o"] = cut["o"][len(cut["c"]) + 3:]
            else:
                no_prefix += 1
        c = classify(cut["o"], cmap)
        if not ((isinstance(c, tuple) and c[1] in LOCAL_WORDS) or (cut["c"] and c is None)):
            continue                                              # a federal or state office: the federal pages and the state rows
        if cut["f"] != ON_LIST:
            cut["n"] = ""                                         # no longer a candidate: counted by status, the name is not kept
        for k in ("c", "o", "n"):
            if cut[k] and contact_like(cut[k], True):
                cut[k] = ""
                blanked += 1
        rows.append(cut)
    return {"layout": LIST_LAYOUT, "page": LIST_PAGE, "service": LIST_SERVICE, "election": LIST_ELECTION, "fetched": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "rows_in": len(data), "by_type": dict(by_type),
            "blanked": blanked, "no_prefix": no_prefix, "rows": rows}


def candidate_list(folder, cmap, say):
    """The local rows of the Secretary of State's candidate list (see cut_list), from the kept copy while it is under a
    week old, else asked once, the way the Secretary's own Candidate Information page asks: one POST, the same honest
    User-Agent, no second try. None if it cannot be had (the local rows then come from the certification alone)."""
    path = os.path.join(folder, LIST_FILE)
    got = None
    if os.path.exists(path):
        try:
            got = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            got = None
        if not (isinstance(got, dict) and got.get("layout") == LIST_LAYOUT and got.get("election") == LIST_ELECTION
                and isinstance(got.get("rows"), list) and got.get("fetched")):
            got = None                                            # not the layout this loader writes: asked again and written over
    if got is None or time.time() - os.path.getmtime(path) >= LIST_MAX_AGE_DAYS * 86400:
        try:
            net.patient_lookups()
            body = json.dumps({"electionYear": int(GENERAL[:4]), "electionId": LIST_ELECTION, "party": None, "officeId": None,
                               "officeType": None, "status": None, "countyId": None}).encode()
            time.sleep(1.0)
            req = Request(LIST_SERVICE, data=body, method="POST",
                          headers={"User-Agent": net.UA, "Content-Type": "application/json", "Accept": "application/json"})
            with urlopen(req, timeout=180) as r:
                raw = r.read()
            kept = cut_list(raw, cmap)
            del raw
            os.makedirs(folder, exist_ok=True)
            json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            got = kept
            say(f"    Texas (local races): asked the Secretary of State's candidate list: {kept['rows_in']:,} rows, {len(kept['rows']):,} for local "
                f"offices kept (nine cells a row; {kept['blanked']} cells that looked like contact details blanked)")
        except Exception as e:  # noqa: BLE001  the list is a second source: without it the certification still loads
            if got is None:
                say(f"    Texas (local races): the Secretary of State's candidate list could not be read ({type(e).__name__}); "
                    "the local rows come from the certification alone")
                return None
            say(f"    Texas (local races): could not ask the candidate list again ({type(e).__name__}); using the kept copy")
    return got


def local_rows(contests, lst, cmap, by_geoid, shown, jd_counties, cert_day):
    """The local races and candidates: {"races": [sl_races rows], "cands": [sl_candidates rows], "places": [sl_places
    rows], "gaps": [sl_gaps rows], "checks": [words], "stats": Counter, and the facts the notes and the report use}.
    `contests` are the certification's (cert_local), `lst` the candidate list's kept rows or None, `jd_counties` the
    counties the certification lists each judicial district's judge under. A contest that cannot be read is left out
    and written to the gaps; nothing here stops the state rows from loading."""
    stats, checks, gaps = Counter(), [], []
    races, order, twice = {}, [], set()
    cert_words = day_words(cert_day)
    list_day = day_words(lst["fetched"]) if lst else ""

    def gap(scope, place_id, place, what, reason, url=fed.URL):
        row = (STATE, scope, place_id, place, what, reason, url)
        if row not in gaps:
            gaps.append(row)

    # ---- 1. the certification: one race a contest; a district's contest is printed under each of its counties
    for c in contests:
        stats["printed"] += 1
        stats["lines"] += len(c["cands"])
        o = local_office(c["heading"], c["geoid"], cmap, by_geoid)
        if o is None:
            gap("county", c["geoid"], by_geoid[c["geoid"]], heading_words(c["heading"]), NOT_CHECKED)
            checks.append(f"a heading this loader does not know is not loaded: {c['heading']!r} in {by_geoid[c['geoid']]} "
                          f"({len(c['cands'])} candidate lines)")
            stats["printed, not loaded"] += 1
            stats["lines not placed"] += len(c["cands"])
            continue
        rid = o["race_id"]
        if rid not in races:
            races[rid] = {"o": o, "lists": {}}
            order.append(rid)
        if c["geoid"] in races[rid]["lists"]:
            twice.add(rid)
        races[rid]["lists"].setdefault(c["geoid"], []).extend(c["cands"])

    good = {}
    for rid in order:
        o, lists = races[rid]["o"], races[rid]["lists"]
        n_lines = sum(len(v) for v in lists.values())

        def leave_out(reason, o=o, rid=rid, n_printed=len(lists), n_lines=n_lines):
            gap("race", rid, o["jurisdiction"], race_words(o), reason)
            checks.append(f"{rid}: not loaded ({reason})")
            stats["printed, not loaded"] += n_printed
            stats["lines not placed"] += n_lines

        versions = {tuple(v) for v in lists.values()}
        if rid in twice:
            leave_out("The Secretary of State's certification prints this contest twice under one county, so its candidates cannot be "
                      "told apart; it is not shown.")
            continue
        if len(versions) != 1:
            leave_out("The Secretary of State's certification prints this contest under several counties and their lists of candidates "
                      "do not agree, so it is not shown.")
            continue
        printed = list(versions.pop())
        if any(not NAME_OK.fullmatch(n) or contact_like(n, True) for n, _c in printed):
            leave_out("A candidate line of this contest on the Secretary of State's certification does not read as a name, so the "
                      "contest is not shown.")
            continue
        names = [shown(n) for n, _c in printed]
        if len(set(names)) != len(names):
            leave_out("The Secretary of State's certification prints the same name twice in this contest, so it is not shown.")
            continue
        ranks = [RANK.get(code, 0) for _n, code in printed if code != "W-I"]
        ordered = all(ranks) and all(a < b for a, b in zip(ranks, ranks[1:]))
        if not ordered:
            checks.append(f"{rid}: the certification's order is not the order of the party columns, or two candidates share a "
                          "label; no ballot order stored")
        cands, pos = [], 0
        for (raw, code), name in zip(printed, names):
            wi = code == "W-I"
            pos += 0 if wi else 1
            cands.append({"key": squash(raw), "name": name, "code": code, "order": pos if ordered and not wi else None,
                          "wi": int(wi), "src": SRC_CERT_LOCAL, "note": None})
        good[rid] = {"o": o, "counties": o["counties"] or sorted(lists), "cands": cands,
                     "notes": ([SPECIAL_NOTE] if o["special"] else [])
                     + ([] if cands else ["The Secretary of State's certification prints this office with no candidate under it."])}
        stats["printed, loaded"] += len(lists)
        stats["lines placed"] += n_lines
        stats["certification contests"] += 1
        stats["certification candidates"] += len(cands)
        stats["in several counties"] += 1 if len(lists) > 1 else 0
        stats["with ballot order"] += 1 if ordered else 0

    # ---- 2. the candidate list: the second route, the declared write-in candidates, and what has changed since
    differ_in, off = Counter(), Counter()
    if lst:
        groups = {}
        for row in lst["rows"]:
            g = groups.setdefault(row["id"] if row["id"] is not None else f"{row['c']}|{row['o']}",
                                  {"county": row["c"], "rows": []})
            g["rows"].append(row)
        left_out = set(races) - set(good)
        matched, loose, label = {}, [], {}
        for gk in sorted(groups, key=str):
            g = groups[gk]
            hit = cmap.get(squash(g["county"])) if g["county"] else None
            g["geoid"] = hit[0] if hit else None
            by_office = {}
            if hit or not g["county"]:
                for row in g["rows"]:
                    o = local_office(row["o"], g["geoid"], cmap, by_geoid)
                    if o:
                        by_office.setdefault(o["race_id"], {"o": o, "rows": []})["rows"].append(row)
            if sum(len(v["rows"]) for v in by_office.values()) != len(g["rows"]):
                where = by_geoid[g["geoid"]] if g["geoid"] else NAME
                gap("county" if g["geoid"] else "state", g["geoid"] or STATE, where,
                    heading_words(g["rows"][0]["o"]) if g["rows"][0]["o"] else "a contest on the candidate list", NOT_CHECKED, LIST_PAGE)
                checks.append(f"an office on the candidate list this loader does not know is not loaded: {g['rows'][0]['o']!r} ({where}; "
                              f"{len(g['rows'])} rows)")
                stats["list contests not loaded"] += 1
                stats["list rows: in contests not loaded"] += len(g["rows"])
                continue
            stats["list contests"] += 1
            if set(by_office) & left_out:
                stats["list rows: in contests not loaded"] += len(g["rows"])
                continue                                          # a contest of the certification left out above: its gap says why
            hits = set(by_office) & set(good)
            if len(hits) == 1:                                    # one office number is one contest, whatever its rows' titles
                matched.setdefault(hits.pop(), []).extend(g["rows"])
            elif not hits:
                first = next(iter(by_office.values()))
                loose.append({"o": first["o"], "rows": list(g["rows"]), "geoid": g["geoid"]})
            else:                                                 # its titles are two contests of the certification: each row to its own
                for rid, v in by_office.items():
                    if rid in good:
                        matched.setdefault(rid, []).extend(v["rows"])
                    else:
                        loose.append({"o": v["o"], "rows": v["rows"], "geoid": g["geoid"]})

        def printed_of(rows):
            return sorted((squash(r["n"]), LIST_PARTY.get(r["p"], r["p"])) for r in rows if r["f"] == ON_LIST and r["p"] != "W" and r["n"])

        # the same candidates under another precinct or place number: one contest, and the race says so
        for rid in order:
            if rid not in good or rid in matched:
                continue
            o = good[rid]["o"]
            mine = sorted((c["key"], c["code"]) for c in good[rid]["cands"] if not c["wi"])
            fits = [g for g in loose if mine and printed_of(g["rows"]) == mine
                    and g["geoid"] == (o["jurisdiction_id"] if o["level"] == "county" else None)]
            if len(fits) == 1:
                matched[rid] = fits[0]["rows"]
                label[rid] = fits[0]["o"]
                loose.remove(fits[0])

        for rid in order:
            if rid not in good:
                continue
            R = good[rid]
            o = R["o"]
            if rid not in matched:
                R["notes"].append(f"On the certification ({cert_words}); the Secretary of State's candidate list as read later ({list_day}) "
                                  "has no such contest.")
                checks.append(f"{rid}: on the certification, not on the candidate list")
                stats["contests not on the list"] += 1
                differ_in.update(R["counties"])
                continue
            rows = matched[rid]
            listed = {}
            for r in rows:
                if r["f"] == ON_LIST and r["p"] != "W" and r["n"] and NAME_OK.fullmatch(r["n"]):
                    listed[(squash(r["n"]), LIST_PARTY.get(r["p"], r["p"]))] = r
            mine = {(c["key"], c["code"]) for c in R["cands"]}
            keys = {c["key"] for c in R["cands"]}
            list_only = {k: r for k, r in listed.items() if k not in mine and k[0] not in keys}
            differs = False
            for c in R["cands"]:
                if c["wi"] or (c["key"], c["code"]) in listed:
                    continue
                other = [k for k in listed if k[0] == c["key"]]
                twin = [k for k, r in list_only.items() if k[1] == c["code"] and same_person(c["name"], shown(r["n"]))]
                if other:
                    differs = True
                    c["note"] = (f"The certification ({cert_words}) prints this candidate as {PARTIES[c['code']]}; the Secretary of State's "
                                 f"candidate list as read later ({list_day}) gives {PARTIES.get(other[0][1], 'another party')}.")
                    stats["party differs"] += 1
                elif len(twin) == 1:          # one name spelled two ways (a nickname, a middle initial): one candidate, said once
                    c["note"] = f"The Secretary of State's candidate list as read later ({list_day}) spells this name differently."
                    del list_only[twin[0]]
                    keys.add(twin[0][0])
                    stats["names spelled two ways"] += 1
                else:
                    differs = True
                    c["note"] = (f"On the Secretary of State's certification ({cert_words}), but not on the Secretary's candidate list as "
                                 f"read later ({list_day}).")
                    stats["names on the certification only"] += 1
            for key, r in sorted(list_only.items()):
                if key[1] not in PARTIES:
                    checks.append(f"{rid}: a party code on the candidate list this loader does not know; that candidate is not added")
                    continue
                differs = True
                R["cands"].append({"key": key[0], "name": shown(r["n"]), "code": key[1], "order": None, "wi": 0, "src": SRC_LIST,
                                   "note": f"Not on the Secretary of State's certification ({cert_words}); on the Secretary's candidate "
                                           f"list as read later ({list_day})."})
                keys.add(key[0])
                stats["names on the list only"] += 1
            for r in rows:                    # every row of the list is counted once: ended, unreadable, write-in or printed
                if r["f"] != ON_LIST:
                    off[r["d"]] += 1
                elif not r["n"] or not NAME_OK.fullmatch(r["n"]):
                    stats["list rows without a readable name"] += 1
                elif r["p"] == "W":
                    stats["list rows: write-ins"] += 1
                    k = squash(r["n"])
                    if k in keys:
                        checks.append(f"{rid}: a declared write-in on the candidate list has the name of another candidate in the contest; not added")
                        continue
                    R["cands"].append({"key": k, "name": shown(r["n"]), "code": "W-I", "order": None, "wi": 1, "src": SRC_LIST, "note": None})
                    keys.add(k)
                    stats["write-ins"] += 1
                else:
                    stats["list rows: printed"] += 1
            if differs:
                R["notes"].append(f"The Secretary of State's certification ({cert_words}) and the Secretary's candidate list as read later "
                                  f"({list_day}) do not name the same candidates here; each candidate's note says which carries the name. "
                                  "The county's sample ballot settles it.")
                stats["contests that differ"] += 1
                differ_in.update(R["counties"])
            if rid in label:
                R["notes"].append(f"The certification ({cert_words}) prints this contest as {race_words(o)}; the Secretary of State's "
                                  f"candidate list ({list_day}) files the same names under {race_words(label[rid])}. The county's sample "
                                  "ballot settles which.")
                stats["contests under another number"] += 1
                differ_in.update(R["counties"])
            if not differs and rid not in label:
                stats["contests the same in both lists"] += 1

        # contests the certification does not print: only a write-in declared, or everyone on the list has left it
        new = {}
        for g in loose:
            N = new.setdefault(g["o"]["race_id"], {"o": g["o"], "rows": []})
            N["rows"].extend(g["rows"])
        for rid, N in sorted(new.items()):
            o, rows, notes = N["o"], N["rows"], []
            words = race_words(o) + (" (unexpired term)" if o["special"] else "")
            if o["special"]:
                notes.append(SPECIAL_NOTE_LIST)
            counties = o["counties"]
            if counties is None:
                counties = sorted(jd_counties.get(o["judicial"], ())) if o["judicial"] else []
                if not counties:
                    gap("race", rid, o["jurisdiction"], words,
                        "The Secretary of State's candidate list names this contest, which the certification does not print under any "
                        "county, and the list does not say which counties vote on it, so it is not shown.", LIST_PAGE)
                    checks.append(f"{rid}: on the candidate list only, and its counties are not in the record; not loaded")
                    stats["list contests not loaded"] += 1
                    stats["list rows: in contests not loaded"] += len(rows)
                    continue
                notes.append("The candidate list does not name the counties that vote on this office; those shown are the counties where "
                             "the certification lists the judge of the same judicial district.")
            cands, keys = [], set()
            for r in rows:
                code = LIST_PARTY.get(r["p"])
                if r["f"] == ON_LIST and r["n"] and NAME_OK.fullmatch(r["n"]) and code and squash(r["n"]) not in keys:
                    keys.add(squash(r["n"]))
                    cands.append({"key": squash(r["n"]), "name": shown(r["n"]), "code": code, "order": None, "wi": int(code == "W-I"),
                                  "src": SRC_LIST, "note": None})
            if len(cands) != sum(1 for r in rows if r["f"] == ON_LIST):
                gap("race", rid, o["jurisdiction"], words,
                    "A candidate of this contest on the Secretary of State's candidate list does not read as a name, so the contest is "
                    "not shown.", LIST_PAGE)
                checks.append(f"{rid}: on the candidate list only, with a row that does not read as a name; not loaded")
                stats["list contests not loaded"] += 1
                stats["list rows: in contests not loaded"] += len(rows)
                continue
            off.update(r["d"] for r in rows if r["f"] != ON_LIST)
            wi = sum(c["wi"] for c in cands)
            stats["list rows: write-ins"] += wi
            stats["list rows: printed"] += len(cands) - wi
            if len(cands) > wi:
                notes.append(f"Not on the certification ({cert_words}); on the Secretary of State's candidate list as read later ({list_day}).")
                stats["list-only contests with a printed candidate"] += 1
                differ_in.update(counties)
            elif wi:
                notes.append("No name is printed on the ballot for this office: the Secretary of State's candidate list names only "
                             + ("a declared write-in candidate." if wi == 1 else "declared write-in candidates."))
                stats["write-in only contests"] += 1
            else:
                kinds = sorted({LIST_STATUS.get(r["d"], "no longer a candidate") for r in rows})
                notes.append(f"The Secretary of State's candidate list ({list_day}) has no candidate left for this office: "
                             + ("the one candidacy on it is marked " + kinds[0] if len(rows) == 1
                                else f"its {len(rows)} candidacies are marked " + " or ".join(kinds)) + ".")
                stats["contests with no candidate"] += 1
            stats["write-ins"] += wi
            good[rid] = {"o": o, "counties": counties, "cands": cands, "notes": notes}
            order.append(rid)

    # ---- 3. the rows
    race_rows, cand_rows, places = [], [], {}
    flagged = 0
    for rid in order:
        if rid not in good:
            continue
        R = good[rid]
        o = R["o"]
        note = " ".join(R["notes"]) or None
        flagged += sum(1 for t in [note] + [c["note"] for c in R["cands"]] if page_would_drop(t))
        race_rows.append((rid, STATE, o["level"], o["office_kind"], o["office"], o["jurisdiction"], o["jurisdiction_id"],
                          json.dumps(R["counties"]), o["district"], o["seat"], o["special"], 1, None, None, None, GENERAL, note))
        seen = set()
        for c in R["cands"]:
            if c["name"] in seen:
                checks.append(f"{rid}: two candidates would be shown under one name; the second is left out")
                continue
            seen.add(c["name"])
            party = PARTIES[c["code"]]
            cand_rows.append((rid, "general", GENERAL, c["name"], party, party_code(party), c["order"], 0, c["wi"], None, None, None,
                              None, c["src"], c["note"]))
        if o["place"]:
            kind, pid, pname = o["place"]
            places.setdefault(pid, [kind, pname, set()])[2].update(R["counties"])
        stats["contests"] += 1
        stats[f"level {o['level']}"] += 1
        stats[f"kind {o['office_kind']}"] += 1
        stats["special"] += o["special"]
        stats["no candidate"] += 0 if R["cands"] else 1
        if o["office_kind"] == "district_attorney" and o["level"] == "county" and o["office"].startswith("Criminal"):
            stats["criminal district attorneys"] += 1
        if o["office_kind"] == "county_commissioner":
            stats["commissioners, unexpired"] += o["special"]
        if o["office_kind"] in ("sheriff", "sheriff_tax_assessor_collector", "tax_assessor_collector", "county_attorney", "constable") \
                or (o["office_kind"] == "district_attorney" and not o["office"].startswith("Criminal")):
            stats["other-year offices"] += 1
            stats["other-year offices, unexpired"] += o["special"]
    stats["candidates"] = len(cand_rows)
    stats["candidates from the certification"] = sum(1 for c in cand_rows if c[13] == SRC_CERT_LOCAL)
    stats["candidates from the list"] = sum(1 for c in cand_rows if c[13] == SRC_LIST)
    if flagged:
        checks.append(f"{flagged} notes read like contact details to the page's last check and would be left off the page")
    place_rows = [(kind, pid, pname, json.dumps(sorted(cs)), SRC_CERT_LOCAL) for pid, (kind, pname, cs) in sorted(places.items())]
    counties = sorted({c for r in race_rows for c in json.loads(r[7])})
    return {"races": race_rows, "cands": cand_rows, "places": place_rows, "gaps": gaps, "checks": checks, "stats": stats, "off": off,
            "counties": counties, "differ_in": differ_in, "list_day": list_day, "cert_words": cert_words}


# ---------- the load ----------

def load(db_path, say=print, keep_dir=FED_FOLDER, local_dir=LOCAL_FOLDER, use_list=True):
    net.patient_lookups()
    cmap = counties()
    by_geoid = {g: full for g, full in cmap.values()}
    seats, offices, as_of, forms = roster()
    shown = shown_with(forms)
    checks, info = [], []

    # 1. the November certification
    net.download(fed.URL, CERT_PATH, max_age_days=30, say=say)
    c_races, listed, c_left, c_facts = read_cert(CERT_PATH, cmap)
    where, lists, disagree = {}, {}, []
    for (rid, geoid), cands in sorted(listed.items()):
        where.setdefault(rid, set()).add(geoid)
        first = lists.setdefault(rid, (geoid, cands))
        if first[1] != cands and rid not in disagree:
            disagree.append(rid)
    for rid in disagree:
        checks.append(f"{rid}: the counties' certification lists disagree; its November candidates are left out")
    for rid, r in c_races.items():
        if r.get("fixed_counties") and where.get(rid, set()) - set(r["fixed_counties"]):
            checks.append(f"{rid}: a county court race listed in {len(where[rid])} counties")
        if r["statewide"] and len(where.get(rid, ())) != N_COUNTIES:
            checks.append(f"{rid}: a statewide contest listed in {len(where.get(rid, ()))} of {N_COUNTIES} counties")

    # which seats: every Senate and House seat the certification lists; statewide offices checked against the list above
    sen = sorted(int(r["district"]) for r in c_races.values() if r["office_kind"] == "state_senate" and not r["special"])
    hou = sorted(int(r["district"]) for r in c_races.values() if r["office_kind"] == "state_house" and not r["special"])
    if hou != list(range(1, 151)):
        checks.append(f"House districts on the certification are not all 150 (missing {sorted(set(range(1, 151)) - set(hou))})")
    if len(sen) != len(set(sen)) or not sen or any(not 1 <= d <= 31 for d in sen):
        checks.append(f"Senate districts on the certification: {sen}")
    missing_exec = sorted(k for k, (key, *_r) in EXEC.items() if f"2026-{STATE}-{key}" not in c_races)
    if missing_exec:
        info.append("statewide offices not on the certification this year: " + ", ".join(missing_exec))

    general = {}
    for rid in c_races:
        if rid in disagree or rid not in lists:
            continue
        general[rid] = [(shown(n), code, order) for order, (n, code) in enumerate(lists[rid][1], start=1)]
        seen_codes = Counter(code for _n, code, _o in general[rid] if code in PARTIES and code not in ("IND", "W-I"))
        if any(v > 1 for v in seen_codes.values()):
            checks.append(f"{rid}: two candidates of one party on the certification")

    # 2. the primaries and runoffs, from the official canvass, checked against the election records
    meta = fed.election_records(FED_FOLDER, say)
    books, printed = {}, {}
    for (kind, code), (_date, ename, _t) in fed.ELECTIONS.items():
        m = meta[f"{kind}-{code}"]
        book, stamp, d, _left = read_canvass(os.path.join(FED_FOLDER, m["file"]), ename, code, cmap)
        books[(kind, code)] = book
        printed[(kind, code)] = stamp
        checks += d
    # the election records against the canvass. The records' race names leave out "UNEXPIRED TERM", so races are
    # compared by seat (the key without -UNEXP), every race of a seat together; votes and totals must be equal, and
    # names the same person (the two sometimes print a name differently: JAMES FRANKLIN ALVARADO, JAMES ALVARADO)
    recs, rec_path = records(meta, keep_dir, say)
    rec_checked, rec_names = 0, []
    seat = lambda rid: rid[:-len("-UNEXP")] if rid.endswith("-UNEXP") else rid
    for (kind, code), book in books.items():
        rec, mine = {}, {}
        for r in recs[f"{kind}-{code}"]["races"]:
            c = classify(r["N"], cmap)
            if isinstance(c, dict):
                rec.setdefault(seat(c["race_id"]), []).append((r["T"], sorted(((v, strip_mark(n)) for n, _p, v in r["C"]), reverse=True)))
            elif c is None:
                checks.append(f"{kind}-{code}: the election record has an office this loader does not know: {r['N']!r}")
        for rid, c in book.items():
            mine.setdefault(seat(rid), []).append((c["total"], sorted(((v, strip_mark(n)) for n, v in c["cands"]), reverse=True)))
        for key in sorted(set(rec) | set(mine)):
            a, b = sorted(rec.get(key, [])), sorted(mine.get(key, []))
            rec_checked += 1
            same_votes = [(t, [v for v, _n in cs]) for t, cs in a] == [(t, [v for v, _n in cs]) for t, cs in b]
            if not same_votes:
                checks.append(f"{kind}-{code}, {key}: the election record's votes differ from the canvass report's"
                              + (" (a one-candidate primary; no votes are stored for it)" if all(len(cs) == 1 for _t, cs in a + b) else ""))
            elif any(not same_person(x, y) for (_t, ca), (_u, cb) in zip(a, b) for (_v, x), (_w, y) in zip(ca, cb)):
                rec_names.append(f"{kind}-{code} {key}")

    # a canvass race is filed under the certification's race for the same seat when the two disagree only on whether
    # it is for the rest of a term, and there is just one such race on the certification
    relabeled = []
    for (kind, code), book in books.items():
        for rid in list(book):
            if rid in c_races:
                continue
            fit = [x for x in (seat(rid), seat(rid) + "-UNEXP") if x in c_races]
            if len(fit) == 1 and fit[0] not in book:
                book[fit[0]] = book.pop(rid)
                relabeled.append(f"{kind}-{code} {rid} -> {fit[0]}")
            else:
                checks.append(f"{rid}: in the {kind} {code} canvass but not on the November certification; its primary is not stored")

    prim, nominee, fields = [], {}, Counter()
    for code in PRIMARY_PARTIES:
        party = PARTIES[code]
        primary, runoff = books[("primary", code)], books[("runoff", code)]
        for rid, c in sorted(primary.items()):
            if rid not in c_races:
                continue
            cands, total = c["cands"], c["total"]
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) == 1:
                nominee[(rid, code)] = ("primary", cands[0][0])
                continue
            fields[c_races[rid]["office_kind"]] += 1
            went, notes = set(), {}
            if ranked[0][1] * 2 > total:
                winners = {ranked[0][0]}
                nominee[(rid, code)] = ("primary", ranked[0][0])
            else:
                r = runoff.get(rid)
                on = [n for n, pc, _o in general.get(rid, []) if pc == code]
                lead, second = shown(ranked[0][0]), shown(ranked[1][0])
                if not r and any(same_person(x, lead) for x in on) and not any(same_person(x, second) for x in on):
                    winners = {ranked[0][0]}
                    nominee[(rid, code)] = ("primary", ranked[0][0])
                    notes = {ranked[0][0]: fed.NO_RUNOFF_LEAD, ranked[1][0]: fed.NO_RUNOFF_SECOND}
                    info.append(f"{rid} {party}: no majority on March 3 and no runoff on May 26; the November certification names the leader")
                elif not r:
                    checks.append(f"{rid} {party}: no majority on March 3 and no runoff in the May 26 canvass")
                    winners = set()
                else:
                    pair = {n for n, _v in r["cands"]}
                    if len(ranked) > 2 and ranked[1][1] == ranked[2][1]:
                        checks.append(f"{rid} {party}: a tie for second place on March 3")
                    if pair != {ranked[0][0], ranked[1][0]}:
                        checks.append(f"{rid} {party}: the runoff's pair is not the primary's top two")
                    winners = went = pair
            for n, votes in cands:
                prim.append({"rid": rid, "election": f"primary-{code}", "date": PRIMARY, "raw": n, "name": shown(n), "code": code,
                             "votes": votes, "pct": round(100 * votes / total, 1) if total else None,
                             "outcome": ("advanced" if n in winners else "lost") if winners else None,
                             "src": SRC_CANVASS[("primary", code)], "note": fed.RUNOFF_NOTE if n in went else notes.get(n)})
        for rid, c in sorted(runoff.items()):
            if rid not in c_races:
                continue
            cands, total = c["cands"], c["total"]
            if rid not in primary:
                checks.append(f"{rid} {party}: a runoff with no March 3 contest")
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) != 2 or ranked[0][1] == ranked[1][1]:
                checks.append(f"{rid} {party}: the runoff has {len(cands)} candidates or a tie")
                continue
            nominee[(rid, code)] = ("runoff", ranked[0][0])
            for n, votes in cands:
                prim.append({"rid": rid, "election": f"runoff-{code}", "date": RUNOFF, "raw": n, "name": shown(n), "code": code,
                             "votes": votes, "pct": round(100 * votes / total, 1) if total else None,
                             "outcome": "advanced" if n == ranked[0][0] else "lost", "src": SRC_CANVASS[("runoff", code)], "note": None})

    # each nominee must be the party's candidate on the November certification
    not_on = []
    for (rid, code), (stage, raw) in sorted(nominee.items()):
        noted = False
        who = shown(raw)
        on = [n for n, pc, _o in general.get(rid, []) if pc == code]
        if any(same_person(x, who) for x in on):
            continue
        not_on.append(rid)
        note = (f"Won the nomination; the Secretary of State's November certification names {on[0]} as the party's candidate instead."
                if on else "Won the nomination; not on the Secretary of State's November certification.")
        for p in prim:
            if p["rid"] == rid and p["election"] == f"{stage}-{code}" and p["raw"] == raw:
                p["note"] = " ".join(x for x in (p["note"], note) if x)
                noted = True
        if rid not in disagree:
            info.append(f"{rid}: the {PARTIES[code]} nominee in the canvass is not the party's candidate on the November certification"
                        + (" (another candidate is listed" if on else " (none is listed")
                        + ("; the stored primary row says so)" if noted else "; a one-candidate primary, not stored)"))
    # a party's November candidate with no March 3 contest for that party (a nominee named by the party after filing)
    no_primary = sorted({rid for rid, cs in general.items() for _n, code, _o in cs
                         if code in PRIMARY_PARTIES and rid not in books[("primary", code)]})

    # 3. holders, the sitting member and the canvass's incumbent marks
    holders, n_holder = {}, {}
    for rid, r in c_races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no one in this office."
        else:
            n_holder[rid] = NO_ROSTER
        holders[rid] = h
    sitting, marked_used, mark_diff, mark_agree, mark_matched = {}, [], [], 0, []
    for rid, r in c_races.items():
        # every name in the race (November, the fields, the runoffs), and every canvass name with its "(I)" mark,
        # one-candidate primaries included
        canv = [(shown(n), is_marked(n)) for book in books.values() if rid in book for n, _v in book[rid]["cands"]]
        names = [n for n, _c, _o in general.get(rid, [])] + [n for n, _m in canv]
        marked = [n for n, m in canv if m]
        h = holders[rid]
        if h:
            fit = [n for n in names if holder_fits(n, h)]
            fam = {family_of(h["full"]), fold(h["last"])} - {""}
            by_mark = [x for x in marked if family_of(x) in fam]
            if fit and all(same_person(fit[0], x) for x in fit):
                sitting[rid] = ({squash(x) for x in fit}, h["id"])
            elif fit:
                checks.append(f"{rid}: more than one candidate's name fits the roster's holder; none is marked as the sitting member")
            elif by_mark and all(same_person(by_mark[0], x) for x in by_mark):
                # the given names do not fit (Jolanda for Jo), but the canvass marks a candidate of the holder's family
                # name as the incumbent: that candidate is taken, and listed
                sitting[rid] = ({squash(x) for x in names if any(same_person(x, y) for y in by_mark)}, h["id"])
                mark_matched.append(rid)
                fit = by_mark
            in_canvass = [n for n, _m in canv if holder_fits(n, h) or n in fit]
            if marked and not any(holder_fits(x, h) or x in fit for x in marked):
                mark_diff.append(f"{rid}: the canvass marks a candidate as the incumbent whose name does not fit the roster's holder")
            elif in_canvass and not marked:
                mark_diff.append(f"{rid}: the roster's holder is in the primary canvass without its incumbent mark")
            elif marked:
                mark_agree += 1
        elif r["chamber"] or r["roster"]:
            if marked:
                mark_diff.append(f"{rid}: the roster lists no holder, and the canvass marks a candidate as the incumbent")
        elif marked:
            if all(same_person(marked[0], x) for x in marked):
                sitting[rid] = ({squash(x) for x in names if any(same_person(x, y) for y in marked)}, None)
                marked_used.append(rid)
            else:
                checks.append(f"{rid}: the canvass marks more than one person as the incumbent")

    def inc_of(rid, name):
        return rid in sitting and squash(name) in sitting[rid][0]

    # 4. rows
    cand = []
    for rid, cs in sorted(general.items()):
        for name, code, order in cs:
            party = PARTIES[code]
            inc = inc_of(rid, name)
            cand.append((rid, "general", GENERAL, name, party, party_code(party), order, 1 if inc else 0, int(code == "W-I"),
                         None, None, None, sitting[rid][1] if inc else None, SRC_CERT, None))
    for p in prim:
        party = PARTIES[p["code"]]
        inc = inc_of(p["rid"], p["name"])
        cand.append((p["rid"], p["election"], p["date"], p["name"], party, party_code(party), None, 1 if inc else 0, 0, p["votes"],
                     p["pct"], p["outcome"], sitting[p["rid"]][1] if inc else None, p["src"], p["note"]))
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"Texas (state races): two candidates shown under one name in one election ({len(dup)} cases, e.g. {dup[0][0]})")

    race_rows, place_rows = [], []
    senate_up = ", ".join(str(d) for d in sen)
    for rid, r in sorted(c_races.items()):
        h = holders[rid]
        note = []
        if r["special"]:
            note.append(SPECIAL_NOTE)
        if rid in disagree:
            note.append("The counties' copies of the certification list this race differently, so its November candidates are not shown.")
        if r["office_kind"] == "state_senate" and not r["special"]:
            note.append(f"Senate terms are staggered: the certification lists {len(sen)} of the Texas Senate's 31 seats this year "
                        f"(districts {senate_up}).")
        if r["office_kind"] == "governor" or r["office_kind"] == "lieutenant_governor":
            note.append("The Governor and Lieutenant Governor are elected separately in Texas.")
        if n_holder.get(rid):
            note.append(n_holder[rid])
        if rid in marked_used:
            note.append(MARK_NOTE)
        cids = None if r["statewide"] else json.dumps(sorted(r.get("fixed_counties") or where.get(rid, ())))
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], cids,
                          r["district"], r["seat"], r["special"], r["partisan"], h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL, " ".join(note) or None))
    places = {}
    for rid, r in c_races.items():
        if r["place"]:
            kind, pid, pname = r["place"]
            cs = places.setdefault((kind, pid), [pname, set()])[1]
            cs.update(where.get(rid, ()))
    place_rows = [("county", g, full, json.dumps([g]), SRC_COUNTIES) for g, full in sorted(by_geoid.items())]
    place_rows += [(k, pid, pname, json.dumps(sorted(cs)) if cs else None, SRC_CERT) for (k, pid), (pname, cs) in sorted(places.items())]

    # privacy: nothing that looks like a contact detail in any stored name or note
    for row in cand:
        for v in (row[3], row[14]):
            if v and CONTACT.search(v):
                raise SystemExit(f"Texas (state races): a stored name or note for {row[0]} looks like a contact detail; nothing written")
    for row in race_rows:
        if row[16] and CONTACT.search(row[16]):
            raise SystemExit(f"Texas (state races): the note for {row[0]} looks like a contact detail; nothing written")

    # 4b. the local rows: the county and precinct offices, county courts and district attorneys the state part leaves,
    # from the same certification, with the Secretary's candidate list as the second route
    cert_day = c_facts["signed"] or "2026-08-28"
    contests, l_tally = cert_local(CERT_PATH, cmap)
    lst = candidate_list(local_dir, cmap, say) if use_list else None
    jd_counties = {}
    for rid, r in c_races.items():
        if r["office_kind"] == "district_court" and r["place"] and r["place"][0] == "judicial":
            jd_counties.setdefault(r["district"], set()).update(where.get(rid, ()))
    loc = local_rows(contests, lst, cmap, by_geoid, shown_local(shown), jd_counties, cert_day)
    clash = {r[0] for r in race_rows} & {r[0] for r in loc["races"]}
    if clash or len({r[0] for r in loc["races"]}) != len(loc["races"]):
        raise SystemExit(f"Texas (local races): a local race id is used twice ({sorted(clash)[0] if clash else 'among the local rows'}); nothing was changed")
    if len({(c[0], c[3]) for c in loc["cands"]}) != len(loc["cands"]):
        raise SystemExit("Texas (local races): two local candidates under one name in one contest; nothing was changed")
    two_readers = all(tuple(c_left.get(w, (0, 0))) == tuple(l_tally.get(w, (0, 0))) for w in LOCAL_WORDS)
    if not two_readers:
        loc["checks"].append("the state part and the local part count the certification's county and district headings or their candidate "
                             "lines differently: " + "; ".join(f"{w} {tuple(c_left.get(w, (0, 0)))} against {tuple(l_tally.get(w, (0, 0)))}"
                                                               for w in LOCAL_WORDS))
    ls, l_off = loc["stats"], loc["off"]
    place_rows += loc["places"]
    off_words = ", ".join(f"{v} {LIST_STATUS.get(k, 'marked ' + (k or 'without a status'))}" for k, v in sorted(l_off.items(), key=lambda x: -x[1]))
    n_off = sum(l_off.values())
    list_adds_up = not lst or len(lst["rows"]) == (ls["list rows: printed"] + ls["list rows: write-ins"] + n_off
                                                   + ls["list rows without a readable name"] + ls["list rows: in contests not loaded"])
    if not list_adds_up:
        loc["checks"].append("the candidate list's kept rows are not all accounted for (see the count above)")
    kinds_words = ", ".join(f"{k[5:].replace('_', ' ')} {v:,}" for k, v in sorted(ls.items(), key=lambda x: -x[1]) if k.startswith("kind "))
    same_counties = N_COUNTIES - len(loc["differ_in"])

    calendar = (
        "On November 3, 2026 Texas counties elect, on party lines, a county judge, the county commissioners for precincts 2 and 4, a "
        "district clerk and a county clerk, a county treasurer and a county surveyor where the county has one, the judges of the county "
        "courts at law and the justices of the peace. "
        f"The Secretary of State's lists also carry a criminal district attorney in {ls['criminal district attorneys']} counties, "
        f"{ls['commissioners, unexpired']} county commissioners elected for the rest of a term, and {ls['other-year offices']} contests "
        "for a sheriff, tax assessor-collector, county attorney, constable or district attorney, "
        f"{ls['other-year offices, unexpired']} of them for the rest of a term. "
        "Cities, school districts and water, hospital and other local districts hold their own elections on a uniform date, the first "
        "Saturday in May or the November date, and the Secretary of State's calendar says many use May.")
    coverage = (
        f"Loaded from the Secretary of State's Ballot Certification Report ({loc['cert_words']}), read county by county for all "
        f"{N_COUNTIES} counties: every county and precinct office, county court, criminal district attorney and district attorney it "
        f"prints, {ls['certification contests']:,} contests and {ls['certification candidates']:,} candidates, all elected on party lines"
        + (f"; and from the Secretary's candidate list ({loc['list_day']}), the same system read live, {ls['write-ins']} declared write-in "
           f"candidates and {ls['write-in only contests'] + ls['contests with no candidate'] + ls['list-only contests with a printed candidate']} "
           "contests the certification does not print. " if lst else ". The Secretary's candidate list could not be read, so declared "
           "write-in candidates are missing. ")
        + "The Secretary's cover certifies the state and district offices and does not say who certified the county and precinct names "
          "printed in the same report, so a county's own sample ballot is the authority. Left out: "
        + (f"the {n_off} candidacies the list marks as ended ({off_words}); " if n_off else "")
        + "offices that drew no candidate; every city, school district and special district election and the appraisal district directors, "
          "which have no statewide list; ballot propositions; local primaries.")
    note_rows = [
        (STATE, "local_calendar", calendar,
         "Texas Secretary of State, Offices up for Election in 2026 (2026 candidate's guide) and Important Election Dates; Texas Election "
         "Code 41.001 (uniform election dates); counts from the Ballot Certification Report", OFFICES_URL),
        (STATE, "local_coverage", coverage,
         "Texas Secretary of State, Ballot Certification Report, 2026 November General Election, and Candidate Information (the "
         "Secretary's candidate list)", fed.URL),
    ]
    gap_rows = loc["gaps"] + [
        (STATE, "state", STATE, NAME, "city, school district and special district races",
         "The Secretary of State's certification covers federal, state, district, county and precinct offices only. Cities, school "
         "districts and water, hospital and other districts that vote on November 3 publish their candidates county by county or one by "
         "one, with no statewide list, so none of them is here yet.", COUNTY_OFFICES_URL),
        (STATE, "state", STATE, NAME, "appraisal district directors",
         "Counties of 75,000 people or more elect three directors of their appraisal district at the general election for state and "
         "county officers (Tax Code 6.0301). The candidates file with the county clerk or elections administrator, and no statewide list "
         "names them.", TAX_CODE_URL),
        (STATE, "state", STATE, NAME, "offices no candidate filed for",
         "The certification and the candidate list name candidates, so a county or precinct office that drew no candidate and no declared "
         "write-in is in neither and is not shown. The county's own sample ballot is the place to check.", fed.URL),
    ]
    if not lst:
        gap_rows.append((STATE, "state", STATE, NAME, "declared write-in candidates",
                         "The Secretary of State's candidate list, which names the declared write-in candidates and marks who has left a "
                         "race, could not be read when this was loaded, so the local races here come from the certification alone.", LIST_PAGE))
    for words, texts in [(f"the gap '{g[4]}' ({g[2]})", g[3:6]) for g in gap_rows] + [(f"the note {n[1]}", n[2:4]) for n in note_rows]:
        if any(page_would_drop(v) for v in texts):
            loc["checks"].append(f"{words} reads like contact details to the page's last check")

    # 5. sources and the write
    n_gen = sum(1 for c in cand if c[1] == "general")
    left_words = "; ".join(f"{k} ({a:,} county lists, {b:,} candidate lines)" for k, (a, b) in sorted(c_left.items()))
    cert_lines = sum(len(v) for (rid, _g), v in listed.items() if rid in general)
    cert_note = (f"Read county by county, all {N_COUNTIES} counties, {c_facts['pages']:,} pages (the cover and "
                 f"{c_facts['pages'] - 1:,} report pages, every page stamp accounted for): offices, names and parties only. "
                 f"{len(c_races)} state races kept ({cert_lines:,} county lines of their candidates; every county's list of each race "
                 "agreed" + (f" except {', '.join(disagree)}, left out" if disagree else "") + "). The list's order is kept as the ballot "
                 "order. Left for the federal pages, or read into the local races (the next source): " + left_words
                 + ". A race's county_ids are the counties whose lists carry it. Names are printed in capitals and shown in ordinary "
                 "capitals (a sitting member as the roster spells the name).")
    src = [(SRC_CERT, STATE, "official candidate list", "Texas Secretary of State",
            "Ballot Certification Report, 2026 November General Election (state and district offices)", fed.URL, c_facts["signed"] or "2026-08-28",
            mdate(CERT_PATH), sha_of(CERT_PATH), n_gen, cert_note)]
    src.append((SRC_CERT_LOCAL, STATE, "official candidate list", "Texas Secretary of State",
                "Ballot Certification Report, 2026 November General Election (county and precinct offices, county courts and district "
                "attorneys)", fed.URL, cert_day, mdate(CERT_PATH), sha_of(CERT_PATH), ls["candidates from the certification"],
                f"The same report, read county by county for all {N_COUNTIES} counties: under each county, every heading for a county or "
                f"precinct office, a county court, a criminal district attorney or a district attorney, and the name and party lines under "
                f"it; the report has no contact columns. {ls['lines']:,} candidate lines under {ls['printed']:,} printed contests gave "
                f"{ls['certification candidates']:,} candidates in {ls['certification contests']:,} contests ({ls['in several counties']} "
                "printed under more than one county, every copy agreeing"
                + (f"; {ls['printed, not loaded']} printed contests could not be read and are in the gaps" if ls["printed, not loaded"] else "")
                + "). The state part of this loader counts the same headings and lines"
                + ("" if two_readers else " differently (see the report)")
                + ". Every one of these offices is elected on party lines. The report's order is kept as the ballot order where it is the "
                "order of the party columns (Election Code 52.091: Republican, Democratic, Libertarian, Green, then independents): "
                f"{ls['with ballot order']:,} of {ls['certification contests']:,} contests. The Secretary's cover certifies the state and "
                "district offices and does not say who certified the county and precinct names. Names are printed in capitals and shown "
                "in ordinary capitals."))
    if lst:
        src.append((SRC_LIST, STATE, "official candidate list", "Texas Secretary of State",
                    "Candidate Information: candidates in the 2026 November General Election (the Secretary's candidate list, as its own "
                    "page asks for it)", LIST_PAGE, "", lst["fetched"], lst["sha256"], len(lst["rows"]),
                    f"One request, the one the page itself makes, answered with {lst['rows_in']:,} rows ({lst['bytes']:,} bytes; the SHA-256 "
                    f"is of the bytes as fetched). Kept: the {len(lst['rows']):,} rows for county and precinct offices, county courts and "
                    "district attorneys, cut down in memory to office type, office number, county, office title, the name as on the ballot "
                    "(not kept for anyone the list no longer counts as a candidate), party, the two status codes and the kind of "
                    "candidate. The mailing address, e-mail, website and occupation columns "
                    f"are never read; {lst['blanked']} kept cells looked like contact details and were blanked. A contest is the list's "
                    "office number; a candidate counts when the list's status is Candidate in the General Election; party W is a declared "
                    f"write-in. Compared with the certification contest by contest: {ls['contests the same in both lists']:,} read the "
                    f"same, {ls['contests that differ']} differ in a name, {ls['contests under another number']} "
                    f"filed under another precinct number, {ls['contests not on the list']} not on the list at all; county by county, "
                    f"{same_counties} of {N_COUNTIES} counties read the same throughout. From the list alone: {ls['write-ins']} declared "
                    f"write-in candidates, {ls['write-in only contests']} contests where only a write-in declared, "
                    f"{ls['contests with no candidate']} with no candidate left"
                    + (f". Left off: the {n_off} candidacies the list marks as ended ({off_words})" if n_off else "")
                    + f". Every kept row is accounted for: {ls['list rows: printed']:,} printed candidates, {ls['list rows: write-ins']} "
                    f"declared write-ins, {n_off} ended, {ls['list rows without a readable name']} without a readable name, "
                    f"{ls['list rows: in contests not loaded']} in contests not loaded" + ("" if list_adds_up else " (which does not add up)") + "."))
    for (kind, code), (date, ename, _t) in fed.ELECTIONS.items():
        m = meta[f"{kind}-{code}"]
        book = {rid: c for rid, c in books[(kind, code)].items() if rid in c_races}
        title = ename.title().replace("2026 ", "")
        src.append((SRC_CANVASS[(kind, code)], STATE, "official results", "Texas Secretary of State, Elections Division",
                    f"Official Canvass Report: 2026 {title}, {dt.date.fromisoformat(date).strftime('%B %d, %Y').replace(' 0', ' ')}",
                    m["url"], printed[(kind, code)], m.get("read", ""), m.get("sha256") or sha_of(os.path.join(FED_FOLDER, m["file"])),
                    sum(1 for p in prim if p["src"] == SRC_CANVASS[(kind, code)]),
                    f"The Official Canvass Report the Secretary of State's election results system offers for this election ({fed.REPORTS_PAGE}, "
                    f"election {m['id']}, marked official), printed {printed[(kind, code)]}. The state offices read ({len(book)}, "
                    f"{sum(len(c['cands']) for c in book.values())} candidates; stored: the fields of two or more): each candidate's canvass votes; every office's Total line equals the sum of its candidates and every printed percent "
                    "matches; the election record's own figures equal the report's, race by race. The report carries no write-in "
                    "line. Names are shown in ordinary capitals; the report's incumbent mark \"(I)\" is taken off the name."))
    src.append((SRC_RECORDS, STATE, "official results", "Texas Secretary of State, Elections Division",
                "Election results system records (StateWide and Districted races) for the 2026 primaries and runoffs",
                f"{fed.API}/election/<id>", "", mdate(rec_path), sha_of(rec_path), sum(len(v["races"]) for v in recs.values()),
                "Elections " + ", ".join(str(v["id"]) for v in recs.values()) + ": only race name, total and each candidate's name, "
                f"party and votes are kept. {rec_checked} state races compared with the canvass reports."))
    src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
                "Texas legislators and statewide officials, as loaded into state_tx.sqlite", "https://github.com/openstates/people",
                as_of, as_of, "", len(seats) + len(offices),
                "Today's holder of each seat and office. The roster carries the Governor, Lieutenant Governor, Attorney General and "
                "Secretary of State only among statewide offices. A candidate is marked as the sitting member only when the name fits "
                "the holder of that seat and every fitting name in the race is the same person. For offices the roster does not "
                "carry, the incumbent flag is the primary canvass's own \"(I)\" mark, with no member id."))
    src.append((SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
                "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
                "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP), sha_of(COUNTY_ZIP),
                N_COUNTIES, "Texas's 254 counties: names and GEOIDs only."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:      # Texas's rows only, in one transaction: the state rows as before, then the local rows, gaps and notes
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-TX-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'TX'")
        con.execute("DELETE FROM sl_sources WHERE state = 'TX'")
        con.execute("DELETE FROM sl_places WHERE (kind = 'county' AND id GLOB '48[0-9][0-9][0-9]') OR id LIKE 'TX-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = 'TX'")
        con.execute("DELETE FROM sl_notes WHERE state = 'TX'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + loc["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + loc["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
        con.executemany("INSERT OR REPLACE INTO sl_gaps VALUES (?,?,?,?,?,?,?)", gap_rows)
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", note_rows)
    con.close()

    # 6. the report: counts, race keys and office titles only
    def grp(rid):
        r = c_races[rid]
        return r["office_kind"] if r["level"] in ("legislature", "court") else ("sboe" if r["office_kind"] == "state_board_of_education" else "statewide")
    order = ["state_senate", "state_house", "statewide", "sboe", "supreme_court", "court_of_criminal_appeals", "court_of_appeals", "district_court"]
    by = Counter(grp(rid) for rid in c_races)
    gen_by = Counter(grp(c[0]) for c in cand if c[1] == "general")
    inc_by = Counter(grp(c[0]) for c in cand if c[1] == "general" and c[7])
    pf = Counter(grp(p["rid"]) for p in prim if p["election"].startswith("primary"))
    fld = Counter()
    for (rid, e) in {(p["rid"], p["election"]) for p in prim}:
        fld[(grp(rid), e.split("-")[0])] += 1
    sp = Counter(grp(rid) for rid, r in c_races.items() if r["special"])
    say(f"    Texas (state races): {len(c_races)} races, {n_gen} candidates on the November ballot; "
        + "; ".join(f"{k}: {by[k]} races" + (f" ({sp[k]} for the rest of a term)" if sp[k] else "") + f", {gen_by[k]} candidates, "
                    f"{fld[(k, 'primary')]} primary fields ({pf[k]} candidates), {fld[(k, 'runoff')]} runoffs, sitting member on the November ballot in {inc_by[k]}"
                    for k in order if by[k]))
    say(f"    Texas (state races): Senate seats up: {senate_up}. Counts: {cert_lines:,} certification lines for these races across "
        f"{len({g for (rid, g) in listed if rid in general})} counties = {n_gen} candidates, one per race; "
        f"{sum(len(c['cands']) for (k, cd), b in books.items() for rid, c in b.items() if rid in c_races)} canvass candidate lines "
        f"for these races, {len(prim)} stored (fields only), every Total line equal to its candidates' sum"
        + ("" if not any("Total" in c or "percent" in c for c in checks) else " EXCEPT as listed below"))
    say(f"    Texas (state races): primaries reconciled with the election records: {rec_checked} race comparisons; "
        f"{len(nominee)} nominations checked against the certification ({len(not_on)} differ); "
        f"{len(no_primary)} party candidates on the certification with no March 3 contest for their party"
        + (f" ({', '.join(no_primary[:8])}{' ...' if len(no_primary) > 8 else ''})" if no_primary else "")
        + f"; the canvass's incumbent marks agree with the roster in {mark_agree} races and differ in {len(mark_diff)}; "
        f"incumbent flag from the canvass mark (offices the roster lacks) in {len(marked_used)} races")
    say(f"    Texas (state races): left for the federal pages or a local phase: {left_words}")
    for line in info:
        say(f"    Texas (state races): {line}")
    if mark_matched:
        say(f"    NOTE Texas (state races): sitting member taken from the canvass's incumbent mark and the roster's family name "
            f"(the given names do not fit): {', '.join(sorted(mark_matched))}")
    if relabeled:
        say(f"    NOTE Texas (state races): the canvass and the certification disagree on whether these are for the rest of a term; "
            f"filed under the certification's race: {'; '.join(relabeled)}")
    if rec_names:
        say(f"    NOTE Texas (state races): the election record prints a name differently from the canvass (votes equal): {'; '.join(rec_names)}")
    no_mark = sorted(d.split(":")[0] for d in mark_diff if "without its incumbent mark" in d)
    if no_mark:
        say(f"    NOTE Texas (state races): the roster's holder is in the primary canvass without the canvass's incumbent mark (seated "
            f"since filing, or unmarked): {', '.join(no_mark)}")
    for d in mark_diff:
        if "without its incumbent mark" not in d:
            say(f"    NOTE Texas (state races): {d}")
    for c in checks:
        say(f"    CHECK Texas (state races): {c}")

    # the local rows: counts, race keys and office titles only
    say(f"    Texas (local races): {ls['contests']:,} contests, {ls['candidates']:,} candidates: county {ls['level county']:,}, district "
        f"attorneys and multicounty courts {ls['level other']:,}; {ls['special']} for the rest of a term; in {len(loc['counties'])} of "
        f"{N_COUNTIES} counties; {kinds_words}; ballot order kept in {ls['with ballot order']:,} contests; {len(loc['places'])} districts, "
        f"{len(gap_rows)} gaps written")
    say(f"    Texas (local races): reconciled with the certification: {ls['lines']:,} candidate lines under {ls['printed']:,} printed "
        f"contests = {ls['lines placed']:,} lines in {ls['printed, loaded']:,} printed contests placed, giving "
        f"{ls['certification candidates']:,} candidates in {ls['certification contests']:,} contests ({ls['in several counties']} printed "
        f"under more than one county, every copy agreeing), + {ls['lines not placed']} lines in {ls['printed, not loaded']} printed contests "
        "not placed; the state part's own count of these headings and lines "
        + ("is the same (" if two_readers else "DIFFERS (")
        + "; ".join(f"{w} {l_tally.get(w, [0, 0])[0]:,} and {l_tally.get(w, [0, 0])[1]:,}" for w in LOCAL_WORDS) + ")"
        + ("" if ls["lines placed"] + ls["lines not placed"] == ls["lines"] and ls["printed, loaded"] + ls["printed, not loaded"] == ls["printed"]
           else "  (DOES NOT ADD UP)"))
    if lst:
        say(f"    Texas (local races): the Secretary's candidate list ({lst['fetched']}; {lst['rows_in']:,} rows, {len(lst['rows']):,} kept "
            f"for local offices, {ls['list contests']:,} contests): {ls['contests the same in both lists']:,} certification contests read "
            f"the same name for name, {ls['contests that differ']} differ ({ls['names on the certification only']} names on the "
            f"certification only, {ls['names on the list only']} on the list only, {ls['party differs']} with another party; "
            f"{ls['names spelled two ways']} names spelled two ways, noted), "
            f"{ls['contests under another number']} under another precinct number, {ls['contests not on the list']} not on the "
            f"list; county by county {same_counties} of {N_COUNTIES} read the same throughout"
            + (f" (not {', '.join(by_geoid[g] for g in sorted(loc['differ_in']))})" if loc["differ_in"] else "")
            + f"; from the list alone: {ls['write-ins']} declared write-in candidates, {ls['write-in only contests']} contests with only a "
            f"write-in, {ls['contests with no candidate']} with no candidate left, {ls['list-only contests with a printed candidate']} "
            f"other contests; {ls['list contests not loaded']} list contests not loaded")
        say(f"    Texas (local races): the list's {len(lst['rows']):,} kept rows = {ls['list rows: printed']:,} printed candidates + "
            f"{ls['list rows: write-ins']} declared write-ins + {n_off} ended and left off ({off_words or 'none'}) + "
            f"{ls['list rows without a readable name']} without a readable name + {ls['list rows: in contests not loaded']} in contests not "
            "loaded" + ("" if list_adds_up else "  (DOES NOT ADD UP)"))
    else:
        say("    Texas (local races): the Secretary's candidate list was not read: no second route, no declared write-in candidates")
    for c in loc["checks"]:
        say(f"    CHECK Texas (local races): {c}")
    return len(cand) + len(loc["cands"])


if __name__ == "__main__":
    args = sys.argv[1:]
    keep, with_list = FED_FOLDER, True
    if "--keep" in args:
        i = args.index("--keep")
        keep = args[i + 1]
        del args[i:i + 2]
    if "--no-list" in args:
        args.remove("--no-list")
        with_list = False
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_tx <database file> [--keep <folder>] [--no-list]")
    load(args[0], keep_dir=keep, use_list=with_list)
