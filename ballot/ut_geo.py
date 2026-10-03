"""
ballot/ut_geo.py - the geography behind Utah's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py and
ballot/ia_geo.py for the few things those added, and changes nothing in any of them), so the same page and the same
reader (ballot/mn_geo_reader.js) read them all.

    python ballot/ut_geo.py                 builds ballot_geo/_building_ut/, runs the self-test on it and, only when it
                                            passes, puts it in place as ballot_geo/ut/
    python ballot/ut_geo.py --selftest      runs the self-test on ballot_geo/ut/ as it stands
    python ballot/ut_geo.py --refresh       asks the map services again even when the cached copies are fresh
    python ballot/ut_geo.py --out DIR       builds somewhere else and tests it there (a trial run; nothing is moved)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ut_local/)
----------------------------------------------------------------------------------------------------------------------
Utah keeps its election geography in one place: the State Geographic Information Database (SGID) of the Utah
Geospatial Resource Center (UGRC), stewarded with the Lieutenant Governor's Office, whose feature services answer
plain requests.
  - Precincts: "Utah Vista Ballot Areas" (UGRC and the Lieutenant Governor's Office): the voting precincts of all 29
    counties as the county clerks submit them to Vista, the state's voter system that decides each voter's ballot. Where
    a county splits a precinct into formal subprecincts only the subprecincts are in the layer, so a shape here is a
    precinct or a subprecinct. Asked for: county number, VistaID, precinct and subprecinct, the county's own name for
    the area (AliasName, kept only where it reads as a place name), version and dates. Never asked for: Comments (free
    text).
  - Congressional, Utah Senate, Utah House and State Board of Education districts: UGRC's district layers, each laid
    over the precincts (the district holding most of a precinct): "Utah US Congress Districts 2026 to 2032" (the plan
    the Third District Court adopted in November 2025, used for elections from January 1, 2026), "Utah House Districts
    2022 to 2032", "Utah Senate Districts 2022 to 2032" and "Utah School Board Districts 2022 to 2032" (never its BOARD
    column, a member's name). The first three also draw the map's own lines. The State Board of Education's 15 districts
    are named by each precinct (sboe), not drawn: the seat is a statewide race the page narrows to a located reader's
    own. UGRC's "Utah District Combination Areas 2026" (every piece of the state with one combination of the four) is
    the check: each precinct's four districts must be a combination it has.
  - Counties: each precinct's own county number (Utah numbers its counties alphabetically, Beaver 1 to Weber 29, and
    the Census Bureau's code is 2n - 1); UGRC's "Utah County Boundaries" for the area check.
  - Cities and towns: UGRC's "Utah Municipal Boundaries" (kept current with the annexations and
    boundary changes the Lieutenant Governor certifies), keyed by the Census Bureau's place code it carries; whether a
    place is a city or a town comes from the Census Bureau's TIGER/Line 2025 places (tl_2025_49_place.zip).
  - Judicial districts: UGRC's "Utah Judicial Districts" (each of the eight is whole counties, Utah Code 78A-1-102),
    read only for which counties are in which district, checked against the statute's list typed in below and against
    the counties the ballot database gives each district's retention votes; the lines are the county lines.
  - School districts: the Census Bureau's TIGER/Line 2025 unified school districts (tl_2025_49_unsd.zip; Utah's 41).

What is built: index.json, manifest.json, precincts/<county>.json (29), layers/<kind>.json (state, county, cd, senate,
house, judicial, mcd, school), school/<id>.json, polling_places.json and reader.js, each as ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "UT" (j = "49", the jurisdiction_id of statewide races and of the Supreme Court and Court of Appeals votes)
  county    "49035"                 sl_places county id; jurisdiction_id of a county's justice court
  mcd       "UT-M-67000"            UT-M- and the Census Bureau's place code (sl_places mcd id); a municipality the Bureau
                                    has no code for yet is UT-M- and UGRC's own three-letter code
  house     "21"   senate "12"   cd "1" (properties.race is the federal race id, 2026-UT-H01)
  judicial  "JD3"                   the jurisdiction_id of district and juvenile court retention votes; d is the number
  school    "UT-S-00510"            UT-S- and the Bureau's five-digit district code; properties.nces is the seven-digit
                                    federal code
  sboe      "UT-SBOE7"              a precinct property only: the State Board of Education district

Not drawn, because no statewide file has the lines: county commission and council districts (Salt Lake County's
council, among others), city council districts, local school board districts, and special districts. index.json lists
every race without a shape under "check", with the reason.

POLLING PLACES: see POLL_HOW. polling_places.json is "waiting" and says so.
"""

import argparse
import collections
import datetime as dt
import hashlib
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
from ballot import wy_geo as Y  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "UT", "49", "Utah"
OUT = os.path.join(HERE, "ballot_geo", "ut")
BUILDING = os.path.join(HERE, "ballot_geo", "_building_ut")
CACHE = os.path.join(HERE, "states_cache", "ut_local")
POLL_DIR = os.path.join(CACHE, "ltgov", "pollingplaces")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://votesearch.utah.gov/voter-search/search/search-by-address/how-and-where-can-i-vote"
N_HOUSE, N_SENATE, N_CD, N_COUNTY, N_JUD, N_SBOE = 75, 29, 4, 29, 8, 15

UGRC = "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/"
SGID = "https://gis.utah.gov/products/sgid/political/"
VISTA_SERVICE = UGRC + "VistaBallotAreas/FeatureServer/0"
VISTA_ITEM = SGID + "voter-precincts/"
VISTA_FIELDS = "OBJECTID,CountyID,VistaID,PrecinctID,SubPrecinctID,AliasName,VersionNbr,EffectiveDate,RcvdDate"      # never Comments
COMBO_SERVICE = UGRC + "political_district_combination_areas_2026/FeatureServer/0"
COMBO_ITEM = SGID + "combined-districts/"
COMBO_FIELDS = "OBJECTID,ComboID,Congress,Senate,House,School,County"
CD_SERVICE = UGRC + "political_us_congress_districts_2026_to_2032/FeatureServer/0"
CD_ITEM = SGID + "us-congressional-districts/"
HOUSE_SERVICE = UGRC + "UtahHouseDistricts2022to2032/FeatureServer/0"
HOUSE_ITEM = SGID + "state-house-districts/"
SENATE_SERVICE = UGRC + "UtahSenateDistricts2022to2032/FeatureServer/0"
SENATE_ITEM = SGID + "state-senate-districts/"
SBOE_SERVICE = UGRC + "UtahSchoolBoardDistricts2022to2032/FeatureServer/0"
SBOE_ITEM = SGID + "state-school-board-districts/"
MUNI_SERVICE = UGRC + "UtahMunicipalBoundaries/FeatureServer/0"
MUNI_ITEM = "https://gis.utah.gov/products/sgid/boundaries/municipal/"
MUNI_FIELDS = "OBJECTID,COUNTYNBR,NAME,SHORTDESC,FIPS,UGRCODE,UPDATED"
COUNTY_SERVICE = UGRC + "UtahCountyBoundaries/FeatureServer/0"
COUNTY_ITEM = "https://gis.utah.gov/products/sgid/boundaries/county/"
JUD_SERVICE = UGRC + "JudicialDistricts/FeatureServer/0"
JUD_ITEM = SGID + "judicial-districts/"
CENSUS = "https://www2.census.gov/"
PLACE_URL = CENSUS + "geo/tiger/TIGER2025/PLACE/tl_2025_49_place.zip"
UNSD_URL = CENSUS + "geo/tiger/TIGER2025/UNSD/tl_2025_49_unsd.zip"

# Utah Code 78A-1-102: the eight judicial districts, each whole counties (checked against UGRC's layer and the ballot database)
STATUTE_JUD = {
    "1": ["Box Elder", "Cache", "Rich"], "2": ["Davis", "Morgan", "Weber"], "3": ["Salt Lake", "Summit", "Tooele"],
    "4": ["Juab", "Millard", "Utah", "Wasatch"], "5": ["Beaver", "Iron", "Washington"],
    "6": ["Garfield", "Kane", "Piute", "Sanpete", "Sevier", "Wayne"], "7": ["Carbon", "Emery", "Grand", "San Juan"],
    "8": ["Daggett", "Duchesne", "Uintah"]}
STATUTE_URL = "https://le.utah.gov/xcode/Title78A/Chapter1/78A-1-S102.html"
COUNTY_NAMES = ["Beaver", "Box Elder", "Cache", "Carbon", "Daggett", "Davis", "Duchesne", "Emery", "Garfield", "Grand", "Iron", "Juab", "Kane",
                "Millard", "Morgan", "Piute", "Rich", "Salt Lake", "San Juan", "Sanpete", "Sevier", "Summit", "Tooele", "Uintah", "Utah",
                "Wasatch", "Washington", "Wayne", "Weber"]      # Utah's own county numbers 1 to 29 are this order

ARC_KINDS = ["county", "mcd", "house", "senate", "cd", "judicial"]
SPLIT_SHARE = W.SPLIT_SHARE       # a precinct with this much of its area in a second district is marked split
PLACE_KIND = {"25": "city", "43": "town"}
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
AREA_SLACK = 0.02

clean_text = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()      # noqa: E731


def county_of(n):
    """The five-digit code of Utah's county number n (1 to 29)."""
    return f"{FIPS}{2 * int(n) - 1:03d}"


def sboe_id(n):
    return f"{STATE}-SBOE{int(n)}"


# ---------------------------------------------------------------- the precincts

SAFE_ALIAS = re.compile(r"[A-Za-z][A-Za-z0-9 .,'()&/#-]{1,47}")
STREETISH = re.compile(r"\d+\s+(?:[NSEW]\.?\s+)?\w*\s*(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Blvd|Court|Ct|Place|Pl|Circle|Cir)\b", re.I)


def alias_name(raw):
    """The county's own name for a precinct where it reads as a place name ("Bicknell", "Marysvale Unincorporated West"),
    else None: the column is free for each county to fill, so anything with an @, a long run of digits or what reads as
    a street address is never kept, and a bare code ("XSH:05") adds nothing."""
    a = clean_text(raw)
    if not a or not SAFE_ALIAS.fullmatch(a) or not re.search(r"[a-z]", a) or re.search(r"@|\d{4,}", a) or STREETISH.search(a):
        return None
    return a


def read_precincts(doc):
    """The ballot areas, one per VistaID (a few counties send one area as several rows: they are put together), in id
    order, and their rings as vertex keys. Returns (pre, polys, said) where said counts what was put right."""
    groups, said = collections.OrderedDict(), collections.Counter()
    for a, rings in doc["rows"]:
        cid = a.get("CountyID")
        vid = re.sub(r"\s+", "", G.blank(a.get("VistaID")))
        pid, sub = re.sub(r"\s+", "", G.blank(a.get("PrecinctID"))), re.sub(r"\s+", "", G.blank(a.get("SubPrecinctID")))
        if not (isinstance(cid, int) and 1 <= cid <= N_COUNTY and re.fullmatch(r"[A-Za-z0-9:_./\-]{1,16}", vid or "") and pid):
            raise GeoError(f"    ballot areas: the row numbered {a.get('OBJECTID')} (county {cid!r}) does not fit the layout this builder was checked against; stopping")
        head, _c, vsub = vid.partition(":")
        if not head.endswith(pid) or vsub != sub:
            said["VistaID and PrecinctID disagree (the VistaID is followed)"] += 1
        key = (county_of(cid), vid)
        g = groups.get(key)
        if g is None:
            groups[key] = g = {"rows": 0, "rings": [], "attrs": a, "head": head, "sub": vsub}
        else:
            said["rows that are a further piece of an area already read"] += 1
        g["rows"] += 1
        g["rings"] += [k for k in (G.clean_ring(r) for r in rings) if k]
    pre, polys = [], []
    for (county, vid), g in sorted(groups.items(), key=lambda kv: (kv[0][0], G.natkey(kv[0][1]))):
        a = g["attrs"]
        alias = alias_name(a.get("AliasName"))
        code = g["head"] + (f", subprecinct {g['sub']}" if g["sub"] else "")
        eff = a.get("EffectiveDate")
        pre.append({"id": f"{county}.{vid}", "county": county, "vista": vid, "precinct": g["head"], "sub": g["sub"] or None,
                    "name": alias or f"Precinct {code}", "alias": alias, "code": code,
                    "effective": dt.datetime.fromtimestamp(eff / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if isinstance(eff, (int, float)) else None})
        polys.append(g["rings"])
    if len({p["county"] for p in pre}) != N_COUNTY:
        raise GeoError(f"    ballot areas: {len({p['county'] for p in pre})} counties, not {N_COUNTY}; stopping")
    return pre, polys, dict(said)


def settle_twins(pre, polys, county_xy):
    """A ring sent, vertex for vertex, as part of two ballot areas (a Summit County subprecinct carried a ring that is a
    Wasatch County precinct): it is kept only in the area whose county holds a point inside it, and left out of the
    others. A ring that is one area's hole and another's outline (an island) is as it should be and is not touched: only
    rings running the same way in two areas are. Returns the ids of the areas that gave a ring up."""
    seen = collections.defaultdict(list)
    for i, rings in enumerate(polys):
        for n, ks in enumerate(rings):
            seen[(frozenset(ks), G.area2([G.vxy(k) for k in ks]) < 0)].append((i, n))
    drop, gave = collections.defaultdict(set), []
    for who in seen.values():
        areas = sorted({i for i, _n in who})
        if len(areas) < 2:
            continue
        i0, n0 = who[0]
        x, y = G.label_point([[G.vxy(k) for k in polys[i0][n0]]])
        home = [i for i in areas if G.in_rings(x, y, county_xy[pre[i]["county"]])]
        if len(home) != 1:
            raise GeoError(f"    ballot areas {', '.join(pre[i]['id'] for i in areas)} share a ring and their counties do not settle whose it is; stopping")
        for i, n in who:
            if i != home[0]:
                drop[i].add(n)
                gave.append(pre[i]["id"])
    for i, ns in drop.items():
        polys[i][:] = [r for n, r in enumerate(polys[i]) if n not in ns]
        if not polys[i]:
            raise GeoError(f"    ballot area {pre[i]['id']} has no ring of its own left; stopping")
    return sorted(gave)


def one_row_each(rows, key, say_what):
    """Rows of a layer that has one place in several rows (a city in two counties): one row each, rings together."""
    out = collections.OrderedDict()
    for a, rings in rows:
        k = key(a)
        if k in out:
            out[k][1].extend(rings)
        else:
            out[k] = (a, list(rings))
    return list(out.values())


# ---------------------------------------------------------------- the ballot database (read-only)

def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ut-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids, office "
                                         "FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    """mn_geo.school_overlay, its answer kept beside the downloads while they have not changed: for each precinct,
    [[district number, share of the precinct's area, thick enough]]."""
    path = os.path.join(CACHE, f"ut_geo_overlay_{name}.json")
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


# ---------------------------------------------------------------- ids against the ballot database

def check_ids(info, shape_ids, said_ids):
    """Every Utah race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape, then race_said). A race without a shape is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "part_of_a_shape": [], "note": "not checked in this build"}
    Sh = shape_ids
    by_layer, missing, matched, seats = collections.Counter(), collections.OrderedDict(), 0, collections.Counter()
    for rid, level, kind, jur, jid, district, county_ids, office in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        court = re.sub(r"_retention$", "", kind or "")
        counties = re.findall(r"\d+", str(county_ids or ""))
        hit, why = None, None
        if level == "statewide" or (court in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
            if level == "statewide" and d and kind == "state_board_of_education" and sboe_id(d) in said_ids.get("sboe", ()):
                seats["sboe"] += 1
        elif level == "court" and not d and not counties and jid in (STATE, FIPS):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "district_court" or (level == "court" and jid in Sh.get("judicial", {})):
            hit = ("judicial", jid)
        elif kind in ("county_commissioner", "county_council"):
            hit = ("county", jid) if not d else ("com", f"{jid}|{d}")
            if d:
                why = "no statewide file has the lines of county commission or council districts; each county keeps its own"
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d:
                why = "no statewide file has the lines of city council districts; the city keeps them (the page places the race on its city)"
        elif level == "school":
            hit = ("school", jid)
            if d:
                why = "no statewide file has the lines of local school board districts"
        elif level == "court" and jid:
            hit = ("mcd", jid) if jid in Sh.get("mcd", {}) else ("county", jid)
        elif level == "court":
            why = ("a justice court that serves several places: the list names the places (in the race's id) but files the court under no one "
                   "jurisdiction, and whose voters decide its judge's retention (the whole county, or a city's own voters) is for election "
                   "officers to say, so the page cannot place it on the map")
        else:
            why = "no statewide file read here has the lines of this kind of district"
        if hit and hit[1] in Sh.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            continue
        key = (level, kind, jur, jid, district)
        e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid or None, "district": district,
                                     "races": 0, "why": why or "no shape carries this id"})
        e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())),
            "statewide_seats_also_named_by_the_precinct": dict(sorted(seats.items())),
            "no_shape": list(missing.values()), "part_of_a_shape": []}


# ---------------------------------------------------------------- polling places

POLL_WAITING = {
    "why": "Utah votes by mail. Each county clerk sets the county's in-person voting locations and ballot drop boxes, and the state "
           "publishes no statewide list of them as a file. The state's voter search answers for one address at a time and, with the "
           "county clerk, is the authority on where to vote or drop off a ballot.",
}
POLL_HOW = ("      polling places: waiting. Utah votes by mail; each county clerk designates in-person voting locations (vote centers on Election "
            "Day and early voting sites) and ballot drop boxes. No statewide file of them is published: vote.utah.gov sends a voter to "
            "votesearch.utah.gov, which answers one address at a time and is not to be scripted, and UGRC's open data has no such layer (its "
            "\"Ballot_Drop_Box_Analysis\" is an analysis, not the clerks' list). If John asks the Lieutenant Governor's Elections Office for the "
            "statewide list of November 3, 2026 voting locations and drop boxes (his step), the file as received (e.g. "
            "UT_2026_General_Voting_Locations.xlsx or .csv) goes in states_cache/ut_local/ltgov/pollingplaces/; a reader for it would still "
            "have to be written and checked against it, keeping only each site's name, address, county, kind (vote center, early voting or drop "
            "box) and dates and hours, never a contact.")


def polling_places(put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER, "status": "waiting", **POLL_WAITING}
    put("polling_places.json", doc)
    say(POLL_HOW)
    return {"file": "polling_places.json", "status": "waiting"}


# ---------------------------------------------------------------- the build

def judicial_of(jdoc, cname_short, info):
    """{county: "JD<n>"} from UGRC's layer, which must agree with Utah Code 78A-1-102 (STATUTE_JUD) and with the
    counties the ballot database gives each district's retention votes."""
    by_name = {re.sub(r"[^a-z]", "", n.lower()): c for c, n in cname_short.items()}
    jud_of, layer = {}, {}
    for a, _r in jdoc["rows"]:
        d = clean_text(a.get("DISTRICT"))
        names = [clean_text(n) for n in re.split(r",", str(a.get("COUNTIES") or "")) if clean_text(n)]
        layer[d] = sorted(names)
        for n in names:
            c = by_name.get(re.sub(r"[^a-z]", "", n.lower()))
            if c is None or c in jud_of:
                raise GeoError(f"    judicial districts: UGRC's layer names a county {n!r} that is unknown or in two districts; stopping")
            jud_of[c] = f"JD{int(d)}"
    if {k: sorted(v) for k, v in STATUTE_JUD.items()} != layer or len(jud_of) != N_COUNTY:
        raise GeoError("    judicial districts: UGRC's layer and Utah Code 78A-1-102 (as typed in this builder) do not list the same counties; stopping")
    want = collections.defaultdict(set)
    for _rid, level, _kind, _jur, jid, _d, county_ids, _o in info.get("races", []):
        if level == "court" and re.fullmatch(r"JD\d", str(jid or "")):
            want[jid].add(tuple(sorted(re.findall(r"\d{5}", str(county_ids or "")))))
    got = collections.defaultdict(list)
    for c, j in jud_of.items():
        got[j].append(c)
    bad = [j for j, v in want.items() if v != {tuple(sorted(got[j]))}]
    if bad:
        raise GeoError(f"    judicial districts: the ballot database gives {bad[0]} other counties than the statute; stopping")
    return jud_of, len(want)


def build(out=BUILDING, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Utah ballot map: ballot areas (precincts), district, municipal, judicial and school district lines (UGRC and the Lieutenant "
        "Governor's Office, the Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    vpath, copath, cdpath, hpath, spath, sbpath, mpath, cypath, jpath = (path(n) for n in (
        "ugrc_vista_ballot_areas_geometry_4326.json.gz", "ugrc_district_combination_areas_2026_geometry_4326.json.gz",
        "ugrc_us_congress_2026_geometry_4326.json.gz", "ugrc_house_2022_geometry_4326.json.gz", "ugrc_senate_2022_geometry_4326.json.gz",
        "ugrc_school_board_2022_geometry_4326.json.gz", "ugrc_municipal_boundaries_geometry_4326.json.gz", "ugrc_county_boundaries_geometry_4326.json.gz",
        "ugrc_judicial_districts_geometry_4326.json.gz"))
    plpath, unpath = path("tl_2025_49_place.zip"), path("tl_2025_49_unsd.zip")
    vdoc = W.fetch_full(VISTA_SERVICE, VISTA_FIELDS, vpath, 500, "OBJECTID", refresh, say)
    codoc = W.fetch_full(COMBO_SERVICE, COMBO_FIELDS, copath, 100, "OBJECTID", refresh, say)
    cddoc = W.fetch_full(CD_SERVICE, "OBJECTID,DISTRICT", cdpath, 2, "OBJECTID", refresh, say)
    hdoc = W.fetch_full(HOUSE_SERVICE, "OBJECTID,DIST", hpath, 20, "OBJECTID", refresh, say)
    sdoc = W.fetch_full(SENATE_SERVICE, "OBJECTID,DIST", spath, 10, "OBJECTID", refresh, say)
    sbdoc = W.fetch_full(SBOE_SERVICE, "OBJECTID,DIST", sbpath, 5, "OBJECTID", refresh, say)      # never BOARD
    mdoc = W.fetch_full(MUNI_SERVICE, MUNI_FIELDS, mpath, 100, "OBJECTID", refresh, say)
    cydoc = W.fetch_full(COUNTY_SERVICE, "OBJECTID,COUNTYNBR,NAME,FIPS_STR", cypath, 10, "OBJECTID", refresh, say)
    jdoc = W.fetch_full(JUD_SERVICE, "OBJECTID,DISTRICT,COUNTIES", jpath, 8, "OBJECTID", refresh, say)
    for url, p in ((PLACE_URL, plpath), (UNSD_URL, unpath)):
        net.download(url, p, 3650, say=lambda *_a: None)
    edited = {k: W.layer_edited(svc, path(f"ut_geo_about_{k}.json"), refresh)
              for k, svc in (("vista", VISTA_SERVICE), ("combo", COMBO_SERVICE), ("cd", CD_SERVICE), ("house", HOUSE_SERVICE),
                             ("senate", SENATE_SERVICE), ("sboe", SBOE_SERVICE), ("muni", MUNI_SERVICE), ("county", COUNTY_SERVICE),
                             ("judicial", JUD_SERVICE))}

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    cshort = {county_of(n + 1): nm for n, nm in enumerate(COUNTY_NAMES)}
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in cshort.items()}

    # ---- UGRC's counties (for the area check, and to settle a ring two counties both sent)
    county_rows = {}
    for a, rings in cydoc["rows"]:
        c = county_of(int(a["COUNTYNBR"]))
        if G.blank(a.get("FIPS_STR")) not in ("", c) or c in county_rows:
            raise GeoError(f"    county boundaries: county number {a.get('COUNTYNBR')!r} and code {a.get('FIPS_STR')!r} disagree; stopping")
        county_rows[c] = [k for k in (G.clean_ring(r) for r in rings) if k]
    clist = sorted(cname)
    if sorted(county_rows) != clist:
        raise GeoError("    county boundaries: not Utah's 29 counties; stopping")

    # ---- the ballot areas: one line between two neighbours, kept once
    pre, polys, put_right = read_precincts(vdoc)
    twins = settle_twins(pre, polys, {c: [[G.vxy(k) for k in r] for r in rings] for c, rings in county_rows.items()})
    if twins:
        put_right["rings sent for two areas, kept only in the area whose county holds them"] = len(twins)
    slivers, gave = W.settle_overlaps(pre, polys)
    arcs, sides, rings_of, odd = G.topology(polys)
    if any(not r for r in rings_of):
        raise GeoError(f"    ballot area {pre[[i for i, r in enumerate(rings_of) if not r][0]]['id']} has no ring left after cleaning; stopping")
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} ballot areas ({len({(p['county'], p['precinct']) for p in pre}):,} precincts), {sum(len(r) for r in rings_of):,} rings, "
        f"{len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to "
        f"{G.TOL_PRECINCT} m); {lone:,} lines have an area on one side only, {len(seam):,} of them with another area just across; {slivers} sliver rings "
        f"left out, {sum(n for _w, n in gave)} points given up by {len(gave)} areas that ran along a neighbour's line the same way"
        + (f"; put right: {put_right}" if put_right else "") + (f"; odd: {dict(odd)}" if odd else ""))

    # ---- the districts: each layer laid over the ballot areas; the combination areas are the check
    combos = set()
    for a, _rings in codoc["rows"]:
        vals = []
        for f in ("Congress", "Senate", "House", "School"):
            v = a.get(f)
            if not (isinstance(v, (int, float)) or re.fullmatch(r"\d{1,2}", str(v or "").strip())):
                raise GeoError(f"    district combination areas: the row numbered {a.get('OBJECTID')} has {f} {v!r}; stopping")
            vals.append(str(int(v)))
        combos.add(tuple(vals))
    ckeys, cpolys, cdarcs, cdsides, _cdr, cdodd = I.fabric(cddoc["rows"], lambda a: str(int(a["DISTRICT"])))
    hkeys, hpolys, harcs, hsides, _hr, hodd = I.fabric(hdoc["rows"], lambda a: str(int(a["DIST"])))
    skeys, spolys, sarcs, ssides, _sr, sodd = I.fabric(sdoc["rows"], lambda a: str(int(a["DIST"])))
    sbkeys, sbpolys, _sbarcs, _sbsides, _sbr, _sbodd = I.fabric(sbdoc["rows"], lambda a: str(int(a["DIST"])))
    if (ckeys != [str(n) for n in range(1, N_CD + 1)] or hkeys != [str(n) for n in range(1, N_HOUSE + 1)] or skeys != [str(n) for n in range(1, N_SENATE + 1)]
            or sbkeys != [str(n) for n in range(1, N_SBOE + 1)]):
        raise GeoError("    district layers: not 4 congressional, 75 House, 29 Senate and 15 State Board of Education districts; stopping")
    if [len({c[i] for c in combos}) for i in range(4)] != [N_CD, N_SENATE, N_HOUSE, N_SBOE]:
        raise GeoError("    the combination areas and the district layers do not number the same districts; stopping")

    # ---- municipalities: UGRC's lines, one row a place, keyed by the Census Bureau's place code
    census_places = {r["PLACEFP"]: r for r, _ in I.read_shapefile(plpath, lambda r: r["STATEFP"] == FIPS)}
    census_inc = {f: r for f, r in census_places.items() if r["LSAD"] in PLACE_KIND and r["FUNCSTAT"] == "A"}
    by_census_name = collections.defaultdict(list)
    for f, r in census_inc.items():
        by_census_name[r["NAME"].casefold()].append(f)
    mrows, mname, mkind, mcode_from = [], {}, {}, collections.Counter()
    for a, rings in one_row_each(mdoc["rows"], lambda a: G.blank(a.get("FIPS")) or "X-" + G.blank(a.get("UGRCODE") or a.get("NAME")), "municipalities"):
        f = G.blank(a.get("FIPS"))
        if not f and len(by_census_name.get(clean_text(a.get("NAME")).casefold(), [])) == 1:
            f = by_census_name[clean_text(a.get("NAME")).casefold()][0]      # a place the state's row gives no code yet, which the Bureau's list has by the same name
            mcode_from["Census place code, by the same name in the Bureau's list"] += 1
        elif re.fullmatch(r"\d{5}", f):
            mcode_from["Census place code"] += 1
        if re.fullmatch(r"\d{5}", f):
            mid = f"{STATE}-M-{f}"
        else:
            code = re.sub(r"[^A-Z0-9]", "", G.blank(a.get("UGRCODE")).upper()) or re.sub(r"[^A-Z0-9]", "", G.blank(a.get("NAME")).upper())
            mid = f"{STATE}-M-{code}"
            mcode_from["UGRC code (no Census place code yet)"] += 1
        cp = census_inc.get(f)
        kind = PLACE_KIND.get(cp["LSAD"]) if cp else None
        nm = clean_text(a.get("NAME"))
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,40}", nm):
            raise GeoError(f"    municipalities: a name that does not fit the layout this builder was checked against ({len(nm)} characters); stopping")
        mname[mid] = names.get(("mcd", mid)) or (cp["NAMELSAD"] if cp else nm)
        mkind[mid] = kind or "municipality"
        mrows.append((dict(a, _id=mid), rings))
    mkeys, mpolys, marcs, msides, _mr, modd = I.fabric(mrows, lambda r: r["_id"])
    if not 250 <= len(mkeys) <= 270:
        raise GeoError(f"    municipalities: {len(mkeys)} places, which does not fit Utah's (about 255 cities and towns); stopping")
    muni_vs_census = {"in_the_states_file_only": sorted(f"{mname[k]} ({k})" for k in mkeys if mkind[k] == "municipality"),
                      "in_the_bureaus_list_only": sorted(f"{r['NAMELSAD']} ({STATE}-M-{f})" for f, r in census_inc.items() if f"{STATE}-M-{f}" not in set(mkeys))}

    # ---- school districts (Census, one fabric)
    srows, sname, snces = [], {}, {}
    for r, rings in I.read_shapefile(unpath, lambda r: r["STATEFP"] == FIPS):
        if r["UNSDLEA"] == "99997":
            continue
        sid = f"{STATE}-S-{r['UNSDLEA']}"
        srows.append((dict(r, _id=sid), Y.as_lonlat(rings)))
        sname[sid] = names.get(("school", sid)) or r["NAME"]
        snces[sid] = FIPS + r["UNSDLEA"]
    schkeys, _schpolys, scharcs, schsides, _schr, schodd = I.fabric(srows, lambda r: r["_id"])
    schfine, _ = G.simplify_arcs(scharcs, _schr, G.TOL_SCHOOL)
    if len(schkeys) != 41:
        raise GeoError(f"    school districts: {len(schkeys)}, not Utah's 41; stopping")
    say(f"      {len(ckeys)} congressional ({len(cdarcs):,} lines), {len(skeys)} Senate ({len(sarcs):,}), {len(hkeys)} House ({len(harcs):,}) districts, "
        f"{len(codoc['rows'])} district combination areas, {len(mkeys)} municipalities ({len(marcs):,} lines; ids from {dict(mcode_from)}), "
        f"{len(schkeys)} school districts ({len(scharcs):,} lines)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("Congress", cdodd), ("House", hodd), ("Senate", sodd), ("municipalities", modd), ("school", schodd)) if o))

    # ---- overlays
    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.TOL_SCHOOL, G.SCHOOL_THICK, 1]).encode()).hexdigest()   # noqa: E731
    o_muni = overlay_cached("municipal", pre_rings, I.rings_xy(mpolys), stamp(vpath, mpath), refresh, say)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _schr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(vpath, unpath), refresh, say)

    splits, nones = {}, []
    for prop, polys_, keys_, src in (("cd", cpolys, ckeys, cdpath), ("senate", spolys, skeys, spath), ("house", hpolys, hkeys, hpath),
                                     ("sboe", sbpolys, [sboe_id(k) for k in sbkeys], sbpath)):
        o = overlay_cached(prop, pre_rings, I.rings_xy(polys_), stamp(vpath, src), refresh, say)
        splits[prop], none = I.assign(pre, o, keys_, prop)
        nones += none
    if nones:
        raise GeoError(f"    {len(nones)} ballot areas touch no district of some kind (e.g. {nones[0]}); stopping")
    not_a_combo = [p["id"] for p in pre if (p["cd"], p["senate"], p["house"], p["sboe"][len(STATE) + 5:]) not in combos]
    if len(not_a_combo) > 0.01 * len(pre):
        raise GeoError(f"    {len(not_a_combo)} ballot areas lie in districts whose combination the state's combination areas do not have (e.g. {not_a_combo[0]}); stopping")
    say("      districts by ballot area (the one holding most of it): " + ", ".join(f"{len(v)} in a second {k} district" for k, v in splits.items())
        + f" ({SPLIT_SHARE:.0%} of the area or more)")

    jud_of, jud_checked = judicial_of(jdoc, cshort, info)
    in_place = several = outside = 0
    for p, got in zip(pre, o_muni):
        rows = sorted(((mkeys[d], s, t) for d, s, t in got), key=lambda x: (-x[1], x[0]))
        own = [(k, s) for k, s, t in rows if t]
        p["mcd"] = own[0][0] if own and own[0][1] >= 0.5 else None
        inside = sum(s for _k, s, _t in rows)
        if len(own) > 1 or (own and p["mcd"] is None) or (p["mcd"] and 1 - inside >= SPLIT_SHARE):
            p["mcd_all"], p["mcd_pct"] = [k for k, _s in own], [round(100 * s, 1) for _k, s in own]
            several += 1
        in_place += p["mcd"] is not None
        outside += p["mcd"] is None and not own
        p["jud"] = jud_of[p["county"]]
    say(f"      municipalities by ballot area: {in_place:,} lie (half or more) in one city or town, {outside:,} in none, "
        f"{several:,} reach more than one place or lie partly outside")
    split = none = edges = 0
    for p, got in zip(pre, o_sch):
        rows = [(schkeys[d], share, thick) for d, share, thick in got]
        keep = sorted(((k, s) for k, s, thick in rows if thick), key=lambda x: (-x[1], x[0]))
        if not keep and rows:
            best = max(((k, s) for k, s, _t in rows), key=lambda x: x[1])
            if best[1] >= 0.5:
                keep = [best]
        outside_s = max(0.0, 1.0 - sum(s for _k, s, _t in rows))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside_s >= 0.03) else None
        p["school_out"] = round(100 * outside_s, 1) if outside_s >= 0.03 else None
        p["school_edge"] = sorted({k for k, _s, _t in rows} - set(p["school"]))
        split += len(keep) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(keep) < 2
    say(f"      school districts by ballot area: {split:,} are split between two or more districts, {none} lie in none, {edges:,} others only brush a "
        "neighbouring district along a line")

    # ---- the area check: each county's ballot areas against UGRC's county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731  Esri's winding: outer rings clockwise
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = {c: sum(signed([G.vxy(k) for k in r]) for r in county_rows[c]) for c in clist}
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the ballot areas of {', '.join(cname[c] for c in off[:5])} do not cover the county UGRC draws; stopping")
    say(f"      area check: the ballot areas cover {100 + state_pct:.3f}% of UGRC's Utah; the county furthest off is {cname[worst]} ({worst_pct:+.2f}%)")

    vals = {"county": [p["county"] for p in pre], "mcd": [p["mcd"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": [p["cd"] for p in pre], "judicial": [p["jud"] for p in pre]}
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

    # ---- write (into a folder beside the target, moved into it only when everything is written)
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

    def one(arcs_, sides_, v, tol):
        g, q, _l, _r = G.build_layer(arcs_, sides_, [v], tol)
        return g, q

    VISTA, COMBO, CDS, LEG, SBOE, MUNI, CTY, JUD, SCH, PLACE = (
        "ut-ugrc-vista-ballot-areas", "ut-ugrc-district-combination-areas-2026", "ut-ugrc-us-congress-districts-2026-2032",
        "ut-ugrc-legislative-districts-2022-2032", "ut-ugrc-school-board-districts-2022-2032", "ut-ugrc-municipal-boundaries",
        "ut-ugrc-county-boundaries", "ut-ugrc-judicial-districts", "ut-census-tiger-2025-school-districts", "ut-census-tiger-2025-places")
    jud_counties = collections.defaultdict(list)
    for c in sorted(cname, key=lambda c: cname[c]):
        jud_counties[jud_of[c]].append(cname[c])
    layer("state", *one(arcs, sides, [STATE] * len(pre), G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, VISTA)
    layer("county", *one(arcs, sides, vals["county"], G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, VISTA)
    layer("cd", *one(cdarcs, cdsides, ckeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, CDS)
    layer("senate", *one(sarcs, ssides, skeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, LEG)
    layer("house", *one(harcs, hsides, hkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v}, LEG)
    layer("judicial", *one(arcs, sides, vals["judicial"], G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{G.ordinal(v[2:])} Judicial District", "j": v, "d": v[2:], "counties": jud_counties[v]},
          VISTA + "; which counties, from " + JUD)
    mg, mq, _l, _r = G.build_layer(marcs, msides, [mkeys], TOL_MCD)
    layer("mcd", mg, mq, TOL_MCD, lambda v: {"id": v, "name": mname[v], "j": v, "d": None, "t": mkind[v]}, MUNI, zoom=MCD_ZOOM)
    sprops = lambda v: {"id": v, "name": sname[v], "j": v, "d": None, "nces": snces[v]}      # noqa: E731
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
        geoms, used_names = [], {"mcd": {}, "school": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p["code"], "house": p["house"], "senate": p["senate"], "cd": p["cd"],
                  "judicial": p["jud"], "sboe": p["sboe"], "school": p["school"]}
            if p["mcd"]:
                pr["mcd"] = p["mcd"]
                used_names["mcd"][p["mcd"]] = mname[p["mcd"]]
            if p.get("mcd_all"):
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
                for k in p["mcd_all"]:
                    used_names["mcd"][k] = mname[k]
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
                raise GeoError(f"    ballot area {g['id']} has no shape on the grid; stopping")
            xs = [x for poly in polys_pts for x, _y in poly[0]]
            ys = [y for poly in polys_pts for _x, y in poly[0]]
            bx += [min(xs) // G.BOX_STEP, min(ys) // G.BOX_STEP, -(-max(xs) // G.BOX_STEP), -(-max(ys) // G.BOX_STEP)]
        boxes[county] = bx
        rel = f"precincts/{county}.json"
        size = put(rel, doc)
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids, {"sboe": {p["sboe"] for p in pre}})
    check["judicial_districts_checked_against_the_races"] = jud_checked
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    ugrc, both, cb = "Utah Geospatial Resource Center (UGRC)", "Utah Geospatial Resource Center and Utah Lieutenant Governor's Office", "U.S. Census Bureau"
    sboe_list = ", ".join(f"{sboe_id(n)} {n}" for n in range(1, N_SBOE + 1))
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": VISTA, "agency": both, "title": "Utah Vista Ballot Areas (the State Geographic Information Database)",
                  "about": "The voting precincts of all 29 counties as the county clerks submit them to Vista, the state's voter system; where a "
                           "county splits a precinct into subprecincts, the subprecincts.",
                  "url": VISTA_ITEM, "service": VISTA_SERVICE, "fetched": vdoc.get("fetched"), "sha256": G.sha_file(vpath), "rows": len(vdoc["rows"])},
                 **edited["vista"]),
            dict({"id": COMBO, "agency": both, "title": "Utah District Combination Areas 2026 (updated after the 2025 court decision)",
                  "about": "Every piece of the state with one combination of congressional, Utah Senate, Utah House and State Board of Education "
                           "district: read as a check that each ballot area's four districts are a combination the state has.",
                  "url": COMBO_ITEM, "service": COMBO_SERVICE, "fetched": codoc.get("fetched"), "sha256": G.sha_file(copath), "rows": len(codoc["rows"])},
                 **edited["combo"]),
            dict({"id": CDS, "agency": both, "title": "Utah US Congress Districts 2026 to 2032",
                  "about": "The four districts the Third District Court adopted in November 2025 after it set aside the Legislature's plan, used for "
                           "elections from January 1, 2026.",
                  "url": CD_ITEM, "service": CD_SERVICE, "fetched": cddoc.get("fetched"), "sha256": G.sha_file(cdpath), "rows": len(ckeys)}, **edited["cd"]),
            dict({"id": LEG, "agency": both, "title": "Utah House Districts 2022 to 2032 and Utah Senate Districts 2022 to 2032",
                  "about": "The 75 House and 29 Senate districts the Legislature drew after the 2020 census.",
                  "url": HOUSE_ITEM, "senate_url": SENATE_ITEM, "service": HOUSE_SERVICE, "senate_service": SENATE_SERVICE, "fetched": hdoc.get("fetched"),
                  "sha256": {"house": G.sha_file(hpath), "senate": G.sha_file(spath)}, "rows": len(hkeys) + len(skeys)}, **edited["house"]),
            dict({"id": SBOE, "agency": both, "title": "Utah School Board Districts 2022 to 2032",
                  "about": "The 15 State Board of Education districts, laid over the ballot areas (the member column is never asked for).",
                  "url": SBOE_ITEM, "service": SBOE_SERVICE, "fetched": sbdoc.get("fetched"), "sha256": G.sha_file(sbpath), "rows": len(sbkeys)}, **edited["sboe"]),
            dict({"id": MUNI, "agency": ugrc, "title": "Utah Municipal Boundaries",
                  "about": "City and town limits, kept current with the boundary changes the Lieutenant Governor certifies; each "
                           "keyed by the Census Bureau's place code it carries.",
                  "url": MUNI_ITEM, "service": MUNI_SERVICE, "fetched": mdoc.get("fetched"), "sha256": G.sha_file(mpath), "rows": len(mkeys)}, **edited["muni"]),
            dict({"id": CTY, "agency": ugrc, "title": "Utah County Boundaries",
                  "about": "Read only for the area check: each county's ballot areas against the county.",
                  "url": COUNTY_ITEM, "service": COUNTY_SERVICE, "fetched": cydoc.get("fetched"), "sha256": G.sha_file(cypath), "rows": len(county_rows)},
                 **edited["county"]),
            dict({"id": JUD, "agency": ugrc, "title": "Utah Judicial Districts",
                  "about": "Read only for which counties make up each of the eight judicial districts, checked against Utah Code 78A-1-102; the lines "
                           "drawn are the county lines.",
                  "url": JUD_ITEM, "service": JUD_SERVICE, "statute": STATUTE_URL, "fetched": jdoc.get("fetched"), "sha256": G.sha_file(jpath), "rows": N_JUD},
                 **edited["judicial"]),
            {"id": SCH, "agency": cb, "title": "TIGER/Line Shapefiles 2025, unified school districts, Utah (tl_2025_49_unsd.zip)",
             "about": "School district lines as the Bureau had them for the 2024-2025 school year, from the State's own reporting.",
             "url": UNSD_URL, "fetched": mtime(unpath), "sha256": G.sha_file(unpath), "rows": len(schkeys)},
            {"id": PLACE, "agency": cb, "title": "TIGER/Line Shapefiles 2025, places, Utah (tl_2025_49_place.zip)",
             "about": "Read only for whether a municipality is a city or a town, and for its name, by the place code UGRC's layer carries.",
             "url": PLACE_URL, "fetched": mtime(plpath), "sha256": G.sha_file(plpath), "rows": len(census_places)},
        ],
        "notes": {
            "lines": f"Every precinct line is the state layer's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 degree (about a "
                     "metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "A shape is a ballot area: a precinct, or where a county clerk has split a precinct into formal subprecincts, a subprecinct "
                         "(subprecincts exist so that everyone in one gets the same ballot). The county clerk is the authority on which precinct an "
                         "address is in.",
            "districts": "Which congressional, Utah Senate, Utah House and State Board of Education district a ballot area lies in is worked out here by "
                         "laying the state's district lines over it (analysis, not an official list): the district holding most of its "
                         f"area. The few ballot areas with {SPLIT_SHARE:.0%} or more of their area in a second district are listed under check. "
                         "The congressional districts are the four the Third District Court adopted in November 2025, used from the 2026 elections.",
            "places": "Utah's cities and towns, by the state's municipal boundaries. A ballot area's mcd is the place holding half or more of it "
                      "(absent in unincorporated country); mcd_all lists every place it reaches where it reaches more than one or lies partly "
                      "outside: to say which place a point is in, ask the mcd layer, not the precinct. A place the Census Bureau's 2025 list does "
                      "not yet carry as a city or town (newly incorporated) is called a municipality; muni_vs_census under counts names the places "
                      "on one list and not the other.",
            "commissioners": "No statewide file has the lines of county commission or council districts; each county keeps its own.",
            "boards": "The State Board of Education's 15 members are each elected by a district; sboe names the district a ballot area votes in.",
            "school": "School district lines are the Census Bureau's 2025 file. Which districts a ballot area lies in is analysis, not an official list: a "
                      f"district counts when its part of the area is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each "
                      "district's share of the area (land and water, not voters).",
            "judicial": "The eight judicial districts are whole counties (Utah Code 78A-1-102); district and juvenile court judges stand for retention "
                        "in them. A justice court judge stands for retention in the county or city the court serves.",
            "wards": "No statewide file has the lines of city council districts: a council district's race is placed on its city, and the city "
                     "recorder says which district an address is in.",
            "authority": "For which precinct an address is in, the county clerk is the authority; for where to vote, the state's voter search and the "
                         "county clerk.",
            "precinct_ids": "A ballot area's id is its county's five digits, a full stop and the VistaID the state's layer gives it (49035.SLC009; "
                            "49011.6BO10:I-S- for a subprecinct).",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of "
                     "its rings, a negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per ballot area. arcMask[i] has bit k set when line i is an outline "
                            "of arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the areas on the right and left of line i (-1: an area in another "
                            "county's file, or one just across a hairline gap in the state's drawing; -2: outside Utah); names gives the names of the "
                            "places the file's areas lie in.",
            "boxes": "boxes[county] holds four whole numbers a ballot area, in the file's order: west, south, east, north in steps of box_step degrees "
                     "from the transform's translate, rounded outwards. A point is tried against every area whose box (widened by half a step) holds it.",
            "precinct_properties": {"name": "the precinct's name: the county's own name for it where the state's layer gives one, else 'Precinct' and "
                                            "its code (and subprecinct)",
                                    "county": "county id", "precinct": "the precinct's code as the county gives it, with the subprecinct",
                                    "mcd": "the city or town holding half or more of the area (absent in unincorporated country)",
                                    "mcd_all": "list, where the area reaches more than one place or lies partly outside: every place it lies in, largest share first",
                                    "mcd_pct": "list, with mcd_all: each place's share of the area, in percent",
                                    "house": "Utah House district", "senate": "Utah Senate district", "cd": "congressional district",
                                    "judicial": "judicial district",
                                    "sboe": f"State Board of Education district ({sboe_list})",
                                    "split": "only where a second district holds 3 percent or more of the area: for house, senate, cd or sboe, each district's share in percent",
                                    "school": "list: the school districts the area lies in, largest share first",
                                    "school_pct": "list, when the area is in more than one: each district's share of its area, in percent",
                                    "school_out": "percent of the area that lies in no school district (given from 3 percent up)",
                                    "school_edge": "list: neighbouring districts that only brush the area along a line (try them too when placing a point)",
                                    "c": "a point inside the area's largest part, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "UT (j is 49)", "county": "the county's five-digit code (49035)",
                    "mcd": "UT-M- and the Census Bureau's place code (UT-M-67000), or UGRC's code for a place the Bureau has no code for yet; "
                           "properties.t says city or town (municipality: incorporated after the Bureau's 2025 list)",
                    "house": "the district (21)", "senate": "the district (12)", "cd": "the district (1); properties.race is the race for Congress",
                    "judicial": "JD and the district's number (JD3); d is the number",
                    "school": "UT-S- and the Census Bureau's five-digit district code; properties.nces is the federal district code",
                    "sboe": "a precinct property only: UT-SBOE and the district's number (UT-SBOE7)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "precincts_before_subprecincts": len({(p["county"], p["precinct"]) for p in pre}), "counties": len(counties),
                   "rows_put_right": put_right, "with_the_countys_own_name": sum(1 for p in pre if p["alias"]),
                   "in_a_city_or_town": in_place, "muni_vs_census": muni_vs_census, "reaching_more_than_one_place_or_partly_outside": several,
                   "split_between_school_districts": split, "rings_too_small_for_the_grid": dropped_rings,
                   "districts_not_a_combination_the_state_lists": not_a_combo,
                   **{f"split_between_{k}_districts": len(v) for k, v in splits.items()},
                   "lines_with_a_precinct_on_one_side": lone, "with_a_precinct_across": len(seam),
                   "sliver_rings_left_out": slivers, "points_given_up_where_two_precincts_overlapped": dict(gave),
                   "area_against_ugrc_counties_percent": {"state": round(state_pct, 3), "furthest_county": worst, "its_difference": round(worst_pct, 2)}},
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Utah races have a shape"
        + (f"; {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Utah ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

TEST_POINTS = [
    # name, longitude, latitude, what the point's ballot area lies in, the city or town at the point (None outside every
    # one), the federal code (NCES) of its school district, and the ballot area itself. County, place, congressional
    # district (the Bureau's "120th Congressional Districts", which carry the 2026 plan), Senate and House district and
    # school district are the Census Bureau's geocoder's answer for those coordinates (asked 2026-10-03:
    # geocoding.geo.census.gov, "geographies/coordinates", Current), an answer that owes nothing to the files tested
    # here; the ballot area, the State Board of Education district and (again) the congressional district are UGRC's own
    # services' answer to a point query. The judicial district is the county's (Utah Code 78A-1-102).
    ('the State Capitol, Salt Lake City', -111.8882, 40.7777, {'county': '49035', 'cd': '1', 'senate': '8', 'house': '22', 'judicial': 'JD3', 'sboe': 'UT-SBOE4'}, "UT-M-67000", "4900870", "49035.SLC008"),
    ('Provo City Center', -111.6585, 40.2338, {'county': '49049', 'cd': '3', 'senate': '24', 'house': '62', 'judicial': 'JD4', 'sboe': 'UT-SBOE13'}, "UT-M-62470", "4900810", "49049.25PR46"),
    ('downtown Ogden, 25th Street', -111.972, 41.221, {'county': '49057', 'cd': '2', 'senate': '5', 'house': '9', 'judicial': 'JD2', 'sboe': 'UT-SBOE2'}, "UT-M-55980", "4900720", "49057.29OG21"),
    ('downtown St. George', -113.5841, 37.1083, {'county': '49053', 'cd': '3', 'senate': '29', 'house': '75', 'judicial': 'JD5', 'sboe': 'UT-SBOE15'}, "UT-M-65330", "4901140", "49053.27STG:41"),
    ('downtown Logan', -111.8338, 41.7355, {'county': '49005', 'cd': '2', 'senate': '2', 'house': '3', 'judicial': 'JD1', 'sboe': 'UT-SBOE1'}, "UT-M-45860", "4900510", "49005.3LG13:I"),
    ('Main Street, Park City', -111.496, 40.644, {'county': '49043', 'cd': '3', 'senate': '20', 'house': '59', 'judicial': 'JD3', 'sboe': 'UT-SBOE6'}, "UT-M-58070", "4900750", "49043.22DVS:25"),
    ('downtown Moab', -109.5498, 38.5733, {'county': '49019', 'cd': '3', 'senate': '26', 'house': '69', 'judicial': 'JD7', 'sboe': 'UT-SBOE14'}, "UT-M-50700", "4900330", "49019.10-3M3"),
    ('downtown Cedar City', -113.0619, 37.6775, {'county': '49021', 'cd': '3', 'senate': '28', 'house': '71', 'judicial': 'JD5', 'sboe': 'UT-SBOE14'}, "UT-M-11320", "4900390", "49021.11CC7:1"),
    ('downtown Vernal', -109.5287, 40.4555, {'county': '49047', 'cd': '3', 'senate': '20', 'house': '68', 'judicial': 'JD8', 'sboe': 'UT-SBOE12'}, "UT-M-80090", "4901080", "49047.24VC09:03"),
    ('downtown Price', -110.8107, 39.5994, {'county': '49007', 'cd': '3', 'senate': '26', 'house': '67', 'judicial': 'JD7', 'sboe': 'UT-SBOE14'}, "UT-M-62030", "4900150", "49007.0417"),
    ('downtown Tooele', -112.2983, 40.5308, {'county': '49045', 'cd': '4', 'senate': '11', 'house': '28', 'judicial': 'JD3', 'sboe': 'UT-SBOE10'}, "UT-M-76680", "4901050", "49045.23TC06"),
    ('downtown Heber City', -111.413, 40.507, {'county': '49051', 'cd': '3', 'senate': '20', 'house': '59', 'judicial': 'JD4', 'sboe': 'UT-SBOE12'}, "UT-M-34200", "4901110", "49051.26-205"),
    ('downtown Brigham City', -112.0153, 41.5102, {'county': '49003', 'cd': '2', 'senate': '1', 'house': '6', 'judicial': 'JD1', 'sboe': 'UT-SBOE1'}, "UT-M-08460", "4900090", "49003.02FED"),
    ('West Valley City Hall', -112.001, 40.6916, {'county': '49035', 'cd': '1', 'senate': '12', 'house': '30', 'judicial': 'JD3', 'sboe': 'UT-SBOE5'}, "UT-M-83470", "4900360", "49035.WVC036"),
    ('Sandy City Hall', -111.891, 40.5717, {'county': '49035', 'cd': '4', 'senate': '15', 'house': '43', 'judicial': 'JD3', 'sboe': 'UT-SBOE9'}, "UT-M-67440", "4900142", "49035.SAN028"),
    ('Orem City Center', -111.6945, 40.2969, {'county': '49049', 'cd': '3', 'senate': '24', 'house': '57', 'judicial': 'JD4', 'sboe': 'UT-SBOE12'}, "UT-M-57300", "4900030", "49049.25OR30"),
    ('Layton City Hall', -111.97, 41.06, {'county': '49011', 'cd': '2', 'senate': '6', 'house': '15', 'judicial': 'JD2', 'sboe': 'UT-SBOE4'}, "UT-M-43660", "4900210", "49011.6LA65:I-N-"),
    ('downtown Kanab', -112.5285, 37.0475, {'county': '49025', 'cd': '3', 'senate': '26', 'house': '69', 'judicial': 'JD6', 'sboe': 'UT-SBOE15'}, "UT-M-39920", "4900480", "49025.13KA2:A"),
    ('downtown Richfield', -112.0841, 38.7725, {'county': '49041', 'cd': '4', 'senate': '27', 'house': '70', 'judicial': 'JD6', 'sboe': 'UT-SBOE14'}, "UT-M-63570", "4900930", "49041.2111:1"),
    ('downtown Blanding', -109.4787, 37.6244, {'county': '49037', 'cd': '3', 'senate': '26', 'house': '69', 'judicial': 'JD7', 'sboe': 'UT-SBOE15'}, "UT-M-06370", "4900900", "49037.1912B"),
    ('downtown Manti', -111.6363, 39.2683, {'county': '49039', 'cd': '4', 'senate': '27', 'house': '66', 'judicial': 'JD6', 'sboe': 'UT-SBOE14'}, "UT-M-47730", "4900960", "49039.20MAN:2M"),
    ('open desert west of Delta, Millard County', -113.2, 39.3, {'county': '49027', 'cd': '4', 'senate': '28', 'house': '29', 'judicial': 'JD4', 'sboe': 'UT-SBOE14'}, None, "4900540", "49027.14HN11:1"),
    ('Lake Point, Tooele County (incorporated after the state layer gave it a code)', -112.26, 40.682, {'county': '49045', 'cd': '4', 'senate': '1', 'house': '29', 'judicial': 'JD3', 'sboe': 'UT-SBOE10'}, "UT-M-42010", "4901050", "49045.23LP01:1"),
    ('Draper, Salt Lake County side', -111.864, 40.525, {'county': '49035', 'cd': '4', 'senate': '19', 'house': '46', 'judicial': 'JD3', 'sboe': 'UT-SBOE7'}, "UT-M-20120", "4900142", "49035.DRP011"),
    ('Huntsville, Weber County', -111.77, 41.261, {'county': '49057', 'cd': '2', 'senate': '3', 'house': '8', 'judicial': 'JD2', 'sboe': 'UT-SBOE2'}, "UT-M-37060", "4901200", "49057.29HU01"),
    ('Magna', -112.093, 40.709, {'county': '49035', 'cd': '1', 'senate': '11', 'house': '27', 'judicial': 'JD3', 'sboe': 'UT-SBOE10'}, "UT-M-47290", "4900360", "49035.MAG003"),
]
LINE_POINTS = [("the Salt Lake-Utah county line at the Point of the Mountain", -111.90, 40.465, ("49035", "49049")),
               ("the Davis-Weber county line", -112.00, 41.153, ("49011", "49057"))]
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
    check(total == index["counts"]["precincts"] == len(ids), "the county files do not hold as many ballot areas as the index says, each with its own id")
    shapes_seen, layer_ids = 0, {}
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        layer_ids[L["kind"]] = {g["id"] for g in gs}
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == N_COUNTY, f"there are not {N_COUNTY} county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the ballot areas on the two sides of a line")
    check(layer_ids.get("senate") == {str(n) for n in range(1, N_SENATE + 1)} and layer_ids.get("house") == {str(n) for n in range(1, N_HOUSE + 1)}
          and layer_ids.get("judicial") == {f"JD{n}" for n in range(1, N_JUD + 1)} and layer_ids.get("cd") == {str(n) for n in range(1, N_CD + 1)}
          and len(layer_ids.get("county", ())) == N_COUNTY and 250 <= len(layer_ids.get("mcd", ())) <= 270 and len(index["school"]["ids"]) == 41,
          "there are not 29 Senate, 75 House, 8 judicial and 4 congressional districts, 29 counties, about 260 municipalities and 41 school districts")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} ballot areas, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every area is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree = collections.defaultdict(list)
    asked = collections.Counter()
    school, place, sboe_seen = collections.Counter(), collections.Counter(), set()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial"}
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
            sboe_seen.add(pr.get("sboe"))
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("school", "school"), ("mcd_all", "mcd")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the area lies in" if sid in pr["school"] else "in a district the area only brushes" if sid else
                   "in none, in an area partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            place["the area's own place" if shape and shape["id"] == pr.get("mcd") else
                  "unincorporated, as the area says" if not shape and not pr.get("mcd") else
                  "another place the area names" if shape and shape["id"] in pr.get("mcd_all", []) else
                  "outside every place, in an area partly outside" if not shape and pr.get("mcd_all") else
                  "a place the area does not name" if shape else "outside the place the area names"] += 1
            if g["id"] in split_ids:
                continue
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
    check(wrong <= 3, f"{wrong} of {tested} ballot areas are not found again from a point inside them")
    check(not sum(no_shape.values()), f"ballot areas carry ids that are no shape of their layer: {dict(no_shape)}")
    check(sboe_seen == {sboe_id(n) for n in range(1, N_SBOE + 1)}, f"the ballot areas name {len(sboe_seen)} State Board of Education districts, not the fifteen")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the area at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} ballot areas' own points fall in no school district though the area is said to lie in one")
    check(place["a place the area does not name"] + place["outside the place the area names"] <= 0.02 * tested, f"the place at an area's own point: {dict(place)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} ballot areas found again from a point inside them; every id an area carries is a shape; layers "
        f"agree at {agree:,} of {sum(asked.values()):,} points ({skipped} too near a line to ask"
        + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items())) + "); school district at each area's point: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1])) + "; place: "
        + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

    # 3. known points
    rel = {c["id"]: c["file"] for c in index["counties"]}
    nces = {g["id"]: g["properties"].get("nces") for g in files.topo("layers/school.json")[0]["objects"]["school"]["geometries"]}
    for name, lon, lat, want, mcd, code, vista in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no ballot area"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: pr.get(k) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        ok &= check(found["geometry"]["id"] == vista, f"{name}: lands in ballot area {found['geometry']['id']}; the state's own service says {vista}")
        sid = G.school_at(files, found["geometry"], lon, lat)
        ok &= check(sid is not None and sid in pr["school"] and nces.get(sid) == code, f"{name}: the school district at the point is {sid} ({nces.get(sid)}); the geocoder says {code}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check((shape and shape["id"]) == mcd and (pr.get("mcd") == mcd or mcd in pr.get("mcd_all", [])),
                    f"{name}: the mcd layer gives {shape and shape['id']} and the area {pr.get('mcd')} {pr.get('mcd_all', '')}; the place is {mcd}")
        for prop, kind in layer_for.items():
            shape2, _edge = G.shape_at(files, kind, lon, lat)
            ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the area says {pr.get(prop)}")
        fdoc, _l = files.topo(rel[found["county"]])
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {fdoc['names'].get('mcd', {}).get(pr.get('mcd'), 'unincorporated')}, "
            f"{fdoc['name']}, CD {pr['cd']}, House {pr['house']}, Senate {pr['senate']}, {pr['judicial']}, {pr['sboe']}, "
            f"{fdoc['names']['school'].get(sid, sid)}; {found['edge']:.0f} m from the area's line")

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

    # 5. polling places say what they are; no name in the files reads like a contact
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    check(not re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|@", json.dumps(polls)), "polling_places.json carries something that reads like a phone number or an e-mail address")
    odd_names = 0
    for c in index["counties"]:
        doc, _l = files.topo(c["file"])
        for g in doc["objects"]["precincts"]["geometries"]:
            n = g["properties"]["name"]
            odd_names += n != f"Precinct {g['properties']['precinct']}" and alias_name(n) != n
    check(odd_names == 0, f"{odd_names} ballot area names are neither 'Precinct' and the code nor a county's own name that reads as a place name")
    say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def put_in_place(building=BUILDING, final=OUT, say=print):
    """The tested folder becomes ballot_geo/ut/ in one rename (an older ut/ is moved aside first and removed after)."""
    old = final.rstrip("\\/") + "._old"
    if os.path.isdir(old):
        shutil.rmtree(old)
    if os.path.isdir(final):
        os.rename(final, old)
    os.rename(building, final)
    if os.path.isdir(old):
        shutil.rmtree(old)
    say(f"    in place: {final}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Utah's ballot map -> ballot_geo/ut/")
    ap.add_argument("--out", default=None, help="folder to build and test in (a trial run; nothing is moved). Default: ballot_geo/_building_ut, put in place as ballot_geo/ut")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask the map services again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built (ballot_geo/ut, or --out)")
    a = ap.parse_args(argv)
    if a.selftest:
        if not selftest(os.path.abspath(a.out or OUT)):
            raise SystemExit(1)
        return
    target = os.path.abspath(a.out or BUILDING)
    build(out=target, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(target):
        raise SystemExit(1)
    if not a.out:
        put_in_place(target, OUT)


if __name__ == "__main__":
    main()
