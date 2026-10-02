"""
ballot/ne_geo.py - the geography behind Nebraska's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py, ballot/sd_geo.py, ballot/oh_geo.py and ballot/mo_geo.py for the few things those
states added, and changes nothing in any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read
them all.

    python ballot/ne_geo.py                 builds ballot_geo/ne/ and runs the self-test (the first build downloads
                                            130 MB of Census files and lays districts over precincts: allow ten minutes)
    python ballot/ne_geo.py --selftest      runs the self-test on the files already built
    python ballot/ne_geo.py --refresh       asks the map services, the statutes and the polling place list again
    python ballot/ne_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

What Nebraska publishes, and what that does to the files
--------------------------------------------------------
Nebraska has no statewide map file of its precincts as they stand in 2026: each county's election office keeps its
own, and the Secretary of State publishes district lines, not precinct lines. The only statewide precinct lines a
script may read are the Census Bureau's 2020 voting districts: the precincts the counties reported for the 2020 census
(1,402 of them). So a shape here is a 2020 voting district, cut wherever a line of the 2021 districts crosses it, and
index.json says so in plain words: a county may have redrawn the precinct since. (Douglas, Sarpy and Lancaster counties
publish their current precinct lines on their own map services; they are not used for the fabric here, because a
county's own drawing does not meet its neighbours' census lines point for point. That would be the next step.) What a
ballot depends on does not depend on the precinct: the county, the legislative and congressional districts, the court
districts, the districts of the Public Service Commission, the Board of Regents and the State Board of Education, the
city, village or township, the school district, the natural resources district, the educational service unit, the
community college area and (in three counties) the county board district at a point are each taken from a current
official file.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ne_local/)
----------------------------------------------------------------------------------------------------------------------
  - Census blocks: the Census Bureau's TIGER/Line 2020 tabulation blocks of Nebraska (tl_2020_31_tabblock20.zip,
    119,103 blocks). Only each block's number, outline and area are read.
  - Which voting district a block is in: the Bureau's 2020 Block Assignment File (BlockAssign_ST31_NE.zip, the VTD
    table), and the voting districts' names from tl_2020_31_vtd20.zip.
  - Which legislative district a block is in: the Bureau's 2024 State Legislative District Block Equivalency File
    (sldu24.zip): the 49 districts of the one-house Legislature, enacted in 2021 (LB 3). Which congressional district:
    the Bureau's 119th Congress Block Equivalency File (cd119.zip): the three districts enacted in 2021 (LB 1). A block
    is in exactly one district, so these lines are exact.
  - Supreme Court judicial districts (six; a Court of Appeals judge is appointed from each, section 24-1101), Public
    Service Commission districts (five), Board of Regents districts (eight) and State Board of Education districts
    (eight): the Secretary of State's own shapefiles of the maps the Legislature enacted in 2021 (SUP21-39001,
    PSC21-39001, REG21-39003 as updated 11-24-21, ED21-39003; sos.nebraska.gov, "District & Subdivision Maps"). Those
    plans were built from 2020 census blocks, so a block is in the district that holds a point inside it. The same
    rule applied to the Secretary's legislative shapefile (LEG21-39006) gives the Census Bureau's own answer for every
    one of 119,103 blocks (2026-10-02); every build repeats that comparison and stops if more than one block in a
    thousand differs.
  - District court judicial districts and county judge districts (twelve each, whole counties; they differ: Otoe and
    Fillmore counties): Neb. Rev. Stat. 24-301.02 and 24-503 on nebraskalegislature.gov. The lines are the county lines.
  - Community college areas (six): Neb. Rev. Stat. 85-1504. Whole counties, except that nine voting districts of
    Cherry County and six precincts of Boone County "as they existed on July 1, 1975" belong to another area. See
    COMMUNITY COLLEGE AREAS.
  - Cities and villages: TIGER/Line 2025 places (tl_2025_31_place.zip; incorporated, active places only). Townships,
    the county lines and the state's outline: TIGER/Line 2025 county subdivisions (tl_2025_31_cousub.zip). Only the
    townships the Bureau marks as functioning governments (the counties with township organization, and Washington
    County's numbered townships) are places here; elsewhere a county subdivision is an election precinct of the
    Bureau's own, with no officers.
  - School districts: TIGER/Line 2025 unified school districts (tl_2025_31_unsd.zip, 245 districts as the State
    reported them to the Bureau for the 2024-25 school year). The ballot database's school ids are the Bureau's codes.
    (The State's own "School Districts" layer was derived from 2018 parcels and is older.)
  - Natural resources districts (23): "Natural Resource District (NRD) Boundaries" on the State of Nebraska's GIS site
    (gis.ne.gov; NebraskaMAP). Only the district's name is asked for.
  - Educational service units (17): "Educational Service Units" on the same site (Nebraska Department of Education).
    Only the unit's number is asked for; the layer's address and phone columns never are.
  - County board districts, each from the county's own map service, asking only for the district number (the layers'
    member names are never requested): Douglas County (the Election Commission's "Political_Subdivisions" service,
    layer "Douglas County Board", seven districts), Lancaster County (the Election Commission's "Elections" service on
    the City of Lincoln's GIS, layer "County Board Dist", five districts; on 2026-10-02 the county's own precinct
    table, which it updates every year, named the same board district as this layer at 217 of 222 precincts, the rest
    being precincts the table itself splits) and Sarpy County ("ElectionAdmin", layer "County Commissioners", five).
  - City wards: Sarpy County's "City Ward" layer (Bellevue, Gretna, La Vista, Papillion) and the Douglas County
    Election Commission's "City Council Bennington" and "City Council Ralston" layers. Only the city's name and the
    ward's number are asked for.
  - Subdistricts of the Papio-Missouri River Natural Resources District and districts of the Metropolitan Community
    College board, inside Douglas and Sarpy counties only: the same two county services. No layer draws them; a
    precinct there names its own (nrd_area, college_area).
    These three counties' layers are read as the Secretary's plans are: a census block is in the district that holds a
    point inside it, and a voting district is cut wherever such a line crosses it, so that a piece lies in one board
    district, one subdistrict and one college district.
  - Polling places: Sarpy County's "Polling Places" layer, whose every row carries the date of the next election it is
    for. See POLLING PLACES.

What is built (ballot_geo/ne/): index.json, manifest.json, precincts/<county>.json (93), layers/<kind>.json (state,
county, cd, senate, judicial, mcd, ward, com, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes. Nebraska's Legislature has one house: its 49 districts are the "senate" layer and there is
no "house" layer. Coordinates are on the same grid (0.00001 degree, translate [-98, 43]; Nebraska lies south of 43
north and mostly west of 98 west, so its grid numbers are negative, which TopoJSON allows).

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "NE" (j = "31", the jurisdiction_id of statewide races)
  county    "31055"                 sl_places county id; jurisdiction_id of county offices and juvenile court judges
  mcd       "NE-M-03950"            NE-M- and the Census code: a city's or village's place code, a township's county
                                    subdivision code (properties.t says which)
  ward      "NE-M-03950|Ward 2"     <city>|<ward as the council race words it>
  com       "31055|District 2"      <county>|<district as the board race words it>: Douglas, Lancaster and Sarpy
  senate    "10"   cd "2" (properties.race is the federal race id, 2026-NE-H02)
  judicial  "NE-DC4"                the district court judicial district (d = "4")
  school    "NE-S-74820"            NE-S- and the Census Bureau's five-digit district code

A precinct also names, with no layer to draw them (the page reads them from the precinct): county_court ("NE-CC4", the
county judge district), appeals ("NE-COA2", the Supreme Court judicial district a Court of Appeals judge sits for),
psc ("NE-PSC2"), regents ("NE-REG4"), sboe ("NE-SBOE8"), nrd ("NE-X-papio-missouri-river-natural-resources-district"),
esu ("NE-X-educational-service-unit-no-3") and college ("NE-X-metropolitan-community-college"): each the id its
races carry as jurisdiction_id, or would.

Not drawn, because no statewide file has the lines: county board districts outside the three counties above, city
wards outside the six cities above, school board wards, the subdistricts of 22 natural resources districts, the
districts of the educational service units and of five community college areas, public power districts and their
subdivisions (the State's "Power Districts" layer is who delivers electricity where, not who votes for which board:
the Nebraska Public Power District's chartered territory covers places other districts serve), reclamation districts,
the Metropolitan Utilities District, the Learning Community and the Omaha transit board. index.json lists every race
without a shape under "check", with the reason.

COMMUNITY COLLEGE AREAS
-----------------------
Section 85-1504 gives 91 counties whole to one area each. In Cherry County the voting districts of "Merriam, Russell,
King, Mother Lake, Cody, Barley, Gillaspie, Lackey, and Calf Creek ... as such voting districts existed on July 1,
1975" are in the Western area and the rest of the county in Mid-Plains; in Boone County the precincts of "North
Oakland, South Oakland, Ashland, North Branch, Shell Creek, and Midland" as they existed in 1975 are in the Northeast
area and the rest in Central. No file has the 1975 lines. The 2020 voting districts of Cherry County still carry eight
of the nine names (Merriman for the statute's "Merriam"; no Calf Creek), and Boone County's carry "Oakland" and "North
Branch-Shell Creek" (no Ashland, no Midland). COLLEGE_PARTS sets out those same-name pairs, one by one; a 2020 voting
district of one of those names is given the statute's area, every other one the county's main area, and index.json
says that this is a reading of names, 45 years apart, and that the county clerk is the authority. Every build checks
that the statute still reads as COLLEGE_PARTS expects and that the 2020 names are still there.

POLLING PLACES
--------------
Nebraska has no statewide list of polling places a script may read: the Secretary of State's VoterCheck answers for
one voter at a time, and each county election office publishes its own list. So there is nothing for John to save for
the whole state. One office publishes its list as an open map layer that says which election it is for: Sarpy
County's "Polling Places" (each row's NEXTELECT is November 3, 2026), with its "Voting Precincts" table saying which
place each of the county's current precincts votes at. That layer is read here (place number, name, street address,
city, hours and the county's own point; a polling place is a public building; the layer's contact, phone and e-mail
columns are never requested), and polling_places.json lists the other 92 counties as not on the list. The map's
precinct lines are the 2020 ones and Sarpy County renumbered its precincts in 2021, so no map precinct is tied to a
place; the list is given by the county's own precincts (by_county). The layer carries two address columns that
disagree in some rows; the one read is FULLADD. The file is marked "unchecked", which a page must not show, until a
person has compared it with the Sarpy County Election Commission's own list and set POLL_CHECKED to True. Lancaster
County's service has a polling place layer too, with no date on it, and Douglas County publishes its list as web
pages; neither is read, because each would have to be shown to be the November 3, 2026 list first.
"""

import argparse
import collections
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
from ballot import mo_geo as M  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "NE", "31", "Nebraska"
N_COUNTIES, N_LEG, N_CD, N_COURT = 93, 49, 3, 12
OUT = os.path.join(HERE, "ballot_geo", "ne")
CACHE = os.path.join(HERE, "states_cache", "ne_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://www.votercheck.necvr.ne.gov/VoterView/"

CENSUS = "https://www2.census.gov/"
BLOCK_URL = CENSUS + "geo/tiger/TIGER2020/TABBLOCK20/tl_2020_31_tabblock20.zip"
BAF_URL = CENSUS + "geo/docs/maps-data/data/baf2020/BlockAssign_ST31_NE.zip"
VTD_URL = CENSUS + "geo/tiger/TIGER2020PL/STATE/31_NEBRASKA/31/tl_2020_31_vtd20.zip"
SLDU_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip"
CD_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/119-congressional-district-befs/cd119.zip"
COUSUB_URL = CENSUS + "geo/tiger/TIGER2025/COUSUB/tl_2025_31_cousub.zip"
PLACE_URL = CENSUS + "geo/tiger/TIGER2025/PLACE/tl_2025_31_place.zip"
UNSD_URL = CENSUS + "geo/tiger/TIGER2025/UNSD/tl_2025_31_unsd.zip"
COUNTY_URL = CENSUS + "geo/docs/reference/codes2020/cou/st31_ne_cou2020.txt"
SHARED = ("sldu24.zip", "cd119.zip")                       # national files another state's build may already have fetched

# The Secretary of State's shapefiles of the maps enacted in 2021: property -> (file on sos.nebraska.gov, how many
# districts, the id's prefix, what the district is called, the plan's own name)
SOS_PAGE = "https://sos.nebraska.gov/elections/district-subdivision-maps"
SOS_FILES = "https://sos.nebraska.gov/sites/default/files/doc/"
PLANS = collections.OrderedDict([
    ("appeals", ("SUP21-39001.zip", 6, "NE-COA", "Supreme Court Judicial District", "SUP21-39001")),
    ("psc", ("PSC21-39001.zip", 5, "NE-PSC", "Public Service Commission District", "PSC21-39001")),
    ("regents", ("REG21-39003%20Updated%2011-24-21_1.zip", 8, "NE-REG", "Board of Regents District", "REG21-39003 (updated 11-24-21)")),
    ("sboe", ("ED21-39003.zip", 8, "NE-SBOE", "State Board of Education District", "ED21-39003")),
])
LEG_FILE = "LEG21-39006.zip"                               # read only to check the rule the four plans above are read by
LEG_SLACK = 0.001                                          # the share of blocks that rule may place otherwise than the Census Bureau's file

STATUTE = "https://nebraskalegislature.gov/laws/statutes.php?statute="
COURTS = {"judicial": ("24-301.02", "NE-DC", "District Court Judicial District"), "county_court": ("24-503", "NE-CC", "County Judge District")}
COLLEGE_LAW = "85-1504"
# The 1975 voting districts section 85-1504 names, and the 2020 voting district of the same name (None: no 2020 voting
# district of the county carries the name). county -> (the area they belong to, {the statute's name: the 2020 name})
COLLEGE_PARTS = {
    "31031": ("Western", {"Merriam": "Merriman", "Russell": "Russell", "King": "King", "Mother Lake": "Mother Lake", "Cody": "Cody", "Barley": "Barley",
                          "Gillaspie": "Gillaspie", "Lackey": "Lackey", "Calf Creek": None}),
    "31011": ("Northeast", {"North Oakland": "Oakland", "South Oakland": "Oakland", "Ashland": None, "North Branch": "North Branch-Shell Creek",
                            "Shell Creek": "North Branch-Shell Creek", "Midland": None}),
}
COLLEGE_MAIN = {"31031": "Mid-Plains", "31011": "Central"}

STATE_GIS = "https://gis.ne.gov/Enterprise/rest/services/"       # the State of Nebraska's GIS site (NebraskaMAP)
NRD_SERVICE = STATE_GIS + "NaturalResourcesDistrictBoundaries/FeatureServer/0"
NRD_ITEM = "https://www.nebraskamap.gov/datasets/4ba353be6a794e379f90391e54ab6a42"
ESU_SERVICE = STATE_GIS + "Educational_Service_Units/FeatureServer/0"
ESU_ITEM = "https://www.nebraskamap.gov/datasets/347a4e7a03554415b9bd73f456917745"
DOUGLAS = "https://services.arcgis.com/pDAi2YK0L0QxVJHj/arcgis/rest/services/Political_Subdivisions/FeatureServer/"
SARPY = "https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/ElectionAdmin_BV_vw/FeatureServer/"
LINCOLN = "https://gis.lincoln.ne.gov/public/rest/services/Planning/Elections/MapServer/"
DOUGLAS_SAYS = ("The Douglas County Election Commission's political subdivision lookup uses this service; its own account says it was updated 8/2/2022.")

# County board districts: county -> (service, the district's column, how many, source id, who publishes it, the
# layer's title, what it says of itself). Only the district's column is asked for.
BOARDS = {
    "31055": (DOUGLAS + "8", "DISTRICT", 7, "ne-douglas-county-election-commission-county-board", "Douglas County Election Commission (Douglas-Omaha GIS)",
              "Political_Subdivisions, layer Douglas County Board", DOUGLAS_SAYS),
    "31109": (LINCOLN + "1", "CBDIST10_I", 5, "ne-lancaster-county-election-commission-county-board", "Lancaster County Election Commission (City of Lincoln GIS)",
              "Elections, layer County Board Dist",
              "A graphical representation of the Lancaster County Board District Boundaries, updated every 10 years as part of the U.S. Census."),
    "31153": (SARPY + "6", "DISTRICTID", 5, "ne-sarpy-county-election-county-commissioners", "Sarpy County, Nebraska (GIS)",
              "ElectionAdmin, layer County Commissioners", "Administrative data supporting elections."),
}
# City wards: (service, the city's column or the city itself, the ward's column, source id, who publishes it, the layer's title)
WARDS = [
    (SARPY + "8", ("column", "CITY"), "DISTRICTID", "ne-sarpy-county-election-city-wards", "Sarpy County, Nebraska (GIS)", "ElectionAdmin, layer City Ward"),
    (DOUGLAS + "5", ("city", "Bennington"), "Ward_Name", "ne-douglas-county-election-commission-bennington-wards", "Douglas County Election Commission (Douglas-Omaha GIS)",
     "Political_Subdivisions, layer City Council Bennington"),
    (DOUGLAS + "6", ("city", "Ralston"), "LABEL", "ne-douglas-county-election-commission-ralston-wards", "Douglas County Election Commission (Douglas-Omaha GIS)",
     "Political_Subdivisions, layer City Council Ralston"),
]
# Parts of a district that a county's own service draws inside that county: (precinct property, a word of the
# district's name, county, service, the part's column, the part as its races word it, source id, publisher, title)
AREAS = [
    ("nrd", "papio-missouri-river", "31055", DOUGLAS + "14", "LABEL", "Subdistrict", "ne-douglas-county-election-commission-papio-nrd",
     "Douglas County Election Commission (Douglas-Omaha GIS)", "Political_Subdivisions, layer Papio Missouri Natural Resources District"),
    ("nrd", "papio-missouri-river", "31153", SARPY + "15", "DISTRICTID", "Subdistrict", "ne-sarpy-county-election-papio-nrd",
     "Sarpy County, Nebraska (GIS)", "ElectionAdmin, layer Papio NRD"),
    ("college", "metropolitan", "31055", DOUGLAS + "10", "LABEL", "District", "ne-douglas-county-election-commission-mcc",
     "Douglas County Election Commission (Douglas-Omaha GIS)", "Political_Subdivisions, layer Metropolitan Community College Board"),
    ("college", "metropolitan", "31153", SARPY + "12", "DISTRICTID", "District", "ne-sarpy-county-election-mcc",
     "Sarpy County, Nebraska (GIS)", "ElectionAdmin, layer Metro Community College"),
]
POLL_SERVICE = SARPY + "0"
POLL_FIELDS = "NAME,POLLINGID,FULLADD,CITY,OPERHOURS,NEXTELECT,fulladdr"      # never CONTACT, PHONE, EMAIL, pocname, pocphone, pocemail
POLL_PCT_SERVICE = SARPY + "2"
POLL_PCT_FIELDS = "PRECINCTID,NAME,pollingid"
POLL_ITEM = "https://www.arcgis.com/home/item.html?id=070092b0b92b48be832bd0dccfe150e6"
POLL_COUNTY = "31153"
POLL_TITLE = "Election - Polling Places (Sarpy County, Nebraska), next election November 3, 2026"
POLL_CHECKED = False              # True only when a person has compared the list with the Sarpy County Election Commission's own

ARC_KINDS = ["county", "senate", "cd", "judicial"]         # the kinds a precinct lies wholly inside, so its lines can draw them
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM, MCD_THICK = I.TOL_MCD, I.MCD_ZOOM, I.MCD_THICK
NEAR_M = G.NEAR_M
AREA_SLACK = 0.02                 # a county's 2020 blocks and the Bureau's 2025 county may differ in area by this share
WATER = "ZZZZZZ"                  # the Bureau's "voting district not defined" (Nebraska has none; kept so a new file cannot slip one in)
PLACE_WORD = {"25": "city", "47": "village"}
TOWN_LSAD = ("44", "45")          # township; Washington County's numbered townships
PIP_STEP = 20000                  # the bands (in 1e-7 degree of latitude) the plans' edges are filed under

clean, slug, title, fold = N.clean, N.slug, M.title, M.fold


# ---------------------------------------------------------------- the Secretary's plans: which district holds a point

class Plan:
    """The districts of one plan, each edge filed under the bands of latitude it crosses, so that the district at a
    point is found by looking at one band's edges only."""

    def __init__(self, shapes):                             # [(district, rings of (x, y) in 1e-7 degree)]
        self.keys = [k for k, _r in shapes]
        self.bands = collections.defaultdict(list)
        for i, (_k, rings) in enumerate(shapes):
            for pts in rings:
                xj, yj = pts[-1]
                for xi, yi in pts:
                    if yi != yj:
                        lo, hi = (yi, yj) if yi < yj else (yj, yi)
                        for b in range(lo // PIP_STEP, hi // PIP_STEP + 1):
                            self.bands[b].append((xi, yi, xj, yj, i))
                    xj, yj = xi, yi

    def at(self, x, y):
        """The districts holding the point (even-odd, so a district's holes and islands need no care)."""
        odd = collections.Counter()
        for xi, yi, xj, yj, i in self.bands.get(int(y) // PIP_STEP, ()):
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                odd[i] += 1
        return [self.keys[i] for i, n in odd.items() if n % 2]


def read_plan(path, n):
    """One of the Secretary's shapefiles: [(district number as text, rings)], checked to be districts 1 to n in
    longitude and latitude. Only the DISTRICT column is read."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(m for m in z.namelist() if m.lower().endswith(".shp"))[:-4]
    prj = z.read(base + ".prj").decode("utf-8", "replace")
    if not prj.startswith('GEOGCS["GCS_North_American_1983"'):
        raise GeoError(f"    {os.path.basename(path)}: the shapefile is no longer in longitude and latitude (NAD 83); stopping")
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    out = []
    for sr in r.iterShapeRecords():
        d = str(sr.record["DISTRICT"]).strip()
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        rings = [[G.vxy(k) for k in ks] for ks in (G.clean_ring(pts[parts[i]:parts[i + 1]]) for i in range(len(parts) - 1)) if ks]
        out.append((d, rings))
    if sorted(d for d, _r in out) != sorted(str(i) for i in range(1, n + 1)):
        raise GeoError(f"    {os.path.basename(path)}: the districts are {sorted(d for d, _r in out)}, not 1 to {n}; stopping")
    return out


# ---------------------------------------------------------------- precincts: 2020 voting districts, from census blocks

def read_tables(bafpath, upath, cdpath, vpath):
    """{block: (county, voting district code, legislative district, congressional district)} for every block in a
    voting district, the blocks in none, and {(county, code): the voting district's name}."""
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

    up, cd = bef(upath, "GEOID,SLDUST"), bef(cdpath, "GEOID,CDFP")
    if set(up) != set(vtd) or set(cd) != set(vtd):
        raise GeoError("    the block assignment file and the legislative and congressional equivalency files do not list the same blocks; stopping")
    table, water = {}, set()
    for b, (c, v) in vtd.items():
        if v == WATER or not v:
            water.add(b)
            continue
        s, d = re.sub(r"^0+", "", up[b]), re.sub(r"^0+", "", cd[b])
        if not (b[:5] == FIPS + c and re.fullmatch(r"[0-9A-Za-z-]{1,6}", v) and re.fullmatch(r"\d{1,2}", s) and re.fullmatch(r"[1-3]", d)):
            raise GeoError(f"    block {b}: county {c!r}, voting district {v!r}, Legislature {up[b]!r}, Congress {cd[b]!r} do not fit the layout this builder was checked against; stopping")
        table[b] = (FIPS + c, v, s, d)
    seen = [{t[i] for t in table.values()} for i in (2, 3)]
    if [len(x) for x in seen] != [N_LEG, N_CD]:
        raise GeoError(f"    the equivalency files give {len(seen[0])} legislative and {len(seen[1])} congressional districts, not {N_LEG} and {N_CD}; stopping")
    import shapefile
    zz = zipfile.ZipFile(vpath)
    base = next(n for n in zz.namelist() if n.endswith(".dbf"))
    vname = {(FIPS + r["COUNTYFP20"], r["VTDST20"].strip()): r["NAME20"] for r in (x.as_dict() for x in shapefile.Reader(dbf=io.BytesIO(zz.read(base))).iterRecords())}
    missing = {(c, v) for c, v, _s, _d in table.values()} - set(vname)
    if missing:
        raise GeoError(f"    {len(missing)} voting districts of the block assignment file are not in {os.path.basename(vpath)} (e.g. {sorted(missing)[0]}); stopping")
    return table, water, vname


def read_units(blockpath, table, water, vname, plans, leg_plan, local, say):
    """The precincts: the blocks of each 2020 voting district put together, one piece for each set of districts it
    reaches (legislative, congressional, the Secretary's four plans and, in the three counties whose own services draw
    them, the county board district and the parts of the natural resources district and the community college area;
    each block being in the district that holds a point inside it). local: {county: [(property, Plan)]}. Returns
    (pre, polys, said, leg, unplaced): what is said of each piece, its rings as vertex keys, the Bureau's own area of
    the blocks by county, how the same rule fared against the Bureau's legislative file, and how many blocks of those
    three counties lie in no one district of a county's layer (their pieces say nothing of it)."""
    import shapefile
    z = zipfile.ZipFile(blockpath)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    groups, seen, twice = collections.defaultdict(set), set(), 0
    said = {"in": collections.Counter(), "all": collections.Counter()}
    props = list(plans)
    local_props = sorted({prop for v in local.values() for prop, _p in v})
    leg = {"blocks": 0, "same": 0, "differ": []}
    lost, unplaced = collections.Counter(), collections.Counter()
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
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        rings = [ks for ks in (G.clean_ring(pts[parts[i]:parts[i + 1]]) for i in range(len(parts) - 1)) if ks]
        xy = sorted(([G.vxy(k) for k in ks] for ks in rings), key=lambda q: -abs(G.area2(q)))
        px, py = G.label_point(xy)
        mine = []
        for prop in props:
            hit = plans[prop].at(px, py)
            if len(hit) != 1:
                lost[prop] += 1
                hit = [None]
            mine.append(hit[0])
        hit = leg_plan.at(px, py)
        leg["blocks"] += 1
        if hit == [table[b][2]]:
            leg["same"] += 1
        elif len(leg["differ"]) < 20:
            leg["differ"].append(b)
        here = dict(local.get(b[:5], ()))
        for prop in local_props:
            hit = here[prop].at(px, py) if prop in here else [None]
            if len(hit) != 1:
                unplaced[prop] += 1
                hit = [None]
            mine.append(hit[0])
        s = groups[table[b] + tuple(mine)]
        for ks in rings:
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
    if lost:
        raise GeoError(f"    blocks whose inside point lies in no district, or in two, of the Secretary's plans: {dict(lost)}; stopping")
    if leg["blocks"] - leg["same"] > LEG_SLACK * leg["blocks"]:
        raise GeoError(f"    the rule the Secretary's plans are read by (a block is in the district holding a point inside it) places {leg['blocks'] - leg['same']:,} of "
                       f"{leg['blocks']:,} blocks in another legislative district than the Census Bureau's file; stopping")
    pieces = collections.Counter(k[:2] for k in groups)
    order = sorted(groups, key=lambda k: (k[0], k[1]) + tuple(G.natkey(x or "") for x in k[2:]))
    part_no, count = {}, collections.Counter()
    for key in order:
        count[key[:2]] += 1
        part_no[key] = count[key[:2]]
    pre, polys, ids = [], [], set()
    for key in order:
        county, code, senate, cd = key[:4]
        pid = f"{county}.{re.sub(r'[^0-9A-Za-z-]', '-', code)}" + (f".{part_no[key]}" if pieces[key[:2]] > 1 else "")
        if pid in ids:
            raise GeoError(f"    two precincts would share the id {pid}; stopping")
        ids.add(pid)
        name = M.vtd_name(code, vname[(county, code)])
        p = {"id": pid, "county": county, "vtd": code, "precinct": county + code, "senate": senate, "cd": cd,
             "name": name + (f", part {part_no[key]}" if pieces[key[:2]] > 1 else ""), "vtdname": name, "parts": pieces[key[:2]]}
        for prop, d in zip(props, key[4:]):
            p[prop] = f"{PLANS[prop][2]}{d}"
        for prop, d in zip(local_props, key[4 + len(props):]):
            p[prop] = d
        pre.append(p)
        polys.append(S.loops(groups[key]))
    say(f"      {len(seen):,} census blocks ({len(water)} in no voting district) put together into {len(pieces):,} voting districts of 2020, {len(pre):,} pieces once cut by "
        f"the 2021 districts ({sum(1 for n in pieces.values() if n > 1)} voting districts reach more than one); the point-inside rule agrees with the Census Bureau's "
        f"legislative file at {leg['same']:,} of {leg['blocks']:,} blocks"
        + (f"; blocks in no one district of a county's own layer: {dict(unplaced)}" if unplaced else ""))
    return pre, polys, said, leg, dict(unplaced)


def local_plan(rows, key):
    """A county layer's districts as a Plan: rows as mo_geo.fetch_small brings them, key(attributes) the district's id."""
    return Plan([(key(a), [[G.vxy(k) for k in ks] for ks in (G.clean_ring(r) for r in rings) if ks]) for a, rings in rows])


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ne-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def county_names(path):
    import csv
    out = {}
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="|"))
    col = {h: i for i, h in enumerate(rows[0])}
    for r in rows[1:]:
        if r and r[col["STATEFP"]] == FIPS:
            out[FIPS + r[col["COUNTYFP"]]] = r[col["COUNTYNAME"]]
    if len(out) != N_COUNTIES:
        raise GeoError(f"    {os.path.basename(path)}: {len(out)} counties, not {N_COUNTIES}; stopping")
    return out


# ---------------------------------------------------------------- the statutes: court districts, community college areas

def statute(section, path, refresh, say):
    """One section of the Revised Statutes as nebraskalegislature.gov prints it, cut down to its own words (from its
    heading to its source note) and kept in a small cache."""
    if not G._fresh(path, refresh):
        try:
            net.patient_lookups()
            raw = net.get(STATUTE + section, timeout=120)
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<[^>]+>", " ", raw.decode("utf-8", "replace"))))
            m = re.search(rf"{re.escape(section)}\. (.*?) Source ", text)
            if not m:
                raise GeoError(f"    Neb. Rev. Stat. {section}: the page no longer reads as a section with a source note")
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump({"section": section, "url": STATUTE + section, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "text": m.group(1)}, fh, indent=1)
            os.replace(path + ".part", path)
            time.sleep(1.0)
        except Exception as e:  # noqa: BLE001
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                raise
            say(f"      could not read Neb. Rev. Stat. {section} again ({str(e).strip()}); using the copy on disk")
    return json.load(open(path, encoding="utf-8"))


def name_list(text):
    return [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", text) if n.strip()]


def court_districts(doc, cname):
    """{county: district number} from a section that reads "District No. 1 shall contain the counties of ...;"."""
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    out, found = {}, re.findall(r"District No\. (\d+) shall contain the count(?:y|ies) of (.*?)(?:;|\.)", doc["text"])
    for no, names in found:
        for n in name_list(names):
            if n not in by_name or by_name[n] in out:
                raise GeoError(f"    Neb. Rev. Stat. {doc['section']}: {n!r} is not a county, or is in two districts; stopping")
            out[by_name[n]] = no
    if sorted(int(no) for no, _n in found) != list(range(1, N_COURT + 1)) or len(out) != N_COUNTIES:
        raise GeoError(f"    Neb. Rev. Stat. {doc['section']}: {len(found)} districts over {len(out)} counties, not {N_COURT} over {N_COUNTIES}; stopping")
    return out


def college_areas(doc, cname):
    """{county: area} for the counties section 85-1504 gives whole to one community college area. The section's two
    exceptions must read exactly as COLLEGE_PARTS and COLLEGE_MAIN expect, or the build stops."""
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    segs = re.findall(r"\((\d)\) The ([A-Za-z-]+) Community College Area shall consist of the following counties: (.*?)(?=; \(\d\)|; and \(\d\)|$)", doc["text"])
    whole, main, parts = {}, {}, {}
    for _no, area, text in segs:
        text = text.strip().rstrip(".")
        m = re.search(r" and the (?:voting districts|precincts) of (.*?) in ([A-Z][\w ]*?) County as such (?:voting districts|precincts) existed on July 1, 1975$", text)
        if m:
            parts[by_name.get(m.group(2))] = (area, name_list(m.group(1)))
            text = text[:m.start()]
        m = re.search(r" and all of ([A-Z][\w ]*?) County except as provided in subdivision \(\d\) of this section$", text)
        if m:
            main[by_name.get(m.group(1))] = area
            text = text[:m.start()]
        for n in name_list(text):
            m = re.fullmatch(r"([A-Z][\w ]*?) except as provided in subdivision \(\d\) of this section", n)
            if m:
                main[by_name.get(m.group(1))] = area
            elif n in by_name and by_name[n] not in whole:
                whole[by_name[n]] = area
            else:
                raise GeoError(f"    Neb. Rev. Stat. {COLLEGE_LAW}: {n!r} is not a county, or is in two areas; stopping")
    want = {c: (area, sorted(names)) for c, (area, names) in COLLEGE_PARTS.items()}
    got = {c: (area, sorted(names)) for c, (area, names) in parts.items()}
    if len(segs) != 6 or main != COLLEGE_MAIN or got != want or len(whole) != N_COUNTIES - 2 or set(whole) & set(main):
        raise GeoError(f"    Neb. Rev. Stat. {COLLEGE_LAW} no longer reads as six areas of whole counties with the Cherry and Boone county exceptions this builder was checked against; stopping")
    return whole


def college_of(p, whole):
    """The community college area of a precinct: the county's, or in Cherry and Boone counties the area section
    85-1504 gives the 1975 voting district of the same name."""
    c = p["county"]
    if c in whole:
        return whole[c], False
    area, names = COLLEGE_PARTS[c]
    base = re.sub(r"\s+Precinct$", "", p["vtdname"])
    return (area, True) if base in {v for v in names.values() if v} else (COLLEGE_MAIN[c], False)


# ---------------------------------------------------------------- map services

def fetch_rows(service, fields, path, refresh, say, geometry=True):
    """Every row of a small layer in one request (its point, if it has one), cached as gzipped JSON."""
    if G._fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    try:
        j = json.loads(net.get(f"{service}/query?where={quote('1=1')}&outFields={fields}&returnGeometry={'true' if geometry else 'false'}&outSR=4326&geometryPrecision=6&f=json",
                               timeout=300, accept="application/json"))
        if "error" in j or j.get("exceededTransferLimit"):
            raise GeoError(f"    {service}: {j.get('error') or 'more rows than one request brings'}")
        rows = [[f["attributes"], [f["geometry"]["x"], f["geometry"]["y"]] if (f.get("geometry") or {}).get("x") is not None else None] for f in j.get("features", [])]
        count = json.loads(net.get(f"{service}/query?where={quote('1=1')}&returnCountOnly=true&f=json", accept="application/json")).get("count")
        if count != len(rows) or not rows:
            raise GeoError(f"    {service}: {len(rows):,} rows came, but the service counts {count}")
        time.sleep(1.0)
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not refresh {os.path.basename(path)} ({str(e).strip()}); using the copy on disk")
            return json.load(gzip.open(path, "rt", encoding="utf-8"))
        raise
    out = {"service": service, "fields": fields, "fetched": dt.date.today().isoformat(), "rows": rows}
    with gzip.open(path + ".part", "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows fetched")
    return out


def number(v):
    """The one number a district's label carries ("District 4", " District 1", "Ward 2", 7, "D3"), or None."""
    found = re.findall(r"\d+", str(v if v is not None else ""))
    return int(found[0]) if len(found) == 1 else None


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"ne_geo_overlay_{name}.json")
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
    path = os.path.join(CACHE, "ne_geo_overlay_places.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say("      laying the city, village and township lines over the precincts (kept for the next build)")
    rows = I.place_overlay(pre_rings, cities, towns, MCD_THICK, say)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def most_with_share(p, got, keys, prop):
    """sd_geo.most, and beside it the share of the precinct the district holds where that is under 97 percent
    (p[prop + "_pct"])."""
    top = S.most(p, got, keys, prop)
    if top is not None:
        share = sum(s for d, s, _t in got if keys[d] == top)
        if share < 0.97:
            p[prop + "_pct"] = round(100 * share, 1)
    return top


# ---------------------------------------------------------------- ids against the ballot database

NO_LINES = {
    "utility_board": "no file has who votes for this board: the State's power district layer is who delivers electricity where, and a district's chartered territory is not that",
    "water_board": "no file read here has a reclamation district's lines or its subdivisions'",
    "airport_board": "an airport authority's voters are its city's or county's, and the contest carries an id of its own that no file ties to them",
    "sanitary_board": "no file read here has this sanitary district's lines",
    "transit_board": "no file read here has the Regional Metropolitan Transit Board's districts",
    "learning_community_council": "no file read here has the Learning Community's lines for the whole of it (two counties' services each draw their own part)",
}


def check_ids(info, shape_ids, said_ids, ward_cities):
    """Every Nebraska race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape, then race_said and place_shape). A race without a shape is listed with the
    reason, and with what the precincts say of its district where they name it."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S_ = shape_ids
    by_layer, missing, matched, said, placed = collections.Counter(), collections.OrderedDict(), 0, collections.Counter(), 0
    for rid, level, kind, jur, jid, district, _seat, _counties in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide":
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif level == "court" and jid in S_.get("judicial", {}):
            hit = ("judicial", jid)
        elif kind in ("county_council", "county_commissioner"):
            hit = ("com", f"{jid}|{d}") if d else ("county", jid)
            if d:
                why = ("no file read here has the lines of this county's board districts, or says whether the whole county votes for each seat; the county's "
                       "election office keeps them")
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = ("the county's ward layer does not hold the ward this council race names" if jid in ward_cities else
                       "no file read here has this city's ward lines; the city or the county's election office keeps them")
        elif level == "school":
            hit = ("school", jid)
            why = "the Census Bureau's 2025 school district file has no district of this id (the ballot database gave the district an id of its own)"
        elif level == "court" and jid in S_.get("county", {}):
            hit = ("county", jid)
        elif level == "court" and jid == FIPS:
            why = "a statewide court's judge is voted on by the whole state; the page's rule places a court by its jurisdiction id, and the state's shape is NE"
        elif level == "other":
            why = NO_LINES.get(kind) or "no layer draws this kind of district"
        else:
            why = "no source carries a boundary for this kind of district"
        if hit and hit[1] in S_.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            continue
        named = next((k for k, ids in sorted(said_ids.items()) if jid and jid in ids), None)
        place = level in ("city", "township") and d and jid in S_.get("mcd", {})
        if named:
            said[named] += 1
        placed += bool(place)
        key = (level, kind, jur, jid, district)
        e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district, "races": 0,
                                     "why": ("no layer draws it; every precinct names its own under " + named) if named else (why or "no shape carries this id")})
        if named:
            e["said_by_the_precinct"] = f"{named}:{jid}"
        if place:
            e["the_place_itself"] = f"mcd:{jid}"
        e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())),
            "named_by_the_precinct": dict(sorted(said.items())), "races_named_by_the_precinct": sum(said.values()),
            "council_wards_placed_by_their_city_only": placed,
            "no_shape": list(missing.values()), "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places (one county's dated layer)

POLL_WAITING = {
    "why": "Nebraska has no statewide list of polling places that can be read: each county's election office publishes its own, and the Secretary of State's "
           "VoterCheck answers for one voter at a time. The county election office and VoterCheck say where a voter votes.",
}
POLL_UNCHECKED_WHY = ("      polling places: Sarpy County's layer for November 3, 2026 was read (one county of 93) and marked 'unchecked', so a page does not show it. "
                      "The county's precincts were renumbered in 2021 and the map's lines are the 2020 ones, so the list is given by the county's own precincts and no "
                      "map precinct is tied to a place. When a person has compared it with the Sarpy County Election Commission's own list, set POLL_CHECKED in ballot/ne_geo.py.")


def read_poll_rows(doc, pdoc):
    """The places and the county's precincts that vote at each: ([place], [(precinct name, place number)], rows whose
    two address columns disagree)."""
    out, seen, differ = [], set(), 0
    for a, pt in doc["rows"]:
        no, name, address, city = clean(a.get("POLLINGID")), clean(a.get("NAME")), clean(a.get("FULLADD")), clean(a.get("CITY"))
        ms = a.get("NEXTELECT")
        day = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if isinstance(ms, (int, float)) else None
        if not (re.fullmatch(r"\d{1,3}", no) and name and address and no not in seen):
            raise GeoError(f"    polling places: the row numbered {no!r} does not fit the layout this reader was checked against")
        if day != ELECTION:
            raise GeoError(f"    polling places: the layer's rows are for the election of {day}, not {ELECTION}")
        seen.add(no)
        other = clean(a.get("fulladdr"))
        differ += bool(other) and other.lower() != address.lower()
        hours = clean(a.get("OPERHOURS"))
        out.append({"no": no, "name": name, "address": address, "city": city, "hours": hours if re.fullmatch(r"[0-9:apm\s-]{6,24}", hours.lower()) else None,
                    "lonlat": [round(pt[0], 5), round(pt[1], 5)] if pt else None})
    if not 40 <= len(out) <= 200:
        raise GeoError(f"    polling places: {len(out)} rows is not the list this reader was checked against")
    pcts = []
    for a, _pt in pdoc["rows"]:
        pid, pname, at = clean(a.get("PRECINCTID")), clean(a.get("NAME")), clean(a.get("pollingid"))
        if not (pid and re.fullmatch(r"Precinct \d{1,3}", pname) and (at in seen or not at)):
            raise GeoError(f"    polling places: the precinct row {pid!r} does not fit the layout this reader was checked against")
        pcts.append((pname, at))
    return sorted(out, key=lambda r: int(r["no"])), sorted(pcts, key=lambda x: G.natkey(x[0])), differ


def polling_places(cname, cbox, got, about, put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    if got is None:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        return {"file": "polling_places.json", "status": "waiting"}
    rows, pcts, differ = got
    b, far, places, at = cbox[POLL_COUNTY], 0, [], {}
    for r in rows:
        pt = r["lonlat"]
        if pt and not (b[0] - 0.05 <= pt[0] <= b[2] + 0.05 and b[1] - 0.05 <= pt[1] <= b[3] + 0.05):
            pt, far = None, far + 1
        at[r["no"]] = len(places)
        places.append(dict({"name": r["name"], "address": r["address"], "city": r["city"], "zip": "", "type": None, "hours": r["hours"], "lonlat": pt, "county": POLL_COUNTY,
                            "precincts": []}, **({"from": "Sarpy County's layer (the county's own point)"} if pt else {})))
    by_county = {POLL_COUNTY: [{"precinct": n, "places": [at[p]] if p in at else [], "on_the_map": []} for n, p in pcts]}
    status = "loaded" if POLL_CHECKED else "unchecked"
    doc.update(status=status,
               source=dict({"agency": "Sarpy County, Nebraska (GIS), for the Sarpy County Election Commission", "title": POLL_TITLE, "url": POLL_ITEM, "service": POLL_SERVICE,
                            "fetched": about.get("fetched"), "sha256": about.get("sha256"),
                            "says": "Sarpy County Polling Places; every row gives November 3, 2026 as the next election it is for."},
                           **({"current_to": about["current_to"]} if about.get("current_to") else {})),
               places=places, precinct={}, no_place={}, by_county=by_county, counties_on_the_list=[POLL_COUNTY],
               counties_not_on_the_list=sorted(c for c in cname if c != POLL_COUNTY),
               note="One county's list: Sarpy County's polling places for November 3, 2026, each with the county's own point, and under by_county the county's own "
                    "precincts (as renumbered in 2021) with the place each votes at. The map's precinct lines are the ones reported to the Census Bureau in 2020, so no "
                    f"map precinct is tied to a place. The layer has two address columns, which disagree in {differ} of {len(rows)} rows; the one given here is the "
                    "layer's FULLADD. Nebraska's other 92 counties publish their own lists; none is read here. Nothing here is shown until a person has compared it "
                    "with the Sarpy County Election Commission's own list.")
    put("polling_places.json", doc)
    say(f"      polling places: {len(places)} places of Sarpy County's layer for November 3, 2026 ({sum(1 for p in places if p['lonlat'])} with a point, {far} points thrown out "
        f"as outside the county; the two address columns disagree in {differ} rows), {len(pcts)} county precincts listed; no map precinct is tied to a place; the other "
        f"{len(cname) - 1} counties are not on any list read here")
    if not POLL_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(places), "with_coordinates": sum(1 for p in places if p["lonlat"]), "rows": len(rows),
            "precincts_listed": len(pcts), "map_precincts_with_a_listed_place": 0, "address_columns_disagree": differ, "counties_on_the_list": [POLL_COUNTY],
            "counties_not_on_the_list": doc["counties_not_on_the_list"]}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Nebraska ballot map: 2020 voting districts, 2021 legislative, congressional, court, commission and board districts, county, city, village, township, "
        "school district, natural resources district and county board lines (the Census Bureau, the Secretary of State, the State's GIS site, three counties' map services)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    urls = (BLOCK_URL, BAF_URL, VTD_URL, SLDU_URL, CD_URL, COUSUB_URL, PLACE_URL, UNSD_URL, COUNTY_URL)
    bpath, bafpath, vpath, upath, cdpath, tpath, plpath, scpath, cpath = paths = tuple(path(u.rsplit("/", 1)[1]) for u in urls)
    for name in SHARED:                                    # the same national file, if another state's build already fetched it
        if not os.path.exists(path(name)):
            for other in ("mo_local", "oh_local", "sd_local"):
                src = os.path.join(HERE, "states_cache", other, name)
                if os.path.exists(src):
                    shutil.copyfile(src, path(name))
                    break
    net.patient_lookups()
    for url, p in zip(urls, paths):
        net.download(url, p, 3650, say=lambda *_a: None)
    plan_path = {prop: path("sos_" + v[0].replace("%20", "_")) for prop, v in PLANS.items()}
    legpath = path("sos_" + LEG_FILE)
    for prop, v in PLANS.items():
        net.download(SOS_FILES + v[0], plan_path[prop], 3650, say=lambda *_a: None)
    net.download(SOS_FILES + LEG_FILE, legpath, 3650, say=lambda *_a: None)
    nrdpath, esupath = path("ne_state_nrd_boundaries_geometry_4326.json.gz"), path("ne_nde_educational_service_units_geometry_4326.json.gz")
    nrddoc = W.fetch_full(NRD_SERVICE, "NRD_Name", nrdpath, 6, "OBJECTID", refresh, say)
    esudoc = W.fetch_full(ESU_SERVICE, "ESU", esupath, 6, "OBJECTID", refresh, say)
    bddocs, bdpaths = {}, {}
    for county, (svc, field, _n, src, *_rest) in sorted(BOARDS.items()):
        bdpaths[county] = path(f"{src.replace('ne-', '')}_geometry_4326.json.gz")
        bddocs[county] = M.fetch_small(svc, field, bdpaths[county], refresh, say)
    wddocs, wdpaths = [], []
    for svc, city, field, src, *_rest in WARDS:
        wdpaths.append(path(f"{src.replace('ne-', '')}_geometry_4326.json.gz"))
        wddocs.append(M.fetch_small(svc, (city[1] + "," if city[0] == "column" else "") + field, wdpaths[-1], refresh, say))
    ardocs, arpaths = [], []
    for _prop, _word, _county, svc, field, _w, src, *_rest in AREAS:
        arpaths.append(path(f"{src.replace('ne-', '')}_geometry_4326.json.gz"))
        ardocs.append(M.fetch_small(svc, field, arpaths[-1], refresh, say))
    edited = {k: W.layer_edited(svc, path(f"ne_geo_about_{k}.json"), refresh)
              for k, svc in [("nrd", NRD_SERVICE), ("esu", ESU_SERVICE), ("polls", POLL_SERVICE)] + [(f"board_{c}", v[0]) for c, v in BOARDS.items()]
              + [(f"ward_{n}", v[0]) for n, v in enumerate(WARDS)] + [(f"area_{n}", v[3]) for n, v in enumerate(AREAS)]}

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_long = county_names(cpath)
    cname = {c: names.get(("county", c)) or n for c, n in county_long.items()}
    laws = {k: statute(v[0], path(f"neb_rev_stat_{v[0]}.json"), refresh, say) for k, v in COURTS.items()}
    laws["college"] = statute(COLLEGE_LAW, path(f"neb_rev_stat_{COLLEGE_LAW}.json"), refresh, say)
    court_no = {k: court_districts(laws[k], county_long) for k in COURTS}
    college_whole = college_areas(laws["college"], county_long)

    pollpath, pollpct, poll_got, poll_about = path("sarpy_county_polling_places_2026-11-03.json.gz"), path("sarpy_county_voting_precincts_table.json.gz"), None, {}
    try:
        pdoc = fetch_rows(POLL_SERVICE, POLL_FIELDS, pollpath, refresh, say)
        tdoc = fetch_rows(POLL_PCT_SERVICE, POLL_PCT_FIELDS, pollpct, refresh, say, geometry=False)
        poll_got = read_poll_rows(pdoc, tdoc)
        poll_about = dict(edited["polls"], fetched=pdoc.get("fetched"), sha256=G.sha_file(pollpath))
    except (Exception, GeoError) as e:  # noqa: BLE001  the map does not depend on this list
        say(f"      polling places: waiting; the list could not be read ({str(e).strip()})")

    # ---- precincts: the 2020 voting districts, from blocks; every shared line kept once
    table, water, vname = read_tables(bafpath, upath, cdpath, vpath)
    plans = {prop: Plan(read_plan(plan_path[prop], v[1])) for prop, v in PLANS.items()}
    local = collections.defaultdict(list)                  # the three counties' own layers, read block by block like the Secretary's plans
    for county, (_svc, field, n, *_rest) in sorted(BOARDS.items()):
        if sorted(number(a[field]) or 0 for a, _r in bddocs[county]["rows"]) != list(range(1, n + 1)):
            raise GeoError(f"    {cname[county]}: the board district layer does not hold districts 1 to {n}, each once; stopping")
        local[county].append(("com", local_plan(bddocs[county]["rows"], lambda a, county=county, field=field: f"{county}|District {number(a[field])}")))
    for (prop, _word, county, _svc, field, part, _src, _who, what), doc in zip(AREAS, ardocs):
        if any(number(a[field]) is None for a, _r in doc["rows"]):
            raise GeoError(f"    {what}: a row has no number; stopping")
        local[county].append((prop + "_area", local_plan(doc["rows"], lambda a, field=field, part=part: f"{part} {number(a[field])}")))
    pre, polys, said, leg, unplaced = read_units(bpath, table, water, vname, plans, Plan(read_plan(legpath, N_LEG)), dict(local), say)
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
    if len({r["COUNTYFP"] for r, _ in cous}) != N_COUNTIES:
        raise GeoError(f"    {os.path.basename(tpath)}: not {N_COUNTIES} counties of county subdivisions; stopping")
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    is_town = [r["LSAD"] in TOWN_LSAD and r["FUNCSTAT"] == "A" for r, _ in cous]      # a township with a government of its own
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
    town_county = collections.defaultdict(set)
    for k, c, t in zip(town_key_all, ccounty, is_town):
        if t:
            town_county[k].add(c)
    # a township's name is not its own in Nebraska (many counties have a Lincoln township): it is given with its county
    census_name = {k: f"{n} ({county_long[sorted(town_county[k])[0]]})" for k, n in census_name.items()}
    census_name.update({k: r["NAMELSAD"] for k, (r, _) in zip(city_key, cities_)})
    mkind = {k: "township" for k in towns}
    mkind.update({k: PLACE_WORD[r["LSAD"]] for k, (r, _) in zip(city_key, cities_)})
    mname = {k: names.get(("mcd", k)) or n for k, n in census_name.items()}
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- school districts (the Bureau's, one fabric), natural resources districts and educational service units (the State's)
    sch = sorted(I.read_shapefile(scpath, lambda r: r["STATEFP"] == FIPS and re.fullmatch(r"\d{5}", r["UNSDLEA"]) and r["UNSDLEA"] != "99997"), key=lambda x: x[0]["UNSDLEA"])
    schkeys = [f"{STATE}-S-{r['UNSDLEA']}" for r, _ in sch]
    if len(set(schkeys)) != len(schkeys) or not 200 <= len(schkeys) <= 300:
        raise GeoError(f"    {os.path.basename(scpath)}: {len(schkeys)} school districts, or two of one code; stopping")
    scharcs, schsides, _sr, schodd = G.topology([rings for _r, rings in sch])
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    scensus = {k: clean(r["NAME"]) for k, (r, _) in zip(schkeys, sch)}
    sname = {k: names.get(("school", k)) or n for k, n in scensus.items()}

    db_special = {pid: n for (kind, pid), n in names.items() if kind == "special"}
    nrd_name = lambda a: re.sub(r"\s*&\s*", " and ", clean(a["NRD_Name"])) + " Natural Resources District"      # noqa: E731
    nrd_id = lambda a: f"{STATE}-X-{slug(nrd_name(a))}"      # noqa: E731
    if len({nrd_id(a) for a, _r in nrddoc["rows"]}) != 23 or any(not clean(a["NRD_Name"]) for a, _r in nrddoc["rows"]):
        raise GeoError("    natural resources districts: not 23 named districts; stopping")
    nrdkeys, nrdpolys, _na, _ns, _nr, nrdodd = I.fabric(N.merge_rows(nrddoc["rows"], nrd_id), nrd_id)
    nrdname = {nrd_id(a): db_special.get(nrd_id(a)) or nrd_name(a) for a, _r in nrddoc["rows"]}
    nrd_unknown = sorted(pid for pid in db_special if pid.endswith("-natural-resources-district") and pid not in nrdname)
    esu_id = lambda a: f"{STATE}-X-educational-service-unit-no-{int(a['ESU'])}"      # noqa: E731
    if any(not str(a.get("ESU") or "").strip().isdigit() for a, _r in esudoc["rows"]):
        raise GeoError("    educational service units: a row has no number; stopping")
    esukeys, esupolys, _ea, _es, _er, esuodd = I.fabric(N.merge_rows(esudoc["rows"], esu_id), esu_id)
    esuname = {esu_id(a): db_special.get(esu_id(a)) or f"Educational Service Unit No. {int(a['ESU'])}" for a, _r in esudoc["rows"]}
    college_id = lambda area: f"{STATE}-X-{slug(area)}-community-college"      # noqa: E731
    college_name = {college_id(a): db_special.get(college_id(a)) or f"{a} Community College" for a in set(college_whole.values()) | set(COLLEGE_MAIN.values())
                    | {v[0] for v in COLLEGE_PARTS.values()}}

    # ---- county board districts and city wards: each its own fabric
    board, bd_odd = {}, {}
    for county, (_svc, field, _n, *_rest) in sorted(BOARDS.items()):
        rows = bddocs[county]["rows"]
        key = lambda a, county=county, field=field: f"{county}|District {number(a[field])}"      # noqa: E731
        keys, cpolys, a_, s_, _r, o_ = I.fabric(N.merge_rows(rows, key), key)
        board[county] = (keys, cpolys, a_, s_)
        if o_:
            bd_odd[county] = dict(o_)
    by_city = collections.defaultdict(list)
    for k, (r, _) in zip(city_key, cities_):
        by_city[fold(r["NAME"])].append(k)
    ward_fabs, wards_drawn, ward_src = [], collections.defaultdict(list), {}
    for (svc, city, field, src, *_rest), doc in zip(WARDS, wddocs):
        rows = []
        for a, rings in doc["rows"]:
            n = number(a.get(field))
            fits = by_city.get(fold(clean(a[city[1]]) if city[0] == "column" else city[1]), [])
            if n is None or not rings:
                continue                                    # a city the layer draws whole, with no ward
            if len(fits) != 1:
                raise GeoError(f"    wards: the layer's city {a.get(city[1]) if city[0] == 'column' else city[1]!r} is not one city of the Census Bureau's file; stopping")
            rows.append(({"key": f"{fits[0]}|Ward {n}"}, rings))
        wkey = lambda a: a["key"]      # noqa: E731
        wkeys, wpolys, warcs, wsides, _wr, wodd = I.fabric(N.merge_rows(rows, wkey), wkey)
        ward_fabs.append((wkeys, wpolys, warcs, wsides, src, wodd))
        for k in wkeys:
            wards_drawn[k.split("|")[0]].append(k.split("|")[1])
            ward_src[k] = src
    wards_drawn = {j: sorted(ws, key=G.natkey) for j, ws in sorted(wards_drawn.items())}
    say(f"      {len(schkeys)} school districts ({len(scharcs):,} lines), {len(nrdkeys)} natural resources districts, {len(esukeys)} educational service units, "
        f"{sum(len(v[0]) for v in board.values())} county board districts in {len(board)} counties, {sum(len(v) for v in wards_drawn.values())} wards of "
        f"{len(wards_drawn)} cities, {len(cous):,} Census county subdivisions ({len(towns):,} townships with a government of their own), {len(cities_):,} cities and villages"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("school", schodd), ("Census", codd), ("places", podd), ("natural resources", nrdodd), ("service units", esuodd)) if o)
        + "".join(f"; odd in {cname[c]}'s board districts: {o}" for c, o in bd_odd.items()))
    if info["found"] and nrd_unknown:
        say(f"      natural resources districts: the ballot database has {len(nrd_unknown)} the State's file does not name ({', '.join(nrd_unknown[:4])})")

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    units_stamp = (bafpath, upath, cdpath) + tuple(plan_path.values()) + tuple(bdpaths[c] for c in sorted(bdpaths)) + tuple(arpaths)      # the blocks' own file never changes
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(*units_stamp, scpath), refresh, say)
    o_mcd = place_overlay_cached(pre_rings, I.rings_xy([r for _a, r in cities_]), I.rings_xy([r for _a, r in town_rows]), stamp(*units_stamp, tpath, plpath), refresh, say)
    o_nrd = overlay_cached("natural-resources", pre_rings, I.rings_xy(nrdpolys), stamp(*units_stamp, nrdpath), refresh, say)
    o_esu = overlay_cached("service-units", pre_rings, I.rings_xy(esupolys), stamp(*units_stamp, esupath), refresh, say)
    place_keys = city_key + [k for k, t in zip(town_key_all, is_town) if t]

    several = no_place = by_name = 0
    city_county = collections.defaultdict(set)
    for p, got, gn, ge in zip(pre, o_mcd, o_nrd, o_esu):
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
        p["jud"] = f"{COURTS['judicial'][1]}{court_no['judicial'][p['county']]}"
        p["county_court"] = f"{COURTS['county_court'][1]}{court_no['county_court'][p['county']]}"
        area, named = college_of(p, college_whole)
        p["college"] = college_id(area)
        by_name += named
        p["nrd"] = most_with_share(p, gn, nrdkeys, "nrd")
        p["esu"] = most_with_share(p, ge, esukeys, "esu")
        p["ward"] = None
        for k in ("com", "nrd_area", "college_area"):
            p.setdefault(k, None)
    if any(not p["nrd"] or not p["esu"] for p in pre):
        bad = [p["id"] for p in pre if not p["nrd"] or not p["esu"]]
        raise GeoError(f"    {len(bad)} precincts touch no natural resources district, or no educational service unit (e.g. {bad[0]}); stopping")
    for county, names_ in COLLEGE_PARTS.items():
        have = {re.sub(r"\s+Precinct$", "", p["vtdname"]) for p in pre if p["county"] == county}
        gone = sorted({v for v in names_[1].values() if v} - have)
        if gone:
            raise GeoError(f"    community college areas: {cname[county]} no longer has a 2020 voting district named {', '.join(gone)}; stopping")
    com_laid = 0
    for county, (keys, cpolys, _a, _s) in sorted(board.items()):      # a piece whose blocks' points fell in no one district: the district holding most of it
        idx = [i for i, p in enumerate(pre) if p["county"] == county and not p["com"]]
        if not idx:
            continue
        got = overlay_cached(f"board-{county}", [pre_rings[i] for i in idx], I.rings_xy(cpolys), stamp(*units_stamp, bdpaths[county]), refresh, say)
        for i, g in zip(idx, got):
            pre[i]["com"] = S.most(pre[i], g, keys, "com")
            com_laid += 1
        none = [pre[i]["id"] for i in idx if not pre[i]["com"]]
        if len(none) > 2:
            raise GeoError(f"    {cname[county]}: {len(none)} precincts touch no board district (e.g. {none[0]}); stopping")
    for n, ((wkeys, wpolys, _wa, _ws, _src, _o), wdpath) in enumerate(zip(ward_fabs, wdpaths)):
        cities_here = {k.split("|")[0] for k in wkeys}
        idx = [i for i, p in enumerate(pre) if cities_here & set(p["mcd_all"])]
        got = overlay_cached(f"wards-{n}", [pre_rings[i] for i in idx], I.rings_xy(wpolys), stamp(*units_stamp, wdpath), refresh, say)
        for i, g in zip(idx, got):
            share = collections.Counter()
            for d, s, _t in g:
                share[wkeys[d]] += s
            top = share.most_common(2)
            if top and top[0][1] >= 0.5:
                pre[i]["ward"] = top[0][0]
                if len(top) > 1 and top[1][1] >= SPLIT_SHARE:
                    pre[i].setdefault("split", {})["ward"] = {k: round(100 * s, 1) for k, s in top}
    area_counts = collections.Counter()
    for prop, word, county, *_rest in AREAS:               # a part is kept only where the precinct lies in the district the part is a part of
        jid = next((k for k in (nrdname if prop == "nrd" else college_name) if word in k), None)
        if jid is None:
            raise GeoError(f"    no {prop} is named {word!r}; stopping")
        for p in pre:
            if p["county"] == county and p[prop + "_area"]:
                if p[prop] == jid:
                    area_counts[prop + "_area"] += 1
                else:
                    p[prop + "_area"] = None
    say(f"      cities, villages and townships by precinct: {several:,} of {len(pre):,} precincts reach more than one place, {no_place:,} lie in none (open country "
        f"without township government); natural resources district: {sum(1 for p in pre if (p.get('split') or {}).get('nrd'))} precincts have {SPLIT_SHARE:.0%} or more "
        f"of their area in a second; educational service unit: {sum(1 for p in pre if (p.get('split') or {}).get('esu'))}; county board district: "
        f"{sum(1 for p in pre if p['com']):,} precincts name one ({com_laid} of them by the district holding most of the precinct); {sum(1 for p in pre if p['ward'])} precincts lie mostly in a "
        f"drawn ward; {area_counts['nrd_area']} name a Papio-Missouri River subdistrict and {area_counts['college_area']} a Metropolitan Community College district; "
        f"{by_name} precincts of Cherry and Boone counties are in their community college area by the name of their voting district")

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

    vals = {"county": [p["county"] for p in pre], "senate": [p["senate"] for p in pre], "cd": [p["cd"] for p in pre], "judicial": [p["jud"] for p in pre]}
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

    def layer(kind, geoms, qlines, tol, props, source, zoom=None, first=None):
        gl = []
        for v, polys_ in sorted(geoms, key=lambda x: ((0 if first(x[0]) else 1) if first else 0, G.natkey(x[0]))):
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

    BLOCKS, VTD, BEF, CDB, SOS, COUSUB, PLACES, SCH, LAW, NRD, ESU, POLLS = (
        "ne-census-tiger-2020-blocks", "ne-census-2020-voting-districts", "ne-census-2024-legislative-bef", "ne-census-cd119-bef", "ne-sos-2021-district-shapefiles",
        "ne-census-tiger-2025-cousub", "ne-census-tiger-2025-place", "ne-census-tiger-2025-unsd", "ne-rev-stat-court-and-college-districts", "ne-state-nrd-boundaries",
        "ne-nde-educational-service-units", "ne-sarpy-county-polling-places-2026-11-03")
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[f"{COURTS['judicial'][1]}{court_no['judicial'][c]}"].append(cname[c])
    layer("state", *own([STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, BLOCKS)
    layer("county", *own(vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, BLOCKS)
    layer("cd", *own(vals["cd"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, BLOCKS + ", put together by " + CDB)
    layer("senate", *own(vals["senate"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Legislative District {v}", "j": FIPS, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("judicial", *own(vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{COURTS['judicial'][2]} {v[len(COURTS['judicial'][1]):]}", "j": v, "d": v[len(COURTS['judicial'][1]):], "counties": jud_counties[v]},
          BLOCKS + "; which counties, from " + LAW)
    layer("mcd", *W.merged_layer([(parcs, psides, city_key), (carcs, csides, town_val)], TOL_MCD), TOL_MCD,
          lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, PLACES + " and " + COUSUB, zoom=MCD_ZOOM, first=lambda v: v in city_set)
    wg, wq = W.merged_layer([(warcs, wsides, wkeys) for wkeys, _p, warcs, wsides, _s, _o in ward_fabs], G.TOL_LOCAL)
    layer("ward", wg, wq, G.TOL_LOCAL, lambda v: {"id": v, "name": f"{mname[v.split('|')[0]]}, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
          ", ".join(w[3] for w in WARDS))
    cg, cq = W.merged_layer([(a_, s_, keys) for _c, (keys, _p, a_, s_) in sorted(board.items())], G.TOL_LOCAL)
    layer("com", cg, cq, G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]} Board, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
          ", ".join(BOARDS[c][3] for c in sorted(BOARDS)))
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
    plan_name = {f"{v[2]}{n}": f"{v[3]} {n}" for v in PLANS.values() for n in range(1, v[1] + 1)}
    cc_name = lambda v: f"{COURTS['county_court'][2]} {v[len(COURTS['county_court'][1]):]}"      # noqa: E731
    by_county = collections.defaultdict(list)
    for i, p in enumerate(pre):
        by_county[p["county"]].append(i)
    counties, boxes, cbox, dropped_rings = [], {}, {}, 0
    for county, idxs in sorted(by_county.items()):
        local = {i: n for n, i in enumerate(idxs)}
        geoms = []
        used_names = {k: {} for k in ("mcd", "school", "com", "ward", "judicial", "county_court", "appeals", "psc", "regents", "sboe", "nrd", "esu", "college")}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "mcd": p["mcd"], "senate": p["senate"], "cd": p["cd"], "judicial": p["jud"],
                  "county_court": p["county_court"], "appeals": p["appeals"], "psc": p["psc"], "regents": p["regents"], "sboe": p["sboe"], "nrd": p["nrd"], "esu": p["esu"],
                  "college": p["college"], "school": p["school"], "as_of": 2020}
            used_names["judicial"][p["jud"]] = shape_ids["judicial"][p["jud"]]["name"]
            used_names["county_court"][p["county_court"]] = cc_name(p["county_court"])
            for k in PLANS:
                used_names[k][p[k]] = plan_name[p[k]]
            used_names["college"][p["college"]] = college_name[p["college"]]
            for k, nm in (("nrd", nrdname), ("esu", esuname)):
                for v in [p[k]] + list((p.get("split") or {}).get(k, {})):
                    used_names[k][v] = nm[v]
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
            for k in ("nrd_pct", "esu_pct", "nrd_area", "college_area", "school_pct", "school_out", "school_edge", "split"):
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

    polls = polling_places(county_long, cbox, poll_got, poll_about, put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    # ---- how each county's board races are filed in the ballot database, and whether its districts are drawn here
    plans_ = {}
    for _rid, _level, kind, _jur, jid, district, _seat, _c in info["races"]:
        if kind in ("county_commissioner", "county_council"):
            e = plans_.setdefault(str(jid), {"plan": 1, "districts": set()})
            if district not in (None, ""):
                e["plan"] = 3
                e["districts"].add(str(district))
    for c, e in plans_.items():
        e["districts"] = sorted(e["districts"], key=G.natkey)
        e["lines"] = "drawn here (the com layer), from the county's own map service" if c in BOARDS else "not in any file read here"
        e["commissioners_elected"] = ("at large, by the county's notice of election" if e["plan"] == 1 else
                                      "from districts, by the county's notice of election" + ("" if c in BOARDS else
                                      "; the county's election office has the lines, and says whether a district's voters alone or the whole county elect each member"))
        e["source"] = "how the county's 2026 notice of election or sample ballot files the board's seats"

    said_ids = {k: {p[k] for p in pre if p.get(k)} for k in ("county_court", "appeals", "psc", "regents", "sboe", "nrd", "esu", "college")}
    check = check_ids(info, shape_ids, said_ids, set(wards_drawn))
    check["wards_drawn"] = wards_drawn
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    check["natural_resources_districts_of_the_ballot_database_not_in_the_state_file"] = nrd_unknown
    check["school_districts_of_the_ballot_database_not_in_the_census_file"] = sorted(pid for (kind, pid) in names if kind == "school" and pid not in sname)
    check["legislative_districts_by_the_point_inside_rule"] = {"blocks": leg["blocks"], "same_as_the_census_file": leg["same"], "blocks_that_differ": leg["differ"]}
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    cb, state_gis = "U.S. Census Bureau", "State of Nebraska, Office of the Chief Information Officer (NebraskaMAP)"
    college_note = ("In Cherry and Boone counties section 85-1504 divides the county by voting districts 'as they existed on July 1, 1975', whose lines no file has. A 2020 "
                    "voting district that still carries one of the statute's names (Merriman, Cody, Russell, King, Barley, Gillaspie, Mother Lake and Lackey in Cherry County; "
                    "Oakland and North Branch-Shell Creek in Boone County) is given the statute's area (Western; Northeast) and every other one the county's main area "
                    "(Mid-Plains; Central). That is a reading of names 45 years apart, not of lines: the statute's Calf Creek (Cherry), Ashland and Midland (Boone) are not "
                    "among the 2020 names, and the county clerk is the authority.")
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            {"id": BLOCKS, "agency": cb, "title": "TIGER/Line Shapefiles 2020, tabulation blocks, Nebraska (tl_2020_31_tabblock20.zip)",
             "about": "The 2020 census blocks: every line of the map's precincts, counties, legislative and congressional districts is a block's.",
             "url": BLOCK_URL, "fetched": mtime(bpath), "bytes": os.path.getsize(bpath), "rows": len(table) + len(water)},
            {"id": VTD, "agency": cb, "title": "2020 Census Block Assignment File, voting districts (BlockAssign_ST31_NE.zip), and the voting districts' names "
                                                "(tl_2020_31_vtd20.zip)",
             "about": "The precincts Nebraska's counties reported for the 2020 census: which voting district each block is in.",
             "url": BAF_URL, "names_url": VTD_URL, "fetched": mtime(bafpath), "sha256": G.sha_file(bafpath), "names_sha256": G.sha_file(vpath),
             "rows": len({(p["county"], p["vtd"]) for p in pre})},
            {"id": BEF, "agency": cb, "title": "2024 State Legislative District Block Equivalency File, upper chamber (sldu24.zip)",
             "about": "Which of the Legislature's 49 districts each block is in, under the plan enacted in 2021.",
             "url": SLDU_URL, "fetched": mtime(upath), "sha256": G.sha_file(upath), "rows": len(table)},
            {"id": CDB, "agency": cb, "title": "119th Congressional District Block Equivalency File (cd119.zip)",
             "about": "Which of the three congressional districts each block is in, under the plan enacted in 2021.",
             "url": CD_URL, "fetched": mtime(cdpath), "sha256": G.sha_file(cdpath), "rows": len(table) + len(water)},
            {"id": SOS, "agency": "Nebraska Secretary of State", "title": "District & Subdivision Maps, GIS shapefiles: " + ", ".join(v[4] for v in PLANS.values()),
             "about": "The Supreme Court judicial districts, the Public Service Commission districts, the Board of Regents districts and the State Board of Education "
                      "districts enacted in 2021 (maps effective October 1, 2021). A census block is in the district that holds a point inside it; the same rule gives the "
                      f"Census Bureau's own answer for {leg['same']:,} of {leg['blocks']:,} blocks when applied to the Secretary's legislative shapefile (LEG21-39006).",
             "url": SOS_PAGE, "files": {prop: SOS_FILES + v[0] for prop, v in PLANS.items()}, "fetched": mtime(plan_path["appeals"]),
             "sha256": G.sha_file(plan_path["appeals"]), "files_sha256": {prop: G.sha_file(pp) for prop, pp in plan_path.items()}, "rows": sum(v[1] for v in PLANS.values())},
            {"id": LAW, "agency": "Nebraska Legislature", "title": "Neb. Rev. Stat. 24-301.02 (district court judicial districts), 24-503 (county judge districts) and "
                                                                    "85-1504 (community college areas)",
             "about": "Which counties make up each court district and each community college area.",
             "url": laws["judicial"]["url"], "county_court_url": laws["county_court"]["url"], "college_url": laws["college"]["url"], "fetched": laws["judicial"]["fetched"],
             "sha256": laws["judicial"]["sha256"], "county_court_sha256": laws["county_court"]["sha256"], "college_sha256": laws["college"]["sha256"], "rows": 30},
            {"id": COUSUB, "agency": cb, "title": "TIGER/Line Shapefiles 2025, county subdivisions, Nebraska (tl_2025_31_cousub.zip)",
             "about": "Townships as the Bureau had them on January 1, 2025 (only those it marks as functioning governments are places here); also the county "
                      "areas the precincts are checked against.",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": PLACES, "agency": cb, "title": "TIGER/Line Shapefiles 2025, places, Nebraska (tl_2025_31_place.zip)",
             "about": "City and village limits (incorporated, active places only), as the Bureau had them on January 1, 2025.", "url": PLACE_URL,
             "fetched": mtime(plpath), "sha256": G.sha_file(plpath), "rows": len(cities_)},
            {"id": SCH, "agency": cb, "title": "TIGER/Line Shapefiles 2025, unified school districts, Nebraska (tl_2025_31_unsd.zip)",
             "about": "School district lines as the State reported them to the Bureau for the 2024-25 school year.", "url": UNSD_URL,
             "fetched": mtime(scpath), "sha256": G.sha_file(scpath), "rows": len(schkeys)},
            dict({"id": NRD, "agency": state_gis, "title": "Natural Resource District (NRD) Boundaries", "about": "Only the district's name is read.",
                  "url": NRD_ITEM, "service": NRD_SERVICE, "fetched": nrddoc.get("fetched"), "sha256": G.sha_file(nrdpath), "rows": len(nrdkeys)}, **edited["nrd"]),
            dict({"id": ESU, "agency": "Nebraska Department of Education; published by the " + state_gis, "title": "Educational Service Units",
                  "about": "Derived, its publisher says, from 2018 State parcels and school district data. Only the unit's number is read.",
                  "url": ESU_ITEM, "service": ESU_SERVICE, "fetched": esudoc.get("fetched"), "sha256": G.sha_file(esupath), "rows": len(esukeys)}, **edited["esu"]),
        ] + [dict({"id": v[3], "agency": v[4], "title": v[5], "about": v[6] + " Only the district number is read.", "url": v[0], "service": v[0],
                   "fetched": bddocs[c].get("fetched"), "sha256": G.sha_file(bdpaths[c]), "rows": v[2]}, **edited[f"board_{c}"]) for c, v in sorted(BOARDS.items())]
        + [dict({"id": v[3], "agency": v[4], "title": v[5], "about": "Only the city's name and the ward's number are read.", "url": v[0], "service": v[0],
                 "fetched": wddocs[n].get("fetched"), "sha256": G.sha_file(wdpaths[n]), "rows": len(ward_fabs[n][0])}, **edited[f"ward_{n}"]) for n, v in enumerate(WARDS)]
        + [dict({"id": v[6], "agency": v[7], "title": v[8], "about": "Only the district number is read. It is laid over the county's precincts to say which part each lies in; "
                                                                      "no layer draws it.",
                 "url": v[3], "service": v[3], "fetched": ardocs[n].get("fetched"), "sha256": G.sha_file(arpaths[n]), "rows": len(ardocs[n]["rows"])}, **edited[f"area_{n}"])
           for n, v in enumerate(AREAS)]
        + ([dict({"id": POLLS, "agency": "Sarpy County, Nebraska (GIS), for the Sarpy County Election Commission", "title": POLL_TITLE, "url": POLL_ITEM,
                  "about": "One county's list, read for polling_places.json (unchecked): place number, name, street address, city, hours and point.",
                  "service": POLL_SERVICE, "fetched": poll_about.get("fetched"), "sha256": poll_about.get("sha256"), "rows": len(poll_got[0])},
                 **({"current_to": poll_about["current_to"]} if poll_about.get("current_to") else {}))] if poll_got else []),
        "notes": {
            "lines": f"Every precinct, county, legislative and congressional line is a 2020 census block's, generalised by at most {G.TOL_PRECINCT} metres and set on a "
                     "grid of 0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "Nebraska publishes no statewide map of its precincts as they stand in 2026. Each shape here is a voting district as its county reported it for "
                         "the 2020 census, cut wherever a line of the districts enacted in 2021 crosses it, and named as the Bureau's file names it. A county may have "
                         "redrawn or renamed its precincts since (Sarpy County renumbered its own in 2021): the county's election office is the authority. What a ballot "
                         "depends on (county, legislative and congressional district, court districts, city, village or township, school district, natural resources "
                         "district, educational service unit, community college area, county board district) is taken from current files and does not depend on the "
                         "precinct.",
            "places": "A precinct can reach more than one place, so the precinct does not say which city or village a voter lives in: the mcd layer answers that for a "
                      "point, cities and villages first. A township is a place here only where the Census Bureau marks it as a functioning government (the counties "
                      "with township organization, and Washington County's numbered townships); its shape is the whole township, the cities and villages in it "
                      "included, and its name is given with its county. Elsewhere open country is in no place, and a precinct there has no mcd. mcd is the place "
                      "holding most of the precinct; mcd_all lists every place it reaches. Limits are the Census Bureau's of January 1, 2025.",
            "legislative": "Nebraska's Legislature has one house of 49 members; its districts are the senate layer, and there is no house layer. Which district a block "
                           "is in is the Census Bureau's 2024 equivalency file's word (the plan enacted in 2021), so a precinct's district is exact.",
            "congressional": "The three districts enacted in 2021 (the Census Bureau's 119th Congress equivalency file). A precinct's district is exact.",
            "statewide_boards": "The Public Service Commission (five districts), the University of Nebraska Board of Regents (eight) and the State Board of Education "
                                "(eight) are each elected by district, and a Court of Appeals judge sits for one of the six Supreme Court judicial districts. A precinct "
                                "names its own district of each (psc, regents, sboe, appeals), from the Secretary of State's shapefiles of the maps enacted in 2021, block "
                                "by block. No layer draws them.",
            "judicial": "The twelve district court judicial districts (the judicial layer) and the twelve county judge districts (county_court) are whole counties "
                        "(Neb. Rev. Stat. 24-301.02, 24-503); they are the same but for Otoe and Fillmore counties. A separate juvenile court's judge is voted on by one county.",
            "commissioners": "A county board's members are elected from districts or at large, as each county has settled (Neb. Rev. Stat. 23-151), and each county draws "
                             "its own districts. Three counties' own map services have the lines, drawn here as the com layer: Douglas (seven districts), Lancaster "
                             "(five) and Sarpy (five). There a census block is in the district that holds a point inside it, and a precinct is cut wherever a board "
                             "district line crosses it, so a precinct's com is its own. No file read here has any other county's.",
            "wards": "No statewide file has city ward lines. Wards are drawn for Bellevue, Gretna, La Vista and Papillion (Sarpy County's layer) and for Bennington and "
                     "Ralston (the Douglas County Election Commission's layers).",
            "school": "School district lines are the Census Bureau's 2025 file (as the State reported them for the 2024-25 school year). Which districts a precinct lies "
                      f"in is analysis, not an official list: a district counts when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; "
                      "school_pct is each district's share of the precinct's area (land and water, not voters). A school board member elected from a ward or subdistrict "
                      "is shown for the whole district: no file read here has those lines.",
            "districts": "nrd and esu are the natural resources district and the educational service unit holding most of a precinct (analysis: the State's lines laid "
                         "over the precinct); nrd_pct and esu_pct give that share where it is under 97 percent, and split names a second district holding 3 percent or "
                         "more. nrd_area is the subdistrict of the Papio-Missouri River Natural Resources District, and college_area the district of the Metropolitan "
                         "Community College board, in Douglas and Sarpy counties only (those two counties' own layers, read block by block, a precinct being cut "
                         "where their lines cross it; the rest of each district has no lines here).",
            "college": "college is the community college area (Neb. Rev. Stat. 85-1504): the county's. " + college_note,
            "authority": "For which precinct an address votes in, and where, the county's election office and the Nebraska Secretary of State's VoterCheck are the authority.",
            "precinct_ids": "A precinct's id is its county's five digits, a full stop and the Census Bureau's 2020 voting district code (31055.001-02); a voting "
                            "district cut by a district line has a second full stop and the piece's number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file; -2: outside Nebraska); names gives the names of the places and districts the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the 2020 voting district's, as the Census Bureau's file gives it (and the piece's number where a district line cuts it)",
                                    "county": "county id", "precinct": "the county's five digits and the Bureau's 2020 voting district code",
                                    "as_of": "the year of the precinct's lines (2020)",
                                    "mcd": "city, village or township holding most of the precinct (none in open country without township government)",
                                    "mcd_all": "list, when the precinct reaches more than one: every city, village and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                                    "senate": "legislative district (the one-house Legislature's)", "cd": "congressional district",
                                    "judicial": "district court judicial district",
                                    "county_court": "county judge district (" + ", ".join(f"NE-CC{n} {n}" for n in range(1, N_COURT + 1)) + ")",
                                    "appeals": "court of appeals district (" + ", ".join(f"NE-COA{n} {n}" for n in range(1, 7)) + "): the Supreme Court judicial district of the same number",
                                    "psc": "public service commissioner district (" + ", ".join(f"NE-PSC{n} {n}" for n in range(1, 6)) + ")",
                                    "regents": "Board of Regents district (" + ", ".join(f"NE-REG{n} {n}" for n in range(1, 9)) + ")",
                                    "sboe": "State Board of Education district (" + ", ".join(f"NE-SBOE{n} {n}" for n in range(1, 9)) + ")",
                                    "nrd": "natural resources district holding most of the precinct",
                                    "nrd_pct": "percent of the precinct inside that natural resources district, where under 97",
                                    "nrd_area": "the subdistrict, in the Papio-Missouri River Natural Resources District's part of Douglas and Sarpy counties",
                                    "esu": "educational service unit holding most of the precinct",
                                    "esu_pct": "percent of the precinct inside that educational service unit, where under 97",
                                    "college": "community college area",
                                    "college_area": "the board district, in the Metropolitan Community College area's part of Douglas and Sarpy counties",
                                    "com": "Douglas, Lancaster and Sarpy counties only: the county board district",
                                    "ward": "list, in a city whose wards are drawn: the council ward holding most of the precinct",
                                    "split": "only where a second district of a kind holds 3 percent or more of the precinct: each one's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "NE (j is 31)", "county": "the county's five-digit code (31055)",
                    "mcd": "NE-M- and the Census code: a city's or village's place code (NE-M-03950), a township's county subdivision code; properties.t says city, village or township",
                    "ward": "<city>|<ward as the council race words it> (NE-M-03950|Ward 2)",
                    "com": "<county>|<district as the board race words it> (31055|District 2): Douglas, Lancaster and Sarpy counties",
                    "senate": "the legislative district (10)", "cd": "the district (2); properties.race is the race for Congress",
                    "judicial": "NE-DC and the district court judicial district's number (NE-DC4); d is the number",
                    "school": "NE-S- and the Census Bureau's five-digit district code (NE-S-74820)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL,
                   "census_names": {k: v for k, v in sorted(scensus.items()) if v != sname[k]}},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans_[c] for c in sorted(plans_)},
        "community_college_areas_by_name": {c: {"area": college_id(v[0]), "main_area": college_id(COLLEGE_MAIN[c]), "statute_names": v[1]} for c, v in sorted(COLLEGE_PARTS.items())},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "whole_precincts": len({p["precinct"] for p in pre}), "counties": len(counties), "census_blocks": len(table) + len(water),
                   "census_blocks_in_no_voting_district": len(water),
                   "split_between_school_districts": split, "in_more_than_one_place": several, "in_no_place": no_place,
                   "rings_too_small_for_the_grid": dropped_rings, "lines_with_a_precinct_on_one_side": lone,
                   "census_blocks_in_no_one_district_of_a_county_layer": unplaced, "precincts_given_their_board_district_by_area": com_laid,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Nebraska races have a shape"
        + (f", and {check.get('races_named_by_the_precinct', 0):,} more have their district named by every precinct; {len(check['no_shape'])} kinds of place without a shape "
           f"(listed in index.json)" if check["no_shape"] else ""))
    say(f"    Nebraska ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

def _want(county, senate, cd, dc, cc, coa, psc, reg, sboe, nrd, esu, college):
    return {"county": county, "senate": str(senate), "cd": str(cd), "judicial": f"NE-DC{dc}", "county_court": f"NE-CC{cc}", "appeals": f"NE-COA{coa}", "psc": f"NE-PSC{psc}",
            "regents": f"NE-REG{reg}", "sboe": f"NE-SBOE{sboe}", "nrd": f"NE-X-{nrd}-natural-resources-district", "esu": f"NE-X-educational-service-unit-no-{esu}",
            "college": f"NE-X-{college}-community-college"}


TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the place at the point (from the mcd layer; None in
    # open country), and a word its school district's name must carry. None of it comes from the files tested here.
    # County, place or township, legislative and congressional district and school district are the Census Bureau's
    # geocoder's answer for those coordinates (asked 2026-10-02: geocoding.geo.census.gov, "geographies/coordinates",
    # its current districts). The Supreme Court (court of appeals), Public Service Commission, Regents and Board of
    # Education districts, the natural resources district and the educational service unit are the State of
    # Nebraska's own map services' answers for the point (gis.ne.gov, asked the same day: which shape of each layer
    # holds it). The district court and county judge districts and the community college area are the county's, read
    # by hand from sections 24-301.02, 24-503 and 85-1504 (Otoe and Fillmore counties are where the two court maps
    # differ; Merriman is in the part of Cherry County the statute gives to the Western area).
    ("the State Capitol, Lincoln", -96.6997, 40.8081, _want("31109", 28, 1, 3, 3, 1, 1, 1, 1, "lower-platte-south", 18, "southeast"), "NE-M-28000", "Lincoln"),
    ("the Douglas County Courthouse, Omaha", -95.9390, 41.2586, _want("31055", 7, 2, 4, 4, 2, 2, 4, 4, "papio-missouri-river", 19, "metropolitan"), "NE-M-37000", "Omaha"),
    ("Olde Towne Bellevue", -95.8908, 41.1367, _want("31153", 45, 1, 2, 2, 4, 3, 5, 2, "papio-missouri-river", 3, "metropolitan"), "NE-M-03950", "Bellevue"),
    ("downtown Papillion", -96.0431, 41.1544, _want("31153", 14, 1, 2, 2, 4, 3, 2, 2, "papio-missouri-river", 3, "metropolitan"), "NE-M-38295", "Papillion"),
    ("downtown Ralston", -96.0425, 41.2053, _want("31055", 12, 2, 4, 4, 4, 2, 4, 4, "papio-missouri-river", 3, "metropolitan"), "NE-M-40605", "Ralston"),
    ("downtown Gretna", -96.2397, 41.1408, _want("31153", 36, 2, 2, 2, 4, 3, 2, 2, "papio-missouri-river", 3, "metropolitan"), "NE-M-20260", "Gretna"),
    ("west Omaha (Elkhorn)", -96.2360, 41.2860, _want("31055", 39, 2, 4, 4, 3, 3, 8, 3, "papio-missouri-river", 3, "metropolitan"), "NE-M-37000", "Elkhorn"),
    ("south Lincoln", -96.68, 40.74, _want("31109", 30, 1, 3, 3, 1, 1, 5, 5, "lower-platte-south", 18, "southeast"), "NE-M-28000", "Lincoln"),
    ("downtown Grand Island", -98.3420, 40.9264, _want("31079", 35, 3, 9, 9, 5, 5, 6, 6, "central-platte", 10, "central"), "NE-M-19595", "Grand Island"),
    ("downtown Kearney", -99.0817, 40.6994, _want("31019", 37, 3, 9, 9, 6, 5, 6, 6, "central-platte", 10, "central"), "NE-M-25055", "Kearney"),
    ("downtown North Platte", -100.7654, 41.1239, _want("31111", 42, 3, 11, 11, 6, 5, 7, 7, "twin-platte", 16, "mid-plains"), "NE-M-35000", "North Platte"),
    ("downtown Scottsbluff", -103.6672, 41.8666, _want("31157", 48, 3, 12, 12, 6, 5, 7, 7, "north-platte", 13, "western"), "NE-M-44245", "Scottsbluff"),
    ("downtown Norfolk", -97.4170, 42.0327, _want("31119", 19, 1, 7, 7, 3, 4, 3, 3, "lower-elkhorn", 8, "northeast"), "NE-M-34615", "Norfolk"),
    ("downtown Hastings", -98.3884, 40.5863, _want("31001", 33, 3, 10, 10, 6, 4, 6, 6, "little-blue", 9, "central"), "NE-M-21415", "Hastings"),
    ("Valentine, Cherry County", -100.5510, 42.8728, _want("31031", 43, 3, 8, 8, 6, 5, 7, 7, "middle-niobrara", 17, "mid-plains"), "NE-M-49950", "Valentine"),
    ("Merriman, Cherry County", -101.7003, 42.9186, _want("31031", 43, 3, 8, 8, 6, 5, 7, 7, "middle-niobrara", 13, "western"), "NE-M-31815", "Gordon-Rushville"),
    ("Albion, Boone County", -98.0037, 41.6908, _want("31011", 41, 3, 5, 5, 3, 4, 6, 6, "lower-loup", 7, "central"), "NE-M-00555", "Boone Central"),
    ("a field in Cliff township, Custer County", -99.90, 41.50, _want("31041", 43, 3, 8, 8, 6, 5, 7, 7, "lower-loup", 10, "mid-plains"), "NE-M-09620", "Anselmo-Merna"),
    ("downtown Blair", -96.1250, 41.5444, _want("31177", 16, 3, 6, 6, 3, 4, 3, 3, "papio-missouri-river", 3, "metropolitan"), "NE-M-05350", "Blair"),
    ("a field in Township 6, Washington County", -96.25, 41.52, _want("31177", 16, 3, 6, 6, 3, 4, 3, 3, "papio-missouri-river", 3, "metropolitan"), "NE-M-49130", "Blair"),
    ("downtown Columbus", -97.3684, 41.4297, _want("31141", 22, 1, 5, 5, 5, 4, 3, 3, "lower-loup", 7, "central"), "NE-M-10110", "Columbus"),
    ("a field in Burrows township, Platte County", -97.60, 41.62, _want("31141", 22, 1, 5, 5, 5, 4, 3, 3, "lower-platte-north", 7, "central"), "NE-M-07275", "Humphrey"),
    ("Osceola, Polk County", -97.5475, 41.1797, _want("31143", 24, 1, 5, 5, 5, 4, 3, 5, "upper-big-blue", 7, "central"), "NE-M-37525", "Osceola"),
    ("downtown Chadron", -103.0000, 42.8290, _want("31045", 43, 3, 12, 12, 6, 5, 7, 7, "upper-niobrara-white", 13, "western"), "NE-M-08605", "Chadron"),
    ("Nebraska City, Otoe County", -95.8590, 40.6767, _want("31131", 1, 3, 1, 2, 5, 1, 5, 2, "nemaha", 4, "southeast"), "NE-M-33705", "Nebraska City"),
    ("Geneva, Fillmore County", -97.5959, 40.5269, _want("31059", 32, 3, 1, 10, 5, 4, 6, 5, "upper-big-blue", 6, "southeast"), "NE-M-18405", "Fillmore Central"),
]
LINE_POINTS = [("the Douglas-Sarpy county line (Harrison Street)", -96.05, 41.19, ("31055", "31153")),
               ("the Lancaster-Saunders county line north of Lincoln", -96.70, 41.046, ("31109", "31155"))]
LAYER_SLACK = 0.005
SAID = ("county_court", "appeals", "psc", "regents", "sboe", "nrd", "esu", "college")


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
    check(layer_ids.get("senate") == {str(n) for n in range(1, N_LEG + 1)} and "house" not in layer_ids
          and layer_ids.get("judicial") == {f"NE-DC{n}" for n in range(1, N_COURT + 1)}
          and layer_ids.get("cd") == {str(n) for n in range(1, N_CD + 1)} and len(layer_ids.get("county", ())) == N_COUNTIES
          and layer_ids.get("com") == {f"{c}|District {n}" for c, v in BOARDS.items() for n in range(1, v[2] + 1)},
          f"there are not {N_LEG} legislative districts (and no house layer), {N_COURT} judicial districts, {N_COUNTIES} counties, {N_CD} congressional districts and "
          f"{sum(v[2] for v in BOARDS.values())} county board districts")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it;
    #    what it says of the districts no layer draws is whole, and the same for every piece of one county where the law makes it so
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place, council, ward = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "senate": "senate", "cd": "cd", "judicial": "judicial"}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    said_seen = collections.defaultdict(set)
    missing_said, by_county = 0, collections.defaultdict(lambda: collections.defaultdict(set))
    want_said = {"county_court": r"NE-CC([1-9]|1[0-2])", "appeals": r"NE-COA[1-6]", "psc": r"NE-PSC[1-5]", "regents": r"NE-REG[1-8]", "sboe": r"NE-SBOE[1-8]",
                 "nrd": r"NE-X-[a-z-]+-natural-resources-district", "esu": r"NE-X-educational-service-unit-no-\d+", "college": r"NE-X-[a-z-]+-community-college"}
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
            for k in SAID:
                ok = isinstance(pr.get(k), str) and re.fullmatch(want_said[k], pr[k]) and doc["names"].get(k, {}).get(pr[k])
                missing_said += not ok
                said_seen[k].add(pr.get(k))
                by_county[k][c["id"]].add(pr.get(k))
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
                if i % 2 and kind != "senate":
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
    check(missing_said == 0, f"{missing_said} times a precinct does not name one of {', '.join(SAID)} with an id of the right form and a name in its county's file")
    check([len(said_seen[k]) for k in SAID] == [12, 6, 5, 8, 8, 23, len(said_seen["esu"]), 6] and 15 <= len(said_seen["esu"]) <= 19,
          f"the precincts name {', '.join(f'{len(said_seen[k])} {k}' for k in SAID)}: not 12 county judge districts, 6 court of appeals, 5 commission, 8 regents, "
          "8 board of education districts, 23 natural resources districts and 6 community college areas")
    two = {k: sorted(c for c, v in by_county[k].items() if len(v) > 1) for k in ("county_court", "college")}
    check(not two["county_court"] and two["college"] == sorted(COLLEGE_PARTS), f"counties whose precincts name two districts: county judge {two['county_court']}, "
          f"community college {two['college']} (only Boone and Cherry counties are divided, and only between community college areas)")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * half, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["a place the precinct does not name"] <= 0.02 * half, f"the place at a precinct's own point: {dict(place)}")
    check(council["a district the precinct does not name"] + council["no district"] <= 0.02 * max(1, sum(council.values())), f"the board district at a precinct's own point: {dict(council)}")
    check(ward["a ward the precinct does not name"] + ward["no ward"] <= max(1, 0.1 * sum(ward.values())), f"the ward at a precinct's own point: {dict(ward)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + f"); school district at {half:,} precincts' points: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city, village or township: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])) + "; county board district: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(council.items(), key=lambda x: -x[1])) + "; ward: "
        + ("; ".join(f"{n:,} {what}" for what, n in sorted(ward.items(), key=lambda x: -x[1])) or "none drawn")
        + f"; every precinct names its county judge, court of appeals, commission, regents, education board, natural resources, service unit and college districts "
          f"({', '.join(str(len(said_seen[k])) for k in SAID)} of them)")

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
        sn = index["school"].get("census_names", {}).get(sid) or fdoc["names"]["school"].get(sid, "") if sid else ""
        ok &= check(sid is not None and sid in pr["school"] and school_word in sn, f"{name}: the school district at the point is {sid} ({sn}), which should name {school_word!r}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        if mcd:
            ok &= check(shape is not None and shape["id"] == mcd and mcd in ([pr["mcd"]] + pr.get("mcd_all", [])),
                        f"{name}: the mcd layer gives {shape and shape['id']} and the precinct names {[pr['mcd']] + pr.get('mcd_all', [])}; the place is {mcd}")
        else:                                              # open country in a county without township government
            ok &= check(shape is None, f"{name}: the mcd layer gives {shape and shape['id']} in open country")
        for prop, kind in layer_for.items():
            shape2, edge2 = G.shape_at(files, kind, lon, lat)
            if shape2 is not None and edge2 <= tol_of[kind] + 10:      # the far-out layer's line is generalised: this close to it, the county file is the one to ask
                continue
            ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {pr.get(prop)}")
        extra = ""
        for k in ("com", "ward"):
            if pr.get(k) or (k == "com" and found["county"] in BOARDS):
                shape3, _edge = G.shape_at(files, k, lon, lat)
                extra += f", {k} {shape3 and shape3['id']}"
                if k == "com":
                    ok &= check(shape3 is not None and shape3["id"].startswith(found["county"] + "|"), f"{name}: no board district of {found['county']} at the point")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape['properties']['name'] if shape else 'open country'}, "
            f"{fdoc['name']}, Legislature {pr['senate']}, Congress {pr['cd']}, {pr['judicial']}, {pr['county_court']}, {pr['appeals']}, {pr['psc']}, {pr['regents']}, "
            f"{pr['sboe']}, {fdoc['names']['nrd'][pr['nrd']]}, {fdoc['names']['esu'][pr['esu']]}, {fdoc['names']['college'][pr['college']]}, {sn}{extra}; "
            f"{found['edge']:.0f} m from the precinct's line")

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
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"]))
              and all(0 <= i < n for rows in polls["by_county"].values() for r in rows for i in r["places"]),
              "polling_places.json names a precinct or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        pts = [p for p in polls["places"] if p.get("lonlat")]
        inside = 0
        for p in pts:
            f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
            inside += bool(f3) and f3["county"] == p["county"]
        check(inside >= 0.97 * len(pts), f"only {inside} of {len(pts)} polling places lie inside their own county")
        say(f"      self-test: polling places: {polls.get('status')}; {n:,} places of one county, {len(pts):,} with a point ({inside:,} inside the county); "
            f"{sum(len(v) for v in polls['by_county'].values())} of the county's own precincts listed; {len(polls['counties_not_on_the_list'])} counties not on the list")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Nebraska's ballot map -> ballot_geo/ne/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/ne)")
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
