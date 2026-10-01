"""
ballot/state_local_mt.py - Montana's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite (the
federal ballot database, ballot_2026.sqlite, is never opened here; U.S. Senator and U.S. Representative rows are left
to the federal pages):

  - the Montana Senate: the 25 of its 50 seats on this year's list (a senator serves four years and half the seats are
    elected every two years, by a list of districts rather than by odd and even, so the seats are read from the list);
  - the Montana House: all 100 seats (one member a district, two-year terms);
  - the Public Service Commission districts on this year's list (partisan, elected by district);
  - the Supreme Court seat and the District Court departments on this year's list (nonpartisan offices).
  No Governor, Attorney General or other statewide executive office is on Montana's ballot this year.

Sources, the Secretary of State's own (and the Census Bureau's county names), nothing else:

  - The Secretary of State's candidate filing lists on candidatefiling.mt.gov, the same two the federal loader reads
    (ballot/lists/mt.py): "FEDERAL GENERAL 2026 Candidate List" (election 450002987) and "FEDERAL PRIMARY 2026
    Candidate List" (450002928). Despite the name each list carries every office the Secretary files, federal, state
    and judicial. Each is a Telerik grid, 100 rows a page, read here through the grid's own pager, one request every
    two seconds, and the row count is checked against the grid's own "items" figure. Columns are taken by name with
    ballot/lists/mt.py's grid_rows, which turns into text only Status, District Type, District, Race, Term Type, Name,
    Party Preference and Ballot Order; the grid also carries mailing addresses, e-mail, web addresses and phones, which
    are never read, printed or kept. Only the state rows are kept, and only those columns, as JSON in ballot_cache/mt/.
    The page's own key writes out the parties (DEM Democratic, REP Republican, LIB Libertarian, IND Independent, MP
    Minor Party, NON Non Partisan) and says "* = Incumbent": an asterisk before a name is the Secretary's mark of the
    incumbent. It is dropped from the name and kept as a check (and, for the Commission and the courts, which the
    roster does not carry, as the incumbent mark).
  - The official results of the June 2, 2026 primary, from sosmt.gov/elections/results/: the "2026 Primary Election
    Precinct by Precinct Report" (a workbook: County ID, County, Precinct, Race, District, Party, Votes, Full Name On
    Ballot are the only columns read), the "2026 Primary Legislative Canvass" (PDF, every Senate and House primary,
    each candidate's party, votes by county and total) and the "2026 Statewide Primary Election Canvass" (PDF: the
    Commission, the Supreme Court and the District Courts). Every primary's per-candidate totals summed from the
    workbook must match the canvass: the legislative canvass party by party, district by district, and the statewide
    canvass by its "Total" lines. The workbook carries no write-in votes, so a field's total is its candidates' sum.
  - The Census Bureau's 2024 county file (cb_2024_us_county_500k.zip, already in states_cache/census/): the names and
    GEOIDs of Montana's 56 counties, read from its attribute table only. Which counties a district reaches is where the
    workbook shows that race on a precinct's ballot in the June primary.

The November ballot is every state row of the general list whose status is FILED (or NOMINATED); a WITHDRAWN or
REMOVED row is left off and counted, and any other status stops the loader. The general list gives no ballot order
for the state races (three of them carry a number, the rest none), so ballot_order is left empty: the page then lists
the names by surname and says the list gives no order. In a partisan race a candidate filed as NON (Non Partisan) is a
declared write-in, as the federal loader reads it: party nominees are DEM, REP, LIB or MP and an independent who
petitioned is IND; the NON rows are on no party's primary list. They get write_in 1 and no ballot position.

The primary: every party's candidates on the June 2 ballot for each race (the primary list's FILED and NOMINATED rows,
which must be exactly the workbook's candidates for that race and party) with their official votes; a field is a
party with two or more candidates on its ballot (primary-DEM, primary-REP, primary-LIB); the one the list marks
NOMINATED advanced and must also have had the most votes. In the nonpartisan judicial primaries (primary-NP) the list's
NOMINATED marks say who advanced (this year's two fields have two candidates each, and both advanced). A candidate who withdrew before the primary or was
removed is not on its ballot and is counted, not shown.

Today's holders come from state_mt.sqlite (the Open States roster): current legislators by chamber and district. The
roster carries no Public Service Commissioners or judges, so those races show no holder and the list's asterisk marks
the incumbent. A candidate is the sitting member (incumbent 1, state_member_id) only when the name fits the seat's
holder (family name and a fitting given name) one to one; a candidate who sits today in the other chamber for the
nesting district (a Senate district holds House districts 2n-1 and 2n: checked here against the workbook's precincts
for every Senate district on the ballot), or, for a Commission race, the one legislator in the roster whose name fits,
gets state_member_id with incumbent 0 and a note. The roster's own spelling is used for a matched member only when it
has exactly the same letters as the filed name (so only the capitals differ); every other name is the filed name in
ordinary capitals, and the race note says so.

County and local offices (the second half of this file; its rows are written beside the state rows and never touch them)
---------------------------------------------------------------------------------------------------------------------
Montana has no statewide list of county candidates before Election Day: the Secretary of State's lists stop at the
district courts, and each county's election administrator certifies and posts the county's own. So the local part goes
county by county, from what a county's election office posts, and every county it cannot read becomes a row in sl_gaps
(never a guess). On 2026-10-01 the election pages of about fifty counties were looked at; LOCAL_SOURCES names the ones
that post something a script can fetch, and CHECKED says what the others carried that day.

  - Sample ballots (Gallatin: every ballot form in one file; Richland: its publication ballot; Carbon, Sanders, Madison
    and Fergus: one file a precinct). They are the counties' own ballots as the voting system prints them (text PDFs, three
    columns): a contest is its title ("FOR COUNTY COMMISSIONER", "DISTRICT 1", "(UNEXPIRED TERM)"), a line "(VOTE FOR
    ONE)", then each name with its party, or NONPARTISAN, in smaller type beneath. A ballot has no contact details at
    all, so the files are kept whole in ballot_cache/mt/local/<county>/. Read here with a reader of this file's own
    (ballot/pdftext.py finds no pages in Gallatin's file, whose catalog object is longer than the 600 bytes it looks
    at, and all of that file's text sits in embedded forms): pages from the trailer's /Root, forms followed, every
    glyph placed, so that a title squeezed to fit its column keeps its word spaces (Carbon's ballots make a word space
    out of character spacing, with no space glyph). Controls on every file: its heading must name the
    county and NOVEMBER 3, 2026; the party lines counted on their own must equal the names placed; a contest must carry
    the same names on every ballot of the county that prints it; and the state contests on the same ballots (Supreme
    Court, district court, Legislature, Public Service Commission) are compared with the Secretary of State's list.
  - Candidate lists (Flathead, Cascade, Beaverhead). Flathead's and Cascade's also print mailing addresses, e-mail and
    phones (Flathead's a website column too): those files are read in memory only, cut down to the office, name, status
    and party cells before anything is turned into text (a cell is taken by the heading its middle is nearest, since a
    centred address can start to the left of its own heading; or, in Cascade's, by its place before the address
    column), and only that cut-down copy is kept, as JSON. Beaverhead's has three columns (office, candidate, party)
    and no contact details.
  - A county whose folder ballot_cache/mt/local/<county>/ holds sample ballots saved by hand (Missoula's are in a shared
    folder that refuses scripts) is read from those files, with the same controls.

What is written: level county for county offices and justices of the peace (a justice's court is the county's; office
kind justice_of_the_peace), soil_water for conservation district supervisors, city for a city or town office.
jurisdiction_id is the county's five-digit code, MT-M-<Census place code> for a city or town, MT-X-<county>-<name> for
a named conservation district. A combined office (Sheriff/Coroner, Treasurer/Assessor, Clerk & Recorder/Surveyor) is
filed under the office named first and keeps its whole title. Partisan or not is read from what the county's own ballot
or list prints, never assumed: Carbon, Sanders, Madison and Fergus print every county office NONPARTISAN. Names rotate from one
ballot form to another (MCA 13-12-205), so no ballot order is given. When a sitting judge is the only candidate the
ballot asks whether the judge shall be retained (MCA 13-14-212); the judge is written as the contest's one candidate
and the race's note says it is a Yes or No vote. Not loaded: ballot questions and measures, write-in candidates (a
ballot prints only a blank line for them), and candidates who withdrew (counted). What could not be loaded goes to
sl_gaps and what the ballot carries and the lists cover to sl_notes (both tables from ballot.check_local.EXTRA_SCHEMA);
only Montana's rows of either are deleted and rewritten.

Usage: python ballot/state_local_mt.py <database file> [--cache <folder>]
"""

import collections
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
import unicodedata
import urllib.parse
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like                                      # noqa: E402
from ballot.common import fold, name_parts, party_code                                        # noqa: E402
from ballot.lists.mt import CANVASS_URL, LIST_URL, LISTS, PRECINCT_URL, canvass_totals, form_fields, grid_rows  # noqa: E402
from ballot.lists.tx import proper                                                             # noqa: E402
from ballot.match import fits                                                                  # noqa: E402
from ballot.pdftext import PDF, Font, Ref, _mul, _ops, lines                                   # noqa: E402
from states import net                                                                         # noqa: E402

STATE, NAME, FIPS = "MT", "Montana", "30"
GENERAL, PRIMARY = "2026-11-03", "2026-06-02"
CACHE = os.path.join(HERE, "ballot_cache", "mt")
ROSTER_DB = os.path.join(HERE, "state_mt.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
LEG_CANVASS_URL = "https://sosmt.gov/docs/31/post-election/76707/2026-primary-state-canvass-legislative"
RESULTS_PAGE = "https://sosmt.gov/elections/results/"

FEDERAL = ("UNITED STATES SENATOR", "UNITED STATES REPRESENTATIVE")
STATE_TYPES = {"Senate", "House", "Public Service Commission", "Supreme Court Justice", "Judicial"}
ON = ("FILED", "NOMINATED")
OFF = re.compile(r"WITHDR|REMOV", re.I)
NOMINEE_CODES = ("DEM", "REP", "LIB", "MP")
BOOK_KEEP = ("County ID", "County", "Precinct", "Race", "District", "Party", "Votes", "Full Name On Ballot")
CAPS = "Montana's lists print names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Declared write-in candidate: the name is not printed on the ballot."
CHAMBER = {"SS": "Senate", "SH": "House"}

SRC_GEN, SRC_PRI = "mt-sos-2026-sl-general-list", "mt-sos-2026-sl-primary-list"
SRC_BOOK, SRC_LEG, SRC_STW = "mt-sos-2026-sl-primary-precinct", "mt-sos-2026-sl-primary-legislative-canvass", "mt-sos-2026-sl-primary-state-canvass"
SRC_COUNTY, SRC_ROSTER = "mt-census-2024-counties", "mt-openstates-roster"

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


# ---------- the candidate lists: allowed columns only ----------

def ask(url, data=None):
    """One page of a list; at most three tries (a refusal or a page without its grid stops the loader)."""
    headers = {"User-Agent": net.UA, "Accept": "text/html"}
    if data:
        headers.update({"Content-Type": "application/x-www-form-urlencoded", "Referer": url})
    last = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=data, headers=headers, method="POST" if data else "GET"), timeout=120) as r:
                page = r.read().decode("utf-8", "replace")
            if 'class="rgHeader' not in page:
                raise SystemExit(f"Montana (state races): {url} answered without its candidate grid (a bot check or a changed "
                                 "page); stopped. A person would need to open it in a browser.")
            return page
        except (HTTPError, URLError, OSError) as e:
            last = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise SystemExit(f"Montana (state races): {url} refused three times ({last}); stopped")


def read_list(kind):
    """Every page of one list; returns {title, url, items, pages, legend, rows (state rows, allowed columns only)}."""
    net.patient_lookups()
    eid, title = LISTS[kind]
    url = LIST_URL + eid
    page = ask(url)
    if f"{title} Candidate List" not in page:
        raise SystemExit(f"Montana (state races): {url} is no longer the {title} Candidate List")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    key = re.search(r"DEM = Democratic[^<]*", page)
    if not m or not key:
        raise SystemExit(f"Montana (state races): the {title} list no longer shows its row count or its key of parties")
    after_key = re.sub(r"<[^>]+>", " ", page[key.start():key.start() + 2000])
    if not re.search(r"\*\s*=\s*Incumbent", after_key):
        raise SystemExit(f"Montana (state races): the {title} list's key no longer says '* = Incumbent'")
    items, pages = int(m.group(1)), int(m.group(2))
    legend = dict(re.findall(r"\b([A-Z]{2,3}) = ([A-Z][a-z]+(?: [A-Z][a-z]+)*)", key.group(0)))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'name="([^"]+)" value=" " onclick="javascript:__doPostBack\(&#39;[^&]+&#39;,&#39;&#39;\)" title="Next Page"', page)
        if not nxt:
            raise SystemExit(f"Montana (state races): page {n - 1} of the {title} list has no Next Page button")
        fields = form_fields(page)
        fields.update({"__EVENTTARGET": nxt.group(1), "__EVENTARGUMENT": ""})
        time.sleep(2)
        page = ask(url, urllib.parse.urlencode(fields).encode())
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Montana (state races): asked for page {n} of the {title} list and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Montana (state races): the {title} list counts {items} rows; {len(rows)} were read")
    kept = [r for r in rows if r["Race"].strip().upper() not in FEDERAL]
    odd = sorted({r["District Type"] for r in kept} - STATE_TYPES)
    if odd:
        raise SystemExit(f"Montana (state races): the {title} list has district types this loader does not know: {odd}")
    return {"title": title, "url": url, "items": items, "pages": pages, "legend": legend, "incumbent_mark": "* = Incumbent",
            "fetched": dt.date.today().isoformat(), "columns": list(rows[0].keys()) if rows else [], "rows": kept}


def cached_list(kind, path, say):
    """The list's state rows, read afresh when the kept copy is two days old or more; the kept copy if the site fails."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8")), "kept copy (under two days old)"
    try:
        got = read_list(kind)
    except SystemExit as e:
        if not os.path.exists(path):
            raise
        say(f"    Montana (state races): {e}; using the copy kept on {day_of(path)}")
        return json.load(open(path, encoding="utf-8")), "kept copy (the site could not be read)"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(got, fh, ensure_ascii=False, indent=0)
    os.replace(tmp, path)
    say(f"      {got['title']} Candidate List: {got['items']} rows on {got['pages']} pages, {len(got['rows'])} for state offices")
    return got, "read afresh"


def fetch_file(url, path, magic, say):
    """An official results file, kept 30 days; at most three tries; a file that is not what it should be stops the loader."""
    net.download(url, path, 30, tries=3, say=say)
    with open(path, "rb") as fh:
        head = fh.read(8)
    if not head.startswith(magic):
        raise SystemExit(f"Montana (state races): {os.path.basename(path)} is not the file expected from {url} (a bot check?); stopped")
    return path


# ---------- races ----------

def race_of(race_text, district_text, term):
    """(race_id, info) for a state race as the lists and the workbook write it; SystemExit for anything else."""
    race = re.sub(r"\s+", " ", (race_text or "").strip().upper())
    dist_digits = re.findall(r"\d+", district_text or "")
    m = re.fullmatch(r"STATE (SENATOR|REPRESENTATIVE) DISTRICT (\d+)", race)
    if m:
        d = str(int(m.group(2)))
        key = "SS" if m.group(1) == "SENATOR" else "SH"
        info = {"level": "legislature", "office_kind": "state_senate" if key == "SS" else "state_house",
                "office": "State Senator" if key == "SS" else "State Representative", "jurisdiction": f"{CHAMBER[key]} District {d}",
                "jurisdiction_id": d, "district": d, "seat": None, "special": 0, "partisan": 1, "chamber": CHAMBER[key], "key": key}
        rid = f"2026-{STATE}-{key}{d}"
    else:
        m = re.fullmatch(r"PUBLIC SERVICE COMMISSIONER, DISTRICT (\d+)", race)
        if m:
            d = str(int(m.group(1)))
            info = {"level": "statewide", "office_kind": "public_service_commissioner", "office": "Public Service Commissioner",
                    "jurisdiction": f"Public Service Commission District {d}", "jurisdiction_id": f"PSC{d}", "district": d, "seat": None,
                    "special": 0, "partisan": 1, "chamber": None, "key": "PSC"}
            rid = f"2026-{STATE}-PSC{d}"
        else:
            m = re.fullmatch(r"SUPREME COURT JUSTICE #(\d+)", race)
            if m:
                s = str(int(m.group(1)))
                info = {"level": "court", "office_kind": "supreme_court", "office": "Supreme Court Justice", "jurisdiction": NAME,
                        "jurisdiction_id": STATE, "district": None, "seat": s, "special": 0, "partisan": 0, "chamber": None, "key": "SC"}
                rid = f"2026-{STATE}-SC{s}"
                dist_digits = []
            else:
                m = re.fullmatch(r"DISTRICT COURT JUDGE DISTRICT (\d+), DEPT (\d+)( UNEXPIRED)?", race)
                if not m:
                    raise SystemExit(f"Montana (state races): a race this loader does not know: {race_text!r}")
                d, dept, unexp = str(int(m.group(1))), str(int(m.group(2))), bool(m.group(3))
                info = {"level": "court", "office_kind": "district_court", "office": "District Court Judge",
                        "jurisdiction": f"{ordinal(d)} Judicial District", "jurisdiction_id": f"JD{d}", "district": d,
                        "seat": f"Department {dept}", "special": 1 if unexp else 0, "partisan": 0, "chamber": None, "key": "DC"}
                rid = f"2026-{STATE}-DC{d}-{dept}" + ("-UNEXP" if unexp else "")
    if term is not None:
        t = (term or "").strip().upper()
        if t == "UNEXPIRED":
            if info["key"] != "DC" or not info["special"]:
                raise SystemExit(f"Montana (state races): an unexpired term this loader does not know: {race_text!r}")
        elif t != "REGULAR":
            raise SystemExit(f"Montana (state races): a term type this loader does not know: {term!r} ({race_text!r})")
    if dist_digits and str(int(dist_digits[-1])) != info["district"]:
        raise SystemExit(f"Montana (state races): the district column ({district_text!r}) does not match the race ({race_text!r})")
    return rid, info


# ---------- the primary results ----------

def primary_votes(path):
    """{race_id: {party code: {name folded: [name on ballot, votes]}}}, {race_id: {county name}}, {race_id: {(county,
    precinct)}}, {county id: county name} for the state races, summed over every precinct."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if not all(k in heads for k in BOOK_KEEP):
        raise SystemExit(f"Montana (state races): the precinct workbook's columns changed ({[h for h in heads if h in BOOK_KEEP]})")
    ix = {k: heads.index(k) for k in BOOK_KEEP}
    votes = collections.defaultdict(lambda: collections.defaultdict(dict))
    counties, precincts, ids = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    for r in it:
        race = re.sub(r"\s+", " ", str(r[ix["Race"]] or "").strip().upper())
        county = re.sub(r"\s+", " ", str(r[ix["County"]] or "").strip())
        ids[str(r[ix["County ID"]] or "").strip()].add(county)
        if not re.match(r"(STATE SENATOR|STATE REPRESENTATIVE|PUBLIC SERVICE COMMISSIONER|SUPREME COURT JUSTICE|DISTRICT COURT JUDGE)\b", race):
            continue
        rid, _ = race_of(race, str(r[ix["District"]] or ""), None)
        name = re.sub(r"\s+", " ", str(r[ix["Full Name On Ballot"]] or "")).strip()
        cell = votes[rid][str(r[ix["Party"]] or "").strip()].setdefault(fold(name), [name, 0])
        cell[1] += int(r[ix["Votes"]] or 0)
        counties[rid].add(county)
        precincts[rid].add((county, str(r[ix["Precinct"]] or "").strip()))
    wb.close()
    bad = sorted(i for i, names in ids.items() if len(names) != 1)
    if bad:
        raise SystemExit(f"Montana (state races): the precinct workbook gives more than one county name for county id(s) {bad}")
    return votes, counties, precincts, {i: next(iter(n)) for i, n in ids.items()}


def legislative_canvass(path, parties):
    """{race_id: [(party code, total)]} from the legislative canvass. Each candidate line is the party, the votes in
    each county and the total; the county figures must add up to the total."""
    words = {v: k for k, v in parties.items()}
    pat = re.compile(r"(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")((?: \d+)+)")
    out, cur, heads = collections.defaultdict(list), None, 0
    for _page, _y, t in lines(path):
        t = re.sub(r"\s+", " ", t).strip()
        m = re.fullmatch(r"(HD|SD) (\d+) Total", t)
        if m:
            cur = f"2026-{STATE}-{'SH' if m.group(1) == 'HD' else 'SS'}{int(m.group(2))}"
            out[cur]
            heads += 1
            continue
        m = pat.fullmatch(t)
        if m:
            if cur is None:
                raise SystemExit("Montana (state races): a candidate line in the legislative canvass before any district heading")
            nums = [int(x) for x in m.group(2).split()]
            if len(nums) < 2 or sum(nums[:-1]) != nums[-1]:
                raise SystemExit(f"Montana (state races): a line of the legislative canvass under {cur} does not add up")
            out[cur].append((words[m.group(1)], nums[-1]))
    if heads != len(out):
        raise SystemExit("Montana (state races): a district heading appears twice in the legislative canvass")
    return out


# ---------- counties ----------

def county_names(path=COUNTY_ZIP):
    """{folded county name: (GEOID, 'Name County')} for Montana, from the Census file's attribute table only."""
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
    return out


# ---------- the roster: names, parties, districts and ids only ----------

def roster():
    con = sqlite3.connect(f"file:{ROSTER_DB}?mode=ro", uri=True)
    seats, everyone = collections.defaultdict(list), []
    for bid, first, last, full, other, party, district, chamber, since in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, district, chamber, term_start "
            "FROM legislators WHERE is_current = 1"):
        p = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "other": other or "",
             "party": party, "chamber": chamber, "district": str(int(district)) if str(district or "").isdigit() else district,
             "since": since}
        seats[(chamber, p["district"])].append(p)
        everyone.append(p)
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, everyone, as_of


def forms(p, strict=False):
    """The ways the roster writes a person: first and last, the full name, and (not strict) its other names."""
    out = [([w for w in fold(p["first"]).split()], fold(p["last"]).split()[-1] if fold(p["last"]) else "")] if p["last"] else []
    out.append(name_parts(p["full"]))
    if not strict:
        out += [name_parts(n.strip()) for n in p["other"].split(";") if n.strip()]
    return [f for f in out if f[1]]


def person_fits(name, p, strict=False):
    cand = name_parts(name)
    return any(fits(cand, f) for f in forms(p, strict))


def shown(caps, member=None):
    """The filed name in ordinary capitals; a matched member as the roster spells the same letters."""
    caps = re.sub(r"\s+", " ", caps.lstrip("*").strip())
    if member and fold(member["full"]).replace(" ", "") == fold(caps).replace(" ", ""):
        return member["full"]
    return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))


# ======================================================================================================================
# County and local offices: county by county, from what each county's election office posts (see the docstring)
# ======================================================================================================================

LOCAL_DIR = "local"                                    # under the cache folder: ballot_cache/mt/local/
READ_ON = "2026-10-01"                                 # the day the counties' election pages were read by hand
LINK_DAYS, FILE_DAYS = 7, 14                           # how long a page's links and a fetched file are kept before asking again
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st30_mt_place2020.txt"
PLACE_FILE = "census_st30_mt_place2020.txt"
DIRECTORY = "https://sosmt.gov/elections/election-administrators-contact-list/"
MCA = "https://archive.legmt.gov/bills/mca/title_0130/chapter_0010/part_0010/section_0040/0130-0010-0010-0040.html"
SRC_PLACES = "mt-census-2020-places"

# What each county's election office posts for November 3, 2026 that a script can fetch. "page" is the county's own
# page, "link" the words of the link on it (the document's own address changes when a county posts a corrected file, so
# the link is looked up afresh), "href" a pattern the link's address must fit.
LOCAL_SOURCES = collections.OrderedDict([
    ("Gallatin", {"how": "ballots", "page": "https://www.gallatinmt.gov/257/Election-Department",
                  "link": r"^2026 General Federal Sample Ballots$", "href": r"/DocumentCenter/View/\d+"}),
    ("Flathead", {"how": "list", "reader": "flathead", "page": "https://flatheadcounty.gov/department-directory/election/election-current",
                  "link": r"FLATHEAD COUNTY CANDIDATES FOR THE 2026 GENERAL ELECTION", "href": r"/download_file/"}),
    ("Cascade", {"how": "list", "reader": "cascade", "page": "https://www.cascadecountymt.gov/692/2026-Federal-General-Election-Informatio",
                 "link": r"^2026 Federal General County Candidate Certification$", "href": r"/DocumentCenter/View/\d+"}),
    ("Lewis and Clark", {"how": "ballots", "page": "https://www.lccountymt.gov/Government/Clerk-and-Recorder-Treasurer/Elections/Example-Ballots",
                         "link": r"^2026 General\b.*\b(Ballot|Sample)", "href": r"\.pdf"}),
    ("Sanders", {"how": "ballots", "page": "https://co.sanders.mt.us/201/Elections",
                 "link": r"^P-\d+ .*SAMPLE BALLOTS?(?: \(PDF\))?$", "href": r"/DocumentCenter/View/\d+"}),
    ("Richland", {"how": "ballots", "page": "https://www.richland.org/elections.html", "link": r"^Sample Ballot Pub$", "href": r"\.pdf$"}),
    ("Carbon", {"how": "ballots", "page": "https://carbonmt.gov/2026-federal-general-election-sample-ballots/",
                "link": r"^Precinct \d+$", "href": r"\.pdf$"}),
    ("Fergus", {"how": "ballots", "page": "https://fergusmt.gov/departments/elections", "link": r"^Precinct \d+$", "href": r"SampleBallot\.pdf$"}),
    ("Beaverhead", {"how": "list", "reader": "beaverhead", "page": "https://www.beaverheadcounty.org/election-office/",
                    "link": r"^2026 Federal General Candidates for Election$", "href": r"\.pdf$"}),
    ("Madison", {"how": "ballots", "page": "https://madisoncountymt.gov/159/Election-Information",
                 "link": r"^\d{1,2}(?:-\d)? [A-Z][A-Z0-9 ]+$", "href": r"/DocumentCenter/View/\d+"}),
])

# What the other counties' own sites carried when they were read by hand on READ_ON: (what was found, the page).
# A county not named here was not reached that day (its site was not found, or its certificate did not match).
NOTHING = "the county's election page, as a script reads it, linked no sample ballot or candidate list for the November 3 election"
REFUSED = "the county's website refused a script (HTTP 403) and was not asked again"
CHECKED = {
    "Yellowstone": (NOTHING, "https://www.yellowstonecountymt.gov/elections/"),
    "Missoula": ("the county's election page linked its November 3 sample ballots in a shared folder that refuses a script (HTTP 403), so they "
                 "wait for copies saved by hand", "https://www.missoulacounty.gov/departments/elections/current-election"),
    "Ravalli": (NOTHING, "https://ravalli.us/145/Elections"),
    "Silver Bow": ("the county's Candidates page carried the list certified for the June primary only", "https://www.co.silverbow.mt.us/3482/Candidates"),
    "Lake": ("the county's Sample Ballots page sent voters to the state's My Voter Page, which shows a ballot only to the voter who signs in, and "
             "posted no list for the county", "https://www.lakemt.gov/185/Sample-Ballots"),
    "Lincoln": (NOTHING, "https://lincolncountymt.us/elections/"),
    "Hill": (NOTHING, "https://hillcounty.us/elections/index.php"),
    "Park": (NOTHING, "https://www.parkcountymt.gov/Government-Departments/Elections/"),
    "Big Horn": ("the county's election page carried a county candidate list from 2022 and nothing for 2026",
                 "https://www.bighorncountymt.gov/237/Federal-General-Elections"),
    "Jefferson": (NOTHING, "https://jeffersoncounty-mt.gov/elections/"),
    "Stillwater": (NOTHING, "https://www.stillwatercountymt.gov/201/Elections"),
    "Deer Lodge": (NOTHING, "https://adlc.us/1097/Elections"),
    "Rosebud": (NOTHING, "https://rosebudcountymt.gov/departments/elections-administrator/"),
    "Teton": (NOTHING, "https://tetoncountymt.gov/clerk-recorder-elections/"),
    "Toole": (NOTHING, "https://toolecountymt.gov/election-office/"),
    "Mineral": ("the county's election page carried notices for the November 3 election but no sample ballot or candidate list",
                "https://co.mineral.mt.us/departments/elections/"),
    "Fallon": (NOTHING, "https://falloncountymt.gov/elections/"),
    "Sweet Grass": (NOTHING, "https://sgcountymt.gov/government-departments/county-govt/clerk-recorder/elections/"),
    "Pondera": (NOTHING, "https://www.ponderacountymt.gov/clerkandrecorder"),
    "Custer": (NOTHING, "https://custercountymt.gov/services/custer-county-election-administration/"),
    "Roosevelt": (NOTHING, "https://www.rooseveltcountymt.gov/election-administration-2/"),
    "Broadwater": (NOTHING, "https://www.broadwatercountymt.gov/departments/government/elections/index.php"),
    "Chouteau": (NOTHING, "https://www.chouteaucountymt.gov/clerkandrecorder"),
    "Sheridan": (NOTHING, "https://www.sheridancountymt.gov/elections"),
    "Daniels": (NOTHING, "https://www.danielscountymt.gov/clerk-recorder"),
    "Blaine": (NOTHING, "https://blainecounty-mt.gov/clerk-recorder/"),
    "Granite": (NOTHING, "https://www.granitecountymt.gov/604/Elections-Office"),
    "Wheatland": (NOTHING, "https://wheatlandcomt.gov/departments/clerk-recorder/elections/"),
    "McCone": (NOTHING, "https://mcconecountymt.gov/departments/election-administration"),
    "Treasure": (NOTHING, "https://www.treasurecountymt.gov/general-1-1"),
    "Liberty": (NOTHING, "https://www.libertycountymt.gov/clerk-and-recorder"),
    "Valley": (NOTHING, "https://www.valleycountymt.gov/1250/Clerk-Recorder-Superintendent-of-Schools"),
    "Dawson": (REFUSED, "https://www.dawsoncountymontana.com/"),
    "Powell": (REFUSED, "https://www.powellcountymt.gov/"),
    "Musselshell": (REFUSED, "https://www.musselshellcounty.org/"),
    "Glacier": (REFUSED, "https://glaciercountymt.gov/"),
}

WHAT = "county offices, justices of the peace and conservation district supervisors"
VOTE = re.compile(r"^\(VOTE (?:FOR (?:UP TO |NO MORE THAN )?(?P<n>ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)|IN ONE OVAL)\)$")
NUMBER = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10}
NOISE = re.compile(r"^(VOTE BOTH SIDES|VOTE IN ALL COLUMNS|INSTRUCTIONS TO VOTERS|TURN BALLOT OVER|CONTINUE VOTING.*)$")
HEADING = re.compile(r"\b([A-Z][A-Z &.'-]*?) COUNTY, MONTANA - (NOVEMBER 3, 2026)\b")
RETAIN = re.compile(r"^Shall (?:Chief Justice|Justice|Judge) (?P<name>.+?) of (?:the )?(?P<court>.+?) of the state of Montana be retained in office "
                    r"for another term\?$")
STATE_TITLE = re.compile(r"^(UNITED STATES (?:SENATOR|REPRESENTATIVE)|STATE (?:SENATOR|REPRESENTATIVE)|PUBLIC SERVICE COMMISSIONER|SUPREME COURT|"
                         r"CHIEF JUSTICE|DISTRICT COURT JUDGE|CLERK OF THE SUPREME COURT)\b")
# the party line under a name, as ballots and lists print it -> the words Montana's state rows use (None: a nonpartisan office)
PARTY_WORDS = {"REPUBLICAN": "Republican", "DEMOCRAT": "Democratic", "DEMOCRATIC": "Democratic", "LIBERTARIAN": "Libertarian",
               "INDEPENDENT": "Independent", "GREEN": "Green", "NONPARTISAN": None, "NON PARTISAN": None, "NON-PARTISAN": None}
# a county office's kind is that of the office its title names first (Sheriff/Coroner is the sheriff's)
KIND_PATTERNS = [(r"\bCLERK OF (?:THE )?(?:DISTRICT )?COURT\b", "clerk_of_court"), (r"\bCLERK\b", "county_clerk"), (r"\bSHERIFF\b", "sheriff"),
                 (r"\bCORONER\b", "coroner"), (r"\bATTORNEY\b", "county_attorney"), (r"\bTREASURER\b", "county_treasurer"),
                 (r"\bSUPERINTENDENT OF SCHOOLS\b", "county_school_superintendent"), (r"\bAUDITOR\b", "county_auditor"),
                 (r"\bASSESSOR\b", "county_assessor"), (r"\bSURVEYOR\b", "county_surveyor"),
                 (r"\bPUBLIC ADMINISTRATOR\b", "public_administrator"), (r"\bRECORDER\b", "county_recorder")]
SMALL_WORDS = {"OF", "THE", "AND"}
CAPS_BALLOT = "The ballot prints names in capitals; they are shown here in ordinary capitals."
RETAIN_NOTE = ("A retention vote: the ballot asks whether Judge {name} shall be retained in office for another term, Yes or No. That is the "
               "form of the ballot when the sitting judge is the only candidate (MCA 13-14-212).")
RETAIN_CAND = "Standing for retention: voters answer Yes or No."
ONE_JUDGE = ("One candidate is on the county's list. If that candidate is the sitting justice of the peace, the ballot asks instead whether "
             "the judge shall be retained in office, Yes or No (MCA 13-14-212).")
ONE_JUDGE_STARRED = ("One candidate is on the county's list, marked there as the incumbent. When the sitting judge is the only candidate the "
                     "ballot asks whether the judge shall be retained in office, Yes or No (MCA 13-14-212).")
ODD_YEAR = ("A city or town office on a ballot of an even-numbered year: Montana's cities and towns elect their officers in November of "
            "odd-numbered years (MCA 13-1-104), and the ballot does not say whether this is for an unexpired term.")
GIVEN_UP = set()                                       # hosts that refused three times in this run are not asked again


class Layout(Exception):
    """A file that does not have the layout this loader was checked against. The message names the file, the page or the
    row and the check that failed; never the text."""


class NotPosted(Exception):
    """The county's page carries no link of the kind looked for."""


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def slug(text):
    """'Lewis and Clark' -> 'lewis-and-clark': letters, digits and hyphens, for ids and file names only."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def kept(path, days):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < days * 86400


def keep_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)
    os.replace(path + ".part", path)


def fetch_bytes(url):
    """The bytes at an address, through states/net.py (the kit's honest User-Agent), one request at a time and a second
    and a half apart; at most three tries, and a host that fails three times is not asked again in this run."""
    host = urllib.parse.urlparse(url).netloc.lower()
    if host in GIVEN_UP:
        raise ConnectionError(f"{host} already refused in this run")
    last = None
    for attempt in range(3):
        try:
            raw = net.get(url, timeout=120)
            time.sleep(1.5)
            return raw
        except (HTTPError, URLError, OSError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    GIVEN_UP.add(host)
    raise ConnectionError(f"{host}: {type(last).__name__} {getattr(last, 'code', '')}".strip())


# ---------- a PDF's text, glyph by glyph ----------

def pdf_pages(pdf):
    """[(page, resources, media box)] in reading order, from the trailer's /Root."""
    cat = None
    for m in reversed(list(re.finditer(rb"/Root\s+(\d+)\s+\d+\s+R", pdf.data))):
        v = pdf._obj(int(m.group(1)))[0]
        if isinstance(v, dict) and "Pages" in v:
            cat = v
            break
    out = []

    def walk(node, res, box, seen):
        if isinstance(node, Ref):
            if node.num in seen:
                return
            seen = seen | {node.num}
        node = pdf.get(node)
        if not isinstance(node, dict):
            return
        res = pdf.get(node.get("Resources")) or res
        box = pdf.get(node.get("MediaBox")) or box
        if node.get("Type") == "Pages" or "Kids" in node:
            for kid in pdf.get(node.get("Kids")) or []:
                walk(kid, res, box, seen)
        else:
            out.append((node, res, [float(pdf.get(x)) for x in box] if box else None))
    if cat:
        walk(cat.get("Pages"), {}, None, frozenset())
    return out


def glyph_runs(pdf, page, res, box=None):
    """Every upright glyph on a page as (x0, y, size, text, x1, width of an em, whether a space glyph came just before
    it): embedded forms are followed, and each glyph is placed on its own, so that a word space made of character
    spacing (a title squeezed to fit) is still a gap."""
    fonts, out = {}, []
    spaced = [False]
    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, Ref))

    def run(data, res, ctm, depth, key):
        res_d = pdf.get(res) or {}
        fres = pdf.get(res_d.get("Font")) or {}
        xres = pdf.get(res_d.get("XObject")) or {}
        saved = []
        tm = tlm = [1, 0, 0, 1, 0, 0]
        st = {"font": None, "size": 1.0, "tc": 0.0, "tw": 0.0, "th": 1.0, "tl": 0.0, "rise": 0.0}

        def show(s):
            nonlocal tm
            font = st["font"]
            if font is None or not isinstance(s, (bytes, bytearray)):
                return
            size, th, tc, tw, rise = st["size"], st["th"], st["tc"], st["tw"], st["rise"]
            if font.two:
                codes = [int.from_bytes(s[k:k + 2], "big") for k in range(0, len(s) - 1, 2)]
                glyphs = [(font.map.get(c, ""), c) for c in codes]
            else:
                glyphs = [(font.map.get(c) or bytes([c & 0xFF]).decode("cp1252", "replace"), c) for c in s]
            for text, code in glyphs:
                w = font.width(code) * size * th
                a = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
                b = _mul([size * th, 0, 0, size, 0, rise], _mul(_mul([1, 0, 0, 1, w, 0], tm), ctm))
                if not text.strip():
                    spaced[0] = spaced[0] or bool(text)
                elif a[0] > 0 and abs(a[1]) < 0.01 * a[0]:
                    if box is None or (box[1] - 1 <= a[5] <= box[3] + 1):
                        out.append((a[4], a[5], abs(a[3]) or size, text, b[4], a[0], spaced[0]))
                    spaced[0] = False
                tm = _mul([1, 0, 0, 1, w + (tc + (tw if (not font.two and code == 32) else 0)) * th, 0], tm)

        for op, a in _ops(data):
            if op == "q":
                saved.append((ctm[:], dict(st)))
            elif op == "Q":
                if saved:
                    ctm, old = saved.pop()
                    st.update(old)
            elif op == "cm" and len(a) == 6:
                ctm = _mul([float(x) for x in a], ctm)
            elif op == "BT":
                tm = tlm = [1, 0, 0, 1, 0, 0]
            elif op == "Tf" and len(a) == 2:
                name = str(a[0])
                if (key, name) not in fonts:
                    fonts[(key, name)] = Font(pdf, fres.get(name))
                st["font"], st["size"] = fonts[(key, name)], float(a[1])
            elif op == "Tc" and a:
                st["tc"] = float(a[0])
            elif op == "Tw" and a:
                st["tw"] = float(a[0])
            elif op == "Tz" and a:
                st["th"] = float(a[0]) / 100
            elif op == "TL" and a:
                st["tl"] = float(a[0])
            elif op == "Ts" and a:
                st["rise"] = float(a[0])
            elif op in ("Td", "TD") and len(a) == 2:
                tx, ty = float(a[0]), float(a[1])
                if op == "TD":
                    st["tl"] = -ty
                tlm = _mul([1, 0, 0, 1, tx, ty], tlm)
                tm = tlm
            elif op == "Tm" and len(a) == 6:
                tm = tlm = [float(x) for x in a]
            elif op == "T*":
                tlm = _mul([1, 0, 0, 1, 0, -st["tl"]], tlm)
                tm = tlm
            elif op == "Tj" and a:
                show(a[-1])
            elif op in ("'", '"') and a:
                tlm = _mul([1, 0, 0, 1, 0, -st["tl"]], tlm)
                tm = tlm
                if op == '"' and len(a) == 3:
                    st["tw"], st["tc"] = float(a[0]), float(a[1])
                show(a[-1])
            elif op == "TJ" and a and isinstance(a[-1], list):
                for item in a[-1]:
                    if isinstance(item, (bytes, bytearray)):
                        show(item)
                    elif isinstance(item, (int, float)):
                        tm = _mul([1, 0, 0, 1, -float(item) / 1000.0 * st["size"] * st["th"], 0], tm)
            elif op == "Do" and a and depth < 6:
                ref = xres.get(str(a[-1]))
                d = pdf.get(ref)
                if isinstance(ref, Ref) and isinstance(d, dict) and d.get("Subtype") == "Form":
                    mat = [float(pdf.get(x)) for x in (pdf.get(d.get("Matrix")) or [1, 0, 0, 1, 0, 0])]
                    run(pdf.stream(ref) or b"", pdf.get(d.get("Resources")) or res_d, _mul(mat, ctm), depth + 1, ref.num)

    run(data, res, [1, 0, 0, 1, 0, 0], 0, 0)
    return out


def rows_of(runs):
    """Glyphs grouped into printed rows, top to bottom: [(y, [glyphs])]."""
    out = []
    for r in sorted(runs, key=lambda r: (-round(r[1], 1), r[0])):
        if out and abs(out[-1][0] - r[1]) <= max(1.0, 0.3 * r[2]):
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return out


def joined(glyphs):
    """The glyphs of one cell as text: a space where the file has a space glyph, or where a gap is wider than a fifth of
    the type (Cascade's list sets the letters of its bold title up to 0.16 of an em apart, and Carbon's ballots make a
    word space of 0.22 with no space glyph at all)."""
    text, end = "", None
    for x0, _y, _size, t, x1, em, sp in sorted(glyphs, key=lambda r: r[0]):
        if end is not None and (sp or x0 - end > 0.2 * em) and not text.endswith(" "):
            text += " "
        text += t
        end = x1 if end is None else max(end, x1)
    return clean(text)


def cells_of(row, gap=1.4):
    """One printed row cut into cells, left to right, where a gap is wider than `gap` times the type. The cells are
    still glyphs: nothing is turned into text here, so a caller can drop a cell unread."""
    rr = sorted(row, key=lambda r: r[0])
    out, cur, end = [], [rr[0]], rr[0][4]
    for r in rr[1:]:
        if r[0] - end > gap * max(r[2], cur[-1][2]):
            out.append(cur)
            cur, end = [r], r[4]
        else:
            cur.append(r)
            end = max(end, r[4])
    out.append(cur)
    return out


def extent(cell):
    return min(r[0] for r in cell), max(r[4] for r in cell)


# ---------- a sample ballot as the voting system prints it ----------

def ballot_contests(raw, county, where):
    """One sample-ballot file -> (its contests, what was counted). A contest is {page, person, title, vote (how many to
    vote for; None for 'in one oval'), cands [(name, party line)], retain (the judge named by a retention question),
    options}. `where` is the file's name, for a message."""
    pdf = PDF(raw)
    pages = pdf_pages(pdf)
    pages_rows = [rows_of(glyph_runs(pdf, page, res, box)) for page, res, box in pages]
    if not pages or not any(pages_rows):
        raise Layout(f"{where}: no text to read (a scanned ballot?)")
    heads = [m for rows in pages_rows for _y, row in rows for m in [HEADING.search(joined(row))] if m]
    want = fold(county).replace(" and ", " ")
    if not heads or any(want not in fold(m.group(1)).replace(" and ", " ") for m in heads):
        raise Layout(f"{where}: the ballot's heading does not name {county} County and November 3, 2026")

    # the column grid, from the '(VOTE FOR ONE)' lines, which sit in the middle of their columns
    centres, sizes, votes_seen, marks = [], [], 0, 0
    for rows in pages_rows:
        for _y, row in rows:
            for cell in cells_of(row):
                t = joined(cell)
                if VOTE.match(t):
                    x0, x1 = extent(cell)
                    centres.append((x0 + x1) / 2)
                    sizes.append(round(cell[0][2], 2))
                    votes_seen += 1
    if not centres:
        raise Layout(f"{where}: no '(VOTE FOR ...)' line")
    base = collections.Counter(sizes).most_common(1)[0][0]
    centres.sort()
    groups = [[centres[0]]]
    for c in centres[1:]:
        if c - groups[-1][-1] <= 0.6 * base:
            groups[-1].append(c)
        else:
            groups.append([c])
    cs = [sum(g) / len(g) for g in groups]
    if len(cs) < 2:
        raise Layout(f"{where}: every contest is in one column, so the column width cannot be told")
    pitch = min(b - a for a, b in zip(cs, cs[1:]))
    if any(abs((b - a) / pitch - round((b - a) / pitch)) > 0.06 for a, b in zip(cs, cs[1:])):
        raise Layout(f"{where}: the columns are not evenly spaced")
    left = cs[0] - pitch / 2
    for rows in pages_rows:                              # the party lines, counted on their own (cells, not columns)
        for _y, row in rows:
            for cell in cells_of(row):
                if 0.87 <= cell[0][2] / base <= 0.93 and joined(cell).upper() in PARTY_WORDS:
                    marks += 1

    contests = []
    for pn, rows in enumerate(pages_rows, 1):
        cols = collections.defaultdict(list)
        for y, row in rows:
            by = collections.defaultdict(list)
            for r in row:
                by[int((r[0] + 0.5 - left) // pitch)].append(r)
            for col, rr in by.items():
                t = joined(rr)
                if t:
                    cols[col].append((y, min(r[0] for r in rr), max(r[4] for r in rr), max(r[2] for r in rr), t))
        stream = [(col, cs[0] + col * pitch, y, x0, x1, size, t)
                  for col in sorted(cols) for y, x0, x1, size, t in sorted(cols[col], key=lambda ln: -ln[0])]

        def party_under(k, x0, y):
            """The party line right under a name at stream[k - 1], when stream[k] is one."""
            if k >= len(stream):
                return None
            c2, _ce, y2, x02, _x12, s2, t2 = stream[k]
            if (c2 == col and 0.87 <= s2 / base <= 0.93 and 0 < y - y2 <= 1.6 * base and 0 < x02 - x0 <= 1.5 * base
                    and t2.upper() in PARTY_WORDS):
                return t2
            return None

        cur, pending, k = None, [], 0
        while k < len(stream):
            col, centre, y, x0, x1, size, t = stream[k]
            rel = size / base
            k += 1
            if rel > 1.12 or rel < 0.85 or NOISE.match(t):
                continue                                           # the ballot's heading, margin marks, instructions
            m = VOTE.match(t)
            if m:
                first = max((j for j, h in enumerate(pending) if h.startswith("FOR ")), default=None)
                title = pending[first:] if first is not None else pending[-4:]
                cur = {"page": pn, "person": first is not None, "title": clean(" ".join(title)),
                       "vote": NUMBER[m.group("n")] if m.group("n") else None, "cands": [], "text": [], "options": []}
                contests.append(cur)
                pending = []
                continue
            if 0.87 <= rel <= 0.93:
                if t.upper() in PARTY_WORDS:
                    raise Layout(f"{where}: page {pn}: a party line with no name above it")
                continue                                           # a footer in the smaller type (the precinct, 'VOTE BOTH SIDES')
            party = party_under(k, x0, y)
            if party is None and k < len(stream):                  # a name printed on two lines
                c2, _ce, y2, x02, _x12, s2, t2 = stream[k]
                if c2 == col and abs(s2 / base - 1) <= 0.05 and abs(x02 - x0) <= 1.0 and 0 < y - y2 <= 1.4 * base:
                    two = party_under(k + 1, x02, y2)
                    if two is not None:
                        t, party, k = f"{t} {t2}", two, k + 1
            if party is not None:
                if cur is None or not cur["person"]:
                    raise Layout(f"{where}: page {pn}: a name with a party line outside any contest for an office")
                cur["cands"].append((t, party))
                k += 1
                continue
            centred = abs((x0 + x1) / 2 - centre) <= 0.6 * base
            if cur is not None and not centred and re.match(r"^(YES|NO)\b", t):
                cur["options"].append(t)
            elif centred and not re.search(r"[a-z]", t):
                pending.append(t)                                  # a section heading, or a line of the next contest's title
            elif cur is not None:
                cur["text"].append(t)                              # the words of a question
    placed = sum(len(c["cands"]) for c in contests)
    if placed != marks:
        raise Layout(f"{where}: {marks} party lines counted on the pages, {placed} names placed in contests")
    if len(contests) != votes_seen:
        raise Layout(f"{where}: {votes_seen} '(VOTE ...)' lines, {len(contests)} contests")
    for c in contests:
        c["retain"] = None
        if not c["person"]:
            continue
        c["title"] = clean(c["title"][4:])
        text = clean(" ".join(c.pop("text")))
        if c["options"] or (c["vote"] is None):
            m = RETAIN.match(text)
            if not m or c["cands"] or [o.upper() for o in c["options"]] != ["YES", "NO"]:
                raise Layout(f"{where}: page {c['page']}: a Yes or No contest for an office that is not a retention question")
            c["retain"] = clean(m.group("name"))
    return contests, {"pages": len(pages), "forms": len(heads), "names": placed, "contests": len(contests)}


def state_race_of(title):
    """The race id of a state contest as a ballot titles it (None for Congress), by the state loader's own race_of."""
    t = clean(title.upper())
    if t.startswith("UNITED STATES"):
        return None
    t = re.sub(r"^(PUBLIC SERVICE COMMISSIONER) (DISTRICT)", r"\1, \2", t)
    t = re.sub(r"\s*\(?UNEXPIRED TERM\)?", " UNEXPIRED", t)
    return race_of(t, "", None)[0]


def county_ballots(county, files):
    """Every sample ballot of one county -> its county and local contests, in the order first met, each with the files
    that print it. `files` is [(label, path, source id)]."""
    found, state, measures, facts = collections.OrderedDict(), {}, collections.Counter(), []
    for label, path, sid in files:
        where = os.path.basename(path)
        with open(path, "rb") as fh:
            contests, fact = ballot_contests(fh.read(), county, where)
        fact.update(label=label, source=sid, local=0, state=0, measures=0)
        for c in contests:
            if not c["person"]:
                measures[c["title"]] += 1
                fact["measures"] += 1
                continue
            names = tuple(sorted(c["cands"]))
            if STATE_TITLE.match(c["title"]):
                fact["state"] += 1
                got = state.setdefault(c["title"], {"names": names, "retain": c["retain"], "orders": set()})
                if (got["names"], got["retain"]) != (names, c["retain"]):
                    raise Layout(f"{where}: a state contest's names differ from another ballot of {county} County")
                got["orders"].add(tuple(n for n, _p in c["cands"]))
                continue
            fact["local"] += 1
            got = found.get(c["title"])      # the same title again is the same contest on another ballot form (Gallatin: 68 forms in one file)
            if got is None:
                got = found[c["title"]] = {"title": c["title"], "vote": c["vote"], "cands": list(c["cands"]), "names": names, "retain": c["retain"],
                                           "forms": 0, "source": sid, "orders": set(), "status": None, "remarks": [], "starred": []}
            elif (got["names"], got["retain"], got["vote"]) != (names, c["retain"], c["vote"]):
                raise Layout(f"{where}: a contest's names differ from another ballot of {county} County (two districts under one title?)")
            got["forms"] += 1
            got["orders"].add(tuple(n for n, _p in c["cands"]))
        facts.append(fact)
    rotated = any(len(got["orders"]) > 1 for got in list(found.values()) + list(state.values()))      # the same names in another order
    return list(found.values()), {"files": facts, "forms": sum(f["forms"] for f in facts), "state": state, "measures": measures, "rotated": rotated}


# ---------- the three county candidate lists ----------

def party_cell(text, where):
    key = clean(text).upper()
    if key not in PARTY_WORDS:
        raise Layout(f"{where}: a party cell holds words that are not a party")
    return clean(text)


def flathead_list(raw, where):
    """Flathead County's one-page list. Its heading row names eleven columns; only the cells under the first four (the
    office, first name, last name and party) are ever turned into text. A cell belongs to the heading its middle is
    nearest; the cells under Mailing Address, City, State, Zip, Email, Phone and Website are dropped as glyphs, unread."""
    pdf = PDF(raw)
    pages = pdf_pages(pdf)
    if len(pages) != 1:
        raise Layout(f"{where}: {len(pages)} pages, not the one page this loader was checked against")
    rows = [(y, cells_of(row, 0.6)) for y, row in rows_of(glyph_runs(pdf, *pages[0]))]
    # the heading row is the first row from the top with several cells (only the one-cell title sits above it); no other
    # row is turned into text to find it
    head = next(((y, cells, [joined(c).lower() for c in cells]) for y, cells in rows if len(cells) >= 4), None)
    if head is None or head[2][1:4] != ["first name", "last name", "party affiliation"] or "2026" not in head[2][0]:
        raise Layout(f"{where}: the heading row does not begin with the office, First Name, Last Name and Party Affiliation")
    mids = [sum(extent(c)) / 2 for c in head[1]]
    labels, people, parties = [], [], 0
    for n, (y, cells) in enumerate(rows, 1):
        if y >= head[0] - 1:
            continue                                               # the title line and the heading row
        take = {}
        for c in cells:
            mid = sum(extent(c)) / 2
            col = min(range(len(mids)), key=lambda j: abs(mid - mids[j]))
            if col < 4:
                if col in take:
                    raise Layout(f"{where}: row {n}: two cells under one heading")
                take[col] = joined(c)                              # only now is an allowed cell turned into text
        if 0 in take:
            labels.append((y, take[0]))
        if any(k in take for k in (1, 2, 3)):
            if not all(k in take for k in (1, 2, 3)):
                raise Layout(f"{where}: row {n}: a candidate row without a first name, a last name and a party")
            parties += 1
            people.append((y, clean(f"{take[1]} {take[2]}"), party_cell(take[3], f"{where}: row {n}")))
    # an office printed once for several candidates sits level with the middle of their rows
    out, i = [], 0
    for ly, office in labels:
        group = []
        while i < len(people):
            group.append(people[i])
            i += 1
            mean = sum(p[0] for p in group) / len(group)
            if abs(mean - ly) <= 2.5:
                break
            if mean < ly - 2.5:
                raise Layout(f"{where}: an office does not sit level with its candidates")
        else:
            raise Layout(f"{where}: an office with no candidate row")
        out.append({"title": office, "cands": [(nm, pt) for _y, nm, pt in group], "status": None, "remarks": [], "starred": []})
    if i != len(people) or sum(len(c["cands"]) for c in out) != parties:
        raise Layout(f"{where}: candidate rows left without an office")
    return {"contests": out, "withdrawn": [], "rows": parties, "published": "", "read": "the office, First Name, Last Name and Party Affiliation columns",
            "never": "the Mailing Address, City, State, Zip, Email, Phone and Website columns"}


def cascade_list(raw, where):
    """Cascade County's Certified Local Candidate List (the second page; the first is a scanned letter). An office is a
    line of its own; a candidate's row is the name, 'Certified' (or 'Elected', where the election was canceled) and the
    party, then the address, phone and e-mail. Only the first three cells of such a row are ever turned into text; the
    rest are dropped as glyphs, unread. A line of its own is read only when it starts left of the address column."""
    pdf = PDF(raw)
    rows = []
    for page, res, box in pdf_pages(pdf):
        rows += [(y, cells_of(row, 0.6)) for y, row in rows_of(glyph_runs(pdf, page, res))]
    wide = [cells for _y, cells in rows if len(cells) >= 4]
    if not wide:
        raise Layout(f"{where}: no row with a name, a mark, a party and an address (a scanned list?)")
    edge = min(extent(cells[3])[0] for cells in wide)              # where the address column starts, from the cells' places alone
    marked = [n for n, (_y, cells) in enumerate(rows, 1)
              if len(cells) >= 3 and extent(cells[2])[0] < edge - 5 and joined(cells[1]) in ("Certified", "Elected")]
    if not marked:
        raise Layout(f"{where}: no row with a name, 'Certified' and a party before the address column")
    contests, withdrawn, cur, mode, titled, parties = [], [], None, "list", 0, 0
    for n, (_y, cells) in enumerate(rows, 1):
        if n in marked:
            if cur is None or mode != "list":
                raise Layout(f"{where}: row {n}: a candidate before any office")
            status = joined(cells[1])
            if (status == "Elected") != (cur["status"] == "affirmation"):
                raise Layout(f"{where}: row {n}: 'Elected' and 'Certified' do not go with the heading above them")
            parties += 1
            cur["cands"].append((joined(cells[0]), party_cell(joined(cells[2]), f"{where}: row {n}")))
            continue
        inside = [c for c in cells if extent(c)[0] < edge - 5]      # cells that start left of the address column
        if not inside or len(inside) != len(cells):
            if mode == "list" and cur is not None and len(cells) > 1:
                raise Layout(f"{where}: row {n}: a row with an address and no 'Certified' mark")
            continue                                               # the page's own title lines (to the right of the names): not read
        if mode == "withdrawn":
            if len(inside) < 2:
                raise Layout(f"{where}: row {n}: a line under Withdrawn Candidates that is not a name, a date and an office")
            m = re.match(r"^\d{1,2}/ ?\d{1,2}/ ?\d{4} ?(.*)$", clean(" ".join(joined(c) for c in inside[1:])))
            if not m or not office_of(m.group(1)):
                raise Layout(f"{where}: row {n}: a withdrawal without a date and an office this loader knows")
            withdrawn.append(clean(m.group(1)))                    # the office only: who withdrew is not kept
            continue
        if len(inside) != 1:
            raise Layout(f"{where}: row {n}: a row that is neither a candidate nor a heading")
        text = joined(inside[0])
        if re.search(r"Certified Local Candidate List", text):
            if not re.search(r"2026 Federal General Election", text):
                raise Layout(f"{where}: the list is not the 2026 Federal General Election's")
            titled += 1
        elif text == "Withdrawn Candidates":
            mode = "withdrawn"
        else:
            m = re.fullmatch(r"Election Canceled - (.+?) - Elected by Affirmation", text)
            cur = {"title": (m.group(1) + " Supervisor") if m else text, "cands": [], "status": "affirmation" if m else None, "remarks": [],
                   "starred": []}
            if not office_of(cur["title"]):
                raise Layout(f"{where}: row {n}: a heading that is not an office this loader knows")
            contests.append(cur)
    if titled != 1 or parties != len(marked) or any(not c["cands"] for c in contests):
        raise Layout(f"{where}: the list's title, its marked rows and its offices do not add up")
    return {"contests": contests, "withdrawn": withdrawn, "rows": parties + len(withdrawn), "published": "",
            "read": "each office's heading and, in a candidate's row, the name, the Certified or Elected mark and the party",
            "never": "the address, phone and e-mail cells that follow them"}


def beaverhead_list(raw, where):
    """Beaverhead County's list: three columns (OFFICE, CANDIDATE, PARTY AFFILIATION) and no contact details. A line
    with a party is a candidate; a line without one is the county's own remark on the office above it."""
    pdf = PDF(raw)
    cut = []
    for page, res, box in pdf_pages(pdf):
        cut += [cells_of(row, 0.6) for _y, row in rows_of(glyph_runs(pdf, page, res))]
    # the title lines and the heading row first: nothing under the heading is turned into text until the heading has
    # been seen to be these three columns and no others
    top, head = [], None
    for i, cells in enumerate(cut[:6]):
        texts = [joined(c) for c in cells]
        if len(texts) >= 3:
            head = i if texts == ["OFFICE", "CANDIDATE", "PARTY AFFILIATION"] else None
            break
        top += texts
    if head is None:
        raise Layout(f"{where}: the heading row is not OFFICE, CANDIDATE, PARTY AFFILIATION (new columns are not read)")
    if "NOVEMBER 3, 2026" not in " ".join(top) or "BEAVERHEAD COUNTY" not in " ".join(top):
        raise Layout(f"{where}: the list's title does not name Beaverhead County and November 3, 2026")
    rows = [([joined(c) for c in cells], cells) for cells in cut[head + 1:]]
    margin = min(extent(c[0])[0] for _t, c in rows) if rows else 0
    contests, cur, published, parties = [], None, "", 0
    for n, (texts, cells) in enumerate(rows, head + 2):
        at_margin = extent(cells[0])[0] <= margin + 3
        m = re.fullmatch(r"UPDATED (\d{1,2})/(\d{1,2})/(\d{4})", " ".join(texts))
        if m:
            published = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        elif not at_margin:
            if not re.fullmatch(r"\* ?= ?incumbent", " ".join(texts)):
                raise Layout(f"{where}: row {n}: a line off the left margin that is not the list's own key or date")
        elif len(texts) == 1:                                      # a line of its own under an office: the county's remark on it
            if cur is None:
                raise Layout(f"{where}: row {n}: a remark before any office")
            cur["remarks"].append(texts[0])
        elif not office_of(texts[0]):
            raise Layout(f"{where}: row {n}: an office this loader does not know")
        elif len(texts) == 3 and texts[2].upper() in PARTY_WORDS:
            parties += 1
            name = clean(texts[1].rstrip("* "))
            cur = {"title": texts[0], "cands": [(name, party_cell(texts[2], f"{where}: row {n}"))], "status": None, "remarks": [],
                   "starred": [name] if texts[1].rstrip().endswith("*") else []}      # the list's key: * = incumbent
            contests.append(cur)
        else:
            cur = {"title": texts[0], "cands": [], "status": "removed" if any("REMOVED FROM BALLOT" in t.upper() for t in texts[1:]) else None,
                   "remarks": texts[1:], "starred": []}
            contests.append(cur)
    if not contests or sum(len(c["cands"]) for c in contests) != parties:
        raise Layout(f"{where}: no offices read")
    return {"contests": contests, "withdrawn": [], "rows": parties, "published": published, "read": "the OFFICE, CANDIDATE and PARTY AFFILIATION columns",
            "never": ""}


READERS = {"flathead": flathead_list, "cascade": cascade_list, "beaverhead": beaverhead_list}


# ---------- offices ----------

def plain_title(t, caps):
    """COUNTY CLERK & RECORDER/SURVEYOR -> County Clerk & Recorder/Surveyor; a title already in ordinary capitals is kept."""
    if not caps:
        return t
    return " ".join(w.lower() if i and w in SMALL_WORDS else "/".join(p.capitalize() for p in w.split("/")) for i, w in enumerate(t.split()))


def office_of(title):
    """A county or local contest's title, as a ballot or a county's list words it -> {level, kind, office, district,
    seat, special, key (for the race id), place, name}; None when the words name no office this loader knows."""
    t = clean(re.sub(r"^FOR\s+", "", clean(title)))
    caps = not re.search(r"[a-z]", t)
    out = {"special": 0, "district": None, "seat": None, "place": None, "name": None, "term": None}
    m = re.search(r"\(?\bUNEXPIRED(?: TERM)?\b\)?", t, re.I)
    if m:
        out["special"], t = 1, clean(t[:m.start()] + " " + t[m.end():])
    m = re.search(r"\b(\d+)[ -]YEAR TERM\b", t, re.I)
    if m:
        out["term"], t = int(m.group(1)), clean(t[:m.start()] + " " + t[m.end():])
    t = re.sub(r"\s*/\s*", "/", t)
    t = clean(re.sub(r"\s+-\s+|,\s*", " ", t))
    for short, long in ((r"\bSUPT\b\.?", "Superintendent"), (r"\bDEPT\b\.?", "Department"), (r"\bDIST\b\.?", "District")):
        t = re.sub(short, long.upper() if caps else long, t, flags=re.I)
    up = t.upper()
    m = re.fullmatch(r"(?P<place>[A-Z .'-]+?) (?P<word>CITY|TOWN) COUNCIL(?: MEMBER)?(?: WARD (?P<ward>\d+))?", up)
    if m:
        ward = f"Ward {int(m.group('ward'))}" if m.group("ward") else None
        return dict(out, level="city", kind="council", office=f"{m.group('word').title()} Council Member", district=ward,
                    place=(m.group("place").title(), m.group("word").lower()), key="council" + (f"-ward-{int(m.group('ward'))}" if ward else ""))
    m = re.fullmatch(r"(?:(?P<name>[A-Z .'-]+?) )?CONSERVATION DISTRICT(?: SUPERVISORS?)?", up)
    if m:
        seat = f"{out['term']}-year term" if out["term"] else None
        return dict(out, level="soil_water", kind="soil_water", office="Conservation District Supervisor", seat=seat,
                    name=m.group("name").title() if m.group("name") else None, key="soil-water" + (f"-{out['term']}-year" if seat else ""))
    m = re.fullmatch(r"(?:COUNTY )?COMMISSIONERS?(?: \(?(?:DISTRICT )?#? ?(\d+)\)?)?", up)
    if m:
        d = int(m.group(1)) if m.group(1) else None
        return dict(out, level="county", kind="county_commissioner", office="County Commissioner", district=f"District {d}" if d else None,
                    key="county-commissioner" + (f"-d{d}" if d else ""))
    m = re.fullmatch(r"(?:COUNTY )?JUSTICE OF THE PEACE(?: (?:DEPARTMENT )?#? ?(\d+))?", up)
    if m:
        d = int(m.group(1)) if m.group(1) else None
        return dict(out, level="county", kind="justice_of_the_peace", office="Justice of the Peace", seat=f"Department {d}" if d else None,
                    key="justice-of-the-peace" + (f"-dept{d}" if d else ""))
    bare = re.sub(r"^COUNTY ", "", up)
    hits = sorted((mm.start(), i, kind) for i, (pat, kind) in enumerate(KIND_PATTERNS) for mm in [re.search(pat, bare)] if mm)
    if not hits or re.search(r"\d", bare):
        return None
    kind = hits[0][2]
    return dict(out, level="county", kind=kind, office=plain_title(t, caps), key=kind.replace("_", "-"))


def census_places(folder, say):
    """{(folded name, 'city' or 'town'): [(place code, name as the Bureau writes it, [county names])]} for Montana's
    incorporated places, from the Census Bureau's 2020 place codes file."""
    path = os.path.join(folder, PLACE_FILE)
    net.download(PLACE_URL, path, 3650, tries=3, say=say)
    out = collections.defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        if head[:9] != ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]:
            raise SystemExit(f"Montana (county and local): {PLACE_FILE}: the header is not the one this loader was checked against")
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            m = re.fullmatch(r"(.+) (city|town)", f[4]) if len(f) >= 9 and f[1] == FIPS and f[5] == "INCORPORATED PLACE" else None
            if m:
                out[(fold(m.group(1)), m.group(2))].append((f[2], f[4], [c.strip() for c in re.split(r"~~~|,", f[8]) if c.strip()]))
    return out, path


# ---------- one county ----------

def page_links(county, src, folder, say):
    """The links on a county's election page that fit the source's pattern, with the page's address, the day it was
    read and its fingerprint. Only those links are kept (never the page), for LINK_DAYS."""
    path = os.path.join(folder, "links.json")
    if kept(path, LINK_DAYS):
        data = json.load(open(path, encoding="utf-8"))
        if data.get("page") == src["page"] and data.get("pattern") == src["link"]:
            return data, path
    try:
        raw = fetch_bytes(src["page"])
    except ConnectionError as e:
        if os.path.exists(path):
            say(f"    Montana (county and local): {county} County's election page could not be read ({e}); using the links kept on {day_of(path)}")
            return json.load(open(path, encoding="utf-8")), path
        raise
    page = raw.decode("utf-8", "replace")
    pat, where = re.compile(src["link"]), re.compile(src.get("href", ""))
    links, seen = [], set()
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page, re.S | re.I):
        text = clean(html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))))
        href = urllib.parse.urljoin(src["page"], html.unescape(m.group(1)).strip())
        if pat.search(text) and where.search(href) and href not in seen:
            seen.add(href)
            links.append({"text": text, "href": href})
    del page
    data = {"page": src["page"], "pattern": src["link"], "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "links": links}
    keep_json(path, data)
    return data, path


def fetched_pdf(link, path, say):
    """A sample ballot (or a list with no contact details), kept whole for FILE_DAYS; an older copy is used if the county's
    site cannot be reached."""
    if kept(path, FILE_DAYS):
        return path
    try:
        raw = fetch_bytes(link["href"])
        if not raw.startswith(b"%PDF"):
            raise ConnectionError("the answer is not a PDF (a challenge page?)")
    except ConnectionError as e:
        if os.path.exists(path):
            say(f"    Montana (county and local): {os.path.basename(path)} could not be fetched again ({e}); using the copy kept on {day_of(path)}")
            return path
        raise
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as fh:
        fh.write(raw)
    os.replace(path + ".part", path)
    return path


def county_list(county, src, link, folder, say):
    """A county's candidate list, cut down to the allowed cells. A list that also prints contact details is read in
    memory and only the cut-down copy is kept (as JSON); the file itself is never written to disk."""
    key = slug(county)
    path = os.path.join(folder, f"{key}_candidate_list.json")
    if kept(path, LINK_DAYS):
        data = json.load(open(path, encoding="utf-8"))
        if data.get("url") == link["href"]:
            return data, path
    try:
        raw = fetch_bytes(link["href"])
        if not raw.startswith(b"%PDF"):
            raise ConnectionError("the answer is not a PDF (a challenge page?)")
    except ConnectionError as e:
        if os.path.exists(path):
            say(f"    Montana (county and local): {county} County's list could not be fetched again ({e}); using the cells kept on {day_of(path)}")
            return json.load(open(path, encoding="utf-8")), path
        raise
    data = READERS[src["reader"]](raw, f"{county} County's candidate list")
    data.update(url=link["href"], text=link["text"], fetched=dt.date.today().isoformat(), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    del raw
    blank_contact(data)
    keep_json(path, data)
    return data, path


def blank_contact(data):
    """A kept cell that reads like contact details (an e-mail typed into a name cell, say) is blanked before the cells are
    kept or stored, and counted; it is never printed."""
    data["blanked"] = 0
    for c in data["contests"]:
        good = [(nm, pt) for nm, pt in c["cands"] if nm and not contact_like(nm, True)]
        data["blanked"] += len(c["cands"]) - len(good)
        c["cands"] = good
        c["remarks"] = [r for r in c["remarks"] if not contact_like(r, True)]
    return data


def ballot_sources(county, files, got, agency, by_hand):
    """One sl_sources row for each sample-ballot file read. `files` is [(label, path, source id, address)]."""
    by = {f["source"]: f for f in got["files"]}
    rows = []
    for label, path, sid, href in files:
        f = by[sid]
        rows.append((sid, STATE, "official sample ballot", agency, f"{county} County sample ballot, November 3, 2026: {label}", href, "",
                     day_of(path), sha_of(path), f["contests"],
                     ("Saved by hand from the county's own posting, which a script cannot reach. " if by_hand else "")
                     + f"A sample ballot as the county's voting system prints it ({f['pages']} pages, {f['forms']} ballot "
                     f"form{'s' if f['forms'] != 1 else ''}): contest titles, names and the party line under each name; a ballot carries no "
                     f"contact details. {f['contests']} contests read" + (", each counted on every form that prints it" if f["forms"] > 1 else "")
                     + f": {f['local']} for county and local offices, {f['state']} for federal and state offices (left to the state rows) and "
                     f"{f['measures']} ballot questions (not loaded). Control: {f['names']} party lines counted on the pages, the same number of "
                     "names placed in contests."))
    return rows


def page_source(county, src, links):
    """The sl_sources row for a county's election page, read for its links."""
    return (f"mt-{slug(county)}-2026-local-page", STATE, "official page", f"{county} County Election Administrator",
            f"{county} County's election page: where its November 3, 2026 " + ("sample ballots are" if src["how"] == "ballots" else "candidate list is")
            + " linked", links["page"], "", links["fetched"], links["sha256"], len(links["links"]),
            "Read for the links to the files only (the words of each link and its address); nothing else on the page is read, and the page is not kept."
            + ("" if links["links"] else " No link to a file for the November 3, 2026 election was on it."))


def ballot_facts(how, files, found, got):
    return {"how": how, "files": len(files), "forms": got["forms"], "state": got["state"], "measures": got["measures"], "rotated": got["rotated"],
            "rows": sum(len(c["cands"]) + (1 if c["retain"] else 0) for c in found), "withdrawn": [], "blanked": 0}


def posted(county, src, folder, say):
    """What a county's own election page links for November 3: (contests, facts, sources). NotPosted when the page has
    no such link; ConnectionError when the county's site cannot be reached and nothing is kept."""
    key = slug(county)
    agency = f"{county} County Election Administrator"
    links, _lpath = page_links(county, src, folder, say)
    page_row = page_source(county, src, links)
    if not links["links"]:
        raise NotPosted(links["fetched"], page_row)
    if src["how"] == "ballots":
        files = []
        for n, link in enumerate(links["links"], 1):
            path = fetched_pdf(link, os.path.join(folder, f"{key}_{slug(link['text'])}.pdf"), say)
            files.append((link["text"], path, f"mt-{key}-2026-local-ballot-{n:02d}", link["href"]))
        found, got = county_ballots(county, [f[:3] for f in files])
        return found, ballot_facts("ballots", files, found, got), [page_row] + ballot_sources(county, files, got, agency, False)
    if len(links["links"]) != 1:
        raise Layout(f"{county} County's election page: {len(links['links'])} links fit the list's name, not one")
    link = links["links"][0]
    if src["reader"] == "beaverhead":                              # no contact details in this one: the file is kept whole
        path = fetched_pdf(link, os.path.join(folder, f"{key}_{slug(link['text'])}.pdf"), say)
        with open(path, "rb") as fh:
            data = READERS[src["reader"]](fh.read(), os.path.basename(path))
        data.update(url=link["href"], text=link["text"], fetched=day_of(path), sha256=sha_of(path))
        blank_contact(data)
    else:
        data, _path = county_list(county, src, link, folder, say)
    sid = f"mt-{key}-2026-local-list"
    found = [dict(c, cands=[tuple(x) for x in c["cands"]], vote=1, retain=None, forms=1, source=sid) for c in data["contests"]]
    row = (sid, STATE, "official candidate list", agency, f"{county} County candidates, November 3, 2026: {clean(link['text']).rstrip('.')}",
           link["href"], data.get("published", ""), data["fetched"], data["sha256"], data["rows"],
           f"Read: {data['read']}. " + (f"Never read, printed or kept: {data['never']}; the file is read in memory and only the cut-down cells "
                                        "are kept. " if data["never"] else "The list prints no contact details. ")
           + f"{sum(len(c['cands']) for c in data['contests'])} candidates in {len(data['contests'])} offices"
           + (f"; {len(data['withdrawn'])} withdrawn, left off ({'; '.join(data['withdrawn'])})" if data["withdrawn"] else "")
           + (f"; {data['blanked']} names that read like contact details blanked" if data.get("blanked") else "") + ".")
    facts = {"how": "list", "files": 1, "forms": 1, "state": {}, "measures": {}, "rotated": False, "rows": data["rows"] - data["blanked"],
             "withdrawn": data["withdrawn"], "blanked": data["blanked"]}
    return found, facts, [page_row, row]


def read_county(county, folder, say):
    """One county's November 3 contests: (contests, facts, sources), from what the county's election page links or, when
    that cannot be had, from sample ballots saved by hand into the county's folder. NotPosted: neither is there.
    ConnectionError: the county's site could not be reached. Layout: what is there could not be read."""
    src = LOCAL_SOURCES.get(county)
    key = slug(county)
    first = None
    if src:
        try:
            return posted(county, src, folder, say)
        except (NotPosted, ConnectionError) as e:
            first = e
    names = sorted(n for n in (os.listdir(folder) if os.path.isdir(folder) else []) if n.lower().endswith(".pdf")
                   and not (src and n.startswith(key + "_")))      # a configured county's own downloads are not hand-saved files
    if not names:
        raise first or NotPosted("")
    page = (src or {}).get("page") or CHECKED.get(county, ("", DIRECTORY))[1]
    files = [(n, os.path.join(folder, n), f"mt-{key}-2026-local-saved-{i:02d}", page) for i, n in enumerate(names, 1)]
    found, got = county_ballots(county, [f[:3] for f in files])
    return found, ballot_facts("saved", files, found, got), ballot_sources(county, files, got, f"{county} County Election Administrator", True)


def local_rows(cache, cmap, state_names, say):
    """County and local offices on the November ballot: rows for sl_races, sl_candidates, sl_places, sl_sources, sl_gaps and
    sl_notes, and the lines of the report. Nothing is placed by guess: what cannot be read becomes a gap."""
    folder = os.path.join(cache, LOCAL_DIR)
    os.makedirs(folder, exist_ok=True)
    out = {"races": [], "cands": [], "places": [], "src": [], "gaps": [], "notes": [], "report": [], "checks": []}
    by_name = {full[:-len(" County")]: (geoid, full) for geoid, full in cmap.values()}
    unknown = [c for c in list(LOCAL_SOURCES) + list(CHECKED) if c not in by_name]
    if unknown:
        raise SystemExit(f"Montana (county and local): counties not in the Census file: {unknown}")
    places, ppath = census_places(folder, say)
    used_places, loaded, state_ok, state_seen = {}, collections.OrderedDict(), 0, 0
    totals = collections.Counter()
    race_ids = set()

    def gap(scope, pid, place, what, reason, url):
        for label, text in (("what", what), ("reason", reason), ("place", place)):
            if contact_like(text, False):
                raise SystemExit(f"Montana (county and local): a gap's {label} for {pid} reads like contact details; reword it")
        out["gaps"].append((STATE, scope, pid, place, what, reason, url))

    for county in sorted(by_name):
        geoid, cname = by_name[county]
        cfolder = os.path.join(folder, slug(county))
        seen, page = CHECKED.get(county, (None, DIRECTORY))
        src = LOCAL_SOURCES.get(county)
        try:
            found, facts, sources = read_county(county, cfolder, say)
        except NotPosted as e:
            if src:
                reason = (f"This county's November 3 list is not loaded yet: the page where the county posts its sample ballots, read on "
                          f"{e.args[0] or READ_ON}, carried none for the November 3, 2026 election yet.")
                page = src["page"]
                out["src"] += list(e.args[1:2])                     # the page was read, so it is a source, with its fingerprint
            elif seen:
                reason = (f"This county's November 3 list is not loaded yet. Montana has no statewide list of county candidates before Election Day; "
                          f"the county's election administrator publishes it, and on {READ_ON} {seen}.")
            else:
                reason = ("This county's November 3 list is not loaded yet. Montana has no statewide list of county candidates before Election Day; "
                          "the county's election administrator publishes the candidates and sample ballots, and the county's own posting has not "
                          "been read.")
            gap("county", geoid, cname, WHAT, reason, page)
            continue
        except ConnectionError as e:
            gap("county", geoid, cname, WHAT, "This county's November 3 list is not loaded: the county's election pages could not be reached when "
                "this was loaded. Loading again will ask once more.", src["page"] if src else page)
            out["checks"].append(f"{county} County: not reached ({e})")
            continue
        except Layout as e:
            gap("county", geoid, cname, WHAT, "This county's November 3 list is not loaded: what the county posts could not be read as the ballot or "
                "list this loader was checked against, so nothing is shown rather than a guess.", src["page"] if src else page)
            out["checks"].append(f"{county} County: {e}")
            continue

        # ---- the county's contests -> races and candidates
        rows_c, cands_c, unknown_titles = [], [], []
        ballot = facts["how"] in ("ballots", "saved")
        offices = [(c, office_of(c["title"])) for c in found]
        partisan_seen = set()
        for c, o in offices:
            if o and o["kind"] not in ("justice_of_the_peace", "soil_water", "council") and c["cands"]:
                partisan_seen.add(all(PARTY_WORDS[p.upper()] is not None for _n, p in c["cands"]))
        for c, o in offices:
            if o is None:
                unknown_titles.append(c["title"])
                continue
            words = [PARTY_WORDS[p.upper()] for _n, p in c["cands"]]
            if c["cands"] and any(w is None for w in words) and not all(w is None for w in words):
                raise SystemExit(f"Montana (county and local): {county} County: a contest mixes party and nonpartisan lines ({o['office']})")
            if c["retain"] or o["kind"] in ("justice_of_the_peace", "soil_water", "council"):
                partisan = 0
                if any(w is not None for w in words):
                    raise SystemExit(f"Montana (county and local): {county} County: a party printed on a nonpartisan office ({o['office']})")
            elif c["cands"]:
                partisan = 0 if all(w is None for w in words) else 1
            else:
                partisan = 1 if partisan_seen == {True} else 0
            note, jur, jid, cids = [], cname, geoid, [geoid]
            if o["level"] == "city":
                name, word = o["place"]
                hits = places.get((fold(name), word), [])
                if len(hits) == 1:
                    code, pname, pcounties = hits[0]
                    jid, jur = f"{STATE}-M-{code}", pname
                    cids = sorted({geoid} | {by_name[n[:-len(" County")]][0] for n in pcounties if n[:-len(" County")] in by_name})
                    used_places[jid] = ("mcd", jid, jur, cids, SRC_PLACES)
                else:
                    jid, jur = f"{STATE}-M-{geoid[2:]}-{slug(name + ' ' + word)}", f"{name} {word}"
                    used_places[jid] = ("mcd", jid, jur, cids, c["source"])
                rid = f"2026-{jid}-{o['key']}" + ("-S" if o["special"] else "")
                note.append(ODD_YEAR)
            elif o["level"] == "soil_water" and o["name"]:
                jur = f"{o['name']} Conservation District"
                jid = f"{STATE}-X-{geoid[2:]}-{slug(jur)}"
                used_places[jid] = ("special", jid, jur, cids, c["source"])
                rid = f"2026-{jid}-supervisor" + (f"-{o['term']}-year" if o["term"] else "") + ("-S" if o["special"] else "")
            else:
                rid = f"2026-{STATE}-{geoid}-{o['key']}" + ("-S" if o["special"] else "")
            if rid in race_ids:
                raise SystemExit(f"Montana (county and local): two contests of {county} County share the race id {rid}")
            race_ids.add(rid)
            if c["status"] == "affirmation":
                note.append("Not on the November 3 ballot: the county's certified list says the election was canceled and these candidates were "
                            "elected by affirmation. A conservation district's election is canceled when no more candidates file than there are "
                            "seats (MCA 13-1-502).")
            elif c["status"] == "removed":
                note.append("Not on the November 3 ballot: the county's list marks this office removed from the ballot and names no candidate.")
            elif not c["cands"] and not c["retain"]:
                note.append("The ballot prints no candidate for this office (a blank write-in line only)." if ballot
                            else "The county's list names no candidate for this office.")
                if o["level"] == "county" and o["kind"] != "justice_of_the_peace":
                    note.append("With no candidate there is no party line to read; the county's other county offices are printed "
                                + ("with parties." if partisan else "without parties."))
            if c["retain"]:
                note.append(RETAIN_NOTE.format(name=shown(c["retain"])))
            elif o["kind"] == "justice_of_the_peace" and not ballot and len(c["cands"]) == 1:
                note.append(ONE_JUDGE_STARRED if c["cands"][0][0] in c["starred"] else ONE_JUDGE)
            if c["vote"] and c["vote"] > 1:
                note.append(f"Voters choose up to {c['vote']}.")
            if o["special"]:
                note.append("For the rest of an unexpired term, as the ballot titles it." if ballot
                            else "For the rest of an unexpired term, as the county's list titles it.")
            if ballot and c["forms"] < facts["forms"]:
                part = {"county_commissioner": "only the voters of this commissioner district vote on it",
                        "soil_water": "only voters inside the conservation district vote on it",
                        "council": "only the voters of this ward vote on it"}.get(o["kind"], "only part of the county votes on it")
                note.append(f"Printed on {c['forms']} of the county's {facts['forms']} ballot forms: {part}.")
                if o["level"] == "soil_water" and not o["name"]:
                    note.append("The ballot does not name the district.")
                    gap("race", rid, cname, "which conservation district this is",
                        f"The sample ballots title this contest Conservation District Supervisor without naming the district. It is printed on "
                        f"{c['forms']} of the county's {facts['forms']} ballot forms, so the district does not reach the whole county.",
                        src["page"] if src else page)
            if c["remarks"]:
                note.append("The county's list adds: " + "; ".join(f"\"{r.rstrip('.')}\"" for r in c["remarks"]) + ".")
            if ballot and (c["cands"] or c["retain"]):
                note.append(CAPS_BALLOT)
            people = [(shown(c["retain"]), None, RETAIN_CAND)] if c["retain"] else \
                     [((shown(n) if ballot else clean(n)), PARTY_WORDS[p.upper()], None) for n, p in c["cands"]]
            if len({fold(n) for n, _p, _x in people}) != len(people):
                raise SystemExit(f"Montana (county and local): the same name twice in {rid}")
            for text in [o["office"], jur, o["district"], o["seat"], " ".join(note)] + [n for n, _p, _x in people]:
                if text and contact_like(text, True):
                    raise SystemExit(f"Montana (county and local): a field of {rid} reads like contact details; nothing is written")
            rows_c.append((rid, STATE, o["level"], o["kind"], o["office"], jur, jid, json.dumps(cids), o["district"], o["seat"], o["special"], partisan,
                           None, None, None, GENERAL, " ".join(note) or None))
            for name, party, cnote in people:
                if c["status"] == "affirmation":
                    cnote = "Marked Elected on the county's list: the election was canceled."
                cands_c.append((rid, "general", GENERAL, name, party if partisan else "Nonpartisan office", party_code(party) if partisan else "N",
                                None, 0, 0, None, None, None, None, c["source"], cnote))
        # rows in = names placed (each in exactly one race) + names under a title the loader does not know + withdrawals counted
        placed = len(cands_c)
        unplaced = sum(len(c["cands"]) + (1 if c["retain"] else 0) for c, o in offices if o is None)
        if placed + unplaced + len(facts["withdrawn"]) != facts["rows"] or len({(x[0], x[3]) for x in cands_c}) != placed:
            raise SystemExit(f"Montana (county and local): {county} County: {facts['rows']} rows read, {placed} names placed, {unplaced} under "
                             f"titles not known, {len(facts['withdrawn'])} withdrawn: they do not add up")
        for title in unknown_titles:
            gap("county", geoid, cname, f"a contest titled {plain_title(title, not re.search(r'[a-z]', title))}",
                f"The county's {'ballot' if ballot else 'list'} carries this contest, but the office is not one this loader knows yet, so it is "
                "not shown rather than filed by guess.", src["page"] if src else page)
            out["checks"].append(f"{county} County: an office title not known: {title}")
        if not ballot:                                             # a list of county offices is not the whole ballot
            has_cd = any(o and o["level"] == "soil_water" for _c, o in offices)
            gap("county", geoid, cname, "any city or town contests" if has_cd else "conservation district and any city or town contests",
                "The county's candidate list covers county offices, justices of the peace and the conservation district. Whether a city or town "
                "office on a special ballot is also voted on is not in that list; it would show on the county's sample ballots, which are not read "
                "for this county." if has_cd else
                "The county's candidate list covers county offices and justices of the peace. Whether a conservation district's supervisors, or a "
                "city or town office on a special ballot, are also voted on is not in that list; it would show on the county's sample ballots, "
                "which are not read for this county.", src["page"] if src else page)
        # the state contests on the same ballots, against the Secretary of State's list
        for title, got in facts["state"].items():
            try:
                rid = state_race_of(title)
            except SystemExit:
                out["checks"].append(f"{county} County's ballots carry a state contest this loader does not know: {title}")
                continue
            if rid is None:
                continue
            state_seen += 1
            mine = {fold(n) for n, _p in got["names"]} | ({fold(got["retain"])} if got["retain"] else set())
            if mine == state_names.get(rid, set()):
                state_ok += 1
            else:
                out["checks"].append(f"{county} County's ballots and the Secretary of State's list differ for {rid} "
                                     f"({len(mine)} names on the ballot, {len(state_names.get(rid, set()))} on the list)")
        out["races"] += rows_c
        out["cands"] += cands_c
        out["src"] += sources
        loaded[county] = dict(facts, races=len(rows_c), names=placed)
        totals["withdrawn"] += len(facts["withdrawn"])
        totals["measures"] += len(facts["measures"])

    out["places"] = [(kind, pid, name, json.dumps(cids), sid) for kind, pid, name, cids, sid in used_places.values()]
    out["src"].append((SRC_PLACES, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Montana (st30_mt_place2020.txt)", PLACE_URL,
                       "", day_of(ppath), sha_of(ppath), sum(len(v) for v in places.values()),
                       "Names and codes of Montana's incorporated cities and towns and the counties they lie in: a city or town office on a county's "
                       "ballot is filed under the one place of that name."))

    # ---- notes and the report
    lv = collections.Counter(r[2] for r in out["races"])
    kinds = collections.Counter(r[3] for r in out["races"])
    level_of = {r[0]: r[2] for r in out["races"]}
    cand_lv = collections.Counter(level_of[c[0]] for c in out["cands"])
    ballots = [c for c, f in loaded.items() if f["how"] in ("ballots", "saved")]
    lists = [c for c, f in loaded.items() if f["how"] == "list"]
    partisan_n = sum(1 for r in out["races"] if r[11])

    def named(cs):
        return ", ".join(cs[:-1]) + (" and " if len(cs) > 1 else "") + cs[-1] if cs else "none"

    calendar = (
        "On November 3, 2026 Montana's counties elect county officers: a county commissioner for six years (more than one seat where a term is "
        "unexpired) and, for four years, the clerk and recorder, sheriff, county attorney, treasurer, county superintendent of schools and the "
        "other county offices a county keeps (many counties combine them, and some also elect a clerk of district court this year), with "
        "justices of the peace on the nonpartisan judicial ballot. Conservation district supervisors are elected at the general election too, "
        "but the election is canceled where no more candidates file than there are seats; and a county's own form of government can put its "
        "offices on the ballot without parties, so partisan or not is read from each county's ballot. Cities and towns elect their officers in "
        "November of odd-numbered years, and school trustees and special purpose districts (fire, water and sewer and the like) on the school "
        "election day in May, so those appear on this ballot only where a special election was called.")
    out["notes"].append((STATE, "local_calendar", calendar,
                         "Montana Code Annotated 13-1-104 (what is elected at a general election), 7-4-2104 and 7-4-2105 (county commissioners), 7-4-2203 "
                         "and 7-4-2205 (county officers and their terms), 3-10-201 (justices of the peace), 13-1-502, 13-1-504 and 76-15-304 "
                         f"(conservation and special purpose districts), 20-20-105 (school election day), as the Legislature publishes them (read {READ_ON})",
                         MCA))
    coverage = (
        "Montana has no statewide list of county candidates before Election Day, so this is read county by county from what each county's election "
        f"office posts: sample ballots for {named(ballots)} "
        f"{'County' if len(ballots) == 1 else 'counties'} and candidate lists for {named(lists)} {'County' if len(lists) == 1 else 'counties'}, "
        f"{len(out['races'])} contests and {len(out['cands'])} names in {len(loaded)} of the 56 counties. Left out: the other {56 - len(loaded)} "
        "counties, each named among the gaps; ballot questions and measures (the statewide initiatives and local questions such as a proposed plan of "
        "government); write-in candidates, for whom a ballot prints only a blank line; and candidates who withdrew"
        f" ({totals['withdrawn']} on the lists read). Names rotate from one ballot form to another under state law, so no ballot order is given.")
    out["notes"].append((STATE, "local_coverage", coverage,
                         "Sample ballots and candidate lists posted by the counties' election administrators, each listed among the sources; MCA 13-12-205 "
                         "(names rotated on the ballot), 13-14-212 (retention questions)", DIRECTORY))
    for row in out["notes"]:
        if contact_like(row[2], False) or contact_like(row[3], False):
            raise SystemExit(f"Montana (county and local): the {row[1]} note reads like contact details; reword it")
    reached = {c for r in out["races"] for c in json.loads(r[7])}
    alone = sum(1 for r in out["races"] if sum(1 for c in out["cands"] if c[0] == r[0]) == 1)
    out["report"].append(
        f"    Montana (county and local): {len(out['races'])} contests in {len(loaded)} of 56 counties ({named(list(loaded))}): county {lv['county']}, "
        f"conservation districts {lv['soil_water']}, city {lv['city']}; {len(out['cands'])} names (county {cand_lv['county']}, conservation "
        f"{cand_lv['soil_water']}, city {cand_lv['city']}); {partisan_n} contests with parties, {len(out['races']) - partisan_n} without; {alone} with one "
        f"name; {kinds['justice_of_the_peace']} justice of the peace contests; {totals['withdrawn']} withdrawn left off; {len(reached)} counties reached; "
        f"{sum(1 for g in out['gaps'] if g[1] == 'county' and g[4] == WHAT)} counties not loaded")
    for county, f in loaded.items():
        out["report"].append(
            f"      {county}: {f['races']} contests, {f['names']} names from " + (f"{f['files']} sample ballot file{'s' if f['files'] != 1 else ''} "
            f"({f['forms']} ballot forms; {len(f['state'])} state contests and {len(f['measures'])} questions on them not loaded"
            f"{'; names rotate between forms' if f['rotated'] else ''})" if f["how"] != "list" else
            f"the county's candidate list ({f['rows']} rows, {len(f['withdrawn'])} withdrawn)"))
    out["report"].append(f"    Montana (county and local): control: {state_ok} of {state_seen} state contests printed on the counties' ballots carry "
                         "exactly the names of the Secretary of State's November list")
    for c in out["checks"]:
        out["report"].append(f"    CHECK Montana (county and local): {c}")
    out["loaded"] = loaded
    return out


# ---------- the load ----------

def load(db_path, say=print, cache=CACHE):
    if os.path.abspath(db_path) == os.path.abspath(os.path.join(HERE, "ballot_2026.sqlite")):
        raise SystemExit("Montana (state races): this loader never writes ballot_2026.sqlite")
    net.patient_lookups()
    g_path = os.path.join(cache, "mt_2026_sl_general_list.json")
    p_path = os.path.join(cache, "mt_2026_sl_primary_list.json")
    gen, g_how = cached_list("general", g_path, say)
    pri, p_how = cached_list("primary", p_path, say)
    fed_cache = os.path.join(HERE, "ballot_cache", "mt")
    book = fetch_file(PRECINCT_URL, os.path.join(fed_cache, "mt_2026_primary_precinct.xlsx"), b"PK", say)
    stw = fetch_file(CANVASS_URL, os.path.join(fed_cache, "mt_2026_primary_state_canvass.pdf"), b"%PDF", say)
    leg = fetch_file(LEG_CANVASS_URL, os.path.join(cache, "mt_2026_primary_legislative_canvass.pdf"), b"%PDF", say)
    legend = {**pri["legend"], **gen["legend"]}
    seats, everyone, as_of = roster()
    checks = []

    def party_of(code):
        if code not in legend:
            raise SystemExit(f"Montana (state races): the party code {code!r} is not in the list's key ({legend})")
        return legend[code]

    # ---- races: every state race on either list
    races = {}
    for r in gen["rows"] + pri["rows"]:
        rid, info = race_of(r["Race"], r["District"], r["Term Type"])
        races.setdefault(rid, info)
    on_primary_list = {race_of(r["Race"], r["District"], r["Term Type"])[0] for r in pri["rows"]}
    on_general_list = {race_of(r["Race"], r["District"], r["Term Type"])[0] for r in gen["rows"]}
    for rid in sorted(on_primary_list - on_general_list):
        checks.append(f"{rid}: on the primary list but not on the November list")

    # ---- the June 2 results and their controls
    votes, race_counties, race_precincts, county_ids = primary_votes(book)
    cmap = county_names()
    book_counties = set(county_ids.values())
    unknown = sorted(c for c in book_counties if fold(c) not in cmap)
    if unknown or len(cmap) != 56:
        raise SystemExit(f"Montana (state races): county names not in the Census file: {unknown} ({len(cmap)} Montana counties there)")

    # every candidate on each party's June ballot (FILED and NOMINATED), and who was left off before it
    filed, nominated, left_off, petitioned, ast_primary = collections.defaultdict(dict), collections.defaultdict(set), collections.Counter(), 0, {}
    for r in pri["rows"]:
        rid, info = race_of(r["Race"], r["District"], r["Term Type"])
        code, name, st = r["Party Preference"], r["Name"].strip(), r["Status"].strip()
        party_of(code)
        if code == "IND":
            if st != "PENDING PETITION" and not OFF.search(st):
                raise SystemExit(f"Montana (state races): an independent on the primary list with the status {st!r} ({rid})")
            petitioned += 1                                  # independents petition for November; they are in no primary
            continue
        if not info["partisan"] and code != "NON":
            raise SystemExit(f"Montana (state races): a party ({code}) on a nonpartisan race ({rid})")
        if info["partisan"] and code not in NOMINEE_CODES:
            raise SystemExit(f"Montana (state races): a party code on a partisan primary that is not read ({code}, {rid})")
        if OFF.search(st):
            left_off[info["level"]] += 1
            continue
        if st not in ON:
            raise SystemExit(f"Montana (state races): a status on the primary list that is not read ({st!r}, {rid})")
        filed[(rid, code)][fold(name.lstrip("*"))] = name
        ast_primary[(rid, fold(name.lstrip("*")))] = name.startswith("*")
        if st == "NOMINATED":
            nominated[(rid, code)].add(fold(name.lstrip("*")))

    book_keys = {(rid, code) for rid, byp in votes.items() for code in byp}
    for key in sorted(set(filed) | book_keys):
        rid, code = key
        got = set(votes.get(rid, {}).get(code, {}))
        if got != set(filed.get(key, {})):
            raise SystemExit(f"Montana (state races): the workbook's candidates for {rid} {code} are not the primary list's "
                             f"({len(got)} in the workbook, {len(filed.get(key, {}))} on the list)")

    leg_totals = legislative_canvass(leg, legend)
    leg_races = {rid for rid in votes if re.fullmatch(rf"2026-{STATE}-S[SH]\d+", rid)}
    if set(leg_totals) != leg_races:
        raise SystemExit(f"Montana (state races): the legislative canvass and the workbook cover different districts "
                         f"({sorted(set(leg_totals) ^ leg_races)[:6]})")
    for rid in leg_races:
        for code, cands in votes[rid].items():
            mine = sorted(v for _n, v in cands.values())
            theirs = sorted(t for c, t in leg_totals[rid] if c == code)
            if mine != theirs:
                raise SystemExit(f"Montana (state races): {rid} {code}: the workbook's totals {mine} are not the legislative canvass's {theirs}")
        if sum(len(c) for c in votes[rid].values()) != len(leg_totals[rid]):
            raise SystemExit(f"Montana (state races): {rid}: the canvass lists a candidate the workbook does not")
    stw_totals = canvass_totals(stw)
    stw_checked = 0
    for rid, byp in votes.items():
        if rid in leg_races:
            continue
        for code, cands in byp.items():
            if tuple(sorted(v for _n, v in cands.values())) not in stw_totals:
                raise SystemExit(f"Montana (state races): {rid} {code}: the workbook's totals match no Total line of the State Canvass")
            stw_checked += 1

    # nesting, checked against the precincts: each Senate district on the ballot holds House districts 2n-1 and 2n
    nest_ok = True
    for rid, pre in race_precincts.items():
        m = re.fullmatch(rf"2026-{STATE}-SS(\d+)", rid)
        if not m:
            continue
        n = int(m.group(1))
        inside = sorted(int(h[len(f"2026-{STATE}-SH"):]) for h, hp in race_precincts.items()
                        if h.startswith(f"2026-{STATE}-SH") and hp and hp <= pre)
        if inside != [2 * n - 1, 2 * n]:
            nest_ok = False
            checks.append(f"{rid}: the House districts wholly inside it are {inside}, not {2 * n - 1} and {2 * n}")

    def other_chamber(info):
        if not nest_ok or info["level"] != "legislature":
            return []
        d = int(info["district"])
        if info["chamber"] == "Senate":
            return [p for h in (2 * d - 1, 2 * d) for p in seats.get(("House", str(h)), [])]
        return seats.get(("Senate", str((d + 1) // 2)), [])

    def sitting(rid, names):
        """{name: (member, incumbent, note)} for the names in one election of a race."""
        info, out = races[rid], {}
        if info["level"] == "court":
            return out
        hs = seats.get((info["chamber"], info["district"]), []) if info["level"] == "legislature" else []
        pairs = [(n, h) for n in names for h in hs if person_fits(n.lstrip("*"), h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h, 1, None)
        for n in names:
            if n in out:
                continue
            if info["level"] == "legislature":
                pool, strict = other_chamber(info), False
            else:                                             # a Commission race: any legislator, full names only
                pool, strict = everyone, True
            got = [p for p in pool if person_fits(n.lstrip("*"), p, strict)]
            if len(got) == 1:
                p = got[0]
                out[n] = (p, 0, f"Serves today in the Montana {p['chamber']} (District {p['district']}).")
        return out

    cand, notes = [], collections.defaultdict(list)

    # ---- the November ballot
    rows_by_race = collections.defaultdict(list)
    withdrawn = collections.Counter()
    general_listed = 0
    for r in gen["rows"]:
        rid, info = race_of(r["Race"], r["District"], r["Term Type"])
        general_listed += 1
        st = r["Status"].strip()
        if OFF.search(st):
            withdrawn[info["level"]] += 1
            continue
        if st not in ON:
            raise SystemExit(f"Montana (state races): a status on the general list that is not read ({st!r}, {rid})")
        rows_by_race[rid].append(r)
    orders = sum(1 for r in gen["rows"] if r["Ballot Order"].strip())
    withdrew_after = collections.defaultdict(set)            # withdrawn from the November list, by race
    for r in gen["rows"]:
        if OFF.search(r["Status"]):
            withdrew_after[race_of(r["Race"], r["District"], r["Term Type"])[0]].add(fold(r["Name"].lstrip("*")))
    write_ins = collections.Counter()
    asterisk_only, roster_only = [], []
    for rid, rows in sorted(rows_by_race.items()):
        info = races[rid]
        fit = sitting(rid, [r["Name"] for r in rows])
        names = collections.Counter(fold(r["Name"].lstrip("*")) for r in rows)
        if any(v > 1 for v in names.values()):
            raise SystemExit(f"Montana (state races): the same name twice in {rid} on the general list")
        for r in rows:
            code, raw = r["Party Preference"], r["Name"].strip()
            star = raw.startswith("*")
            member, inc, note = fit.get(raw, (None, 0, None))
            n = [note] if note else []
            wi = 0
            if info["partisan"]:
                party = party_of(code)
                if code == "NON":
                    if any(k[0] == rid and fold(raw.lstrip("*")) in v for k, v in filed.items()):
                        raise SystemExit(f"Montana (state races): a NON candidate in {rid} was on a party's primary ballot")
                    wi = 1
                    write_ins[info["level"]] += 1
                    n.append(WRITE_IN)
                    pcode = party_code("nonpartisan")               # the list's own NON, written out; write_in marks it
                elif code in NOMINEE_CODES:
                    pcode = party_code(party)
                    if fold(raw.lstrip("*")) not in nominated.get((rid, code), set()):
                        gone = nominated.get((rid, code), set()) & withdrew_after.get(rid, set())
                        n.append(f"Not the {party} nominee on the June 2 primary list for this seat; on the November list later "
                                 f"(the list does not say how)" + (", after the nominee withdrew." if gone else "."))
                elif code == "IND":
                    pcode = party_code(party)
                else:
                    raise SystemExit(f"Montana (state races): a party code on the general list that is not read ({code}, {rid})")
            else:
                if code != "NON":
                    raise SystemExit(f"Montana (state races): a party ({code}) on a nonpartisan race ({rid})")
                party, pcode = "Nonpartisan office", "N"
            if info["level"] == "legislature":
                if star and not inc:
                    asterisk_only.append(f"{rid} ({shown(raw)})")
                    inc = 1
                elif inc and not star:
                    roster_only.append(f"{rid} ({shown(raw, member)}, in the roster from {member['since'] or 'an unknown date'})")
                if inc and member and member["party"] and code in NOMINEE_CODES and member["party"] != party:
                    checks.append(f"{rid}: sitting member listed as {member['party']}, on the ballot as {party}")
            elif star and not member:
                inc = 1                                       # the Commission and the courts: the list's own incumbent mark
            cand.append((rid, "general", GENERAL, shown(raw, member), party, pcode, None, inc, wi, None, None, None,
                         member["id"] if member else None, SRC_GEN, " ".join(n) or None))

    # ---- the June 2 primary fields
    fields = collections.Counter()
    top_odd = []
    for rid, code in sorted((rid, code) for rid, byp in votes.items() for code in byp):
        byname = votes[rid][code]
        if len(byname) < 2:
            continue
        info = races[rid]
        nominees = nominated.get((rid, code), set())
        ranked = sorted(byname.items(), key=lambda kv: -kv[1][1])
        k = 2 if code == "NON" else 1
        if {f for f, _ in ranked[:k]} != nominees or (len(ranked) > k and ranked[k - 1][1][1] == ranked[k][1][1]):
            top_odd.append(f"{rid} {code}")
        election = "primary-NP" if code == "NON" else f"primary-{code}"
        party = "Nonpartisan office" if code == "NON" else party_of(code)
        pcode = "N" if code == "NON" else party_code(party)
        total = sum(v for _n, v in byname.values())
        listed = filed[(rid, code)]
        fit = sitting(rid, [listed[f] for f in byname])
        fields[info["office_kind"] if info["level"] == "legislature" else info["level"]] += 1
        for f, (_ballot_name, v) in ranked:
            raw = listed[f]
            member, inc, note = fit.get(raw, (None, 0, None))
            if info["level"] == "legislature" and raw.startswith("*") and not inc:
                inc = 1
            elif info["level"] != "legislature" and raw.startswith("*") and not member:
                inc = 1
            n = [note] if note else []
            if f in nominees and f in withdrew_after.get(rid, set()):
                n.append("Won the primary and later withdrew; not on the November ballot.")
            cand.append((rid, election, PRIMARY, shown(raw, member), party, pcode, None, inc, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if f in nominees else "lost",
                         member["id"] if member else None, SRC_BOOK, " ".join(n) or None))

    # ---- checks on the whole
    keys = collections.Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"Montana (state races): the same name twice in one election: {dup[:3]}")
    gen_by_race = collections.Counter(c[0] for c in cand if c[1] == "general")
    if gen_by_race.total() + withdrawn.total() != general_listed:
        raise SystemExit("Montana (state races): November rows written plus withdrawn do not equal the list's state rows")
    empty = sorted(rid for rid in races if gen_by_race[rid] == 0)
    senate = sorted(int(i["district"]) for i in races.values() if i["office_kind"] == "state_senate")
    house = sorted(int(i["district"]) for i in races.values() if i["office_kind"] == "state_house")
    if house != list(range(1, 101)):
        checks.append(f"House districts on the list are not 1 to 100 (missing {sorted(set(range(1, 101)) - set(house))})")
    if len(senate) != 25:
        checks.append(f"{len(senate)} Senate districts on the list, not 25 (half of 50)")
    for (ch, d), hs in sorted(seats.items()):
        if len(hs) > 1:
            checks.append(f"the roster lists {len(hs)} sitting members for {ch} District {d}")

    # ---- race rows
    race_rows = []
    for rid, i in sorted(races.items()):
        note = []
        hid = hname = hparty = None
        if i["level"] == "legislature":
            hs = seats.get((i["chamber"], i["district"]), [])
            if len(hs) == 1:
                hid, hname, hparty = hs[0]["id"], hs[0]["full"], hs[0]["party"]
            elif not hs:
                note.append(f"The Open States roster ({as_of}) lists no sitting member for this seat.")
        elif i["level"] == "statewide":
            note.append("Elected on party lines by the voters of this Public Service Commission district. The roster this site "
                        "uses does not carry the Commission, so today's holder is not shown; the Secretary of State's list marks "
                        "an incumbent who is running with an asterisk, shown here as Incumbent.")
        else:
            note.append("A nonpartisan office. The roster this site uses does not carry judges, so today's holder is not shown; "
                        "the Secretary of State's list marks an incumbent who is running with an asterisk, shown here as Incumbent.")
        if i["special"]:
            note.append("For the rest of an unexpired term, as the Secretary of State's list titles it.")
        if i["office_kind"] == "state_senate":
            note.append("Half of the Senate's 50 seats are elected this year; this is one of the 25 on the list.")
        if rid not in votes:
            note.append("Not on the June 2 primary ballot.")
        note.append(CAPS)
        cids = sorted(cmap[fold(c)][0] for c in race_counties.get(rid, set()))
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], i["jurisdiction"], i["jurisdiction_id"],
                          json.dumps(cids) if cids else None, i["district"], i["seat"], i["special"], i["partisan"],
                          hid, hname, hparty, GENERAL, " ".join(note)))

    # ---- places: counties, and the districts on the ballot with the counties they reach
    place_rows = [("county", geoid, full, json.dumps([geoid]), SRC_COUNTY) for geoid, full in sorted(cmap.values())]
    for rid, i in sorted(races.items()):
        kind = {"state_senate": "senate", "state_house": "house", "public_service_commissioner": "psc", "district_court": "judicial"}.get(i["office_kind"])
        if not kind:
            continue
        pid = f"{STATE}-{i['jurisdiction_id']}" if kind in ("psc", "judicial") else f"{STATE}-{i['district']}"
        cids = sorted(cmap[fold(c)][0] for c in race_counties.get(rid, set()))
        place_rows.append((kind, pid, i["jurisdiction"], json.dumps(cids) if cids else None, SRC_BOOK))
    place_rows = list({(k, p): (k, p, n, c, s) for k, p, n, c, s in place_rows}.values())

    # ---- county and local offices (their own rows; nothing above is touched). The names of each state race's printed
    # candidates go along only as a control on the reading of the counties' ballots.
    state_names = {rid: {fold(r["Name"].lstrip("*")) for r in rows if not (races[rid]["partisan"] and r["Party Preference"] == "NON")}
                   for rid, rows in rows_by_race.items()}
    local = local_rows(cache, cmap, state_names, say)
    clash = ({r[0] for r in race_rows} & {r[0] for r in local["races"]}) | ({(k, p) for k, p, _n, _c, _s in place_rows} & {(r[0], r[1]) for r in local["places"]})
    if clash:
        raise SystemExit(f"Montana: a county or local row shares an id with a state row: {sorted(map(str, clash))[:5]}")

    n_book = sum(len(c) for byp in votes.values() for c in byp.values())
    src = [
        (SRC_GEN, STATE, "official candidate list", "Montana Secretary of State",
         "FEDERAL GENERAL 2026 Candidate List (November 3, 2026): the state offices", gen["url"], "", gen["fetched"], sha_of(g_path),
         general_listed,
         f"Every page of the grid read ({gen['items']} rows, every office; {g_how}); the {general_listed} state rows kept, and only "
         "Status, District Type, District, Race, Term Type, Name, Party Preference and Ballot Order: the grid's addresses, e-mail, web "
         f"and phone columns are never read. Withdrawn or removed, left off: {withdrawn.total()}. Declared write-ins (NON on a partisan "
         f"race): {write_ins.total()}. The list gives no ballot order for the state races ({orders} of {general_listed} rows carry a "
         "number), so none is shown. Parties written out from the list's key; its asterisk is its mark of the incumbent. The "
         "fingerprint is of the kept columns (ballot_cache/mt/mt_2026_sl_general_list.json)."),
        (SRC_PRI, STATE, "official candidate list", "Montana Secretary of State",
         "FEDERAL PRIMARY 2026 Candidate List (June 2, 2026): the state offices", pri["url"], "", pri["fetched"], sha_of(p_path),
         len(pri["rows"]),
         f"Every page of the grid read ({pri['items']} rows; {p_how}); {len(pri['rows'])} state rows kept, allowed columns only. Who "
         "was on each party's June ballot (FILED and NOMINATED) and whom it NOMINATED; withdrawn or removed before the primary, not "
         f"on its ballot: {left_off.total()}; independents, who petition for November and are in no primary: {petitioned}."),
        (SRC_BOOK, STATE, "official results", "Montana Secretary of State",
         "2026 Primary Election Precinct by Precinct Report (June 2, 2026)", PRECINCT_URL, "", day_of(book), sha_of(book), n_book,
         "Votes summed over every precinct for each state race; only County ID, County, Precinct, Race, District, Party, Votes and "
         "Full Name On Ballot are read. The file carries no write-in votes, so a field's total is the sum of its candidates' votes. "
         "The counties listed for each district are those whose precincts had the race on their June ballot."),
        (SRC_LEG, STATE, "official results", "Montana Secretary of State", "2026 Legislative Primary Election Canvass",
         LEG_CANVASS_URL, "", day_of(leg), sha_of(leg), sum(len(v) for v in leg_totals.values()),
         f"Control: every Senate and House candidate's total in the precinct workbook matches this canvass, party by party, in all "
         f"{len(leg_totals)} districts; each canvass line's county figures add up to its total. Linked from {RESULTS_PAGE} as "
         "\"Legislative\" under the 2026 primary."),
        (SRC_STW, STATE, "official results", "Montana Secretary of State", "2026 Statewide Primary Election Canvass", CANVASS_URL, "",
         day_of(stw), sha_of(stw), stw_checked,
         f"Control: the totals of each of the {stw_checked} Public Service Commission, Supreme Court and District Court primaries in the "
         "precinct workbook match a Total line of this canvass."),
        (SRC_COUNTY, STATE, "official place names", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)",
         COUNTY_URL, "", day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(cmap), "Montana's 56 counties: names and GEOIDs only."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)", "Montana legislators serving today, as loaded into state_mt.sqlite",
         "https://github.com/openstates/people", as_of, as_of, "", len(everyone),
         "Today's holder of each legislative seat (names, parties, districts and ids only), and which candidates are those members "
         "(same seat, family name and a fitting given name, the only fit). The roster carries no Public Service Commissioners or judges."),
    ]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:      # Montana's rows only, in one transaction
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'mt-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + local["cands"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["src"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    # ---- the report: counts, and race ids for anything to read
    def kind_of(rid):
        i = races[rid]
        return i["office_kind"] if i["level"] == "legislature" else i["level"]
    by = collections.Counter(kind_of(rid) for rid in races)
    gen_n = collections.Counter(kind_of(c[0]) for c in cand if c[1] == "general")
    one = collections.Counter(kind_of(rid) for rid in races if sum(1 for c in cand if c[0] == rid and c[1] == "general" and not c[8]) == 1)
    inc = collections.Counter(kind_of(c[0]) for c in cand if c[1] == "general" and c[7])
    say(f"    Montana (state races): Senate {by['state_senate']} seats, House {by['state_house']}, Public Service Commission "
        f"{by['statewide']}, courts {by['court']}; {gen_n.total()} candidates on the November ballot (Senate {gen_n['state_senate']}, "
        f"House {gen_n['state_house']}, Commission {gen_n['statewide']}, courts {gen_n['court']}; {write_ins.total()} declared write-ins; "
        f"{withdrawn.total()} withdrawn left off); one name printed: Senate {one['state_senate']}, House {one['state_house']}, "
        f"Commission {one['statewide']}, courts {one['court']}; incumbent on the ballot: Senate {inc['state_senate']}, House "
        f"{inc['state_house']}, Commission {inc['statewide']}, courts {inc['court']}; primary fields: Senate {fields['state_senate']}, "
        f"House {fields['state_house']}, Commission {fields['statewide']}, courts {fields['court']} (official votes, checked against "
        f"both canvasses); {len(place_rows)} places")
    for label, items in (("no candidate on the November list", empty), ("marked incumbent by the list, not matched to the roster", asterisk_only),
                         ("matched to the seat's member in the roster, not marked incumbent by the list", roster_only),
                         ("primary where the NOMINATED mark is not the top vote-getter (or a tie)", top_odd)):
        if items:
            say(f"    CHECK Montana (state races): {label}: {', '.join(items)}")
    for c in checks:
        say(f"    CHECK Montana (state races): {c}")
    for line in local["report"]:
        say(line)
    return {"races": len(races), "general": gen_n.total(), "by_race_kind": dict(by), "general_by_kind": dict(gen_n), "fields": dict(fields),
            "empty": empty, "asterisk_only": asterisk_only, "roster_only": roster_only, "top_odd": top_odd, "checks": checks,
            "local_races": len(local["races"]), "local_candidates": len(local["cands"]), "local_counties": list(local["loaded"]),
            "local_gaps": len(local["gaps"]), "local_checks": local["checks"]}


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_mt.py <database file> [--cache <folder>]")
    load(os.path.abspath(args[0]), cache=cache)
