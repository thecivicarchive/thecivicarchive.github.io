"""
ballot/wy_geo.py - the geography behind Wyoming's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, ballot/sd_geo.py for putting
census blocks together into precincts, and ballot/wi_geo.py, ballot/ia_geo.py and ballot/state_local_wy.py for the few
things those added, and changes nothing in any of them), so the same page and the same reader (ballot/mn_geo_reader.js)
read them all.

    python ballot/wy_geo.py                 builds ballot_geo/wy/ and runs the self-test (about five minutes the first
                                            time: 140 MB of census blocks, then districts laid over precincts)
    python ballot/wy_geo.py --selftest      runs the self-test on the files already built
    python ballot/wy_geo.py --refresh       asks for the Secretary of State's precinct table and the statute again
    python ballot/wy_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

What Wyoming publishes, and what that does to the files
-------------------------------------------------------
Wyoming has no statewide map file of its precincts as they stand in 2026: each county clerk keeps the county's own,
and the Secretary of State publishes a table of precinct codes with their House and Senate districts (a PDF), not
lines. The only statewide precinct lines a script may read are the Census Bureau's 2020 voting districts: the precincts
the counties reported for the 2020 census (512 of them). The Legislature redrew every legislative district in 2022 and
the counties renumbered many precincts to fit, so a shape here is a 2020 voting district cut wherever a 2022-plan
legislative district line or a city or town limit crosses it, and index.json says so in plain words. What a ballot
depends on does not depend on the precinct: the county, the House and Senate district, the judicial district, the city
or town and the school district at a point are each taken from a current official file.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/wy_local/)
----------------------------------------------------------------------------------------------------------------------
  - Census blocks: the Census Bureau's TIGER/Line 2020 tabulation blocks of Wyoming (tl_2020_56_tabblock20.zip, 53,769
    blocks). Only each block's number, its inside point and its outline are read.
  - Which voting district a block is in: the Bureau's 2020 Block Assignment File (BlockAssign_ST56_WY.zip, the VTD
    table), and the voting districts' names from tl_2020_56_vtd20.zip. Albany and Sheridan counties named their voting
    districts after the polling place (a person's home, a business carrying a person's name among them), as did a few
    elsewhere: those are named by their code, and the Bureau's name is never written.
  - Which House and Senate district a block is in: the Bureau's 2024 State Legislative District Block Equivalency Files
    (NationalSLDL24 and NationalSLDU24, the same national files ballot/sd_geo.py reads): the plan the Legislature enacted
    in 2022, 62 House and 31 Senate districts, one member each. A block is in exactly one district, so the legislative
    lines here are exact.
  - Cities and towns: TIGER/Line 2025 places (tl_2025_56_place.zip), the incorporated ones only (Wyoming's 99 cities and
    towns; census-designated places are not governments). A block belongs to the city or town its own inside point lies
    in, so a precinct piece lies wholly inside one city or town, or wholly outside every one.
  - School districts: TIGER/Line 2025 unified school districts (tl_2025_56_unsd.zip) and the one district the Bureau
    files as elementary (tl_2025_56_elsd.zip: Fremont County School District 38). The Bureau's "School District Not
    Defined" (Yellowstone National Park) is left out.
  - County lines and the state's outline for the area check: TIGER/Line 2025 county subdivisions
    (tl_2025_56_cousub.zip), and county names from the Bureau's 2020 list of county codes (st56_wy_cou2020.txt).
  - Judicial districts: W.S. 5-3-101 (nine districts, each whole counties), read from the Legislature's own file of
    Title 5 by ballot/state_local_wy.judicial_districts. The circuit courts sit in the same districts.
  - The Secretary of State's "Statewide Senate Districts and House Districts By County Report" (2026, a PDF linked as
    "Districts and Precincts by County" from sos.wyo.gov/Elections): each county's 2026 precinct codes and the House and
    Senate districts of each. Only the county, district and precinct code cells are read; the report's header (it names
    the staff member who ran it) is skipped and never written. Used as a check: a piece is marked listed_2026 where its
    2020 code reads as the same numbers as a 2026 code of its county AND the report puts that 2026 precinct in the
    piece's House district.
  - Polling places: Wyoming publishes no statewide list a script may read. See POLLING PLACES below.

What is built (ballot_geo/wy/): index.json, manifest.json, precincts/<county>.json (23), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "WY" (j = "56", the jurisdiction_id of statewide races and of the Supreme Court and Chancery Court votes)
  county    "56021"                 sl_places county id; jurisdiction_id of county offices
  mcd       "WY-M-13900"            WY-M- and the Census Bureau's place code (the ballot database's own ids)
  house     "11"   senate "8"   cd "0" (properties.race is 2026-WY-H00)
  judicial  "WY-JD1"                the jurisdiction_id of district and circuit court retention votes; d is the number
  school    "WY-S-021-1"            WY-S-, the three-digit code of the county the district is named for, and its number
                                    (Johnson County School District 1 is the database's WY-S-019-school-district, the
                                    one school district of that county there)

Not drawn, because no statewide file has the lines: city wards (the city clerk keeps them; a ward's council race is
placed on its city), school trustee areas, hospital, fire, cemetery, conservation, senior citizen, museum, water and
sewer and improvement districts, and community college districts. index.json lists every race without a shape under
"check", with the reason. County commissioners are elected by the whole county (the 2026 lists give no districts).

POLLING PLACES: the Secretary of State's Polling Place Locator (myelectionday.sos.wyo.gov) answers one voter at a time,
and each county clerk designates the county's polling places and vote centers by resolution. polling_places.json is
"waiting" and says so; see POLL_HOW for what a person could save and where.
"""

import argparse
import collections
import csv
import datetime as dt
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
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import sd_geo as S  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "WY", "56", "Wyoming"
OUT = os.path.join(HERE, "ballot_geo", "wy")
CACHE = os.path.join(HERE, "states_cache", "wy_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://myelectionday.sos.wyo.gov/WYVOTES/Pages/VOSearch.aspx"      # the Secretary of State's Polling Place Locator

CENSUS = "https://www2.census.gov/"
BLOCK_URL = CENSUS + "geo/tiger/TIGER2020/TABBLOCK20/tl_2020_56_tabblock20.zip"
BAF_URL = CENSUS + "geo/docs/maps-data/data/baf2020/BlockAssign_ST56_WY.zip"
VTD_URL = CENSUS + "geo/tiger/TIGER2020PL/STATE/56_WYOMING/56/tl_2020_56_vtd20.zip"
SLDL_URL = S.SLDL_URL
SLDU_URL = S.SLDU_URL
COUSUB_URL = CENSUS + "geo/tiger/TIGER2025/COUSUB/tl_2025_56_cousub.zip"
PLACE_URL = CENSUS + "geo/tiger/TIGER2025/PLACE/tl_2025_56_place.zip"
UNSD_URL = CENSUS + "geo/tiger/TIGER2025/UNSD/tl_2025_56_unsd.zip"
ELSD_URL = CENSUS + "geo/tiger/TIGER2025/ELSD/tl_2025_56_elsd.zip"
COUNTY_URL = CENSUS + "geo/docs/reference/codes2020/cou/st56_wy_cou2020.txt"
SOS_PAGE = "https://sos.wyo.gov/Elections/Default.aspx"
TABLE_URL = "https://sos.wyo.gov/Elections/Docs/2026/2026_Districts_and_Precincts_by_County.pdf"
TITLE5_URL = "https://wyoleg.gov/statutes/compress/title05.pdf"

ARC_KINDS = ["county", "mcd", "house", "senate", "cd", "judicial"]      # each precinct piece lies wholly inside one of each (or no city)
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
AREA_SLACK = 0.02                 # a county's precincts (2020 blocks) and the Bureau's 2025 county may differ in area by this share
PLACE_LSAD = {"25": "city", "43": "town"}
NAMED_BY_CODE = {"56001", "56033"}      # Albany and Sheridan: the 2020 names are polling places, a person's home among them
CODE_ONLY = re.compile(r"'S\b|\bHOME\b|\bINC\b\.?|\bLLC\b|K-MOTIVE|\bRANCH\b", re.I)      # names elsewhere that name a home or a business
NO_VTD = "ZZZZZZ"                 # the Bureau's code for blocks in no voting district
ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth"]

clean = S.clean


def as_lonlat(rings):
    """Rings of vertex keys (as ia_geo.read_shapefile gives them) back as [longitude, latitude] points, for ia_geo.fabric."""
    return [[(x / 1e7, y / 1e7) for x, y in (G.vxy(k) for k in ring)] for ring in rings]


# ---------------------------------------------------------------- the Bureau's tables

def read_tables(bafpath, lpath, upath, vpath):
    """{block: (county, voting district code, House district, Senate district)} and {(county, code): the voting
    district's name} from the Bureau's files."""
    z = zipfile.ZipFile(bafpath)
    lines = z.read("BlockAssign_ST56_WY_VTD.txt").decode("utf-8").splitlines()
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
        if not (b[:5] == FIPS + c and v and re.fullmatch(r"\d{1,2}", h) and 1 <= int(h) <= 62 and re.fullmatch(r"\d{1,2}", s) and 1 <= int(s) <= 31):
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


def county_names(path):
    """{county code: "Albany County"} from the Bureau's list of county codes."""
    out = {}
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="|"))
    col = {h: i for i, h in enumerate(rows[0])}
    for r in rows[1:]:
        if r and r[col["STATEFP"]] == FIPS:
            out[FIPS + r[col["COUNTYFP"]]] = r[col["COUNTYNAME"]]
    if len(out) != 23:
        raise GeoError(f"    {os.path.basename(path)}: {len(out)} counties, not 23; stopping")
    return out


def vtd_name(county, code, raw):
    """A voting district's name as the page prints it: the Bureau's, unless it names a polling place that is a home or
    a business (then the code). Never a name the rule sets aside."""
    n = re.sub(r"\s+", " ", raw or "").strip(" -")
    if code == NO_VTD:
        return "Area in no voting district (2020)"
    if county in NAMED_BY_CODE or not n or CODE_ONLY.search(n):
        return "Voting district " + (re.sub(r"^0+(?=\d)", "", code) or code)
    if n.isupper() and re.search(r"[A-Z]{3}", n):
        n = " ".join(w if re.fullmatch(r"[0-9#\-./&()]+|[IVX]+|RS|GR|K-\d+", w) else w[:1] + w[1:].lower() for w in n.split(" "))
        n = re.sub(r"\b(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), n)
    return n


# ---------------------------------------------------------------- cities and towns, by each block's inside point

def read_places(path):
    """The incorporated cities and towns: [(record, rings as vertex keys)], in code order."""
    rows = I.read_shapefile(path, lambda r: r["STATEFP"] == FIPS and r["LSAD"] in PLACE_LSAD)
    if not 95 <= len(rows) <= 105 or any(r["CLASSFP"] != "C1" or r["FUNCSTAT"] != "A" for r, _ in rows):
        raise GeoError(f"    {os.path.basename(path)}: {len(rows)} incorporated cities and towns that do not fit the layout this builder was checked against; stopping")
    return sorted(rows, key=lambda x: x[0]["PLACEFP"])


def block_places(blockpath, places):
    """{block: place code or None}: the incorporated place whose 2025 limits hold the block's own inside point."""
    import shapefile
    z = zipfile.ZipFile(blockpath)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))[:-4]
    pl = []
    for r, rings in places:
        xy = [[G.vxy(k) for k in ring] for ring in rings]
        xs, ys = [p[0] for ring in xy for p in ring], [p[1] for ring in xy for p in ring]
        pl.append((r["PLACEFP"], (min(xs), min(ys), max(xs), max(ys)), xy))
    out = {}
    for rec in shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf"))).iterRecords():
        d = rec.as_dict()
        x, y = int(round(float(d["INTPTLON20"]) * 1e7)), int(round(float(d["INTPTLAT20"]) * 1e7))
        hit = None
        for code, (x0, y0, x1, y1), xy in pl:
            if x0 <= x <= x1 and y0 <= y <= y1 and G.in_rings(x, y, xy):
                hit = code
                break
        out[d["GEOID20"]] = hit
    return out


def read_units(blockpath, table, bplace, vname, say):
    """The precincts: the blocks of each 2020 voting district put together, one piece for each legislative district and
    each city or town (or none) it reaches. Returns (pre, polys): what is said of each, and its rings as vertex keys."""
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
        s = groups[table[b] + (bplace.get(b) or "",)]
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
    pieces = collections.Counter(k[:2] for k in groups)
    order = sorted(groups, key=lambda k: (k[0], k[1], G.natkey(k[2]), k[4]))
    part_no, n_of = {}, collections.Counter()
    for key in order:
        n_of[key[:2]] += 1
        part_no[key] = n_of[key[:2]]
    pre, polys, ids = [], [], set()
    for key in order:
        county, code, house, senate, place = key
        many = pieces[key[:2]] > 1
        pid = f"{county}.{re.sub(r'[^0-9A-Za-z-]', '-', code)}" + (f".{part_no[key]}" if many else "")
        if pid in ids:
            raise GeoError(f"    two precincts would share the id {pid}; stopping")
        ids.add(pid)
        name = vtd_name(county, code, vname[(county, code)])
        pre.append({"id": pid, "county": county, "vtd": code, "precinct": county + code, "house": house, "senate": senate,
                    "mcd": f"{STATE}-M-{place}" if place else None,
                    "name": name + (f", part {part_no[key]}" if many else ""), "vtdname": name, "parts": pieces[key[:2]]})
        polys.append(S.loops(groups[key]))
    say(f"      {len(seen):,} census blocks put together into {len(pieces):,} voting districts of 2020, {len(pre):,} pieces once cut by the 2022-plan "
        f"legislative districts and the cities' and towns' limits ({sum(1 for n in pieces.values() if n > 1)} voting districts reach more than one)")
    return pre, polys


# ---------------------------------------------------------------- the Secretary of State's 2026 precinct table

def code_numbers(code):
    """The numbers a precinct code reads as: 2020's 001-01 and 2026's 01-01 are both (1, 1); 2020's six digits 001101
    are (11, 1)."""
    code = clean(code)
    if re.fullmatch(r"\d{6}", code):
        return (int(code[:4]), int(code[4:]))
    return tuple(int(x) for x in re.findall(r"\d+", code)) or None


def read_sos_table(path, cname):
    """{county: {2026 precinct code: {"H": {House districts}, "S": {Senate districts}}}} from the Secretary of State's
    report. Only the county, district and code cells are read; the page heading lines are skipped."""
    from ballot import pdftext
    by_name = {S.name_fold(n.replace(" County", "")): c for c, n in cname.items()}
    pdf = pdftext.PDF(open(path, "rb").read())
    out = collections.defaultdict(lambda: collections.defaultdict(lambda: {"H": set(), "S": set()}))
    county = dist = None
    for page, res in pdf.pages():
        for _y, rs in pdftext.rows(pdf, page, res):
            t = pdftext.join(sorted(rs, key=lambda r: r[0])).strip()
            if not t or t.startswith(("County:", "User Name", "Districts By", "County District", "WyoReg")):
                continue
            m = re.fullmatch(r"([A-Z][A-Z .]+?)\s+(Senate|House) District (\d+)", t) or re.fullmatch(r"()(Senate|House) District (\d+)", t)
            if m:
                if m.group(1):
                    county = by_name.get(S.name_fold(m.group(1)))
                    if county is None:
                        raise GeoError(f"    the Secretary's precinct table names a county this builder does not know ({m.group(1)!r}); stopping")
                dist = (m.group(2)[0], str(int(m.group(3))))
                continue
            if county and dist and re.fullmatch(r"[0-9][0-9A-Za-z\-.]*", t):
                out[county][t][dist[0]].add(dist[1])
                continue
            raise GeoError(f"    the Secretary's precinct table has a line this reader was not checked against ({len(t)} characters); stopping")
    if len(out) != 23 or sum(len(v) for v in out.values()) < 350:
        raise GeoError(f"    the Secretary's precinct table was read as {len(out)} counties, {sum(len(v) for v in out.values())} precincts; stopping")
    return out


# ---------------------------------------------------------------- the ballot database (read-only)

def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'wy-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"wy_geo_overlay_{name}.json")
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


def school_id(name, cname3, db_school):
    """WY-S-<the county's three digits>-<number> from the Bureau's "Albany County School District 1"; the ballot
    database's own id where it files a county's one district under another (Johnson County's)."""
    m = re.fullmatch(r"(.+?) County School District (\d+)", clean(name))
    if not m or S.name_fold(m.group(1)) not in cname3:
        raise GeoError(f"    school districts: {name!r} does not read as '<County> County School District <number>'; stopping")
    c3 = cname3[S.name_fold(m.group(1))]
    return f"{STATE}-S-{c3}-{int(m.group(2))}", c3


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, plans):
    """Every Wyoming race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape, then place_shape for a ward's race). A race without a shape is listed with the
    reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    Sh = shape_ids
    by_layer, missing, matched, within = collections.Counter(), collections.OrderedDict(), 0, collections.Counter()
    for rid, level, kind, jur, jid, district, county_ids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        court = re.sub(r"_retention$", "", kind or "")
        hit, why = None, None
        if level == "statewide" or (court in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif level == "court" and not d and not county_ids and jid in (STATE, FIPS):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d.upper()))
        elif kind == "district_court" or (level == "court" and jid in Sh.get("judicial", {})):
            hit = ("judicial", jid)
        elif kind in ("county_commissioner", "county_council"):
            plan = plans.get(jid) or {}
            whole = not d or (f"{jid}|{d}" not in Sh.get("com", {}) and plan.get("plan") == 2 and d in (plan.get("districts") or []))
            hit = ("county", jid) if whole else ("com", f"{jid}|{d}")
            if not whole:
                why = "no statewide file has the lines of county commissioner districts"
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = "no statewide file has the lines of city wards; the city clerk keeps them (the page places the race on its city)"
                if jid in Sh.get("mcd", {}):
                    within["ward race placed on its city (mcd)"] += 1
        elif level == "school":
            hit = ("school", jid)
        elif level == "soil_water":
            why = "no official statewide file of conservation district lines could be read by a script"
        elif level == "hospital":
            why = "no statewide file has the lines of hospital districts; the county clerk keeps them"
        elif kind == "college_board":
            why = "community college districts and their trustee areas: no statewide file has the lines"
        else:
            why = "no statewide file has the lines of this kind of special district; the county clerk keeps them"
        if hit and hit[1] in Sh.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "placed_on_a_wider_shape": dict(within),
            "no_shape": list(missing.values()), "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places

POLL_WAITING = {
    "why": "Wyoming publishes no statewide list of polling places that could be read for these files: the Secretary of State's Polling Place "
           "Locator answers for one voter at a time, and each county clerk designates the county's polling places and vote centers. The "
           "Locator and the county clerk say where a voter votes.",
}
POLL_HOW = ("      polling places: waiting. There is no statewide file. The Secretary of State's Polling Place Locator "
            "(myelectionday.sos.wyo.gov) answers one address at a time and is not to be scripted. Each county clerk publishes the county's "
            "polling places or vote centers for November 3, 2026 (the clerks' pages are listed in sos.wyo.gov/Elections/Docs/WYCountyClerks.pdf). "
            "Were a person to save those 23 lists, the place for them is states_cache/wy_local/polling/<county code>_<county>.<pdf|html|xlsx> "
            "(56021_laramie.pdf and so on); a reader for them would still have to be written and checked against them.")


def polling_places(put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER, "status": "waiting", **POLL_WAITING}
    put("polling_places.json", doc)
    say(POLL_HOW)
    return {"file": "polling_places.json", "status": "waiting"}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Wyoming ballot map: 2020 voting districts, 2022-plan legislative districts, county, city and town, school and judicial district "
        "lines (the Census Bureau, W.S. 5-3-101, the Secretary of State's 2026 precinct table)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    urls = (BLOCK_URL, BAF_URL, VTD_URL, SLDL_URL, SLDU_URL, COUSUB_URL, PLACE_URL, UNSD_URL, ELSD_URL, COUNTY_URL)
    bpath, bafpath, vpath, lpath, upath, tpath, ppath, unpath, elpath, cpath = (path(u.rsplit("/", 1)[1]) for u in urls)
    for url, p in zip(urls, (bpath, bafpath, vpath, lpath, upath, tpath, ppath, unpath, elpath, cpath)):
        twin = os.path.join(HERE, "states_cache", "sd_local", os.path.basename(p))
        if url in (SLDL_URL, SLDU_URL) and not os.path.exists(p) and os.path.exists(twin):
            shutil.copyfile(twin, p)      # the same national file, already fetched once by ballot/sd_geo.py
        net.download(url, p, 3650, say=lambda *_a: None)
    tabpath = path("2026_Districts_and_Precincts_by_County.pdf")
    if refresh and os.path.exists(tabpath):
        os.utime(tabpath, (0, 0))
    net.download(TABLE_URL, tabpath, 30, say=lambda *_a: None)

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_long = county_names(cpath)
    cname = {c: names.get(("county", c)) or n for c, n in county_long.items()}
    cname3 = {S.name_fold(n.replace(" County", "")): c[2:] for c, n in county_long.items()}
    from ballot import state_local_wy as L
    from ballot.common import fold as lfold
    if refresh and os.path.exists(path("wy_statutes_title05.pdf")):
        os.remove(path("wy_statutes_title05.pdf"))
    jud_map, law_path = L.judicial_districts(CACHE, {lfold(n.replace(" County", "")): (c, n) for c, n in county_long.items()}, say=say)
    jud_of = {c: f"{STATE}-JD{no}" for no, cs in jud_map.items() for c in cs}
    sos = read_sos_table(tabpath, county_long)

    # ---- precincts: the 2020 voting districts, from blocks, cut by legislative districts and city and town limits
    table, vname = read_tables(bafpath, lpath, upath, vpath)
    places = read_places(ppath)
    bplace = block_places(bpath, places)
    pre, polys = read_units(bpath, table, bplace, vname, say)
    if sorted({p["county"] for p in pre}) != sorted(cname):
        raise GeoError("    the blocks and the Bureau's list of counties do not have the same 23 counties; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError("    a precinct has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precinct pieces, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; "
        f"{sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); {lone:,} lines are the state's edge"
        + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the Census Bureau's county subdivisions: only for the county lines of the area check
    cous = sorted(I.read_shapefile(tpath, lambda r: r["STATEFP"] == FIPS), key=lambda x: (x[0]["COUNTYFP"], x[0]["COUSUBFP"]))
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, [FIPS + r["COUNTYFP"] for r, _ in cous])
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- cities and towns (2025 limits), one fabric for the mcd layer
    mrow = {f"{STATE}-M-{r['PLACEFP']}": r for r, _ in places}
    mkeys, mpolys, marcs, msides, _mr, modd = I.fabric([(r, as_lonlat(rings)) for r, rings in places], lambda r: f"{STATE}-M-{r['PLACEFP']}")
    mkind = {k: PLACE_LSAD[r["LSAD"]] for k, r in mrow.items()}
    mname = {k: names.get(("mcd", k)) or r["NAMELSAD"] for k, r in mrow.items()}

    # ---- school districts: the unified districts and the one elementary district, one fabric
    db_school = {pid for (kind, pid) in names if kind == "school"}
    srows, sname, snces, odd_ids = [], {}, {}, []
    for spath, col in ((unpath, "UNSDLEA"), (elpath, "ELSDLEA")):
        for r, rings in I.read_shapefile(spath, lambda r: r["STATEFP"] == FIPS):
            if r[col] == "99997":
                continue                                      # School District Not Defined (Yellowstone National Park)
            sid, c3 = school_id(r["NAME"], cname3, db_school)
            if sid not in db_school:
                own = [i for i in db_school if i.startswith(f"{STATE}-S-{c3}-") and not re.fullmatch(rf"{STATE}-S-{c3}-\d+", i)]
                if len(own) == 1 and sum(1 for x in db_school if x.startswith(f"{STATE}-S-{c3}-")) == 1:
                    odd_ids.append((sid, own[0]))
                    sid = own[0]
            r = dict(r, _id=sid)
            srows.append((r, as_lonlat(rings)))
            sname[sid] = names.get(("school", sid)) or re.sub(r" (\d+)$", r" #\1", r["NAME"])
            snces[sid] = FIPS + r[col]
    schkeys, schpolys, scharcs, schsides, _sr, schodd = I.fabric(srows, lambda r: r["_id"])
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    say(f"      {len(mkeys)} cities and towns ({len(marcs):,} lines), {len(schkeys)} school districts ({len(scharcs):,} lines)"
        + (f"; the database's own ids kept for {', '.join(f'{a} as {b}' for a, b in odd_ids)}" if odd_ids else "")
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("places", modd), ("school", schodd), ("Census", codd)) if o))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    units_stamp = (bpath, bafpath, lpath, upath, ppath)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(*units_stamp, unpath, elpath), refresh, say)

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
        p["jud"] = jud_of[p["county"]]
        split += len(keep) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(keep) < 2
    say(f"      school districts by precinct: {split:,} precinct pieces are split between two or more districts, {none} lie in none, "
        f"{edges:,} others only brush a neighbouring district along a line; cities and towns: {sum(1 for p in pre if p['mcd']):,} pieces lie inside one")

    # ---- the area check: each county's precincts (2020 blocks) against the Bureau's 2025 county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in clist}
    if sorted(area_p) != clist:
        raise GeoError("    area check: the blocks and the 2025 county subdivisions do not have the same 23 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws; stopping")
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's 2025 Wyoming; the county furthest off is {cname[worst]} ({worst_pct:+.2f}%)")

    # ---- the Secretary's 2026 table against the pieces: the same numbers in the code, and the same House district
    listed, agree_s, by_num = 0, 0, collections.defaultdict(dict)
    for c, codes in sos.items():
        nums = collections.Counter(code_numbers(k) for k in codes)
        for k in codes:
            if nums[code_numbers(k)] == 1:
                by_num[c][code_numbers(k)] = k
    n_2020 = collections.Counter((p["county"], code_numbers(p["vtd"])) for p in {(q["county"], q["vtd"]): q for q in pre}.values())
    for p in pre:
        p["listed"] = None
        num = code_numbers(p["vtd"])
        k = by_num[p["county"]].get(num) if num and n_2020[(p["county"], num)] == 1 else None
        if k and p["house"] in sos[p["county"]][k]["H"]:
            p["listed"] = k
            listed += 1
            agree_s += p["senate"] in sos[p["county"]][k]["S"]
    say(f"      the Secretary's 2026 precinct table: {sum(len(v) for v in sos.values())} precincts in 23 counties; {listed:,} of {len(pre):,} pieces carry a 2020 "
        f"code that reads as a 2026 code of their county whose House district is theirs ({agree_s:,} of those also have their Senate district)")

    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": ["0"] * len(pre), "judicial": [p["jud"] for p in pre]}
    mask = []
    for r, l in sides:
        m = 0
        for bit, kind in enumerate(ARC_KINDS):
            if r < 0 or l < 0:
                if vals[kind][max(r, l)] is not None:
                    m |= 1 << bit
            elif vals[kind][r] != vals[kind][l]:
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
            if v is None:
                continue
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

    BLOCKS, BEF, PLACE, SCH, LAW, VTD, TAB, COUSUB = ("wy-census-tiger-2020-blocks", "wy-census-2024-legislative-bef", "wy-census-tiger-2025-places",
                                                      "wy-census-tiger-2025-school-districts", "wy-wyoleg-w.s.-5-3-101", "wy-census-2020-voting-districts",
                                                      "wy-sos-2026-districts-and-precincts-by-county", "wy-census-tiger-2025-cousub")
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[jud_of[c]].append(cname[c])
    layer("state", *own([STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, BLOCKS)
    layer("county", *own(vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, BLOCKS)
    layer("cd", *own(vals["cd"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": "Wyoming's one congressional district (the whole state)", "j": None, "d": v, "race": f"2026-{STATE}-H00"}, BLOCKS)
    layer("senate", *own(vals["senate"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Senate District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("house", *own(vals["house"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"House District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("judicial", *own(vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("judicial", v)) or f"{ORDINALS[int(v[len(STATE) + 3:]) - 1]} Judicial District", "j": v,
                     "d": v[len(STATE) + 3:], "counties": jud_counties[v]}, BLOCKS + "; which counties, from " + LAW)
    mg, mq, _l, _r = G.build_layer(marcs, msides, [mkeys], TOL_MCD)
    layer("mcd", mg, mq, TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, PLACE, zoom=MCD_ZOOM)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None, "nces": snces[v]}      # noqa: E731
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
        geoms, used_names = [], {"mcd": {}, "school": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "house": p["house"], "senate": p["senate"], "cd": "0",
                  "judicial": p["jud"], "school": p["school"], "as_of": 2020}
            if p["mcd"]:
                pr["mcd"] = p["mcd"]
                used_names["mcd"][p["mcd"]] = mname[p["mcd"]]
            if p["listed"]:
                pr["listed_2026"], pr["code_2026_said"] = True, p["listed"]
            for k in ("school_pct", "school_out", "school_edge"):
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

    polls = polling_places(put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    # ---- how the ballot database's commissioner races are filed (the 2026 lists give no districts: elected at large)
    plans = {}
    for _rid, _level, kind, _jur, jid, district, _c in info["races"]:
        if kind == "county_commissioner":
            e = plans.setdefault(str(jid), {"plan": 1, "districts": set(), "source": "the county clerks' 2026 candidate lists and sample ballots"})
            if district not in (None, ""):
                e["plan"] = 3
                e["districts"].add(str(district))
    for e in plans.values():
        e["districts"] = sorted(e["districts"], key=G.natkey)
        e["commissioners_elected"] = ("at large, by the whole county, as the 2026 lists file them" if e["plan"] == 1 else
                                      "from commissioner districts, by the 2026 lists; no statewide file has the lines")

    check = check_ids(info, shape_ids, plans)
    check["school_ids_taken_from_the_ballot_database"] = dict(odd_ids)
    check["pieces_matched_to_the_2026_precinct_table"] = listed
    check["school_districts_of_the_ballot_database_without_a_shape"] = sorted(db_school - set(schkeys))
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    cb = "U.S. Census Bureau"
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            {"id": BLOCKS, "agency": cb, "title": "TIGER/Line Shapefiles 2020, tabulation blocks, Wyoming (tl_2020_56_tabblock20.zip)",
             "about": "The 2020 census blocks: every line of the map's precincts, counties and legislative districts is a block's.",
             "url": BLOCK_URL, "fetched": mtime(bpath), "sha256": G.sha_file(bpath), "rows": len(table)},
            {"id": VTD, "agency": cb, "title": "2020 Census Block Assignment File, voting districts (BlockAssign_ST56_WY.zip), and the voting districts' names "
                                                "(tl_2020_56_vtd20.zip)",
             "about": "The precincts Wyoming's counties reported to the Bureau for the 2020 census: which voting district each block is in.",
             "url": BAF_URL, "names_url": VTD_URL, "fetched": mtime(bafpath), "sha256": G.sha_file(bafpath), "names_sha256": G.sha_file(vpath),
             "rows": len({(p["county"], p["vtd"]) for p in pre})},
            {"id": BEF, "agency": cb, "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip: the national files)",
             "about": "Which House and Senate district each block is in, under the plan the Legislature enacted in 2022 (62 House and 31 Senate districts).",
             "url": SLDL_URL, "upper_url": SLDU_URL, "fetched": mtime(lpath), "sha256": G.sha_file(lpath), "upper_sha256": G.sha_file(upath), "rows": len(table)},
            {"id": PLACE, "agency": cb, "title": "TIGER/Line Shapefiles 2025, places, Wyoming (tl_2025_56_place.zip): the incorporated cities and towns",
             "about": "City and town limits as the Bureau had them on January 1, 2025. A block belongs to the city or town its own inside point lies in.",
             "url": PLACE_URL, "fetched": mtime(ppath), "sha256": G.sha_file(ppath), "rows": len(mkeys)},
            {"id": SCH, "agency": cb, "title": "TIGER/Line Shapefiles 2025, unified and elementary school districts, Wyoming (tl_2025_56_unsd.zip, tl_2025_56_elsd.zip)",
             "about": "School district lines as the Bureau had them for the 2024-2025 school year, from the State's own reporting.",
             "url": UNSD_URL, "elementary_url": ELSD_URL, "fetched": mtime(unpath), "sha256": G.sha_file(unpath), "elementary_sha256": G.sha_file(elpath),
             "rows": len(schkeys)},
            {"id": COUSUB, "agency": cb, "title": "TIGER/Line Shapefiles 2025, county subdivisions, Wyoming (tl_2025_56_cousub.zip)",
             "about": "Read only for the county areas the precincts are checked against (Wyoming's county subdivisions are statistical, not governments).",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": LAW, "agency": "Wyoming Legislature", "title": "W.S. 5-3-101: Judicial districts enumerated (the Legislature's file of Title 5)",
             "url": TITLE5_URL, "fetched": mtime(law_path), "sha256": G.sha_file(law_path), "rows": 9},
            {"id": TAB, "agency": "Wyoming Secretary of State, Elections Division",
             "title": "Statewide Senate Districts and House Districts By County Report, 2026 (Districts and Precincts by County)",
             "about": "Each county's 2026 precinct codes and their House and Senate districts; read as a check (listed_2026).",
             "url": TABLE_URL, "page": SOS_PAGE, "fetched": mtime(tabpath), "sha256": G.sha_file(tabpath), "rows": sum(len(v) for v in sos.values())},
        ],
        "notes": {
            "lines": f"Every precinct, county and legislative line is a 2020 census block's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of "
                     "0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "Wyoming publishes no statewide map of its precincts as they stand in 2026. Each shape here is a voting district as the county "
                         "reported it to the Census Bureau for the 2020 census, cut wherever a legislative district of the 2022 plan or a city or town "
                         "limit crosses it. The Legislature redrew every district in 2022 and many counties renumbered their precincts since, so the "
                         "county clerk is the authority on a voter's precinct. listed_2026 marks a piece whose 2020 code reads as the same "
                         "numbers as a 2026 code of its county in the Secretary of State's table, which puts that precinct in the piece's House "
                         "district (code_2026_said gives the 2026 code). What a ballot "
                         "depends on (county, House and Senate district, judicial district, city or town, school district) does not depend on the precinct.",
            "places": "Wyoming has 99 incorporated cities and towns and no townships. A precinct piece lies wholly inside one city or town (mcd) or "
                      "outside every one: a piece in open country names no place. A block is given to the city or town its own inside point lies in, "
                      "by the limits of January 1, 2025, so a recent annexation that cuts a block is drawn to the nearest block line.",
            "commissioners": "County commissioners are elected by the voters of the whole county (the 2026 lists give no commissioner districts); "
                             "supervisor_plans says so county by county.",
            "legislative": "Each of the 62 House districts and 31 Senate districts elects one member. Which district a block is in is the Census Bureau's "
                           "2024 equivalency file's word for the 2022 plan, so a precinct piece's districts are exact.",
            "school": "School district lines are the Census Bureau's 2025 file. Which districts a precinct piece lies in is analysis, not an official list: a "
                      f"district counts when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each "
                      "district's share of the piece's area (land and water, not voters). Trustee areas within a district are not drawn.",
            "judicial": "The nine judicial districts are whole counties (W.S. 5-3-101); district and circuit court judges stand for retention in them.",
            "wards": "No statewide file has the lines of city wards: a ward's council race is placed on its city, and the city clerk says which ward an address is in.",
            "authority": "For which precinct an address votes in, and where, the county clerk and the Wyoming Secretary of State's Polling Place Locator are the authority.",
            "precinct_ids": "A precinct's id is its county's five digits, a full stop and the Census Bureau's 2020 voting district code (56021.0001-1); a "
                            "voting district cut by a legislative line or a city limit has a second full stop and the piece's number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct piece. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file; -2: outside Wyoming); names gives the names of the places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the 2020 voting district's as the Census Bureau's file gives it, or its code where that name is a "
                                            "polling place (and the piece's number where a line cuts it)",
                                    "county": "county id", "precinct": "the county's five digits and the Bureau's 2020 voting district code",
                                    "as_of": "the year of the precinct's lines (2020)",
                                    "listed_2026": "true where the Secretary of State's 2026 table has a precinct of the county whose code reads as the same numbers and whose House district is the piece's",
                                    "code_2026_said": "with listed_2026: that 2026 precinct code, as the Secretary's table writes it",
                                    "mcd": "the city or town the piece lies in (absent in open country)",
                                    "house": "House district", "senate": "Senate district", "cd": "congressional district (0: the whole state)",
                                    "judicial": "judicial district",
                                    "school": "list: the school districts the piece lies in, largest share first",
                                    "school_pct": "list, when the piece is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the piece's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the piece along a line (try them too when placing a point)",
                                    "c": "a point inside the piece's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "WY (j is 56)", "county": "the county's five-digit code (56021)",
                    "mcd": "WY-M- and the Census Bureau's place code (WY-M-13900); properties.t says city or town",
                    "house": "the district (11)", "senate": "the district (8)", "cd": "0; properties.race is the race for Congress",
                    "judicial": "WY-JD and the district's number (WY-JD1); d is the number",
                    "school": "WY-S-, the three digits of the county the district is named for, and its number (WY-S-021-1); properties.nces is the "
                              "federal district code"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "voting_districts_2020": len({(p["county"], p["vtd"]) for p in pre}), "counties": len(counties), "census_blocks": len(table),
                   "pieces_in_a_city_or_town": sum(1 for p in pre if p["mcd"]), "pieces_matched_to_the_2026_table": listed,
                   "precincts_in_the_2026_table": sum(len(v) for v in sos.values()),
                   "split_between_school_districts": split, "rings_too_small_for_the_grid": dropped_rings, "lines_with_a_precinct_on_one_side": lone,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Wyoming races have a shape"
        + (f"; {sum(check['placed_on_a_wider_shape'].values())} ward races are placed on their city" if check["placed_on_a_wider_shape"] else "")
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Wyoming ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the city or town at the point (None outside every one),
    # and the federal code (NCES) of its school district. County, place, 2026 legislative districts (upper and lower) and
    # school district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02:
    # geocoding.geo.census.gov, "geographies/coordinates", Current), an answer that owes nothing to the files tested here.
    # The judicial district is the county's (W.S. 5-3-101).
    ("the State Capitol, Cheyenne", -104.8198, 41.1402, {"county": "56021", "senate": "8", "house": "11", "judicial": "WY-JD1"}, "WY-M-13900", "5601980"),
    ("Casper City Hall", -106.3245, 42.8510, {"county": "56025", "senate": "28", "house": "56", "judicial": "WY-JD7"}, "WY-M-13150", "5604510"),
    ("Laramie, the university", -105.5800, 41.3140, {"county": "56001", "senate": "9", "house": "45", "judicial": "WY-JD2"}, "WY-M-45050", "5600730"),
    ("downtown Gillette", -105.5020, 44.2910, {"county": "56005", "senate": "24", "house": "53", "judicial": "WY-JD6"}, "WY-M-31855", "5601470"),
    ("downtown Rock Springs", -109.2240, 41.5870, {"county": "56037", "senate": "12", "house": "17", "judicial": "WY-JD3"}, "WY-M-67235", "5605302"),
    ("downtown Sheridan", -106.9560, 44.7970, {"county": "56033", "senate": "21", "house": "29", "judicial": "WY-JD4"}, "WY-M-69845", "5605695"),
    ("Jackson, the town square", -110.7625, 43.4799, {"county": "56039", "senate": "17", "house": "23", "judicial": "WY-JD9"}, "WY-M-40120", "5605830"),
    ("downtown Riverton", -108.3800, 43.0250, {"county": "56013", "senate": "26", "house": "55", "judicial": "WY-JD9"}, "WY-M-66220", "5605220"),
    ("downtown Cody", -109.0560, 44.5260, {"county": "56029", "senate": "18", "house": "24", "judicial": "WY-JD5"}, "WY-M-15760", "5602070"),
    ("downtown Evanston", -110.9630, 41.2680, {"county": "56041", "senate": "15", "house": "49", "judicial": "WY-JD3"}, "WY-M-25620", "5602760"),
    ("downtown Lander", -108.7310, 42.8330, {"county": "56013", "senate": "25", "house": "54", "judicial": "WY-JD9"}, "WY-M-44760", "5602870"),
    ("Arapahoe, Fremont County", -108.4890, 42.9690, {"county": "56013", "senate": "25", "house": "33", "judicial": "WY-JD9"}, None, "5600960"),
    ("open range north of Jeffrey City", -107.80, 42.60, {"county": "56013", "senate": "26", "house": "34", "judicial": "WY-JD9"}, None, "5602870"),
    ("Afton, Lincoln County", -110.9310, 42.7250, {"county": "56023", "senate": "16", "house": "21", "judicial": "WY-JD3"}, "WY-M-00245", "5604060"),
    ("downtown Torrington", -104.1840, 42.0650, {"county": "56015", "senate": "3", "house": "5", "judicial": "WY-JD8"}, "WY-M-77530", "5602990"),
    ("downtown Newcastle", -104.2050, 43.8540, {"county": "56045", "senate": "3", "house": "2", "judicial": "WY-JD6"}, "WY-M-56215", "5604830"),
    ("Bar Nunn", -106.3420, 42.9130, {"county": "56025", "senate": "30", "house": "58", "judicial": "WY-JD7"}, "WY-M-05245", "5604510"),
    ("Wilson, Teton County", -110.8750, 43.5000, {"county": "56039", "senate": "16", "house": "22", "judicial": "WY-JD9"}, None, "5605830"),
]
LINE_POINTS = [("the Laramie-Albany county line on Interstate 80", -105.28, 41.24, ("56021", "56001")),
               ("the Natrona-Converse county line near Glenrock", -106.07, 42.85, ("56025", "56009"))]
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
    check(len(index["counties"]) == 23, "there are not 23 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(layer_ids.get("senate") == {str(n) for n in range(1, 32)} and layer_ids.get("house") == {str(n) for n in range(1, 63)}
          and layer_ids.get("judicial") == {f"WY-JD{n}" for n in range(1, 10)} and layer_ids.get("cd") == {"0"} and len(layer_ids.get("county", ())) == 23
          and 95 <= len(layer_ids.get("mcd", ())) <= 105,
          "there are not 31 Senate districts, 62 House districts, 9 judicial districts, 23 counties, one congressional district and about 99 cities and towns")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precinct pieces, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place = collections.Counter(), collections.Counter()
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
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in pr["school"] else "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, edge = G.shape_at(files, "mcd", lon, lat)
            place["the piece's own city or town" if shape and shape["id"] == pr.get("mcd") else
                  "open country, as the piece says" if not shape and not pr.get("mcd") else
                  "within a city's 2025 limits, on a block whose inside point is not" if shape and not pr.get("mcd") else
                  "outside the 2025 limits of the city the piece names" if not shape else "in another city"] += 1
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
    check(place["the piece's own city or town"] + place["open country, as the piece says"] >= 0.97 * tested, f"the city or town at a piece's own point: {dict(place)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precinct pieces found again from a point inside them; every id a piece carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each piece's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city or town: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    nces = {g["id"]: g["properties"].get("nces") for g in files.topo("layers/school.json")[0]["objects"]["school"]["geometries"]}
    for name, lon, lat, want, mcd, code in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        sid = G.school_at(files, found["geometry"], lon, lat)
        ok &= check(sid is not None and sid in pr["school"] and nces.get(sid) == code, f"{name}: the school district at the point is {sid} ({nces.get(sid)}); the geocoder says {code}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check((shape and shape["id"]) == mcd and pr.get("mcd") == mcd, f"{name}: the mcd layer gives {shape and shape['id']} and the piece {pr.get('mcd')}; the place is {mcd}")
        for prop, kind in layer_for.items():
            shape2, _edge = G.shape_at(files, kind, lon, lat)
            ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the piece says {pr.get(prop)}")
        fdoc, _l = files.topo(rel[found["county"]])
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {fdoc['names'].get('mcd', {}).get(pr.get('mcd'), 'open country')}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, {pr['judicial']}, {fdoc['names']['school'].get(sid, sid)}; {found['edge']:.0f} m from the piece's line")

    # 4. county lines: the spot on one county's own drawing of the line nearest to a chosen point
    for name, lon, lat, pair in LINE_POINTS:
        doc, lines = files.topo(rel[pair[0]])
        bit = 1 << doc["arcKinds"].index("county")
        x, y = G.to_grid(lon, lat)
        cs = math.cos(math.radians(lat))
        best = None
        for a, pts in enumerate(lines):
            if doc["arcMask"][a] & bit and -1 in (doc["arcSides"][2 * a], doc["arcSides"][2 * a + 1]):
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

    # 5. polling places say what they are
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    check(not re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(polls)), "polling_places.json carries something that reads like a phone number or an e-mail address")
    say(f"      self-test: polling places: {polls.get('status')}")

    # 6. nothing set aside reaches a file: the Bureau's names of Albany's and Sheridan's voting districts, and names of homes and businesses
    blob = "".join(open(os.path.join(out, *c["file"].split("/")), encoding="utf-8").read() for c in index["counties"]) + json.dumps(index)
    check(not re.search(r"(?i)'s home|\bhome\b|\binc\b\.?|k-motive|fairgrounds exhibit", blob), "a county file or the index carries a voting district name this builder sets aside")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Wyoming's ballot map -> ballot_geo/wy/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/wy)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask for the Secretary of State's precinct table and the statute again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if not a.selftest:
        build(out=out, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
