"""
ballot/oh_geo.py - the geography behind Ohio's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py and ballot/sd_geo.py for the few things those states added, and changes nothing in
any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read all six.

    python ballot/oh_geo.py                 builds ballot_geo/oh/ and runs the self-test (the first build downloads
                                            280 MB of census blocks and lays districts over precincts: allow half an hour)
    python ballot/oh_geo.py --selftest      runs the self-test on the files already built
    python ballot/oh_geo.py --refresh       asks the map services, the statute and the polling place list again
    python ballot/oh_geo.py --out DIR       builds somewhere else (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

What Ohio publishes, and what that does to the files
----------------------------------------------------
Ohio has no statewide map file of its precincts as they stand in 2026: each county board of elections keeps the
county's own, and the Secretary of State's sites refuse scripts. The only statewide precinct lines a script may read are
the Census Bureau's 2020 voting districts: the precincts the boards reported for the 2020 census (8,933 of them, and
"not defined" for Lake Erie, which is left out). The Bureau's code for each is the Secretary of State's own precinct
code (Bureau 043ABS = Secretary 43ABS: county 43 in the alphabet, Lake; precinct ABS), so a precinct here can be tied
to the Secretary's current list by code, not by a guess at its name. A shape here is a 2020 voting district, cut
wherever a line of the 2024 legislative districts or the 2026 congressional districts crosses it, and index.json says
so in plain words: a board may have redrawn the precinct since. What a ballot depends on does not depend on the
precinct: the county, the legislative and congressional districts, the court of appeals district, the city, village
or township and the school district at a point are each taken from a current official file.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/oh_local/)
----------------------------------------------------------------------------------------------------------------------
  - Census blocks: the Census Bureau's TIGER/Line 2020 tabulation blocks of Ohio (tl_2020_39_tabblock20.zip, 276,428
    blocks). Only each block's number and outline are read.
  - Which voting district a block is in: the Bureau's 2020 Block Assignment File (BlockAssign_ST39_OH.zip, the VTD
    table), and the voting districts' names from tl_2020_39_vtd20.zip.
  - Which Ohio House and Senate district a block is in: the Bureau's 2024 State Legislative District Block Equivalency
    Files (sldl24.zip, sldu24.zip): the plan the Ohio Redistricting Commission adopted in September 2023, 99 House and
    33 Senate districts. A block is in exactly one district, so the legislative lines here are exact.
  - Which congressional district a block is in: the Ohio Redistricting Commission's own block assignment file for the
    Congressional Redistricting Plan it adopted on October 31, 2025 (redistricting.ohio.gov, district map 430, "October
    31 2025 CD BAF.xlsx"): the fifteen districts first used in 2026. Exact, block by block.
  - Cities and villages: TIGER/Line 2025 places (tl_2025_39_place.zip; incorporated places only). Townships, the county
    lines and the state's outline: TIGER/Line 2025 county subdivisions (tl_2025_39_cousub.zip).
  - County names: the Bureau's 2020 list of county codes (st39_oh_cou2020.txt).
  - School districts: "Ohio School District Boundaries" on the State of Ohio's GIS server (maps.ohio.gov; the Ohio
    Geographically Referenced Information Program and the Department of Education, 2025). Only the district's number
    (IRN) and name are asked for.
  - Court of appeals districts: R.C. 2501.01 on codes.ohio.gov (twelve districts, each whole counties); the lines are
    the county lines.
  - Cuyahoga County Council districts: the Cuyahoga County Board of Elections' "County Council Districts 2021 effective
    2022-2032" (the Board's own ArcGIS service). Only the district number is asked for.
  - Polling places: "Polling Locations - Full List with Precincts", the Secretary of State's list as the Ohio Emergency
    Management Agency publishes it ("updated before each election"; the copy read says May 2026). Asked for: county,
    the Secretary's precinct code, precinct name, the polling location's name and address, and its point. See POLLING
    PLACES.

What is built (ballot_geo/oh/): index.json, manifest.json, precincts/<county>.json (88), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, ward, com, school), school/<id>.json, polling_places.json and reader.js, each
as ballot/mn_geo.py describes. Coordinates are on the same grid (0.00001 degree, translate [-98, 43]; Ohio lies south
of 43 north, so its grid latitudes are negative numbers, which TopoJSON allows).

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "OH" (j = "39", the jurisdiction_id of statewide races)
  county    "39049"                 sl_places county id; jurisdiction_id of county offices and common pleas judges
  mcd       "OH-M-49056"            OH-M- and the Census code: a city's or village's place code, a township's county
                                    subdivision code (properties.t says which)
  ward      "OH-M-49056|Ward 3"     <city>|<ward as the council race words it>; only for a city whose council race is
                                    in the ballot database and whose precincts are named by ward (Mentor), as of 2020
  com       "39035|1"               Cuyahoga County Council district: <county>|<district>
  house     "23"   senate "18"   cd "14" (properties.race is the federal race id, 2026-OH-H14)
  judicial  "OH-CA10"               the court of appeals district (d = "10")
  school    "OH-S-043489"           OH-S- and the Department's six-digit district number (IRN)

Not drawn, because no statewide file has the lines: city wards (but Mentor's, above), Summit County Council's
districts (none is on the 2026 ballot) and State Board of Education districts (none is in the ballot database).
index.json lists every race without a shape under "check", with the reason, and under check.page_rule the two kinds of
contest whose shape is here but which the page's own rule looks for elsewhere.

POLLING PLACES
--------------
The Secretary of State's own sites refuse scripts. The Ohio Emergency Management Agency publishes the Secretary's list
of every precinct's polling location as an open map layer, with the Secretary's precinct code on every row, and that is
read here. Its own description says it is updated before each election and that the copy now up was updated in May
2026 (the primary), so polling_places.json is marked "unchecked", which a page must not show on the map, until a
person has confirmed that the layer carries the November 3, 2026 list and set POLL_CHECKED to True. A listed precinct
is tied to the map by the Secretary's code; a 2026 precinct whose code no 2020 voting district carries is listed under
its county without a shape.
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

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "OH", "39", "Ohio"
OUT = os.path.join(HERE, "ballot_geo", "oh")
CACHE = os.path.join(HERE, "states_cache", "oh_local")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://voterlookup.ohiosos.gov/"

CENSUS = "https://www2.census.gov/"
BLOCK_URL = CENSUS + "geo/tiger/TIGER2020/TABBLOCK20/tl_2020_39_tabblock20.zip"
BAF_URL = CENSUS + "geo/docs/maps-data/data/baf2020/BlockAssign_ST39_OH.zip"
VTD_URL = CENSUS + "geo/tiger/TIGER2020PL/STATE/39_OHIO/39/tl_2020_39_vtd20.zip"
SLDL_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip"
SLDU_URL = CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip"
COUSUB_URL = CENSUS + "geo/tiger/TIGER2025/COUSUB/tl_2025_39_cousub.zip"
PLACE_URL = CENSUS + "geo/tiger/TIGER2025/PLACE/tl_2025_39_place.zip"
COUNTY_URL = CENSUS + "geo/docs/reference/codes2020/cou/st39_oh_cou2020.txt"
ORC = "https://www.redistricting.ohio.gov/"
CD_PLAN = 430                                              # the Commission's number for the plan adopted October 31, 2025
CD_URL = ORC + f"api/public/districtmaps/{CD_PLAN}/download"
CD_LIST = ORC + "api/public/districtmaps/"
CD_FILE = "orc_congressional_plan_2025-10-31.zip"
CD_MEMBER = "October 31 2025 CD BAF.xlsx"
SCHOOL_SERVICE = "https://maps.ohio.gov/arcgis/rest/services/Hosted/Ohio_School_Districts_2025/FeatureServer/0"
SCHOOL_FIELDS = "irn,name"
COUNCIL_SERVICE = "https://services7.arcgis.com/GXM8JipKyc0m6HBi/arcgis/rest/services/County_Council_Districts_2021_effective_2022-2032/FeatureServer/0"
COUNCIL_FIELDS = "CCD21"                                   # never the voter counts the layer also carries
COUNCIL_COUNTY = "39035"
STATUTE_URL = "https://codes.ohio.gov/ohio-revised-code/section-2501.01"
POLL_SERVICE = "https://services6.arcgis.com/zxOMWqh0yAD6mMsJ/arcgis/rest/services/pollinglocs_final_for_AGOL/FeatureServer/0"
POLL_ITEM = "https://www.arcgis.com/home/item.html?id=9701092fb20b420897780fdeb1305d47"
POLL_FIELDS = "COUNTY_CO,COUNTY_NAME,STATE_PRECINCT_CODE,Precinct_Name,Precinct_Location,match_address"
POLL_TITLE = "Polling Locations - Full List with Precincts"
POLL_CHECKED = False              # True only when a person has confirmed that the layer carries the November 3, 2026 list

ARC_KINDS = ["county", "house", "senate", "cd", "judicial"]      # the kinds a precinct lies wholly inside, so its lines can draw them
SPLIT_SHARE = W.SPLIT_SHARE
TOL_MCD, MCD_ZOOM, MCD_THICK = I.TOL_MCD, I.MCD_ZOOM, I.MCD_THICK
NEAR_M = G.NEAR_M
AREA_SLACK = 0.02                 # a county's 2020 blocks and the Bureau's 2025 county may differ in area by this share
WATER = "ZZZZZZ"                  # the Bureau's "voting district not defined": Lake Erie
ORDINALS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6, "Seventh": 7, "Eighth": 8, "Ninth": 9, "Tenth": 10,
            "Eleventh": 11, "Twelfth": 12}
ROMANS = {"II", "III", "IV", "VI", "VII", "VIII", "IX"}

clean, slug = N.clean, N.slug


def title(text):
    """A name printed in capitals, in ordinary capitals; a word with a figure in it, a single letter and a Roman
    numeral stay as they are."""
    return re.sub(r"(?<![0-9A-Za-z])[A-Z]{2,}(?![0-9A-Za-z])", lambda m: m.group(0) if m.group(0) in ROMANS else m.group(0).capitalize(),
                  re.sub(r"\s+", " ", text or "").strip())


# ---------------------------------------------------------------- precincts: 2020 voting districts, from census blocks

def read_cd(path):
    """{block: congressional district} from the Commission's block assignment file."""
    import openpyxl
    z = zipfile.ZipFile(path)
    if CD_MEMBER not in z.namelist():
        raise GeoError(f"    {os.path.basename(path)}: no {CD_MEMBER!r} inside ({z.namelist()}); stopping")
    ws = openpyxl.load_workbook(io.BytesIO(z.read(CD_MEMBER)), read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = next(rows)
    if str(head[0]).strip() != "Block" or not str(head[1]).startswith("DistrictID"):
        raise GeoError(f"    {CD_MEMBER}: the heading is now {head!r}; stopping")
    out = {}
    for r in rows:
        if r[0] is None:
            continue
        b, d = str(r[0]).strip(), str(r[1]).strip()
        if not re.fullmatch(r"39\d{13}", b) or not re.fullmatch(r"1[0-5]|[1-9]", d) or b in out:
            raise GeoError(f"    {CD_MEMBER}: the row {r!r} does not fit the layout this builder was checked against; stopping")
        out[b] = d
    if sorted(set(out.values()), key=int) != [str(n) for n in range(1, 16)]:
        raise GeoError(f"    {CD_MEMBER}: not fifteen districts; stopping")
    return out


def read_tables(bafpath, lpath, upath, vpath, cdpath):
    """{block: (county, voting district code, House, Senate, congressional district)} for every block in a voting
    district, the blocks in none (Lake Erie), and {(county, code): the voting district's name}."""
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

    low, up, cd = bef(lpath, "GEOID,SLDLST"), bef(upath, "GEOID,SLDUST"), read_cd(cdpath)
    if set(low) != set(vtd) or set(up) != set(vtd) or set(cd) != set(vtd):
        raise GeoError("    the block assignment file, the legislative equivalency files and the Commission's congressional file do not list the same blocks; stopping")
    table, water = {}, set()
    for b, (c, v) in vtd.items():
        if v == WATER:
            water.add(b)
            continue
        h, s = re.sub(r"^0+", "", low[b]), re.sub(r"^0+", "", up[b])
        if not (b[:5] == FIPS + c and re.fullmatch(r"\d{3}[A-Z]{3}", v) and int(v[:3]) * 2 - 1 == int(c) and re.fullmatch(r"\d{1,2}", h) and re.fullmatch(r"\d{1,2}", s)):
            raise GeoError(f"    block {b}: county {c!r}, voting district {v!r}, House {low[b]!r}, Senate {up[b]!r} do not fit the layout this builder was checked against; stopping")
        table[b] = (FIPS + c, v, h, s, cd[b])
    nest = collections.defaultdict(set)
    for _c, _v, h, s, _d in table.values():
        nest[h].add(s)
    if len(nest) != 99 or any(len(s) != 1 for s in nest.values()) or len({next(iter(s)) for s in nest.values()}) != 33:
        raise GeoError("    the equivalency files do not give 99 House districts, each inside one of 33 Senate districts; stopping")
    import shapefile
    zz = zipfile.ZipFile(vpath)
    base = next(n for n in zz.namelist() if n.endswith(".dbf"))
    vname = {(FIPS + r["COUNTYFP20"], r["VTDST20"].strip()): r["NAME20"] for r in (x.as_dict() for x in shapefile.Reader(dbf=io.BytesIO(zz.read(base))).iterRecords())}
    missing = {(c, v) for c, v, _h, _s, _d in table.values()} - set(vname)
    if missing:
        raise GeoError(f"    {len(missing)} voting districts of the block assignment file are not in {os.path.basename(vpath)} (e.g. {sorted(missing)[0]}); stopping")
    return table, water, vname, {h: next(iter(s)) for h, s in nest.items()}


def read_units(blockpath, table, water, vname, say):
    """The precincts: the blocks of each 2020 voting district put together, one piece for each legislative and
    congressional district it reaches. Returns (pre, polys): what is said of each, and its rings as vertex keys."""
    import shapefile
    z = zipfile.ZipFile(blockpath)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    groups, seen, twice = collections.defaultdict(set), set(), 0
    said = {"in": collections.Counter(), "all": collections.Counter()}      # the Bureau's own land and water area of the blocks, by county
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
    order = sorted(groups, key=lambda k: (k[0], k[1], G.natkey(k[2]), G.natkey(k[4])))
    part_no, count = {}, collections.Counter()
    for key in order:
        count[key[:2]] += 1
        part_no[key] = count[key[:2]]
    pre, polys, ids = [], [], set()
    for key in order:
        county, code, house, senate, cd = key
        pid = f"{county}.{code}" + (f".{part_no[key]}" if pieces[key[:2]] > 1 else "")
        if pid in ids:
            raise GeoError(f"    two precincts would share the id {pid}; stopping")
        ids.add(pid)
        name = title(vname[(county, code)]) or f"Voting district {code[3:]}"
        pre.append({"id": pid, "county": county, "vtd": code, "precinct": county + code, "code": f"{int(code[:3])}{code[3:]}", "house": house, "senate": senate,
                    "cd": cd, "name": name + (f", part {part_no[key]}" if pieces[key[:2]] > 1 else ""), "vtdname": name, "rawname": vname[(county, code)],
                    "parts": pieces[key[:2]]})
        polys.append(S.loops(groups[key]))
    say(f"      {len(seen):,} census blocks ({len(water)} of them Lake Erie, in no voting district) put together into {len(pieces):,} voting districts of 2020, "
        f"{len(pre):,} pieces once cut by the 2024 legislative and 2026 congressional districts ({sum(1 for n in pieces.values() if n > 1)} voting districts reach more than one)")
    return pre, polys, said


def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'oh-%'"):
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
    if len(out) != 88:
        raise GeoError(f"    {os.path.basename(path)}: {len(out)} counties, not 88; stopping")
    return out


def appeals(path, cname, refresh, say):
    """{county: court of appeals district number} from R.C. 2501.01, kept in a small cache; the statute's own sentence
    is the source."""
    if not G._fresh(path, refresh):
        try:
            net.patient_lookups()
            raw = net.get(STATUTE_URL, timeout=120)
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<script.*?</script>|<style.*?</style>|<[^>]+>", " ", raw.decode("utf-8", "replace"))))
            found = {}
            for word, names in re.findall(r"\([A-L]\) (\w+) district: (.*?)[;.]", text):
                found[str(ORDINALS[word])] = [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", names) if n.strip()]
            if "twelve judicial court of appeals districts" not in text or sorted(found, key=int) != [str(n) for n in range(1, 13)]:
                raise GeoError("    R.C. 2501.01 no longer reads as twelve districts, each a list of counties")
            eff = re.search(r"Effective: ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
            with open(path + ".part", "w", encoding="utf-8") as fh:
                json.dump({"url": STATUTE_URL, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
                           "effective": eff.group(1) if eff else None, "districts": found}, fh, indent=1)
            os.replace(path + ".part", path)
        except Exception as e:  # noqa: BLE001
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                raise
            say(f"      could not read R.C. 2501.01 again ({e}); using the copy on disk")
    doc = json.load(open(path, encoding="utf-8"))
    by_name = {n.replace(" County", ""): c for c, n in cname.items()}
    out = {}
    for no, names in doc["districts"].items():
        for n in names:
            if n not in by_name or by_name[n] in out:
                raise GeoError(f"    R.C. 2501.01: {n!r} is not a county, or is in two districts; stopping")
            out[by_name[n]] = no
    if len(out) != 88:
        raise GeoError(f"    R.C. 2501.01 places {len(out)} counties, not 88; stopping")
    return out, doc


def adopted_plan(path, refresh):
    """What the Commission's own list says of the congressional plan (kept in a small cache): it must be marked adopted."""
    if not G._fresh(path, refresh):
        try:
            rows = json.loads(net.get(CD_LIST, accept="application/json", timeout=120))
            row = next(r for r in rows if r.get("id") == CD_PLAN)
            with open(path + ".part", "w", encoding="utf-8") as fh:      # the row's "name" (who sent the plan in) is not kept
                json.dump({"id": CD_PLAN, "adopted": bool(row.get("isAdopted")), "congressional": row.get("type") == 1, "title": row.get("submittedByOrganization"),
                           "submitted": (row.get("submissionTime") or "")[:10], "fetched": dt.date.today().isoformat()}, fh)
            os.replace(path + ".part", path)
        except Exception:  # noqa: BLE001
            if not os.path.exists(path):
                raise
    doc = json.load(open(path, encoding="utf-8"))
    if not (doc.get("adopted") and doc.get("congressional")):
        raise GeoError(f"    the Ohio Redistricting Commission's list does not mark district map {CD_PLAN} as an adopted congressional plan; stopping")
    return doc


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed."""
    path = os.path.join(CACHE, f"oh_geo_overlay_{name}.json")
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
    path = os.path.join(CACHE, "oh_geo_overlay_places.json")
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


# ---------------------------------------------------------------- wards, where the precincts' own names give them

def named_wards(pre, info, census_name, listed_names):
    """Council wards for the cities whose council races the ballot database carries by ward, where the 2020 voting
    districts of the city are named "<CITY> CITY <ward><letter>" and the Secretary's current list still names the very
    same precinct codes the same way. Returns ({precinct number: "<city>|Ward n"}, the cities drawn, and why not for the rest)."""
    want = collections.defaultdict(set)
    for _rid, level, kind, _jur, jid, district, _seat in info["races"]:
        if level == "city" and kind == "council" and district and re.fullmatch(r"Ward \d+", str(district)):
            want[str(jid)].add(str(district))
    vals, drawn, why = {}, {}, {}
    for jid, asked in sorted(want.items()):
        base = re.sub(r" (city|village)$", "", census_name.get(jid, "")).upper()
        if not base:
            why[jid] = "the Census Bureau's file has no place of this code"
            continue
        pat = re.compile(rf"(?:PRECINCT )?{re.escape(base)}(?: CITY)? (\d+)-?([A-Z])")
        mine = {}
        for i, p in enumerate(pre):
            m = pat.fullmatch(p["rawname"].strip().upper())
            if m and p["mcd"] == jid:
                mine[i] = m.group(1)
        codes = {(pre[i]["county"], pre[i]["vtd"]) for i in mine}
        now = {k: pat.fullmatch(n.strip().upper()) for k, n in listed_names.items() if pat.fullmatch(n.strip().upper())}
        same = set(now) == codes and all(now[(pre[i]["county"], pre[i]["vtd"])].group(1) == w for i, w in mine.items())
        if not mine or not all(a.split()[1] in set(mine.values()) for a in asked):
            why[jid] = "the 2020 voting districts of the city are not named by ward"
        elif not same:
            why[jid] = "the Secretary of State's current precinct list no longer names the city's precincts as the 2020 voting districts were named, so the wards may have been redrawn"
        else:
            for i, w in mine.items():
                vals[i] = f"{jid}|Ward {w}"
            drawn[jid] = sorted({f"Ward {w}" for w in mine.values()}, key=G.natkey)
    return vals, drawn, why


# ---------------------------------------------------------------- ids against the ballot database

PAGE_RULE = {"court_of_appeals": "the shape is judicial:<jurisdiction_id> (OH-CA10); the page's rule looks for a court's jurisdiction_id among the cities and the counties",
             "county_council": "the shape is com:<county>|<district> (39035|1); the page's rule draws every county office on the whole county"}


def check_ids(info, shape_ids, ward_why):
    """Every Ohio race in the ballot database against the shapes. A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    S_ = shape_ids
    by_layer, missing, matched, other_rule = collections.Counter(), collections.OrderedDict(), 0, collections.Counter()
    for rid, level, kind, jur, jid, district, _seat in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide" or kind == "supreme_court" or (kind == "court_of_appeals" and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "court_of_appeals":
            hit = ("judicial", jid)
        elif kind == "county_council" and d:
            hit = ("com", f"{jid}|{d}")
            why = "no file read here has the lines of this county's council districts"
        elif level == "county" or (level == "court" and jid in S_.get("county", {})):
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = "no statewide file has the lines of city wards; " + ward_why.get(jid, "the county board of elections keeps them")
        elif level == "school":
            hit = ("school", jid)
        else:
            why = "no source carries a boundary for this kind of district"
        if hit and hit[1] in S_.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            if kind in PAGE_RULE and hit[0] in ("judicial", "com"):
                other_rule[kind] += 1
        else:
            key = (level, kind, jur, jid, district)
            e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": district,
                                         "races": 0, "why": why or "no shape carries this id"})
            e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "part_of_a_shape": [],
            "page_rule": [{"office_kind": k, "races": n, "note": PAGE_RULE[k]} for k, n in sorted(other_rule.items())]}


# ---------------------------------------------------------------- polling places (the Secretary's list, as the Emergency Management Agency publishes it)

POLL_WAITING = {
    "why": "The Ohio Secretary of State's list of polling locations for November 3, 2026 could not be read when these files were built. The Secretary's "
           "voter lookup and the county board of elections say where a voter votes.",
}
POLL_UNCHECKED_WHY = ("      polling places: read from the Secretary's list as the Ohio Emergency Management Agency publishes it, and marked 'unchecked', so a page "
                      "does not show them. The layer says it is updated before each election and was last updated in May 2026; when it carries the November 3, "
                      "2026 list, set POLL_CHECKED in ballot/oh_geo.py. The map's precinct lines are the 2020 ones, tied to the list by the Secretary's precinct code.")


def fetch_points(path, refresh, say):
    """Every row of the polling location layer with its point, cached as gzipped JSON."""
    if G._fresh(path, refresh):
        return json.load(gzip.open(path, "rt", encoding="utf-8"))
    net.patient_lookups()
    rows, offset = [], 0
    while True:
        url = (f"{POLL_SERVICE}/query?where={quote('1=1')}&outFields={POLL_FIELDS}&returnGeometry=true&outSR=4326&geometryPrecision=6"
               f"&orderByFields=OBJECTID&resultOffset={offset}&resultRecordCount=2000&f=json")
        j = json.loads(net.get(url, timeout=300, accept="application/json"))
        if "error" in j:
            raise GeoError(f"    {POLL_SERVICE}: {j['error']}")
        feats = j.get("features", [])
        rows += [[f["attributes"], [f["geometry"]["x"], f["geometry"]["y"]] if f.get("geometry") else None] for f in feats]
        offset += len(feats)
        if not feats or not j.get("exceededTransferLimit"):
            break
        time.sleep(1.0)
    count = json.loads(net.get(f"{POLL_SERVICE}/query?where={quote('1=1')}&returnCountOnly=true&f=json", accept="application/json")).get("count")
    if count != len(rows):
        raise GeoError(f"    {POLL_SERVICE}: {len(rows):,} rows came, but the service counts {count}")
    out = {"service": POLL_SERVICE, "fields": POLL_FIELDS, "fetched": dt.date.today().isoformat(), "rows": rows}
    with gzip.open(path + ".part", "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows fetched")
    return out


def read_poll_rows(doc, cname):
    """The list's rows: [{"county", "vtd" (the Census form of the Secretary's code), "code", "precinct", "name",
    "address", "city", "zip", "lonlat"}]. A row that does not fit the layout stops the reading."""
    by_no = {n + 1: c for n, c in enumerate(sorted(cname, key=lambda c: cname[c]))}
    out, seen = [], set()
    for a, pt in doc["rows"]:
        no, code = a.get("COUNTY_CO"), clean(a.get("STATE_PRECINCT_CODE")).upper()
        m = re.fullmatch(r"0*(\d{1,2})[-\s]*(?:[A-Z][-\s])?([A-Z]{3})", code)
        county = by_no.get(no)
        if not m or int(m.group(1)) != no or county is None or re.sub(r"[^A-Z]", "", cname[county].replace(" County", "").upper()) != re.sub(r"[^A-Z]", "", clean(a.get("COUNTY_NAME")).upper()):
            raise GeoError(f"    polling places: the row with precinct code {code!r} (county {no!r}) does not fit the layout this reader was checked against")
        vtd = f"{no:03d}{m.group(2)}"
        if (county, vtd) in seen:
            raise GeoError(f"    polling places: precinct {code!r} is listed twice")
        seen.add((county, vtd))
        parts = [x.strip() for x in clean(a.get("match_address")).split(",")]
        if len(parts) >= 4 and parts[-2] == "Ohio" and re.fullmatch(r"\d{5}", parts[-1]):
            address, city, zipc = ", ".join(parts[:-3]), parts[-3], parts[-1]
        else:
            address, city, zipc = ", ".join(p for p in parts if p), "", ""
        out.append({"county": county, "vtd": vtd, "code": f"{no}{m.group(2)}", "precinct": title(re.sub(r"^PRECINCT\s+", "", clean(a.get("Precinct_Name")))),
                    "rawname": clean(a.get("Precinct_Name")), "name": title(clean(a.get("Precinct_Location"))), "address": address, "city": city, "zip": zipc,
                    "lonlat": [round(pt[0], 5), round(pt[1], 5)] if pt else None})
    if len(out) < 8000 or len({r["county"] for r in out}) != 88:
        raise GeoError(f"    polling places: {len(out):,} rows in {len({r['county'] for r in out})} counties is not the statewide list this reader was checked against")
    return out


def polling_places(pre, cname, cbox, rows, about, put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    if rows is None:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        return {"file": "polling_places.json", "status": "waiting"}
    units = collections.defaultdict(list)
    for p in pre:
        units[(p["county"], p["vtd"])].append(p["id"])
    places, order, precinct, by_county, far, at_of = {}, [], {}, collections.OrderedDict(), 0, {}
    for r in sorted(rows, key=lambda r: (r["county"], G.natkey(r["precinct"]), r["code"])):
        key = (r["county"], r["name"].lower(), r["address"].lower(), r["city"].lower())
        if key not in places:
            pt, b = r["lonlat"], cbox[r["county"]]
            if pt and not (b[0] - 0.05 <= pt[0] <= b[2] + 0.05 and b[1] - 0.05 <= pt[1] <= b[3] + 0.05):
                pt, far = None, far + 1
            places[key] = {"name": r["name"], "address": r["address"], "city": r["city"], "zip": r["zip"], "type": None, "hours": None, "lonlat": pt,
                           "county": r["county"], "precincts": []}
            if pt:
                places[key]["from"] = "the Ohio Emergency Management Agency's layer (the address placed on the map by that agency)"
            order.append(key)
        at = at_of.setdefault(key, len(order) - 1)
        on_map = sorted(units.get((r["county"], r["vtd"]), []))
        for pid in on_map:
            precinct[pid] = at
            places[key]["precincts"].append(pid)
        by_county.setdefault(r["county"], []).append({"precinct": r["precinct"], "code": r["code"], "places": [at], "on_the_map": on_map})
    plist = [places[k] for k in order]
    status = "loaded" if POLL_CHECKED else "unchecked"
    matched = sum(1 for rows_ in by_county.values() for r in rows_ if r["on_the_map"])
    doc.update(status=status,
               source=dict({"agency": "Ohio Secretary of State; published by the Ohio Emergency Management Agency", "title": POLL_TITLE, "url": POLL_ITEM,
                            "service": POLL_SERVICE, "fetched": about.get("fetched"), "sha256": about.get("sha256"),
                            "says": "Polling locations from the Ohio Secretary of State's office, updated May 2026; updated before each election."},
                           **({"current_to": about["current_to"]} if about.get("current_to") else {})),
               places=plist, precinct=dict(sorted(precinct.items())), no_place={}, by_county=by_county, counties_not_on_the_list=sorted(c for c in cname if c not in by_county),
               note="by_county is the Secretary of State's list as published: each county's precincts by name and by the Secretary's precinct code, with the place "
                    "of each (numbers into places). The map's precinct lines are the ones the county boards reported to the Census Bureau in 2020; precinct "
                    "ties a map precinct to the list where the Secretary's code is the same, and a board may have redrawn the precinct since. The list read "
                    "was last updated for the May 2026 primary, so nothing here is shown until it is confirmed for November 3, 2026.")
    put("polling_places.json", doc)
    n_listed = sum(len(v) for v in by_county.values())
    say(f"      polling places: {len(rows):,} precincts on the list, {len(plist):,} places ({sum(1 for p in plist if p['lonlat']):,} with a point, {far} points thrown out "
        f"as outside the county); {matched:,} listed precincts carry the code of a 2020 voting district; {len(precinct):,} of the map's {len(pre):,} precincts carry a listed place")
    if not POLL_CHECKED:
        say(POLL_UNCHECKED_WHY)
    return {"file": "polling_places.json", "status": status, "places": len(plist), "with_coordinates": sum(1 for p in plist if p["lonlat"]), "rows": len(rows),
            "precincts_listed": n_listed, "listed_and_matched_to_the_map": matched, "map_precincts_with_a_listed_place": len(precinct),
            "precincts_with_several_places": 0, "counties_not_on_the_list": doc["counties_not_on_the_list"]}


# ---------------------------------------------------------------- the build

def build(out=OUT, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Ohio ballot map: 2020 voting districts, 2024 legislative districts, 2026 congressional districts, county, city, village, township and school "
        "district lines (the Census Bureau, the Ohio Redistricting Commission, the State's GIS server)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    urls = (BLOCK_URL, BAF_URL, VTD_URL, SLDL_URL, SLDU_URL, COUSUB_URL, PLACE_URL, COUNTY_URL)
    bpath, bafpath, vpath, lpath, upath, tpath, plpath, cpath = (path(u.rsplit("/", 1)[1]) for u in urls)
    cdpath = path(CD_FILE)
    net.patient_lookups()
    for url, p in list(zip(urls, (bpath, bafpath, vpath, lpath, upath, tpath, plpath, cpath))) + [(CD_URL, cdpath)]:
        net.download(url, p, 3650, say=lambda *_a: None)
    plan = adopted_plan(path("oh_geo_about_cd_plan.json"), refresh)
    scpath, ccpath = path("ogrip_school_districts_2025_geometry_4326.json.gz"), path("cuyahoga_boe_council_districts_2022_geometry_4326.json.gz")
    scdoc = W.fetch_full(SCHOOL_SERVICE, SCHOOL_FIELDS, scpath, 40, "objectid", refresh, say)
    ccdoc = W.fetch_full(COUNCIL_SERVICE, COUNCIL_FIELDS, ccpath, 11, "FID", refresh, say)
    edited = {k: W.layer_edited(svc, path(f"oh_geo_about_{k}.json"), refresh) for k, svc in (("school", SCHOOL_SERVICE), ("council", COUNCIL_SERVICE), ("polls", POLL_SERVICE))}

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    county_long = county_names(cpath)
    cname = {c: names.get(("county", c)) or n for c, n in county_long.items()}
    jud_no, jud_doc = appeals(path("orc_2501.01.json"), county_long, refresh, say)

    pollpath, poll_rows, poll_about = path("oema_sos_polling_locations.json.gz"), None, {}
    try:
        pdoc = fetch_points(pollpath, refresh, say)
        poll_rows = read_poll_rows(pdoc, county_long)
        poll_about = dict(edited["polls"], fetched=pdoc.get("fetched"), sha256=G.sha_file(pollpath))
    except (Exception, GeoError) as e:  # noqa: BLE001  the map does not depend on this list
        say(f"      polling places: waiting; the list could not be read ({str(e).strip()})")

    # ---- precincts: the 2020 voting districts, from blocks; every shared line kept once
    table, water, vname, senate_of = read_tables(bafpath, lpath, upath, vpath, cdpath)
    pre, polys, said = read_units(bpath, table, water, vname, say)
    if sorted({p["county"] for p in pre}) != sorted(cname):
        raise GeoError("    the blocks and the Bureau's list of counties do not have the same 88 counties; stopping")
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
    if len({r["COUNTYFP"] for r, _ in cous}) != 88 or any(r["LSAD"] not in ("00", "25", "44", "47") for r, _ in cous):
        raise GeoError(f"    {os.path.basename(tpath)}: not 88 counties of cities, villages and townships; stopping")
    carcs, csides, _crings, codd = G.topology([rings for _r, rings in cous])
    ccounty = [FIPS + r["COUNTYFP"] for r, _ in cous]
    is_town = [r["LSAD"] == "44" and r["CLASSFP"] in ("T1", "T5") for r, _ in cous]      # a township with a government of its own
    town_rows = [(r, rings) for (r, rings), t in zip(cous, is_town) if t]
    town_key_all = [f"{STATE}-M-{r['COUSUBFP']}" for r, _ in cous]
    town_val = [k if t else None for k, t in zip(town_key_all, is_town)]
    cities_ = sorted(I.read_shapefile(plpath, lambda r: r["STATEFP"] == FIPS and r["LSAD"] in ("25", "47")), key=lambda x: x[0]["PLACEFP"])
    parcs, psides, _prings, podd = G.topology([rings for _r, rings in cities_])
    city_key = [f"{STATE}-M-{r['PLACEFP']}" for r, _ in cities_]
    towns = sorted({k for k in town_val if k})             # a township that reaches into a second county is two rows of the Bureau's file and one place
    town_names = collections.defaultdict(set)
    for k, (r, _), t in zip(town_key_all, cous, is_town):
        if t:
            town_names[k].add(r["NAMELSAD"])
    if len(set(city_key)) != len(city_key) or set(city_key) & set(towns) or any(len(n) != 1 for n in town_names.values()):
        raise GeoError("    a city and a township, or two places of different names, share a code; stopping")
    city_set = set(city_key)
    census_name = {k: r["NAMELSAD"] for k, (r, _), t in zip(town_key_all, cous, is_town) if t}
    census_name.update({k: r["NAMELSAD"] for k, (r, _) in zip(city_key, cities_)})
    mkind = {k: "township" for k in towns}
    mkind.update({k: "city" if r["LSAD"] == "25" else "village" for k, (r, _) in zip(city_key, cities_)})
    mname = {k: names.get(("mcd", k)) or n for k, n in census_name.items()}
    town_county = collections.defaultdict(set)
    for k, c, t in zip(town_key_all, ccounty, is_town):
        if t:
            town_county[k].add(c)
    chains, _pairs, cshapes, _loose = G.dissolve(carcs, csides, ccounty)
    county_rings = {c: [G.ring_xy(ring, chains) for ring, _p in rings] for c, rings in cshapes.items()}
    clist = sorted(county_rings)

    # ---- school districts and Cuyahoga's council districts: each its own fabric
    for a, _r in scdoc["rows"]:
        if not re.fullmatch(r"\d{6}", clean(a["irn"])) or not clean(a["name"]):
            raise GeoError(f"    school districts: the row numbered {a.get('irn')!r} does not fit the layout this builder was checked against; stopping")
    sid = lambda a: f"{STATE}-S-{clean(a['irn'])}"      # noqa: E731
    schkeys, _schpolys, scharcs, schsides, _sr, schodd = I.fabric(N.merge_rows(scdoc["rows"], sid), sid)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    sname = {sid(a): names.get(("school", sid(a))) or title(clean(a["name"])) for a, _r in scdoc["rows"]}
    if len(ccdoc["rows"]) != 11 or sorted(int(a["CCD21"]) for a, _r in ccdoc["rows"]) != list(range(1, 12)):
        raise GeoError("    Cuyahoga County Council districts: not eleven districts numbered 1 to 11; stopping")
    cckey = lambda a: f"{COUNCIL_COUNTY}|{int(a['CCD21'])}"      # noqa: E731
    cckeys, ccpolys, ccarcs, ccsides, _ccr, ccodd = I.fabric(N.merge_rows(ccdoc["rows"], cckey), cckey)
    say(f"      {len(schkeys)} school districts ({len(scharcs):,} lines), {len(cckeys)} Cuyahoga County Council districts, {len(cous):,} Census county subdivisions "
        f"({len(towns):,} townships with a government of their own), {len(cities_):,} cities and villages"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("school", schodd), ("council", ccodd), ("Census", codd), ("places", podd)) if o))

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    units_stamp = (bafpath, lpath, upath, cdpath)          # the blocks' own file is 280 MB and never changes: its name stands for it
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(*units_stamp, scpath), refresh, say)
    o_mcd = place_overlay_cached(pre_rings, I.rings_xy([r for _a, r in cities_]), I.rings_xy([r for _a, r in town_rows]), stamp(*units_stamp, tpath, plpath), refresh, say)
    place_keys = city_key + [f"{STATE}-M-{r['COUSUBFP']}" for r, _ in town_rows]
    cuy = [i for i, p in enumerate(pre) if p["county"] == COUNCIL_COUNTY]
    o_cc = overlay_cached("cuyahoga-council", [pre_rings[i] for i in cuy], I.rings_xy(ccpolys), stamp(*units_stamp, ccpath), refresh, say)

    several = no_place = 0
    for p, got in zip(pre, o_mcd):
        rows = sorted(((place_keys[d], s, t) for d, s, t in got), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t and (k in city_set or p["county"] in town_county.get(k, ()))] or [(k, s) for k, s, _t in rows[:1]]
        p["mcd"] = own[0][0] if own else None
        p["mcd_all"] = [k for k, _s in own]
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in own] if len(own) > 1 else None
        several += len(own) > 1
        no_place += not own
        p["jud"] = f"{STATE}-CA{jud_no[p['county']]}"
        p["com"] = None
    if no_place > 5:
        raise GeoError(f"    {no_place} precincts lie in no city, village or township; stopping")
    for i, got in zip(cuy, o_cc):
        pre[i]["com"] = S.most(pre[i], got, cckeys, "com")
    no_cc = [pre[i]["id"] for i in cuy if not pre[i]["com"]]
    if no_cc:
        raise GeoError(f"    Cuyahoga County: {len(no_cc)} precincts touch no council district (e.g. {no_cc[0]}); stopping")
    say(f"      cities, villages and townships by precinct: {several:,} of {len(pre):,} precincts reach more than one place, {no_place} lie in none; "
        f"Cuyahoga County Council: {sum(1 for i in cuy if pre[i].get('split', {}).get('com'))} of {len(cuy):,} precincts have {SPLIT_SHARE:.0%} or more of their area in a second district")
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

    # ---- the area checks: each county's precincts against the area the Bureau gives their blocks, and all the county's blocks
    #      (Lake Erie too) against the Bureau's 2025 county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731  Esri's winding: outer rings clockwise
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed(r) for r in county_rings[c]) for c in clist}
    if sorted(area_p) != clist or sorted(said["in"]) != clist:
        raise GeoError("    area check: the blocks and the 2025 county subdivisions do not have the same 88 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / said["in"][c] - 1))
    worst_pct = 100 * (area_p[worst] / said["in"][worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(said["in"].values()) - 1)
    off = [c for c in clist if abs(area_p[c] / said["in"][c] - 1) > 0.005]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] + f' ({100 * (area_p[c] / said['in'][c] - 1):+.2f}%)' for c in off[:8])} do not have the area the Census Bureau gives their blocks; stopping")
    off = [c for c in clist if abs(said["all"][c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the 2020 blocks of {', '.join(cname[c] + f' ({100 * (said['all'][c] / area_c[c] - 1):+.1f}%)' for c in off[:8])} do not cover the county the Census Bureau draws in 2025; stopping")
    lake = 100 * (1 - sum(said["in"].values()) / sum(said["all"].values()))
    say(f"      area check: the precincts have {100 + state_pct:.3f}% of the area the Census Bureau gives their blocks (the county furthest off is {cname[worst]}, {worst_pct:+.2f}%); "
        f"every county's blocks are within {AREA_SLACK:.0%} of the Bureau's 2025 county; {lake:.1f}% of Ohio's area (Lake Erie, mostly) is in no voting district")

    # ---- the Secretary's current list against the map's precincts, by the Secretary's own code
    listed_names = {(r["county"], r["vtd"]): r["rawname"] for r in poll_rows or []}
    for p in pre:
        p["listed"] = (p["county"], p["vtd"]) in listed_names
    ward_val, wards_drawn, ward_why = named_wards(pre, info, census_name, listed_names) if poll_rows else ({}, {}, {})
    if not poll_rows:
        ward_why = collections.defaultdict(lambda: "the Secretary of State's current precinct list could not be read, so the 2020 names could not be checked against it")

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

    BLOCKS, VTD, BEF, CDP, COUSUB, PLACES, SCH, CCD, LAW, POLLS = (
        "oh-census-tiger-2020-blocks", "oh-census-2020-voting-districts", "oh-census-2024-legislative-bef", "oh-orc-congressional-plan-2025-10-31",
        "oh-census-tiger-2025-cousub", "oh-census-tiger-2025-place", "oh-ogrip-school-districts-2025", "oh-cuyahoga-boe-council-districts-2022",
        "oh-rc-2501.01", "oh-sos-polling-locations")
    nth = lambda n: G.ordinal(n)      # noqa: E731
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[f"{STATE}-CA{jud_no[c]}"].append(cname[c])
    layer("state", *own([STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, BLOCKS)
    layer("county", *own(vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, BLOCKS)
    layer("cd", *own(vals["cd"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, BLOCKS + ", put together by " + CDP)
    layer("senate", *own(vals["senate"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, BLOCKS + ", put together by " + BEF)
    layer("house", *own(vals["house"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v, "senate": senate_of[v]}, BLOCKS + ", put together by " + BEF)
    layer("judicial", *own(vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{nth(v[len(STATE) + 3:])} District Court of Appeals", "j": v, "d": v[len(STATE) + 3:], "counties": jud_counties[v]},
          BLOCKS + "; which counties, from " + LAW)
    layer("mcd", *W.merged_layer([(parcs, psides, city_key), (carcs, csides, town_val)], TOL_MCD), TOL_MCD,
          lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, PLACES + " and " + COUSUB, zoom=MCD_ZOOM)
    if ward_val:
        layer("ward", *own([ward_val.get(i) for i in range(len(pre))], G.TOL_LOCAL), G.TOL_LOCAL,
              lambda v: {"id": v, "name": f"{mname[v.split('|')[0]]}, {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1], "as_of": 2020}, VTD + ", by the precincts' names")
    cg, cq, _l, _r = G.build_layer(ccarcs, ccsides, [cckeys], G.TOL_LOCAL)
    layer("com", cg, cq, G.TOL_LOCAL, lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]} Council District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}, CCD)
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
            pr = {"name": p["name"], "county": county, "precinct": p["precinct"], "code": p["code"], "mcd": p["mcd"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "judicial": p["jud"], "school": p["school"], "as_of": 2020}
            for k in p["mcd_all"]:
                used_names["mcd"][k] = mname[k]
            if len(p["mcd_all"]) > 1:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
            if p["com"]:
                pr["com"] = p["com"]
                for k in [p["com"]] + list((p.get("split") or {}).get("com", {})):
                    used_names["com"][k] = shape_ids["com"][k]["name"]
            if i in ward_val:
                pr["ward"] = [ward_val[i]]
                used_names["ward"][ward_val[i]] = shape_ids["ward"][ward_val[i]]["name"]
            if p["listed"]:
                pr["listed_2026"] = True
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

    polls = polling_places(pre, county_long, cbox, poll_rows, poll_about, put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    plans = {}
    for _rid, _level, kind, _jur, jid, district, _seat in info["races"]:
        if kind == "county_commissioner" and district in (None, ""):
            plans[str(jid)] = {"plan": 1, "districts": [], "commissioners_elected": "at large (R.C. 305.01: three commissioners, elected by the whole county)",
                               "source": "the county board of elections' 2026 candidate list"}

    check = check_ids(info, shape_ids, ward_why)
    check["wards_drawn_from_2020_precinct_names"] = wards_drawn
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    cb = "U.S. Census Bureau"
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            {"id": BLOCKS, "agency": cb, "title": "TIGER/Line Shapefiles 2020, tabulation blocks, Ohio (tl_2020_39_tabblock20.zip)",
             "about": "The 2020 census blocks: every line of the map's precincts, counties, legislative and congressional districts is a block's.",
             "url": BLOCK_URL, "fetched": mtime(bpath), "bytes": os.path.getsize(bpath), "rows": len(table) + len(water)},
            {"id": VTD, "agency": cb, "title": "2020 Census Block Assignment File, voting districts (BlockAssign_ST39_OH.zip), and the voting districts' names "
                                                "(tl_2020_39_vtd20.zip)",
             "about": "The precincts Ohio's county boards of elections reported for the 2020 census: which voting district each block is in. The Bureau's code is "
                      "the Secretary of State's precinct code.",
             "url": BAF_URL, "names_url": VTD_URL, "fetched": mtime(bafpath), "sha256": G.sha_file(bafpath), "names_sha256": G.sha_file(vpath),
             "rows": len({(p["county"], p["vtd"]) for p in pre})},
            {"id": BEF, "agency": cb, "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip)",
             "about": "Which Ohio House and Senate district each block is in, under the plan the Ohio Redistricting Commission adopted in September 2023.",
             "url": SLDL_URL, "upper_url": SLDU_URL, "fetched": mtime(lpath), "sha256": G.sha_file(lpath), "upper_sha256": G.sha_file(upath), "rows": len(table)},
            {"id": CDP, "agency": "Ohio Redistricting Commission", "title": f"{plan.get('title') or 'Congressional Redistricting Plan'}, adopted October 31, 2025: block assignment file ({CD_MEMBER})",
             "about": "Which congressional district each block is in, under the fifteen districts first used at the 2026 elections.",
             "url": CD_URL, "page": ORC + "maps", "fetched": mtime(cdpath), "sha256": G.sha_file(cdpath), "rows": len(table) + len(water)},
            {"id": COUSUB, "agency": cb, "title": "TIGER/Line Shapefiles 2025, county subdivisions, Ohio (tl_2025_39_cousub.zip)",
             "about": "Townships as the Bureau had them on January 1, 2025; also the county areas the precincts are checked against.",
             "url": COUSUB_URL, "fetched": mtime(tpath), "sha256": G.sha_file(tpath), "rows": len(cous)},
            {"id": PLACES, "agency": cb, "title": "TIGER/Line Shapefiles 2025, places, Ohio (tl_2025_39_place.zip)",
             "about": "City and village limits (incorporated places only), as the Bureau had them on January 1, 2025.", "url": PLACE_URL, "fetched": mtime(plpath),
             "sha256": G.sha_file(plpath), "rows": len(cities_)},
            dict({"id": SCH, "agency": "Ohio Geographically Referenced Information Program and the Ohio Department of Education; on the State of Ohio's GIS server",
                  "title": "Ohio School District Boundaries (2025)", "url": SCHOOL_SERVICE, "service": SCHOOL_SERVICE, "fetched": scdoc.get("fetched"),
                  "sha256": G.sha_file(scpath), "rows": len(schkeys)}, **edited["school"]),
            dict({"id": CCD, "agency": "Cuyahoga County Board of Elections", "title": "County Council Districts 2021, effective 2022-2032",
                  "about": "Only the district number is read.", "url": COUNCIL_SERVICE, "service": COUNCIL_SERVICE, "fetched": ccdoc.get("fetched"),
                  "sha256": G.sha_file(ccpath), "rows": len(cckeys)}, **edited["council"]),
            {"id": LAW, "agency": "Ohio Legislative Service Commission", "title": "Ohio Revised Code 2501.01: Judicial court of appeals districts",
             "url": jud_doc["url"], "fetched": jud_doc["fetched"], "sha256": jud_doc["sha256"], "effective": jud_doc.get("effective"), "rows": 12},
        ] + ([dict({"id": POLLS, "agency": "Ohio Secretary of State; published by the Ohio Emergency Management Agency", "title": POLL_TITLE, "url": POLL_ITEM,
                    "about": "The Secretary's list of every precinct and its polling location, last updated for the May 2026 primary; read for the precinct codes "
                             "and names still in use, and for polling_places.json (unchecked).",
                    "service": POLL_SERVICE, "fetched": poll_about.get("fetched"), "sha256": poll_about.get("sha256"), "rows": len(poll_rows)},
                   **({"current_to": poll_about["current_to"]} if poll_about.get("current_to") else {}))] if poll_rows else []),
        "notes": {
            "lines": f"Every precinct, county, legislative and congressional line is a 2020 census block's, generalised by at most {G.TOL_PRECINCT} metres and set on a "
                     "grid of 0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "Ohio publishes no statewide map of its precincts as they stand in 2026. Each shape here is a voting district as the county board of "
                         "elections reported it for the 2020 census, cut wherever a 2024 legislative or 2026 congressional district line crosses it, and named as "
                         "the Bureau's file names it. A board may have redrawn or renamed its precincts since: the board is the authority. listed_2026 is true "
                         "where the Secretary of State's current precinct list still carries the precinct's code. What a ballot depends on (county, legislative "
                         "and congressional district, court of appeals district, city, village or township, school district) is taken from current files and "
                         "does not depend on the precinct. Lake Erie belongs to no voting district and is left out.",
            "places": "A precinct can reach more than one place, and a village lies inside a township, so the precinct does not say which city, village or "
                      "township a voter lives in: the mcd layer answers that for a point, cities and villages first (a point inside a village's limits is given "
                      "the village; it is in the township around it too, whose shape is the whole township, villages included). Townships without a government of "
                      "their own (those a city has absorbed) are left out. mcd is the place holding most of the precinct; mcd_all lists every place it reaches. "
                      "Limits are the Census Bureau's of January 1, 2025.",
            "commissioners": "A county's three commissioners are elected by the whole county (R.C. 305.01). Cuyahoga County has a charter: an executive elected by the "
                             "whole county and a council of eleven, one from each district (the com layer; a precinct's com is the district holding most of it, "
                             "analysis, and the layer answers for a point). Summit County's council districts are not drawn; none is on the 2026 ballot.",
            "legislative": "Which House and Senate district a block is in is the Census Bureau's 2024 equivalency file's word (the plan adopted in September 2023), "
                           "so a precinct's district is exact. Each Senate district is three House districts.",
            "congressional": "Which congressional district a block is in is the Ohio Redistricting Commission's own block assignment file for the plan it adopted on "
                             "October 31, 2025, first used in 2026; a precinct's district is exact.",
            "school": "School district lines are the State's file of 2025. Which districts a precinct lies in is analysis, not an official list: a district counts "
                      f"when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share of the "
                      "precinct's area (land and water, not voters). No school board is on the November 2026 ballot.",
            "judicial": "The twelve court of appeals districts are whole counties (R.C. 2501.01). A common pleas judge is elected by the county.",
            "wards": "No statewide file has city ward lines. A ward is drawn only for a city whose council race is in the ballot database, whose 2020 voting "
                     "districts are named by ward, and whose precincts the Secretary of State's current list still names the same way under the same codes; it "
                     "is the ward as its precincts stood in 2020 (properties.as_of).",
            "authority": "For which precinct an address votes in, and where, the county board of elections and the Ohio Secretary of State's voter lookup are the authority.",
            "precinct_ids": "A precinct's id is its county's five digits, a full stop and the Census Bureau's 2020 voting district code (39085.043ABS: the Secretary "
                            "of State's precinct 43ABS); a voting district cut by a district line has a second full stop and the piece's number.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file; -2: outside Ohio, or Lake Erie); names gives the names of the places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the 2020 voting district's, as the Census Bureau's file gives it, in ordinary capitals (and the piece's number where a district line cuts it)",
                                    "county": "county id", "precinct": "the county's five digits and the Bureau's 2020 voting district code",
                                    "code": "the Secretary of State's precinct code (county number in the alphabet and three letters)",
                                    "as_of": "the year of the precinct's lines (2020)",
                                    "listed_2026": "true where the Secretary of State's current precinct list carries this code",
                                    "mcd": "city, village or township holding most of the precinct",
                                    "mcd_all": "list, when the precinct reaches more than one: every city, village and township it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                                    "house": "Ohio House district", "senate": "Ohio Senate district", "cd": "congressional district (the 2026 lines)",
                                    "judicial": "court of appeals district",
                                    "com": "Cuyahoga County only: the county council district holding most of the precinct",
                                    "ward": "list, in a city whose wards are drawn: the council ward",
                                    "split": "only where a second council district holds 3 percent or more of the precinct: each one's share in percent",
                                    "school": "list: the school districts the precinct lies in, largest share first",
                                    "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                                    "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "OH (j is 39)", "county": "the county's five-digit code (39049)",
                    "mcd": "OH-M- and the Census code: a city's or village's place code (OH-M-49056), a township's county subdivision code; properties.t says city, village or township",
                    "ward": "<city>|<ward> (OH-M-49056|Ward 3); properties.as_of is 2020",
                    "com": "<county>|<council district> (39035|1), Cuyahoga County only",
                    "house": "the district (23); properties.senate is its Senate district", "senate": "the district (18)",
                    "cd": "the district (14); properties.race is the race for Congress",
                    "judicial": "OH-CA and the court of appeals district's number (OH-CA10); d is the number",
                    "school": "OH-S- and the Department's six-digit district number (OH-S-043489)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {c: plans[c] for c in sorted(plans)},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "whole_precincts": len({p["precinct"] for p in pre}), "counties": len(counties), "census_blocks": len(table) + len(water),
                   "census_blocks_in_lake_erie": len(water),
                   "precincts_on_the_2026_list_by_code": len({p["precinct"] for p in pre if p["listed"]}),
                   "split_between_school_districts": split, "in_more_than_one_city_or_township": several,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Ohio races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Ohio ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's precinct lies in, the place at the point (from the mcd layer), and a
    # word its school district's name must carry. County, place, legislative districts and school district are the
    # Census Bureau's geocoder's answer for those coordinates (asked 2026-10-02: geocoding.geo.census.gov,
    # "geographies/coordinates", its 2026 legislative districts), an answer that owes nothing to the files tested here.
    # The congressional district is the Commission's block assignment file's for the census block the geocoder named.
    # The court of appeals district is the county's (R.C. 2501.01).
    ("the Statehouse, Columbus", -82.9988, 39.9612, {"county": "39049", "senate": "15", "house": "1", "cd": "15", "judicial": "OH-CA10"}, "OH-M-18000", "Columbus"),
    ("Public Square, Cleveland", -81.6938, 41.4996, {"county": "39035", "senate": "23", "house": "20", "cd": "11", "judicial": "OH-CA8"}, "OH-M-16000", "Cleveland"),
    ("Fountain Square, Cincinnati", -84.5120, 39.1015, {"county": "39061", "senate": "9", "house": "24", "cd": "1", "judicial": "OH-CA1"}, "OH-M-15000", "Cincinnati"),
    ("downtown Toledo", -83.5379, 41.6528, {"county": "39095", "senate": "11", "house": "42", "cd": "9", "judicial": "OH-CA6"}, "OH-M-77000", "Toledo"),
    ("downtown Akron", -81.5190, 41.0814, {"county": "39153", "senate": "28", "house": "34", "cd": "13", "judicial": "OH-CA9"}, "OH-M-01000", "Akron"),
    ("downtown Dayton", -84.1916, 39.7589, {"county": "39113", "senate": "6", "house": "36", "cd": "10", "judicial": "OH-CA2"}, "OH-M-21000", "Dayton"),
    ("downtown Youngstown", -80.6495, 41.0998, {"county": "39099", "senate": "33", "house": "58", "cd": "6", "judicial": "OH-CA7"}, "OH-M-88000", "Youngstown"),
    ("Athens, the university", -82.1013, 39.3292, {"county": "39009", "senate": "30", "house": "95", "cd": "2", "judicial": "OH-CA4"}, "OH-M-02736", "Athens"),
    ("Mentor, the Civic Center", -81.3396, 41.6662, {"county": "39085", "senate": "18", "house": "23", "cd": "14", "judicial": "OH-CA11"}, "OH-M-49056", "Mentor"),
    ("Mentor, east side", -81.30, 41.69, {"county": "39085", "senate": "18", "house": "57", "cd": "14", "judicial": "OH-CA11"}, "OH-M-49056", "Mentor"),
    ("Marietta", -81.4548, 39.4154, {"county": "39167", "senate": "30", "house": "94", "cd": "2", "judicial": "OH-CA4"}, "OH-M-47628", "Marietta"),
    ("Lima", -84.1052, 40.7426, {"county": "39003", "senate": "12", "house": "78", "cd": "4", "judicial": "OH-CA3"}, "OH-M-43554", "Lima"),
    ("Parma", -81.7229, 41.4048, {"county": "39035", "senate": "24", "house": "14", "cd": "7", "judicial": "OH-CA8"}, "OH-M-61000", "Parma"),
    ("Shaker Heights", -81.5370, 41.4739, {"county": "39035", "senate": "21", "house": "18", "cd": "11", "judicial": "OH-CA8"}, "OH-M-71682", "Shaker Heights"),
    ("a field in Paulding Township, Paulding County", -84.58, 41.12, {"county": "39125", "senate": "1", "house": "82", "cd": "9", "judicial": "OH-CA3"}, "OH-M-61266", "Paulding"),
    ("Portsmouth", -82.9977, 38.7317, {"county": "39145", "senate": "14", "house": "90", "cd": "2", "judicial": "OH-CA4"}, "OH-M-64304", "Portsmouth"),
    ("Sandusky", -82.7079, 41.4489, {"county": "39043", "senate": "2", "house": "89", "cd": "9", "judicial": "OH-CA6"}, "OH-M-70380", "Sandusky"),
    ("Canton", -81.3784, 40.7989, {"county": "39151", "senate": "29", "house": "49", "cd": "13", "judicial": "OH-CA5"}, "OH-M-12000", "Canton"),
]
LINE_POINTS = [("the Franklin-Delaware county line north of Columbus", -83.00, 40.14, ("39049", "39041")),
               ("the Cuyahoga-Summit county line south of Cleveland", -81.55, 41.35, ("39035", "39153"))]
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
    check(len(index["counties"]) == 88, "there are not 88 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == 33 and len(layer_ids.get("house", ())) == 99 and len(layer_ids.get("judicial", ())) == 12
          and layer_ids.get("cd") == {str(n) for n in range(1, 16)} and len(layer_ids.get("county", ())) == 88
          and layer_ids.get("com") == {f"{COUNCIL_COUNTY}|{n}" for n in range(1, 12)},
          "there are not 33 Senate districts, 99 House districts, 12 court of appeals districts, 88 counties, 15 congressional districts and 11 Cuyahoga council districts")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place, council = collections.Counter(), collections.Counter(), collections.Counter()
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
                      else "a place the precinct does not name" if shape else "no place"] += 1
            if pr.get("com"):
                shape, _edge = G.shape_at(files, "com", lon, lat)
                council["the precinct's own district" if shape and shape["id"] == pr["com"] else
                        "another district the precinct is split with" if shape and shape["id"] in (pr.get("split") or {}).get("com", {}) else
                        "a district the precinct does not name" if shape else "no district"] += 1
            if pr.get("ward"):
                shape, _edge = G.shape_at(files, "ward", lon, lat)
                check(shape is not None and shape["id"] == pr["ward"][0], f"precinct {g['id']}: the ward layer gives {shape and shape['id']} at its own point, not {pr['ward'][0]}")
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
    check(place["no place"] <= 0.002 * half and place["a place the precinct does not name"] <= 0.02 * half, f"the place at a precinct's own point: {dict(place)}")
    check(council["a district the precinct does not name"] + council["no district"] <= 0.02 * max(1, sum(council.values())), f"the council district at a Cuyahoga precinct's own point: {dict(council)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree at {agree:,} of "
        f"{sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + f"); school district at {half:,} precincts' points: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; city, village or township: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])) + "; Cuyahoga council district: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(council.items(), key=lambda x: -x[1])))

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
        extra = "".join(f", {k} {pr[k][0] if isinstance(pr[k], list) else pr[k]}" for k in ("com", "ward") if pr.get(k))
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, "
            f"{fdoc['name']}, House {pr['house']}, Senate {pr['senate']}, Congress {pr['cd']}, {pr['judicial']}, {sn}{extra}; {found['edge']:.0f} m from the precinct's line")

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
        pts = [p for p in polls["places"] if p.get("lonlat")]
        for p in pts[::5]:
            f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
            inside += bool(f3) and f3["county"] == p["county"]
        check(inside >= 0.97 * len(pts[::5]), f"only {inside} of {len(pts[::5])} polling places tried lie inside their own county")
        say(f"      self-test: polling places: {polls.get('status')}; {n:,} places, {len(pts):,} with a point ({inside:,} of the {len(pts[::5]):,} tried lie inside "
            f"their own county); {len(polls['precinct']):,} map precincts carry a listed place")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Ohio's ballot map -> ballot_geo/oh/")
    ap.add_argument("--out", default=OUT, help="folder to build (default: ballot_geo/oh)")
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
