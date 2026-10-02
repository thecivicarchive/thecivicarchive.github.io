"""
ballot/nd_geo.py - the geography behind North Dakota's ballot map, in the same files and formats ballot/mn_geo.py
writes for Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and
ballot/wi_geo.py and ballot/ia_geo.py for the few things Wisconsin and Iowa added, and changes nothing in any of them),
so the same page and the same reader (ballot/mn_geo_reader.js) read all four.

    python ballot/nd_geo.py                 builds ballot_geo/nd/ and runs the self-test (about two minutes the first
                                            time, most of it laying townships and school districts over precincts)
    python ballot/nd_geo.py --selftest      runs the self-test on the files already built
    python ballot/nd_geo.py --refresh       asks the map services and the Secretary's page again
    python ballot/nd_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/nd_local/)
----------------------------------------------------------------------------------------------------------------------
  - Precinct parts: "NDGISHUB Voter Precincts" (North Dakota Secretary of State, Elections; published on the state's
    GIS Hub, gishubdata-ndgov.hub.arcgis.com): "voter precinct splits for the 2026 election", 912 parts of 359
    precincts, each with its county, legislative district, city, ward, county commissioner district, soil conservation
    district, judicial district, park district, school district, and whether it lies in the Garrison Diversion
    Conservancy District, the Southwest Water Authority, an ambulance or fire district, a vector control district or a
    library district. Every column is a district; the layer has no column about a person.
    One county's rows carry a mistyped county code (Morton: 30859 for 38059): a part's county is taken from the first
    two digits of its precinct number (the county's number in the alphabet), checked against the county's name, and the
    area check (each county's parts against the Census Bureau's county) stops the build if they are not where the
    county is. Five small parts are numbered 9999.01 in the table; here each is its precinct's number followed by 99.
  - House subdistricts: the Legislative Council's "NDGISHUB Legislative Districts" (the 47 districts as revised under
    the federal court's order of January 8, 2024; district 4 is drawn as 4A and 4B). Only the district number is asked
    for. It is laid over the precinct parts to tell 4A from 4B, and to check the table's district numbers.
  - School districts: the Department of Public Instruction's "NDGISHUB School Districts". Only the district's name
    and number are asked for.
  - Cities, townships and unorganized territories: the Census Bureau's TIGER/Line 2025 county subdivisions of North
    Dakota (tl_2025_38_cousub.zip). In North Dakota a city is a county subdivision of its own, outside every township.
  - Polling places: the Secretary of State's "Election Administration Information" page for the November 3, 2026
    general election (vip.sos.nd.gov/Precincts.aspx?eid=348), its "Statewide Polling Places" table, asked for whole
    through the table's own page-size command. Read by heading: county number, legislative district, precinct number,
    polling location, address, city, zip code, polling hours. The county auditor's phone column is never read.

What North Dakota calls things, and what that does to the files
---------------------------------------------------------------
The smallest area the Secretary publishes is a precinct part (a precinct cut wherever a city, ward, school, park or
other district line crosses it), so a shape here is a part and everything the table says of it is exact for it. The
page calls it a precinct; its name gives the precinct number and the part. A rural part is often several townships
together, so (as in Iowa) the township at a point is asked of the mcd layer, not of the part; a part inside a city
says so itself.

County commissioners (index.json, "supervisor_plans", in the words the page builder reads): plan 1, elected at large;
plan 2, the table lists every district on every part of the county, so each commissioner stands for a district and the
whole county votes; plan 3, each part names one district, whose voters alone elect its commissioner. Only plan 3
districts are shapes.

What is built (ballot_geo/nd/): index.json, manifest.json, precincts/<county>.json (53), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, ward, com, swcd, park, school), school/<id>.json, polling_places.json and
reader.js, each as ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "ND" (j = "38", the jurisdiction_id of statewide races)
  county    "38015"                 sl_places county id; jurisdiction_id of county offices
  mcd       "ND-M-07200"            ND-M- and the Census county subdivision code (a city's is its place code)
  ward      "ND-M-32060|Ward 5"     <city>|<ward> (no city office is on the November 2026 ballot)
  com       "38003|District 2"      <county>|<district as the commissioner race words it>, plan 3 counties only
  house     "41", "4A"   senate "41"   cd "0" (properties.race is 2026-ND-H00)
  judicial  "ND-SC"                 sl_places judicial_district id (d = "South Central")
  swcd      "ND-X-015-burleigh-county-soil-conservation-district"   sl_places special id; j the same, d null
  park      "ND-P-017-fargo"        ND-P-, the county's three digits and the park district's name
  school    "ND-S-08001"            ND-S- and the Department's five-digit district number

Not drawn: the Garrison Diversion Conservancy District's director districts (each is a county; the page's rule places
no shape for that kind of office, and a part says whether it lies in the district), ambulance, fire, vector control,
library and Southwest Water Authority districts (named on each part, no layer). index.json lists every race without a
shape under "check".
"""

import argparse
import collections
import datetime as dt
import hashlib
import html
import io
import csv
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
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741

GeoError = G.GeoError
STATE, FIPS = "ND", "38"
OUT = os.path.join(HERE, "ballot_geo", "nd")
CACHE = os.path.join(HERE, "states_cache", "nd_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://vip.sos.nd.gov/wheretovote.aspx"

HUB_GIS = "https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/"      # the State of North Dakota's GIS Hub
HUB = "https://gishubdata-ndgov.hub.arcgis.com/datasets/"
PCT_SERVICE = HUB_GIS + "NDGISHUB_Voter_Precincts/FeatureServer/0"
PCT_ITEM = HUB + "5274182ee81142f99784f90287d64a21"
PCT_FIELDS = ("PPartName,PPartID,CountyID,Precinct,CountyName,CityDistrict,Commissioner1,Commissioner2,Commissioner3,Commissioner4,Commissioner5,"
              "ConservationDistrict,GarrisonDiversion,Judicial,Legislative,Park,School,SW_WaterAuthority,Ward,EmergencyServices,Vector,Library,"
              "SW_WaterAuthorityCity,Ward2,Ward3")
LEG_SERVICE = HUB_GIS + "NDGISHUB_Legislative_Districts/FeatureServer/0"
LEG_ITEM = HUB + "037645e2310f4ce58116a4ae1b0183ed"
SCHOOL_SERVICE = HUB_GIS + "NDGISHUB_School_Districts/FeatureServer/0"
SCHOOL_ITEM = HUB + "92f18ca07aaf457f86d74ed33d2fe67f"
SCHOOL_FIELDS = "DistrictName,DistrictID"
COUSUB_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_38_cousub.zip"
POLL_URL = "https://vip.sos.nd.gov/Precincts.aspx?eid=348"
POLL_GRID = "ctl00$ContentPlaceHolder1$rgStatewidePollingPlaces"
POLL_HEADS = {"county": "County", "cc": "County Number", "ld": "Legislative District", "pp": "Precinct Number", "name": "Polling Location",
              "address": "Address", "city": "City", "zip": "Zip Code", "hours": "Polling Hours"}      # never "County Auditor Phone"
POLL_LAYOUT_CHECKED = False       # True only when a person has compared a dozen precincts of polling_places.json with the Secretary's page

JUD = {"East Central": "EC", "North Central": "NC", "Northeast": "NE", "Northeast Central": "NEC", "Northwest": "NW", "South Central": "SC",
       "Southeast": "SE", "Southwest": "SW"}
ARC_KINDS = ["county", "ward", "com", "house", "senate", "cd", "judicial", "swcd", "park"]      # not mcd: rural parts do not follow township lines
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM, MCD_THICK = I.TOL_MCD, I.MCD_ZOOM, I.MCD_THICK
NEAR_M = G.NEAR_M
AREA_SLACK = 0.05                 # a county's parts and the Census Bureau's county may differ in area by this share (the parts leave out some
                                  # open water: Benson County's are 4.1 percent smaller, Ramsey County's 2.2, around Devils Lake)
LSAD_WORD = {"25": "city", "44": "township", "46": "unorganized territory"}


def clean(v):
    return re.sub(r"\s+", " ", G.blank(v)).strip()


def city_fold(t):
    """A city's name for matching the table's spelling to the Census Bureau's (St John / St. John, Reiles Acres / Reile's Acres)."""
    return re.sub(r"^city of ", "", re.sub(r"[^a-z0-9 ]", "", clean(t).lower()))


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


# ---------------------------------------------------------------- the precinct table

def soil_name(v):
    n = clean(v).replace("Soil Conservation County", "Soil Conservation District")
    return n if "Soil Conservation" in n else re.sub(r" District$", " Soil Conservation District", n)


def park_name(v):
    return re.sub(r"\s+Park(\s+(Board|District))?$", "", clean(v)) + " Park District"


def read_parts(doc):
    """The precinct parts, in id order, each with what the table says of it, and their rings as vertex keys."""
    pre, polys, seen, fixed = [], [], set(), collections.Counter()
    cnames, plans = {}, collections.defaultdict(set)
    for a, rings in doc["rows"]:
        pct, part = clean(a["Precinct"]), clean(a["PPartID"]).replace(".", "")
        if re.fullmatch(r"\d{8}", part) and not part.startswith("9999") and pct != part[:6]:
            pct = part[:6]                                    # a precinct number typed a digit short; the part's own number carries it whole
            fixed["precinct number taken from the part's"] += 1
        ld = re.fullmatch(r"District (\d\d)", clean(a["Legislative"]))
        if not (re.fullmatch(r"\d{6}", pct) and 1 <= int(pct[:2]) <= 53 and ld and ld.group(1) == pct[2:4] and clean(a["CountyName"])
                and clean(a["Judicial"]) in JUD and clean(a["ConservationDistrict"])):
            raise GeoError(f"    precinct table: the row for part {part!r} of precinct {pct!r} does not fit the layout this builder was checked against; stopping")
        county = f"{FIPS}{2 * int(pct[:2]) - 1:03d}"
        if str(a["CountyID"]) != county:
            fixed[county] += 1
        if cnames.setdefault(county, clean(a["CountyName"])) != clean(a["CountyName"]):
            raise GeoError(f"    precinct table: county {county} is given two names; stopping")
        if re.fullmatch(r"\d{8}", part) and part.startswith(pct):
            pid, no = part, part[6:]
        elif part.startswith("9999"):
            pid, no = pct + "99", "99"
            fixed["numbered 9999.01"] += 1
        else:
            raise GeoError(f"    precinct table: part {part!r} is not its precinct's number ({pct}) and two digits; stopping")
        if pid in seen:
            raise GeoError(f"    precinct table: two rows are part {pid}; stopping")
        seen.add(pid)
        com = [clean(a[f"Commissioner{i}"]) for i in range(1, 6) if clean(a[f"Commissioner{i}"])]
        if not com or not all(c == "Districts At-Large" or re.fullmatch(r"District [1-5]", c) for c in com):
            raise GeoError(f"    precinct table: part {pid} names commissioner districts in words this builder was not checked against; stopping")
        plan = 1 if com[0] == "Districts At-Large" else 3 if len(com) == 1 else 2
        plans[county].add((plan, tuple(com) if plan == 2 else ()))
        wards = []
        for k in ("Ward", "Ward2", "Ward3"):
            if clean(a[k]):
                m = re.search(r"Ward (\d+)$", clean(a[k]))
                if not m or not clean(a["CityDistrict"]):
                    raise GeoError(f"    precinct table: part {pid} names a ward ({clean(a[k])!r}) this builder cannot read, or one outside a city; stopping")
                wards.append(f"Ward {m.group(1)}")
        pre.append({"id": pid, "county": county, "countyname": clean(a["CountyName"]), "precinct": pct, "part": no,
                    "city": clean(a["CityDistrict"]), "wardwords": wards, "plan": plan, "comd": com[0] if plan == 3 else None, "comlist": com,
                    "ld": str(int(pct[2:4])), "jud": "ND-" + JUD[clean(a["Judicial"])], "soil": soil_name(a["ConservationDistrict"]),
                    "parkname": park_name(a["Park"]) if clean(a["Park"]) else "", "schoolsaid": clean(a["School"]),
                    "garrison": bool(clean(a["GarrisonDiversion"])), "sww": bool(clean(a["SW_WaterAuthority"])),
                    "ems": clean(a["EmergencyServices"]) if clean(a["EmergencyServices"]) not in ("", "None") else "",
                    "vector": bool(clean(a["Vector"])), "library": clean(a["Library"])})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    order = sorted(range(len(pre)), key=lambda i: pre[i]["id"])
    pre, polys = [pre[i] for i in order], [polys[i] for i in order]
    if len(cnames) != 53:
        raise GeoError(f"    precinct table: {len(cnames)} counties, not 53; stopping")
    mixed = [c for c, v in plans.items() if len(v) > 1]
    if mixed:
        raise GeoError(f"    precinct table: the parts of county {mixed[0]} do not agree on how its commissioners are elected; stopping")
    n_parts = collections.Counter(p["precinct"] for p in pre)
    for p in pre:
        p["name"] = f"Precinct {p['precinct']}" + (f", part {p['part']}" if n_parts[p["precinct"]] > 1 else "")
    return pre, polys, dict(fixed), cnames


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'nd-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"nd_geo_overlay_{name}.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say(f"      laying the {name} lines over the precinct parts (kept for the next build)")
    res = G.school_overlay(pre_rings, districts, levels=(G.SCHOOL_THICK,), say=None)
    rows = [[[d, round(share, 5), thick[0]] for d, share, thick in row] for row in res]
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def merge_rows(rows, key):
    """Rows of one layer that share an id (a district drawn in two pieces) become one row."""
    by = collections.OrderedDict()
    for a, rings in rows:
        k = key(a)
        if k in by:
            by[k][1].extend(rings)
        else:
            by[k] = [a, list(rings)]
    return [(a, rings) for a, rings in by.values()]


# ---------------------------------------------------------------- one line between two neighbours

KNIT_M = 3.0                      # metres: two parts' drawings of one line this close together are made the same line
KX, KY = G.M_PER_UNIT * math.cos(math.radians(47.5)), G.M_PER_UNIT      # metres in 1e-7 degree, east and north, in the middle of the state


def _tidy(ks):
    out = []
    for k in ks:
        if out and out[-1] == k:
            continue
        if len(out) >= 2 and out[-2] == k:
            out.pop()
            continue
        out.append(k)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    while len(out) >= 3:
        if out[-1] == out[1]:
            out = out[2:]
        elif out[-2] == out[0]:
            out = out[1:-1]
        else:
            break
    return out if len(out) >= 3 else None


def knit(polys, eps_m=KNIT_M, passes=3):
    """The Secretary's parts were drawn county by county and part by part: a line two neighbours share is often drawn
    twice, a metre or two apart, or with a corner on one side that the other side runs straight past. Here corners
    within eps_m of one another become one corner, and a corner within eps_m of a neighbour's straight run becomes a
    corner of that run too, so that most shared lines are one line again (no point moves more than about eps_m).
    Lines drawn further apart than that stay two lines. Returns (corners moved, corners added)."""
    moved = added = 0
    canon, grid = {}, collections.defaultdict(list)
    for k in sorted({k for rings in polys for ks in rings for k in ks}):
        x, y = G.vxy(k)
        mx, my = x * KX, y * KY
        cx, cy = int(mx // eps_m), int(my // eps_m)
        best, who = eps_m * eps_m, None
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for ox, oy, ok in grid.get((gx, gy), ()):
                    d = (ox - mx) ** 2 + (oy - my) ** 2
                    if d <= best:
                        best, who = d, ok
        if who is None:
            grid[(cx, cy)].append((mx, my, k))
            canon[k] = k
        else:
            canon[k] = who
            moved += 1
    for rings in polys:
        rings[:] = [t for t in (_tidy([canon[k] for k in ks]) for ks in rings) if t]
    C = 30.0
    for _ in range(passes):
        vgrid = collections.defaultdict(list)
        for k in {k for rings in polys for ks in rings for k in ks}:
            x, y = G.vxy(k)
            vgrid[(int(x * KX // C), int(y * KY // C))].append((x * KX, y * KY, k))
        cache = {}

        def between(a, b):
            if (a, b) in cache:
                return cache[(a, b)]
            if (b, a) in cache:
                return cache[(b, a)][::-1]
            (ax, ay), (bx, by) = G.vxy(a), G.vxy(b)
            ax, ay, bx, by = ax * KX, ay * KY, bx * KX, by * KY
            dx, dy = bx - ax, by - ay
            dd = dx * dx + dy * dy
            cells, steps = set(), int(math.sqrt(dd) // (C / 2)) + 1
            for n in range(steps + 1):
                cx, cy = int((ax + n / steps * dx) // C), int((ay + n / steps * dy) // C)
                cells.update((gx, gy) for gx in (cx - 1, cx, cx + 1) for gy in (cy - 1, cy, cy + 1))
            found = set()
            for c in cells:
                for vx, vy, k in vgrid.get(c, ()):
                    if k == a or k == b:
                        continue
                    t = ((vx - ax) * dx + (vy - ay) * dy) / dd
                    if 0 < t < 1 and (vx - ax - t * dx) ** 2 + (vy - ay - t * dy) ** 2 <= eps_m * eps_m:
                        found.add((t, k))
            cache[(a, b)] = [k for _t, k in sorted(found)]
            return cache[(a, b)]

        n_added = 0
        for rings in polys:
            new = []
            for ks in rings:
                out, a = [], ks[-1]
                for b in ks:
                    ins = between(a, b)
                    n_added += len(ins)
                    out.extend(ins)
                    out.append(b)
                    a = b
                t = _tidy(out)
                if t:
                    new.append(t)
            rings[:] = new
        added += n_added
        if not n_added:
            break
    return moved, added


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, plans):
    """Every North Dakota race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape). A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, _county_ids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "district_court":
            hit = ("judicial", jid)
        elif kind == "county_commissioner":
            plan = plans.get(jid) or {}
            whole = not d or (f"{jid}|{d}" not in S.get("com", {}) and plan.get("plan") == 2 and d in (plan.get("districts") or []))
            hit = ("county", jid) if whole else ("com", f"{jid}|{d}")
            if not whole and hit[1] not in S.get("com", {}):
                why = (f"the Secretary of State's precinct table lists {', '.join(plan.get('districts') or []) or 'no commissioner districts'} for this county "
                       f"({'elected at large' if plan.get('plan') == 1 else 'every part of the county votes on each' if plan.get('plan') == 2 else 'each elected by its own district'}), not {d}")
        elif level == "county":
            hit = ("county", jid)
        elif level == "soil_water":
            own = sorted(i for i, p in S.get("swcd", {}).items() if p.get("j") == jid)
            whole = [i for i in own if S["swcd"][i].get("d") is None]
            hit = ("swcd", whole[0]) if len(whole) == 1 else None
            why = None if hit else "the precinct table names no soil conservation district that carries this id"
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
        elif level == "school":
            hit = ("school", jid)
        elif level == "other" and jid in S.get("county", {}):
            hit = ("county", jid)
        elif kind == "water_board":
            why = ("a director of the Garrison Diversion Conservancy District is elected by one county's voters; the page's rule places no shape for this kind "
                   "of office, so the race is listed for the county and the map says nothing about it (each precinct part says whether it lies in the district)")
        else:
            why = "no source carries a boundary for this kind of district"
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


# ---------------------------------------------------------------- polling places (the Secretary of State's own page)

POLL_WAITING = {
    "why": "The North Dakota Secretary of State's list of polling places for November 3, 2026 could not be read when these files were built. "
           "The Secretary's \"Where do I vote\" page answers for one address at a time and, with the county auditor, is the authority.",
}
POLL_UNCHECKED_WHY = ("      polling places: read from the Secretary's page and marked 'unchecked', so a page does not show them yet. Compare a dozen "
                      "precincts of polling_places.json with vip.sos.nd.gov/Precincts.aspx?eid=348 (Statewide Polling Places), then set "
                      "POLL_LAYOUT_CHECKED = True in ballot/nd_geo.py and build again.")


def fetch_polls(path, refresh, say):
    """The Statewide Polling Places table, whole, cut down on the spot to the columns named in POLL_HEADS (found by
    their headings) and kept as JSON. The page is asked twice: once as it opens, once with the table's own command for
    a page long enough to hold every row."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    try:
        net.patient_lookups()
        first = net.get(POLL_URL, timeout=180)
        page = first.decode("utf-8", "replace")
        if "Statewide Polling Places" not in page and POLL_GRID.replace("$", "_") not in page:
            raise GeoError("    polling places: the Secretary's page no longer has a Statewide Polling Places table")
        if "November 3, 2026" not in page:
            raise GeoError("    polling places: the Secretary's page (election 348) no longer speaks of November 3, 2026")
        fields = {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', page)}
        fields.update({"__EVENTTARGET": POLL_GRID, "__EVENTARGUMENT": f"FireCommand:{POLL_GRID}$ctl00;PageSize;5000"})
        time.sleep(1.0)
        req = Request(POLL_URL, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": POLL_URL})
        with urlopen(req, timeout=300) as r:
            raw = r.read()
        text = raw.decode("utf-8", "replace")
        seg = text[text.find(f'id="{POLL_GRID.replace("$", "_")}_ctl00"'):]
        heads = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r'<th scope="col" class="rgHeader"[^>]*>(.*?)</th>', seg[:seg.find("</thead>")], re.S)]
        col = {k: heads.index(h) for k, h in POLL_HEADS.items() if h in heads}
        if set(col) != set(POLL_HEADS):
            raise GeoError(f"    polling places: the table's headings are now {heads}; the reader needs to be told the layout")
        rows = []
        for tr in re.findall(r'<tr class="rg(?:Alt)?Row"[^>]*>(.*?)</tr>', seg, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            rows.append({k: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cells[i]))).strip() for k, i in col.items()})
        m = re.search(r"(\d+)\s*</strong>\s*items in\s*<strong>\s*(\d+)", seg)
        if not rows or not m or int(m.group(1)) != len(rows) or m.group(2) != "1":
            raise GeoError(f"    polling places: {len(rows):,} rows came, and the table counts {m.group(1) if m else 'none'}; stopping")
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not read the Secretary's polling place page again ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        raise
    out = {"url": POLL_URL, "fetched": dt.date.today().isoformat(), "columns": sorted(POLL_HEADS.values()),
           "sha256_of_the_answer": hashlib.sha256(raw).hexdigest(), "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows of the Statewide Polling Places table")
    return out


def census_geocode(rows, say):
    """mn_geo.census_geocode for North Dakota addresses: [(id, street, city, zip)] -> {id: (lon, lat, matched address)}.
    Polling places are public buildings; nothing else is ever sent."""
    net.patient_lookups()
    buf = io.StringIO()
    w = csv.writer(buf)
    for rid, street, city, zipc in rows:
        w.writerow([rid, street, city, STATE, zipc])
    boundary = "----ndgeo" + uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"places.csv\"\r\n"
            f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n").encode("utf-8")
    req = Request(G.GEOCODER, data=body, headers={"User-Agent": net.UA, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urlopen(req, timeout=900) as r:
        text = r.read().decode("utf-8", "replace")
    out = {}
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) >= 6 and rec[2].strip() == "Match":
            try:
                lon, lat = (float(v) for v in rec[5].split(","))
            except ValueError:
                continue
            out[rec[0].strip()] = (round(lon, 5), round(lat, 5), rec[4].strip())
    say(f"      polling places: {len(rows):,} addresses asked of the Census Bureau's geocoder, {len(out):,} matched")
    return out


def place_points(places, cbox, say):
    """Coordinates from the street address (kept in a small cache). A match outside the place's own county (its box,
    widened a little) is thrown out."""
    cache_path = os.path.join(CACHE, "nd_geo_pollingplace_points.json")
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
        hit, b = kept.get(key(p)), cbox[p.pop("_county")]
        if not hit:
            continue
        if not (b[0] - 0.05 <= hit[0] <= b[2] + 0.05 and b[1] - 0.05 <= hit[1] <= b[3] + 0.05):
            far += 1
            continue
        p["lonlat"], p["from"] = [hit[0], hit[1]], "the Census Bureau's geocoder, from the street address"
        placed += 1
    return placed, far


def polling_places(pre, cname, cbox, put, say, refresh):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    path = os.path.join(CACHE, "sos_statewide_polling_places_348.json")
    try:
        got = fetch_polls(path, refresh, say)
    except Exception as e:  # noqa: BLE001  the map does not depend on this list
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(f"      polling places: waiting; the Secretary's page could not be read ({e})")
        return {"file": "polling_places.json", "status": "waiting"}
    parts_of = collections.defaultdict(list)
    for p in pre:
        parts_of[p["precinct"]].append(p["id"])
    places, order, of_pct, unmatched = {}, [], collections.OrderedDict(), set()
    for r in got["rows"]:
        if not (re.fullmatch(r"\d\d", r["cc"]) and re.fullmatch(r"\d\d", r["ld"]) and re.fullmatch(r"\d\d", r["pp"]) and r["name"]):
            raise GeoError("    polling places: a row's county number, legislative district or precinct number is not two digits; the reader needs to be told the layout")
        pct = r["cc"] + r["ld"] + r["pp"]
        key = (r["name"].lower(), r["address"].lower(), r["city"].lower(), r["zip"][:5])
        if key not in places:
            places[key] = {"name": r["name"], "address": r["address"], "city": r["city"], "zip": r["zip"][:5], "type": None, "hours": r["hours"],
                           "lonlat": None, "precincts": [], "_county": f"{FIPS}{2 * int(r['cc']) - 1:03d}"}
            order.append(key)
        if pct not in parts_of:
            unmatched.add(pct)
            continue
        of_pct.setdefault(pct, [])
        if key not in of_pct[pct]:
            of_pct[pct].append(key)
        for pid in parts_of[pct]:
            if pid not in places[key]["precincts"]:
                places[key]["precincts"].append(pid)
    plist = [places[k] for k in order]
    precinct, several = {}, {}
    for pct, keys in of_pct.items():
        for pid in parts_of[pct]:
            if len(keys) == 1:
                precinct[pid] = order.index(keys[0])
            else:
                names = "; ".join(f"{places[k]['name']} ({places[k]['address']}, {places[k]['city']})" for k in keys)
                several[pid] = (f"is listed with {len(keys)} polling places on the Secretary of State's list ({names}); the Secretary's "
                                "\"Where do I vote\" page or the county auditor says which serve your address")
    placed, far = place_points(plist, cbox, say)
    without = sorted(set(parts_of) - set(of_pct))
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "North Dakota Secretary of State", "title": "Statewide Polling Places, general election of November 3, 2026 (Election Administration Information)",
                       "url": POLL_URL, "saved": got.get("fetched"), "sha256": G.sha_file(path)},
               places=plist, precinct=dict(sorted(precinct.items())), no_place=dict(sorted(several.items())),
               note="A precinct listed with one polling place is in precinct; a precinct listed with several is in no_place, with the places named. "
                    "The list is by precinct, so every part of a precinct carries the precinct's places.")
    put("polling_places.json", doc)
    say(f"      polling places: {len(got['rows']):,} rows, {len(plist):,} places ({placed:,} placed by the Census Bureau's geocoder, {far} matches thrown out as outside "
        f"the county); {len(of_pct):,} of {len(parts_of):,} precincts of the map are on the list ({sum(1 for k in of_pct.values() if len(k) == 1):,} with one "
        f"place, {sum(1 for k in of_pct.values() if len(k) > 1):,} with several); {len(unmatched):,} listed precincts are not on the map"
        + (f" (e.g. {', '.join(sorted(unmatched)[:5])})" if unmatched else "") + f"; {len(without):,} precincts of the map are not listed"
        + (f" (e.g. {', '.join(without[:5])})" if without else ""))
    if not POLL_LAYOUT_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(plist), "with_coordinates": sum(1 for p in plist if p["lonlat"]),
            "rows": len(got["rows"]), "precincts_listed": len(of_pct) + len(unmatched), "listed_and_not_on_the_map": sorted(unmatched),
            "on_the_map_and_not_listed": without, "precincts_with_several_places": sum(1 for k in of_pct.values() if len(k) > 1)}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    North Dakota ballot map: precinct part, district, township, city and school district lines (the state's GIS Hub, the Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    ppath, lpath, scpath, tpath = (path(n) for n in ("sos_voter_precincts_2026_geometry_4326.json.gz", "lc_legislative_districts_geometry_4326.json.gz",
                                                     "dpi_school_districts_geometry_4326.json.gz", "tl_2025_38_cousub.zip"))
    pdoc = W.fetch_full(PCT_SERVICE, PCT_FIELDS, ppath, 200, "OBJECTID", refresh, say)
    ldoc = W.fetch_full(LEG_SERVICE, "DISTRICT", lpath, 10, "OBJECTID", refresh, say)
    scdoc = W.fetch_full(SCHOOL_SERVICE, SCHOOL_FIELDS, scpath, 40, "OBJECTID", refresh, say)
    net.download(COUSUB_URL, tpath, 3650, say=say)
    edited = {k: W.layer_edited(svc, path(f"nd_geo_about_{k}.json"), refresh)
              for k, svc in (("precincts", PCT_SERVICE), ("legislative", LEG_SERVICE), ("school", SCHOOL_SERVICE))}

    # ---- precinct parts: one line between two neighbours, kept once
    pre, polys, fixed, county_short = read_parts(pdoc)
    knit_moved, knit_added = knit(polys)
    if any(not rings for rings in polys):
        raise GeoError("    a precinct part has no ring left after its lines were set together; stopping")
    slivers, gave = W.settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct part has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precinct parts of {len({p['precinct'] for p in pre}):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); "
        f"two drawings of one line within {KNIT_M:.0f} m were made one ({knit_moved:,} corners moved, {knit_added:,} added); "
        f"{lone:,} lines still have a part on one side only, {len(seam):,} of them with another part just across; {slivers} rings under "
        f"{W.SLIVER_M2:.0f} square metres left out, {sum(n for _w, n in gave)} points given up by {len(gave)} parts that ran along a neighbour's line the same way"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's county subdivisions: cities, townships, unorganized territories (one fabric)
    cous = sorted(I.read_shapefile(tpath, lambda r: r["STATEFP"] == FIPS and r["COUSUBFP"] != "00000"), key=lambda x: (x[0]["COUNTYFP"], x[0]["COUSUBFP"]))
    if len({r["COUNTYFP"] for r, _ in cous}) != 53 or any(r["LSAD"] not in LSAD_WORD for r, _ in cous):
        raise GeoError(f"    {os.path.basename(tpath)}: not 53 counties of cities, townships and unorganized territories; stopping")
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    # a township's code can be used again in another county (and a city can lie in two): a code used by two different places is told apart by its county
    code_names = collections.defaultdict(set)
    for r, _ in cous:
        code_names[r["COUSUBFP"]].add(r["NAMELSAD"])
    mkey = [f"{STATE}-M-{r['COUSUBFP']}" if len(code_names[r["COUSUBFP"]]) == 1 else f"{STATE}-M-{r['COUSUBFP']}-{r['COUNTYFP']}" for r, _ in cous]
    census_name = {k: r["NAMELSAD"] for k, (r, _) in zip(mkey, cous)}
    mkind = {k: LSAD_WORD[r["LSAD"]] for k, (r, _) in zip(mkey, cous)}
    city_in = {}
    for k, (r, _) in zip(mkey, cous):
        if r["LSAD"] == "25":
            city_in[(FIPS + r["COUNTYFP"], city_fold(r["NAME"]))] = k

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in county_short.items()}
    title = lambda n: re.sub(r" (city|township)$", lambda m: " " + m.group(1).title(), n)      # noqa: E731
    mname = {k: names.get(("mcd", k)) or (title(n) if mkind[k] != "city" else "City of " + n[:-5]) for k, n in census_name.items()}

    # ---- counties' own shapes from the Census Bureau (for the area check)
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- commissioner plans
    plans = {}
    for p in pre:
        e = plans.setdefault(p["county"], {"plan": p["plan"], "districts": set()})
        e["districts"].update(c for c in p["comlist"] if c != "Districts At-Large")
    for e in plans.values():
        e["districts"] = sorted(e["districts"])
        e["commissioners_elected"] = {1: "at large", 2: "one for each district, by the voters of the whole county", 3: "each by the voters of its own district"}[e["plan"]]

    # ---- soil conservation districts: the ballot database's id where it has the district
    soil_counties = collections.defaultdict(set)
    for p in pre:
        if p["part"] != "99":
            soil_counties[p["soil"]].add(p["county"])
    db_soil = {pid: n for (kind, pid), n in names.items() if kind == "special" and "soil-conservation" in pid}
    soil_id, soil_new = {}, []
    for n, cs in sorted(soil_counties.items()):
        fits = [pid for pid in db_soil if re.sub(r"^ND-X-\d{3}-", "", pid) == slug(n)]
        if len(fits) == 1:
            soil_id[n] = fits[0]
        else:
            soil_id[n] = f"{STATE}-X-{min(cs)[2:]}-{slug(n)}"
            soil_new.append(n)
    unmatched_soil = sorted(set(db_soil) - set(soil_id.values()))
    if info["found"] and unmatched_soil:
        raise GeoError(f"    soil conservation districts: the ballot database has {unmatched_soil[:3]}, which the precinct table does not name; stopping")
    swname = {i: db_soil.get(i) or n for n, i in soil_id.items()}

    # ---- House subdistricts (4A, 4B) and a check of the table's districts: the Legislative Council's lines over the parts
    lrows = merge_rows(ldoc["rows"], lambda a: clean(a["DISTRICT"]).upper())
    lkeys, lpolys, larcs, lsides, _lr, lodd = I.fabric(lrows, lambda a: clean(a["DISTRICT"]).upper())
    numbers = sorted({re.sub(r"[A-Z]$", "", k) for k in lkeys}, key=int)
    subs = sorted(k for k in lkeys if re.search(r"[A-Z]$", k))
    if numbers != [str(n) for n in range(1, 48)] or any(not re.fullmatch(r"\d+[AB]", k) for k in subs):
        raise GeoError(f"    legislative districts: the Council's layer does not have districts 1 to 47 (it has {lkeys[:6]}...); stopping")
    for rows_, keyf, what in ((scdoc["rows"], lambda a: a["DistrictID"], "school districts"),):
        for a, _r in rows_:
            if not isinstance(keyf(a), (int, float)) or not 0 < int(keyf(a)) < 100000 or not clean(a["DistrictName"]):
                raise GeoError(f"    {what}: the row numbered {keyf(a)!r} does not fit the layout this builder was checked against; stopping")
    sid = lambda a: f"{STATE}-S-{int(a['DistrictID']):05d}"      # noqa: E731
    schkeys, schpolys, scharcs, schsides, _sr, schodd = I.fabric(merge_rows(scdoc["rows"], sid), sid)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    sname = {sid(a): names.get(("school", sid(a))) or clean(a["DistrictName"]) + " School District" for a, _r in scdoc["rows"]}
    say(f"      {len(lkeys)} legislative district shapes ({', '.join(subs) or 'no subdistricts'}), {len(schkeys)} school districts ({len(scharcs):,} lines), "
        f"{len(cous):,} Census county subdivisions ({len(carcs):,} lines)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("legislative", lodd), ("school", schodd), ("Census", codd)) if o))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, KNIT_M, 2]).encode()).hexdigest()   # noqa: E731
    o_leg = overlay_cached("legislative", pre_rings, I.rings_xy(lpolys), stamp(ppath, lpath), refresh, say)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(ppath, scpath), refresh, say)
    o_mcd = overlay_cached("places", pre_rings, I.rings_xy([r for _a, r in cous]), stamp(ppath, tpath), refresh, say)

    leg_differs, split_h = [], []
    for p, got in zip(pre, o_leg):
        got = sorted(got, key=lambda g: -g[1])
        p["senate"] = p["ld"]
        p["house"] = p["ld"]
        mine = [(lkeys[d], s) for d, s, _t in got if re.sub(r"[A-Z]$", "", lkeys[d]) == p["ld"]]
        if got and re.sub(r"[A-Z]$", "", lkeys[got[0][0]]) != p["ld"]:
            leg_differs.append({"id": p["id"], "table": p["ld"], "council_layer": lkeys[got[0][0]], "share": round(100 * got[0][1], 1)})
        if any(k.startswith(p["ld"]) and k != p["ld"] for k in subs if re.sub(r"[A-Z]$", "", k) == p["ld"]):
            sub = [(k, s) for k, s in mine if k != p["ld"]]
            if not sub:
                raise GeoError(f"    precinct part {p['id']} is in legislative district {p['ld']}, which has subdistricts, and touches neither; stopping")
            p["house"] = sub[0][0]
            if len(sub) > 1 and sub[1][1] >= SPLIT_SHARE:
                p.setdefault("split", {})["house"] = {k: round(100 * s, 1) for k, s in sub if s >= SPLIT_SHARE}
                split_h.append(p["id"])
    say(f"      legislative districts: the table's district is the Council's at {len(pre) - len(leg_differs):,} of {len(pre):,} parts"
        + (f" (it differs at {', '.join(d['id'] for d in leg_differs[:6])}{'...' if len(leg_differs) > 6 else ''}: the table is followed)" if leg_differs else "")
        + f"; {len(split_h)} parts of a district with subdistricts have {SPLIT_SHARE:.0%} or more of their area in the second")

    several = city_unmatched = city_moved = 0
    unmatched_cities = set()
    for p, got in zip(pre, o_mcd):
        share, thick = collections.Counter(), set()
        for d, s, t in got:                                   # a city in two counties is two rows of the Bureau's file and one place
            share[mkey[d]] += s
            if t:
                thick.add(mkey[d])
        rows = sorted(((k, s, k in thick) for k, s in share.items()), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t]
        if not own:
            own = [(k, s) for k, s, _t in rows[:1]]
        if not own:
            raise GeoError(f"    precinct part {p['id']} lies in no township and no city; stopping")
        if p["city"]:
            said = city_fold(p["city"])
            k = city_in.get((p["county"], said)) or city_in.get((p["county"], re.sub(r" city$", "", said))) or city_in.get((p["county"], said + " city"))
            if k is None:
                city_unmatched += 1
                unmatched_cities.add(f"{p['city']} ({cname[p['county']]})")
            else:
                if own[0][0] != k:
                    city_moved += 1
                own = [(k, dict(own).get(k, 0.0))] + [(x, s) for x, s in own if x != k]
            p["cityname"] = mname[k] if k is not None else "City of " + p["city"]
        p["mcd"] = own[0][0]
        p["mcd_all"] = [k for k, _s in own]
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in own] if len(own) > 1 else None
        several += len(own) > 1
        p["ward_ids"] = [f"{p['mcd']}|{w}" for w in p["wardwords"]] if p["city"] and mkind[p["mcd"]] == "city" else []
        p["com"] = f"{p['county']}|{p['comd']}" if p["comd"] else None
        p["swcd"] = soil_id[p["soil"]]
        p["park"] = f"{STATE}-P-{p['county'][2:]}-{slug(re.sub(r' Park District$', '', p['parkname']))}" if p["parkname"] else None
    say(f"      cities and townships by part: {several:,} of {len(pre):,} parts reach more than one place; {sum(1 for p in pre if p['city']):,} parts are in a city by "
        f"the table's own word ({city_moved} of them lie mostly outside the Census Bureau's limits of that city; {city_unmatched} name a city the Bureau's "
        f"file does not have in that county{': ' + ', '.join(sorted(unmatched_cities)[:8]) if unmatched_cities else ''})")
    park_names = {p["park"]: p["parkname"] for p in pre if p["park"]}
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
    say(f"      school districts by part: {split:,} parts are split between two or more districts, {none} lie in none, "
        f"{edges:,} others only brush a neighbouring district along a line")

    # ---- the area check: each county's parts against the Census Bureau's county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731  Esri's winding: outer rings clockwise
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in clist}
    if sorted(area_p) != clist:
        raise GeoError("    area check: the precinct table and the Census Bureau do not have the same 53 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precinct parts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws ({', '.join(f'{100 * (area_p[c] / area_c[c] - 1):+.1f}%' for c in off[:5])}); stopping")
    if fixed:
        say("      " + "; ".join(f"{n} parts are numbered 9999.01 in the table and are filed as their precinct's part 99" if c == "numbered 9999.01" else
                                 f"{n} rows' precinct number was taken from the part's own number" if c.startswith("precinct number") else
                                 f"{n} rows of {cname[c]} carried another code in CountyID and were filed by their precinct number" for c, n in sorted(fixed.items())))
    say(f"      area check: the precinct parts cover {100 + state_pct:.3f}% of the Census Bureau's North Dakota; the county furthest off is {cname[worst]} ({worst_pct:+.2f}%)")

    vals = {"county": [p["county"] for p in pre], "ward": [p["ward_ids"][0] if p["ward_ids"] else None for p in pre], "com": [p["com"] for p in pre],
            "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": ["0"] * len(pre), "judicial": [p["jud"] for p in pre],
            "swcd": [p["swcd"] for p in pre], "park": [p["park"] for p in pre]}
    ward_sets = [vals["ward"]] + [[p["ward_ids"][n] if len(p["ward_ids"]) > n else None for p in pre] for n in (1, 2)]
    ward_sets = [v for v in ward_sets if any(v)]
    shared_wards = sorted({w for p in pre if len(p["ward_ids"]) > 1 for w in p["ward_ids"]})
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

    def own(v, tol, sets=None):
        g, q, _l, _r = G.build_layer(arcs, sides, sets or [vals[v]], tol)
        return g, q

    PCT, LEG, SCH, CENSUS = "nd-sos-voter-precincts-2026", "nd-lc-legislative-districts", "nd-dpi-school-districts", "nd-census-tiger-2025-cousub"
    jud_name = {"ND-" + v: k for k, v in JUD.items()}
    jud_counties = collections.defaultdict(set)
    for p in pre:
        jud_counties[p["jud"]].add(cname[p["county"]])
    # The parts of two counties do not meet on one line (each county's were drawn by themselves), so anything wider than a
    # county is drawn from a file that has it whole: the state, the counties and the judicial districts (whole counties,
    # by the table) from the Census Bureau's lines, the legislative districts from the Legislative Council's.
    def census(v, tol):
        g, q, _l, _r = G.build_layer(carcs, csides, [v], tol)
        return g, q

    def council(v, tol):
        g, q, _l, _r = G.build_layer(larcs, lsides, [v], tol)
        return g, q

    jud_of = {}
    for p in pre:
        if jud_of.setdefault(p["county"], p["jud"]) != p["jud"]:
            raise GeoError(f"    precinct table: {cname[p['county']]} is put in two judicial districts; stopping")
    soil_of = collections.defaultdict(set)
    for p in pre:
        soil_of[p["county"]].add(p["swcd"])
    whole_soil = {c: next(iter(v)) for c, v in soil_of.items() if len(v) == 1}      # counties that lie in one soil conservation district
    layer("state", *census([STATE] * len(cous), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": "North Dakota", "j": FIPS, "d": None}, CENSUS)
    layer("county", *census(ccounty, G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, CENSUS)
    layer("cd", *census(["0"] * len(cous), G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": "North Dakota's one congressional district (the whole state)", "j": None, "d": v, "race": f"2026-{STATE}-H00"}, CENSUS)
    layer("senate", *council([re.sub(r"[A-Z]$", "", k) for k in lkeys], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Legislative District {v} (Senate)", "j": v, "d": v}, LEG)
    layer("house", *council(lkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"Legislative District {v} (House)", "j": v, "d": v, "senate": re.sub(r"[A-Z]$", "", v)},
          LEG)
    layer("judicial", *census([jud_of[c] for c in ccounty], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("judicial_district", v)) or f"{jud_name[v]} Judicial District", "j": v, "d": jud_name[v], "counties": sorted(jud_counties[v])}, CENSUS + "; which counties, from " + PCT)
    mg, mq, _l, _r = G.build_layer(carcs, csides, [mkey], TOL_MCD)
    layer("mcd", mg, mq, TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, CENSUS, zoom=MCD_ZOOM)
    if ward_sets:
        layer("ward", *own("ward", G.TOL_LOCAL, ward_sets), G.TOL_LOCAL,
              lambda v: dict({"id": v, "name": f"{mname[v.split('|')[0]]}, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
                             **({"shared": True} if v in shared_wards else {})), PCT)
    layer("com", *own("com", G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Commissioner {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, PCT)
    sw_g, sw_q = W.merged_layer([(carcs, csides, [whole_soil.get(c) for c in ccounty]),
                                 (arcs, sides, [None if p["county"] in whole_soil else p["swcd"] for p in pre])], G.TOL_LOCAL)
    sw_by = collections.OrderedDict()
    for v, polys_ in sw_g:                                    # a district that is whole counties and part of another is one shape of several pieces
        sw_by.setdefault(v, []).extend(polys_)
    layer("swcd", list(sw_by.items()), sw_q, G.TOL_LOCAL, lambda v: {"id": v, "name": swname[v], "j": v, "d": None},
          CENSUS + " where a county lies in one district; " + PCT + " inside the counties that are divided")
    layer("park", *own("park", G.TOL_LOCAL), G.TOL_LOCAL, lambda v: {"id": v, "name": park_names[v], "j": v, "d": None}, PCT)
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
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "school": {}, "swcd": {}, "park": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "mcd": p["mcd"], "house": p["house"], "senate": p["senate"], "cd": "0",
                  "judicial": p["jud"], "swcd": p["swcd"], "school": p["school"]}
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            used_names["swcd"][p["swcd"]] = swname[p["swcd"]]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["ward_ids"]:
                pr["ward"] = p["ward_ids"]
                for w in p["ward_ids"]:
                    used_names["ward"][w] = w.split("|")[1]
            if p["com"]:
                pr["com"] = p["com"]
                used_names["com"][p["com"]] = "Commissioner " + p["comd"]
            if p["park"]:
                pr["park"] = p["park"]
                used_names["park"][p["park"]] = p["parkname"]
            for k, v in (("city", p["city"] and p.get("cityname")), ("garrison", p["garrison"]), ("sw_water", p["sww"]), ("ems", p["ems"]),
                         ("vector", p["vector"]), ("library", p["library"]), ("school_said", p["schoolsaid"])):
                if v:
                    pr[k] = v
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
                raise GeoError(f"    precinct part {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // G.BOX_STEP, min(ys) // G.BOX_STEP, -(-max(xs) // G.BOX_STEP), -(-max(ys) // G.BOX_STEP)]
        boxes[county] = bx
        rel = f"precincts/{county}.json"
        size = put(rel, doc)
        cbox[county] = doc["bbox"]
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(pre, cname, cbox, put, say, refresh)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids, plans)
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    check["legislative_district_differs_from_the_council_layer"] = leg_differs
    check["soil_conservation_districts_not_in_the_ballot_database"] = soil_new
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    sos = "North Dakota Secretary of State, Elections; published on the North Dakota GIS Hub"
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": PCT, "agency": sos, "title": "NDGISHUB Voter Precincts (voter precinct splits for the 2026 election)",
                  "about": "Precinct parts and precinct part splits by legislative district, county, city, ward, school district, emergency services, "
                           "commissioner district, park district, Southwest Water Authority, Garrison Diversion, vector control and library.",
                  "url": PCT_ITEM, "service": PCT_SERVICE, "fetched": pdoc.get("fetched"), "sha256": G.sha_file(ppath), "rows": len(pre),
                  "disclaimer": "The State of North Dakota has compiled this data according to conventional cartographic standards, using what is thought to be the "
                                "most reliable information available. The State of North Dakota makes every effort to provide virus-free files but does not "
                                "guarantee uncorrupted files. The State of North Dakota does not guarantee this data to be free from errors, inaccuracies, or "
                                "viruses, and disclaims any responsibility or liability for interpretations or decisions based on this data."},
                 **edited["precincts"]),
            dict({"id": LEG, "agency": "North Dakota Legislative Council; published on the North Dakota GIS Hub",
                  "title": "NDGISHUB Legislative Districts (the 47 districts as revised under the United States District Court's order of January 8, 2024)",
                  "about": "Read to tell House subdistricts 4A and 4B apart and to check the precinct table's district numbers; the lines drawn are the precinct parts'.",
                  "url": LEG_ITEM, "service": LEG_SERVICE, "fetched": ldoc.get("fetched"), "sha256": G.sha_file(lpath), "rows": len(ldoc["rows"])}, **edited["legislative"]),
            dict({"id": SCH, "agency": "North Dakota Department of Public Instruction; published on the North Dakota GIS Hub", "title": "NDGISHUB School Districts",
                  "url": SCHOOL_ITEM, "service": SCHOOL_SERVICE, "fetched": scdoc.get("fetched"), "sha256": G.sha_file(scpath), "rows": len(schkeys)}, **edited["school"]),
            {"id": CENSUS, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025, county subdivisions, North Dakota (tl_2025_38_cousub.zip)",
             "about": "Cities, townships and unorganized territories as the Bureau had them on January 1, 2025; also the county areas the precinct parts are checked against.",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)}],
        "notes": {
            "lines": f"Every line is the Secretary of State's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 degree (about a "
                     "metre). A point within a few metres of a line can fall on either side of it.",
            "parts": "The smallest area the Secretary of State publishes is a precinct part: a precinct cut wherever a city, ward, school, park or other "
                     "district line crosses it. Each shape here is one part, named by its precinct's number and its own, and what is said of it (county, "
                     "legislative district, city, ward, commissioner district, soil conservation district, judicial district, park district) is the "
                     "Secretary's table's own word for that part.",
            "places": "A part outside the cities is often several townships together, so the part does not say which township a voter lives in: the mcd "
                      "layer (the Census Bureau's cities, townships and unorganized territories of January 1, 2025) answers that for a point. A part "
                      "the Secretary's table puts in a city is given that city, whatever the Bureau's older city limits say.",
            "commissioners": "The Secretary's table says how each county elects its commissioners: at large; one for each district by the voters of the whole "
                             "county (the table lists every district on every part); or each by the voters of its own district. Only districts of the "
                             "last kind are voting areas, so only they are shapes; supervisor_plans gives every county's.",
            "legislative": "A legislative district elects one senator and two representatives; district 4 elects one representative from each of its "
                           "subdistricts, 4A and 4B, told apart here by laying the Legislative Council's lines over the precinct parts (analysis).",
            "school": "School district lines are the Department of Public Instruction's. Which districts a part lies in is analysis, not an official list: a "
                      f"district counts when its piece of the part is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's "
                      "share of the part's area (land and water, not voters). The Secretary's table names a school district only on some parts "
                      "(school_said). No school office is on the November 2026 ballot.",
            "wards": "The Secretary's table names city wards for a few cities. Where it lists several wards on one part (the part is not cut along the "
                     "ward lines), each of those wards is drawn as the whole part and marked shared.",
            "authority": "For which precinct an address votes in, and where, the county auditor and the North Dakota Secretary of State's \"Where do I vote\" page are the authority.",
            "precinct_ids": "A part's id is its precinct's six digits (the county's number in the alphabet, the legislative district, the precinct) and "
                            "the part's two (47292007). Five parts the table numbers 9999.01 are filed as part 99 of their precinct.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct part. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the parts on the right and left of line i (-1: a part in another "
                            "county's file, or one just across a hairline gap in the state's drawing; -2: outside North Dakota); names gives the names of the "
                            "places the file's parts lie in.",
            "boxes": "boxes[county] holds four whole numbers a part, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every part whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name (Precinct 472920, part 07): its number in the Secretary's table and the part's",
                                    "county": "county id", "precinct": "the precinct's six-digit number", "mcd": "city, township or unorganized territory holding most of the part (the table's own city where it names one)",
                                    "mcd_all": "list, when the part reaches more than one: every city and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the part's area, in percent",
                                    "city": "the city the Secretary's table puts the part in",
                                    "ward": "list: the city ward the precinct lies in (absent where the table names none)",
                                    "com": "county commissioner district (only in a county whose commissioners are each elected by their own district's voters)",
                                    "house": "House district (the legislative district; 4A or 4B in district 4)", "senate": "Senate district (the legislative district)",
                                    "cd": "congressional district (0: the whole state)",
                                    "judicial": "judicial district", "swcd": "soil conservation district", "park": "park district",
                                    "garrison": "true where the part lies in the Garrison Diversion Conservancy District",
                                    "sw_water": "true where the part lies in the Southwest Water Authority",
                                    "ems": "the ambulance or fire district the table names", "vector": "true where the part lies in a vector control district",
                                    "library": "the library district the table names", "school_said": "the school district the table names, in its words",
                                    "split": "only where a second House subdistrict holds 3 percent or more of the part: each one's share in percent",
                                    "school": "list: the school districts the part lies in, largest share first",
                                    "school_pct": "list, when the part is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the part's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the part along a line (try them too when placing a point)",
                                    "c": "a point inside the part's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "ND (j is 38)", "county": "the county's five-digit code (38015)",
                    "mcd": "ND-M- and the Census county subdivision code (ND-M-07200); properties.t says city, township or unorganized territory",
                    "ward": "<city>|<ward> (ND-M-32060|Ward 5)", "com": "<county>|<district as the race words it> (38003|District 2)",
                    "house": "the district (41; 4A, 4B)", "senate": "the district (41)", "cd": "0; properties.race is the race for Congress",
                    "judicial": "the ballot database's id (ND-SC); d is the district's name",
                    "swcd": "the ballot database's id (ND-X-015-burleigh-county-soil-conservation-district); j is the same",
                    "park": "ND-P-, the county's three digits and the park district's name (ND-P-017-fargo)",
                    "school": "ND-S- and the Department's five-digit district number (ND-S-08001)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "whole_precincts": len({p["precinct"] for p in pre}), "counties": len(counties), "rows_put_right": fixed,
                   "split_between_school_districts": split, "in_more_than_one_city_or_township": several,
                   "rings_too_small_for_the_grid": dropped_rings, "split_between_house_subdistricts": len(split_h),
                   "lines_with_a_precinct_on_one_side": lone, "with_a_precinct_across": len(seam),
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} North Dakota races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    North Dakota ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's part lies in, the place at the point (from the mcd layer), and a word
    # its school district's name must carry. County, county subdivision, 2026 legislative districts (upper and lower)
    # and school district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02), an answer
    # that owes nothing to the files tested here. The judicial district is the county's (N.D. Sup. Ct. Admin. R. 2).
    ("the State Capitol, Bismarck", -100.7830, 46.8208, {"county": "38015", "senate": "35", "house": "35", "judicial": "ND-SC"}, "ND-M-07200", "Bismarck"),
    ("Fargo City Hall", -96.7880, 46.8790, {"county": "38017", "senate": "44", "house": "44", "judicial": "ND-EC"}, "ND-M-25700", "Fargo"),
    ("downtown Grand Forks", -97.0329, 47.9253, {"county": "38035", "senate": "18", "house": "18", "judicial": "ND-NEC"}, "ND-M-32060", "Grand Forks"),
    ("downtown Minot", -101.2923, 48.2330, {"county": "38101", "senate": "3", "house": "3", "judicial": "ND-NC"}, "ND-M-53380", "Minot"),
    ("downtown Williston", -103.6180, 48.1470, {"county": "38105", "senate": "1", "house": "1", "judicial": "ND-NW"}, "ND-M-86220", "Williston"),
    ("downtown Dickinson", -102.7896, 46.8792, {"county": "38089", "senate": "37", "house": "37", "judicial": "ND-SW"}, "ND-M-19620", "Dickinson"),
    ("New Town, Mountrail County (House subdistrict 4A)", -102.4902, 47.9808, {"county": "38061", "senate": "4", "house": "4A", "judicial": "ND-NC"}, "ND-M-56740", "New Town"),
    ("Garrison, McLean County (House subdistrict 4B)", -101.4160, 47.6520, {"county": "38055", "senate": "4", "house": "4B", "judicial": "ND-SC"}, "ND-M-29460", "Garrison"),
    ("Fort Yates, Sioux County", -100.6300, 46.0870, {"county": "38085", "senate": "31", "house": "31", "judicial": "ND-SC"}, "ND-M-27860", "Yates"),
    ("Mandan, Morton County (rows filed under a mistyped county code in the state's layer)", -100.8896, 46.8267,
     {"county": "38059", "senate": "34", "house": "34", "judicial": "ND-SC"}, "ND-M-49900", "Mandan"),
    ("a field in Ashtabula Township, Barnes County", -98.05, 47.10, {"county": "38003", "senate": "24", "house": "24", "judicial": "ND-SE"}, "ND-M-03580", "Barnes County North"),
    ("Medora, Billings County", -103.5244, 46.9139, {"county": "38007", "senate": "39", "house": "39", "judicial": "ND-SW"}, "ND-M-51900", "Billings"),
]
LINE_POINTS = [("the Burleigh-Kidder county line east of Sterling", -100.0, 46.82, ("38015", "38043")),
               ("the Cass-Barnes county line west of Tower City", -97.7, 46.92, ("38017", "38003"))]
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
    ids, county_of = set(), {}
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        geoms = doc["objects"]["precincts"]["geometries"]
        total += len(geoms)
        ids |= {g["id"] for g in geoms}
        county_of.update({g["id"]: c["id"] for g in geoms})
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
    check(total == index["counts"]["precincts"] == len(ids), "the county files do not hold as many precinct parts as the index says, each with its own id")
    shapes_seen, layer_ids = 0, {}
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        layer_ids[L["kind"]] = {g["id"] for g in gs}
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == 53, "there are not 53 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the parts on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == 47 and len(layer_ids.get("house", ())) == 48 and len(layer_ids.get("judicial", ())) == 8 and layer_ids.get("cd") == {"0"},
          "there are not 47 Senate districts, 48 House districts and subdistricts, 8 judicial districts and one congressional district")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precinct parts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every part is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place = collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com", "swcd": "swcd", "park": "park", "ward": "ward"}
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
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the part lies in" if sid in pr["school"] else "in a district the part only brushes" if sid else
                   "in none, in a part partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            place["the part's own place" if shape and shape["id"] == pr["mcd"] else "another place the part names" if shape and shape["id"] in pr.get("mcd_all", [])
                  else "a place the part does not name" if shape else "no place"] += 1
            if g["id"] not in split_ids:
                for prop, kind in layer_for.items():
                    if kind not in layer_ids or (i % 3 and kind not in ("com", "park", "ward")):
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
    check(wrong <= 3, f"{wrong} of {tested} precinct parts are not found again from a point inside them")
    check(not sum(no_shape.values()), f"parts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the part at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} parts' own points fall in no school district though the part is said to lie in one")
    check(place["no place"] == 0 and place["a place the part does not name"] <= 0.02 * tested, f"the place at a part's own point: {dict(place)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precinct parts found again from a point inside them; every id a part carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each part's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city or township at each part's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    for name, lon, lat, want, mcd, school_word in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct part"):
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
                    f"{name}: the mcd layer gives {shape and shape['id']} and the part names {[pr['mcd']] + pr.get('mcd_all', [])}; the place is {mcd}")
        for prop, kind in layer_for.items():
            if kind in layer_ids and pr.get(prop) is not None:
                shape2, _edge = G.shape_at(files, kind, lon, lat)
                mine = pr.get(prop)
                ok &= check(shape2 is not None and (shape2["id"] in mine if isinstance(mine, list) else shape2["id"] == mine),
                            f"{name}: layer {kind} gives {shape2 and shape2['id']}, the part says {mine}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, {pr['judicial']}, {sn}"
            + (f", commissioner {pr['com'].split('|')[1]}" if pr.get("com") else "") + (f", {', '.join(w.split('|')[1] for w in pr['ward'])}" if pr.get("ward") else "")
            + f"; {found['edge']:.0f} m from the part's line")

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

    # 5. polling places say what they are, and name only parts and places that are there
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values())
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])) and not set(polls["precinct"]) & set(polls["no_place"]),
              "polling_places.json names a precinct part or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        inside = 0
        for p in polls["places"]:
            if p.get("lonlat"):
                f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
                inside += bool(f3) and f3["county"] in {county_of[v] for v in p["precincts"]}
        say(f"      self-test: polling places: {polls.get('status')}; {len(polls['places']):,} places, {sum(1 for p in polls['places'] if p.get('lonlat')):,} with a point "
            f"({inside:,} of them inside the county of a precinct that votes there); {len(polls['precinct']):,} parts have one place, {len(polls['no_place']):,} several")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind North Dakota's ballot map -> ballot_geo/nd/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/nd)")
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
