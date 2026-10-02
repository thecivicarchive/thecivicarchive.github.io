"""
ballot/mn_geo.py - the geography behind Minnesota's ballot map: every precinct, every kind of district a ballot is
made of, and (when John has saved the list) every polling place, as a folder of small static files a page can load
piece by piece.

    python ballot/mn_geo.py                 builds ballot_geo/mn/ and runs the self-test (about two minutes; the first
                                            build also lays the school districts over the precincts, five minutes more)
    python ballot/mn_geo.py --selftest      runs the self-test on the files already built
    python ballot/mn_geo.py --refresh       asks the two map services again even when the cached copies are fresh
    python ballot/mn_geo.py --out DIR       builds somewhere else (a trial run)
    python ballot/mn_geo.py --polls DIR     looks for the saved polling place list in another folder (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the words the
ballot database uses for council districts, so that every shape's id matches the id its races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/mn_local/)
----------------------------------------------------------------------------------------------------------------------
  - Precincts: the Secretary of State's voting districts, published on the Minnesota Geospatial Commons
    (us_mn_state_sos/bdry_votingdistricts, the service ballot/state_local_mn.py reads for attributes). Asked for in
    longitude and latitude at full detail (outSR=4326, seven decimals, 250 precincts a request): the lines are light
    (about 660,000 points) and, at full detail, neighbouring precincts share their boundary point for point, which is
    what lets a shared line be kept once and every district be put together from its precincts exactly. (Asking the
    server to generalise each precinct by itself breaks that: two neighbours then disagree about their common line.)
    The generalising is done here instead, a line at a time, so both sides of a line always agree.
  - School districts: the Department of Education's School District Boundaries, SY2025-26
    (us_mn_state_mde/bdry_school_district_boundaries), fetched the same way. The Department calls these generalised
    boundaries, compiled for residential areas, and not the legal lines for taxation.
  - The Secretary of State's own sites are never asked for anything (they show this machine a CAPTCHA). Polling places
    are read only from a file John saves: see POLLING PLACES below.

What is built (ballot_geo/mn/, about 8 MB in all; a page loads index.json, one or two layers, and then only the
counties in view)
----------------------------------------------------------------------------------------------------------------------
  index.json              the sources, each county's bounding box and file, every precinct's bounding box (so a point
                          can be placed on the device: boxes -> the county file or two that could hold it -> the exact
                          test), each layer's file, size and tolerance, the formats in a few lines, and "check": every
                          Minnesota race in the ballot database against the shapes (which have none, and which are
                          elected from part of a shape).
  manifest.json           every file's size and SHA-256.
  precincts/27001.json    one TopoJSON file per county (87). Object "precincts": one geometry per precinct, id = the
     ... 27173.json       Secretary's VTDID, with properties: name, county, mcd, ward (a list), com, house, senate, cd,
                          judicial, swcd, hospital, park, school (a list; with school_pct where a precinct is split
                          between school districts, school_out where part of it lies in none, and school_edge for
                          neighbouring districts that only brush it along a line). Each value is the id of a shape in
                          the layer of the same name. Three members beyond plain TopoJSON, all aligned with "arcs":
                          "arcKinds" (the kinds, in bit order), "arcMask" (for each line, the kinds whose outline runs
                          along it) and "arcSides" (the precinct on the right and on the left of each line; -1 another
                          county's precinct, -2 outside Minnesota). With them a page draws any district's outline at
                          full detail, down to the street, from the county files alone. "names" gives the names of the
                          places in the file.
  layers/<kind>.json      one TopoJSON file per kind of district, generalised for the zoom at which the whole layer is
                          drawn (statewide kinds 100 m, good to about zoom 10; local kinds 30 m, good to about zoom
                          12; closer in, the county files take over): state, county, cd, senate, house, judicial, mcd
                          (cities, townships and unorganized territories), ward, com (county commissioner districts),
                          swcd (soil and water), hospital, park, school. Every shape has id, bbox, and properties
                          name, j, d (the jurisdiction_id and district its races carry in sl_races), c (a point inside
                          it for a label).
  school/<id>.json        each school district at full detail (3 m), for the exact test in a split precinct and for
                          drawing close in.
  polling_places.json     the polling places and the precincts that vote at each, or a note that they are waiting.
  reader.js               a small reader for these files (ballot/mn_geo_reader.js, copied; plain functions, no
                          library): decode a file, find the precinct at a point, list a district's outline. The
                          self-test below does in Python exactly what it does, and the two were run against each other
                          on 700 points under Windows Script Host (an engine older than any browser in use).

Tried on 2026-10-01, besides the self-test: 110 points (70 anywhere in the state, 40 in ten cities) asked of the two
services themselves (which precinct holds this point, which school district) gave the same precinct and the same school
district as the built files, every one; and every layer's area equals the sum of its precincts' within a hundredth of
one percent.

Coordinates are longitude and latitude on a grid of 0.00001 degree (about a metre): every file's TopoJSON transform is
scale [0.00001, 0.00001], translate [-98, 43], and each line is delta-encoded (TopoJSON's own rule).

Ids (they are the ballot database's own)
----------------------------------------
  county    "001"            sl_places county id; sl_races.jurisdiction_id of county offices
  mcd       "00172"          sl_places mcd id; jurisdiction_id of city and township offices
  ward      "00694|Ward 2"   jurisdiction_id | district of a council race (the district in the database's own words:
                             "Ward 2", "Ward E", Rochester's "District 1", Glencoe's "Precinct 2", Red Wing's
                             "Wards 1 & 2", which is drawn as wards 1 and 2 together)
  com       "001|1"          county | commissioner district
  house     "1A"   senate "1"   judicial "JD1"   cd "1" (properties.race is the federal race id, 2026-MN-H01)
  swcd      the Secretary's four-digit code. Where supervisors are elected by district (Anoka, Carver, Dakota, Scott,
            Washington, Renville, Fillmore) a shape is one supervisor district: j = county, d = district. Elsewhere a
            shape is the whole soil and water district and every supervisor race of it is on every ballot in it:
            j = county, d = null; where a county has two districts (Otter Tail, Polk, St. Louis) properties.jn is the
            jurisdiction as sl_races writes it ("Otter Tail East (soil and water district)").
  hospital  "HD00310"        sl_places hospital id
  park      "053|1" (Three Rivers Park District: the county park commissioner races), "43000|1" (Minneapolis Park and
            Recreation Board, elected in odd years)
  school    "ISD0001", "SSD0001", "CSD0323"     sl_places school id

Which school districts a precinct lies in is worked out here by laying the Department's boundaries over the precinct
(analysis, not an official list): a district is kept when its part of the precinct is at least SCHOOL_THICK metres
thick somewhere, so the hairline overlaps two boundary files leave along a shared line are set aside (tried on
2026-10-01: 1,472 overlaps were thinner than 10 m, 5,837 thicker than 300 m, and only 466 lay between; a third of
Minnesota's precincts really are split between school districts). school_pct is each district's share of the precinct's
area (land and water, not voters). Where a precinct is split, the device settles which district a point is in from
school/<id>.json, trying the precinct's school and school_edge districts.

Not drawn, because neither source has the lines: school board member districts inside a school district (Minneapolis,
Elk River, Winona and nine more), hospital board seats for one township (the race id carries the township's code, which
a precinct's mcd matches), the two sanitary districts, and the two school districts the Department's 2025-26 file does
not have yet (ISD 2913 and 2918). index.json lists them under "check".

POLLING PLACES
--------------
There is no statewide polling-place file on the Minnesota Geospatial Commons (only precincts and election results are
published there by the Secretary of State) or on any other state page a script can read. The Secretary of State's
Polling Place List is ordered with a form, for a fee ($46 for the whole state on 2026-10-01, so it is John's decision),
and arrives by e-mail as a comma-delimited text file (precinct, polling place name and address, type and status, county
code, MCD code, school district codes). When John has it he saves it into states_cache/mn_local/sos/pollingplaces/ and
this builder reads it: columns are found by their headings; only the precinct, the place's name and street address,
its type and status and any coordinates are kept (a polling place is a public building; its address is not private
data); a place with no coordinates is put on the map by the Census Bureau's geocoder from its street address (no key;
kept in a small cache), and a match far from its precincts is thrown out. The reader was written before any such file
had been seen (it was tried on a made-up list), so its output is marked "unchecked", which a page must not show, until
a person has compared it with the file and set POLL_LAYOUT_CHECKED to True. Until a file is there, polling_places.json
says the list is waiting. Counties publish their own polling place lists and some have map services (Ramsey, Olmsted,
Anoka, Washington, Sherburne, Pope were seen in passing); none is read here, because each would have to be shown to
be the November 3, 2026 list before a voter is sent anywhere by it.
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
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
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402

OUT = os.path.join(HERE, "ballot_geo", "mn")
CACHE = os.path.join(HERE, "states_cache", "mn_local")
POLL_DIR = os.path.join(CACHE, "sos", "pollingplaces")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = os.path.join(HERE, "ballot", "mn_geo_reader.js")

VTD_SERVICE = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/bdry_votingdistricts/FeatureServer/0"
VTD_ITEM = "https://gisdata.mn.gov/dataset/bdry-votingdistricts"
VTD_FIELDS = ("vtdid,pctname,pctcode,mcdname,mcdcode,mcdfips,ctu_type,countyname,countycode,countyfips,congdist,mnsendist,mnlegdist,"
              "ctycomdist,juddist,swcdist,swcdist_n,ward,hospdist,hospdist_n,parkdist,parkdist_n")
MDE_SERVICE = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_mde/bdry_school_district_boundaries/FeatureServer/0"
MDE_ITEM = "https://gisdata.mn.gov/dataset/bdry-school-district-boundaries"
MDE_FIELDS = "sdorgid,formid,sdtype,sdnumber,prefname,shortname"
HUB_SEARCH = "https://gis.data.mn.gov/api/search/v1/collections/all/items?limit=5&q="
META_URL = "https://www.arcgis.com/sharing/rest/content/items/{}/info/metadata/metadata.xml"
MAX_AGE_DAYS = 30
ELECTION = "2026-11-03"

VERSION = 1
SCALE = 1e-5                      # the grid: 0.00001 degree
ORIGIN = (-98.0, 43.0)            # TopoJSON translate
XOFF = 1800000000                 # vertex keys: ((longitude in 1e-7 degree + XOFF) << 30) | latitude in 1e-7 degree
YMASK = (1 << 30) - 1
OXI, OYI = int(round(ORIGIN[0] * 1e7)), int(round(ORIGIN[1] * 1e7))
M_PER_UNIT = 0.011132             # metres in 1e-7 degree of latitude
BOX_STEP = 100                    # precinct boxes in index.json: grid units of 0.001 degree, rounded outwards

TOL_PRECINCT = 1.5                # metres: lines in the county files
TOL_SCHOOL = 3.0                  # metres: school/<id>.json
TOL_WIDE = 100.0                  # metres: layers drawn with the whole state in view (a pixel at about zoom 10)
TOL_LOCAL = 30.0                  # metres: layers drawn from a county's width down to a city's (a pixel at about zoom 12)
NEAR_M = 30.0                     # metres: a point this close to a precinct's line is said to be near it
SCHOOL_THICK = 60.0               # metres: a school district's part of a precinct must be this thick somewhere to count
SCHOOL_TYPE = {"01": "ISD", "02": "CSD", "03": "SSD"}
SCHOOL_WORD = {"01": "ISD", "02": "Common School District", "03": "SSD"}

ARC_KINDS = ["county", "mcd", "ward", "com", "house", "senate", "cd", "judicial", "swcd", "hospital", "park"]
SWCD_BY_DISTRICT = re.compile(r"^(.*) District (\d+)$")


class GeoError(SystemExit):
    pass


# ---------------------------------------------------------------- small geometry

def vkey(lon, lat):
    return ((int(round(lon * 1e7)) + XOFF) << 30) | int(round(lat * 1e7))


def vxy(k):
    return (k >> 30) - XOFF, k & YMASK


def qpt(k):
    """A vertex on the files' grid (TopoJSON's quantised position)."""
    return ((k >> 30) - XOFF - OXI + 50) // 100, ((k & YMASK) - OYI + 50) // 100


def lonlat(q):
    return q[0] * SCALE + ORIGIN[0], q[1] * SCALE + ORIGIN[1]


def clean_ring(ring):
    """One ring as vertex keys, without its closing point, repeated points or spikes (out and straight back);
    None when fewer than three points are left."""
    ks = []
    for p in ring:
        k = vkey(p[0], p[1])
        if ks and ks[-1] == k:
            continue
        if len(ks) >= 2 and ks[-2] == k:
            ks.pop()
            continue
        ks.append(k)
    if len(ks) > 1 and ks[0] == ks[-1]:
        ks.pop()
    while len(ks) >= 3:
        if ks[-1] == ks[1]:
            ks = ks[2:]
        elif ks[-2] == ks[0]:
            ks = ks[1:-1]
        else:
            break
    return ks if len(ks) >= 3 else None


def area2(pts):
    """Twice the signed area of a ring of (x, y) pairs, counter-clockwise positive."""
    s = 0
    x0, y0 = pts[-1]
    for x1, y1 in pts:
        s += x0 * y1 - x1 * y0
        x0, y0 = x1, y1
    return s


def in_ring(x, y, pts):
    inside = False
    xj, yj = pts[-1]
    for xi, yi in pts:
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        xj, yj = xi, yi
    return inside


def in_rings(x, y, rings):
    """Even-odd: inside an odd number of the rings."""
    n = 0
    for pts in rings:
        if in_ring(x, y, pts):
            n += 1
    return n % 2 == 1


def seg_dist2(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    dd = dx * dx + dy * dy
    if dd == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * dx + (py - ay) * dy) / dd
    if t <= 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    if t >= 1:
        return (px - bx) ** 2 + (py - by) ** 2
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def simplify(pts, tol_m):
    """Douglas-Peucker on one line of vertex keys; the ends stay. A closed line keeps at least a triangle."""
    n = len(pts)
    if n <= 2 or tol_m <= 0:
        return pts
    closed = pts[0] == pts[-1]
    if closed and n <= 5:
        return pts
    c = math.cos(math.radians((pts[0] & YMASK) / 1e7))
    xs = [((k >> 30) - XOFF) * c for k in pts]
    ys = [k & YMASK for k in pts]
    tol2 = (tol_m / M_PER_UNIT) ** 2
    keep = bytearray(n)
    keep[0] = keep[n - 1] = 1
    if closed:
        far = max(range(1, n - 1), key=lambda k: (xs[k] - xs[0]) ** 2 + (ys[k] - ys[0]) ** 2)
        keep[far] = 1
        stack = [(0, far), (far, n - 1)]
    else:
        stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        ax, ay, bx, by = xs[i], ys[i], xs[j], ys[j]
        dx, dy = bx - ax, by - ay
        dd = dx * dx + dy * dy
        m, mi = -1.0, -1
        for k in range(i + 1, j):
            px, py = xs[k] - ax, ys[k] - ay
            if dd == 0:
                d = px * px + py * py
            else:
                t = (px * dx + py * dy) / dd
                if t <= 0:
                    d = px * px + py * py
                elif t >= 1:
                    d = (xs[k] - bx) ** 2 + (ys[k] - by) ** 2
                else:
                    ex, ey = px - t * dx, py - t * dy
                    d = ex * ex + ey * ey
            if d > m:
                m, mi = d, k
        if m > tol2:
            keep[mi] = 1
            stack.append((i, mi))
            stack.append((mi, j))
    if closed and sum(keep) < 4:
        ax, ay, bx, by = xs[0], ys[0], xs[far], ys[far]
        third = max((k for k in range(1, n - 1) if not keep[k]), key=lambda k: seg_dist2(xs[k], ys[k], ax, ay, bx, by))
        keep[third] = 1
    return [pts[k] for k in range(n) if keep[k]]


# ---------------------------------------------------------------- the two map services

def _fresh(path, refresh):
    return (not refresh) and os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < MAX_AGE_DAYS * 86400


def dataset_about(title, service, path, refresh, say):
    """What its publisher says about a dataset: the Commons' own record (title, one-line summary) and, from the item's
    metadata, the date it was published, the date the data are current to, its use limits and its disclaimer (the
    Secretary of State's must travel with any copy of the data, so index.json carries it). Only those tags are read;
    the metadata's contact names, telephone numbers and e-mail addresses never are. Kept in a small cache; when the
    record cannot be read the build carries on with the last copy, or without."""
    if _fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    import xml.etree.ElementTree as ET

    def clean(t):
        return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", t or "")).strip() or None

    out = {"fetched": dt.date.today().isoformat()}
    try:
        net.patient_lookups()
        j = json.loads(net.get(HUB_SEARCH + quote(title), accept="application/json"))
        root = service.rsplit("/", 1)[0].lower()
        for f in j.get("features") or []:
            p = f.get("properties") or {}
            if (p.get("url") or "").lower().rstrip("/") == root and re.fullmatch(r"[0-9a-f]{32}", p.get("id") or ""):
                out.update(item=p["id"], title=p.get("title"), snippet=clean(p.get("snippet")), publisher=p.get("source"))
                break
        if out.get("item"):
            out["metadata"] = META_URL.format(out["item"])
            raw = net.get(out["metadata"], timeout=120)
            out["metadata_sha256"] = hashlib.sha256(raw).hexdigest()
            doc = ET.fromstring(raw[:4 << 20])
            for key, tag in (("published", "dataIdInfo/idCitation/date/pubDate"), ("current_to", "dataIdInfo/dataExt/tempEle/TempExtent/exTemp/TM_Instant/tmPosition"),
                             ("use", "dataIdInfo/resConst/Consts/useLimit"), ("disclaimer", "dataIdInfo/resConst/LegConsts/useLimit")):
                el = doc.find(tag)
                out[key] = clean(el.text) if el is not None else None
    except Exception as e:  # noqa: BLE001  the lines do not depend on this record
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not read what the Commons says about {title!r} ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        say(f"      could not read what the Commons says about {title!r} ({e}); carrying on without it")
        return out
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    os.replace(path + ".part", path)
    return out


def fetch_full(service, fields, path, page, refresh, say):
    """Every feature of one layer with its rings in longitude and latitude at full detail, page by page, one request
    at a time, cached as gzipped JSON. If the service cannot be reached and an older copy is on disk, that copy is used
    and the caller is told."""
    if _fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    try:
        rows, offset = [], 0
        while True:
            url = (f"{service}/query?where={quote('1=1')}&outFields={fields}&returnGeometry=true&outSR=4326&geometryPrecision=7"
                   f"&orderByFields=objectid&resultOffset={offset}&resultRecordCount={page}&f=json")
            j = json.loads(net.get(url, timeout=300, accept="application/json"))
            if "error" in j:
                raise GeoError(f"    {service}: {j['error']}")
            feats = j.get("features", [])
            rows += [[f["attributes"], (f.get("geometry") or {}).get("rings") or []] for f in feats]
            offset += len(feats)
            if not feats or not j.get("exceededTransferLimit"):
                break
            time.sleep(1.0)
        count = json.loads(net.get(f"{service}/query?where={quote('1=1')}&returnCountOnly=true&f=json", accept="application/json")).get("count")
        if count != len(rows):
            raise GeoError(f"    {service}: {len(rows):,} shapes came, but the service counts {count}; stopping")
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
            return json.load(gzip.open(path, "rt", encoding="utf-8"))
        raise
    out = {"service": service, "fields": fields, "geometry": "longitude and latitude (EPSG:4326), seven decimals, full detail",
           "fetched": dt.date.today().isoformat(), "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(tmp, path)
    say(f"      {os.path.basename(path)}: {len(rows):,} shapes fetched")
    return out


# ---------------------------------------------------------------- topology: every shared line once

def topology(polys):
    """polys: for each polygon its rings (vertex keys, Esri's winding: the polygon is on the right of each edge).
    Returns arcs (each a list of vertex keys; a closed one repeats its first point), sides ([right, left] polygon of
    each arc, -1 for none), rings (for each polygon, each ring as signed arc numbers: ~a is arc a backwards), and a
    few counts of anything odd in the data."""
    owner, odd = {}, collections.Counter()
    for i, rings in enumerate(polys):
        for ks in rings:
            a = ks[-1]
            for b in ks:
                if (a, b) in owner and owner[(a, b)] != i:
                    odd["edges claimed by two polygons"] += 1
                owner[(a, b)] = i
                a = b
    deg = collections.Counter()
    for (a, b) in owner:
        if a < b or (b, a) not in owner:
            deg[a] += 1
            deg[b] += 1
    arcs, sides, seen, rings_of = [], [], {}, []
    for i, rings in enumerate(polys):
        mine = []
        for ks in rings:
            n = len(ks)
            left = [owner.get((ks[(k + 1) % n], ks[k]), -1) for k in range(n)]
            brk = [k for k in range(n) if deg[ks[k]] != 2 or left[k - 1] != left[k]]
            if not brk:
                s = min(range(n), key=ks.__getitem__)
                pieces = [ks[s:] + ks[:s] + [ks[s]]]
            else:
                pieces = []
                for j, b0 in enumerate(brk):
                    b1 = brk[(j + 1) % len(brk)]
                    pieces.append(ks[b0:b1 + 1] if b1 > b0 else ks[b0:] + ks[:b1 + 1])
            refs = []
            for pts in pieces:
                fwd = (pts[1] <= pts[-2]) if pts[0] == pts[-1] else (pts[0] < pts[-1])
                can = pts if fwd else pts[::-1]
                key = (can[0], can[1], can[-2], can[-1], len(can))
                a = seen.get(key)
                if a is None:
                    a = seen[key] = len(arcs)
                    arcs.append(can)
                    sides.append([-1, -1])
                side = 0 if fwd else 1
                if sides[a][side] not in (-1, i):
                    odd["lines with two polygons on one side"] += 1
                sides[a][side] = i
                refs.append(a if fwd else ~a)
            mine.append(refs)
        rings_of.append(mine)
    return arcs, sides, rings_of, odd


def ring_keys(refs, arcs):
    out = []
    for r in refs:
        a = arcs[r] if r >= 0 else arcs[~r][::-1]
        out.extend(a if not out else a[1:])
    return out


def ring_xy(refs, arcs):
    return [vxy(k) for k in ring_keys(refs, arcs)[:-1]]


def simplify_arcs(arcs, rings_of, tol_m):
    """Every arc generalised by itself (so both sides of a line stay the same line). A ring that would lose more than
    half its area, or flip, gets its arcs back at a quarter of the tolerance, then in full."""
    out = [simplify(a, tol_m) for a in arcs]
    restored = 0
    for step in (tol_m / 4.0, 0.0):
        bad = set()
        for rings in rings_of:
            for refs in rings:
                a0 = area2(ring_xy(refs, arcs))
                a1 = area2(ring_xy(refs, out))
                if a0 == 0:
                    continue
                if a1 == 0 or (a1 > 0) != (a0 > 0) or abs(a1) < 0.5 * abs(a0) or abs(a1) > 2.0 * abs(a0):
                    bad.update(r if r >= 0 else ~r for r in refs)
        if not bad:
            break
        for a in bad:
            out[a] = simplify(arcs[a], step)
        restored += len(bad)
    return out, restored


def group_polys(rings):
    """rings: [(refs, pts)] in Esri's winding (outer rings clockwise). Returns polygons, each [outer refs, hole refs
    ...], largest first."""
    outers, holes = [], []
    for refs, pts in rings:
        a = area2(pts)
        if a == 0:
            continue
        (outers if a < 0 else holes).append([abs(a), refs, pts, []])
    outers.sort(key=lambda o: -o[0])
    for h in holes:
        home = None
        for o in reversed(outers):                       # smallest first
            if o[0] <= h[0]:
                continue
            votes = sum(1 for (x, y) in h[2][:3] if in_ring(x, y, o[2]))
            if votes * 2 > min(3, len(h[2])):
                home = o
                break
        if home is None:
            outers.append([h[0], h[1], h[2], []])        # a hole with no outer ring around it: kept as its own shape
        else:
            home[3].append(h[1])
    outers.sort(key=lambda o: -o[0])
    return [[o[1]] + o[3] for o in outers]


def dissolve(arcs, sides, vals):
    """Put the polygons that share a value together. Returns chains (the boundary lines between different values, each
    as long as it can be: a list of vertex keys), pairs (the value on the right and on the left of each chain) and
    shapes {value: [(ring as signed chain numbers, its points)]} in Esri's winding (the shape on the right)."""
    def val(p):
        return vals[p] if p >= 0 else None

    def pair(a, e):                                       # the values right and left when arc a is walked from its end e
        vr, vl = val(sides[a][0]), val(sides[a][1])
        return (vr, vl) if e == 0 else (vl, vr)

    ends = collections.defaultdict(list)
    bnd = []
    for a, (r, l) in enumerate(sides):
        if val(r) != val(l):
            bnd.append(a)
            ends[arcs[a][0]].append((a, 0))
            ends[arcs[a][-1]].append((a, 1))
    junction = set()
    for node, lst in ends.items():
        if len(lst) != 2:
            junction.add(node)
        else:
            (a1, e1), (a2, e2) = lst
            if a1 != a2 and pair(a1, 1 - e1) != pair(a2, e2):
                junction.add(node)
    used, chains, pairs = set(), [], []

    def walk(a, e):
        pts, pr = [], pair(a, e)
        while True:
            used.add(a)
            seg = arcs[a] if e == 0 else arcs[a][::-1]
            pts.extend(seg if not pts else seg[1:])
            node = seg[-1]
            if node in junction:
                break
            lst = ends[node]
            here = (a, 1 - e)
            nxt = lst[1] if lst[0] == here else lst[0]
            if nxt[0] in used:
                break
            a, e = nxt
        chains.append(pts)
        pairs.append(pr)

    for node in junction:
        for a, e in ends[node]:
            if a not in used:
                walk(a, e)
    for a in bnd:
        if a not in used:
            walk(a, 0)

    items = collections.defaultdict(list)
    for c, (vr, vl) in enumerate(pairs):
        if vr is not None:
            items[vr].append(c)
        if vl is not None:
            items[vl].append(~c)

    def start(r):
        return chains[r][0] if r >= 0 else chains[~r][-1]

    def finish(r):
        return chains[r][-1] if r >= 0 else chains[~r][0]

    def heading(r, at_end):
        """Direction of travel at the start (or the end) of an oriented chain."""
        pts = chains[r] if r >= 0 else chains[~r][::-1]
        (x0, y0), (x1, y1) = (vxy(pts[-2]), vxy(pts[-1])) if at_end else (vxy(pts[0]), vxy(pts[1]))
        c = math.cos(math.radians(y0 / 1e7))
        return (x1 - x0) * c, y1 - y0

    shapes, loose = {}, 0
    for v, refs in items.items():
        begins = collections.defaultdict(list)
        for r in refs:
            begins[start(r)].append(r)
        unused = set(refs)
        rings = []
        for first in refs:
            if first not in unused:
                continue
            ring, cur = [], first
            while True:
                unused.discard(cur)
                ring.append(cur)
                node = finish(cur)
                cands = [r for r in begins[node] if r in unused]
                if node == start(first):
                    cands.append(first)
                if not cands:
                    ring = None
                    break
                if len(cands) == 1:
                    nxt = cands[0]
                else:                                     # the shape touches itself here: take the sharpest right turn
                    ix, iy = heading(cur, True)
                    nxt, best = None, None
                    for r in cands:
                        ox, oy = heading(r, False)
                        turn = math.atan2(ix * oy - iy * ox, ix * ox + iy * oy)
                        if best is None or turn < best:
                            nxt, best = r, turn
                if nxt == first:
                    break
                cur = nxt
            if ring is None:
                loose += 1
                continue
            rings.append((ring, ring_xy(ring, chains)))
        shapes[v] = rings
    return chains, pairs, shapes, loose


# ---------------------------------------------------------------- TopoJSON

def quantise(lines):
    """Each line on the grid, repeated points dropped; None for a line that has shrunk to nothing."""
    out = []
    for pts in lines:
        q = []
        for k in pts:
            p = qpt(k)
            if not q or q[-1] != p:
                q.append(p)
        closed = pts[0] == pts[-1]
        out.append(None if len(q) < (4 if closed else 2) else q)
    return out


def ring_q(refs, qarcs):
    out = []
    for r in refs:
        a = qarcs[r] if r >= 0 else qarcs[~r][::-1]
        out.extend(a if not out else a[1:])
    return out


def label_point(rings):
    """A point inside a polygon (its rings as grid points): the centroid of the outer ring if that is inside, else the
    middle of the widest stretch of the polygon on the centroid's latitude."""
    outer = rings[0]
    a = cx = cy = 0.0
    x0, y0 = outer[-1]
    for x1, y1 in outer:
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
        x0, y0 = x1, y1
    if a == 0:
        return outer[0]
    cx, cy = cx / (3 * a), cy / (3 * a)
    if in_rings(cx, cy, rings):
        return cx, cy
    best = None
    for y in (cy, cy + 0.37, min(p[1] for p in outer) * 0.5 + max(p[1] for p in outer) * 0.5 + 0.41):
        xs = []
        for pts in rings:
            xj, yj = pts[-1]
            for xi, yi in pts:
                if (yi > y) != (yj > y):
                    xs.append((xj - xi) * (y - yi) / (yj - yi) + xi)
                xj, yj = xi, yi
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            if best is None or xs[i + 1] - xs[i] > best[0]:
                best = (xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2, y)
        if best:
            break
    return (best[1], best[2]) if best else outer[0]


def topo_doc(objects, qarcs, more=None):
    """A TopoJSON topology. objects: {name: [geometry]}, each geometry {"id", "properties", "polys": [[outer ring,
    hole, ...], ...]} with rings as signed numbers into qarcs, in Esri's winding. Rings are written the GeoJSON way
    (outer rings counter-clockwise, holes clockwise). Only the lines used are written; `more(used)` may add members
    aligned with them (used = the qarcs number of each written line). Returns (document, dropped rings, kept geometry
    ring points for the callers' own sums)."""
    local, used = {}, []

    def ref(r):
        a = r if r >= 0 else ~r
        j = local.get(a)
        if j is None:
            j = local[a] = len(used)
            used.append(a)
        return j if r >= 0 else ~j

    dropped = 0
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    out_objects, shapes_pts = {}, {}
    for name, geoms in objects.items():
        out = []
        for g in geoms:
            polys, polys_pts = [], []
            for poly in g["polys"]:
                rings, rings_pts = [], []
                for n, refs in enumerate(poly):
                    good = [r for r in refs if qarcs[r if r >= 0 else ~r] is not None]
                    pts = ring_q(good, qarcs)[:-1] if good else []
                    if len(set(pts)) < 3 or area2(pts) == 0:
                        dropped += 1
                        if n == 0:
                            break
                        continue
                    rings.append([ref(~r) for r in reversed(good)])
                    rings_pts.append(pts)
                if rings:
                    polys.append(rings)
                    polys_pts.append(rings_pts)
            o = {"type": None, "id": g["id"], "properties": dict(g["properties"])}
            if polys:
                xs = [p[0] for poly in polys_pts for p in poly[0]]
                ys = [p[1] for poly in polys_pts for p in poly[0]]
                x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                xmin, ymin, xmax, ymax = min(xmin, x0), min(ymin, y0), max(xmax, x1), max(ymax, y1)
                (w, s), (e, n_) = lonlat((x0, y0)), lonlat((x1, y1))
                o["bbox"] = [round(w, 5), round(s, 5), round(e, 5), round(n_, 5)]
                if g.get("label"):
                    lx, ly = lonlat(label_point(polys_pts[0]))
                    o["properties"]["c"] = [round(lx, 4), round(ly, 4)]
                if len(polys) == 1:
                    o["type"], o["arcs"] = "Polygon", polys[0]
                else:
                    o["type"], o["arcs"] = "MultiPolygon", polys
            shapes_pts[(name, g["id"])] = polys_pts
            out.append(o)
        out_objects[name] = {"type": "GeometryCollection", "geometries": out}
    arcs_out = []
    for a in used:
        q = qarcs[a]
        line, (px, py) = [[q[0][0], q[0][1]]], q[0]
        for x, y in q[1:]:
            line.append([x - px, y - py])
            px, py = x, y
        arcs_out.append(line)
    doc = {"type": "Topology", "v": VERSION, "transform": {"scale": [SCALE, SCALE], "translate": [ORIGIN[0], ORIGIN[1]]}}
    if xmin != float("inf"):
        (w, s), (e, n_) = lonlat((xmin, ymin)), lonlat((xmax, ymax))
        doc["bbox"] = [round(w, 5), round(s, 5), round(e, 5), round(n_, 5)]
    if more:
        doc.update(more(used))
    doc["objects"] = out_objects
    doc["arcs"] = arcs_out
    return doc, dropped, shapes_pts


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(raw)
    return len(raw), hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- the precinct table

def blank(v):
    return (v or "").strip()


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def read_precincts(doc):
    """The precinct rows, in VTDID order, each cut down to what the map needs, and their rings as vertex keys. A table
    that no longer fits what this was checked against stops the build, naming the check."""
    rows = sorted(doc["rows"], key=lambda r: r[0]["vtdid"])
    pre, polys, seen = [], [], set()
    for a, rings in rows:
        vtdid, county, mcd = blank(a["vtdid"]), blank(a["countyfips"]), blank(a["mcdfips"])
        ok = (re.fullmatch(r"27\d{7}", vtdid) and vtdid == "27" + county + blank(a["pctcode"]) and vtdid not in seen
              and re.fullmatch(r"\d{5}", mcd) and int(blank(a["countycode"])) * 2 - 1 == int(county)
              and re.fullmatch(r"\d{1,2}[AB]", blank(a["mnlegdist"]).upper()) and blank(a["mnsendist"]).isdigit()
              and blank(a["congdist"]).isdigit() and blank(a["juddist"]).isdigit() and blank(a["ctycomdist"]).isdigit())
        if not ok:
            raise GeoError(f"    precinct table: the row for VTDID {vtdid!r} does not fit the layout this builder was checked against; stopping")
        seen.add(vtdid)
        ward = blank(a["ward"])
        m = re.fullmatch(r"W-0*(\w+)", ward)
        if ward and not m:
            raise GeoError(f"    precinct table: ward {ward!r} (VTDID {vtdid}) is not written W-<number or letter>; stopping")
        hosp, park = blank(a["hospdist"]), blank(a["parkdist"])
        pre.append({"id": vtdid, "name": blank(a["pctname"]), "county": county, "countyname": blank(a["countyname"]), "mcd": mcd,
                    "mcdname": blank(a["mcdname"]), "ctu": blank(a["ctu_type"]), "wardcode": m.group(1) if m else "",
                    "com": str(int(blank(a["ctycomdist"]))), "house": re.sub(r"^0+", "", blank(a["mnlegdist"]).upper()),
                    "senate": str(int(blank(a["mnsendist"]))), "cd": str(int(blank(a["congdist"]))), "jud": str(int(blank(a["juddist"]))),
                    "swcd": blank(a["swcdist"]), "swcd_n": blank(a["swcdist_n"]),
                    "hosp": f"HD{int(hosp):05d}" if hosp else "", "hosp_n": blank(a["hospdist_n"]),
                    "parkcode": park, "park_n": blank(a["parkdist_n"])})
        polys.append([k for k in (clean_ring(r) for r in rings) if k])
    if len({p["county"] for p in pre}) != 87:
        raise GeoError(f"    precinct table: {len({p['county'] for p in pre})} counties, not 87; stopping")
    return pre, polys


def read_db(db):
    """Read-only: the names the ballot database gives Minnesota's places, the districts its council races name, and
    its races' places (for the check that every shape's id is one the races carry). Empty when there is no database."""
    info = {"names": {}, "council": collections.defaultdict(set), "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'mn-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat FROM sl_races WHERE state = 'MN'"))
    finally:
        con.close()
    for _rid, _level, kind, _jur, jid, district, _seat in info["races"]:
        if kind == "council" and district:
            info["council"][jid].add(district)
    info["found"] = True
    return info


# Council districts that are several wards together, where the words alone do not say which. Each needs the city's own
# page saying so; none is guessed. Crystal: City Charter, section 2.04 ("Section One, consisting of Wards One and Two;
# Section Two, consisting of Wards Three and Four"), the city's own PDF, read 2026-10-01
# (SHA-256 1849de9a83459044a6861d9d1ef6aa02319d090894bddcbb0a6f026fca7ef061).
CRYSTAL_CHARTER = "https://www.crystalmn.gov/UserFiles/Servers/Server_10879634/File/Government/City%20Council/CityCharter.pdf"
WARD_GROUPS = {("14158", "Section I"): (["1", "2"], "Crystal City Charter, section 2.04", CRYSTAL_CHARTER),
               ("14158", "Section II"): (["3", "4"], "Crystal City Charter, section 2.04", CRYSTAL_CHARTER)}


def ward_words(pre, council):
    """The words each ward goes by in the ballot database. Returns label {(mcd, ward code): "Ward 2"}, joined
    {(mcd, "Wards 1 & 2"): [codes]} and the council districts no ward can be found for."""
    codes = collections.defaultdict(set)
    for p in pre:
        if p["wardcode"]:
            codes[p["mcd"]].add(p["wardcode"])
    label, joined, unmatched = {}, {}, []
    for mcd, cs in codes.items():
        word = "Ward"
        for s in council.get(mcd, ()):
            m = re.fullmatch(r"(District|Precinct) (\w+)", s)
            if m and m.group(2) in cs:
                word = m.group(1)
        for c in cs:
            label[(mcd, c)] = f"{word} {c}"
    for mcd, strings in council.items():
        cs = codes.get(mcd, set())
        for s in sorted(strings):
            m = re.fullmatch(r"(Ward|District|Precinct) (\w+)", s)
            if m and label.get((mcd, m.group(2))) == s:
                continue
            m = re.fullmatch(r"Wards (\w+) (?:&|and) (\w+)", s)
            if m and m.group(1) in cs and m.group(2) in cs:
                joined[(mcd, s)] = [m.group(1), m.group(2)]
            elif (mcd, s) in WARD_GROUPS and all(c in cs for c in WARD_GROUPS[(mcd, s)][0]):
                joined[(mcd, s)] = list(WARD_GROUPS[(mcd, s)][0])
            else:
                unmatched.append((mcd, s))
    return label, joined, unmatched


def park_id(p):
    """Three Rivers Park District's commissioner districts are the county park commissioner races (jurisdiction: the
    county); the Minneapolis Park and Recreation Board's are the city's."""
    if not p["parkcode"]:
        return None
    if p["park_n"].startswith("Three Rivers"):
        return f"{p['county']}|{int(p['parkcode'])}"
    if p["park_n"].startswith("Minneapolis Park"):
        return f"{p['mcd']}|{int(p['parkcode'])}"
    return f"{p['park_n']}|{p['parkcode']}"


# ---------------------------------------------------------------- school districts laid over precincts

def school_overlay(pre_rings, districts, levels=(SCHOOL_THICK,), say=print):
    """For each precinct, the school districts that overlap it: [(district number in `districts`, share of the
    precinct's area, [thick enough at each level])]. Both are drawn on a grid over the precinct (cells of 6 to 20
    metres, coarser only for a precinct more than 60 km across) and counted; "thick enough" means a square of about
    that many metres fits inside the overlap, so hairline overlaps along a shared line fail it. A district holding half
    the precinct or more is thick without the test. `levels` must rise."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    dbox = []
    for rings in districts:
        boxes = [(min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r)) for r in rings]
        dbox.append(((min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)), boxes))
    out = []
    shrink = ImageFilter.MinFilter(3)
    for n, rings in enumerate(pre_rings):
        x0, y0 = min(p[0] for r in rings for p in r), min(p[1] for r in rings for p in r)
        x1, y1 = max(p[0] for r in rings for p in r), max(p[1] for r in rings for p in r)
        kx, ky = M_PER_UNIT * math.cos(math.radians((y0 + y1) / 2e7)), M_PER_UNIT
        span = max((x1 - x0) * kx, (y1 - y0) * ky, 1.0)
        cell = min(max(span / 900.0, 6.0), 20.0)
        if span / cell > 3000:
            cell = span / 3000.0
        reach = [max(1, int(math.ceil((lv / cell - 1) / 2.0))) for lv in levels]
        size = (int((x1 - x0) * kx / cell) + 3, int((y1 - y0) * ky / cell) + 3)

        def mask(some):
            m = None
            for r in some:
                t = Image.new("1", size, 0)
                ImageDraw.Draw(t).polygon([((x - x0) * kx / cell + 1, (y1 - y) * ky / cell + 1) for x, y in r], fill=1)
                m = t if m is None else ImageChops.logical_xor(m, t)
            return m

        mine = mask(rings)
        total = mine.convert("L").histogram()[255]
        got = []
        if total:
            for d, (box, boxes) in enumerate(dbox):
                if box[0] > x1 or box[2] < x0 or box[1] > y1 or box[3] < y0:
                    continue
                some = [r for r, b in zip(districts[d], boxes) if not (b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0)]
                if not some:
                    continue
                both = ImageChops.logical_and(mine, mask(some))
                bb = both.getbbox()
                if bb is None:
                    continue
                share = both.crop(bb).convert("L").histogram()[255] / total
                if share >= 0.5:
                    thick = [True] * len(levels)
                else:
                    m = max(reach) + 1                       # a rim of empty cells, so the edge of the picture never props a shape up
                    sub = both.crop((bb[0] - m, bb[1] - m, bb[2] + m, bb[3] + m)).convert("L")
                    thick, done, alive = [], 0, True
                    for r in reach:
                        while alive and done < r:
                            sub = sub.filter(shrink)
                            done += 1
                            alive = sub.getbbox() is not None
                        thick.append(alive)
                got.append((d, share, thick))
        out.append(got)
        if say and (n + 1) % 1000 == 0:
            say(f"      school districts over precincts: {n + 1:,} of {len(pre_rings):,}")
    return out


def overlay_cached(pre_rings, districts, stamp, path, refresh, say):
    """The overlay takes a few minutes, so its answer is kept beside the two downloads and used again while they (and
    the rule) have not changed."""
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return [[(d, share, [thick]) for d, share, thick in row] for row in kept["rows"]]
        except (ValueError, OSError):
            pass
    say("      laying the school districts over the precincts (a few minutes; kept for the next build)")
    res = school_overlay(pre_rings, districts, levels=(SCHOOL_THICK,), say=say)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": [[(d, round(share, 5), thick[0]) for d, share, thick in row] for row in res]}, fh, separators=(",", ":"))
    os.replace(tmp, path)
    return res


# ---------------------------------------------------------------- layers and files

def natkey(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def build_layer(arcs, sides, value_sets, tol_m):
    """Shapes for one layer: each list of values in value_sets is dissolved (most layers have one; wards add the
    council districts made of several wards), every boundary generalised once. Returns ([(value, polygons)], the lines
    on the grid, rings that could not be closed, lines given back their detail)."""
    lines, geoms, loose_all, restored_all = [], [], 0, 0
    for vals in value_sets:
        chains, _pairs, shapes, loose = dissolve(arcs, sides, vals)
        simple, restored = simplify_arcs(chains, [[ring for ring, _p in rings] for rings in shapes.values()], tol_m)
        base = len(lines)
        lines.extend(simple)
        for v, rings in shapes.items():
            polys = group_polys([(ring, ring_xy(ring, simple)) for ring, _p in rings])
            geoms.append((v, [[[r + base if r >= 0 else ~(~r + base) for r in ring] for ring in poly] for poly in polys]))
        loose_all += loose
        restored_all += restored
    return geoms, quantise(lines), loose_all, restored_all


def zoom_for(tol_m):
    """The web-map zoom at which the tolerance is one pixel in Minnesota (latitude 46)."""
    return round(math.log2(108740.0 / tol_m), 1)


def sos_mcd_name(p):
    base = re.sub(r"\s+(Twp|Unorg)\.?$", "", p["mcdname"])
    return f"{base} {p['ctu']}".strip()


def check_ids(info, shape_ids, swcd):
    """Every Minnesota race in the ballot database against the shapes: the layer and id that draw its place. Races
    whose place has no shape are listed by kind with the reason; races elected from part of a shape (a school board
    member district, a hospital board seat for one township) are listed with the shape they sit inside."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    by_layer, missing, parts, matched = collections.Counter(), collections.OrderedDict(), [], 0
    for rid, level, kind, jur, jid, district, seat in sorted(info["races"]):
        hit, why, part = None, None, None
        if level == "statewide" or kind in ("supreme_court", "court_of_appeals"):
            hit = ("state", "MN")
        elif kind == "state_senate":
            hit = ("senate", district)
        elif kind == "state_house":
            hit = ("house", district)
        elif kind == "district_court":
            hit = ("judicial", jid)
        elif kind == "county_commissioner":
            hit = ("com", f"{jid}|{district}")
        elif kind == "county_park":
            hit = ("park", f"{jid}|{district}")
        elif level == "county":
            hit = ("county", jid)
        elif level == "soil_water":
            codes = sorted(c for c, e in swcd.items() if e["county"] == jid)
            by_d = [c for c in codes if swcd[c]["d"] == district]
            by_n = [c for c in codes if swcd[c]["jn"] and swcd[c]["jn"] == jur]
            whole = [c for c in codes if swcd[c]["d"] is None]
            if by_d:
                hit = ("swcd", by_d[0])
            elif by_n:
                hit = ("swcd", by_n[0])
            elif len(whole) == 1:
                hit = ("swcd", whole[0])
            else:
                why = "the precinct table names no single soil and water district for this race"
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{district}") if district else ("mcd", jid)
            if district and hit[1] not in shape_ids["ward"]:
                why = "the precinct table has no ward of this name in this city"
        elif level == "school":
            hit = ("school", jid)
            part = district
            if jid not in shape_ids["school"]:
                why = "the Department of Education's 2025-26 boundary file does not have this district yet"
        elif level == "hospital":                        # a board has a member for each city and township (or numbered district) and one at large
            hit = ("hospital", jid)
            part = (f"Seat {seat}" if str(seat).isdigit() else seat) if seat and seat != "At Large" else None
        else:
            why = "neither source carries a boundary for this kind of district"
        if hit and hit[1] in shape_ids.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            if part:
                parts.append({"race_id": rid, "layer": hit[0], "id": hit[1], "part": part})
        else:
            key = (level, kind, jur, jid, district if level != "hospital" else None)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": key[4],
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "part_of_a_shape": parts}


# ---------------------------------------------------------------- polling places (from a file John saves)

POLL_WAITING = {            # goes into polling_places.json, which is published: words for a reader, nothing about this kit
    "why": "Minnesota publishes no statewide file of polling places that can simply be downloaded: the Secretary of State's Polling Place "
           "List is ordered with a form, for a fee, and has not been obtained yet. The Secretary's Polling Place Finder answers for one "
           "address at a time and is the authority.",
}
POLL_HOW = ("      polling places: waiting. There is no statewide file to download. The Secretary of State's list is an order, not a download "
            "(it costs $46 for the whole state, so it is John's decision): on sos.mn.gov, Election Administration & Campaigns > Data & Maps > "
            "Polling Place List Requests, open the Polling Place List Request Form, ask for the whole state, text format, the November 3, 2026 "
            "state general election, and send it with payment (by mail or in person); the Secretary e-mails a link within 1 to 10 business "
            "days (it works for seven). Save the text file as states_cache/mn_local/sos/pollingplaces/polling_place_list_20261103.txt and "
            "run this again.")
POLL_COLUMNS = {                                  # each alternative: words that must all begin a word of the heading
    "vtd": [("vtd",)],
    "county_code": [("county", "code"), ("county", "id"), ("county", "num"), ("countycode",), ("countyid",)],
    "county_name": [("county", "name"), ("county",)],
    "precinct_code": [("precinct", "code"), ("precinct", "id"), ("precinct", "num"), ("pct", "code"), ("precinctcode",)],
    "precinct_name": [("precinct", "name"), ("precinct",)],
    "place": [("polling", "place", "name"), ("poll", "name"), ("location", "name"), ("facility",), ("polling", "place"), ("location",)],
    "address": [("address", "1"), ("street",), ("address",)],
    "city": [("city",)],
    "zip": [("zip",), ("postal",)],
    "type": [("type",)],
    "status": [("status",)],
    "lat": [("lat",)],
    "lon": [("lon",), ("lng",)],
}
POLL_NEVER = ("phone", "email", "e mail", "contact", "judge", "clerk", "owner")      # headings never read, whatever else they say
POLL_LAYOUT_CHECKED = False       # set to True only when a person has compared the reader's output with a real list


def _poll_columns(head):
    words = [re.sub(r"[^a-z0-9]+", " ", h.lower()).split() for h in head]
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


def read_polling_file(path, pre):
    """The Secretary's Polling Place List, cut down on the spot to the precinct, the place's name and street address,
    its type and status, and coordinates if the file gives them. Returns a dict for polling_places.json, or raises
    GeoError saying which check failed (headings only are ever named, never a line)."""
    base = os.path.basename(path)
    text = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise GeoError(f"    {base}: fewer than two lines; not a polling place list")
    delim = max(",;\t|", key=lines[0].count)
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    cols = _poll_columns(rows[0])
    if "place" not in cols or not ({"vtd"} & set(cols) or {"precinct_code", "precinct_name"} & set(cols)):
        raise GeoError(f"    {base}: the first line does not name a precinct column and a polling place column (its headings: "
                       f"{'; '.join(h.strip() for h in rows[0])}); the reader needs to be told the layout")
    ids = {p["id"] for p in pre}
    by_name = collections.defaultdict(list)
    for p in pre:
        by_name[(re.sub(r"[^a-z0-9]", "", p["countyname"].lower()), re.sub(r"[^a-z0-9]", "", p["name"].lower()))].append(p["id"])

    def cell(r, field):
        i = cols.get(field)
        return r[i].strip() if i is not None and i < len(r) else ""

    codes = [int(cell(r, "county_code")) for r in rows[1:] if cell(r, "county_code").isdigit()]
    fips = bool(codes) and max(codes) > 87
    places, order, precinct, no_place, unmatched = {}, [], {}, {}, 0
    for r in rows[1:]:
        vtd = cell(r, "vtd")
        if vtd not in ids:
            vtd = None
            cc, pc = cell(r, "county_code"), cell(r, "precinct_code")
            if cc.isdigit() and pc.isdigit():
                guess = f"27{int(cc) if fips else 2 * int(cc) - 1:03d}{int(pc):04d}"
                vtd = guess if guess in ids else None
            if vtd is None:
                fits = by_name.get((re.sub(r"[^a-z0-9]", "", re.sub(r"(?i)\s+county$", "", cell(r, "county_name")).lower()),
                                    re.sub(r"[^a-z0-9]", "", cell(r, "precinct_name").lower())), [])
                vtd = fits[0] if len(fits) == 1 else None
        if vtd is None:
            unmatched += 1
            continue
        kind, status = cell(r, "type"), cell(r, "status")
        name = re.sub(r"\s+", " ", cell(r, "place"))
        if re.search(r"(?i)\bmail\b", f"{kind} {status} {name}"):
            no_place[vtd] = "votes by mail"
            continue
        if not name:
            continue
        key = (name.lower(), cell(r, "address").lower(), cell(r, "city").lower(), cell(r, "zip")[:5])
        if key not in places:
            places[key] = {"name": name, "address": re.sub(r"\s+", " ", cell(r, "address")), "city": cell(r, "city"), "zip": cell(r, "zip")[:5],
                           "type": kind or None, "lonlat": None, "precincts": []}
            try:
                lon, lat = float(cell(r, "lon")), float(cell(r, "lat"))
                if -97.5 < lon < -89.0 and 43.0 < lat < 49.5:
                    places[key]["lonlat"] = [round(lon, 5), round(lat, 5)]
            except ValueError:
                pass
            order.append(key)
        if vtd not in places[key]["precincts"]:
            places[key]["precincts"].append(vtd)
        precinct[vtd] = order.index(key)
    if len(precinct) + len(no_place) < 0.9 * len(ids):
        raise GeoError(f"    {base}: only {len(precinct) + len(no_place):,} of {len(ids):,} precincts could be found in it "
                       f"(columns read: {', '.join(sorted(cols))}); the reader needs to be told the layout")
    return {"places": [places[k] for k in order], "precinct": dict(sorted(precinct.items())), "no_place": dict(sorted(no_place.items())),
            "rows": len(rows) - 1, "rows_not_matched": unmatched, "columns_read": sorted(cols),
            "precincts_without_a_row": sorted(ids - set(precinct) - set(no_place))}


GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def census_geocode(rows, say):
    """[(id, street, city, zip)] -> {id: (longitude, latitude, the address as the Bureau matched it)}: the Census
    Bureau's batch geocoder (no key; up to 1,000 addresses a request here, one request at a time). Polling places are
    public buildings; nothing else is ever sent."""
    import uuid
    from urllib.request import Request, urlopen
    net.patient_lookups()
    out = {}
    for start in range(0, len(rows), 1000):
        buf = io.StringIO()
        w = csv.writer(buf)
        for rid, street, city, zipc in rows[start:start + 1000]:
            w.writerow([rid, street, city, "MN", zipc])
        boundary = "----mngeo" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"places.csv\"\r\n"
                f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n").encode("utf-8")
        req = Request(GEOCODER, data=body, headers={"User-Agent": net.UA, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urlopen(req, timeout=900) as r:
            text = r.read().decode("utf-8", "replace")
        for rec in csv.reader(io.StringIO(text)):
            if len(rec) >= 6 and rec[2].strip() == "Match":
                try:
                    lon, lat = (float(v) for v in rec[5].split(","))
                except ValueError:
                    continue
                out[rec[0].strip()] = (round(lon, 5), round(lat, 5), rec[4].strip())
        say(f"      polling places: {min(start + 1000, len(rows)):,} of {len(rows):,} addresses asked of the Census Bureau's geocoder")
        time.sleep(1.0)
    return out


def place_points(places, pbox, cache_path, say):
    """Coordinates for the places the file gives none for, from the street address (kept in a small cache, so an
    address is asked once). A match more than about 40 km from every precinct that votes there is thrown out."""
    kept = {}
    if os.path.exists(cache_path):
        try:
            kept = json.load(open(cache_path, encoding="utf-8"))
        except (ValueError, OSError):
            kept = {}
    ask = []
    for n, p in enumerate(places):
        p["_key"] = f"{p['address']}|{p['city']}|{p['zip']}".lower()
        if not p["lonlat"] and p["address"] and p["_key"] not in kept:
            ask.append((str(n), p["address"], p["city"], p["zip"]))
    if ask:
        try:
            got = census_geocode(ask, say)
        except Exception as e:  # noqa: BLE001  the list is still worth having without points on a map
            say(f"      polling places: the Census Bureau's geocoder could not be reached ({e}); places without coordinates stay off the map")
            got = None
        if got is not None:
            for rid, _street, _city, _zip in ask:
                kept[places[int(rid)]["_key"]] = list(got[rid]) if rid in got else None
            with open(cache_path + ".part", "w", encoding="utf-8") as fh:
                json.dump(kept, fh, separators=(",", ":"))
            os.replace(cache_path + ".part", cache_path)
    placed = far = 0
    for p in places:
        hit = kept.get(p.pop("_key"))
        if p["lonlat"]:
            p["from"] = "the Secretary of State's list"
            continue
        if not hit:
            continue
        lon, lat = hit[0], hit[1]
        boxes = [pbox[v] for v in p["precincts"] if v in pbox]
        if boxes and all(lon < b[0] - 0.5 or lon > b[2] + 0.5 or lat < b[1] - 0.35 or lat > b[3] + 0.35 for b in boxes):
            far += 1
            continue
        p["lonlat"], p["from"] = [lon, lat], "the Census Bureau's geocoder, from the street address"
        placed += 1
    return placed, far


def polling_places(out, pre, put, say, folder=None, pbox=None):
    folder = folder or POLL_DIR
    found = sorted((f for ext in ("*.txt", "*.csv", "*.tsv") for f in glob.glob(os.path.join(folder, ext))), key=os.path.getmtime)
    doc = {"v": VERSION, "election": ELECTION, "finder": "https://pollfinder.sos.mn.gov/"}
    if not found:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(POLL_HOW)
        return {"file": "polling_places.json", "status": "waiting"}
    path = found[-1]
    try:
        got = read_polling_file(path, pre)
    except GeoError as e:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(str(e))
        return {"file": "polling_places.json", "status": "unread"}
    in_file = sum(1 for p in got["places"] if p["lonlat"])
    placed, far = place_points(got["places"], pbox or {}, os.path.join(CACHE, "mn_geo_pollingplace_points.json"), say)
    with_point = sum(1 for p in got["places"] if p["lonlat"])
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Minnesota Secretary of State", "title": "Polling Place List, state general election of November 3, 2026",
                       "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": sha_file(path)},
               places=got["places"], precinct=got["precinct"], no_place=got["no_place"])
    put("polling_places.json", doc)
    say(f"      polling places ({os.path.basename(path)}): {len(got['places']):,} places for {len(got['precinct']):,} precincts ({in_file:,} with "
        f"coordinates in the file, {placed:,} placed by the Census Bureau's geocoder, {far} matches thrown out as too far from their precincts, "
        f"{len(got['places']) - with_point:,} without a point), {len(got['no_place']):,} precincts vote by mail, "
        f"{got['rows_not_matched']:,} of {got['rows']:,} rows fit no precinct, {len(got['precincts_without_a_row']):,} precincts have no row; "
        f"columns read: {', '.join(got['columns_read'])}")
    if not POLL_LAYOUT_CHECKED:
        say("      polling places: the reader was written before any such file was seen, so the file is marked 'unchecked' and a page must not "
            "show it yet. Compare a dozen precincts in polling_places.json with the file (and with the Secretary's Polling Place Finder), "
            "then set POLL_LAYOUT_CHECKED = True in ballot/mn_geo.py and build again.")
    return {"file": "polling_places.json", "status": status, "places": len(got["places"]), "with_coordinates": with_point}


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def clear_out(out):
    """Only this builder's own files are ever removed."""
    for sub in ("precincts", "layers", "school"):
        d = os.path.join(out, sub)
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, "*.json")):
                os.remove(f)
    for f in ("index.json", "manifest.json", "polling_places.json", "reader.js"):
        if os.path.exists(os.path.join(out, f)):
            os.remove(os.path.join(out, f))


def build(out=OUT, db=DB, refresh=False, say=print, polls_dir=None):
    t0 = time.time()
    say("    Minnesota ballot map: precinct and school district lines (Minnesota Geospatial Commons)")
    os.makedirs(CACHE, exist_ok=True)
    vpath = os.path.join(CACHE, "sos_votingdistricts_geometry_4326.json.gz")
    mpath = os.path.join(CACHE, "mde_school_district_geometry_4326.json.gz")
    vdoc = fetch_full(VTD_SERVICE, VTD_FIELDS, vpath, 250, refresh, say)
    mdoc = fetch_full(MDE_SERVICE, MDE_FIELDS, mpath, 40, refresh, say)
    about_v = dataset_about("Voting Districts, Minnesota", VTD_SERVICE, os.path.join(CACHE, "mn_geo_about_votingdistricts.json"), refresh, say)
    about_m = dataset_about("School District Boundaries, Minnesota", MDE_SERVICE, os.path.join(CACHE, "mn_geo_about_schooldistricts.json"), refresh, say)

    # ---- precincts: one line between two neighbours, kept once
    pre, polys = read_precincts(vdoc)
    arcs, sides, rings_of, odd = topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = simplify_arcs(arcs, rings_of, TOL_PRECINCT)
    qfine = quantise(fine)
    say(f"      {len(pre):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {TOL_PRECINCT} m)"
        + (f"; odd: {dict(odd)}" if odd else ""))

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the precinct table alone, and council districts are all called wards")
    label, joined, ward_unmatched = ward_words(pre, info["council"])
    cname, mname = {}, {}
    for p in pre:
        cname[p["county"]] = names.get(("county", p["county"])) or f"{p['countyname']} County"
        mname[p["mcd"]] = names.get(("mcd", p["mcd"])) or sos_mcd_name(p)
        p["ward_id"] = f"{p['mcd']}|{label[(p['mcd'], p['wardcode'])]}" if p["wardcode"] else None
        p["wards"] = ([p["ward_id"]] + sorted(f"{mcd}|{s}" for (mcd, s), codes in joined.items() if mcd == p["mcd"] and p["wardcode"] in codes)) if p["wardcode"] else []
        p["com_id"] = f"{p['county']}|{p['com']}"
        p["jud_id"] = "JD" + p["jud"]
        p["park_id"] = park_id(p)
    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "ward": [p["ward_id"] for p in pre],
            "com": [p["com_id"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": [p["cd"] for p in pre], "judicial": [p["jud_id"] for p in pre], "swcd": [p["swcd"] or None for p in pre],
            "hospital": [p["hosp"] or None for p in pre], "park": [p["park_id"] for p in pre]}
    mask = []
    for r, l in sides:
        m = 0
        for bit, kind in enumerate(ARC_KINDS):
            v = vals[kind]
            if (v[r] if r >= 0 else None) != (v[l] if l >= 0 else None):
                m |= 1 << bit
        mask.append(m)

    # ---- school districts: their own lines, and which precincts they reach
    srows = sorted(mdoc["rows"], key=lambda r: (r[0]["sdtype"], r[0]["sdnumber"]))
    skeys = []
    for a, _rings in srows:
        if a["sdtype"] not in SCHOOL_TYPE or not re.fullmatch(r"\d{4}", a["sdnumber"] or ""):
            raise GeoError(f"    school districts: type {a['sdtype']!r} number {a['sdnumber']!r} is not one this builder was checked against; stopping")
        skeys.append(SCHOOL_TYPE[a["sdtype"]] + a["sdnumber"])
    if len(set(skeys)) != len(skeys):
        raise GeoError("    school districts: two rows share a type and number; stopping")
    sname = {k: names.get(("school", k)) or f"{a['prefname']} ({SCHOOL_WORD[a['sdtype']]} #{int(a['sdnumber'])})" for k, (a, _r) in zip(skeys, srows)}
    spolys = [[k for k in (clean_ring(r) for r in rings) if k] for _a, rings in srows]
    sarcs, ssides, srings_of, sodd = topology(spolys)
    sfine, _ = simplify_arcs(sarcs, srings_of, TOL_SCHOOL)
    say(f"      {len(skeys)} school districts, {len(sarcs):,} lines between them ({sum(len(a) for a in sarcs):,} points)" + (f"; odd: {dict(sodd)}" if sodd else ""))
    stamp = hashlib.sha256(json.dumps([sha_file(vpath), sha_file(mpath), TOL_PRECINCT, TOL_SCHOOL, SCHOOL_THICK, 2]).encode()).hexdigest()
    overlay = overlay_cached([[ring_xy(refs, fine) for refs in rings] for rings in rings_of],
                             [[ring_xy(refs, sfine) for refs in rings] for rings in srings_of], stamp,
                             os.path.join(CACHE, "mn_geo_school_overlay.json"), refresh, say)
    split = thin_only = none = edges = 0
    partly = []
    for p, got in zip(pre, overlay):
        keep = [(skeys[d], share) for d, share, thick in got if thick[0]]
        if not keep and got:                             # a precinct too small for the thickness test: its main district, if it has one
            best = max(((skeys[d], share) for d, share, _t in got), key=lambda x: x[1])
            if best[1] >= 0.5:
                keep = [best]
                thin_only += 1
        keep.sort(key=lambda x: (-x[1], x[0]))
        outside = max(0.0, 1.0 - sum(share for _d, share, _t in got))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside >= 0.03) else None
        p["school_out"] = round(100 * outside, 1) if outside >= 0.03 else None
        p["school_edge"] = sorted({skeys[d] for d, _s, _t in got} - set(p["school"]))
        split += len(keep) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(keep) < 2
        if outside >= 0.03:
            partly.append(f"{p['name']} ({p['countyname']}) {100 * outside:.0f}%")
    say(f"      school districts by precinct: {split:,} precincts are split between two or more, {none} lie in none, {edges:,} others only brush "
        f"a neighbouring district along a line" + (f"; {thin_only} have only a thin overlap (the largest is kept)" if thin_only else "")
        + (f"; partly outside every district: {', '.join(partly[:8])}" if partly else ""))

    # ---- write: into a folder beside the real one, moved into place only when everything is written, so a build
    # that stops halfway leaves the last good folder as it was
    final, out = out, out.rstrip("\\/") + ".part"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    files, today = {}, dt.date.today().isoformat()

    def put(rel, doc):
        size, sha = write_json(os.path.join(out, *rel.split("/")), doc)
        files[rel] = {"bytes": size, "sha256": sha}
        return size

    # layers
    swcd = {}
    for p in pre:
        if p["swcd"]:
            e = swcd.setdefault(p["swcd"], {"name": p["swcd_n"], "counties": set()})
            e["counties"].add(p["county"])
    per_county = collections.defaultdict(list)
    for code, e in swcd.items():
        if len(e["counties"]) != 1:
            raise GeoError(f"    soil and water district {code} ({e['name']}) reaches {len(e['counties'])} counties; this builder expects one; stopping")
        e["county"] = next(iter(e["counties"]))
        m = SWCD_BY_DISTRICT.match(e["name"])
        e["d"] = str(int(m.group(2))) if m else None
        per_county[e["county"]].append(code)
    for code, e in swcd.items():
        whole = [c for c in per_county[e["county"]] if swcd[c]["d"] is None]
        e["jn"] = f"{e['name']} (soil and water district)" if e["d"] is None and len(whole) > 1 else None
    hosp = {p["hosp"]: p["hosp_n"] for p in pre if p["hosp"]}
    park = {p["park_id"]: (p["park_n"], str(int(p["parkcode"]))) for p in pre if p["park_id"]}
    jud_name = lambda j: names.get(("judicial", j)) or f"{ordinal(j[2:])} Judicial District"   # noqa: E731

    def ward_props(v):
        mcd, d = v.split("|", 1)
        pr = {"id": v, "name": f"{mname[mcd]}, {d}", "j": mcd, "d": d}
        if (mcd, d) in joined:
            pr["of"] = [f"{mcd}|{label[(mcd, c)]}" for c in joined[(mcd, d)]]
        return pr

    def swcd_props(v):
        e = swcd[v]
        pr = {"id": v, "name": e["name"], "j": e["county"], "d": e["d"]}
        if e["jn"]:
            pr["jn"] = e["jn"]
        return pr

    joined_vals = []
    for (mcd, s), codes in sorted(joined.items()):
        joined_vals.append([f"{mcd}|{s}" if p["mcd"] == mcd and p["wardcode"] in codes else None for p in pre])
    specs = [
        ("state", [["MN"] * len(pre)], TOL_WIDE, lambda v: {"id": "MN", "name": "Minnesota", "j": "MN", "d": None}),
        ("county", [vals["county"]], TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": "27" + v}),
        ("cd", [vals["cd"]], TOL_WIDE, lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-MN-H{int(v):02d}"}),
        ("senate", [vals["senate"]], TOL_WIDE, lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": "MN", "d": v}),
        ("house", [vals["house"]], TOL_WIDE, lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": "MN", "d": v}),
        ("judicial", [vals["judicial"]], TOL_WIDE, lambda v: {"id": v, "name": jud_name(v), "j": v, "d": v[2:]}),
        ("mcd", [vals["mcd"]], TOL_LOCAL, lambda v: {"id": v, "name": mname[v], "j": v, "d": None}),
        ("ward", [vals["ward"]] + joined_vals, TOL_LOCAL, ward_props),
        ("com", [vals["com"]], TOL_LOCAL, lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Commissioner District {v.split('|')[1]}",
                                                     "j": v.split("|")[0], "d": v.split("|")[1]}),
        ("swcd", [vals["swcd"]], TOL_LOCAL, swcd_props),
        ("hospital", [vals["hospital"]], TOL_LOCAL, lambda v: {"id": v, "name": hosp[v], "j": v, "d": None, "jn": f"{hosp[v]} (hospital district)"}),
        ("park", [vals["park"]], TOL_LOCAL, lambda v: {"id": v, "name": f"{park[v][0]}, District {park[v][1]}", "j": v.split("|")[0], "d": park[v][1]}),
    ]
    layers, shape_ids = [], {}
    for kind, value_sets, tol, props in specs:
        geoms, qlines, loose, _rest = build_layer(arcs, sides, value_sets, tol)
        gl = []
        for v, polys in sorted(geoms, key=lambda x: natkey(x[0])):
            pr = props(v)
            gl.append({"id": pr.pop("id"), "properties": pr, "polys": polys, "label": True})
        doc, dropped, _pts = topo_doc({kind: gl}, qlines)
        doc["kind"], doc["tolerance_m"] = kind, tol
        size = put(f"layers/{kind}.json", doc)
        empty = [g["id"] for g in doc["objects"][kind]["geometries"] if g["type"] is None]
        if empty or loose:
            say(f"      layer {kind}: {len(empty)} shapes with no outline ({', '.join(empty[:5])}), {loose} rings that would not close")
        shape_ids[kind] = {g["id"]: g["properties"] for g in doc["objects"][kind]["geometries"]}
        layers.append({"kind": kind, "file": f"layers/{kind}.json", "bytes": size, "shapes": len(gl), "tolerance_m": tol, "good_to_zoom": zoom_for(tol)})

    # school districts: the overview layer, and each district at full detail
    sgeoms, sq, _loose, _rest = build_layer(sarcs, ssides, [skeys], TOL_LOCAL)
    gl = [{"id": v, "properties": {"name": sname[v], "j": v, "d": None}, "polys": polys, "label": True} for v, polys in sorted(sgeoms, key=lambda x: natkey(x[0]))]
    doc, _dropped, _pts = topo_doc({"school": gl}, sq)
    doc["kind"], doc["tolerance_m"] = "school", TOL_LOCAL
    size = put("layers/school.json", doc)
    shape_ids["school"] = {g["id"]: g["properties"] for g in doc["objects"]["school"]["geometries"]}
    layers.append({"kind": "school", "file": "layers/school.json", "bytes": size, "shapes": len(gl), "tolerance_m": TOL_LOCAL, "good_to_zoom": zoom_for(TOL_LOCAL)})
    dgeoms, dq, _l, _r = build_layer(sarcs, ssides, [skeys], TOL_SCHOOL)
    school_bytes = 0
    for v, polys in dgeoms:
        doc, _dropped, _pts = topo_doc({"school": [{"id": v, "properties": {"name": sname[v], "j": v, "d": None}, "polys": polys, "label": True}]}, dq)
        doc["kind"], doc["tolerance_m"] = "school", TOL_SCHOOL
        school_bytes += put(f"school/{v}.json", doc)

    # county files
    by_county = collections.defaultdict(list)
    for i, p in enumerate(pre):
        by_county[p["county"]].append(i)
    counties, boxes, pbox, dropped_rings = [], {}, {}, 0
    for county, idxs in sorted(by_county.items()):
        local = {i: n for n, i in enumerate(idxs)}
        geoms, used_names = [], {"mcd": {}, "swcd": {}, "hospital": {}, "park": {}, "school": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "mcd": p["mcd"], "com": p["com_id"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "judicial": p["jud_id"], "school": p["school"]}
            used_names["mcd"][p["mcd"]] = mname[p["mcd"]]
            if p["school_pct"]:
                pr["school_pct"] = p["school_pct"]
            if p["school_out"]:
                pr["school_out"] = p["school_out"]
            if p["school_edge"]:
                pr["school_edge"] = p["school_edge"]
            for k in p["school"] + p["school_edge"]:
                used_names["school"][k] = sname[k]
            if p["wards"]:
                pr["ward"] = p["wards"]
            if p["swcd"]:
                pr["swcd"] = p["swcd"]
                used_names["swcd"][p["swcd"]] = p["swcd_n"]
            if p["hosp"]:
                pr["hospital"] = p["hosp"]
                used_names["hospital"][p["hosp"]] = p["hosp_n"]
            if p["park_id"]:
                pr["park"] = p["park_id"]
                used_names["park"][p["park_id"]] = f"{park[p['park_id']][0]}, District {park[p['park_id']][1]}"
            geoms.append({"id": p["id"], "properties": pr, "polys": group_polys([(refs, ring_xy(refs, fine)) for refs in rings_of[i]]), "label": True})

        def more(used, county=county, local=local, used_names=used_names):
            am, asd = [], []
            for a in used:
                am.append(mask[a])
                for side in sides[a]:
                    asd.append(local[side] if side in local else (-2 if side < 0 else -1))
            return {"county": county, "fips": "27" + county, "name": cname[county], "arcKinds": ARC_KINDS, "arcMask": am, "arcSides": asd,
                    "names": {k: dict(sorted(v.items())) for k, v in used_names.items() if v}}

        doc, dropped, pts = topo_doc({"precincts": geoms}, qfine, more)
        dropped_rings += dropped
        bx = []
        for g in geoms:
            polys_pts = pts[("precincts", g["id"])]
            if not polys_pts:
                raise GeoError(f"    precinct {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // BOX_STEP, min(ys) // BOX_STEP, -(-max(xs) // BOX_STEP), -(-max(ys) // BOX_STEP)]
            pbox[g["id"]] = lonlat((min(xs), min(ys))) + lonlat((max(xs), max(ys)))
        boxes[county] = bx
        rel = f"precincts/27{county}.json"
        size = put(rel, doc)
        counties.append({"id": county, "fips": "27" + county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(out, pre, put, say, polls_dir, pbox)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids, swcd)
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)

    def said(about, *keys):                               # what the publisher says: the date, the use limits, the disclaimer
        return {k: about.get(k) for k in keys if about.get(k)}

    index = {
        "v": VERSION, "state": "MN", "election": ELECTION, "built": today,
        "transform": {"scale": [SCALE, SCALE], "translate": [ORIGIN[0], ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": "mn-sos-voting-districts-lines", "agency": "Office of the Minnesota Secretary of State, Elections Division; published on the Minnesota Geospatial Commons",
                  "title": about_v.get("title") or "Voting Districts, Minnesota", "about": about_v.get("snippet"), "url": VTD_ITEM, "service": VTD_SERVICE,
                  "fetched": vdoc.get("fetched"), "sha256": sha_file(vpath), "rows": len(pre)},
                 **said(about_v, "published", "current_to", "use", "disclaimer", "metadata")),
            dict({"id": "mn-mde-school-district-lines", "agency": "Minnesota Department of Education; published on the Minnesota Geospatial Commons",
                  "title": about_m.get("title") or "School District Boundaries, Minnesota, SY2025-26", "about": about_m.get("snippet"), "url": MDE_ITEM,
                  "service": MDE_SERVICE, "fetched": mdoc.get("fetched"), "sha256": sha_file(mpath), "rows": len(skeys)},
                 **said(about_m, "published", "current_to", "use", "disclaimer", "metadata")),
            {"id": "mn-crystal-charter", "agency": "City of Crystal", "title": "City Charter, section 2.04 (which wards make up each council section)",
             "url": CRYSTAL_CHARTER, "fetched": "2026-10-01", "sha256": "1849de9a83459044a6861d9d1ef6aa02319d090894bddcbb0a6f026fca7ef061", "rows": 2}],
        "notes": {
            "lines": f"Every precinct line is the Secretary of State's, generalised by at most {TOL_PRECINCT} metres and set on a grid of 0.00001 degree "
                     "(about a metre); every other district is put together from whole precincts, so its outline is the precincts' own lines. "
                     "A point within a few metres of a line can fall on either side of it.",
            "school": "School district lines are the Department of Education's own compilation, which the Department calls generalised and "
                      "not the legal lines for taxation. Which districts a precinct lies in is analysis, not an official list: a district "
                      f"counts when its part of the precinct is at least {SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's "
                      "share of the precinct's area (land and water, not voters).",
            "authority": "For which precinct an address votes in, and where, the Secretary of State's Polling Place Finder and the county's sample ballot are the authority.",
            "disclaimers": "The Secretary of State's notice says any copy of its data, or of part of it, must carry its disclaimer; the "
                           "Department of Education asks that its limits travel with its data too. Both are under sources, word for word, "
                           "and belong on the page that shows this map.",
            "precinct_ids": "A precinct's id is the Secretary's VTDID: 27, the county's three-digit FIPS code, and the four-digit precinct code "
                            "the Secretary's results files use (their county ID is (FIPS + 1) / 2).",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/27<county>.json, object 'precincts': one shape per precinct, id = VTDID. arcMask[i] has bit k set when "
                            "line i is an outline of arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left "
                            "of line i (-1: a precinct in another county's file, -2: outside Minnesota); names gives the names of the "
                            "places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step "
                     "degrees from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened "
                     "by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name", "county": "county id", "mcd": "city, township or unorganized territory",
                                    "ward": "list: the council districts the precinct lies in (absent where the city has none)",
                                    "com": "county commissioner district", "house": "state House district", "senate": "state Senate district",
                                    "cd": "congressional district", "judicial": "judicial district", "swcd": "soil and water district (absent in Hennepin and Ramsey)",
                                    "hospital": "hospital district (absent outside one)", "park": "park district (absent outside one)",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is split: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "county": "the county's three-digit code (001)", "mcd": "the place's five-digit code (00172)",
                    "ward": "<place>|<district as the council race words it> (00694|Ward 2)", "com": "<county>|<district> (001|1)",
                    "house": "the district (1A)", "senate": "the district (1)", "cd": "the district (1); properties.race is the race for Congress",
                    "judicial": "JD and the district (JD1)",
                    "swcd": "the Secretary's four-digit code; d is the supervisor district where supervisors are elected by district, and "
                            "jn is the jurisdiction's name on the ballot pages where a county has two soil and water districts",
                    "hospital": "HD and the district's code (HD00310)", "park": "<county or city>|<district> (053|1)",
                    "school": "the district's type and number (ISD0001)"},
        },
        "counties": counties, "box_step": BOX_STEP * SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(skeys, key=natkey), "bytes": school_bytes, "tolerance_m": TOL_SCHOOL},
        "tolerance_m": {"precincts": TOL_PRECINCT, "school": TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "polling_places": polls,
        "counts": {"precincts": len(pre), "counties": len(counties), "split_between_school_districts": split,
                   "rings_too_small_for_the_grid": dropped_rings},
        "check": check,
    }
    put("index.json", index)
    manifest = {"v": VERSION, "built": today, "files": dict(sorted(files.items()))}
    write_json(os.path.join(out, "manifest.json"), manifest)
    total = sum(f["bytes"] for f in files.values()) + os.path.getsize(os.path.join(out, "manifest.json"))
    os.makedirs(final, exist_ok=True)
    clear_out(final)
    for rel in list(files) + ["manifest.json"]:
        dst = os.path.join(final, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(os.path.join(out, *rel.split("/")), dst)
    shutil.rmtree(out)
    say(f"      {len(counties)} county files ({sum(c['bytes'] for c in counties) / 1e6:.1f} MB), {len(layers)} layers "
        f"({sum(l['bytes'] for l in layers) / 1e6:.1f} MB), {len(skeys)} school district files ({school_bytes / 1e6:.1f} MB), "
        f"index {files['index.json']['bytes'] / 1e3:.0f} KB; {total / 1e6:.1f} MB in all, in {final}")
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Minnesota races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    for mcd, s in sorted(ward_unmatched):
        if f"{mcd}|{s}" not in shape_ids["ward"]:
            say(f"      a council district with no ward to draw: {mname.get(mcd, mcd)}, {s}")
    say(f"    Minnesota ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point lies in, and a word its school district's name must carry. The three
    # buildings stand where OpenStreetMap puts them; the town hall is where the Census Bureau's geocoder puts its
    # street address (25043 Cedar Avenue). What each point lies in is the Census Bureau's geocoder's answer for those
    # coordinates (county, county subdivision, congressional and 2026 legislative districts, school district; asked
    # 2026-10-01), an answer that owes nothing to the files tested here. The judicial district is the county's, by statute.
    ("the State Capitol, St. Paul", -93.10222, 44.95519,
     {"county": "123", "mcd": "58000", "cd": "4", "senate": "65", "house": "65B", "judicial": "JD2", "school": "ISD0625"}, "Paul"),
    ("Duluth City Hall", -92.105276, 46.783857,
     {"county": "137", "mcd": "17000", "cd": "8", "senate": "8", "house": "8A", "judicial": "JD6", "school": "ISD0709"}, "Duluth"),
    ("Rochester City Hall", -92.459438, 44.020409,
     {"county": "109", "mcd": "54880", "cd": "1", "senate": "25", "house": "25B", "judicial": "JD3", "school": "ISD0535"}, "Rochester"),
    ("Eureka Town Hall, a rural township hall in Dakota County", -93.217969, 44.583277,
     {"county": "037", "mcd": "19871", "cd": "2", "senate": "57", "house": "57A", "judicial": "JD1", "school": "ISD0194"}, "Lakeville"),
]
LINE_POINT = ("the Hennepin-Ramsey county line, in the Mississippi under the Lake Street-Marshall Avenue bridge", -93.2024, 44.9484, ("053", "123"))


class Files:
    """The built folder, read the way a page reads it: the index first, then only the files a point needs."""

    def __init__(self, root):
        self.root = root
        self.cache = {}
        self.index = self.load("index.json")

    def load(self, rel):
        with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8") as fh:
            return json.load(fh)

    def topo(self, rel):
        if rel not in self.cache:
            doc = self.load(rel)
            lines = []
            for arc in doc["arcs"]:
                x = y = 0
                pts = []
                for dx, dy in arc:
                    x += dx
                    y += dy
                    pts.append((x, y))
                lines.append(pts)
            self.cache[rel] = (doc, lines)
        return self.cache[rel]


def geom_polys(lines, geom):
    """A geometry's polygons, each a list of rings (outer first), each ring grid points without the closing one."""
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]] if geom["type"] == "Polygon" else []
    out = []
    for poly in polys:
        rings = []
        for refs in poly:
            pts = []
            for r in refs:
                a = lines[r] if r >= 0 else lines[~r][::-1]
                pts.extend(a if not pts else a[1:])
            rings.append(pts[:-1])
        out.append(rings)
    return out


def to_grid(lon, lat):
    return (lon - ORIGIN[0]) / SCALE, (lat - ORIGIN[1]) / SCALE


def edge_metres(x, y, rings):
    """Metres from a grid point to the nearest edge of any of the rings."""
    c = math.cos(math.radians(y * SCALE + ORIGIN[1]))
    best = float("inf")
    for pts in rings:
        ax, ay = pts[-1]
        for bx, by in pts:
            d = seg_dist2(x * c, y, ax * c, ay, bx * c, by)
            if d < best:
                best = d
            ax, ay = bx, by
    return math.sqrt(best) * SCALE * 111320.0


def locate(files, lon, lat):
    """The precinct at a point: (found, near). found is None or a dict (county, i, geometry, edge = metres to the
    precinct's nearest line); near lists the other precincts whose line is within NEAR_M metres. A point that falls
    in no precinct (on a line, in a hairline gap) is given to the nearest one within NEAR_M."""
    x, y = to_grid(lon, lat)
    bx, by = x / BOX_STEP, y / BOX_STEP
    found, near = None, []
    for county, b in sorted(files.index["boxes"].items()):
        for i in range(0, len(b), 4):
            if b[i] - 0.5 <= bx <= b[i + 2] + 0.5 and b[i + 1] - 0.5 <= by <= b[i + 3] + 0.5:
                doc, lines = files.topo(f"precincts/27{county}.json")
                g = doc["objects"]["precincts"]["geometries"][i // 4]
                rings = [r for poly in geom_polys(lines, g) for r in poly]
                hit = {"county": county, "i": i // 4, "geometry": g, "edge": edge_metres(x, y, rings)}
                if found is None and in_rings(x, y, rings):
                    found = hit
                elif hit["edge"] <= NEAR_M:
                    near.append(hit)
    if found is None and near:
        near.sort(key=lambda h: h["edge"])
        found = near.pop(0)
    return found, near


def shape_at(files, kind, lon, lat, rel=None):
    """The shape of a layer at a point: (geometry, metres to its nearest line), or (None, None)."""
    doc, lines = files.topo(rel or f"layers/{kind}.json")
    x, y = to_grid(lon, lat)
    for g in doc["objects"][kind]["geometries"]:
        bb = g.get("bbox")
        if not bb or not (bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]):
            continue
        rings = [r for poly in geom_polys(lines, g) for r in poly]
        if in_rings(x, y, rings):
            return g, edge_metres(x, y, rings)
    return None, None


def school_at(files, precinct, lon, lat):
    """The school district at a point whose precinct is known: at once where the precinct lies in one district and
    touches no other; else the districts it lies in, then the ones it only brushes, tried against their own lines.
    None: in no school district, or too near a line to say."""
    pr = precinct["properties"]
    todo = list(pr.get("school", [])) + list(pr.get("school_edge", []))
    if len(todo) == 1 and not pr.get("school_out"):
        return todo[0]
    x, y = to_grid(lon, lat)
    for sid in todo:
        doc, lines = files.topo(f"school/{sid}.json")
        if in_rings(x, y, [r for poly in geom_polys(lines, doc["objects"]["school"]["geometries"][0]) for r in poly]):
            return sid
    return None


def selftest(out=OUT, say=print):
    """Reads only the built files. Returns True when everything holds."""
    files = Files(out)
    index, fails = files.index, []

    def check(ok, what):
        if not ok:
            fails.append(what)
            say(f"      FAIL: {what}")
        return ok

    # 1. the files are all there and say what the index says; every line knows which precincts lie on its two sides,
    #    and is marked as an outline of exactly the kinds of district that differ across it
    total = bad_side = bad_mask = lines_seen = 0

    def own(geom, kind):                                  # a precinct's own district of a kind (its own ward is the first in the list)
        v = geom["properties"].get(kind)
        return v[0] if isinstance(v, list) else v

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
                    for r in refs:                         # rings run with the shape on their left: forwards along a line, the shape is its left side
                        bad_side += sides_[2 * r + 1 if r >= 0 else 2 * ~r] != gi
        for a in range(len(lines)):
            r, l = sides_[2 * a], sides_[2 * a + 1]
            lines_seen += 1
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
        f"(county lines counted in both counties), sides and outline marks all in order")

    # 2. every precinct is found again from a point inside it, through the index's boxes and its county's file;
    #    and that point's school district, settled from the district's own lines, is one the precinct names
    wrong, tested, agree, skipped, disagree = 0, 0, 0, 0, []
    school = collections.Counter()
    layer_for = {"county": "county", "mcd": "mcd", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com"}
    for c in index["counties"]:
        doc, lines = files.topo(c["file"])
        for i, g in enumerate(doc["objects"]["precincts"]["geometries"]):
            polys = geom_polys(lines, g)
            px, py = label_point(polys[0])
            lon, lat = px * SCALE + ORIGIN[0], py * SCALE + ORIGIN[1]
            found, _near = locate(files, lon, lat)
            tested += 1
            if not found or found["geometry"]["id"] != g["id"]:
                wrong += 1
            sid = school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in g["properties"]["school"] else
                   "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if g["properties"].get("school_out") else "in none"] += 1
            if i % 10 == 0:                              # and the layers agree with the precinct, away from their lines
                for prop, kind in layer_for.items():
                    shape, edge = shape_at(files, kind, lon, lat)
                    tol = next(l["tolerance_m"] for l in index["layers"] if l["kind"] == kind)
                    if shape is None or edge <= tol + 10:
                        skipped += 1
                    elif shape["id"] == g["properties"][prop]:
                        agree += 1
                    else:
                        disagree.append((g["id"], kind, shape["id"], g["properties"][prop]))
    check(wrong == 0, f"{wrong} of {tested} precincts are not found again from a point inside them")
    check(not disagree, f"{len(disagree)} layer shapes disagree with the precinct at a point well inside them, e.g. {disagree[:3]}")
    check(school["in none"] <= 2, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; layers agree at {agree:,} points "
        f"({skipped} too near a line to ask); school district at each precinct's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])))

    # 3. five known points
    for name, lon, lat, want, school_word in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want if k != "school"}
        ok = check(got == {k: v for k, v in want.items() if k != "school"}, f"{name}: lands in {got}, not {want}")
        ok &= check(want["school"] in pr["school"], f"{name}: school districts {pr['school']}, not {want['school']}")
        sdoc, _slines = files.topo(f"school/{want['school']}.json")
        sname = sdoc["objects"]["school"]["geometries"][0]["properties"]["name"]
        ok &= check(school_at(files, found["geometry"], lon, lat) == want["school"] and school_word in sname,
                    f"{name}: the school district at the point is {school_at(files, found['geometry'], lon, lat)}, not {want['school']} ({sname})")
        for prop, kind in layer_for.items():
            shape, _edge = shape_at(files, kind, lon, lat)
            ok &= check(shape is not None and shape["id"] == pr[prop], f"{name}: layer {kind} gives {shape and shape['id']}, the precinct says {pr[prop]}")
        fdoc, _l = files.topo(f"precincts/27{found['county']}.json")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: precinct {pr['name']} ({found['geometry']['id']}), {fdoc['names']['mcd'][pr['mcd']]}, "
            f"{fdoc['name']}, commissioner district {pr['com'].split('|')[1]}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, "
            f"{pr['judicial']}, {', '.join(pr['school'])}" + (f", {', '.join(pr['ward'])}" if pr.get("ward") else "")
            + f"; {found['edge']:.0f} m from the precinct's line")

    # 4. a point on a county line: the bridge, and the exact spot on the line nearest to it
    name, lon, lat, pair = LINE_POINT
    found, _near = locate(files, lon, lat)
    check(found is not None and found["county"] in pair, f"{name}: lands in {found and found['county']}")
    doc, lines = files.topo(f"precincts/27{pair[0]}.json")
    bit = 1 << doc["arcKinds"].index("county")
    x, y = to_grid(lon, lat)
    c = math.cos(math.radians(lat))
    best = None
    for a, pts in enumerate(lines):
        if doc["arcMask"][a] & bit:
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                d = seg_dist2(x * c, y, ax * c, ay, bx * c, by)
                if best is None or d < best[0]:
                    best = (d, (ax + bx) / 2.0, (ay + by) / 2.0)
    on = (best[1] * SCALE + ORIGIN[0], best[2] * SCALE + ORIGIN[1])
    f2, n2 = locate(files, on[0], on[1])
    sides_ = {f2["county"]} | {h["county"] for h in n2} if f2 else set()
    ok = check(f2 is not None and f2["edge"] < 1.0 and sides_ == set(pair),
               f"a point exactly on the {pair[0]}/{pair[1]} line lands in {f2 and f2['county']} with {sorted(sides_)} at hand, {f2 and round(f2['edge'], 2)} m from the line")
    if found and f2:
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: the bridge point is in {found['geometry']['properties']['name']} "
            f"(county {found['county']}), {math.sqrt(best[0]) * SCALE * 111320.0:.0f} m from the line; the spot exactly on the line "
            f"({on[0]:.5f}, {on[1]:.5f}) is given to {f2['geometry']['properties']['name']} (county {f2['county']}) with "
            f"{', '.join(sorted(h['geometry']['properties']['name'] for h in n2))} across it")

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
    ap = argparse.ArgumentParser(description="The geography behind Minnesota's ballot map -> ballot_geo/mn/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/mn)")
    ap.add_argument("--db", default=DB, help="ballot database to read names and council districts from, read-only")
    ap.add_argument("--polls", default=None, help="folder to look for the saved polling place list in (default: states_cache/mn_local/sos/pollingplaces)")
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
