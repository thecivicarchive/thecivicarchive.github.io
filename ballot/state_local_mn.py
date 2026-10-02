"""
ballot/state_local_mn.py - Minnesota's state and local races on the November 3, 2026 ballot, from the Secretary of
State's own candidate files, into ballot_local_2026.sqlite. The federal ballot database (ballot_2026.sqlite) is never
opened here, and U.S. Senator and U.S. Representative rows are left to the federal pages.

    python ballot/state_local_mn.py                 builds ballot_local_2026.sqlite next to ballot_2026.sqlite
    python ballot/state_local_mn.py --db test.sqlite  builds another file (for a trial run)
    python ballot/state_local_mn.py --refresh        asks the place lists again even when the cached copies are fresh

What is read, and what never is
-------------------------------
John saved four files from the Secretary of State's candidate site (its CAPTCHA answered by him; this code never asks
that site for anything) into states_cache/mn_local/sos/20261103/, beside the Secretary's own column note. Each line is
split on semicolons and cut down, on the spot, to the cells named below; the rest of the line (residence and campaign
addresses, cities, ZIP codes, phones, websites, e-mail, a running mate's contact details) is dropped before anything
else sees it, and is never printed, logged, cached or stored. The layouts were confirmed from the column note and from
the kept cells alone; a file that no longer fits stops the loader, which names the file, the line number and the check,
never the line. (From 2026-10-01, on John's order, the campaign website a candidate listed is read apart, by
ballot/local_sites.py, with this loader's own `allowed_cells`; this loader still drops that cell with the rest.)

  Candidates in the General Election - Federal, State, and County Offices (21 cells a line)
      1 name; 2 office ID; 3 office title; 4 county ID (88 = statewide or several counties); 5 the order column;
      6 party abbreviation. Cell 0 is the office ID followed by the order code and a two-digit number, and is read
      only to confirm cells 2 and 5.
  Candidates in the General Election - Local Offices (18 cells a line; the note lists 19, and this file carries no
      party cell: every local office is nonpartisan)
      0 office code (jurisdiction code, office ID, order code 90, a two-digit number); 1 name; 2 office ID;
      3 office title; 4 county ID; 5 MCD FIPS code; 6 school district number.
  Candidate Filings - Federal, State, and County Offices (20 cells a line: the first list without the order column)
      1 name; 2 office ID; 3 office title; 4 county ID; 5 party. Read only for the partisan August 11 primaries
      (statewide offices and the Legislature).
  Candidate Filings - Local Offices is not read: nonpartisan primaries are not shown yet.

The order column is not a place for each candidate. It is the party's order code (R 03, DFL 04, FI 08, GP 09, IND 10,
LIB 11, UNI 12; 90 for every nonpartisan candidate), the same two digits cell 0 carries after the office ID. In a
partisan race each party has one candidate, so ballot_order is that candidate's rank by the code (1, 2, 3 ...). A
nonpartisan candidate's ballot_order is left empty: the files give no ballot position for them (the two-digit number
after 90 is neither alphabetical nor a stated ballot order).

Places, from official lists (downloaded with states/net.py, an honest User-Agent, one request at a time, and cached in
states_cache/mn_local/):
  - county names: local_mn_counties.json (the Census Bureau's 2024 county file, as the county pages use it); the
    Secretary's county IDs 1-87 are checked against the Secretary's own precinct table, which carries both the ID and
    the county FIPS code (FIPS = 2 x ID - 1 for every county).
  - cities, townships and unorganized territories (MCD FIPS codes): names from the Census Bureau's 2020 county
    subdivision codes file (st27_mn_cousub2020.txt); a code created since 2020 is named from the Secretary's precinct
    table; a code in neither is named as the candidate file's own title writes it. Which counties a place reaches comes
    from the precinct table.
  - the Secretary of State's voting-district (precinct) table, published on the Minnesota Geospatial Commons
    (us_mn_state_sos/bdry_votingdistricts): each precinct's county, city or township, legislative districts, judicial
    district, soil and water district and hospital district. It gives the counties each legislative district, judicial
    district and hospital district reaches, and the hospital districts' names.
  - school districts: the Department of Education's School District Boundaries, SY2025-26 (us_mn_state_mde): number,
    type and name. The counties a district reaches are worked out by laying its boundary over the precincts' counties
    on a 100-metre grid, counting only cells more than 200 metres inside a county (so the slivers two boundary files
    leave along a shared line are not counted); the Secretary's own county for the district is always kept. A district
    the Department's 2025-26 list does not have yet (ISD 2913 and 2918 on 2026-09-30) is named as the Secretary's file
    writes it ("ISD #2913"), with the Secretary's county.

No candidate's name is ever used to look anything up here. Nothing but names, offices, places and parties reaches the
database from this loader: no photos, ages, websites, biographies, money or Wikipedia for anyone. (What the cards of
statewide, legislative, court, county, city and school board candidates may show beyond the list, each with its
source, is ballot/local_sites.py's work and lives in tables of its own.)

The tables (the contract the page builder reads)
------------------------------------------------
  sl_races       one row per contest. race_id is 2026-MN-<office ID>-<jurisdiction>: the county FIPS for county and
                 soil and water races, the MCD FIPS for cities and townships, ISD/SSD plus the four-digit number for a
                 school district (ISD 1 and SSD 1 share a number, so the type is part of the key), HD plus the
                 Secretary's five-digit district code for hospital and other districts (plus the seat's MCD, or its
                 name, where a hospital district elects members by area), MN for statewide, legislative and judicial
                 races; a special election adds -S (a city can hold a regular and a special election for the same
                 office). district holds the legislative district (12, 12A), the county commissioner, soil and water
                 or judicial district number, or a city's or school district's own words (Ward 2, Section II,
                 District 1, Gibbon District); seat holds a judicial seat number, a town supervisor's seat letter or
                 number, a council seat number, At Large, a school board Position, or a hospital board member's area.
  sl_candidates  one row per candidate per election: "general" (November 3) for everyone on the list, and
                 "primary-DFL" or "primary-REP" (August 11) where two or more filed for the party.
  sl_sources     every file read, with its address, when it was fetched, its SHA-256 and how many rows it gave.
  sl_places      the places a reader picks from: county, mcd, school, hospital, judicial, senate, house (Minnesota's
                 all carry source ids that begin mn-).

Other states' loaders (ballot/state_local_ia.py and the like) write into the same database; this one deletes and
rewrites Minnesota's rows only, in one transaction.
"""

import argparse
import collections
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists.mn import PARTY  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

DB = os.path.join(HERE, "ballot_local_2026.sqlite")
SOS = os.path.join(HERE, "states_cache", "mn_local", "sos", "20261103")
CACHE = os.path.join(HERE, "states_cache", "mn_local")
STATE_DB = os.path.join(HERE, "state_mn.sqlite")
COUNTIES_JSON = os.path.join(HERE, "local_mn_counties.json")
GENERAL_DATE, PRIMARY_DATE = "2026-11-03", "2026-08-11"
CANDIDATE_SITE = "https://candidates.sos.mn.gov/"

COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st27_mn_cousub2020.txt"
VTD_SERVICE = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/bdry_votingdistricts/FeatureServer/0"
VTD_ITEM = "https://gisdata.mn.gov/dataset/bdry-votingdistricts"
VTD_FIELDS = ("vtdid,mcdname,mcdfips,ctu_type,countyname,countycode,countyfips,mnsendist,mnlegdist,ctycomdist,juddist,"
              "swcdist,swcdist_n,ward,hospdist,hospdist_n,parkdist,parkdist_n")
MDE_SERVICE = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_mde/bdry_school_district_boundaries/FeatureServer/0"
MDE_ITEM = "https://gisdata.mn.gov/dataset/bdry-school-district-boundaries"
MDE_FIELDS = "sdorgid,formid,sdtype,sdnumber,prefname,shortname"
MAX_AGE_DAYS = 30
CELL = 100          # metres a grid cell, for the school district overlay
BAND = 5            # cells in the window that must all be one county (so 200 m either side of a county line is set aside)
MIN_CELLS = 1       # interior cells a district must have in a county to be said to reach it

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL,
  jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL,
  holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT,
  ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT,
  state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

LEVELS = ["statewide", "legislature", "court", "county", "soil_water", "city", "township", "school", "hospital", "other"]
PARTISAN_LEVELS = {"statewide", "legislature"}
SCHOOL_TYPE = {"01": "ISD", "02": "Common School District", "03": "SSD"}
SCHOOL_CODE = {"ISD": "01", "SSD": "03"}


class LayoutError(SystemExit):
    pass


# ---------------------------------------------------------------- reading the Secretary's files, allowed cells only

def _file(pattern):
    hits = sorted(glob.glob(os.path.join(SOS, pattern)))
    if not hits:
        raise SystemExit(f"    Minnesota state and local: no file matching {pattern!r} in {SOS}")
    return hits[0]


def allowed_cells(path, width, keep):
    """(line number, {name: cell}) for each line, keeping only the cells at the positions in `keep`. The whole line
    lives only inside this function and is dropped as soon as the allowed cells are taken; a line with the wrong
    number of cells stops the loader, which reports the file, the line number and the count, never the content."""
    base = os.path.basename(path)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            cells = line.rstrip("\r\n").split(";")
            if len(cells) != width:
                raise LayoutError(f"    {base}: line {n} has {len(cells)} cells, not the {width} this loader was checked against; stopping")
            row = {k: cells[i].strip() for k, i in keep.items()}
            del cells, line
            yield n, row


def _check(ok, path, n, what):
    if not ok:
        raise LayoutError(f"    {os.path.basename(path)}: line {n} fails the layout check '{what}'; stopping (the line is not printed)")


def clean_name(name):
    return re.sub(r"\s+", " ", name or "").strip()


def read_general_state():
    path = _file("*Candidates in the General Election - Federal, State, and County Offices*")
    rows = []
    for n, r in allowed_cells(path, 21, {"code": 0, "name": 1, "office_id": 2, "title": 3, "county": 4, "order": 5, "party": 6}):
        _check(re.fullmatch(r"\d{4}", r["office_id"]), path, n, "office ID is four digits")
        _check(r["county"].isdigit() and 1 <= int(r["county"]) <= 88, path, n, "county ID is 1-88")
        _check(re.fullmatch(r"\d{2}", r["order"]), path, n, "order column is two digits")
        _check(re.fullmatch(r"[A-Z]{1,4}", r["party"]), path, n, "party is an abbreviation")
        _check(r["code"][:4] == r["office_id"] and r["code"][4:6] == r["order"], path, n, "cell 0 = office ID + order code")
        _check(bool(r["name"]) and bool(r["title"]), path, n, "name and office title present")
        r["name"] = clean_name(r.pop("name"))
        r["county"] = str(int(r["county"]))
        r.pop("code")
        r["line"] = n
        rows.append(r)
    return path, rows


def read_general_local():
    path = _file("*Candidates in the General Election - Local Offices*")
    rows = []
    for n, r in allowed_cells(path, 18, {"code": 0, "name": 1, "office_id": 2, "title": 3, "county": 4, "mcd": 5, "sd": 6}):
        _check(re.fullmatch(r"\d{13}", r["code"]), path, n, "office code is thirteen digits")
        _check(re.fullmatch(r"\d{4}", r["office_id"]) and r["code"][5:9] == r["office_id"], path, n, "office code carries the office ID")
        _check(r["code"][9:11] == "90", path, n, "order code is 90 (nonpartisan)")
        _check(r["county"].isdigit() and 1 <= int(r["county"]) <= 87, path, n, "county ID is 1-87")
        _check(r["mcd"] == "" or re.fullmatch(r"\d{5}", r["mcd"]), path, n, "MCD FIPS is empty or five digits")
        _check(r["sd"] == "" or re.fullmatch(r"\d{4}", r["sd"]), path, n, "school district number is empty or four digits")
        _check(bool(r["name"]) and bool(r["title"]), path, n, "name and office title present")
        r["name"] = clean_name(r.pop("name"))
        r["county"] = str(int(r["county"]))
        r["jcode"] = r.pop("code")[:5]
        r["line"] = n
        rows.append(r)
    return path, rows


def read_filings_state():
    path = _file("*Candidate Filings - Federal, State, and County Offices*")
    rows = []
    for n, r in allowed_cells(path, 20, {"name": 1, "office_id": 2, "title": 3, "county": 4, "party": 5}):
        _check(re.fullmatch(r"\d{4}", r["office_id"]), path, n, "office ID is four digits")
        _check(re.fullmatch(r"[A-Z]{1,4}", r["party"]), path, n, "party is an abbreviation")
        r["name"] = clean_name(r.pop("name"))
        rows.append(r)
    return path, rows


# ---------------------------------------------------------------- official place lists

def _fresh(path, refresh):
    return (not refresh) and os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < MAX_AGE_DAYS * 86400


def _arcgis(service, fields, path, refresh, say, geometry=False, page=2000):
    """Every row of one ArcGIS feature layer (attributes, and generalised rings in UTM 15N metres when geometry is
    asked for), page by page, one request at a time, cached as JSON."""
    if _fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    rows, offset = [], 0
    geo = "&returnGeometry=true&outSR=26915&maxAllowableOffset=50&geometryPrecision=0" if geometry else "&returnGeometry=false"
    while True:
        url = (f"{service}/query?where={quote('1=1')}&outFields={fields}{geo}&orderByFields=objectid"
               f"&resultOffset={offset}&resultRecordCount={page}&f=json")
        j = json.loads(net.get(url, accept="application/json"))
        if "error" in j:
            raise SystemExit(f"    {service}: {j['error']}")
        feats = j.get("features", [])
        if geometry:
            rows += [[f["attributes"], (f.get("geometry") or {}).get("rings") or []] for f in feats]
        else:
            rows += [f["attributes"] for f in feats]
        offset += len(feats)
        if not feats or not j.get("exceededTransferLimit"):
            break
        time.sleep(1.0)
    out = {"service": service, "fields": fields, "geometry": "UTM 15N (EPSG:26915), generalised to 50 m" if geometry else None,
           "fetched": dt.date.today().isoformat(), "rows": rows}
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows fetched")
    return out


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def load_places(refresh, say):
    os.makedirs(CACHE, exist_ok=True)
    net.patient_lookups()
    paths = {"cousub": os.path.join(CACHE, "census_st27_mn_cousub2020.txt"),
             "vtd": os.path.join(CACHE, "sos_votingdistricts_attributes.json"),
             "vtd_rings": os.path.join(CACHE, "sos_votingdistricts_county_rings_26915.json"),
             "mde": os.path.join(CACHE, "mde_school_districts_sy2025_26.json"),
             "mde_rings": os.path.join(CACHE, "mde_school_district_rings_26915.json")}
    net.download(COUSUB_URL, paths["cousub"], 3650 if not refresh else 0, say=say)
    vtd = _arcgis(VTD_SERVICE, VTD_FIELDS, paths["vtd"], refresh, say)
    mde = _arcgis(MDE_SERVICE, MDE_FIELDS, paths["mde"], refresh, say)
    vtd_rings = _arcgis(VTD_SERVICE, "countyfips", paths["vtd_rings"], refresh, say, geometry=True, page=1000)
    mde_rings = _arcgis(MDE_SERVICE, "sdtype,sdnumber", paths["mde_rings"], refresh, say, geometry=True, page=100)

    counties_doc = json.load(open(COUNTIES_JSON, encoding="utf-8"))
    county_name = {f: v["name"] for f, v in counties_doc["info"].items()}
    cousub = {}
    with open(paths["cousub"], encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        if head[:7] != ["STATE", "STATEFP", "COUNTYFP", "COUNTYNAME", "COUSUBFP", "COUSUBNS", "COUSUBNAME"]:
            raise LayoutError("    st27_mn_cousub2020.txt: the header is not the one this loader was checked against; stopping")
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) >= 7 and f[1] == "27":
                cousub.setdefault(f[4], {"name": f[6], "counties": set()})["counties"].add(f[2])

    pct = vtd["rows"]
    # the Secretary's county IDs, from the Secretary's own precinct table
    code_fips = collections.defaultdict(set)
    for r in pct:
        code_fips[str(int(r["countycode"]))].add(r["countyfips"])
    county_of = {}
    for code, fipses in code_fips.items():
        if len(fipses) != 1 or int(next(iter(fipses))) != 2 * int(code) - 1:
            raise SystemExit(f"    precinct table: county ID {code} does not map to one FIPS code 2 x ID - 1 ({sorted(fipses)}); stopping")
        county_of[code] = next(iter(fipses))
    if len(county_of) != 87:
        raise SystemExit(f"    precinct table: {len(county_of)} county IDs, not 87; stopping")

    def blank(v):
        return (v or "").strip()

    mcd = {}
    for r in pct:
        m = blank(r["mcdfips"])
        if not m:
            continue
        e = mcd.setdefault(m, {"counties": set(), "sos_name": None, "type": blank(r["ctu_type"])})
        e["counties"].add(r["countyfips"])
        base = re.sub(r"\s+(Twp|Unorg)\.?$", "", blank(r["mcdname"]))
        e["sos_name"] = f"{base} {e['type']}".strip() if base else None
    lower_counties = collections.defaultdict(set)
    upper_counties = collections.defaultdict(set)
    jud_counties = collections.defaultdict(set)
    hosp = {}
    swcd = collections.defaultdict(set)
    for r in pct:
        f = r["countyfips"]
        if blank(r["mnlegdist"]):
            lower_counties[re.sub(r"^0+", "", blank(r["mnlegdist"]).upper())].add(f)
        if blank(r["mnsendist"]):
            upper_counties[str(int(blank(r["mnsendist"])))].add(f)
        if blank(r["juddist"]):
            jud_counties[str(int(blank(r["juddist"])))].add(f)
        if blank(r["hospdist"]):
            e = hosp.setdefault(int(blank(r["hospdist"])), {"name": blank(r["hospdist_n"]), "counties": set()})
            e["counties"].add(f)
        if blank(r["swcdist"]):
            swcd[f].add((blank(r["swcdist"]), blank(r["swcdist_n"])))

    schools = {}
    for r in mde["rows"]:
        t = SCHOOL_TYPE.get(r["sdtype"])
        if not t:
            continue
        key = ("CSD" if r["sdtype"] == "02" else t) + r["sdnumber"]
        schools[key] = {"name": r["prefname"], "short": r["shortname"], "type": r["sdtype"], "number": r["sdnumber"], "counties": set()}
    reach, overlay_note = school_county_overlay(vtd_rings["rows"], mde_rings["rows"], say)
    for key, fipses in reach.items():
        if key in schools:
            schools[key]["counties"] |= fipses
    return {"paths": paths, "vtd": vtd, "mde": mde, "county_name": county_name, "county_of": county_of, "cousub": cousub, "mcd": mcd,
            "lower": lower_counties, "upper": upper_counties, "judicial": jud_counties, "hospital": hosp, "swcd": swcd,
            "schools": schools, "overlay_note": overlay_note}


def _signed_area(ring):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2.0


def school_county_overlay(precincts, districts, say):
    """{school key: {county FIPS}}: the counties each school district reaches, from the Department of Education's
    boundaries laid over the Secretary's precincts (each carrying its county) on a 100-metre grid. Only cells whose
    5 x 5 neighbourhood is all one county count, so a district must reach more than 200 metres past a county line to
    be said to reach that county. (Tried against the data on 2026-09-30: 187 district-county touches had no such cell,
    the slivers two boundary files leave along a shared line; six had one to three; the rest eleven or more. The six
    are kept: a school district a reader cannot find is worse than one extra in a list.)"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    xs = [x for _a, rings in precincts for ring in rings for x, _y in ring]
    ys = [y for _a, rings in precincts for ring in rings for _x, y in ring]
    x0, y1 = min(xs) - 2 * CELL, max(ys) + 2 * CELL
    w, h = int((max(xs) - x0) / CELL) + 3, int((y1 - min(ys)) / CELL) + 3
    fipses = sorted({a["countyfips"] for a, _r in precincts})
    idx = {f: i + 1 for i, f in enumerate(fipses)}
    county = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(county)

    def px(ring):
        return [((x - x0) / CELL, (y1 - y) / CELL) for x, y in ring]

    for a, rings in precincts:
        for ring in rings:
            if len(ring) >= 3 and _signed_area(ring) < 0:      # outer rings (clockwise in Esri JSON)
                draw.polygon(px(ring), fill=idx[a["countyfips"]])
    same = ImageChops.difference(county.filter(ImageFilter.MaxFilter(BAND)), county.filter(ImageFilter.MinFilter(BAND)))
    interior = Image.composite(county, Image.new("L", (w, h), 0), same.point(lambda v: 255 if v == 0 else 0))
    out, small = {}, 0
    for a, rings in districts:
        t = {"01": "ISD", "02": "CSD", "03": "SSD"}.get(a["sdtype"])
        if not t or not rings:
            continue
        pts = [p for ring in rings for p in px(ring)]
        bx0, by0 = max(0, int(min(p[0] for p in pts)) - 1), max(0, int(min(p[1] for p in pts)) - 1)
        bx1, by1 = min(w, int(max(p[0] for p in pts)) + 2), min(h, int(max(p[1] for p in pts)) + 2)
        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        for hole in (False, True):
            for ring in rings:
                if len(ring) >= 3 and (_signed_area(ring) > 0) == hole:
                    md.polygon([(x - bx0, y - by0) for x, y in px(ring)], fill=0 if hole else 255)
        hist = interior.crop((bx0, by0, bx1, by1)).histogram(mask=mask)
        touch = county.crop((bx0, by0, bx1, by1)).histogram(mask=mask)
        got = {fipses[i - 1] for i in range(1, len(fipses) + 1) if hist[i] >= MIN_CELLS}
        small += sum(1 for i in range(1, len(fipses) + 1) if touch[i] > 0 and hist[i] < MIN_CELLS)
        out[t + a["sdnumber"]] = got
    note = (f"Counties each school district reaches: its boundary (Department of Education, SY2025-26, generalised to 50 m) laid over "
            f"the Secretary of State's precincts on a {CELL}-metre grid, counting only cells more than {CELL * (BAND // 2)} metres inside "
            f"a county (at least {MIN_CELLS}); {small} thinner touches along county lines were set aside. The Secretary's own county for a "
            f"district is always kept. Analysis, not an official list.")
    say(f"      school districts laid over counties: {len(out)} districts, {sum(len(v) for v in out.values())} district-county pairs")
    return out, note


# ---------------------------------------------------------------- office titles

ORD = {"1": "1st", "2": "2nd", "3": "3rd"}


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def classify(title):
    """The office title as the Secretary writes it -> {level, office_kind, office, district, seat, special, elect,
    place, swcd_part, judicial}. `place` is the title's own last bracket (a city, township, school or hospital
    district, as written). A title nothing here fits comes back as level and office_kind 'other'."""
    t = re.sub(r"\s+", " ", title).strip()
    c = {"special": 0, "elect": None, "place": None, "district": None, "seat": None, "swcd_part": None, "judicial": None}
    m = re.match(r"^Special Election for (.+)$", t, re.I)
    if m:
        c["special"], t = 1, m.group(1).strip()
    m = re.search(r"\s*\(Elect (\d+)\)$", t)
    if m:
        c["elect"], t = int(m.group(1)), t[:m.start()].strip()

    def out(level, kind, office, **kw):
        c.update(level=level, office_kind=kind, office=office, **kw)
        return c

    # statewide and legislative
    if re.fullmatch(r"Governor\s*(&|and)\s*L(ieutenan)?t\.?\s*Governor", t, re.I):
        return out("statewide", "governor", "Governor and Lieutenant Governor")
    for words, kind in (("Attorney General", "attorney_general"), ("Secretary of State", "secretary_of_state"), ("State Auditor", "state_auditor")):
        if t.lower() == words.lower():
            return out("statewide", kind, words)
    m = re.fullmatch(r"State Senator District (\d+)", t, re.I)
    if m:
        return out("legislature", "state_senate", "State Senator", district=str(int(m.group(1))))
    m = re.fullmatch(r"State Representative District (\d+)([AB])", t, re.I)
    if m:
        return out("legislature", "state_house", "State Representative", district=f"{int(m.group(1))}{m.group(2).upper()}")
    # courts
    m = re.fullmatch(r"(Chief Justice|Associate Justice) - Supreme Court(?: (\d+))?", t, re.I)
    if m:
        return out("court", "supreme_court", f"{m.group(1).title()}, Supreme Court", seat=m.group(2))
    m = re.fullmatch(r"(?:Chief )?Judge - Court of Appeals(?: (\d+))?", t, re.I)
    if m:
        return out("court", "court_of_appeals", "Judge, Court of Appeals", seat=m.group(1))
    m = re.fullmatch(r"Judge - (\d+)(?:st|nd|rd|th) District Court(?: (\d+))?", t, re.I)
    if m:
        return out("court", "district_court", f"Judge, {ordinal(m.group(1))} District Court", district=str(int(m.group(1))),
                   seat=m.group(2), judicial=str(int(m.group(1))))
    # county
    m = re.fullmatch(r"County Commissioner District (\d+)", t, re.I)
    if m:
        return out("county", "county_commissioner", "County Commissioner", district=str(int(m.group(1))))
    m = re.fullmatch(r"County Park Commissioner District (\d+)", t, re.I)
    if m:
        return out("county", "county_park", "County Park Commissioner", district=str(int(m.group(1))))
    for words, kind in (("County Attorney", "county_attorney"), ("County Sheriff", "sheriff"), ("County Auditor/Treasurer", "county_auditor_treasurer"),
                        ("County Auditor-Treasurer", "county_auditor_treasurer"), ("County Auditor", "county_auditor"),
                        ("County Treasurer", "county_treasurer"), ("County Recorder", "county_recorder"), ("County Surveyor", "county_surveyor")):
        if t.lower() == words.lower():
            return out("county", kind, words.replace("-", "/"))
    m = re.fullmatch(r"Soil and Water Supervisor District (\d+)(?: \((East|West|North|South)\))?", t, re.I)
    if m:
        return out("soil_water", "soil_water", "Soil and Water Supervisor", district=str(int(m.group(1))),
                   swcd_part=m.group(2).title() if m.group(2) else None)

    # local offices: the jurisdiction is the last bracket
    m = re.search(r"\s*\(([^()]+)\)$", t)
    if m:
        c["place"], t = m.group(1).strip(), t[:m.start()].strip()
    if t.lower() == "mayor":
        return out("city", "mayor", "Mayor")
    m = re.fullmatch(r"Council Member(?: (.+))?", t, re.I)
    if m:
        q = (m.group(1) or "").strip()
        if not q:
            return out("city", "council", "Council Member")
        if re.fullmatch(r"At Large", q, re.I):
            return out("city", "council", "Council Member", seat="At Large")
        s = re.fullmatch(r"Seat (\w+)", q, re.I)
        if s:
            return out("city", "council", "Council Member", seat=s.group(1))
        if re.fullmatch(r"(Wards? [\w &]+|Section [IVX\d]+|District \w+|Precinct \w+)", q, re.I):
            return out("city", "council", "Council Member", district=q)
        return out("other", "other", t)
    for words, kind in (("City Clerk - Treasurer", "city_clerk_treasurer"), ("City Clerk-Treasurer", "city_clerk_treasurer"),
                        ("City Clerk", "city_clerk"), ("City Treasurer", "city_treasurer")):
        if t.lower() == words.lower():
            return out("city", kind, words.replace(" - ", "-"))
    if t.lower() == "utility board commissioner":
        return out("city", "utility_board", "Utility Board Commissioner")
    if t.lower() == "board of public works":
        return out("city", "other", "Board of Public Works")
    if t.lower() == "sanitary district board member":
        return out("other", "sanitary_board", "Sanitary District Board Member")
    m = re.fullmatch(r"Town Supervisor(?: (At Large|Seat (\w+)))?", t, re.I)
    if m:
        return out("township", "town_supervisor", "Town Supervisor", seat=("At Large" if m.group(1) and not m.group(2) else m.group(2)))
    for words, kind in (("Town Clerk - Treasurer", "town_clerk_treasurer"), ("Town Clerk-Treasurer", "town_clerk_treasurer"),
                        ("Town Clerk", "town_clerk"), ("Town Treasurer", "town_treasurer")):
        if t.lower() == words.lower():
            return out("township", kind, words.replace(" - ", "-"))
    m = re.fullmatch(r"School Board Member(?: (.+))?", t, re.I)
    if m:
        q = (m.group(1) or "").strip()
        if not q:
            return out("school", "school_board", "School Board Member")
        if re.fullmatch(r"At Large", q, re.I):
            return out("school", "school_board", "School Board Member", seat="At Large")
        if re.fullmatch(r"Position \d+", q, re.I):
            return out("school", "school_board", "School Board Member", seat=q)
        if re.fullmatch(r"(District \w+|[\w .'-]+ District)", q, re.I):
            return out("school", "school_board", "School Board Member", district=q)
        return out("other", "other", t)
    m = re.fullmatch(r"Hospital District Board Member(?: (.+))?", t, re.I)
    if m:
        q = (m.group(1) or "").strip()
        if not q:
            return out("hospital", "hospital_board", "Hospital District Board Member")
        if re.fullmatch(r"At Large", q, re.I):
            return out("hospital", "hospital_board", "Hospital District Board Member", seat="At Large")
        if re.fullmatch(r"\d+", q):
            return out("hospital", "hospital_board", "Hospital District Board Member", seat=q)
        return out("hospital", "hospital_board", "Hospital District Board Member", seat=re.sub(r"^at large", "At Large", q, flags=re.I))
    return out("other", "other", title.strip())


def is_congress(title):
    return bool(re.match(r"U\.?\s?S\.?\s+(Senator|Representative)", title or "", re.I))


# ---------------------------------------------------------------- the build

def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "", text or "")


def county_label(places, fips):
    n = places["county_name"].get(fips)
    return f"{n} County" if n else f"County {fips}"


def mcd_label(places, code, place_text):
    """(name, source id) for an MCD FIPS code: the Census Bureau's 2020 list, else the Secretary's precinct table, else
    the candidate file's own words."""
    if code in places["cousub"]:
        return places["cousub"][code]["name"], "mn-census-2020-cousub"
    e = places["mcd"].get(code)
    if e and e["sos_name"]:
        return e["sos_name"], "mn-sos-voting-districts"
    return (place_text or f"MCD {code}"), "mn-sos-2026-general-local"


def bare_place(text):
    """'Acoma Township' / 'Aitkin city' / 'Lima Unorg' -> 'acoma' / 'aitkin' / 'lima', for comparing names only."""
    t = re.sub(r"\s+(city|township|twp\.?|unorg\.?|unorganized territory)$", "", (text or "").strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]", "", fold(t.replace("St.", "Saint").replace("St ", "Saint ")))


def resolve_mcd(places, code, county_fips, place_text):
    """(MCD code, note). A code that neither the Census Bureau's list nor the Secretary's precinct table knows (on
    2026-09-30, the local file gives Scandia's contests 45952, while both lists give Scandia city 58900) is replaced by
    the one place in the same county whose name is the title's own, and the change is said in the race's note; with no
    such single place the code is kept as the file gives it."""
    if code in places["mcd"] or code in places["cousub"]:
        return code, None
    want = bare_place(place_text)
    fits_ = sorted(m for m, e in places["mcd"].items() if county_fips in e["counties"]
                   and bare_place(places["cousub"][m]["name"] if m in places["cousub"] else e["sos_name"]) == want)
    if want and len(fits_) == 1:
        name = mcd_label(places, fits_[0], None)[0]
        return fits_[0], (f"The Secretary's candidate file gives this contest the MCD code {code}, which neither the Census Bureau's list "
                          f"nor the Secretary's precinct table has; it is filed here under {name} ({fits_[0]}), the one place of that name "
                          f"in {county_label(places, county_fips)}.")
    return code, None


def mcd_counties(places, code, fallback):
    got = set(places["mcd"].get(code, {}).get("counties", set()))
    if not got and code in places["cousub"]:
        got = set(places["cousub"][code]["counties"])
    return got | ({fallback} if fallback else set())


def party_label(code):
    return PARTY.get(code, code)


def load(say=print, db=DB, refresh=False):
    say("    Minnesota state and local: reading the Secretary of State's candidate files (names, offices, places and parties only)")
    gpath, grows = read_general_state()
    lpath, lrows = read_general_local()
    fpath, frows = read_filings_state()
    say("    Minnesota state and local: official place lists (Census Bureau, Secretary of State precinct table, Department of Education)")
    places = load_places(refresh, say)
    county_of = places["county_of"]

    races, cands, titles_of, unclassified, anomalies = {}, [], collections.defaultdict(set), [], []
    recoded = {}
    rows_placed = collections.Counter()
    congress_rows = 0

    def add_race(rid, title, fields):
        titles_of[rid].add(title)
        if rid in races:
            return
        races[rid] = fields

    # ---- the federal, state and county list
    order_codes = collections.defaultdict(dict)
    for r in grows:
        if is_congress(r["title"]):
            congress_rows += 1
            continue
        c = classify(r["title"])
        if c["level"] == "other":
            unclassified.append(("state/county list", r["title"]))
        county_fips = county_of.get(r["county"]) if r["county"] != "88" else None
        partisan = 1 if c["level"] in PARTISAN_LEVELS else 0
        key, jur, jur_id, cids = "MN", "Minnesota", "MN", None
        if c["level"] == "legislature":
            chamber = "Senate" if c["office_kind"] == "state_senate" else "House"
            jur = f"{chamber} District {c['district']}"
            src = places["upper"] if chamber == "Senate" else places["lower"]
            cids = sorted(src.get(c["district"], set())) or None
        elif c["office_kind"] == "district_court":
            jur, jur_id = f"{ordinal(c['judicial'])} Judicial District", f"JD{c['judicial']}"
            cids = sorted(places["judicial"].get(c["judicial"], set())) or None
        elif c["level"] in ("county", "soil_water") or (c["level"] == "other" and county_fips):
            if not county_fips:
                anomalies.append(f"{r['title']}: a county office listed with county ID {r['county']}")
                county_fips = "000"
            key, jur_id, cids, jur = county_fips, county_fips, [county_fips], county_label(places, county_fips)
            if c["level"] == "soil_water":
                names = sorted(places["swcd"].get(county_fips, set()), key=lambda x: x[1])
                part = c["swcd_part"]
                pick = [n for _i, n in names if part and re.search(rf"\b{part}\b", n, re.I)]
                if part and len(pick) == 1:
                    jur = f"{pick[0]} (soil and water district)"
                elif part:
                    jur = f"{county_label(places, county_fips)} ({part})"
        if c["level"] in PARTISAN_LEVELS and r["party"] == "NP":
            anomalies.append(f"{r['title']}: a partisan office with a nonpartisan candidate (line {r['line']})")
        if c["level"] not in PARTISAN_LEVELS and r["party"] != "NP":
            anomalies.append(f"{r['title']}: a nonpartisan office with a party abbreviation {r['party']} (line {r['line']})")
        rid = f"2026-MN-{r['office_id']}-{key}" + ("-S" if c["special"] else "")
        note = []
        if c["elect"] and c["elect"] > 1:
            note.append(f"Voters choose {c['elect']}.")
        if c["office_kind"] == "governor":
            note.append("The Governor and Lieutenant Governor are elected together, one ticket to a party.")
        add_race(rid, r["title"], dict(race_id=rid, state="MN", level=c["level"], office_kind=c["office_kind"], office=c["office"],
                                       jurisdiction=jur, jurisdiction_id=jur_id, county_ids=json.dumps(cids) if cids else None,
                                       district=c["district"], seat=c["seat"], special=c["special"], partisan=partisan,
                                       holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL_DATE,
                                       note=" ".join(note) or None))
        if partisan:
            party, pcode = party_label(r["party"]), ("D" if r["party"] == "DFL" else party_code(party_label(r["party"])))
            order_codes[rid][r["name"]] = int(r["order"])
            cnote = None if r["party"] in PARTY else f"The Secretary's file abbreviates this party as {r['party']}; its full name is not in the files."
        else:
            party, pcode, cnote = "Nonpartisan office", "N", None
        cands.append(dict(race_id=rid, election="general", election_date=GENERAL_DATE, name=r["name"], party=party, party_code=pcode,
                          ballot_order=None, incumbent=0, write_in=0, votes=None, pct=None, outcome=None, state_member_id=None,
                          source_id="mn-sos-2026-general-statecounty", note=cnote, _line=("S", r["line"])))
        rows_placed[c["level"]] += 1

    # a partisan race's ballot order: each candidate's rank by the party order code
    for rid, codes in order_codes.items():
        if len(set(codes.values())) != len(codes):
            anomalies.append(f"{rid}: two candidates share a party order code; no ballot order given")
            continue
        rank = {n: i + 1 for i, (n, _c) in enumerate(sorted(codes.items(), key=lambda x: x[1]))}
        for cd in cands:
            if cd["race_id"] == rid:
                cd["ballot_order"] = rank.get(cd["name"])

    # ---- the local list
    for r in lrows:
        c = classify(r["title"])
        if c["level"] == "other" and c["office_kind"] == "other":
            unclassified.append(("local list", r["title"]))
        county_fips = county_of[r["county"]]
        place_text = c["place"]
        if c["level"] == "school" or r["sd"]:
            label = re.match(r"^(ISD|SSD)\s*#\s*(\d+)$", place_text or "", re.I)
            stype = label.group(1).upper() if label else "ISD"
            if not label or int(label.group(2)) != int(r["sd"] or -1):
                anomalies.append(f"{r['title']}: school label and school district number {r['sd']} disagree")
            key = f"{stype}{r['sd']}"
            s = places["schools"].get(key)
            if s is None:      # a district the Department's 2025-26 list does not have: named as the Secretary's file writes it
                s = places["schools"][key] = {"name": f"{stype} #{int(r['sd'])}", "type": SCHOOL_CODE[stype], "number": r["sd"], "counties": set(),
                                              "sos_only": True}
            s["counties"].add(county_fips)
            jur = s["name"] if s.get("sos_only") else f"{s['name']} ({stype} #{int(r['sd'])})"
            cids = sorted(s["counties"])
            jur_id = key
        elif c["level"] == "hospital":
            code = int(r["jcode"])
            hd = places["hospital"].get(code)
            key = f"HD{r['jcode']}"
            hname = hd["name"] if hd else None
            if c["seat"] is None and place_text and (r["mcd"] or not hname or fold(place_text) != fold(hname)):
                c["seat"] = place_text      # a member elected from one city or township of the district (Perham city in Perham's)
            area = c["seat"] if c["seat"] not in (None, "At Large") and not str(c["seat"]).isdigit() else None
            if area:
                key += "-" + (r["mcd"] if r["mcd"] else slug(area))
            jur = f"{hname} (hospital district)" if hname else f"{place_text} (hospital district)"
            jur_id = f"HD{r['jcode']}"
            cids = sorted(set(hd["counties"] if hd else set()) | {county_fips} | (mcd_counties(places, r["mcd"], None) if r["mcd"] else set()))
        elif c["level"] == "other":
            key = f"HD{r['jcode']}"
            jur, jur_id = place_text or f"District {r['jcode']}", key
            cids = sorted(mcd_counties(places, r["mcd"], county_fips) if r["mcd"] else {county_fips})
        else:      # city and township offices
            if not r["mcd"]:
                anomalies.append(f"{r['title']}: a city or township office with no MCD code")
                key, jur, jur_id, cids = f"C{county_fips}", place_text, None, [county_fips]
            else:
                key, how = resolve_mcd(places, r["mcd"], county_fips, place_text)
                if how:
                    recoded[(r["mcd"], key)] = how
                jur, _src = mcd_label(places, key, place_text if c["level"] != "city" or not place_text else f"{place_text} city")
                jur_id, cids = key, sorted(mcd_counties(places, key, county_fips))
        rid = f"2026-MN-{r['office_id']}-{key}" + ("-S" if c["special"] else "")
        note = []
        if c["level"] in ("city", "township") and (r["mcd"], key) in recoded:
            note.append(recoded[(r["mcd"], key)])
        if c["elect"] and c["elect"] > 1:
            note.append(f"Voters choose {c['elect']}.")
        add_race(rid, r["title"], dict(race_id=rid, state="MN", level=c["level"], office_kind=c["office_kind"], office=c["office"],
                                       jurisdiction=jur, jurisdiction_id=jur_id, county_ids=json.dumps(cids) if cids else None,
                                       district=c["district"], seat=c["seat"], special=c["special"], partisan=0,
                                       holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL_DATE,
                                       note=" ".join(note) or None))
        cands.append(dict(race_id=rid, election="general", election_date=GENERAL_DATE, name=r["name"], party="Nonpartisan office", party_code="N",
                          ballot_order=None, incumbent=0, write_in=0, votes=None, pct=None, outcome=None, state_member_id=None,
                          source_id="mn-sos-2026-general-local", note=None, _line=("L", r["line"])))
        rows_placed[c["level"]] += 1

    for race in races.values():      # a school district's counties, once every one of its rows has added the Secretary's county
        if race["level"] == "school":
            race["county_ids"] = json.dumps(sorted(places["schools"][race["jurisdiction_id"]]["counties"]))
    clash = {rid: sorted(t) for rid, t in titles_of.items() if len(t) > 1}
    if clash:
        raise SystemExit("    two different office titles share a race id; stopping: " + "; ".join(f"{k}: {v}" for k, v in list(clash.items())[:5]))
    seen = collections.Counter((c["race_id"], c["election"], c["name"]) for c in cands)
    dup = [k for k, n in seen.items() if n > 1]
    if dup:
        raise SystemExit(f"    the same name twice in one race ({len(dup)}), e.g. {dup[0][0]}; stopping")

    # ---- the August 11 partisan primaries, from the filings
    nominee = collections.defaultdict(dict)
    for cd in cands:
        if races[cd["race_id"]]["partisan"]:
            nominee[cd["race_id"]][fold(cd["name"])] = cd
    filed = collections.defaultdict(list)
    for r in frows:
        if is_congress(r["title"]):
            continue
        c = classify(r["title"])
        if c["level"] not in PARTISAN_LEVELS:
            continue
        rid = f"2026-MN-{r['office_id']}-MN" + ("-S" if c["special"] else "")
        if rid not in races:
            anomalies.append(f"{r['title']}: filed for, but no race on the November list (no candidate left?)")
            continue
        filed[(rid, r["party"])].append(r["name"])
    primaries = 0
    for (rid, p), names in sorted(filed.items()):
        names = sorted(set(names))
        if len(names) < 2 or p in ("NP", "IND"):
            continue
        onlist = [n for n in names if fold(n) in nominee[rid] and nominee[rid][fold(n)]["party"] == party_label(p)]
        if len(onlist) != 1:
            anomalies.append(f"{rid} {p}: {len(names)} filed and {len(onlist)} on the November list; no primary field written")
            continue
        primaries += 1
        code = {"R": "REP"}.get(p, p)
        for n in names:
            cands.append(dict(race_id=rid, election=f"primary-{code}", election_date=PRIMARY_DATE, name=n, party=party_label(p),
                              party_code="D" if p == "DFL" else party_code(party_label(p)), ballot_order=None, incumbent=0, write_in=0,
                              votes=None, pct=None, outcome="advanced" if n in onlist else "lost", state_member_id=None,
                              source_id="mn-sos-2026-filings-statecounty", note=None, _line=None))

    # ---- who holds each partisan seat today, and which candidates they are
    matched, ambiguous, vacant, initial_matches = [], [], [], []
    rcon = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "party_name", "district", "chamber"), row)) for row in rcon.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party, party_name, district, chamber FROM legislators WHERE is_current = 1")]
    offs = {row[0]: dict(zip(("office", "id", "first", "last", "full", "party", "party_name"), row)) for row in rcon.execute(
        "SELECT office, bioguide_id, first_name, last_name, official_full, party, party_name FROM officials")}
    rcon.close()

    def forms(p):
        out = [([w for w in fold(p["first"]).split()], fold(p["last"]))] if p.get("first") and p.get("last") else []
        for n in [p.get("full")] + [x.strip() for x in (p.get("other") or "").split(";")]:
            if n:
                out.append(name_parts(n))
        return [f for f in out if f[1]]

    def person_fits(name, p, loose=False):
        cand = name_parts(re.split(r"\s+and\s+", name)[0])
        return any(fits(cand, f, loose=loose) for f in forms(p))

    def written_party(p):
        return {"DFL": "Democratic-Farmer-Labor", "D": "Democratic-Farmer-Labor", "R": "Republican", "Republican": "Republican"}.get(
            p.get("party_name") or p.get("party"), p.get("party_name") or p.get("party"))

    seats = {("Senate" if l["chamber"] == "Senate" else "House", re.sub(r"^0+", "", str(l["district"]).upper())): [] for l in legs}
    for l in legs:
        seats[("Senate" if l["chamber"] == "Senate" else "House", re.sub(r"^0+", "", str(l["district"]).upper()))].append(l)
    by_race = collections.defaultdict(list)
    for cd in cands:
        by_race[cd["race_id"]].append(cd)
    for rid, race in races.items():
        if race["level"] == "legislature":
            chamber = "Senate" if race["office_kind"] == "state_senate" else "House"
            holders = seats.get((chamber, race["district"]), [])
            if len(holders) == 1:
                hl = holders[0]
                race.update(holder_id=hl["id"], holder_name=hl["full"], holder_party=written_party(hl))
            elif not holders:
                vacant.append(rid)
                race["note"] = ((race["note"] or "") + " No member holds this seat on the state roster today.").strip()
            # the sitting member of this seat, and members of the other chamber whose district lies in (or holds) this one
            others = []
            if chamber == "Senate":
                others = [(l, f"Serves in the Minnesota House today (District {l['district']}).") for s in ("A", "B")
                          for l in seats.get(("House", race["district"] + s), [])]
            else:
                others = [(l, f"Serves in the Minnesota Senate today (District {l['district']}).")
                          for l in seats.get(("Senate", re.sub(r"[AB]$", "", race["district"])), [])]
            for member, how in [(h, None) for h in holders] + others:
                fitting = sorted({cd["name"] for cd in by_race[rid] if person_fits(cd["name"], member)})
                by_initial = False
                if not fitting and not how:
                    # the seat's own member, by a given name's first letter (Aaron for A.B. Repinski, whom the roster calls
                    # Ripper), only when the family name is the only one of its kind in the race, as ballot/match.py does
                    fams = collections.Counter(name_parts(n)[1] for n in {cd["name"] for cd in by_race[rid]})
                    fitting = sorted({cd["name"] for cd in by_race[rid] if fams[name_parts(cd["name"])[1]] == 1
                                      and person_fits(cd["name"], member, loose=True)})
                    by_initial = bool(fitting)
                if len(fitting) == 1:
                    for cd in by_race[rid]:
                        if cd["name"] == fitting[0]:
                            cd["state_member_id"] = member["id"]
                            if how:
                                cd["note"] = how
                            else:
                                cd["incumbent"] = 1
                    matched.append((rid, fitting[0], member["id"], "same seat" if not how else "other chamber"))
                    if by_initial:
                        initial_matches.append((rid, fitting[0], member["full"]))
                elif len(fitting) > 1:
                    ambiguous.append((rid, member["full"], fitting))
        elif race["level"] == "statewide":
            key = {"governor": "governor", "attorney_general": "attorney general", "secretary_of_state": "secretary of state",
                   "state_auditor": "state auditor"}[race["office_kind"]]
            h = offs.get(key)
            if not h:
                race["note"] = ((race["note"] or "") + " The state roster used here does not list who holds this office today.").strip()
                continue
            name = h["full"]
            if key == "governor" and offs.get("lt_governor"):
                name = f"{h['full']} and {offs['lt_governor']['full']}"
            race.update(holder_id=h["id"], holder_name=name, holder_party=written_party(h))
            fitting = sorted({cd["name"] for cd in by_race[rid] if person_fits(cd["name"], h)})
            if len(fitting) == 1:
                for cd in by_race[rid]:
                    if cd["name"] == fitting[0]:
                        cd["incumbent"] = 1
                        cd["state_member_id"] = h["id"]      # the page tells "on the ballot again" from "open" by this id
                matched.append((rid, fitting[0], h["id"], "statewide office"))
            elif len(fitting) > 1:
                ambiguous.append((rid, h["full"], fitting))

    # ---- checks
    placed_rows = sum(1 for cd in cands if cd["election"] == "general")
    expect = (len(grows) - congress_rows) + len(lrows)
    lines_seen = collections.Counter(cd["_line"] for cd in cands if cd["_line"])
    if placed_rows != expect or any(n != 1 for n in lines_seen.values()) or len(lines_seen) != expect:
        raise SystemExit(f"    check failed: {expect} non-Congress rows but {placed_rows} candidacies placed; stopping")
    senate = {r["district"] for r in races.values() if r["office_kind"] == "state_senate"}
    house = {r["district"] for r in races.values() if r["office_kind"] == "state_house"}
    missing_senate = [str(d) for d in range(1, 68) if str(d) not in senate]
    missing_house = [f"{d}{s}" for d in range(1, 68) for s in "AB" if f"{d}{s}" not in house]
    uncontested = sorted((r["district"] for r in races.values() if r["level"] == "legislature" and len(
        [cd for cd in by_race[r["race_id"]] if cd["election"] == "general"]) == 1), key=lambda d: (int(re.sub(r"\D", "", d)), d))

    # ---- sources and places
    sources = []

    def source(source_id, kind, agency, title, url, path, rows, note, fetched=None):
        sources.append((source_id, "MN", kind, agency, title, url, "", fetched or _day(path), _sha(path), rows, note))

    source("mn-sos-2026-general-statecounty", "official candidate list", "Minnesota Secretary of State",
           "Candidates in the General Election: Federal, State, and County Offices (November 3, 2026)", CANDIDATE_SITE, gpath,
           len(grows) - congress_rows,
           f"Saved by hand from the Secretary of State's candidate site, which admits people rather than scripts: {os.path.basename(gpath)}. "
           "Read: name, office ID, office title, county ID, the party order code and party. Addresses, cities, ZIP codes, phones, "
           "e-mail and running mates' contact details are never read; the campaign website a candidate listed is read apart. "
           "U.S. Senator and U.S. Representative rows are left to the federal pages. "
           "In a partisan race the ballot order is each candidate's rank by the party order code the file gives; nonpartisan candidates all "
           "carry the code 90, so the file gives no ballot position for them.")
    source("mn-sos-2026-general-local", "official candidate list", "Minnesota Secretary of State",
           "Candidates in the General Election: Local Offices (Municipal, School, and Hospital District) (November 3, 2026)", CANDIDATE_SITE,
           lpath, len(lrows),
           f"Saved by hand from the Secretary of State's candidate site: {os.path.basename(lpath)}. Read: office code, name, office ID, office "
           "title, county ID, MCD FIPS code and school district number. Every local office is nonpartisan; the file gives no ballot position. "
           "Addresses, cities, ZIP codes, phones and e-mail are never read; the campaign website a candidate listed is read apart.")
    source("mn-sos-2026-filings-statecounty", "official candidate list", "Minnesota Secretary of State",
           "Candidate Filings: Federal, State, and County Offices (2026)", CANDIDATE_SITE, fpath, len(frows),
           f"Saved by hand from the same site: {os.path.basename(fpath)}. Used only for the August 11 partisan primaries (statewide offices and the Legislature): "
           "everyone who filed for a party that two or more filed for. The one on the November list is marked as having advanced and the "
           "rest as having lost (which also covers anyone who withdrew); votes wait for the official results files. Read: name, office ID, "
           "office title, county ID and party; contact details are never read.")
    p = places["paths"]
    source("mn-census-2020-cousub", "official place codes", "U.S. Census Bureau",
           "2020 county subdivision codes, Minnesota (st27_mn_cousub2020.txt)", COUSUB_URL, p["cousub"], len(places["cousub"]),
           "Names of cities, townships and unorganized territories by MCD FIPS code.")
    source("mn-sos-voting-districts", "official boundaries (attributes)", "Minnesota Secretary of State, published by the Minnesota Geospatial Commons",
           "Voting Districts, Minnesota (precinct table)", VTD_ITEM, p["vtd"], len(places["vtd"]["rows"]),
           "Each precinct's county ID and FIPS code, city or township, legislative, judicial, soil and water and hospital districts: the "
           "check of the Secretary's county IDs (FIPS = 2 x ID - 1), the counties each place and district reaches, the names of hospital "
           "districts and split soil and water districts, and names for MCD codes created since 2020. Service: " + VTD_SERVICE,
           fetched=places["vtd"].get("fetched"))
    source("mn-mde-school-districts-2025-26", "official boundaries", "Minnesota Department of Education, published by the Minnesota Geospatial Commons",
           "School District Boundaries, Minnesota, SY2025-26", MDE_ITEM, p["mde"], len(places["mde"]["rows"]),
           "School district numbers, types and names. " + places["overlay_note"] + " Service: " + MDE_SERVICE, fetched=places["mde"].get("fetched"))
    source("mn-census-2024-counties", "official boundaries", "U.S. Census Bureau",
           "Cartographic boundary file, counties, 1:500,000 (2024), as local_mn_counties.json holds it", "https://www2.census.gov/geo/tiger/GENZ2024/shp/",
           COUNTIES_JSON, len(places["county_name"]), "County names by FIPS code.")
    source("mn-openstates-roster", "official roster", "Open States people project (CC0), as state_mn.sqlite holds it",
           "Minnesota legislators and statewide officials serving today", "https://github.com/openstates/people", STATE_DB, len(legs) + len(offs),
           "Who holds each legislative seat and statewide office today, and which candidates are those members (same seat, family name and a "
           "fitting given name, the only fit). Only names, parties and districts are read from it.")

    place_rows = []
    for f, n in sorted(places["county_name"].items()):
        place_rows.append(("county", f, f"{n} County", json.dumps([f]), "mn-census-2024-counties"))
    local_mcds, local_county = {}, {}
    for r in lrows:
        if r["mcd"] and r["mcd"] not in local_mcds:
            local_mcds[r["mcd"]], local_county[r["mcd"]] = classify(r["title"])["place"], county_of[r["county"]]
    gone = {old for (old, new) in recoded}
    for code in sorted((set(places["mcd"]) | set(local_mcds)) - gone):
        name, src = mcd_label(places, code, local_mcds.get(code))
        place_rows.append(("mcd", code, name, json.dumps(sorted(mcd_counties(places, code, local_county.get(code)))), src))
    for key, s in sorted(places["schools"].items()):
        if s.get("sos_only"):
            place_rows.append(("school", key, s["name"], json.dumps(sorted(s["counties"])), "mn-sos-2026-general-local"))
            continue
        label = SCHOOL_TYPE[s["type"]]
        place_rows.append(("school", key, f"{s['name']} ({label} #{int(s['number'])})", json.dumps(sorted(s["counties"])) if s["counties"] else None,
                           "mn-mde-school-districts-2025-26"))
    for code, h in sorted(places["hospital"].items()):
        place_rows.append(("hospital", f"HD{code:05d}", h["name"], json.dumps(sorted(h["counties"])), "mn-sos-voting-districts"))
    for d, cs in sorted(places["judicial"].items(), key=lambda x: int(x[0])):
        place_rows.append(("judicial", f"JD{d}", f"{ordinal(d)} Judicial District", json.dumps(sorted(cs)), "mn-sos-voting-districts"))
    for d, cs in sorted(places["upper"].items(), key=lambda x: int(x[0])):
        place_rows.append(("senate", d, f"Senate District {d}", json.dumps(sorted(cs)), "mn-sos-voting-districts"))
    for d, cs in sorted(places["lower"].items(), key=lambda x: (int(re.sub(r"\D", "", x[0])), x[0])):
        place_rows.append(("house", d, f"House District {d}", json.dumps(sorted(cs)), "mn-sos-voting-districts"))
    missing_schools = sorted({r["jurisdiction_id"] for r in races.values() if r["level"] == "school" and places["schools"][r["jurisdiction_id"]].get("sos_only")})

    # ---- write: Minnesota's rows only, in one transaction. Other states' loaders share this database, so nothing of
    # theirs is touched: Minnesota's races and candidates go by state and race id, its sources by state, its places by
    # their mn- source ids.
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    ccols = ["race_id", "election", "election_date", "name", "party", "party_code", "ballot_order", "incumbent", "write_in", "votes", "pct",
             "outcome", "state_member_id", "source_id", "note"]
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-MN-%' OR race_id IN (SELECT race_id FROM sl_races WHERE state = 'MN')")
        con.execute("DELETE FROM sl_races WHERE state = 'MN'")
        con.execute("DELETE FROM sl_sources WHERE state = 'MN'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'mn-%'")
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", [tuple(r[k] for k in cols) for r in races.values()])
        con.executemany(f"INSERT INTO sl_candidates VALUES ({','.join('?' * len(ccols))})", [tuple(c[k] for k in ccols) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # ---- report
    per_level = collections.Counter(r["level"] for r in races.values())
    general = sum(1 for c in cands if c["election"] == "general")
    say("    races by level: " + ", ".join(f"{lv} {per_level[lv]:,}" for lv in LEVELS if per_level[lv]))
    say("    candidacies by level: " + ", ".join(f"{lv} {rows_placed[lv]:,}" for lv in LEVELS if rows_placed[lv]))
    say(f"    check: {expect:,} non-Congress rows in the two November files, {general:,} candidacies placed, each in exactly one race "
        f"({congress_rows} U.S. Senate and House rows left to the federal pages)")
    say(f"    Legislature: {len(senate)} of 67 Senate and {len(house)} of 134 House districts have a race"
        + (f"; no race on the list: Senate {', '.join(missing_senate)}" if missing_senate else "")
        + (f"; House {', '.join(missing_house)}" if missing_house else "")
        + f"; {len(uncontested)} with one candidate: {', '.join(uncontested)}")
    say(f"    sitting members matched to candidates: {sum(1 for m in matched if m[3] == 'same seat')} in their own seat, "
        f"{sum(1 for m in matched if m[3] == 'other chamber')} running for the other chamber, {sum(1 for m in matched if m[3] == 'statewide office')} statewide; "
        f"vacant seats: {', '.join(vacant) or 'none'}")
    for rid, name, who in initial_matches:
        say(f"      matched by a given name's first letter (read these): {rid}: {name} is {who}")
    for rid, who, names in ambiguous:
        say(f"      left unmatched (more than one name fits {who}): {rid}: {'; '.join(names)}")
    if unclassified:
        say(f"    titles not classified (level and office kind 'other'): {len(unclassified)}")
        for where, t in sorted(set(unclassified)):
            say(f"      {where}: {t}")
    other_kind = sorted({(r["level"], r["office"]) for r in races.values() if r["office_kind"] == "other"})
    if other_kind:
        say("    office kind 'other': " + "; ".join(f"{o} ({lv})" for lv, o in other_kind))
    unknown_parties = sorted({c["note"].split(" as ")[1].split(";")[0] for c in cands if c["note"] and "abbreviates" in c["note"]})
    if unknown_parties:
        say(f"    party abbreviations with no full name in the files (printed as written): {', '.join(unknown_parties)}")
    for (old, new), _how in sorted(recoded.items()):
        say(f"    MCD code refiled by name: the file's {old} is {mcd_label(places, new, None)[0]} ({new})")
    if missing_schools:
        say(f"    school districts not in the Department of Education's 2025-26 list (named as the Secretary writes them): {', '.join(missing_schools)}")
    for a in anomalies:
        say(f"    note: {a}")
    say(f"    Minnesota state and local: {len(races):,} races, {general:,} candidates on the November ballot; {primaries} party primaries with a "
        f"field; {len(place_rows):,} places; {os.path.basename(db)}")
    return {"races": len(races), "candidates": general, "primaries": primaries, "per_level": dict(per_level), "unclassified": unclassified,
            "ambiguous": ambiguous, "anomalies": anomalies, "missing_senate": missing_senate, "missing_house": missing_house,
            "uncontested": uncontested, "vacant": vacant, "matched": matched}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Minnesota's state and local races on the November 3, 2026 ballot -> ballot_local_2026.sqlite")
    ap.add_argument("--db", default=DB, help="database file to build (default: ballot_local_2026.sqlite next to ballot_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask the place lists again even when the cached copies are fresh")
    a = ap.parse_args(argv)
    if os.path.abspath(a.db) == os.path.abspath(os.path.join(HERE, "ballot_2026.sqlite")):
        raise SystemExit("    this loader never writes ballot_2026.sqlite")
    load(db=os.path.abspath(a.db), refresh=a.refresh)


if __name__ == "__main__":
    main()
