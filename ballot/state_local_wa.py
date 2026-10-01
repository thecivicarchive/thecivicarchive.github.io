"""
ballot/state_local_wa.py - Washington's state races on the November 3, 2026 ballot: the 24 State Senate seats whose
four-year terms end this year, all 98 seats of the House of Representatives (two in each of the 49 legislative
districts, Position 1 and Position 2), and the appellate court seats on the list (five Justice of the Supreme Court
positions and eight Court of Appeals positions, all nonpartisan), with the August 4 top-two primary and its certified
votes. Washington elects its Governor and the other statewide executive officers in presidential years (2028 next),
so no statewide executive office is on the 2026 ballot; the federal rows (U.S. Representative) are left to
ballot/lists/wa.py and the federal database, which is never opened here.

Sources, all the Secretary of State's own:
  - The candidate lists on voter.votewa.gov: "GENERAL 2026 Candidate List" (election 899) and "PRIMARY 2026 Candidate
    List" (election 898), the same Telerik grids the federal loader reads, every page read through the grid's own pager
    and the rows counted against the grid's own "items" figure. Columns are found by their headings and only these
    cells are ever turned into text: District Type, District, Race, Term Type, Term Length, Name, Party Preference,
    Status, Election Status and Ballot Order. The grid also carries Mailing Address, Email, Phone and Filing Date; those
    cells are never read, printed or kept, and the pages themselves are never saved: only the kept cells of the state
    rows go to ballot_cache/wa/sl_wa_2026_<general|primary>_state.json, with each page's SHA-256 and a count (no
    names) of the other offices' rows. A Withdrawn candidate is left off and counted; any other status stops the loader.
  - The certified results of the August 4, 2026 primary: the "All Results Excel" workbook the federal loader finds
    through the results site's own election record (results.votewa.gov) and caches as
    ballot_cache/wa/wa_2026_primary_all_results.xlsx; only its State Senator, State Representative, Supreme Court and
    Court of Appeals contests are read (office, candidate, party preference, votes). Every candidate's county rows
    ("Precinct Results") must add up to the statewide total ("Summary Results").
  - The Secretary of State's results exports of the November 5, 2024 and November 8, 2022 general elections
    (results.vote.wa.gov/results/<date>/export/<date>_AllState.csv: race, candidate, party, votes, percentage and
    jurisdiction only). 2022 and 2024 together show which Senate seats were elected when (a 2022 seat's four-year term
    ends in January 2027); 2024 shows who won each House position, which the Open States roster does not record.
  - Who holds each seat today: the Open States roster in state_wa.sqlite (legislators, is_current = 1, by chamber and
    district; only ids, names, party, chamber and district are selected). The roster carries no House position and no
    judges. A House position's holder is the 2024 winner of that position when that winner still sits for the
    district; otherwise the district's one other sitting representative, when the other position's holder is known
    (Zach Hall, appointed in 2025 to the Position 1 seat Victoria Hunt won in 2024). Courts show no holder.

Washington's primary is top-two: every candidate, of every party preference, is on one primary ballot, and the two with
the most votes advance whatever their parties (a tie for second advances everyone tied); Supreme Court and Court of
Appeals races work the same way, and an office with no more than two candidates skips the primary (the primary list
marks them "Advanced to General"). So the one primary field is election "primary" (as on the federal side), shown only
where two or more candidates were on the August ballot. The party shown is the candidate's own stated preference as
the ballot and results print it, without parentheses ("Prefers Democratic Party", "States No Party Preference"); it is
not a party's nomination. party_code is D or R only for "Prefers Democratic/Democrat Party" and "Prefers Republican/GOP
Party", L and G for Libertarian and Green, I for Independent and no party preference, O for anything else (Labor
Democrat, Cascade Democrat and the like are O, not D). Nonpartisan courts are "Nonpartisan office", code N.

Controls: each list's rows = its own count; the primary field is exactly the primary list's Active candidates for the
race; everyone on the general list advanced from the primary (top two with ties); each candidate's party preference
agrees between the results and both lists; county rows add up; the Senate seats on the list are exactly the 2022 seats
and none of the 2024 ones, 49 in all; the House list has all 98 positions. Every mismatch is reported, never patched.

County and local contests (John, 2026-09-30)
--------------------------------------------
The same GENERAL 2026 Candidate List carries every county, city and district office with a candidate on the November
ballot, but the whole list does not say which county a row belongs to ("County", "Prosecuting Attorney"). So the list
is read once more county by county, through its own county menu (the address ending &c=<two-digit code>, 39 counties),
with the same reader and the same ten cells; a view that fits on one page shows no count, so its rows are counted. The
kept cells of the rows that are neither the state's nor Congress's go to ballot_cache/wa/local/
wa_2026_general_local_<all|code>.json, with each page's SHA-256; no page is kept. The whole list is the control: every
county or local row on it must be on at least one county's view, and no view may carry a row it lacks (the two write a
district in different capitals, so rows are compared without regard to capitals). A contest that reaches several
counties (a superior court for three counties, a public utility district that crosses a county line, the King County
district court's Southeast Electoral District, on Pierce County's list too) is one contest with every such county in
county_ids.

Each county types its own titles ("COUNTY COMMISSIONER #03", "Commissioner Dist. No. 3", "District 3"), so a contest is
read by rules, never by position, and anything the rules cannot read is stored in the list's own words and reported:
  - county offices (District Type Countywide, County, Commissioner, Council): level county, the county's FIPS code.
    Assessor, auditor, clerk, coroner, prosecuting attorney, sheriff, treasurer, commissioner, council member, and two
    charter offices (King's Director of Elections, Clallam's Director of Community Development). A commissioner's or
    council member's number is kept as the list words it (District 3, No. 3). Where the list files the contest under
    the county, the number is the seat (the whole county votes in November, RCW 36.32.050); where it files it under
    the numbered district itself (King, Pierce, Clark, Spokane, Franklin, Yakima), it is the district, and the note
    says so. A title that is only "District 3" (Jefferson) is read from the Secretary of State's November 2022 results
    export for that county, which names the seat ("Jefferson Commissioner, District 3"); the note says so.
  - judges: level court, with county_ids, as Minnesota's district judges are: superior_court (four unexpired terms),
    district_court (a county's court, or the part of it the list names: King's electoral districts, Snohomish's four
    courts) and municipal_court (Seattle, Tacoma). A county clerk titled "Clerk of Superior Court" is a county office.
  - cities (City/Town, City Council): level city, named and keyed from the Census Bureau's 2020 place codes when the
    list's name fits exactly one incorporated place ("Seattle city", WA-M-63000); otherwise the list's words and a key
    of county code and name.
  - other districts (Public Utility, Port, Fire): level other. The list gives no district numbers, and a district's
    words differ by county ("PUD ALL", "Benton County PUD", "Public Utility District (ALL)"): the county's own name and
    the words that only say the whole district votes are set aside (pud_name), and the name is followed by the county
    or counties whose lists carry it: "Public Utility District No. 1 (Island and Snohomish counties)". The key is
    WA-X-<county codes>-<name>. Nothing says which county a district that crosses a line belongs to, so none is named.
A contest is partisan when its candidates show a party preference on the list (RCW 29A.04.110: county offices, unless a
county's charter says otherwise); the list writes a preference short and in capitals (DEMOCRATIC), stored as a ballot
words it ("Prefers Democratic Party") in ordinary capitals. Judges and district offices are "Nonpartisan office", N.
Ballot order is the list's own; where a district's candidates are numbered across its contests no order is stored.
Term Type "Unexpired" is special = 1; "Short & Full" and "Initial Full" are said in the note. Local primaries are not
loaded. Local candidates are never matched to the roster: no holder, no incumbent mark, no link.
Also written: sl_places (the 39 counties from the Census county file; each city and district a contest names),
sl_gaps (what the list cannot show) and sl_notes (local_calendar, local_coverage).

Privacy: only office, district, candidate name, party preference, ballot order, status and votes are read. No address,
city, ZIP code, phone, website, e-mail, filing date or treasurer is read, printed, logged, cached or stored; no photos,
ages, websites, biographies or money reach the database.

    python -m ballot.state_local_wa <path to a test database>
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
import urllib.parse
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import openpyxl  # noqa: E402

from ballot.check_local import EXTRA_SCHEMA  # noqa: E402
from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import wa as W  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE = "WA"
GENERAL, PRIMARY = "2026-11-03", W.PRIMARY
ROSTER = os.path.join(HERE, "state_wa.sqlite")
LISTS = {"general": ("899", "GENERAL 2026"), "primary": ("898", "PRIMARY 2026")}
LIST_FILE = "sl_wa_2026_{}_state.json"
PAST = {"2024": ("20241105", "November 5, 2024"), "2022": ("20221108", "November 8, 2022")}
PAST_URL = "https://results.vote.wa.gov/results/{0}/export/{0}_AllState.csv"
PAST_FILE = "wa_{}_general_results_allstate.csv"
SRC_GEN, SRC_PRI, SRC_RES = "wa-sos-2026-state-general-list", "wa-sos-2026-state-primary-list", "wa-sos-2026-state-primary-results"
SRC_PAST = {"2024": "wa-sos-2024-general-results", "2022": "wa-sos-2022-general-results"}
SRC_ROSTER = "wa-openstates-roster"
SCAN_SRC = {"wa-sos-2026-certification": "wa-sos-2026-state-certification", "wa-sos-2026-primary-canvass": "wa-sos-2026-state-primary-canvass"}

# Only these cells of a grid row are ever turned into text.
KEEP = ("District Type", "District", "Race", "Term Type", "Term Length", "Name", "Party Preference", "Status", "Election Status",
        "Ballot Order")
SENATE_SEATS, DISTRICTS = 49, 49
NONPARTISAN = "Nonpartisan office"
VIEW_FILE = "wa_2026_general_local_{}.json"                    # in ballot_cache/wa/local/: "all", or a county's list code
COUNTY_MENU = "ctl00$ContentPlaceHolder1$ddlCounty"
FIPS = "53"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st53_wa_place2020.txt"
PLACE_FILE = "census_st53_wa_place2020.txt"
PAST_COUNTY_URL = "https://results.vote.wa.gov/results/20221108/export/20221108_{}.csv"
PAST_COUNTY_FILE = "wa_2022_general_results_{}.csv"
RCW = "https://app.leg.wa.gov/RCW/default.aspx?cite="
SRC_ALL, SRC_VIEW = "wa-sos-2026-local-general-list-all", "wa-sos-2026-local-general-list-c{}"
SRC_COUNTIES, SRC_PLACES, SRC_PAST_COUNTY = "wa-census-2024-counties", "wa-census-2020-places", "wa-sos-2022-general-results-{}"
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")

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

TOP_TWO = ("Washington's primary is top-two: every candidate was on one August 4 ballot and the two with the most votes advanced, "
           "whatever their parties. The party shown is the candidate's own stated preference as the ballot prints it, not a party's "
           "nomination.")
SENATE_NOTE = ("Washington senators serve four-year terms, and about half the Senate is elected every two years. This district's "
               "seat was elected for a four-year term in November 2022 (the Secretary of State's results), a term that ends in January 2027.")
HOUSE_NOTE = ("Each legislative district elects two representatives, Position 1 and Position 2, both for two-year terms, so every "
              "House seat is on the ballot every even year.")
SHORT_FULL = ("The Secretary of State's list gives this race as \"Short & Full\": the winner also serves the rest of the present "
              "term, not only the full two-year term that begins in January 2027.")
COURT_NOTE = ("A nonpartisan office: no party is printed on the ballot. The Open States roster does not carry judges, so no holder "
              "is shown.")
SKIPPED_PRIMARY = ("With no more than two candidates filed, this office was not on the August primary ballot; the primary list marks "
                   "its candidates \"Advanced to General\".")
COURT_TOP_TWO = "The two with the most votes in the August 4 primary advanced."
ORDER_NOTE = "Ballot order as the Secretary of State's general election list gives it."


# ------------------------------------------------------------------------------------------------ fetching and caching

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def ask(req, say):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            if isinstance(req, str):
                return net.get(req, accept="text/html")
            with urlopen(req, timeout=120) as r:
                return r.read()
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      voter.votewa.gov: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def text(cell):
    return W.text(cell)


def grid_rows(page):
    """The kept cells of every row of one page of the grid, found by the headings; no other cell is turned into text."""
    heads = [text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
        raise SystemExit(f"Washington: the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {heads.index(k): k for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        row, n = {}, 0
        for n, m in enumerate(re.finditer(r"<td[^>]*>(.*?)</td>", tr, re.S), start=1):
            if n - 1 in idx:
                row[idx[n - 1]] = text(m.group(1))
        if n != len(heads):
            raise SystemExit("Washington: a grid row does not line up with the grid's headings")
        yield row


def state_row(r):
    """True for a row this loader keeps: the Legislature, the Supreme Court and the Court of Appeals."""
    t = r["District Type"].strip().upper()
    if t == "LEGISLATIVE":
        return True
    if t == "JUDICIAL":
        d = r["District"].strip().lower()
        return d == "supreme court" or d.startswith("court of appeals")
    return False


def read_list(kind, folder, say, max_age_days=2):
    """The kept cells of the state rows of one list, every page read; cached (kept cells only) for two days."""
    path = os.path.join(folder, LIST_FILE.format(kind))
    if fresh(path, max_age_days):
        return path, json.load(open(path, encoding="utf-8"))
    eid, title = LISTS[kind]
    url = W.LIST_URL + eid
    try:
        raw = ask(url, say)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the {title} list could not be read ({e}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        raise
    page = raw.decode("utf-8", "replace")
    hashes = [hashlib.sha256(raw).hexdigest()]
    if not re.search(rf"<title>\s*{title} Candidate List\s*</title>", page):
        raise SystemExit(f"Washington: {url} is no longer the {title} Candidate List (a challenge page? nothing is read)")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    if not m:
        raise SystemExit(f"Washington: the {title} list no longer shows its row count")
    items, pages = int(m.group(1)), int(m.group(2))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'<input type="(submit|button)" name="([^"]+)" value=" " (?:onclick="javascript:__doPostBack\(&#39;([^&]+)&#39;,'
                        r'&#39;&#39;\)" )?title="Next Page" class="rgPageNext" />', page)
        if not nxt:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has no Next Page button")
        fields = W.form(page)
        if nxt.group(1) == "submit":
            fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(2): " "})
        elif nxt.group(3):
            fields.update({"__EVENTTARGET": nxt.group(3), "__EVENTARGUMENT": ""})
        else:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has a Next Page button that is not read")
        time.sleep(2)
        req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        raw = ask(req, say)
        page = raw.decode("utf-8", "replace")
        hashes.append(hashlib.sha256(raw).hexdigest())
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Washington: asked for page {n} of the {title} list and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Washington: the {title} list counts {items} rows; {len(rows)} were read")
    kept = [r for r in rows if state_row(r)]
    other = collections.Counter(r["District Type"].strip().upper() for r in rows if not state_row(r))
    keep = {"title": title, "url": url, "read": dt.date.today().isoformat(), "items": items, "pages": pages, "page_sha256": hashes,
            "rows": kept, "other": dict(sorted(other.items()))}
    os.makedirs(folder, exist_ok=True)
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {title} Candidate List: {items} rows on {pages} pages, {len(kept)} for the Legislature and the appellate courts")
    return path, keep


def past_results(year, folder, say):
    """[(race, candidate, votes)] for the Legislature from one past general election's statewide export (race, candidate,
    party, votes, percentage and jurisdiction are all the file has)."""
    date, _words = PAST[year]
    path = os.path.join(folder, PAST_FILE.format(year))
    net.download(PAST_URL.format(date), path, max_age_days=365, say=say)
    raw = open(path, "rb").read()
    if raw.lstrip()[:1] == b"<":
        raise SystemExit(f"Washington: {os.path.basename(path)} is a web page, not the results export; delete it and run again")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not {"Race", "Candidate", "Votes"} <= set(reader.fieldnames or []):
        raise SystemExit(f"Washington: the {year} results export's columns changed ({reader.fieldnames})")
    out = []
    for r in reader:
        race = r["Race"].strip()
        if re.search(r"legislative district", race, re.I):
            out.append((race, r["Candidate"].strip(), int(r["Votes"] or 0)))
    return path, out


# ------------------------------------------------------------------------------------- the local rows, county by county

_REFUSED = []      # filled once the list's site refuses a request (403, 429) after its retries; it is then not asked again in this run


def federal_row(r):
    return r["District Type"].strip().upper() == "CONGRESSIONAL"


def read_view(code, folder, say, max_age_days=2):
    """The kept cells of the local rows of one view of the GENERAL 2026 Candidate List: the whole list (code "all") or one
    county's (its two-digit code in the list's own county menu, the address ending &c=<code>). Every page is read through
    the grid's own pager and the rows are counted against the grid's own "items" figure where it shows one (a view that
    fits on one page shows none). Nothing of a page is kept but the kept cells of the rows that are neither the state's nor
    Congress's, a count of those, and each page's SHA-256: ballot_cache/wa/local/wa_2026_general_local_<code>.json."""
    path = os.path.join(folder, VIEW_FILE.format(code))
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    title = LISTS["general"][1]
    if not _REFUSED:
        try:
            keep = fetch_view(code, say)
        except (HTTPError, OSError) as e:
            if isinstance(e, HTTPError) and e.code in (403, 429):
                _REFUSED.append(e.code)                    # refused after its two more tries: the host is not asked again in this run
            if not os.path.exists(path):
                raise
            say(f"      the {title} list ({code}) could not be read ({e}); using the copy read earlier")
        else:
            os.makedirs(folder, exist_ok=True)
            tmp = path + ".part"
            json.dump(keep, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, path)
            time.sleep(2)
            return keep
    if os.path.exists(path):
        if len(_REFUSED) == 1:
            say("      the candidate list's site refused the reader; it is not asked again in this run, and the copies read earlier are used")
            _REFUSED.append(0)                             # said once
        return json.load(open(path, encoding="utf-8"))
    raise SystemExit(f"Washington: the candidate list's site refused the reader earlier in this run, so it is not asked again; there is no "
                     f"earlier copy of the {title} list ({code})")


def fetch_view(code, say):
    """One view of the GENERAL 2026 list, every page, cut down in memory to what read_view keeps."""
    eid, title = LISTS["general"]
    url = W.LIST_URL + eid + ("" if code == "all" else "&c=" + code)
    raw = ask(url, say)
    page = raw.decode("utf-8", "replace")
    hashes = [hashlib.sha256(raw).hexdigest()]
    if not re.search(rf"<title>\s*{title} Candidate List\s*</title>", page):
        raise SystemExit(f"Washington: {url} is no longer the {title} Candidate List (a challenge page? nothing is read)")
    menu = re.search(rf'<select[^>]*name="{re.escape(COUNTY_MENU)}"[^>]*>(.*?)</select>', page, re.S)
    if not menu:
        raise SystemExit(f"Washington: the {title} list no longer has its county menu")
    options = {v: text(lbl) for v, lbl in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', menu.group(1), re.S)}
    chosen = re.search(r'<option selected="selected" value="([^"]*)"', menu.group(1))
    chosen = chosen.group(1) if chosen else ""
    if chosen != ("" if code == "all" else code):
        raise SystemExit(f"Washington: asked the {title} list for county code {code!r}; the page shows {chosen!r}")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    items, pages = (int(m.group(1)), int(m.group(2))) if m else (None, 1)
    if not m and re.search(r'class="rgPageNext"', page):
        raise SystemExit(f"Washington: the {title} list ({code}) has a pager but no row count")
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'<input type="(submit|button)" name="([^"]+)" value=" " (?:onclick="javascript:__doPostBack\(&#39;([^&]+)&#39;,'
                        r'&#39;&#39;\)" )?title="Next Page" class="rgPageNext" />', page)
        if not nxt:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list ({code}) has no Next Page button")
        fields = W.form(page)
        if nxt.group(1) == "submit":
            fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(2): " "})
        elif nxt.group(3):
            fields.update({"__EVENTTARGET": nxt.group(3), "__EVENTARGUMENT": ""})
        else:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list ({code}) has a Next Page button that is not read")
        time.sleep(2)
        req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        raw = ask(req, say)
        page = raw.decode("utf-8", "replace")
        hashes.append(hashlib.sha256(raw).hexdigest())
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Washington: asked for page {n} of the {title} list ({code}) and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if items is not None and len(rows) != items:
        raise SystemExit(f"Washington: the {title} list ({code}) counts {items} rows; {len(rows)} were read")
    if items is None and len(rows) > 100:
        raise SystemExit(f"Washington: the {title} list ({code}) gave {len(rows)} rows on one page, more than a page holds")
    kept = [r for r in rows if not state_row(r) and not federal_row(r)]
    return {"code": code, "county": options.get(code) if code != "all" else None, "menu": options if code == "all" else None,
            "title": title, "url": url, "read": dt.date.today().isoformat(), "items": len(rows), "counted": items is not None,
            "pages": pages, "page_sha256": hashes, "rows": kept, "state_rows": sum(1 for r in rows if state_row(r)),
            "federal_rows": sum(1 for r in rows if federal_row(r))}


TOP_TWO_LOCAL = "Top-two primary: the party shown is each candidate's own stated preference."
ORDER_ODD = "The list numbers this district's candidates across its contests, so no ballot position is given here."
YEARS = {"1": "one year", "2": "two years", "3": "three years", "4": "four years", "5": "five years", "6": "six years"}
SMALL_WORDS, KEPT_CAPITALS = {"OF", "AND", "THE", "FOR", "IN"}, {"PUD", "GOP", "II", "III", "IV"}

# A county office's title on the list, lower case, once the county's name and the word "County" are taken off its front.
COUNTY_OFFICES = {
    "assessor": ("county_assessor", "County Assessor"),
    "auditor": ("county_auditor", "County Auditor"),
    "clerk": ("county_clerk", "County Clerk"),
    "clerk of superior court": ("county_clerk", "County Clerk"),
    "coroner": ("coroner", "County Coroner"),
    "prosecuting attorney": ("county_attorney", "Prosecuting Attorney"),
    "prosecutor": ("county_attorney", "Prosecuting Attorney"),
    "sheriff": ("sheriff", "County Sheriff"),
    "treasurer": ("county_treasurer", "County Treasurer"),
    "director of elections": ("county_elections_director", "Director of Elections"),
    "director of community development": ("county_community_development_director", "Director of Community Development"),
}
COUNTY_TYPES = ("COUNTYWIDE", "COUNTY", "COMMISSIONER", "COUNCIL")
CITY_TYPES = ("CITY/TOWN", "CITY COUNCIL")
# The District Type of a district that is not a county, a city or a court: level, office kind, office, place kind, id letter.
DISTRICT_TYPES = {
    "PUBLIC UTILITY": ("other", "utility_board", "Public Utility District Commissioner", "special", "X"),
    "PORT": ("other", "port_board", "Port Commissioner", "special", "X"),
    "FIRE": ("other", "fire_board", "Fire Commissioner", "special", "X"),
    "SCHOOL": ("school", "school_board", "School Director", "school", "S"),
    "HOSPITAL": ("hospital", "hospital_board", "Hospital District Commissioner", "hospital", "H"),
}
WHOLE_COURT = ("COUNTY", "DISTRICT COURT", "DISTRICT COURT JUDGE", "DISTRICT COURT JUDGES", "COURT DISTRICT")
SEAT = re.compile(r"^(?P<res>residency\s+)?(?P<w>district|dist|position|postion|pos|department|dept)?\.?\s*(?:no\.?|#)?\s*0*"
                  r"(?P<n>\d+|[A-Za-z](?![A-Za-z]))\s*(?P<rest>.*)$", re.I)
SEAT_WORD = {"district": "District", "dist": "District", "position": "Position", "postion": "Position", "pos": "Position",
             "department": "Department", "dept": "Department"}


def squeeze(text):
    return re.sub(r"\s+", " ", text or "").strip()


def plain(text):
    """The list's own words in ordinary capitals: a word typed all in capitals keeps one capital (PUD stays, small words go
    lower); a word typed in mixed case is kept as typed."""
    out = []
    for i, word in enumerate(squeeze(text).split(" ")):
        parts = []
        for p in re.split(r"([-/])", word):
            letters = re.sub(r"[^A-Za-z]", "", p)
            if len(letters) >= 2 and letters.isupper() and letters not in KEPT_CAPITALS:
                p = p.lower()
                if not (letters in SMALL_WORDS and i):
                    j = next(k for k, ch in enumerate(p) if ch.isalpha())
                    p = p[:j] + p[j].upper() + p[j + 1:]
            parts.append(p)
        out.append("".join(parts))
    return " ".join(out)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def county_words(names):
    """'King County'; 'King and Pierce counties'; 'Ferry, Pend Oreille and Stevens counties'."""
    if len(names) == 1:
        return f"{names[0]} County"
    return f"{', '.join(names[:-1])} and {names[-1]} counties"


def local_party(listed):
    """The list writes a party preference short and in capitals (DEMOCRATIC, STATES NO PARTY PREFERENCE); it is stored the
    way a ballot words it and the state rows already carry it: 'Prefers Democratic Party', 'States No Party Preference'."""
    w = squeeze(listed)
    if w.upper() in ("STATES NO PARTY PREFERENCE", "NO PARTY PREFERENCE"):
        return "States No Party Preference"
    return f"Prefers {plain(w)} Party"


def designator(text):
    """What tells one seat of an office from another, as the list words it, evened out: 'Dist. No. 3' -> ('District 3',
    '3', ''); 'Pos. 2' -> ('Position 2', '2', ''); 'DEPARTMENT NO. 1' -> ('Department 1', '1', ''); '#03', 'No. 3', '(3)'
    and '3' -> ('No. 3', '3', ''); 'Dist #B AL' -> ('District B', 'B', 'AL'); 'Full Time' -> ('Full Time', None, '').
    Returns (seat words, its number or letter, any words left over)."""
    t = squeeze(re.sub(r"[()]", " ", text or "")).strip(" ,;:-")
    if not t:
        return None, None, ""
    m = SEAT.match(t)
    if not m:
        return plain(t), None, ""
    n = m.group("n").upper()
    label = ("Residency " if m.group("res") else "") + SEAT_WORD.get((m.group("w") or "").lower(), "No.")
    if m.group("res") and not m.group("w"):
        return plain(t), None, ""
    return f"{label} {n}", n, m.group("rest").strip(" ,;:-")


def strip_words(text, names, pattern):
    """A contest title with the words that name its office (the pattern) and its place (the names) taken out."""
    t = re.sub(pattern, " ", text, flags=re.I)
    for n in names:
        t = re.sub(rf"\b{re.escape(n)}\b", " ", t, flags=re.I)
    return squeeze(t)


def city_of(words):
    """('Seattle', None) from 'City of Seattle'; ('Seattle', '5') from 'SEATTLE CITY COUNCIL DISTRICT 5'; else (None, None)."""
    d = squeeze(words)
    m = re.fullmatch(r"(?i)(?:the )?(?:city|town) of (.+)", d)
    if m:
        return m.group(1).strip(), None
    m = re.fullmatch(r"(?i)(.+?) (?:city|town) council district (?:no\.? ?|# ?)?0*(\d+)", d)
    if m:
        return m.group(1).strip(), m.group(2)
    return None, None


def pud_name(words, counties):
    """A public utility district as the list words it, evened out. The lists call the same kind of district 'PUD ALL',
    'Benton County PUD', 'Public Utility District (ALL)', 'PUBLIC UTILITY DISTRICT NO. 1': the county's own name and the
    words that only say the whole district votes (ALL, COUNTYWIDE, AT-LARGE) are set aside; a number written straight
    after 'Public Utility District' is kept as 'No. n'. 'PUD DISTRICT 2' is kept as it is, because the list does not say
    whether 2 is the district's number or a commissioner district inside it. Anything else is the list's own words."""
    t = re.sub(r"[()]", " ", squeeze(words).upper())
    t = re.sub(r"\bDISTRICT-AT-LARGE\b|\bAT[- ]LARGE\b|\bCOUNTYWIDE\b|\bALL\b", " ", t)
    for c in counties:
        t = re.sub(rf"\b{re.escape(c.upper())}\b", " ", t)
    t = squeeze(re.sub(r"\bCOUNTY\b", " ", t))
    if re.fullmatch(r"(?:PUD|PUBLIC UTILITY DIST(?:RICT)?)(?: DISTRICT)?", t):
        return "Public Utility District"
    m = re.fullmatch(r"PUBLIC UTILITY DIST(?:RICT)? (?:NO\. ?|# ?)?0*(\d+)", t) or re.fullmatch(r"PUD (?:NO\. ?|# ?)0*(\d+)", t)
    if m:
        return f"Public Utility District No. {m.group(1)}"
    m = re.fullmatch(r"PUD DISTRICT (?:NO\. ?|# ?)?0*(\d+)", t)
    if m:
        return f"PUD District {m.group(1)}"
    return plain(words)


def term_note(term, length):
    """(special, a sentence or None) for the list's Term Type and Term Length."""
    years = YEARS.get(length)
    if term == "Regular":
        return 0, (f"A regular term of {years} on the list." if years and length not in ("4", "6") else None)
    if term == "Short & Full":
        return 0, "Short and full term: the winner also serves the rest of the current term."
    if term == "Unexpired":
        return 1, (f"For the rest of a term: {years} on the list." if years else "For the rest of a term.")
    if term == "Initial Full":
        return 0, "On the list as an \"Initial Full\" term" + (f" of {years}." if years else ".")
    return 0, f"On the list as a \"{term}\" term."


def county_table(path=COUNTY_ZIP):
    """{folded county name: (five-digit code, 'Adams County')} for Washington's 39 counties, from the Census Bureau's
    cartographic county file the kit already has (names and codes only)."""
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
    if len(out) != 39:
        raise SystemExit(f"Washington: the Census county file gives {len(out)} counties, not 39")
    return out


def census_places(folder, say):
    """(path, {folded name without its kind word: [(place code, 'Seattle city')]}) for Washington's incorporated places,
    from the Census Bureau's 2020 place codes file (places only, no people; cached whole)."""
    path = os.path.join(folder, PLACE_FILE)
    net.download(PLACE_URL, path, max_age_days=3650, say=say)
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    if not lines or lines[0].split("|")[:6] != ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE"]:
        raise SystemExit(f"Washington: {PLACE_FILE} does not begin with the Census place codes heading; delete it and run again")
    out = collections.defaultdict(list)
    for line in lines[1:]:
        f = line.split("|")
        if len(f) >= 6 and f[1] == FIPS and f[5] == "INCORPORATED PLACE" and re.fullmatch(r"\d{5}", f[2]):
            out[fold(re.sub(r"\s+(?:city|town)$", "", f[4]))].append((f[2], f[4]))
    return path, out


def past_office(county, n, folder, say):
    """(path, address, title, rows in the file) of the one race in a county's November 2022 results export that names a
    commissioner or council seat for district n, for a seat the 2026 list titles only 'District n'; title None when there
    is not exactly one. The export holds race, candidate, party, votes, percentage and jurisdiction (no contact columns,
    so it is cached whole); only the race titles are read."""
    path = os.path.join(folder, PAST_COUNTY_FILE.format(slug(county)))
    url = PAST_COUNTY_URL.format(county.replace(" ", ""))
    try:
        net.download(url, path, max_age_days=3650, tries=3, say=say)
        raw = open(path, "rb").read()
    except (HTTPError, OSError):
        return None, url, None, 0
    if raw.lstrip()[:1] == b"<":
        return None, url, None, 0
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    if "Race" not in (reader.fieldnames or []):
        return path, url, None, 0
    races = [squeeze(r["Race"]) for r in reader]
    hits = [t for t in sorted(set(races))
            if re.fullmatch(rf"(?:{re.escape(county)} )?(?:County )?(?:Commissioner|Council(?:or| Member|member)?),? District (?:No\. ?)?0*{n}", t, re.I)]
    return path, url, (hits[0] if len(hits) == 1 else None), len(races)


def row_key(r):
    """One candidacy, whatever capitals a view writes its district in (the same row shows 'Council' on one view and
    'COUNCIL' on another)."""
    return (squeeze(r["District Type"]).upper(), squeeze(r["District"]).upper(), squeeze(r["Race"]).casefold(), squeeze(r["Term Type"]),
            squeeze(r["Term Length"]), squeeze(r["Name"]), squeeze(r["Party Preference"]).upper(), squeeze(r["Status"]),
            squeeze(r["Ballot Order"]))


def load_local(folder, say):
    """The county and local contests of the GENERAL 2026 list, read county by county. Returns a dict: races (sl_races
    rows as dicts), cands (sl_candidates rows), places, sources, gaps, notes (rows for those tables), report (lines for the
    run) and a few counts."""
    os.makedirs(folder, exist_ok=True)
    ctable = county_table()
    ppath, by_name = census_places(folder, say)
    whole = read_view("all", folder, say)
    menu = whole.get("menu") or {}
    codes = {c: label for c, label in menu.items() if fold(label) in ctable}
    others = sorted(label for c, label in menu.items() if c not in codes and label)
    if len(codes) != 39 or len({fold(v) for v in codes.values()}) != 39 or others != ["State"]:
        raise SystemExit("Washington: the list's county menu is no longer the 39 counties and 'State'; nothing is read")
    views = {c: read_view(c, folder, say) for c in sorted(codes)}
    fips = {c: ctable[fold(label)][0] for c, label in codes.items()}
    lsad = {c: ctable[fold(label)][1] for c, label in codes.items()}
    short = {c: re.sub(r"\s+County$", "", lsad[c]) for c in codes}
    report, extra_src = [], {}

    # ---- every county or local row of the whole list is on some county's view, and nothing else is
    where, first = collections.defaultdict(list), collections.OrderedDict()
    for c in sorted(views):
        seen = set()
        for r in views[c]["rows"]:
            k = row_key(r)
            if k in seen:
                raise SystemExit(f"Washington: {lsad[c]}'s view of the list carries one candidacy twice ({squeeze(r['Race'])})")
            seen.add(k)
            where[k].append(c)
            first.setdefault(k, r)
    wk = collections.Counter(row_key(r) for r in whole["rows"])
    lost = sorted({(k[1], k[2]) for k in wk if k not in where})
    stray = sorted({(k[1], k[2]) for k in where if k not in wk})
    control = not lost and not stray and all(v == 1 for v in wk.values())
    if whole["items"] != len(whole["rows"]) + whole["state_rows"] + whole["federal_rows"]:
        raise SystemExit("Washington: the whole list's rows do not add up to its own count")
    if lost:
        report.append(f"{sum(1 for k in wk if k not in where)} county or local rows of the whole list are on no county's view: {lost[:6]}")
    if stray:
        report.append(f"{sum(1 for k in where if k not in wk)} rows on a county's view are not on the whole list: {stray[:6]}")
    if any(v > 1 for v in wk.values()):
        report.append(f"{sum(1 for v in wk.values() if v > 1)} county or local rows are on the whole list twice")

    contests = collections.OrderedDict()
    for k, r in first.items():
        contests.setdefault((tuple(where[k]),) + k[:5], []).append(r)

    races, cands, places, unread, gone, gaps = collections.OrderedDict(), [], {}, [], [], []
    placed = skipped = 0

    def city_place(city, dwords, cs):
        hits = by_name.get(fold(city), []) if city else []
        if len(hits) == 1:
            return hits[0][1], f"{STATE}-M-{hits[0][0]}", SRC_PLACES
        # the name fits no one incorporated place on the Census Bureau's list: the list's own words, keyed by county and name
        report.append(f"a city or town on the list fits no one place on the Census Bureau's list ({plain(dwords)}); named in the list's own words")
        return (f"{plain(dwords)} ({county_words([short[c] for c in cs])})", f"{STATE}-M-{'-'.join(fips[c][2:] for c in cs)}-{slug(plain(dwords))}",
                SRC_ALL)

    def classify(dtype, dwords, race, cs):
        """One contest's office and place from the list's District Type, District and Race, or None when it cannot be told."""
        names, c3 = [short[c] for c in cs], [fips[c][2:] for c in cs]
        d_up = dwords.upper()
        x = dict(district=None, seat=None, notes=[], pkind=None, psrc=SRC_ALL)

        def seat_of(rest):
            words, n, left = designator(rest)
            if left:
                x["notes"].append(f"The list titles this contest \"{race}\".")
            return words, n

        # ---- judges: superior, district and municipal courts (a county clerk can be titled "Clerk of Superior Court")
        if dtype in ("JUDICIAL", "DISTRICT COURT") or (re.search(r"\b(?:district|municipal|superior) court\b", race, re.I)
                                                       and not re.search(r"\bclerk\b", race, re.I)):
            if re.search(r"\bmunicipal court\b", race, re.I):
                city, _sub = city_of(dwords)
                jname, jid, x["psrc"] = city_place(city, dwords, cs)
                seat, _n = seat_of(strip_words(race, [city] if city else [], r"\bmunicipal\s+court\b|\bjudges?\b"))
                x.update(level="court", kind="municipal_court", office="Municipal Court Judge", jname=jname, jid=jid, pkind="mcd", seat=seat)
                return x
            if re.search(r"\bsuperior court\b", dwords + " " + race, re.I):
                named = sorted(fold(n) for n in re.split(r",|\band\b", re.sub(r"(?i)\s*superior court.*$", "", dwords)) if n.strip())
                if named != sorted(fold(n) for n in names):
                    report.append(f"{plain(dwords)}: the counties it names are not the counties whose views carry it ({', '.join(names)})")
                seat, _n = seat_of(strip_words(race, names, r"\bsuperior\s+court\b|\bjudges?\b|\bcounty\b"))
                x.update(level="court", kind="superior_court", office="Superior Court Judge", jname=plain(dwords), jid="SUP-" + "-".join(c3), seat=seat)
                return x
            if dtype == "DISTRICT COURT" or re.search(r"\bdistrict court\b", dwords + " " + race, re.I):
                if len(cs) == 1 and d_up in WHOLE_COURT + (lsad[cs[0]].upper(),):
                    jname, jid = f"{lsad[cs[0]]} District Court", f"DC-{c3[0]}"
                else:                                                            # a part of a county's court, in the list's own words
                    part = re.sub(r"^Court\s*-\s*", "District Court, ", plain(dwords))      # 'Court - North District'
                    jname, jid = f"{part} ({county_words(names)})", "DC-" + "-".join(c3) + "-" + slug(plain(dwords))
                rest = strip_words(race, names, r"\bdistrict\s+court\b|\bjudges?\b|\bcounty\b")
                own = {w.casefold() for w in re.findall(r"[A-Za-z]+", dwords)}      # words that only repeat the district's name
                rest = " ".join(w for w in rest.split() if not re.sub(r"[^A-Za-z]", "", w) or re.sub(r"[^A-Za-z]", "", w).casefold() not in own)
                seat, n = seat_of(rest)
                tail = re.search(r"(\d+)\s*$", dwords)
                if seat and n and tail and tail.group(1).lstrip("0") == n and seat == f"No. {n}":
                    seat = None                                                  # 'Judge - District Court 1' of 'District Court 1'
                x.update(level="court", kind="district_court", office="District Court Judge", jname=jname, jid=jid, seat=seat)
                return x
            unread.append((dtype, dwords, race))
            x.update(level="court", kind="other", office=plain(race), jname=f"{plain(dwords)} ({county_words(names)})",
                     jid="CT-" + "-".join(c3) + "-" + slug(plain(dwords)))
            return x

        # ---- county offices
        if dtype in COUNTY_TYPES:
            if len(cs) != 1:
                return None
            c = cs[0]
            x.update(level="county", jname=lsad[c], jid=fips[c], pkind="county", psrc=SRC_COUNTIES)
            core = squeeze(re.sub(r"^county\s+", "", re.sub(rf"^{re.escape(short[c])}\s+", "", re.sub(r"^metropolitan\s+", "", race, flags=re.I),
                                                              flags=re.I), flags=re.I))
            whole_county = d_up in ("COUNTY", lsad[c].upper()) or "ALL COUNTY" in d_up
            if core.casefold() in COUNTY_OFFICES:
                x["kind"], x["office"] = COUNTY_OFFICES[core.casefold()]
                if not whole_county:
                    x["notes"].append(f"The list files this contest under \"{plain(dwords)}\".")
                    report.append(f"{lsad[c]}: {x['office']} is filed under {plain(dwords)!r}, not the county")
                return x
            m = re.match(r"(?i)commissioner\b(.*)$", core)
            m2 = re.match(r"(?i)council(?:or|member|\s+member)?\b(.*)$", core)
            m3 = re.fullmatch(r"(?i)district\s+(?:no\.?\s*|#\s*)?0*(\d+)", core)
            if m:
                x["kind"], x["office"], rest = "county_commissioner", "County Commissioner", m.group(1)
            elif m2:
                x["kind"], rest = "county_council", m2.group(1)
                x["office"] = "County Councilor" if re.match(r"(?i)councilor", core) else "County Council Member"
            elif m3:
                path, url, title, n_rows = past_office(short[c], m3.group(1), folder, say)
                if not title:
                    unread.append((dtype, dwords, race))
                    x.update(kind="other", office=plain(race))
                    return x
                council = bool(re.search(r"(?i)council", title))
                x["kind"], x["office"] = ("county_council", "County Council Member") if council else ("county_commissioner", "County Commissioner")
                x["notes"].append(f"The list titles this contest only \"{race}\"; the Secretary of State's November 2022 results call the "
                                  f"seat \"{title}\".")
                extra_src[SRC_PAST_COUNTY.format(slug(short[c]))] = (path, url, short[c], n_rows)
                rest = core
            else:
                unread.append((dtype, dwords, race))
                x.update(kind="other", office=plain(race))
                return x
            words, n = seat_of(rest)
            tail = re.search(r"(\d+)\s*$", d_up)
            if whole_county:
                x["seat"] = words
            elif n and tail and tail.group(1).lstrip("0") == n and re.search(r"\bDISTRICT\b", d_up):
                x["district"] = n
                x["notes"].append(f"Filed on the list under {plain(dwords)}, not the county as a whole.")
            else:
                x["seat"] = words
                x["notes"].append(f"The list files this contest under \"{plain(dwords)}\".")
                report.append(f"{lsad[c]}: {x['office']} {words or ''} is filed under {plain(dwords)!r}; who votes on it is not read from that")
            return x

        # ---- city and town offices
        if dtype in CITY_TYPES or dtype.startswith(("CITY", "TOWN")):
            city, sub = city_of(dwords)
            jname, jid, x["psrc"] = city_place(city, dwords, cs)
            x.update(level="city", jname=jname, jid=jid, pkind="mcd")
            core = strip_words(race, [city] if city else [], r"^\s*city\b")
            m = re.match(r"(?i)council(?:or|member|\s+member)?\b(.*)$", core)
            if core.casefold() == "mayor":
                x.update(kind="mayor", office="Mayor")
            elif m:
                x.update(kind="council", office="Council Member")
                words, n = seat_of(m.group(1))
                if sub and n == sub:
                    x["district"] = n
                    x["notes"].append(f"Filed on the list under {plain(dwords)}, not the city as a whole.")
                else:
                    x["seat"] = words
            else:
                unread.append((dtype, dwords, race))
                x.update(kind="other", office=plain(race))
            return x

        # ---- every other district: public utility, port, fire (school and hospital districts vote in odd years)
        known = next((v for k, v in DISTRICT_TYPES.items() if dtype.startswith(k)), None)
        base = pud_name(dwords, names) if dtype == "PUBLIC UTILITY" else plain(dwords)
        level, kind, office, pkind, letter = known or ("other", "other", plain(race), "special", "X")
        x.update(level=level, kind=kind, office=office, pkind=pkind, jname=f"{base} ({county_words(names)})",
                 jid=f"{STATE}-{letter}-{'-'.join(c3)}-{slug(base)}")
        m = re.search(r"(?i)\b(?:commissioner|comm|director)\b\.?(?!.*\b(?:commissioner|comm|director)\b)(.*)$", race)
        if known and m:
            x["seat"], _n = seat_of(m.group(1))
        else:
            unread.append((dtype, dwords, race))
            if known:
                x["seat"] = plain(race)
        return x

    for (cs, dtype, _dup, _rf, term, length), rows in contests.items():
        forms = collections.Counter(squeeze(r["District"]) for r in rows)
        dwords = max(forms, key=lambda s: (s != s.upper(), forms[s], s))
        race = squeeze(rows[0]["Race"])
        active = [r for r in rows if r["Status"] == "Active"]
        x = classify(dtype, dwords, race, cs)
        if x is None:
            gaps.append((STATE, "race", f"{'-'.join(fips[c] for c in cs)}-{slug(race)}", county_words([short[c] for c in cs]), f"{plain(race)}",
                         f"The Secretary of State's list files this county office under {len(cs)} counties at once, so which county's "
                         "office it is cannot be told from the list.", views[cs[0]]["url"]))
            report.append(f"a county office listed by {len(cs)} counties was not loaded: {race}")
            skipped += len(rows)
            continue
        for r in rows:
            if r["Status"] == "Withdrawn":
                gone.append((race, cs))
            elif r["Status"] != "Active":
                raise SystemExit(f"Washington: a status on the general list that is not read ({r['Status']!r}, {race}, {lsad[cs[0]]})")
        special, tnote = term_note(term, length)
        notes = list(x["notes"])
        if len(cs) > 1:
            notes.append(f"On the county lists of {county_words([short[c] for c in cs]).replace(' counties', '')}.")
        if tnote:
            notes.append(tnote)
        prefs = [bool(squeeze(r["Party Preference"])) for r in (active or rows)]
        partisan = int(any(prefs))
        if x["level"] == "court" and partisan:
            report.append(f"{x['jname']}: a judge's contest shows a party preference on the list; it is stored as a nonpartisan office")
            partisan = 0
        elif partisan and not all(prefs):
            report.append(f"{x['jname']}, {x['office']}: some candidates show a party preference and some do not")
        orders = [squeeze(r["Ballot Order"]) for r in active]
        ordered = all(o.isdigit() for o in orders) and sorted(int(o) for o in orders) == list(range(1, len(orders) + 1))
        if active and not ordered:
            notes.append(ORDER_ODD)
        if not active:
            notes.append(f"Nobody is on the list for this office: the {len(rows)} who filed withdrew.")
        if partisan:
            notes.append(TOP_TWO_LOCAL)
        kslug = x["kind"].replace("_", "-") + (f"-{slug(x['office'])}" if x["kind"] == "other" else "")
        core = x["jid"] if x["jid"].startswith(("DC-", "SUP-")) else f"{x['jid']}-{kslug}" if x["level"] == "county" else \
            f"{x['jid'][len(STATE) + 1:] if x['jid'].startswith(STATE + '-') else x['jid']}-{kslug}"
        rid = (f"2026-{STATE}-{core}" + (f"-{slug(x['district'])}" if x["district"] else "") + (f"-{slug(x['seat'])}" if x["seat"] else "")
               + ("-S" if special else ""))
        if rid in races or not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise SystemExit(f"Washington: two contests on the list come to one race id, or the id is not well formed ({rid})")
        fl = sorted(fips[c] for c in cs)
        races[rid] = dict(race_id=rid, state=STATE, level=x["level"], office_kind=x["kind"], office=x["office"], jurisdiction=x["jname"],
                          jurisdiction_id=x["jid"], county_ids=json.dumps(fl), district=x["district"], seat=x["seat"], special=special,
                          partisan=partisan, holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL,
                          note=" ".join(notes) or None)
        if x["pkind"] and x["pkind"] != "county":
            p = places.setdefault((x["pkind"], x["jid"]), [x["jname"], set(), x["psrc"]])
            p[1].update(fl)
        seen = set()
        for r in sorted(active, key=lambda r: (int(r["Ballot Order"]) if squeeze(r["Ballot Order"]).isdigit() else 0)):
            name = squeeze(r["Name"])
            if not name or name in seen:
                raise SystemExit(f"Washington: a candidate with no name, or one name twice, in {rid}")
            seen.add(name)
            if partisan:
                party = local_party(r["Party Preference"]) if squeeze(r["Party Preference"]) else "No party preference on the list"
                pcode = code(party)
            else:
                party, pcode = NONPARTISAN, "N"
            cands.append([rid, "general", GENERAL, name, party, pcode, int(r["Ballot Order"]) if ordered else None, 0, 0, None, None, None,
                          None, SRC_VIEW.format(cs[0]), None])
            placed += 1

    for t in sorted(set(unread)):
        report.append(f"a title on the list that is not read, stored in the list's own words: {t}")
    with_pa = {json.loads(r["county_ids"])[0] for r in races.values() if r["office_kind"] == "county_attorney"}
    if len(with_pa) != 39:
        report.append(f"{39 - len(with_pa)} counties show no prosecuting attorney contest on the list")
    total_rows = len(first)
    if placed + len(gone) + skipped != total_rows:
        raise SystemExit(f"Washington: {total_rows} county and local rows on the county views, but {placed} placed, {len(gone)} withdrawn "
                         f"and {skipped} not loaded")

    # ---- places: every county, and each city or district a contest names
    place_rows = [("county", fips[c], lsad[c], json.dumps([fips[c]]), SRC_COUNTIES) for c in sorted(codes, key=lambda c: fips[c])]
    place_rows += [(kind, pid, name, json.dumps(sorted(cset)), src) for (kind, pid), (name, cset, src) in sorted(places.items())]

    # ---- sources: one row for the whole list, one for each county's view, and the place lists
    cols = ("District Type, District, Race, Term Type, Term Length, Name, Party Preference, Status, Election Status and Ballot Order")
    view_sha = lambda v: v["page_sha256"][0] if len(v["page_sha256"]) == 1 else hashlib.sha256("".join(v["page_sha256"]).encode()).hexdigest()
    sources = [(SRC_ALL, STATE, "official candidate list", "Washington Secretary of State",
                "GENERAL 2026 Candidate List (November 3, 2026), all counties: county and local offices", whole["url"], "", whole["read"],
                view_sha(whole), len(whole["rows"]),
                f"The whole list, every page read through the grid's own pager ({whole['items']} rows on {whole['pages']} pages; the count "
                f"matched): {len(whole['rows'])} rows for county and local offices, {whole['state_rows']} for the Legislature and the appellate "
                f"courts and {whole['federal_rows']} for Congress, which are read elsewhere. It is the control for the 39 county views, which "
                "say which county a row belongs to: every county or local row here is on at least one county's view, and no view carries a "
                f"row this list lacks{'' if control else ' (this did not hold on this run; see the run log)'}. Only {cols} were read; the "
                "mailing address, e-mail, phone and filing date columns were never read and the pages were not kept. The list writes a party "
                "preference short and in capitals (DEMOCRATIC); it is shown as a ballot words it (Prefers Democratic Party), in ordinary "
                f"capitals. Ballot order as the list gives it. Withdrawn, left off: {len(gone)}. The sha256 here is of the pages' own hashes "
                "joined.")]
    for c in sorted(codes):
        v = views[c]
        sources.append((SRC_VIEW.format(c), STATE, "official candidate list", "Washington Secretary of State",
                        f"GENERAL 2026 Candidate List (November 3, 2026), {lsad[c]}'s view: county and local offices", v["url"], "", v["read"],
                        view_sha(v), len(v["rows"]),
                        f"{lsad[c]}'s own view of the list (the address ending &c={c}): {v['items']} rows on {v['pages']} page"
                        f"{'s' if v['pages'] > 1 else ''} ({'the grid counts them' if v['counted'] else 'a single page shows no count, so the rows were counted'}), "
                        f"{len(v['rows'])} of them for county and local offices. Only {cols} were read; the mailing address, e-mail, phone and "
                        "filing date columns were never read and the page was not kept."
                        + (" The sha256 here is of the pages' own hashes joined." if len(v["page_sha256"]) > 1 else "")))
    sources.append((SRC_COUNTIES, STATE, "official boundaries", "U.S. Census Bureau",
                    "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "", mtime(COUNTY_ZIP),
                    sha(COUNTY_ZIP), 39, "Washington's 39 counties: names and five-digit codes only."))
    sources.append((SRC_PLACES, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Washington (st53_wa_place2020.txt)",
                    PLACE_URL, "", mtime(ppath), sha(ppath), sum(len(v) for v in by_name.values()),
                    "Names and codes of Washington's incorporated cities and towns. A city on the candidate list takes the Census Bureau's "
                    "name and code only when its name fits exactly one place."))
    for sid, (path, url, county, n_rows) in sorted(extra_src.items()):
        sources.append((sid, STATE, "official results", "Washington Secretary of State",
                        f"November 8, 2022 General Election results, {county} County export", url, "", mtime(path), sha(path), n_rows,
                        "Race titles only were read, to learn which office the 2026 list titles with a district number alone. The file "
                        "holds race, candidate, party, votes, percentage and jurisdiction; it has no contact columns."))

    # ---- what is not here, and the calendar
    list_url = whole["url"]
    gaps += [
        (STATE, "state", STATE, "Washington", "write-in candidates for county and local offices",
         "The Secretary of State's candidate list names only the candidates printed on the ballot. A write-in candidate declares with the "
         "county auditor and is not on this list.", list_url),
        (STATE, "state", STATE, "Washington", "offices nobody filed for",
         "The Secretary of State's list is a list of candidates, so an office that nobody filed for does not appear on it. The county "
         "auditor's sample ballot is the authority for such an office.", list_url)]
    by_kind = collections.Counter(r["office_kind"] for r in races.values())
    by_level = collections.Counter(r["level"] for r in races.values())
    judges = by_kind["superior_court"] + by_kind["district_court"] + by_kind["municipal_court"]
    courts_of = sorted({re.sub(r"\s+(?:city|town)$", "", r["jurisdiction"]) for r in races.values() if r["office_kind"] == "municipal_court"})
    few = [f"{by_level['city']} city council seats" if by_level["city"] else "",
           f"{by_kind['port_board'] + by_kind['fire_board']} port and fire district seats" if by_kind["port_board"] + by_kind["fire_board"] else "",
           f"the municipal court judges of {' and '.join(courts_of)}" if courts_of else ""]
    few = [w for w in few if w]
    note_rows = [
        (STATE, "local_calendar",
         "On November 3, 2026 Washington elects county officers (assessor, auditor, clerk, coroner, prosecuting attorney, sheriff, "
         "treasurer, and commissioner or council seats), district court judges and public utility district commissioners"
         + (f", and fills {by_kind['superior_court']} unexpired superior court terms" if by_kind["superior_court"] else "")
         + "; a county office carries party preferences unless the county's charter makes it nonpartisan. Cities, towns, school "
         "districts and most other districts (fire, port, hospital, water, park) elect their officers in November of odd-numbered "
         "years, next in 2027"
         + (f", so only a few of their seats are on this ballot: {', '.join(few[:-1]) + ' and ' + few[-1] if len(few) > 1 else few[0]}"
            if few else "")
         + ". Conservation districts hold their elections at times set by their own law, and a county charter may put county "
         "elections in odd-numbered years.",
         "Revised Code of Washington 29A.04.321 and 29A.04.330 (when state, county, city and district elections are held), 29A.04.110 "
         "(partisan offices), 36.16.030 (elective county officers), 3.34.050 (district judges) and 35.20.150 (Seattle's municipal "
         "judges); the Secretary of State's GENERAL 2026 Candidate List for what is on this ballot",
         RCW + "29A.04.330"),
        (STATE, "local_coverage",
         "Loaded: every contest for a county, city or district office with a candidate on the Secretary of State's GENERAL 2026 Candidate "
         f"List, read county by county for all 39 counties: {by_level['county']} contests for county offices, {judges} for superior, "
         f"district and municipal court judges (shown with the judges), {by_kind['utility_board']} for public utility district "
         f"commissioners and {by_level['city'] + by_level['other'] - by_kind['utility_board']} for city council, port and fire district "
         f"seats, {placed} candidates in all. Not loaded: ballot measures, levies and other questions, which the candidate list does not "
         "carry; write-in candidates; any office nobody filed for; and the local primaries of August 4. A district is named in the "
         "list's own words with the county or counties whose lists carry it, because the list gives no district numbers.",
         "Washington Secretary of State, GENERAL 2026 Candidate List", list_url)]
    return dict(races=races, cands=cands, places=place_rows, sources=sources, gaps=gaps, notes=note_rows, report=report, placed=placed,
                rows=total_rows, whole=len(whole["rows"]), gone=len(gone), skipped=skipped, control=control, items=whole["items"],
                state_rows=whole["state_rows"], federal_rows=whole["federal_rows"],
                county_rows=sum(len(v["rows"]) for v in views.values()))


# ---------------------------------------------------------------------------------------------------------- the races

def race_of(r):
    """(race_id, level, office_kind, office, jurisdiction, jurisdiction_id, district, seat, partisan) for a kept list row."""
    d, race = r["District"].strip(), r["Race"].strip()
    if r["District Type"].strip().upper() == "LEGISLATIVE":
        m = re.fullmatch(r"legislative district (\d+)", d, re.I)
        if not m or not 1 <= int(m.group(1)) <= DISTRICTS:
            raise SystemExit(f"Washington: a legislative row names a district that is not read ({d!r})")
        n = str(int(m.group(1)))
        if race == "State Senator":
            return (f"2026-{STATE}-SS{n}", "legislature", "state_senate", "State Senator", f"Legislative District {n}", n, n, None, 1)
        p = re.fullmatch(r"State Representative Pos\. ([12])", race)
        if not p:
            raise SystemExit(f"Washington: a legislative race that is not read ({race!r}, {d})")
        return (f"2026-{STATE}-SH{n}-{p.group(1)}", "legislature", "state_house", "State Representative", f"Legislative District {n}", n, n,
                f"Position {p.group(1)}", 1)
    if d.lower() == "supreme court":
        p = re.fullmatch(r"Justice Position #?0*(\d+)", race)
        if not p:
            raise SystemExit(f"Washington: a Supreme Court race that is not read ({race!r})")
        return (f"2026-{STATE}-SC{p.group(1)}", "court", "supreme_court", "Justice of the Supreme Court", "Washington", STATE, None,
                f"Position {p.group(1)}", 0)
    m = re.fullmatch(r"court of appeals, division (\d), district (\d)", d, re.I)
    p = re.fullmatch(r"Judge Position (\d+)", race)
    if not m or not p:
        raise SystemExit(f"Washington: a Court of Appeals race that is not read ({d!r}, {race!r})")
    div, dist, pos = m.group(1), m.group(2), p.group(1)
    return (f"2026-{STATE}-COA{div}-{dist}-{pos}", "court", "court_of_appeals", "Judge of the Court of Appeals",
            f"Court of Appeals, Division {div}, District {dist}", f"COA{div}-{dist}", f"Division {div}, District {dist}", f"Position {pos}", 0)


OFFICE_RE = [
    (re.compile(r"State Senator - Legislative District (\d+)"), lambda m: f"2026-{STATE}-SS{int(m.group(1))}"),
    (re.compile(r"State Representative Pos\. ([12]) - Legislative District (\d+)"), lambda m: f"2026-{STATE}-SH{int(m.group(2))}-{m.group(1)}"),
    (re.compile(r"Justice Position #?0*(\d+) - Supreme Court"), lambda m: f"2026-{STATE}-SC{m.group(1)}"),
    (re.compile(r"Judge Position (\d+) - Court of Appeals,? Division (\d),? District (\d)", re.I),
     lambda m: f"2026-{STATE}-COA{m.group(2)}-{m.group(3)}-{m.group(1)}"),
]
BOOK_KEEP = ("Office Name", "Ballot Name", "Party", "Total")
NOT_CANDIDATES = ("ballots cast", "over votes", "under votes")


def book_race(office):
    office = re.sub(r"\s+", " ", str(office or "")).strip()
    for rx, rid in OFFICE_RE:
        m = rx.fullmatch(office)
        if m:
            return rid(m)
    if re.search(r"state senator|state representative|supreme court|court of appeals", office, re.I):
        raise SystemExit(f"Washington: a state office in the primary results that is not read ({office!r})")
    return None


def book_rows(wb, name, keep):
    it = wb[name].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if not all(k in heads for k in keep):
        raise SystemExit(f"Washington: the {name} sheet's columns changed ({[h for h in heads if h]})")
    idx = {k: heads.index(k) for k in keep}
    for r in it:
        rid = book_race(r[idx["Office Name"]])
        if rid:
            yield rid, {k: r[i] for k, i in idx.items()}


def primary_results(book):
    """{race: {"cands": [(name, party, votes)], "write_in": votes}} for the state offices, every figure checked against the
    sum of its county rows. Returns (results, counties, problems)."""
    wb = openpyxl.load_workbook(book, read_only=True, data_only=True)
    out, state = {}, collections.Counter()
    for rid, r in book_rows(wb, "Summary Results", BOOK_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        f = out.setdefault(rid, {"cands": [], "write_in": 0})
        v = int(r["Total"] or 0)
        if name.lower() in NOT_CANDIDATES:
            continue
        if re.match(r"write[- ]in", name, re.I):
            f["write_in"] += v
            state[(rid, "write-in")] += v
            continue
        party = re.sub(r"\s+", " ", str(r["Party"] or "")).strip()
        f["cands"].append((name, party, v))
        state[(rid, fold(name))] += v
    counties, byc = set(), collections.Counter()
    for rid, r in book_rows(wb, "Precinct Results", ("Precinct",) + BOOK_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        if name.lower() in NOT_CANDIDATES:
            continue
        key = "write-in" if re.match(r"write[- ]in", name, re.I) else fold(name)
        byc[(rid, key)] += int(r["Total"] or 0)
        counties.add(str(r["Precinct"]).strip())
    wb.close()
    problems = [f"{k[0]} {k[1]}: county rows add to {byc[k]:,}, the statewide sheet says {state[k]:,}"
                for k in sorted(set(byc) | set(state)) if byc[k] != state[k]]
    return out, len(counties), problems


# ---------------------------------------------------------------------------------------------------------- parties

def shown(party):
    """'(Prefers Democratic Party)' -> 'Prefers Democratic Party', as the ballot prints it without the parentheses."""
    return re.sub(r"\s+", " ", (party or "").strip().strip("()")).strip()


def code(party):
    p = shown(party).lower()
    m = re.fullmatch(r"prefers (.+?) party", p)
    word = m.group(1) if m else p
    if word in ("democratic", "democrat"):
        return "D"
    if word in ("republican", "gop"):
        return "R"
    if word == "libertarian":
        return "L"
    if word == "green":
        return "G"
    if word in ("independent", "states no party preference", "no party preference"):
        return "I"
    return "O"


def same_pref(party, listed):
    """The results' preference and a list's short form agree: (Prefers StandUp America Party) and STANDUP-AMERICA, letters
    only."""
    return re.sub(r"[^A-Z]", "", W.short(party)) == re.sub(r"[^A-Z]", "", (listed or "").upper())


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators: ids, names, party, chamber and district only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    con.close()
    for p in legs:
        p["district"] = str(int(p["district"])) if str(p["district"] or "").isdigit() else str(p["district"] or "")
    return legs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's first name or any
    other form of the name it keeps)."""
    readings = [name_parts(name), name_parts(re.sub(r'"[^"]*"|\([^)]*\)', " ", name))]
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and r[1] and fits(r, f) for r in readings for f in forms)


def party_letter(roster_party):
    t = (roster_party or "").lower()
    return "D" if t.startswith("democrat") else "R" if t.startswith("republican") else "O"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "wa")
    os.makedirs(folder, exist_ok=True)
    report = []

    gpath, gen = read_list("general", folder, say)
    ppath, pri = read_list("primary", folder, say)
    book, info = W.results_book(folder)
    results, counties, unreconciled = primary_results(book)
    past = {y: past_results(y, folder, say) for y in PAST}
    legs = roster(roster_db)
    local = load_local(os.path.join(folder, "local"), say)      # county and local contests; the state rows below never see them

    # ---- the races and the November ballot, from the general list
    races, listed, gone = {}, collections.defaultdict(list), []
    for r in gen["rows"]:
        rid, level, okind, office, juris, jid, district, seat, partisan = race_of(r)
        if r["Status"] == "Withdrawn":
            gone.append((rid, r["Name"]))
            continue
        if r["Status"] != "Active":
            raise SystemExit(f"Washington: a status on the general list that is not read ({r['Status']!r}, {rid})")
        if not r["Ballot Order"].isdigit():
            raise SystemExit(f"Washington: no ballot order on the general list for {r['Name']} ({rid})")
        term = r["Term Type"].strip()
        if term not in ("Regular", "Short & Full", "Unexpired"):
            raise SystemExit(f"Washington: a term type on the general list that is not read ({term!r}, {rid})")
        if rid not in races:
            races[rid] = dict(race_id=rid, state=STATE, level=level, office_kind=okind, office=office, jurisdiction=juris,
                              jurisdiction_id=jid, county_ids=None, district=district, seat=seat, special=int(term == "Unexpired"),
                              partisan=partisan, holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL, note=None,
                              _term=term, _length=r["Term Length"].strip())
        elif (races[rid]["_term"], races[rid]["_length"]) != (term, r["Term Length"].strip()):
            raise SystemExit(f"Washington: two term types for {rid} on the general list")
        listed[rid].append(r)

    # ---- the primary list: who was on the August ballot, and who withdrew before it
    filed, withdrew, skipped = collections.defaultdict(dict), [], collections.defaultdict(list)
    for r in pri["rows"]:
        rid = race_of(r)[0]
        if r["Status"] == "Withdrawn":
            withdrew.append(f"{r['Name']} ({rid})")
        elif r["Status"] == "Active":
            if fold(r["Name"]) in filed[rid]:
                raise SystemExit(f"Washington: {r['Name']} is on the primary list twice for {rid}")
            filed[rid][fold(r["Name"])] = r
            if r["Election Status"] == "Advanced to General":
                skipped[rid].append(r)
            elif r["Election Status"] != "In Primary":
                raise SystemExit(f"Washington: an election status on the primary list that is not read ({r['Election Status']!r}, {rid})")
        else:
            raise SystemExit(f"Washington: a status on the primary list that is not read ({r['Status']!r}, {rid})")

    # ---- which seats: the Senate seats elected in 2022, all 98 House positions
    senate_won = {y: {int(re.search(r"district (\d+)", race, re.I).group(1)) for race, _c, _v in rows_
                      if re.fullmatch(r"legislative district \d+ - state senator", race, re.I)} for y, (_p, rows_) in past.items()}
    sen = sorted(int(x["district"]) for x in races.values() if x["office_kind"] == "state_senate")
    if set(sen) != senate_won["2022"] - senate_won["2024"]:
        report.append(f"the Senate seats on the list {sen} are not the seats elected in 2022 and not again in 2024 "
                      f"{sorted(senate_won['2022'] - senate_won['2024'])}")
    if set(sen) & senate_won["2024"]:
        report.append(f"Senate seats on the list that were elected for four years in 2024: {sorted(set(sen) & senate_won['2024'])}")
    if len(senate_won["2024"] | set(sen)) != SENATE_SEATS:
        report.append(f"the 2024 Senate seats and the 2026 list's cover {len(senate_won['2024'] | set(sen))} of {SENATE_SEATS} districts")
    for x in races.values():
        if x["office_kind"] == "state_senate" and x["_term"] != "Regular":
            report.append(f"{x['race_id']}: the Senate race is a {x['_term']} term")
    house = {(int(x["district"]), x["seat"]) for x in races.values() if x["office_kind"] == "state_house"}
    want = {(d, f"Position {p}") for d in range(1, DISTRICTS + 1) for p in (1, 2)}
    if house != want:
        report.append(f"House positions with no candidate on the general list: {sorted(want - house)}")
    for rid in set(filed) - set(races):
        report.append(f"{rid}: on the primary list, but nobody for it on the general list")

    # ---- who holds each seat today
    past_won = {}
    for race, cand, votes in past["2024"][1]:
        m = re.fullmatch(r"legislative district (\d+) - state representative pos\. ([12])", race, re.I)
        if m:
            key = (m.group(1), f"Position {m.group(2)}")
            past_won.setdefault(key, []).append((votes, cand))
    holder, how = {}, {}
    for d in range(1, DISTRICTS + 1):
        d = str(d)
        sitting = [p for p in legs if p["chamber"] == "House" and p["district"] == d]
        if len(sitting) != 2:
            report.append(f"the roster shows {len(sitting)} sitting representatives for District {d}")
        for pos in ("Position 1", "Position 2"):
            ranked = sorted(past_won.get((d, pos), []), reverse=True)
            if not ranked:
                report.append(f"no 2024 result for District {d} {pos}")
                continue
            won = ranked[0][1]
            fit = [p for p in sitting if person_fits(won, p)]
            if len(fit) == 1:
                holder[(d, pos)], how[(d, pos)] = fit[0], ("won", won)
        for pos, other in (("Position 1", "Position 2"), ("Position 2", "Position 1")):
            if (d, pos) not in holder and (d, other) in holder:
                rest = [p for p in sitting if p["id"] != holder[(d, other)]["id"]]
                if len(rest) == 1:
                    won = sorted(past_won.get((d, pos), []), reverse=True)
                    holder[(d, pos)], how[(d, pos)] = rest[0], ("rest", won[0][1] if won else None, holder[(d, other)]["full"])
        for pos in ("Position 1", "Position 2"):
            if (d, pos) not in holder:
                report.append(f"District {d} {pos}: which sitting representative holds it could not be told from the record")

    for rid, x in races.items():
        notes = []
        h = None
        if x["office_kind"] == "state_senate":
            hs = [p for p in legs if p["chamber"] == "Senate" and p["district"] == x["district"]]
            h = hs[0] if len(hs) == 1 else None
            if h is None:
                report.append(f"{rid}: {len(hs)} sitting senators in the roster for this district")
            notes += [SENATE_NOTE]
        elif x["office_kind"] == "state_house":
            key = (x["district"], x["seat"])
            h = holder.get(key)
            notes.append(HOUSE_NOTE)
            if h is not None and how[key][0] == "won":
                notes.append(f"Who holds this position today: {h['full']}, who won it in November 2024 (the Secretary of State's "
                             "results) and still serves, by the Open States roster.")
            elif h is not None:
                _k, won, other = how[key]
                notes.append(f"Who holds this position today: {h['full']}. The roster does not say which position a representative "
                             f"holds; {other} won the district's other position in November 2024 and still serves, and "
                             f"{h['full']} is the district's other sitting representative"
                             + (f" ({won} won this position in 2024 and no longer sits for the district)." if won else "."))
            else:
                notes.append("Which of the district's sitting representatives holds this position could not be told from the record, "
                             "so no holder is shown.")
            if x["_term"] == "Short & Full":
                notes.append(SHORT_FULL)
        else:
            notes.append(COURT_NOTE)
            if x["office_kind"] == "supreme_court":
                notes.append("Justices of the Supreme Court serve six-year terms and are elected statewide.")
            else:
                notes.append("Judges of the Court of Appeals serve six-year terms and are elected by district within their division.")
            if x["_term"] == "Unexpired":
                notes.append(f"This election is for the rest of a term: the Secretary of State's list gives it as Unexpired, "
                             f"{x['_length']} years.")
            elif x["_term"] == "Short & Full":
                notes.append("The Secretary of State's list gives this race as \"Short & Full\": the winner also serves the rest of "
                             "the present term.")
        if x["partisan"]:
            notes.append(TOP_TWO)
        elif rid in results:
            notes.append(COURT_TOP_TWO)
        elif rid in skipped:
            notes.append(SKIPPED_PRIMARY)
        notes.append(ORDER_NOTE)
        if h is not None:
            x.update(holder_id=h["id"], holder_name=h["full"], holder_party=h["party"])
        x["note"] = " ".join(notes)
        x["_holder"] = h
        x["_chamber"] = {"state_senate": "Senate", "state_house": "House"}.get(x["office_kind"])

    def where(p):
        pos = next((k[1] for k, v in holder.items() if v["id"] == p["id"]), None)
        return f"Washington {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {p['district']}" + (f", {pos}" if pos else "")

    def identify(race, name, pcode):
        """(incumbent, state_member_id, note): the seat's sitting member when the name fits; else a sitting legislator of a
        compatible party anywhere when the name fits exactly one."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if not race["_chamber"]:
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and (pcode not in ("D", "R") or party_letter(p["party"]) in (pcode, "O"))]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {where(pool[0])}."
        return 0, None, None

    # ---- controls between the lists and the results, and the rows
    cands, fields, singles, upsets, off_list, wrote_in = [], 0, 0, [], [], []
    for rid in sorted(races):
        race = races[rid]
        on_list = {fold(r["Name"]): r for r in listed[rid]}
        printed = {}
        if rid in results:
            field, write_in = results[rid]["cands"], results[rid]["write_in"]
            names = {fold(n) for n, _p, _v in field}
            if names != set(filed[rid]):
                report.append(f"{rid}: the results' candidates are not the primary list's Active candidates "
                              f"(results only: {sorted(names - set(filed[rid]))}; list only: {sorted(set(filed[rid]) - names)})")
            for n, p, _v in field:
                if race["partisan"]:
                    if not p:
                        report.append(f"{rid}: {n} has no party preference in the results")
                    elif fold(n) in filed[rid] and not same_pref(p, filed[rid][fold(n)]["Party Preference"]):
                        report.append(f"{rid}: {n}'s party preference differs between the results ({p}) and the primary list "
                                      f"({filed[rid][fold(n)]['Party Preference']})")
                elif p:
                    report.append(f"{rid}: a nonpartisan candidate, {n}, has a party in the results ({p})")
                printed[fold(n)] = shown(p)
            ranked = sorted(field, key=lambda c: (-c[2], c[0]))
            second = ranked[1][2] if len(ranked) > 1 else ranked[0][2]
            went = {fold(n) for n, _p, v in ranked if v >= second}
            if set(on_list) - went - (set(on_list) - set(filed[rid])):
                upsets.append(f"{rid}: {sorted(set(on_list) - went - (set(on_list) - set(filed[rid])))}")
            for n in sorted(went - set(on_list)):
                off_list.append(f"{rid}: {n}")
            total = sum(v for _n, _p, v in field) + write_in
            if len(field) >= 2:
                fields += 1
                for name, party, v in ranked:
                    pcode = code(party) if race["partisan"] else "N"
                    inc, mid, n2 = identify(race, name, pcode)
                    note = [n2] if n2 else []
                    if fold(name) in went and fold(name) not in on_list:
                        note.append("Advanced from the top-two primary, but is not on the Secretary of State's list for the November ballot.")
                    lr = filed[rid].get(fold(name))
                    order = int(lr["Ballot Order"]) if lr and lr["Ballot Order"].isdigit() else None
                    cands.append([rid, "primary", PRIMARY, name, shown(party) if race["partisan"] else NONPARTISAN, pcode, order, inc, 0,
                                  v, round(100 * v / total, 1) if total else None, "advanced" if fold(name) in went else "lost", mid,
                                  SRC_RES, " ".join(note) or None])
            else:
                singles += 1
        else:
            if race["partisan"]:
                report.append(f"{rid}: a partisan race with no primary results")
            elif set(on_list) != {fold(r["Name"]) for r in skipped.get(rid, [])}:
                report.append(f"{rid}: not in the primary results, and the general list is not the primary list's 'Advanced to General' names")
        for r in sorted(listed[rid], key=lambda r: int(r["Ballot Order"])):
            extra = None
            if race["partisan"]:
                party = printed.get(fold(r["Name"]))
                if not party and rid in results and fold(r["Name"]) not in filed[rid]:
                    # not printed on the August ballot and named on the November list: a write-in who advanced; the results
                    # count write-ins together, so no votes of this candidate's own are stored
                    party = r["Party Preference"].strip().capitalize()
                    pcode = "I" if party.lower() in ("states no party preference", "no party preference") else "O"
                    extra = (f"Was not printed on the August primary ballot; the Secretary of State's general list names this candidate "
                             f"for the November ballot, with the party preference written \"{r['Party Preference'].strip()}\" (shown here "
                             f"in ordinary capitals). The certified primary results count write-in votes together, not by name "
                             f"({results[rid]['write_in']:,} in this race).")
                    wrote_in.append(f"{rid}: {r['Name']}")
                elif not party:
                    report.append(f"{rid}: {r['Name']} is on the general list but not in the primary results; the list's own words are shown")
                    party = r["Party Preference"].strip().capitalize()
                    pcode = "O"
                else:
                    if not same_pref(party, r["Party Preference"]):
                        report.append(f"{rid}: {r['Name']}'s party preference differs between the general list ({r['Party Preference']}) "
                                      f"and the results ({party})")
                    pcode = code(party)
            else:
                if r["Party Preference"]:
                    report.append(f"{rid}: a nonpartisan candidate, {r['Name']}, has a party on the general list")
                party, pcode = NONPARTISAN, "N"
            inc, mid, n2 = identify(race, r["Name"], pcode)
            cands.append([rid, "general", GENERAL, r["Name"], party, pcode, int(r["Ballot Order"]), inc, 0, None, None, None, mid, SRC_GEN,
                          " ".join(x for x in (extra, n2) if x) or None])
        orders = sorted(int(r["Ballot Order"]) for r in listed[rid])
        if orders != list(range(1, len(orders) + 1)):
            report.append(f"{rid}: the general list's ballot order is {orders}")

    for rid in sorted(set(results) - set(races)):
        report.append(f"{rid}: in the primary results, but nobody for it on the general list")
    report += [f"primary results do not add up: {u}" for u in unreconciled]
    report += [f"on the general list without being in the primary's top two: {u}" for u in upsets]
    report += [f"in the primary's top two but not on the general list: {u}" for u in off_list]
    report += [f"on the general list after a write-in run in the primary (not a printed candidate; no votes of their own stored): {u}"
               for u in wrote_in]

    # House incumbents who filed for the other position, or elsewhere
    for rid in sorted(races):
        race = races[rid]
        if race["office_kind"] != "state_house":
            continue
        for r in listed[rid]:
            for (d, pos), p in holder.items():
                if d == race["district"] and pos != race["seat"] and person_fits(r["Name"], p):
                    report.append(f"{rid}: {r['Name']} fits {p['full']}, who holds District {d} {pos} by the record read here")

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Washington: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- write: Washington's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(races[r][c] for c in cols) for r in sorted(races)]
    other = lambda keep: ", ".join(f"{k.title()} {v}" for k, v in keep["other"].items())
    list_sha = lambda keep: hashlib.sha256("".join(keep["page_sha256"]).encode()).hexdigest()
    src = [
        (SRC_GEN, STATE, "official candidate list", "Washington Secretary of State",
         "GENERAL 2026 Candidate List (November 3, 2026): State Senator, State Representative, Supreme Court and Court of Appeals",
         gen["url"], "", gen["read"], list_sha(gen), len(gen["rows"]),
         f"Every page of the grid read through its own pager ({gen['items']} rows on {gen['pages']} pages, every office; the count "
         "matched). Only District Type, District, Race, Term Type, Term Length, Name, Party Preference, Status, Election Status and Ballot "
         "Order were read; mailing addresses, e-mail, phones and filing dates were never read and the pages were not kept. Ballot order "
         f"as the list gives it. Withdrawn, left off: {len(gone)}. The sha256 here is of the pages' own hashes joined. Other offices on "
         f"the list, counted only (local offices and the federal rows): {other(gen)}."),
        (SRC_PRI, STATE, "official candidate list", "Washington Secretary of State",
         "PRIMARY 2026 Candidate List (August 4, 2026): State Senator, State Representative, Supreme Court and Court of Appeals",
         pri["url"], "", pri["read"], list_sha(pri), len(pri["rows"]),
         f"Read the same way ({pri['items']} rows on {pri['pages']} pages). Used to check the primary results (every Active candidate, "
         "each one's party preference) and for the August ballot order. Withdrawn before the primary, not on its ballot: "
         f"{'; '.join(withdrew) or 'none'}. Other offices, counted only: {other(pri)}."),
        (SRC_RES, STATE, "official results", "Washington Secretary of State",
         "2026 Primary (August 4, 2026): All Results Excel, certified results: State Senator, State Representative and Supreme Court",
         info["url"], (info.get("asOf") or "")[:10], mtime(book), sha(book), sum(len(f["cands"]) for f in results.values()),
         f"Found through the results site's own record of the election ({W.API}), which marks these results official. Top-two primary: "
         "each field's total is its candidates' votes plus write-ins (over- and under-votes left out). A field is shown only where two "
         f"or more candidates were on the ballot ({fields} fields; {singles} races had one candidate). "
         + (f"Every figure checked against the sum of its rows for {counties} counties." if not unreconciled
            else "Did not add up: " + "; ".join(unreconciled) + ".")),
    ]
    for y, (path, rows_) in past.items():
        date, words = PAST[y]
        src.append((SRC_PAST[y], STATE, "official results", "Washington Secretary of State",
                    f"{words} General Election results, statewide export (AllState.csv)", PAST_URL.format(date), "", mtime(path), sha(path),
                    len(rows_),
                    "Legislative races only were read (race, candidate, votes). "
                    + ("Used for who won each House position, which the roster does not record, and for which Senate seats were elected "
                       "for four years in 2024." if y == "2024" else "Used for which Senate seats were elected in 2022, whose terms end in January 2027.")))
    src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_wa.sqlite", "Sitting Washington legislators",
                "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db), len(legs),
                "Who holds each legislative seat today (chamber and district); the roster carries no House position and no judges."))
    for fsid, (fname, url, title) in W.SCANS.items():
        path = os.path.join(folder, fname)
        if os.path.exists(path):
            src.append((SCAN_SRC[fsid], STATE, "official certification", "Washington Secretary of State", title, url, "", mtime(path), sha(path), 0,
                        f"Posted on {W.SOS_PAGE}. A scanned image with no text layer (the federal loader's copy): fingerprinted here, not read."))

    clash = sorted(set(races) & set(local["races"]))
    if clash:
        raise SystemExit(f"Washington: a local contest and a state race share a race id ({clash[:3]})")
    local_rows = [tuple(r[c] for c in cols) for r in local["races"].values()]

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
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows + local_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["sources"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    gen_rows = [c for c in cands if c[1] == "general"]
    pri_rows = [c for c in cands if c[1] == "primary"]
    by = lambda kind, rows_: sum(1 for c in rows_ if races[c[0]]["office_kind"] == kind)
    nk = lambda kind: sum(1 for r in races.values() if r["office_kind"] == kind)
    say(f"    Washington: {len(races)} races ({nk('state_senate')} Senate, {nk('state_house')} House, {nk('supreme_court')} Supreme Court, "
        f"{nk('court_of_appeals')} Court of Appeals); {len(gen_rows)} candidates on the November list (Senate {by('state_senate', gen_rows)}, "
        f"House {by('state_house', gen_rows)}, Supreme Court {by('supreme_court', gen_rows)}, Court of Appeals "
        f"{by('court_of_appeals', gen_rows)}; {len(gone)} withdrawn left off); {fields} top-two primary fields, {len(pri_rows)} primary rows "
        f"(Senate {by('state_senate', pri_rows)}, House {by('state_house', pri_rows)}, Supreme Court {by('supreme_court', pri_rows)}), "
        "certified votes, county sums checked")
    for c in cands:
        if c[12] and not c[7]:
            say(f"      matched elsewhere: {c[0]} {c[1]}: {c[3]} -> {c[12]}")
    for line in report:
        say(f"      check: {line}")

    lr = local["races"].values()
    lv = collections.Counter(r["level"] for r in lr)
    kinds = collections.Counter(r["office_kind"] for r in lr)
    per = collections.Counter(local["races"][c[0]]["level"] for c in local["cands"])
    reached = {f for r in lr if r["level"] in LOCAL_LEVELS for f in json.loads(r["county_ids"])}
    say(f"    Washington, county and local: {len(local['races'])} contests, {local['placed']} candidates: county offices {lv['county']} "
        f"({per['county']} candidates), judges of the superior, district and municipal courts {lv['court']} ({per['court']}), city "
        f"{lv['city']} ({per['city']}), public utility, port and fire districts {lv['other']} ({per['other']}); {len(reached)} of 39 "
        f"counties have a county or local contest; {sum(r['partisan'] for r in lr)} contests carry party preferences")
    say(f"      the list's own count: {local['items']} rows = {local['state_rows']} Legislature and appellate courts + {local['federal_rows']} "
        f"Congress + {local['whole']} county and local; the 39 county views hold {local['county_rows']} county and local rows, "
        f"{local['rows']} once a contest that reaches several counties is counted once; {local['placed']} placed, each in one contest, "
        f"{local['gone']} withdrawn left off, {local['skipped']} not loaded; whole list and county views agree: "
        f"{'yes' if local['control'] else 'NO'}")
    say("      office kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    for line in local["report"]:
        say(f"      check (local): {line}")
    return len(gen_rows) + local["placed"]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_wa <database>")
    load(sys.argv[1])
