"""
ballot/state_local_ky.py - Kentucky's state races on the November 3, 2026 ballot: the nineteen even-numbered State Senate
seats (four-year terms, half the Senate every two years; the Secretary of State's list names exactly these), all 100 seats
of the House of Representatives, and the appellate court seats on the list (one Justice of the Supreme Court and three
Judges of the Court of Appeals, all nonpartisan), with each party's contested May 19 primary and its certified votes.
Kentucky elects its Governor and the other statewide officers in odd years (2027 next), so no statewide office is on the
2026 ballot.

Sources, both the state's own and both the ones the federal loader (ballot/lists/ky.py) already reads:
  - The Secretary of State's "Candidate Filings with the Office of the Secretary of State" for the 2026 General Election
    (web.sos.ky.gov/CandidateFilings/): the pages for State Senator (Default.aspx?id=11), State Representative (id=12),
    Justice of the Supreme Court (id=14) and Judge of the Court of Appeals (id=15), read with the federal loader's
    filings(): the page must be the 2026 General Election's, columns are taken by their headings, and only Name (the
    first line of the cell), Office, District/Division and Party are turned into text; the address and e-mail column is
    never read. Every group's count in its heading must match its rows. A candidate in the "Withdrawn / Deceased /
    Disqualified" group is left off and counted. Party printed "Write-In" is a declared write-in (not printed on the
    ballot). The list gives no ballot order (it goes by district, then filing); its own order within a race is kept, as
    on the federal side, write-ins left out of it. The other offices on the list (Commonwealth's Attorney, Circuit and
    District Judges, Family Court, the constitutional amendment) are local or not a candidate race and are counted only.
  - The State Board of Elections' "Official 2026 Primary Election Results" certification (the PDF the federal loader
    caches as ballot_cache/ky/ky_2026_primary_certification_of_vote_totals.pdf), its State Senator and State
    Representative sections, read with the federal loader's text-position parts. Kentucky prints a primary only when it
    is contested; each section's county rows must add up to its Total Votes row. The certification prints no write-in
    line, so a field's total is the sum of its candidates' votes. The most votes wins (no runoffs); the one on the
    November list for that party must be the field's top vote-getter.
  - Holders of each legislative seat from the Open States roster in state_ky.sqlite (legislators, is_current = 1, by
    chamber and district). The roster carries no judges, so the court seats show no holder.

Privacy: only office, district, candidate name, party, ballot order (the list's own), status and votes are read. The
filings pages are never saved: only the kept cells of each row go to ballot_cache/ky/sl_ky_2026_general_filings_state.json,
with each page's SHA-256. The certification holds names and vote counts only.

The local levels (county, city, school board, soil and water, and the trial courts), written beside the state rows
-----------------------------------------------------------------------------------------------------------------
  - The Secretary of State's "Candidate Filings with the County Clerk" (web.sos.ky.gov/CandidateFilings/countyfilings.aspx):
    one list for all 120 counties, entered by the county clerks. It is read from the page's own "Excel spreadsheet of All
    Candidates" button, posted as the page posts it with the kit's honest User-Agent. The answer is an old-format .xls
    (a BIFF8 workbook in an OLE2 file); a small reader here turns into text only the cells of the columns kept (County,
    Last Name, First Name, Middle Name, Suffix, Party, Office, Office Description, District, Unexpired, Withdrawn,
    Disqualified, Deceased). The Date filed, PO Address, PO City, PO State, PO Zip and EMail columns are never decoded,
    the file is never written anywhere, and a kept cell that looks like contact details (a clerk can type an e-mail
    address into a name column) is blanked before the rows are cached in ballot_cache/ky/local/. The page's "List All
    Candidates" view carries the same rows without the Unexpired mark, so the spreadsheet is the one read; the page's
    directory of offices gives the list's own count for every office and for the withdrawn, and each must match.
  - What a row says: the office (sixteen kinds), the county whose clerk entered it, a party, a district number for some,
    and a free-text Office Description that is the only place a city or a school district is named. A row is tied to a
    city or an independent school district only when that text fits exactly one name on the Census Bureau's lists (the
    2020 place-by-county codes, the consolidated cities file for Louisville's metro government, the 2024 unified and
    elementary school district files): the name as printed, part of exactly one name (Neon for Fleming-Neon), or one
    slip of spelling from exactly one name; or, when no city is named, because the county has one city. A county school
    district's members are elected by division (KRS 160.210), an independent district's by the whole district. Every
    such match that is not the name as printed is listed when the loader runs. A row that names no city, district or
    division that can be told is never guessed: it goes to sl_gaps, county by county, and the contests it might belong
    to say so.
  - Withdrawn, disqualified and deceased candidates are left off. Where the list still shows more than one candidate of a
    party for a seat that has one (the May primary's field, never pruned), the contest is kept without names and listed
    as a gap. A city or school district two county clerks list is one contest, each candidate once.
  - Names: the list holds the family name in capitals; names are shown in ordinary capitals, given names first, with
    Jr, Sr, II, III or IV after the family name. The list gives no ballot order, so none is stored.
  - The trial courts: District Judge, Circuit Judge (two pages; the second is the family court seats) and Commonwealth's
    Attorney from the Secretary of State's own filings pages (Default.aspx?id=17, 16, 20, 13), read with the federal
    loader's filings(); the counties of each judicial district and circuit from KRS 24A.030 and 23A.020 as the
    Legislative Research Commission publishes them.
  - The State Board of Elections' "Kentucky Election Schedule" (a table of offices by year) is read for which offices are
    regularly elected in 2026 and which are on this ballot only for the rest of a term.
  - Tables: sl_races and sl_candidates (levels county, soil_water, city, school and court), sl_places (the 120 counties
    and every city, school district and other district a contest names), sl_gaps, sl_notes (local_calendar,
    local_coverage) and sl_sources. Only Kentucky's rows are deleted and rewritten, in one transaction.

    python -m ballot.state_local_ky <path to a test database>
"""

import collections
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.parse
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot import pdftext as P  # noqa: E402
from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.lists import ky as KY  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE = "KY"
GENERAL, PRIMARY = "2026-11-03", KY.PRIMARY
ROSTER = os.path.join(HERE, "state_ky.sqlite")
SRC_LIST, SRC_CERT, SRC_ROSTER = "ky-sos-2026-state-general-filings", "ky-sbe-2026-state-primary-certification", "ky-openstates-roster"
LIST_FILE = "sl_ky_2026_general_filings_state.json"
CERT_FILE = "ky_2026_primary_certification_of_vote_totals.pdf"          # the federal loader's copy

# ---- the local offices
COUNTY_URL = "https://web.sos.ky.gov/CandidateFilings/countyfilings.aspx"
COUNTY_FILE = "ky_2026_county_clerk_filings.json"                       # in ballot_cache/ky/local/: the kept columns only
XLS_HEADINGS = ["County", "Last Name", "First Name", "Middle Name", "Suffix", "Party", "Office", "Office Description", "District",
                "Date filed", "PO Address", "PO City", "PO State", "PO Zip", "EMail", "Unexpired", "Withdrawn", "Disqualified", "Deceased"]
XLS_KEEP = ("County", "Last Name", "First Name", "Middle Name", "Suffix", "Party", "Office", "Office Description", "District",
            "Unexpired", "Withdrawn", "Disqualified", "Deceased")
COURT_FILE = "ky_2026_trial_court_filings.json"                         # in ballot_cache/ky/local/: the kept cells only
# The Secretary of State's own filings pages for the offices elected by judicial district or circuit:
# page id -> (the office as the page's heading prints it, what the home page calls the page)
COURT_PAGES = {"17": ("District Judge", "District Judge"), "16": ("Circuit Judge", "Circuit Judge"),
               "20": ("Circuit Judge", "Circuit Judge Family Court"), "13": ("Commonwealth's Attorney", "Commonwealth's Attorney")}
CENSUS_SHP = "https://www2.census.gov/geo/tiger/GENZ2024/shp/"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")          # the kit's own copy
OFFICIAL = {      # the official lists read beside the candidate lists: file in ballot_cache/ky/local/ -> address
    "places": ("census_st21_ky_place_by_county2020.txt",
               "https://www2.census.gov/geo/docs/reference/codes2020/place_by_cou/st21_ky_place_by_county2020.txt"),
    "concity": ("cb_2024_us_concity_500k.zip", CENSUS_SHP + "cb_2024_us_concity_500k.zip"),
    "unsd": ("cb_2024_21_unsd_500k.zip", CENSUS_SHP + "cb_2024_21_unsd_500k.zip"),
    "elsd": ("cb_2024_21_elsd_500k.zip", CENSUS_SHP + "cb_2024_21_elsd_500k.zip"),
    "districts": ("krs_24A_030_judicial_districts.pdf", "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=48467"),
    "circuits": ("krs_23A_020_judicial_circuits.pdf", "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=53357"),
    "schedule": ("ky_sbe_election_schedule_2026_2036.pdf", "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
}
SRC_COUNTY, SRC_COURT = "ky-sos-2026-county-clerk-filings", "ky-sos-2026-trial-court-filings"
SRC_COUNTIES, SRC_PLACES, SRC_CONCITY = "ky-census-2024-counties", "ky-census-2020-places", "ky-census-2024-consolidated-cities"
SRC_UNSD, SRC_ELSD = "ky-census-2024-unified-school-districts", "ky-census-2024-elementary-school-districts"
SRC_DISTRICTS, SRC_CIRCUITS, SRC_SCHEDULE = "ky-krs-24a-030-judicial-districts", "ky-krs-23a-020-judicial-circuits", "ky-sbe-election-schedule-2026-2036"
FIPS = "21"
TOTAL_COUNTIES = 120

# The county list's offices: office as the list prints it -> (office_kind, office as shown, how it is elected)
COUNTY_OFFICES = {
    "COUNTY JUDGE / EXECUTIVE": ("county_executive", "County Judge/Executive", "county"),
    "COUNTY CLERK": ("county_clerk", "County Clerk", "county"),
    "COUNTY ATTORNEY": ("county_attorney", "County Attorney", "county"),
    "SHERIFF": ("sheriff", "Sheriff", "county"),
    "JAILER": ("jailer", "Jailer", "county"),
    "CORONER": ("coroner", "Coroner", "county"),
    "PROPERTY VALUATION ADMINISTRATOR": ("county_assessor", "Property Valuation Administrator", "county"),
    "SURVEYOR": ("county_surveyor", "County Surveyor", "county"),
    "CIRCUIT COURT CLERK": ("clerk_of_court", "Circuit Court Clerk", "county"),
    "MAGISTRATE / JUSTICE OF THE PEACE": ("magistrate", "Magistrate/Justice of the Peace", "district"),
    "COUNTY COMMISSIONER": ("county_commissioner", "County Commissioner", "district"),
    "CONSTABLE": ("constable", "Constable", "district"),
}
OTHER_OFFICES = ("SOIL AND WATER CONSERVATION DISTRICT SUPERVISOR", "MAYOR", "CITY LEGISLATIVE BODY", "SCHOOL BOARD MEMBER")
PARTY_WORDS = {"REPUBLICAN PARTY": "Republican Party", "DEMOCRATIC PARTY": "Democratic Party", "INDEPENDENT": "Independent",
               "KENTUCKY PARTY": "Kentucky Party", "LIBERTARIAN PARTY": "Libertarian Party", "WRITE-IN": "Write-In",
               "NONPARTISAN": "Nonpartisan"}
MAJOR = ("Republican Party", "Democratic Party")
# The two merged city-county governments, as county clerks write them in the list's free-text column
MERGED_NAMES = {"48003": ("METRO", "LOUISVILLE METRO", "LOUISVILLE"), "46027": ("URBAN COUNTY", "LEXINGTON")}
MERGED_OFFICE = {"48003": "Metro Council Member", "46027": "Urban County Council Member"}
ABBR = {"MT": "MOUNT", "FT": "FORT", "ST": "SAINT", "JCT": "JUNCTION"}
COUNTY_WORDS = set("COUNTY CO OF THE FOR AND OFFICE KENTUCKY KY WRITE IN CANDIDATE UNEXPIRED TERM DISTRICT DIST DIVISION DIV NO NUMBER "
                   "MAGISTRATE MAGISTRATES JUSTICE PEACE CONSTABLE CONSTABLES COMMISSIONER COMMISSIONERS".split())
CITY_WORDS = set("CITY OF THE FOR AND COUNCIL COUNCILMAN COUNCILMEMBER COUNCILPERSON MEMBER MEMBERS COMMISSION COMMISSIONER COMMISSIONERS "
                 "MAYOR MAYORAL LEGISLATIVE BODY AT LARGE WRITE IN CANDIDATE COUNTY CO KENTUCKY KY DISTRICT DIST WARD UNEXPIRED TERM SEAT".split())
SCHOOL_WORDS = set("SCHOOL SCHOOLS BOARD OF THE FOR AND EDUCATION MEMBER MEMBERS DISTRICT DIST DIVISION DIV PUBLIC COUNTY CO BD ED "
                   "UNEXPIRED TERM WRITE IN CANDIDATE KENTUCKY KY SEAT NO NUMBER".split())
INDEPENDENT_WORDS = ("INDEPENDENT", "IND", "CITY")
NUMBER_WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10,
                "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10}
GENERATION = re.compile(r"^(?:JR|SR)\.?$|^(?:II|III|IV|V)$")
COURTESY = re.compile(r"^(?:MR|MRS|MS|MISS)\.?$")

SOIL_NOTE = ("When no more candidates file than there are supervisors to elect, they are declared elected and the contest is not "
             "printed on the ballot (KRS 262.240). The list does not say how many are being elected.")
AT_LARGE_NOTE = ("The list files this city's candidates together, with no ward or district, and does not say how many seats are being "
                 "filled.")
SEATS_NOTE = "The list does not say how many seats are being filled."
SCHOOL_AT_LARGE_NOTE = ("An independent school district's board is elected by the whole district (KRS 160.210). The list does not say "
                        "how many seats are being filled.")
UNEXPIRED_NOTE = "For the rest of an unexpired term."
CLERK_NOTE = ("For the rest of an unexpired term: circuit court clerks are elected for six years, next in 2030 (State Board of "
              "Elections' election schedule).")
CIRCUIT_NOTE = ("Circuit judges are elected for eight years, next in 2030 (State Board of Elections' election schedule); this seat is "
                "on the 2026 ballot for the time left until then.")
FAMILY_NOTE = "The Secretary of State's list files it under Circuit Judge, Family Court."
CWA_NOTE = ("Commonwealth's attorneys are elected for six years, next in 2030 (State Board of Elections' election schedule); this "
            "office is on the 2026 ballot for the time left until then.")
ONLY_WRITE_INS = "Only declared write-in candidates are on the list for this office, so no name is printed on the ballot."
LIST_AUTHORITY = "The county clerk's sample ballot is the authority."

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

# The Candidate Filings pages read here: page id -> (office as the page prints it, race prefix, level, office_kind, partisan).
PAGES = {"11": ("State Senator", "SS", "legislature", "state_senate", 1),
         "12": ("State Representative", "SH", "legislature", "state_house", 1),
         "14": ("Justice of the Supreme Court", "SC", "court", "supreme_court", 0),
         "15": ("Judge of the Court of Appeals", "COA", "court", "court_of_appeals", 0)}
KIND = {v[0]: (k,) + v[1:] for k, v in PAGES.items()}
# The certification's sections read here, and the district line each carries.
CERT_OFFICES = {"State Senator": "state_senate", "State Representative": "state_house"}
CERT_DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) (Senatorial|Representative) District$")
ORDINAL = re.compile(r"^(\d+)(?:st|nd|rd|th)$")
COA_DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) / (\d+)(?:st|nd|rd|th)$")
PRIMARY_CODE = {"Republican Party": "REP", "Democratic Party": "DEM"}
NONPARTISAN = "Nonpartisan office"
SENATE_SEATS, HOUSE_SEATS = 38, 100
RACE_COLS = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
             "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]

SENATE_NOTE = ("Kentucky senators serve four-year terms, and half the Senate is elected every two years (Kentucky Constitution, "
               "Section 31). This is one of the 19 districts, the even-numbered ones, on the Secretary of State's 2026 list.")
COURT_NOTE = ("A nonpartisan office: no party is printed on the ballot. The Open States roster does not carry judges, so no holder "
              "is shown. The Secretary of State's list names only the court seats someone filed for.")
ORDER_NOTE = ("Kentucky's candidate list gives no ballot order; candidates are kept in the list's own order (by district, then "
              "filing), declared write-ins left out of it.")
WRITE_IN = KY.WRITE_IN
CAPS = KY.CAPS
NOT_ON_LIST = KY.NOT_ON_LIST


# ------------------------------------------------------------------------------------------------ fetching and caching

def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            return net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def filings(folder, say, max_age_days=2):
    """The kept cells of the four state office pages, as JSON in the cache: {read, pages: {office: {url, sha256, groups, rows}}}.
    The pages themselves are never written anywhere."""
    path = os.path.join(folder, LIST_FILE)
    if fresh(path, max_age_days):
        return path
    keep = {"read": dt.date.today().isoformat(), "pages": {}}
    try:
        for pid, (office, *_rest) in PAGES.items():
            raw = fetch(KY.FILINGS + pid, accept="text/html", say=say)
            got = KY.filings(raw.decode("utf-8", "replace"), office)
            keep["pages"][office] = {"url": KY.FILINGS + pid, "sha256": hashlib.sha256(raw).hexdigest(),
                                     "groups": got["groups"], "rows": got["rows"]}
            time.sleep(1.5)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the Candidate Filings pages could not be read ({e}); using the copy read earlier")
            return path
        raise
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def other_offices(say):
    """The office links on the Candidate Filings home page with their counts: [(office, count)] (headings only)."""
    try:
        raw = fetch("https://web.sos.ky.gov/CandidateFilings/", accept="text/html", say=say).decode("utf-8", "replace")
    except (HTTPError, OSError):
        return None
    out = []
    for m in re.finditer(r'<a[^>]+href="[^"]*[Dd]efault\.aspx\?id=(\d+)[^"]*"[^>]*>(.*?)</a>', raw, re.S):
        text = KY.text_of(m.group(2))
        c = re.fullmatch(r"(.+?) \((\d+)\)", text)
        if c:
            out.append((m.group(1), c.group(1), int(c.group(2))))
    return out


# ------------------------------------------------------------------- a small reader for the old Excel format (.xls)
# The county filings list comes as a BIFF8 workbook inside an OLE2 compound file, and the kit has no package for that
# format. This reader gives the cells of chosen columns only: the heading row is read whole (it holds headings), every
# other row only in the columns asked for. The text of any other cell (the list's address, city, ZIP, e-mail and date
# columns) is never decoded: shared strings are kept as places in the file and turned into text one asked-for cell at
# a time.

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
OLE_MARK = 0xFFFFFFFA                 # sector numbers from here up are markers (end of chain, free, FAT, DIFAT)


class XlsError(Exception):
    pass


def ole_stream(d, wanted=("Workbook", "Book")):
    """The bytes of the workbook stream of an OLE2 compound file."""
    if d[:8] != OLE_MAGIC:
        raise XlsError("not an OLE2 compound file")
    ssz = 1 << struct.unpack_from("<H", d, 30)[0]
    if ssz not in (512, 4096):
        raise XlsError("an unusual sector size")
    cutoff = struct.unpack_from("<I", d, 56)[0]
    dir_start = struct.unpack_from("<I", d, 48)[0]
    difat = [v for v in struct.unpack_from("<109I", d, 76) if v < OLE_MARK]
    nxt, n = struct.unpack_from("<II", d, 68)

    def sec(i):
        b = d[(i + 1) * ssz:(i + 2) * ssz]
        if len(b) != ssz:
            raise XlsError("a sector lies beyond the end of the file")
        return b

    while nxt < OLE_MARK and n > 0:
        vals = struct.unpack("<%dI" % (ssz // 4), sec(nxt))
        difat += [v for v in vals[:-1] if v < OLE_MARK]
        nxt, n = vals[-1], n - 1
    fat = []
    for s in difat:
        fat += struct.unpack("<%dI" % (ssz // 4), sec(s))

    def chain(start, size=None):
        out, i, guard = [], start, 0
        while i < OLE_MARK:
            if i >= len(fat) or guard > len(fat):
                raise XlsError("a sector chain is broken")
            out.append(sec(i))
            i, guard = fat[i], guard + 1
        b = b"".join(out)
        return b if size is None else b[:size]

    directory = chain(dir_start)
    for k in range(0, len(directory), 128):
        e = directory[k:k + 128]
        if len(e) < 128 or e[66] != 2:                      # 2: a stream
            continue
        nlen = struct.unpack_from("<H", e, 64)[0]
        if e[:max(0, nlen - 2)].decode("utf-16-le", "replace") in wanted:
            start = struct.unpack_from("<I", e, 116)[0]
            size = struct.unpack_from("<Q", e, 120)[0] if ssz == 4096 else struct.unpack_from("<I", e, 120)[0]
            if size < cutoff:
                raise XlsError("the workbook stream is in the mini stream (a file this small is not expected)")
            b = chain(start, size)
            if len(b) != size:
                raise XlsError("the workbook stream is shorter than its directory entry says")
            return b
    raise XlsError("no Workbook stream in the file")


def biff_records(wb):
    i = 0
    while i + 4 <= len(wb):
        rid, ln = struct.unpack_from("<HH", wb, i)
        yield rid, wb[i + 4:i + 4 + ln]
        i += 4 + ln


def sst_spans(chunks):
    """Where each shared string's characters lie: [[(chunk, start, bytes, wide)]], one list per string, nothing decoded.
    A string's characters may run on into the next CONTINUE record, which then begins with a fresh one-byte flag."""
    _total, unique = struct.unpack_from("<II", chunks[0], 0)
    ci, pos, out = 0, 8, []

    def need(n):
        nonlocal ci, pos
        if pos >= len(chunks[ci]):
            ci, pos = ci + 1, 0
        if ci >= len(chunks) or pos + n > len(chunks[ci]):
            raise XlsError("the shared strings table ends inside a string's heading")
        b = chunks[ci][pos:pos + n]
        pos += n
        return b

    for _ in range(unique):
        cch = struct.unpack("<H", need(2))[0]
        flags = need(1)[0]
        runs = struct.unpack("<H", need(2))[0] if flags & 0x08 else 0
        ext = struct.unpack("<I", need(4))[0] if flags & 0x04 else 0
        left, wide, spans = cch, flags & 0x01, []
        while left > 0:
            if pos >= len(chunks[ci]):
                ci, pos = ci + 1, 0
                if ci >= len(chunks):
                    raise XlsError("the shared strings table ends inside a string")
                wide = chunks[ci][pos] & 0x01
                pos += 1
            room = len(chunks[ci]) - pos
            take = min(left, room // 2 if wide else room)
            if take == 0:
                raise XlsError("a shared string is split inside a character")
            nbytes = take * 2 if wide else take
            spans.append((ci, pos, nbytes, wide))
            pos += nbytes
            left -= take
        skip = 4 * runs + ext
        while skip > 0:
            if pos >= len(chunks[ci]):
                ci, pos = ci + 1, 0
                if ci >= len(chunks):
                    raise XlsError("the shared strings table ends inside a string's formatting")
            step = min(skip, len(chunks[ci]) - pos)
            pos, skip = pos + step, skip - step
        out.append(spans)
    return out


def rk_value(rk):
    if rk & 0x02:
        v = rk >> 2
        if v & 0x20000000:
            v -= 0x40000000
        v = float(v)
    else:
        v = struct.unpack("<d", struct.pack("<Q", (rk & 0xFFFFFFFC) << 32))[0]
    return v / 100.0 if rk & 0x01 else v


class Xls:
    """The first worksheet of an .xls file: cells by (row, column), turned into text only on request."""

    def __init__(self, data):
        recs = list(biff_records(ole_stream(data)))
        self.spans, self.chunks, self.cells, self.last_row, self.sheets = [], [], {}, -1, 0
        depth, pending = 0, None
        for k, (rid, b) in enumerate(recs):
            if rid == 0x0809:                               # BOF: the workbook's own part, then one part per sheet
                depth += 1
                if depth == 1:
                    self.sheets += 1
                continue
            if rid == 0x000A:                               # EOF
                depth -= 1
                continue
            if depth != 1:
                continue
            if self.sheets == 1:                            # the workbook's own part: the shared strings
                if rid == 0x00FC:
                    self.chunks = [b]
                    j = k + 1
                    while j < len(recs) and recs[j][0] == 0x003C:
                        self.chunks.append(recs[j][1])
                        j += 1
                    self.spans = sst_spans(self.chunks)
                continue
            if self.sheets != 2:                            # only the first sheet is read
                continue
            if rid == 0x00FD:                               # LABELSST: a place in the shared strings
                r, c, _xf, isst = struct.unpack_from("<HHHI", b, 0)
                self._put(r, c, "sst", isst)
            elif rid in (0x0204, 0x00D6):                   # LABEL, RSTRING: text in the cell itself
                r, c, _xf, cch = struct.unpack_from("<HHHH", b, 0)
                wide = b[8] & 1
                self._put(r, c, "raw", (b[9:9 + cch * (2 if wide else 1)], wide))
            elif rid == 0x0203:                             # NUMBER
                r, c, _xf, v = struct.unpack_from("<HHHd", b, 0)
                self._put(r, c, "num", v)
            elif rid == 0x027E:                             # RK
                r, c, _xf, rk = struct.unpack_from("<HHHI", b, 0)
                self._put(r, c, "num", rk_value(rk))
            elif rid == 0x00BD:                             # MULRK
                r, c0 = struct.unpack_from("<HH", b, 0)
                for i in range((len(b) - 6) // 6):
                    _xf, rk = struct.unpack_from("<HI", b, 4 + 6 * i)
                    self._put(r, c0 + i, "num", rk_value(rk))
            elif rid == 0x0205:                             # BOOLERR
                r, c, _xf, v, err = struct.unpack_from("<HHHBB", b, 0)
                if not err:
                    self._put(r, c, "bool", bool(v))
            elif rid == 0x0006:                             # FORMULA: its stored result
                r, c, _xf = struct.unpack_from("<HHH", b, 0)
                res = b[6:14]
                if res[6:8] == b"\xff\xff":
                    if res[0] == 0:
                        pending = (r, c)                    # text, in the STRING record that follows
                    elif res[0] == 1:
                        self._put(r, c, "bool", bool(res[2]))
                else:
                    self._put(r, c, "num", struct.unpack("<d", res)[0])
            elif rid == 0x0207 and pending:                 # STRING
                cch = struct.unpack_from("<H", b, 0)[0]
                wide = b[2] & 1
                self._put(pending[0], pending[1], "raw", (b[3:3 + cch * (2 if wide else 1)], wide))
                pending = None

    def _put(self, r, c, kind, v):
        self.cells[(r, c)] = (kind, v)
        if r > self.last_row:
            self.last_row = r

    def text(self, cell):
        if cell is None:
            return ""
        kind, v = cell
        if kind == "sst":
            if v >= len(self.spans):
                raise XlsError("a cell points past the end of the shared strings table")
            return "".join(self.chunks[ci][a:a + n].decode("utf-16-le" if wide else "latin-1", "replace") for ci, a, n, wide in self.spans[v])
        if kind == "raw":
            return v[0].decode("utf-16-le" if v[1] else "latin-1", "replace")
        if kind == "bool":
            return "TRUE" if v else "FALSE"
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    def headings(self):
        return [self.text(self.cells.get((0, c))).strip() for c in range(1 + max((c for (r, c) in self.cells if r == 0), default=-1))]

    def rows(self, keep):
        """[[text of each column named in keep]] for every row below the heading row, in the sheet's own order."""
        heads = self.headings()
        idx = [heads.index(h) for h in keep]
        return [[re.sub(r"\s+", " ", self.text(self.cells.get((r, c)))).strip() for c in idx] for r in range(1, self.last_row + 1)]


# ------------------------------------------------------------------------- the county clerks' filings (local offices)

def form_post(url, fields, say=print, timeout=600):
    """The page's own form, posted as the page posts it, with the kit's honest User-Agent; asked at most twice more on a
    refusal or a server error (never past a challenge page). Returns (bytes, the answer's file name or '')."""
    for attempt in range(3):
        try:
            req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                          headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
            with urlopen(req, timeout=timeout) as r:
                m = re.search(r'filename="?([^";]+)', r.headers.get("Content-Disposition") or "")
                return r.read(), (m.group(1).strip() if m else "")
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


NAME_COLUMNS = ("Last Name", "First Name", "Middle Name", "Suffix")


def scrub(rows, kept):
    """A clerk can type an e-mail address or a telephone number into a name or description cell. Any kept cell that
    looks like contact details is blanked here, before the rows are cached or read by anything else:
    [[the row's number in the sheet, the column]], never the text."""
    out = []
    for n, r in enumerate(rows, 2):
        for i, v in enumerate(r):
            if v and (contact_like(v, True) or (kept[i] in NAME_COLUMNS and ("@" in v or re.search(r"\d{3,}", v)))):
                r[i] = ""
                out.append([n, kept[i]])
    return out


def county_filings(folder, say, max_age_days=2):
    """The kept columns of the Secretary of State's "Candidate Filings with the County Clerk" list, as JSON in the cache:
    {read, url, file, bytes, sha256, directory: {office: the page's own count}, counties: [the page's county chooser],
    headings: [the sheet's heading row], kept: [the columns kept], rows: [[kept cells]]}. The list is the page's own
    "Excel spreadsheet of All Candidates" button; the spreadsheet itself is never written anywhere, and its address, city,
    state, ZIP, e-mail and date columns are never turned into text."""
    path = os.path.join(folder, COUNTY_FILE)
    if fresh(path, max_age_days):
        return path
    os.makedirs(folder, exist_ok=True)
    try:
        page = fetch(COUNTY_URL, accept="text/html", say=say).decode("utf-8", "replace")
        if "Candidate Filings with the County Clerk" not in page or 'name="ctl00$MainContent$bExcel"' not in page:
            raise SystemExit("Kentucky: the county filings page no longer has its heading or its Excel button; read the page again")
        fields = {m.group(1): H.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
        if "__VIEWSTATE" not in fields:
            raise SystemExit("Kentucky: the county filings page's form has changed (no __VIEWSTATE); read the page again")
        directory = {}
        for m in re.finditer(r'<a[^>]+href="javascript:__doPostBack\(&#39;[^&]*rptDirectory[^&]*&#39;[^>]*>(.*?)</a>', page, re.S):
            c = re.fullmatch(r"(.+?) \((\d+)\)", KY.text_of(m.group(1)))
            if c:
                directory[c.group(1)] = int(c.group(2))
        chooser = re.search(r'<select[^>]*name="ctl00\$MainContent\$ddlCounty"[^>]*>(.*?)</select>', page, re.S)
        counties = [KY.text_of(x) for x in re.findall(r"<option[^>]*>(.*?)</option>", chooser.group(1), re.S)] if chooser else []
        counties = [c for c in counties if c]
        fields.update({"ctl00$MainContent$ddlCounty": "", "ctl00$MainContent$ddlOffice": "", "ctl00$MainContent$ddlParty": "",
                       "ctl00$MainContent$tFName": "", "ctl00$MainContent$tLName": "", "ctl00$MainContent$tDateFiled": "",
                       "ctl00$MainContent$bExcel": "Excel spreadsheet of All Candidates"})
        time.sleep(1.5)
        raw, fname = form_post(COUNTY_URL, fields, say=say)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the county filings list could not be read ({e}); using the copy read earlier")
            return path
        raise
    if raw[:8] != OLE_MAGIC:
        raise SystemExit("Kentucky: the county filings page's Excel button did not answer with an Excel file (first bytes checked); "
                         "read the page again")
    try:
        book = Xls(raw)
        heads = book.headings()
        if heads != XLS_HEADINGS:
            raise SystemExit("Kentucky: the county filings spreadsheet's heading row is not the one this loader was checked against "
                             f"({len(heads)} headings); stopping")
        rows = book.rows(XLS_KEEP)
    except (XlsError, struct.error, IndexError) as e:
        raise SystemExit(f"Kentucky: the county filings spreadsheet could not be read ({type(e).__name__}: {e}); stopping")
    del book
    blanked = scrub(rows, XLS_KEEP)
    keep = {"read": dt.date.today().isoformat(), "url": COUNTY_URL, "file": fname, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "directory": directory, "counties": counties, "headings": heads, "kept": list(XLS_KEEP), "scrubbed": blanked, "rows": rows}
    del raw
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def court_filings(folder, say, max_age_days=2):
    """The kept cells of the Secretary of State's own filings pages for District Judge, Circuit Judge (two pages: the
    second is the family court seats) and Commonwealth's Attorney, as JSON in the cache. The pages are never written
    anywhere; the federal loader's reader takes Name (first line), Office, District/Division and Party only."""
    path = os.path.join(folder, COURT_FILE)
    if fresh(path, max_age_days):
        return path
    os.makedirs(folder, exist_ok=True)
    keep = {"read": dt.date.today().isoformat(), "pages": {}}
    try:
        for pid, (office, called) in COURT_PAGES.items():
            raw = fetch(KY.FILINGS + pid, accept="text/html", say=say)
            got = KY.filings(raw.decode("utf-8", "replace"), office)
            for r in got["rows"]:                          # a name cell that holds contact details is blanked before anything is kept
                if contact_like(r["Name"], True) or "@" in r["Name"] or re.search(r"\d{3,}", r["Name"]):
                    r["Name"] = ""
            keep["pages"][pid] = {"office": office, "called": called, "url": KY.FILINGS + pid, "sha256": hashlib.sha256(raw).hexdigest(),
                                  "groups": got["groups"], "rows": got["rows"]}
            time.sleep(1.5)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the trial court filings pages could not be read ({e}); using the copy read earlier")
            return path
        raise
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------- official lists: counties, places, schools

def official_files(folder, say, report):
    """The official lists read beside the candidate lists, downloaded once into the cache (none has a contact column):
    {key: path, or None when an optional one could not be had}."""
    paths = {}
    for key, (fname, url) in OFFICIAL.items():
        optional = key in ("districts", "circuits", "schedule")
        path = os.path.join(folder, fname)
        try:
            net.download(url, path, 30 if optional else 3650, tries=3, say=say)
        except (HTTPError, OSError) as e:
            if not optional:
                raise
            report.append(f"{fname} could not be downloaded ({e}); what depends on it is left out")
            path = None
        paths[key] = path
    paths["counties"] = COUNTY_ZIP
    if not os.path.exists(COUNTY_ZIP):
        paths["counties"] = os.path.join(folder, os.path.basename(COUNTY_ZIP))
        net.download(CENSUS_SHP + os.path.basename(COUNTY_ZIP), paths["counties"], 3650, say=say)
    return paths


def dbf_rows(zip_path):
    """The attribute table of a Census boundary file, as dicts."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(zip_path)
    name = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(name)))
    fields = [f[0] for f in rdr.fields[1:]]
    return [dict(zip(fields, rec)) for rec in rdr.iterRecords()]


def letters(text):
    return re.sub(r"[^A-Z]", "", (text or "").upper())


def words(text):
    """A name's or a description's words in capitals, punctuation dropped, Mt, Ft, St and Jct written out."""
    t = re.sub(r"[^A-Z0-9]+", " ", (text or "").upper().replace("'", "").replace("&", " AND "))
    return [re.sub(r"BOROUGH$", "BORO", ABBR.get(w, w)) for w in t.split()]      # Middlesboro is the Bureau's Middlesborough


def counties_of(path):
    """({fips: "Adair County"}, {ADAIR: fips}) for Kentucky's 120 counties, from the Census Bureau's county file."""
    name, key = {}, {}
    for r in dbf_rows(path):
        if str(r.get("STATEFP")) == FIPS:
            name[str(r["GEOID"])] = str(r["NAMELSAD"])
            key[letters(str(r["NAME"]))] = str(r["GEOID"])
    if len(name) != TOTAL_COUNTIES or len(key) != TOTAL_COUNTIES:
        raise SystemExit(f"Kentucky: the Census county file gives {len(name)} Kentucky counties, not {TOTAL_COUNTIES}")
    return name, key


def places_of(paths):
    """{place code: {name, base, counties, src}}: Kentucky's active cities from the Census Bureau's 2020 place-by-county
    list (census designated places and the two entries the Bureau keeps only for its own arithmetic, the old city of
    Louisville and the metro government's "balance", are not governments and are left out), and the Louisville/Jefferson
    County metro government from the Bureau's consolidated cities file, in the county its balance is listed under."""
    out, balance = {}, {}
    with open(paths["places"], encoding="utf-8") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        if head != ["STATE", "STATEFP", "COUNTYFP", "COUNTYNAME", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT"]:
            raise SystemExit("Kentucky: the Census place file's heading row is not the one this loader was checked against")
        for n, line in enumerate(fh, 2):
            f = line.rstrip("\r\n").split("|")
            if len(f) != 10:
                raise SystemExit(f"Kentucky: line {n} of the Census place file has {len(f)} cells, not 10")
            if f[1] != FIPS or f[7] != "INCORPORATED PLACE":
                continue
            if f[9] == "A":
                out.setdefault(f[4], {"name": f[6], "counties": set(), "src": SRC_PLACES})["counties"].add(FIPS + f[2])
            elif f[6].endswith(" (balance)"):
                balance.setdefault(f[6][:-len(" (balance)")], set()).add(FIPS + f[2])
    for r in dbf_rows(paths["concity"]):
        if str(r.get("STATEFP")) == FIPS:
            name = str(r["NAMELSAD"])
            if name not in balance:
                raise SystemExit("Kentucky: the consolidated city in the Census file has no \"(balance)\" entry in the place file to say "
                                 "which county it is in")
            out[str(r["CONCTYFP"])] = {"name": name, "counties": set(balance[name]), "src": SRC_CONCITY}
    for code, p in out.items():
        p["base"] = re.sub(r"\s+(?:city|urban county|metro government)$", "", p["name"])
        p["written"] = [words(p["base"])] + [words(a) for a in MERGED_NAMES.get(code, ())]
    return out


def schools_of(paths, county_key):
    """({county fips: {lea, name, src}}, {lea: {lea, name, base, src}}): the county school districts and the independent
    ones, from the Census Bureau's unified and elementary school district files."""
    county, indep = {}, {}
    for key, field, src in (("unsd", "UNSDLEA", SRC_UNSD), ("elsd", "ELSDLEA", SRC_ELSD)):
        for r in dbf_rows(paths[key]):
            name, lea = str(r["NAME"]), str(r[field])
            m = re.fullmatch(r"(.+) County School District", name)
            if m and letters(m.group(1)) in county_key:
                county[county_key[letters(m.group(1))]] = {"lea": lea, "name": name, "src": src}
                continue
            m = re.fullmatch(r"(.+) Independent School District", name)
            if m:
                indep[lea] = {"lea": lea, "name": name, "base": m.group(1), "src": src, "written": [words(m.group(1))]}
    if len(county) != TOTAL_COUNTIES:
        raise SystemExit(f"Kentucky: the Census school district file names {len(county)} county school districts, not {TOTAL_COUNTIES}")
    return county, indep


def pdf_lines(path):
    pdf = P.PDF(open(path, "rb").read())
    return [P.join(rs) for page, res in pdf.pages() for _y, rs in P.rows(pdf, page, res) if P.join(rs)]


def judicial_counties(path, section, word, county_key):
    """{number: [county fips]} from the statute that lists each judicial district's (KRS 24A.030) or circuit's (KRS 23A.020)
    counties, one numbered sentence each: "(12) Twelfth Judicial District. Henry, Oldham, and Trimble." Every county must be
    named exactly once and the numbers must run from 1; otherwise None, with the reason."""
    lines = pdf_lines(path)
    if not lines or not lines[0].startswith(f"{section} Judicial {word.lower()}s.") or "(Effective January 1, 2031)" in lines[0]:
        return None, "its first line is not the heading of the section in force for this election"
    text = " ".join(lines).split(" Effective:")[0]
    out = {}
    for m in re.finditer(r"\((\d+)\) [A-Z][A-Za-z-]+ Judicial %s\. ([^.()]+)\." % word, text):
        names = [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(2).strip()) if n.strip()]
        if any(letters(n) not in county_key for n in names):
            return None, f"sentence ({m.group(1)}) names something that is not a Kentucky county"
        out[int(m.group(1))] = [county_key[letters(n)] for n in names]
    named = [f for fs in out.values() for f in fs]
    if sorted(out) != list(range(1, len(out) + 1)) or len(named) != TOTAL_COUNTIES or len(set(named)) != TOTAL_COUNTIES:
        return None, f"{len(out)} numbered sentences naming {len(set(named))} counties ({len(named)} names); every county once was expected"
    return out, None


def schedule_years(path):
    """{office as the schedule prints it: [years marked]} from the State Board of Elections' "Kentucky Election Schedule", a
    table with one column per year and an X under each year an office is elected."""
    pdf = P.PDF(open(path, "rb").read())
    out = {}
    for page, res in pdf.pages():
        rows, years = [], []
        for _y, rs in P.rows(pdf, page, res):
            chunks = []                                      # the file prints a letter or two at a time: pieces that touch are one chunk
            for x0, _yy, size, text, x1 in sorted(rs, key=lambda r: r[0]):
                if chunks and x0 - chunks[-1][1] <= 0.18 * size:
                    chunks[-1][1], chunks[-1][2] = max(chunks[-1][1], x1), chunks[-1][2] + text
                else:
                    chunks.append([x0, x1, text])
            toks = []
            for x0, x1, text in chunks:
                for m in re.finditer(r"\S+", text):          # a chunk's words, each given its share of the chunk's width
                    toks.append((x0 + (x1 - x0) * (m.start() + m.end()) / 2 / max(1, len(text)), m.group(0)))
            rows.append(toks)
            ys = [(x, t) for x, t in toks if re.fullmatch(r"20\d\d", t)]
            if len(ys) >= 8 and not years:
                years = ys
        if not years:
            continue
        for toks in rows:
            marks = [x for x, t in toks if re.fullmatch(r"X[12]?", t)]
            label = " ".join(t for _x, t in toks if not re.fullmatch(r"X[12]?", t))
            if marks and label:
                out[label] = sorted(int(min(years, key=lambda p: abs(p[0] - x))[1]) for x in marks)
    return out


SCHEDULE_FACTS = (      # (the start of the schedule's row label, a year it must mark, a year it must not mark, in plain words)
    ("COUNTY OFFICERS", 2026, 2028, "county officers are elected in 2026"),
    ("DISTRICT JUDGE", 2026, 2028, "district judges are elected in 2026"),
    ("LOCAL SCHOOL BOARD", 2026, 2027, "part of each school board is elected in 2026"),
    ("A. Mayor", 2026, 2027, "mayors are elected in 2026 and 2028, by turns"),
    ("B. Legislative Body", 2026, 2027, "city legislative bodies are elected every even year"),
    ("CIRCUIT CLERK", 2030, 2026, "circuit court clerks are next elected in 2030"),
    ("CIRCUIT JUDGE", 2030, 2026, "circuit judges are next elected in 2030"),
    ("COMMONWEALTH'S ATTORNEY", 2030, 2026, "Commonwealth's attorneys are next elected in 2030"),
    ("STATE OFFICERS", 2027, 2026, "statewide officers are elected in 2027"),
)


def schedule_checked(path):
    """(facts found, facts not found) in the election schedule's own marks."""
    try:
        got = schedule_years(path)
    except Exception as e:  # noqa: BLE001  a schedule that cannot be read confirms nothing
        return [], [f"the schedule could not be read ({type(e).__name__})"]
    ok, bad = [], []
    for label, yes, no, plain in SCHEDULE_FACTS:
        years = [ys for k, ys in got.items() if k.startswith(label)]
        (ok if len(years) == 1 and yes in years[0] and no not in years[0] else bad).append(plain)
    return ok, bad


# ----------------------------------------------------------------- the trial courts: by judicial district or circuit

def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def court_rows(folder, say, paths, county_key, sched_ok, report):
    """The offices elected by judicial district or circuit, from the Secretary of State's own filings pages: District Judge
    (every district, a nonpartisan office), and the Circuit Judge and Commonwealth's Attorney seats on the 2026 ballot (both
    are next elected in full in 2030). The counties of each district and circuit come from the statutes that draw them."""
    listed = json.load(open(court_filings(folder, say), encoding="utf-8"))
    maps = {}
    for key, section, word in (("districts", "24A.030", "District"), ("circuits", "23A.020", "Circuit")):
        maps[key] = None
        if paths.get(key):
            maps[key], why = judicial_counties(paths[key], section, word, county_key)
            if maps[key] is None:
                report.append(f"KRS {section} could not be read into counties ({why}); the {word.lower()} contests carry no counties")
    confirmed = lambda words_: any(words_ in f for f in sched_ok)  # noqa: E731
    races, counts, gaps = {}, collections.Counter(), []
    for pid, page in listed["pages"].items():
        called = page["called"]
        if sum(c for _g, c, w in page["groups"] if not w) != sum(1 for r in page["rows"] if not r["withdrawn"]):
            report.append(f"the {called} page's headings and its rows do not count the same candidates")
        for r in page["rows"]:
            m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)(?: / (\d+)(?:st|nd|rd|th))?", r["District/Division"])
            if not m:
                raise SystemExit(f"Kentucky: could not read the district and division of a {called} filing")
            d, div = int(m.group(1)), m.group(2) and int(m.group(2))
            if r["withdrawn"]:
                counts["withdrawn"] += 1
                continue
            if not r["Name"]:
                counts["nameless"] += 1
                report.append(f"a {called} filing whose name cell held something that is not a name is left off")
                continue
            tail = f"-{div}" if div else ""
            if pid == "17":
                x = dict(race_id=f"2026-{STATE}-DJ{d}{tail}", office_kind="district_court", office="District Judge",
                         jurisdiction=f"{ordinal(d)} Judicial District", jurisdiction_id=f"{STATE}-JD{d}", district=str(d), special=0,
                         partisan=0, _map="districts", _note=None)
            elif pid == "13":
                x = dict(race_id=f"2026-{STATE}-CWA{d}{tail}", office_kind="commonwealth_attorney", office="Commonwealth's Attorney",
                         jurisdiction=f"{ordinal(d)} Judicial Circuit", jurisdiction_id=f"{STATE}-JC{d}", district=f"{ordinal(d)} Circuit",
                         special=1, partisan=1, _map="circuits",
                         _note=CWA_NOTE if confirmed("Commonwealth's attorneys") else UNEXPIRED_NOTE)
            else:
                x = dict(race_id=f"2026-{STATE}-CJ{d}{tail}", office_kind="circuit_court", office="Circuit Judge",
                         jurisdiction=f"{ordinal(d)} Judicial Circuit", jurisdiction_id=f"{STATE}-JC{d}", district=f"{ordinal(d)} Circuit",
                         special=1, partisan=0, _map="circuits",
                         _note=(CIRCUIT_NOTE if confirmed("circuit judges") else UNEXPIRED_NOTE) + (" " + FAMILY_NOTE if pid == "20" else ""))
            x = races.setdefault(x["race_id"], dict(x, state=STATE, level="court", seat=f"Division {div}" if div else None, holder_id=None,
                                                    holder_name=None, holder_party=None, election_date=GENERAL, _cands=[], _d=d))
            party = r["Party"]
            write_in = int(party == "Write-In")
            if not x["partisan"]:
                if party not in ("Nonpartisan", "Write-In"):
                    report.append(f"{x['race_id']}: a nonpartisan seat's candidate is listed with a party")
                party, code = NONPARTISAN, "N"
            else:
                code = party_code(party)
            if any(c["name"] == r["Name"] for c in x["_cands"]):
                raise SystemExit(f"Kentucky: one name is listed twice in {x['race_id']}")
            x["_cands"].append(dict(name=r["Name"], party=party, code=code, write_in=write_in))
            counts[called] += 1
            counts["write-ins"] += write_in
    race_rows, cands = [], []
    for rid, x in races.items():
        cmap = maps[x["_map"]]
        x["county_ids"] = json.dumps(cmap[x["_d"]]) if cmap and x["_d"] in cmap else None
        if cmap is not None and x["_d"] not in cmap:
            report.append(f"{rid}: the statute names no {x['_map'][:-1]} of this number, so the contest carries no counties")
        notes = [x["_note"]] if x["_note"] else []
        per = collections.Counter(c["party"] for c in x["_cands"] if not c["write_in"] and c["party"] in MAJOR)
        twice = [(p, n) for p, n in per.items() if n > 1] if x["partisan"] else []
        if twice:
            p, n = max(twice, key=lambda t: t[1])
            why = (f"The Secretary of State's list shows {n} {p} candidates for this office, which has one candidate a party in November, "
                   f"so no name is shown here.")
            notes, x["_cands"] = [why], []
            gaps.append((STATE, "race", rid, f"{x['office']}, {x['jurisdiction']}", "November candidates", why, KY.FILINGS + "13"))
        elif x["_cands"] and all(c["write_in"] for c in x["_cands"]):
            notes.append(ONLY_WRITE_INS)
        x["note"] = " ".join(notes) or None
        race_rows.append(tuple(x[c] for c in RACE_COLS))
        for c in x["_cands"]:
            cands.append([rid, "general", GENERAL, c["name"], c["party"], c["code"], None, 0, c["write_in"], None, None, None, None, SRC_COURT,
                          WRITE_IN if c["write_in"] else None])
    return dict(races=races, race_rows=race_rows, cands=cands, gaps=gaps, counts=counts, listed=listed, maps=maps)


# ---------------------------------------------------------------------------------- names, parties and free-text places

def osa(a, b, limit=2):
    """How many slips of spelling separate two words (a letter dropped, added or changed, or two neighbours swapped);
    anything above the limit comes back as limit + 1."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return min(prev[-1], limit + 1)


SMALL_CAPS = {"MC": "Mc", "ST": "St", "DR": "Dr"}


def ordinary(text):
    """Words the list holds in capitals, in ordinary capitals (the federal loaders' proper()); a word typed in ordinary
    capitals is kept as typed, and so are initials and two letters with no vowel (JD, TJ)."""
    out = []
    for w in (text or "").split():
        lead, core, tail = re.fullmatch(r"([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)", w).groups()
        solid = re.sub(r"[^A-Za-z]", "", core)
        if core in SMALL_CAPS:
            core = SMALL_CAPS[core]
        elif (re.search(r"[A-Z]{2}", core) and core == core.upper() and not re.fullmatch(r"[IVX]+", core)
              and (len(solid) != 2 or re.search(r"[AEIOUY]", solid) or GENERATION.match(core))):
            core = proper(core)
        out.append(lead + core + tail)
    return " ".join(out)


def filed_name(first, middle, last, extra):
    """(the name, what was done with the list's "Suffix" column). The list holds a name in four columns; the Secretary of
    State's page prints the fourth in front of the rest. Here the name runs given names, family name, then Jr, Sr, II, III
    or IV when that is what the fourth column holds. A courtesy title there (Mr, Mrs, Ms) is left out; a nickname there is
    kept after the given names, unless the given names already carry it or it only writes the same name again."""
    given = [w for w in (first, middle) if w]
    tail, nick, did = "", "", ""
    if extra:
        if GENERATION.match(extra):
            tail, did = extra, "generation"
        elif COURTESY.match(extra):
            did = "courtesy"
        elif last and letters(extra.split()[-1]) == letters(last.split()[0]):
            did = "restated"
        elif letters(extra) in {letters(w) for g in given for w in g.split()}:
            did = "repeated"
        else:
            nick, did = extra, "nickname"
    name = ordinary(" ".join(p for p in given + [nick, last, tail] if p))
    return re.sub(r"\s+", " ", name).strip(), did


def same_filer(a, b):
    """Two rows of one contest, from two county clerks' lists, that are one candidate: the same first given name, given names
    that do not contradict each other (a middle name or initial one clerk left out is no contradiction), the same family
    name or one a single slip of spelling away, and no different Jr, Sr or number."""
    ta, sa = name_words(a)
    tb, sb = name_words(b)
    if len(ta) < 2 or len(tb) < 2 or (sa and sb and sa != sb):
        return False
    near = lambda x, y: x == y or (min(len(x), len(y)) >= 5 and osa(x, y, 1) <= 1)  # noqa: E731
    if len(ta) == len(tb):                          # word for word, one of them a single slip apart at most
        differ = [(x, y) for x, y in zip(ta, tb) if x != y]
        return len(differ) <= 1 and all(near(x, y) for x, y in differ)
    short, long_ = sorted((ta, tb), key=len)       # one clerk left a middle name or initial out
    if short[0] != long_[0] or not near(short[-1], long_[-1]):
        return False
    return all(x[0] == y[0] for x, y in zip(short[1:-1], long_[1:-1]))


def name_words(r):
    """(a row's name as words, given names first, without Jr, Sr or a number; those apart)."""
    ws = words(f"{r['First Name']} {r['Middle Name']} {r['Last Name']}")
    return [w for w in ws if not GENERATION.match(w)], [w for w in ws + words(r["Suffix"]) if GENERATION.match(w)]


def party_words(p, unknown):
    if p in PARTY_WORDS:
        return PARTY_WORDS[p]
    unknown[p] += 1
    return " ".join(w.capitalize() for w in p.split())


class Finder:
    """Finds which official place a clerk's free text names, among the places it is given."""

    def __init__(self, entries, generic):
        """entries: {id: [the ways its name is written, each a list of words]}; generic: words that name no place."""
        self.entries, self.generic, self.names = entries, generic, {}
        for pid, written in entries.items():
            for ws in written:
                key = "".join(ws)
                self.names[key] = pid if self.names.get(key, pid) == pid else None      # None: two places share the name

    def is_generic(self, t):
        if t in self.generic or len(t) <= 2 or t.isdigit() or re.fullmatch(r"\d+(ST|ND|RD|TH)", t) or t in NUMBER_WORDS:
            return True
        return any(len(g) >= 5 and osa(t, g, 2) <= (1 if len(g) < 8 else 2) for g in self.generic)

    def leftover(self, toks):
        return [t for t in toks if not self.is_generic(t)]

    def find(self, toks, own=()):
        """(id or None, how): how is 'exact' (the name is printed), 'part' (what is printed is part of exactly one name),
        'slip' (one slip of spelling from exactly one name), 'generic' (no place is named) or 'words' (words that fit no
        place). A name followed by COUNTY or CO is the county's, not the city's or the school district's; `own` is a name
        that needs more than its own printing to count (the county's own name, for an independent school district)."""
        best = []
        for i in range(len(toks)):
            for j in range(i + 1, min(len(toks), i + 6) + 1):
                key = "".join(toks[i:j])
                if self.names.get(key) is None:
                    continue
                if (j < len(toks) and toks[j] in ("COUNTY", "CO")) or key in own:
                    continue
                best.append((len(key), self.names[key]))
        if best:
            top = max(n for n, _p in best)
            ids = {p for n, p in best if n == top}
            return (ids.pop(), "exact") if len(ids) == 1 else (None, "words")
        rest = self.leftover(toks)
        if not rest:
            return None, "generic"
        part = {pid for pid, written in self.entries.items() for ws in written
                if any(ws[k:k + len(rest)] == rest for k in range(len(ws) - len(rest) + 1))}
        if len(part) == 1 and len("".join(rest)) >= 4:
            return part.pop(), "part"
        slips = []
        for i in range(len(toks)):
            for j in range(i + 1, min(len(toks), i + 5) + 1):
                key = "".join(toks[i:j])
                if len(key) < 5 or key in own:
                    continue
                for name, pid in self.names.items():
                    if pid is not None and len(name) >= 6 and osa(key, name, 1) == 1:
                        slips.append((len(name), pid))
        if slips:
            top = max(n for n, _p in slips)
            ids = {p for n, p in slips if n == top}
            if len(ids) == 1:
                return ids.pop(), "slip"
        return None, "words"


def number_in(toks):
    """The one district number a description's words give (4, 4TH, FOUR, SB4, #4), or None."""
    found = set()
    for t in toks:
        m = re.fullmatch(r"(?:SB|D|DIST|DIV)?(\d{1,2})(?:ST|ND|RD|TH)?", t)
        if m:
            found.add(int(m.group(1)))
        elif t in NUMBER_WORDS:
            found.add(NUMBER_WORDS[t])
    return str(found.pop()) if len(found) == 1 else None


def has_word(toks, word, slips=1):
    return any(t == word or (len(t) >= 5 and osa(t, word, slips) <= slips) for t in toks)


def says_council(toks):
    return any(t.startswith("COUNCIL") or osa(t, "COUNCIL", 1) <= 1 for t in toks)


def says_commission(toks):
    return any(t in ("COM", "COMM") or re.match(r"COM+I+S", t) for t in toks)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


# ---------------------------------------------------------------------------------------- the local levels, put together

def local_rows(cache, say):
    """Everything this loader writes for the local levels: races, candidates, places, gaps, notes and sources, from the
    Secretary of State's "Candidate Filings with the County Clerk" list and its own filings pages for the trial courts."""
    folder = os.path.join(cache, "ky", "local")
    os.makedirs(folder, exist_ok=True)
    report = []
    listed = json.load(open(county_filings(folder, say), encoding="utf-8"))
    paths = official_files(folder, say, report)
    county_name, county_key = counties_of(paths["counties"])
    places = places_of(paths)
    school_county, school_indep = schools_of(paths, county_key)
    by_county = collections.defaultdict(list)
    for code, p in places.items():
        for f in p["counties"]:
            by_county[f].append(code)

    if listed.get("kept") != list(XLS_KEEP):
        raise SystemExit("Kentucky: the cached county filings list does not hold the columns this loader keeps; delete it and run again")
    rows = [dict(zip(XLS_KEEP, r), n=n) for n, r in enumerate(listed["rows"], 2)]        # n: the row's number in the sheet
    blanked_cells = listed.get("scrubbed") or []      # cells that held contact details, blanked before the list was cached
    for r in rows:
        if letters(r["County"]) not in county_key:
            raise SystemExit(f"Kentucky: row {r['n']} of the county filings list names a county that is not one of the {TOTAL_COUNTIES}")
        if r["Office"] not in COUNTY_OFFICES and r["Office"] not in OTHER_OFFICES:
            raise SystemExit(f"Kentucky: row {r['n']} of the county filings list is for an office this loader does not know; read the list again")
        if any(r[k] not in ("", "YES") for k in ("Unexpired", "Withdrawn", "Disqualified", "Deceased")):
            raise SystemExit(f"Kentucky: row {r['n']} of the county filings list has a mark other than YES in a yes-or-blank column")
        if not r["Party"] or (not r["Last Name"] and [r["n"], "Last Name"] not in blanked_cells):
            raise SystemExit(f"Kentucky: row {r['n']} of the county filings list has no family name or no party")
        r["fips"] = county_key[letters(r["County"])]
        r["_live"] = not (r["Withdrawn"] or r["Disqualified"] or r["Deceased"])
    gone = collections.Counter(k for r in rows for k in ("Withdrawn", "Disqualified", "Deceased") if r[k])
    live = [r for r in rows if r["_live"]]

    # ---- the list's own totals: the page's directory counts each office's candidates, and those left off, apart
    directory = listed.get("directory") or {}
    left_off = len(rows) - len(live)
    per_office = collections.Counter(r["Office"] for r in live)
    for office, n in per_office.items():
        want = [c for k, c in directory.items() if k.upper() == office]
        if want != [n]:
            report.append(f"the list's own count for {office.title()} is {want[0] if want else 'missing'}; {n} rows were read")
    off = [c for k, c in directory.items() if k.lower().startswith("withdrawn")]
    if off != [left_off]:
        report.append(f"the list's own count of withdrawn, deceased and disqualified is {off[0] if off else 'missing'}; {left_off} rows carry such a mark")

    races, cands, unplaced = {}, [], []
    unknown_party, name_did = collections.Counter(), collections.Counter()

    # Every row is put in its contest, the withdrawn, disqualified and deceased too. Those are never shown and never make a
    # contest, a district or a ward of their own (a number typed on a withdrawn row is no evidence of a seat), but a
    # withdrawal one county clerk has entered counts against the same name on another clerk's list of the same contest.
    def race(rid, **kw):
        if rid not in races:
            races[rid] = dict(race_id=rid, state=STATE, special=0, holder_id=None, holder_name=None, holder_party=None,
                              election_date=GENERAL, district=None, seat=None, _notes=[], _rows=[], _gone=[], **kw)
        return races[rid]

    def put(rid, r):
        races[rid]["_rows" if r["_live"] else "_gone"].append(r)
        r["rid"] = rid

    def lost(r, what, why):
        if r["_live"]:
            unplaced.append((r["fips"], what, why))
        r["rid"] = None

    # ---- a row whose name cell held contact details has no name to show: it is set aside with the gaps
    office_what = {"MAYOR": "mayor candidates", "CITY LEGISLATIVE BODY": "city council or commission candidates",
                   "SCHOOL BOARD MEMBER": "school board candidates",
                   "SOIL AND WATER CONSERVATION DISTRICT SUPERVISOR": "soil and water conservation district supervisor candidates"}
    for r in rows:
        if not r["Last Name"]:
            what = office_what.get(r["Office"]) or ("magistrate, constable or county commissioner candidates"
                                                    if COUNTY_OFFICES[r["Office"]][2] == "district" else "county office candidates")
            lost(r, what, "under something that is not a name")
    named = [r for r in rows if r["Last Name"]]

    # ---- county offices
    learned = collections.defaultdict(dict)        # (county, family of offices) -> {a district's name words: its number}
    numbered = set()                               # (county, family) with at least one numbered row
    cfinder = {}

    def county_words(f):
        if f not in cfinder:
            cfinder[f] = Finder({}, COUNTY_WORDS | set(words(re.sub(r" County$", "", county_name[f]))))
        return cfinder[f]

    def family(office):
        return "commissioner" if office == "COUNTY COMMISSIONER" else "magisterial"

    def district_name(f, toks):
        """The words of a description that name a district: not the office's or the county's own words, and not a precinct
        code such as A101. A single letter (Jefferson County's Commissioner A) is a name."""
        cw = county_words(f)
        return [t for t in toks if not re.fullmatch(r"[A-Z]\d{2,}", t) and t not in cw.generic and (re.fullmatch(r"[A-Z]", t) or not cw.is_generic(t))]

    for r in named:
        if r["_live"] and COUNTY_OFFICES.get(r["Office"], ("", "", ""))[2] == "district" and r["District"]:
            numbered.add((r["fips"], family(r["Office"])))
            name = tuple(district_name(r["fips"], words(r["Office Description"])))
            if name:
                learned[(r["fips"], family(r["Office"]))].setdefault(name, set()).add(r["District"])
    ignored_district = by_name = conflicts = 0
    for r in named:
        if r["Office"] not in COUNTY_OFFICES:
            continue
        kind, office, how = COUNTY_OFFICES[r["Office"]]
        f = r["fips"]
        base = dict(level="county", office_kind=kind, office=office, jurisdiction=county_name[f], jurisdiction_id=f,
                    county_ids=json.dumps([f]), partisan=1)
        if how == "county":
            ignored_district += bool(r["District"]) and r["_live"]
            rid = f"2026-{STATE}-{f}-{kind.replace('_', '-')}" + ("-S" if kind == "clerk_of_court" else "")
            x = race(rid, **base)
            if kind == "clerk_of_court":      # elected for six years, next in 2030: any seat on the 2026 list is for the rest of a term
                x["special"] = 1
            put(rid, r)
            continue
        toks = words(r["Office Description"])
        fam, name = (f, family(r["Office"])), district_name(f, toks)
        said = number_in([t for t in toks if not re.fullmatch(r"[A-Z]\d{2,}", t)])
        conflicts += bool(r["_live"] and r["District"] and said and said != r["District"])
        d = r["District"] or said
        if not d and name and fam in numbered:
            # the county numbers its districts: a name counts only where a numbered row of the same county carries it
            hits = {n for known, ns in learned[fam].items() if len(ns) == 1
                    and any(tuple(name[k:k + len(known)]) == known for k in range(len(name) - len(known) + 1)) for n in ns}
            if len(hits) == 1:
                d, by_name = hits.pop(), by_name + r["_live"]
        elif not d and name:
            d = " ".join(proper(w) if len(w) > 1 else w for w in name)      # the county names its districts (East, Central, A)
        if not d:
            lost(r, "magistrate, constable or county commissioner candidates",
                 "with a district the list gives no number for" if name else "without a district")
            continue
        rid = f"2026-{STATE}-{f}-{kind.replace('_', '-')}-{slug(d)}"
        race(rid, **base)["district"] = d if d.isdigit() else f"District {d}" if len(d) == 1 else f"{d} District"
        put(rid, r)

    # ---- soil and water conservation districts: one a county, except where the list itself names two
    split = collections.defaultdict(set)
    part = re.compile(r"\b(NORTH|SOUTH|EAST|WEST)\s+([A-Z]+)\b")
    for r in named:
        if r["Office"].startswith("SOIL"):
            m = part.search(r["Office Description"].upper())
            r["_part"] = m.group(1).title() if m and letters(m.group(2)) == letters(r["County"]) else None
            if r["_part"] and r["_live"]:
                split[r["fips"]].add(r["_part"])
    specials = {}
    for r in named:
        if not r["Office"].startswith("SOIL"):
            continue
        f = r["fips"]
        cname = re.sub(r" County$", "", county_name[f])
        if len(split[f]) >= 2:
            if not r["_part"]:
                lost(r, "soil and water conservation district supervisor candidates", "without saying which of the county's two districts")
                continue
            key = f"{STATE}-X-{f[2:]}-{slug(r['_part'] + ' ' + cname)}"
            specials[key] = (f"{r['_part']} {cname} soil and water conservation district", [f])
            rid = f"2026-{key}-soil-water"
            race(rid, level="soil_water", office_kind="soil_water", office="Soil and Water Conservation District Supervisor",
                 jurisdiction=specials[key][0], jurisdiction_id=key, county_ids=json.dumps([f]), partisan=0)
        else:
            rid = f"2026-{STATE}-{f}-soil-water"
            race(rid, level="soil_water", office_kind="soil_water", office="Soil and Water Conservation District Supervisor",
                 jurisdiction=county_name[f], jurisdiction_id=f, county_ids=json.dumps([f]), partisan=0)
        put(rid, r)

    # ---- cities: the free text names the city
    finder, matched_how = {}, collections.Counter()
    slips, parts, only_city = set(), set(), set()

    def city_finder(f):
        if f not in finder:
            finder[f] = Finder({code: places[code]["written"] for code in by_county[f]},
                               CITY_WORDS | set(words(re.sub(r" County$", "", county_name[f]))))
        return finder[f]

    city_rows = collections.defaultdict(list)          # place code -> its legislative body rows
    for r in named:
        if r["Office"] not in ("MAYOR", "CITY LEGISLATIVE BODY"):
            continue
        f, toks = r["fips"], words(r["Office Description"])
        mayor = r["Office"] == "MAYOR" or (has_word(toks, "MAYOR") and not says_council(toks) and not says_commission(toks))
        what = "mayor candidates" if mayor else "city council or commission candidates"
        code, how = city_finder(f).find(toks)
        if code is None and how == "generic" and len(by_county[f]) == 1:
            code, how = by_county[f][0], "only"
            only_city.add((county_name[f], places[code]["name"]))
        if code is None:
            lost(r, what, "without naming the city" if how == "generic" else "with words that fit no city of the county on the Census Bureau's list")
            continue
        matched_how[how] += r["_live"]
        if how == "slip":
            slips.add((r["Office Description"], places[code]["name"]))
        elif how == "part":
            parts.add((r["Office Description"], places[code]["name"]))
        r["_code"], r["_toks"] = code, toks
        if mayor:
            if r["Office"] != "MAYOR":
                name_did["mayor filed under City Legislative Body"] += r["_live"]
            rid = f"2026-{STATE}-M-{code}-mayor"
            p = places[code]
            race(rid, level="city", office_kind="mayor", office="Mayor", jurisdiction=p["name"], jurisdiction_id=f"{STATE}-M-{code}",
                 county_ids=None, partisan=None)
            put(rid, r)
        else:
            city_rows[code].append(r)
    ward_cities = []
    for code, rs in city_rows.items():
        p = places[code]
        current = [r for r in rs if r["_live"]]
        ds = collections.Counter(r["District"] for r in current if r["District"])
        # elected by ward or district: most of its rows carry a number and the numbers differ (a stray number or two is a
        # clerk's own filing mark, often the magisterial district the city lies in)
        wards = len(ds) >= 3 and sum(ds.values()) * 2 >= len(current)
        said = (any(says_council(r["_toks"]) for r in rs), any(says_commission(r["_toks"]) for r in rs))
        office = MERGED_OFFICE.get(code) or {(True, False): "City Council Member", (False, True): "City Commissioner"}.get(said, "City Legislative Body Member")
        base = dict(level="city", office_kind="council", office=office, jurisdiction=p["name"], jurisdiction_id=f"{STATE}-M-{code}",
                    county_ids=None, partisan=None)
        if wards:
            ward_cities.append((p["name"], len(ds), len(current)))
        for r in rs:
            if not wards:
                rid = f"2026-{STATE}-M-{code}-council"
                x = race(rid, **base)
                if AT_LARGE_NOTE not in x["_notes"]:
                    x["_notes"].append(AT_LARGE_NOTE)
            elif r["District"]:
                rid = f"2026-{STATE}-M-{code}-council-{r['District']}"
                race(rid, **base)["district"] = r["District"]
            elif any(a == "AT" and b == "LARGE" for a, b in zip(r["_toks"], r["_toks"][1:])):
                rid = f"2026-{STATE}-M-{code}-council-at-large"
                x = race(rid, **base)
                x["seat"] = "At Large"
                if SEATS_NOTE not in x["_notes"]:
                    x["_notes"].append(SEATS_NOTE)
            else:
                lost(r, "city council or commission candidates", "without a ward or district, in a city that elects by ward or district")
                continue
            put(rid, r)

    # ---- school boards: an independent district is named in the free text; a county district's members have a division
    sfinder, division_rows = {}, collections.defaultdict(list)
    school_how = collections.Counter()
    for r in named:
        if r["Office"] != "SCHOOL BOARD MEMBER":
            continue
        f, toks = r["fips"], words(r["Office Description"])
        cname = letters(re.sub(r" County$", "", county_name[f]))
        if f not in sfinder:
            sfinder[f] = Finder({lea: s["written"] for lea, s in school_indep.items()},
                                SCHOOL_WORDS | set(INDEPENDENT_WORDS) | set(words(re.sub(r" County$", "", county_name[f]))))
        marked = any(t in INDEPENDENT_WORDS[:2] or (len(t) >= 9 and osa(t, "INDEPENDENT", 2) <= 2) for t in toks)
        lea, how = sfinder[f].find(toks, own=() if marked else (cname,))
        unexpired = bool(r["Unexpired"]) or has_word(toks, "UNEXPIRED", 2)
        if lea is not None:
            s = school_indep[lea]
            school_how[how] += r["_live"]
            if how == "slip":
                slips.add((r["Office Description"], s["name"]))
            elif how == "part":
                parts.add((r["Office Description"], s["name"]))
            rid = f"2026-{STATE}-S-{lea}-school-board" + ("-S" if unexpired else "")
            x = race(rid, level="school", office_kind="school_board", office="School Board Member", jurisdiction=s["name"],
                     jurisdiction_id=f"{STATE}-S-{lea}", county_ids=None, partisan=0)
            x["special"] = int(unexpired)
            note = UNEXPIRED_NOTE if unexpired else SCHOOL_AT_LARGE_NOTE
            if note not in x["_notes"]:
                x["_notes"].append(note)
            put(rid, r)
            continue
        division = r["District"] or number_in(toks)
        conflicts += bool(r["_live"] and r["District"] and number_in(toks) and number_in(toks) != r["District"])
        if how == "words" and not r["District"] and not division:
            lost(r, "school board candidates", "with words that fit no school district on the Census Bureau's list")
            continue
        if any(t in ("INDEPENDENT", "IND", "CITY") for t in toks) and not r["District"]:
            lost(r, "school board candidates", "for an independent or city school district it does not name")
            continue
        if not division:
            lost(r, "school board candidates", "without a division of the county school district")
            continue
        school_how["county division"] += r["_live"]
        division_rows[(f, division)].append((r, unexpired))
    for (f, division), items in division_rows.items():      # one seat a division: an unexpired term on any of its rows is the seat's
        s = school_county[f]
        items_live = [(r, u) for r, u in items if r["_live"]]
        k = sum(1 for _r, u in items_live if u)
        rid = f"2026-{STATE}-S-{s['lea']}-school-board-{division}" + ("-S" if k else "")
        x = race(rid, level="school", office_kind="school_board", office="School Board Member", jurisdiction=s["name"],
                 jurisdiction_id=f"{STATE}-S-{s['lea']}", county_ids=None, partisan=0)
        x["district"], x["special"] = division, int(bool(k))
        if k:
            x["_notes"].append(UNEXPIRED_NOTE + ("" if k == len(items_live) else f" The list marks {k} of its {len(items_live)} candidates so."))
        for r, _u in items:
            put(rid, r)

    if any("rid" not in r for r in live):
        raise SystemExit("Kentucky: a row of the county filings list was neither put in a contest nor set aside; stopping")
    for rid in [rid for rid, x in races.items() if not x["_rows"]]:      # only withdrawn, disqualified or deceased rows: no contest is made of them
        del races[rid]
    used_places = {x["jurisdiction_id"].split("-M-")[1] for x in races.values() if x["level"] == "city"}
    used_schools = collections.defaultdict(set)
    for x in races.values():
        if x["level"] == "school":
            used_schools[x["jurisdiction_id"].split("-S-")[1]].update(r["fips"] for r in x["_rows"] + x["_gone"])
    specials = {k: v for k, v in specials.items() if any(x["jurisdiction_id"] == k for x in races.values())}

    # ---- the official schedule: which of these offices are on the 2026 ballot only for the rest of a term
    sched_ok, sched_bad = schedule_checked(paths["schedule"]) if paths["schedule"] else ([], ["the schedule was not downloaded"])
    if sched_bad:
        report.append("the State Board of Elections' election schedule did not confirm: " + "; ".join(sched_bad))
    confirmed = lambda words_: any(words_ in f for f in sched_ok)  # noqa: E731

    # ---- candidates: one row a person a contest; a city or school district two county clerks list is one contest
    party_noise, merged, dropped, elsewhere = collections.Counter(), collections.Counter(), 0, 0
    gaps, blanked, emptied = [], [], []
    for rid, x in races.items():
        rs = x["_rows"]
        if x["partisan"] is None:      # a city office is partisan where the list files most of its candidates under a party
            printed = [r for r in rs if r["Party"] != "WRITE-IN"] or [r for r in x["_gone"] if r["Party"] != "WRITE-IN"]
            x["partisan"] = int(bool(printed) and 2 * sum(1 for r in printed if r["Party"] != "NONPARTISAN") > len(printed))
        found = []
        for r in rs:
            name, did = filed_name(r["First Name"], r["Middle Name"], r["Last Name"], r["Suffix"])
            if did:
                name_did[did] += 1
            write_in = int(r["Party"] == "WRITE-IN")
            if x["partisan"]:
                party = party_words(r["Party"], unknown_party)
                code = party_code(party)
            else:
                party, code = NONPARTISAN, "N"
                party_noise[x["level"]] += r["Party"] not in ("NONPARTISAN", "WRITE-IN")
            c = next((c for c in found if c["_key"] == letters(name)), None)                # the same name, punctuation aside
            if c is None:      # or the same person on another county clerk's list, written a little differently
                c = next((c for c in found if r["fips"] not in c["_fips"] and any(same_filer(r, o) for o in c["_src"])), None)
                if c is not None:
                    mine, theirs = name_words(r)[0], name_words(c["_src"][0])[0]
                    if (len(mine) == len(theirs) and mine != theirs) or mine[-1] != theirs[-1]:      # spelled differently, not just shorter
                        c["_spelled"].append(f"{county_name[r['fips']]}'s list writes the name {name}.")
            if c is not None:
                merged["twice in one county's list" if r["fips"] in c["_fips"] else "by two county clerks"] += 1
                if c["write_in"] and not write_in:              # the row that prints the name carries the party
                    c["party"], c["code"] = party, code
                elif c["write_in"] == write_in and c["party"] != party:
                    report.append(f"{rid}: one name is listed twice under two parties; the first is kept")
                c["_fips"].add(r["fips"])
                c["_marks"].add((r["fips"], write_in))
                c["_src"].append(r)
                continue
            found.append(dict(name=name, party=party, code=code, write_in=write_in, note=None, _key=letters(name), _fips={r["fips"]},
                              _marks={(r["fips"], write_in)}, _src=[r], _spelled=[]))
        for g in x["_gone"]:           # a withdrawal one county clerk has entered counts against the same name on another's list
            gname = letters(filed_name(g["First Name"], g["Middle Name"], g["Last Name"], g["Suffix"])[0])
            for c in [c for c in found if g["fips"] not in c["_fips"] and (c["_key"] == gname or any(same_filer(g, o) for o in c["_src"]))]:
                found.remove(c)
                elsewhere += 1
        for c in found:
            notes = []
            if len({w for _f, w in c["_marks"]}) == 2:          # listed twice, once as a write-in and once not: said, not settled
                yes = " and ".join(sorted({county_name[f] for f, w in c["_marks"] if w}))
                no = " and ".join(sorted({county_name[f] for f, w in c["_marks"] if not w}))
                c["write_in"] = 0
                notes.append(f"The list files this candidate as a declared write-in in {yes} and as a candidate on the ballot in {no}.")
                merged["listed both as a write-in and not"] += 1
            elif c["write_in"]:
                notes.append(WRITE_IN)
            c["note"] = " ".join(notes + c["_spelled"]) or None
        x["_cands"] = found
        x["_counties"] = sorted({r["fips"] for r in rs + x["_gone"]})
        if not found:
            n = len(x["_gone"]) + (len(rs) if rs else 0)
            x["_notes"] = [f"The list shows no candidate for this office now: the {n} who filed {'is' if n == 1 else 'are'} marked withdrawn, "
                           "disqualified or deceased."]
            emptied.append(rid)
            continue
        # one seat, on party lines: a party has one candidate in November
        one_seat = x["partisan"] and (x["level"] == "county" or x["office_kind"] == "mayor" or (x["office_kind"] == "council" and x["district"]))
        if one_seat:
            per = collections.Counter(c["party"] for c in found if not c["write_in"] and c["party"] in MAJOR)
            twice = [(p, n) for p, n in per.items() if n > 1]
            if twice:
                p, n = max(twice, key=lambda t: t[1])
                why = (f"The Secretary of State's list still shows {n} {p} candidates for this office, which has one candidate a party in "
                       f"November; it does not say who won the May 19 primary, so no name is shown here.")
                x["_notes"] = [why + " " + LIST_AUTHORITY]
                dropped += len(found)
                blanked.append(rid)
                where = "" if not x["district"] else f", District {x['district']}" if x["district"].isdigit() else f", {x['district']}"
                gaps.append((STATE, "race", rid, f"{x['office']}{where}, {x['jurisdiction']}", "November candidates",
                             why + " " + LIST_AUTHORITY, COUNTY_URL))
                x["_cands"] = []

    # ---- what could not be placed, county by county
    per_gap = collections.defaultdict(collections.Counter)
    for f, what, why in unplaced:
        per_gap[(f, what)][why] += 1
    more = collections.defaultdict(dict)          # county -> {kind of contest: words for a note on its neighbours}
    family_of = {"mayor candidates": "mayor", "city council or commission candidates": "council", "school board candidates": "school",
                 "magistrate, constable or county commissioner candidates": "district", "county office candidates": "county",
                 "soil and water conservation district supervisor candidates": "soil"}
    for (f, what), whys in sorted(per_gap.items()):
        n = sum(whys.values())
        said = (" " + next(iter(whys)) if len(whys) == 1 else " (" + ", ".join(f"{k} {why}" for why, k in whys.most_common()) + ")")
        singular = what.replace("candidates", "candidate") if n == 1 else what
        gaps.append((STATE, "county", f, county_name[f], what,
                     f"The Secretary of State's list files {n} {singular} in {county_name[f]}{said}, so {'it' if n == 1 else 'they'} cannot be "
                     f"put in a contest here. {LIST_AUTHORITY}", COUNTY_URL))
        more[f][family_of[what]] = (f"The list has {n} more {singular} in {county_name[f]} that it does not tie to a contest; "
                                    f"{'it' if n == 1 else 'any of them'} may belong here.")

    # ---- races, with their counties and notes
    race_rows = []
    for rid, x in races.items():
        kind = x["office_kind"]
        if x["level"] == "city":
            code = x["jurisdiction_id"].split("-M-")[1]
            x["county_ids"] = json.dumps(sorted(places[code]["counties"] | set(x["_counties"])))
        elif x["level"] == "school":
            lea = x["jurisdiction_id"].split("-S-")[1]
            x["county_ids"] = json.dumps(sorted(used_schools[lea]))
        notes = list(x["_notes"])
        if kind == "clerk_of_court" and rid not in blanked:
            notes.append(CLERK_NOTE if confirmed("circuit court clerks") else UNEXPIRED_NOTE)
        if x["level"] == "soil_water":
            notes.append(SOIL_NOTE)
        if x["_cands"] and all(c["write_in"] for c in x["_cands"]):
            notes.append(ONLY_WRITE_INS)
        fam = {"mayor": "mayor", "council": "council", "school_board": "school", "soil_water": "soil"}.get(
            kind, "district" if kind in ("magistrate", "constable", "county_commissioner") else "county" if x["level"] == "county" else None)
        for f in x["_counties"]:
            if fam in more.get(f, {}):
                notes.append(more[f][fam])
        x["note"] = " ".join(notes) or None
        race_rows.append(tuple(x[c] for c in RACE_COLS))
        for c in x["_cands"]:
            cands.append([rid, "general", GENERAL, c["name"], c["party"], c["code"], None, 0, c["write_in"], None, None, None, None, SRC_COUNTY,
                          c["note"]])

    # ---- places: every county, and every city, school district and other district a contest here names
    place_rows = [("county", f, n, json.dumps([f]), SRC_COUNTIES) for f, n in sorted(county_name.items())]
    for code in sorted(used_places):
        p = places[code]
        listing = {f for x in races.values() if x["jurisdiction_id"] == f"{STATE}-M-{code}" for f in x["_counties"]}
        place_rows.append(("mcd", f"{STATE}-M-{code}", p["name"], json.dumps(sorted(p["counties"] | listing)), p["src"]))
    by_lea = {s["lea"]: s for s in list(school_county.values()) + list(school_indep.values())}
    for lea, fs in sorted(used_schools.items()):
        place_rows.append(("school", f"{STATE}-S-{lea}", by_lea[lea]["name"], json.dumps(sorted(fs)), by_lea[lea]["src"]))
    for key, (name, fs) in sorted(specials.items()):
        place_rows.append(("special", key, name, json.dumps(fs), SRC_COUNTY))

    return dict(races=races, race_rows=race_rows, cands=cands, gaps=gaps, place_rows=place_rows, unplaced=unplaced, report=report, rows=rows,
                live=live, gone=gone, listed=listed, paths=paths, county_name=county_name, county_key=county_key, places=places,
                school_county=school_county, school_indep=school_indep, used_places=used_places, used_schools=used_schools, matched_how=matched_how, school_how=school_how, slips=slips, parts=parts,
                only_city=only_city, ward_cities=ward_cities, ignored_district=ignored_district, by_name=by_name, conflicts=conflicts,
                unknown_party=unknown_party,
                name_did=name_did, party_noise=party_noise, merged=merged, dropped=dropped, blanked=blanked, elsewhere=elsewhere,
                emptied=emptied, sched_ok=sched_ok,
                sched_bad=sched_bad, folder=folder, per_office=per_office, left_off=left_off)


# ---------------------------------------------------------------------------------------------- the primary certification

def certification(path):
    """[{office, district, party, names, total, counties, page}] for every State Senator and State Representative section
    of the certification: the federal loader's reader (ballot/lists/ky.py certification()), with the state offices'
    sections and their district lines in place of the federal ones."""
    pdf = P.PDF(open(path, "rb").read())
    out, cur, section, covers = [], None, None, []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = KY.page_runs(pdf, page, res)
        flat = [r for r in runs if abs(r[3] - r[1]) < 0.01]
        up = [r for r in runs if abs(r[3] - r[1]) >= 0.01]
        rows = KY.flat_rows(flat)
        texts = [P.join(rs) for _y, rs in rows]
        if "For the office of" in texts:
            if cur is not None:
                raise SystemExit(f"Kentucky: a certification section ends at page {n} without its Total Votes row")
            section = texts[texts.index("For the office of") + 1]
            covers.append(section)
            if not any("Official 2026 Primary Election Results" == t for t in texts):
                raise SystemExit("Kentucky: the certification's cover page is not the Official 2026 Primary Election Results'")
            continue
        if section not in CERT_OFFICES:
            continue
        pending, head = [], None
        for (y, rs), text in zip(rows, texts):
            if KY.PAGE_HEAD.match(text):
                continue
            toks = KY.tokens(rs)
            nums = [t for t in toks if KY.NUMBER.match(t[2])]
            if text.startswith("Total Votes"):
                if cur is None or len(nums) != len(cur["edges"]):
                    raise SystemExit(f"Kentucky: a Total Votes row on page {n} of the certification does not fit its section")
                cur["total"] = [int(t[2].replace(",", "")) for t in nums]
                out.append(cur)
                cur, pending = None, []
                continue
            if nums and not KY.NUMBER.match(toks[0][2]) and all(KY.NUMBER.match(t[2]) for t in toks[1:]):     # a county row
                if head is not None:
                    edges = [t[1] for t in nums]
                    where = f"{head['office']} {head['district']} {head['party']}"
                    cols = {}
                    for rs2 in head["names"]:
                        for k, t in KY.by_edge(rs2, edges, where).items():
                            cols.setdefault(k, []).append(t)
                    for x, top, bottom, t in KY.upward_lines(up):
                        if bottom > y and top < head["y"]:
                            k = [k for k, e in enumerate(edges) if 0 < e - x < 50]
                            if len(k) != 1:
                                raise SystemExit(f"Kentucky: a name printed upward in {where} is under no column")
                            cols.setdefault(k[0], []).append((x, t))
                    names = []
                    for k in range(len(edges)):
                        got = cols.get(k, [])
                        if got and isinstance(got[0], tuple):
                            got = [t for _x, t in sorted(got, reverse=True)]
                        if not got:
                            raise SystemExit(f"Kentucky: column {k + 1} of {where} has no name")
                        names.append(" ".join(got))
                    cur = {"office": head["office"], "district": head["district"], "party": head["party"], "names": names,
                           "edges": edges, "counties": {}, "page": n}
                    head = None
                if cur is None:
                    raise SystemExit(f"Kentucky: a county row on page {n} of the certification comes before any section heading")
                county = toks[0][2]
                vals = {}
                for t in nums:
                    k = [k for k, e in enumerate(cur["edges"]) if abs(t[1] - e) <= 1.5]
                    if len(k) != 1:
                        raise SystemExit(f"Kentucky: a number in {county}'s row on page {n} is under no column")
                    vals[k[0]] = int(t[2].replace(",", ""))
                if len(vals) != len(cur["edges"]) or county in cur["counties"]:
                    raise SystemExit(f"Kentucky: {county}'s row on page {n} of the certification does not fit its section")
                cur["counties"][county] = [vals[k] for k in range(len(cur["edges"]))]
                continue
            if KY.PARTY_ROW.match(text):
                if cur is not None:
                    raise SystemExit(f"Kentucky: a new section starts on page {n} of the certification before the last one's Total Votes row")
                if not pending or pending[0] != section:
                    raise SystemExit(f"Kentucky: a party heading on page {n} of the certification has no {section} heading above it")
                ds = [CERT_DISTRICT.match(t) for t in pending[1:]]
                ds = [m for m in ds if m]
                if len(ds) != 1 or (ds[0].group(2) == "Senatorial") != (section == "State Senator"):
                    raise SystemExit(f"Kentucky: a {section} section on page {n} of the certification names no district of its chamber")
                head = {"office": section, "district": str(int(ds[0].group(1))), "party": text, "y": y, "names": []}
                pending = []
                continue
            if head is not None:
                head["names"].append(rs)
            elif cur is None:
                pending.append(text)
            # else: the names printed again at the top of a section's next page
    if cur is not None or head is not None:
        raise SystemExit("Kentucky: the certification's last state section has no Total Votes row")
    for office in CERT_OFFICES:
        if office not in covers:
            raise SystemExit(f"Kentucky: the certification has no {office} part")
    return out, covers


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators: ids, names, party, chamber and district only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    con.close()
    return legs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's first name or any
    other form of the name it keeps)."""
    readings = [name_parts(name), name_parts(re.sub(r'"[^"]*"', " ", name))]        # with and without a quoted nickname
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(r, f) for r in readings for f in forms)


def bare(party):
    return re.sub(r"\s+Party$", "", (party or "").strip())


def chamber_words(p):
    return f"Kentucky {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def race_for(row):
    """(race_id, level, office_kind, office, jurisdiction, district, seat, partisan) for one list row."""
    office, dd = row["Office"], row["District/Division"]
    pid, prefix, level, okind, partisan = KIND[office]
    if okind == "court_of_appeals":
        m = COA_DISTRICT.match(dd)
        if not m:
            raise SystemExit(f"Kentucky: could not read the district and division of a Court of Appeals filing ({dd!r})")
        d, div = str(int(m.group(1))), str(int(m.group(2)))
        return (f"2026-{STATE}-{prefix}{d}-{div}", level, okind, office, f"Court of Appeals District {d}, Division {div}", d, div, partisan)
    m = ORDINAL.match(dd)
    if not m:
        raise SystemExit(f"Kentucky: could not read the district of a {office} filing ({dd!r})")
    d = str(int(m.group(1)))
    where = {"state_senate": "Senate District", "state_house": "House District", "supreme_court": "Supreme Court District"}[okind]
    return (f"2026-{STATE}-{prefix}{d}", level, okind, office, f"{where} {d}", d, None, partisan)


def local_sources(L, C):
    """(sl_sources rows, sl_notes rows) for the local levels, with the list's own totals reconciled in the first row's note."""
    listed, gone, unplaced, merged = L["listed"], L["gone"], L["unplaced"], L["merged"]
    n_rows, n_live, stored = len(L["rows"]), len(L["live"]), len(L["cands"])
    placed = n_live - len(unplaced)
    repeats = merged["by two county clerks"] + merged["twice in one county's list"]
    if placed != stored + repeats + L["dropped"] + L["elsewhere"]:
        L["report"].append(f"{placed} rows were placed but {stored} candidates, {repeats} repeats and {L['dropped'] + L['elsewhere']} set "
                           "aside do not add up to that")
    how, did = L["matched_how"] + L["school_how"], L["name_did"]
    noise = sum(L["party_noise"].values())
    src = [(SRC_COUNTY, STATE, "official candidate list", "Kentucky Secretary of State",
            "Candidate Filings with the County Clerk, 2026: every county's candidates for county, city, school board and soil and water "
            "offices (the page's \"Excel spreadsheet of All Candidates\")", COUNTY_URL, "", listed["read"], listed["sha256"], n_rows,
            f"The page's own Excel button, posted as the page posts it ({listed['file'] or 'an .xls file'}, {listed['bytes']:,} bytes; the "
            "SHA-256 is of the file as fetched, and the file is not kept). Columns read: County, Last Name, First Name, Middle Name, "
            "Suffix, Party, Office, Office Description, District, Unexpired, Withdrawn, Disqualified, Deceased. The Date filed, PO Address, "
            "PO City, PO State, PO Zip and EMail columns are never turned into text. "
            f"Of {n_rows:,} rows, {L['left_off']} are marked withdrawn ({gone['Withdrawn']}), disqualified ({gone['Disqualified']}) or "
            f"deceased ({gone['Deceased']}) and left off; the page's own directory counts the other {n_live:,} office by office"
            + (", and every office's count matched. " if not any("own count" in x for x in L["report"]) else ", and not every count matched. ")
            + f"{placed:,} rows are placed, each in one contest; {len(unplaced)} name no city, school district or district that can be "
            f"told and are listed as gaps, county by county. Of the rows placed, {repeats} repeat a candidate already in the contest (a "
            f"city or school district that two county clerks list, or one name twice) and count once; {L['elsewhere']} are left off "
            f"because the other county clerk's list marks the same candidate withdrawn; and {L['dropped']} belong to the "
            f"{len(L['blanked'])} contests where the list still shows more than one candidate of a party for one seat, which are kept "
            f"without names. That leaves {stored:,} candidates. {len(L['emptied'])} contests are kept with no name because everyone who "
            f"filed for them is marked withdrawn, disqualified or deceased. "
            "The list holds each name in four columns, the family name in capitals; names are shown here in ordinary capitals, given "
            f"names first, with Jr, Sr, II, III or IV after the family name. A courtesy title in the Suffix column ({did['courtesy']} "
            f"rows) is left out; a nickname there ({did['nickname']} rows) is kept after the given names. The list gives no ballot order. "
            "Cities and school districts are named only in the free-text Office Description column, and a row is tied to one only when "
            f"that text fits exactly one name on the Census Bureau's lists: {how['exact']:,} rows by the name as printed, {how['part']} by "
            f"part of a name, {how['slip']} by a name one slip of spelling away, {how['only']} because the county has one city, and "
            f"{how['county division']} school board rows by the division number of the county's own school district. "
            f"{did['mayor filed under City Legislative Body']} rows filed under City Legislative Body whose description says Mayor are shown "
            f"as candidates for mayor. {noise} rows for school board and soil and water offices carry a party in the list; those offices are "
            f"nonpartisan and no party is shown. A district number on a county-wide office ({L['ignored_district']} rows) is ignored, and "
            f"where the District column and the description give different numbers ({L['conflicts']} rows) the column is used."
            + (f" {len(listed.get('scrubbed') or [])} kept cell held contact details a clerk had typed into it: it is blanked before anything "
               "is kept, and its row is listed with the gaps." if listed.get("scrubbed") else ""))]
    pages = C["listed"]["pages"]
    counts = C["counts"]
    src.append((SRC_COURT, STATE, "official candidate list", "Kentucky Secretary of State",
                "Candidate Filings with the Office of the Secretary of State, 2026 General Election: District Judge, Circuit Judge and "
                "Commonwealth's Attorney", KY.FILINGS + "17", "", C["listed"]["read"],
                hashlib.sha256("".join(p["sha256"] for p in pages.values()).encode()).hexdigest(), sum(len(p["rows"]) for p in pages.values()),
                "The Secretary of State's own filings pages for " + ", ".join(f"{p['called']} ({sum(1 for r in p['rows'] if not r['withdrawn'])})"
                                                                               for p in pages.values())
                + ", read with the federal loader's reader: name (first line), office, district and division, and party only; the address and "
                  "e-mail column is never read and the pages are not kept. Every group's count in its heading matched its rows. "
                  f"{len(C['cands'])} candidates in {len(C['race_rows'])} contests; withdrawn, deceased or disqualified, left off: "
                  f"{counts['withdrawn']}; declared write-in candidates: {counts['write-ins']}. The list names only the seats someone filed "
                  "for and gives no ballot order. The sha256 here is of the pages' own hashes joined."))
    p = L["paths"]

    def official(sid, key, kind, agency, title, published, rows, note):
        if p.get(key):
            url = CENSUS_SHP + os.path.basename(COUNTY_ZIP) if key == "counties" else OFFICIAL[key][1]
            src.append((sid, STATE, kind, agency, title, url, published, mtime(p[key]), sha(p[key]), rows, note))

    census = "U.S. Census Bureau"
    official(SRC_COUNTIES, "counties", "official boundaries", census, "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "2024", TOTAL_COUNTIES, "The names and five-digit codes of Kentucky's 120 counties.")
    official(SRC_PLACES, "places", "official place codes", census, "2020 place codes by county, Kentucky (st21_ky_place_by_county2020.txt)", "2020",
             sum(1 for x in L["places"].values() if x["src"] == SRC_PLACES),
             "Kentucky's active cities with the counties each lies in: the names a contest's free text is matched to, and each city's code. "
             "Census designated places are not governments and are left out.")
    official(SRC_CONCITY, "concity", "official boundaries", census, "Cartographic boundary file, consolidated cities, 2024 (cb_2024_us_concity_500k)",
             "2024", sum(1 for x in L["places"].values() if x["src"] == SRC_CONCITY),
             "The name and code of the Louisville/Jefferson County metro government, whose mayor and council the whole county elects.")
    schools = list(L["school_county"].values()) + list(L["school_indep"].values())
    official(SRC_UNSD, "unsd", "official boundaries", census, "Cartographic boundary file, unified school districts, Kentucky, 2024 "
             "(cb_2024_21_unsd_500k)", "2024", sum(1 for s in schools if s["src"] == SRC_UNSD),
             "The names and codes of the 120 county school districts and of the independent districts that run through grade 12.")
    official(SRC_ELSD, "elsd", "official boundaries", census, "Cartographic boundary file, elementary school districts, Kentucky, 2024 "
             "(cb_2024_21_elsd_500k)", "2024", sum(1 for s in schools if s["src"] == SRC_ELSD),
             "The names and codes of the independent school districts that stop at grade 8.")
    lrc = "Kentucky General Assembly (Legislative Research Commission)"
    for sid, key, title, word in ((SRC_DISTRICTS, "districts", "KRS 24A.030, Judicial districts (the version in force until January 1, 2031)", "district"),
                                  (SRC_CIRCUITS, "circuits", "KRS 23A.020, Judicial circuits", "circuit")):
        m = C["maps"].get(key)
        official(sid, key, "statute", lrc, title, "", len(m or {}),
                 f"The counties of each judicial {word}: {len(m)} numbered sentences, every county named once." if m
                 else f"Its list of each judicial {word}'s counties could not be read on the last run.")
    official(SRC_SCHEDULE, "schedule", "official calendar", "Kentucky State Board of Elections", "Kentucky Election Schedule, 2026-2036", "",
             len(L["sched_ok"]), ("Which offices are elected in which year. Checked in its marks: " + "; ".join(L["sched_ok"]) + "."
                                  if L["sched_ok"] and not L["sched_bad"] else "Its marks could not be confirmed on the last run."))

    if not L["sched_bad"]:
        calendar = ("On November 3, 2026 Kentucky elects each county's officers (judge/executive, magistrates or commissioners, county clerk, "
                    "county attorney, sheriff, jailer, coroner, surveyor, property valuation administrator and constables), its district "
                    "judges, every city council and commission, the mayors and school board members whose four-year terms are ending, and "
                    "soil and water conservation district supervisors. Statewide officers are elected in 2027, and circuit judges, circuit "
                    "court clerks and Commonwealth's attorneys in 2030, so the few such seats on this ballot are filled only for the time "
                    "left until then. The other mayors and school board seats, and Louisville's even-numbered Metro Council districts, are "
                    "elected in 2028.")
    else:
        calendar = ("The Secretary of State's lists for November 3, 2026 hold county officers, district judges, mayors, city councils and "
                    "commissions, school board members and soil and water conservation district supervisors. Which offices are elected in "
                    "other years could not be confirmed from the State Board of Elections' schedule on the last run.")
    n_unplaced, n_blank = len(unplaced), len(L["blanked"])
    coverage = ("Loaded: every contest the Secretary of State's \"Candidate Filings with the County Clerk\" list ties to a place, in all 120 "
                "counties (county officers, magistrates, commissioners, constables, circuit court clerks, mayors, city councils and "
                "commissions, school boards, soil and water supervisors), and the district judges, circuit judges and Commonwealth's "
                f"attorneys on the Secretary of State's own filings pages. Left out: withdrawn, disqualified and deceased candidates; "
                f"{n_unplaced} candidates the list files without a city, school district or district that can be told (gaps, county by "
                f"county); the names in {n_blank} contests where the list still shows more than one candidate of a party for one seat; "
                "ballot questions (Constitutional Amendment 1 and any local question); primaries. The list gives no ballot order, and a soil "
                "and water contest with no more candidates than seats is not printed on the ballot.")
    notes = [(STATE, "local_calendar", calendar, "Kentucky State Board of Elections, Kentucky Election Schedule (2026-2036); KRS 262.240 for "
              "soil and water supervisors", OFFICIAL["schedule"][1]),
             (STATE, "local_coverage", coverage, "Kentucky Secretary of State, Candidate Filings (the county clerks' list and the Secretary's "
              "own pages)", COUNTY_URL)]
    return src, notes


def local_report(L, C, say):
    """What the local levels came to, and everything a person should read: names matched by part or by a slip, single cities."""
    races, gaps = L["races"], L["gaps"] + C["gaps"]
    per = collections.Counter(x["level"] for x in races.values())
    say(f"    Kentucky local: {len(L['rows']):,} rows on the county clerks' list, {L['left_off']} withdrawn, disqualified or deceased left "
        f"off, {len(L['live']):,} live; {len(L['live']) - len(L['unplaced']):,} placed, {len(L['unplaced'])} not; {len(L['race_rows']):,} "
        f"contests (" + ", ".join(f"{k} {v:,}" for k, v in sorted(per.items())) + f") and {len(L['cands']):,} candidates; "
        f"{len(L['blanked'])} contests kept without names and {len(L['emptied'])} where everyone who filed is marked withdrawn; "
        f"{L['elsewhere']} left off as withdrawn on another county's list; trial courts: {len(C['race_rows'])} contests, {len(C['cands'])} candidates; "
        f"{len(L['place_rows'])} places; gaps: " + ", ".join(f"{k} {v}" for k, v in sorted(collections.Counter(g[1] for g in gaps).items())))
    say("      repeats: " + (", ".join(f"{k} {v}" for k, v in sorted(L["merged"].items())) or "none")
        + "; name column: " + ", ".join(f"{k} {v}" for k, v in sorted(L["name_did"].items())))
    for words_, name in sorted(L["slips"]):
        say(f"      matched by one slip of spelling (read these): \"{words_}\" is {name}")
    for words_, name in sorted(L["parts"]):
        say(f"      matched by part of a name (read these): \"{words_}\" is {name}")
    say("      a contest with no city named, in a county with one city: " + "; ".join(f"{c}: {p}" for c, p in sorted(L["only_city"])))
    say("      cities that elect by ward or district: " + "; ".join(f"{n} ({d} districts, {r} rows)" for n, d, r in sorted(L["ward_cities"])))
    if L["unknown_party"]:
        say("      party words not seen before (shown as printed): " + ", ".join(sorted(L["unknown_party"])))
    for line in L["report"]:
        say(f"      check: {line}")


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "ky")
    os.makedirs(folder, exist_ok=True)
    report = []

    lpath = filings(folder, say)
    listed = json.load(open(lpath, encoding="utf-8"))
    cpath = os.path.join(folder, CERT_FILE)
    net.download(KY.CERT_URL, cpath, max_age_days=30, say=say)
    if not open(cpath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Kentucky: the primary certification downloaded is not a PDF; read the results page again")
    sections, covers = certification(cpath)
    legs = roster(roster_db)
    home = other_offices(say)

    # ---- races and November candidates, from the list
    races, general, gone, write_ins, order, nominee, counted = {}, [], [], [], {}, {}, {}
    for office, page in listed["pages"].items():
        live = sum(c for _g, c, w in page["groups"] if not w)
        counted[office] = (live, sum(1 for r in page["rows"] if not r["withdrawn"]))
        if counted[office][0] != counted[office][1]:
            report.append(f"the {office} page's headings count {live} candidates but {counted[office][1]} rows were read")
        for r in page["rows"]:
            rid, level, okind, office_, juris, d, seat, partisan = race_for(r)
            if r["withdrawn"]:
                gone.append((rid, r["Name"]))
                continue
            if rid not in races:
                chamber = {"state_senate": "Senate", "state_house": "House"}.get(okind)
                hs = [p for p in legs if chamber and p["chamber"] == chamber and str(p["district"]).lstrip("0") == d]
                h = hs[0] if len(hs) == 1 else None
                note = []
                if okind == "state_senate":
                    note.append(SENATE_NOTE)
                if chamber and h is None:
                    note.append("The roster shows no sitting member for this seat.")
                    report.append(f"{rid}: {len(hs)} sitting members in the roster for this seat")
                if not partisan:
                    note.append(COURT_NOTE)
                note.append(ORDER_NOTE)
                races[rid] = dict(race_id=rid, state=STATE, level=level, office_kind=okind, office=office_, jurisdiction=juris,
                                  jurisdiction_id=d, county_ids=None, district=d, seat=seat, special=0, partisan=partisan,
                                  holder_id=h["id"] if h else None, holder_name=h["full"] if h else None,
                                  holder_party=h["party"] if h else None, election_date=GENERAL, note=" ".join(note), _holder=h,
                                  _chamber=chamber)
            party = r["Party"]
            write_in = int(party == "Write-In")
            if not partisan:
                if party not in ("Nonpartisan", "Write-In"):
                    report.append(f"{rid}: a nonpartisan seat's candidate is listed with the party {party!r}")
                shown_party, code = NONPARTISAN, "N"
            else:
                shown_party, code = party, party_code(party)
            if write_in:
                write_ins.append((rid, r["Name"]))
                pos = None
            else:
                order[rid] = order.get(rid, 0) + 1
                pos = order[rid]
                if party in PRIMARY_CODE:
                    if (rid, party) in nominee:
                        raise SystemExit(f"Kentucky: two {party} candidates for {rid} on the November list")
                    nominee[(rid, party)] = r["Name"]
            general.append(dict(rid=rid, name=r["Name"], party=shown_party, code=code, pos=pos, write_in=write_in))

    def identify(race, name, party):
        """(incumbent, state_member_id, note) for one name: the seat's sitting member when the name fits, else a sitting
        legislator of the same party elsewhere when the name fits exactly one."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if not race["_chamber"]:
            return 0, None, None
        pool = [p for p in legs if bare(p["party"]) == bare(party) and person_fits(name, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    cands = []
    for g in general:
        race = races[g["rid"]]
        inc, mid, n2 = identify(race, g["name"], g["party"])
        note = " ".join(x for x in (WRITE_IN if g["write_in"] else None, n2) if x) or None
        cands.append([g["rid"], "general", GENERAL, g["name"], g["party"], g["code"], g["pos"], inc, g["write_in"], None, None, None,
                      mid, SRC_LIST, note])

    # ---- which seats: the Senate's even half, the whole House
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    house = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if sen != list(range(2, SENATE_SEATS + 1, 2)):
        report.append(f"the Senate seats on the list are not the 19 even-numbered districts: {sen}")
    if house != list(range(1, HOUSE_SEATS + 1)):
        missing = sorted(set(range(1, HOUSE_SEATS + 1)) - set(house))
        report.append(f"House districts with no candidate on the list: {missing}")
    for rid, race in races.items():
        if not any(c[0] == rid and not c[8] for c in cands):
            report.append(f"{rid}: only declared write-ins on the list; nobody's name will be printed")

    # ---- primary fields: certified votes, county rows reconciled to Total Votes
    unreconciled, upset, stray, nfields, primary = [], [], [], 0, []
    for s in sections:
        okind = CERT_OFFICES[s["office"]]
        rid = f"2026-{STATE}-{'SS' if okind == 'state_senate' else 'SH'}{s['district']}"
        if s["party"] not in PRIMARY_CODE:
            raise SystemExit(f"Kentucky: a {s['party']} primary for {rid} in the certification; its election code is not set")
        summed = [sum(c[k] for c in s["counties"].values()) for k in range(len(s["names"]))]
        if summed != s["total"]:
            unreconciled.append(f"{rid} {s['party']}: county rows add to {summed}, Total Votes row says {s['total']}")
        if rid not in races:
            stray.append(f"{rid} {s['party']}")
            continue
        if len(s["names"]) < 2:
            continue
        nfields += 1
        race = races[rid]
        total = sum(s["total"])
        won = nominee.get((rid, s["party"]))
        top = max(range(len(s["names"])), key=lambda k: s["total"][k])
        if sorted(s["total"], reverse=True)[:2].count(s["total"][top]) > 1:
            report.append(f"{rid} {s['party']} primary: the top two are tied")
        picked = [k for k, nm in enumerate(s["names"]) if won and KY.same_person(nm, won)]
        if len(picked) > 1:
            raise SystemExit(f"Kentucky: {won} on the November list fits more than one name in the {rid} {s['party']} primary")
        winner = picked[0] if picked else top
        if winner != top:
            upset.append(f"{rid} {s['party']}")
        if not picked:
            report.append(f"{rid} {s['party']} primary: its top vote-getter is not the {s['party']} candidate on the November list "
                          f"({won or 'none'})")
        for k, printed in enumerate(s["names"]):
            name, caps = KY.shown(printed)
            inc, mid, n2 = identify(race, name, s["party"])
            notes = [CAPS] if caps else []
            if k == winner and not picked:
                notes.append(NOT_ON_LIST)
            if n2:
                notes.append(n2)
            primary.append([rid, f"primary-{PRIMARY_CODE[s['party']]}", PRIMARY, name, s["party"], party_code(s["party"]), None, inc, 0,
                            s["total"][k], round(100 * s["total"][k] / total, 1) if total else None,
                            "advanced" if k == winner else "lost", mid, SRC_CERT, " ".join(notes) or None])
    if stray:
        report.append(f"primary sections for seats not on the November list (not loaded): {stray}")
    report += [f"primary section does not add up: {u}" for u in unreconciled]
    if upset:
        report.append("the November nominee is not the primary's top vote-getter in " + ", ".join(upset))
    cands += primary

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Kentucky: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- the rest of the list, counted only
    skipped, called = [], {}
    if home is None:
        report.append("the Candidate Filings home page could not be read, so the other offices on it were not counted")
    else:
        for pid, office, n in home:
            if pid in PAGES:
                live = counted.get(PAGES[pid][0], (None,))[0]
                if live is not None and live != n:
                    report.append(f"the home page counts {n} candidates for {office}; its page counts {live}")
            elif pid in COURT_PAGES:                       # read below, with the local levels
                called[pid] = n
            elif pid not in KY.OFFICE_PAGES:
                skipped.append(f"{office} ({n})")

    # ---- the local levels: the county clerks' list and the trial courts
    L = local_rows(cache, say)
    C = court_rows(L["folder"], say, L["paths"], L["county_key"], L["sched_ok"], L["report"])
    for pid, n in called.items():
        page = C["listed"]["pages"].get(pid)
        if page and n != sum(c for _g, c, w in page["groups"] if not w):
            L["report"].append(f"the home page counts {n} candidates for {page['called']}; its page counts another number")
    local_src, local_notes = local_sources(L, C)
    local_races, local_cands = L["race_rows"] + C["race_rows"], L["cands"] + C["cands"]
    clash = {r[0] for r in local_races} & set(races)
    if clash or len({r[0] for r in local_races}) != len(local_races):
        raise SystemExit("Kentucky: two contests share one race id; stopping")
    seen = set()
    for c in local_cands:
        if (c[0], c[1], c[3]) in seen:
            raise SystemExit(f"Kentucky: one name is listed twice in {c[0]}")
        seen.add((c[0], c[1], c[3]))

    # ---- write: Kentucky's rows only, in one transaction
    cols = RACE_COLS
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    nlist = sum(len(p["rows"]) for p in listed["pages"].values())
    src = [
        (SRC_LIST, STATE, "official candidate list", "Kentucky Secretary of State",
         "Candidate Filings with the Office of the Secretary of State, 2026 General Election: State Senator, State Representative, "
         "Justice of the Supreme Court and Judge of the Court of Appeals", KY.FILINGS + "12", "", listed["read"],
         hashlib.sha256("".join(p["sha256"] for p in listed["pages"].values()).encode()).hexdigest(), nlist,
         "Read from the pages " + ", ".join(f"{o} ({p['url']}, SHA-256 {p['sha256'][:16]}...)" for o, p in listed["pages"].items())
         + ". Name (first line), office, district/division and party only; the address and e-mail column is never read and the "
           "pages are not kept. Every group's count in its heading matched its rows. The list gives no ballot order (it goes by "
           f"district, then filing); its own order is kept. Withdrawn, deceased or disqualified, left off: {len(gone)}. Declared "
           f"write-in candidates (party printed \"Write-In\"): {len(write_ins)}. The sha256 here is of the pages' own hashes joined."
         + (f" Also on the list and not loaded here: {', '.join(skipped)}." if skipped else "")
         + " The trial court offices on the list (District Judge, Circuit Judge, Commonwealth's Attorney) are read as local contests."),
        (SRC_CERT, STATE, "official results", "Kentucky State Board of Elections",
         "Official 2026 Primary Election Results, May 19, 2026 (\"2026 Primary Results - Official Certification\"): State Senator "
         "and State Representative", KY.CERT_URL, KY.created(cpath), mtime(cpath), sha(cpath), sum(len(s["names"]) for s in sections),
         f"Linked from {KY.RESULTS_PAGE}. One section per contested party primary (an uncontested primary is not on the ballot): "
         f"{sum(1 for s in sections if s['office'] == 'State Senator')} State Senator and "
         f"{sum(1 for s in sections if s['office'] == 'State Representative')} State Representative sections. Statewide Total Votes "
         "stored, checked against the county rows. The certification has no write-in line, so shares are of the candidates' votes. "
         "The date given as published is the file's own creation date. "
         + ("Every section's county rows add up to its Total Votes row." if not unreconciled else "Did not add up: " + "; ".join(unreconciled) + ".")),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ky.sqlite",
         "Sitting Kentucky legislators", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db), len(legs),
         "Who holds each legislative seat today (chamber and district); the roster carries no judges."),
    ]
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (STATE.lower() + "-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows + local_races)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local_cands)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local_src)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", L["place_rows"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", L["gaps"] + C["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local_notes)
    con.close()

    gen = [c for c in cands if c[1] == "general"]
    by = lambda kind, rows: sum(1 for c in rows if races[c[0]]["office_kind"] == kind)
    say(f"    Kentucky: {len(races)} races ({len(sen)} Senate, {len(house)} House, "
        f"{sum(1 for r in races.values() if r['level'] == 'court')} appellate court); {len(gen)} candidates on the November list "
        f"(Senate {by('state_senate', gen)}, House {by('state_house', gen)}, courts "
        f"{by('supreme_court', gen) + by('court_of_appeals', gen)}; {len(write_ins)} declared write-ins, {len(gone)} withdrawn left off); "
        f"{nfields} primary fields, {len(primary)} primary rows (Senate {by('state_senate', primary)}, House {by('state_house', primary)}), "
        "certified votes")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    local_report(L, C, say)
    return len(gen) + len(local_cands)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_ky <database>")
    load(sys.argv[1])
