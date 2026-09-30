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

Usage: python ballot/state_local_mt.py <database file> [--cache <folder>]
"""

import collections
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code                                        # noqa: E402
from ballot.lists.mt import CANVASS_URL, LIST_URL, LISTS, PRECINCT_URL, canvass_totals, form_fields, grid_rows  # noqa: E402
from ballot.lists.tx import proper                                                             # noqa: E402
from ballot.match import fits                                                                  # noqa: E402
from ballot.pdftext import lines                                                               # noqa: E402
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
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'mt-%'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
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
    return {"races": len(races), "general": gen_n.total(), "by_race_kind": dict(by), "general_by_kind": dict(gen_n), "fields": dict(fields),
            "empty": empty, "asterisk_only": asterisk_only, "roster_only": roster_only, "top_odd": top_odd, "checks": checks}


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
