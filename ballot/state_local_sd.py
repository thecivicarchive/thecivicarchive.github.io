"""
ballot/state_local_sd.py - South Dakota's state races on the November 3, 2026 ballot: every State Senate seat (35, one
member a district), every State House seat (70: two members a district, except that Districts 26 and 28 are each split
into single-member A and B districts), Governor and Lieutenant Governor (one ticket, one vote), and the statewide offices
on this year's list: Secretary of State, Attorney General, State Auditor, State Treasurer, Commissioner of School and
Public Lands and Public Utilities Commissioner. South Dakota elects both chambers every two years, so every seat is up.

Sources, the Secretary of State's own and nothing else:

  - The 2026 General Election Candidate List (vip.sdsos.gov, election 774): a Telerik grid of every contest, 50 rows a
    page, paged here through the grid's own page links (one request a second). Columns are taken by name, and only
    Contest, Name, Party, District/County, Ballot Order, Status, WithdrawnDate, OfficeSeqNum, DistrictType, elType and
    eldate; the grid also carries mailing addresses (Mailing Address, elAddress1, elAddress2, elCity, elState, elZip),
    which are never read, printed or kept. The state offices' rows are kept, and only those columns, as JSON in
    ballot_cache/sd/ (the county and local rows in ballot_cache/sd/local/, see below). A withdrawn candidate is left
    off the November ballot.
  - The 2026 Primary Election Candidate List (election 773), read the same way. South Dakota prints a party primary
    only when it is contested; every candidate in a contested primary has a ballot order on the list, which is used as
    a check (uncontested Democrats have one too, so its absence proves nothing). A party primary is a field when it has
    more candidates on the ballot than seats (one, or two in a two-member House district). Who advanced is read from the November list: the party's candidates for that seat
    there, a withdrawn one included (he or she won the primary and withdrew later).
  - The July 28 Republican runoff for Governor: the Secretary of State's results site (electionresults.sd.gov) shows it
    as its current election. Only the names of the runoff's two candidates are read from it (they are the two who
    advanced from the June 2 field); the site labels its figures "Unofficial Results", so no figure is loaded. The
    names are kept in ballot_cache/sd/, and a later run reads the kept names and asks the site nothing.
  - No vote counts: the State Canvassing Board's certified canvass of the 2026 primary and runoff was not published on
    sdsos.gov as of 2026-09-30 (see ballot/lists/sd.py). Every primary and runoff row has votes None.

Today's holders come from state_sd.sqlite (the Open States roster): current legislators by chamber and district, and
the officials table for Governor, Attorney General and Secretary of State (the roster does not carry the Auditor, the
Treasurer, the Commissioner of School and Public Lands or the Public Utilities Commissioners). A two-member House
district has two holders: holder_id holds both roster ids joined by a comma, holder_name both names joined by " and ",
holder_party both parties joined by ", " (one party when both are the same). Only names, parties, districts and ids are
read from the roster; its e-mail, phone and address columns never are.

A candidate is marked as the sitting member (incumbent 1, state_member_id) only when the name fits a holder of that same
seat (for Governor, the first name on the ticket against the Governor), and the fit is one to one. A candidate who sits
today in the other chamber for the same district, or who holds another seat or office in the roster (for a statewide
race), gets state_member_id with incumbent 0 and a note, again only when exactly one roster person fits.

County and local races (John, 2026-09-30)
-----------------------------------------
The same November list carries county offices in all 66 counties (commissioners by district and at large, auditors,
sheriffs, registers of deeds and a few finance officers, treasurers, coroners and a state's attorney, all on a party
ballot), councils in the cities and towns that vote in November and put their candidates into the state's system,
conservation district supervisors, water development district directors and Heartland Consumers Power District
directors (all nonpartisan). One reading of the grid serves both sides: the rows of every other kind than the state
offices' are kept, allowed columns only, in ballot_cache/sd/local/, and kept copies no more than three days old are
used as they are, so a re-run downloads nothing while a weekly run reads the lists again (as does --refresh). From the
June list the local side keeps only which contests it carried and where (no candidate), to say what was voted on in
June.

  - A contest is one office, one place and one of the list's office numbers (OfficeSeqNum, a hidden column). The list
    prints the same title for contests that differ only in that number (three Trustee contests in one town, two
    Conservation District Supervisor contests in one district) and does not say how they differ, so they are kept
    apart, numbered in the list's order ("Contest 1 of 2") and the note says so. The list does not say how many are
    elected in a contest or which contests fill an unexpired term; nothing of the kind is guessed (special is 0).
  - Parties on county offices are written out as on the state rows; every other local office is "Nonpartisan office".
    Ballot order is the list's own column, which is empty for most uncontested candidates. A candidate with no
    opponent is elected without being printed (SDCL 12-16-1.1); the note on a one-candidate contest says so. Withdrawn
    candidates are left off. Write-in votes are not counted in South Dakota (SDCL 12-20-21.2), so there are none.
  - Treasurers, state's attorneys and coroners, and commissioners from even-numbered districts, are regularly elected
    in presidential years (SDCL 7-7-1.1, 7-8-1). Where the list has such a contest in 2026 the note says so, and that
    the list does not say why.
  - Places: county names and codes from the Census county file the kit keeps (cb_2024_us_county_500k.zip); cities and
    towns from the Census Bureau's 2020 place codes for South Dakota (name, code and county; the list's city must be
    the only incorporated place of that name). A conservation district the list names by its county is filed under
    that county; the four it names otherwise (Brule-Buffalo, East Pennington, Elk Creek, Pennington) by the Department
    of Agriculture and Natural Resources' district histories. A water development district director area's counties
    are the ones its description names in ARSD 74:05:05:16 to :21.01 (a city named there without its county is placed
    by the Census place codes); the Heartland subdivisions' counties are from the district's certification to the
    Secretary of State (SDCL 49-36-3). Those tables were typed by hand from the documents, each listed in sl_sources
    with the day it was read and its SHA-256; none is fetched again at run time.
  - The Secretary of State's 2026 guide lists the director areas up for election; one with no candidate on the list is
    kept as a contest with no candidate and a note. A county with no row for sheriff, auditor (or finance officer) or
    register of deeds gets a line in sl_gaps: the list does not say why, and candidates for county office file with
    the county auditor, so an office missing from the list is no proof that no one is running.
  - A row the loader cannot place (an office or a kind of district it does not know, a city that is not exactly one
    Census place) goes to sl_gaps and is never guessed. Ballot questions, school boards and cities that are not on the
    state list, and local primaries are not loaded.

Usage: python ballot/state_local_sd.py <database file> [--cache <folder>] [--refresh]
"""

import datetime as dt
import hashlib
import html as H
import http.cookiejar
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import zipfile
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like   # noqa: E402
from ballot.common import fold, name_parts, party_code      # noqa: E402
from ballot.match import fits                               # noqa: E402
from states import net                                      # noqa: E402

STATE, FIPS, NAME = "SD", "46", "South Dakota"
GENERAL, PRIMARY, RUNOFF = "2026-11-03", "2026-06-02", "2026-07-28"
GENERAL_URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=774"
PRIMARY_URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=773"
RUNOFF_URL = "https://electionresults.sd.gov/resultsSW.aspx?type=SWR&map=CTY"
ROSTER_DB = os.path.join(HERE, "state_sd.sqlite")
CACHE = os.path.join(HERE, "ballot_cache", "sd")
MAX_AGE_DAYS = 3                                            # kept copies of the lists no older than this are used as they are

# the only grid columns ever read; every other column (the addresses among them) is never turned into text
KEEP = ("Contest", "Name", "Party", "District/County", "Ballot Order", "Status", "WithdrawnDate", "OfficeSeqNum",
        "DistrictType", "elType", "eldate")
STATE_TYPES = {"SW", "SEN", "HOU"}                          # statewide, State Senate, State House; the other rows are the local side's
PARTY = {"REP": "Republican", "DEM": "Democratic", "IND": "Independent", "LIB": "Libertarian"}
STATUS_MARK = re.compile(r"\s*\((?:Withdrawn|Successful Challenge)[^)]*\)\s*$")

# statewide contests as the lists print them: (race key, office_kind, office shown, roster office)
STATEWIDE = {
    "Governor and Lieutenant Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),
    "Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),        # the primary's name for the same race
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "State Auditor": ("AUD", "state_auditor", "State Auditor", None),
    "State Treasurer": ("TREAS", "state_treasurer", "State Treasurer", None),
    "Commissioner of School and Public Lands": ("SPL", "school_and_public_lands_commissioner", "Commissioner of School and Public Lands", None),
    "Public Utilities Commissioner": ("PUC", "public_utilities_commissioner", "Public Utilities Commissioner", None),
}
LEGISLATURE = {"State Senator": ("SS", "state_senate", "State Senator", "Senate"),
               "State Representative": ("SH", "state_house", "State Representative", "House")}
CHAMBER_WORDS = {"Senate": "the South Dakota Senate", "House": "the South Dakota House of Representatives"}

SRC_GENERAL = "sd-sos-2026-state-candidate-list"
SRC_PRIMARY = "sd-sos-2026-state-primary-candidate-list"
SRC_RUNOFF = "sd-sos-2026-governor-runoff-contest"
SRC_ROSTER = "sd-openstates-roster"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


# ---------- the candidate grids: allowed columns only ----------

def grid_rows(page):
    """The allowed columns of every row on one page of the grid, as dicts. Cells of other columns are never unescaped."""
    heads = [text(h) for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    missing = [k for k in KEEP if k not in heads]
    if missing:
        raise SystemExit(f"South Dakota (state races): the candidate grid's columns changed; missing {missing}")
    idx = {k: heads.index(k) for k in KEEP}
    out = []
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("South Dakota (state races): a grid row does not line up with the grid's headings")
        out.append({k: text(cells[i]) for k, i in idx.items()})
    return out


def read_grid(url, election, say=print):
    """Every page of a candidate list, each row cut down to the allowed columns as it is read; returns (items the grid
    reports, rows, the SHA-256 of the pages' bytes as fetched, in order). Asks at most three times for any one page,
    then stops and says so."""
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    net.patient_lookups()
    digest = hashlib.sha256()

    def ask(data=None):
        headers = {"User-Agent": net.UA, "Accept": "text/html"}
        if data:
            headers.update({"Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        last = None
        for attempt in range(3):
            try:
                with opener.open(Request(url, data=data, headers=headers), timeout=120) as r:
                    raw = r.read()
                page = raw.decode("utf-8", "replace")
                if 'class="rgHeader' not in page:
                    raise SystemExit(f"South Dakota (state races): {url} answered without its candidate grid "
                                     "(a bot check or a changed page); stopped")
                digest.update(raw)
                return page
            except (HTTPError, URLError, OSError) as e:
                last = e
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        raise SystemExit(f"South Dakota (state races): {url} refused three times ({last}); stopped")

    page = ask()
    if f"2026 {election} Election" not in page:
        raise SystemExit(f"South Dakota (state races): {url} is no longer the 2026 {election} Election list")
    info = re.search(r"(\d+)\s*(?:</strong>)?\s*items in\s*(?:<strong>)?\s*(\d+)", page)
    if not info:
        raise SystemExit("South Dakota (state races): the grid's item count was not found")
    items, pages = int(info.group(1)), int(info.group(2))
    seen, kept, n = 0, [], 1
    while True:
        rows = grid_rows(page)
        seen += len(rows)
        kept += rows
        if n >= pages:
            break
        pager = page[page.find('class="rgPager"'):][:20000]
        links = [(text(t), H.unescape(tg)) for tg, t in
                 re.findall(r'<a[^>]*href="javascript:__doPostBack\(&#39;([^&]+)&#39;[^"]*"[^>]*>(.*?)</a>', pager, re.S)]
        target = next((tg for t, tg in links if t == str(n + 1)), None)
        if target is None:                                   # past page 10: the last "..." opens the next block of pages
            target = next((tg for t, tg in reversed(links) if t == "..."), None)
        if target is None:
            raise SystemExit(f"South Dakota (state races): no link to page {n + 1} of {url}")
        form = {m.group(1): H.unescape(m.group(2))
                for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
        form["__EVENTTARGET"], form["__EVENTARGUMENT"] = target, ""
        time.sleep(1.0)
        page = ask(urllib.parse.urlencode(form).encode())
        n += 1
        cur = re.search(r'class="rgCurrentPage"[^>]*>\s*<span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"South Dakota (state races): paging {url} went wrong at page {n}")
    if seen != items:
        raise SystemExit(f"South Dakota (state races): read {seen} rows of {url}, the grid reports {items}")
    return items, kept, digest.hexdigest()


def _fresh(day):
    try:
        return (dt.date.today() - dt.date.fromisoformat(day)).days <= MAX_AGE_DAYS
    except (TypeError, ValueError):
        return False


def general_cut(rows):
    """What the local side keeps of the November list: every row that is not a state office's, allowed columns only."""
    return {"columns": list(KEEP), "rows": [{k: r[k] for k in KEEP} for r in rows]}


def primary_cut(rows):
    """What the local side keeps of the June list: which contests it carried and where, with no candidate at all."""
    tally = defaultdict(lambda: defaultdict(set))
    for r in rows:
        tally[r["DistrictType"]][r["Contest"]].add(r["District/County"])
    return {"columns": ["DistrictType", "Contest", "District/County"], "rows_by_type": dict(sorted(Counter(r["DistrictType"] for r in rows).items())),
            "tally": {t: {c: sorted(v) for c, v in sorted(cs.items())} for t, cs in sorted(tally.items())}}


def cached_grid(url, election, path, date_prefix, say=print, local_path=None, local_cut=None, refresh=False):
    """One reading of a list serves both sides: its state rows are kept as JSON in `path` (allowed columns only, as
    before), and what the local side needs of the other rows (local_cut, again allowed columns only) in `local_path`.
    Kept copies no older than MAX_AGE_DAYS are used as they are, so a re-run downloads nothing; `refresh` reads the
    list again. If the site cannot be read, kept copies of any age are used and the run says so.
    Returns (items, state rows, fetched, how, the local side's part)."""
    kept = None
    if os.path.exists(path) and (not local_path or os.path.exists(local_path)):
        kept = (json.load(open(path, encoding="utf-8")), json.load(open(local_path, encoding="utf-8")) if local_path else None)
    if kept and not refresh and all(_fresh(k["fetched"]) for k in kept if k):
        got, loc = kept
        return got["items"], got["rows"], got["fetched"], f"kept copy of {got['fetched']}", loc
    try:
        items, every, digest = read_grid(url, election, say)
    except SystemExit as e:
        if not kept:
            raise
        got, loc = kept
        say(f"    South Dakota (state races): {e}; using the copy kept on {got['fetched']}")
        return got["items"], got["rows"], got["fetched"], "kept copy", loc
    rows = [r for r in every if r["DistrictType"] in STATE_TYPES and not r["Contest"].startswith("United States ")]
    odd = [r for r in rows if not r["eldate"].startswith(date_prefix) or r["elType"] != election]
    if odd:
        raise SystemExit(f"South Dakota (state races): {len(odd)} rows of the {election} list are not dated {date_prefix}")
    fetched = dt.date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"url": url, "fetched": fetched, "items": items, "columns": list(KEEP), "rows": [{k: r[k] for k in KEEP} for r in rows]},
                  fh, ensure_ascii=False, indent=0)
    loc = None
    if local_path:
        other = [r for r in every if r["DistrictType"] not in STATE_TYPES]
        dated = [r for r in other if r["eldate"].startswith(date_prefix) and r["elType"] == election]
        loc = {"url": url, "fetched": fetched, "items": items, "pages_sha256": digest, "other_election": len(other) - len(dated)}
        loc.update(local_cut(dated))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "w", encoding="utf-8") as fh:
            json.dump(loc, fh, ensure_ascii=False, indent=0)
    return items, rows, fetched, "read afresh", loc


# ---------- the July 28 runoff: the two names only ----------

def runoff_names(path, say=print, refresh=False):
    """The candidates in the Republican runoff for Governor: the names kept earlier when there are any (a finished
    runoff's two names do not change, so a re-run asks nothing); else, or on `refresh`, from the results site while it
    still shows July 28. Returns (names, fetched) or (None, None)."""
    if not refresh and os.path.exists(path):
        got = json.load(open(path, encoding="utf-8"))
        return got["names"], got["fetched"]
    try:
        page = net.get(RUNOFF_URL).decode("utf-8", "replace")
        date = re.search(r'id="hidElectionDate[^"]*" value="([^"]*)"', page)
        if date and date.group(1) == "7/28/2026":
            page = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
            contests = {}
            for block in page.split('class="display-results-box-a"')[1:]:
                title = re.search(r"<h1>(.*?)</h1>", block, re.S)
                title = text(re.sub(r"<span.*?</span>", "", title.group(1), flags=re.S)) if title else ""
                contests[title] = [(text(n), text(p)) for n, p in re.findall(
                    r'class="col display-results-box-d">\s*<h1>(.*?)</h1>\s*<h2[^>]*>(.*?)</h2>', block, re.S)]
            names = [n for n, p in contests.get("Governor", []) if p == "Republican"]
            if len(names) == 2 and len(contests.get("Governor", [])) == 2:
                fetched = dt.date.today().isoformat()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"url": RUNOFF_URL, "fetched": fetched, "election": "2026-07-28 Republican primary runoff, Governor",
                               "names": names}, fh, ensure_ascii=False, indent=1)
                return names, fetched
            say("    South Dakota (state races): the results site's July 28 page does not show a two-candidate Republican runoff for Governor")
    except (HTTPError, URLError, OSError) as e:
        say(f"    South Dakota (state races): the results site could not be read ({e})")
    if os.path.exists(path):
        got = json.load(open(path, encoding="utf-8"))
        return got["names"], got["fetched"]
    return None, None


# ---------- the roster: names, parties, districts and ids only ----------

def roster():
    con = sqlite3.connect(ROSTER_DB)
    seats = defaultdict(list)                                # (chamber, district) -> [person]
    for bid, first, last, full, party, district, chamber in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        seats[(chamber, district)].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                           "party": party, "chamber": chamber, "district": district})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": party, "label": label}
    as_of = con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or ""
    con.close()
    return seats, offices, as_of[:10]


def person_fits(name, p):
    cand = name_parts(name)
    return fits(cand, ([w for w in fold(p["first"]).split()], fold(p["last"]))) or fits(cand, name_parts(p["full"]))


def same_person(a, b):
    """Two ways of writing one candidate's name ('Larry  Rhoden' on the results site, 'Larry Rhoden' on the list)."""
    return fold(a) == fold(b) or fits(name_parts(a), name_parts(b))


def ticket_head(name):
    """'Larry Rhoden & Tony Venhuizen' -> 'Larry Rhoden' (the candidate for Governor is named first)."""
    return re.split(r"\s+(?:&|and)\s+", name, maxsplit=1)[0]


# ---------- county and local races: what was typed from official documents ----------

READ = "2026-09-30"                                         # the day the documents below were read and these tables typed
LOCAL_SRC = "sd-sos-2026-local-candidate-list"
JUNE_SRC = "sd-sos-2026-june-list-local-contests"
COUNTY_SRC = "sd-census-2024-counties"
PLACE_SRC = "sd-census-2020-places"
WDD_GUIDE_SRC = "sd-sos-2026-wdd-guide"
HCP_SRC = "sd-sos-2026-heartland-certification"
SOS_2026 = "https://sdsos.gov/elections-voting/upcoming-elections/general-information/2026%20Election%20Information/"
OFFICES_URL = SOS_2026 + "2026-offices-to-be-filled.aspx"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
PLACES_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st46_sd_place2020.txt"
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")

# the list's contests: contest -> (office_kind, the office as a ballot prints it, the word in the race id)
CTY_OFFICES = {
    "County Auditor": ("county_auditor", "County Auditor", "auditor"),
    "County Treasurer": ("county_treasurer", "County Treasurer", "treasurer"),
    "County Finance Officer": ("county_finance_officer", "County Finance Officer", "finance-officer"),
    "States Attorney": ("county_attorney", "State's Attorney", "states-attorney"),
    "Sheriff": ("sheriff", "Sheriff", "sheriff"),
    "Register of Deeds": ("register_of_deeds", "Register of Deeds", "register-of-deeds"),
    "Coroner": ("coroner", "Coroner", "coroner"),
    "County Commissioner At Large": ("county_commissioner", "County Commissioner", "commissioner"),
}
CITY_OFFICES = {
    "Mayor": ("mayor", "Mayor", "mayor"),
    "City Council Member": ("council", "City Council Member", "council"),
    "City Commissioner": ("council", "City Commissioner", "city-commissioner"),
    "Alderman": ("council", "Alderman", "alderman"),
    "Trustee": ("council", "Trustee", "trustee"),
}
# offices with one holder: a county has one of each, and each director area or subdivision elects one director
ONE_SEAT = {"county_auditor", "county_treasurer", "county_finance_officer", "county_attorney", "sheriff", "register_of_deeds", "coroner",
            "water_board", "utility_board", "mayor"}
REGULAR_2026 = (("sheriff", ("Sheriff",)), ("county auditor or finance officer", ("County Auditor", "County Finance Officer")),
                ("register of deeds", ("Register of Deeds",)))      # SDCL 7-7-1.1(1): elected in 1974 and every fourth year after

COM_RX = re.compile(r"(?P<county>.+?)\s*-\s*(?:District\s+)?(?P<d>\d+(?:-\d+)*)")       # Aurora-1, Deuel - District 1, Lyman - District 3-4-5
WARD_RX = re.compile(r"(?P<city>.+?)\s+Ward\s*-?\s*0*(?P<w>\d+)", re.I)                 # Baltic Ward-1, Platte Ward-01
WDD_PLACE_RX = re.compile(r"(?P<name>.+?)\s*WDD\s*-?\s*0*(?P<a>\d+)", re.I)             # East Dakota WDD 1, South Central WDD-3, Vermillion Basin WDD7
WDD_CONTEST_RX = re.compile(r"(?P<name>.+) Water Development District Director")
HCP_RX = re.compile(r"Subdivision\s+0*(?P<n>\d+)", re.I)

# Water development districts. WDD_UP: the director areas the Secretary of State's 2026 guide lists as up for election
# (the odd-numbered ones; one director an area, four-year terms). WDD_AREAS: for each of them, the counties its
# description names in the rule (ARSD 74:05:05), and the cities the rule names without a county, which are placed by
# the Census Bureau's place codes. Typed by hand from the documents read on READ; their fingerprints are in REF_SHA.
WDD_RULE = {"James River": "74:05:05:16", "Central Plains": "74:05:05:17", "South Central": "74:05:05:18", "West River": "74:05:05:19",
            "East Dakota": "74:05:05:20", "West Dakota": "74:05:05:21", "Vermillion Basin": "74:05:05:21.01"}
WDD_UP = {"James River": (1, 3, 5, 7, 9), "Central Plains": (1, 3, 5, 7), "South Central": (1, 3, 5, 7), "West River": (1, 3, 5),
          "East Dakota": (1, 3, 5, 7, 9), "West Dakota": (1, 3, 5, 7, 9), "Vermillion Basin": (1, 3, 5, 7)}
WDD_AREAS = {
    ("James River", 1): ((), ("Aberdeen",)),
    ("James River", 3): (("Brown", "Marshall"), ()),
    ("James River", 5): ((), ("Huron",)),
    ("James River", 7): (("Hanson", "Davison", "Aurora", "Hutchinson"), ()),
    ("James River", 9): (("Hutchinson", "Yankton"), ()),
    ("Central Plains", 1): ((), ("Pierre",)),
    ("Central Plains", 3): (("Hyde", "Sully", "Faulk"), ()),
    ("Central Plains", 5): (("Faulk", "Potter"), ()),
    ("Central Plains", 7): ((), ("Pierre",)),
    ("South Central", 1): (("Gregory", "Lyman", "Charles Mix"), ()),
    ("South Central", 3): (("Buffalo", "Brule", "Aurora"), ()),
    ("South Central", 5): (("Bon Homme", "Douglas", "Charles Mix"), ()),
    ("South Central", 7): (("Charles Mix", "Douglas"), ()),
    ("West River", 1): (("Haakon", "Pennington"), ()),
    ("West River", 3): (("Mellette", "Jones"), ()),
    ("West River", 5): (("Lyman",), ()),
    ("East Dakota", 1): (("Codington", "Grant"), ()),
    ("East Dakota", 3): (("Deuel", "Hamlin", "Kingsbury", "Brookings"), ()),
    ("East Dakota", 5): ((), ("Sioux Falls",)),
    ("East Dakota", 7): ((), ("Sioux Falls",)),
    ("East Dakota", 9): ((), ("Sioux Falls",)),
    ("West Dakota", 1): (("Pennington",), ()),
    ("West Dakota", 3): (("Pennington",), ()),
    ("West Dakota", 5): (("Pennington",), ()),
    ("West Dakota", 7): (("Pennington",), ()),
    ("West Dakota", 9): (("Pennington",), ()),
    ("Vermillion Basin", 1): (("Clay",), ()),
    ("Vermillion Basin", 3): (("Clay", "Turner"), ()),
    ("Vermillion Basin", 5): (("Turner", "McCook"), ()),
    ("Vermillion Basin", 7): (("Kingsbury", "Lake", "Miner"), ()),
}
# Heartland Consumers Power District: the subdivisions electing a director in 2026 (the Secretary of State's "Offices
# to be Filled in 2026"), with the counties the district's certification of December 17, 2025 names for each
HCP_SUBDIVISIONS = {
    4: (("Lincoln", "Minnehaha", "Union"), "Lincoln County, Split Rock township in Minnehaha County and eight townships in Union County"),
    5: (("Day", "Grant", "Marshall", "Roberts"), "Marshall and Roberts counties and most of Day and Grant counties"),
    6: (("Beadle", "Clark", "Kingsbury", "Lake", "Moody"), "Beadle and Lake counties and most of Clark, Kingsbury and Moody counties"),
}
# conservation districts the list does not name by a county: the counties they lie in, from the Department of
# Agriculture and Natural Resources' histories of the districts
SCD_NAMED = {"Brule-Buffalo": ("Brule", "Buffalo"), "East Pennington": ("Pennington",), "Elk Creek": ("Meade",), "Pennington": ("Pennington",)}

REF_SHA = {      # SHA-256 of each document's bytes as fetched on READ (statutes and rules through the Legislature's own data address)
    "sdcl-12-16-1.1": "0563993e0b873eb4a08a575f093eb9cc5666e55eac7239e9e724ca2f4438a72f",
    "sdcl-7-7-1.1": "180192cb33105b243422f57ac1f539efa3229c3d3057309e1b64cc50d911baf2",
    "sdcl-7-8-1": "f709376ade0dd1c36763b2b72eb96421e37da3f86d79fe994507be991066fe1a",
    "sdcl-9-13-1": "bed26bf6bd324a927ae1077508133f41749f576c84984251e3d02533096993f6",
    "sdcl-9-13-37": "5675cd60e6ca576f313a6c55b3bf22566bef8653db88afacc0ac065074a4bad5",
    "sdcl-9-13-5": "2ecdd411f0b5c7278fd2bcc95d68571c04bcd591b70506ef665a293a6e809e56",
    "sdcl-13-7-10": "77c0d14a7c15f5368420a83a4102c7cf050591011d90c146355adf902dbb136e",
    "sdcl-8-3-1": "19bc11cad475e54206e03319e103e284ee9a614f89b97e9de73fae341bd68ae2",
    "sdcl-8-3-2": "025d75e20e2c63fe82961c2884e3854e5c33c595711e7060c58131f379df1d25",
    "sdcl-38-8-39": "dcaa3a6b006e9a7e1cca0c0f918db97a4ab0f78d1a037f20d3acfe676e2b40d4",
    "sdcl-12-6-4": "46c002847e984ce5a4b85aa151678e833266bb523ecf8797cdfa7f0c714e48a0",
    "sdcl-7-7-1.2": "cd7cf2a101fd66df5aa2083500577d014e8bf6c58b6b381b9d5237ee7d8ad081",
    "sdcl-7-7-1.8": "27730b2edcac1b5e994007d05ffb14b557aa99d077e99aca8bd76002b62ce837",
    "sdcl-12-20-21.2": "db3f74f383acf2b3936ca7964a2c038e26978f6d03201de1c09c2e2b9241b461",
    "sdcl-46A-3B-5": "e001c2e8375d725d4670d4404e5be0f72476b3015622cd676a0a12612110a6f4",
    "arsd-74:05:05:16": "8c09277237f9c55e2f9615731e83da10603c8b91ddd6976e05c7686574b8e68f",
    "arsd-74:05:05:17": "0c1e9c753147a8e2ff093a3ed047bc8810babc7d862985ab69fe7fe30c125e7f",
    "arsd-74:05:05:18": "2c2f301cff18fe591e413b1000b9c72d81f53e38996cc244927b729aac5ad7e6",
    "arsd-74:05:05:19": "2c9e0ee69d4c3cf64156da5a3c032f25f4040d216d6505ea37065ebe4ee35d20",
    "arsd-74:05:05:20": "f99dd7c778bff060ff95981d503f40b29b3228f8b959e0a2396eb1a92f2e6f7c",
    "arsd-74:05:05:21": "8efa6c732a864862003af98003f2d656b439c28f9375d512c5152dbdda7dc54b",
    "arsd-74:05:05:21.01": "a5cafa2806429592470c71e5dadcdc770b679c007e45117d0fdcfa8659e12d31",
    "sos_offices": "094ec0959bf9e993212b7a88d117418d9b98acb92a340c7ddd9ea715a37697a4",
    "sos_wdd_guide": "6d572b68925e46331421dac9e33e890063c9e2d555a03ea9ac2db0f188e0ee52",
    "sos_heartland": "12f853d185c38b6359157f43e5d5869d5b3a14ddc6ec2394b3ce8c673419efe2",
    "danr_elk_creek": "eef95bdb1f60698a969e17b01bb9de9efead7c2767836aa4fb55c12fac78c188",
    "danr_east_pennington": "a3fb14c3669bda68bf9cfc6a796c35d1c4fc63ad22062d4fd38647b0bd58fa95",
    "danr_pennington": "10ff2ecb194aa91d7af51980b13eb944466f9d4f0005136925d18300fae3ce62",
    "danr_brule_buffalo": "3a2ff56d3d4d16883d7d0bbcb02654aeea4b966c1413e159f96462ad699393a5",
}
STATUTES = (      # (section, what it is about, what it was read for)
    ("12-16-1.1", "a candidate with no opponent is elected without being printed on the ballot", "Read for the notes on contests with one candidate."),
    ("46A-3B-5", "a lone candidate for a water development district director area is issued a certificate of election",
     "Read for the notes on director areas with one candidate."),
    ("12-20-21.2", "write-in votes are not counted", "Read for the coverage note: the list has no write-in candidates."),
    ("7-7-1.1", "which county officers are elected in which years", "Read for the calendar note and the counties whose list lacks a regular office."),
    ("7-7-1.2", "combining county offices", "Read for the counties whose list lacks a regular office."),
    ("7-7-1.8", "combining a county office with other counties", "Read for the counties whose list lacks a regular office."),
    ("7-8-1", "county commissioners: their number, terms and which districts are elected when", "Read for the calendar note."),
    ("12-6-4", "where nominating petitions are filed", "Read for the counties whose list lacks a regular office."),
    ("9-13-1", "a city's or town's election date: June or November", "Read for the calendar note."),
    ("9-13-37", "city and town elections held with the June primary or the November election", "Read for the note on cities not on the list."),
    ("9-13-5", "no city or town election when no seat is contested", "Read for the note on cities not on the list."),
    ("13-7-10", "a school district's election date: June or November", "Read for the calendar note."),
    ("8-3-1", "the annual township meeting on the first Tuesday of March", "Read for the calendar note."),
    ("8-3-2", "township officers are chosen at the annual meeting", "Read for the calendar note."),
    ("38-8-39", "conservation district supervisors", "Read for the calendar note."),
)
RULE_DATE = {"74:05:05:16": "2022-11-21", "74:05:05:17": "2022-11-21", "74:05:05:18": "2022-11-21", "74:05:05:19": "2022-11-21",
             "74:05:05:20": "2024-12-04", "74:05:05:21": "2022-11-21", "74:05:05:21.01": "2024-12-04"}      # each rule's last amendment
DANR = "https://danr.sd.gov/Conservation/docs/HistoryConservationDistricts/"
DISTRICT_HISTORIES = (      # (key, the district, its number, file, the counties read from it)
    ("danr_brule_buffalo", "Brule-Buffalo", "03", "BruleBuffalo_03.pdf", "Brule and Buffalo"),
    ("danr_pennington", "Pennington", "10", "Pennington_10.pdf", "Pennington (west of the Cheyenne River)"),
    ("danr_elk_creek", "Elk Creek", "14", "ElkCreek_14.pdf", "Meade (all but its northeast corner)"),
    ("danr_east_pennington", "East Pennington", "39", "EastPennington_39.pdf", "Pennington (east of the Cheyenne River)"),
)


def reference_sources():
    """sl_sources rows for the documents the tables above were typed from, as read on READ."""
    leg = "South Dakota Legislature"
    out = [
        (WDD_GUIDE_SRC, STATE, "official guide", "South Dakota Secretary of State", "2026 Water Development District Election Guide",
         "https://sdsos.gov/elections-voting/assets/2026%20Documents/2026-WDD-DirectorGuide.pdf", "2025-10-28", READ, REF_SHA["sos_wdd_guide"],
         sum(len(v) for v in WDD_UP.values()),
         "Which director areas are up for election in 2026 (the odd-numbered ones, one director an area, four-year terms), typed by hand."),
        (HCP_SRC, STATE, "official certification (a scan)", "Heartland Consumers Power District, filed with the South Dakota Secretary of State",
         "Certification of the district's counties, precincts and directors for the 2026 election (SDCL 49-36-3)",
         SOS_2026 + "2026%20Election%20Assets/Election%20Information/HeartlandConsumerPowerCertificationfor2026001.pdf", "2025-12-17", READ,
         REF_SHA["sos_heartland"], len(HCP_SUBDIVISIONS),
         "The counties of Subdivisions 4, 5 and 6, read from the scan by hand. The letter's own contact lines and the directors' names are not used."),
        ("sd-sos-2026-offices-to-be-filled", STATE, "official page", "South Dakota Secretary of State", "Offices to be Filled in 2026",
         OFFICES_URL, "", READ, REF_SHA["sos_offices"], 0,
         "Which county and district offices are filled in 2026 and for how long, and which Heartland subdivisions elect a director. The "
         "fingerprint is of the page as it was fetched that day."),
    ]
    for name, rule in WDD_RULE.items():
        out.append((f"sd-arsd-{rule.replace(':', '-').replace('.', '-')}", STATE, "administrative rule", leg,
                    f"ARSD {rule}, {name} water development district director areas", f"https://sdlegislature.gov/Rules/Administrative/{rule}",
                    RULE_DATE[rule], READ, REF_SHA[f"arsd-{rule}"], len(WDD_UP[name]),
                    "The counties each odd-numbered director area's description names, typed by hand; the date is the rule's last amendment. "
                    "Read through the Legislature's own data address for the rule, and the fingerprint is of that page as fetched."))
    for key, name, number, file_name, where in DISTRICT_HISTORIES:
        out.append((f"sd-danr-conservation-district-{number}", STATE, "official history",
                    "South Dakota Department of Agriculture and Natural Resources", f"History of Conservation Districts: {name} (No. {number})",
                    DANR + file_name, "", READ, REF_SHA[key], 1, f"The counties the district lies in: {where}. Read by hand."))
    for cite, about, why in STATUTES:
        out.append((f"sd-sdcl-{cite.replace('.', '-').lower()}", STATE, "statute", leg, f"SDCL {cite}: {about}",
                    f"https://sdlegislature.gov/Statutes/{cite}", "", READ, REF_SHA[f"sdcl-{cite}"], 0,
                    why + " The fingerprint is of the section's page as fetched that day."))
    return out


# ---------- county and local races: places ----------

def slug(words):
    return re.sub(r"[^a-z0-9]+", "-", (words or "").lower()).strip("-")


def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def day_of(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


def census_counties(say=print):
    """South Dakota's counties from the Census county file the kit keeps: {name: (5-digit code, 'X County')}."""
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, 3650, say=say)
    import shapefile                                        # pyshp, one of the kit's five packages
    z = zipfile.ZipFile(COUNTY_ZIP)
    tables = [n for n in z.namelist() if n.lower().endswith(".dbf")]
    if len(tables) != 1:
        raise SystemExit("South Dakota (local races): the Census county file does not hold exactly one table")
    out = {}
    for rec in shapefile.Reader(dbf=io.BytesIO(z.read(tables[0]))).iterRecords():
        d = rec.as_dict()
        if str(d.get("STATEFP")) == FIPS:
            out[str(d["NAME"])] = (str(d["GEOID"]), str(d["NAMELSAD"]))
    if len(out) != 66 or any(not re.fullmatch(FIPS + r"\d{3}", code) for code, _full in out.values()):
        raise SystemExit(f"South Dakota (local races): the Census county file gives {len(out)} South Dakota counties, not 66")
    return out


def census_places(path, say=print):
    """Incorporated places in the Census Bureau's 2020 place codes for South Dakota (a public code list: names, codes
    and counties, no person in it; kept whole). Returns ({the name without its kind word: [(code, the name as the
    Bureau writes it, [county names])]}, rows in the file)."""
    net.download(PLACES_URL, path, 365, say=say)
    name = os.path.basename(path)
    lines = open(path, encoding="utf-8").read().splitlines()
    head = lines[0].split("|") if lines else []
    if any(k not in head for k in ("STATEFP", "PLACEFP", "PLACENAME", "TYPE", "COUNTIES")):
        raise SystemExit(f"South Dakota (local races): {name}, line 1: the heading is not the Census place codes' heading")
    out, n = defaultdict(list), 0
    for i, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        cells = line.split("|")
        if len(cells) != len(head):
            raise SystemExit(f"South Dakota (local races): {name}, line {i}: the cells do not line up with the heading")
        d = dict(zip(head, cells))
        n += 1
        if d["STATEFP"] == FIPS and d["TYPE"] == "INCORPORATED PLACE" and re.fullmatch(r"\d{5}", d["PLACEFP"]):
            bare = re.sub(r"\s+(city|town|village)$", "", d["PLACENAME"])
            out[bare].append((d["PLACEFP"], d["PLACENAME"], [c.strip()[:-len(" County")] for c in d["COUNTIES"].split("~~~") if c.strip().endswith(" County")]))
    return out, n


def wdd_contest(name, area, counties, cities):
    """A water development district's director area, from the table typed from the rule; or why it cannot be placed."""
    named, towns = WDD_AREAS[(name, area)]
    cnames, by_town = list(named), {}
    for town in towns:
        got = cities.get(town, [])
        if len(got) != 1 or not got[0][2]:
            return "the rule names a city for this director area that is not exactly one place in the Census Bureau's place codes"
        by_town[town] = got[0][2]
        cnames += [c for c in got[0][2] if c not in cnames]
    if any(c not in counties for c in cnames):
        return "a county named for this director area is not in the Census county file"
    jur = f"{name} Water Development District"
    return dict(level="other", kind="water_board", office="Water Development District Director", partisan=0, jur=jur, jur_id=f"{STATE}-X-{slug(jur)}",
                counties=cnames, district=f"Director Area {area}", seat=None, word="director", tail=f"area{area}", seq_in_id=False,
                place=("special", jur), wdd=(name, area), towns=by_town)


def place_contest(r, counties, cities):
    """Where one local row's contest belongs: a dict (level, office kind, office, jurisdiction, counties, district and
    seat, the words for its race id), or a few words saying why the loader cannot place it. Nothing is guessed: an
    office, a kind of district or a place the tables above do not know is left out and listed in sl_gaps."""
    t, contest, where = r["DistrictType"], r["Contest"], r["District/County"]
    if t == "CTY":
        if contest not in CTY_OFFICES:
            return "it is an office the loader does not know yet"
        if where not in counties:
            return "the list files it under a county the Census county file does not name"
        kind, office, word = CTY_OFFICES[contest]
        seat = "At Large" if contest.endswith(" At Large") else None
        return dict(level="county", kind=kind, office=office, partisan=1, jur=counties[where][1], jur_id=counties[where][0], counties=[where],
                    district=None, seat=seat, word=word, tail="atlarge" if seat else "", seq_in_id=True, place=None)
    if t == "COM":
        m = COM_RX.fullmatch(where)
        if contest != "County Commissioner" or not m:
            return "it is an office or a commissioner district the loader cannot read"
        county, d = m.group("county").strip(), m.group("d")
        if county not in counties:
            return "the list files it under a county the Census county file does not name"
        d = d if "-" in d else str(int(d))
        return dict(level="county", kind="county_commissioner", office="County Commissioner", partisan=1, jur=counties[county][1],
                    jur_id=counties[county][0], counties=[county], district=f"District {d}" if "-" in d else d, seat=None, word="commissioner",
                    tail="d" + d, seq_in_id=True, place=None)
    if t in ("MUN", "WAR"):
        if contest not in CITY_OFFICES:
            return "it is an office the loader does not know yet"
        city, district = where, None
        if t == "WAR":
            m = WARD_RX.fullmatch(where)
            if not m:
                return "it is filed under a ward the loader cannot read"
            city, district = m.group("city").strip(), f"Ward {int(m.group('w'))}"
        got = cities.get(city, [])
        if len(got) != 1 or not got[0][2] or any(c not in counties for c in got[0][2]):
            return "the list's city is not exactly one incorporated place in the Census Bureau's place codes"
        code, name, cnames = got[0]
        kind, office, word = CITY_OFFICES[contest]
        return dict(level="city", kind=kind, office=office, partisan=0, jur=name, jur_id=f"{STATE}-M-{code}", counties=list(cnames), district=district,
                    seat=None, word=word, tail=slug(district).replace("-", ""), seq_in_id=True, place=("mcd", name))
    if t == "SCD":
        if contest != "Conservation District Supervisor":
            return "it is an office the loader does not know yet"
        if where.endswith(" County") and where[:-len(" County")] in counties:
            cnames = [where[:-len(" County")]]
        elif where in SCD_NAMED:
            cnames = list(SCD_NAMED[where])
        else:
            return "it is a conservation district whose counties the loader's table does not have"
        if contact_like(where, True):
            return "the words the list files it under cannot be shown"
        jur = f"{where} Conservation District"
        key = (counties[cnames[0]][0][2:] + "-" if len(cnames) == 1 else "") + slug(jur)
        return dict(level="soil_water", kind="soil_water", office="Conservation District Supervisor", partisan=0, jur=jur, jur_id=f"{STATE}-X-{key}",
                    counties=cnames, district=None, seat=None, word="supervisor", tail="", seq_in_id=True, place=("special", jur))
    if t == "WDD":
        c, w = WDD_CONTEST_RX.fullmatch(contest), WDD_PLACE_RX.fullmatch(where)
        if not c or not w or fold(c.group("name")) != fold(w.group("name")):
            return "it is a water development district contest the loader cannot read"
        name, area = c.group("name"), int(w.group("a"))
        if (name, area) not in WDD_AREAS:
            return "it is a director area whose counties the loader's table does not have"
        return wdd_contest(name, area, counties, cities)
    if t == "HCP":
        m = HCP_RX.fullmatch(where)
        if contest != "Heartland Consumers Power District Director" or not m:
            return "it is a power district contest the loader cannot read"
        n = int(m.group("n"))
        if n not in HCP_SUBDIVISIONS or any(c not in counties for c in HCP_SUBDIVISIONS[n][0]):
            return "it is a subdivision whose counties the loader's table does not have"
        jur = "Heartland Consumers Power District"
        return dict(level="other", kind="utility_board", office="Consumers Power District Director", partisan=0, jur=jur,
                    jur_id=f"{STATE}-X-{slug(jur)}", counties=list(HCP_SUBDIVISIONS[n][0]), district=f"Subdivision {n}", seat=None, word="director",
                    tail=f"sub{n}", seq_in_id=False, place=("special", jur), hcp=n)
    return "it is a kind of district the loader does not know yet"


def base_id(info, seq):
    key = info["jur_id"] if info["level"] == "county" else info["jur_id"][len(STATE) + 1:]
    return f"2026-{STATE}-{key}-{info['word']}" + (f"-{seq}" if info["seq_in_id"] else "") + (f"-{info['tail']}" if info["tail"] else "")


# ---------- county and local races: the build ----------

ONE = "One candidate is on the list. A candidate with no opponent is elected automatically and is not printed on the ballot (SDCL 12-16-1.1)."
ONE_WDD = ("One candidate is on the list. When only one candidate files for a director area no election is held and the candidate is issued a "
           "certificate of election (SDCL 46A-3B-5).")
ONE_CITY = "One candidate is on the list."
NO_ORDER_ONE_SEAT = "The list gives no ballot order for these candidates."
NO_ORDER = ("The list gives no ballot order for these candidates and does not say how many are elected. When there are no more candidates than "
            "seats, they are elected automatically and are not printed on the ballot (SDCL 12-16-1.1).")
NO_ORDER_CITY = "The list gives no ballot order for these candidates and does not say how many are elected."
HOW_MANY = "The list does not say how many are elected."
OFF_YEAR_OFFICE = ("State law has counties elect this office in presidential years (SDCL 7-7-1.1); the list does not say why it is being filled "
                   "here in 2026.")
OFF_YEAR_DISTRICT = ("State law has even-numbered commissioner districts elected in presidential years (SDCL 7-8-1); the list does not say why "
                     "this one is being filled in 2026.")
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def local_side(g_local, p_local, how, cache, say=print):
    """The November list's county, city and district rows -> what goes into sl_races, sl_candidates, sl_places, sl_gaps,
    sl_notes and sl_sources for them, and the lines to report. Every text written is checked for anything that looks
    like contact details; a candidate's name that does is left off and counted, by race, never shown."""
    counties = census_counties(say)
    place_path = os.path.join(cache, "local", "st46_sd_place2020.txt")
    cities, place_rows_n = census_places(place_path, say)
    code = lambda names: sorted(counties[n][0] for n in names)
    rows = g_local["rows"]
    checks, unplaced = [], defaultdict(int)

    # ---- contests: one office, one place, one of the list's office numbers
    found = {}                                                # (base id, office number) -> the contest
    for r in rows:
        info = place_contest(r, counties, cities)
        if isinstance(info, str):
            unplaced[(r["DistrictType"], r["Contest"], r["District/County"], info)] += 1
            continue
        key = (base_id(info, r["OfficeSeqNum"]), r["OfficeSeqNum"])
        c = found.setdefault(key, dict(info, seq=r["OfficeSeqNum"], on=[], withdrawn=0, twice=0, held=0))
        name = STATUS_MARK.sub("", r["Name"]).strip()
        if r["Status"] != "Active" or r["WithdrawnDate"]:
            c["withdrawn"] += 1
        elif not name or contact_like(name, True):
            c["held"] += 1                                    # nothing that looks like contact details is ever stored
        elif any(name == x["name"] for x in c["on"]):
            c["twice"] += 1
        else:
            c["on"].append({"name": name, "code": r["Party"], "order": int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None})
    for name, areas in WDD_UP.items():                        # director areas the guide lists as up, with no row on the list
        for area in areas:
            info = wdd_contest(name, area, counties, cities)
            if isinstance(info, str):
                checks.append(f"{name} water development district, area {area}: {info}")
            elif not any(k[0] == base_id(info, "") for k in found):
                found[(base_id(info, ""), "")] = dict(info, seq="", on=[], withdrawn=0, twice=0, held=0, from_guide=True)
    listed_wdd = {c["wdd"] for c in found.values() if c.get("wdd") and not c.get("from_guide")}
    not_up = sorted(f"{n} {a}" for n, a in listed_wdd if a not in WDD_UP.get(n, ()))
    if not_up:
        checks.append(f"director areas on the list that the Secretary of State's guide does not list as up: {', '.join(not_up)}")

    by_base = defaultdict(list)
    for (base, seq), c in found.items():
        by_base[base].append(seq)
    number = lambda seq: int(seq) if str(seq).isdigit() else 0
    contests = {}
    for (base, seq), c in sorted(found.items(), key=lambda kv: (kv[0][0], number(kv[0][1]))):
        rid = base if len(by_base[base]) == 1 else f"{base}-{seq}"      # two office numbers for one director area: each keeps its number
        if rid in contests or not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise SystemExit(f"South Dakota (local races): a race id is not unique or not plain: {rid}")
        contests[rid] = dict(c, rid=rid)

    # ---- the same title more than once in one place: kept apart, numbered in the list's order
    same = defaultdict(list)
    for c in contests.values():
        same[(c["jur_id"], c["office"], c["district"], c["seat"])].append(c)
    for group in same.values():
        if len(group) > 1:
            group.sort(key=lambda c: number(c["seq"]))
            for i, c in enumerate(group, 1):
                label = f"Contest {i} of {len(group)}"
                c["seat"] = f"{c['seat']}, {label[0].lower()}{label[1:]}" if c["seat"] else label
                c["one_of"] = len(group)

    races, cands = [], []
    held = sum(c["held"] for c in contests.values())
    twice = sum(c["twice"] for c in contests.values())
    withdrawn = sum(c["withdrawn"] for c in contests.values())
    for rid, c in contests.items():
        on, city = c["on"], c["level"] == "city"
        orders = [x["order"] for x in on if x["order"] is not None]
        if len(set(orders)) != len(orders):
            checks.append(f"{rid}: two candidates share a ballot order on the list; no order written")
            for x in on:
                x["order"] = None
            orders = []
        note = []
        if c.get("one_of"):
            note.append(f"This is one of {NUMBER_WORDS.get(c['one_of'], c['one_of'])} separate contests for {c['office']} here on the Secretary of "
                        "State's list, which does not say how they differ (for instance a full term and the rest of an unexpired one); the "
                        "county auditor can say which is which.")
        if c.get("wdd"):
            name, area = c["wdd"]
            note.append(f"Only voters in Director Area {area} of the district vote in this contest (the area is set out in ARSD {WDD_RULE[name]}).")
            for town, where in c["towns"].items():
                note.append(f"The rule names {town} precincts without a county; the Census Bureau places {town} in "
                            f"{and_list(sorted(where))} {'County' if len(where) == 1 else 'counties'}.")
        if c.get("hcp"):
            note.append(f"Only voters in Subdivision {c['hcp']} of the district vote in this contest: {HCP_SUBDIVISIONS[c['hcp']][1]}. Cities and "
                        "towns are outside the district unless they have joined it (the district's certification to the Secretary of State, "
                        "December 2025).")
        if c["kind"] in ("county_treasurer", "county_attorney", "coroner"):
            note.append(OFF_YEAR_OFFICE)                      # SDCL 7-7-1.1(2): elected in 1976 and every fourth year after
        if c["kind"] == "county_commissioner" and (c["district"] or "").isdigit() and int(c["district"]) % 2 == 0:
            note.append(OFF_YEAR_DISTRICT)
        if not on:
            if c.get("from_guide"):
                note.append("No candidate for this director area is on the November list; the Secretary of State's 2026 guide lists the area "
                            "as up for election.")
            else:
                note.append("Every candidate the list shows for this contest has withdrawn." if c["withdrawn"] and not (c["held"] or c["twice"])
                            else "No candidate for this contest can be shown from the list.")
        elif len(on) == 1:
            note.append(ONE_CITY if city else ONE_WDD if c.get("wdd") else ONE)
        elif not orders:
            note.append(NO_ORDER_ONE_SEAT if c["kind"] in ONE_SEAT else NO_ORDER_CITY if city else NO_ORDER)
        elif c["kind"] not in ONE_SEAT and (c["level"] in ("city", "soil_water") or c["seat"] or not (c["district"] or "").isdigit()):
            note.append(HOW_MANY)                             # at-large and combined commissioner districts, councils, supervisors
        races.append((rid, STATE, c["level"], c["kind"], c["office"], c["jur"], c["jur_id"], json.dumps(code(c["counties"])), c["district"], c["seat"],
                      0, c["partisan"], None, None, None, GENERAL, " ".join(note) or None))
        for x in on:
            if c["partisan"]:
                party = PARTY.get(x["code"], x["code"])
                pcode = party_code(party)
                if x["code"] not in PARTY:
                    checks.append(f"{rid}: a party office with the party code {x['code']!r} on the list")
            else:
                party, pcode = "Nonpartisan office", "N"
                if x["code"] != "NON":
                    checks.append(f"{rid}: a nonpartisan office with the party code {x['code']!r} on the list")
            cands.append((rid, "general", GENERAL, x["name"], party, pcode, x["order"], 0, 0, None, None, None, None, LOCAL_SRC, None))

    # ---- places: every county, and each city and district a contest uses
    places = {("county", c): (full, [c], COUNTY_SRC) for _n, (c, full) in counties.items()}
    for c in contests.values():
        if c["place"]:
            kind, name = c["place"]
            src = PLACE_SRC if kind == "mcd" else WDD_GUIDE_SRC if c.get("from_guide") else LOCAL_SRC
            got = places.setdefault((kind, c["jur_id"]), (name, [], src))
            if got[0] != name:
                raise SystemExit(f"South Dakota (local races): two names for one place id: {c['jur_id']}")
            if got[2] == WDD_GUIDE_SRC and src == LOCAL_SRC:      # a district with rows on the list is named from the list
                got = places[(kind, c["jur_id"])] = (name, got[1], src)
            got[1][:] = sorted(set(got[1]) | set(code(c["counties"])))
    place_rows = [(kind, pid, name, json.dumps(cids), src) for (kind, pid), (name, cids, src) in sorted(places.items())]

    # ---- gaps: what the list does not give, never guessed and never dropped silently
    gaps = []
    for (t, contest, where, why), n in sorted(unplaced.items()):
        shown = [w if not contact_like(w, True) else "(not shown)" for w in (contest, where)]
        gaps.append((STATE, "race", slug(f"{t}-{contest}-{where}")[:90] or t.lower(), shown[1], shown[0],
                     f"The Secretary of State's November list has {n} candidate row{'s' if n != 1 else ''} for this contest, but {why}; "
                     "it is left out here rather than guessed at.", GENERAL_URL))
    has = defaultdict(set)
    for r in rows:
        if r["DistrictType"] == "CTY" and r["District/County"] in counties:
            has[r["District/County"]].add(r["Contest"])
    for name, (fips, full) in sorted(counties.items(), key=lambda kv: kv[1][0]):
        for what, titles in REGULAR_2026:
            if not has[name] & set(titles):
                gaps.append((STATE, "county", fips, full, what,
                             "The Secretary of State's November list has no row for this office in this county and does not say why (state law has "
                             "organized counties elect it in 2026, SDCL 7-7-1.1, unless it is combined with another office or with another "
                             "county's, SDCL 7-7-1.2 and 7-7-1.8); candidates for county office file with the county auditor (SDCL 12-6-4), who is "
                             "the one to ask.", GENERAL_URL))
    n_cities = len({c["jur_id"] for c in contests.values() if c["level"] == "city"})
    cities_w = NUMBER_WORDS.get(n_cities, str(n_cities))
    gaps.append((STATE, "state", STATE, NAME, "city and town elections not on the state list",
                 "Each city or town picks the June or the November date for its election (SDCL 9-13-1) and certifies its own candidates to its "
                 f"county auditor (SDCL 9-13-37); the Secretary of State's November list carries {cities_w} of them, a city with no more "
                 "candidates than openings and no question to vote on holds no election (SDCL 9-13-5), and no statewide list says which others, "
                 "if any, vote on November 3.", GENERAL_URL))
    gaps.append((STATE, "state", STATE, NAME, "school board races",
                 "Each school board picks the June or the November date for its election (SDCL 13-7-10); no school district is on the Secretary "
                 "of State's November list, and no statewide list says whether any district votes on November 3 on a ballot of its own.",
                 GENERAL_URL))

    # ---- notes: the calendar, and what this list covers
    level_n = Counter(c["level"] for c in contests.values())
    june = p_local.get("rows_by_type", {})                    # the June list's rows by kind of district: one row a candidate
    june_city = june.get("MUN", 0) + june.get("WAR", 0)
    june_school = june.get("SCH", 0) + june.get("SBR", 0)
    city_cands = sum(len(c["on"]) for c in contests.values() if c["level"] == "city")
    wdd_listed = sum(1 for c in contests.values() if c.get("wdd") and c["on"])
    wdd_empty = sum(1 for c in contests.values() if c.get("from_guide"))
    hcp_n = sum(1 for c in contests.values() if c.get("hcp"))
    notes = [
        (STATE, "local_calendar",
         "On November 3, 2026 South Dakota's counties elect commissioners from odd-numbered and at-large districts, auditors, sheriffs and "
         "registers of deeds, and voters also choose conservation district supervisors, water development district directors from odd-numbered "
         "areas and three Heartland Consumers Power District directors. Each city and each school board picks the June primary date or the "
         f"November date for its own election: this year the Secretary of State's June 2 list named {june_city} municipal and {june_school} "
         f"school board candidates, and its November list names {city_cands} city and town candidates in {cities_w} places and no school "
         "board candidate. Townships choose their officers at the annual meeting on the first Tuesday of March, and county "
         "treasurers, state's attorneys and coroners are regularly elected in presidential years.",
         "SDCL 7-7-1.1, 7-8-1, 8-3-1, 8-3-2, 9-13-1, 13-7-10 and 38-8-39; South Dakota Secretary of State, Offices to be Filled in 2026, and "
         "its 2026 primary and general election candidate lists", OFFICES_URL),
        (STATE, "local_coverage",
         f"Loaded from the Secretary of State's 2026 General Election Candidate List: {level_n['county']} county contests in all 66 counties, "
         f"{level_n['city']} city and town contests in {cities_w} places, {level_n['soil_water']} conservation district contests, {wdd_listed} "
         f"water development district director areas ({wdd_empty} more are up with no candidate on the list) and {hcp_n} Heartland Consumers "
         f"Power District subdivisions, with {len(cands)} candidates; {withdrawn} who withdrew are left off. The list does not say how many are "
         "elected in a contest or which contests fill an unexpired term, and candidates for county office file with the county auditor, so an "
         "office missing from the list is no proof that no one is running; a candidate with no opponent is elected without being printed on "
         "the ballot (SDCL 12-16-1.1), and write-in votes are not counted (SDCL 12-20-21.2). Not loaded: ballot questions, local primaries, "
         "school boards, and any city or town that votes in November without being on the state list.",
         "South Dakota Secretary of State, 2026 General Election Candidate List", GENERAL_URL),
    ]

    # ---- sources
    sources = [
        (LOCAL_SRC, STATE, "official candidate list", "South Dakota Secretary of State",
         "2026 General Election Candidate List (county, city and district offices)", GENERAL_URL, "", g_local["fetched"], g_local["pages_sha256"],
         len(rows),
         f"Every page of the grid read ({g_local['items']} rows, {how}); the {len(rows)} rows that are not state offices kept, and only Contest, "
         "Name, Party, District/County, Ballot Order, Status, WithdrawnDate, OfficeSeqNum, DistrictType, elType and eldate; the grid's "
         f"mailing-address columns are never read. Withdrawn, left off: {withdrawn}. A contest is one office, one place and one of the list's "
         "office numbers. The fingerprint is of the pages as fetched, in order; the kept columns are in the cache folder's "
         f"local/sd_2026_general_local.json (SHA-256 {sha_of(os.path.join(cache, 'local', 'sd_2026_general_local.json'))[:16]})."),
        (JUNE_SRC, STATE, "official candidate list (contests only)", "South Dakota Secretary of State",
         "2026 Primary Election Candidate List, June 2, 2026: which local contests it carried", PRIMARY_URL, "", p_local["fetched"],
         p_local["pages_sha256"], sum(p_local.get("rows_by_type", {}).values()),
         f"Every page of the grid read ({p_local['items']} rows). For the rows that are not state offices only the kind of district, the contest "
         "and the place are kept, with no candidate at all; they say which cities and school boards voted in June. The fingerprint is of the "
         "pages as fetched, in order."),
        (COUNTY_SRC, STATE, "official boundaries (names and codes)", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 1:500,000 (2024)", COUNTY_URL, "", day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(counties),
         "County names and codes for South Dakota's 66 counties, from the file's table."),
        (PLACE_SRC, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, South Dakota (st46_sd_place2020.txt)", PLACES_URL, "",
         day_of(place_path), sha_of(place_path), place_rows_n,
         "Names, codes and counties of incorporated places: the cities and towns on the candidate list, and the cities a director-area rule "
         "names without a county."),
    ] + reference_sources()

    # ---- the last check on every text written: nothing that looks like contact details
    for r in races:
        for col, v in zip(("office", "jurisdiction", "district", "seat", "note"), (r[4], r[5], r[8], r[9], r[16])):
            if v and contact_like(v, True):
                raise SystemExit(f"South Dakota (local races): the {col} of {r[0]} looks like contact details; stopped")
    for kind, pid, name, _c, _s in place_rows:
        if contact_like(name, True):
            raise SystemExit(f"South Dakota (local races): the name of place {kind} {pid} looks like contact details; stopped")

    # ---- the count: every row of the list is a candidate placed, a withdrawal, or accounted for by name
    placed = len(cands)
    left = sum(unplaced.values())
    if placed + withdrawn + twice + held + left != len(rows):
        raise SystemExit(f"South Dakota (local races): {len(rows)} rows on the list, but {placed} placed, {withdrawn} withdrawn, {twice} repeated, "
                         f"{held} held back and {left} not placed")
    ids = Counter((x[0], x[3]) for x in cands)
    if any(v > 1 for v in ids.values()):
        raise SystemExit("South Dakota (local races): a candidate is in one race twice")
    reached = {f for r in races for f in json.loads(r[7])}
    kinds = Counter(r[3] for r in races)
    report = [
        f"    South Dakota (local races): {len(races)} contests (" + ", ".join(f"{lv} {level_n[lv]}" for lv in LOCAL_LEVELS if level_n[lv]) + f"); "
        f"{placed} candidates placed, each in exactly one contest, of {len(rows)} rows on the list ({withdrawn} withdrawn left off"
        + (f", {twice} repeated" if twice else "") + (f", {held} held back by the privacy check" if held else "")
        + (f", {left} not placed: see the gaps" if left else "") + f"); {len(reached)} of 66 counties have a contest; "
        f"{sum(1 for c in contests.values() if len(c['on']) == 1)} contests have one candidate, {sum(1 for c in contests.values() if not c['on'])} none; "
        f"{sum(1 for c in contests.values() if c.get('one_of'))} share a title with another contest in the same place; "
        f"{len(place_rows)} places, {len(gaps)} gaps ({how})",
        "    South Dakota (local races): office kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()),
    ]
    if g_local.get("other_election"):
        checks.append(f"{g_local['other_election']} rows of the November list are not dated November 3 and were not read")
    report += [f"    CHECK South Dakota (local races): {c}" for c in checks]
    return {"races": races, "cands": cands, "places": place_rows, "gaps": gaps, "notes": notes, "sources": sources, "report": report}


# ---------- the load ----------

def race_of(contest, district_text):
    """(race_id, info) for a state contest on the lists; a SystemExit for a contest the loader does not know."""
    if contest in STATEWIDE:
        key, kind, office, roster_office = STATEWIDE[contest]
        return f"2026-{STATE}-{key}", {"level": "statewide", "office_kind": kind, "office": office, "district": None,
                                       "chamber": None, "roster": roster_office}
    if contest in LEGISLATURE:
        m = re.fullmatch(r"District 0*(\d+[AB]?)", district_text)
        if not m:
            raise SystemExit(f"South Dakota (state races): a district the loader cannot read: {district_text!r}")
        key, kind, office, chamber = LEGISLATURE[contest]
        d = m.group(1)
        return f"2026-{STATE}-{key}{d}", {"level": "legislature", "office_kind": kind, "office": office, "district": d,
                                          "chamber": chamber, "roster": None}
    raise SystemExit(f"South Dakota (state races): an office the loader does not know: {contest!r}")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def after_primary(date_text):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_text or "")
    return bool(m) and dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))) > dt.date(2026, 6, 2)


def load(db_path, say=print, cache=CACHE, refresh=False):
    seats, offices, as_of = roster()
    checks = []
    g_path = os.path.join(cache, "sd_2026_general_state.json")
    p_path = os.path.join(cache, "sd_2026_primary_state.json")
    r_path = os.path.join(cache, "sd_2026_governor_runoff_names.json")
    g_items, g_rows, g_fetched, g_how, g_local = cached_grid(GENERAL_URL, "General", g_path, "11/3/2026", say,
                                                             os.path.join(cache, "local", "sd_2026_general_local.json"), general_cut, refresh)
    p_items, p_rows, p_fetched, p_how, p_local = cached_grid(PRIMARY_URL, "Primary", p_path, "6/2/2026", say,
                                                             os.path.join(cache, "local", "sd_2026_primary_local_tally.json"), primary_cut, refresh)
    ro_names, ro_fetched = runoff_names(r_path, say, refresh)
    local = local_side(g_local, p_local, g_how, cache, say)      # stops here, before anything is written, if the local rows cannot be built

    # ---- races: every contest on the November list, and every seat the roster says exists
    races = {}
    for r in g_rows:
        rid, info = race_of(r["Contest"], r["District/County"])
        races.setdefault(rid, info)
    for r in p_rows:
        rid, info = race_of(r["Contest"], r["District/County"])
        if rid not in races:
            raise SystemExit(f"South Dakota (state races): {rid} is on the primary list but not on the November list")
    missing_seats = sorted({f"2026-{STATE}-{'SS' if ch == 'Senate' else 'SH'}{d}" for (ch, d) in seats} - set(races))
    # one senator a district; two representatives, except in the single-member A and B districts (26A, 26B, 28A, 28B)
    n_seats = {rid: 2 if i["chamber"] == "House" and not i["district"][-1:].isalpha() else 1 for rid, i in races.items()}
    for rid, i in races.items():
        held = len(seats.get((i["chamber"], i["district"]), [])) if i["level"] == "legislature" else None
        if held is not None and held != n_seats[rid]:
            checks.append(f"{rid}: the roster lists {held} sitting members for {n_seats[rid]} seats")

    holders, notes = {}, {}
    for rid, i in races.items():
        if i["level"] == "legislature":
            hs = seats.get((i["chamber"], i["district"]), [])
            holders[rid] = hs
            if not hs:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
            if i["chamber"] == "House" and n_seats[rid] == 2:
                notes[rid] = ("Elect 2. Two members represent this district in the State House; the two candidates with the "
                              "most votes are elected." + (" " + notes[rid] if rid in notes else ""))
        else:
            h = offices.get(i["roster"]) if i["roster"] else None
            holders[rid] = [h] if h else []
            if not h:
                notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
    notes[f"2026-{STATE}-GOV"] = ("South Dakota elects the Governor and Lieutenant Governor together, on one vote; the list "
                                  "names each ticket, the candidate for Governor first.")
    primary_offices = {race_of(r["Contest"], r["District/County"])[0] for r in p_rows}
    for rid, i in races.items():
        if i["level"] == "statewide" and rid not in primary_offices:
            notes[rid] = ((notes[rid] + " ") if rid in notes else "") + "This office was not on the June 2 primary ballot."

    # everyone in the roster, for a candidate who sits today in another seat or office
    everyone = [p for ps in seats.values() for p in ps] + [dict(p, chamber=None, district=None) for p in offices.values()]

    def sitting(rid, names):
        """{name: (member id, incumbent, note)}: a one-to-one fit with the seat's holders; else, for a legislative race,
        one sitting member of the other chamber for the same district; for a statewide race, one roster person."""
        i, out = races[rid], {}
        heads = {n: ticket_head(n) if rid.endswith("-GOV") else n for n in names}
        hs = holders[rid]
        pairs = [(n, h) for n in names for h in hs if person_fits(heads[n], h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h["id"], 1, None)
        for n in names:
            if n in out:
                continue
            if i["level"] == "legislature":
                other = "House" if i["chamber"] == "Senate" else "Senate"
                pool = [p for (ch, d), ps in seats.items() if ch == other and
                        (d == i["district"] or (other == "House" and re.fullmatch(re.escape(i["district"]) + "[AB]", d or ""))
                         or (other == "Senate" and d == re.sub(r"[AB]$", "", i["district"]))) for p in ps]
            else:
                pool = [p for p in everyone if not any(p["id"] == h["id"] for h in hs)]
            got = [p for p in pool if person_fits(heads[n], p)]
            if len(got) == 1:
                p = got[0]
                where = (f"{CHAMBER_WORDS[p['chamber']]}, District {p['district']}" if p["chamber"] else p["label"])
                out[n] = (p["id"], 0, f"Serves today in {where}." if p["chamber"] else f"Serves today as {where}.")
        return out

    cand = []

    # ---- the November ballot
    on_ballot = defaultdict(list)
    noms_shown = defaultdict(list)                           # (race, party code) -> names on the list, withdrawn included
    withdrawn = []
    for r in g_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        name = STATUS_MARK.sub("", r["Name"]).strip()
        noms_shown[(rid, r["Party"])].append(name)
        if r["Status"] != "Active" or r["WithdrawnDate"]:
            withdrawn.append(rid)
            continue
        on_ballot[rid].append(r | {"Name": name})
    primary_names = defaultdict(list)
    for r in p_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        primary_names[(rid, r["Party"])].append(STATUS_MARK.sub("", r["Name"]).strip())
    for rid, rows in on_ballot.items():
        fit = sitting(rid, [r["Name"] for r in rows])
        for r in rows:
            party = PARTY.get(r["Party"], r["Party"])
            mid, inc, note = fit.get(r["Name"], (None, 0, None))
            n = [note] if note else []
            if races[rid]["level"] == "legislature" or rid.endswith("-GOV"):
                if r["Party"] in ("REP", "DEM") and not any(same_person(ticket_head(r["Name"]), x) for x in primary_names[(rid, r["Party"])]):
                    n.append(f"Not on the June 2 {party} primary list for this seat; named afterwards (the list does not say how).")
            if inc and holders[rid]:
                h = next(h for h in holders[rid] if h["id"] == mid)
                if h["party"] and h["party"] != party:
                    checks.append(f"{rid}: sitting member listed as {h['party']}, on the ballot as {party}")
            order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None
            cand.append((rid, "general", GENERAL, r["Name"], party, party_code(party), order, inc, 0, None, None, None,
                         mid, SRC_GENERAL, " ".join(n) or None))

    # ---- the June 2 primary fields, and the July 28 runoff
    ballot = defaultdict(list)                               # (race, party code) -> primary-ballot rows
    off_primary = 0
    for r in p_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        on = r["Status"] == "Active" or (r["Status"] == "Withdrawn" and after_primary(r["WithdrawnDate"]))
        if not on:
            off_primary += 1
            continue
        ballot[(rid, r["Party"])].append(r | {"Name": STATUS_MARK.sub("", r["Name"]).strip()})
    fields = Counter()
    unsettled, order_odd = [], []
    runoff_used = False
    for (rid, code), rows in sorted(ballot.items()):
        k = n_seats[rid]
        printed = [r for r in rows if r["Ballot Order"].isdigit()]
        if len(rows) <= k:
            continue
        if len(printed) != len(rows):
            order_odd.append(f"{rid} {code} (a field of {len(rows)}, {len(printed)} with a ballot order)")
        party = PARTY.get(code, code)
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        fit = sitting(rid, [r["Name"] for r in rows])
        runoff = None
        if rid.endswith("-GOV") and code == "REP":
            if not ro_names:
                checks.append("the Republican runoff for Governor could not be read: June 2 outcomes left open")
            else:
                runoff = [n for n in ro_names if sum(1 for r in rows if same_person(n, r["Name"])) == 1]
                if len(runoff) != 2:
                    checks.append(f"the runoff's candidates ({ro_names}) are not both in the June 2 Republican field for Governor")
                    runoff = None
        if runoff:
            runoff_used = True
            # the November list names the ticket ("Larry Rhoden & Tony Venhuizen"): its first name is the nominee for Governor
            winner = [n for n in runoff if any(same_person(n, ticket_head(x)) for x in noms_shown[(rid, code)])]
            for r in rows:
                mid, inc, note = fit.get(r["Name"], (None, 0, None))
                a = any(same_person(n, r["Name"]) for n in runoff)
                cand.append((rid, f"primary-{code}", PRIMARY, r["Name"], party, party_code(party),
                             int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None, inc, 0, None, None,
                             "advanced" if a else "lost", mid, SRC_PRIMARY,
                             " ".join(x for x in [note, "Advanced to the July 28 runoff." if a else None] if x) or None))
            if len(winner) != 1:
                checks.append(f"the runoff's winner is not the one Republican on the November list for Governor ({runoff})")
            rfit = sitting(rid, runoff)
            for n in runoff:
                mid, inc, note = rfit.get(n, (None, 0, None))
                cand.append((rid, f"runoff-{code}", RUNOFF, n, party, party_code(party), None, inc, 0, None, None,
                             None if len(winner) != 1 else ("advanced" if n == winner[0] else "lost"), mid, SRC_RUNOFF, note))
            continue
        won = [r for r in rows if any(same_person(r["Name"], x) for x in noms_shown[(rid, code)])]
        settled = len(won) == k
        if not settled:
            unsettled.append(f"{rid} {party} ({len(won)} of {k} found on the November list)")
        for r in rows:
            mid, inc, note = fit.get(r["Name"], (None, 0, None))
            outcome = None if not settled else ("advanced" if r in won else "lost")
            cand.append((rid, f"primary-{code}", PRIMARY, r["Name"], party, party_code(party),
                         int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None, inc, 0, None, None, outcome, mid,
                         SRC_PRIMARY, note))

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"South Dakota (state races): the same name twice in one election: {dup}")
    gen_by_race = Counter(c[0] for c in cand if c[1] == "general")
    empty = sorted(rid for rid in races if gen_by_race[rid] == 0)
    short = sorted(f"{rid} ({gen_by_race[rid]} for {n_seats[rid]} seats)" for rid in races if 0 < gen_by_race[rid] < n_seats[rid])
    listed = len(g_rows)
    if gen_by_race.total() + len(withdrawn) != listed:
        raise SystemExit("South Dakota (state races): November rows written plus withdrawn do not equal the list's state rows")
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
    sen = sorted(int(re.sub(r"\D", "", i["district"])) for i in races.values() if i["office_kind"] == "state_senate")
    if sen != list(range(1, 36)):
        checks.append(f"State Senate districts on the list are not 1 to 35: {sen}")
    house_seats = sum(n_seats[rid] for rid, i in races.items() if i["office_kind"] == "state_house")
    if house_seats != 70:
        checks.append(f"State House seats on the list add to {house_seats}, not 70")

    race_rows = []
    for rid, i in sorted(races.items()):
        hs = holders[rid]
        hid = ",".join(h["id"] for h in hs) or None
        hname = " and ".join(h["full"] for h in hs) or None
        hparty = ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], NAME, FIPS, None, i["district"], None, 0, 1,
                          hid, hname, hparty, GENERAL, notes.get(rid)))

    n_primary_state = len(p_rows)
    src = [
        (SRC_GENERAL, STATE, "official candidate list", "South Dakota Secretary of State",
         "2026 General Election Candidate List (state offices and the Legislature)", GENERAL_URL, "", g_fetched, sha_of(g_path), listed,
         f"Every page of the grid read ({g_items} rows, {g_how}); the {listed} rows for state offices and the Legislature kept, and only "
         "Contest, Name, Party, District/County, Ballot Order, Status, WithdrawnDate, OfficeSeqNum, DistrictType, elType and eldate; "
         f"the grid's mailing-address columns are never read. Withdrawn, left off the November ballot: {len(withdrawn)}. Parties "
         "written out from REP, DEM, IND, LIB. The fingerprint is of the kept columns (ballot_cache/sd/sd_2026_general_state.json)."),
        (SRC_PRIMARY, STATE, "official candidate list", "South Dakota Secretary of State",
         "2026 Primary Election Candidate List, June 2, 2026 (Governor and the Legislature)", PRIMARY_URL, "", p_fetched, sha_of(p_path),
         n_primary_state,
         f"Every page of the grid read ({p_items} rows, {p_how}; most are county and party offices, not kept); {n_primary_state} rows "
         "for Governor and the Legislature kept, allowed columns only; mailing addresses never read. A party primary is a field when "
         "more candidates were on its ballot than seats; withdrawn before June 2 or decertified after a challenge, left off: "
         f"{off_primary}. Who advanced is read from the November list. No vote counts: the State Canvassing Board's certified "
         "canvass of the 2026 primary was not published on the Secretary of State's site as of 2026-09-30, and the results site labels its "
         "figures unofficial."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "South Dakota legislators and statewide officials, as loaded into state_sd.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (names, parties, districts and ids only). The roster does not carry the Auditor, "
         "the Treasurer, the Commissioner of School and Public Lands or the Public Utilities Commissioners."),
    ]
    if runoff_used:
        src.append((SRC_RUNOFF, STATE, "results site (candidate names only)", "South Dakota Secretary of State",
                    "Primary Election July 28, 2026: Governor (the Republican runoff's two candidates)", RUNOFF_URL, "", ro_fetched,
                    sha_of(r_path), len(ro_names),
                    "Only the names of the runoff's two candidates are read, as the two who advanced from the June 2 Republican field; "
                    "the winner is the Republican on the November list. The site labels its figures \"Unofficial Results\", so no "
                    "figure is loaded; votes wait for the State Canvassing Board's certified canvass."))

    clash = sorted(set(r[0] for r in race_rows) & set(r[0] for r in local["races"]))
    if clash:
        raise SystemExit(f"South Dakota: a local race id is also a state race's: {clash[:3]}")

    # South Dakota's rows only, in one transaction: its races and candidates by state and race id, its sources, gaps and
    # notes by state, its places by their sd- source ids. Other states' rows in the same database are never touched.
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executescript(EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (STATE.lower() + "-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        taken = {(k, i) for k, i in con.execute("SELECT kind, id FROM sl_places")} & {(p[0], p[1]) for p in local["places"]}
        if taken:      # another state's loader holds a place id of ours: stop, and the transaction undoes the deletes
            raise SystemExit(f"South Dakota (local races): place ids already used by another state's rows: {sorted(taken)[:3]}")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + local["cands"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["sources"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    # ---- the report: counts only
    by = Counter(kind_of(rid) for rid in races)
    gen = Counter(kind_of(c[0]) for c in cand if c[1] == "general")
    one = Counter(kind_of(rid) for rid, v in gen_by_race.items() if v <= n_seats[rid])
    inc = Counter(kind_of(c[0]) for c in cand if c[1] == "general" and c[7])
    say(f"    South Dakota (state races): {by['state_senate']} Senate seats, {by['state_house']} House races ({house_seats} seats), "
        f"{by['statewide']} statewide offices; {gen.total()} candidates on the November "
        f"ballot (Senate {gen['state_senate']}, House {gen['state_house']}, statewide {gen['statewide']}; {len(withdrawn)} withdrawn left "
        f"off; no more candidates than seats: Senate {one['state_senate']}, House {one['state_house']}, statewide {one['statewide']}); "
        f"sitting member on the ballot: Senate {inc['state_senate']}, House {inc['state_house']}, statewide {inc['statewide']}; "
        f"primary fields: Senate {fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}"
        + ("; the July 28 runoff for Governor" if runoff_used else "") + " (who advanced, no vote counts)")
    for label, items in (("no candidate on the November list", empty), ("fewer candidates than seats", short),
                         ("seats in the roster not on the November list", missing_seats), ("primary fields left open", unsettled),
                         ("ballot order does not match the field", order_odd)):
        if items:
            say(f"    CHECK South Dakota (state races): {label}: {', '.join(items)}")
    for c in checks:
        say(f"    CHECK South Dakota (state races): {c}")
    for line in local["report"]:
        say(line)
    return len(cand) + len(local["cands"])


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    again = "--refresh" in args
    if again:
        args.remove("--refresh")
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_sd.py <database file> [--cache <folder>] [--refresh]")
    if os.path.basename(args[0]).lower() == "ballot_2026.sqlite":
        raise SystemExit("this loader never writes ballot_2026.sqlite")
    load(args[0], cache=cache, refresh=again)
