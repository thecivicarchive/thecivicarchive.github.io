"""
ballot/mo_geo.py - the geography behind Missouri's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py, ballot/sd_geo.py and ballot/oh_geo.py for the few things those states added, and
changes nothing in any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read them all.

    python ballot/mo_geo.py                 builds ballot_geo/mo/ and runs the self-test (the first build downloads
                                            340 MB of census blocks and lays districts over precincts: allow half an hour)
    python ballot/mo_geo.py --selftest      runs the self-test on the files already built
    python ballot/mo_geo.py --refresh       asks the map services, the statutes and the polling place list again
    python ballot/mo_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names, for the words the
ballot database uses for council wards, and for the check that every shape's id is one the races carry.

What Missouri publishes, and what that does to the files
--------------------------------------------------------
Missouri has no statewide map file of its precincts as they stand in 2026: each of the 116 election authorities (114
county clerks or boards, the City of St. Louis and Kansas City) keeps its own, and the Secretary of State publishes no
lines. The only statewide precinct lines a script may read are the Census Bureau's 2020 voting districts: the precincts
the election authorities reported for the 2020 census (4,604 of them). So a shape here is a 2020 voting district, cut
wherever a line of the 2022 legislative or congressional districts crosses it, and index.json says so in plain words:
an election authority may have redrawn the precinct since. What a ballot depends on does not depend on the precinct:
the county, the legislative and congressional districts, the judicial circuit, the court of appeals district, the
city, town, village or township, the school district and (in four charter counties) the county council district at a
point are each taken from a current official file.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/mo_local/)
----------------------------------------------------------------------------------------------------------------------
  - Census blocks: the Census Bureau's TIGER/Line 2020 tabulation blocks of Missouri (tl_2020_29_tabblock20.zip,
    253,632 blocks). Only each block's number and outline are read.
  - Which voting district a block is in: the Bureau's 2020 Block Assignment File (BlockAssign_ST29_MO.zip, the VTD
    table), and the voting districts' names from tl_2020_29_vtd20.zip.
  - Which Missouri House and Senate district a block is in: the Bureau's 2024 State Legislative District Block
    Equivalency Files (sldl24.zip, sldu24.zip): the plans drawn in 2022 (163 House districts, 34 Senate districts). A
    block is in exactly one district, so the legislative lines here are exact.
  - Which congressional district a block is in: the Bureau's 119th Congress Block Equivalency File (cd119.zip): the
    eight districts enacted in 2022. The map the General Assembly passed in 2025 is paused until voters decide a
    referendum on it in November 2026, so the 2022 lines are the ones in effect for this election (ballot/races.py
    carries the same note, from NCSL's tracker). If that changes, CD_NOTE and CD_URL here are what to change.
  - Cities, towns and villages: TIGER/Line 2025 places (tl_2025_29_place.zip; incorporated, active places only).
    Townships, the county lines and the state's outline: TIGER/Line 2025 county subdivisions (tl_2025_29_cousub.zip).
    Only the townships the Bureau marks as functioning governments (the counties with township organization) are
    places here; in the rest of Missouri a township is a line on the map with no officers.
  - County names: the Bureau's 2020 list of county codes (st29_mo_cou2020.txt). The City of St. Louis is a county of
    its own (29510).
  - School districts: "Missouri Public Schools", layer "Public School Districts", on the State of Missouri's ArcGIS
    site (Office of Geospatial Information, with the Department of Elementary and Secondary Education): 515 districts.
    Only the district's name and its six-digit county-district code are asked for; the layer's address, phone, fax,
    e-mail and web columns never are.
  - Judicial circuits (46, each whole counties; the 22nd is the City of St. Louis): which counties, from the Secretary
    of State's Official Manual 2025-2026, chapter 5, as ballot/state_local_mo.py reads it (circuit numbers and county
    names only). The lines are the county lines.
  - Court of appeals districts (Eastern, Southern, Western; each whole counties): RSMo 477.050, 477.060 and 477.070 on
    revisor.mo.gov. The lines are the county lines.
  - County council and legislature districts, each from the county's own map service, asking only for the district
    number (the layers' member names, parties, phones and e-mail are never requested):
      Jackson County Legislature, six districts: Jackson County GIS, "Legislative Districts", layer "Individual
        Districts". (The three at-large legislators are elected by the whole county; their districts are where they
        must live, and are not shapes.)
      St. Charles County Council, seven districts: St. Charles County GIS, "Voting Information", layer "County Council
        Districts".
      Jefferson County Council, seven districts: Jefferson County's "Voting Districts", layer "County Council
        Districts" (the 2022 redistricting).
      St. Louis County Council, seven districts: the St. Louis County Board of Elections' "St. Louis County Council
        Districts" (the lines a federal court set on February 22, 2022).
  - City wards: St. Charles County GIS, "Voting Information", layer "Municipal Wards" (only the city's name and the
    ward's number are asked for). A ward is drawn only for a city whose council race the ballot database carries.
  - Polling places: the St. Louis County Board of Elections' "November 3, 2026 General Election - Polling Places".
    See POLLING PLACES.

What is built (ballot_geo/mo/): index.json, manifest.json, precincts/<county>.json (115), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, ward, com, school), school/<id>.json, polling_places.json and reader.js, each
as ballot/mn_geo.py describes. Coordinates are on the same grid (0.00001 degree, translate [-98, 43]; Missouri lies
south of 43 north, so its grid latitudes are negative numbers, which TopoJSON allows).

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "MO" (j = "29", the jurisdiction_id of statewide races)
  county    "29095"                 sl_places county id; jurisdiction_id of county offices and associate circuit judges
  mcd       "MO-M-64082"            MO-M- and the Census code: a city's, town's or village's place code, a township's
                                    county subdivision code (properties.t says which)
  ward      "MO-M-64082|Ward Four"  <city>|<ward as the council race words it>
  com       "29095|1"               <county>|<council or legislature district>: Jackson, Jefferson, St. Charles and
                                    St. Louis counties
  house     "60"   senate "6"   cd "3" (properties.race is the federal race id, 2026-MO-H03)
  judicial  "MO-JC16"               the judicial circuit (d = "Circuit 16", as the circuit's races word it)
  school    "MO-S-048078"           MO-S- and the Department's six-digit county-district code; the St. Louis City
                                    district carries the id the ballot database gave it (SCHOOL_IDS)

A precinct also names its court of appeals district ("appeals": MO-COA-E, MO-COA-S, MO-COA-W). No layer draws it: the
page's own rule has no place for a court district that is neither the state nor a contest's jurisdiction id, so
index.json lists those five retention votes under check.said_by_the_precinct.

Not drawn, because no statewide file has the lines: an associate commissioner's district (a county commission's
Eastern and Western or Northern and Southern halves), city wards outside St. Charles County, and school board
subdistricts. index.json lists every race without a shape under "check", with the reason.

POLLING PLACES
--------------
Missouri has no statewide list of polling places a script may read: the Secretary of State's voter lookup asks for a
voter's own details, and each election authority publishes its own list. One authority publishes the November 3, 2026
list as an open map layer: the St. Louis County Board of Elections (200 places, each with its point). That layer is
read here (place number, name, street address, ZIP code, and whether it is an absentee site; a polling place is a
public building), and polling_places.json lists the other 114 counties as not on the list. The layer does not say
which precinct votes at which place, and the map's precinct lines are the 2020 ones, so no precinct is tied to a
place, and the file is marked "unchecked", which a page must not show, until a person has confirmed how the Board
assigns voters to places and set POLL_CHECKED to True.
"""

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import time
import zipfile
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import nd_geo as N  # noqa: E402
from ballot import sd_geo as S  # noqa: E402
from ballot import oh_geo as O  # noqa: E402,E741

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "MO", "29", "Missouri"
N_COUNTIES, N_HOUSE, N_SENATE, N_CD, N_CIRCUITS = 115, 163, 34, 8, 46
OUT = os.path.join(HERE, "ballot_geo", "mo")
CACHE = os.path.join(HERE, "states_cache", "mo_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://voteroutreach.sos.mo.gov/portal/"

CENSUS = "https://www2.census.gov/"
BLOCK_URL = CENSUS + "geo/tiger/TIGER2020/TABBLOCK20/tl_2020_29_tabblock20.zip"
BAF_URL = CENSUS + "geo/docs/maps-data/data/baf2020/BlockAssign_ST29_MO.zip"
VTD_URL = CENSUS + "geo/tiger/TIGER2020PL/STATE/29_MISSOURI/29/tl_2020_29_vtd20.zip"
SLDL_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip"
SLDU_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip"
CD_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/119-congressional-district-befs/cd119.zip"
CD_NOTE = ("The eight districts enacted in 2022 (the Census Bureau's 119th Congress equivalency file). The map the General Assembly passed in 2025 is paused "
           "until voters decide a referendum on it in November 2026, so the 2022 lines are in effect for this election.")
COUSUB_URL = CENSUS + "geo/tiger/TIGER2025/COUSUB/tl_2025_29_cousub.zip"
PLACE_URL = CENSUS + "geo/tiger/TIGER2025/PLACE/tl_2025_29_place.zip"
COUNTY_URL = CENSUS + "geo/docs/reference/codes2020/cou/st29_mo_cou2020.txt"
SHARED = ("sldl24.zip", "sldu24.zip")                      # national files another state's build may already have fetched
SCHOOL_SERVICE = "https://services6.arcgis.com/r9ddpXHABk7voAmS/arcgis/rest/services/Missouri_Public_Schools/FeatureServer/1"
SCHOOL_ITEM = "https://www.arcgis.com/home/item.html?id=cc5213ba5f7e48a38354a483cfaa1675"
SCHOOL_FIELDS = "DIST_NAME,DIST_CODE"                      # never the address, phone, fax, e-mail or web columns
# A district the ballot database filed under an id of its own before these files existed: {the Department's code: (that id, a word its name must carry)}
SCHOOL_IDS = {"115115": ("MO-S-510-city-of-st-louis-board-of-education", "St. Louis City")}
STATUTE = "https://revisor.mo.gov/main/OneSection.aspx?section="
APPEALS = {"E": ("Eastern District", "477.050"), "S": ("Southern District", "477.060"), "W": ("Western District", "477.070")}

# County council and legislature districts: county -> (service, the district's column, the row number's column, how many,
# the body, the source id, who publishes it, the layer's title, what it says of itself). Only the district's column is asked for.
COUNCILS = {
    "29095": ("https://jcgis.jacksongov.org/arcgis/rest/services/ElectionAdministration/LegislativeDistricts/MapServer/1", "DISTRICT", 6,
              "Legislative District", "mo-jackson-county-gis-legislative-districts", "Jackson County, Missouri (GIS)",
              "Legislative Districts :: Jackson County, MO, layer Individual Districts", "The six districts that each elect one county legislator."),
    "29099": ("https://services1.arcgis.com/Ur3TPhgM56qvxaar/arcgis/rest/services/Voting_Districts/FeatureServer/0", "Council_District", 7,
              "Council District", "mo-jefferson-county-council-districts-2022", "Jefferson County, Missouri (GIS)",
              "Voting Districts, layer County Council Districts", "The district lines the county's Redistricting Committee drew in 2022."),
    "29183": ("https://gis-dev.sccmo.org/scc_gis/rest/services/open_data/Voting_Information/FeatureServer/8", "DISTRICT", 7,
              "Council District", "mo-st-charles-county-gis-council-districts", "St. Charles County, Missouri (GIS)",
              "Voting Information, layer County Council Districts", "The county's open-data service; the address is the one the county's own listing gives."),
    "29189": ("https://services6.arcgis.com/wkbq75VVf2MvUvs7/arcgis/rest/services/St_Louis_County_Council_Districts/FeatureServer/0", "DISTRICT", 7,
              "Council District", "mo-st-louis-county-boe-council-districts-2022", "St. Louis County Board of Elections",
              "St. Louis County Council Districts", "County Council District lines were set per Federal Court Order issued on 2/22/2022 based on the 2020 Census results."),
}
AT_LARGE = {"29095": "Jackson County's three at-large legislators are elected by the whole county; each must live in the at-large district the seat is named for"}
WARD_SERVICE = "https://gis-dev.sccmo.org/scc_gis/rest/services/open_data/Voting_Information/FeatureServer/3"
WARD_FIELDS = "CITY,NAME"                                  # never the members' names
WARD_COUNTY = "29183"
WARD_SRC = "mo-st-charles-county-gis-municipal-wards"
NUMBER_WORDS = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen"]
POLL_SERVICE = "https://services6.arcgis.com/wkbq75VVf2MvUvs7/arcgis/rest/services/11_3_26_PollingPlaces/FeatureServer/0"
POLL_ITEM = "https://www.arcgis.com/home/item.html?id=ca7ef61a58894857be003bbb5b241746"
POLL_FIELDS = "loc,name,address,zipcode,abs_type"
POLL_COUNTY = "29189"
POLL_TITLE = "November 3, 2026 General Election - Polling Places (St. Louis County Board of Elections)"
POLL_CHECKED = False              # True only when a person has confirmed how the Board assigns voters to these places

ARC_KINDS = ["county", "house", "senate", "cd", "judicial"]      # the kinds a precinct lies wholly inside, so its lines can draw them
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM, MCD_THICK = I.TOL_MCD, I.MCD_ZOOM, I.MCD_THICK
NEAR_M = G.NEAR_M
AREA_SLACK = 0.02                 # a county's 2020 blocks and the Bureau's 2025 county may differ in area by this share
WATER = "ZZZZZZ"                  # the Bureau's "voting district not defined"
PLACE_WORD = {"25": "city", "43": "town", "47": "village"}

clean, slug, title = N.clean, N.slug, O.title


def fold(text):
    """A name for matching: capitals, letters and figures only, Saint as St."""
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"\bSAINT\b", "ST", (text or "").upper()))


# ---------------------------------------------------------------- precincts: 2020 voting districts, from census blocks

def read_tables(bafpath, lpath, upath, cdpath, vpath):
    """{block: (county, voting district code, House, Senate, congressional district)} for every block in a voting
    district, the blocks in none, and {(county, code): the voting district's name}."""
    z = zipfile.ZipFile(bafpath)
    member = next(n for n in z.namelist() if n.endswith("_VTD.txt"))
    lines = z.read(member).decode("utf-8").splitlines()
    if lines[0].strip() != "BLOCKID|COUNTYFP|DISTRICT":
        raise GeoError(f"    {os.path.basename(bafpath)}: the voting district table's heading is now {lines[0]!r}; stopping")
    vtd = {}
    for line in lines[1:]:
        b, c, v = line.split("|")
        vtd[b] = (c, v.strip())

    def bef(path, head):
        zz, out = zipfile.ZipFile(path), {}
        member = next(n for n in zz.namelist() if n.lower().startswith("national"))
        with zz.open(member) as fh:
            text = io.TextIOWrapper(fh, "utf-8")
            if next(text).strip() != head:
                raise GeoError(f"    {os.path.basename(path)}: the heading is not {head!r}; stopping")
            for line in text:
                if line.startswith(FIPS):
                    b, d = line.strip().split(",")
                    out[b] = d
        return out

    low, up, cd = bef(lpath, "GEOID,SLDLST"), bef(upath, "GEOID,SLDUST"), bef(cdpath, "GEOID,CDFP")
    if set(low) != set(vtd) or set(up) != set(vtd) or set(cd) != set(vtd):
        raise GeoError("    the block assignment file and the legislative and congressional equivalency files do not list the same blocks; stopping")
    table, water = {}, set()
    for b, (c, v) in vtd.items():
        if v == WATER or not v:
            water.add(b)
            continue
        h, s, d = re.sub(r"^0+", "", low[b]), re.sub(r"^0+", "", up[b]), re.sub(r"^0+", "", cd[b])
        if not (b[:5] == FIPS + c and re.fullmatch(r"[0-9A-Za-z-]{1,6}", v) and re.fullmatch(r"\d{1,3}", h) and re.fullmatch(r"\d{1,2}", s) and re.fullmatch(r"[1-8]", d)):
            raise GeoError(f"    block {b}: county {c!r}, voting district {v!r}, House {low[b]!r}, Senate {up[b]!r}, Congress {cd[b]!r} do not fit the layout this builder was checked against; stopping")
        table[b] = (FIPS + c, v, h, s, d)
    seen = [{t[i] for t in table.values()} for i in (2, 3, 4)]
    if [len(x) for x in seen] != [N_HOUSE, N_SENATE, N_CD]:
        raise GeoError(f"    the equivalency files give {len(seen[0])} House, {len(seen[1])} Senate and {len(seen[2])} congressional districts, not {N_HOUSE}, {N_SENATE} and {N_CD}; stopping")
    import shapefile
    zz = zipfile.ZipFile(vpath)
    base = next(n for n in zz.namelist() if n.endswith(".dbf"))
    vname = {(FIPS + r["COUNTYFP20"], r["VTDST20"].strip()): r["NAME20"] for r in (x.as_dict() for x in shapefile.Reader(dbf=io.BytesIO(zz.read(base))).iterRecords())}
    missing = {(c, v) for c, v, _h, _s, _d in table.values()} - set(vname)
    if missing:
        raise GeoError(f"    {len(missing)} voting districts of the block assignment file are not in {os.path.basename(vpath)} (e.g. {sorted(missing)[0]}); stopping")
    return table, water, vname


def vtd_name(code, raw):
    """A voting district's name as the page prints it: the Bureau's, without its "VTD" label; a name printed all in
    capitals in ordinary capitals; a name that is only the code again stays the code."""
    n = re.sub(r"\s+", " ", re.sub(r"^\s*VTD\b[\s\-:]*", "", raw or "", flags=re.I)).strip(" -")
    if not n:
        return "Voting district " + code.lstrip("0")
    if n.upper() == n and re.search(r"[A-Z]{4}", n) and not re.search(r"\d[A-Z]|[A-Z]\d", n):
        n = title(n)
    return n[0].upper() + n[1:] if n[0].islower() else n


def read_units(blockpath, table, water, vname, say):
    """The precincts: the blocks of each 2020 voting district put together, one piece for each legislative and
    congressional district it reaches. Returns (pre, polys, said): what is said of each, its rings as vertex keys, and
    the Bureau's own area of the blocks by county."""
    import shapefile
    z = zipfile.ZipFile(blockpath)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    groups, seen, twice = collections.defaultdict(set), set(), 0
    said = {"in": collections.Counter(), "all": collections.Counter()}
    for sr in r.iterShapeRecords():
        b = sr.record["GEOID20"]
        said["all"][b[:5]] += sr.record["ALAND20"] + sr.record["AWATER20"]
        if b in water:
            seen.add(b)
            continue
        said["in"][b[:5]] += sr.record["ALAND20"] + sr.record["AWATER20"]
        if b not in table or b in seen:
            raise GeoError(f"    {os.path.basename(blockpath)}: block {b} is not in the block assignment file, or is there twice; stopping")
        seen.add(b)
        s = groups[table[b]]
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        for i in range(len(parts) - 1):
            ks = G.clean_ring(pts[parts[i]:parts[i + 1]])
            if not ks:
                continue
            a = ks[-1]
            for k in ks:
                if (k, a) in s:
                    s.remove((k, a))
                elif (a, k) in s:
                    twice += 1
                else:
                    s.add((a, k))
                a = k
    if len(seen) != len(table) + len(water):
        raise GeoError(f"    {os.path.basename(blockpath)}: {len(seen):,} blocks, but the block assignment file lists {len(table) + len(water):,}; stopping")
    if twice:
        raise GeoError(f"    {os.path.basename(blockpath)}: {twice} edges are claimed by two blocks of one precinct; stopping")
    pieces = collections.Counter(k[:2] for k in groups)
    order = sorted(groups, key=lambda k: (k[0], k[1], G.natkey(k[2]), G.natkey(k[3]), G.natkey(k[4])))
    part_no, count = {}, collections.Counter()
    for key in order:
        count[key[:2]] += 1
        part_no[key] = count[key[:2]]
    pre, polys, ids = [], [], set()
    for key in order:
        county, code, house, senate, cd = key
        pid = f"{county}.{re.sub(r'[^0-9A-Za-z-]', '-', code)}" + (f".{part_no[key]}" if pieces[key[:2]] > 1 else "")
        if pid in ids:
            raise GeoError(f"    two precincts would share the id {pid}; stopping")
        ids.add(pid)
        name = vtd_name(code, vname[(county, code)])
        pre.append({"id": pid, "county": county, "vtd": code, "precinct": county + code, "house": house, "senate": senate, "cd": cd,
                    "name": name + (f", part {part_no[key]}" if pieces[key[:2]] > 1 else ""), "vtdname": name, "parts": pieces[key[:2]]})
        polys.append(S.loops(groups[key]))
    say(f"      {len(seen):,} census blocks ({len(water)} in no voting district) put together into {len(pieces):,} voting districts of 2020, "
        f"{len(pre):,} pieces once cut by the 2022 legislative and congressional districts ({sum(1 for n in pieces.values() if n > 1)} voting districts reach more than one)")
    return pre, polys, said


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'mo-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def county_names(path):
    out = {}
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="|"))
    col = {h: i for i, h in enumerate(rows[0])}
    for r in rows[1:]:
        if r and r[col["STATEFP"]] == FIPS:
            out[FIPS + r[col["COUNTYFP"]]] = r[col["COUNTYNAME"]]
    if len(out) != N_COUNTIES:
        raise GeoError(f"    {os.path.basename(path)}: {len(out)} counties, not {N_COUNTIES}; stopping")
    return out


def circuits(cname, say):
    """({county: circuit number}, what the source says of itself) from the Secretary of State's Official Manual, as
    ballot/state_local_mo.py reads and keeps it (circuit numbers and county names only)."""
    from ballot import state_local_mo as M
    got, about = M.read_circuits(M.LOCAL_DIR, sorted(cname.items()), say)
    if got is None:
        raise GeoError(f"    judicial circuits: the Official Manual's list could not be used ({about}); stopping")
    out = {c: str(no) for no, cs in got.items() for c in cs}
    if sorted(out) != sorted(cname) or len(got) != N_CIRCUITS:
        raise GeoError(f"    judicial circuits: {len(got)} circuits over {len(out)} counties, not {N_CIRCUITS} over {N_COUNTIES}; stopping")
    return out, about


def appeals(path, cname, refresh, say):
    """({county: "E" | "S" | "W"}, the cached record) from RSMo 477.050, 477.060 and 477.070: the Eastern and Southern
    districts are lists of counties, the Western is every other county."""
    if not G._fresh(path, refresh):
        try:
            net.patient_lookups()
            doc = {"fetched": dt.date.today().isoformat(), "sections": {}}
            for key, (_word, sec) in APPEALS.items():
                raw = net.get(STATUTE + sec, timeout=120)
                text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<[^>]+>", " ", raw.decode("utf-8", "replace"))))
                m = re.search(rf"{re.escape(sec)}\. Territorial jurisdiction of the (\w+) district court of appeals\. \W* The jurisdiction of the \w+ district of the court of appeals "
                              r"shall be coextensive with (.*?)\.\W*-{4,}", text)
                if not m or m.group(1).lower() != APPEALS[key][0].split()[0].lower():
                    raise GeoError(f"    RSMo {sec} no longer reads as the territory of the {APPEALS[key][0]}")
                doc["sections"][key] = {"url": STATUTE + sec, "sha256": hashlib.sha256(raw).hexdigest(), "text": m.group(2)}
                time.sleep(1.0)
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=1)
            os.replace(path + ".part", path)
        except Exception as e:  # noqa: BLE001
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                raise
            say(f"      could not read RSMo 477.050 to 477.070 again ({e}); using the copy on disk")
    doc = json.load(open(path, encoding="utf-8"))
    by_name = {fold(n.replace(" County", "")): c for c, n in cname.items() if n.endswith(" County")}
    out = {}
    for key in ("E", "S"):
        text = doc["sections"][key]["text"]
        m = re.fullmatch(r"the counties of (.*?)( and the city of St\. Louis)?", text)
        if not m:
            raise GeoError(f"    RSMo {APPEALS[key][1]}: the sentence is no longer a list of counties; stopping")
        for n in [x.strip() for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)) if x.strip()]:
            c = by_name.get(fold(n))
            if c is None or c in out:
                raise GeoError(f"    RSMo {APPEALS[key][1]}: {n!r} is not a county, or is in two districts; stopping")
            out[c] = key
        if m.group(2):
            out[FIPS + "510"] = key
    if "all the counties in the state except those embraced in the jurisdiction of the eastern and the southern districts" not in doc["sections"]["W"]["text"]:
        raise GeoError("    RSMo 477.070 no longer gives the Western District every other county; stopping")
    for c in cname:
        out.setdefault(c, "W")
    n = collections.Counter(out.values())
    if (n["E"], n["S"], n["W"]) != (26, 44, 45):
        raise GeoError(f"    court of appeals districts: {dict(n)} counties, not 26 Eastern, 44 Southern and 45 Western; stopping")
    return out, doc


def fetch_small(service, fields, path, refresh, say, where="1=1"):
    """Every feature of a small layer (one request; a map server that does not page) with its rings in longitude and
    latitude, cached as gzipped JSON in mn_geo.fetch_full's layout."""
    if G._fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    try:
        j = json.loads(net.get(f"{service}/query?where={quote(where)}&outFields={fields}&returnGeometry=true&outSR=4326&geometryPrecision=7&f=json", timeout=300, accept="application/json"))
        if "error" in j or j.get("exceededTransferLimit"):
            raise GeoError(f"    {service}: {j.get('error') or 'more rows than one request brings'}")
        rows = [[f["attributes"], (f.get("geometry") or {}).get("rings") or []] for f in j.get("features", [])]
        count = json.loads(net.get(f"{service}/query?where={quote(where)}&returnCountOnly=true&f=json", accept="application/json")).get("count")
        if count != len(rows) or not rows:
            raise GeoError(f"    {service}: {len(rows):,} shapes came, but the service counts {count}")
        time.sleep(1.0)
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not refresh {os.path.basename(path)} ({str(e).strip()}); using the copy on disk")
            return json.load(gzip.open(path, "rt", encoding="utf-8"))
        raise
    out = {"service": service, "fields": fields, "geometry": "longitude and latitude (EPSG:4326), seven decimals, full detail", "fetched": dt.date.today().isoformat(), "rows": rows}
    with gzip.open(path + ".part", "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} shapes fetched")
    return out


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"mo_geo_overlay_{name}.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say(f"      laying the {name} lines over the precincts (kept for the next build)")
    res = G.school_overlay(pre_rings, districts, levels=(G.SCHOOL_THICK,), say=None)
    rows = [[[d, round(share, 5), thick[0]] for d, share, thick in row] for row in res]
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def place_overlay_cached(pre_rings, cities, towns, stamp, refresh, say):
    path = os.path.join(CACHE, "mo_geo_overlay_places.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say("      laying the city, town, village and township lines over the precincts (kept for the next build)")
    rows = I.place_overlay(pre_rings, cities, towns, MCD_THICK, say)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


# ---------------------------------------------------------------- wards: the words the council races use

def ward_cities(info, census_name, city_county):
    """{the ward layer's folded city name: (place id, {ward number: the district as the council race words it})} for the
    cities of WARD_COUNTY whose council races the ballot database carries by ward."""
    want = collections.defaultdict(set)
    for _rid, level, kind, _jur, jid, district, _seat in info["races"]:
        if level == "city" and kind == "council" and district:
            want[str(jid)].add(str(district))
    out, why = {}, {}
    for jid, asked in sorted(want.items()):
        if WARD_COUNTY not in city_county.get(jid, ()):
            why[jid] = "no file read here has this city's ward lines; the city or its election authority keeps them"
            continue
        label = {}
        for d in asked:
            m = re.fullmatch(r"Ward (\w+)", d)
            n = (int(m.group(1)) if m.group(1).isdigit() else NUMBER_WORDS.index(m.group(1)) if m.group(1) in NUMBER_WORDS else None) if m else None
            if n:
                label[n] = d
        if not label:
            why[jid] = "the council race's district is not worded as a numbered ward"
            continue
        style = "word" if any(not d.split()[1].isdigit() for d in label.values()) else "digit"
        out[fold(re.sub(r" (city|town|village)$", "", census_name[jid]))] = (jid, label, style)
    return out, why


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, ward_why, appeals_ids):
    """Every Missouri race in the ballot database against the shapes. A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S_ = shape_ids
    by_layer, missing, matched, said = collections.Counter(), collections.OrderedDict(), 0, collections.Counter()
    for rid, level, kind, jur, jid, district, _seat in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if kind == "court_of_appeals_retention" and d:
            key = next((k for k, (word, _sec) in APPEALS.items() if word == d), None)
            if key and f"{STATE}-COA-{key}" in appeals_ids:
                said[f"{STATE}-COA-{key}"] += 1
            why = ("the court of appeals district is whole counties and every precinct names its own (appeals), but no layer draws it: the page's rule has no "
                   "place for a court district that is neither the state nor the contest's jurisdiction id")
        elif level == "statewide" or (level == "court" and jid == FIPS and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d))
        elif level == "court" and jid in S_.get("judicial", {}):
            hit = ("judicial", jid)
        elif kind in ("county_council", "county_commissioner") and d:
            if f"{jid}|{d}" in S_.get("com", {}):
                hit = ("com", f"{jid}|{d}")
            elif jid in AT_LARGE and "at-large" in d.lower():
                hit = ("county", jid)
            else:
                why = "no file read here has the lines of this county's commission or council districts; the county's election authority keeps them"
        elif level == "county" or (level == "court" and jid in S_.get("county", {})):
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = ward_why.get(jid, "no file read here has this city's ward lines")
        elif level == "school":
            hit = ("school", jid)
        else:
            why = "no source carries a boundary for this kind of district"
        if hit and hit[1] in S_.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "part_of_a_shape": [], "said_by_the_precinct": {"property": "appeals", "races": dict(sorted(said.items()))}}


# ---------------------------------------------------------------- polling places (one election authority's open list)

POLL_WAITING = {
    "why": "Missouri has no statewide list of polling places that can be read: each county's election authority publishes its own. The election authority "
           "and the Secretary of State's voter lookup say where a voter votes.",
}
POLL_UNCHECKED_WHY = ("      polling places: the St. Louis County Board of Elections' November 3, 2026 list was read (one county of 115) and marked 'unchecked', so a page "
                      "does not show it. The layer does not say which precinct votes at which place; when a person has confirmed how the Board assigns voters to "
                      "places, set POLL_CHECKED in ballot/mo_geo.py.")
POLL_TYPE = {"none": None, "abs": "polling place; also an in-person absentee site before election day", "boe": "the Board of Elections' office"}


def fetch_points(path, refresh, say):
    if G._fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    j = json.loads(net.get(f"{POLL_SERVICE}/query?where={quote('1=1')}&outFields={POLL_FIELDS}&returnGeometry=true&outSR=4326&geometryPrecision=6&f=json", timeout=300, accept="application/json"))
    if "error" in j or j.get("exceededTransferLimit"):
        raise GeoError(f"    {POLL_SERVICE}: {j.get('error') or 'more rows than one request brings'}")
    rows = [[f["attributes"], [f["geometry"]["x"], f["geometry"]["y"]] if f.get("geometry") else None] for f in j.get("features", [])]
    count = json.loads(net.get(f"{POLL_SERVICE}/query?where={quote('1=1')}&returnCountOnly=true&f=json", accept="application/json")).get("count")
    if count != len(rows):
        raise GeoError(f"    {POLL_SERVICE}: {len(rows):,} rows came, but the service counts {count}")
    out = {"service": POLL_SERVICE, "fields": POLL_FIELDS, "fetched": dt.date.today().isoformat(), "rows": rows}
    with gzip.open(path + ".part", "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows fetched")
    return out


def read_poll_rows(doc):
    out, seen = [], set()
    for a, pt in doc["rows"]:
        loc, name, address = clean(a.get("loc")), clean(a.get("name")), clean(a.get("address"))
        zipc = str(a.get("zipcode") or "").strip()
        kind = clean(a.get("abs_type")).lower() or "none"
        if not (re.fullmatch(r"\d{1,4}", loc) and name and address and re.fullmatch(r"6[0-9]{4}", zipc) and kind in POLL_TYPE and loc not in seen):
            raise GeoError(f"    polling places: the row numbered {loc!r} does not fit the layout this reader was checked against")
        seen.add(loc)
        out.append({"loc": loc, "name": title(name), "address": title(address), "zip": zipc, "type": POLL_TYPE[kind], "lonlat": [round(pt[0], 5), round(pt[1], 5)] if pt else None})
    if not 100 <= len(out) <= 400:
        raise GeoError(f"    polling places: {len(out)} rows is not the list this reader was checked against")
    return sorted(out, key=lambda r: int(r["loc"]))


def polling_places(cname, cbox, rows, about, put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    if rows is None:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        return {"file": "polling_places.json", "status": "waiting"}
    b, far, places = cbox[POLL_COUNTY], 0, []
    for r in rows:
        pt = r["lonlat"]
        if pt and not (b[0] - 0.05 <= pt[0] <= b[2] + 0.05 and b[1] - 0.05 <= pt[1] <= b[3] + 0.05):
            pt, far = None, far + 1
        places.append(dict({"name": r["name"], "address": r["address"], "city": "", "zip": r["zip"], "type": r["type"], "hours": None, "lonlat": pt, "county": POLL_COUNTY,
                            "precincts": []}, **({"from": "the St. Louis County Board of Elections' layer (the Board's own point)"} if pt else {})))
    status = "loaded" if POLL_CHECKED else "unchecked"
    doc.update(status=status,
               source=dict({"agency": "St. Louis County Board of Elections", "title": POLL_TITLE, "url": POLL_ITEM, "service": POLL_SERVICE, "fetched": about.get("fetched"),
                            "sha256": about.get("sha256"), "says": "Polling places used in the November 3, 2026 General Election in St. Louis County, Missouri."},
                           **({"current_to": about["current_to"]} if about.get("current_to") else {})),
               places=places, precinct={}, no_place={}, by_county={}, counties_on_the_list=[POLL_COUNTY],
               counties_not_on_the_list=sorted(c for c in cname if c != POLL_COUNTY),
               note="One election authority's list: the St. Louis County Board of Elections' polling places for November 3, 2026, each with the Board's own point. "
                    "The list does not say which precinct votes at which place, and the map's precinct lines are the ones reported to the Census Bureau in 2020, "
                    "so no precinct is tied to a place. Missouri's other 114 counties (the City of St. Louis and Kansas City among them) publish their own lists; "
                    "none is read here. Nothing here is shown until a person has confirmed how the Board assigns voters to these places.")
    put("polling_places.json", doc)
    say(f"      polling places: {len(places)} places of the St. Louis County Board of Elections' November 3, 2026 list ({sum(1 for p in places if p['lonlat'])} with a point, "
        f"{far} points thrown out as outside the county); no precinct is tied to a place; the other {len(cname) - 1} counties are not on any list read here")
    if not POLL_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(places), "with_coordinates": sum(1 for p in places if p["lonlat"]), "rows": len(rows),
            "precincts_listed": 0, "map_precincts_with_a_listed_place": 0, "counties_on_the_list": [POLL_COUNTY], "counties_not_on_the_list": doc["counties_not_on_the_list"]}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Missouri ballot map: 2020 voting districts, 2022 legislative and congressional districts, county, city, town, village, township, school district "
        "and county council lines (the Census Bureau, the State's GIS site, four counties' map services)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    urls = (BLOCK_URL, BAF_URL, VTD_URL, SLDL_URL, SLDU_URL, CD_URL, COUSUB_URL, PLACE_URL, COUNTY_URL)
    bpath, bafpath, vpath, lpath, upath, cdpath, tpath, plpath, cpath = paths = tuple(path(u.rsplit("/", 1)[1]) for u in urls)
    for name in SHARED:                                    # the same national file, if another state's build already fetched it
        if not os.path.exists(path(name)):
            for other in ("oh_local", "sd_local"):
                src = os.path.join(HERE, "states_cache", other, name)
                if os.path.exists(src):
                    shutil.copyfile(src, path(name))
                    break
    net.patient_lookups()
    for url, p in zip(urls, paths):
        net.download(url, p, 3650, say=lambda *_a: None)
    scpath = path("ogi_dese_school_districts_geometry_4326.json.gz")
    scdoc = W.fetch_full(SCHOOL_SERVICE, SCHOOL_FIELDS, scpath, 40, "OBJECTID", refresh, say)
    ccdocs, ccpaths = {}, {}
    for county, (svc, field, _n, _word, src, *_rest) in sorted(COUNCILS.items()):
        ccpaths[county] = path(f"{src.replace('mo-', '')}_geometry_4326.json.gz")
        ccdocs[county] = fetch_small(svc, field, ccpaths[county], refresh, say)
    wdpath = path("st_charles_county_gis_municipal_wards_geometry_4326.json.gz")
    wddoc = fetch_small(WARD_SERVICE, WARD_FIELDS, wdpath, refresh, say)
    edited = {k: W.layer_edited(svc, path(f"mo_geo_about_{k}.json"), refresh)
              for k, svc in [("school", SCHOOL_SERVICE), ("polls", POLL_SERVICE), ("wards", WARD_SERVICE)] + [(f"council_{c}", v[0]) for c, v in COUNCILS.items()]}

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_long = county_names(cpath)
    cname = {c: names.get(("county", c)) or n for c, n in county_long.items()}
    jud_no, jud_doc = circuits(county_long, say)
    app_of, app_doc = appeals(path("rsmo_477.050-070.json"), county_long, refresh, say)

    pollpath, poll_rows, poll_about = path("st_louis_county_boe_polling_places_2026-11-03.json.gz"), None, {}
    try:
        pdoc = fetch_points(pollpath, refresh, say)
        poll_rows = read_poll_rows(pdoc)
        poll_about = dict(edited["polls"], fetched=pdoc.get("fetched"), sha256=G.sha_file(pollpath))
    except (Exception, GeoError) as e:  # noqa: BLE001  the map does not depend on this list
        say(f"      polling places: waiting; the list could not be read ({str(e).strip()})")

    # ---- precincts: the 2020 voting districts, from blocks; every shared line kept once
    table, water, vname = read_tables(bafpath, lpath, upath, cdpath, vpath)
    pre, polys, said = read_units(bpath, table, water, vname, say)
    if sorted({p["county"] for p in pre}) != sorted(cname):
        raise GeoError(f"    the blocks and the Bureau's list of counties do not have the same {N_COUNTIES} counties; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; "
        f"{sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); {lone:,} lines are the state's edge"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's county subdivisions (one fabric) and incorporated places
    cous = sorted(I.read_shapefile(tpath, lambda r: r["STATEFP"] == FIPS), key=lambda x: (x[0]["COUNTYFP"], x[0]["COUSUBFP"]))
    if len({r["COUNTYFP"] for r, _ in cous}) != N_COUNTIES or any(r["LSAD"] not in ("25", "44") for r, _ in cous):
        raise GeoError(f"    {os.path.basename(tpath)}: not {N_COUNTIES} counties of townships; stopping")
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    is_town = [r["LSAD"] == "44" and r["FUNCSTAT"] in ("A", "B") for r, _ in cous]      # a township with a government of its own
    town_rows = [(r, rings) for (r, rings), t in zip(cous, is_town) if t]
    town_key_all = [f"{STATE}-M-{r['COUSUBFP']}" for r, _ in cous]
    cities_ = sorted(I.read_shapefile(plpath, lambda r: r["STATEFP"] == FIPS and r["LSAD"] in PLACE_WORD and r["FUNCSTAT"] == "A"), key=lambda x: x[0]["PLACEFP"])
    parcs, psides, _prings, podd = G.topology([rings for _r, rings in cities_])
    city_key = [f"{STATE}-M-{r['PLACEFP']}" for r, _ in cities_]
    city_set = set(city_key)
    # a township and a city can carry the same five digits (the Bureau numbers them apart): the township then takes its county's code too
    clash = {k for k, t in zip(town_key_all, is_town) if t and k in city_set}
    town_key_all = [f"{STATE}-M-{r['COUNTYFP']}{r['COUSUBFP']}" if k in clash else k for k, (r, _) in zip(town_key_all, cous)]
    town_val = [k if t else None for k, t in zip(town_key_all, is_town)]
    towns = sorted({k for k in town_val if k})
    town_names = collections.defaultdict(set)
    for k, (r, _), t in zip(town_key_all, cous, is_town):
        if t:
            town_names[k].add(r["NAMELSAD"])
    if len(city_set) != len(city_key) or city_set & set(towns) or any(len(n) != 1 for n in town_names.values()):
        raise GeoError("    a city and a township, or two places of different names, share a code; stopping")
    census_name = {k: r["NAMELSAD"] for k, (r, _), t in zip(town_key_all, cous, is_town) if t}
    census_name.update({k: r["NAMELSAD"] for k, (r, _) in zip(city_key, cities_)})
    mkind = {k: "township" for k in towns}
    mkind.update({k: PLACE_WORD[r["LSAD"]] for k, (r, _) in zip(city_key, cities_)})
    mname = {k: names.get(("mcd", k)) or n for k, n in census_name.items()}
    town_county = collections.defaultdict(set)
    for k, c, t in zip(town_key_all, ccounty, is_town):
        if t:
            town_county[k].add(c)
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- school districts, county council districts and wards: each its own fabric
    for a, _r in scdoc["rows"]:
        if not re.fullmatch(r"\d{6}", clean(a["DIST_CODE"])) or not clean(a["DIST_NAME"]):
            raise GeoError(f"    school districts: the row numbered {a.get('DIST_CODE')!r} does not fit the layout this builder was checked against; stopping")
    for code, (_sid, word) in SCHOOL_IDS.items():
        if not any(clean(a["DIST_CODE"]) == code and word in clean(a["DIST_NAME"]) for a, _r in scdoc["rows"]):
            raise GeoError(f"    school districts: district {code} is no longer named {word!r}; stopping")
    sid = lambda a: SCHOOL_IDS[clean(a["DIST_CODE"])][0] if clean(a["DIST_CODE"]) in SCHOOL_IDS else f"{STATE}-S-{clean(a['DIST_CODE'])}"      # noqa: E731
    schkeys, _schpolys, scharcs, schsides, _sr, schodd = I.fabric(N.merge_rows(scdoc["rows"], sid), sid)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    sname = {sid(a): names.get(("school", sid(a))) or clean(a["DIST_NAME"]) for a, _r in scdoc["rows"]}
    sdese = {sid(a): clean(a["DIST_NAME"]) for a, _r in scdoc["rows"]}
    council, cc_odd = {}, {}
    for county, (_svc, field, n, _word, *_rest) in sorted(COUNCILS.items()):
        rows = ccdocs[county]["rows"]
        got = sorted(int(str(a[field]).strip()) for a, _r in rows) if all(str(a[field]).strip().isdigit() for a, _r in rows) else None
        if got != list(range(1, n + 1)):
            raise GeoError(f"    {cname[county]}: the council district layer does not hold districts 1 to {n}, each once; stopping")
        key = lambda a, county=county, field=field: f"{county}|{int(str(a[field]).strip())}"      # noqa: E731
        keys, cpolys, a_, s_, _r, o_ = I.fabric(N.merge_rows(rows, key), key)
        council[county] = (keys, cpolys, a_, s_)
        if o_:
            cc_odd[county] = dict(o_)
    city_county = collections.defaultdict(set)             # which counties a city lies in, from where its limits' middle points fall is not needed: the Bureau's place file has no county, so
    wc_rows = []                                           # a city is tied to WARD_COUNTY when the ward layer names it and the precincts of that county reach it (below)
    say(f"      {len(schkeys)} school districts ({len(scharcs):,} lines), {sum(len(v[0]) for v in council.values())} county council districts in {len(council)} counties, "
        f"{len(cous):,} Census county subdivisions ({len(towns):,} townships with a government of their own), {len(cities_):,} cities, towns and villages"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("school", schodd), ("Census", codd), ("places", podd)) if o)
        + "".join(f"; odd in {cname[c]}'s council districts: {o}" for c, o in cc_odd.items()))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    units_stamp = (bafpath, lpath, upath, cdpath)          # the blocks' own file is 340 MB and never changes: its name stands for it
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(*units_stamp, scpath), refresh, say)
    o_mcd = place_overlay_cached(pre_rings, I.rings_xy([r for _a, r in cities_]), I.rings_xy([r for _a, r in town_rows]), stamp(*units_stamp, tpath, plpath), refresh, say)
    place_keys = city_key + [k for k, t in zip(town_key_all, is_town) if t]

    several = no_place = 0
    for p, got in zip(pre, o_mcd):
        rows = sorted(((place_keys[d], s, t) for d, s, t in got), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t and (k in city_set or p["county"] in town_county.get(k, ()))]
        p["mcd"] = own[0][0] if own else None
        p["mcd_all"] = [k for k, _s in own]
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in own] if len(own) > 1 else None
        several += len(own) > 1
        no_place += not own
        for k, _s in own:
            if k in city_set:
                city_county[k].add(p["county"])
        p["jud"] = f"{STATE}-JC{jud_no[p['county']]}"
        p["appeals"] = f"{STATE}-COA-{app_of[p['county']]}"
        p["com"] = None
        p["ward"] = None
    for county, (keys, cpolys, _a, _s) in sorted(council.items()):
        idx = [i for i, p in enumerate(pre) if p["county"] == county]
        got = overlay_cached(f"council-{county}", [pre_rings[i] for i in idx], I.rings_xy(cpolys), stamp(*units_stamp, ccpaths[county]), refresh, say)
        for i, g in zip(idx, got):
            pre[i]["com"] = S.most(pre[i], g, keys, "com")
        none = [pre[i]["id"] for i in idx if not pre[i]["com"]]
        if len(none) > 2:
            raise GeoError(f"    {cname[county]}: {len(none)} precincts touch no council district (e.g. {none[0]}); stopping")
    say(f"      cities, towns, villages and townships by precinct: {several:,} of {len(pre):,} precincts reach more than one place, {no_place:,} lie in none "
        f"(the open country of a county without township government); county council districts: "
        f"{sum(1 for p in pre if (p.get('split') or {}).get('com'))} of {sum(1 for p in pre if p['com']):,} precincts have {SPLIT_SHARE:.0%} or more of their area in a second district")

    # ---- wards: the cities of St. Charles County whose council races the ballot database carries
    wcities, ward_why = ward_cities(info, census_name, city_county)
    ward_fab, wards_drawn = None, {}
    if wcities:
        for a, rings in wddoc["rows"]:
            hit = wcities.get(fold(clean(a["CITY"])))
            if hit and clean(a["NAME"]).isdigit():
                jid, label, style = hit
                n = int(clean(a["NAME"]))
                word = label.get(n) or (f"Ward {NUMBER_WORDS[n]}" if style == "word" and n < len(NUMBER_WORDS) else f"Ward {n}")
                wc_rows.append(({"key": f"{jid}|{word}"}, rings))
        for name_, (jid, label, _style) in wcities.items():
            have = {a["key"].split("|")[1] for a, _r in wc_rows if a["key"].startswith(jid + "|")}
            if not set(label.values()) <= have:
                ward_why[jid] = "the county's ward layer does not hold the ward this city's council race names"
                wc_rows = [(a, r) for a, r in wc_rows if not a["key"].startswith(jid + "|")]
            else:
                wards_drawn[jid] = sorted(have, key=lambda w: (NUMBER_WORDS.index(w.split()[1]) if w.split()[1] in NUMBER_WORDS else 99, w))
    if wc_rows:
        wkey = lambda a: a["key"]      # noqa: E731
        wkeys, wpolys, warcs, wsides, _wr, wodd = I.fabric(N.merge_rows(wc_rows, wkey), wkey)
        ward_fab = (wkeys, warcs, wsides)
        idx = [i for i, p in enumerate(pre) if p["county"] == WARD_COUNTY and any(k in wards_drawn for k in p["mcd_all"])]
        got = overlay_cached("wards", [pre_rings[i] for i in idx], I.rings_xy(wpolys), stamp(*units_stamp, wdpath), refresh, say)
        for i, g in zip(idx, got):
            share = collections.Counter()
            for d, s, _t in g:
                share[wkeys[d]] += s
            top = share.most_common(2)
            if top and top[0][1] >= 0.5:
                pre[i]["ward"] = top[0][0]
                if len(top) > 1 and top[1][1] >= SPLIT_SHARE:
                    pre[i].setdefault("split", {})["ward"] = {k: round(100 * s, 1) for k, s in top}
        say(f"      wards: {len(wkeys)} wards of {', '.join(mname[j] for j in sorted(wards_drawn))} from the county's layer; {sum(1 for p in pre if p['ward'])} precincts lie mostly in one"
            + (f"; odd: {dict(wodd)}" if wodd else ""))

    split = none = edges = 0
    for p, got in zip(pre, o_sch):
        rows = [(schkeys[d], share, thick) for d, share, thick in got]
        keep = sorted(((k, s) for k, s, thick in rows if thick), key=lambda x: (-x[1], x[0]))
        if not keep and rows:
            best = max(((k, s) for k, s, _t in rows), key=lambda x: x[1])
            if best[1] >= 0.5:
                keep = [best]
        outside = max(0.0, 1.0 - sum(s for _k, s, _t in rows))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside >= 0.03) else None
        p["school_out"] = round(100 * outside, 1) if outside >= 0.03 else None
        p["school_edge"] = sorted({k for k, _s, _t in rows} - set(p["school"]))
        split += len(keep) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(keep) < 2
    say(f"      school districts by precinct: {split:,} precincts are split between two or more districts, {none} lie in none, "
        f"{edges:,} others only brush a neighbouring district along a line")

    # ---- the area checks: each county's precincts against the area the Bureau gives their blocks, and the county's blocks
    #      against the Bureau's 2025 county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731  Esri's winding: outer rings clockwise
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in clist}
    if sorted(area_p) != clist or sorted(said["in"]) != clist:
        raise GeoError(f"    area check: the blocks and the 2025 county subdivisions do not have the same {N_COUNTIES} counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / said["in"][c] - 1))
    worst_pct = 100 * (area_p[worst] / said["in"][worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(said["in"].values()) - 1)
    off = [c for c in clist if abs(area_p[c] / said["in"][c] - 1) > 0.005]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] + f' ({100 * (area_p[c] / said['in'][c] - 1):+.2f}%)' for c in off[:8])} do not have the area the Census Bureau gives their blocks; stopping")
    off = [c for c in clist if abs(said["all"][c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the 2020 blocks of {', '.join(cname[c] + f' ({100 * (said['all'][c] / area_c[c] - 1):+.1f}%)' for c in off[:8])} do not cover the county the Census Bureau draws in 2025; stopping")
    say(f"      area check: the precincts have {100 + state_pct:.3f}% of the area the Census Bureau gives their blocks (the county furthest off is {cname[worst]}, {worst_pct:+.2f}%); "
        f"every county's blocks are within {AREA_SLACK:.0%} of the Bureau's 2025 county")

    vals = {"county": [p["county"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": [p["cd"] for p in pre],
            "judicial": [p["jud"] for p in pre]}
    mask = []
    for r, l in sides:
        m = 0
        for bit, kind in enumerate(ARC_KINDS):
            if r < 0 or l < 0 or vals[kind][r] != vals[kind][l]:
                m |= 1 << bit
        mask.append(m)

    # ---- write (into a folder beside the real one, moved into place only when everything is written)
    final, out = out, out.rstrip("\\/") + ".part"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    files, today = {}, dt.date.today().isoformat()

    def put(rel, doc):
        size, sha = G.write_json(os.path.join(out, *rel.split("/")), doc)
        files[rel] = {"bytes": size, "sha256": sha}
        return size

    layers, shape_ids = [], {}

    def layer(kind, geoms, qlines, tol, props, source, zoom=None):
        gl = []
        for v, polys_ in sorted(geoms, key=lambda x: G.natkey(x[0])):
            pr = props(v)
            gl.append({"id": pr.pop("id"), "properties": pr, "polys": polys_, "label": True})
        doc, _dropped, _pts = G.topo_doc({kind: gl}, qlines)
        doc["kind"], doc["tolerance_m"] = kind, tol
        size = put(f"layers/{kind}.json", doc)
        empty = [g["id"] for g in doc["objects"][kind]["geometries"] if g["type"] is None]
        if empty:
            say(f"      layer {kind}: {len(empty)} shapes with no outline ({', '.join(empty[:5])})")
        shape_ids[kind] = {g["id"]: g["properties"] for g in doc["objects"][kind]["geometries"]}
        layers.append({"kind": kind, "file": f"layers/{kind}.json", "bytes": size, "shapes": len(gl), "tolerance_m": tol,
                       "good_to_zoom": zoom or G.zoom_for(tol), "lines_from": source})

    def own(v, tol):
        g, q, _l, _r = G.build_layer(arcs, sides, [v], tol)
        return [x for x in g if x[0] is not None], q

    BLOCKS, VTD, BEF, CDB, COUSUB, PLACES, SCH, MANUAL, LAW, POLLS = (
        "mo-census-tiger-2020-blocks", "mo-census-2020-voting-districts", "mo-census-2024-legislative-bef", "mo-census-cd119-bef",
        "mo-census-tiger-2025-cousub", "mo-census-tiger-2025-place", "mo-ogi-dese-school-districts", "mo-sos-official-manual-2025-2026-ch5",
        "mo-rsmo-477.050-070", "mo-st-louis-county-boe-polling-places-2026-11-03")
    nth = lambda n: G.ordinal(n)      # noqa: E731
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[f"{STATE}-JC{jud_no[c]}"].append(cname[c])
    cc_word = {c: v[3] for c, v in COUNCILS.items()}
    layer("state", *own([STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, BLOCKS)
    layer("county", *own(vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, BLOCKS)
    layer("cd", *own(vals["cd"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, BLOCKS + ", put together by " + CDB)
    layer("senate", *own(vals["senate"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("house", *own(vals["house"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("judicial", *own(vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{nth(v[len(STATE) + 3:])} Judicial Circuit", "j": v, "d": f"Circuit {v[len(STATE) + 3:]}", "counties": jud_counties[v]},
          BLOCKS + "; which counties, from " + MANUAL)
    layer("mcd", *W.merged_layer([(parcs, psides, city_key), (carcs, csides, town_val)], TOL_MCD), TOL_MCD,
          lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, PLACES + " and " + COUSUB, zoom=MCD_ZOOM)
    if ward_fab:
        wg, wq, _l, _r = G.build_layer(ward_fab[1], ward_fab[2], [ward_fab[0]], G.TOL_LOCAL)
        layer("ward", wg, wq, G.TOL_LOCAL, lambda v: {"id": v, "name": f"{mname[v.split('|')[0]]}, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, WARD_SRC)
    cg, cq = W.merged_layer([(a_, s_, keys) for _c, (keys, _p, a_, s_) in sorted(council.items())], G.TOL_LOCAL)
    layer("com", cg, cq, G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]} {cc_word[v.split('|')[0]]} {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
          ", ".join(COUNCILS[c][4] for c in sorted(COUNCILS)))
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None}      # noqa: E731
    sg, sq, _l, _r = G.build_layer(scharcs, schsides, [schkeys], G.TOL_LOCAL)
    layer("school", sg, sq, G.TOL_LOCAL, sprops, SCH)
    dgeoms, dq, _l, _r = G.build_layer(scharcs, schsides, [schkeys], G.TOL_SCHOOL)
    school_bytes = 0
    for v, polys_ in dgeoms:
        pr = sprops(v)
        pr.pop("id")
        doc, _d, _p = G.topo_doc({"school": [{"id": v, "properties": pr, "polys": polys_, "label": True}]}, dq)
        doc["kind"], doc["tolerance_m"] = "school", G.TOL_SCHOOL
        school_bytes += put(f"school/{v}.json", doc)

    # county files
    by_county = collections.defaultdict(list)
    for i, p in enumerate(pre):
        by_county[p["county"]].append(i)
    counties, boxes, cbox, dropped_rings = [], {}, {}, 0
    for county, idxs in sorted(by_county.items()):
        local = {i: n for n, i in enumerate(idxs)}
        geoms, used_names = [], {"mcd": {}, "school": {}, "com": {}, "ward": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "mcd": p["mcd"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "judicial": p["jud"], "appeals": p["appeals"], "school": p["school"], "as_of": 2020}
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["com"]:
                pr["com"] = p["com"]
                for k in [p["com"]] + list((p.get("split") or {}).get("com", {})):
                    used_names["com"][k] = shape_ids["com"][k]["name"]
            if p["ward"]:
                pr["ward"] = [p["ward"]]
                for k in [p["ward"]] + list((p.get("split") or {}).get("ward", {})):
                    used_names["ward"][k] = shape_ids["ward"][k]["name"]
            for k in ("school_pct", "school_out", "school_edge", "split"):
                if p.get(k):
                    pr[k] = p[k]
            for k in p["school"] + p["school_edge"]:
                used_names["school"][k] = sname[k]
            geoms.append({"id": p["id"], "properties": pr, "polys": G.group_polys([(refs, G.ring_xy(refs, fine)) for refs in rings_of[i]]), "label": True})

        def more(used, county=county, local=local, used_names=used_names):
            am, asd = [], []
            for a in used:
                am.append(mask[a])
                for side in sides[a]:
                    asd.append(local[side] if side in local else (-1 if side >= 0 else -2))
            return {"county": county, "fips": county, "name": cname[county], "arcKinds": ARC_KINDS, "arcMask": am, "arcSides": asd,
                    "names": {k: dict(sorted(v.items())) for k, v in used_names.items() if v}}

        doc, dropped, pts = G.topo_doc({"precincts": geoms}, qfine, more)
        dropped_rings += dropped
        bx = []
        for g in geoms:
            polys_pts = pts[("precincts", g["id"])]
            if not polys_pts:
                raise GeoError(f"    precinct {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // G.BOX_STEP, min(ys) // G.BOX_STEP, -(-max(xs) // G.BOX_STEP), -(-max(ys) // G.BOX_STEP)]
        boxes[county] = bx
        rel = f"precincts/{county}.json"
        size = put(rel, doc)
        cbox[county] = doc["bbox"]
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(county_long, cbox, poll_rows, poll_about, put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    plans = {}
    for county, why in AT_LARGE.items():
        ds = sorted({str(d) for _rid, _lv, kind, _jur, jid, d, _seat in info["races"] if kind == "county_council" and str(jid) == county and d and "at-large" in str(d).lower()})
        plans[county] = {"plan": 2, "districts": ds, "commissioners_elected": why + "; the six district legislators are elected by their districts (the com layer)",
                         "source": "Jackson County's own map service draws both kinds of district; the at-large districts are not shapes here"}

    check = check_ids(info, shape_ids, ward_why, {p["appeals"] for p in pre})
    check["wards_drawn"] = wards_drawn
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    cb = "U.S. Census Bureau"
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            {"id": BLOCKS, "agency": cb, "title": "TIGER/Line Shapefiles 2020, tabulation blocks, Missouri (tl_2020_29_tabblock20.zip)",
             "about": "The 2020 census blocks: every line of the map's precincts, counties, legislative and congressional districts is a block's.",
             "url": BLOCK_URL, "fetched": mtime(bpath), "bytes": os.path.getsize(bpath), "rows": len(table) + len(water)},
            {"id": VTD, "agency": cb, "title": "2020 Census Block Assignment File, voting districts (BlockAssign_ST29_MO.zip), and the voting districts' names "
                                                "(tl_2020_29_vtd20.zip)",
             "about": "The precincts Missouri's election authorities reported for the 2020 census: which voting district each block is in.",
             "url": BAF_URL, "names_url": VTD_URL, "fetched": mtime(bafpath), "sha256": G.sha_file(bafpath), "names_sha256": G.sha_file(vpath),
             "rows": len({(p["county"], p["vtd"]) for p in pre})},
            {"id": BEF, "agency": cb, "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip)",
             "about": "Which Missouri House and Senate district each block is in, under the plans drawn in 2022.",
             "url": SLDL_URL, "upper_url": SLDU_URL, "fetched": mtime(lpath), "sha256": G.sha_file(lpath), "upper_sha256": G.sha_file(upath), "rows": len(table)},
            {"id": CDB, "agency": cb, "title": "119th Congressional District Block Equivalency File (cd119.zip)",
             "about": "Which congressional district each block is in. " + CD_NOTE,
             "url": CD_URL, "fetched": mtime(cdpath), "sha256": G.sha_file(cdpath), "rows": len(table) + len(water)},
            {"id": COUSUB, "agency": cb, "title": "TIGER/Line Shapefiles 2025, county subdivisions, Missouri (tl_2025_29_cousub.zip)",
             "about": "Townships as the Bureau had them on January 1, 2025 (only those it marks as functioning governments are places here); also the county "
                      "areas the precincts are checked against.",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": PLACES, "agency": cb, "title": "TIGER/Line Shapefiles 2025, places, Missouri (tl_2025_29_place.zip)",
             "about": "City, town and village limits (incorporated, active places only), as the Bureau had them on January 1, 2025.", "url": PLACE_URL,
             "fetched": mtime(plpath), "sha256": G.sha_file(plpath), "rows": len(cities_)},
            dict({"id": SCH, "agency": "State of Missouri, Office of Geospatial Information, with the Department of Elementary and Secondary Education",
                  "title": "Missouri Public Schools, layer Public School Districts", "about": "Only the district's name and county-district code are read. District "
                  "boundaries are updated annually, if needed.", "url": SCHOOL_ITEM, "service": SCHOOL_SERVICE, "fetched": scdoc.get("fetched"),
                  "sha256": G.sha_file(scpath), "rows": len(schkeys)}, **edited["school"]),
        ] + [dict({"id": v[4], "agency": v[5], "title": v[6], "about": v[7] + " Only the district number is read.", "url": v[0], "service": v[0],
                   "fetched": ccdocs[c].get("fetched"), "sha256": G.sha_file(ccpaths[c]), "rows": v[2]}, **edited[f"council_{c}"]) for c, v in sorted(COUNCILS.items())]
        + [dict({"id": WARD_SRC, "agency": "St. Charles County, Missouri (GIS)", "title": "Voting Information, layer Municipal Wards",
                 "about": "Only the city's name and the ward's number are read; a ward is drawn only for a city whose council race is in the ballot database.",
                 "url": WARD_SERVICE, "service": WARD_SERVICE, "fetched": wddoc.get("fetched"), "sha256": G.sha_file(wdpath), "rows": len(wc_rows)}, **edited["wards"]),
           {"id": MANUAL, "agency": "Missouri Secretary of State", "title": "Official Manual, State of Missouri, 2025-2026, chapter 5: Judicial Branch",
            "about": "Which counties make up each of the 46 judicial circuits (circuit numbers and county names only are kept).",
            "url": jud_doc.get("url"), "fetched": jud_doc.get("fetched"), "sha256": jud_doc.get("sha256"), "rows": N_CIRCUITS},
           {"id": LAW, "agency": "Missouri Revisor of Statutes", "title": "RSMo 477.050, 477.060, 477.070: territorial jurisdiction of the court of appeals districts",
            "url": STATUTE + "477.050", "southern_url": STATUTE + "477.060", "western_url": STATUTE + "477.070", "fetched": app_doc["fetched"],
            "sha256": app_doc["sections"]["E"]["sha256"], "rows": 3}]
        + ([dict({"id": POLLS, "agency": "St. Louis County Board of Elections", "title": POLL_TITLE, "url": POLL_ITEM,
                  "about": "One county's list, read for polling_places.json (unchecked): place number, name, street address, ZIP code and whether it is an absentee site.",
                  "service": POLL_SERVICE, "fetched": poll_about.get("fetched"), "sha256": poll_about.get("sha256"), "rows": len(poll_rows)},
                 **({"current_to": poll_about["current_to"]} if poll_about.get("current_to") else {}))] if poll_rows else []),
        "notes": {
            "lines": f"Every precinct, county, legislative and congressional line is a 2020 census block's, generalised by at most {G.TOL_PRECINCT} metres and set on a "
                     "grid of 0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "Missouri publishes no statewide map of its precincts as they stand in 2026. Each shape here is a voting district as the county's election "
                         "authority reported it for the 2020 census, cut wherever a 2022 legislative or congressional district line crosses it, and named as "
                         "the Bureau's file names it. An election authority may have redrawn or renamed its precincts since: it is the authority. What a ballot "
                         "depends on (county, legislative and congressional district, judicial circuit, court of appeals district, city, town, village or "
                         "township, school district, county council district) is taken from current files and does not depend on the precinct.",
            "places": "A precinct can reach more than one place, so the precinct does not say which city, town or village a voter lives in: the mcd layer answers "
                      "that for a point, cities, towns and villages first. A township is a place here only where the Census Bureau marks it as a functioning "
                      "government (the counties with township organization); its shape is the whole township, the cities in it included. Elsewhere open country "
                      "is in no place, and a precinct there has no mcd. mcd is the place holding most of the precinct; mcd_all lists every place it reaches. "
                      "Limits are the Census Bureau's of January 1, 2025. Kansas City reaches into four counties and is one shape.",
            "commissioners": "Most counties have a presiding commissioner elected by the whole county and two associate commissioners elected by halves of the county, "
                             "whose line no statewide file has. Four charter counties elect a council or legislature by district, drawn from the county's own map "
                             "service (the com layer; a precinct's com is the district holding most of it, analysis, and the layer answers for a point): Jackson "
                             "(six district legislators; three more are elected by the whole county), Jefferson, St. Charles and St. Louis counties.",
            "legislative": "Which House and Senate district a block is in is the Census Bureau's 2024 equivalency file's word (the plans drawn in 2022), "
                           "so a precinct's district is exact.",
            "congressional": CD_NOTE + " A precinct's district is exact for those lines.",
            "school": "School district lines are the State's file. Which districts a precinct lies in is analysis, not an official list: a district counts "
                      f"when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share of the "
                      "precinct's area (land and water, not voters). School boards are elected in April; one board seat is on the November 2026 ballot.",
            "judicial": "The 46 judicial circuits are whole counties (the 22nd is the City of St. Louis). An associate circuit judge is elected by one county. The "
                        "three court of appeals districts are whole counties too (RSMo 477.050 to 477.070): a precinct names its own (appeals), and no layer draws them.",
            "wards": "No statewide file has city ward lines. A ward is drawn only for a city whose council race is in the ballot database and whose county's own "
                     "map service has the lines (St. Charles County's Municipal Wards layer).",
            "authority": "For which precinct an address votes in, and where, the county's election authority and the Missouri Secretary of State's voter lookup are the authority.",
            "precinct_ids": "A precinct's id is its county's five digits, a full stop and the Census Bureau's 2020 voting district code (29051.000012); a voting "
                            "district cut by a district line has a second full stop and the piece's number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file; -2: outside Missouri); names gives the names of the places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the 2020 voting district's, as the Census Bureau's file gives it (and the piece's number where a district line cuts it)",
                                    "county": "county id", "precinct": "the county's five digits and the Bureau's 2020 voting district code",
                                    "as_of": "the year of the precinct's lines (2020)",
                                    "mcd": "city, town, village or township holding most of the precinct (none in open country without township government)",
                                    "mcd_all": "list, when the precinct reaches more than one: every city, town, village and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                                    "house": "Missouri House district", "senate": "Missouri Senate district", "cd": "congressional district (the 2022 lines)",
                                    "judicial": "judicial circuit",
                                    "appeals": "court of appeals district (MO-COA-E Eastern, MO-COA-S Southern, MO-COA-W Western)",
                                    "com": "Jackson, Jefferson, St. Charles and St. Louis counties only: the county council district holding most of the precinct",
                                    "ward": "list, in a city whose wards are drawn: the council ward holding most of the precinct",
                                    "split": "only where a second council district or ward holds 3 percent or more of the precinct: each one's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "MO (j is 29)", "county": "the county's five-digit code (29095; the City of St. Louis is 29510)",
                    "mcd": "MO-M- and the Census code: a city's, town's or village's place code (MO-M-64082), a township's county subdivision code; properties.t says city, town, village or township",
                    "ward": "<city>|<ward as the council race words it> (MO-M-64082|Ward Four)",
                    "com": "<county>|<council or legislature district> (29095|1): Jackson, Jefferson, St. Charles and St. Louis counties",
                    "house": "the district (60)", "senate": "the district (6)",
                    "cd": "the district (3); properties.race is the race for Congress",
                    "judicial": "MO-JC and the circuit's number (MO-JC16); d is the circuit as its races word it (Circuit 16)",
                    "school": "MO-S- and the Department's six-digit county-district code (MO-S-048078); the St. Louis City district carries the ballot database's own id"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL,
                   "department_names": {k: v for k, v in sorted(sdese.items()) if v != sname[k]}},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "whole_precincts": len({p["precinct"] for p in pre}), "counties": len(counties), "census_blocks": len(table) + len(water),
                   "census_blocks_in_no_voting_district": len(water),
                   "split_between_school_districts": split, "in_more_than_one_place": several, "in_no_place": no_place,
                   "rings_too_small_for_the_grid": dropped_rings, "lines_with_a_precinct_on_one_side": lone,
                   "area_against_the_census_blocks_own_area_percent": {"state": round(state_pct, 3), "furthest_county": worst, "its_difference": round(worst_pct, 2)}},
        "check": check,
    }
    put("index.json", index)
    manifest = {"v": G.VERSION, "built": today, "files": dict(sorted(files.items()))}
    G.write_json(os.path.join(out, "manifest.json"), manifest)
    total = sum(f["bytes"] for f in files.values()) + os.path.getsize(os.path.join(out, "manifest.json"))
    os.makedirs(final, exist_ok=True)
    G.clear_out(final)
    for rel in list(files) + ["manifest.json"]:
        dst = os.path.join(final, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(os.path.join(out, *rel.split("/")), dst)
    shutil.rmtree(out)
    say(f"      {len(counties)} county files ({sum(c['bytes'] for c in counties) / 1e6:.1f} MB), {len(layers)} layers "
        f"({sum(l['bytes'] for l in layers) / 1e6:.1f} MB), {len(schkeys)} school district files ({school_bytes / 1e6:.1f} MB), "
        f"index {files['index.json']['bytes'] / 1e3:.0f} KB; {total / 1e6:.1f} MB in all, in {final}")
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Missouri races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Missouri ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the place at the point (from the mcd layer; None in
    # open country), and a word its school district's name must carry. County, place, legislative districts and school
    # district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02: geocoding.geo.census.gov,
    # "geographies/coordinates", its 2026 legislative districts), an answer that owes nothing to the files tested here.
    # The congressional district is the Bureau's 119th Congress equivalency file's for the census block the geocoder
    # named (the geocoder itself answers with the paused 2025 map). The circuit is the county's (the Official Manual).
    ("the Capitol, Jefferson City", -92.173, 38.5791, {"county": "29051", "senate": "6", "house": "60", "cd": "3", "judicial": "MO-JC19", "appeals": "MO-COA-W"}, "MO-M-37000", "Jefferson City"),
    ("City Hall, St. Louis", -90.1994, 38.6273, {"county": "29510", "senate": "5", "house": "78", "cd": "1", "judicial": "MO-JC22", "appeals": "MO-COA-E"}, "MO-M-65000", "St. Louis City"),
    ("City Hall, Kansas City", -94.5783, 39.1003, {"county": "29095", "senate": "7", "house": "23", "cd": "5", "judicial": "MO-JC16", "appeals": "MO-COA-W"}, "MO-M-38000", "Kansas City 33"),
    ("Park Central Square, Springfield", -93.2923, 37.209, {"county": "29077", "senate": "30", "house": "132", "cd": "7", "judicial": "MO-JC31", "appeals": "MO-COA-S"}, "MO-M-70000", "Springfield"),
    ("the courthouse, Columbia", -92.329, 38.953, {"county": "29019", "senate": "19", "house": "45", "cd": "4", "judicial": "MO-JC13", "appeals": "MO-COA-W"}, "MO-M-15670", "Columbia"),
    ("Independence Square", -94.4155, 39.0925, {"county": "29095", "senate": "11", "house": "21", "cd": "5", "judicial": "MO-JC16", "appeals": "MO-COA-W"}, "MO-M-35000", "Independence"),
    ("City Hall, St. Charles", -90.4812, 38.783, {"county": "29183", "senate": "23", "house": "106", "cd": "3", "judicial": "MO-JC11", "appeals": "MO-COA-E"}, "MO-M-64082", "St. Charles"),
    ("Clayton", -90.337, 38.649, {"county": "29189", "senate": "4", "house": "99", "cd": "1", "judicial": "MO-JC21", "appeals": "MO-COA-E"}, "MO-M-14572", "Clayton"),
    ("Hillsboro", -90.5629, 38.2323, {"county": "29099", "senate": "3", "house": "111", "cd": "3", "judicial": "MO-JC23", "appeals": "MO-COA-E"}, "MO-M-32248", "Hillsboro"),
    ("Joplin", -94.5133, 37.0842, {"county": "29097", "senate": "32", "house": "161", "cd": "7", "judicial": "MO-JC29", "appeals": "MO-COA-S"}, "MO-M-37592", "Joplin"),
    ("Cape Girardeau", -89.527, 37.3059, {"county": "29031", "senate": "27", "house": "147", "cd": "8", "judicial": "MO-JC32", "appeals": "MO-COA-E"}, "MO-M-11242", "Cape Girardeau"),
    ("St. Joseph", -94.8467, 39.7675, {"county": "29021", "senate": "34", "house": "10", "cd": "6", "judicial": "MO-JC5", "appeals": "MO-COA-W"}, "MO-M-64550", "St. Joseph"),
    ("Kirksville", -92.5832, 40.1948, {"county": "29001", "senate": "18", "house": "3", "cd": "6", "judicial": "MO-JC2", "appeals": "MO-COA-W"}, "MO-M-39026", "Kirksville"),
    ("West Plains", -91.8524, 36.7281, {"county": "29091", "senate": "33", "house": "154", "cd": "8", "judicial": "MO-JC37", "appeals": "MO-COA-S"}, "MO-M-78928", "West Plains"),
    ("Lee's Summit", -94.3822, 38.9108, {"county": "29095", "senate": "8", "house": "34", "cd": "5", "judicial": "MO-JC16", "appeals": "MO-COA-W"}, "MO-M-41348", "Lee's Summit"),
    ("O'Fallon", -90.6998, 38.8106, {"county": "29183", "senate": "2", "house": "103", "cd": "3", "judicial": "MO-JC11", "appeals": "MO-COA-E"}, "MO-M-54074", "Zumwalt"),
    ("a field in Texas County", -91.95, 37.3, {"county": "29215", "senate": "33", "house": "143", "cd": "8", "judicial": "MO-JC25", "appeals": "MO-COA-S"}, "MO-M-57890", "Houston"),
    ("Kansas City north of the river", -94.5727, 39.246, {"county": "29047", "senate": "17", "house": "16", "cd": "5", "judicial": "MO-JC7", "appeals": "MO-COA-W"}, "MO-M-38000", "North Kansas City"),
    ("Arnold", -90.3776, 38.4328, {"county": "29099", "senate": "22", "house": "113", "cd": "8", "judicial": "MO-JC23", "appeals": "MO-COA-E"}, "MO-M-01972", "Fox"),
    ("Florissant", -90.3226, 38.7892, {"county": "29189", "senate": "13", "house": "75", "cd": "1", "judicial": "MO-JC21", "appeals": "MO-COA-E"}, "MO-M-24778", "Ferguson"),
]
LINE_POINTS = [("the Jackson-Cass county line south of Kansas City", -94.45, 38.84, ("29095", "29037")),
               ("the St. Charles-Warren county line", -90.96, 38.80, ("29183", "29219"))]
LAYER_SLACK = 0.005


def selftest(out=OUT, say=print):
    """Reads only the built files. Returns True when everything holds."""
    files = G.Files(out)
    index, fails = files.index, []
    locate = W.locate

    def check(ok, what):
        if not ok:
            fails.append(what)
            say(f"      FAIL: {what}")
        return ok

    def own(geom, kind):
        v = geom["properties"].get(kind)
        return v[0] if isinstance(v, list) else v

    # 1. the files are all there and say what the index says; lines know their two sides and their outline marks
    total = bad_side = bad_mask = lines_seen = edge_lines = 0
    ids = set()
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        geoms = doc["objects"]["precincts"]["geometries"]
        total += len(geoms)
        ids |= {g["id"] for g in geoms}
        ok = (len(geoms) == c["precincts"] == len(index["boxes"][c["id"]]) // 4 and len(doc["arcMask"]) == len(doc["arcs"])
              and len(doc["arcSides"]) == 2 * len(doc["arcs"]) and all(g["type"] in ("Polygon", "MultiPolygon") for g in geoms)
              and doc["arcKinds"] == index["arc_kinds"])
        if not check(ok, f"{c['file']} does not fit the index"):
            continue
        sides_, masks = doc["arcSides"], doc["arcMask"]
        for gi, g in enumerate(geoms):
            for poly in (g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]):
                for refs in poly:
                    for r in refs:
                        bad_side += sides_[2 * r + 1 if r >= 0 else 2 * ~r] != gi
        for a in range(len(lines)):
            r, l = sides_[2 * a], sides_[2 * a + 1]
            lines_seen += 1
            edge_lines += min(r, l) < 0
            for bit, kind in enumerate(doc["arcKinds"]):
                if r >= 0 and l >= 0:
                    want = own(geoms[r], kind) != own(geoms[l], kind)
                elif min(r, l) == -2:
                    want = own(geoms[max(r, l)], kind) is not None
                else:
                    continue
                bad_mask += bool(masks[a] & (1 << bit)) != want
    check(total == index["counts"]["precincts"] == len(ids), "the county files do not hold as many precincts as the index says, each with its own id")
    shapes_seen, layer_ids = 0, {}
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        layer_ids[L["kind"]] = {g["id"] for g in gs}
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == N_COUNTIES, f"there are not {N_COUNTIES} county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == N_SENATE and len(layer_ids.get("house", ())) == N_HOUSE and len(layer_ids.get("judicial", ())) == N_CIRCUITS
          and layer_ids.get("cd") == {str(n) for n in range(1, N_CD + 1)} and len(layer_ids.get("county", ())) == N_COUNTIES
          and layer_ids.get("com") == {f"{c}|{n}" for c, v in COUNCILS.items() for n in range(1, v[2] + 1)},
          f"there are not {N_SENATE} Senate districts, {N_HOUSE} House districts, {N_CIRCUITS} circuits, {N_COUNTIES} counties, {N_CD} congressional districts and "
          f"{sum(v[2] for v in COUNCILS.values())} county council districts")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place, council, ward = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial"}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        for i, g in enumerate(doc["objects"]["precincts"]["geometries"]):
            polys = G.geom_polys(lines, g)
            px, py = G.label_point(polys[0])
            lon, lat = px * G.SCALE + G.ORIGIN[0], py * G.SCALE + G.ORIGIN[1]
            found, _near = locate(files, lon, lat)
            tested += 1
            if not found or found["geometry"]["id"] != g["id"]:
                wrong += 1
            pr = g["properties"]
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school"), ("com", "com"), ("ward", "ward")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            if i % 2 == 0:
                sid = G.school_at(files, g, lon, lat)
                school["in a district the precinct lies in" if sid in pr["school"] else "in a district the precinct only brushes" if sid else
                       "in none, in a precinct partly outside every district" if pr.get("school_out") else "in none"] += 1
                shape, _edge = G.shape_at(files, "mcd", lon, lat)
                place["the precinct's own place" if shape and shape["id"] == pr["mcd"] else "another place the precinct names" if shape and shape["id"] in pr.get("mcd_all", [])
                      else "a place the precinct does not name" if shape else "open country, as the precinct says" if not pr["mcd"] else
                      "open country, in a precinct that reaches a place"] += 1
            if pr.get("com"):
                shape, _edge = G.shape_at(files, "com", lon, lat)
                council["the precinct's own district" if shape and shape["id"] == pr["com"] else
                        "another district the precinct is split with" if shape and shape["id"] in (pr.get("split") or {}).get("com", {}) else
                        "a district the precinct does not name" if shape else "no district"] += 1
            if pr.get("ward"):
                shape, _edge = G.shape_at(files, "ward", lon, lat)
                ward["the precinct's own ward" if shape and shape["id"] == pr["ward"][0] else
                     "another ward the precinct is split with" if shape and shape["id"] in (pr.get("split") or {}).get("ward", {}) else
                     "a ward the precinct does not name" if shape else "no ward"] += 1
            for prop, kind in layer_for.items():
                if i % 4 and kind not in ("house", "cd"):
                    continue
                if i % 2 and kind in ("house", "cd"):
                    continue
                shape, edge = G.shape_at(files, kind, lon, lat)
                if shape is not None and edge <= tol_of[kind] + 10:
                    skipped += 1
                    continue
                asked[kind] += 1
                if shape is not None and shape["id"] == pr.get(prop):
                    agree += 1
                else:
                    disagree[kind].append((g["id"], shape and shape["id"], pr.get(prop)))
    half = sum(school.values())
    check(wrong <= 5, f"{wrong} of {tested} precincts are not found again from a point inside them")
    check(not sum(no_shape.values()), f"precincts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * half, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["a place the precinct does not name"] <= 0.02 * half, f"the place at a precinct's own point: {dict(place)}")
    check(council["a district the precinct does not name"] + council["no district"] <= 0.02 * max(1, sum(council.values())), f"the council district at a precinct's own point: {dict(council)}")
    check(ward["a ward the precinct does not name"] + ward["no ward"] <= max(1, 0.1 * sum(ward.values())), f"the ward at a precinct's own point: {dict(ward)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + f"); school district at {half:,} precincts' points: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city, town, village or township: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])) + "; county council district: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(council.items(), key=lambda x: -x[1])) + "; ward: "
        + ("; ".join(f"{n:,} {what}" for what, n in sorted(ward.items(), key=lambda x: -x[1])) or "none drawn"))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    for name, lon, lat, want, mcd, school_word in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        sid = G.school_at(files, found["geometry"], lon, lat)
        fdoc, _l = files.topo(rel[found["county"]])
        sn = index["school"].get("department_names", {}).get(sid) or fdoc["names"]["school"].get(sid, "") if sid else ""
        ok &= check(sid is not None and sid in pr["school"] and school_word in sn, f"{name}: the school district at the point is {sid} ({sn}), which should name {school_word!r}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        if mcd in layer_ids["mcd"]:
            ok &= check(shape is not None and shape["id"] == mcd and mcd in ([pr["mcd"]] + pr.get("mcd_all", [])),
                        f"{name}: the mcd layer gives {shape and shape['id']} and the precinct names {[pr['mcd']] + pr.get('mcd_all', [])}; the place is {mcd}")
        else:                                              # a township without a government of its own is no place here
            ok &= check(shape is None, f"{name}: the mcd layer gives {shape and shape['id']} in open country (the Bureau's township there, {mcd}, has no government)")
        for prop, kind in layer_for.items():
            shape2, edge2 = G.shape_at(files, kind, lon, lat)
            if shape2 is not None and edge2 <= tol_of[kind] + 10:      # the far-out layer's line is generalised: this close to it, the county file is the one to ask
                continue
            ok &= check(shape2 is not None and shape2["id"] == pr.get(prop),f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {pr.get(prop)}")
        extra = ""
        for k in ("com", "ward"):
            if pr.get(k) or (k == "com" and found["county"] in COUNCILS):
                shape3, _edge = G.shape_at(files, k, lon, lat)
                extra += f", {k} {shape3 and shape3['id']}"
                if k == "com":
                    ok &= check(shape3 is not None and shape3["id"].startswith(found["county"] + "|"), f"{name}: no council district of {found['county']} at the point")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape['properties']['name'] if shape else 'open country'}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, {pr['judicial']}, {pr['appeals']}, {sn}{extra}; {found['edge']:.0f} m from the precinct's line")

    # 4. county lines: the spot on one county's own drawing of the line nearest to a chosen point
    for name, lon, lat, pair in LINE_POINTS:
        doc, lines = files.topo(rel[pair[0]])
        bit = 1 << doc["arcKinds"].index("county")
        x, y = G.to_grid(lon, lat)
        cs = math.cos(math.radians(lat))
        best = None
        for a, pts in enumerate(lines):
            if doc["arcMask"][a] & bit:
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    d = G.seg_dist2(x * cs, y, ax * cs, ay, bx * cs, by)
                    if best is None or d < best[0]:
                        best = (d, (ax + bx) / 2.0, (ay + by) / 2.0)
        on = (best[1] * G.SCALE + G.ORIGIN[0], best[2] * G.SCALE + G.ORIGIN[1])
        f2, n2 = locate(files, on[0], on[1])
        sides_ = ({f2["county"]} | {h["county"] for h in n2}) if f2 else set()
        ok = check(f2 is not None and f2["edge"] < 1.0 and sides_ == set(pair),
                   f"a point on {pair[0]}'s drawing of the {pair[0]}/{pair[1]} line lands in {f2 and f2['county']} with {sorted(sides_)} at hand, {f2 and round(f2['edge'], 2)} m from the line")
        if f2:
            say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: the spot on the line ({on[0]:.5f}, {on[1]:.5f}) is given to "
                f"{f2['geometry']['properties']['name']} with {', '.join(sorted(h['geometry']['properties']['name'] for h in n2))} at hand")

    # 5. polling places say what they are, and name only precincts and places that are there
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        n = len(polls["places"])
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < n for i in polls["precinct"].values())
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])),
              "polling_places.json names a precinct or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        pts = [p for p in polls["places"] if p.get("lonlat")]
        inside = 0
        for p in pts:
            f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
            inside += bool(f3) and f3["county"] == p["county"]
        check(inside >= 0.97 * len(pts), f"only {inside} of {len(pts)} polling places lie inside their own county")
        say(f"      self-test: polling places: {polls.get('status')}; {n:,} places of one county, {len(pts):,} with a point ({inside:,} inside the county); "
            f"{len(polls['counties_not_on_the_list'])} counties not on the list")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Missouri's ballot map -> ballot_geo/mo/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/mo)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask the map services, the statutes and the polling place list again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
