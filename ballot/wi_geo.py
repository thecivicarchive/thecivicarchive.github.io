"""
ballot/wi_geo.py - the geography behind Wisconsin's ballot map, in the same files and formats ballot/mn_geo.py writes
for Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and changes nothing in
it), so the same page and the same reader (ballot/mn_geo_reader.js) read both.

    python ballot/wi_geo.py                 builds ballot_geo/wi/ and runs the self-test (about fifteen minutes the
                                            first time, most of it laying districts over wards; about three after)
    python ballot/wi_geo.py --selftest      runs the self-test on the files already built
    python ballot/wi_geo.py --refresh       asks the map services again even when the cached copies are fresh
    python ballot/wi_geo.py --out DIR       builds somewhere else (a trial run)
    python ballot/wi_geo.py --polls DIR     looks for the saved polling place list in another folder (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

What Wisconsin calls things. The smallest piece of a Wisconsin ballot map is the municipal WARD (what Minnesota calls
a precinct): the files' "precincts" are wards. A city's council districts are ALDERMANIC DISTRICTS (the files' "ward"
kind, as in Minnesota, where a ward is a council district), and a county board's are SUPERVISORY DISTRICTS (the "com"
kind). Clerks report results by reporting unit, which is one ward or several together; that is not geography and is
not here.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/wi_local/)
----------------------------------------------------------------------------------------------------------------------
  - Wards: the Wisconsin Legislature's Legislative Technology Services Bureau (LTSB), "WI Municipal Wards (July 2026)",
    its twice-yearly collection from the 72 county clerks under Wis. Stat. 5.15(4)(br) (gis-ltsb.hub.arcgis.com). Each
    ward carries its county, its city, village or town, its county supervisory district and its aldermanic district.
    Only those columns and the date the county sent them are asked for; the layer's CONTACT column (a county office's
    e-mail) is never requested.
  - Assembly and Senate districts: LTSB, "WI Assembly Districts (2024)" (2023 Wisconsin Act 94; each row names its
    Senate district). Congressional districts: LTSB, "WI Congressional Districts (2022)" (the lines in force since
    Johnson v. Wisconsin Elections Commission, 2022). The ward table no longer says which of these a ward lies in, so
    that is worked out here by laying the districts over the wards (analysis: the district holding most of the ward;
    a ward with 3 percent or more in a second district is marked "split" and listed in index.json).
  - School districts: the Department of Public Instruction, "School Districts, Wisconsin" (data-wi-dpi.opendata.
    arcgis.com). Wisconsin has three kinds: unified (K-12), elementary (K-8) and union high school districts; a union
    high school district lies over the elementary districts that feed it, so a ward there is in two districts at once.
  - Counties, and the state's outline: the Census Bureau's TIGER/Line 2025 county subdivisions of Wisconsin
    (tl_2025_55_cousub.zip), put together by county, with the "not defined" subdivisions (the Great Lakes) left out.
    They are used for the far-out county, state and Court of Appeals layers only, because the counties' own ward
    lines do not meet point for point along county lines (see "County lines" below). They also give each city,
    village and town its Census name ("Albion town"), which is how sl_places names them.
  - Court of Appeals districts: Wis. Stat. 752.11(1), read from docs.legis.wisconsin.gov (which counties make up each
    of the four districts, and the three two-county circuits).
  - The Wisconsin Elections Commission's site (elections.wi.gov) answers scripts with a Cloudflare challenge and is
    never asked for anything here. Polling places are read only from a file John saves: see POLLING PLACES.

County lines. Inside a county the wards fit together point for point (the county sent them as one fabric). Across a
county line they usually do not: each county drew the line itself, and the two drawings differ by a few metres (four
fifths of the differences are under 5 m; a few reach tens of metres, mostly along rivers). So in the county files a
line on a county's edge has the county's ward on one side and -1 (another county's ward, in another file) or -2
(nothing: the state line, a lake) on the other, and which districts' outlines run along it is worked out from the
ward found just across it. A point in the sliver between two counties' drawings is given to the nearest ward within
30 metres, as a point on any line is. The far-out layers that would show every county line as a seam (state, county,
Court of Appeals, Congress, Senate, Assembly) are therefore drawn from sources that are one fabric statewide (the
Census Bureau's and LTSB's own district files); the local layers (cities, villages and towns; aldermanic and
supervisory districts) are put together from the wards.

What is built (ballot_geo/wi/): index.json, manifest.json, precincts/<county>.json (72; id = the ward's 14-digit
WARD_FIPS), layers/<kind>.json (state, county, cd, senate, house, judicial, mcd, ward, com, school), school/<id>.json,
polling_places.json and reader.js, each as ballot/mn_geo.py describes. Coordinates are on the same grid (0.00001
degree, translate [-98, 43]).

Ids (the ballot database's own; a county is its five-digit code under the local conventions)
---------------------------------------------------------------------------------------------
  state     "WI" (j = "55", the jurisdiction_id of statewide races)
  county    "55025"                 sl_places county id; jurisdiction_id of county offices
  mcd       "WI-M-48000"            WI-M- and the Census county subdivision code (sl_places mcd id)
  ward      "WI-M-48000|District 5" an aldermanic district: <city>|District <number>
  com       "55025|37"              <county>|<supervisory district>
  house     "76"   senate "26"   cd "2" (properties.race is the federal race id, 2026-WI-H02)
  judicial  "CA4"                   the Court of Appeals district (d = "4"); properties.circuits names its circuits
  school    "WI-S-3269"             WI-S- and the Department's four-digit district code; properties.t is its kind

POLLING PLACES
--------------
No state page a script may read carries Wisconsin's polling places: the Elections Commission's site refuses scripts,
MyVote answers one address at a time, and LTSB and the state's open-data sites publish none. The Commission has posted
a spreadsheet of polling places before each election; when John has saved the November 3, 2026 one into
states_cache/wi_local/wec/pollingplaces/ (.xlsx, .csv or .txt) this builder reads it: columns are found by their
headings; only the county, the municipality, the wards or reporting unit, the place's name and street address and any
coordinates are kept. The reader was written before any such file had been seen, so its output is marked "unchecked",
which a page must not show, until a person has compared it with the file and set POLL_LAYOUT_CHECKED to True.
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
import zipfile
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402

GeoError = G.GeoError
STATE, FIPS = "WI", "55"
OUT = os.path.join(HERE, "ballot_geo", "wi")
CACHE = os.path.join(HERE, "states_cache", "wi_local")
POLL_DIR = os.path.join(CACHE, "wec", "pollingplaces")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS

LTSB = "https://services1.arcgis.com/FDsAtKBk8Hy4cAH0/arcgis/rest/services/"
DPI = "https://services8.arcgis.com/o4NJgD3NfeHnWy06/arcgis/rest/services/"
WARD_SERVICE = LTSB + "WI_Municipal_Wards_July/FeatureServer/0"
WARD_ITEM = "https://gis-ltsb.hub.arcgis.com/datasets/328b712cb66a420694ccbfe57aaffdda"
WARD_FIELDS = "WARD_FIPS,WARDID,CNTY_FIPS,CNTY_NAME,MCD_FIPS,COUSUBFP,MCD_NAME,CTV,SUPER_FIPS,SUPERID,ALDER_FIPS,ALDERID,DATE_SUB"   # never CONTACT
ASM_SERVICE = LTSB + "WI_Assembly_Districts_2024/FeatureServer/0"
ASM_ITEM = "https://gis-ltsb.hub.arcgis.com/datasets/55e24ed7087e4d0492381713d770eafb"
CD_SERVICE = LTSB + quote("WI_Congressional_Districts_(2022)") + "/FeatureServer/0"
CD_ITEM = "https://gis-ltsb.hub.arcgis.com/datasets/f42754138e2a4408810116e413e9947d"
SCHOOL_SERVICE = DPI + "Wisconsin_School_Districts/FeatureServer/9"
SCHOOL_ITEM = "https://data-wi-dpi.opendata.arcgis.com/datasets/f0829af06794426a88f32949234ec646"
COUSUB_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_55_cousub.zip"
STATUTE_URL = "https://docs.legis.wisconsin.gov/statutes/statutes/752/11"
FINDER = "https://myvote.wi.gov/en-us/Find-My-Polling-Place"
ELECTION = "2026-11-03"

ARC_KINDS = ["county", "mcd", "ward", "com", "house", "senate", "cd", "judicial"]
CTV_WORD = {"C": ("City", "city"), "V": ("Village", "village"), "T": ("Town", "town")}
SCHOOL_KIND = {"Unified": "unified (K-12)", "Elementary": "elementary (K-8)", "Secondary": "union high school"}
SPLIT_SHARE = 0.03                # a ward with this much of its area in a second district is marked split
SLIVER_M2 = 50.0                 # square metres: a ring of a ward smaller than this is digitising noise, and is left out
SEAM_M = 40.0                     # metres: another ward this close across a county's edge is the ward on the other side
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}
NEAR_M = G.NEAR_M


# ---------------------------------------------------------------- the sources

def fetch_full(service, fields, path, page, oid, refresh, say):
    """Every feature of one layer with its rings in longitude and latitude at full detail (as mn_geo.fetch_full, for a
    service whose row number has another name), cached as gzipped JSON."""
    if G._fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    try:
        rows, offset = [], 0
        while True:
            url = (f"{service}/query?where={quote('1=1')}&outFields={fields}&returnGeometry=true&outSR=4326&geometryPrecision=7"
                   f"&orderByFields={oid}&resultOffset={offset}&resultRecordCount={page}&f=json")
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
    with gzip.open(path + ".part", "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} shapes fetched")
    return out


def layer_edited(service, path, refresh):
    """The date the publisher last changed a layer (the service's own record), kept in a small cache."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    out = {}
    try:
        j = json.loads(net.get(service + "?f=json", accept="application/json"))
        ms = (j.get("editingInfo") or {}).get("dataLastEditDate") or (j.get("editingInfo") or {}).get("lastEditDate")
        if ms:
            out["current_to"] = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
    except Exception:  # noqa: BLE001  the lines do not depend on this record
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
    return out


def read_cousub(path):
    """The Census Bureau's county subdivisions: [(county, code, name, rings as vertex keys)], the undefined ones (open
    water) left out, in county and code order."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    out = []
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec["STATEFP"] != FIPS or rec["COUSUBFP"] == "00000":
            continue
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        rings = [k for k in (G.clean_ring(pts[parts[i]:parts[i + 1]]) for i in range(len(parts) - 1)) if k]
        out.append((FIPS + rec["COUNTYFP"], rec["COUSUBFP"], rec["NAMELSAD"], rings))
    out.sort(key=lambda x: (x[0], x[1]))
    if len({c for c, *_ in out}) != 72:
        raise GeoError(f"    {os.path.basename(path)}: {len({c for c, *_ in out})} counties, not 72; stopping")
    return out


def court_of_appeals(path, refresh, say):
    """Wis. Stat. 752.11(1): {"districts": {"1": [county names]}, "pairs": [[a, b]], "sha256", "fetched"}; the parsed
    answer is kept, and a statute that no longer reads the way this was checked against stops the build."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    try:
        raw = net.get(STATUTE_URL)
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path):
            say(f"      could not read Wis. Stat. 752.11 again ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        raise
    text = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", raw.decode("utf-8", "replace")))
    out = {"districts": {}, "pairs": [], "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat()}
    for m in re.finditer(r"District (I{1,3}|IV) consists of the judicial circuits? for (.*?) (?:County|counties)\.", text):
        d, body = ROMAN[m.group(1)], m.group(2)
        if d in out["districts"]:
            continue
        for a, b in re.findall(r"([A-Z][A-Za-z. ]+?) and ([A-Z][A-Za-z. ]+?) \(a combined 2-county circuit\)", body):
            out["pairs"].append([a.split(", ")[-1].strip(), b.strip()])
        body = body.replace("(a combined 2-county circuit)", "")
        out["districts"][d] = [n.strip() for n in re.split(r",| and ", body) if n.strip()]
    if sorted(out["districts"]) != ["1", "2", "3", "4"] or sum(len(v) for v in out["districts"].values()) != 72 or len(out["pairs"]) != 3:
        raise GeoError("    Wis. Stat. 752.11(1) no longer reads as four districts of 72 counties with three two-county circuits; stopping")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return out


def read_wards(doc):
    """The ward rows, in WARD_FIPS order, cut down to what the map needs, and their rings as vertex keys."""
    rows = sorted(doc["rows"], key=lambda r: r[0]["WARD_FIPS"])
    pre, polys, seen = [], [], set()
    for a, rings in rows:
        wid, county, cousub, wardid = (G.blank(a[k]) for k in ("WARD_FIPS", "CNTY_FIPS", "COUSUBFP", "WARDID"))
        ok = (re.fullmatch(r"55\d{3}", county) and re.fullmatch(r"\d{5}", cousub) and re.fullmatch(r"\d{3}[0-9A-Z]", wardid)
              and wid == county + cousub + wardid and wid not in seen and G.blank(a["CTV"]) in CTV_WORD
              and G.blank(a["SUPERID"]).isdigit() and G.blank(a["SUPER_FIPS"]) == county + G.blank(a["SUPERID"])
              and G.blank(a["ALDERID"]).isdigit() and G.blank(a["MCD_NAME"]))
        if not ok:
            raise GeoError(f"    ward table: the row for WARD_FIPS {wid!r} does not fit the layout this builder was checked against; stopping")
        seen.add(wid)
        alder = str(int(a["ALDERID"]))
        pre.append({"id": wid, "county": county, "countyname": G.blank(a["CNTY_NAME"]), "cousub": cousub, "mcd": f"{STATE}-M-{cousub}",
                    "mcdname": G.blank(a["MCD_NAME"]), "ctv": G.blank(a["CTV"]), "wardno": re.sub(r"^0+(?=.)", "", wardid),
                    "com": str(int(a["SUPERID"])), "alder": alder if alder != "0" else "", "sent": G.blank(a["DATE_SUB"]).split(" ")[0]})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    if len({p["county"] for p in pre}) != 72:
        raise GeoError(f"    ward table: {len({p['county'] for p in pre})} counties, not 72; stopping")
    kinds = collections.defaultdict(set)
    for p in pre:
        kinds[p["cousub"]].add((p["mcdname"].lower(), p["ctv"]))
    two = [c for c, v in kinds.items() if len(v) > 1]
    if two:
        raise GeoError(f"    ward table: the place code {two[0]} is used for two different places; stopping")
    return pre, polys


def settle_overlaps(pre, polys):
    """A few counties' files leave digitising noise that no map of wards can hold: a ring a few square metres in size
    lying along a neighbour's line, or two neighbours whose common line weaves so that for a few centimetres both run
    the same way along it (each then claims the same side of that line). Rings under SLIVER_M2 are left out, and where
    two wards still run the same way along a line, the later ward gives up the point that line ends at (its line moves
    by the length of that line, at most a few metres). Returns (rings left out, [(ward, points given up)])."""
    slivers = 0
    for rings in polys:
        if len(rings) > 1:
            keep = []
            for ks in rings:
                pts = [G.vxy(k) for k in ks]
                c = math.cos(math.radians(pts[0][1] / 1e7))
                if abs(G.area2(pts)) * c * G.M_PER_UNIT ** 2 / 2 < SLIVER_M2:
                    slivers += 1
                else:
                    keep.append(ks)
            if keep:
                rings[:] = keep
    gave = collections.Counter()
    for _pass in range(12):
        owner, drop = {}, collections.defaultdict(set)
        for i, rings in enumerate(polys):
            for n, ks in enumerate(rings):
                a = ks[-1]
                for b in ks:
                    o = owner.get((a, b))
                    if o is not None and o != i:
                        drop[(i, n)].add(b)
                    else:
                        owner[(a, b)] = i
                    a = b
        if not drop:
            break
        for (i, n), gone in drop.items():
            ks = [k for k in polys[i][n] if k not in gone]
            gave[pre[i]["id"]] += len(polys[i][n]) - len(ks)
            while len(ks) >= 3 and ks[0] == ks[-1]:
                ks.pop()
            polys[i][n] = ks if len(ks) >= 3 else None
        for rings in polys:
            rings[:] = [ks for ks in rings if ks]
    return slivers, sorted(gave.items())


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'wi-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


# ---------------------------------------------------------------- districts laid over wards

def rings_xy(polys):
    return [[[G.vxy(k) for k in ring] for ring in rings] for rings in polys]


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed: for each ward,
    [(district number, share of the ward's area, thick enough)]."""
    path = os.path.join(CACHE, f"wi_geo_overlay_{name}.json")
    if not refresh and os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
            if kept.get("stamp") == stamp and len(kept.get("rows", [])) == len(pre_rings):
                return kept["rows"]
        except (ValueError, OSError):
            pass
    say(f"      laying the {name} districts over the wards (some minutes; kept for the next build)")
    res = G.school_overlay(pre_rings, districts, levels=(G.SCHOOL_THICK,), say=None)
    rows = [[[d, round(share, 5), thick[0]] for d, share, thick in row] for row in res]
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    return rows


def assign(pre, overlay, keys, prop):
    """Each ward's district of one kind: the one holding most of it. Returns the wards split between two (a second
    district holds SPLIT_SHARE of the ward or more) and the wards no district touches."""
    split, none = [], []
    for p, got in zip(pre, overlay):
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


# ---------------------------------------------------------------- what lies across a county's edge

def across(arcs, sides, pre):
    """For each line with a ward on one side only: the other wards whose own one-sided lines run within SEAM_M metres
    of it (the wards across a county line, drawn a little differently by the other county). {line: set of wards};
    a line that is missing has nothing across it (the state line, a lake shore)."""
    cx, cy = 8000, 5000                                   # cells of about 60 by 55 metres, in 1e-7 degree
    grid = collections.defaultdict(list)
    lone = [a for a, (r, l) in enumerate(sides) if r < 0 or l < 0]
    for a in lone:
        w = max(sides[a])
        pts = [G.vxy(k) for k in arcs[a]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = (x0, y0, x1, y1, w)
            for gx in range(min(x0, x1) // cx, max(x0, x1) // cx + 1):
                for gy in range(min(y0, y1) // cy, max(y0, y1) // cy + 1):
                    grid[(gx, gy)].append(seg)
    lim2 = (SEAM_M / G.M_PER_UNIT) ** 2
    out = {}
    for a in lone:
        w = max(sides[a])
        pts = [G.vxy(k) for k in arcs[a]]
        if len(pts) > 2:                                  # the ends are corners, where a third ward's lines meet: ask along the line
            pts = pts[1:-1]
        step = max(1, len(pts) // 24)
        found = set()
        for x, y in pts[::step]:
            c = math.cos(math.radians(y / 1e7))
            best, who = lim2, None
            for gx in (x // cx - 1, x // cx, x // cx + 1):
                for gy in (y // cy - 1, y // cy, y // cy + 1):
                    for x0, y0, x1, y1, w2 in grid.get((gx, gy), ()):
                        if w2 == w:
                            continue
                        d = G.seg_dist2(x * c, y, x0 * c, y0, x1 * c, y1)
                        if d < best:
                            best, who = d, w2
            if who is not None:
                found.add(who)
        if found:
            out[a] = found
    return out


# ---------------------------------------------------------------- layers

def merged_layer(parts, tol):
    """One layer from several fabrics (each its own lines): parts = [(arcs, sides, values)]. Returns ([(value,
    polygons)], lines on the grid)."""
    geoms, lines = [], []
    for arcs, sides, vals in parts:
        g, q, _loose, _rest = G.build_layer(arcs, sides, [vals], tol)
        base = len(lines)
        lines.extend(q)
        for v, polys in g:
            geoms.append((v, [[[r + base if r >= 0 else ~(~r + base) for r in ring] for ring in poly] for poly in polys]))
    return geoms, lines


def check_ids(info, shape_ids):
    """Every Wisconsin race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape); a contest of a kind that rule does not place (a municipal court) is listed
    with the shape that does hold its place, where one does."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, _seat in sorted(info["races"]):
        hit, why = None, None
        d = re.sub(r"^0+(?=.)", "", str(district)) if district not in (None, "") else ""
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", d)
        elif kind == "state_house":
            hit = ("house", d)
        elif kind == "court_of_appeals":
            hit = ("judicial", "CA" + d)
        elif kind == "county_commissioner":
            hit = ("com", f"{jid}|{d}")
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township", "court") and str(jid).startswith(f"{STATE}-M-"):
            hit = ("ward", f"{jid}|{district}") if district else ("mcd", jid)
        elif level == "school":
            hit = ("school", jid)
        else:
            why = "no source carries a boundary for this kind of district (a court several municipalities share)"
        if hit and hit[1] in shape_ids.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places (from a file John saves)

POLL_WAITING = {
    "why": "Wisconsin publishes no statewide file of polling places that this site can read by itself: the Wisconsin Elections "
           "Commission's list has not been obtained yet. MyVote Wisconsin answers for one address at a time and is the authority.",
}
POLL_HOW = ("      polling places: waiting. No state page a script may read carries them (elections.wi.gov answers scripts with a Cloudflare "
            "challenge, which is never worked around). John: open elections.wi.gov in your own browser, search it for \"polling places\", and "
            "if the Commission has posted its spreadsheet of polling places for the November 3, 2026 General Election, save it (as it is: "
            ".xlsx or .csv) into states_cache/wi_local/wec/pollingplaces/ and run this again. If there is no such spreadsheet, say so: the "
            "other route is each municipal clerk's Type B notice, 1,850 of them.")
POLL_COLUMNS = {
    "county": [("county",)],
    "muni": [("municipality",), ("muni",)],
    "wards": [("reporting", "unit"), ("wards",), ("ward",)],
    "place": [("polling", "place", "name"), ("polling", "location"), ("poll", "name"), ("location", "name"), ("polling", "place"), ("facility",), ("location",)],
    "address": [("address", "1"), ("street",), ("address",)],
    "city": [("city",)],
    "zip": [("zip",), ("postal",)],
    "lat": [("lat",)],
    "lon": [("lon",), ("lng",)],
}
POLL_NEVER = ("phone", "email", "e mail", "contact", "clerk", "inspector", "owner")
POLL_LAYOUT_CHECKED = False       # set to True only when a person has compared the reader's output with a real list


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


def ward_numbers(text):
    """"Wards 1-3, 5 & 7A" -> ["1", "2", "3", "5", "7A"]; a text with no number -> []."""
    out = []
    for a, b in re.findall(r"(\d+[A-Z]?)(?:\s*-\s*(\d+))?", re.sub(r"(?i)^.*?\bwards?\b", "", text.upper(), count=1) if re.search(r"(?i)\bwards?\b", text) else ""):
        if b and a.isdigit() and int(b) >= int(a) and int(b) - int(a) < 400:
            out += [str(n) for n in range(int(a), int(b) + 1)]
        else:
            out.append(a.lstrip("0") or "0")
    return out


def read_polling_file(path, pre):
    """The Commission's polling place list, cut down on the spot to the wards, the place's name and street address
    and coordinates if the file gives them. Raises GeoError naming the check that failed (headings only, never a line)."""
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
    if not {"place", "county", "muni"} <= set(cols):
        raise GeoError(f"    {base}: the first line does not name a county, a municipality and a polling place (its headings: "
                       f"{'; '.join(str(h).strip() for h in rows[0])}); the reader needs to be told the layout")
    fold = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())      # noqa: E731
    by_muni = collections.defaultdict(dict)
    for p in pre:
        for key in ((fold(p["countyname"]), p["ctv"], fold(p["mcdname"])), (None, p["ctv"], fold(p["mcdname"]))):
            by_muni[key].setdefault(p["wardno"], []).append(p["id"])

    def cell(r, field):
        i = cols.get(field)
        return r[i].strip() if i is not None and i < len(r) else ""

    places, order, precinct, unmatched = {}, [], {}, 0
    for r in rows[1:]:
        m = re.match(r"(?i)\s*(city|village|town)\s+of\s+(.*?)\s*(?:-.*)?$", cell(r, "muni")) or re.match(r"(?i)\s*(.*?)\s*[-,]?\s*(city|village|town)\s*$", cell(r, "muni"))
        if not m:
            unmatched += 1
            continue
        kind, name = (m.group(1), m.group(2)) if m.group(1).lower() in ("city", "village", "town") else (m.group(2), m.group(1))
        wards = by_muni.get((fold(re.sub(r"(?i)\s+county$", "", cell(r, "county"))), kind[0].upper(), fold(name)))
        if not wards:
            unmatched += 1
            continue
        nums = ward_numbers(cell(r, "wards")) or sorted(wards)
        ids = [i for n in nums for i in wards.get(n, [])]
        place = re.sub(r"\s+", " ", cell(r, "place"))
        if not ids or not place:
            unmatched += 1
            continue
        key = (place.lower(), cell(r, "address").lower(), cell(r, "city").lower(), cell(r, "zip")[:5])
        if key not in places:
            places[key] = {"name": place, "address": re.sub(r"\s+", " ", cell(r, "address")), "city": cell(r, "city"), "zip": cell(r, "zip")[:5],
                           "type": None, "lonlat": None, "precincts": []}
            try:
                lon, lat = float(cell(r, "lon")), float(cell(r, "lat"))
                if -93.0 < lon < -86.2 and 42.4 < lat < 47.4:
                    places[key]["lonlat"] = [round(lon, 5), round(lat, 5)]
            except ValueError:
                pass
            order.append(key)
        for i in ids:
            if i not in places[key]["precincts"]:
                places[key]["precincts"].append(i)
            precinct[i] = order.index(key)
    ids_all = {p["id"] for p in pre}
    if len(precinct) < 0.9 * len(ids_all):
        raise GeoError(f"    {base}: only {len(precinct):,} of {len(ids_all):,} wards could be found in it (columns read: {', '.join(sorted(cols))}); "
                       "the reader needs to be told the layout")
    return {"places": [places[k] for k in order], "precinct": dict(sorted(precinct.items())), "no_place": {}, "rows": len(rows) - 1,
            "rows_not_matched": unmatched, "columns_read": sorted(cols), "precincts_without_a_row": sorted(ids_all - set(precinct))}


def polling_places(pre, put, say, folder=None):
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
        got = read_polling_file(path, pre)
    except GeoError as e:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(str(e))
        return {"file": "polling_places.json", "status": "unread"}
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Wisconsin Elections Commission", "title": "Polling places, General Election of November 3, 2026",
                       "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path)},
               places=got["places"], precinct=got["precinct"], no_place=got["no_place"])
    put("polling_places.json", doc)
    with_point = sum(1 for p in got["places"] if p["lonlat"])
    say(f"      polling places ({os.path.basename(path)}): {len(got['places']):,} places for {len(got['precinct']):,} wards ({with_point:,} with "
        f"coordinates in the file; the rest are listed without a point on the map), {got['rows_not_matched']:,} of {got['rows']:,} rows fit no "
        f"ward, {len(got['precincts_without_a_row']):,} wards have no row; columns read: {', '.join(got['columns_read'])}")
    if not POLL_LAYOUT_CHECKED:
        say("      polling places: the reader was written before any such file was seen, so the file is marked 'unchecked' and a page must not "
            "show it yet. Compare a dozen wards in polling_places.json with the file (and with MyVote Wisconsin), then set "
            "POLL_LAYOUT_CHECKED = True in ballot/wi_geo.py and build again.")
    return {"file": "polling_places.json", "status": status, "places": len(got["places"]), "with_coordinates": with_point}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print, polls_dir=None):
    t0 = time.time()
    say("    Wisconsin ballot map: ward, district and school district lines (LTSB, the Department of Public Instruction, the Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    wpath = os.path.join(CACHE, "ltsb_wards_2026_07_geometry_4326.json.gz")
    apath = os.path.join(CACHE, "ltsb_assembly_2024_geometry_4326.json.gz")
    cpath = os.path.join(CACHE, "ltsb_congress_2022_geometry_4326.json.gz")
    spath = os.path.join(CACHE, "dpi_school_districts_geometry_4326.json.gz")
    tpath = os.path.join(CACHE, "tl_2025_55_cousub.zip")
    wdoc = fetch_full(WARD_SERVICE, WARD_FIELDS, wpath, 250, "OBJECTID", refresh, say)
    adoc = fetch_full(ASM_SERVICE, "ASM2024,SEN2024", apath, 10, "FID", refresh, say)
    cdoc = fetch_full(CD_SERVICE, "CON2021", cpath, 2, "FID", refresh, say)
    sdoc = fetch_full(SCHOOL_SERVICE, "DISTRICT,SDID,LEAID,TYPE", spath, 40, "OBJECTID", refresh, say)
    net.download(COUSUB_URL, tpath, 3650, say=say)
    coa = court_of_appeals(os.path.join(CACHE, "wi_geo_statute_752_11.json"), refresh, say)
    edited = {k: layer_edited(svc, os.path.join(CACHE, f"wi_geo_about_{k}.json"), refresh)
              for k, svc in (("wards", WARD_SERVICE), ("assembly", ASM_SERVICE), ("congress", CD_SERVICE), ("school", SCHOOL_SERVICE))}

    # ---- wards: one line between two neighbours, kept once (inside a county)
    pre, polys = read_wards(wdoc)
    slivers, gave = settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a ward has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} wards, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); "
        f"{lone:,} lines have a ward on one side only, {len(seam):,} of them with another county's ward just across"
        + f"; {slivers} rings under {SLIVER_M2:.0f} square metres left out, {sum(n for _w, n in gave)} points given up by {len(gave)} wards that ran along a neighbour's line the same way"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's counties (one fabric statewide), and its names for cities, villages and towns
    cous = read_cousub(tpath)
    carcs, csides, _crings, codd = G.topology([c[3] for c in cous])
    census_name = {}
    for county, code, name, _r in cous:
        census_name.setdefault(code, name)
    county_short = {}
    for p in pre:
        county_short[p["county"]] = p["countyname"]
    by_short = {re.sub(r"[^a-z]", "", n.lower()): c for c, n in county_short.items()}
    jud = {}
    for d, names_ in coa["districts"].items():
        for n in names_:
            c = by_short.get(re.sub(r"[^a-z]", "", n.lower()))
            if c is None or c in jud:
                raise GeoError(f"    Wis. Stat. 752.11(1): the county {n!r} is not one of the ward table's 72, or is named twice; stopping")
            jud[c] = "CA" + d
    if len(jud) != 72:
        raise GeoError("    Wis. Stat. 752.11(1) does not place all 72 counties; stopping")
    circuits = collections.defaultdict(list)
    paired = {re.sub(r"[^a-z]", "", n.lower()): " and ".join(pair) for pair in coa["pairs"] for n in pair}
    for c, n in sorted(county_short.items(), key=lambda x: x[1]):
        word = paired.get(re.sub(r"[^a-z]", "", n.lower()), n)
        if word not in circuits[jud[c]]:
            circuits[jud[c]].append(word)

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in county_short.items()}
    mname = {}
    for p in pre:
        mname[p["mcd"]] = names.get(("mcd", p["mcd"])) or census_name.get(p["cousub"]) or f"{p['mcdname']} {CTV_WORD[p['ctv']][1]}"
        p["name"] = f"{CTV_WORD[p['ctv']][0]} of {p['mcdname']}, Ward {p['wardno']}"
        p["ward_id"] = f"{p['mcd']}|District {p['alder']}" if p["alder"] else None
        p["com_id"] = f"{p['county']}|{p['com']}"
        p["jud_id"] = jud[p["county"]]

    # ---- Assembly, Senate, Congress and school districts: their own lines, and which wards they hold
    arows = sorted(adoc["rows"], key=lambda r: int(r[0]["ASM2024"]))
    akeys = [str(int(a["ASM2024"])) for a, _r in arows]
    sen_of = {str(int(a["ASM2024"])): str(int(a["SEN2024"])) for a, _r in arows}
    if akeys != [str(n) for n in range(1, 100)] or collections.Counter(collections.Counter(sen_of.values()).values()) != {3: 33}:
        raise GeoError("    Assembly districts: not 99 districts, three to each of 33 Senate districts; stopping")
    apolys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in arows]
    aarcs, asides, _ar, aodd = G.topology(apolys)
    crows = sorted(cdoc["rows"], key=lambda r: int(r[0]["CON2021"]))
    ckeys = [str(int(a["CON2021"])) for a, _r in crows]
    if ckeys != [str(n) for n in range(1, 9)]:
        raise GeoError("    congressional districts: not eight; stopping")
    cpolys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in crows]
    cdarcs, cdsides, _cr, cdodd = G.topology(cpolys)
    srows = sorted(sdoc["rows"], key=lambda r: r[0]["SDID"])
    skeys, stype = [], {}
    for a, _rings in srows:
        if a["TYPE"] not in SCHOOL_KIND or not re.fullmatch(r"\d{4}", a["SDID"] or ""):
            raise GeoError(f"    school districts: type {a['TYPE']!r} code {a['SDID']!r} is not one this builder was checked against; stopping")
        skeys.append(f"{STATE}-S-{a['SDID']}")
        stype[skeys[-1]] = a["TYPE"]
    if len(set(skeys)) != len(skeys):
        raise GeoError("    school districts: two rows share a code; stopping")
    sname = {k: names.get(("school", k)) or f"{G.blank(a['DISTRICT'])} School District" for k, (a, _r) in zip(skeys, srows)}
    spolys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in srows]
    base_n = [n for n, k in enumerate(skeys) if stype[k] != "Secondary"]      # unified and elementary districts tile the state;
    high_n = [n for n, k in enumerate(skeys) if stype[k] == "Secondary"]      # union high school districts lie over the elementary ones
    sfab = []
    for group in (base_n, high_n):
        a_, s_, r_, o_ = G.topology([spolys[n] for n in group])
        f_, _ = G.simplify_arcs(a_, r_, G.TOL_SCHOOL)
        sfab.append((a_, s_, r_, f_, [skeys[n] for n in group], o_))
    say(f"      99 Assembly districts ({len(aarcs):,} lines), 8 congressional ({len(cdarcs):,}), {len(skeys)} school districts "
        f"({len(base_n)} unified or elementary, {len(high_n)} union high school; {len(sfab[0][0]) + len(sfab[1][0]):,} lines), "
        f"{len(cous):,} Census county subdivisions ({len(carcs):,} lines)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("Assembly", aodd), ("Congress", cdodd), ("school", sfab[0][5]), ("Census", codd)) if o))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    o_asm = overlay_cached("assembly", pre_rings, rings_xy(apolys), stamp(wpath, apath), refresh, say)
    o_cd = overlay_cached("congressional", pre_rings, rings_xy(cpolys), stamp(wpath, cpath), refresh, say)
    sdistricts = [[G.ring_xy(refs, f_) for refs in rings] for (_a, _s, r_, f_, _k, _o) in sfab for rings in r_]
    sorder = sfab[0][4] + sfab[1][4]
    o_sch = overlay_cached("school", pre_rings, sdistricts, stamp(wpath, spath), refresh, say)
    split_h, none_h = assign(pre, o_asm, akeys, "house")
    split_c, none_c = assign(pre, o_cd, ckeys, "cd")
    if none_h or none_c:
        raise GeoError(f"    {len(none_h)} wards touch no Assembly district and {len(none_c)} no congressional district (e.g. {(none_h + none_c)[0]}); stopping")
    split_s = []
    for p in pre:
        p["senate"] = sen_of[p["house"]]
        sh = (p.get("split") or {}).get("house")
        if sh and len({sen_of[h] for h in sh}) > 1:
            agg = collections.Counter()
            for h, pct in sh.items():
                agg[sen_of[h]] += pct
            p["split"]["senate"] = {k: round(v, 1) for k, v in agg.items()}
            split_s.append(p["id"])
    say(f"      districts by ward (the one holding most of the ward): {len(split_h)} wards have {SPLIT_SHARE:.0%} or more of their area in a second "
        f"Assembly district, {len(split_s)} in a second Senate district, {len(split_c)} in a second congressional district")
    split = none = edges = 0
    for p, got in zip(pre, o_sch):
        rows = [(sorder[d], share, thick) for d, share, thick in got]
        keep = [(k, s) for k, s, thick in rows if thick]
        if not keep and rows:
            best = max(((k, s) for k, s, _t in rows if stype[k] != "Secondary"), key=lambda x: x[1], default=None)
            if best and best[1] >= 0.5:
                keep = [best]
        keep.sort(key=lambda x: (stype[x[0]] == "Secondary", -x[1], x[0]))     # where a child's first school is, first
        base = [(k, s) for k, s in keep if stype[k] != "Secondary"]
        outside = max(0.0, 1.0 - sum(s for k, s, _t in rows if stype[k] != "Secondary"))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside >= 0.03) else None
        p["school_out"] = round(100 * outside, 1) if outside >= 0.03 else None
        p["school_edge"] = sorted({k for k, _s, _t in rows} - set(p["school"]))
        split += len(base) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(base) < 2
    say(f"      school districts by ward: {split:,} wards are split between two or more unified or elementary districts, "
        f"{sum(1 for p in pre if any(stype[k] == 'Secondary' for k in p['school'])):,} lie in a union high school district as well as an elementary one, "
        f"{none} lie in none, {edges:,} others only brush a neighbouring district along a line")

    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "ward": [p["ward_id"] for p in pre],
            "com": [p["com_id"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": [p["cd"] for p in pre], "judicial": [p["jud_id"] for p in pre]}
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
                if kind == "county" or (others is None and mine is not None) or (others is not None and any(vals[kind][o] != mine for o in others)):
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

    def layer(kind, geoms, qlines, tol, props, source):
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
                       "good_to_zoom": G.zoom_for(tol), "lines_from": source})

    def one(arcs_, sides_, v, tol):
        g, q, _l, _r = G.build_layer(arcs_, sides_, [v], tol)
        return g, q

    ccounty = [c[0] for c in cous]
    CENSUS, LTSB_W, LTSB_D = "wi-census-tiger-2025-cousub", "wi-ltsb-wards-2026-07", "wi-ltsb-assembly-2024"
    layer("state", *one(carcs, csides, [STATE] * len(cous), G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": STATE, "name": "Wisconsin", "j": FIPS, "d": None}, CENSUS)
    layer("county", *one(carcs, csides, ccounty, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, CENSUS)
    layer("cd", *one(cdarcs, cdsides, ckeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, "wi-ltsb-congress-2022")
    layer("senate", *one(aarcs, asides, [sen_of[k] for k in akeys], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, LTSB_D)
    layer("house", *one(aarcs, asides, akeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"Assembly District {v}", "j": v, "d": v, "senate": sen_of[v]}, LTSB_D)
    layer("judicial", *one(carcs, csides, [jud[c] for c in ccounty], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Court of Appeals District {next(k for k, n in ROMAN.items() if n == v[2:])}", "j": v, "d": v[2:],
                     "circuits": circuits[v]}, CENSUS)
    layer("mcd", *one(arcs, sides, vals["mcd"], G.TOL_LOCAL), G.TOL_LOCAL, lambda v: {"id": v, "name": mname[v], "j": v, "d": None}, LTSB_W)
    layer("ward", *one(arcs, sides, vals["ward"], G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{mname[v.split('|')[0]]}, Aldermanic {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, LTSB_W)
    layer("com", *one(arcs, sides, vals["com"], G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Supervisory District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, LTSB_W)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None, "t": SCHOOL_KIND[stype[v]]}   # noqa: E731
    layer("school", *merged_layer([(a_, s_, k_) for (a_, s_, _r, _f, k_, _o) in sfab], G.TOL_LOCAL), G.TOL_LOCAL, sprops, "wi-dpi-school-districts")
    dgeoms, dq = merged_layer([(a_, s_, k_) for (a_, s_, _r, _f, k_, _o) in sfab], G.TOL_SCHOOL)
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
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "school": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "mcd": p["mcd"], "com": p["com_id"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "judicial": p["jud_id"], "school": p["school"]}
            used_names["mcd"][p["mcd"]] = mname[p["mcd"]]
            used_names["com"][p["com_id"]] = f"Supervisory District {p['com']}"
            for k in ("school_pct", "school_out", "school_edge", "split"):
                if p.get(k):
                    pr[k] = p[k]
            for k in p["school"] + p["school_edge"]:
                used_names["school"][k] = sname[k]
            if p["ward_id"]:
                pr["ward"] = [p["ward_id"]]
                used_names["ward"][p["ward_id"]] = f"Aldermanic District {p['alder']}"
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
                raise GeoError(f"    ward {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // G.BOX_STEP, min(ys) // G.BOX_STEP, -(-max(xs) // G.BOX_STEP), -(-max(ys) // G.BOX_STEP)]
        boxes[county] = bx
        rel = f"precincts/{county}.json"
        size = put(rel, doc)
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(pre, put, say, polls_dir)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids)
    check["split_wards"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    sent = collections.Counter(p["sent"] for p in pre)
    ltsb = "Wisconsin Legislature, Legislative Technology Services Bureau (LTSB)"
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today,
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": LTSB_W, "agency": ltsb, "title": "WI Municipal Wards (July 2026)",
                  "about": "Municipal ward lines collected from the 72 county clerks in July 2026 under Wis. Stat. 5.15(4)(br), with each ward's "
                           "county, municipality, county supervisory district and aldermanic district.",
                  "url": WARD_ITEM, "service": WARD_SERVICE, "fetched": wdoc.get("fetched"), "sha256": G.sha_file(wpath), "rows": len(pre),
                  "counties_sent": f"{max(sent.values()):,} wards came in on the commonest day, {max(sent, key=sent.get)}"}, **edited["wards"]),
            dict({"id": LTSB_D, "agency": ltsb, "title": "WI Assembly Districts (2024), each with its Senate district (2023 Wisconsin Act 94)",
                  "url": ASM_ITEM, "service": ASM_SERVICE, "fetched": adoc.get("fetched"), "sha256": G.sha_file(apath), "rows": 99}, **edited["assembly"]),
            dict({"id": "wi-ltsb-congress-2022", "agency": ltsb, "title": "WI Congressional Districts (2022)",
                  "url": CD_ITEM, "service": CD_SERVICE, "fetched": cdoc.get("fetched"), "sha256": G.sha_file(cpath), "rows": 8}, **edited["congress"]),
            dict({"id": "wi-dpi-school-districts", "agency": "Wisconsin Department of Public Instruction", "title": "School Districts, Wisconsin",
                  "url": SCHOOL_ITEM, "service": SCHOOL_SERVICE, "fetched": sdoc.get("fetched"), "sha256": G.sha_file(spath), "rows": len(skeys)}, **edited["school"]),
            {"id": CENSUS, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025, county subdivisions, Wisconsin (tl_2025_55_cousub.zip)",
             "about": "County lines for the far-out layers, and the names of cities, villages and towns.",
             "url": COUSUB_URL, "fetched": dt.datetime.fromtimestamp(os.path.getmtime(tpath)).strftime("%Y-%m-%d"), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": "wi-stat-752-11", "agency": "Wisconsin Legislature", "title": "Wis. Stat. 752.11(1): the counties of each Court of Appeals district",
             "url": STATUTE_URL, "fetched": coa["fetched"], "sha256": coa["sha256"], "rows": 72}],
        "notes": {
            "lines": f"Every ward line is the one its county sent the Legislature in July 2026, generalised by at most {G.TOL_PRECINCT} metres and set on a grid "
                     "of 0.00001 degree (about a metre). Cities, villages and towns, aldermanic districts and county supervisory districts are put "
                     "together from whole wards. A point within a few metres of a line can fall on either side of it, and along a county line "
                     "the two counties' own drawings can differ by several metres.",
            "districts": "Which Assembly, Senate and congressional district a ward lies in is worked out here by laying the Legislature's district "
                         "lines over the ward (analysis, not an official list): the district holding most of the ward's area. The few wards "
                         f"with {SPLIT_SHARE:.0%} or more of their area in a second district are listed, and near such a line MyVote Wisconsin decides.",
            "school": "School district lines are the Department of Public Instruction's. Which districts a ward lies in is analysis, not an "
                      f"official list: a district counts when its part of the ward is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is "
                      "each district's share of the ward's area (land and water, not voters). A union high school district lies over the "
                      "elementary districts that feed it, so a ward there is in both and its shares add to more than 100.",
            "authority": "For which ward an address votes in, and where, MyVote Wisconsin (the Wisconsin Elections Commission) and the municipal clerk are the authority.",
            "precinct_ids": "A ward's id is LTSB's WARD_FIPS: 55, the county's three-digit code, the municipality's five-digit Census code and the "
                            "four-character ward number. Clerks report results by reporting unit (one ward or several), which is not geography.",
            "county_lines": "Wards fit together point for point inside a county and not across county lines, so the state, county, Court of "
                            "Appeals, Assembly, Senate and congressional layers are drawn from statewide files (each layer's lines_from names "
                            "its source) and can differ from the ward files by a few metres.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per ward, id = WARD_FIPS. arcMask[i] has bit k set when "
                            "line i is an outline of arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the wards on the right and left "
                            "of line i (-1: a ward in another county's file, which draws its own copy of the line; -2: outside Wisconsin, or "
                            "open water); names gives the names of the places the file's wards lie in.",
            "boxes": "boxes[county] holds four whole numbers a ward, in the file's order: west, south, east, north in steps of box_step "
                     "degrees from the transform's translate, rounded outwards. A point is tried against every ward whose box (widened "
                     "by half a step) holds it.",
            "precinct_properties": {"name": "the ward's name (Town of Albion, Ward 1)", "county": "county id", "mcd": "city, village or town",
                                    "ward": "list: the aldermanic district the ward lies in (absent where the municipality has none)",
                                    "com": "county supervisory district", "house": "Assembly district", "senate": "state Senate district",
                                    "cd": "congressional district", "judicial": "Court of Appeals district",
                                    "split": "only where a second district holds 3 percent or more of the ward: for house, senate or cd, each district's share in percent",
                                    "school": "list: the school districts the ward lies in: unified and elementary districts first, largest share first, then any union high school district",
                                    "school_pct": "list, when the ward is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the ward's area that lies in no unified or elementary district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the ward along a line (try them too when placing a point)",
                                    "c": "a point inside the ward's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "WI (j is 55)", "county": "the county's five-digit code (55025)", "mcd": "WI-M- and the place's five-digit Census code (WI-M-48000)",
                    "ward": "<place>|District <number> (WI-M-48000|District 5)", "com": "<county>|<supervisory district> (55025|37)",
                    "house": "the Assembly district (76)", "senate": "the district (26)", "cd": "the district (2); properties.race is the race for Congress",
                    "judicial": "CA and the Court of Appeals district (CA4)",
                    "school": "WI-S- and the Department's four-digit code (WI-S-3269); properties.t says unified, elementary or union high school"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(skeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "polling_places": polls,
        "counts": {"precincts": len(pre), "counties": len(counties), "split_between_school_districts": split,
                   "rings_too_small_for_the_grid": dropped_rings, "split_between_assembly_districts": len(split_h),
                   "split_between_congressional_districts": len(split_c), "lines_on_a_county_edge": lone, "with_a_ward_across": len(seam),
                   "sliver_rings_left_out": slivers, "points_given_up_where_two_wards_overlapped": dict(gave)},
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
        f"({sum(l['bytes'] for l in layers) / 1e6:.1f} MB), {len(skeys)} school district files ({school_bytes / 1e6:.1f} MB), "
        f"index {files['index.json']['bytes'] / 1e3:.0f} KB; {total / 1e6:.1f} MB in all, in {final}")
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Wisconsin races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Wisconsin ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point lies in, and a word its school district's name must carry. What each
    # point lies in is the Census Bureau's geocoder's answer for those coordinates (county, county subdivision, 120th
    # Congress district, 2026 legislative districts; asked 2026-10-02), an answer that owes nothing to the files tested
    # here. The Court of Appeals district is the county's, by Wis. Stat. 752.11. The school district is checked by name only.
    ("the State Capitol, Madison", -89.38417, 43.07472,
     {"county": "55025", "mcd": "WI-M-48000", "cd": "2", "senate": "26", "house": "76", "judicial": "CA4"}, "Madison"),
    ("Milwaukee City Hall", -87.90972, 43.04167,
     {"county": "55079", "mcd": "WI-M-53000", "cd": "4", "senate": "7", "house": "19", "judicial": "CA1"}, "Milwaukee"),
    ("downtown Eau Claire", -91.4985, 44.8113,
     {"county": "55035", "mcd": "WI-M-22300", "cd": "3", "senate": "31", "house": "91", "judicial": "CA3"}, "Eau Claire"),
    ("downtown Green Bay", -88.0150, 44.5133,
     {"county": "55009", "mcd": "WI-M-31000", "cd": "8", "senate": "30", "house": "90", "judicial": "CA3"}, "Green Bay"),
    ("Superior", -92.1005, 46.7208,
     {"county": "55031", "mcd": "WI-M-78650", "cd": "7", "senate": "25", "house": "73", "judicial": "CA3"}, "Superior"),
    ("a farm field in the Town of Green Valley, Marathon County", -89.95, 44.75,
     {"county": "55073", "mcd": "WI-M-31450", "cd": "7", "senate": "29", "house": "86", "judicial": "CA3"}, ""),
]
LINE_POINT = ("the Dane-Jefferson county line east of Cambridge", -89.0090, 43.0000, ("55025", "55055"))
LAYER_SLACK = 0.005               # the statewide layers come from other files than the wards: this share of points may disagree


def locate(files, lon, lat):
    """mn_geo.locate, with each county's file taken from the index (a Wisconsin county is its five-digit code)."""
    x, y = G.to_grid(lon, lat)
    bx, by = x / G.BOX_STEP, y / G.BOX_STEP
    rel = {c["id"]: c["file"] for c in files.index["counties"]}
    found, near = None, []
    for county, b in sorted(files.index["boxes"].items()):
        for i in range(0, len(b), 4):
            if b[i] - 0.5 <= bx <= b[i + 2] + 0.5 and b[i + 1] - 0.5 <= by <= b[i + 3] + 0.5:
                doc, lines = files.topo(rel[county])
                g = doc["objects"]["precincts"]["geometries"][i // 4]
                rings = [r for poly in G.geom_polys(lines, g) for r in poly]
                hit = {"county": county, "i": i // 4, "geometry": g, "edge": G.edge_metres(x, y, rings)}
                if found is None and G.in_rings(x, y, rings):
                    found = hit
                elif hit["edge"] <= NEAR_M:
                    near.append(hit)
    if found is None and near:
        near.sort(key=lambda h: h["edge"])
        found = near.pop(0)
    return found, near


def selftest(out=OUT, say=print):
    """Reads only the built files. Returns True when everything holds."""
    files = G.Files(out)
    index, fails = files.index, []

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
            edge_lines += min(r, l) < 0
            for bit, kind in enumerate(doc["arcKinds"]):
                if r >= 0 and l >= 0:
                    want = own(geoms[r], kind) != own(geoms[l], kind)
                elif kind == "county":
                    want = True
                elif min(r, l) == -2:
                    want = own(geoms[max(r, l)], kind) is not None
                else:
                    continue                               # the ward across the line is in another county's file
                bad_mask += bool(masks[a] & (1 << bit)) != want
    check(total == index["counts"]["precincts"], "the county files do not hold as many wards as the index says")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the wards on the two sides of a line")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} wards, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a county's edge), sides and outline marks all in order")

    # 2. every ward is found again from a point inside it; that point's school district is one the ward names; and the
    #    layers agree with the ward, away from their lines
    wrong, tested, agree, skipped = 0, 0, 0, 0
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school = collections.Counter()
    layer_for = {"county": "county", "mcd": "mcd", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com"}
    from_wards = {l["kind"] for l in index["layers"] if l.get("lines_from") == "wi-ltsb-wards-2026-07"}
    split_ids = {s["id"] for s in index["check"].get("split_wards", [])}
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
            school["in a district the ward lies in" if sid in g["properties"]["school"] else
                   "in a district the ward only brushes" if sid else
                   "in none, in a ward partly outside every district" if g["properties"].get("school_out") else "in none"] += 1
            if i % 5 == 0 and g["id"] not in split_ids:
                for prop, kind in layer_for.items():
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
    check(wrong <= 3, f"{wrong} of {tested} wards are not found again from a point inside them")
    for kind, bad in disagree.items():
        limit = 0 if kind in from_wards else max(2, int(LAYER_SLACK * asked[kind]))
        check(len(bad) <= limit, f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the ward at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.002 * tested, f"{school['in none']} wards' own points fall in no school district though the ward is said to lie in one")
    say(f"      self-test: {tested - wrong:,} of {tested:,} wards found again from a point inside them; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each ward's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    for name, lon, lat, want, school_word in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no ward"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        sid = G.school_at(files, found["geometry"], lon, lat)
        fdoc, _l = files.topo(rel[found["county"]])
        sn = fdoc["names"]["school"].get(sid, "") if sid else ""
        ok &= check(sid is not None and sid in pr["school"] and school_word in sn, f"{name}: the school district at the point is {sid} ({sn}), which should name {school_word!r}")
        for prop, kind in layer_for.items():
            shape, _edge = G.shape_at(files, kind, lon, lat)
            ok &= check(shape is not None and shape["id"] == pr[prop], f"{name}: layer {kind} gives {shape and shape['id']}, the ward says {pr[prop]}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {fdoc['names']['mcd'][pr['mcd']]}, "
            f"{fdoc['name']}, supervisory district {pr['com'].split('|')[1]}, Assembly {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, "
            f"{pr['judicial']}, {sn}" + (f", {pr['ward'][0].split('|')[1]}" if pr.get("ward") else "") + f"; {found['edge']:.0f} m from the ward's line")

    # 4. a county line: the spot on one county's own drawing of it nearest to a chosen point
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
               f"a point on {pair[0]}'s drawing of the {pair[0]}/{pair[1]} line lands in {f2 and f2['county']} with {sorted(sides_)} at hand, {f2 and round(f2['edge'], 2)} m from the line")
    if f2:
        other = [h for h in n2 if h["county"] != pair[0]]
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: the spot on Dane County's own line ({on[0]:.5f}, {on[1]:.5f}) is given to "
            f"{f2['geometry']['properties']['name']} with {', '.join(sorted(h['geometry']['properties']['name'] for h in n2))} at hand"
            + (f"; the other county's drawing of the line runs {min(h['edge'] for h in other):.1f} m away" if other else ""))

    # 5. polling places say what they are
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        ids = {g["id"] for c in index["counties"] for g in files.topo(c["file"])[0]["objects"]["precincts"]["geometries"]}
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values()),
              "polling_places.json names a ward or a place that is not there")
    say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Wisconsin's ballot map -> ballot_geo/wi/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/wi)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--polls", default=None, help="folder to look for the saved polling place list in (default: states_cache/wi_local/wec/pollingplaces)")
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
