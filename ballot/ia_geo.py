"""
ballot/ia_geo.py - the geography behind Iowa's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py for the
few things Wisconsin added, and changes nothing in either), so the same page and the same reader
(ballot/mn_geo_reader.js) read all three.

    python ballot/ia_geo.py                 builds ballot_geo/ia/ and runs the self-test (about three minutes the first
                                            time, most of it laying districts over precincts; under one after)
    python ballot/ia_geo.py --selftest      runs the self-test on the files already built
    python ballot/ia_geo.py --refresh       asks the map services again even when the cached copies are fresh
    python ballot/ia_geo.py --out DIR       builds somewhere else (a trial run)
    python ballot/ia_geo.py --polls DIR     looks for a saved polling place list in another folder (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ia_local/)
----------------------------------------------------------------------------------------------------------------------
  - Precincts: "State of Iowa Precinct Boundaries" (Iowa Secretary of State and Legislative Services Agency, on the
    state's open-data site geodata.iowa.gov): the precincts as of the 2022 reprecincting, last changed January 2024.
    Asked for: county, the precinct's official name and number, the number of its polling place and the date of the
    row. Never asked for: the Editor and EditNotes columns (a staff member's name, free text).
    Two counties' rows have a wrong or short county code in the layer's CoFIPS column (Wayne County's four precincts
    carry Polk County's; Jasper County's is written 99, not 099), while their county name, county number and
    precinct number agree: a row's county is taken from its county number, and the area check (each county's
    precincts against the Census Bureau's county) stops the build if a county's precincts are not where the county is.
  - Iowa House, Iowa Senate and congressional districts: the Legislative Services Agency's "Iowa Legislative Districts"
    (the plan enacted in 2021, in force from the 2022 election). Only the district number is asked for; the layers
    also carry each member's name, party, photo and e-mail, which are never requested.
  - County supervisor districts: the Agency's "County Supervisor Districts" (as of January 11, 2024), with each
    county's plan under Iowa Code 331.206: Plan One (elected at large), Plan Two (elected at large, one from each
    district of residence) or Plan Three (each district's own voters elect its supervisor). Only Plan Three districts
    are voting areas, so only they are shapes; the others are listed in index.json under "supervisor_plans".
  - School districts: the Department of Education's "Current Iowa School Districts" (2026-2027). Only the district's
    name and number are asked for; the layer's administrator, phone, e-mail and address columns never are.
  - Counties, townships and the state's outline: the Census Bureau's TIGER/Line 2025 county subdivisions of Iowa
    (tl_2025_19_cousub.zip). Cities: TIGER/Line 2025 places (tl_2025_19_place.zip; incorporated cities only).
  - Judicial election districts (Iowa Code 602.6109: 1A, 1B, 2A, 2B, 3A, 3B, 4, 5A, 5B, 5C, 6, 7, 8A, 8B): each is
    whole counties; which counties is read from the Agency's "Judicial Districts" layer and the lines are the Census
    Bureau's county lines.
  - Soil and water conservation districts: one a county, except Pottawattamie County's two (East and West), whose
    line is the Agency's (its soil and water layer of 2016, the only published line).

What Iowa calls things, and what that does to the files
-------------------------------------------------------
A precinct in Iowa is often several townships together, or a small city with the township around it ("Lincoln/Grant").
So a precinct does not say which township or city a voter lives in, and that matters: under Iowa Code 39.22 township
trustees and clerks are elected by the voters of the township who live outside the limits of any city. The "mcd" layer
therefore carries both kinds of place, cities first: a point is in the city whose limits hold it, and otherwise in its
township. A township's shape is the whole township (the Census Bureau's), cities included; index.json says so. A
precinct's "mcd" is the place holding most of its area and "mcd_all" lists every place it reaches; a page that needs
the place at a point must ask the mcd layer (MNGeo.shapeAt) and not the precinct. For the same reason "mcd" is not one
of the kinds whose outline the county files can draw (arc_kinds), and the layer is kept at fine detail for every zoom.

Precincts must lie inside one legislative district (Iowa Code 49.3), so which House, Senate and congressional district
a precinct is in is found by laying the Agency's district lines over it: the district holding most of the precinct. A
precinct with 3 percent or more of its area in a second district is marked "split" and listed in index.json.

What is built (ballot_geo/ia/): index.json, manifest.json, precincts/<county>.json (99), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, com, swcd, hospital, school), school/<id>.json, polling_places.json and
reader.js, each as ballot/mn_geo.py describes. Coordinates are on the same grid (0.00001 degree, translate [-98, 43];
Iowa lies south of 43.5 north, so most of its grid latitudes are negative numbers, which TopoJSON allows).

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "IA" (j = "19", the jurisdiction_id of statewide races)
  county    "19153"                 sl_places county id; jurisdiction_id of county offices
  mcd       "IA-M-91707"            a township: IA-M- and the Census county subdivision code (sl_places mcd id)
            "IA-M-21000"            a city: IA-M- and the Census place code (no city office is on the 2026 ballot)
  com       "19153|4"               <county>|<supervisor district>, Plan Three counties only
  house     "33"   senate "17"   cd "3" (properties.race is the federal race id, 2026-IA-H03)
  judicial  "JD5C"                  the judicial election district (d = "5C")
  swcd      "IA-SW-153"             the county's soil and water conservation district: j = the county, d = null.
                                    Pottawattamie's two are "IA-SW-155E" and "IA-SW-155W", with properties.jn
  hospital  "IA-H-153-county-public-hospital"   sl_places hospital id: a county public hospital is the county
  school    "IA-S-1737"             IA-S- and the Department's four-digit district number

Not drawn, because no statewide source has the lines: the supervisor districts drawn since January 2024 (Black Hawk,
Johnson and Story counties moved to Plan Three for 2026; Dallas County went to five supervisors), city wards, school
director districts for odd-year elections (the Agency publishes those; no school office is on the 2026 ballot),
sanitary, water, lighting and lake districts. index.json lists every race without a shape under "check".

Tried on 2026-10-02, besides the self-test: 70 points (40 anywhere in the state, 30 in ten cities) asked of the
publishers' own services (which precinct, House, Senate, congressional, school and supervisor district holds this
point) gave the same answers as the built files, every one; and ballot/mn_geo_reader.js, run under Windows Script
Host on 700 points, gave the same precinct, distance to its line, city or township and House district as the Python
here, every one (Iowa's grid latitudes are negative; the reader needed no change).

POLLING PLACES
--------------
The same open-data site carries "Iowa Polling Places" (1,386 buildings with coordinates) and each precinct row names
its polling place by number. But every row of that layer is marked 2024 and it was last changed on September 11,
2024: it is the list for the 2024 general election, not for November 3, 2026, and a voter must not be sent anywhere by
it. So polling_places.json says the list is waiting and gives the Secretary of State's own finder. Two ways it can
change, both John's decision: (1) if the Secretary of State's office or the Agency confirms the layer is current for
November 3, 2026 (or republishes it), set POLL_USE_PUBLISHED_LAYER = True and build again; (2) if he is given a
statewide list for that election, he saves it (.csv or .txt, as it is) into states_cache/ia_local/sos/pollingplaces/
and this builder reads it with mn_geo's reader (columns found by their headings), marked "unchecked" until a person
has compared it with the file.
"""

import argparse
import collections
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
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402

GeoError = G.GeoError
STATE, FIPS = "IA", "19"
OUT = os.path.join(HERE, "ballot_geo", "ia")
CACHE = os.path.join(HERE, "states_cache", "ia_local")
POLL_DIR = os.path.join(CACHE, "sos", "pollingplaces")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://apps.sos.iowa.gov/elections/voterreg/pollingplace/search.aspx"      # as linked from sos.iowa.gov/voting-election-day

STATE_GIS = "https://services.arcgis.com/vPD5PVLI6sfkZ5E4/arcgis/rest/services/"      # the State of Iowa's ArcGIS organisation
LSA_GIS = "https://services2.arcgis.com/KhKjlwEBlPJd6v51/arcgis/rest/services/"       # the Legislative Services Agency's
HUB = "https://geodata.iowa.gov/datasets/"
PCT_SERVICE = STATE_GIS + "Iowa_Precincts/FeatureServer/0"
PCT_ITEM = HUB + "d394edea208c4003ac1d6bd1ec78532f"
PCT_FIELDS = "CoFIPS,CoName,CoNo,PctNameOfficial,Label,PctNumID,PCTID_TXT,NumID,PPID,EditDate"        # never Editor, EditNotes
SUP_SERVICE = STATE_GIS + "CountySupervisorDistricts/FeatureServer/0"
SUP_FIELDS = "DISTRICT,MEMBERS,NAME,CONO,FIPS,COUNTY,CODIST_ID,PLANTYPE,NUMDISTRICTS"            # never EDITNOTES
LEG_SERVICE = LSA_GIS + "IowaLegislativeDistricts/FeatureServer/"
LEG_ITEM = HUB + "d1a9e1b15b9a4436b776983db02f7b20"
SUP_ITEM = HUB + "a14f87eb39ec470e81684a8a3efd2d96"
SWCD_ITEM = HUB + "7e1ebfae60294fa19811aa98b39db086"
SCHOOL_SERVICE = STATE_GIS + "CurrentIowaSchoolDistricts/FeatureServer/0"
SCHOOL_ITEM = HUB + "2c56482f1e4b40c69947a2ee67515d6e"
SCHOOL_FIELDS = "SchoolDistName,DE_DIST,DistrictName,DistrictNCESCode"                           # never the administrator, phone, e-mail or address columns
JUD_SERVICE = LSA_GIS + "JudicialDistricts/FeatureServer/1"
JUD_ITEM = HUB + "167f1e58375643a68eba19eed8b044f3"
SWCD_SERVICE = STATE_GIS + "ReapSWCD/FeatureServer/0"
POLL_SERVICE = STATE_GIS + "IowaPollingPlaces/FeatureServer/0"
POLL_ITEM = HUB + "b5df2a66ec294337bd7ad5c17c7673fd"
POLL_FIELDS = "CONO,COUNTYNAME,POLLINGPLACENAME,POLLINGPLACEADDR,PPID,PPNUM,ACTIVE,X,Y"          # never NOTE (free text)
COUSUB_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_19_cousub.zip"
PLACE_URL = "https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_19_place.zip"

POTT = "19155"                                            # Pottawattamie County: two soil and water conservation districts
JUD_DISTRICTS = ["1A", "1B", "2A", "2B", "3A", "3B", "4", "5A", "5B", "5C", "6", "7", "8A", "8B"]
ARC_KINDS = ["county", "com", "house", "senate", "cd", "judicial", "swcd", "hospital"]      # not mcd: precincts do not follow township and city lines
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD = 5.0                     # metres: the mcd layer is the only place its lines are, so it is kept fine
MCD_ZOOM = 30                     # "good to zoom" for the mcd layer: a page never leaves it for the county files
MCD_THICK = G.SCHOOL_THICK        # metres: a place's part of a precinct must be this thick somewhere to be listed
NEAR_M = G.NEAR_M
POLL_USE_PUBLISHED_LAYER = False  # True only when the 2024 layer has been confirmed (or republished) for November 3, 2026


# ---------------------------------------------------------------- the sources

def read_shapefile(path, keep):
    """A Census shapefile inside its zip: [(record as a dict, rings as vertex keys)] for the records `keep` accepts."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    out = []
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        if not keep(rec):
            continue
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        out.append((rec, [k for k in (G.clean_ring(pts[parts[i]:parts[i + 1]]) for i in range(len(parts) - 1)) if k]))
    return out


def read_precincts(doc):
    """The precinct rows, in id order, cut down to what the map needs, and their rings as vertex keys."""
    pre, polys, seen, fixed = [], [], set(), collections.Counter()
    for a, rings in doc["rows"]:
        co, txt, name = G.blank(a["CoFIPS"]), G.blank(a["PCTID_TXT"]), re.sub(r"\s+", " ", G.blank(a["PctNameOfficial"]))
        if not name and G.blank(a.get("Label")):      # two rows have no official name; the layer's own label (the name in capitals) is used
            name = re.sub(r"\s+", " ", G.blank(a["Label"])).title()
            fixed["named from the label"] += 1
        m = re.fullmatch(r"(\d{3})-(\d{3})", txt)
        if m and isinstance(a["CoNo"], int) and int(m.group(1)) == a["CoNo"] and co != f"{2 * a['CoNo'] - 1:03d}":
            co = f"{2 * a['CoNo'] - 1:03d}"      # the county number, the precinct number and the name agree; the CoFIPS cell does not
            fixed[FIPS + co] += 1
        ok = (re.fullmatch(r"\d{3}", co) and 1 <= int(co) <= 197 and m and int(m.group(1)) == a["CoNo"] == (int(co) + 1) // 2
              and name and G.blank(a["CoName"]))
        if not ok:
            raise GeoError(f"    precinct table: the row for precinct {txt!r} of county {co!r} does not fit the layout this builder was checked against; stopping")
        pid = FIPS + co + m.group(2)
        if pid in seen:
            raise GeoError(f"    precinct table: two rows are precinct {txt}; stopping")
        seen.add(pid)
        pre.append({"id": pid, "county": FIPS + co, "countyname": G.blank(a["CoName"]), "name": name, "ppid": G.blank(a["PPID"]),
                    "edited": dt.datetime.fromtimestamp((a["EditDate"] or 0) / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if a["EditDate"] else "",
                    })
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    order = sorted(range(len(pre)), key=lambda i: pre[i]["id"])
    pre, polys = [pre[i] for i in order], [polys[i] for i in order]
    if len({p["county"] for p in pre}) != 99:
        raise GeoError(f"    precincts: {len({p['county'] for p in pre})} counties, not 99; stopping")
    names = collections.defaultdict(set)
    for p in pre:
        names[p["county"]].add(p["countyname"])
    two = [c for c, v in names.items() if len(v) > 1]
    if two:
        raise GeoError(f"    precinct table: county {two[0]} is given two names ({', '.join(sorted(names[two[0]]))}); stopping")
    return pre, polys, dict(fixed)


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ia-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def rings_xy(polys):
    return [[[G.vxy(k) for k in ring] for ring in rings] for rings in polys]


def ring_area_m2(pts):
    c = math.cos(math.radians(sum(y for _x, y in pts) / len(pts) / 1e7))
    return abs(G.area2(pts)) * c * G.M_PER_UNIT ** 2 / 2


# ---------------------------------------------------------------- districts laid over precincts

def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed: for each precinct,
    [[district number, share of the precinct's area, thick enough]]."""
    path = os.path.join(CACHE, f"ia_geo_overlay_{name}.json")
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


def place_overlay(pre_rings, cities, towns, thick_m, say=None):
    """For each precinct, the places it reaches: [[number, share of the precinct's area, thick enough]], where a number
    below len(cities) is a city and the rest are townships. A city's part is what lies inside its limits; a township's
    part is what lies in the township and in no city (Iowa Code 39.22: a township's officers are elected outside city
    limits). Drawn and counted on a grid over the precinct, as mn_geo.school_overlay does."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    def boxes(districts):
        out = []
        for rings in districts:
            bs = [(min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r)) for r in rings]
            out.append(((min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)), bs))
        return out

    cbox, tbox = boxes(cities), boxes(towns)
    shrink = ImageFilter.MinFilter(3)
    out = []
    for n, rings in enumerate(pre_rings):
        x0, y0 = min(p[0] for r in rings for p in r), min(p[1] for r in rings for p in r)
        x1, y1 = max(p[0] for r in rings for p in r), max(p[1] for r in rings for p in r)
        kx, ky = G.M_PER_UNIT * math.cos(math.radians((y0 + y1) / 2e7)), G.M_PER_UNIT
        span = max((x1 - x0) * kx, (y1 - y0) * ky, 1.0)
        cell = min(max(span / 900.0, 6.0), 20.0)
        if span / cell > 3000:
            cell = span / 3000.0
        reach = max(1, int(math.ceil((thick_m / cell - 1) / 2.0)))
        size = (int((x1 - x0) * kx / cell) + 3, int((y1 - y0) * ky / cell) + 3)

        def mask(some):
            m = None
            for r in some:
                t = Image.new("1", size, 0)
                ImageDraw.Draw(t).polygon([((x - x0) * kx / cell + 1, (y1 - y) * ky / cell + 1) for x, y in r], fill=1)
                m = t if m is None else ImageChops.logical_xor(m, t)
            return m

        def measure(both, total):
            bb = both.getbbox()
            if bb is None:
                return None
            share = both.crop(bb).convert("L").histogram()[255] / total
            if share >= 0.5:
                return share, True
            sub = both.crop((bb[0] - reach - 1, bb[1] - reach - 1, bb[2] + reach + 1, bb[3] + reach + 1)).convert("L")
            for _ in range(reach):
                sub = sub.filter(shrink)
                if sub.getbbox() is None:
                    return share, False
            return share, True

        def near(box_list, districts):
            for d, (box, bs) in enumerate(box_list):
                if box[0] > x1 or box[2] < x0 or box[1] > y1 or box[3] < y0:
                    continue
                some = [r for r, b in zip(districts[d], bs) if not (b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0)]
                if some:
                    yield d, mask(some)

        mine = mask(rings)
        total = mine.convert("L").histogram()[255]
        got = []
        if total:
            rural = mine
            for d, m in near(cbox, cities):
                hit = measure(ImageChops.logical_and(mine, m), total)
                if hit:
                    got.append([d, round(hit[0], 5), hit[1]])
                    rural = ImageChops.logical_and(rural, ImageChops.invert(m))
            for d, m in near(tbox, towns):
                hit = measure(ImageChops.logical_and(rural, m), total)
                if hit:
                    got.append([len(cities) + d, round(hit[0], 5), hit[1]])
        out.append(got)
        if say and (n + 1) % 500 == 0:
            say(f"      cities and townships over precincts: {n + 1:,} of {len(pre_rings):,}")
    return out


def place_overlay_cached(pre_rings, cities, towns, stamp, refresh, say):
    path = os.path.join(CACHE, "ia_geo_overlay_places.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say("      laying the city and township lines over the precincts (kept for the next build)")
    rows = place_overlay(pre_rings, cities, towns, MCD_THICK, say)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def assign(pre, overlay, keys, prop, only=None):
    """Each precinct's district of one kind: the one holding most of it (W.assign, for some precincts only). Returns
    the precincts split between two and the precincts no district touches."""
    split, none = [], []
    for p, got in zip(pre, overlay):
        if only is not None and not only(p):
            p[prop] = None
            continue
        got = sorted(got, key=lambda g: -g[1])
        if not got:
            none.append(p["id"])
            p[prop] = None
            continue
        p[prop] = keys[got[0][0]]
        if len(got) > 1 and got[1][1] >= SPLIT_SHARE:
            p.setdefault("split", {})[prop] = {keys[d]: round(100 * s, 1) for d, s, _t in got if s >= SPLIT_SHARE}
            split.append(p["id"])
    return split, none


def fabric(rows, key):
    """One layer's shapes as a fabric: (keys in order, polygons as vertex keys, arcs, sides, rings, anything odd)."""
    rows = sorted(rows, key=lambda r: G.natkey(key(r[0])))
    keys = [key(a) for a, _r in rows]
    if len(set(keys)) != len(keys):
        raise GeoError(f"    two shapes share the id {[k for k, n in collections.Counter(keys).items() if n > 1][0]!r}; stopping")
    polys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in rows]
    slivers, gave = W.settle_overlaps([{"id": k} for k in keys], polys)      # two neighbours that run the same way along a line: the later one gives the point up
    arcs, sides, rings, odd = G.topology(polys)
    if slivers or gave:
        odd = collections.Counter(odd)
        odd["sliver rings left out"] += slivers
        odd["points given up where two shapes overlapped"] += sum(n for _k, n in gave)
        odd = collections.Counter({k: v for k, v in odd.items() if v})
    if any(not r for r in rings):
        raise GeoError(f"    the shape {keys[[i for i, r in enumerate(rings) if not r][0]]!r} has no ring left after cleaning; stopping")
    return keys, polys, arcs, sides, rings, odd


# ---------------------------------------------------------------- ids against the ballot database

def township_hint(jur, counties, shapes, town_county):
    """Why a township race names no shape, with what the Census Bureau's file has instead in the same county."""
    here = {i: p["name"] for i, p in shapes.items() if p.get("t") == "township" and town_county.get(i) in counties}
    fold = lambda t: re.sub(r"[^a-z]", "", t.lower())      # noqa: E731
    same = sorted(i for i, n in here.items() if fold(n) == fold(jur or ""))
    if same:
        return f"the Census Bureau's file carries {jur} as {same[0]}; the ballot database files it under another id"
    word = fold(re.sub(r"(?i)\s*township$", "", jur or ""))
    like = sorted(n for n in here.values() if word and word in fold(n))
    if like:
        return f"the Census Bureau's 2025 file has no township of this name in the county; it has {' and '.join(like)}"
    return "no Census county subdivision carries this id"


def check_ids(info, shape_ids, plans, town_county=None):
    """Every Iowa race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape). A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, county_ids in sorted(info["races"], key=lambda r: r[0]):
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
        elif kind == "county_commissioner":
            hit = ("com", f"{jid}|{d}")
            plan = plans.get(jid)
            if not d:
                why = "elected by the whole county: the page's rule looks for a supervisor district, so the race names no shape and is listed for everyone in the county"
            elif plan is None:
                why = "the Legislative Services Agency's layer of supervisor districts (January 2024) has no row for this county"
            elif plan["plan"] != 3:
                why = (f"the Agency's layer (January 2024) shows this county electing supervisors at large (Plan {'One' if plan['plan'] == 1 else 'Two'}); "
                       "if it has moved to districts since, no statewide source has the new lines")
            elif d not in plan["districts"]:
                why = f"the Agency's layer (January 2024) has districts {', '.join(plan['districts'])} for this county, not {d}"
        elif level == "county":
            hit = ("county", jid)
        elif level == "soil_water":
            own = sorted(i for i, p in S.get("swcd", {}).items() if p.get("j") == jid)
            by_n = [i for i in own if S["swcd"][i].get("jn") and S["swcd"][i]["jn"] == jur]
            whole = [i for i in own if S["swcd"][i].get("d") is None]
            hit = ("swcd", by_n[0]) if by_n else ("swcd", whole[0]) if len(whole) == 1 else None
            why = None if hit else "the county has two soil and water conservation districts and the race's jurisdiction names neither as the map does"
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = "no source has city ward lines"
            elif jid not in S.get("mcd", {}):
                try:
                    cos = set(json.loads(county_ids or "[]"))
                except ValueError:
                    cos = set()
                why = township_hint(jur, cos, S.get("mcd", {}), town_county or {})
        elif level == "school":
            hit = ("school", jid)
        elif level == "hospital":
            hit = ("hospital", jid)
        elif level == "other" and kind == "extension_council" and jid in S.get("county", {}):
            why = "a county-wide board (the county's agricultural extension district is the county); the page's rule places no shape for this kind of office, so it is listed for the whole county"
        else:
            why = "no source carries a boundary for this kind of district (a sanitary, water, lighting or lake district)"
        if hit and hit[1] in S.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places

POLL_WAITING = {
    "why": "Iowa's published statewide list of polling places is the one for the 2024 general election (last changed in September 2024), "
           "not the list for November 3, 2026, so it is not shown here. The Iowa Secretary of State's polling place finder answers for one "
           "address at a time and, with the county auditor, is the authority.",
}
POLL_HOW = ("      polling places: waiting. The state's open-data layer \"Iowa Polling Places\" was read (see the counts above) but every row of it "
            "is marked 2024 and it was last changed on {changed}: it is not the November 3, 2026 list, so nothing from it is published. John's "
            "decision, either way: (1) ask the Secretary of State's elections office (or the Legislative Services Agency, which publishes the "
            "layer) whether it is current for November 3, 2026; if they say yes or republish it, set POLL_USE_PUBLISHED_LAYER = True in "
            "ballot/ia_geo.py and build again; or (2) if they send a statewide list for that election, save it as it is (.csv or .txt) into "
            "states_cache/ia_local/sos/pollingplaces/ and build again.")


def published_places(pdoc, pre):
    """The 2024 layer joined to the precincts by the polling place number each precinct row carries."""
    by_id, places, order, precinct = {}, [], {}, {}
    for a, _g in pdoc["rows"]:
        by_id[G.blank(a["PPID"])] = a
    for p in pre:
        a = by_id.get(p["ppid"]) if p["ppid"] else None
        if a is None or not G.blank(a["POLLINGPLACENAME"]):
            continue
        if p["ppid"] not in order:
            addr = re.sub(r"\s+", " ", G.blank(a["POLLINGPLACEADDR"]))
            m = re.match(r"(.*?),?\s+IA\s+(\d{5})(?:-\d{4})?$", addr)
            lonlat = None
            if isinstance(a.get("X"), (int, float)) and isinstance(a.get("Y"), (int, float)) and -96.7 < a["X"] < -90.1 and 40.3 < a["Y"] < 43.6:
                lonlat = [round(a["X"], 5), round(a["Y"], 5)]
            order[p["ppid"]] = len(places)
            places.append({"name": re.sub(r"\s+", " ", G.blank(a["POLLINGPLACENAME"])), "address": m.group(1) if m else addr, "city": "",
                           "zip": m.group(2) if m else "", "type": None, "lonlat": lonlat, "precincts": []})
        places[order[p["ppid"]]]["precincts"].append(p["id"])
        precinct[p["id"]] = order[p["ppid"]]
    return places, precinct


def polling_places(pre, put, say, refresh, folder=None):
    folder = folder or POLL_DIR
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    found = sorted((f for ext in ("*.csv", "*.txt", "*.tsv") for f in glob.glob(os.path.join(folder, ext))), key=os.path.getmtime)
    if found:
        path = found[-1]
        try:
            got = G.read_polling_file(path, pre)
        except GeoError as e:
            doc.update(status="waiting", **POLL_WAITING)
            put("polling_places.json", doc)
            say(str(e))
            return {"file": "polling_places.json", "status": "unread"}
        doc.update(status="unchecked",
                   source={"agency": "Iowa Secretary of State", "title": "Polling places, general election of November 3, 2026",
                           "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path)},
                   places=got["places"], precinct=got["precinct"], no_place=got["no_place"])
        put("polling_places.json", doc)
        say(f"      polling places ({os.path.basename(path)}): {len(got['places']):,} places for {len(got['precinct']):,} precincts; marked 'unchecked' "
            "(the reader was written before any such file was seen): a page must not show it until a person has compared a dozen precincts with the file")
        return {"file": "polling_places.json", "status": "unchecked", "places": len(got["places"])}
    ppath = os.path.join(CACHE, "lsa_polling_places_2024.json.gz")
    about = {}
    try:
        pdoc = W.fetch_full(POLL_SERVICE, POLL_FIELDS, ppath, 1000, "OBJECTID", refresh, say)
        edited = W.layer_edited(POLL_SERVICE, os.path.join(CACHE, "ia_geo_about_polling.json"), refresh).get("current_to")
        places, precinct = published_places(pdoc, pre)
        years = sorted({G.blank(str(a.get("ACTIVE") or "")) for a, _g in pdoc["rows"]})
        about = {"title": "Iowa Polling Places (Iowa Secretary of State, Iowa Legislative Services Agency)", "url": POLL_ITEM, "service": POLL_SERVICE,
                 "last_changed": edited, "rows_marked": years, "places": len(pdoc["rows"]), "precincts_with_a_place": len(precinct),
                 "precincts": len(pre), "sha256": G.sha_file(ppath)}
        say(f"      polling places: the state's layer has {len(pdoc['rows']):,} places, every row marked {', '.join(years)}, last changed {edited}; "
            f"{len(precinct):,} of {len(pre):,} precincts name one of them")
    except Exception as e:  # noqa: BLE001  the map does not depend on this layer
        say(f"      polling places: the state's layer could not be read ({e})")
        pdoc, places, precinct, edited = None, [], {}, None
    if POLL_USE_PUBLISHED_LAYER and places:
        doc.update(status="loaded",
                   source={"agency": "Iowa Secretary of State and Iowa Legislative Services Agency",
                           "title": f"Iowa Polling Places layer (last changed {edited})", "saved": pdoc.get("fetched"), "sha256": G.sha_file(ppath)},
                   places=places, precinct=dict(sorted(precinct.items())), no_place={})
        put("polling_places.json", doc)
        return {"file": "polling_places.json", "status": "loaded", "places": len(places), "with_coordinates": sum(1 for p in places if p["lonlat"]),
                "published_layer": about}
    doc.update(status="waiting", **POLL_WAITING)
    put("polling_places.json", doc)
    say(POLL_HOW.format(changed=edited or "an earlier date"))
    return {"file": "polling_places.json", "status": "waiting", "published_layer": about}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print, polls_dir=None):
    t0 = time.time()
    say("    Iowa ballot map: precinct, district, township, city and school district lines (the State of Iowa's open data, the Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    ppath, suppath, hpath, spath, cpath = (path(n) for n in ("lsa_precincts_2022_geometry_4326.json.gz", "lsa_supervisor_districts_2024_geometry_4326.json.gz",
                                                             "lsa_house_2023_geometry_4326.json.gz", "lsa_senate_2023_geometry_4326.json.gz",
                                                             "lsa_congress_2023_geometry_4326.json.gz"))
    scpath, jpath, swpath = path("doe_school_districts_2026_27_geometry_4326.json.gz"), path("lsa_judicial_subdistricts_geometry_4326.json.gz"), path("lsa_swcd_geometry_4326.json.gz")
    tpath, plpath = path("tl_2025_19_cousub.zip"), path("tl_2025_19_place.zip")
    pdoc = W.fetch_full(PCT_SERVICE, PCT_FIELDS, ppath, 200, "OBJECTID", refresh, say)
    supdoc = W.fetch_full(SUP_SERVICE, SUP_FIELDS, suppath, 100, "OBJECTID", refresh, say)
    hdoc = W.fetch_full(LEG_SERVICE + "0", "DISTRICTID,NAME,DISTNUM", hpath, 10, "OBJECTID", refresh, say)
    sdoc = W.fetch_full(LEG_SERVICE + "1", "DISTRICTID,NAME,DISTNUM", spath, 10, "OBJECTID", refresh, say)
    cdoc = W.fetch_full(LEG_SERVICE + "2", "DISTRICTID,NAME,DistrictNum", cpath, 1, "OBJECTID", refresh, say)
    scdoc = W.fetch_full(SCHOOL_SERVICE, SCHOOL_FIELDS, scpath, 40, "OBJECTID", refresh, say)
    jdoc = W.fetch_full(JUD_SERVICE, "JUD_SDIST", jpath, 5, "OBJECTID", refresh, say)
    swdoc = W.fetch_full(SWCD_SERVICE, "Name,District", swpath, 25, "OBJECTID_1", refresh, say)
    for url, p in ((COUSUB_URL, tpath), (PLACE_URL, plpath)):
        net.download(url, p, 3650, say=say)
    edited = {k: W.layer_edited(svc, path(f"ia_geo_about_{k}.json"), refresh)
              for k, svc in (("precincts", PCT_SERVICE), ("supervisor", SUP_SERVICE), ("house", LEG_SERVICE + "0"), ("school", SCHOOL_SERVICE))}

    # ---- precincts: one line between two neighbours, kept once
    pre, polys, fips_fixed = read_precincts(pdoc)
    slivers, gave = W.settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); "
        f"{lone:,} lines have a precinct on one side only, {len(seam):,} of them with another precinct just across; {slivers} rings under "
        f"{W.SLIVER_M2:.0f} square metres left out, {sum(n for _w, n in gave)} points given up by {len(gave)} precincts that ran along a neighbour's line the same way"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's county subdivisions (one fabric statewide) and places
    cous = sorted(read_shapefile(tpath, lambda r: r["STATEFP"] == FIPS), key=lambda x: (x[0]["COUNTYFP"], x[0]["COUSUBFP"]))
    if len({r["COUNTYFP"] for r, _ in cous}) != 99:
        raise GeoError(f"    {os.path.basename(tpath)}: {len({r['COUNTYFP'] for r, _ in cous})} counties, not 99; stopping")
    carcs, csides, crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    cities_ = sorted(read_shapefile(plpath, lambda r: r["STATEFP"] == FIPS and r["LSAD"] == "25"), key=lambda x: x[0]["PLACEFP"])
    parcs, psides, _prings, podd = G.topology([rings for _r, rings in cities_])
    town_rows = [(r, rings) for r, rings in cous if r["LSAD"] != "25"]      # townships (and one unorganized territory); a city that is its own subdivision is in the places file
    town_key = [f"{STATE}-M-{r['COUSUBFP']}" for r, _ in cous]
    town_val = [k if r["LSAD"] != "25" else None for k, (r, _) in zip(town_key, cous)]
    city_key = [f"{STATE}-M-{r['PLACEFP']}" for r, _ in cities_]
    if len(set(city_key)) != len(city_key) or set(city_key) & {k for k in town_val if k} or len({k for k in town_val if k}) != len(town_rows):
        raise GeoError("    a city and a township, or two of either, share a code; stopping")
    city_set = set(city_key)
    census_name = {k: r["NAMELSAD"] for k, (r, _) in zip(town_key, cous)}
    census_name.update({k: r["NAMELSAD"] for k, (r, _) in zip(city_key, cities_)})
    town_county = {k: c for k, c in zip(town_key, ccounty)}

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_short = {}
    for p in pre:
        county_short[p["county"]] = p["countyname"]
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in county_short.items()}
    mname = {k: names.get(("mcd", k)) or n for k, n in census_name.items()}

    # ---- counties' own shapes (for the judicial districts and the area check)
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)
    jrows = sorted(jdoc["rows"], key=lambda r: G.natkey(r[0]["JUD_SDIST"]))
    jkeys = [G.blank(a["JUD_SDIST"]) for a, _r in jrows]
    if sorted(jkeys) != sorted(JUD_DISTRICTS):
        raise GeoError(f"    judicial election districts: the layer has {jkeys}, not Iowa Code 602.6109's fourteen; stopping")
    jrings = rings_xy([[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in jrows])
    jud, weak = {}, []
    for c, got in zip(clist, G.school_overlay([county_rings[c] for c in clist], jrings, levels=(G.SCHOOL_THICK,), say=None)):
        got = sorted(got, key=lambda g: -g[1])
        if not got or got[0][1] < 0.9:
            weak.append(c)
        else:
            jud[c] = "JD" + jkeys[got[0][0]]
    if weak or len(jud) != 99:
        raise GeoError(f"    judicial election districts: {len(weak)} counties are not nine tenths inside one district (e.g. {weak[:3]}); stopping")

    # ---- supervisor districts and plans
    plans, sup_rows = {}, []
    for a, rings in supdoc["rows"]:
        m = re.fullmatch(r"PLAN ([123])", G.blank(a["PLANTYPE"]))
        county, d = f"{FIPS}{int(a['FIPS']):03d}", G.blank(a["DISTRICT"])
        if not m or county not in county_short or not (d.isdigit() or d == "AT-LARGE"):
            raise GeoError(f"    supervisor districts: the row for county {a.get('FIPS')!r}, district {d!r} does not fit the layout this builder was checked against; stopping")
        e = plans.setdefault(county, {"plan": int(m.group(1)), "supervisors": a["NUMDISTRICTS"], "districts": []})
        if e["plan"] != int(m.group(1)):
            raise GeoError(f"    supervisor districts: county {county} is given two plans; stopping")
        if d.isdigit():
            e["districts"].append(d)
            if e["plan"] == 3:
                sup_rows.append(({"id": f"{county}|{d}"}, rings))
    for e in plans.values():
        e["districts"].sort(key=int)
    skeys_, spolys_, suarcs, susides, _sur, suodd = fabric(sup_rows, lambda a: a["id"])
    plan3 = {c for c, e in plans.items() if e["plan"] == 3}

    # ---- House, Senate, Congress, school districts, Pottawattamie's two soil and water districts
    hkeys, hpolys, harcs, hsides, _hr, hodd = fabric(hdoc["rows"], lambda a: str(int(a["DISTNUM"])))
    skeys, spolys, sarcs, ssides, _ser, sodd = fabric(sdoc["rows"], lambda a: str(int(a["DISTNUM"])))
    ckeys, cpolys, cdarcs, cdsides, _cdr, cdodd = fabric(cdoc["rows"], lambda a: str(int(a["DistrictNum"])))
    if hkeys != [str(n) for n in range(1, 101)] or skeys != [str(n) for n in range(1, 51)] or ckeys != ["1", "2", "3", "4"]:
        raise GeoError("    legislative districts: not 100 House, 50 Senate and 4 congressional districts; stopping")
    for a, _r in scdoc["rows"]:
        if not isinstance(a["DE_DIST"], (int, float)) or not 0 < int(a["DE_DIST"]) < 10000 or not G.blank(a["DistrictName"]):
            raise GeoError(f"    school districts: the row numbered {a['DE_DIST']!r} does not fit the layout this builder was checked against; stopping")
    schkeys, schpolys, scharcs, schsides, _sr, schodd = fabric(scdoc["rows"], lambda a: f"{STATE}-S-{int(a['DE_DIST']):04d}")
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    sname = {f"{STATE}-S-{int(a['DE_DIST']):04d}": names.get(("school", f"{STATE}-S-{int(a['DE_DIST']):04d}")) or re.sub(r"\bComm\b", "Community", G.blank(a["DistrictName"]))
             for a, _r in scdoc["rows"]}
    pott = [(a, r) for a, r in swdoc["rows"] if G.blank(a["Name"]).upper().startswith("POTTAWATTAMIE")]
    if sorted(G.blank(a["Name"]).upper() for a, _r in pott) != ["POTTAWATTAMIE EAST", "POTTAWATTAMIE WEST"] or len(swdoc["rows"]) != 100:
        raise GeoError("    soil and water districts: not one hundred, with Pottawattamie East and West; stopping")
    wkeys, wpolys, warcs, wsides, _wr, _wodd = fabric(pott, lambda a: f"{STATE}-SW-155{G.blank(a['Name']).upper()[-4]}")
    swcd_of = {c: f"{STATE}-SW-{c[2:]}" for c in county_short if c != POTT}
    swname = {v: f"{cname[c]} Soil and Water Conservation District" for c, v in swcd_of.items()}
    swname.update({f"{STATE}-SW-155E": "East Pottawattamie Soil and Water Conservation District", f"{STATE}-SW-155W": "West Pottawattamie Soil and Water Conservation District"})
    hosp_of = {}
    for (kind, pid), _n in names.items():
        m = re.fullmatch(rf"{STATE}-H-(\d{{3}})-county-public-hospital", pid) if kind == "hospital" else None
        if m and FIPS + m.group(1) in county_short:
            hosp_of[FIPS + m.group(1)] = pid
    say(f"      100 House districts ({len(harcs):,} lines), 50 Senate ({len(sarcs):,}), 4 congressional ({len(cdarcs):,}), {len(schkeys)} school districts "
        f"({len(scharcs):,} lines), {len(skeys_)} supervisor districts in {len(plan3)} Plan Three counties ({len(suarcs):,} lines), "
        f"{len(cous):,} Census county subdivisions ({len(carcs):,} lines), {len(cities_):,} cities ({len(parcs):,} lines)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("House", hodd), ("Senate", sodd), ("Congress", cdodd), ("school", schodd), ("supervisor", suodd),
                                                         ("Census", codd), ("cities", podd)) if o))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, MCD_THICK, 1]).encode()).hexdigest()   # noqa: E731
    o_house = overlay_cached("house", pre_rings, rings_xy(hpolys), stamp(ppath, hpath), refresh, say)
    o_sen = overlay_cached("senate", pre_rings, rings_xy(spolys), stamp(ppath, spath), refresh, say)
    o_cd = overlay_cached("congressional", pre_rings, rings_xy(cpolys), stamp(ppath, cpath), refresh, say)
    o_sup = overlay_cached("supervisor", pre_rings, rings_xy(spolys_), stamp(ppath, suppath), refresh, say)
    o_sw = overlay_cached("pottawattamie-soil", pre_rings, rings_xy(wpolys), stamp(ppath, swpath), refresh, say)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(ppath, scpath), refresh, say)
    o_mcd = place_overlay_cached(pre_rings, rings_xy([r for _a, r in cities_]), rings_xy([r for _a, r in town_rows]), stamp(ppath, tpath, plpath), refresh, say)
    place_keys = city_key + [f"{STATE}-M-{r['COUSUBFP']}" for r, _ in town_rows]

    split_h, none_h = assign(pre, o_house, hkeys, "house")
    split_s, none_s = assign(pre, o_sen, skeys, "senate")
    split_c, none_c = assign(pre, o_cd, ckeys, "cd")
    if none_h or none_s or none_c:
        raise GeoError(f"    {len(none_h)} precincts touch no House district, {len(none_s)} no Senate district, {len(none_c)} no congressional district "
                       f"(e.g. {(none_h + none_s + none_c)[0]}); stopping")
    unnested = sorted({(p["house"], p["senate"]) for p in pre if p["senate"] != str((int(p["house"]) + 1) // 2)})
    if unnested:
        raise GeoError(f"    House and Senate districts: precincts put House district {unnested[0][0]} in Senate district {unnested[0][1]}, "
                       "but a Senate district is House districts 2n-1 and 2n; stopping")
    split_com, none_com = assign(pre, o_sup, skeys_, "com", only=lambda p: p["county"] in plan3)
    wrong_com = [p["id"] for p in pre if p["com"] and not p["com"].startswith(p["county"] + "|")]
    if none_com or wrong_com:
        raise GeoError(f"    supervisor districts: {len(none_com)} precincts of Plan Three counties touch no district and {len(wrong_com)} fall in another "
                       f"county's (e.g. {(none_com + wrong_com)[0]}); stopping")
    split_w, none_w = assign(pre, o_sw, wkeys, "swcd", only=lambda p: p["county"] == POTT)
    if none_w:
        raise GeoError(f"    Pottawattamie County: {len(none_w)} precincts touch neither soil and water district; stopping")
    say(f"      districts by precinct (the one holding most of the precinct): {len(split_h)} precincts have {SPLIT_SHARE:.0%} or more of their area in a "
        f"second House district, {len(split_s)} in a second Senate district, {len(split_c)} in a second congressional district, {len(split_com)} in a "
        f"second supervisor district, {len(split_w)} in Pottawattamie's other soil and water district")
    several = no_place = 0
    for p, got in zip(pre, o_mcd):
        rows = sorted(((place_keys[d], s, t) for d, s, t in got), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t and (k in city_set or town_county.get(k) == p["county"])]
        if not own:
            own = [(k, s) for k, s, _t in rows[:1]]
        if not own:
            no_place += 1
            raise GeoError(f"    precinct {p['id']} lies in no township and no city; stopping")
        p["mcd"] = own[0][0]
        p["mcd_all"] = [k for k, _s in own]
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in own] if len(own) > 1 else None
        several += len(own) > 1
        p["swcd"] = p.get("swcd") or swcd_of[p["county"]]
        p["hospital"] = hosp_of.get(p["county"])
        p["jud_id"] = jud[p["county"]]
    say(f"      cities and townships by precinct: {several:,} of {len(pre):,} precincts reach more than one place (a township's part is what lies outside "
        f"every city); {len(pre) - several:,} lie in one")
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

    # ---- the area check: each county's precincts against the Census Bureau's county
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # Esri's winding: outer rings clockwise
    worst = max(clist, key=lambda c: abs(area_p[c] / sum(ring_area_m2(r) * (1 if G.area2(r) < 0 else -1) for r in county_rings[c]) - 1))
    worst_pct = 100 * (area_p[worst] / sum(ring_area_m2(r) * (1 if G.area2(r) < 0 else -1) for r in county_rings[worst]) - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(ring_area_m2(r) * (1 if G.area2(r) < 0 else -1) for c in clist for r in county_rings[c]) - 1)
    off = [c for c in clist if abs(area_p[c] / sum(ring_area_m2(r) * (1 if G.area2(r) < 0 else -1) for r in county_rings[c]) - 1) > 0.02]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws (more than 2% apart); stopping")
    if fips_fixed:
        say("      " + "; ".join(f"{n} precinct rows had no official name and are named from the layer's label" if c == "named from the label" else
                                 f"{n} precinct rows of {cname[c]} carried another code in CoFIPS and were filed by their county number" for c, n in sorted(fips_fixed.items())))
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's Iowa; the county furthest off is {cname[worst]} ({worst_pct:+.2f}%)")

    vals = {"county": [p["county"] for p in pre], "com": [p["com"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": [p["cd"] for p in pre], "judicial": [p["jud_id"] for p in pre], "swcd": [p["swcd"] for p in pre], "hospital": [p["hospital"] for p in pre]}
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

    def one(arcs_, sides_, v, tol):
        g, q, _l, _r = G.build_layer(arcs_, sides_, [v], tol)
        return g, q

    CENSUS, PLACES, PCT, LEG, SUP, SCH = ("ia-census-tiger-2025-cousub", "ia-census-tiger-2025-place", "ia-sos-lsa-precincts-2022", "ia-lsa-legislative-districts",
                                          "ia-lsa-supervisor-districts-2024", "ia-doe-school-districts-2026-27")
    counties_of = collections.defaultdict(list)
    for c in sorted(jud, key=lambda c: cname[c]):
        counties_of[jud[c]].append(cname[c])
    layer("state", *one(carcs, csides, [STATE] * len(cous), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": "Iowa", "j": FIPS, "d": None}, CENSUS)
    layer("county", *one(carcs, csides, ccounty, G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, CENSUS)
    layer("cd", *one(cdarcs, cdsides, ckeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, LEG)
    layer("senate", *one(sarcs, ssides, skeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, LEG)
    layer("house", *one(harcs, hsides, hkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v, "senate": str((int(v) + 1) // 2)}, LEG)
    layer("judicial", *one(carcs, csides, [jud[c] for c in ccounty], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Judicial Election District {v[2:]}", "j": v, "d": v[2:], "counties": counties_of[v]}, CENSUS)
    layer("mcd", *W.merged_layer([(parcs, psides, city_key), (carcs, csides, town_val)], TOL_MCD), TOL_MCD,
          lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": "city" if v in city_set else "township"}, CENSUS + " and " + PLACES, zoom=MCD_ZOOM)
    layer("com", *one(suarcs, susides, skeys_, G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Supervisor District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, SUP)
    swprops = lambda v: dict({"id": v, "name": swname[v], "j": FIPS + v[6:9], "d": None}, **({"jn": swname[v]} if v[6:9] == POTT[2:] else {}))   # noqa: E731
    layer("swcd", *W.merged_layer([(carcs, csides, [swcd_of.get(c) for c in ccounty]), (warcs, wsides, wkeys)], G.TOL_WIDE), G.TOL_WIDE, swprops,
          CENSUS + "; Pottawattamie's two from ia-lsa-soil-water-2016")
    if hosp_of:
        layer("hospital", *one(carcs, csides, [hosp_of.get(c) for c in ccounty], G.TOL_WIDE), G.TOL_WIDE,
              lambda v: {"id": v, "name": names.get(("hospital", v)) or "County public hospital", "j": v, "d": None}, CENSUS)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None}      # noqa: E731
    layer("school", *one(scharcs, schsides, schkeys, G.TOL_LOCAL), G.TOL_LOCAL, sprops, SCH)
    dgeoms, dq = one(scharcs, schsides, schkeys, G.TOL_SCHOOL)
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
    counties, boxes, dropped_rings = [], {}, 0
    for county, idxs in sorted(by_county.items()):
        local = {i: n for n, i in enumerate(idxs)}
        geoms, used_names = [], {"mcd": {}, "com": {}, "school": {}, "swcd": {}, "hospital": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "mcd": p["mcd"], "house": p["house"], "senate": p["senate"], "cd": p["cd"],
                  "judicial": p["jud_id"], "swcd": p["swcd"], "school": p["school"]}
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            used_names["swcd"][p["swcd"]] = swname[p["swcd"]]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["com"]:
                pr["com"] = p["com"]
                used_names["com"][p["com"]] = f"Supervisor District {p['com'].split('|')[1]}"
            if p["hospital"]:
                pr["hospital"] = p["hospital"]
                used_names["hospital"][p["hospital"]] = names.get(("hospital", p["hospital"])) or "County public hospital"
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
                    asd.append(local[side] if side in local else (-1 if side >= 0 or a in seam else -2))
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
        entry = {"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)}
        counties.append(entry)

    polls = polling_places(pre, put, say, refresh, polls_dir)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids, plans, town_county)
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    lsa, both = "Iowa Legislative Services Agency", "Iowa Secretary of State and Iowa Legislative Services Agency"
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": PCT, "agency": both, "title": "State of Iowa Precinct Boundaries (as of the 2022 reprecincting)",
                  "about": "Every precinct of the 99 counties, with its county, official name and number.",
                  "url": PCT_ITEM, "service": PCT_SERVICE, "fetched": pdoc.get("fetched"), "sha256": G.sha_file(ppath),
                  "rows": len(pre)}, **edited["precincts"]),
            dict({"id": LEG, "agency": lsa, "title": "Iowa Legislative Districts: Iowa House, Iowa Senate and U.S. House districts (the 2021 plan)",
                  "url": LEG_ITEM, "service": LEG_SERVICE.rstrip("/"), "fetched": hdoc.get("fetched"),
                  "sha256": {"house": G.sha_file(hpath), "senate": G.sha_file(spath), "congress": G.sha_file(cpath)}, "rows": 154}, **edited["house"]),
            dict({"id": SUP, "agency": both, "title": "County Supervisor Districts (as of January 11, 2024)",
                  "about": "Each county's plan under Iowa Code 331.206 and the districts of Plan Two and Plan Three counties. Only Plan Three districts "
                           "(each district's voters elect its own supervisor) are shapes here.",
                  "url": SUP_ITEM, "service": SUP_SERVICE, "fetched": supdoc.get("fetched"), "sha256": G.sha_file(suppath),
                  "rows": len(supdoc["rows"])}, **edited["supervisor"]),
            dict({"id": SCH, "agency": "Iowa Department of Education", "title": "Current Iowa School Districts (2026-2027)",
                  "url": SCHOOL_ITEM, "service": SCHOOL_SERVICE, "fetched": scdoc.get("fetched"), "sha256": G.sha_file(scpath), "rows": len(schkeys)}, **edited["school"]),
            {"id": CENSUS, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025, county subdivisions, Iowa (tl_2025_19_cousub.zip)",
             "about": "County lines, the state's outline and the townships.", "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": PLACES, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025, places, Iowa (tl_2025_19_place.zip)",
             "about": "City limits (incorporated cities only), as the Bureau had them on January 1, 2025.", "url": PLACE_URL, "fetched": mtime(plpath),
             "sha256": G.sha_file(plpath), "rows": len(cities_)},
            {"id": "ia-lsa-judicial-districts", "agency": lsa, "title": "Judicial Districts: judicial election districts (Iowa Code 602.6109)",
             "about": "Read only for which counties make up each of the fourteen judicial election districts; the lines drawn are the Census Bureau's county lines.",
             "url": JUD_ITEM, "service": JUD_SERVICE, "fetched": jdoc.get("fetched"), "sha256": G.sha_file(jpath), "rows": 14},
            {"id": "ia-lsa-soil-water-2016", "agency": lsa, "title": "Iowa Soil and Water Conservation Districts (2016)",
             "about": "Used only for the line between Pottawattamie County's East and West districts; every other district is its county.",
             "url": SWCD_ITEM, "service": SWCD_SERVICE, "fetched": swdoc.get("fetched"), "sha256": G.sha_file(swpath), "rows": 2}],
        "notes": {
            "lines": f"Every precinct line is the state layer's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 degree (about a "
                     "metre). A point within a few metres of a line can fall on either side of it.",
            "districts": "Which Iowa House, Iowa Senate and congressional district, and in a Plan Three county which supervisor district, a precinct lies in "
                         "is worked out here by laying the district lines over the precinct (analysis, not an official list): the district holding most "
                         f"of the precinct's area. The few precincts with {SPLIT_SHARE:.0%} or more of their area in a second district are listed under check.",
            "places": "A precinct in Iowa is often several townships together, or a small city and the township around it, so a precinct does not say "
                      "which township or city a voter lives in. The mcd layer has both kinds of place, cities first: a point is in the city whose limits "
                      "hold it, and otherwise in its township. A township's shape is the whole township, cities included, but under Iowa Code 39.22 a "
                      "township's trustees and clerk are elected only by the voters who live outside the limits of any city. A precinct's mcd is the "
                      "place holding most of its area (a township counted without its cities) and mcd_all lists every place it reaches: to say which "
                      "place a point is in, ask the mcd layer, not the precinct. City limits are the Census Bureau's of January 1, 2025.",
            "supervisors": "Under Iowa Code 331.206 a county elects its supervisors at large (Plan One), at large with one from each district of residence "
                           "(Plan Two), or each from a district by that district's voters alone (Plan Three). Only Plan Three districts are voting areas, "
                           "so only they are shapes; supervisor_plans gives every county's plan as the state's layer had it on January 11, 2024. Counties "
                           "that changed plan or redrew districts after that date are not in any statewide file.",
            "school": "School district lines are the Department of Education's. Which districts a precinct lies in is analysis, not an official list: a "
                      f"district counts when its part of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's "
                      "share of the precinct's area (land and water, not voters). No school office is on the November 2026 ballot (Iowa's school "
                      "elections are in November of odd years).",
            "soil_water": "A soil and water conservation district is its county, except Pottawattamie County's two (East and West).",
            "authority": "For which precinct an address votes in, and where, the county auditor and the Iowa Secretary of State's polling place finder are the authority.",
            "precinct_ids": "A precinct's id is 19, the county's three-digit code and the three-digit precinct number the state's layer gives it (19153144).",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file, or one just across a hairline gap in the state's drawing; -2: outside Iowa); names gives the names of the "
                            "places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards (south of 43 north they are negative). A point is tried against every precinct "
                     "whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name (144 Sheldahl 1), as the state's layer writes it",
                                    "county": "county id", "mcd": "city or township holding most of the precinct's area",
                                    "mcd_all": "list, when the precinct reaches more than one: every city and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                                    "com": "county supervisor district (only in a county whose supervisors are each elected by their own district's voters)",
                                    "house": "Iowa House district", "senate": "Iowa Senate district", "cd": "congressional district",
                                    "judicial": "judicial election district", "swcd": "soil and water conservation district",
                                    "hospital": "county public hospital (only in a county whose hospital trustees are on the ballot database)",
                                    "split": "only where a second district holds 3 percent or more of the precinct: for house, senate, cd, com or swcd, each district's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "IA (j is 19)", "county": "the county's five-digit code (19153)",
                    "mcd": "IA-M- and the Census code: a township's county subdivision code (IA-M-91707), a city's place code (IA-M-21000); properties.t says which",
                    "com": "<county>|<supervisor district> (19153|4)", "house": "the district (33)", "senate": "the district (17)",
                    "cd": "the district (3); properties.race is the race for Congress", "judicial": "JD and the judicial election district (JD5C)",
                    "swcd": "IA-SW- and the county's three digits (IA-SW-153; IA-SW-155E and IA-SW-155W in Pottawattamie County, with properties.jn)",
                    "hospital": "the ballot database's id (IA-H-153-county-public-hospital)",
                    "school": "IA-S- and the Department's four-digit district number (IA-S-1737)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "counties": len(counties), "rows_put_right": fips_fixed,
                   "split_between_school_districts": split, "in_more_than_one_city_or_township": several,
                   "rings_too_small_for_the_grid": dropped_rings, "split_between_house_districts": len(split_h),
                   "split_between_senate_districts": len(split_s), "split_between_congressional_districts": len(split_c),
                   "split_between_supervisor_districts": len(split_com), "lines_with_a_precinct_on_one_side": lone, "with_a_precinct_across": len(seam),
                   "sliver_rings_left_out": slivers, "points_given_up_where_two_precincts_overlapped": dict(gave),
                   "area_against_census_counties_percent": {"state": round(state_pct, 3), "furthest_county": worst, "its_difference": round(worst_pct, 2)}},
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Iowa races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Iowa ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the place at the point (from the mcd layer), and a
    # word its school district's name must carry. What each point lies in is the Census Bureau's geocoder's answer for
    # those coordinates (county, county subdivision, incorporated place, 120th Congress district, 2026 legislative
    # districts; asked 2026-10-02), an answer that owes nothing to the files tested here. The judicial election
    # district is the county's, by Iowa Code 602.6109.
    ("the State Capitol, Des Moines", -93.6037, 41.5911,
     {"county": "19153", "cd": "3", "senate": "17", "house": "33", "judicial": "JD5C", "swcd": "IA-SW-153"}, "IA-M-21000", "Des Moines"),
    ("Cedar Rapids City Hall", -91.6690, 41.9767,
     {"county": "19113", "cd": "2", "senate": "39", "house": "78", "judicial": "JD6", "swcd": "IA-SW-113"}, "IA-M-12000", "Cedar Rapids"),
    ("the Old Capitol, Iowa City", -91.5357, 41.6613,
     {"county": "19103", "cd": "1", "senate": "45", "house": "90", "judicial": "JD6", "swcd": "IA-SW-103"}, "IA-M-38595", "Iowa City"),
    ("downtown Sioux City", -96.4046, 42.4960,
     {"county": "19193", "cd": "4", "senate": "1", "house": "2", "judicial": "JD3B", "swcd": "IA-SW-193"}, "IA-M-73335", "Sioux City"),
    ("downtown Council Bluffs", -95.8500, 41.2610,
     {"county": "19155", "cd": "4", "senate": "10", "house": "20", "judicial": "JD4", "swcd": "IA-SW-155W"}, "IA-M-16860", "Council Bluffs"),
    ("downtown Dubuque", -90.6665, 42.5006,
     {"county": "19061", "cd": "2", "senate": "36", "house": "71", "judicial": "JD1A", "swcd": "IA-SW-061"}, "IA-M-22395", "Dubuque"),
    ("the courthouse square, Newton (Jasper County, written 99 in the state's layer)", -93.0480, 41.6990,
     {"county": "19099", "cd": "1", "senate": "19", "house": "38", "judicial": "JD5A", "swcd": "IA-SW-099"}, "IA-M-56505", "Newton"),
    ("Corydon, Wayne County (rows filed under Polk County's code in the state's layer)", -93.3180, 40.7570,
     {"county": "19185", "cd": "3", "senate": "12", "house": "24", "judicial": "JD5B", "swcd": "IA-SW-185"}, "IA-M-16635", "Wayne"),
    ("a farm field in Grant Township, Tama County", -92.63, 42.24,
     {"county": "19171", "cd": "2", "senate": "27", "house": "53", "judicial": "JD6", "swcd": "IA-SW-171"}, "IA-M-91707", "Gladbrook"),
    ("a farm field in Lincoln Township, Tama County (the same precinct, the next township)", -92.75, 42.24,
     {"county": "19171", "cd": "2", "senate": "27", "house": "53", "judicial": "JD6", "swcd": "IA-SW-171"}, "IA-M-92619", "Gladbrook"),
]
LINE_POINTS = [("the Polk-Story county line north of Ankeny", -93.60, 41.8634, ("19153", "19169")),
               ("the Polk-Jasper county line east of Mitchellville", -93.3284, 41.68, ("19153", "19099"))]
LAYER_SLACK = 0.005               # the layers come from other files than the precincts: this share of points may disagree


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
                    continue                               # the precinct across the line is in another county's file
                bad_mask += bool(masks[a] & (1 << bit)) != want
    check(total == index["counts"]["precincts"] == len(ids), "the county files do not hold as many precincts as the index says, each with its own id")
    shapes_seen = 0
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == 99, "there are not 99 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; that point's school district is one the precinct names;
    #    the place at that point is one the precinct names; and the layers agree with the precinct, away from their lines
    wrong, tested, agree, skipped = 0, 0, 0, 0
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place = collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com", "swcd": "swcd", "hospital": "hospital"}
    have = {l["kind"] for l in index["layers"]}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    split_ids = {s["id"] for s in index["check"].get("split_precincts", [])}
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
            sid = G.school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in pr["school"] else "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            place["the precinct's largest place" if shape and shape["id"] == pr["mcd"] else "another place the precinct names" if shape and shape["id"] in pr.get("mcd_all", [])
                  else "a place the precinct does not name" if shape else "no place"] += 1
            if g["id"] not in split_ids:
                for prop, kind in layer_for.items():
                    if kind not in have or (i % 3 and kind not in ("com", "hospital")):
                        continue
                    shape, edge = G.shape_at(files, kind, lon, lat)
                    if shape is None and pr.get(prop) is None:
                        continue
                    if shape is not None and edge <= tol_of[kind] + 10:
                        skipped += 1
                        continue
                    asked[kind] += 1
                    if shape is not None and shape["id"] == pr.get(prop):
                        agree += 1
                    else:
                        disagree[kind].append((g["id"], shape and shape["id"], pr.get(prop)))
    check(wrong <= 3, f"{wrong} of {tested} precincts are not found again from a point inside them")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.002 * tested, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["no place"] == 0 and place["a place the precinct does not name"] <= 0.01 * tested,
          f"the place at a precinct's own point: {dict(place)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each precinct's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city or township at each precinct's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

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
        sn = fdoc["names"]["school"].get(sid, "") if sid else ""
        ok &= check(sid is not None and sid in pr["school"] and school_word in sn, f"{name}: the school district at the point is {sid} ({sn}), which should name {school_word!r}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check(shape is not None and shape["id"] == mcd and mcd in ([pr["mcd"]] + pr.get("mcd_all", [])),
                    f"{name}: the mcd layer gives {shape and shape['id']} and the precinct names {[pr['mcd']] + pr.get('mcd_all', [])}; the place is {mcd}")
        for prop, kind in layer_for.items():
            if kind in have and (pr.get(prop) is not None or kind in want):
                shape2, _edge = G.shape_at(files, kind, lon, lat)
                ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {pr.get(prop)}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: precinct {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, {pr['judicial']}, {sn}"
            + (f", supervisor district {pr['com'].split('|')[1]}" if pr.get("com") else "") + f"; {found['edge']:.0f} m from the precinct's line")

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
            other = [h for h in n2 if h["county"] != f2["county"]]
            say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: the spot on the line ({on[0]:.5f}, {on[1]:.5f}) is given to "
                f"{f2['geometry']['properties']['name']} with {', '.join(sorted(h['geometry']['properties']['name'] for h in n2))} at hand"
                + (f"; the other county's line runs {min(h['edge'] for h in other):.1f} m away" if other else ""))

    # 5. polling places say what they are
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values()),
              "polling_places.json names a precinct or a place that is not there")
    say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Iowa's ballot map -> ballot_geo/ia/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/ia)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--polls", default=None, help="folder to look for a saved polling place list in (default: states_cache/ia_local/sos/pollingplaces)")
    ap.add_argument("--refresh", action="store_true", help="ask the map services again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh, polls_dir=a.polls)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
