"""
ballot/mt_geo.py - the geography behind Montana's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py and ballot/nd_geo.py for the few things those states added, and changes nothing in any of them), so the
same page and the same reader (ballot/mn_geo_reader.js) read them all.

    python ballot/mt_geo.py                 builds ballot_geo/mt/ and runs the self-test (the first build downloads about
                                            40 MB of map layers and lays districts over the precinct parts: allow half an hour)
    python ballot/mt_geo.py --selftest      runs the self-test on the files already built
    python ballot/mt_geo.py --refresh       asks the map services and the Secretary of State's page again
    python ballot/mt_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/mt_local/)
----------------------------------------------------------------------------------------------------------------------
Every map layer is the Montana State Library's (its Geographic Information Services, which keeps the Montana Spatial
Data Infrastructure's boundary framework with the Secretary of State and the counties), published as public ArcGIS
layers that answer plain scripts.
  - Precinct parts: "MontanaPrecinctSplits (View)", layer SOSCurrentPrecinctSplits, published 2026-07-17: 3,389 parts of
    the Secretary of State's 731 precincts, each with its county and the district of every kind its voters vote in:
    congressional, House, Senate, Public Service Commission, judicial, county commissioner, city and ward, school and
    single-member trustee district, conservation district, and hospital, fire, water, sewer, park, library, cemetery,
    ambulance, mosquito, resort, irrigation, drainage, rural, improvement, transportation, study commission, special
    and court (jury) districts. Every column is a district; the layer has no column about a person.
  - Whole precincts: the Library's "Montana Voting Precincts" (727 precincts, lines from each county, updated county by
    county between 2012 and 2024). The parts layer does not yet cover every county whole (Carbon and Powell counties' parts
    cover about 70 percent of the county, Beaverhead's 84, Lake's 86, Stillwater's 88), so where a precinct of this layer
    has 3 percent or more of its area, and at least a square kilometre, outside every part, the whole precinct is added
    to its county file after the parts, marked "whole": a point the parts do not cover falls in it, and learns what lines
    can tell (county, House and Senate district, congressional and judicial district, Public Service Commission district,
    city or town, school districts), not what only the Secretary's table says (ward, commissioner district and the rest).
  - The Library's "Montana Administrative Boundaries Framework": counties (with the judicial district of each), House
    and Senate districts (2024-2032), congressional districts (adopted November 12, 2021), Public Service Commission
    districts, incorporated cities and towns, and elementary, secondary (high school) and K-12 school districts.
  - The county commissioner rule: Montana Code Annotated 7-4-2104 (leg.mt.gov), checked for its own words on every build.
  - Polling places: the Secretary of State's "Polling Location-Satellite Office Locations" page (sosmt.gov), its
    Polling Place Locations table, asked for whole through the table's own data call. Read by column name: precinct
    number, county, precinct name, House and Senate district, polling place, address, city, zip code and hours. The
    table's editor columns are never read. See POLLING PLACES.

What Montana calls things, and what that does to the files
-----------------------------------------------------------
The smallest area the Secretary's table names is a precinct part (a precinct cut wherever any district line crosses
it), so a shape here is a part and everything the table says of it is exact for it. The page calls it a precinct; its
name gives the precinct's name and the part's number. Montana has no townships: outside its 127 cities and towns
(two of them consolidated city-county governments, Butte-Silver Bow and Anaconda-Deer Lodge) a part names no place.
School districts overlap in Montana: an elementary district lies under a high school district, or one K-12 district
serves both, so a part lies in an elementary or K-12 district and often in a high school district as well.

County commissioners (index.json, "supervisor_plans", in the words the page builder reads): MCA 7-4-2104 says a
commissioner is chosen from the residents of the district but "the election ... must be submitted to the entire
electorate of the county" unless a county's own plan of government or a court order provides otherwise. So in every
county but the two consolidated governments the plan is 2 (each commissioner stands for a district and the whole county
votes), the commissioner districts are not voting areas and are not drawn, and each part keeps the table's own words
for its commissioner district (com_said). A county whose plan of government or a court order elects by district is not
known to these files; the county's election office is the authority.

What is built (ballot_geo/mt/): index.json, manifest.json, precincts/<county>.json (56), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, ward, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes. Coordinates are on the same grid (0.00001 degree, translate [-98, 43]; Montana lies west of
98 west, so its grid numbers are negative in x, which TopoJSON allows).

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "MT" (j = "MT", the jurisdiction_id of statewide races)
  county    "30009"                 sl_places county id; jurisdiction_id of county offices
  mcd       "MT-M-61525"            MT-M- and the Census Bureau's place code (the Library's FIPS_CODE)
  ward      "MT-M-61525|Ward 1"     <city>|Ward <number>, where the table's ward words give a number
  house     "55"   senate "28"   cd "2" (properties.race is the federal race id, 2026-MT-H02)
  judicial  "JD22"                  the jurisdiction_id of district court races (sl_places id MT-JD22)
  school    "MT-S-0861"             MT-S- and the Office of Public Instruction's legal entity number; properties.t says
                                    elementary, high school or K-12; properties.nces is the federal district code
A part also names, with no layer: psc ("PSC2"), the jurisdiction_id of a Public Service Commission race.
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
import urllib.parse
import uuid
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import nd_geo as N  # noqa: E402

GeoError = G.GeoError
STATE, FIPS = "MT", "30"
OUT = os.path.join(HERE, "ballot_geo", "mt")
CACHE = os.path.join(HERE, "states_cache", "mt_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://prodvoterportal.mt.gov/WhereToVote.aspx"      # as linked from sosmt.gov/elections/vote/

MSL = "https://services.arcgis.com/qnjIrwR8z5Izc0ij/arcgis/rest/services/"      # the Montana State Library's ArcGIS organisation
SPLIT_SERVICE = MSL + quote("MontanaPrecinctSplits_(View)") + "/FeatureServer/0"
SPLIT_ITEM = "https://www.arcgis.com/home/item.html?id=fd949a9c917042c1bb4a226a564a376b"
SPLIT_FIELDS = ("CountyName,CountyCode,County,Prec_Code,Prec_Name,Precinct_I,PrecSpltCd,PPartName,CntyPrecSp,AmbDist,CemDist,CityDist,ComCounDis,"
                "CongDist,CntyDist,CntyComDis,DrainDist,FireDist,HospDist,HouseDist,IrrDist,JudDist,LibrDist,MosqDist,ParkDist,PSCommDist,ResortDist,"
                "RuralDist,RurImpDist,SchDist,SchSingDis,SenateDist,SewerDist,SoilConDis,SpecDist,StateDist,StdyCmDist,SCJDist,UrbnTrnDis,WardDist,"
                "WtrDist,JuryDist")
FRAME = MSL + "Montana_Administrative_Boundaries_Framework/FeatureServer/"
FRAME_ITEM = "https://www.arcgis.com/home/item.html?id=6567477b52b1421292c77831e5581a60"
FRAME_PAGE = "https://msl.mt.gov/GIS/Boundaries"
SCHOOL_FIELDS = "NAME,LE_NUMBER,TYPE,County_Code,County_Name,District_Number,SDLEA,LAST_UPDATE"
LAYERS = {      # name: (Framework layer, fields asked for, cached file, rows a request)
    "counties": (5, "NAME,ALLFIPS,FIPS,CountyCode,County,Judicial,LAST_UPDATE", "msl_counties_geometry_4326.json.gz", 10),
    "house": (63, "District,Name", "msl_house_2024_geometry_4326.json.gz", 20),
    "senate": (62, "District,Name", "msl_senate_2024_geometry_4326.json.gz", 10),
    "cd": (9, "DistrictNumber,DistrictName,DistrictCode,Notes,Source", "msl_congressional_geometry_4326.json.gz", 1),
    "psc": (40, "DistrictNumber,DistrictName,DistrictCode,Notes,Source,LastUpdate", "msl_psc_geometry_4326.json.gz", 1),
    "cities": (7, "NAME,COUNTY,FIPS_CODE,LAST_UPDATE,CLASS,TYPE,City_Town,COUNTYNAME", "msl_cities_towns_geometry_4326.json.gz", 50),
    "elementary": (10, SCHOOL_FIELDS, "msl_school_elementary_geometry_4326.json.gz", 40),
    "secondary": (11, SCHOOL_FIELDS, "msl_school_secondary_geometry_4326.json.gz", 20),
    "k12": (12, SCHOOL_FIELDS, "msl_school_k12_geometry_4326.json.gz", 20),
    "precincts": (19, "NUMBER,NAME,COUNTY,SOSPRECINCT,SOURCE,LAST_UPDATE,PRECINCT_ID,PRECINCT_CODE,COUNTY_ID,PrecinctName",
                  "msl_voting_precincts_geometry_4326.json.gz", 100),      # never POLLCODE, POLLINGPLACE (an older list)
}
SPLIT_FILE = "sos_current_precinct_splits_geometry_4326.json.gz"
STATUTE_URL = "https://leg.mt.gov/bills/mca/title_0070/chapter_0040/part_0210/section_0040/0070-0040-0210-0040.html"
STATUTE_WORDS = "must be submitted to the entire electorate of the county unless otherwise provided for"
POLL_PAGE = "https://sosmt.gov/elections/polling-location-satellite-office-locations/"
POLL_AJAX = "https://sosmt.gov/wp-admin/admin-ajax.php?action=get_wdtable&table_id=50"
POLL_COLS = {"pp": "precinctnumber", "county": "county", "city": "pollingplacecity", "address": "pollingplaceaddress", "precinct": "precinctname",
             "hd": "hd", "sd": "sd", "name": "pollingplacelocation", "zip": "pollingplacezip", "hours": "pollingplacehours"}
POLL_EDITED = "wdt_last_edited_at"       # read for its date only; the editor's name beside it never is
POLL_LAYOUT_CHECKED = False       # True only when a person has compared a dozen precincts of polling_places.json with the Secretary's page

ARC_KINDS = ["county", "mcd", "ward", "house", "senate", "cd", "judicial"]
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
NEAR_M = G.NEAR_M
WHOLE_SHARE = 0.03                # a whole precinct is added where this share of it, and at least WHOLE_KM2, lies outside every part
WHOLE_KM2 = 1.0
EDGE_M = 1000.0                   # metres: a part's one-sided line this close to the state line is on the state line
CONSOLIDATED = {"30093": "Butte-Silver Bow", "30023": "Anaconda-Deer Lodge"}
SCHOOL_TYPE = {1: ("E", "elementary"), 2: ("H", "high school"), 3: ("K", "K-12")}
SAID = {      # the table's other columns, kept in its own words on each part (the page reads none of them as an id)
    "CityDist": "city_said", "WardDist": "ward_said", "CntyComDis": "com_said", "SchDist": "school_said", "SchSingDis": "trustee_said",
    "SoilConDis": "swcd_said", "HospDist": "hospital_said", "FireDist": "fire_said", "WtrDist": "water_said", "SewerDist": "sewer_said",
    "ParkDist": "park_said", "LibrDist": "library_said", "CemDist": "cemetery_said", "AmbDist": "ambulance_said", "MosqDist": "mosquito_said",
    "ResortDist": "resort_said", "IrrDist": "irrigation_said", "DrainDist": "drainage_said", "RuralDist": "rural_said",
    "RurImpDist": "improvement_said", "UrbnTrnDis": "transit_said", "StdyCmDist": "study_said", "SpecDist": "special_said",
    "JuryDist": "court_said", "ComCounDis": "community_council_said"}
SAID_WORDS = {
    "city_said": "the city or town district the table names, in its words", "ward_said": "the ward the table names, in its words",
    "com_said": "the county commissioner district the table names, in its words (where the commissioner must live; see supervisor_plans)",
    "school_said": "the school districts the table names, in its words", "trustee_said": "the school trustee district the table names",
    "swcd_said": "the conservation district the table names", "hospital_said": "the hospital district the table names",
    "fire_said": "the fire district the table names", "water_said": "the water or water and sewer district the table names",
    "sewer_said": "the sewer district the table names", "park_said": "the park district the table names",
    "library_said": "the library district the table names", "cemetery_said": "the cemetery district the table names",
    "ambulance_said": "the ambulance district the table names", "mosquito_said": "the mosquito district the table names",
    "resort_said": "the resort area district the table names", "irrigation_said": "the irrigation district the table names",
    "drainage_said": "the drainage district the table names", "rural_said": "the rural (outside a city) district the table names",
    "improvement_said": "the rural improvement district the table names", "transit_said": "the urban transportation district the table names",
    "study_said": "the local government study commission district the table names", "special_said": "the special district the table names",
    "court_said": "the city or municipal court (jury) district the table names", "community_council_said": "the community council district the table names"}


def clean(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def fold(t):
    return re.sub(r"[^A-Z0-9 ]", "", clean(t).upper().replace("&", " AND ").replace("-", " ")).replace("  ", " ").strip()


def title(t):
    """A name the files write in capitals, in ordinary capitals (K-12 and roman numerals kept)."""
    out = []
    for w in clean(t).split(" "):
        if re.fullmatch(r"K-12|[IVX]+|#?\d+\w*", w):
            out.append(w)
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    t = " ".join(out)
    return re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), t)


def ordinal(n):
    return G.ordinal(n)


# ---------------------------------------------------------------- the sources

def load(name, refresh, say):
    lid, fields, fname, page = LAYERS[name]
    return W.fetch_full(FRAME + str(lid), fields, os.path.join(CACHE, fname), page, "OBJECTID", refresh, say)


def statute(refresh, say):
    """MCA 7-4-2104, read for its own words: the build stops if the rule this module follows is no longer there."""
    path = os.path.join(CACHE, "mca_7-4-2104.html")
    net.download(STATUTE_URL, path, 0 if refresh else 30, say=say)
    raw = open(path, "rb").read()
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace"))))
    if STATUTE_WORDS not in text:
        raise GeoError("    MCA 7-4-2104 no longer reads as this builder was checked against (the whole county elects each commissioner); stopping")
    return {"url": STATUTE_URL, "fetched": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path),
            "words": "the election of the member or members of the board must be submitted to the entire electorate of the county unless otherwise "
                     "provided for under: (a) a plan of government provided for in a county adopting an optional or alternative form of government; or (b) a court order"}


# ---------------------------------------------------------------- the precinct table

NUM = {"I": "1", "II": "2", "III": "3"}


def num_of(t, pattern):
    m = re.fullmatch(pattern, clean(t).upper())
    return str(int(m.group(1))) if m else None


def com_num(t):
    """The number at the end of the table's words for a commissioner district (COMM DIST 2, COMMISSIONER DIST # 12,
    COUNTY COMMISSIONER DIST II); None where they end in no number (MALTA DISTRICT B, COMMISSIONER DIST)."""
    m = re.search(r"(?:#\s*|\b)0*(\d{1,2}|I{1,3})$", clean(t).upper())
    return None if not m else NUM.get(m.group(1), m.group(1))


def read_parts(doc, county_name):
    """The precinct parts, in id order, each with what the table says of it, and their rings as vertex keys."""
    pre, polys, seen, odd = [], [], set(), collections.Counter()
    for a, rings in doc["rows"]:
        county = clean(a["County"])
        if county not in county_name or fold(a["CountyName"]) != fold(county_name[county]):
            raise GeoError(f"    precinct table: a row's county ({county!r}, {clean(a['CountyName'])!r}) is not one of the Library's 56; stopping")
        part_name = clean(a["PPartName"])
        pid = f"{county}-" + re.sub(r"[^A-Za-z0-9.]+", "-", part_name).strip("-").upper()
        if not part_name or pid in seen:
            raise GeoError(f"    precinct table: part {part_name!r} of {county_name[county]} is not named, or named twice; stopping")
        seen.add(pid)
        house = num_of(a["HouseDist"], r"HOUSE DISTRICT 0*(\d+)")
        senate = num_of(a["SenateDist"], r"SENATE DISTRICT 0*(\d+)")
        cd = num_of(a["CongDist"], r"0*([12])(?:ST|ND) CONGRESSIONAL")
        jud = num_of(a["JudDist"], r"JUDICIAL DISTRICT 0*(\d+)")
        psc = num_of(a["PSCommDist"], r"PUBLIC SERVICE COMMISSIONER,? DISTRICT 0*([1-5])")
        for what, v, raw in (("House district", house, a["HouseDist"]), ("Senate district", senate, a["SenateDist"]), ("congressional district", cd, a["CongDist"]),
                             ("judicial district", jud, a["JudDist"]), ("Public Service Commission district", psc, a["PSCommDist"])):
            if v is None:
                odd[f"{what} not given" if not clean(raw) or re.fullmatch(r"[A-Z ]+", clean(raw).upper()) else f"{what} in other words"] += 1
        p = {"id": pid, "county": county, "precinct": clean(a["Prec_Name"]), "part": clean(a["PrecSpltCd"]), "house_t": house, "senate_t": senate,
             "cd_t": cd, "jud_t": jud, "psc_t": psc, "whole": False}
        for col, key in SAID.items():
            if clean(a[col]):
                p[key] = clean(a[col])
        pre.append(p)
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    order = sorted(range(len(pre)), key=lambda i: (pre[i]["county"], G.natkey(pre[i]["precinct"]), G.natkey(pre[i]["part"]), pre[i]["id"]))
    pre, polys = [pre[i] for i in order], [polys[i] for i in order]
    if len({p["county"] for p in pre}) != 56:
        raise GeoError(f"    precinct table: {len({p['county'] for p in pre})} counties, not 56; stopping")
    n_parts = collections.Counter((p["county"], p["precinct"]) for p in pre)
    for p in pre:
        base = p["precinct"] if re.search(r"[A-Za-z]", p["precinct"]) else f"Precinct {p['precinct']}"
        p["name"] = base + (f", part {p['part']}" if n_parts[(p["county"], p["precinct"])] > 1 else "")
    return pre, polys, dict(odd)


def ward_word(raw, city):
    """'Ward <n>' where the table's ward words give a number (WARD 2, WARD #2, CITY COUNCIL WARD2, BILLINGS #2, BELGRADE 2,
    TOWN OF DARBY - WARD 2, a ward number with the city's initial beside it: WARD #2W in Whitefish, FB-2 in Fort Benton);
    None for words that give none (CITY LIMITS, WARD EAST, WARD 2-1)."""
    t = clean(raw).upper()
    cname = fold(city)
    words = [w for w in cname.split() if w not in ("CITY", "TOWN", "OF")]
    ini = "".join(w[0] for w in words)
    m = re.fullmatch(r"(?:.*?\b)?WARD\s*#?\s*0*([1-9]\d?)(?:\s+-\s+.*)?", t)
    if m:
        return f"Ward {m.group(1)}"
    m = re.fullmatch(r"(.+?)\s*#\s*0*([1-9]\d?)", t) or re.fullmatch(r"(.+?) 0*([1-9]\d?)", t)
    if m and fold(m.group(1)) in (cname, " ".join(words)):
        return f"Ward {m.group(2)}"
    m = re.fullmatch(r"(?:.*?\b)?WARD\s*#?\s*0*([1-9]\d?)([A-Z])", t)
    if m and ini and m.group(2) == ini[0]:
        return f"Ward {m.group(1)}"
    m = re.fullmatch(r"(?:.*?\b)?WARD\s*([A-Z])0*([1-9]\d?)", t)
    if m and ini and m.group(1) == ini[0]:
        return f"Ward {m.group(2)}"
    m = re.fullmatch(r".*?\b([A-Z]{1,2})-0*([1-9]\d?)", t)
    if m and m.group(1) == ini:
        return f"Ward {m.group(2)}"
    return None


CITY_NOISE = re.compile(r"\b(CITY ?WIDE( DIST(RICT)?)?|CITY OF|TOWN OF|CITY LIMITS|ALL|WARDS? .*|DIST(RICT)?)\b")


def city_key(t):
    k = fold(CITY_NOISE.sub(" ", clean(t).upper()))
    k = re.sub(r"^CITY\s+|\s+(CITY|TOWN)$", "", k).strip()
    return re.sub(r"\bST\b", "SAINT", k)


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'mt-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"mt_geo_overlay_{name}.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say(f"      laying the {name} lines over the precincts (kept for the next build)")
    t0 = time.time()
    res = G.school_overlay(pre_rings, districts, levels=(G.SCHOOL_THICK,), say=None)
    rows = [[[d, round(share, 5), thick[0]] for d, share, thick in row] for row in res]
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      ... {name}: {time.time() - t0:.0f} s")
    return rows


def ranked(got, keys):
    """An overlay row as [(key, share, thick)], largest share first (a district drawn in several rows counted once)."""
    share, thick = collections.Counter(), set()
    for d, s, t in got:
        share[keys[d]] += s
        if t:
            thick.add(keys[d])
    return sorted(((k, s, k in thick) for k, s in share.items()), key=lambda x: (-x[1], G.natkey(x[0])))


def edge_set(arcs, sides, outline, lim_m=EDGE_M):
    """The one-sided lines of a fabric that lie on the state line: those whose middle point is within lim_m of a segment
    of `outline` (lines as vertex keys)."""
    cx, cy = 20000, 15000
    grid = collections.defaultdict(list)
    for line in outline:
        pts = [G.vxy(k) for k in line]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for gx in range(min(x0, x1) // cx, max(x0, x1) // cx + 1):
                for gy in range(min(y0, y1) // cy, max(y0, y1) // cy + 1):
                    grid[(gx, gy)].append((x0, y0, x1, y1))
    lim2 = (lim_m / G.M_PER_UNIT) ** 2
    out = set()
    for a, (r, l) in enumerate(sides):
        if r >= 0 and l >= 0:
            continue
        pts = [G.vxy(k) for k in arcs[a]]
        x, y = pts[len(pts) // 2]
        c = math.cos(math.radians(y / 1e7))
        for gx in (x // cx - 1, x // cx, x // cx + 1):
            for gy in (y // cy - 1, y // cy, y // cy + 1):
                for x0, y0, x1, y1 in grid.get((gx, gy), ()):
                    if G.seg_dist2(x * c, y, x0 * c, y0, x1 * c, y1) <= lim2:
                        out.add(a)
                        break
                if a in out:
                    break
            if a in out:
                break
    return out


def fabric_knit(rows, key):
    """N.knit and the overlap rule applied to a layer whose neighbours' lines do not always meet point for point."""
    rows = sorted(rows, key=lambda r: G.natkey(key(r[0])))
    keys = [key(a) for a, _r in rows]
    polys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in rows]
    N.knit(polys)
    W.settle_overlaps([{"id": k} for k in keys], polys)
    arcs, sides, rings, odd = G.topology(polys)
    if any(not r for r in rings):
        raise GeoError(f"    the shape {keys[[i for i, r in enumerate(rings) if not r][0]]!r} has no ring left after cleaning; stopping")
    return keys, polys, arcs, sides, rings, odd


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, plans, said_ids):
    """Every Montana race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape, then race_said for a district the precincts name). A race without a shape is
    listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, said, missing, matched = collections.Counter(), collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, _county_ids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
            if jid in said_ids.get("psc", ()):
                said["psc"] += 1
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "district_court":
            hit = ("judicial", jid)
        elif kind in ("county_commissioner", "county_council"):
            plan = plans.get(jid) or {}
            whole = not d or (f"{jid}|{d}" not in S.get("com", {}) and plan.get("plan") == 2 and d in (plan.get("districts") or []))
            hit = ("county", jid) if whole else ("com", f"{jid}|{d}")
            if not whole:
                why = ("a consolidated city-county government elects its commission under its own charter, which no file read here sets out"
                       if jid in CONSOLIDATED else f"the precinct table and the ballot database do not name {d} among this county's commissioner districts")
        elif level == "county":
            hit = ("county", jid)
        elif level == "soil_water":
            why = ("no file read here draws Montana's conservation districts whole (the State Library's layer of them is incomplete and names "
                   "some by number only); each precinct part keeps the table's own words for its conservation district (swcd_said)")
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
        elif level == "school":
            hit = ("school", jid)
        elif level == "court" and jid in S.get("mcd", {}):
            hit = ("mcd", jid)
        elif level == "other" and jid in S.get("county", {}):
            hit = ("county", jid)
        else:
            why = "no source read here carries a boundary for this kind of district"
        if hit and hit[1] in S.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "named_by_the_precinct": dict(said),
            "no_shape": list(missing.values()), "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places (the Secretary of State's own page)

POLL_WAITING = {
    "why": "The Montana Secretary of State's list of polling places could not be read when these files were built. The Secretary's My Voter "
           "Page answers for one voter at a time and, with the county election administrator, is the authority.",
}
POLL_UNCHECKED_WHY = ("      polling places: read from the Secretary's page and marked 'unchecked', so a page does not show them yet. The page does not say "
                      "which election its list is for (its rows were entered on May 14, 2026, before the June primary): a person should confirm with "
                      "the Secretary of State or a few county election offices that it is the November 3, 2026 list, compare a dozen precincts of "
                      "polling_places.json with sosmt.gov/elections/polling-location-satellite-office-locations/, then set POLL_LAYOUT_CHECKED = True "
                      "in ballot/mt_geo.py and build again.")


def fetch_polls(path, refresh, say):
    """The Polling Place Locations table, whole, through the table's own data call, cut down on the spot to the columns
    named in POLL_COLS (found by name in the page's own description of the table) and kept as JSON."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    try:
        net.patient_lookups()
        raw_page = net.get(POLL_PAGE, timeout=180)
        page = raw_page.decode("utf-8", "replace")
        if "Polling Place Locations" not in page:
            raise GeoError("    polling places: the Secretary's page no longer has a Polling Place Locations table")
        m = re.search(r'id="table_1_desc"[^>]*value=\'([^\']*)\'', page)
        desc = json.loads(html.unescape(m.group(1))) if m else {}
        if str(desc.get("tableWpId")) != "50":
            raise GeoError("    polling places: the page's first table is no longer the Polling Place Locations table (50)")
        cols = [c.get("name") for c in (desc.get("dataTableParams") or {}).get("columnDefs", [])]
        idx = {k: cols.index(v) for k, v in POLL_COLS.items() if v in cols}
        if set(idx) != set(POLL_COLS) or POLL_EDITED not in cols:
            raise GeoError(f"    polling places: the table's columns are now {cols}; the reader needs to be told the layout")
        nonce = re.search(r'id="wdtNonceFrontendServerSide_50"[^>]*value="([^"]+)"', page)
        fields = [("draw", "1"), ("start", "0"), ("length", "5000"), ("wdtNonce", nonce.group(1) if nonce else "")]
        for i in range(len(cols)):
            fields += [(f"columns[{i}][data]", str(i)), (f"columns[{i}][searchable]", "true"), (f"columns[{i}][orderable]", "true"),
                       (f"columns[{i}][search][value]", ""), (f"columns[{i}][search][regex]", "false")]
        fields += [("order[0][column]", "0"), ("order[0][dir]", "asc"), ("search[value]", ""), ("search[regex]", "false")]
        time.sleep(1.0)
        req = Request(POLL_AJAX, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": POLL_PAGE,
                               "X-Requested-With": "XMLHttpRequest"})
        with urlopen(req, timeout=300) as r:
            raw = r.read()
        j = json.loads(raw)
        data = j.get("data") or []
        if not data or str(j.get("recordsTotal")) != str(len(data)):
            raise GeoError(f"    polling places: {len(data):,} rows came, and the table counts {j.get('recordsTotal')}; stopping")
        rows = [{k: clean(r[i]) for k, i in idx.items()} for r in data]
        edited = sorted({re.sub(r"^(\d\d)/(\d\d)/(\d{4}).*$", r"\3-\2-\1", clean(r[cols.index(POLL_EDITED)])) for r in data if clean(r[cols.index(POLL_EDITED)])})
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not read the Secretary's polling place page again ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        raise
    out = {"url": POLL_PAGE, "fetched": dt.date.today().isoformat(), "columns": sorted(POLL_COLS.values()), "rows_edited": [edited[0], edited[-1]] if edited else None,
           "sha256_of_the_answer": hashlib.sha256(raw).hexdigest(), "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows of the Polling Place Locations table")
    return out


def pct_key(t):
    """A precinct's name for matching the polling place list to the precinct table (PREC 01 / PRECNCT 1 / PCT 01)."""
    t = clean(t).upper().replace("_", " ")
    t = re.sub(r"\b(PRECINCT|PRECNCT|PREC|PCT|NO)\b\.?|#", " ", t)
    toks = re.findall(r"[A-Z]+|\d+", t)
    return " ".join(str(int(x)) if x.isdigit() else x for x in toks)


def pct_numbers(t):
    """The numbers in a precinct's name, a letter after one kept with it (FRENCHTWN 90A and FRENCHTOWN 90 A: 90A; P 1
    ROCKVALE-SILESIA and P 1: 1; BRADY_19 and 19_BRADY: 19), for a second try where the names are written differently."""
    t = re.sub(r"\b(\d+) ([A-Z])\b", r"\1\2", clean(t).upper().replace("_", " "))
    return tuple(sorted(re.sub(r"^0+(?=\d)", "", x) for x in re.findall(r"\b\d+[A-Z]?\b", t)))


def census_geocode(rows, say):
    """mn_geo.census_geocode for Montana addresses: [(id, street, city, zip)] -> {id: (lon, lat, matched address)}.
    Polling places are public buildings; nothing else is ever sent."""
    net.patient_lookups()
    out = {}
    for start in range(0, len(rows), 1000):
        buf = io.StringIO()
        w = csv.writer(buf)
        for rid, street, city, zipc in rows[start:start + 1000]:
            w.writerow([rid, street, city, STATE, zipc])
        boundary = "----mtgeo" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"places.csv\"\r\n"
                f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n").encode("utf-8")
        req = Request(G.GEOCODER, data=body, headers={"User-Agent": net.UA, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urlopen(req, timeout=900) as r:
            text = r.read().decode("utf-8", "replace")
        for rec in csv.reader(io.StringIO(text)):
            if len(rec) >= 6 and rec[2].strip() == "Match":
                try:
                    lon, lat = (float(v) for v in rec[5].split(","))
                except ValueError:
                    continue
                out[rec[0].strip()] = (round(lon, 5), round(lat, 5), rec[4].strip())
        time.sleep(1.0)
    say(f"      polling places: {len(rows):,} addresses asked of the Census Bureau's geocoder, {len(out):,} matched")
    return out


def place_points(places, cbox, say):
    """Coordinates from the street address (kept in a small cache). A match outside the place's own county (its box,
    widened a little) is thrown out."""
    cache_path = os.path.join(CACHE, "mt_geo_pollingplace_points.json")
    kept = {}
    if os.path.exists(cache_path):
        try:
            kept = json.load(open(cache_path, encoding="utf-8"))
        except (ValueError, OSError):
            kept = {}
    key = lambda p: f"{p['address']}|{p['city']}|{p['zip']}".lower()      # noqa: E731
    ask = [(str(n), p["address"], p["city"], p["zip"]) for n, p in enumerate(places) if p["address"] and key(p) not in kept]
    if ask:
        try:
            got = census_geocode(ask, say)
            for rid, *_ in ask:
                kept[key(places[int(rid)])] = list(got[rid]) if rid in got else None
            with open(cache_path + ".part", "w", encoding="utf-8") as fh:
                json.dump(kept, fh, separators=(",", ":"))
            os.replace(cache_path + ".part", cache_path)
        except Exception as e:  # noqa: BLE001  the list is still worth having without points on a map
            say(f"      polling places: the Census Bureau's geocoder could not be reached ({e}); places without coordinates stay off the map")
    placed = far = 0
    for p in places:
        hit, b = kept.get(key(p)), cbox.get(p.pop("_county"))
        if not hit or not b:
            continue
        if not (b[0] - 0.05 <= hit[0] <= b[2] + 0.05 and b[1] - 0.05 <= hit[1] <= b[3] + 0.05):
            far += 1
            continue
        p["lonlat"], p["from"] = [hit[0], hit[1]], "the Census Bureau's geocoder, from the street address"
        placed += 1
    return placed, far


def polling_places(pre, cname, cbox, put, say, refresh):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    path = os.path.join(CACHE, "sos_polling_place_locations.json")
    try:
        got = fetch_polls(path, refresh, say)
    except Exception as e:  # noqa: BLE001  the map does not depend on this list
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(f"      polling places: waiting; the Secretary's page could not be read ({e})")
        return {"file": "polling_places.json", "status": "waiting"}
    by_name = {fold(n).replace(" COUNTY", ""): c for c, n in cname.items()}
    shapes = collections.defaultdict(list)                     # (county, precinct key) -> [(House district, shape id)]
    for p in pre:
        shapes[(p["county"], pct_key(p["precinct"]))].append((p.get("house"), p["id"]))
    places, order, of_shape, unmatched, rows_off = {}, [], collections.OrderedDict(), [], 0
    for r in got["rows"]:
        county = by_name.get(fold(r["county"]).replace(" COUNTY", ""))
        if not county or not r["name"]:
            rows_off += 1
            continue
        fits = []
        for k in (pct_key(r["precinct"]), pct_key(r["pp"])):
            fits = shapes.get((county, k), [])
            if fits:
                break
        hd = str(int(r["hd"])) if r["hd"].isdigit() else None
        if not fits and pct_numbers(r["precinct"]):            # the names written differently: the one precinct of the county with the same numbers and House district
            same = {pk for (c, pk) in shapes if c == county and pct_numbers(pk) == pct_numbers(r["precinct"])}
            same = {pk for pk in same if any(h == hd for h, _i in shapes[(county, pk)])} or same
            if len(same) == 1:
                fits = shapes[(county, same.pop())]
        if len({h for h, _i in fits}) > 1:                     # two precincts of one name, told apart by their House district
            fits = [(h, i) for h, i in fits if h == hd] or fits
        if not fits:
            unmatched.append(f"{r['precinct']} ({r['county']})")
            continue
        key = (r["name"].lower(), r["address"].lower(), r["city"].lower(), r["zip"][:5])
        if key not in places:
            places[key] = {"name": title(r["name"]), "address": title(r["address"]), "city": title(r["city"]), "zip": r["zip"][:5], "type": None,
                           "hours": r["hours"], "lonlat": None, "precincts": [], "_county": county}
            order.append(key)
        for _h, sid in fits:
            of_shape.setdefault(sid, [])
            if key not in of_shape[sid]:
                of_shape[sid].append(key)
            if sid not in places[key]["precincts"]:
                places[key]["precincts"].append(sid)
    plist = [places[k] for k in order]
    precinct, several = {}, {}
    for sid, keys in of_shape.items():
        if len(keys) == 1:
            precinct[sid] = order.index(keys[0])
        else:
            names = "; ".join(f"{places[k]['name']} ({places[k]['address']}, {places[k]['city']})" for k in keys)
            several[sid] = (f"is listed with {len(keys)} polling places on the Secretary of State's list ({names}); the Secretary's My Voter Page "
                            "or the county election administrator says which serves your address")
    placed, far = place_points(plist, cbox, say)
    without = sorted(p["id"] for p in pre if p["id"] not in of_shape)
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Montana Secretary of State", "title": "Polling Place Locations (Polling Location-Satellite Office Locations page)",
                       "url": POLL_PAGE, "saved": got.get("fetched"), "rows_entered": got.get("rows_edited"), "sha256": G.sha_file(path)},
               places=plist, precinct=dict(sorted(precinct.items())), no_place=dict(sorted(several.items())),
               note="The list is by precinct, so every part of a precinct carries the precinct's polling place. The Secretary's page does not say "
                    "which election the list is for; its rows were entered in May 2026.")
    put("polling_places.json", doc)
    say(f"      polling places: {len(got['rows']):,} rows, {len(plist):,} places ({placed:,} placed by the Census Bureau's geocoder, {far} matches thrown out as outside "
        f"the county); {len(of_shape):,} of {len(pre):,} shapes of the map are tied to a place ({len(several)} to several); {len(unmatched)} listed precincts "
        f"are not on the map" + (f" (e.g. {', '.join(unmatched[:6])})" if unmatched else "") + (f"; {rows_off} rows name no county or place" if rows_off else "")
        + f"; {len(without):,} shapes are not tied to a place")
    if not POLL_LAYOUT_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(plist), "with_coordinates": sum(1 for p in plist if p["lonlat"]),
            "rows": len(got["rows"]), "listed_and_not_on_the_map": unmatched, "shapes_not_tied_to_a_place": len(without),
            "shapes_with_several_places": len(several)}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Montana ballot map: precinct part, precinct, district, city and town and school district lines (the Montana State Library)")
    os.makedirs(CACHE, exist_ok=True)
    spath = os.path.join(CACHE, SPLIT_FILE)
    sdoc = W.fetch_full(SPLIT_SERVICE, SPLIT_FIELDS, spath, 100, "OBJECTID", refresh, say)
    docs = {k: load(k, refresh, say) for k in LAYERS}
    paths = {k: os.path.join(CACHE, LAYERS[k][2]) for k in LAYERS}
    edited = {"splits": W.layer_edited(SPLIT_SERVICE, os.path.join(CACHE, "mt_geo_about_splits.json"), refresh)}
    for k, (lid, _f, _n, _p) in LAYERS.items():
        edited[k] = W.layer_edited(FRAME + str(lid), os.path.join(CACHE, f"mt_geo_about_{k}.json"), refresh)
    law = statute(refresh, say)
    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")

    # ---- counties (the Library's), their judicial districts, and the state's outline
    crows = docs["counties"]["rows"]
    county_short = {clean(a["ALLFIPS"]): clean(a["NAME"]) for a, _r in crows}
    if len(county_short) != 56 or any(not re.fullmatch(r"30\d{3}", c) for c in county_short):
        raise GeoError("    counties: the Library's layer does not have Montana's 56 counties; stopping")
    cname = {c: names.get(("county", c)) or f"{title(n)} County" for c, n in county_short.items()}
    jud_of = {}
    for a, _r in crows:
        n = num_of(a["Judicial"], r"JUDICIAL DISTRICT 0*(\d+)")
        if not n:
            raise GeoError(f"    counties: {cname[clean(a['ALLFIPS'])]} names no judicial district; stopping")
        jud_of[clean(a["ALLFIPS"])] = f"JD{n}"
    ckeys, _cpolys, carcs, csides, _cr, codd = fabric_knit(crows, lambda a: clean(a["ALLFIPS"]))
    outline = [carcs[a] for a, (r, l) in enumerate(csides) if r < 0 or l < 0]

    # ---- precinct parts: one line between two neighbours, kept once
    pre, polys, table_odd = read_parts(sdoc, county_short)
    knit_moved, knit_added = N.knit(polys)
    if any(not rings for rings in polys):
        raise GeoError("    a precinct part has no ring left after its lines were set together; stopping")
    slivers, gave = W.settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct part has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    seam = W.across(arcs, sides, pre)
    on_edge = edge_set(arcs, sides, outline)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precinct parts of {len({(p['county'], p['precinct']) for p in pre}):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines "
        f"({sum(len(a) for a in arcs):,} points); two drawings of one line within {N.KNIT_M:.0f} m were made one ({knit_moved:,} corners moved, {knit_added:,} added); "
        f"{lone:,} lines still have a part on one side only ({len(seam):,} of them with another part just across, {len(on_edge):,} on the state line); "
        f"{slivers} sliver rings left out, {sum(n for _w, n in gave)} points given up by {len(gave)} parts" + (f"; odd: {dict(odd)}" if odd else "")
        + (f"; the table: {table_odd}" if table_odd else ""))

    # ---- whole precincts where the parts leave a piece of one uncovered
    prow = docs["precincts"]["rows"]
    by_short = {fold(n): c for c, n in county_short.items()}
    wpolys, wmeta = [], []
    for a, rings in prow:
        c = by_short.get(fold(a["COUNTY"]))
        if not c:
            raise GeoError(f"    precincts: a precinct's county ({clean(a['COUNTY'])!r}) is not one of the 56; stopping")
        ks = [k for k in (G.clean_ring(r) for r in rings) if k]
        if ks:
            wpolys.append(ks)
            wmeta.append((c, clean(a["NAME"]) or clean(a["PrecinctName"]) or clean(a["SOSPRECINCT"]), a.get("LAST_UPDATE")))
    part_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.SCHOOL_THICK, N.KNIT_M, 1]).encode()).hexdigest()   # noqa: E731
    o_cov = overlay_cached("parts-over-precincts", [[[G.vxy(k) for k in ks] for ks in rs] for rs in wpolys], part_rings, stamp(spath, paths["precincts"]), refresh, say)
    keep_w = []
    for n, (rs, got) in enumerate(zip(wpolys, o_cov)):
        area = sum(I.ring_area_m2([G.vxy(k) for k in ks]) * (1 if G.area2([G.vxy(k) for k in ks]) < 0 else -1) for ks in rs)
        left = max(0.0, 1.0 - sum(s for _d, s, _t in got))
        if left >= WHOLE_SHARE and left * area / 1e6 >= WHOLE_KM2:
            keep_w.append((n, round(100 * left, 1), round(left * area / 1e6, 1)))
    wpre, wsel = [], []
    used_ids = {p["id"] for p in pre}
    for n, left_pct, left_km2 in keep_w:
        c, nm, upd = wmeta[n]
        wid = f"{c}-WHOLE-" + re.sub(r"[^A-Za-z0-9.]+", "-", nm).strip("-").upper()
        while wid in used_ids:
            wid += "-2"
        used_ids.add(wid)
        year = dt.datetime.fromtimestamp(upd / 1000, dt.timezone.utc).year if isinstance(upd, (int, float)) else None
        wpre.append({"id": wid, "county": c, "precinct": nm, "part": "", "whole": True, "as_of": str(year) if year else None,
                     "name": (nm if re.search(r"[A-Za-z]", nm) else f"Precinct {nm}") + " (the whole precinct, where the parts are not drawn)",
                     "uncovered_pct": left_pct, "uncovered_km2": left_km2, "house_t": None, "senate_t": None, "cd_t": None, "jud_t": None, "psc_t": None})
        wsel.append(wpolys[n])
    warcs, wsides, wrings, wodd = G.topology(wsel) if wsel else ([], [], [], {})
    wfine, _ = G.simplify_arcs(warcs, wrings, G.TOL_PRECINCT) if wsel else ([], 0)
    nA, offA = len(pre), len(arcs)
    say(f"      {len(wpre)} whole precincts added where the parts leave a piece uncovered ({', '.join(f'{p['precinct']} ({cname[p['county']]}) {p['uncovered_pct']:.0f}%' for p in wpre[:8])}"
        f"{'...' if len(wpre) > 8 else ''})")
    allpre = pre + wpre
    all_arcs = arcs + warcs
    all_sides = sides + [[s + nA if s >= 0 else -1 for s in sd] for sd in wsides]
    all_rings = rings_of + [[[r + offA if r >= 0 else ~(~r + offA) for r in refs] for refs in rs] for rs in wrings]
    all_fine = fine + wfine
    qfine = G.quantise(all_fine)
    pre_rings = [[G.ring_xy(refs, all_fine) for refs in rings] for rings in all_rings]

    # ---- the Library's district layers
    hkeys, hpolys, harcs, hsides, _hr, hodd = fabric_knit(docs["house"]["rows"], lambda a: str(int(a["District"])))
    skeys_, spolys_, sarcs, ssides, _sr, sodd = fabric_knit(docs["senate"]["rows"], lambda a: str(int(a["District"])))
    dkeys, dpolys, darcs, dsides, _dr, dodd = fabric_knit(docs["cd"]["rows"], lambda a: str(int(a["DistrictNumber"])))
    if hkeys != [str(n) for n in range(1, 101)] or skeys_ != [str(n) for n in range(1, 51)] or dkeys != ["1", "2"]:
        raise GeoError("    the Library's layers do not have House districts 1 to 100, Senate districts 1 to 50 and congressional districts 1 and 2; stopping")
    psc_layer = {str(int(a["DistrictNumber"])) for a, _r in docs["psc"]["rows"]}
    ppkeys = [f"PSC{int(a['DistrictNumber'])}" for a, _r in docs["psc"]["rows"]]
    if psc_layer != {"1", "2", "3", "4", "5"}:
        raise GeoError("    the Library's Public Service Commission layer does not have districts 1 to 5; stopping")
    city_rows = []
    for a, rings in docs["cities"]["rows"]:
        f = int(a["FIPS_CODE"] or 0)
        if not 3000000 < f < 3100000:
            raise GeoError(f"    cities and towns: {clean(a['NAME'])!r} carries no Montana place code; stopping")
        city_rows.append((a, rings))
    mid = lambda a: f"{STATE}-M-{int(a['FIPS_CODE']) % 100000:05d}"      # noqa: E731
    mkeys, mpolys, marcs, msides, _mr, modd = fabric_knit(city_rows, mid)
    mrow = {mid(a): a for a, _r in city_rows}
    mkind = {k: "consolidated city-county" if "Consolidated" in clean(a["TYPE"]) else clean(a["TYPE"]).lower() for k, a in mrow.items()}
    mname = {k: names.get(("mcd", k)) or (clean(a["NAME"]) if mkind[k] == "consolidated city-county" else f"{clean(a['NAME'])} {mkind[k]}") for k, a in mrow.items()}
    mcounty = {k: by_short.get(fold(a["COUNTYNAME"])) for k, a in mrow.items()}
    school_rows, stype, snces, sname = [], {}, {}, {}
    for layer_name in ("elementary", "k12", "secondary"):
        for a, rings in docs[layer_name]["rows"]:
            if a["TYPE"] not in SCHOOL_TYPE or not re.fullmatch(r"\d{4}", clean(a["LE_NUMBER"])):
                raise GeoError(f"    school districts: {clean(a['NAME'])!r} (type {a['TYPE']!r}, number {a['LE_NUMBER']!r}) does not fit the layout this builder was checked against; stopping")
            k = f"{STATE}-S-{clean(a['LE_NUMBER'])}"
            if k in stype:
                raise GeoError(f"    school districts: two districts carry the number {k}; stopping")
            letter, word = SCHOOL_TYPE[a["TYPE"]]
            stype[k], snces[k] = letter, FIPS + clean(a["SDLEA"])
            base = re.sub(r"\s+(K-12 SCHOOLS?|SCHOOLS?|ELEMENTARY|HIGH SCHOOL|HIGH)$", "", clean(a["NAME"]).upper())
            sname[k] = names.get(("school", k)) or f"{title(base)} {dict(E='Elementary', H='High School', K='K-12')[letter]} District"
            school_rows.append((a, rings, k))
    sfab = []
    for group in (("E", "K"), ("H",)):
        rows_ = [(a, r) for a, r, k in school_rows if stype[k] in group]
        keyf = lambda a: f"{STATE}-S-{clean(a['LE_NUMBER'])}"      # noqa: E731
        k_, p_, a_, s_, r_, o_ = fabric_knit(rows_, keyf)
        f_, _ = G.simplify_arcs(a_, r_, G.TOL_SCHOOL)
        sfab.append((a_, s_, r_, f_, k_, o_))
    say(f"      the Library's layers: 100 House and 50 Senate districts, 2 congressional, 5 Public Service Commission, {len(mkeys)} cities and towns, "
        f"{len(stype)} school districts ({sum(1 for v in stype.values() if v == 'E')} elementary, {sum(1 for v in stype.values() if v == 'K')} K-12, "
        f"{sum(1 for v in stype.values() if v == 'H')} high school), 56 counties"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("House", hodd), ("Senate", sodd), ("Congress", dodd), ("cities", modd), ("counties", codd),
                                                           ("schools", sfab[0][5]), ("high schools", sfab[1][5])) if o))

    st = lambda k: stamp(spath, paths["precincts"], paths[k])      # noqa: E731
    o_house = overlay_cached("house", pre_rings, I.rings_xy(hpolys), st("house"), refresh, say)
    o_senate = overlay_cached("senate", pre_rings, I.rings_xy(spolys_), st("senate"), refresh, say)
    o_cd = overlay_cached("congressional", pre_rings, I.rings_xy(dpolys), st("cd"), refresh, say)
    o_psc = overlay_cached("psc", pre_rings, I.rings_xy([[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in docs["psc"]["rows"]]), st("psc"), refresh, say)
    o_city = overlay_cached("cities", pre_rings, I.rings_xy(mpolys), st("cities"), refresh, say)
    sdistricts = [[G.ring_xy(refs, f_) for refs in rings] for (_a, _s, r_, f_, _k, _o) in sfab for rings in r_]
    sorder = sfab[0][4] + sfab[1][4]
    o_sch = overlay_cached("school", pre_rings, sdistricts,
                           hashlib.sha256(json.dumps([st("elementary"), G.sha_file(paths["k12"]), G.sha_file(paths["secondary"]), G.TOL_SCHOOL]).encode()).hexdigest(), refresh, say)

    # ---- districts by part: the table's word, and the lines laid over the part to check it (or to stand in for it)
    differs = collections.defaultdict(list)
    filled = collections.Counter()
    for p, gh, gs, gc, gp in zip(allpre, o_house, o_senate, o_cd, o_psc):
        for prop, got, keys in (("house", gh, hkeys), ("senate", gs, skeys_), ("cd", gc, dkeys), ("psc", gp, ppkeys)):
            rows = ranked(got, keys)
            said = p[f"{prop}_t"]
            if said and prop == "psc":
                said = "PSC" + said
            top = rows[0][0] if rows else None
            if said:
                p[prop] = said
                if top and top != said and rows[0][1] >= 0.9:
                    differs[prop].append({"id": p["id"], "table": said, "lines": top, "share": round(100 * rows[0][1], 1)})
            else:
                if top is None:
                    raise GeoError(f"    {p['id']} lies in no {prop} district of the Library's lines; stopping")
                p[prop] = top
                filled[prop] += 1
            if not said and len(rows) > 1 and rows[1][1] >= SPLIT_SHARE:
                p.setdefault("split", {})[prop] = {k: round(100 * s, 1) for k, s, _t in rows if s >= SPLIT_SHARE}
        p["judicial"] = f"JD{p['jud_t']}" if p["jud_t"] else jud_of[p["county"]]
        if not p["jud_t"]:
            filled["judicial"] += 1
        elif p["judicial"] != jud_of[p["county"]]:
            differs["judicial"].append({"id": p["id"], "table": p["judicial"], "county": jud_of[p["county"]]})
    say(f"      districts by part: the table's own word is kept; where it gives none the Library's lines stand in ({dict(filled)}); where the lines put 90 "
        f"percent or more of a part in another district than the table says: " + (", ".join(f"{k} {len(v)}" for k, v in sorted(differs.items())) or "nowhere"))

    # ---- cities and towns, wards
    city_in = collections.defaultdict(dict)
    for k in mkeys:
        city_in[mcounty[k]][city_key(mrow[k]["NAME"])] = k
    by_lines, unmatched_city, ward_none = 0, collections.Counter(), collections.Counter()
    for p, got in zip(allpre, o_city):
        rows = ranked(got, mkeys)
        top = rows[0] if rows else None
        p["mcd"] = None
        said = p.get("city_said")
        if said:
            key, here = city_key(said), city_in.get(p["county"], {})
            k = here.get(key) or (lambda f: f[0] if len(f) == 1 else None)([v for n, v in here.items() if key and (n.startswith(key) or key.startswith(n))])
            if k is None and top and top[1] >= 0.5:
                k, by_lines = top[0], by_lines + 1
            if k is None:
                unmatched_city[f"{said} ({cname[p['county']]})"] += 1
            p["mcd"] = k
        elif (p["whole"] or p["county"] in CONSOLIDATED) and top and top[1] >= 0.5:
            p["mcd"] = top[0]
        p["ward_ids"] = []
        if p["mcd"] and p.get("ward_said") and mkind[p["mcd"]] != "consolidated city-county":
            w = ward_word(p["ward_said"], mrow[p["mcd"]]["NAME"])
            if w:
                p["ward_ids"] = [f"{p['mcd']}|{w}"]
            else:
                ward_none[p["ward_said"]] += 1
    say(f"      cities and towns by part: {sum(1 for p in allpre if p['mcd']):,} parts lie in one ({by_lines} of them named by the table in words that fit "
        f"no city's name, and placed by the lines); {sum(unmatched_city.values())} parts name a city no file has"
        + (f" ({', '.join(sorted(unmatched_city))})" if unmatched_city else "")
        + f"; wards: {sum(1 for p in allpre if p['ward_ids']):,} parts in a numbered ward, {sum(ward_none.values())} whose ward words give no number"
        + (f" ({', '.join(sorted(ward_none)[:12])}{'...' if len(ward_none) > 12 else ''})" if ward_none else ""))

    # ---- school districts
    split = none = edges = 0
    for p, got in zip(allpre, o_sch):
        rows = [(sorder[d], share, thick) for d, share, thick in got]
        keep = [(k, s) for k, s, thick in rows if thick]
        if not keep and rows:
            best = max(((k, s) for k, s, _t in rows if stype[k] != "H"), key=lambda x: x[1], default=None)
            if best and best[1] >= 0.5:
                keep = [best]
        keep.sort(key=lambda x: (stype[x[0]] == "H", -x[1], x[0]))      # where a child's first school is, first
        base = [(k, s) for k, s in keep if stype[k] != "H"]
        outside = max(0.0, 1.0 - sum(s for k, s, _t in rows if stype[k] != "H"))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside >= 0.03) else None
        p["school_out"] = round(100 * outside, 1) if outside >= 0.03 else None
        p["school_edge"] = sorted({k for k, _s, _t in rows} - set(p["school"]))
        split += len(base) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(base) < 2
    say(f"      school districts by part: {split:,} parts are split between two or more elementary or K-12 districts, "
        f"{sum(1 for p in allpre if any(stype[k] == 'H' for k in p['school'])):,} lie in a high school district as well, {none} lie in none, "
        f"{edges:,} others only brush a neighbouring district along a line")

    # ---- commissioner plans (MCA 7-4-2104)
    db_com = collections.defaultdict(set)
    for _rid, level, kind, _jur, jid, district, _c in info["races"]:
        if kind == "county_commissioner" and district:
            db_com[jid].add(str(district).strip())
    plans = {}
    for c in sorted(county_short):
        if c in CONSOLIDATED:
            continue
        nums = sorted({com_num(p["com_said"]) for p in pre if p["county"] == c and p.get("com_said")} - {None}, key=G.natkey)
        ds = sorted({f"District {n}" for n in nums} | db_com.get(c, set()), key=G.natkey)
        plans[c] = {"plan": 2, "districts": ds,
                    "commissioners_elected": "one for each district, by the voters of the whole county (MCA 7-4-2104), unless the county's own plan of "
                                             "government or a court order provides otherwise",
                    "districts_from": "the Secretary of State's precinct table" + (" and the ballot database's races" if db_com.get(c) else "") if nums else
                                      ("the ballot database's races" if db_com.get(c) else "none named")}

    # ---- the area check: each county's parts against the Library's county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings[:nA]):
        for r in rings:
            area_p[p["county"]] += signed(r)
    county_rings = {k: [[G.vxy(x) for x in ks] for ks in rs] for k, rs in zip(ckeys, _cpolys)}
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in ckeys}
    cover = {c: round(100 * area_p[c] / area_c[c], 1) for c in ckeys}
    low = sorted((v, c) for c, v in cover.items() if v < 97)
    say(f"      area check: the precinct parts cover {100 * sum(area_p.values()) / sum(area_c.values()):.1f}% of Montana; counties under 97%: "
        + (", ".join(f"{cname[c]} {v}%" for v, c in low) or "none"))
    if any(v < 50 for v, _c in low):
        raise GeoError("    area check: the precinct parts cover less than half of a county; stopping")

    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "ward": [p["ward_ids"][0] if p["ward_ids"] else None for p in pre],
            "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": [p["cd"] for p in pre], "judicial": [p["judicial"] for p in pre]}
    mask = []
    for a, (r, l) in enumerate(sides):
        m = 0
        if r >= 0 and l >= 0:
            for bit, kind in enumerate(ARC_KINDS):
                if vals[kind][r] != vals[kind][l]:
                    m |= 1 << bit
        else:
            w, others = max(r, l), seam.get(a)
            for bit, kind in enumerate(ARC_KINDS):
                mine = vals[kind][w]
                if (others is None and mine is not None) or (others is not None and any(vals[kind][o] != mine for o in others)):
                    m |= 1 << bit
        mask.append(m)
    mask += [0] * len(warcs)                                  # a whole precinct's lines are no district's outline: the parts' and the layers' are

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

    def from_fabric(a_, s_, v, tol):
        g, q, _l, _r = G.build_layer(a_, s_, [v], tol)
        return g, q

    SPL, FRM, PCTS = "mt-msl-sos-precinct-splits-2026", "mt-msl-administrative-boundaries-framework", "mt-msl-voting-precincts"
    jud_counties = collections.defaultdict(list)
    for c in ckeys:
        jud_counties[jud_of[c]].append(cname[c])
    layer("state", *from_fabric(carcs, csides, [STATE] * len(ckeys), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": "Montana", "j": STATE, "d": None}, FRM)
    layer("county", *from_fabric(carcs, csides, ckeys, G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, FRM)
    layer("cd", *from_fabric(darcs, dsides, dkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, FRM)
    layer("senate", *from_fabric(sarcs, ssides, skeys_, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", f"{STATE}-{v}")) or f"Senate District {v}", "j": v, "d": v}, FRM)
    layer("house", *from_fabric(harcs, hsides, hkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", f"{STATE}-{v}")) or f"House District {v}", "j": v, "d": v}, FRM)
    layer("judicial", *from_fabric(carcs, csides, [jud_of[c] for c in ckeys], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("judicial", f"{STATE}-{v}")) or f"{ordinal(v[2:])} Judicial District", "j": v, "d": v[2:],
                     "counties": sorted(jud_counties[v])}, FRM + " (counties, each with its judicial district)")
    layer("mcd", *from_fabric(marcs, msides, mkeys, TOL_MCD), TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, FRM, zoom=MCD_ZOOM)
    ward_vals = vals["ward"]
    if any(ward_vals):
        layer("ward", *from_fabric(arcs, sides, ward_vals, G.TOL_LOCAL), G.TOL_LOCAL,
              lambda v: {"id": v, "name": f"{mname[v.split('|')[0]]}, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, SPL)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None, "t": SCHOOL_TYPE[{"E": 1, "H": 2, "K": 3}[stype[v]]][1], "nces": snces[v]}   # noqa: E731
    layer("school", *W.merged_layer([(a_, s_, k_) for (a_, s_, _r, _f, k_, _o) in sfab], G.TOL_LOCAL), G.TOL_LOCAL, sprops, FRM)
    dgeoms, dq = W.merged_layer([(a_, s_, k_) for (a_, s_, _r, _f, k_, _o) in sfab], G.TOL_SCHOOL)
    school_bytes = 0
    for v, polys_ in dgeoms:
        pr = sprops(v)
        pr.pop("id")
        doc, _d, _p = G.topo_doc({"school": [{"id": v, "properties": pr, "polys": polys_, "label": True}]}, dq)
        doc["kind"], doc["tolerance_m"] = "school", G.TOL_SCHOOL
        school_bytes += put(f"school/{v}.json", doc)

    # county files
    by_county = collections.defaultdict(list)
    for i, p in enumerate(allpre):
        by_county[p["county"]].append(i)
    counties, boxes, cbox, dropped_rings = [], {}, {}, 0
    for county, idxs in sorted(by_county.items()):
        idxs = sorted(idxs)                                   # the parts first, then the whole precincts: a point is given to the first shape holding it
        local = {i: n for n, i in enumerate(idxs)}
        geoms, used_names = [], {"mcd": {}, "ward": {}, "school": {}}
        for i in idxs:
            p = allpre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "house": p["house"], "senate": p["senate"], "cd": p["cd"],
                  "judicial": p["judicial"], "psc": p["psc"], "school": p["school"]}
            if p["whole"]:
                pr["whole"] = True
                if p["as_of"]:
                    pr["as_of"] = p["as_of"]
            else:
                pr["part"] = p["part"]
            if p["mcd"]:
                pr["mcd"] = p["mcd"]
                used_names["mcd"][p["mcd"]] = mname[p["mcd"]]
            if p["ward_ids"]:
                pr["ward"] = p["ward_ids"]
                for w in p["ward_ids"]:
                    used_names["ward"][w] = w.split("|")[1]
            for k in ("school_pct", "school_out", "school_edge", "split"):
                if p.get(k):
                    pr[k] = p[k]
            for k in SAID.values():
                if p.get(k):
                    pr[k] = p[k]
            for k in p["school"] + p["school_edge"]:
                used_names["school"][k] = sname[k]
            geoms.append({"id": p["id"], "properties": pr, "polys": G.group_polys([(refs, G.ring_xy(refs, all_fine)) for refs in all_rings[i]]), "label": True})

        def more(used, county=county, local=local, used_names=used_names):
            am, asd = [], []
            for a in used:
                am.append(mask[a])
                for side in all_sides[a]:
                    asd.append(local[side] if side in local else (-2 if a < offA and a in on_edge and a not in seam and side < 0 else -1))
            return {"county": county, "fips": county, "name": cname[county], "arcKinds": ARC_KINDS, "arcMask": am, "arcSides": asd,
                    "names": {k: dict(sorted(v.items())) for k, v in used_names.items() if v}}

        doc, dropped, pts = G.topo_doc({"precincts": geoms}, qfine, more)
        dropped_rings += dropped
        bx = []
        for g in geoms:
            polys_pts = pts[("precincts", g["id"])]
            if not polys_pts:
                raise GeoError(f"    precinct part {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // G.BOX_STEP, min(ys) // G.BOX_STEP, -(-max(xs) // G.BOX_STEP), -(-max(ys) // G.BOX_STEP)]
        boxes[county] = bx
        rel = f"precincts/{county}.json"
        size = put(rel, doc)
        cbox[county] = doc["bbox"]
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size,
                         "precincts": len(idxs), "whole_precincts": sum(1 for i in idxs if allpre[i]["whole"])})

    polls = polling_places(allpre, cname, cbox, put, say, refresh)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    said_ids = {"psc": {p["psc"] for p in allpre}}
    check = check_ids(info, shape_ids, plans, said_ids)
    check["table_differs_from_the_lines"] = {k: v for k, v in sorted(differs.items())}
    check["filled_from_the_lines"] = dict(filled)
    check["parts_naming_a_city_no_file_has"] = dict(unmatched_city)
    check["ward_words_without_a_number"] = dict(ward_none)
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in allpre if p.get("split")]
    check["whole_precincts_added"] = [{"id": p["id"], "name": p["precinct"], "county": p["county"], "uncovered_pct": p["uncovered_pct"],
                                       "uncovered_km2": p["uncovered_km2"], "lines_of": p["as_of"]} for p in wpre]
    check["county_area_covered_by_parts_percent"] = {c: v for v, c in low}
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    msl = "Montana State Library, Geographic Information Services"
    disclaimer = ("The Montana State Library provides this product/service for informational purposes only. The Library did not produce it for, nor is "
                  "it suitable for legal, engineering, or surveying purposes. Consumers of this information should review or consult the primary data "
                  "and information sources to ascertain the viability of the information for their purposes. The Library provides these data in good "
                  "faith but does not represent or warrant its accuracy, adequacy, or completeness.")
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": SPL, "agency": msl + ", with the Montana Secretary of State", "title": "MontanaPrecinctSplits (View), layer SOSCurrentPrecinctSplits",
                  "about": "The Secretary of State's current precinct parts, each with every district its voters vote in.", "url": SPLIT_ITEM,
                  "service": SPLIT_SERVICE, "published": "2026-07-17", "fetched": sdoc.get("fetched"), "sha256": G.sha_file(spath), "rows": len(pre),
                  "disclaimer": disclaimer}, **edited["splits"]),
            dict({"id": PCTS, "agency": msl, "title": "Montana Voting Precincts (Montana Administrative Boundaries Framework, layer 19)",
                  "about": "Whole precincts, from each county's lines; read only where the parts leave a piece of a precinct uncovered.",
                  "url": FRAME_ITEM, "service": FRAME + "19", "fetched": docs["precincts"].get("fetched"), "sha256": G.sha_file(paths["precincts"]),
                  "rows": len(prow), "disclaimer": disclaimer}, **edited["precincts"]),
            dict({"id": FRM, "agency": msl, "title": "Montana Administrative Boundaries Framework (MSDI): counties, House and Senate districts (2024-2032), "
                  "congressional districts, Public Service Commission districts, incorporated cities and towns, elementary, secondary and K-12 school districts",
                  "url": FRAME_ITEM, "page": FRAME_PAGE, "service": FRAME, "fetched": docs["counties"].get("fetched"),
                  "sha256": {k: G.sha_file(paths[k]) for k in LAYERS if k != "precincts"}, "disclaimer": disclaimer},
                 **{"current_to": max((e.get("current_to") or "") for k, e in edited.items() if k not in ("splits", "precincts")) or None}),
            {"id": "mt-mca-7-4-2104", "agency": "Montana Legislature", "title": "Montana Code Annotated 7-4-2104, Commissioners to be elected by district",
             "url": law["url"], "fetched": law["fetched"], "sha256": law["sha256"], "words": law["words"]}],
        "notes": {
            "lines": f"Every precinct line is the Secretary of State's table's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 "
                     "degree (about a metre); where two neighbours drew one line twice a few metres apart the two drawings were made one. A point within "
                     "a few metres of a line can fall on either side of it.",
            "parts": "The smallest area the Secretary's table names is a precinct part: a precinct cut wherever a district line crosses it. Each shape "
                     "is one part, named by its precinct's name and its own number, and what is said of it is the table's own word for that part. "
                     "Where the table leaves a district blank, the State Library's lines of that district stand in (check: filled_from_the_lines).",
            "whole_precincts": "The parts do not yet cover every county whole. Where a precinct of the Library's precinct layer has "
                               f"{WHOLE_SHARE:.0%} or more of its area (and at least {WHOLE_KM2:g} square kilometre) outside every part, the whole precinct "
                               "is added to the county's file after the parts and marked whole, with the year of its lines (as_of): a point the "
                               "parts cover is given the part; a point they do not cover is given the whole precinct, which says only what lines can tell.",
            "places": "Montana has no townships. A part the table puts in a city or town is given that city or town (mcd); a part in open country "
                      "names no place. Butte-Silver Bow and Anaconda-Deer Lodge are consolidated city-county governments.",
            "wards": "A part's ward is the table's word, read as a number where the words give one (Ward 2, BILLINGS #2, WARD #2W in Whitefish); "
                     "ward_said keeps the words themselves.",
            "commissioners": "MCA 7-4-2104: a county commissioner must live in the district, and the whole county elects each one, unless the county's "
                             "plan of government or a court order provides otherwise. So the commissioner districts are not voting areas and are not "
                             "drawn; com_said keeps the table's words, and supervisor_plans says how each county elects (the two consolidated "
                             "governments elect under their own charters and are left out). The county's election office is the authority.",
            "school": "School district lines are the State Library's. Which districts a part lies in is analysis, not an official list: a district "
                      f"counts when its piece of the part is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share "
                      "of the part's area (land and water, not voters). An elementary district lies under a high school district, so a part is "
                      "usually in both; school_said keeps the table's own words. No school office is on the November 2026 ballot (trustees are "
                      "elected in May).",
            "authority": "For which precinct an address votes in, and where, the county election administrator and the Montana Secretary of State's My "
                         "Voter Page are the authority.",
            "precinct_ids": "A part's id is its county's five digits and the table's name for the part (30063-UC95E-02); a whole precinct's is its "
                            "county's five digits, WHOLE and the precinct's name.",
            "disclaimers": "The Montana State Library asks that its limits travel with its data; they are under sources, word for word.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct part, then any whole precincts (whole: true). arcMask[i] "
                            "has bit k set when line i is an outline of arc_kinds[k] (never on a whole precinct's lines); arcSides[2i] and arcSides[2i+1] "
                            "are the shapes on the right and left of line i (-1: a shape in another county's file, one just across a gap in the "
                            "drawing, or none; -2: outside Montana); names gives the names of the places the file's shapes lie in.",
            "boxes": "boxes[county] holds four whole numbers a shape, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every shape whose box (widened by half a step) "
                     "holds it, and given to the first that holds it.",
            "precinct_properties": dict({
                "name": "the precinct's name (UC 95 E, part 02): the Secretary's table's name for the precinct and the part's number",
                "county": "county id", "precinct": "the precinct's name in the Secretary's table", "part": "the part's number in the table",
                "whole": "true on a whole precinct added where the parts do not cover it", "as_of": "on a whole precinct, the year its lines were last changed",
                "mcd": "city or town (absent in open country)", "ward": "list: the city ward the part lies in, where the table's words give its number",
                "house": "House district", "senate": "Senate district", "cd": "congressional district", "judicial": "judicial district",
                "psc": "public service commissioner district (" + ", ".join(f"PSC{n} {n}" for n in range(1, 6)) + ")",
                "split": "on a part whose district the table leaves blank: each district's share in percent, where a second holds 3 percent or more",
                "school": "list: the school districts the part lies in, elementary or K-12 first, largest share first, then any high school district",
                "school_pct": "list, when the part is in more than one: each district's share of its area, in percent",
                "school_out": "percent of the part's area that lies in no elementary or K-12 district (given from 3 percent up)",
                "school_edge": "list: neighbouring districts that only brush the part along a line (try them too when placing a point)",
                "c": "a point inside the part's largest piece, for a label: [longitude, latitude]"}, **SAID_WORDS),
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "MT", "county": "the county's five-digit code (30009)",
                    "mcd": "MT-M- and the Census Bureau's place code (MT-M-61525); properties.t says city, town or consolidated city-county",
                    "ward": "<city>|Ward <number> (MT-M-61525|Ward 1)", "house": "the district (55)", "senate": "the district (28)",
                    "cd": "the district (2); properties.race is the race for Congress", "judicial": "JD and the district (JD22)",
                    "school": "MT-S- and the Office of Public Instruction's legal entity number (MT-S-0861); properties.t says elementary, high school or "
                              "K-12, properties.nces the federal district code"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(stype, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": plans,
        "polling_places": polls,
        "counts": {"precincts": len(allpre), "parts": len(pre), "whole_precincts_added": len(wpre), "precincts_in_the_table": len({(p["county"], p["precinct"]) for p in pre}),
                   "counties": len(counties), "split_between_school_districts": split, "rings_too_small_for_the_grid": dropped_rings,
                   "lines_with_a_part_on_one_side": lone, "with_a_part_across": len(seam), "on_the_state_line": len(on_edge),
                   "sliver_rings_left_out": slivers, "points_given_up_where_two_parts_overlapped": dict(gave), "table_rows_odd": table_odd,
                   "parts_cover_percent_of_montana": round(100 * sum(area_p.values()) / sum(area_c.values()), 2)},
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
        f"({sum(l['bytes'] for l in layers) / 1e6:.1f} MB), {len(stype)} school district files ({school_bytes / 1e6:.1f} MB), "
        f"index {files['index.json']['bytes'] / 1e3:.0f} KB; {total / 1e6:.1f} MB in all, in {final}")
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Montana races have a shape"
        + (f", {sum(check['named_by_the_precinct'].values())} more are named by the precinct (psc)" if check["named_by_the_precinct"] else "")
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Montana ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's shape lies in, the city or town at the point (None in open country), and
    # the federal codes (NCES) of the elementary and high school districts at the point. County, place, 2026 legislative
    # districts, congressional district and school districts are the Census Bureau's geocoder's answer for those
    # coordinates (asked 2026-10-02), an answer that owes nothing to the files tested here.
    ("the State Capitol, Helena", -112.0182, 46.5857, {"county": "30049", "senate": "41", "house": "82", "cd": "2"}, "MT-M-35600", ("3000005", "3013830")),
    ("Billings City Hall", -108.5055, 45.7845, {"county": "30111", "senate": "24", "house": "47", "cd": "2"}, "MT-M-06550", ("3003870", "3003900")),
    ("Missoula City Hall", -113.9957, 46.8730, {"county": "30063", "senate": "50", "house": "100", "cd": "1"}, "MT-M-50200", ("3018570", "3018540")),
    ("Bozeman City Hall", -111.0335, 45.6805, {"county": "30031", "senate": "29", "house": "57", "cd": "1"}, "MT-M-08950", ("3004560", "3004590")),
    ("the Great Falls Civic Center", -111.3010, 47.5045, {"county": "30013", "senate": "10", "house": "19", "cd": "2"}, "MT-M-32800", ("3013040", "3013050")),
    ("Kalispell City Hall", -114.3105, 48.1985, {"county": "30029", "senate": "4", "house": "7", "cd": "1"}, "MT-M-40075", ("3015450", "3015420")),
    ("the Butte-Silver Bow courthouse", -112.5365, 46.0150, {"county": "30093", "senate": "36", "house": "72", "cd": "1"}, "MT-M-11397", ("3005280", "3005310")),
    ("downtown Havre", -109.6830, 48.5500, {"county": "30041", "senate": "14", "house": "27", "cd": "2"}, "MT-M-35050", ("3013560", "3013590")),
    ("Jordan, Garfield County", -106.9100, 47.3205, {"county": "30033", "senate": "18", "house": "35", "cd": "2"}, "MT-M-39925", ("3015340", "3011880")),
    ("Pablo, Lake County", -114.1190, 47.6000, {"county": "30047", "senate": "8", "house": "15", "cd": "1"}, None, ("3022790", "3022800")),
    ("Red Lodge, Carbon County", -109.2470, 45.1855, {"county": "30009", "senate": "28", "house": "55", "cd": "2"}, "MT-M-61525", ("3022080", "3022110")),
    ("a ranch road south of Nye, Stillwater County", -109.80, 45.40, {"county": "30095", "senate": "28", "house": "56", "cd": "2"}, None, ("3019530", "3001740")),
]
LINE_POINTS = [("the Missoula-Ravalli county line south of Lolo", -114.08, 46.68, ("30063", "30081")),
               ("the Yellowstone-Stillwater county line west of Laurel", -108.90, 45.70, ("30111", "30095"))]
LAYER_SLACK = 0.01                # the layers come from other files than the parts: this share of points may disagree


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
    ids, county_of, whole = set(), {}, set()
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        geoms = doc["objects"]["precincts"]["geometries"]
        total += len(geoms)
        ids |= {g["id"] for g in geoms}
        whole |= {g["id"] for g in geoms if g["properties"].get("whole")}
        county_of.update({g["id"]: c["id"] for g in geoms})
        first_whole = next((i for i, g in enumerate(geoms) if g["properties"].get("whole")), len(geoms))
        ok = (len(geoms) == c["precincts"] == len(index["boxes"][c["id"]]) // 4 and len(doc["arcMask"]) == len(doc["arcs"])
              and len(doc["arcSides"]) == 2 * len(doc["arcs"]) and all(g["type"] in ("Polygon", "MultiPolygon") for g in geoms)
              and doc["arcKinds"] == index["arc_kinds"] and all(g["properties"].get("whole") for g in geoms[first_whole:]))
        if not check(ok, f"{c['file']} does not fit the index, or a whole precinct comes before a part"):
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
            if (r >= 0 and r >= first_whole) or (l >= 0 and l >= first_whole):
                bad_mask += masks[a] != 0
                continue
            for bit, kind in enumerate(doc["arcKinds"]):
                if r >= 0 and l >= 0:
                    want = own(geoms[r], kind) != own(geoms[l], kind)
                elif min(r, l) == -2:
                    want = own(geoms[max(r, l)], kind) is not None
                else:
                    continue
                bad_mask += bool(masks[a] & (1 << bit)) != want
    check(total == index["counts"]["precincts"] == len(ids), "the county files do not hold as many shapes as the index says, each with its own id")
    shapes_seen, layer_ids = 0, {}
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        layer_ids[L["kind"]] = {g["id"] for g in gs}
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == 56, "there are not 56 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the shapes on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == 50 and len(layer_ids.get("house", ())) == 100 and len(layer_ids.get("judicial", ())) == 22
          and layer_ids.get("cd") == {"1", "2"} and len(layer_ids.get("county", ())) == 56,
          "there are not 50 Senate districts, 100 House districts, 22 judicial districts, 2 congressional districts and 56 counties")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} shapes ({len(whole)} whole precincts), every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every part is found again from a point inside it; every whole precinct from a point the parts leave uncovered;
    #    every id a shape carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = [], 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place = collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "ward": "ward"}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    split_ids = {s["id"] for s in index["check"].get("split_precincts", [])}
    whole_found = whole_tried = 0
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        geoms = doc["objects"]["precincts"]["geometries"]
        for i, g in enumerate(geoms):
            polys = G.geom_polys(lines, g)
            pr = g["properties"]
            if pr.get("whole"):
                rings = [r for poly in polys for r in poly]
                xs, ys = [p[0] for r in rings for p in r], [p[1] for r in rings for p in r]
                spot = None
                for n in range(1, 400):                      # a point of the precinct no part holds: a scan of a 20 by 20 grid over its box
                    x = min(xs) + (max(xs) - min(xs)) * ((n % 20) + 0.5) / 20
                    y = min(ys) + (max(ys) - min(ys)) * ((n // 20) + 0.5) / 20
                    if not G.in_rings(x, y, rings):
                        continue
                    lon, lat = x * G.SCALE + G.ORIGIN[0], y * G.SCALE + G.ORIGIN[1]
                    f, _n = locate(files, lon, lat)
                    if f and f["geometry"]["id"] == g["id"]:
                        spot = (lon, lat)
                        break
                whole_tried += 1
                whole_found += spot is not None
                continue
            px, py = G.label_point(polys[0])
            lon, lat = px * G.SCALE + G.ORIGIN[0], py * G.SCALE + G.ORIGIN[1]
            found, _near = locate(files, lon, lat)
            tested += 1
            if not found or found["geometry"]["id"] != g["id"]:
                wrong.append((g["id"], found and found["geometry"]["id"]))
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the part lies in" if sid in pr["school"] else "in a district the part only brushes" if sid else
                   "in none, in a part partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            place["the part's own city or town" if shape and shape["id"] == pr.get("mcd") else
                  "open country, as the part says" if not shape and not pr.get("mcd") else
                  "inside the limits of a city the part does not name" if shape and not pr.get("mcd") else
                  "outside the limits of the city the part names" if not shape else "in another city"] += 1
            if g["id"] not in split_ids:
                for prop, kind in layer_for.items():
                    if kind not in layer_ids or (i % 3 and kind != "ward"):
                        continue
                    shape, edge = G.shape_at(files, kind, lon, lat)
                    if shape is None and pr.get(prop) is None:
                        continue
                    if shape is not None and edge <= tol_of[kind] + 10:
                        skipped += 1
                        continue
                    asked[kind] += 1
                    mine = pr.get(prop)
                    if shape is not None and (shape["id"] in mine if isinstance(mine, list) else shape["id"] == mine):
                        agree += 1
                    else:
                        disagree[kind].append((g["id"], shape and shape["id"], mine))
    check(len(wrong) <= max(3, tested // 500), f"{len(wrong)} of {tested} precinct parts are not found again from a point inside them, e.g. {wrong[:4]}")
    check(whole_found == whole_tried, f"only {whole_found} of {whole_tried} whole precincts are found from a point no part holds")
    check(not sum(no_shape.values()), f"parts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(3, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the part at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} parts' own points fall in no school district though the part is said to lie in one")
    say(f"      self-test: {tested - len(wrong):,} of {tested:,} precinct parts found again from a point inside them, and {whole_found} of {whole_tried} whole "
        f"precincts from a point no part holds; every id a part carries is a shape; layers agree at {agree:,} of {sum(asked.values()):,} points "
        f"({skipped} too near a line to ask" + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items()))
        + "); school district at each part's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1]))
        + "; city or town at each part's point (the Library's city limits against the table's word): "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    nces = {g["id"]: g["properties"].get("nces") for g in files.topo("layers/school.json")[0]["objects"]["school"]["geometries"]}
    for name, lon, lat, want, mcd, (elem, high) in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct part"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        codes = {nces.get(s) for s in pr["school"]}
        sid = G.school_at(files, found["geometry"], lon, lat)
        ok &= check(elem in codes and high in codes and nces.get(sid) == elem, f"{name}: the part's school districts are {sorted(c for c in codes if c)} and the one at the point "
                    f"{nces.get(sid)}; the geocoder says {elem} and {high}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check((shape and shape["id"]) == mcd and pr.get("mcd") == mcd, f"{name}: the mcd layer gives {shape and shape['id']} and the part {pr.get('mcd')}; the place is {mcd}")
        for prop, kind in layer_for.items():
            if kind in layer_ids and pr.get(prop) is not None:
                shape2, _edge = G.shape_at(files, kind, lon, lat)
                mine = pr.get(prop)
                ok &= check(shape2 is not None and (shape2["id"] in mine if isinstance(mine, list) else shape2["id"] == mine),
                            f"{name}: layer {kind} gives {shape2 and shape2['id']}, the part says {mine}")
        fdoc, _l = files.topo(rel[found["county"]])
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {fdoc['names'].get('mcd', {}).get(pr.get('mcd'), 'open country')}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, {pr['judicial']}, {pr['psc']}, "
            f"{', '.join(fdoc['names']['school'].get(s, s) for s in pr['school'])}" + (f", {', '.join(w.split('|')[1] for w in pr['ward'])}" if pr.get("ward") else "")
            + (" (a whole precinct)" if pr.get("whole") else "") + f"; {found['edge']:.0f} m from the shape's line")

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

    # 5. polling places say what they are, and name only shapes and places that are there
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values())
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])) and not set(polls["precinct"]) & set(polls["no_place"]),
              "polling_places.json names a shape or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        inside = 0
        for p in polls["places"]:
            if p.get("lonlat"):
                f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
                inside += bool(f3) and f3["county"] in {county_of[v] for v in p["precincts"]}
        say(f"      self-test: polling places: {polls.get('status')}; {len(polls['places']):,} places, {sum(1 for p in polls['places'] if p.get('lonlat')):,} with a point "
            f"({inside:,} of them inside the county of a precinct that votes there); {len(polls['precinct']):,} shapes have one place, {len(polls['no_place']):,} several")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Montana's ballot map -> ballot_geo/mt/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/mt)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask the map services and the Secretary's page again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
