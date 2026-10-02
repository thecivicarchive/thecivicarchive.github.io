"""
ballot/mi_geo.py - the geography behind Michigan's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py and ballot/sd_geo.py for the few things those states added, and changes nothing in
any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read them all.

    python ballot/mi_geo.py                 builds ballot_geo/mi/ and runs the self-test (about fifteen minutes the
                                            first time, most of it laying districts over precincts; about three after)
    python ballot/mi_geo.py --selftest      runs the self-test on the files already built
    python ballot/mi_geo.py --refresh       asks the map services and the statute again even when the copies are fresh
    python ballot/mi_geo.py --out DIR       builds somewhere else (a trial run)
    python ballot/mi_geo.py --polls DIR     looks for a saved polling place list in another folder (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names, for the words the
ballot database uses for council wards, and for the check that every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/mi_local/)
----------------------------------------------------------------------------------------------------------------------
  - Precincts: the Michigan Department of State, Bureau of Elections, "2026 Voting Precincts", published on the State
    of Michigan's GIS Open Data site (gis-michigan.opendata.arcgis.com): 3,895 precincts, each with the Bureau's
    precinct id, its county, its city or township (the Census code), its ward and its name. Only those columns are
    asked for; the layer's counts of registered and active voters never are.
  - State House and Senate districts: "Remedial State House Districts 2021 - Approved in 2024" and "Remedial State
    Senate Districts 2021 - Approved in 2024", the State's own layers of the plans the federal court approved after
    Agee v. Benson (the House plan first used in 2024, the Senate plan first used in 2026). Congressional districts:
    "Michigan U.S. Congressional Districts 2021" (the 2021 plan, still in force). Only the district number is asked
    for; the layers' legislator and party columns never are.
  - County commissioner districts: "2021 County Commissioner Districts v25" (the State's layer of the districts each
    county's apportionment commission drew in 2021). Only the county and the district number are asked for; the
    layer's commissioner and party columns never are.
  - School districts and villages: the Michigan Geographic Framework's "School District" (each row with the Center
    for Educational Performance and Information's five-digit district code) and "Village" layers, on the same site.
    (The same site's "Community College Districts" layer is not used: it mixes district lines with whole counties
    drawn for context, so two colleges' shapes lie over one another and it cannot say which district a place is in.)
  - District court districts and judicial circuits: the Revised Judicature Act, chapters 5 and 81 (MCL 600.501 to
    600.550a and 600.8101 to 600.8163), the Legislature's own PDFs, read with ballot/state_local_mi.py's reader. A
    district court district is a group of counties, cities and townships, so its shape is put together from whole
    precincts by each precinct's county and city or township. See DISTRICT COURTS.
  - Names of cities, villages and townships: the Census Bureau's 2020 code lists for Michigan (st26_mi_cousub2020.txt,
    st26_mi_place2020.txt), which is how sl_places names them ("Addison township").
  - michigan.gov and the Michigan Voter Information Center refuse scripts and are never asked for anything.

Lines. The Bureau's precincts are very nearly one fabric: a line two neighbours share is the same line in both, except
that one in ten such lines was drawn twice a few centimetres apart. Corners within KNIT_M (one metre, the files' own
grid) of one another are made one corner (ballot/nd_geo.py's knit), after which nine lines in ten have a precinct on
both sides. The rest are shore: the precincts stop at the Great Lakes and the rivers between them, and a line with a
precinct on one side only is written as the map's edge. In a few places two neighbours' drawings stay more than a
metre apart; a point in the gap between them is given to the nearest precinct within 30 metres, as a point on any
line is.

What is built (ballot_geo/mi/): index.json, manifest.json, precincts/<county>.json (83; id = the Bureau's precinct id,
WP-<county>-<city or township>-<ward and precinct>), layers/<kind>.json (state, county, cd, senate, house, judicial,
mcd, ward, com, school), school/<id>.json, polling_places.json and reader.js, each as ballot/mn_geo.py describes.
Coordinates are on the same grid (0.00001 degree, translate [-98, 43]; the south of Michigan lies below 43 north, so
grid latitudes there are negative numbers, which TopoJSON allows).

Which layers are whose lines. State, county, city and township, ward and district court are put together from whole
precincts (the precinct table says which each precinct is in). Congressional, Senate, House, county commissioner and
school districts and villages are drawn from their own layers; which of them a precinct lies in is worked out here by
laying those lines over the precinct (analysis, not an official list).

Split precincts. Michigan lets a precinct straddle a district line (its voters then get different ballots), and about
one precinct in fourteen does (287 of 3,895): a House, Senate, congressional or county commissioner line runs through it. Such a
precinct is cut along those lines here (see CUTTING), and each piece is a shape of its own in the county file: id
<precinct id>.<n>, name "..., part n", with the Bureau's id under "precinct", so a point is given the districts of
the piece it is in and not those of the larger half. A second district counts only when it holds 3 percent of the
precinct or more and its part is at least 60 metres thick somewhere; anything less is the two files' drawings of one
line differing by a few metres, and the precinct stays whole.

CUTTING
-------
For one precinct: its own edges and the edges of the districts that reach it are cut at every crossing, the district
edges outside it are dropped, and what is left is walked face by face. Each face is given the districts found at a
point just inside it; a face narrower than 20 metres or smaller than 2,000 square metres (a sliver between the two
files' drawings of one line) joins the neighbour it shares most of its edge with; faces of the same districts are put
together into one piece. The pieces' areas must add up to the precinct's, or the precinct is left whole and listed as
split. The district files' lines are not moved to fit the precincts' (tried on 2026-10-02: making the two drawings
one line within a metre tangled the precinct fabric), so a piece's inner edge is the district file's own line.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "MI" (j = "26", the jurisdiction_id of statewide races)
  county    "26163"                 sl_places county id; jurisdiction_id of county offices
  mcd       "MI-M-22000"            MI-M- and the Census code: a city's or township's county subdivision code, a
                                    village's place code (properties.t says city, township or village). A village
                                    lies inside a township and its voters are in both; the villages come first in
                                    the layer, so a point inside a village is given the village.
  ward      "MI-M-34000|Ward 1"     <city>|<ward as the council race words it>
  com       "26163|5"               <county>|<commissioner district>
  house     "77"   senate "21"   cd "7" (properties.race is the federal race id, 2026-MI-H07)
  judicial  "MI-DC36", "MI-DC52-1"  a district court district, or its election division where judges are elected by
                                    division: the jurisdiction_id of a district court race
  school    "MI-S-33020"            MI-S- and the district's five-digit code
A precinct also names its judicial circuit ("circuit": "MI-CC30", the jurisdiction_id of a circuit court race); no
layer draws the circuits, which are whole counties.

DISTRICT COURTS
---------------
Chapter 81 of the Revised Judicature Act says what each district consists of ("the cities of Warren and Center Line",
"the county of Oakland except the cities of ..."), and for some districts which election divisions it has. It also
keeps alternatives side by side: a district as it is, and as it would be if its local governments consolidated it
with a neighbour (the 2nd, or 2A and 2B). Which alternative is in force is not in the act. The Bureau of Elections'
candidate listing is: a district or division that has a seat on the November 2026 ballot is in force, and an
alternative is set aside when a listed district of another number takes in the whole of one of its cities or
townships. Of the districts left, the one that names a city or township itself comes before one that takes it in
with its county (a city that reaches into a second county is in its own district there too); among those, the one
on the 2026 listing (the smaller, where two are); failing that, the only one; and where the act still offers two, the
place is given to neither, and index.json says so. Nothing is filled in from memory.

Not drawn, because no statewide file has trustworthy lines: city council districts that are not the wards of the
precinct table, district library districts, community college districts, and Court of Appeals districts (their
races carry no jurisdiction id; every district's race is listed for every reader). Circuit and
probate judges are elected by counties, and the page places them by county. index.json lists every race without a
shape under "check", with the reason.

POLLING PLACES
--------------
No state page a script may read carries Michigan's polling places: the Michigan Voter Information Center answers for
one voter or one address at a time and refuses scripts, michigan.gov refuses scripts, and the State's GIS Open Data
site publishes precincts and no polling places. The list is kept in the Qualified Voter File by each city and township
clerk; a statewide copy would have to be asked of the Bureau of Elections. If John obtains one and saves it (as it is:
.xlsx, .csv or .txt) into states_cache/mi_local/boe/pollingplaces/ this builder reads it: columns are found by their
headings; only the county, the city or township, the ward and precinct, the place's name and street address and any
coordinates are kept. The reader was written before any such file had been seen, so its output is marked "unchecked",
which a page must not show, until a person has compared it with the file and set POLL_LAYOUT_CHECKED to True.
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import nd_geo as N  # noqa: E402
from ballot import sd_geo as S  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "MI", "26", "Michigan"
OUT = os.path.join(HERE, "ballot_geo", "mi")
CACHE = os.path.join(HERE, "states_cache", "mi_local")
POLL_DIR = os.path.join(CACHE, "boe", "pollingplaces")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://mvic.sos.state.mi.us/Voter/Index"

MI_GIS = "https://services3.arcgis.com/dxRQUfTDNtfqZ301/arcgis/rest/services/"      # the State of Michigan's ArcGIS organisation
HUB = "https://gis-michigan.opendata.arcgis.com/datasets/"
PCT_SERVICE = MI_GIS + "VotingPrecinct/FeatureServer/0"
PCT_ITEM = HUB + "b7df95c78668407280a7dead8e26aad0"
PCT_FIELDS = "PrecinctID,CountyFIPS,MCDFIPS,Ward,Precinct,PrecinctCode,VTD,PrecinctLongName,PrecinctShortName,JurisdictionName,ElectionYear"   # never RegisteredVoters, ActiveVoters
HOUSE_SERVICE = MI_GIS + "Remedial_State_House_2021/FeatureServer/0"
HOUSE_ITEM = HUB + "aaf070fe03ac47158a4fec29cf77c3cd"
SENATE_SERVICE = MI_GIS + "Remedial_State_Senate_2021/FeatureServer/0"
SENATE_ITEM = HUB + "bfeeedb6c6ec43bea31a51b164764775"
LEG_FIELDS = "Name,MGFVersion"                                # never Legislator
CD_SERVICE = MI_GIS + "US_Congressional_Districts_2021/FeatureServer/23"
CD_ITEM = HUB + "54edc5b8c1c54de39421e858998a6b31"
CD_FIELDS = "NAME,VER"                                        # never LEGISLATOR, PARTY, URL
COM_SERVICE = "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/boundaries/MapServer/10"
COM_ITEM = HUB + "4c8d0d854ac04d8787cb3cf6dab7fbec"
COM_FIELDS = "CountyFIPS,DistrictCode,DistrictName"           # never Commissioner, Party, Population
SCHOOL_SERVICE = MI_GIS + "SchoolDistrict/FeatureServer/4"
SCHOOL_ITEM = HUB + "d63363e9a7684f8fbea9ddcd309abfad"
SCHOOL_FIELDS = "Name,DCode,MGFVersion"
VILLAGE_SERVICE = MI_GIS + "Village/FeatureServer/1"
VILLAGE_ITEM = HUB + "abc05b6e33f74bc28601b107b4ce341e"
VILLAGE_FIELDS = "FIPSCode,Name,MGFVersion"
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st26_mi_cousub2020.txt"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st26_mi_place2020.txt"
MCL_PDF = "https://www.legislature.mi.gov/documents/mcl/pdf/MCL-236-1961-{}.pdf"

ARC_KINDS = ["county", "mcd", "ward", "com", "house", "senate", "cd", "judicial"]
SPLIT_SHARE = W.SPLIT_SHARE
KNIT_M = 1.0                      # metres: corners of two neighbours' drawings this close together are made one corner
CUT_KINDS = ("house", "senate", "cd", "com")      # the districts a precinct is cut along when one of their lines runs through it
FACE_MIN_W = 20.0                 # metres: a face of a cut precinct narrower than this (twice its area over its perimeter) is a sliver
FACE_MIN_M2 = 2000.0              # square metres: so is one smaller than this
OUTSIDE = "outside"
SNAP = 2                          # grid units of 1e-7 degree (two centimetres): a crossing this close to a corner is the corner
TOL_MCD = I.TOL_MCD               # metres: the mcd layer is the only place a village's lines are, so it is kept fine
MCD_ZOOM = I.MCD_ZOOM             # "good to zoom" for the mcd layer: a page never leaves it for the county files
NEAR_M = G.NEAR_M
POLL_LAYOUT_CHECKED = False       # set to True only when a person has compared the reader's output with a real list


# ---------------------------------------------------------------- the sources

def read_names(cousub_path, place_path):
    """The Census Bureau's 2020 names: ({county subdivision code: name}, {place code: name})."""
    cous, places = {}, {}
    for line in open(cousub_path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
        f = line.split("|")
        if len(f) >= 7 and f[1] == FIPS and f[4] != "00000":
            cous.setdefault(f[4], f[6].strip())
    for line in open(place_path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
        f = line.split("|")
        if len(f) >= 6 and f[1] == FIPS and f[5].strip().upper() == "INCORPORATED PLACE":
            places.setdefault(f[2], f[4].strip())
    if len(cous) < 1400 or len(places) < 500:
        raise GeoError("    the Census Bureau's code lists for Michigan do not read as this builder was checked against (1,500 cities and townships, 530 cities and villages); stopping")
    return cous, places


def read_precincts(doc, cousub_name):
    """The precinct rows, in the Bureau's id order, cut down to what the map needs, and their rings as vertex keys. A
    table that no longer fits what this was checked against stops the build, naming the check."""
    rows = sorted(doc["rows"], key=lambda r: r[0]["PrecinctID"])
    pre, polys, seen = [], [], set()
    for a, rings in rows:
        pid, county, mcd, ward, pct = (G.blank(a[k]) for k in ("PrecinctID", "CountyFIPS", "MCDFIPS", "Ward", "Precinct"))
        ok = (re.fullmatch(r"\d{3}", county) and re.fullmatch(r"\d{5}", mcd) and re.fullmatch(r"\d{2}", ward) and re.fullmatch(r"\d{3}[A-Z]?", pct)
              and pid == f"WP-{county}-{mcd}-{ward}{pct}" and pid not in seen and a["ElectionYear"] == 2026 and G.blank(a["PrecinctLongName"])
              and G.blank(a["JurisdictionName"]))
        if not ok:
            raise GeoError(f"    precinct table: the row for {pid!r} does not fit the layout this builder was checked against; stopping")
        seen.add(pid)
        census = cousub_name.get(mcd, "")
        long_name, jname = G.blank(a["PrecinctLongName"]), G.blank(a["JurisdictionName"])
        kind = ("township" if census.endswith("township") else "city" if census.endswith("city") else
                "township" if re.search(r"\bTownship\b", long_name.split(",")[0]) else "city")
        pre.append({"id": pid, "name": long_name, "county": FIPS + county, "mcdcode": mcd, "mcd": f"{STATE}-M-{mcd}", "jname": jname, "kind": kind,
                    "census": census or (f"{re.sub(r' Township$', '', jname)} township" if kind == "township" else f"{jname} city"),
                    "wardcode": str(int(ward)) if int(ward) else "", "pct": re.sub(r"^0+(?=.)", "", pct)})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    if len({p["county"] for p in pre}) != 83:
        raise GeoError(f"    precinct table: {len({p['county'] for p in pre})} counties, not 83; stopping")
    kinds = collections.defaultdict(set)
    for p in pre:
        kinds[p["mcdcode"]].add((p["census"], p["kind"]))
    two = [c for c, v in kinds.items() if len(v) > 1]
    if two:
        raise GeoError(f"    precinct table: the place code {two[0]} is used for two different places; stopping")
    return pre, polys


def read_db(db):
    """Read-only: the names the ballot database gives Michigan's places, the districts its council races name, its
    races (for the check that every shape's id is one the races carry) and the district court districts on its list."""
    info = {"names": {}, "council": collections.defaultdict(set), "races": [], "courts": {}, "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name, cids in con.execute("SELECT kind, id, name, county_ids FROM sl_places WHERE source_id LIKE 'mi-%'"):
            info["names"][(kind, pid)] = name
            if kind == "judicial" and pid.startswith(f"{STATE}-DC"):
                try:
                    info["courts"][pid] = sorted(json.loads(cids or "[]"))
                except ValueError:
                    info["courts"][pid] = []
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    for _rid, _level, kind, _jur, jid, district, _seat, _c in info["races"]:
        if kind == "council" and district:
            info["council"][jid].add(district)
    info["found"] = True
    return info


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed: for each precinct,
    [[district number, share of the precinct's area, thick enough]]."""
    path = os.path.join(CACHE, f"mi_geo_overlay_{name}.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say(f"      laying the {name} lines over the precincts (some minutes; kept for the next build)")
    res = G.school_overlay(pre_rings, districts, levels=(G.SCHOOL_THICK,), say=None)
    rows = [[[d, round(share, 5), thick[0]] for d, share, thick in row] for row in res]
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def numbered(doc, field, count, what):
    """A layer of districts numbered 1 to count -> its rows keyed by the number, as text."""
    rows = N.merge_rows(doc["rows"], lambda a: str(int(a[field])))
    keys = sorted((str(int(a[field])) for a, _r in rows), key=int)
    if keys != [str(n) for n in range(1, count + 1)]:
        raise GeoError(f"    {what}: not {count} districts numbered 1 to {count}; stopping")
    return rows


# ---------------------------------------------------------------- cutting a precinct along the district lines that cross it

def kxy(x, y):
    """The vertex key of a point given in whole units of 1e-7 degree (what mn_geo.vxy gives back)."""
    return ((x + G.XOFF) << 30) | y


def _meet(p, q, r, s):
    """Where two edges meet: (points to cut p-q at, points to cut r-s at). A proper crossing is one point, rounded to
    the grid; an end of one lying on the other cuts the other there (which also takes care of edges that overlap)."""
    d1 = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d2 = (q[0] - p[0]) * (s[1] - p[1]) - (q[1] - p[1]) * (s[0] - p[0])
    d3 = (s[0] - r[0]) * (p[1] - r[1]) - (s[1] - r[1]) * (p[0] - r[0])
    d4 = (s[0] - r[0]) * (q[1] - r[1]) - (s[1] - r[1]) * (q[0] - r[0])
    if ((d1 > 0) != (d2 > 0)) and d1 and d2 and ((d3 > 0) != (d4 > 0)) and d3 and d4:
        t = d1 / (d1 - d2)
        x = (r[0] + int(round((s[0] - r[0]) * t)), r[1] + int(round((s[1] - r[1]) * t)))
        for e in (p, q, r, s):                                # a crossing within two centimetres of a corner is that corner
            if abs(x[0] - e[0]) <= SNAP and abs(x[1] - e[1]) <= SNAP:
                x = e
                break
        return ([x] if x != p and x != q else []), ([x] if x != r and x != s else [])

    def on(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]) and c != a and c != b)

    return [c for c in (r, s) if on(p, q, c)], [c for c in (p, q) if on(r, s, c)]


def _fixed_meet(a, b, c, d):
    """Where the edge c-d must be cut so that it meets the edge a-b at one of a-b's own ends: a-b is a precinct's
    edge, which already has a corner wherever a district line crosses it (crossings), and is not cut again; a
    district edge that crosses it is cut at the nearer of its two ends."""
    d1 = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d2 = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
    d3 = (d[0] - c[0]) * (a[1] - c[1]) - (d[1] - c[1]) * (a[0] - c[0])
    d4 = (d[0] - c[0]) * (b[1] - c[1]) - (d[1] - c[1]) * (b[0] - c[0])
    if ((d1 > 0) != (d2 > 0)) and d1 and d2 and ((d3 > 0) != (d4 > 0)) and d3 and d4:
        t = d3 / (d3 - d4)                                    # how far along a-b the crossing is
        e = a if t < 0.5 else b
        return [e] if e != c and e != d else []
    return [e for e, side in ((a, d3), (b, d4)) if side == 0 and e != c and e != d      # an end of a-b lying on c-d cuts it there
            and min(c[0], d[0]) <= e[0] <= max(c[0], d[0]) and min(c[1], d[1]) <= e[1] <= max(c[1], d[1])]


def node_segments(segs, fixed=None):
    """segs: [(a, b, tag)] with a, b grid points. Every edge is cut wherever another meets it, until none crosses
    another; returns the pieces, each with the tag of the edge it was cut from. Edges whose tag is `fixed` are never
    cut: an edge that crosses one is cut at the fixed edge's nearer end instead."""
    segs = [(a, b, f) for a, b, f in segs if a != b]
    for _pass in range(12):
        x0, y0 = min(min(a[0], b[0]) for a, b, _f in segs), min(min(a[1], b[1]) for a, b, _f in segs)
        x1, y1 = max(max(a[0], b[0]) for a, b, _f in segs), max(max(a[1], b[1]) for a, b, _f in segs)
        cell = max(x1 - x0, y1 - y0, 64) / 64.0
        grid = collections.defaultdict(list)
        for i, (a, b, _f) in enumerate(segs):
            for gx in range(int((min(a[0], b[0]) - x0) / cell), int((max(a[0], b[0]) - x0) / cell) + 1):
                for gy in range(int((min(a[1], b[1]) - y0) / cell), int((max(a[1], b[1]) - y0) / cell) + 1):
                    grid[(gx, gy)].append(i)
        cuts, seen = collections.defaultdict(set), set()
        for bucket in grid.values():
            for n, i in enumerate(bucket):
                a, b, f = segs[i]
                for j in bucket[n + 1:]:
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    c, d, g = segs[j]
                    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]) or max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
                        continue
                    if fixed is not None and (f == fixed or g == fixed):
                        if f != g:
                            if f == fixed:
                                cuts[j].update(_fixed_meet(a, b, c, d))
                            else:
                                cuts[i].update(_fixed_meet(c, d, a, b))
                        continue
                    on_i, on_j = _meet(a, b, c, d)
                    cuts[i].update(on_i)
                    cuts[j].update(on_j)
        if not any(cuts.values()):
            break
        out = []
        for i, (a, b, f) in enumerate(segs):
            pts = cuts.get(i)
            if not pts:
                out.append((a, b, f))
                continue
            chain = [a] + sorted(pts, key=lambda c: (c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) + [b]
            out.extend((u, v, f) for u, v in zip(chain, chain[1:]) if u != v)
        segs = out
    return segs


def crossings(rings, cutters):
    """Where district edges cross one precinct's own edges: {(a, b) with a < b, an edge of the precinct: the new points
    on it}. Worked out on the precinct's edges as its neighbours have them too, so that both sides of a shared edge
    come to the very same points."""
    own = [(a, b) for r in rings for a, b in zip(r, r[1:] + r[:1])]
    out = collections.defaultdict(set)
    for a, b, tag in node_segments([(a, b, n) for n, (a, b) in enumerate(own)] + [(a, b, -1) for a, b in cutters]):
        if tag >= 0:
            ends = own[tag]
            out[ends if ends[0] < ends[1] else (ends[1], ends[0])].update(c for c in (a, b) if c not in ends)
    return {k: v for k, v in out.items() if v}


def add_points(polys, points):
    """Give every ring that has an edge named in `points` ({(a, b) with a < b, as vertex keys: the new points}) those
    points, in their order along the edge. Returns how many were put in."""
    put = 0
    for rings in polys:
        for n, ks in enumerate(rings):
            new, a = [], ks[-1]
            for b in ks:
                extra = points.get((a, b) if a < b else (b, a))
                if extra:
                    (ax, ay), (bx, by) = G.vxy(a), G.vxy(b)
                    order = sorted(extra, key=lambda k: (G.vxy(k)[0] - ax) * (bx - ax) + (G.vxy(k)[1] - ay) * (by - ay))
                    new.extend(order)
                    put += len(order)
                new.append(b)
                a = b
            if len(new) != len(ks):
                rings[n] = new
    return put


def cut_rings(rings, cutters, label_at):
    """One precinct's rings (grid points, Esri's winding) cut along the district edges `cutters` ([(a, b)]). label_at(x,
    y) names the districts at a point inside the precinct. Returns {label: [ring as vertex keys, the piece on the right
    of each edge]} when the precinct falls into two pieces or more, else None; and a word on why not."""
    c0 = math.cos(math.radians(rings[0][0][1] / 1e7))
    kx, ky = G.M_PER_UNIT * c0, G.M_PER_UNIT
    edges = collections.defaultdict(int)
    for a, b, f in node_segments([(a, b, 1) for r in rings for a, b in zip(r, r[1:] + r[:1])] + [(a, b, 2) for a, b in cutters], fixed=1):
        edges[(a, b) if a < b else (b, a)] |= f
    along = {(a, b) for r in rings for a, b in zip(r, r[1:] + r[:1])}      # Esri winds a ring with the precinct on its right: the face on the left of such an edge is outside
    for a, b in [e for e in along if e[0] < e[1] and (e[1], e[0]) in along]:      # a ring that runs out along a line and back along it: no width, no edge
        along -= {(a, b), (b, a)}
        edges.pop((a, b), None)
    for (a, b), f in list(edges.items()):                     # a district edge counts only inside the precinct
        if f == 2 and not G.in_rings((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, rings):
            del edges[(a, b)]
    while True:                                               # and only if it leads somewhere: loose ends cut nothing
        deg = collections.Counter()
        for a, b in edges:
            deg[a] += 1
            deg[b] += 1
        loose = [e for e, f in edges.items() if f == 2 and (deg[e[0]] == 1 or deg[e[1]] == 1)]
        if not loose:
            break
        for e in loose:
            del edges[e]
    if not any(f == 2 for f in edges.values()):
        return None, "no district line runs through it once the two drawings are made one"
    out = collections.defaultdict(list)
    for a, b in edges:
        out[a].append(b)
        out[b].append(a)
    where = {}
    for u, vs in out.items():
        vs.sort(key=lambda v: math.atan2(v[1] - u[1], v[0] - u[0]))
        for n, v in enumerate(vs):
            where[(u, v)] = n
    face_of, faces = {}, []
    for start in where:
        if start in face_of:
            continue
        cyc, cur = [], start
        while cur not in face_of:                             # the face on the left of each edge: at every corner, the next edge clockwise from the way back
            face_of[cur] = len(faces)
            cyc.append(cur)
            u, v = cur
            cur = (v, out[v][where[(v, u)] - 1])
        faces.append(cyc)
    labels, small, a2s = [], [], []
    for n, cyc in enumerate(faces):
        a2 = sum(u[0] * v[1] - v[0] * u[1] for u, v in cyc)
        per = sum(math.hypot((v[0] - u[0]) * kx, (v[1] - u[1]) * ky) for u, v in cyc)
        u, v = max(cyc, key=lambda e: (e[1][0] - e[0][0]) ** 2 + (e[1][1] - e[0][1]) ** 2)
        dx, dy = v[0] - u[0], v[1] - u[1]
        ln = math.hypot(dx, dy)
        px, py = (u[0] + v[0]) / 2.0 - dy / ln * 2.0, (u[1] + v[1]) / 2.0 + dx / ln * 2.0      # two centimetres to the left of its longest edge
        labels.append(OUTSIDE if any(e in along for e in cyc) else label_at(px, py))
        a2s.append(a2)
        area = a2 / 2.0 * kx * ky
        if a2 > 0 and labels[-1] != OUTSIDE and (area < FACE_MIN_M2 or 2 * area / per < FACE_MIN_W):
            small.append((area, n))
    inside2 = sum(a2 for a2, lab in zip(a2s, labels) if lab != OUTSIDE)      # the precinct's own area, twice, in grid units: what the pieces must add up to
    group = list(range(len(faces)))                           # a sliver joins the neighbour it shares most of its edge with, and goes where that one goes

    def top(n):
        while group[n] != n:
            group[n] = group[group[n]]
            n = group[n]
        return n

    for _area, n in sorted(small):
        w = collections.Counter()
        for u, v in faces[n]:
            o = face_of[(v, u)]
            if labels[o] != OUTSIDE and top(o) != top(n):
                w[top(o)] += math.hypot((v[0] - u[0]) * kx, (v[1] - u[1]) * ky)
        if w:
            group[top(n)] = max(sorted(w), key=lambda k: w[k])
    final = [labels[top(n)] if lab != OUTSIDE else OUTSIDE for n, lab in enumerate(labels)]
    size = collections.Counter()
    for a2, lab in zip(a2s, final):
        if lab != OUTSIDE:
            size[lab] += a2 / 2.0 * kx * ky
    if not size:
        return None, "no face of it could be placed"
    main = max(sorted(size, key=str), key=lambda k: size[k])
    final = [main if lab != OUTSIDE and size[lab] < FACE_MIN_M2 else lab for lab in final]      # a piece that is all slivers is no piece
    kept = sorted({lab for lab in final if lab != OUTSIDE}, key=G.natkey)
    if len(kept) < 2:
        return None, "the second district's part of it is only a sliver along a line"
    sides = collections.defaultdict(set)
    for (u, v), n in face_of.items():
        if final[n] != OUTSIDE and final[face_of[(v, u)]] != final[n]:
            sides[final[n]].add((kxy(*v), kxy(*u)))             # the piece on the right, as Esri winds
    pieces = {lab: S.loops(sides[lab]) for lab in kept}
    signed = lambda ks: -G.area2([G.vxy(k) for k in ks])      # noqa: E731
    whole = sum(-G.area2(r) for r in rings)
    parts = sum(signed(r) for rs in pieces.values() for r in rs)
    if parts != inside2 or inside2 != whole or any(sum(signed(r) for r in rs) <= 0 for rs in pieces.values()):
        return None, "its pieces did not add up to the whole precinct"
    return pieces, None


def cut_precincts(pre, polys, lines, say):
    """Cut every precinct a district line runs through. lines: {kind: (keys, polygons as vertex keys)}. Returns (pre,
    polys) with a row per piece, and [(precinct id, kinds, why)] for those left whole."""
    index = {}
    for kind, (keys, dpolys) in lines.items():
        for key, rings in zip(keys, dpolys):
            xy = [[G.vxy(k) for k in ks] for ks in rings]
            box = (min(p[0] for r in xy for p in r), min(p[1] for r in xy for p in r), max(p[0] for r in xy for p in r), max(p[1] for r in xy for p in r))
            index[(kind, key)] = (xy, box)
    def cutters_of(p, xy):
        """The kinds a precinct is split by, the districts of each that reach it (largest share first), and their edges near it."""
        kinds = [k for k in CUT_KINDS if k in (p.get("split") or {})]
        x0, y0 = min(q[0] for r in xy for q in r) - 50, min(q[1] for r in xy for q in r) - 50
        x1, y1 = max(q[0] for r in xy for q in r) + 50, max(q[1] for r in xy for q in r) + 50
        cutters, kept = set(), {}
        for kind in kinds:
            kept[kind] = [key for key in sorted(p["split"][kind], key=lambda d: -p["split"][kind][d]) if (kind, key) in index]
            for key in kept[kind]:
                dxy, box = index[(kind, key)]
                if box[0] > x1 or box[2] < x0 or box[1] > y1 or box[3] < y0:
                    continue
                for r in dxy:
                    for a, b in zip(r, r[1:] + r[:1]):
                        if not (max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1):
                            cutters.add((a, b) if a < b else (b, a))
        return kinds, kept, sorted(cutters)

    # first, where the district lines cross the precincts' edges: those points are given to every ring that has the edge,
    # so that a cut precinct and its neighbour (cut or not) still share one line, point for point
    todo = [n for n, p in enumerate(pre) if any(k in (p.get("split") or {}) for k in CUT_KINDS)]
    points = collections.defaultdict(set)
    for n in todo:
        xy = [[G.vxy(k) for k in ks] for ks in polys[n]]
        _kinds, _kept, cutters = cutters_of(pre[n], xy)
        for (a, b), new in crossings(xy, cutters).items():
            ka, kb = kxy(*a), kxy(*b)
            points[(ka, kb) if ka < kb else (kb, ka)].update(kxy(*c) for c in new)
    shared = add_points(polys, points)

    out_pre, out_polys, left, cut = [], [], [], 0
    for p, rings in zip(pre, polys):
        pieces, why = None, None
        if any(k in (p.get("split") or {}) for k in CUT_KINDS):
            xy = [[G.vxy(k) for k in ks] for ks in rings]
            kinds, kept, cutters = cutters_of(p, xy)

            def label_at(x, y, kinds=kinds, kept=kept, p=p):
                return tuple(next((key for key in kept[kind] if G.in_rings(x, y, index[(kind, key)][0])), p[kind]) for kind in kinds)

            try:
                pieces, why = cut_rings(xy, cutters, label_at)
            except GeoError:
                pieces, why = None, "its pieces' outlines would not close"
            if pieces is None:
                left.append((p["id"], kinds, why))
        if not pieces:
            out_pre.append(dict(p, precinct=p["id"], parts=1))
            out_polys.append(rings)
            continue
        cut += 1
        for n, (lab, prings) in enumerate(sorted(pieces.items(), key=lambda x: G.natkey(x[0])), 1):
            q = dict(p, id=f"{p['id']}.{n}", name=f"{p['name']}, part {n}", precinct=p["id"], parts=len(pieces))
            q.update(zip(kinds, lab))
            q["split"] = {k: v for k, v in p["split"].items() if k not in kinds}
            if not q["split"]:
                del q["split"]
            out_pre.append(q)
            out_polys.append([list(r) for r in prings])
    say(f"      split precincts: {cut} precincts cut along the district lines that run through them, into {sum(1 for q in out_pre if q['parts'] > 1)} pieces "
        f"({shared:,} crossing points given to the rings on both sides of an edge); "
        f"{len(left)} left whole" + (f" ({'; '.join(f'{n} because {w}' for w, n in sorted(collections.Counter(w for _i, _k, w in left).items()))})" if left else ""))
    return out_pre, out_polys, left


# ---------------------------------------------------------------- district courts, from the act's own words

def statute(refresh, say):
    """The Revised Judicature Act's circuits and district court districts, read by ballot/state_local_mi.py's reader
    from the Legislature's own PDFs of chapters 5 and 81 (kept in this builder's cache)."""
    from ballot import state_local_mi as M
    paths = [os.path.join(CACHE, f"mcl-236-1961-{ch}.pdf") for ch in ("5", "81")]
    fetch = refresh or not all(os.path.exists(p) and os.path.getsize(p) for p in paths)
    return M, M.read_statute(CACHE, say=lambda *_a: None, fetch=fetch), paths


def phrase_places(M, words):
    """One of the act's phrases -> (what it takes in, what it leaves out), each {"counties", "cities", "townships",
    "in": the counties a "in the county of" names for its townships}. A village the act names is filed with the cities
    (the two it names are cities today)."""
    words = re.sub(r",? which is located in .*$", "", words)
    parts = re.split(r",? except(?: for)? ", words, maxsplit=1)

    def lists(part):
        out = {"counties": [], "cities": [], "townships": [], "in": re.findall(rf" in the count(?:y|ies) of ({M.PLACE_NAME})", part)}
        part = re.sub(rf" in the count(?:y|ies) of {M.PLACE_NAME}", "", part)
        for kind, pat in (("counties", r"\bcount(?:y|ies) of "), ("cities", r"\b(?:cit(?:y|ies)|villages?) of "), ("townships", r"\btownships? of ")):
            for m in re.finditer(pat + rf"({M.PLACE_LIST})", part):
                out[kind] += M.list_names(m.group(1))
        return out

    return lists(parts[0]), lists(parts[1]) if len(parts) > 1 else {"counties": [], "cities": [], "townships": [], "in": []}


def court_districts(pre, cshort, info, refresh, say):
    """Each precinct's district court district (or election division) and judicial circuit, as the module's heading
    sets out. Returns (the act's reader's answer, what was found: units, names, problems)."""
    M, st, paths = statute(refresh, say)
    by_county = {M.county_key(n): c for c, n in cshort.items()}
    places = {}                                               # (county, code) -> (kind, name for comparing)
    for p in pre:
        places[(p["county"], p["mcdcode"])] = (p["kind"], M.bare(p["census"]))
    by_name = collections.defaultdict(set)
    for key, (kind, name) in places.items():
        by_name[(kind, name)].add(key)
    not_found, vague = [], []

    def members(spec, within, label):
        """(the places a phrase takes in with a county, the places it names themselves)"""
        whole, got = set(), set()
        for n in spec["counties"]:
            c = by_county.get(M.county_key(n))
            if c is None:
                not_found.append(f"{label}: the county of {n}")
                continue
            whole |= {k for k in places if k[0] == c}
        scope = {by_county.get(M.county_key(n)) for n in spec["in"]} - {None} or within
        for kind, names_ in (("city", spec["cities"]), ("township", spec["townships"])):
            for n in names_:
                hits = by_name.get((kind, M.bare(n)), set())
                codes = {k[1] for k in hits}
                if len(codes) > 1 and scope:                  # two places of one name: the one in the district's own county
                    hits = {k for k in hits if k[0] in scope}
                    codes = {k[1] for k in hits}
                if not hits:
                    not_found.append(f"{label}: the {kind} of {n}")
                elif len(codes) > 1:
                    vague.append(f"{label}: the {kind} of {n} (the act names no county, and {len(codes)} places have the name)")
                else:
                    got |= hits
        return whole, got

    def unit(label, div, sec, inc, exc, within, words, more=None):
        key = label if div is None else f"{label}-{div}"
        w, n = members(inc, within, key)
        xw, xn = members(exc, within, key)
        named = n - xw - xn
        if more:
            named |= members(more, set(), key)[1]
        return {"label": label, "div": div, "sec": sec, "places": ((w | n) - xw - xn) | named, "named": named, "words": words}

    units = {}                                                # "52", "52-1" -> {"label", "div", "sec", "places", "named", "words"}
    label_counties = {}
    for label, (sec, d) in st["districts"].items():
        inc, exc = phrase_places(M, d["words"])
        label_counties[label] = {by_county.get(M.county_key(n)) for n in inc["counties"] + inc["in"]} - {None}
        units[label] = unit(label, None, sec, inc, exc, label_counties[label], M.statute_words(d["words"]))
    for (label, n), (sec, text, also) in st["divisions"].items():
        inc, exc = phrase_places(M, text)
        more = phrase_places(M, also if also.startswith("the ") else "the " + also)[0] if also else None
        units[f"{label}-{n}"] = unit(label, n, sec, inc, exc, label_counties.get(label, set()),
                                     M.statute_words(text) + (f"; also {M.statute_words(also)}" if also else ""), more)

    listed = {i[len(STATE) + 3:] for i in info["courts"]}     # the districts and divisions with a seat on the 2026 listing
    unknown = sorted(listed - set(units))
    by_division = {u["label"] for k, u in units.items() if u["div"] and any(x.startswith(u["label"] + "-") for x in listed)}
    usable = {k: u for k, u in units.items() if (u["div"] is not None) == (u["label"] in by_division)}
    live = {k for k in usable if k in listed}
    live_places = collections.defaultdict(set)
    for k in live:
        for pl in usable[k]["places"]:
            live_places[pl].add(k)
    parts_of = collections.defaultdict(set)                   # a city's or township's code -> its parts, county by county
    for pl in places:
        parts_of[pl[1]].add(pl)
    dead = set()                                              # an alternative: a listed district of another number takes in the whole of one of its places
    for k, u in usable.items():
        if k not in live and any(all(any(usable[o]["label"] != u["label"] for o in live_places.get(part, ())) for part in parts_of[code])
                                 for code in {pl[1] for pl in u["places"]}):
            dead.add(k)
    chosen, two_listed, two_offered, none = {}, [], [], []
    for pl in sorted(places):
        pool = [k for k, u in usable.items() if pl in u["places"] and k not in dead]
        pool = [k for k in pool if pl in usable[k]["named"]] or pool
        mine = sorted((k for k in pool if k in live), key=lambda k: (len(usable[k]["places"]), k))
        if len(mine) > 1:
            two_listed.append((pl, mine))
        if not mine:
            mine = sorted(pool)
            if len(mine) > 1:
                two_offered.append((pl, mine))
                continue
        if not mine:
            none.append(pl)
            continue
        chosen[pl] = mine[0]
    for p in pre:
        u = chosen.get((p["county"], p["mcdcode"]))
        p["jud"] = f"{STATE}-DC{u}" if u else None
    circuit = {}
    for n, (_sec, names_) in st["circuits"].items():
        for name in names_:
            c = by_county.get(M.county_key(name))
            if c is None or c in circuit:
                raise GeoError(f"    MCL 600 chapter 5: the county {name!r} is not one of the precinct table's 83, or is in two circuits; stopping")
            circuit[c] = f"{STATE}-CC{n}"
    if len(circuit) != 83:
        raise GeoError(f"    MCL 600 chapter 5 places {len(circuit)} of the 83 counties in a judicial circuit; stopping")
    for p in pre:
        p["circuit"] = circuit[p["county"]]

    used = sorted({u for u in chosen.values()}, key=G.natkey)
    control = []                                              # each listed district's counties here against the ballot database's
    for k in sorted(live, key=G.natkey):
        here = sorted({pl[0] for pl, u in chosen.items() if u == k})
        if here != info["courts"].get(f"{STATE}-DC{k}"):
            control.append({"id": f"{STATE}-DC{k}", "counties_here": here, "counties_in_the_ballot_database": info["courts"].get(f"{STATE}-DC{k}")})
    place_word = lambda pl: f"{next(p['census'] for p in pre if (p['county'], p['mcdcode']) == pl)} ({cshort[pl[0]]} County)"   # noqa: E731
    found = {
        "through": st["through"][1], "paths": paths, "units": {k: usable[k] for k in used},
        "drawn": len(used), "on_the_2026_listing": len([k for k in used if k in live]),
        "listed_not_in_the_act": [f"{STATE}-DC{k}" for k in unknown],
        "listed_with_no_precinct": [f"{STATE}-DC{k}" for k in sorted(live - set(used), key=G.natkey)],
        "set_aside_as_overlapping_a_listed_district": sorted(dead, key=G.natkey),
        "in_two_listed_districts_given_to_the_smaller": [{"place": place_word(pl), "districts": [f"{STATE}-DC{k}" for k in ks]} for pl, ks in two_listed],
        "the_act_offers_two_and_neither_is_listed": [{"place": place_word(pl), "districts": [f"{STATE}-DC{k}" for k in ks]} for pl, ks in two_offered],
        "in_no_district_of_the_act": [place_word(pl) for pl in none],
        "names_the_precinct_table_does_not_have": sorted(set(not_found)), "names_two_places_share": sorted(set(vague)),
        "counties_against_the_ballot_database": control,
    }
    return found


def court_name(names, unit, u):
    M_ord = G.ordinal
    n = re.match(r"\d+", u["label"]).group()
    base = f"{M_ord(n)} District Court" if u["label"] == n else f"{u['label']} District Court"
    return names.get(("judicial", f"{STATE}-DC{unit}")) or base + (f", {M_ord(u['div'])} Division" if u["div"] else "")


# ---------------------------------------------------------------- ids against the ballot database

PAGE_RULE = {
    "circuit_court": "elected by the counties of the circuit; the page places the race by its counties, and a precinct's own word (circuit) names the circuit",
    "probate_court": "elected by the county (or the counties of a probate district); the page places the race by its counties",
    "court_of_appeals": "elected by Court of Appeals district; the races carry no jurisdiction id, so every district's race is listed for every reader",
}


def check_ids(info, shape_ids):
    """Every Michigan race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape). A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    T = shape_ids
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, _seat, _cids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = re.sub(r"^0+(?=.)", "", str(district).strip()) if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", d)
        elif kind == "state_house":
            hit = ("house", d)
        elif kind == "district_court":
            hit = ("judicial", jid)
            why = "the Revised Judicature Act's words for this district could not be tied to the precinct table's cities and townships"
        elif kind == "county_commissioner":
            hit = ("com", f"{jid}|{d}")
            why = "the State's layer of commissioner districts (2021) has no district of this number in this county"
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{district}") if district else ("mcd", jid)
            if district:
                why = "the precinct table has no ward of this name in this city (the city's council districts are not the table's wards)"
        elif level == "school":
            hit = ("school", jid)
            why = "the State's layer of school districts has no district of this code"
        elif kind in PAGE_RULE:
            why = PAGE_RULE[kind]
        elif kind == "college_board":
            why = ("no statewide file has trustworthy lines for community college districts (the State's layer of them mixes district lines with whole "
                   "counties drawn for context); the page places the race by its counties")
        else:
            why = "no statewide file has lines for this kind of district (a district library); the page places the race by its counties"
        if hit and hit[1] in T.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()), "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places (from a file John saves)

POLL_WAITING = {
    "why": "Michigan publishes no statewide file of polling places that this site can read by itself: each city and township clerk keeps its "
           "own in the State's voter file, and a statewide list has not been obtained. The Michigan Voter Information Center answers for one "
           "voter or one address at a time and is the authority.",
}
POLL_HOW = ("      polling places: waiting. No state page a script may read carries them (the Michigan Voter Information Center and michigan.gov "
            "refuse scripts, which is never worked around, and the State's GIS Open Data site has precincts and no polling places). There is no "
            "download for John to save either: a statewide list would have to be asked of the Bureau of Elections (a public records request "
            "for the November 3, 2026 polling locations by precinct, as a spreadsheet). If one arrives, save it as it is (.xlsx, .csv or "
            ".txt) into states_cache/mi_local/boe/pollingplaces/ and run this again.")
POLL_COLUMNS = {
    "county": [("county",)],
    "muni": [("jurisdiction",), ("municipality",), ("city", "township"), ("township",)],
    "ward": [("ward",)],
    "precinct": [("precinct", "number"), ("precinct", "num"), ("precinct",), ("pct",)],
    "place": [("polling", "place", "name"), ("polling", "location"), ("poll", "name"), ("location", "name"), ("polling", "place"), ("facility",), ("location",)],
    "address": [("address", "1"), ("street",), ("address",)],
    "city": [("city",)],
    "zip": [("zip",), ("postal",)],
    "lat": [("lat",)],
    "lon": [("lon",), ("lng",)],
}
POLL_NEVER = ("phone", "email", "e mail", "contact", "clerk", "inspector", "owner", "voter")


def _poll_columns(head):
    words = [re.sub(r"[^a-z0-9]+", " ", str(h or "").lower()).split() for h in head]
    taken, found = set(), {}
    for field, alts in POLL_COLUMNS.items():
        for alt in alts:
            hit = [i for i, ws in enumerate(words) if i not in taken and all(any(w.startswith(a) for w in ws) for a in alt)
                   and not any(n in " ".join(ws) for n in POLL_NEVER)]
            if hit:
                found[field] = hit[0]
                taken.add(hit[0])
                break
    return found


def read_polling_file(path, pre, cshort):
    """A statewide polling place list, cut down on the spot to the precinct, the place's name and street address and
    coordinates if the file gives them. Raises GeoError naming the check that failed (headings only, never a line)."""
    from ballot import state_local_mi as M
    base = os.path.basename(path)
    if path.lower().endswith(".xlsx"):
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(c.strip() for c in r)]
    else:
        text = open(path, "rb").read().decode("utf-8-sig", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=max(",;\t|", key=(lines[0] if lines else "").count)))
    if len(rows) < 2:
        raise GeoError(f"    {base}: fewer than two lines; not a polling place list")
    cols = _poll_columns(rows[0])
    if not {"place", "county", "muni", "precinct"} <= set(cols):
        raise GeoError(f"    {base}: the first line does not name a county, a city or township, a precinct and a polling place (its headings: "
                       f"{'; '.join(str(h).strip() for h in rows[0])}); the reader needs to be told the layout")
    index = collections.defaultdict(list)                     # a split precinct's pieces vote at the precinct's place
    for p in pre:
        index[(M.county_key(cshort[p["county"]]), p["kind"], M.bare(p["census"]), p["wardcode"], p["pct"])].append(p["id"])

    def cell(r, field):
        i = cols.get(field)
        return r[i].strip() if i is not None and i < len(r) else ""

    places, order, precinct, unmatched = {}, [], {}, 0
    for r in rows[1:]:
        muni = cell(r, "muni")
        kind = "township" if re.search(r"(?i)\b(township|twp)\b", muni) else "city"
        num = lambda t: re.sub(r"^0+(?=.)", "", re.sub(r"(?i)^\s*(ward|precinct|pct)\.?\s*", "", t).strip())      # noqa: E731
        pids = index.get((M.county_key(cell(r, "county")), kind, M.bare(muni), num(cell(r, "ward")) if cell(r, "ward") not in ("", "0", "00") else "", num(cell(r, "precinct"))))
        place = re.sub(r"\s+", " ", cell(r, "place"))
        if not pids or not place:
            unmatched += 1
            continue
        key = (place.lower(), cell(r, "address").lower(), cell(r, "city").lower(), cell(r, "zip")[:5])
        if key not in places:
            places[key] = {"name": place, "address": re.sub(r"\s+", " ", cell(r, "address")), "city": cell(r, "city"), "zip": cell(r, "zip")[:5],
                           "type": None, "lonlat": None, "precincts": []}
            try:
                lon, lat = float(cell(r, "lon")), float(cell(r, "lat"))
                if -90.5 < lon < -82.3 and 41.6 < lat < 48.4:
                    places[key]["lonlat"] = [round(lon, 5), round(lat, 5)]
            except ValueError:
                pass
            order.append(key)
        for pid in pids:
            if pid not in places[key]["precincts"]:
                places[key]["precincts"].append(pid)
            precinct[pid] = order.index(key)
    ids_all = {p["id"] for p in pre}
    if len(precinct) < 0.9 * len(ids_all):
        raise GeoError(f"    {base}: only {len(precinct):,} of {len(ids_all):,} precincts could be found in it (columns read: {', '.join(sorted(cols))}); "
                       "the reader needs to be told the layout")
    return {"places": [places[k] for k in order], "precinct": dict(sorted(precinct.items())), "no_place": {}, "rows": len(rows) - 1,
            "rows_not_matched": unmatched, "columns_read": sorted(cols), "precincts_without_a_row": sorted(ids_all - set(precinct))}


def polling_places(pre, cshort, put, say, folder=None):
    folder = folder or POLL_DIR
    found = sorted((f for ext in ("*.xlsx", "*.csv", "*.txt", "*.tsv") for f in glob.glob(os.path.join(folder, ext))), key=os.path.getmtime)
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    if not found:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(POLL_HOW)
        return {"file": "polling_places.json", "status": "waiting"}
    path = found[-1]
    try:
        got = read_polling_file(path, pre, cshort)
    except GeoError as e:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(str(e))
        return {"file": "polling_places.json", "status": "unread"}
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Michigan Department of State, Bureau of Elections", "title": "Polling locations by precinct, General Election of November 3, 2026",
                       "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path)},
               places=got["places"], precinct=got["precinct"], no_place=got["no_place"])
    put("polling_places.json", doc)
    with_point = sum(1 for p in got["places"] if p["lonlat"])
    say(f"      polling places ({os.path.basename(path)}): {len(got['places']):,} places for {len(got['precinct']):,} precincts ({with_point:,} with "
        f"coordinates in the file; the rest are listed without a point on the map), {got['rows_not_matched']:,} of {got['rows']:,} rows fit no "
        f"precinct, {len(got['precincts_without_a_row']):,} precincts have no row; columns read: {', '.join(got['columns_read'])}")
    if not POLL_LAYOUT_CHECKED:
        say("      polling places: the reader was written before any such file was seen, so the file is marked 'unchecked' and a page must not "
            "show it yet. Compare a dozen precincts in polling_places.json with the file (and with the Michigan Voter Information Center), then "
            "set POLL_LAYOUT_CHECKED = True in ballot/mi_geo.py and build again.")
    return {"file": "polling_places.json", "status": status, "places": len(got["places"]), "with_coordinates": with_point}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print, polls_dir=None):
    t0 = time.time()
    say("    Michigan ballot map: precinct, district, village and school district lines (the Bureau of Elections and the Michigan Geographic "
        "Framework, on the State's GIS Open Data site), and district courts from the Revised Judicature Act")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    jobs = [("precincts", PCT_SERVICE, PCT_FIELDS, "boe_voting_precincts_2026_geometry_4326.json.gz", 250, "OBJECTID"),
            ("house", HOUSE_SERVICE, LEG_FIELDS, "mgf_remedial_house_2024_geometry_4326.json.gz", 10, "OBJECTID"),
            ("senate", SENATE_SERVICE, LEG_FIELDS, "mgf_remedial_senate_2024_geometry_4326.json.gz", 5, "OBJECTID"),
            ("congress", CD_SERVICE, CD_FIELDS, "mgf_congress_2021_geometry_4326.json.gz", 2, "OBJECTID"),
            ("commissioner", COM_SERVICE, COM_FIELDS, "mgf_commissioner_2021_geometry_4326.json.gz", 50, "OBJECTID_1"),
            ("school", SCHOOL_SERVICE, SCHOOL_FIELDS, "mgf_school_districts_geometry_4326.json.gz", 40, "OBJECTID"),
            ("village", VILLAGE_SERVICE, VILLAGE_FIELDS, "mgf_villages_geometry_4326.json.gz", 60, "OBJECTID")]
    docs, paths = {}, {}
    for name, svc, fields, fname, page, oid in jobs:
        paths[name] = path(fname)
        docs[name] = W.fetch_full(svc, fields, paths[name], page, oid, refresh, say)
    edited = {name: W.layer_edited(svc, path(f"mi_geo_about_{name}.json"), refresh) for name, svc, *_ in jobs}
    net.patient_lookups()
    cousub_path, place_path = path("census_st26_mi_cousub2020.txt"), path("census_st26_mi_place2020.txt")
    net.download(COUSUB_URL, cousub_path, 3650, say=lambda *_a: None)
    net.download(PLACE_URL, place_path, 3650, say=lambda *_a: None)
    cousub_name, place_name = read_names(cousub_path, place_path)

    # ---- the precinct table
    pre, polys = read_precincts(docs["precincts"], cousub_name)
    whole_precincts = len(pre)

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone, and district courts are placed by the act alone")
    cshort = {}
    for p in pre:
        cshort[p["county"]] = cshort.get(p["county"]) or ""
    # county names: the ballot database's, else the Census list's (the cousub list names each row's county)
    for line in open(cousub_path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
        f = line.split("|")
        if len(f) >= 4 and f[1] == FIPS and FIPS + f[2] in cshort:
            cshort[FIPS + f[2]] = re.sub(r" County$", "", f[3].strip())
    if not all(cshort.values()):
        raise GeoError("    a county of the precinct table is not in the Census Bureau's list; stopping")
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in cshort.items()}
    mname, mkind = {}, {}
    for p in pre:
        mname[p["mcd"]] = names.get(("mcd", p["mcd"])) or p["census"]
        mkind[p["mcd"]] = p["kind"]

    # ---- district courts and circuits, from the act
    courts = court_districts(pre, cshort, info, refresh, say)
    say(f"      district courts (MCL 600.8101 to 600.8163, through Public Act {courts['through']}): {courts['drawn']} districts and election divisions "
        f"put together from precincts, {courts['on_the_2026_listing']} of them with a seat on the 2026 listing; "
        f"{sum(1 for p in pre if not p['jud'])} precincts are given none"
        + "".join(f"; {what}: {len(courts[key])}" for key, what in (
            ("listed_not_in_the_act", "listed districts the act's reader does not have"), ("listed_with_no_precinct", "listed districts no precinct is given to"),
            ("in_two_listed_districts_given_to_the_smaller", "places in two listed districts (given to the smaller)"),
            ("the_act_offers_two_and_neither_is_listed", "places the act offers two districts for (given none)"),
            ("in_no_district_of_the_act", "places in no district of the act"), ("names_the_precinct_table_does_not_have", "names the precinct table does not have"),
            ("names_two_places_share", "names two places share"), ("counties_against_the_ballot_database", "districts whose counties differ from the ballot database's")) if courts[key]))

    # ---- wards, in the ballot database's own words
    label, joined, ward_unmatched = G.ward_words(pre, info["council"])
    for p in pre:
        p["ward_id"] = f"{p['mcd']}|{label[(p['mcd'], p['wardcode'])]}" if p["wardcode"] else None
        p["wards"] = ([p["ward_id"]] + sorted(f"{m}|{s}" for (m, s), codes in joined.items() if m == p["mcd"] and p["wardcode"] in codes)) if p["wardcode"] else []

    # ---- the districts that have lines of their own
    hrows = numbered(docs["house"], "Name", 110, "State House districts")
    srows = numbered(docs["senate"], "Name", 38, "State Senate districts")
    crows = numbered(docs["congress"], "NAME", 13, "congressional districts")
    num = lambda f: (lambda a: str(int(a[f])))      # noqa: E731
    hkeys, hpolys, harcs, hsides, _hr, hodd = I.fabric(hrows, num("Name"))
    skeys, spolys, sarcs, ssides, _sr, sodd = I.fabric(srows, num("Name"))
    ckeys, cpolys, carcs, csides, _cr, codd = I.fabric(crows, num("NAME"))
    for a, _r in docs["commissioner"]["rows"]:
        m = re.fullmatch(r"District (\d+)", G.blank(a["DistrictName"]))
        if not (re.fullmatch(r"\d{3}", G.blank(a["CountyFIPS"])) and m and G.blank(a["DistrictCode"]).endswith(f"{int(m.group(1)):02d}")):
            raise GeoError(f"    commissioner districts: the row {a.get('DistrictCode')!r} does not fit the layout this builder was checked against; stopping")
    comkey = lambda a: f"{FIPS}{a['CountyFIPS']}|{int(a['DistrictName'].split()[1])}"      # noqa: E731
    comkeys, compolys, comarcs, comsides, _comr, comodd = I.fabric(N.merge_rows(docs["commissioner"]["rows"], comkey), comkey)
    if {k.split("|")[0] for k in comkeys} != set(cshort):
        raise GeoError("    commissioner districts: the layer does not cover the 83 counties; stopping")
    for a, _r in docs["school"]["rows"]:
        if not re.fullmatch(r"\d{5}", G.blank(a["DCode"])) or not G.blank(a["Name"]):
            raise GeoError(f"    school districts: the row coded {a.get('DCode')!r} does not fit the layout this builder was checked against; stopping")
    schkey = lambda a: f"{STATE}-S-{a['DCode']}"      # noqa: E731
    schrows = N.merge_rows(docs["school"]["rows"], schkey)
    schkeys, _schpolys, scharcs, schsides, schrings, schodd = I.fabric(schrows, schkey)
    schfine, _ = G.simplify_arcs(scharcs, schrings, G.TOL_SCHOOL)
    sname = {schkey(a): names.get(("school", schkey(a))) or G.blank(a["Name"]) for a, _r in schrows}
    for a, _r in docs["village"]["rows"]:
        if not re.fullmatch(r"\d{5}", G.blank(a["FIPSCode"])) or f"{STATE}-M-{a['FIPSCode']}" in mname:
            raise GeoError(f"    villages: the row coded {a.get('FIPSCode')!r} is not a five-digit code, or is the code of a city or township too; stopping")
    vkey = lambda a: f"{STATE}-M-{a['FIPSCode']}"      # noqa: E731
    vrows = N.merge_rows(docs["village"]["rows"], vkey)
    vkeys, vpolys, varcs, vsides, _vr, vodd = I.fabric(vrows, vkey)
    for a, _r in vrows:
        mname[vkey(a)] = names.get(("mcd", vkey(a))) or place_name.get(a["FIPSCode"]) or f"{G.blank(a['Name'])} village"
        mkind[vkey(a)] = "village"
    say(f"      110 House districts ({len(harcs):,} lines), 38 Senate ({len(sarcs):,}), 13 congressional ({len(carcs):,}), {len(comkeys)} county commissioner "
        f"districts ({len(comarcs):,}), {len(schkeys)} school districts ({len(scharcs):,}), {len(vkeys)} villages"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("House", hodd), ("Senate", sodd), ("Congress", codd), ("commissioner", comodd), ("school", schodd), ("villages", vodd)) if o))

    # ---- which districts each whole precinct reaches (the one holding most of it; a second one with 3 percent or more, thick enough)
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, KNIT_M, FACE_MIN_W, FACE_MIN_M2, 2]).encode()).hexdigest()   # noqa: E731
    pp = paths["precincts"]
    raw_rings = I.rings_xy(polys)
    o_house = overlay_cached("house", raw_rings, I.rings_xy(hpolys), stamp(pp, paths["house"]), refresh, say)
    o_senate = overlay_cached("senate", raw_rings, I.rings_xy(spolys), stamp(pp, paths["senate"]), refresh, say)
    o_cd = overlay_cached("congressional", raw_rings, I.rings_xy(cpolys), stamp(pp, paths["congress"]), refresh, say)
    o_com = overlay_cached("commissioner", raw_rings, I.rings_xy(compolys), stamp(pp, paths["commissioner"]), refresh, say)
    none_of = collections.Counter()
    for n, p in enumerate(pre):
        p["house"] = S.most(p, o_house[n], hkeys, "house")
        p["senate"] = S.most(p, o_senate[n], skeys, "senate")
        p["cd"] = S.most(p, o_cd[n], ckeys, "cd")
        p["com"] = S.most(p, [g for g in o_com[n] if comkeys[g[0]].split("|")[0] == p["county"]], comkeys, "com")
        for k in CUT_KINDS:
            none_of[k] += p[k] is None
    if any(none_of.values()):
        raise GeoError(f"    precincts that touch no district: {dict(none_of)}; stopping")
    splits = {k: sum(1 for p in pre if k in (p.get("split") or {})) for k in CUT_KINDS}
    say(f"      districts by precinct: a district line runs through {sum(1 for p in pre if p.get('split')):,} of the {len(pre):,} precincts "
        f"({splits['house']} House, {splits['senate']} Senate, {splits['cd']} congressional, {splits['com']} county commissioner)")

    # ---- one line between two neighbours, kept once: the precincts' drawings made one, split precincts cut, and the new corners
    #      (where a district line crosses a precinct's edge) given to the neighbour across that edge too
    lines = {"house": (hkeys, hpolys), "senate": (skeys, spolys), "cd": (ckeys, cpolys), "com": (comkeys, compolys)}
    moved, added = N.knit(polys, eps_m=KNIT_M)
    pre, polys, left_whole = cut_precincts(pre, polys, lines, say)
    moved2 = added2 = 0
    slivers, gave = W.settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {whole_precincts:,} precincts in {len(pre):,} shapes, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); {moved + moved2:,} corners within "
        f"{KNIT_M:g} m of a neighbour's made one corner and {added + added2:,} added to a neighbour's straight run; {lone:,} lines have a precinct on "
        "one side only (shore, mostly)"
        + (f"; {slivers} rings under {W.SLIVER_M2:.0f} square metres left out" if slivers else "")
        + (f"; {sum(n for _w, n in gave)} points given up by {len(gave)} shapes that ran along a neighbour's line the same way" if gave else "")
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- school districts and villages over the shapes
    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    cut_stamp = hashlib.sha256(json.dumps([p["id"] for p in pre] + [sum(len(r) for r in rings) for rings in pre_rings]).encode()).hexdigest()      # the shapes as cut
    o_sch = overlay_cached("school", pre_rings, [[G.ring_xy(refs, schfine) for refs in rings] for rings in schrings], stamp(pp, paths["school"]) + cut_stamp, refresh, say)
    o_vil = overlay_cached("village", pre_rings, I.rings_xy(vpolys), stamp(pp, paths["village"]) + cut_stamp, refresh, say)
    for n, p in enumerate(pre):
        vs = sorted(((vkeys[d], s) for d, s, thick in o_vil[n] if thick), key=lambda x: (-x[1], x[0]))
        p["mcd_all"] = [p["mcd"]] + [k for k, _s in vs]
        p["mcd_pct"] = [100.0] + [round(100 * s, 1) for _k, s in vs]
    say(f"      {sum(1 for p in pre if len(p['mcd_all']) > 1):,} shapes reach into a village")
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

    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "ward": [p["ward_id"] for p in pre], "com": [p["com"] for p in pre],
            "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": [p["cd"] for p in pre], "judicial": [p["jud"] for p in pre]}
    mask = []
    for r, l in sides:
        m = 0
        for bit, kind in enumerate(ARC_KINDS):
            v = vals[kind]
            if (v[r] if r >= 0 else None) != (v[l] if l >= 0 else None) or (kind == "county" and (r < 0 or l < 0)):
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

    def layer(kind, geoms, qlines, tol, props, source, zoom=None, keep_order=False):
        gl = []
        for v, polys_ in (geoms if keep_order else sorted(geoms, key=lambda x: G.natkey(x[0]))):
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

    def own(v_sets, tol):
        g, q, _l, _r = G.build_layer(arcs, sides, v_sets, tol)
        return [x for x in g if x[0] is not None], q

    def other(arcs_, sides_, keys, tol):
        g, q, _l, _r = G.build_layer(arcs_, sides_, [keys], tol)
        return g, q

    PCT, HSE, SEN, CDS, COM, SCH, VIL, LAW, CEN = (
        "mi-boe-voting-precincts-2026", "mi-remedial-house-2024", "mi-remedial-senate-2024", "mi-congressional-2021", "mi-commissioner-districts-2021",
        "mi-mgf-school-districts", "mi-mgf-villages", "mi-mcl-600-chapters-5-81", "mi-census-2020-names")
    units = courts["units"]
    jud_counties = collections.defaultdict(set)
    for p in pre:
        if p["jud"]:
            jud_counties[p["jud"]].add(cname[p["county"]])
    jname = {f"{STATE}-DC{k}": court_name(names, k, u) for k, u in units.items()}
    listed_courts = set(info["courts"])

    def jud_props(v):
        u = units[v[len(STATE) + 3:]]
        return {"id": v, "name": jname[v], "j": v, "d": v[len(STATE) + 3:], "counties": sorted(jud_counties[v]), "law": f"MCL {u['sec']}",
                "consists_of": u["words"], "on_the_2026_listing": v in listed_courts}

    def ward_props(v):
        m, d = v.split("|", 1)
        pr = {"id": v, "name": f"{mname[m]}, {d}", "j": m, "d": d}
        if (m, d) in joined:
            pr["of"] = [f"{m}|{label[(m, c)]}" for c in joined[(m, d)]]
        return pr

    joined_vals = [[f"{m}|{s}" if p["mcd"] == m and p["wardcode"] in codes else None for p in pre] for (m, s), codes in sorted(joined.items())]
    layer("state", *own([[STATE] * len(pre)], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, PCT)
    layer("county", *own([vals["county"]], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, PCT)
    layer("cd", *other(carcs, csides, ckeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, CDS)
    layer("senate", *other(sarcs, ssides, skeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, SEN)
    layer("house", *other(harcs, hsides, hkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v}, HSE)
    layer("judicial", *own([vals["judicial"]], G.TOL_LOCAL), G.TOL_LOCAL, jud_props, PCT + "; which cities and townships, from " + LAW)
    vg, vq = other(varcs, vsides, vkeys, TOL_MCD)
    mg, mq = own([vals["mcd"]], TOL_MCD)
    shift = len(vq)
    mcd_geoms = (sorted(vg, key=lambda x: G.natkey(x[0]))
                 + sorted(((v, [[[r + shift if r >= 0 else ~(~r + shift) for r in ring] for ring in poly] for poly in polys_]) for v, polys_ in mg), key=lambda x: G.natkey(x[0])))
    layer("mcd", mcd_geoms, vq + mq, TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]},
          f"{VIL} (villages, first in the file) and {PCT} (cities and townships)", zoom=MCD_ZOOM, keep_order=True)
    layer("ward", *own([vals["ward"]] + joined_vals, G.TOL_LOCAL), G.TOL_LOCAL, ward_props, PCT)
    layer("com", *other(comarcs, comsides, comkeys, G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Commissioner District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, COM)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None}      # noqa: E731
    layer("school", *other(scharcs, schsides, schkeys, G.TOL_LOCAL), G.TOL_LOCAL, sprops, SCH)
    dgeoms, dq = other(scharcs, schsides, schkeys, G.TOL_SCHOOL)
    school_bytes = 0
    for v, polys_ in dgeoms:
        pr = sprops(v)
        pr.pop("id")
        doc, _d, _p = G.topo_doc({"school": [{"id": v, "properties": pr, "polys": polys_, "label": True}]}, dq)
        doc["kind"], doc["tolerance_m"] = "school", G.TOL_SCHOOL
        school_bytes += put(f"school/{v}.json", doc)

    # county files
    cirname = {p["circuit"]: names.get(("judicial", p["circuit"])) or f"{G.ordinal(p['circuit'][len(STATE) + 3:])} Circuit Court" for p in pre}
    by_county = collections.defaultdict(list)
    for i, p in enumerate(pre):
        by_county[p["county"]].append(i)
    counties, boxes, dropped_rings = [], {}, 0
    for county, idxs in sorted(by_county.items()):
        local = {i: n for n, i in enumerate(idxs)}
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "judicial": {}, "circuit": {}, "school": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "mcd": p["mcd"], "com": p["com"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "circuit": p["circuit"], "school": p["school"]}
            if p["parts"] > 1:
                pr["parts"] = p["parts"]
            used_names["circuit"][p["circuit"]] = cirname[p["circuit"]]
            used_names["com"][p["com"]] = f"Commissioner District {p['com'].split('|')[1]}"
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["jud"]:
                pr["judicial"] = p["jud"]
                used_names["judicial"][p["jud"]] = jname[p["jud"]]
            if p["wards"]:
                pr["ward"] = p["wards"]
                for w in p["wards"]:
                    used_names["ward"][w] = w.split("|", 1)[1]
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
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(pre, cshort, put, say, polls_dir)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids)
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    check["split_precincts_left_whole"] = [{"id": i, "kinds": kinds, "why": why} for i, kinds, why in left_whole]
    check["district_courts"] = {k: v for k, v in courts.items() if k not in ("units", "paths", "through")}
    check["council_districts_with_no_ward_to_draw"] = [{"place": mname.get(m, m), "district": s} for m, s in sorted(ward_unmatched) if f"{m}|{s}" not in shape_ids["ward"]]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    mgf = "State of Michigan, Department of Technology, Management and Budget, Center for Shared Solutions (the Michigan Geographic Framework)"

    def src(sid, agency, title, about, item, service, name, rows):
        return dict({"id": sid, "agency": agency, "title": title, "about": about, "url": item, "service": service, "fetched": docs[name].get("fetched"),
                     "sha256": G.sha_file(paths[name]), "rows": rows}, **edited[name])

    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            src(PCT, "Michigan Department of State, Bureau of Elections; published on the State of Michigan's GIS Open Data site", "2026 Voting Precincts",
                "Precinct lines for 2026, each with the Bureau's precinct id, its county, its city or township, its ward and its name.",
                PCT_ITEM, PCT_SERVICE, "precincts", len(pre)),
            src(HSE, mgf, "Remedial State House Districts 2021 - Approved in 2024", "The 110 House districts as the court approved them in 2024 (first used in 2024).",
                HOUSE_ITEM, HOUSE_SERVICE, "house", 110),
            src(SEN, mgf, "Remedial State Senate Districts 2021 - Approved in 2024", "The 38 Senate districts as the court approved them in 2024 (first used in 2026).",
                SENATE_ITEM, SENATE_SERVICE, "senate", 38),
            src(CDS, mgf, "Michigan U.S. Congressional Districts 2021", "The 13 congressional districts of the 2021 plan.", CD_ITEM, CD_SERVICE, "congress", 13),
            src(COM, mgf, "2021 County Commissioner Districts v25", "The commissioner districts each county's apportionment commission drew in 2021.",
                COM_ITEM, COM_SERVICE, "commissioner", len(comkeys)),
            src(SCH, mgf, "School District", "School district lines, each with the district's five-digit code.", SCHOOL_ITEM, SCHOOL_SERVICE, "school", len(schkeys)),
            src(VIL, mgf, "Village", "Village limits.", VILLAGE_ITEM, VILLAGE_SERVICE, "village", len(vkeys)),
            {"id": LAW, "agency": "Michigan Legislature, Legislative Service Bureau",
             "title": "Revised Judicature Act of 1961, chapters 5 and 81 (MCL 600.501 to 600.550a and 600.8101 to 600.8163)",
             "about": f"Which counties each judicial circuit consists of, and which counties, cities and townships each district court district and election division; complete through Public Act {courts['through']}.",
             "url": MCL_PDF.format("81"), "also": MCL_PDF.format("5"), "fetched": mtime(courts["paths"][1]),
             "sha256": G.sha_file(courts["paths"][1]), "sha256_chapter_5": G.sha_file(courts["paths"][0]), "rows": courts["drawn"]},
            {"id": CEN, "agency": "U.S. Census Bureau", "title": "2020 code lists for Michigan: county subdivisions and places (st26_mi_cousub2020.txt, st26_mi_place2020.txt)",
             "about": "The names of cities, villages and townships.", "url": COUSUB_URL, "also": PLACE_URL, "fetched": mtime(cousub_path),
             "sha256": G.sha_file(cousub_path), "sha256_places": G.sha_file(place_path), "rows": len(cousub_name) + len(place_name)}],
        "notes": {
            "lines": f"Every precinct line is the Bureau of Elections', generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 degree (about a "
                     f"metre); where two neighbours' drawings of one line lay within {KNIT_M:g} metre of each other they were made one line. The state, "
                     "counties, cities and townships, wards and district courts are put together from whole precincts. A point within a few metres of "
                     "a line can fall on either side of it. The precincts stop at the Great Lakes and the rivers between them.",
            "districts": "Which House, Senate, congressional and county commissioner district a precinct lies in is worked out here by laying the State's "
                         "district lines over the precinct (analysis, not an official list). Where such a line runs through a precinct (a second "
                         f"district holds {SPLIT_SHARE:.0%} of it or more, in a part at least {G.SCHOOL_THICK:.0f} metres thick) the precinct is cut along "
                         "the line and each piece is a shape of its own (id <precinct>.<n>, the Bureau's id under 'precinct'), so a point is given "
                         "the districts of its own piece. A precinct that could not be cut carries 'split' and is listed under check. Near any "
                         "district line the Michigan Voter Information Center decides.",
            "places": "A precinct belongs to one city or township (the precinct table says which). A village lies inside a township, and a voter in "
                      "a village is a voter of the township too; a precinct that reaches into a village lists it (mcd_all), and the mcd layer answers "
                      "for a point, villages first: a point inside a village's limits is given the village, and it is in the township around it too.",
            "judicial": "A district court district, or the election division of one, is a group of counties, cities and townships set out in the Revised "
                        "Judicature Act (MCL 600.8101 to 600.8163). Where the act keeps two versions of a district side by side, the one with a seat on the "
                        "Bureau of Elections' 2026 candidate listing is taken as in force; where neither is listed the precinct is given no district. "
                        "Circuit judges are elected by the counties of the circuit (the precinct's circuit), probate judges by the county.",
            "commissioners": "County commissioner districts are the 2021 apportionment as the State compiled it; a county that has redrawn its districts since is not known here.",
            "school": "School district lines are the Michigan Geographic Framework's. Which districts a precinct lies in is analysis, not an official "
                      f"list: a district counts when its part of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each "
                      "district's share of the precinct's area (land and water, not voters).",
            "authority": "For which precinct an address votes in, and where, the Michigan Voter Information Center (the Department of State) and the city or township clerk are the authority.",
            "precinct_ids": "A precinct's id is the Bureau of Elections' own: WP, the county's three-digit code, the city's or township's five-digit Census code, "
                            "and the two-digit ward and three-digit precinct numbers. A piece of a split precinct adds a full stop and its number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct, id = the Bureau's precinct id. arcMask[i] has bit k set "
                            "when line i is an outline of arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line "
                            "i (-1: a precinct in another county's file, -2: no precinct: the state's edge, a Great Lake, or a gap between two "
                            "drawings); names gives the names of the places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step "
                     "degrees from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened "
                     "by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name (City of Holland, Ward 4, Precinct 7)", "county": "county id", "mcd": "city or township",
                                    "mcd_all": "list, when the precinct reaches into a village: its city or township, then the villages, largest share first",
                                    "mcd_pct": "list, with mcd_all: the share of the precinct's area in each, in percent (a village lies inside the township)",
                                    "ward": "list: the council districts the precinct lies in (absent where the city has no wards)",
                                    "com": "county commissioner district holding most of the precinct",
                                    "house": "state House district holding most of the precinct", "senate": "state Senate district holding most of the precinct",
                                    "cd": "congressional district holding most of the precinct",
                                    "judicial": "district court (the district, or its election division, that elects the precinct's district judges; absent where the act offers two and neither is listed)",
                                    "circuit": "judicial circuit (its circuit judges are elected by the counties of the circuit)",
                                    "precinct": "the Bureau of Elections' precinct id (the shape's own id, but for a piece of a split precinct)",
                                    "parts": "only on a piece of a split precinct: how many pieces the precinct was cut into along district lines",
                                    "split": "only where a district line runs through the precinct and it could not be cut: for house, senate, cd or com, each district's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is split: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "MI (j is 26)", "county": "the county's five-digit code (26163)",
                    "mcd": "MI-M- and the Census code: a city's or township's county subdivision code (MI-M-22000), a village's place code; properties.t says city, township or village",
                    "ward": "<city>|<ward as the council race words it> (MI-M-34000|Ward 1)", "com": "<county>|<commissioner district> (26163|5)",
                    "house": "the district (77)", "senate": "the district (21)", "cd": "the district (7); properties.race is the race for Congress",
                    "judicial": "MI-DC and the district court district, with its election division where judges are elected by division (MI-DC36, MI-DC52-1)",
                    "school": "MI-S- and the district's five-digit code (MI-S-33020)",
                    "circuit (a precinct's word, no layer)": "MI-CC and the circuit's number (MI-CC30)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "polling_places": polls,
        "counts": {"precincts": len(pre), "precincts_of_the_bureau": whole_precincts, "counties": len(counties),
                   "split_precincts_cut": len({p["precinct"] for p in pre if p["parts"] > 1}), "pieces_of_split_precincts": sum(1 for p in pre if p["parts"] > 1),
                   "split_precincts_left_whole": len(left_whole), "split_between_school_districts": split,
                   "rings_too_small_for_the_grid": dropped_rings, "with_a_house_line_through": splits["house"],
                   "with_a_senate_line_through": splits["senate"], "with_a_congressional_line_through": splits["cd"],
                   "with_a_commissioner_line_through": splits["com"], "reaching_into_a_village": sum(1 for p in pre if len(p["mcd_all"]) > 1),
                   "with_no_district_court": sum(1 for p in pre if not p["jud"]), "lines_with_a_precinct_on_one_side": lone,
                   "corners_made_one": moved + moved2, "corners_added_to_a_straight_run": added + added2, "sliver_rings_left_out": slivers,
                   "points_given_up_where_two_precincts_overlapped": dict(gave)},
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Michigan races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check.get("no_shape") else ""))
    say(f"    Michigan ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the precinct there must say, the shape the mcd layer must give the point, and a
    # word its school district's name must carry. County, city or township, village, congressional and 2026 legislative
    # districts and school district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02),
    # an answer that owes nothing to the files tested here. The district court is read from the Revised Judicature Act
    # by hand (MCL 600.8121a: the city of Detroit is the 36th district; and so on), the circuit likewise (chapter 5).
    ("the State Capitol, Lansing", -84.5555, 42.7336,
     {"county": "26065", "mcd": "MI-M-46000", "cd": "7", "senate": "21", "house": "77", "judicial": "MI-DC54A", "circuit": "MI-CC30"}, "MI-M-46000", "Lansing"),
    ("the Coleman A. Young Municipal Center, Detroit", -83.0437, 42.3293,
     {"county": "26163", "mcd": "MI-M-22000", "cd": "13", "senate": "1", "house": "9", "judicial": "MI-DC36", "circuit": "MI-CC3"}, "MI-M-22000", "Detroit"),
    ("Grand Rapids City Hall", -85.6706, 42.9690,
     {"county": "26081", "mcd": "MI-M-34000", "cd": "3", "senate": "30", "house": "84", "judicial": "MI-DC61", "circuit": "MI-CC17"}, "MI-M-34000", "Grand Rapids"),
    ("downtown Marquette", -87.3954, 46.5436,
     {"county": "26103", "mcd": "MI-M-51900", "cd": "1", "senate": "38", "house": "109", "judicial": "MI-DC96", "circuit": "MI-CC25"}, "MI-M-51900", "Marquette"),
    ("downtown Ann Arbor", -83.7480, 42.2808,
     {"county": "26161", "mcd": "MI-M-03000", "cd": "6", "senate": "15", "house": "23", "judicial": "MI-DC15", "circuit": "MI-CC22"}, "MI-M-03000", "Ann Arbor"),
    ("downtown Lake Orion, a village inside Orion Township", -83.2397, 42.7845,
     {"county": "26125", "mcd": "MI-M-61100", "cd": "9", "senate": "23", "house": "54", "judicial": "MI-DC52-3", "circuit": "MI-CC6"}, "MI-M-44940", "Lake Orion"),
    ("downtown Flint", -83.6875, 43.0125,
     {"county": "26049", "mcd": "MI-M-29000", "cd": "8", "senate": "27", "house": "70", "judicial": "MI-DC67-5", "circuit": "MI-CC7"}, "MI-M-29000", "Flint"),
    ("Novi, Twelve Mile and Novi Road", -83.4755, 42.4950,
     {"county": "26125", "mcd": "MI-M-59440", "cd": "6", "senate": "13", "house": "21", "judicial": "MI-DC52-1", "circuit": "MI-CC6"}, "MI-M-59440", "Novi"),
    ("a field in Bridgehampton Township, Sanilac County", -82.75, 43.50,
     {"county": "26151", "mcd": "MI-M-10420", "cd": "9", "senate": "25", "house": "98", "judicial": "MI-DC73A", "circuit": "MI-CC24"}, "MI-M-10420", "Deckerville"),
    ("downtown Traverse City", -85.6206, 44.7631,
     {"county": "26055", "mcd": "MI-M-80340", "cd": "1", "senate": "37", "house": "103", "judicial": "MI-DC86", "circuit": "MI-CC13"}, "MI-M-80340", "Traverse City"),
    ("Eastpointe", -82.9555, 42.4684,
     {"county": "26099", "mcd": "MI-M-24290", "cd": "10", "senate": "11", "house": "12", "judicial": "MI-DC38", "circuit": "MI-CC16"}, "MI-M-24290", ""),
    ("East Lansing, the university", -84.4822, 42.7251,
     {"county": "26065", "mcd": "MI-M-24120", "cd": "7", "senate": "28", "house": "73", "judicial": "MI-DC54B", "circuit": "MI-CC30"}, "MI-M-24120", "East Lansing"),
    ("Sault Ste. Marie", -84.3476, 46.4953,
     {"county": "26033", "mcd": "MI-M-71740", "cd": "1", "senate": "37", "house": "107", "judicial": "MI-DC91", "circuit": "MI-CC50"}, "MI-M-71740", "Sault"),
    ("Battle Creek", -85.1797, 42.3212,
     {"county": "26025", "mcd": "MI-M-05920", "cd": "4", "senate": "18", "house": "44", "judicial": "MI-DC10", "circuit": "MI-CC37"}, "MI-M-05920", "Battle Creek"),
]
LINE_POINT = ("the Ingham-Eaton county line west of Lansing", -84.60, 42.60, ("26065", "26045"))
LAYER_SLACK = 0.005               # some layers come from other files than the precincts: this share of points may disagree


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

    # 1. the files are all there and say what the index says; lines know their two sides and are marked as outlines
    #    of exactly the kinds of district that differ across them
    total = bad_side = bad_mask = lines_seen = edge_lines = 0
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        geoms = doc["objects"]["precincts"]["geometries"]
        total += len(geoms)
        ok = (len(geoms) == c["precincts"] == len(index["boxes"][c["id"]]) // 4 and len(doc["arcMask"]) == len(doc["arcs"])
              and len(doc["arcSides"]) == 2 * len(doc["arcs"]) and all(g["type"] in ("Polygon", "MultiPolygon") for g in geoms))
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
            edge_lines += min(r, l) == -2
            for bit, kind in enumerate(doc["arcKinds"]):
                if r >= 0 and l >= 0:
                    want = own(geoms[r], kind) != own(geoms[l], kind)
                elif kind == "county":
                    want = True
                elif min(r, l) == -2:
                    want = own(geoms[max(r, l)], kind) is not None
                else:
                    continue                               # the neighbour is in another county's file
                bad_mask += bool(masks[a] & (1 << bit)) != want
    check(total == index["counts"]["precincts"], "the county files do not hold as many precincts as the index says")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"(county lines counted in both counties; {edge_lines:,} with a precinct on one side only), sides and outline marks all in order")

    # 2. every precinct is found again from a point inside it; that point's school district is one the precinct names;
    #    and the layers agree with the precinct, away from their lines
    wrong, tested, agree, skipped = 0, 0, 0, 0
    disagree, asked, school = collections.defaultdict(list), collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com"}
    from_precincts = {l["kind"] for l in index["layers"] if l.get("lines_from", "").startswith("mi-boe-voting-precincts-2026")}
    split_ids = {s["id"] for s in index["check"].get("split_precincts", [])}
    village_ok = village_asked = 0
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
            sid = G.school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in g["properties"]["school"] else
                   "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if g["properties"].get("school_out") else "in none"] += 1
            if i % 4 == 0 or g["properties"].get("parts"):
                for prop, kind in layer_for.items():
                    if g["properties"].get(prop) is None or (g["id"] in split_ids and prop in g["properties"].get("split", {})):
                        continue
                    shape, edge = G.shape_at(files, kind, lon, lat)
                    tol = next(l["tolerance_m"] for l in index["layers"] if l["kind"] == kind)
                    if shape is None or edge <= tol + 10:
                        skipped += 1
                        continue
                    asked[kind] += 1
                    if shape["id"] == g["properties"][prop]:
                        agree += 1
                    else:
                        disagree[kind].append((g["id"], shape["id"], g["properties"][prop]))
                shape, edge = G.shape_at(files, "mcd", lon, lat)      # the place at the point: the precinct's own, or a village it lists
                if shape is not None and edge > 15:
                    village_asked += 1
                    village_ok += shape["id"] in (g["properties"].get("mcd_all") or [g["properties"]["mcd"]])
    check(wrong <= 3, f"{wrong} of {tested} precincts are not found again from a point inside them")
    for kind, bad in disagree.items():
        limit = 0 if kind in from_precincts else max(2, int(LAYER_SLACK * asked[kind]))
        check(len(bad) <= limit, f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(village_asked - village_ok <= max(2, int(LAYER_SLACK * village_asked)),
          f"layer mcd: at {village_asked - village_ok} of {village_asked} points the place is neither the precinct's own nor a village it lists")
    check(school["in none"] <= 0.002 * tested, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + f"); the city, township or village at "
        f"{village_ok:,} of {village_asked:,} points is one the precinct names; school district at each precinct's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    for name, lon, lat, want, place, school_word in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check(shape is not None and shape["id"] == place and place in (pr.get("mcd_all") or [pr["mcd"]]),
                    f"{name}: the mcd layer gives {shape and shape['id']}, which should be {place}, one of {pr.get('mcd_all') or [pr['mcd']]}")
        sid = G.school_at(files, found["geometry"], lon, lat)
        fdoc, _l = files.topo(rel[found["county"]])
        sn = fdoc["names"]["school"].get(sid, "") if sid else ""
        ok &= check(sid is not None and sid in pr["school"] and school_word in sn, f"{name}: the school district at the point is {sid} ({sn}), which should name {school_word!r}")
        for prop, kind in layer_for.items():
            if prop in pr.get("split", {}):
                continue
            shape, _edge = G.shape_at(files, kind, lon, lat)
            ok &= check(shape is not None and shape["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape and shape['id']}, the precinct says {pr.get(prop)}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {fdoc['names']['mcd'].get(place, place)}, "
            f"{fdoc['name']}, commissioner district {pr['com'].split('|')[1]}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, "
            f"{fdoc['names']['judicial'].get(pr.get('judicial'), 'no district court')}, {sn}" + (f", {pr['ward'][0].split('|')[1]}" if pr.get("ward") else "")
            + f"; {found['edge']:.0f} m from the precinct's line")

    # 4. a point on a county line: the exact spot on the line nearest to a chosen point
    name, lon, lat, pair = LINE_POINT
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
               f"a point exactly on the {pair[0]}/{pair[1]} line lands in {f2 and f2['county']} with {sorted(sides_)} at hand, {f2 and round(f2['edge'], 2)} m from the line")
    if f2:
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: the spot exactly on the line ({on[0]:.5f}, {on[1]:.5f}) is given to "
            f"{f2['geometry']['properties']['name']} (county {f2['county']}) with {', '.join(sorted(h['geometry']['properties']['name'] for h in n2))} across it")

    # 5. polling places say what they are
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        ids = {g["id"] for c in index["counties"] for g in files.topo(c["file"])[0]["objects"]["precincts"]["geometries"]}
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values()),
              "polling_places.json names a precinct or a place that is not there")
    say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Michigan's ballot map -> ballot_geo/mi/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/mi)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--polls", default=None, help="folder to look for a saved polling place list in (default: states_cache/mi_local/boe/pollingplaces)")
    ap.add_argument("--refresh", action="store_true", help="ask the map services and the statute again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh, polls_dir=a.polls)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
