"""
ballot/sd_geo.py - the geography behind South Dakota's ballot map, in the same files and formats ballot/mn_geo.py
writes for Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and
ballot/wi_geo.py, ballot/ia_geo.py and ballot/nd_geo.py for the few things those states added, and changes nothing in
any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read all five.

    python ballot/sd_geo.py                 builds ballot_geo/sd/ and runs the self-test (about three minutes the first
                                            time: 100 MB of census blocks, then districts laid over precincts)
    python ballot/sd_geo.py --selftest      runs the self-test on the files already built
    python ballot/sd_geo.py --refresh       asks the map services, the statute and the polling place list again
    python ballot/sd_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

What South Dakota publishes, and what that does to the files
------------------------------------------------------------
South Dakota has no statewide map file of its precincts as they stand in 2026: each county auditor keeps the county's
own, and the Secretary of State publishes a list of precinct names and polling places (a PDF), not lines. The only
statewide precinct lines a script may read are the Census Bureau's 2020 voting districts: the precincts the counties
reported to the Bureau for the 2020 census (785 of them; the State's own Department of Agriculture and Natural
Resources uses the same file to plan its water development districts). So a shape here is a 2020 voting district, cut
wherever a 2024 legislative district line crosses it (835 pieces), and index.json says so in plain words: it is the
county's precinct as it stood in 2020, and a county may have redrawn it since. What matters for a ballot does not
depend on the precinct: the county, the legislative district (and House subdistrict), the judicial circuit, the school
district, the city or township, the conservation district and the water development district at a point are each
taken from a current official file.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/sd_local/)
----------------------------------------------------------------------------------------------------------------------
  - Census blocks: the Census Bureau's TIGER/Line 2020 tabulation blocks of South Dakota (tl_2020_46_tabblock20.zip,
    71,383 blocks). Only each block's number and outline are read.
  - Which voting district a block is in: the Bureau's 2020 Block Assignment File (BlockAssign_ST46_SD.zip, the VTD
    table), and the voting districts' names from tl_2020_46_vtd20.zip. Grant County's voting districts carry what read
    as people's names in the Bureau's file; here they are named by their code and those names are never written.
  - Which legislative district a block is in: the Bureau's 2024 State Legislative District Block Equivalency Files
    (sldl24.zip, sldu24.zip): the plan the Legislature enacted in 2021, 35 districts, each electing one senator and two
    representatives, with districts 26 and 28 each divided into two single-member House districts (26A, 26B, 28A, 28B).
    A block is in exactly one district, so the legislative lines here are exact.
  - Cities, towns, townships and unorganized territories, the county lines and the state's outline: TIGER/Line 2025
    county subdivisions (tl_2025_46_cousub.zip). In South Dakota every incorporated city and town is a county
    subdivision of its own, outside every township.
  - County names: the Bureau's 2020 list of county codes (st46_sd_cou2020.txt).
  - School districts: the South Dakota Department of Education's "School District Boundaries 2025-2026" (the State's
    GIS service, Bureau of Information and Telecommunications). Only the district's name and number are asked for.
  - Conservation districts: "Conservation District Boundaries, December 2017" on the State's GIS server (sdgis.sd.gov),
    69 districts. Only the district's name is asked for.
  - Water development districts: the Department of Agriculture and Natural Resources' "WDD Data Viewer" (the seven
    districts' boundaries), and for East Dakota the "East Dakota WDD Directors 2026" divisions (nine director areas).
    Only the polygons layer is asked for, and only the district and area numbers; that service's other layer, which
    lists the sitting directors with their addresses, is never requested.
  - Judicial circuits: SDCL 16-5-1.2 on sdlegislature.gov (seven circuits, each whole counties); the lines are the
    county lines.
  - Polling places: the Secretary of State's "Precinct Polling Places for General Election - November 3rd, 2026" (a
    PDF, linked from sdsos.gov's "2026 Election Precincts & Polling Places" page), read with ballot/pdftext.py by the
    headings' columns: county, precinct name, polling place, address, city. The instructions column is not read.

What is built (ballot_geo/sd/): index.json, manifest.json, precincts/<county>.json (66), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, swcd, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "SD" (j = "46", the jurisdiction_id of statewide races)
  county    "46099"                 sl_places county id; jurisdiction_id of county offices
  mcd       "SD-M-59020"            SD-M- and the Census county subdivision code (a city's is its place code)
  house     "15", "26A"   senate "15"   cd "0" (properties.race is 2026-SD-H00)
  judicial  "SD-JC2"                the circuit's number (d = "Second")
  swcd      "SD-X-005-beadle-county-conservation-district"   sl_places special id where the database has the
            district; j the same, d null
  school    "SD-S-49005"            SD-S-, then the Department's number (49-5) as two and three digits

Not drawn, because no statewide file has the lines: county commissioner districts (each county draws its own under
SDCL 7-8-10), city wards, the director areas of six of the seven water development districts and the subdivisions of
the Heartland Consumers Power District. index.json lists every race without a shape under "check", with the reason. A
precinct does say which water development district it lies in, and in East Dakota which director area.
"""

import argparse
import collections
import csv
import datetime as dt
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
import uuid
import zipfile
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
STATE, FIPS, STATE_NAME = "SD", "46", "South Dakota"
OUT = os.path.join(HERE, "ballot_geo", "sd")
CACHE = os.path.join(HERE, "states_cache", "sd_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://vip.sdsos.gov/VIPLogin.aspx"

CENSUS = "https://www2.census.gov/"
BLOCK_URL = CENSUS + "geo/tiger/TIGER2020/TABBLOCK20/tl_2020_46_tabblock20.zip"
BAF_URL = CENSUS + "geo/docs/maps-data/data/baf2020/BlockAssign_ST46_SD.zip"
VTD_URL = CENSUS + "geo/tiger/TIGER2020PL/STATE/46_SOUTH_DAKOTA/46/tl_2020_46_vtd20.zip"
SLDL_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip"
SLDU_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip"
COUSUB_URL = CENSUS + "geo/tiger/TIGER2025/COUSUB/tl_2025_46_cousub.zip"
COUNTY_URL = CENSUS + "geo/docs/reference/codes2020/cou/st46_sd_cou2020.txt"
BIT = "https://services1.arcgis.com/PwrabBhZHUggYYSp/arcgis/rest/services/"      # the State of South Dakota's ArcGIS Online organisation (BIT)
SCHOOL_SERVICE = BIT + "School_District_Boundaries_2025_2026_With_Maps/FeatureServer/11"
SCHOOL_FIELDS = "dist_num,name"
SOIL_SERVICE = "https://sdgis.sd.gov/host/rest/services/Hosted/Conservation_District_Boundaries_Dec_2017/FeatureServer/0"
WDD_SERVICE = BIT + "WDD_Data_Viewer/FeatureServer/2"
WDD_FIELDS = "wddistrict,DistrictName"
EDWDD_SERVICE = BIT + "East_Dakota_WDD_Directors_2026/FeatureServer/1"      # the divisions; layer 0 (the directors, with addresses) is never asked for
EDWDD_FIELDS = "DistNum,WDD"
STATUTE_URL = "https://sdlegislature.gov/api/Statutes/16-5-1.2.html"
STATUTE_PAGE = "https://sdlegislature.gov/Statutes/16-5-1.2"
POLL_PAGE = "https://sdsos.gov/elections-voting/upcoming-elections/general-information/2026%20Election%20Information/2026-Election-Polling-Places.aspx"
POLL_URL = ("https://sdsos.gov/elections-voting/upcoming-elections/general-information/2026%20Election%20Information/"
            "2026%20Election%20Assets/General/2026PrecinctPollingPlaces_General_v2.pdf")
POLL_HEADS = ["County", "Precinct Name", "Polling Place", "Address", "City", "Instructions"]      # the last is where the others end; never read
POLL_TITLE = "Precinct Polling Places for General Election - November 3rd, 2026"
POLL_CHECKED = False              # True only when a person has compared a county's precincts here with its auditor's 2026 precinct map

ARC_KINDS = ["county", "house", "senate", "cd", "judicial"]      # the kinds a precinct lies wholly inside, so its lines can draw them
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
NEAR_M = G.NEAR_M
AREA_SLACK = 0.02                 # a county's precincts (2020 blocks) and the Bureau's 2025 county may differ in area by this share
LSAD_WORD = {"25": "city", "43": "town", "44": "township", "46": "unorganized territory", "47": "village"}
NAMED_BY_CODE = {"46051"}         # Grant County: the Bureau's file names its voting districts with what read as people's names
ORDINALS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6, "Seventh": 7}

clean, slug = N.clean, N.slug


# ---------------------------------------------------------------- precincts: 2020 voting districts, from census blocks

def read_tables(bafpath, lpath, upath, vpath):
    """{block: (county, voting district code, House district, Senate district)} and {(county, code): the voting
    district's name} from the Bureau's files."""
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

    low, up = bef(lpath, "GEOID,SLDLST"), bef(upath, "GEOID,SLDUST")
    if set(low) != set(vtd) or set(up) != set(vtd):
        raise GeoError("    the block assignment file and the legislative equivalency files do not list the same blocks; stopping")
    table = {}
    for b, (c, v) in vtd.items():
        h, s = re.sub(r"^0+", "", low[b]), re.sub(r"^0+", "", up[b])
        if not (b[:5] == FIPS + c and v and re.fullmatch(r"\d{1,2}[AB]?", h) and re.fullmatch(r"\d{1,2}", s) and re.sub(r"[AB]$", "", h) == s):
            raise GeoError(f"    block {b}: county {c!r}, voting district {v!r}, House {low[b]!r}, Senate {up[b]!r} do not fit the layout this builder was checked against; stopping")
        table[b] = (FIPS + c, v, h, s)
    import shapefile
    zz = zipfile.ZipFile(vpath)
    base = next(n for n in zz.namelist() if n.endswith(".dbf"))
    vname = {(FIPS + r["COUNTYFP20"], r["VTDST20"].strip()): r["NAME20"] for r in (x.as_dict() for x in shapefile.Reader(dbf=io.BytesIO(zz.read(base))).iterRecords())}
    missing = {(c, v) for c, v, _h, _s in table.values()} - set(vname)
    if missing:
        raise GeoError(f"    {len(missing)} voting districts of the block assignment file are not in {os.path.basename(vpath)} (e.g. {sorted(missing)[0]}); stopping")
    return table, vname


def loops(edges):
    """The directed edges left on the outside of a group of blocks, as closed rings (vertex keys, the group on the
    right of each edge), each ring passing through no point twice."""
    nxt = collections.defaultdict(list)
    for a, b in sorted(edges, reverse=True):
        nxt[a].append(b)
    rings = []
    for start in sorted(nxt):
        while nxt[start]:
            path, pos, cur = [start], {start: 0}, start
            while True:
                if not nxt[cur]:
                    raise GeoError("    a group of blocks has an outline that does not close; stopping")
                b = nxt[cur].pop()
                if b in pos:
                    i = pos[b]
                    rings.append(path[i:])
                    for k in path[i + 1:]:
                        del pos[k]
                    del path[i + 1:]
                    cur = b
                    if i == 0:
                        break
                else:
                    pos[b] = len(path)
                    path.append(b)
                    cur = b
    return [r for r in rings if len(r) >= 3]


def vtd_name(county, code, raw):
    """A voting district's name as the page prints it: the Bureau's, without its "VTD" label."""
    n = re.sub(r"\s+", " ", re.sub(r"^\s*VTD\b[\s\-:]*", "", raw or "", flags=re.I)).strip(" -")
    if county in NAMED_BY_CODE or not n:
        return "Voting district " + re.sub(r"^0?V[TD]{2}-?", "", code)
    return n[0].upper() + n[1:] if n[0].islower() else n


def read_units(blockpath, table, vname, say):
    """The precincts: the blocks of each 2020 voting district put together, one piece for each legislative district it
    reaches. Returns (pre, polys): what is said of each, and its rings as vertex keys (the piece on the right)."""
    import shapefile
    z = zipfile.ZipFile(blockpath)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    groups, seen, twice = collections.defaultdict(set), set(), 0
    for sr in r.iterShapeRecords():
        b = sr.record["GEOID20"]
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
    if len(seen) != len(table):
        raise GeoError(f"    {os.path.basename(blockpath)}: {len(seen):,} blocks, but the block assignment file lists {len(table):,}; stopping")
    if twice:
        raise GeoError(f"    {os.path.basename(blockpath)}: {twice} edges are claimed by two blocks of one precinct; stopping")
    pieces = collections.Counter((c, v) for c, v, _h, _s in groups)
    part_no = {}
    for key in sorted(groups, key=lambda k: (k[0], k[1], G.natkey(k[2]))):
        part_no[key] = sum(1 for k in part_no if k[:2] == key[:2]) + 1
    pre, polys, ids = [], [], set()
    for key in sorted(groups, key=lambda k: (k[0], k[1], part_no[k])):
        county, code, house, senate = key
        pid = f"{county}.{re.sub(r'[^0-9A-Za-z-]', '-', code)}" + (f".{part_no[key]}" if pieces[key[:2]] > 1 else "")
        if pid in ids:
            raise GeoError(f"    two precincts would share the id {pid}; stopping")
        ids.add(pid)
        name = vtd_name(county, code, vname[(county, code)])
        pre.append({"id": pid, "county": county, "vtd": code, "precinct": county + code, "house": house, "senate": senate,
                    "name": name + (f", part {part_no[key]}" if pieces[key[:2]] > 1 else ""), "vtdname": name, "parts": pieces[key[:2]]})
        polys.append(loops(groups[key]))
    say(f"      {len(seen):,} census blocks put together into {len(pieces):,} voting districts of 2020, {len(pre):,} pieces once cut by the 2024 legislative districts "
        f"({sum(1 for n in pieces.values() if n > 1)} voting districts reach more than one)")
    return pre, polys


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'sd-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, seat FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def county_names(path):
    """{county code: "Aurora County"} from the Bureau's list of county codes."""
    out = {}
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="|"))
    col = {h: i for i, h in enumerate(rows[0])}
    for r in rows[1:]:
        if r and r[col["STATEFP"]] == FIPS:
            out[FIPS + r[col["COUNTYFP"]]] = r[col["COUNTYNAME"]]
    if len(out) != 66:
        raise GeoError(f"    {os.path.basename(path)}: {len(out)} counties, not 66; stopping")
    return out


def circuits(path, cname, refresh, say):
    """{county: circuit number} from SDCL 16-5-1.2, kept in a small cache; the statute's own sentence is the source."""
    if not G._fresh(path, refresh):
        try:
            net.patient_lookups()
            raw = net.get(STATUTE_URL, timeout=120)
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<style.*?</style>|<[^>]+>", " ", raw.decode("utf-8", "replace"))))
            found = {}
            for word, names in re.findall(r"\(\d\) (\w+) Circuit: (.*?) Counties", text):
                found[str(ORDINALS[word])] = [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", names) if n.strip()]
            if "seven judicial circuits" not in text or sorted(found) != [str(n) for n in range(1, 8)]:
                raise GeoError("    SDCL 16-5-1.2 no longer reads as seven circuits, each a list of counties")
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump({"url": STATUTE_PAGE, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "circuits": found}, fh, indent=1)
            os.replace(path + ".part", path)
        except Exception as e:  # noqa: BLE001
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                raise
            say(f"      could not read SDCL 16-5-1.2 again ({e}); using the copy on disk")
    doc = json.load(open(path, encoding="utf-8"))
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    out = {}
    for no, names in doc["circuits"].items():
        for n in names:
            if n not in by_name or by_name[n] in out:
                raise GeoError(f"    SDCL 16-5-1.2: {n!r} is not a county, or is in two circuits; stopping")
            out[by_name[n]] = no
    if len(out) != 66:
        raise GeoError(f"    SDCL 16-5-1.2 places {len(out)} counties, not 66; stopping")
    return out, doc


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"sd_geo_overlay_{name}.json")
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


def most(p, got, keys, prop):
    """The district of one kind holding most of a precinct (None when none touches it); a second district with
    SPLIT_SHARE or more of the precinct, and thick enough to be more than a hairline, is written into p["split"]."""
    share, thick = collections.Counter(), set()
    for d, s, t in got:
        share[keys[d]] += s
        if t:
            thick.add(keys[d])
    rows = sorted(share.items(), key=lambda x: (-x[1], x[0]))
    if not rows:
        return None
    second = [(k, s) for k, s in rows[1:] if s >= SPLIT_SHARE and k in thick]
    if second:
        p.setdefault("split", {})[prop] = {k: round(100 * s, 1) for k, s in rows[:1] + second}
    return rows[0][0]


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, plans):
    """Every South Dakota race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape). A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    for rid, level, kind, jur, jid, district, _seat in sorted(info["races"], key=lambda r: r[0]):
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
            if not whole:
                why = ("no statewide file has the lines of county commissioner districts: each county board draws its own (SDCL 7-8-10) and the county "
                       "auditor keeps them")
        elif level == "county":
            hit = ("county", jid)
        elif level == "soil_water":
            own = sorted(i for i, p in S.get("swcd", {}).items() if p.get("j") == jid)
            whole = [i for i in own if S["swcd"][i].get("d") is None]
            hit = ("swcd", whole[0]) if len(whole) == 1 else None
            why = None if hit else "the State's conservation district file (December 2017) names no district that carries this id"
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = "no statewide file has the lines of city wards; the city's finance officer keeps them"
        elif level == "school":
            hit = ("school", jid)
        elif level == "other" and jid in S.get("county", {}):
            hit = ("county", jid)
        elif kind == "water_board":
            why = ("a water development district director is elected from a director area; the page's rule places no shape for this kind of office, and "
                   "only the East Dakota district publishes its areas' lines (each precinct says which district it lies in, and in East Dakota which area)")
        elif kind == "utility_board":
            why = "no statewide file has the lines of the Heartland Consumers Power District's subdivisions"
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


# ---------------------------------------------------------------- polling places (the Secretary of State's list, a PDF)

POLL_WAITING = {
    "why": "The South Dakota Secretary of State's list of precinct polling places for November 3, 2026 could not be read when these files were built. "
           "The Secretary's Voter Information Portal and the county auditor say where a voter votes.",
}
POLL_UNCHECKED_WHY = ("      polling places: read from the Secretary's list and marked 'unchecked', so a page does not show them on the map. The list names each "
                      "county's 2026 precincts; the map's precinct lines are the ones the counties gave the Census Bureau in 2020, matched to the list by "
                      "name. Until a county's lines are confirmed for 2026 (POLL_CHECKED in ballot/sd_geo.py), a page may show the list by county "
                      "(by_county in polling_places.json) and must not say which place serves a spot on the map.")


def read_poll_list(path):
    """The list's rows: [{"county", "precinct", "name", "address", "city"}], each cell taken from under its heading."""
    from ballot import pdftext
    pdf = pdftext.PDF(open(path, "rb").read())
    cols, rows, title = None, [], False
    for page, res in pdf.pages():
        for _y, rs in pdftext.rows(pdf, page, res):
            rs = sorted(rs, key=lambda r: r[0])
            text = pdftext.join(rs)
            if text == POLL_TITLE:
                title = True
                continue
            if text.replace(" ", "").startswith("CountyPrecinctName"):
                chars = [(ch, r[0]) for r in rs for ch in r[3] if ch != " "]
                s, at, cols = "".join(c for c, _x in chars), 0, []
                for h in POLL_HEADS:
                    i = s.find(h.replace(" ", ""), at)
                    if i < 0:
                        raise GeoError(f"    polling places: the list's headings are now {text!r}; the reader needs to be told the layout")
                    cols.append(chars[i][1])
                    at = i + 1
                continue
            if cols is None:
                continue
            cells = [[] for _ in POLL_HEADS]
            for r in rs:
                cells[max([i for i, x in enumerate(cols) if x <= r[0] + 1.5] or [0])].append(r)
            county, pct, name, address, city = (pdftext.join(c) for c in cells[:5])
            if county and pct and name:
                rows.append({"county": county, "precinct": pct, "name": name, "address": address, "city": city})
    if not title or len(rows) < 500:
        raise GeoError(f"    polling places: the file is not the general election list this reader was checked against ({len(rows)} rows)")
    return rows


def name_fold(t):
    t = re.sub(r"(?i)\bprecincts?\b|\bpct\b|\bvoting district\b|\bconsolidated\b", " ", t)
    return " ".join(re.sub(r"^0+(?=\w)", "", w) for w in re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def precinct_number(name, listed):
    """The number a precinct goes by: of a listed precinct written "Precinct-04", or the one number a 2020 voting
    district's name gives after the word precinct ("precinct 4 ArmourTown", "ward 2 (part of precinct 4)")."""
    if listed:
        m = re.fullmatch(r"(?i)precinct[\s-]*#?\s*0*([0-9]+[a-z]?)", name.strip())
        return m.group(1).lower() if m else None
    found = {re.sub(r"^0+(?=\w)", "", x).lower() for x in re.findall(r"(?i)precinct\s*#?\s*([0-9]+[a-z]?)\b", name)}
    return next(iter(found)) if len(found) == 1 else None


def match_listed(rows, pre, cname):
    """Each listed 2026 precinct against the 2020 voting districts of its county, by name: the same name, or the same
    precinct number. Returns {(county, listed precinct): [voting district codes]} and the listed counties."""
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    vtds = collections.defaultdict(dict)
    for p in pre:
        vtds[p["county"]][p["vtd"]] = p["vtdname"]
    listed = collections.defaultdict(list)
    for r in rows:
        c = by_name.get(r["county"])
        if c is None:
            raise GeoError(f"    polling places: {r['county']!r} is not a county; the reader needs to be told the layout")
        if r["precinct"] not in listed[c]:
            listed[c].append(r["precinct"])
    out = {}
    for c, names in listed.items():
        free = dict(vtds[c])
        folded = collections.defaultdict(list)
        for code, n in free.items():
            folded[name_fold(n)].append(code)
        for n in names:
            same = folded.get(name_fold(n), [])
            if len(same) == 1 and c not in NAMED_BY_CODE:
                out[(c, n)] = [same[0]]
                free.pop(same[0], None)
        for n in names:
            num = precinct_number(n, True)
            if (c, n) in out or num is None or c in NAMED_BY_CODE:
                continue
            same = [code for code, vn in free.items() if precinct_number(vn, False) == num]
            if same:
                out[(c, n)] = sorted(same)
                for code in same:
                    free.pop(code)
    return out, {c: names for c, names in listed.items()}


def census_geocode(rows, say):
    """nd_geo.census_geocode for South Dakota addresses: [(id, street, city, zip)] -> {id: (lon, lat, matched address)}.
    Polling places are public buildings; nothing else is ever sent."""
    net.patient_lookups()
    buf = io.StringIO()
    w = csv.writer(buf)
    for rid, street, city, zipc in rows:
        w.writerow([rid, street, city, STATE, zipc])
    boundary = "----sdgeo" + uuid.uuid4().hex
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
    cache_path = os.path.join(CACHE, "sd_geo_pollingplace_points.json")
    kept = {}
    if os.path.exists(cache_path):
        try:
            kept = json.load(open(cache_path, encoding="utf-8"))
        except (ValueError, OSError):
            kept = {}
    key = lambda p: f"{p['address']}|{p['city']}".lower()      # noqa: E731
    ask = [(str(n), p["address"], p["city"], "") for n, p in enumerate(places) if p["address"] and key(p) not in kept]
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
        hit, b = kept.get(key(p)), cbox[p["county"]]
        if not hit:
            continue
        if not (b[0] - 0.05 <= hit[0] <= b[2] + 0.05 and b[1] - 0.05 <= hit[1] <= b[3] + 0.05):
            far += 1
            continue
        p["lonlat"], p["from"] = [hit[0], hit[1]], "the Census Bureau's geocoder, from the street address"
        placed += 1
    return placed, far


def polling_places(pre, cname, cbox, path, rows, matched, listed, put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    if rows is None:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        return {"file": "polling_places.json", "status": "waiting"}
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    units = collections.defaultdict(list)
    for p in pre:
        units[(p["county"], p["vtd"])].append(p["id"])
    places, order, of_listed = {}, [], collections.OrderedDict()
    for r in rows:
        c = by_name[r["county"]]
        key = (c, r["name"].lower(), r["address"].lower(), r["city"].lower())
        if key not in places:
            places[key] = {"name": r["name"], "address": r["address"], "city": r["city"], "zip": "", "type": None, "hours": None, "lonlat": None,
                           "county": c, "precincts": []}
            order.append(key)
        of_listed.setdefault((c, r["precinct"]), [])
        if key not in of_listed[(c, r["precinct"])]:
            of_listed[(c, r["precinct"])].append(key)
    at = {k: n for n, k in enumerate(order)}
    of_unit = collections.defaultdict(list)                   # a precinct of the map -> the places of the listed precincts its voting district was matched to
    for (c, n), codes in matched.items():
        for code in codes:
            for pid in units[(c, code)]:
                for key in of_listed[(c, n)]:
                    if key not in of_unit[pid]:
                        of_unit[pid].append(key)
                    if pid not in places[key]["precincts"]:
                        places[key]["precincts"].append(pid)
    plist = [places[k] for k in order]
    precinct, several = {}, {}
    for pid, keys in of_unit.items():
        if len(keys) == 1:
            precinct[pid] = at[keys[0]]
        else:
            names = "; ".join(f"{places[k]['name']} ({', '.join(x for x in (places[k]['address'], places[k]['city']) if x)})" for k in keys)
            several[pid] = (f"is listed with {len(keys)} polling places on the Secretary of State's list ({names}); the Secretary's Voter Information "
                            "Portal or the county auditor says which serve your address")
    placed, far = place_points(plist, cbox, say)
    by_county = collections.OrderedDict()
    for c in sorted(listed):
        by_county[c] = [{"precinct": n, "places": [at[k] for k in of_listed[(c, n)]], "on_the_map": sorted(pid for code in matched.get((c, n), []) for pid in units[(c, code)])}
                        for n in listed[c]]
    not_listed = sorted(c for c in cname if c not in listed)
    status = "loaded" if POLL_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "South Dakota Secretary of State", "title": POLL_TITLE, "url": POLL_URL, "page": POLL_PAGE,
                       "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path)},
               places=plist, precinct=dict(sorted(precinct.items())), no_place=dict(sorted(several.items())), by_county=by_county,
               counties_not_on_the_list=not_listed,
               note="by_county is the Secretary of State's list as it stands: each county's 2026 precincts by name, with the places of each (numbers into "
                    "places). The map's precinct lines are the ones the counties reported to the Census Bureau in 2020; precinct and no_place tie a "
                    "map precinct to the list only where its 2020 name or number is the same as a listed precinct's, and a county may have redrawn the "
                    "precinct since, so they are not shown until checked. A precinct listed with several places (a county with vote centers) is in no_place.")
    put("polling_places.json", doc)
    n_listed = sum(len(v) for v in listed.values())
    say(f"      polling places: {len(rows):,} rows, {len(plist):,} places in {len(listed)} counties ({placed:,} placed by the Census Bureau's geocoder, {far} matches "
        f"thrown out as outside the county); {n_listed:,} precincts on the 2026 list, {len(matched):,} of them matched by name or number to a 2020 voting district; "
        f"{len(of_unit):,} of the map's {len(pre):,} precincts carry a listed place ({len(precinct):,} one, {len(several):,} several)"
        + (f"; not on the list: {', '.join(cname[c] for c in not_listed)}" if not_listed else ""))
    if not POLL_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(plist), "with_coordinates": sum(1 for p in plist if p["lonlat"]), "rows": len(rows),
            "precincts_listed": n_listed, "listed_and_matched_to_the_map": len(matched), "map_precincts_with_a_listed_place": len(of_unit),
            "precincts_with_several_places": len(several), "counties_not_on_the_list": not_listed}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    South Dakota ballot map: 2020 voting districts, 2024 legislative districts, county, city, township, school, conservation and water "
        "district lines (the Census Bureau, the State's GIS services)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    bpath, bafpath, vpath, lpath, upath, tpath, cpath = (path(u.rsplit("/", 1)[1]) for u in (BLOCK_URL, BAF_URL, VTD_URL, SLDL_URL, SLDU_URL, COUSUB_URL, COUNTY_URL))
    for url, p in ((BLOCK_URL, bpath), (BAF_URL, bafpath), (VTD_URL, vpath), (SLDL_URL, lpath), (SLDU_URL, upath), (COUSUB_URL, tpath), (COUNTY_URL, cpath)):
        net.download(url, p, 3650, say=lambda *_a: None)
    scpath, swpath, wpath, edpath = (path(n) for n in ("doe_school_districts_2025_26_geometry_4326.json.gz", "conservation_districts_2017_geometry_4326.json.gz",
                                                       "danr_wdd_boundaries_geometry_4326.json.gz", "danr_east_dakota_wdd_divisions_2026_geometry_4326.json.gz"))
    scdoc = W.fetch_full(SCHOOL_SERVICE, SCHOOL_FIELDS, scpath, 40, "OBJECTID", refresh, say)
    swdoc = W.fetch_full(SOIL_SERVICE, "dist_name", swpath, 25, "fid", refresh, say)
    wdoc = W.fetch_full(WDD_SERVICE, WDD_FIELDS, wpath, 7, "objectid", refresh, say)
    eddoc = W.fetch_full(EDWDD_SERVICE, EDWDD_FIELDS, edpath, 50, "OBJECTID", refresh, say)
    edited = {k: W.layer_edited(svc, path(f"sd_geo_about_{k}.json"), refresh)
              for k, svc in (("school", SCHOOL_SERVICE), ("soil", SOIL_SERVICE), ("wdd", WDD_SERVICE), ("edwdd", EDWDD_SERVICE))}
    pollpath, poll_rows = path(POLL_URL.rsplit("/", 1)[1]), None
    try:
        if refresh and os.path.exists(pollpath):
            os.utime(pollpath, (0, 0))
        net.download(POLL_URL, pollpath, 7, say=lambda *_a: None)
        poll_rows = read_poll_list(pollpath)
    except Exception as e:  # noqa: BLE001  the map does not depend on this list
        say(f"      polling places: waiting; the Secretary's list could not be read ({e})")

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_long = county_names(cpath)
    cname = {c: names.get(("county", c)) or n for c, n in county_long.items()}
    jud_no, jud_doc = circuits(path("sdcl_16-5-1.2.json"), county_long, refresh, say)

    # ---- precincts: the 2020 voting districts, from blocks; every shared line kept once
    table, vname = read_tables(bafpath, lpath, upath, vpath)
    pre, polys = read_units(bpath, table, vname, say)
    if sorted({p["county"] for p in pre}) != sorted(cname):
        raise GeoError("    the blocks and the Bureau's list of counties do not have the same 66 counties; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precincts, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; "
        f"{sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); {lone:,} lines are the state's edge"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's county subdivisions: cities, towns, townships, unorganized territories (one fabric)
    cous = sorted(I.read_shapefile(tpath, lambda r: r["STATEFP"] == FIPS and r["COUSUBFP"] != "00000"), key=lambda x: (x[0]["COUNTYFP"], x[0]["COUSUBFP"]))
    if len({r["COUNTYFP"] for r, _ in cous}) != 66 or any(r["LSAD"] not in LSAD_WORD for r, _ in cous):
        raise GeoError(f"    {os.path.basename(tpath)}: not 66 counties of cities, towns, townships and unorganized territories; stopping")
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    code_names = collections.defaultdict(set)                 # a code used by two different places is told apart by its county; a city in two counties is one place
    for r, _ in cous:
        code_names[r["COUSUBFP"]].add(r["NAMELSAD"])
    mkey = [f"{STATE}-M-{r['COUSUBFP']}" if len(code_names[r["COUSUBFP"]]) == 1 else f"{STATE}-M-{r['COUSUBFP']}-{r['COUNTYFP']}" for r, _ in cous]
    census_name = {k: re.sub(r" UT$", " unorganized territory", r["NAMELSAD"]) for k, (r, _) in zip(mkey, cous)}
    mkind = {k: LSAD_WORD[r["LSAD"]] for k, (r, _) in zip(mkey, cous)}
    mname = {k: names.get(("mcd", k)) or n for k, n in census_name.items()}
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- school, conservation and water development districts: each its own fabric
    for a, _r in scdoc["rows"]:
        if not re.fullmatch(r"\d\d-\d{1,3}", clean(a["dist_num"])) or not clean(a["name"]).endswith(clean(a["dist_num"])):
            raise GeoError(f"    school districts: the row numbered {a.get('dist_num')!r} does not fit the layout this builder was checked against; stopping")
    sid = lambda a: "{}-S-{:02d}{:03d}".format(STATE, *(int(x) for x in clean(a["dist_num"]).split("-")))      # noqa: E731
    schkeys, schpolys, scharcs, schsides, _sr, schodd = I.fabric(N.merge_rows(scdoc["rows"], sid), sid)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    sname = {sid(a): names.get(("school", sid(a))) or clean(a["name"]) for a, _r in scdoc["rows"]}

    db_soil = {pid: n for (kind, pid), n in names.items() if kind == "special" and pid.endswith("conservation-district")}
    soil_id, soil_new = {}, []
    for n in sorted({clean(a["dist_name"]) for a, _r in swdoc["rows"]}):
        if not n:
            raise GeoError("    conservation districts: a row has no name; stopping")
        s = slug(n)
        fits = [pid for pid in db_soil if re.sub(rf"^{STATE}-X-(\d{{3}}-)?", "", pid) in (s + "-conservation-district", s + "-county-conservation-district")]
        if len(fits) == 1:
            soil_id[n] = fits[0]
        else:
            soil_id[n] = f"{STATE}-X-{s}-conservation-district"
            soil_new.append(n)
    if len(set(soil_id.values())) != len(soil_id):
        raise GeoError("    conservation districts: two districts of the State's file would share an id; stopping")
    unmatched_soil = sorted(set(db_soil) - set(soil_id.values()))
    swname = {i: db_soil.get(i) or re.sub(r"\s*-\s*", "-", n) + " Conservation District" for n, i in soil_id.items()}
    swid = lambda a: soil_id[clean(a["dist_name"])]      # noqa: E731
    swkeys, swpolys, swarcs, swsides, _swr, swodd = I.fabric(N.merge_rows(swdoc["rows"], swid), swid)

    db_wdd = {n: pid for (kind, pid), n in names.items() if kind == "special" and pid.endswith("water-development-district")}
    wname = lambda a: clean(a["DistrictName"]) + " Water Development District"      # noqa: E731
    wid = lambda a: db_wdd.get(wname(a)) or f"{STATE}-X-{slug(wname(a))}"      # noqa: E731
    if len(wdoc["rows"]) != 7 or any(not clean(a["DistrictName"]) for a, _r in wdoc["rows"]):
        raise GeoError("    water development districts: not seven named districts; stopping")
    wkeys, wpolys, _wa, _ws, _wr, wodd = I.fabric(N.merge_rows(wdoc["rows"], wid), wid)
    wdd_name = {wid(a): wname(a) for a, _r in wdoc["rows"]}
    east = next((wid(a) for a, _r in wdoc["rows"] if clean(a["wddistrict"]) == "ED"), None)
    if any(clean(a["WDD"]) != "ED" or not re.fullmatch(r"[1-9]", clean(str(a["DistNum"]))) for a, _r in eddoc["rows"]) or east is None:
        raise GeoError("    East Dakota Water Development District: the divisions do not fit the layout this builder was checked against; stopping")
    edkeys, edpolys, _ea, _es, _er, edodd = I.fabric(N.merge_rows(eddoc["rows"], lambda a: clean(str(a["DistNum"]))), lambda a: clean(str(a["DistNum"])))
    say(f"      {len(schkeys)} school districts ({len(scharcs):,} lines), {len(swkeys)} conservation districts ({len(swarcs):,} lines), {len(wkeys)} water "
        f"development districts, {len(edkeys)} East Dakota director areas, {len(cous):,} Census county subdivisions ({len(carcs):,} lines)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("school", schodd), ("conservation", swodd), ("water", wodd), ("East Dakota", edodd), ("Census", codd)) if o))
    if info["found"] and unmatched_soil:
        say(f"      conservation districts: the ballot database has {len(unmatched_soil)} the State's file does not name ({', '.join(unmatched_soil[:4])})")

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    units_stamp = (bpath, bafpath, lpath, upath)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(*units_stamp, scpath), refresh, say)
    o_mcd = overlay_cached("places", pre_rings, I.rings_xy([r for _a, r in cous]), stamp(*units_stamp, tpath), refresh, say)
    o_sw = overlay_cached("conservation", pre_rings, I.rings_xy(swpolys), stamp(*units_stamp, swpath), refresh, say)
    o_wdd = overlay_cached("water", pre_rings, I.rings_xy(wpolys), stamp(*units_stamp, wpath), refresh, say)
    o_ed = overlay_cached("east-dakota-areas", pre_rings, I.rings_xy(edpolys), stamp(*units_stamp, edpath), refresh, say)

    several = no_soil = in_wdd = 0
    for p, gm, gs, gw, ge in zip(pre, o_mcd, o_sw, o_wdd, o_ed):
        share, thick = collections.Counter(), set()
        for d, s, t in gm:                                    # a city in two counties is two rows of the Bureau's file and one place
            if ccounty[d] != p["county"]:
                continue
            share[mkey[d]] += s
            if t:
                thick.add(mkey[d])
        rows = sorted(((k, s, k in thick) for k, s in share.items()), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t] or [(k, s) for k, s, _t in rows[:1]]
        if not own:
            raise GeoError(f"    precinct {p['id']} lies in no city, township or unorganized territory of its county; stopping")
        p["mcd"] = own[0][0]
        p["mcd_all"] = [k for k, _s in own]
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in own] if len(own) > 1 else None
        several += len(own) > 1
        p["cd"], p["jud"] = "0", f"{STATE}-JC{jud_no[p['county']]}"
        p["swcd"] = most(p, gs, swkeys, "swcd")
        no_soil += p["swcd"] is None
        wd = sorted(((wkeys[d], s) for d, s, t in gw if t or s >= 0.5), key=lambda x: -x[1])
        p["wdd"] = wd[0][0] if wd and wd[0][1] >= 0.5 else None
        p["wdd_pct"] = round(100 * wd[0][1], 1) if p["wdd"] and wd[0][1] < 0.97 else None
        p["wdd_area"] = None
        if p["wdd"] == east:
            area = most(p, ge, edkeys, "wdd_area")
            p["wdd_area"] = f"Director Area {area}" if area else None
            if p.get("split", {}).get("wdd_area"):
                p["split"]["wdd_area"] = {f"Director Area {k}": v for k, v in p["split"]["wdd_area"].items()}
        in_wdd += p["wdd"] is not None
    say(f"      cities and townships by precinct: {several:,} of {len(pre):,} precincts reach more than one place; conservation district: "
        f"{sum(1 for p in pre if p.get('split', {}).get('swcd'))} precincts have {SPLIT_SHARE:.0%} or more of their area in a second, {no_soil} lie in none; "
        f"{in_wdd:,} precincts lie mostly in a water development district")
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

    # ---- the area check: each county's precincts (2020 blocks) against the Bureau's 2025 county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731  Esri's winding: outer rings clockwise
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in clist}
    if sorted(area_p) != clist:
        raise GeoError("    area check: the blocks and the 2025 county subdivisions do not have the same 66 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws; stopping")
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's 2025 South Dakota; the county furthest off is {cname[worst]} ({worst_pct:+.2f}%)")

    # ---- the Secretary's 2026 list against the map's precincts, by name
    matched, listed = match_listed(poll_rows, pre, county_long) if poll_rows is not None else ({}, {})
    on_list = {(c, code) for (c, _n), codes in matched.items() for code in codes}
    for p in pre:
        p["listed"] = (p["county"], p["vtd"]) in on_list

    vals = {"county": [p["county"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": ["0"] * len(pre),
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
        return g, q

    BLOCKS, BEF, COUSUB, SCH, SOIL, WDD, EDW, LAW, VTD = ("sd-census-tiger-2020-blocks", "sd-census-2024-legislative-bef", "sd-census-tiger-2025-cousub",
                                                         "sd-doe-school-districts-2025-26", "sd-conservation-districts-2017", "sd-danr-wdd-boundaries",
                                                         "sd-danr-east-dakota-wdd-divisions-2026", "sd-sdcl-16-5-1.2", "sd-census-2020-voting-districts")
    ordinal = {str(n): w for w, n in ORDINALS.items()}
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[f"{STATE}-JC{jud_no[c]}"].append(cname[c])
    layer("state", *own([STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, BLOCKS)
    layer("county", *own(vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, BLOCKS)
    layer("cd", *own(vals["cd"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": "South Dakota's one congressional district (the whole state)", "j": None, "d": v, "race": f"2026-{STATE}-H00"}, BLOCKS)
    layer("senate", *own(vals["senate"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("house", *own(vals["house"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v, "senate": re.sub(r"[AB]$", "", v),
                     "seats": 1 if re.search(r"[AB]$", v) else 2}, BLOCKS + ", put together by " + BEF)
    layer("judicial", *own(vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{ordinal[v[len(STATE) + 3:]]} Judicial Circuit", "j": v, "d": ordinal[v[len(STATE) + 3:]], "counties": jud_counties[v]},
          BLOCKS + "; which counties, from " + LAW)
    mg, mq, _l, _r = G.build_layer(carcs, csides, [mkey], TOL_MCD)
    layer("mcd", mg, mq, TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, COUSUB, zoom=MCD_ZOOM)
    swg, swq, _l, _r = G.build_layer(swarcs, swsides, [swkeys], G.TOL_LOCAL)
    layer("swcd", swg, swq, G.TOL_LOCAL, lambda v: {"id": v, "name": swname[v], "j": v, "d": None}, SOIL)
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
        geoms, used_names = [], {"mcd": {}, "school": {}, "swcd": {}, "wdd": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "mcd": p["mcd"], "house": p["house"], "senate": p["senate"], "cd": "0",
                  "judicial": p["jud"], "school": p["school"], "as_of": 2020}
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["swcd"]:
                pr["swcd"] = p["swcd"]
                for k in [p["swcd"]] + list((p.get("split") or {}).get("swcd", {})):
                    used_names["swcd"][k] = swname[k]
            if p["wdd"]:
                pr["wdd"] = p["wdd"]
                used_names["wdd"][p["wdd"]] = wdd_name[p["wdd"]]
            for k, v in (("wdd_pct", p["wdd_pct"]), ("wdd_area", p["wdd_area"]), ("listed_2026", p["listed"])):
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

    polls = polling_places(pre, county_long, cbox, pollpath, poll_rows, matched, listed, put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    # ---- how the ballot database's commissioner races are filed (the only word on a county's plan that a script can read)
    plans = {}
    for _rid, _level, kind, _jur, jid, district, seat in info["races"]:
        if kind == "county_commissioner":
            e = plans.setdefault(str(jid), {"plan": 1, "districts": set(), "source": "the Secretary of State's 2026 candidate list"})
            if district not in (None, ""):
                e["plan"] = 3
                e["districts"].add(str(district))
    for e in plans.values():
        e["districts"] = sorted(e["districts"], key=G.natkey)
        e["commissioners_elected"] = ("at large, by the candidate list" if e["plan"] == 1 else
                                      "from commissioner districts, by the candidate list; the county auditor has the lines, and no statewide file does")

    check = check_ids(info, shape_ids, plans)
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    check["conservation_districts_not_in_the_ballot_database"] = soil_new
    check["conservation_districts_of_the_ballot_database_not_in_the_state_file"] = unmatched_soil
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    bit = "State of South Dakota, Bureau of Information and Telecommunications (GIS)"
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    cb = "U.S. Census Bureau"
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            {"id": BLOCKS, "agency": cb, "title": "TIGER/Line Shapefiles 2020, tabulation blocks, South Dakota (tl_2020_46_tabblock20.zip)",
             "about": "The 2020 census blocks: every line of the map's precincts, counties and legislative districts is a block's.",
             "url": BLOCK_URL, "fetched": mtime(bpath), "sha256": G.sha_file(bpath), "rows": len(table)},
            {"id": VTD, "agency": cb, "title": "2020 Census Block Assignment File, voting districts (BlockAssign_ST46_SD.zip), and the voting districts' names "
                                                "(tl_2020_46_vtd20.zip)",
             "about": "The precincts South Dakota's counties reported to the Bureau for the 2020 census: which voting district each block is in.",
             "url": BAF_URL, "names_url": VTD_URL, "fetched": mtime(bafpath), "sha256": G.sha_file(bafpath), "names_sha256": G.sha_file(vpath),
             "rows": len({(p["county"], p["vtd"]) for p in pre})},
            {"id": BEF, "agency": cb, "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip)",
             "about": "Which House and Senate district each block is in, under the plan the Legislature enacted in 2021.",
             "url": SLDL_URL, "upper_url": SLDU_URL, "fetched": mtime(lpath), "sha256": G.sha_file(lpath), "upper_sha256": G.sha_file(upath), "rows": len(table)},
            {"id": COUSUB, "agency": cb, "title": "TIGER/Line Shapefiles 2025, county subdivisions, South Dakota (tl_2025_46_cousub.zip)",
             "about": "Cities, towns, townships and unorganized territories as the Bureau had them on January 1, 2025; also the county areas the precincts are checked against.",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            dict({"id": SCH, "agency": "South Dakota Department of Education; published by the " + bit, "title": "School District Boundaries 2025-2026",
                  "url": SCHOOL_SERVICE, "service": SCHOOL_SERVICE, "fetched": scdoc.get("fetched"), "sha256": G.sha_file(scpath), "rows": len(schkeys)}, **edited["school"]),
            dict({"id": SOIL, "agency": bit, "title": "Conservation District Boundaries, December 2017",
                  "about": "The only statewide file of conservation district lines; a district that has changed since 2017 is drawn as it was.",
                  "url": SOIL_SERVICE, "service": SOIL_SERVICE, "fetched": swdoc.get("fetched"), "sha256": G.sha_file(swpath), "rows": len(swkeys)}, **edited["soil"]),
            dict({"id": WDD, "agency": "South Dakota Department of Agriculture and Natural Resources; published by the " + bit,
                  "title": "WDD Data Viewer: water development district boundaries",
                  "url": WDD_SERVICE, "service": WDD_SERVICE, "fetched": wdoc.get("fetched"), "sha256": G.sha_file(wpath), "rows": len(wkeys)}, **edited["wdd"]),
            dict({"id": EDW, "agency": "South Dakota Department of Agriculture and Natural Resources; published by the " + bit,
                  "title": "East Dakota WDD Directors 2026: divisions (the nine director areas)",
                  "about": "Only the divisions' polygons and their area numbers are read; the service's list of directors is never requested.",
                  "url": EDWDD_SERVICE, "service": EDWDD_SERVICE, "fetched": eddoc.get("fetched"), "sha256": G.sha_file(edpath), "rows": len(eddoc["rows"])}, **edited["edwdd"]),
            {"id": LAW, "agency": "South Dakota Legislature, Legislative Research Council", "title": "SDCL 16-5-1.2: Number of judicial circuits; counties included",
             "url": jud_doc["url"], "fetched": jud_doc["fetched"], "sha256": jud_doc["sha256"], "rows": 7},
        ],
        "notes": {
            "lines": f"Every precinct, county and legislative line is a 2020 census block's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of "
                     "0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "South Dakota publishes no statewide map of its precincts as they stand in 2026. Each shape here is a voting district as the county "
                         "reported it to the Census Bureau for the 2020 census, cut wherever a 2024 legislative district line crosses it, and named as the "
                         "Bureau's file names it. A county may have redrawn or renamed its precincts since: the county auditor is the authority. "
                         "listed_2026 is true where the Secretary of State's list of 2026 precincts has a precinct of the same name or number in the county. "
                         "What a ballot depends on (county, legislative district, city or township, school, conservation and water development district) "
                         "is taken from current files and does not depend on the precinct.",
            "places": "A precinct is often several townships together, or a town with the townships around it, so the precinct does not say which city or "
                      "township a voter lives in: the mcd layer (the Census Bureau's cities, towns, townships and unorganized territories of January 1, "
                      "2025) answers that for a point. mcd is the place holding most of the precinct; mcd_all lists every place it reaches.",
            "commissioners": "A county board may elect its members at large, from single-member districts, from multi-member districts or from a mix (SDCL "
                             "7-8-10), and draws its own districts; no statewide file has the lines, so no commissioner district is a shape. "
                             "supervisor_plans says how each county's commissioner races are filed on the Secretary of State's 2026 candidate list.",
            "legislative": "A legislative district elects one senator and two representatives; districts 26 and 28 each elect one representative from each "
                           "of two House districts (26A, 26B, 28A, 28B). Which district a block is in is the Census Bureau's 2024 equivalency file's word, "
                           "so a precinct's district is exact.",
            "school": "School district lines are the Department of Education's for 2025-2026. Which districts a precinct lies in is analysis, not an official "
                      f"list: a district counts when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each "
                      "district's share of the precinct's area (land and water, not voters). No school office is on the November 2026 ballot.",
            "conservation": "Conservation district lines are the State's file of December 2017, the only one published. A precinct's swcd is the district "
                            "holding most of it (analysis); where a second district holds 3 percent or more, split.swcd gives each one's share, and the swcd "
                            "layer answers for a point.",
            "water": "wdd is the water development district holding most of a precinct (at least half of it), from the Department of Agriculture and Natural "
                     "Resources' boundaries; wdd_pct is given where that is under 97 percent. wdd_area is the director area, published for the East Dakota "
                     "district only. No layer draws them: the page places no shape for this kind of office.",
            "judicial": "The seven judicial circuits are whole counties (SDCL 16-5-1.2). No judge is on the November 2026 ballot.",
            "authority": "For which precinct an address votes in, and where, the county auditor and the South Dakota Secretary of State's Voter Information Portal are the authority.",
            "precinct_ids": "A precinct's id is its county's five digits, a full stop and the Census Bureau's 2020 voting district code (46099.VTD1-3); a "
                            "voting district cut by a legislative line has a second full stop and the piece's number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file; -2: outside South Dakota); names gives the names of the places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the 2020 voting district's, as the Census Bureau's file gives it (and the piece's number where a legislative line cuts it)",
                                    "county": "county id", "precinct": "the county's five digits and the Bureau's 2020 voting district code",
                                    "as_of": "the year of the precinct's lines (2020)",
                                    "listed_2026": "true where the Secretary of State's 2026 list has a precinct of the same name or number in the county",
                                    "mcd": "city, town, township or unorganized territory holding most of the precinct",
                                    "mcd_all": "list, when the precinct reaches more than one: every city and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                                    "house": "House district (the legislative district; 26A, 26B, 28A or 28B in districts 26 and 28)",
                                    "senate": "Senate district (the legislative district)", "cd": "congressional district (0: the whole state)",
                                    "judicial": "judicial circuit", "swcd": "conservation district holding most of the precinct",
                                    "wdd": "water development district (absent outside every one)",
                                    "wdd_pct": "percent of the precinct inside that water development district, where under 97",
                                    "wdd_area": "the director area, in the East Dakota Water Development District",
                                    "split": "only where a second conservation district or director area holds 3 percent or more of the precinct: each one's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "SD (j is 46)", "county": "the county's five-digit code (46099)",
                    "mcd": "SD-M- and the Census county subdivision code (SD-M-59020); properties.t says city, town, township or unorganized territory",
                    "house": "the district (15; 26A, 26B, 28A, 28B); properties.seats is the number of representatives it elects", "senate": "the district (15)",
                    "cd": "0; properties.race is the race for Congress",
                    "judicial": "SD-JC and the circuit's number (SD-JC2); d is the circuit's ordinal (Second)",
                    "swcd": "the ballot database's id where it has the district (SD-X-005-beadle-county-conservation-district); j is the same",
                    "school": "SD-S-, then the Department's number as two and three digits (49-5 is SD-S-49005)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "water_development_districts": {k: wdd_name[k] for k in sorted(wdd_name)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "whole_precincts": len({p["precinct"] for p in pre}), "counties": len(counties), "census_blocks": len(table),
                   "precincts_on_the_2026_list_by_name": sum(1 for p in pre if p["listed"]),
                   "split_between_school_districts": split, "in_more_than_one_city_or_township": several,
                   "rings_too_small_for_the_grid": dropped_rings, "lines_with_a_precinct_on_one_side": lone,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} South Dakota races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    South Dakota ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the place at the point (from the mcd layer), and a
    # word its school district's name must carry. County, county subdivision, legislative districts (upper and lower)
    # and school district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02:
    # geocoding.geo.census.gov, "geographies/coordinates", its current legislative districts), an answer that owes
    # nothing to the files tested here. The judicial circuit is the county's (SDCL 16-5-1.2).
    ("the State Capitol, Pierre", -100.3464, 44.3672, {"county": "46065", "senate": "24", "house": "24", "judicial": "SD-JC6"}, "SD-M-49600", "Pierre"),
    ("downtown Sioux Falls", -96.7290, 43.5460, {"county": "46099", "senate": "15", "house": "15", "judicial": "SD-JC2"}, "SD-M-59020", "Sioux Falls"),
    ("downtown Rapid City", -103.2250, 44.0805, {"county": "46103", "senate": "32", "house": "32", "judicial": "SD-JC7"}, "SD-M-52980", "Rapid City"),
    ("downtown Aberdeen", -98.4870, 45.4647, {"county": "46013", "senate": "3", "house": "3", "judicial": "SD-JC5"}, "SD-M-00100", "Aberdeen"),
    ("Brookings, the university campus", -96.7860, 44.3190, {"county": "46011", "senate": "7", "house": "7", "judicial": "SD-JC3"}, "SD-M-07580", "Brookings"),
    ("downtown Watertown", -97.1140, 44.8990, {"county": "46029", "senate": "5", "house": "5", "judicial": "SD-JC3"}, "SD-M-69300", "Watertown"),
    ("Mission, Todd County (House district 26A)", -100.6580, 43.3060, {"county": "46121", "senate": "26", "house": "26A", "judicial": "SD-JC6"}, "SD-M-42940", "Todd County"),
    ("Pine Ridge, Oglala Lakota County", -102.5560, 43.0260, {"county": "46102", "senate": "27", "house": "27", "judicial": "SD-JC7"}, "SD-M-70415", "Oglala Lakota"),
    ("Eagle Butte, Dewey County (House district 28A)", -101.2330, 45.0020, {"county": "46041", "senate": "28", "house": "28A", "judicial": "SD-JC4"}, "SD-M-45545", "Eagle Butte"),
    ("Sisseton, Roberts County", -97.0500, 45.6640, {"county": "46109", "senate": "1", "house": "1", "judicial": "SD-JC5"}, "SD-M-59260", "Sisseton"),
    ("a field in Alpha Township, Hand County", -99.05, 44.60, {"county": "46059", "senate": "23", "house": "23", "judicial": "SD-JC3"}, "SD-M-01100", "Miller"),
    ("Winner, Tripp County", -99.8590, 43.3760, {"county": "46123", "senate": "21", "house": "21", "judicial": "SD-JC6"}, "SD-M-72180", "Winner"),
    ("Yankton", -97.3920, 42.8790, {"county": "46135", "senate": "18", "house": "18", "judicial": "SD-JC1"}, "SD-M-73060", "Yankton"),
    ("Spearfish", -103.8590, 44.4900, {"county": "46081", "senate": "31", "house": "31", "judicial": "SD-JC4"}, "SD-M-60020", "Spearfish"),
    ("Wagner, Charles Mix County", -98.2930, 43.0800, {"county": "46023", "senate": "21", "house": "21", "judicial": "SD-JC1"}, "SD-M-68020", "Wagner"),
    ("Box Elder, Pennington County", -103.0680, 44.1120, {"county": "46103", "senate": "35", "house": "35", "judicial": "SD-JC7"}, "SD-M-06620", "Douglas"),
]
LINE_POINTS = [("the Minnehaha-Lincoln county line in Sioux Falls", -96.73, 43.50, ("46099", "46083")),
               ("the Pennington-Meade county line north of Rapid City", -103.2, 44.14, ("46103", "46093"))]
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
    check(len(index["counties"]) == 66, "there are not 66 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == 35 and len(layer_ids.get("house", ())) == 37 and {"26A", "26B", "28A", "28B"} <= layer_ids.get("house", set())
          and len(layer_ids.get("judicial", ())) == 7 and layer_ids.get("cd") == {"0"} and len(layer_ids.get("county", ())) == 66,
          "there are not 35 Senate districts, 37 House districts (26A, 26B, 28A, 28B among them), 7 judicial circuits, 66 counties and one congressional district")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place, soil = collections.Counter(), collections.Counter(), collections.Counter()
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
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school"), ("swcd", "swcd")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in pr["school"] else "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            place["the precinct's own place" if shape and shape["id"] == pr["mcd"] else "another place the precinct names" if shape and shape["id"] in pr.get("mcd_all", [])
                  else "a place the precinct does not name" if shape else "no place"] += 1
            shape, _edge = G.shape_at(files, "swcd", lon, lat)
            soil["the precinct's own district" if shape and shape["id"] == pr.get("swcd") else
                 "another district the precinct is split with" if shape and shape["id"] in (pr.get("split") or {}).get("swcd", {}) else
                 "a district the precinct does not name" if shape else "no district"] += 1
            for prop, kind in layer_for.items():
                if i % 3 and kind not in ("house",):
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
    check(wrong <= 3, f"{wrong} of {tested} precincts are not found again from a point inside them")
    check(not sum(no_shape.values()), f"precincts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["no place"] == 0 and place["a place the precinct does not name"] <= 0.02 * tested, f"the place at a precinct's own point: {dict(place)}")
    check(soil["a district the precinct does not name"] + soil["no district"] <= 0.02 * tested, f"the conservation district at a precinct's own point: {dict(soil)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each precinct's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city or township: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])) + "; conservation district: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(soil.items(), key=lambda x: -x[1])))

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
            shape2, _edge = G.shape_at(files, kind, lon, lat)
            ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {pr.get(prop)}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, {pr['judicial']}, {sn}; {found['edge']:.0f} m from the precinct's line")

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
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])) and not set(polls["precinct"]) & set(polls["no_place"])
              and all(0 <= i < n for rows in polls["by_county"].values() for r in rows for i in r["places"])
              and all(v in ids for rows in polls["by_county"].values() for r in rows for v in r["on_the_map"]),
              "polling_places.json names a precinct or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        inside = 0
        for p in polls["places"]:
            if p.get("lonlat"):
                f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
                inside += bool(f3) and f3["county"] == p["county"]
        say(f"      self-test: polling places: {polls.get('status')}; {n:,} places, {sum(1 for p in polls['places'] if p.get('lonlat')):,} with a point "
            f"({inside:,} of them inside their own county); {len(polls['precinct']):,} map precincts carry one listed place, {len(polls['no_place']):,} several")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind South Dakota's ballot map -> ballot_geo/sd/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/sd)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask the map services, the statute and the polling place list again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
