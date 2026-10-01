"""
ballot/state_local_or.py - Oregon's state races on the November 3, 2026 ballot: Governor, the fifteen State Senate seats
up this year and all sixty House seats, with the May 19 party primaries that chose the nominees; and, of the local
offices, the District Attorney and Circuit Court judge contests on the same list (see "County and judicial-district
offices" below). Written into ballot_local_2026.sqlite (never ballot_2026.sqlite), Oregon's rows only.

    python ballot/state_local_or.py <database file> [--cache <folder>] [--refresh]

Sources, all the Oregon Secretary of State's Elections Division's own (the same two the federal loader,
ballot/lists/or.py, reads for Congress; this loader keeps the state rows):

  * ORESTAR's candidate filing search ("Search Candidate & Campaign Filings", secure.sos.state.or.us/orestar/
    CFSearchPage.do, "Candidate Filings"), asked exactly as its own page asks: the page's list of offices for each 2026
    election (/orestar/ajaxdataserver/getCFOfficeGrpsByElection), its list of districts for an office
    (/orestar/ajaxdataserver/findOfficeForOfficeGrp), then the search form itself, with the site's anti-forgery token
    and the "include disqualified" box ticked, and once more by withdrawal date (the only way the search shows a
    withdrawn filing). The page shows at most 50 rows, so an office with 50 or more filings is asked district by
    district, and the districts' counts must add up to the office's. The result grid has seven columns (Ballot Name,
    Party, Office, Election, Filing Method, Filing Date, Qualified), none of them contact details; each is taken by its
    heading. The page's Export and Printable Report files and each filing's detail page (which carries addresses) are
    never fetched. The cached copy (ballot_cache/or/or_2026_orestar_state.json) keeps the seven columns only.
    The 2026 General Election list names Governor, State Senator (15 districts), State Representative (60), District
    Attorney and Judge of the Circuit Court. The last two (county and judicial-district offices) are counted in this
    reading and loaded from a reading of their own, described under "County and judicial-district offices" below.
  * The "2026 May Primary Election Official Results" (the May 19, 2026, Primary Election Abstract of Votes), the file the
    federal loader already keeps (ballot_cache/or/or_2026_primary_official_results.pdf), read with ballot/pdftext.py.
    Several districts share a page; a district heading ("3rd District", sometimes split over two lines) starts each
    one, then a section per party: the candidates' family names across the top (* nominee, (WI) a write-in who won the
    nomination), their given names under them, one row per county and a Total row (a one-county district has no Total
    row: its county row is the total). Checks: every county is one of Oregon's 36; each column's county rows add up to
    its Total; the names printed on each party's ballot are exactly that party's qualified filings on ORESTAR's 2026
    Primary Election list, and every such filing has a contest; the nominee marked * is the column with the most votes;
    the party's "Nominated" filing on the November list is that nominee (or the list says why not). "Misc." is votes for
    names not printed and not nominated. The Commissioner of the Bureau of Labor and Industries and the judges of the
    Supreme Court and Court of Appeals were on the May ballot and are marked ** Elected there (a majority in May decides a
    nonpartisan office); they are not on the November ballot and are named in the source note only.
  * The November 5, 2024, General Election Abstract of Votes (Election History page, "Official Results of November
    General"): only the district headings on its State Senator pages are read, to show which fifteen Senate seats were
    elected in 2024 for four years. Oregon senators serve four years; a 2026 Senate seat that was also elected in 2024
    would be filling the rest of a term (special = 1). In 2026 there is none: the 2026 list's fifteen and 2024's fifteen
    are the thirty seats.
  * The Census Bureau's 2024 county file (states_cache/census/cb_2024_us_county_500k.zip, its attribute table only):
    Oregon's 36 county names and FIPS codes, to check the abstract's county rows and to say which counties each district
    reaches (from the abstract's own county rows).

Who holds each seat today comes from state_or.sqlite (the Open States roster the state pages use): legislators serving
now, by chamber and district, and the officials table for the Governor. Only ids, names, parties and districts are
selected (the roster's other names too, so Emerson Levy on the ballot fits Em Levy in the roster); its contact columns
never are. A candidate is the incumbent only when the name fits exactly one sitting member of the same chamber and
district (or the sitting Governor), and that member fits only that candidate.

Oregon lets more than one party nominate a candidate (including by write-in votes in another party's primary), and
ORESTAR lists each nomination as a filing of its own. The November ballot is one row per candidate with every
nominating party, shown in the order the nominations were filed ("Democrat, Working Families"). A filing with the
method "Write In" is a party's nomination won with write-in votes at the May primary and accepted afterwards (every
one of them is a (WI) nominee of that party in the abstract, which the loader checks); the name is printed on the
November ballot under that party like any other nomination, so it is not a write-in there. "Independent" on Oregon's
lists is a political party, apart from "Nonaffiliated" (no party). The list gives no ballot order, so ballot_order is
left empty.

A field is a party primary with two or more names printed on that party's ballot; a write-in nominee's column beside
them is kept (write_in 1). pct is of the party primary's votes, Misc. included. The nominee marked * advanced.

County and judicial-district offices (John, 2026-09-30; a narrow pass: the statewide part only)
------------------------------------------------------------------------------------------------
Oregon has no statewide list of county, city and district candidates: a candidate for county office files with the
county elections official and a candidate for city office with the city's elections officer (ORS 249.035), and the
county clerk conducts every election and prepares the ballots (ORS 246.200). The Secretary of State's list carries the
offices filed with the state, and two of those are local: District Attorney (one for each county, ORS 8.610) and Judge
of the Circuit Court (by judicial district and position, ORS 3.012). Both are nonpartisan (ORS 249.002). They are loaded
here, filed under level "court" with the counties they reach; every one of the 36 counties gets a row in sl_gaps saying
that its county, city and district contests are not loaded yet. Nothing is read county by county in this pass.

  * The same ORESTAR search, 2026 General Election, asked for District Attorney and for Judge of the Circuit Court by
    two routes: every filing for the office, and contest by contest through the page's own menu of counties, districts
    and positions. The two readings must give the same rows and the page's own "N found" counts; a third search by
    withdrawal date counts withdrawn filings. Only six columns are turned into text, each found by its heading: Ballot
    Name, Party, Office, Election, Filing Method and Qualified (the grid has no contact columns; the filing date is not
    read for these offices, and the Export file, the printable report and the filings' detail pages are never
    fetched). A kept cell that looked like contact details would be blanked and counted before anything else saw it.
    The pages are not kept: ballot_cache/or/local/or_2026_orestar_local.json holds the six columns of the qualified
    filings, each page's SHA-256 and counts. A filing with Qualified "No" and a withdrawn filing are left off and
    counted, never named. The list gives no ballot order.
  * Why a contest is on the November ballot at all (most judges and district attorneys were elected on May 19: a
    majority at the nominating election decides a nonpartisan office, ORS 249.088) comes from the list's Filing Method
    and from the May 19 abstract, whose Judge of the Circuit Court and District Attorney pages are read for each
    contest's heading, county rows and marks (* nominee, ** elected; the county rows must add up to the Total row, and
    the one contest of several counties printed without a Total row, the 15th District's, has its county rows added
    up instead): "Nominated" is checked against the abstract (no one elected, the two with the most votes marked as
    nominees, no majority); "Fee" or "Completed Petitions" is a filing for the November election itself (ORS 249.205)
    and "Auto Nominated **" the list's mark for "Automatically nominated to General Election", as the page's own
    footnote reads (ORS 249.091), and for both the abstract must have no such contest. The race's note says which in
    plain words; a contest whose rows the rules cannot read keeps its race, with no candidate, a note and a row in
    sl_gaps, and nothing is guessed. No primary rows are stored for these offices.
  * Which counties a judicial district covers: ORS 3.012 (Oregon Revised Statutes, chapter 3, on the Legislature's
    site; cached whole in ballot_cache/or/local/, it is statute text), checked against the county rows the abstract
    prints under that district's positions. If the two disagreed the race would carry no counties and a gap. A
    district attorney's county is the one the list names.
  * Tables: sl_races (level court; office_kind district_attorney, jurisdiction the county and its FIPS code;
    office_kind circuit_court, jurisdiction "<n>th Judicial District", id OR-JD<n>, district the number, seat
    "Position <p>"; race ids 2026-OR-DA-<county FIPS> and 2026-OR-CC<district>-P<position>), sl_candidates (election
    general, "Nonpartisan office", N, no ballot order, never matched to a roster), sl_places (kind judicial for the
    districts used; the 36 county rows as before), sl_gaps and sl_notes (ballot.check_local.EXTRA_SCHEMA; keys
    local_calendar and local_coverage), all rewritten for Oregon on every run.

The privacy rule: only office, district, name, party, filing method, filing date, status and votes are read from any
file (for the local offices: no filing date either). None of these files carries an address, telephone number, website
or e-mail, and the code would not read one if it did. A local candidate has no holder, incumbent mark, roster link,
photo, age, website, biography or money here, and one who withdrew or did not qualify is counted, not named.
"""

import collections
import datetime as dt
import hashlib
import importlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, rows as pdf_rows                            # noqa: E402
from states import net                                                     # noqa: E402

fed = importlib.import_module("ballot.lists.or")                            # "or" is a keyword, so imported by name
Orestar, SEARCH_PAGE, ORESTAR, text, us_date, cells = fed.Orestar, fed.SEARCH_PAGE, fed.ORESTAR, fed.text, fed.us_date, fed.cells

STATE, NAME, FIPS = "OR", "Oregon", "41"
GENERAL, PRIMARY = "2026-11-03", "2026-05-19"
ELECTIONS = {"general": "2026 General Election", "primary": "2026 Primary Election"}
OFFICES = {"GOV": "Governor", "SS": "State Senator", "SR": "State Representative"}
NOT_LOADED = {"DA": "District Attorney", "JCC": "Judge of the Circuit Court"}
KEEP = ("Ballot Name", "Party", "Office", "Election", "Filing Method", "Filing Date", "Qualified")
ROSTER = os.path.join(HERE, "state_or.sqlite")
DEFAULT_CACHE = os.path.join(CACHE, "or")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
HISTORY_PAGE = fed.HISTORY_PAGE
RESULTS_2024 = {"uri": "13735458", "date": "2024-11-05", "title": "November 5, 2024, General Election Abstract of Votes"}
TITLE_2026 = fed.TITLE
CODES = {"Democrat": "DEM", "Republican": "REP", "Libertarian": "LIB"}      # other parties take ORESTAR's own code
PAGE_OFFICES = {"Governor": "GOV", "State Senator": "SS", "State Representative": "SH"}
DECIDED = ("Commissioner of the Bureau of Labor and Industries", "Judge of the Supreme Court", "Judge of the Court of Appeals",
           "Judge of the Oregon Tax Court")
FOOTER = ("* Nominee", "** Elected", "WI = Write In")
NUM = re.compile(r"\d{1,3}(?:,\d{3})*")
ORD = re.compile(r"(\d+)(?:st|nd|rd|th)(?: District)?")
METHODS_GENERAL = {"Nominated", "Minor Party", "Completed Petitions", "Assembly", "Auto Nominated", "Write In", "Vacancy",
                   "Selected by Secretary of State"}
METHODS_PRIMARY = {"Fee", "Completed Petitions", "Write In"}
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
INDEPENDENT = "On Oregon's lists Independent is a political party, apart from Nonaffiliated (no party)."
NO_ORDER = "The Secretary of State's list gives no ballot positions."
AGENCY = "Oregon Secretary of State, Elections Division"
SRC = {"general": "or-sos-2026-sl-general-list", "primary": "or-sos-2026-sl-primary-list",
       "results": "or-sos-2026-sl-primary-results", "senate2024": "or-sos-2024-senate-abstract",
       "county": "or-census-2024-counties", "roster": "or-openstates-roster-2026",
       "local_list": "or-sos-2026-local-general-list", "local_results": "or-sos-2026-local-primary-results",
       "districts": "or-ors-3-012-judicial-districts"}

# ---- county and judicial-district offices on the state's list (the local pass)
LOCAL = {"DA": "District Attorney", "JCC": "Judge of the Circuit Court"}
LOCAL_KEEP = ("Ballot Name", "Party", "Office", "Election", "Filing Method", "Qualified")      # no filing date for these offices
LOCAL_FILE = "or_2026_orestar_local.json"
LOCAL_METHODS = {"Nominated", "Fee", "Completed Petitions", "Auto Nominated"}                  # the grid's footnote mark (" **") set aside
LOCAL_PAGES = {"Judge of the Circuit Court": "JCC", "District Attorney": "DA"}
POSITION = re.compile(r"(\d+)(st|nd|rd|th) District, Position (\d+)")
ORS = "https://www.oregonlegislature.gov/bills_laws/"
ORS_CHAPTER_3 = ORS + "ors/ors003.html"
ORS_INDEX = ORS + "Pages/ORS.aspx"
ORS_FILE = "or_ors_chapter_003.html"
CLERKS_PAGE = "https://sos.oregon.gov/elections/Pages/countyofficials.aspx"
_ONES = "first second third fourth fifth sixth seventh eighth ninth".split()
ORDINALS = {w: i + 1 for i, w in enumerate(_ONES + "tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
                                                  "nineteenth".split())}
for _tens, _stem, _whole in ((20, "twenty", "twentieth"), (30, "thirty", "thirtieth")):
    ORDINALS[_whole] = _tens
    ORDINALS.update({f"{_stem}-{w}": _tens + i + 1 for i, w in enumerate(_ONES)})
LEGISLATURE = "Oregon Legislative Assembly, Legislative Counsel Committee"
RUNOFF = ("No candidate won more than half of the votes for this {what} at the May 19 primary, so the two with the most votes are on the "
          "November ballot (ORS 249.088).")
FILED = ("This {what} was not on the May 19 primary ballot: the candidates filed for the November election. ORS 249.205 allows that when a "
         "vacancy in a nonpartisan office comes too late for the primary, or when the only candidate nominated dies, withdraws or becomes "
         "ineligible.")
AUTO = ("Marked on the Secretary of State's list as automatically nominated to the general election. Under ORS 249.091, when no more than "
        "two candidates file to fill a vacancy in a nonpartisan office, their names are left off the May primary ballot and go on the "
        "November ballot.")
NOMINATED_ONLY = "The Secretary of State's list files the candidates for this {what} as nominated at the May 19 primary."
NO_CANDIDATE = "The Secretary of State's list shows no qualified candidate for this {what}."
CALENDAR = ("On November 3, 2026 Oregon voters elect the sheriffs, county clerks and county treasurers whose terms end, county commissioners "
            "chosen on a party ballot, city officers (state law holds city elections together with state and county ones), and directors of "
            "soil and water conservation districts and people's utility districts. Other nonpartisan offices, such as district attorney, "
            "circuit judge and county assessor, are settled at the May 19 primary when one candidate wins a majority, and reach the November "
            "ballot only as a runoff between the top two or to fill a vacancy; a county's home rule charter can set other rules for its own "
            "offices. School, community college, fire, water, park, library, port and most other district boards are elected on the third "
            "Tuesday in May of odd-numbered years, next on May 18, 2027.")
CALENDAR_SOURCE = "Oregon Revised Statutes 204.005, 249.088, 249.091, 249.205, 254.035, 255.335, 261.420 and 568.520"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def fresh(path, days):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < days * 86400


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def join(cs):
    return " ".join(c[2] for c in cs)


# ---------------------------------------------------------------- ORESTAR: the seven columns only

def xml_items(body):
    return [(text(n), v.strip()) for n, v in re.findall(r"<item><name>(.*?)</name><value>(.*?)</value></item>", body, re.S)]


def offices_of(s, eid):
    """{code: label} of the offices ORESTAR lists for one election."""
    got = s.open(ORESTAR + f"ajaxdataserver/getCFOfficeGrpsByElection?elecRsn={eid}&elecYear=2026").decode("utf-8", "replace")
    return {v: n for n, v in xml_items(got) if v}


def districts_of(s, code, eid):
    """[(label, value)] of an office's districts for one election, in the page's own order."""
    got = s.open(ORESTAR + f"ajaxdataserver/findOfficeForOfficeGrp?officeGroupselected={code}&elecYear=2026"
                 f"&cfElecRsn={eid}").decode("utf-8", "replace")
    return [(n, v) for n, v in xml_items(got) if v]


def search(s, election, code, grp=("", ""), withdrawn=False):
    """(kept columns of every filing shown, the page's own count). Rows are read only when the count is under 50."""
    label, value = grp
    fields = {"cfSearchButtonName": "", "cfName": "", "cfyearActive": "2026", "cfElection": s.elections[election],
              "cfOffice": code, "cfOfficeGrp": value, "cfPartyAffiliation": "", "cfDisqualifiedCandidates": "on",
              "cfFilingType": "", "cfFilingFromDate": "", "cfFilingToDate": "",
              "cfWithDrawFromDate": "01/01/2025" if withdrawn else "", "cfWithDrawToDate": "12/31/2026" if withdrawn else "",
              s.token[0]: s.token[1]}
    page = s.open(s.action, data=urllib.parse.urlencode(fields).encode()).decode("utf-8", "replace")
    office = {**OFFICES, **NOT_LOADED}[code]
    what = f"{election}, {office}" + (f", {label}" if label else "") + (" (withdrawn)" if withdrawn else "")
    if "Candidate Filing Search Results" not in page:
        raise SystemExit(f"Oregon (state races): ORESTAR did not return its search results for {what}")
    crit = re.search(r"Election Year: 2026, Election: ([^,<]+), Office: ([^,<]+?)(?:, District, Position, County or City: ([^,<]+?))?"
                     r"(?:,[^<]*)?\s*</td>", page)
    if not crit or crit.group(1).strip() != election or crit.group(2).strip() != office or (crit.group(3) or "").strip() != label:
        raise SystemExit(f"Oregon (state races): ORESTAR answered a different search than {what}")
    found = re.search(r"(\d+) found for the above search criteria", page)
    if not found:
        raise SystemExit(f"Oregon (state races): ORESTAR's results for {what} no longer say how many were found")
    n = int(found.group(1))
    if n >= 50:
        return [], n
    out = []
    table = re.search(r'<table id="cfSearchResults".*?</table>', page, re.S)
    if table:
        heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table.group(0), re.S)]
        if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
            raise SystemExit(f"Oregon (state races): ORESTAR's result columns changed ({len(heads)} headings)")
        idx = {k: heads.index(k) for k in KEEP}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if not tds or (n == 0 and len(tds) == 1):
                continue
            if len(tds) != len(heads):
                raise SystemExit(f"Oregon (state races): an ORESTAR result row for {what} does not line up with its headings")
            out.append({k: text(tds[i]) for k, i in idx.items()})
    if len(out) != n:
        raise SystemExit(f"Oregon (state races): ORESTAR counts {n} filings for {what}; {len(out)} were read")
    for r in out:
        if r["Election"] != election:
            raise SystemExit(f"Oregon (state races): an ORESTAR row for {what} names another election")
    return out, n


def every_filing(s, election, code, groups, withdrawn):
    """Every filing for an office: asked for the office, and district by district when the office has 50 or more."""
    rows, n = search(s, election, code, withdrawn=withdrawn)
    if n < 50:
        return rows, n, False
    rows = []
    for g in groups:
        got, m = search(s, election, code, g, withdrawn)
        if m >= 50:
            raise SystemExit(f"Oregon (state races): ORESTAR counts {m} filings for {election}, {OFFICES[code]}, {g[0]}")
        rows += got
    if len(rows) != n:
        raise SystemExit(f"Oregon (state races): the district searches for {election}, {OFFICES[code]} give {len(rows)} filings; "
                         f"the office search counts {n}")
    return rows, n, True


def read_lists(folder, say, refresh=False):
    """{"general": {...}, "primary": {...}} from ORESTAR, kept on disk (the seven columns only) for two days."""
    path = os.path.join(folder, "or_2026_orestar_state.json")
    if not refresh and fresh(path, 2):
        return json.load(open(path, encoding="utf-8")), path
    s = Orestar()
    out = {"page": SEARCH_PAGE, "parties": s.parties, "fetched": dt.date.today().isoformat()}
    for kind, label in ELECTIONS.items():
        eid = s.elections[label]
        offered = offices_of(s, eid)
        e = {"election": label, "id": eid, "offices": offered, "rows": [], "withdrawn": [], "counts": {}, "districts": {},
             "by_district": [], "not_loaded": {}}
        for code in OFFICES:
            if code not in offered:
                e["counts"][code] = 0
                continue
            groups = districts_of(s, code, eid)
            e["districts"][code] = [g for g, _v in groups]
            for withdrawn in (False, True):
                rows, n, split = every_filing(s, label, code, groups, withdrawn)
                e["withdrawn" if withdrawn else "rows"].extend(rows)
                e["counts"][code + (" withdrawn" if withdrawn else "")] = n
                if split:
                    e["by_district"].append(code + (" withdrawn" if withdrawn else ""))
        if kind == "general":
            for code, office in NOT_LOADED.items():
                if code in offered:
                    _rows, n = search(s, label, code)
                    e["not_loaded"][office] = n                  # a count only; the rows are not kept
        out[kind] = e
        say(f"      ORESTAR Candidate Filings, {label}: {len(e['rows'])} state filings, {len(e['withdrawn'])} withdrawn")
    os.makedirs(folder, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out, path


def race_of(office):
    """ORESTAR's Office column -> (race_id, kind, district)."""
    if office == "Governor":
        return f"2026-{STATE}-GOV", "GOV", None
    m = re.fullmatch(r"State (Senator|Representative), (\d+)(?:st|nd|rd|th) District", office or "")
    if m:
        k = "SS" if m.group(1) == "Senator" else "SH"
        return f"2026-{STATE}-{k}{int(m.group(2))}", k, str(int(m.group(2)))
    raise SystemExit(f"Oregon (state races): an ORESTAR row names an office that is not read ({office!r})")


# ---------------------------------------------------------------- the official results (vote counts only)

def results_2024(folder, say):
    """The Senate districts on the November 5, 2024 abstract (district headings of its State Senator pages only)."""
    pdf_path = os.path.join(folder, "or_2024_general_official_results.pdf")
    url = fed.RECORDS + "DocumentStream.ashx?uri=" + RESULTS_2024["uri"]
    net.download(url, pdf_path, max_age_days=365, say=say)
    if open(pdf_path, "rb").read(5) != b"%PDF-":
        raise SystemExit(f"Oregon (state races): {os.path.basename(pdf_path)} is not a PDF; delete it and run again")
    pdf = PDF(open(pdf_path, "rb").read())
    districts, pages = [], []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = [cs for cs in (cells(rs) for _y, rs in pdf_rows(pdf, page, res)) if cs]
        if len(prow) < 2 or join(prow[1]) != "State Senator":
            continue
        if join(prow[0]) != RESULTS_2024["title"]:
            raise SystemExit(f"Oregon (state races): page {n} of the 2024 abstract is not headed {RESULTS_2024['title']!r}")
        pages.append(n)
        lines = [join(cs) for cs in prow[2:] if all(c[0] < 150 for c in cs)]
        i = 0
        while i < len(lines):
            m = ORD.fullmatch(lines[i])
            if m:
                if not lines[i].endswith("District"):
                    if i + 1 >= len(lines) or lines[i + 1] != "District":
                        raise SystemExit(f"Oregon (state races): a district heading on page {n} of the 2024 abstract is not read")
                    i += 1
                districts.append(str(int(m.group(1))))
            i += 1
    if len(set(districts)) != len(districts) or not districts:
        raise SystemExit(f"Oregon (state races): the 2024 abstract's State Senator headings are not read ({districts})")
    return {"path": pdf_path, "url": url, "record": fed.RECORDS + "RecordViewer.aspx?uri=" + RESULTS_2024["uri"],
            "districts": sorted(districts, key=int), "pages": pages}


def place(cols, x0, x1):
    """The column (by right edge) a label belongs to: labels are right-aligned, and the column must not end left of it."""
    options = [i for i, c in enumerate(cols) if c >= x0 - 2]
    return min(options, key=lambda i: abs(cols[i] - x1)) if options else None


def finish(s, where, counties):
    """One party section -> {"cols": [...], "misc": n, "counties": [...]}, after its checks."""
    if s["total"] is None:
        if len(s["data"]) != 1:
            raise SystemExit(f"Oregon (state races): no Total row under {where}")
        total_cells = [c for c in s["data"][0] if NUM.fullmatch(c[2])]
    else:
        total_cells = s["total"]
    if not total_cells or not all(NUM.fullmatch(c[2]) for c in total_cells):
        raise SystemExit(f"Oregon (state races): the Total row under {where} is not read")
    cols = [c[1] for c in total_cells]
    labels = [[] for _ in cols], [[] for _ in cols]
    for k, rows_ in ((0, s["head"]), (1, s["given"])):
        for cs in rows_:
            for x0, x1, t in cs:
                i = place(cols, x0, x1)
                if i is None:
                    raise SystemExit(f"Oregon (state races): a name under {where} lies right of every column")
                labels[k][i].append(t)
    fam = [" ".join(x) for x in labels[0]]
    giv = [" ".join(x) for x in labels[1]]
    misc = fam[-1] == "Misc."
    if misc and giv[-1]:
        raise SystemExit(f"Oregon (state races): the Misc. column under {where} has a given name")
    k = len(cols) - (1 if misc else 0)
    if not all(fam[:k]) or any(f == "Misc." for f in fam[:k]):
        raise SystemExit(f"Oregon (state races): a candidate column under {where} is missing a name")
    sums, names = [0] * len(cols), []
    for cs in s["data"]:
        county = " ".join(c[2] for c in cs if not NUM.fullmatch(c[2]))
        if fold(county) not in counties:
            raise SystemExit(f"Oregon (state races): a row under {where} is not one of Oregon's counties ({county!r})")
        vals = [None] * len(cols)
        for x0, x1, t in cs:
            if NUM.fullmatch(t):
                i = next((i for i, c in enumerate(cols) if abs(c - x1) <= 2.5), None)
                if i is None or vals[i] is not None:
                    raise SystemExit(f"Oregon (state races): a count under {where} is not in a column ({county})")
                vals[i] = int(t.replace(",", ""))
        if None in vals:
            raise SystemExit(f"Oregon (state races): {county} under {where} is missing a count")
        sums = [a + b for a, b in zip(sums, vals)]
        names.append(county)
    total = [int(c[2].replace(",", "")) for c in total_cells]
    if sums != total:
        raise SystemExit(f"Oregon (state races): the county rows under {where} do not add up to the Total row")
    out = []
    for i in range(k):
        f, g = fam[i], giv[i]
        wi = bool(re.search(r"\(WI\)", f + " " + g))
        f, g = re.sub(r"\s*\(WI\)\s*", " ", f).strip(), re.sub(r"\s*\(WI\)\s*", " ", g).strip()
        mark = re.match(r"\*+", f)
        out.append({"family": f.lstrip("*"), "given": g, "mark": mark.group(0) if mark else "", "wi": wi, "votes": total[i]})
    return {"cols": out, "misc": total[-1] if misc else 0, "counties": names}


def read_abstract(path, parties, counties):
    """({(race_id, party): contest}, [decided nonpartisan offices]) from the May 19 abstract's state pages."""
    pdf = PDF(open(path, "rb").read())
    contests, decided, titled = {}, [], False
    last = (None, None)                                       # (office, district) at the foot of the previous page
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = [cs for cs in (cells(rs) for _y, rs in pdf_rows(pdf, page, res)) if cs]
        if len(prow) < 2:
            continue
        if join(prow[0]) != TITLE_2026:
            raise SystemExit(f"Oregon (state races): page {n} of the official results is not headed {TITLE_2026!r}")
        titled = True
        office = join(prow[1])
        if office in DECIDED:
            pos = join(prow[2]) if len(prow) > 2 and join(prow[2]).startswith("Position") else ""
            marks = [c[2] for cs in prow[2:5] for c in cs if c[2].startswith("*")]
            decided.append({"office": office, "position": pos, "elected": [m[2:] for m in marks if m.startswith("**")],
                            "runoff": [m[1:] for m in marks if not m.startswith("**")], "page": n})
            last = (None, None)
            continue
        kind = PAGE_OFFICES.get(office)
        if not kind:
            last = (None, None)
            continue
        district = last[1] if last[0] == office else None
        cur, i = None, 2
        while i < len(prow):
            cs = prow[i]
            line = join(cs)
            m = ORD.fullmatch(line)
            if kind != "GOV" and m and all(c[0] < 150 for c in cs):
                if not line.endswith("District"):
                    if i + 1 >= len(prow) or join(prow[i + 1]) != "District":
                        raise SystemExit(f"Oregon (state races): a district heading on page {n} of the official results is not read")
                    i += 1
                district, cur = str(int(m.group(1))), None
                i += 1
                continue
            party = re.sub(r" \(cont\.\)$", "", line)
            if party in parties and all(c[0] < 150 for c in cs):
                if kind != "GOV" and district is None:
                    raise SystemExit(f"Oregon (state races): a party section on page {n} of the official results has no district")
                race = f"2026-{STATE}-GOV" if kind == "GOV" else f"2026-{STATE}-{kind}{district}"
                cur = {"race": race, "party": party, "head": [], "given": [], "data": [], "total": None, "phase": "head", "page": n}
                contests.setdefault((race, party), []).append(cur)
            elif line in FOOTER:
                cur = None
            elif cur is None:
                raise SystemExit(f"Oregon (state races): a line on page {n} of the official results is not read")
            elif cur["phase"] == "head" and cs[0][2] == "County":
                cur["given"].append(cs[1:])
                cur["phase"] = "given"
            elif cur["phase"] == "head":
                cur["head"].append(cs)
            elif cur["phase"] in ("given", "data") and cs[0][2] == "Total":
                cur["total"], cur["phase"] = cs[1:], "done"
            elif cur["phase"] in ("given", "data") and len(cs) > 1 and not NUM.fullmatch(cs[0][2]) and all(NUM.fullmatch(c[2]) for c in cs[1:]):
                cur["data"].append(cs)
                cur["phase"] = "data"
            elif cur["phase"] == "given":
                cur["given"].append(cs)
            else:
                raise SystemExit(f"Oregon (state races): a line on page {n} of the official results is not read")
            i += 1
        last = (office, district)
    if not titled:
        raise SystemExit("Oregon (state races): the file is not the abstract of votes of the May 19, 2026 primary")
    out = {}
    for (race, party), parts in contests.items():
        merged = {"cols": [], "misc": 0, "counties": None, "pages": []}
        for p in parts:
            where = f"{race} {party} (page {p['page']})"
            f = finish(p, where, counties)
            if merged["counties"] is not None and sorted(merged["counties"]) != sorted(f["counties"]):
                raise SystemExit(f"Oregon (state races): the continued section for {race} {party} lists other counties")
            merged["counties"] = f["counties"]
            merged["cols"] += f["cols"]
            merged["misc"] += f["misc"]
            merged["pages"].append(p["page"])
        out[(race, party)] = merged
    return out, decided


# ---------------------------------------------------------------- counties and the roster

def county_names(path=COUNTY_ZIP):
    """{folded county name: (GEOID, 'Name County')} for Oregon, from the Census file's attribute table only."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec.get("NAMELSAD") or f"{rec['NAME']} County"))
    if len(out) != 36:
        raise SystemExit(f"Oregon (state races): the Census county file lists {len(out)} Oregon counties, not 36")
    return out


def roster(path=ROSTER):
    """Sitting legislators and the Governor: id, names, party and district only."""
    if not os.path.exists(path):
        return [], [], ""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "other"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, other_names FROM legislators "
        "WHERE is_current = 1")]
    officials = [dict(zip(("id", "office", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, first_name, last_name, official_full, party_name FROM officials")]
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for m in members:
        m["district"] = str(int(m["district"])) if str(m["district"] or "").isdigit() else str(m["district"] or "")
    return members, officials, as_of


def nk(name):
    """A name folded for matching (letters only, single spaces), never for showing."""
    return " ".join(fold(name).split())


def person_fits(name, p):
    """The name fits the person's first and last name, full name or one of the roster's other names (Emerson Levy for Em Levy)."""
    parts = name_parts(name)
    forms = [p["full"] or ""] + [f.strip() for f in (p.get("other") or "").split(";") if f.strip()]
    return (fits(parts, (fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split())))
            or any(fits(parts, name_parts(f)) for f in forms))


def names_fit(a, b):
    return nk(a) == nk(b) or fits(name_parts(a), name_parts(b))


def clean(name):
    """A ballot name as shown: ORESTAR's asterisk mark dropped, spaces single."""
    return re.sub(r"\s+", " ", (name or "").replace("*", "")).strip()


# ---------------------------------------------------------------- county and judicial-district offices on the state's list

def local_search(s, code, grp=("", ""), withdrawn=False, hashes=None):
    """One search of the 2026 General Election list for District Attorney or Judge of the Circuit Court: (the six kept
    cells of every filing shown, the page's own count). Rows are read only when the count is under 50. hashes receives
    the SHA-256 of the page as fetched; the page itself is not kept."""
    election, office = ELECTIONS["general"], LOCAL[code]
    label, value = grp
    fields = {"cfSearchButtonName": "", "cfName": "", "cfyearActive": "2026", "cfElection": s.elections[election],
              "cfOffice": code, "cfOfficeGrp": value, "cfPartyAffiliation": "", "cfDisqualifiedCandidates": "on",
              "cfFilingType": "", "cfFilingFromDate": "", "cfFilingToDate": "",
              "cfWithDrawFromDate": "01/01/2025" if withdrawn else "", "cfWithDrawToDate": "12/31/2026" if withdrawn else "",
              s.token[0]: s.token[1]}
    raw = s.open(s.action, data=urllib.parse.urlencode(fields).encode())
    if hashes is not None:
        hashes.append(hashlib.sha256(raw).hexdigest())
    page = raw.decode("utf-8", "replace")
    what = office + (f", {label}" if label else "") + (" (withdrawn)" if withdrawn else "")
    if "Candidate Filing Search Results" not in page:
        raise SystemExit(f"Oregon (local offices): ORESTAR did not return its search results for {what}")
    asked = (f"Election Year: 2026, Election: {election}, Office: {office}"
             + (f", District, Position, County or City: {label}" if label else "") + ", Disqualified Candidates"
             + (", Withdrawal Date From: 01/01/2025, Withdrawal Date To: 12/31/2026" if withdrawn else ""))
    crit = re.search(r"Election Year: 2026,[^<]*</td>", page)                 # the page's own words for the search it answered
    if not crit or text(crit.group(0)) != asked:
        raise SystemExit(f"Oregon (local offices): ORESTAR answered a different search than {what}")
    found = re.search(r"(\d+) found for the above search criteria", page)
    if not found:
        raise SystemExit(f"Oregon (local offices): ORESTAR's results for {what} no longer say how many were found")
    n = int(found.group(1))
    if n >= 50:
        return [], n
    out = []
    table = re.search(r'<table id="cfSearchResults".*?</table>', page, re.S)
    if table:
        heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table.group(0), re.S)]
        if not all(k in heads for k in LOCAL_KEEP) or len(set(heads)) != len(heads):
            raise SystemExit(f"Oregon (local offices): ORESTAR's result columns changed ({len(heads)} headings)")
        idx = {k: heads.index(k) for k in LOCAL_KEEP}                          # only these cells are ever turned into text
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if not tds or (n == 0 and len(tds) == 1):
                continue
            if len(tds) != len(heads):
                raise SystemExit(f"Oregon (local offices): an ORESTAR result row for {what} does not line up with its headings")
            out.append({k: text(tds[i]) for k, i in idx.items()})
    if len(out) != n:
        raise SystemExit(f"Oregon (local offices): ORESTAR counts {n} filings for {what}; {len(out)} were read")
    if any(r["Election"] != election for r in out):
        raise SystemExit(f"Oregon (local offices): an ORESTAR row for {what} names another election")
    return out, n


def read_local_lists(folder, say, refresh=False):
    """ORESTAR's District Attorney and Circuit Court filings for the 2026 General Election, read by two routes (the whole
    office, and contest by contest through the page's own menu) that must agree, and kept on disk for two days: the six
    columns of the qualified filings, counts and each page's SHA-256. A filing that is not qualified or was withdrawn
    is kept as a count under its contest, never by name."""
    path = os.path.join(folder, LOCAL_FILE)
    if not refresh and fresh(path, 2):
        return json.load(open(path, encoding="utf-8")), path
    s = Orestar()
    label = ELECTIONS["general"]
    eid = s.elections[label]
    offered = offices_of(s, eid)
    out = {"page": SEARCH_PAGE, "fetched": dt.date.today().isoformat(), "election": label, "id": eid, "kept": list(LOCAL_KEEP),
           "offered": sorted(offered.values()), "offices": {}}
    whole_row = lambda r: tuple(r[k] for k in LOCAL_KEEP)
    filing = lambda r: (nk(r["Ballot Name"]), r["Office"])

    def blank(rows, o=None):
        """A kept cell that looks like contact details is blanked before anything else sees it, and counted (never shown)."""
        for r in rows:
            for k in LOCAL_KEEP:
                if r[k] and contact_like(r[k], True):
                    r[k] = ""
                    if o is not None:
                        o["blanked"] += 1
        return rows

    for code, office in LOCAL.items():
        o = {"office": office, "listed": code in offered, "contests": [], "count": 0, "by_contest": {}, "rows": [], "left_off": [],
             "withdrawn": 0, "both": 0, "blanked": 0, "page_sha256": []}
        out["offices"][code] = o
        if not o["listed"]:
            continue
        hashes = o["page_sha256"]
        groups = districts_of(s, code, eid)
        whole, n = local_search(s, code, hashes=hashes)
        whole, rows = blank(whole), []
        for g in groups:
            got, m = local_search(s, code, g, hashes=hashes)
            if m >= 50:
                raise SystemExit(f"Oregon (local offices): ORESTAR counts {m} filings for {office}, {g[0]}")
            o["by_contest"][g[0]] = m
            rows += [dict(r, Contest=g[0]) for r in blank(got, o)]
        if len(rows) != n:
            raise SystemExit(f"Oregon (local offices): the contest-by-contest searches for {office} give {len(rows)} filings; "
                             f"the office search counts {n}")
        if n < 50 and sorted(map(whole_row, whole)) != sorted(map(whole_row, rows)):
            raise SystemExit(f"Oregon (local offices): the two readings of {office} (the whole office, and contest by contest) give "
                             "different rows")
        gone, wn = local_search(s, code, withdrawn=True, hashes=hashes)
        gone = blank(gone, o)
        o["both"] = len({filing(r) for r in rows} & {filing(r) for r in gone})
        for r in rows:
            if r["Qualified"] == "Yes":
                o["rows"].append(r)
            else:
                o["left_off"].append({"Office": r["Office"], "Contest": r["Contest"], "Qualified": r["Qualified"]})
        o["left_off"] += [{"Office": r["Office"], "withdrew": True} for r in gone]
        o.update(contests=[g[0] for g in groups], count=n, withdrawn=wn)
    kept = sum(len(o["rows"]) for o in out["offices"].values())
    say(f"      ORESTAR Candidate Filings, {label}: {sum(o['count'] for o in out['offices'].values())} district attorney and circuit court "
        f"filings read twice, {kept} qualified, {sum(o['withdrawn'] for o in out['offices'].values())} withdrawn")
    os.makedirs(folder, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out, path


def judicial_districts(folder, counties, say):
    """({district number: [county GEOIDs]}, facts about the file) from ORS 3.012, "The first judicial district consists of
    Jackson County and has 11 judges" and so on; (None, {"why": ...}) when the statute cannot be read as expected. The
    27 districts must be numbered 1 to 27 and hold each of the 36 counties once."""
    path = os.path.join(folder, ORS_FILE)
    try:
        net.download(ORS_CHAPTER_3, path, max_age_days=30, say=say)
    except Exception as e:      # noqa: BLE001  any trouble fetching the statute: the abstract's county rows then stand alone
        return None, {"why": f"the statute's page could not be fetched ({type(e).__name__})"}
    page = text(open(path, "rb").read().decode("cp1252", "replace"))
    edition = re.search(r"\b(20\d\d) EDITION\b", page)
    out, why = {}, None
    hits = re.findall(r"The ([a-z-]+) judicial district consists of (.+?) and has \w+ judges?\.", page)
    for word, where in hits:
        one, many = re.fullmatch(r"(.+) County", where), re.fullmatch(r"the counties of (.+)", where)
        names = [one.group(1)] if one else [w.strip() for w in re.split(r",\s*|\s+and\s+", many.group(1)) if w.strip()] if many else []
        if word not in ORDINALS or not names or any(fold(x) not in counties for x in names):
            why = "a sentence of ORS 3.012 is not in the form read here"
            break
        ids = sorted(counties[fold(x)][0] for x in names)
        if out.setdefault(str(ORDINALS[word]), ids) != ids:
            why = "the chapter states one district's counties in two ways"
            break
    if not why and (sorted(out, key=int) != [str(i) for i in range(1, len(out) + 1)]
                    or sorted(i for ids in out.values() for i in ids) != sorted(g for g, _n in counties.values())):
        why = "the districts read from ORS 3.012 do not hold each of the 36 counties once"
    if why:
        if not hits:
            os.remove(path)                                                  # not the statute's page: asked for again next time
        return None, {"why": why}
    return out, {"path": path, "edition": edition.group(1) if edition else "", "sentences": len(hits)}


def summed_total(data):
    """A Total row made from a contest's county rows, for a contest of several counties that the abstract prints without
    one (the 15th District's in 2026): cells at the first row's right edges holding each column's sum. None when the
    rows' counts do not line up in the same columns."""
    edges = [c[1] for c in data[0] if NUM.fullmatch(c[2])]
    sums = [0] * len(edges)
    for cs in data:
        nums = [c for c in cs if NUM.fullmatch(c[2])]
        if not edges or len(nums) != len(edges) or any(abs(c[1] - e) > 2.5 for c, e in zip(nums, edges)):
            return None
        sums = [a + int(c[2].replace(",", "")) for a, c in zip(sums, nums)]
    return [(e - 1, e, f"{v:,}") for e, v in zip(edges, sums)]


def read_court_pages(path, counties):
    """({("JCC", district, position) or ("DA", county GEOID): {"cols", "misc", "counties", "pages"}}, the pages read) from
    the Judge of the Circuit Court and District Attorney pages of the May 19 abstract: each contest's heading, the names
    with their marks (* nominee, ** elected) and the county rows, with the checks the state pages get (finish):
    every county is one of Oregon's 36 and the county rows add up to the Total row ("summed" marks a contest of several
    counties printed without a Total row, whose county rows are added up here instead). counties are GEOIDs, sorted."""
    pdf = PDF(open(path, "rb").read())
    parts, pages = collections.OrderedDict(), []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = [cs for cs in (cells(rs) for _y, rs in pdf_rows(pdf, page, res)) if cs]
        code = LOCAL_PAGES.get(join(prow[1])) if len(prow) > 1 else None
        if not code:
            continue
        if join(prow[0]) != TITLE_2026:
            raise SystemExit(f"Oregon (local offices): page {n} of the official results is not headed {TITLE_2026!r}")
        pages.append(n)
        cur = None
        for cs in prow[2:]:
            line = join(cs)
            head, key = re.sub(r" \(cont\.\)$", "", line), None
            if cs[0][0] < 150 and code == "JCC":
                m = POSITION.fullmatch(head)
                key = ("JCC", str(int(m.group(1))), str(int(m.group(3)))) if m else None
            elif cs[0][0] < 150:
                m = re.fullmatch(r"(.+) County", head)
                key = ("DA", counties[fold(m.group(1))][0]) if m and fold(m.group(1)) in counties else None
            if key:
                cur = {"head": [], "given": [], "data": [], "total": None, "phase": "head", "page": n}
                parts.setdefault(key, []).append(cur)
            elif line in FOOTER:
                cur = None
            elif cur is None:
                raise SystemExit(f"Oregon (local offices): a line on page {n} of the official results is not read")
            elif cur["phase"] == "head" and cs[0][2] == "County":
                cur["given"].append(cs[1:])
                cur["phase"] = "given"
            elif cur["phase"] == "head":
                cur["head"].append(cs)
            elif cur["phase"] in ("given", "data") and cs[0][2] == "Total":
                cur["total"], cur["phase"] = cs[1:], "done"
            elif cur["phase"] in ("given", "data") and len(cs) > 1 and not NUM.fullmatch(cs[0][2]) and all(NUM.fullmatch(c[2]) for c in cs[1:]):
                cur["data"].append(cs)
                cur["phase"] = "data"
            elif cur["phase"] == "given":
                cur["given"].append(cs)
            else:
                raise SystemExit(f"Oregon (local offices): a line on page {n} of the official results is not read")
    out = {}
    for key, ps in parts.items():
        merged = {"cols": [], "misc": 0, "counties": None, "pages": [], "summed": False}
        for p in ps:
            if p["total"] is None and len(p["data"]) > 1:
                p["total"], merged["summed"] = summed_total(p["data"]), True
                if p["total"] is None:
                    raise SystemExit(f"Oregon (local offices): the county rows under {' '.join(key)} (page {p['page']}) have no Total row and "
                                     "do not line up in columns")
            f = finish(p, f"{' '.join(key)} (page {p['page']})", counties)
            ids = sorted(counties[fold(c)][0] for c in f["counties"])
            if merged["counties"] is not None and merged["counties"] != ids:
                raise SystemExit(f"Oregon (local offices): the continued section for {' '.join(key)} lists other counties")
            merged["counties"] = ids
            merged["cols"] += f["cols"]
            merged["misc"] += f["misc"]
            merged["pages"].append(p["page"])
        out[key] = merged
    return out, pages


def is_runoff(contest, names):
    """The abstract shows what the November list's "Nominated" says: no one elected, the two with the most votes marked as
    nominees, neither with more than half of the votes cast (Misc. included), and those two are the November names."""
    if not contest or len(names) != 2:
        return False
    cols = contest["cols"]
    stars = [c for c in cols if c["mark"] == "*"]
    by_votes = sorted(cols, key=lambda c: -c["votes"])
    total = sum(c["votes"] for c in cols) + contest["misc"]
    written = [clean(f"{c['given']} {c['family']}") for c in stars]
    return (len(stars) == 2 and not any(c["mark"] == "**" for c in cols) and all(c in stars for c in by_votes[:2])
            and (len(by_votes) < 3 or by_votes[2]["votes"] < by_votes[1]["votes"]) and by_votes[0]["votes"] * 2 <= total
            and all(sum(1 for w in written if names_fit(w, n)) == 1 for n in names)
            and all(sum(1 for n in names if names_fit(w, n)) == 1 for w in written))


def local_part(folder, rpath, info, counties, taken, say, refresh=False):
    """The District Attorney and Circuit Court contests on the November list, as rows for sl_races, sl_candidates,
    sl_places, sl_sources, sl_gaps and sl_notes, with what to report. taken: the state races' ids."""
    os.makedirs(folder, exist_ok=True)
    lists, lpath = read_local_lists(folder, say, refresh)
    may, pages = read_court_pages(rpath, counties)
    law, facts = judicial_districts(folder, counties, say)
    problems, remarks = [], []
    seen = collections.defaultdict(set)                    # judicial district -> the county lists the abstract prints under its positions
    for key, c in may.items():
        if key[0] == "JCC":
            seen[key[1]].add(tuple(c["counties"]))
    if law is None:
        problems.append(f"ORS 3.012 was not read ({facts['why']}); the judicial districts' counties come from the May 19 abstract alone")
    differ = sorted((d for d in seen if law is not None and seen[d] != {tuple(law.get(d, ()))}), key=int)
    for d in differ:
        problems.append(f"judicial district {d}: ORS 3.012 and the May 19 abstract name different counties")

    def district_counties(d):
        """(the county GEOIDs of judicial district d, None) or (None, why not)."""
        if len(seen.get(d, ())) > 1:
            return None, "the official results of the May 19 primary print different counties under this district's positions"
        observed = list(next(iter(seen[d]))) if seen.get(d) else None
        if law is None:
            return (observed, None) if observed else (None, "state law's list of judicial districts (ORS 3.012) could not be read and the "
                                                            "official results of the May 19 primary have no contest in this district")
        if d not in law:
            return None, "state law's list of judicial districts (ORS 3.012) has no district of this number"
        if observed is not None and observed != law[d]:
            return None, "state law (ORS 3.012) and the official results of the May 19 primary name different counties for this district"
        return law[d], None

    races, cands, places, gaps = [], [], {}, []
    by_kind, left, per_office, unread = collections.Counter(), collections.Counter(), {}, 0
    method = lambda r: re.sub(r"\s*\*+$", "", r["Filing Method"])          # "Auto Nominated **": the asterisks point to the page's footnote
    for code, o in lists["offices"].items():
        office, what = LOCAL[code], "position" if code == "JCC" else "office"
        per_office[office] = o["count"]
        named = sum(1 for x in o["left_off"] if x.get("withdrew"))
        left["withdrawn"] += max(o["withdrawn"], named)
        left["not qualified"] += sum(1 for x in o["left_off"] if x.get("Qualified") == "No")
        if o["both"]:
            problems.append(f"ORESTAR lists {o['both']} {office} filing(s) as both standing and withdrawn")
        if o["blanked"]:
            problems.append(f"{o['blanked']} cell(s) of the {office} rows looked like contact details and were blanked")
        rows_of = collections.defaultdict(list)
        for r in o["rows"]:
            rows_of[r["Contest"]].append(r)
        for label in o["contests"]:
            rows, ids, why, shape = rows_of.get(label, []), None, None, None
            if code == "JCC":
                m = POSITION.fullmatch(label)
                if m:
                    d, pos = str(int(m.group(1))), str(int(m.group(3)))
                    rid, key = f"2026-{STATE}-CC{d}-P{pos}", ("JCC", d, pos)
                    ids, why = district_counties(d)
                    shape = ("circuit_court", f"{m.group(1)}{m.group(2)} Judicial District", f"{STATE}-JD{d}", d, f"Position {pos}")
            else:
                m = re.fullmatch(r"(.+) County", label)
                hit = counties.get(fold(m.group(1))) if m else None
                if hit:
                    rid, key, ids = f"2026-{STATE}-DA-{hit[0]}", ("DA", hit[0]), [hit[0]]
                    shape = ("district_attorney", hit[1], hit[0], None, None)
            if shape is None:                                                  # a title the rules do not read: said, never guessed
                unread += 1
                problems.append(f"a {office} contest on the November list has a title that is not read; it is left out")
                gaps.append((STATE, "state", STATE, NAME, f"{office} contest {unread} on the list" if contact_like(label, True) else f"{office}, {label}",
                             "The Secretary of State's November list names this contest in words this loader does not read (a county for a "
                             "district attorney, a district and a position for a judge), so it is left out rather than guessed at.", SEARCH_PAGE))
                continue
            if rid in taken or any(r[0] == rid for r in races):
                raise SystemExit(f"Oregon (local offices): two contests share the race id {rid}")
            kind, jname, jid, district, seat = shape
            names, bad = [clean(r["Ballot Name"]) for r in rows], None
            if any(r["Office"] != f"{office}, {label}" for r in rows):
                bad = "its rows name another office than the contest they are listed under"
            elif not all(names):
                bad = "a candidate's name could not be read"
            elif len({nk(x) for x in names}) != len(names):
                bad = "one name is on it twice"
            elif any(r["Party"] != "Nonpartisan" for r in rows):
                bad = "it shows a party beside a candidate for this nonpartisan office"
            elif any(method(r) not in LOCAL_METHODS for r in rows):
                bad = "it files a candidate by a method this loader does not read"
            elif any(x.get("Contest") == label and x.get("Qualified") != "No" for x in o["left_off"]):
                bad = "one of its filings has a status that is neither qualified nor not qualified"
            notes, in_may, methods = [], may.get(key), {method(r) for r in rows}
            if bad:
                n = len(rows)
                problems.append(f"{rid}: the November list's rows are not read ({bad}); the race is kept with no candidate")
                notes.append(f"The Secretary of State's list has {n} candidate row{'s' if n != 1 else ''} for this {what}, but {bad}; the "
                             "candidates are left out here rather than guessed at.")
                gaps.append((STATE, "race", rid, jname, "the candidates for this contest",
                             f"The Secretary of State's November list has {n} candidate row{'s' if n != 1 else ''} for this contest, but {bad}, "
                             "so the candidates are left out here rather than guessed at.", SEARCH_PAGE))
                rows, names = [], []
            elif not rows:
                notes.append(NO_CANDIDATE.format(what=what))
            elif methods == {"Nominated"}:
                if is_runoff(in_may, names):
                    notes.append(RUNOFF.format(what=what))
                else:
                    problems.append(f"{rid}: filed as nominated, but the May 19 abstract does not show these candidates as its two nominees "
                                    "short of a majority")
                    notes.append(NOMINATED_ONLY.format(what=what))
            elif methods <= {"Fee", "Completed Petitions"} and in_may is None:
                notes.append(FILED.format(what=what))
            elif methods == {"Auto Nominated"} and in_may is None:
                notes.append(AUTO)
            else:
                remarks.append(f"{rid}: filing methods {', '.join(sorted(methods))}, {'on' if in_may else 'not on'} the May 19 abstract; no "
                               "sentence is written on why it is on the November ballot")
            if ids is None:
                problems.append(f"{rid}: no county list ({why})")
                gaps.append((STATE, "race", rid, jname, "the counties this judicial district covers",
                             f"This race is shown without its counties because {why}.", ORS_CHAPTER_3))
            elif code == "JCC":
                places[jid] = ("judicial", jid, jname, json.dumps(ids), SRC["districts"] if law is not None else SRC["local_results"])
            races.append((rid, STATE, "court", kind, office, jname, jid, json.dumps(ids) if ids else None, district, seat, 0, 0, None, None,
                          None, GENERAL, " ".join(notes + [NO_ORDER])))
            by_kind[kind] += 1
            for name in names:
                cands.append({"race_id": rid, "election": "general", "election_date": GENERAL, "name": name, "party": "Nonpartisan office",
                              "party_code": "N", "ballot_order": None, "incumbent": 0, "write_in": 0, "votes": None, "pct": None,
                              "outcome": None, "state_member_id": None, "source_id": SRC["local_list"], "note": None})

    # ---- the control: every qualified filing on the list is one candidate in exactly one race, unless its race says why not
    placed = collections.Counter(c["race_id"] for c in cands)
    qualified = sum(len(o["rows"]) for o in lists["offices"].values())
    set_aside = qualified - len(cands)
    if len({(c["race_id"], c["name"]) for c in cands}) != len(cands):
        raise SystemExit("Oregon (local offices): two candidate rows share a race and a name")
    if set_aside and not any(g[1] in ("race", "state") for g in gaps):
        raise SystemExit(f"Oregon (local offices): {set_aside} qualified filings are in no race and no gap says why")

    # ---- what is not loaded: every county's own contests
    for geoid, full in sorted(counties.values()):
        gaps.append((STATE, "county", geoid, full, "county, city and district contests",
                     f"Not loaded yet: {full}'s county, city and district candidates are not on the Secretary of State's list, which holds only "
                     "the offices filed with the state; the county clerk, who prepares the county's ballot, publishes them, and that list has "
                     "not been read here yet.", CLERKS_PAGE))

    plural = lambda n, word: f"{n} {word}{'s' if n != 1 else ''}"
    off = sum(left.values())
    coverage = (f"Loaded from the Secretary of State's candidate list for November 3, and shown with the judges: "
                f"{plural(by_kind['district_attorney'], 'district attorney contest')} and {plural(by_kind['circuit_court'], 'circuit judge position')}, "
                f"with {plural(len(cands), 'candidate')}" + (f" ({plural(off, 'filing')} not qualified or withdrawn left off)" if off else "")
                + ". These are the only local offices filed with the state. County commissioner, sheriff, clerk, treasurer, city, soil and "
                "water district and utility district contests are not loaded yet for any of Oregon's 36 counties, and each county says so. "
                "Ballot measures and the May primaries for these offices are not loaded.")
    notes = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, ORS_INDEX),
             (STATE, "local_coverage", coverage, "Oregon Secretary of State, Elections Division: candidate filings for the 2026 General Election",
              SEARCH_PAGE)]

    hashes = [h for o in lists["offices"].values() for h in o["page_sha256"]]
    counts = ", ".join(f"{k} {v}" for k, v in per_office.items())
    contests = sum(len(o["contests"]) for o in lists["offices"].values())
    summed = sum(1 for c in may.values() if c["summed"])
    abstract_note = ("The abstract has no Judge of the Circuit Court or District Attorney page." if not pages else
                     f"Pages {pages[0]} to {pages[-1]} of the abstract the state rows are read from: each contest's heading, its county rows "
                     "(which must add up to its Total row"
                     + (f"; {summed} contest{'s' if summed != 1 else ''} of several counties printed without a Total row had the county rows "
                        "added up instead" if summed else "")
                     + ") and the marks beside the names (* nominee, ** elected). Used to check which counties vote on a judicial district's "
                     "positions and whether a November contest was on the May ballot; no primary rows are stored for these offices.")
    sources = [
        source_row(SRC["local_list"], "official candidate list", AGENCY,
                   "ORESTAR Candidate Filings: 2026 General Election, District Attorney and Judge of the Circuit Court",
                   SEARCH_PAGE, "", lists.get("fetched") or day_of(lpath), hashlib.sha256("".join(hashes).encode()).hexdigest(),
                   sum(per_office.values()),
                   "Read through the search page's own form (with its anti-forgery token) by two routes: every filing for each office, and "
                   f"contest by contest through the page's own menu ({contests} contests); the two readings give the same rows and the page's "
                   f"own counts ({counts}). A third search by withdrawal date counts withdrawn filings. Ballot name, party, office, election, "
                   "filing method and Qualified only: the grid has no contact columns, the filing date is not read, and the Export file, the "
                   "printable report and the filings' detail pages are never fetched. Left off and counted, never named: "
                   f"{left['not qualified']} not qualified, {left['withdrawn']} withdrawn. The list gives no ballot order. The pages are not "
                   f"kept: the sha256 here is of the {len(hashes)} pages' own hashes joined."),
        source_row(SRC["local_results"], "official results", AGENCY,
                   "2026 May Primary Election Official Results (May 19, 2026, Primary Election Abstract of Votes): Judge of the Circuit Court "
                   "and District Attorney",
                   info["url"], info.get("published", ""), day_of(rpath), sha_file(rpath), len(may), abstract_note),
    ]
    if law is not None:
        sources.append(source_row(
            SRC["districts"], "statute", LEGISLATURE,
            f"Oregon Revised Statutes{', ' + facts['edition'] + ' edition' if facts['edition'] else ''}, chapter 3: ORS 3.012, Judicial districts",
            ORS_CHAPTER_3, "", day_of(facts["path"]), sha_file(facts["path"]), len(law),
            f"The counties of each of the {len(law)} judicial districts, from the statute's own sentences; together they hold each of the 36 "
            f"counties once. Checked against the county rows the May 19 abstract prints under the positions of {len(seen)} districts: "
            + (f"districts {', '.join(differ)} differ." if differ else "all agree.")))
    reached = sorted({c for r in races for c in json.loads(r[7] or "[]")})
    return {"races": races, "cands": cands, "places": list(places.values()), "sources": sources, "gaps": gaps, "notes": notes,
            "problems": problems, "remarks": remarks, "by_kind": dict(by_kind), "left": dict(left), "per_office": per_office,
            "reached": reached, "placed": dict(placed), "qualified": qualified, "fetched": lists.get("fetched", "")}


# ---------------------------------------------------------------- load

def source_row(source_id, kind, agency, title, url, published, fetched, sha256, rows, note):
    return (source_id, STATE, kind, agency, title, url, published or "", fetched or "", sha256 or "", rows, note)


def load(db_path, say=print, cache=DEFAULT_CACHE, roster_path=ROSTER, refresh=False):
    net.patient_lookups()
    folder = cache
    os.makedirs(folder, exist_ok=True)
    lists, lpath = read_lists(folder, say, refresh)
    rpath, info = fed.results_pdf(folder)                    # the file (and record) the federal loader already keeps
    s2024 = results_2024(folder, say)
    counties = county_names()
    members, officials, roster_as_of = roster(roster_path)
    gen, pri, key = lists["general"], lists["primary"], lists["parties"]
    party_names = set(key.values())
    problems, notes_out = [], []

    # ---- the seats on the November ballot: ORESTAR's own district lists for the 2026 General Election
    races = collections.OrderedDict()

    def add_race(rid, kind, district):
        if rid in races:
            return races[rid]
        if kind == "GOV":
            r = {"race_id": rid, "level": "statewide", "office_kind": "governor", "office": "Governor", "jurisdiction": NAME,
                 "jurisdiction_id": FIPS, "district": None, "chamber": None}
        else:
            senate = kind == "SS"
            r = {"race_id": rid, "level": "legislature", "office_kind": "state_senate" if senate else "state_house",
                 "office": "State Senator" if senate else "State Representative",
                 "jurisdiction": f"{'Senate' if senate else 'House'} District {district}", "jurisdiction_id": district,
                 "district": district, "chamber": "Senate" if senate else "House"}
        r.update({"special": 0, "notes": [], "county_ids": None})
        races[rid] = r
        return r

    for code, labels in gen["districts"].items():
        for label in labels:
            if code == "GOV":
                if label != "statewide":
                    raise SystemExit(f"Oregon (state races): ORESTAR lists Governor under {label!r}")
                add_race(f"2026-{STATE}-GOV", "GOV", None)
                continue
            m = ORD.fullmatch(label)
            if not m or not label.endswith("District"):
                raise SystemExit(f"Oregon (state races): an ORESTAR district label that is not read ({label!r})")
            k = "SS" if code == "SS" else "SH"
            add_race(f"2026-{STATE}-{k}{int(m.group(1))}", k, str(int(m.group(1))))
    senate_2026 = sorted((r["district"] for r in races.values() if r["office_kind"] == "state_senate"), key=int)
    house_2026 = sorted((r["district"] for r in races.values() if r["office_kind"] == "state_house"), key=int)
    if house_2026 != [str(i) for i in range(1, 61)]:
        problems.append(f"the November list's House districts are not the sixty ({len(house_2026)} listed)")
    again = sorted(set(senate_2026) & set(s2024["districts"]), key=int)
    halves = not again and sorted(set(senate_2026) | set(s2024["districts"]), key=int) == [str(i) for i in range(1, 31)]
    if not halves and not again:
        problems.append(f"the 2026 Senate seats ({', '.join(senate_2026)}) and 2024's ({', '.join(s2024['districts'])}) are not the thirty")
    for d in again:
        races[f"2026-{STATE}-SS{d}"]["special"] = 1
        races[f"2026-{STATE}-SS{d}"]["notes"].append("This seat was also elected in 2024 for four years; the 2026 election fills the rest "
                                                     "of that term.")
    for r in races.values():
        if r["office_kind"] == "state_senate" and not r["special"]:
            r["notes"].append("Oregon senators serve four years; " + (
                f"{len(senate_2026)} of the thirty seats are elected in 2026, the other {len(s2024['districts'])} were elected in 2024."
                if halves else "this seat was not on the November 2024 ballot."))
        if r["office_kind"] == "governor":
            r["notes"].append("Oregon has no lieutenant governor.")

    # ---- the November ballot: one row per candidate, every nominating party in the order filed
    by_cand, off, nominated, wi_filings = collections.OrderedDict(), [], {}, []
    for r in gen["rows"]:
        rid, _kind, _district = race_of(r["Office"])
        if rid not in races:
            raise SystemExit(f"Oregon (state races): a filing for {r['Office']} names a seat not on ORESTAR's district list")
        name, party = clean(r["Ballot Name"]), r["Party"]
        if party not in party_names:
            raise SystemExit(f"Oregon (state races): the general list names a party not in ORESTAR's party key ({party!r})")
        if r["Qualified"] == "No":
            off.append(f"{name} ({party}, {rid}, not qualified)")
            continue
        if r["Qualified"] != "Yes":
            raise SystemExit(f"Oregon (state races): a Qualified value on the general list that is not read ({r['Qualified']!r})")
        if r["Filing Method"] not in METHODS_GENERAL:
            raise SystemExit(f"Oregon (state races): a filing method on the general list that is not read ({r['Filing Method']!r})")
        if r["Filing Method"] in ("Nominated", "Write In"):              # the primary's nominee, by printed name or write-in votes
            if (rid, party) in nominated:
                raise SystemExit(f"Oregon (state races): the general list names two {party} nominees for {rid}")
            nominated[(rid, party)] = name
            if r["Filing Method"] == "Write In":
                wi_filings.append((rid, name, party))
        c = by_cand.setdefault((rid, nk(name)), {"race": rid, "name": name, "filings": []})
        if c["name"] != name:
            raise SystemExit(f"Oregon (state races): one candidate's ballot name differs between filings ({c['name']!r}, {name!r})")
        c["filings"].append((us_date(r["Filing Date"]), party, r["Filing Method"]))
    withdrawn_gen = [f"{clean(r['Ballot Name'])} ({r['Party']}, {race_of(r['Office'])[0]}, withdrew)" for r in gen["withdrawn"]]
    for kind in (gen, pri):
        filing = lambda r: (nk(r["Ballot Name"]), r["Office"], r["Party"])
        both = {filing(r) for r in kind["rows"]} & {filing(r) for r in kind["withdrawn"]}
        if both:
            problems.append(f"ORESTAR lists {len(both)} filing(s) as both standing and withdrawn in the {kind['election']}")

    # ---- the May 19 primary: ORESTAR's primary list and the official abstract
    ballot, not_qualified, declared_wi = collections.defaultdict(dict), [], []
    for r in pri["rows"]:
        rid, _k, _d = race_of(r["Office"])
        name, party = clean(r["Ballot Name"]), r["Party"]
        if r["Qualified"] == "No":
            not_qualified.append(f"{name} ({party}, {rid})")
            continue
        if r["Qualified"] != "Yes" or r["Filing Method"] not in METHODS_PRIMARY:
            raise SystemExit(f"Oregon (state races): a primary filing that is not read ({r['Qualified']!r}, {r['Filing Method']!r}, {rid})")
        if r["Filing Method"] == "Write In":
            declared_wi.append(f"{name} ({party}, {rid})")
            continue
        ballot[(rid, party)][nk(name)] = name
    withdrew_pri = [f"{clean(r['Ballot Name'])} ({r['Party']}, {race_of(r['Office'])[0]})" for r in pri["withdrawn"]]

    contests, decided = read_abstract(rpath, party_names, counties)
    for (rid, party) in sorted(set(ballot) - set(contests)):
        problems.append(f"{rid} {party}: qualified primary filings but no contest in the official results")
    fields, primary_rows, wi_nominees, cands = 0, 0, [], []
    for (rid, party), f in sorted(contests.items()):
        if rid not in races:
            problems.append(f"{rid} {party}: a primary contest for a seat not on the November list")
            continue
        r = races[rid]
        if r["level"] == "legislature":
            ids = sorted({counties[fold(c)][0] for c in f["counties"]})
            if r["county_ids"] is None:
                r["county_ids"] = ids
            elif r["county_ids"] != ids:
                problems.append(f"{rid}: the party sections of the official results list different counties")
        filed = ballot.get((rid, party), {})
        shown, printed = [], 0
        for col in f["cols"]:
            written = clean(f"{col['given']} {col['family']}")
            if col["wi"]:
                shown.append(written)
                continue
            hit = nk(written) if nk(written) in filed else None
            if hit is None:
                hits = [k for k in filed if names_fit(written, filed[k])]
                if len(hits) != 1:
                    raise SystemExit(f"Oregon (state races): {written} ({rid} {party}) in the official results is not on the primary list")
                hit = hits[0]
            shown.append(filed[hit])
            printed += 1
        if sorted(nk(n) for n, c in zip(shown, f["cols"]) if not c["wi"]) != sorted(filed):
            problems.append(f"{rid} {party}: the official results' printed names are not the primary list's")
        marked = [i for i, c in enumerate(f["cols"]) if c["mark"] == "*"]
        if any(c["mark"] == "**" for c in f["cols"]):
            problems.append(f"{rid} {party}: a partisan contest marks someone ** Elected")
        votes = [c["votes"] for c in f["cols"]]
        top = votes.index(max(votes)) if votes else None
        if len(marked) > 1 or (marked and (marked[0] != top or votes.count(votes[top]) > 1)) or (votes and not marked):
            problems.append(f"{rid} {party}: the nominee marked * is not the one top vote-getter")
        nominee = marked[0] if len(marked) == 1 else None
        if nominee is not None:
            if f["cols"][nominee]["wi"]:
                wi_nominees.append((rid, shown[nominee], party))
            got = nominated.get((rid, party))
            if got is None:
                gone = any(race_of(w["Office"])[0] == rid and w["Party"] == party and names_fit(clean(w["Ballot Name"]), shown[nominee])
                           for w in gen["withdrawn"])
                how = "withdrew" if gone else "is not on the November list as its nominee"
                notes_out.append(f"{rid}: {shown[nominee]} won the {party} nomination on May 19 and {how}")
                others = [c["name"] for (rr, _k), c in by_cand.items() if rr == rid and any(p == party for _d, p, _m in c["filings"])]
                r["notes"].append(f"{shown[nominee]} won the {party} nomination at the May 19 primary"
                                  + (" with write-in votes" if f["cols"][nominee]["wi"] else "") + f" and {how}; "
                                  + (f"the {party} candidate on the November list is {', '.join(others)}." if others
                                     else f"no {party} candidate is on the November list."))
            elif not names_fit(got, shown[nominee]):
                notes_out.append(f"{rid}: the {party} nominee on the November list ({got}) is not the May 19 winner ({shown[nominee]})")
        if printed < 2:
            continue
        fields += 1
        total = sum(votes) + f["misc"]
        code = CODES.get(party) or next((c for c, p in key.items() if p == party), None)
        if not code:
            raise SystemExit(f"Oregon (state races): no code for the party {party!r}")
        for i in sorted(range(len(shown)), key=lambda i: -votes[i]):
            cands.append({"race_id": rid, "election": f"primary-{code}", "election_date": PRIMARY, "name": shown[i], "party": party,
                          "party_code": pcode(party), "ballot_order": None, "incumbent": 0, "write_in": int(f["cols"][i]["wi"]),
                          "votes": votes[i], "pct": round(100 * votes[i] / total, 1) if total else None,
                          "outcome": "advanced" if i == nominee else "lost", "state_member_id": None, "source_id": SRC["results"],
                          "note": WRITE_IN if f["cols"][i]["wi"] else None})
            primary_rows += 1
    for r in races.values():
        if r["county_ids"] is None and r["level"] == "legislature":
            notes_out.append(f"{r['race_id']}: no party section in the official results, so no county list")

    # ---- November rows
    gen_rows, count = [], collections.Counter()
    for (rid, _fk), c in by_cand.items():
        filings = sorted(c["filings"], key=lambda f: f[0])
        parties = [p for _d, p, _m in filings]
        if len(set(parties)) != len(parties):
            raise SystemExit(f"Oregon (state races): {c['name']} has two filings for one party for {rid}")
        notes = []
        if len(parties) > 1:
            notes.append(f"Nominated by more than one party; Oregon's list has a filing for each ({', then '.join(parties)}), "
                         "and the parties are shown in the order the nominations were filed.")
        won = [p for _d, p, m in filings if m == "Write In"]
        if won:
            notes.append(f"Won the {' and '.join(won)} nomination with write-in votes at the May 19 primary; the name is printed "
                         "under that party in November.")
        if "Independent" in parties:
            notes.append(INDEPENDENT)
        count[rid] += 1
        gen_rows.append({"race_id": rid, "election": "general", "election_date": GENERAL, "name": c["name"], "party": ", ".join(parties),
                         "party_code": pcode(parties[0]), "ballot_order": None, "incumbent": 0, "write_in": 0, "votes": None,
                         "pct": None, "outcome": None, "state_member_id": None, "source_id": SRC["general"],
                         "note": " ".join(notes) or None})
    for rid, n, p in wi_filings:
        if not any(rr == rid and pp == p and names_fit(nn, n) for rr, nn, pp in wi_nominees):
            problems.append(f"{rid}: {n}'s {p} filing is marked Write In, but the abstract has no {p} write-in nominee of that name")

    # ---- holders and incumbents
    incumbents = 0
    for r in races.values():
        if r["chamber"]:
            hold = [m for m in members if m["chamber"] == r["chamber"] and m["district"] == r["district"]]
        else:
            hold = [o for o in officials if o["office"] == "governor"]
        r["holder"] = hold
        if not hold:
            r["notes"].append("The roster used here lists no one holding this seat today.")
            continue
        mine = [g for g in gen_rows if g["race_id"] == r["race_id"]]
        for h in hold:
            hits = [g for g in mine if person_fits(g["name"], h)]
            if len(hits) == 1 and sum(1 for hh in hold if person_fits(hits[0]["name"], hh)) == 1:
                hits[0]["incumbent"], hits[0]["state_member_id"] = 1, h["id"]
                incumbents += 1

    # ---- checks
    for rid, r in races.items():
        if not count[rid]:
            problems.append(f"{rid}: no candidate on the November list")
    uncontested = [rid for rid in races if count[rid] == 1]
    listed = sum(len(c["filings"]) for c in by_cand.values())
    qualified = sum(1 for r in gen["rows"] if r["Qualified"] == "Yes")
    if listed != qualified:
        problems.append(f"{listed} filings kept against {qualified} qualified on the November list")
    for code in OFFICES:
        n = gen["counts"].get(code, 0)
        got = sum(1 for r in gen["rows"] if race_of(r["Office"])[1] == {"GOV": "GOV", "SS": "SS", "SR": "SH"}[code])
        if n != got:
            problems.append(f"the November list counts {n} {OFFICES[code]} filings; {got} were read")
    for d in decided:
        if d["runoff"]:
            problems.append(f"{d['office']} {d['position']}: the official results name nominees for November ({', '.join(d['runoff'])}), not loaded")

    # ---- the county and judicial-district offices on the same list (district attorneys, circuit judges), and what is not loaded
    local = local_part(os.path.join(folder, "local"), rpath, info, counties, set(races), say, refresh)
    for office, n in gen["not_loaded"].items():
        if local["per_office"].get(office, 0) != n:
            notes_out.append(f"the November list counted {n} {office} filings when the state rows were read ({lists.get('fetched') or day_of(lpath)}) "
                             f"and {local['per_office'].get(office, 0)} when the local rows were ({local['fetched']})")

    # ---- rows
    race_rows = []
    for r in races.values():
        hold = r["holder"]
        race_rows.append((r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                          json.dumps(r["county_ids"]) if r["county_ids"] else None, r["district"], None, r["special"], 1,
                          "; ".join(h["id"] for h in hold) or None, "; ".join(h["full"] or f"{h['first']} {h['last']}" for h in hold) or None,
                          "; ".join(h["party"] or "" for h in hold) or None, GENERAL, " ".join(r["notes"] + [NO_ORDER]) or None))
    ccols = ("race_id", "election", "election_date", "name", "party", "party_code", "ballot_order", "incumbent", "write_in", "votes",
             "pct", "outcome", "state_member_id", "source_id", "note")
    all_cands = gen_rows + cands
    keys = [(c["race_id"], c["election"], c["name"]) for c in all_cands]
    if len(set(keys)) != len(keys):
        raise SystemExit("Oregon (state races): two candidate rows share a race, election and name")
    place_rows = [("county", geoid, full, json.dumps([geoid]), SRC["county"]) for geoid, full in sorted(counties.values())]
    for r in races.values():
        if r["level"] == "legislature" and r["county_ids"]:
            place_rows.append(("senate" if r["office_kind"] == "state_senate" else "house", f"OR-{r['district']}", r["jurisdiction"],      # state-prefixed: sl_places is shared by every state
                               json.dumps(r["county_ids"]), SRC["results"]))
    decided_words = "; ".join(f"{d['office']}{' ' + d['position'] if d['position'] else ''} ({', '.join(d['elected']) or 'no one'} elected)"
                              for d in decided)
    fusion = sum(1 for g in gen_rows if "," in (g["party"] or ""))
    sources = [
        source_row(SRC["general"], "official candidate list", AGENCY,
                   "ORESTAR Candidate Filings: 2026 General Election, Governor, State Senator and State Representative",
                   SEARCH_PAGE, "", lists.get("fetched") or day_of(lpath), sha_file(lpath), len(gen["rows"]),
                   "Read through the search page's own form (with its anti-forgery token), every filing for each office with disqualified "
                   f"filings included, and again by withdrawal date; the page's counts checked ({', '.join(f'{k} {v}' for k, v in gen['counts'].items())}); "
                   f"asked district by district: {', '.join(gen['by_district']) or 'none'}. Ballot name, party, office, election, filing method, "
                   "filing date and Qualified only; the Export file, the printable report and the filings' detail pages are never fetched. One "
                   f"row per candidate: a candidate nominated by several parties has a filing for each ({fusion} such candidates). The list "
                   f"gives no ballot order. Left off: {'; '.join(off + withdrawn_gen) or 'none'}. Nominations won with write-in votes in May "
                   f"(filing method Write In, each checked against the abstract): {'; '.join(f'{n} ({p}, {rid})' for rid, n, p in wi_filings) or 'none'}. "
                   f"The list's county and judicial-district offices ({'; '.join(f'{k}, {v} filings' for k, v in gen['not_loaded'].items()) or 'none'} "
                   f"when this was read) are loaded from a reading of their own: see {SRC['local_list']}. "
                   "Congress is left to the federal loader."),
        source_row(SRC["primary"], "official candidate list", AGENCY,
                   "ORESTAR Candidate Filings: 2026 Primary Election, Governor, State Senator and State Representative",
                   SEARCH_PAGE, "", lists.get("fetched") or day_of(lpath), sha_file(lpath), len(pri["rows"]),
                   "Used to check the official results (every name printed under a party's contest is that party's qualified filing, and "
                   "the other way round) and for the ballot names on the primary rows. "
                   f"Not qualified: {'; '.join(not_qualified) or 'none'}. Withdrawn before the primary: {'; '.join(withdrew_pri) or 'none'}. "
                   f"Declared write-ins: {'; '.join(declared_wi) or 'none'}."),
        source_row(SRC["results"], "official results", AGENCY,
                   "2026 May Primary Election Official Results (May 19, 2026, Primary Election Abstract of Votes): state offices",
                   info["url"], info.get("published", ""), day_of(rpath), sha_file(rpath), primary_rows,
                   f"Linked as Official Results from the Election History page ({HISTORY_PAGE}); record viewer {info['record']}. "
                   f"{len(contests)} party contests for Governor and the Legislature read; every column's county rows add up to its Total "
                   "(a one-county district's county row is its total). A field's total is its candidates' votes plus Misc. (votes for names "
                   "not printed and not nominated). Write-in nominees, marked (WI), are named as the abstract writes them. The counties each "
                   "district reaches are the abstract's county rows. Decided on May 19 and not on the November ballot: "
                   f"{decided_words or 'none'}."),
        source_row(SRC["senate2024"], "official results", AGENCY,
                   "November 5, 2024, General Election Abstract of Votes: State Senator (district headings only)",
                   s2024["url"], RESULTS_2024["date"], day_of(s2024["path"]), sha_file(s2024["path"]), len(s2024["districts"]),
                   f"Linked as Official Results of November General from the Election History page; record viewer {s2024['record']}. Only the "
                   f"district headings of the State Senator pages ({', '.join(map(str, s2024['pages']))}) are read: the seats elected in 2024 "
                   f"({', '.join(s2024['districts'])}). The 2026 list's Senate seats ({', '.join(senate_2026)}) "
                   + ("are the other fifteen, so none fills the rest of a term." if not again else f"include {', '.join(again)}, also elected in 2024 (special).")),
        source_row(SRC["county"], "official place names", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)",
                   COUNTY_URL, "", day_of(COUNTY_ZIP), sha_file(COUNTY_ZIP), len(counties), "Oregon's 36 counties: names and GEOIDs only."),
    ]
    if members or officials:
        sources.append(source_row(SRC["roster"], "roster", "Open States (people project, CC0)",
                                  "Legislators serving now and statewide officials (state_or.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", roster_as_of, day_of(roster_path), sha_file(roster_path),
                                  len(members) + len(officials),
                                  "Used only to say who holds each seat today and to mark incumbents: ids, names, parties and districts. "
                                  "Not an official record."))

    # ---- the local rows beside them: nothing that looks like contact details goes in (a candidate's name was checked when read)
    for table, key, texts in ([("sl_races", r[0], (r[4], r[5], r[8], r[9], r[16])) for r in local["races"]]
                              + [("sl_candidates", c["race_id"], (c["name"],)) for c in local["cands"]]
                              + [("sl_places", p[1], (p[2],)) for p in local["places"]]):
        if any(t and contact_like(t, True) for t in texts):
            raise SystemExit(f"Oregon (local offices): a text for {table} {key} looks like contact details; nothing is written")
    for table, key, texts in ([("sl_gaps", f"{g[1]} {g[2]}", g[3:6]) for g in local["gaps"]] + [("sl_notes", n[1], n[2:4]) for n in local["notes"]]):
        if any(t and contact_like(t, False) for t in texts):
            raise SystemExit(f"Oregon (local offices): a text for {table} {key} looks like a web address or contact details; nothing is written")
    race_rows += local["races"]
    all_cands += local["cands"]
    place_rows += local["places"]
    sources += local["sources"]
    if len({r[0] for r in race_rows}) != len(race_rows) or len({(c["race_id"], c["election"], c["name"]) for c in all_cands}) != len(all_cands):
        raise SystemExit("Oregon: a local row repeats a state row's key")

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA + EXTRA_SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'or-%'")
            con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany(f"INSERT INTO sl_candidates VALUES ({','.join('?' * len(ccols))})", [tuple(c[k] for k in ccols) for c in all_cands])
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
            con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
            con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    finally:
        con.close()

    by_kind = collections.Counter(r["office_kind"] for r in races.values())
    gen_by_kind = collections.Counter(races[g["race_id"]]["office_kind"] for g in gen_rows)
    say(f"    Oregon: {len(races)} state races on the November ballot (Governor {by_kind['governor']}, Senate {by_kind['state_senate']}, "
        f"House {by_kind['state_house']}), {len(gen_rows)} candidates ({fusion} nominated by more than one party, {len(wi_filings)} "
        f"nominations won by write-in votes, {len(off) + len(withdrawn_gen)} left off); {fields} primary fields with official votes ({primary_rows} rows); "
        f"{incumbents} incumbents marked; {len(uncontested)} races with one candidate")
    lk, gap_scopes = local["by_kind"], collections.Counter(g[1] for g in local["gaps"])
    aside = local["qualified"] - len(local["cands"])
    say(f"    Oregon (local offices on the state's list): {len(local['races'])} contests filed under courts (district attorney "
        f"{lk.get('district_attorney', 0)}, circuit judge {lk.get('circuit_court', 0)}) with {len(local['cands'])} candidates, reaching "
        f"{len(local['reached'])} of the 36 counties; {local['qualified']} qualified filings on the list, "
        f"{'each in one race' if not aside else f'{aside} of them set aside (see the gaps)'}; left off: "
        f"{', '.join(f'{v} {k}' for k, v in local['left'].items()) or 'none'}; gaps: "
        f"{', '.join(f'{k} {v}' for k, v in sorted(gap_scopes.items()))} (every county's own county, city and district contests are not loaded)")
    problems += local["problems"]
    notes_out += local["remarks"]
    for p in problems:
        say(f"      CHECK {p}")
    for n in notes_out:
        say(f"      note: {n}")
    return {"races": len(races), "candidates": len(gen_rows), "by_kind": dict(by_kind), "general_by_kind": dict(gen_by_kind),
            "fields": fields, "primary_rows": primary_rows, "incumbents": incumbents, "problems": problems, "notes": notes_out,
            "uncontested": uncontested, "decided": decided, "wi_nominations": wi_filings, "left_off": off + withdrawn_gen,
            "not_loaded": gen["not_loaded"], "senate_2026": senate_2026, "senate_2024": s2024["districts"],
            "local": {"races": len(local["races"]), "candidates": len(local["cands"]), "by_kind": lk, "left_off": local["left"],
                      "counties": local["reached"], "gaps": dict(gap_scopes), "qualified": local["qualified"], "placed": local["placed"]}}


def pcode(party):
    """A one-letter code for colour only; Nonaffiliated (no party) is coloured as no party."""
    return "I" if party == "Nonaffiliated" else party_code(party)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache, refresh = DEFAULT_CACHE, "--refresh" in args
    args = [a for a in args if a != "--refresh"]
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_or.py <database file> [--cache <folder>] [--refresh]")
    load(args[0], cache=cache, refresh=refresh)
