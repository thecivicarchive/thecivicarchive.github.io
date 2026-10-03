"""
ballot/ar_geo.py - the geography behind Arkansas's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py, ballot/sd_geo.py, ballot/ky_geo.py and ballot/mi_geo.py for the few things those added,
and changes nothing in any of them), so the same page and the same reader (ballot/mn_geo_reader.js) read them all.

    python ballot/ar_geo.py                 builds ballot_geo/_building_ar/, runs the self-test on it, and only when the
                                            self-test passes puts it in place as ballot_geo/ar/ (the page builder draws a
                                            map for any state whose folder exists)
    python ballot/ar_geo.py --selftest      runs the self-test on ballot_geo/ar/ as it stands
    python ballot/ar_geo.py --refresh       asks every source again even when the cached copies are fresh
    python ballot/ar_geo.py --out DIR       builds and tests somewhere else, and leaves it there (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ar_local/geo/)
-------------------------------------------------------------------------------------------------------------------------
Every layer but one is the State of Arkansas's own, from the Arkansas GIS Office's public feature service "Boundaries"
(gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Boundaries/FeatureServer), read in longitude and latitude at full
detail. Each layer's own record names its publisher:
  - Precincts: ELECTION_PRECINCTS (layer 11), the voting precincts "assigned by each County Election Commission",
    compiled by the Secretary of State and kept by the GIS Office (edits through 2026). A precinct carries only its county
    and its name: no district. Which districts it lies in is worked out here by laying the district lines over it, and a
    precinct a district line runs through (3 percent or more of it, in a part thicker than a hairline) is cut along that
    line into parts (mi_geo.cut_precincts), each part in one House, Senate, congressional and justice of the peace
    district.
  - House (HOUSE_DISTRICTS, 15), Senate (SENATE_DISTRICTS, 34) and congressional (CONGRESSIONAL_DISTRICTS, 6) districts,
    the plans in force since 2022; justice of the peace districts (JUSTICE_PEACE_DISTRICT, 19), the quorum court
    districts every county redrew after the 2020 census.
  - Cities and towns: MUNICIPAL_BOUNDARY (41), with each city's Census place code (the ids of the ballot database's
    cities); council wards: MUNICIPAL_WARDS (50).
  - Circuit court districts and subdistricts: CIRCUIT_COURT (3). The districts are whole counties; each county's district
    is read from the lines and checked against every circuit judge and prosecuting attorney contest's counties.
  - School districts: PUB_SCHOOL_DISTRICTS (29), with the Department of Education's LEA code. School boards are elected
    in March (Act 503 of 2025); November carries only runoffs.
  - Townships: TOWNSHIP_POLITICAL_DIVISION (57), the political townships constables are elected by. Not a layer: a precinct
    names the township holding at least half of it, where the layer has one.
  - The area check uses the Census Bureau's 1:500,000 county file the kit already keeps (cb_2024_us_county_500k.zip).
  - Place names: the Census Bureau's 2020 place list for Arkansas (st05_ar_place2020.txt), where the ballot database has
    no name of its own.

What is built (ballot_geo/ar/): index.json, manifest.json, precincts/<county>.json (75), layers/<kind>.json (state, county,
cd, senate, house, judicial, com, mcd, ward, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "AR" (j = "05")
  county    "05119"                   sl_places county id; jurisdiction_id of county offices
  com       "05119|1"                 <county>|<justice of the peace district> (the quorum court: Arkansas's county board)
  house     "35"   senate "12"   cd "2" (properties.race is 2026-AR-H02)
  judicial  "AR-JD6", "AR-JD11-West"  the jurisdiction_id of circuit judge and prosecuting attorney races
  judicial_subdistrict "AR-JD6-S1"   (a precinct property) subdistrict 6.1 of the 6th circuit
  mcd       "AR-M-41000"              AR-M- and the Census Bureau's place code
  ward      "AR-M-41000|Ward 1"       <city>|Ward <n>, as the council races word it
  school    "AR-S-6001000"            AR-S- and the LEA code; a district the ballot database names by an id of its own keeps
                                      that id (Elkins: AR-S-143-elkins-school-district-10)
  township  "05119|Big Rock"          (a precinct property) <county>|<township>

POLLING PLACES
--------------
No list of polling places is published where a script may read it. The Secretary of State's VoterView answers for one
voter at a time (by name and birth date), and each county's election commission names its own polling sites, many of
them vote centers open to any voter of the county. polling_places.json says so ("waiting"); nothing is read.
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
from ballot import nd_geo as N  # noqa: E402
from ballot import ky_geo as K  # noqa: E402
from ballot import sd_geo as S  # noqa: E402
from ballot import mi_geo as M  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "AR", "05", "Arkansas"
GEO_ROOT = os.path.join(HERE, "ballot_geo")
OUT = os.path.join(GEO_ROOT, "ar")
BUILDING = os.path.join(GEO_ROOT, "_building_ar")
CACHE = os.path.join(HERE, "states_cache", "ar_local", "geo")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://www.voterview.ar-nova.org/voterview"      # the Secretary of State's VoterView: one voter's polling place
SOS_ELECTIONS = "https://www.sos.arkansas.gov/elections"

AGIO = "https://gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Boundaries/FeatureServer/"
AGIO_HUB = "https://gis.arkansas.gov/"
LAYERS = {      # key: (layer number, fields, object id field, page size, the layer's name)
    "precincts": (11, "objectid,county_fips,county_name,precinct,edit_date", "objectid", 200, "ELECTION_PRECINCTS"),
    "house": (15, "objectid,ndistrict", "objectid", 100, "HOUSE_DISTRICTS"),
    "senate": (34, "objectid,ndistrict", "objectid", 100, "SENATE_DISTRICTS"),
    "cd": (6, "objectid,district", "objectid", 100, "CONGRESSIONAL_DISTRICTS"),
    "jp": (19, "objectid,county,fips,district", "objectid", 100, "JUSTICE_PEACE_DISTRICT"),
    "cities": (41, "objectid,city_name,city_fips,classification,revised_date", "objectid", 100, "MUNICIPAL_BOUNDARY"),
    "wards": (50, "objectid,city_name,city_fips,ward,ward_code,revised_date", "objectid", 100, "MUNICIPAL_WARDS"),
    "circuit": (3, "objectid,circuit_court", "objectid", 50, "CIRCUIT_COURT"),
    "school": (29, "objectid,lea,name", "objectid", 100, "PUB_SCHOOL_DISTRICTS"),
    "townships": (57, "objectid,county,countyfips,name", "objectid", 100, "TOWNSHIP_POLITICAL_DIVISION"),
}
FILE_OF = {k: "agio_" + v[4].lower() for k, v in LAYERS.items()}
PLACE_LIST = os.path.join(HERE, "ballot_cache", "ar", "local", "st05_ar_place2020.txt")
PLACE_LIST_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st05_ar_place2020.txt"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")      # the kit's own copy, for the area check

# The school districts the ballot database names by an id of its own (its loader read them from a county's list), by
# LEA code: the database's id and the layer's name (checked when the build runs).
SCHOOL_IN_DB = {"7201000": ("AR-S-143-elkins-school-district-10", "Elkins")}

ARC_KINDS = ["county", "com", "house", "senate", "cd", "judicial"]
CUT_KINDS = ("house", "senate", "cd", "com")
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
WHOLE_SHARE = 0.98                # a precinct with this share of its area in one city (or ward) is that city's
HALF = 0.5                        # a precinct names the township or subdistrict holding at least this share of it
KNIT_M = 1.0                      # metres: two precincts' drawings of one line this close together are made the same line
TINY_M2 = 100.0                   # square metres: a precinct drawn only as a sliver this small is left out (and listed) once the knitting folds it flat
AREA_SLACK = 0.03
COUNTY_AGREE = 0.95               # a county's circuit: the share of its precincts the circuit lines must put in one district
COUNTS = {"county": 75, "house": 100, "senate": 35, "cd": 4, "judicial": 28}
SIDE = {"N": "North", "S": "South", "E": "East", "W": "West"}


def clean(v):
    return K.clean(v)


def letters(text):
    return re.sub(r"[^A-Z]", "", (text or "").upper())


def num(v):
    """'086' -> '86', 26.0 -> '26'; None for a blank."""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    s = re.sub(r"\D", "", str(v if v is not None else ""))
    return str(int(s)) if s else None


def slug(t):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (t or "").lower())).strip("-")


def circuit_of(code):
    """The layer's circuit code -> (the circuit's label as the ballot database writes it, the subdistrict or None):
    '08N' -> ('8-North', None); '2.1' -> ('2', '1'); '11W.2' -> ('11-West', '2'); '04' -> ('4', None)."""
    m = re.fullmatch(r"0*(\d{1,2})([NSEW]?)(?:\.(\d))?", clean(code))
    if not m:
        raise GeoError(f"    circuit court layer: the code {code!r} does not fit the layout this builder was checked against; stopping")
    label = m.group(1) + (f"-{SIDE[m.group(2)]}" if m.group(2) else "")
    return label, m.group(3)


def jname(v):
    """'AR-JD6' -> '6th Judicial Circuit'; 'AR-JD11-West' -> '11th Judicial Circuit, West'."""
    m = re.fullmatch(rf"{STATE}-JD(\d+)(?:-(North|South|East|West))?", v)
    return f"{G.ordinal(m.group(1))} Judicial Circuit" + (f", {m.group(2)}" if m.group(2) else "")


# ---------------------------------------------------------------- sources

def fetch(key, refresh, say):
    n, fields, oid, page, _name = LAYERS[key]
    return W.fetch_full(AGIO + str(n), fields, os.path.join(CACHE, FILE_OF[key] + "_geometry_4326.json.gz"), page, oid, refresh, say)


def about(key, refresh):
    """What the GIS Office's record of a layer says of it (its description and its credit line), kept in a small cache.
    The lines do not depend on this record."""
    path = os.path.join(CACHE, f"about_{FILE_OF[key]}.json")
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    out = {}
    try:
        net.patient_lookups()
        j = json.loads(net.get(AGIO + str(LAYERS[key][0]) + "?f=json", accept="application/json"))
        strip = lambda t: re.sub(r"\s+", " ", re.sub(r"&nbsp;|&amp;", " ", re.sub(r"(?s)<[^>]+>", " ", t or ""))).strip() or None      # noqa: E731
        ms = (j.get("editingInfo") or {}).get("dataLastEditDate") or (j.get("editingInfo") or {}).get("lastEditDate")
        out = {"name": j.get("name"), "description": strip(j.get("description")), "credits": strip(j.get("copyrightText")),
               "current_to": dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if ms else None,
               "fetched": dt.date.today().isoformat()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    except Exception:  # noqa: BLE001
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
    return out


def place_names():
    """{place code: the Census Bureau's 2020 name ("Alexander city", "Alicia town")} from its place list."""
    if not os.path.exists(PLACE_LIST):
        os.makedirs(CACHE, exist_ok=True)
        net.download(PLACE_LIST_URL, os.path.join(CACHE, "st05_ar_place2020.txt"), 3650, say=lambda *_a: None)
    path = PLACE_LIST if os.path.exists(PLACE_LIST) else os.path.join(CACHE, "st05_ar_place2020.txt")
    out = {}
    for line in open(path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
        f = line.split("|")
        if len(f) >= 5 and f[1] == FIPS:
            out[f[2]] = f[4].strip()
    return out


# ---------------------------------------------------------------- the ballot database

def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ar-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, office, jurisdiction, jurisdiction_id, district, county_ids "
                                         "FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def check_ids(info, shape_ids, judicial_counties):
    """Every Arkansas race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape). A race without a shape is listed with the reason. A court contest's counties must
    lie inside its district (else the circuit table is wrong, and the build stops). Justices of the peace and constables
    are county offices to the page builder (the county is drawn); whether the map also has each one's own district is
    counted apart."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "no_shape": [], "note": "not checked in this build"}
    Sh = shape_ids
    by_layer, missing, matched = collections.Counter(), collections.OrderedDict(), 0
    jp_own, jp_not = [], []
    for rid, level, kind, _office, jur, jid, district, county_ids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        cids = re.findall(r"\d{5}", str(county_ids or ""))
        hit, why = None, None
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "district_court" or (level == "court" and jid in Sh.get("judicial", {})):
            hit = ("judicial", jid)
            own = set(judicial_counties.get(jid, ()))
            if jid in Sh.get("judicial", {}) and cids and not set(cids) <= own:
                raise GeoError(f"    {rid}: the list prints it in counties {cids} outside {jid} ({sorted(own)}); the circuit lines are wrong; stopping")
        elif kind in ("county_commissioner", "county_council"):
            hit = ("county", jid) if not d else ("com", f"{jid}|{d}")
        elif level == "county":
            hit = ("county", jid)
            if kind == "justice_of_the_peace":
                (jp_own if f"{jid}|{d}" in Sh.get("com", {}) else jp_not).append(rid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d and hit[1] not in Sh.get("ward", {}):
                why = ("the city's wards are not on the GIS Office's ward layer; the city is drawn" if jid in Sh.get("mcd", {})
                       else "the GIS Office's municipal boundaries do not have this city")
        elif level == "school":
            hit = ("school", jid)
        if hit and hit[1] in Sh.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            continue
        key = (level, kind, jur, jid, district if level in ("city", "township") else None)
        e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": key[4],
                                     "races": 0, "why": why or "no shape carries this id"})
        e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "no_shape": list(missing.values()),
            "justice_of_the_peace": {"races": len(jp_own) + len(jp_not), "own_district_on_the_com_layer": len(jp_own), "not_on_it": jp_not,
                                     "note": "the page builder draws a justice of the peace contest as its county (race_shape files a county "
                                             "office under the county); the com layer holds each one's own district, with the id "
                                             "<county>|<district> the contest carries"}}


# ---------------------------------------------------------------- polling places

POLL_WAITING = {"why": "Arkansas publishes no list of polling places a script may read: the Secretary of State's VoterView "
                       "answers for one voter at a time, and each county's election commission names its own polling sites "
                       "(many counties use vote centers, open to every voter of the county). The county election commission "
                       "is the authority."}


def polling_places(put, say):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER, "status": "waiting", **POLL_WAITING}
    put("polling_places.json", doc)
    say("      polling places: waiting. No statewide list is published where a script may read it (VoterView answers one voter at a time; "
        "each county election commission names its own sites, often vote centers)")
    return {"file": "polling_places.json", "status": "waiting"}


# ---------------------------------------------------------------- helpers for the build

def knit(polys):
    """nd_geo.knit at Arkansas's latitude."""
    keep = N.KX
    N.KX = G.M_PER_UNIT * math.cos(math.radians(34.8))
    try:
        return N.knit(polys, eps_m=KNIT_M)
    finally:
        N.KX = keep


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    path = os.path.join(CACHE, f"ar_geo_overlay_{name}.json")
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


def rows_fabric(rows, keyf):
    """A layer's rows that share an id merged into one shape, then made a fabric: (keys, polygons, arcs, sides, rings, odd)."""
    merged = N.merge_rows([(a, r) for a, r in rows if keyf(a)], keyf)
    return I.fabric(merged, keyf)


def thick_list(got, keys, whole=WHOLE_SHARE):
    """From one precinct's overlay row: ([(id, share)] of the thick pieces, largest first, the id holding at least
    `whole` of it or None, the share outside them all)."""
    rows_ = sorted(((keys[d], s, t) for d, s, t in got), key=lambda g: (-g[1], G.natkey(g[0])))
    thick = [(k, s) for k, s, t in rows_ if t]
    one = thick[0][0] if len(thick) == 1 and thick[0][1] >= whole else None
    return thick, one, max(0.0, 1.0 - sum(s for _k, s, _t in rows_))


def cut(pre, polys, lines, say):
    """mi_geo.cut_precincts with Arkansas's kinds."""
    keep = M.CUT_KINDS
    M.CUT_KINDS = CUT_KINDS
    try:
        return M.cut_precincts(pre, polys, lines, say)
    finally:
        M.CUT_KINDS = keep


# ---------------------------------------------------------------- the build

def build(out=BUILDING, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Arkansas ballot map: precinct, district, city, ward and school district lines (Arkansas GIS Office, for the Secretary of State "
        "and the county election commissions; Census Bureau for the area check)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    docs = {k: fetch(k, refresh, say) for k in LAYERS}
    abouts = {k: about(k, refresh) for k in LAYERS}
    gz = lambda k: path(FILE_OF[k] + "_geometry_4326.json.gz")      # noqa: E731
    census_place = place_names()

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")

    # ---- precincts: one shape per county and name (a precinct drawn in several pieces is one precinct)
    county_short = {}
    prow = []
    for a, rings in docs["precincts"]["rows"]:
        cf, cn, pn = clean(a["county_fips"]), clean(a["county_name"]), clean(a["precinct"])
        if not (re.fullmatch(r"\d{3}", cf) and cn and pn):
            raise GeoError(f"    precinct layer: the row {a.get('objectid')!r} ({cf!r}, {cn!r}, {pn!r}) does not fit the layout this builder was checked against; stopping")
        c = FIPS + cf
        if county_short.setdefault(c, cn) != cn:
            raise GeoError(f"    precinct layer: county {c} is given two names ({county_short[c]!r}, {cn!r}); stopping")
        prow.append(({"county": c, "name": pn, "id": f"{c}-{slug(pn)}"}, rings))
    if len(county_short) != 75:
        raise GeoError(f"    precinct layer: {len(county_short)} counties, not 75; stopping")
    by_id = collections.defaultdict(set)
    for a, _r in prow:
        by_id[a["id"]].add(a["name"])
    clash = {k: v for k, v in by_id.items() if len(v) > 1}
    if clash:
        raise GeoError(f"    precinct layer: two precinct names make one id: {list(clash.items())[:3]}; stopping")
    pieces_of = collections.Counter(a["id"] for a, _r in prow)
    merged = sorted(N.merge_rows(prow, lambda a: a["id"]), key=lambda x: G.natkey(x[0]["id"]))
    pre, polys = [], []
    for a, rings in merged:
        pre.append({"id": a["id"], "county": a["county"], "name": a["name"], "rows": pieces_of[a["id"]]})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    if any(not rings for rings in polys):
        raise GeoError(f"    precinct layer: {[p['id'] for p, r in zip(pre, polys) if not r][:3]} have no ring; stopping")
    whole_precincts = len(pre)
    say(f"      {len(docs['precincts']['rows']):,} precinct rows in 75 counties make {whole_precincts:,} precincts "
        f"({sum(1 for n in pieces_of.values() if n > 1)} drawn in more than one row)")
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in county_short.items()}

    # ---- the districts' own lines
    hkeys, hpolys, harcs, hsides, _hr, hodd = rows_fabric(docs["house"]["rows"], lambda a: num(a["ndistrict"]))
    skeys, spolys, sarcs, ssides, _sr, sodd = rows_fabric(docs["senate"]["rows"], lambda a: num(a["ndistrict"]))
    ckeys, cpolys, carcs, csides, _cr, codd = rows_fabric(docs["cd"]["rows"], lambda a: num(a["district"]))
    for k, keys, want in (("House", hkeys, 100), ("Senate", skeys, 35), ("congressional", ckeys, 4)):
        if sorted(keys, key=int) != [str(n) for n in range(1, want + 1)]:
            raise GeoError(f"    {k} districts: {len(keys)} shapes, not districts 1 to {want}; stopping")
    for a, _r in docs["jp"]["rows"]:
        if not (re.fullmatch(r"\d{3}", clean(a["fips"])) and num(a["district"]) and FIPS + clean(a["fips"]) in county_short):
            raise GeoError(f"    justice of the peace districts: the row {a.get('objectid')!r} does not fit the layout this builder was checked against; stopping")
    jpkey = lambda a: f"{FIPS}{clean(a['fips'])}|{num(a['district'])}"      # noqa: E731
    jkeys, jpolys, jarcs, jsides, _jr, jodd = rows_fabric(docs["jp"]["rows"], jpkey)
    if {k.split("|")[0] for k in jkeys} != set(county_short):
        raise GeoError("    justice of the peace districts: the layer does not cover the 75 counties; stopping")
    jp_per = collections.Counter(k.split("|")[0] for k in jkeys)
    say(f"      100 House districts ({len(harcs):,} lines), 35 Senate ({len(sarcs):,}), 4 congressional ({len(carcs):,}), {len(jkeys)} justice of the peace "
        f"districts ({min(jp_per.values())} to {max(jp_per.values())} a county)"
        + "".join(f"; odd in {n}: {dict(o)}" for n, o in (("House", hodd), ("Senate", sodd), ("Congress", codd), ("JP", jodd)) if o))

    # ---- which districts each whole precinct reaches (the one holding most of it; a second one with 3 percent or more, thick enough)
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.SCHOOL_THICK, KNIT_M, M.FACE_MIN_W, M.FACE_MIN_M2, 1]).encode()).hexdigest()   # noqa: E731
    raw_rings = I.rings_xy(polys)
    o_house = overlay_cached("house", raw_rings, I.rings_xy(hpolys), stamp(gz("precincts"), gz("house")), refresh, say)
    o_senate = overlay_cached("senate", raw_rings, I.rings_xy(spolys), stamp(gz("precincts"), gz("senate")), refresh, say)
    o_cd = overlay_cached("congressional", raw_rings, I.rings_xy(cpolys), stamp(gz("precincts"), gz("cd")), refresh, say)
    o_jp = overlay_cached("justice_of_the_peace", raw_rings, I.rings_xy(jpolys), stamp(gz("precincts"), gz("jp")), refresh, say)
    none_of = collections.Counter()
    for n, p in enumerate(pre):
        p["house"] = S.most(p, o_house[n], hkeys, "house")
        p["senate"] = S.most(p, o_senate[n], skeys, "senate")
        p["cd"] = S.most(p, o_cd[n], ckeys, "cd")
        p["com"] = S.most(p, [g for g in o_jp[n] if jkeys[g[0]].split("|")[0] == p["county"]], jkeys, "com")
        for k in CUT_KINDS:
            none_of[k] += p[k] is None
    if any(none_of.values()):
        bad = [p["id"] for p in pre if any(p[k] is None for k in CUT_KINDS)]
        raise GeoError(f"    precincts that touch no district: {dict(none_of)} ({bad[:5]}); stopping")
    splits = {k: sum(1 for p in pre if k in (p.get("split") or {})) for k in CUT_KINDS}
    say(f"      districts by precinct: a district line runs through {sum(1 for p in pre if p.get('split')):,} of the {len(pre):,} precincts "
        f"({splits['house']} House, {splits['senate']} Senate, {splits['cd']} congressional, {splits['com']} justice of the peace)")

    # ---- one line between two neighbours; split precincts cut along the district lines
    lines = {"house": (hkeys, hpolys), "senate": (skeys, spolys), "cd": (ckeys, cpolys), "com": (jkeys, jpolys)}
    moved, added = knit(polys)
    for rings in polys:      # a ring the knitting folded flat is no ring
        rings[:] = [r for r in rings if r and len(r) >= 3]
    gone = [(p, round(sum(abs(I.ring_area_m2(r)) for r in raw), 1)) for p, rings, raw in zip(pre, polys, raw_rings) if not rings]
    if any(a > TINY_M2 for _p, a in gone):
        raise GeoError(f"    precincts with no ring left once their lines were set together: {[(p['id'], a) for p, a in gone][:5]}; stopping")
    tiny = [{"id": p["id"], "name": p["name"], "county": p["county"], "square_metres": a} for p, a in gone]
    if tiny:
        keep = [n for n, rings in enumerate(polys) if rings]
        pre, polys = [pre[n] for n in keep], [polys[n] for n in keep]
        say(f"      left out: {len(tiny)} precincts drawn only as slivers of under {TINY_M2:.0f} square metres "
            f"({', '.join(t['name'] + ' of ' + cname[t['county']] for t in tiny)})")
    pre, polys, left_whole = cut(pre, polys, lines, say)
    slivers, gave = W.settle_overlaps(pre, polys)
    if any(not rings for rings in polys):
        raise GeoError("    a precinct has no ring left after its lines were set together; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {whole_precincts:,} precincts in {len(pre):,} shapes, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them "
        f"({sum(len(a) for a in arcs):,} points; {sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); drawings of one line within "
        f"{KNIT_M:.0f} m made one ({moved:,} corners moved, {added:,} added); {lone:,} lines have a precinct on one side only, {len(seam):,} of them with "
        f"another precinct just across; {slivers} sliver rings left out, {sum(n for _w, n in gave)} points given up where two precincts ran the same way "
        "along a line" + (f"; odd: {dict(odd)}" if odd else ""))
    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    cut_stamp = hashlib.sha256(json.dumps([p["id"] for p in pre] + [sum(len(r) for r in rings) for rings in pre_rings]).encode()).hexdigest()

    # ---- circuit court districts: whole counties, read from the lines; subdistricts named on each precinct
    crow = docs["circuit"]["rows"]
    circ_key = lambda a: f"{STATE}-JD{circuit_of(a['circuit_court'])[0]}"      # noqa: E731
    sub_key = lambda a: (f"{STATE}-JD{circuit_of(a['circuit_court'])[0]}-S{circuit_of(a['circuit_court'])[1]}"      # noqa: E731
                         if circuit_of(a["circuit_court"])[1] else None)
    jdkeys, jdpolys, *_r1 = rows_fabric(crow, circ_key)
    if len(jdkeys) != COUNTS["judicial"]:
        raise GeoError(f"    circuit court layer: {len(jdkeys)} circuits, not {COUNTS['judicial']}; stopping")
    ov_jd = overlay_cached("circuit", pre_rings, I.rings_xy(jdpolys), stamp(gz("precincts"), gz("circuit")) + cut_stamp, refresh, say)
    vote = collections.defaultdict(collections.Counter)
    for p, got in zip(pre, ov_jd):
        best = max(got, key=lambda g: g[1]) if got else None
        vote[p["county"]][jdkeys[best[0]] if best else None] += 1
    jd_of, jd_counties = {}, collections.defaultdict(list)
    for c, cnt in sorted(vote.items()):
        top, n = cnt.most_common(1)[0]
        if top is None or n < COUNTY_AGREE * sum(cnt.values()):
            raise GeoError(f"    circuit court layer: {cname[c]} is not in one circuit ({dict(cnt)}); stopping")
        jd_of[c] = top
        jd_counties[top].append(c)
    if set(jd_counties) != set(jdkeys):
        raise GeoError(f"    circuit court layer: circuits with no county: {sorted(set(jdkeys) - set(jd_counties))}; stopping")
    for p in pre:
        p["judicial"] = jd_of[p["county"]]
    subkeys, subpolys, *_r2 = rows_fabric(crow, sub_key)
    ov_sub = overlay_cached("circuit_subdistricts", pre_rings, I.rings_xy(subpolys), stamp(gz("precincts"), gz("circuit")) + cut_stamp, refresh, say)
    sub_split = 0
    for p, got in zip(pre, ov_sub):
        thick, _one, _out = thick_list(got, subkeys)
        best = thick[0] if thick and thick[0][1] >= HALF and thick[0][0].startswith(p["judicial"] + "-S") else None
        p["sub"] = best[0] if best else None
        p["sub_pct"] = round(100 * best[1], 1) if best and best[1] < WHOLE_SHARE else None
        sub_split += bool(best and best[1] < WHOLE_SHARE)
    say(f"      circuits: {len(jdkeys)}, every county in one ({', '.join(f'{k[3:]}: {len(v)}' for k, v in sorted(jd_counties.items(), key=lambda x: G.natkey(x[0])))}); "
        f"subdistricts {', '.join(subkeys)}: {sum(1 for p in pre if p['sub']):,} precincts named, {sub_split} of them split")

    # ---- cities and towns, and wards (the GIS Office's), laid over the precincts
    for a, _r in docs["cities"]["rows"]:
        if not re.fullmatch(r"\d{5}", clean(a["city_fips"])):
            raise GeoError(f"    municipal boundary: the row {a.get('objectid')!r} has no five-digit place code; stopping")
    pkeyf = lambda a: f"{STATE}-M-{clean(a['city_fips'])}"      # noqa: E731
    places = sorted(N.merge_rows(docs["cities"]["rows"], pkeyf), key=lambda x: pkeyf(x[0]))
    pkeys = [pkeyf(a) for a, _r in places]
    pname, ptype = {}, {}
    for k, (a, _r) in zip(pkeys, places):
        census = census_place.get(k[5:])
        pname[k] = names.get(("mcd", k)) or census or f"{clean(a['city_name'])} {'town' if 'town' in clean(a['classification']).lower() else 'city'}"
        ptype[k] = "town" if (census or pname[k]).endswith(" town") else "city"
    place_polys = [[k for k in (G.clean_ring(r) for r in rings) if k] for _a, rings in places]
    ov_pl = overlay_cached("places", pre_rings, I.rings_xy(place_polys), stamp(gz("precincts"), gz("cities")) + cut_stamp, refresh, say)
    several = whole = 0
    for p, got in zip(pre, ov_pl):
        thick, one, _out = thick_list(got, pkeys)
        p["mcd"] = one
        p["mcd_all"] = [k for k, _s in thick] if thick and one is None else None
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in thick] if p["mcd_all"] else None
        whole += one is not None
        several += len(thick) > 1
    say(f"      cities and towns: {len(places)} (the GIS Office's municipal boundaries); {whole:,} precinct shapes lie wholly in one, "
        f"{sum(1 for p in pre if p['mcd_all']):,} partly in one or more, {several:,} reach more than one")

    odd_wards = []

    def wkeyf(a):
        # "Ward 3" (and the few the layer letters: Malvern's "Ward 1A", Rison's "Ward A"), kept as the layer writes them
        m = re.fullmatch(r"Ward 0*(\d{1,2}[A-Z]?|[A-Z])", clean(a["ward"]), re.I) or re.fullmatch(r"W0*(\d{1,2})", clean(a["ward_code"]), re.I)
        if not m or not re.fullmatch(r"\d{5}", clean(a["city_fips"])):
            odd_wards.append(f"{clean(a['city_name'])}: {clean(a['ward'])!r}")
            return None
        return f"{STATE}-M-{clean(a['city_fips'])}|Ward {m.group(1).upper()}"
    wrows = docs["wards"]["rows"]
    wkeys, wpolys, warcs, wsides, _wr, wodd = rows_fabric(wrows, wkeyf)
    odd_wards = sorted(set(odd_wards))
    ov_w = overlay_cached("wards", pre_rings, I.rings_xy(wpolys), stamp(gz("precincts"), gz("wards")) + cut_stamp, refresh, say)
    wsplit = 0
    for p, got in zip(pre, ov_w):
        thick, _one, _out = thick_list(got, wkeys)
        p["ward_ids"] = [k for k, _s in thick]
        p["ward_pct"] = [round(100 * s, 1) for _k, s in thick] if len(thick) > 1 or (thick and thick[0][1] < WHOLE_SHARE) else None
        wsplit += len(thick) > 1
    wcity = {f"{STATE}-M-{clean(a['city_fips'])}": clean(a["city_name"]) for a, _r in wrows}
    wname = {k: f"{pname.get(k.split('|')[0]) or wcity.get(k.split('|')[0]) or k.split('|')[0]}, {k.split('|')[1]}" for k in wkeys}
    ward_not_place = sorted({k.split("|")[0] for k in wkeys} - set(pkeys))
    say(f"      wards: {len(wkeys)} wards of {len({k.split('|')[0] for k in wkeys})} cities and towns; {sum(1 for p in pre if p['ward_ids']):,} precinct shapes "
        f"lie in one or more, {wsplit:,} in more than one" + (f"; rows with no ward number: {odd_wards[:6]}" if odd_wards else "")
        + (f"; cities not among the municipal boundaries: {ward_not_place}" if ward_not_place else "") + (f"; odd: {dict(wodd)}" if wodd else ""))

    # ---- townships (a precinct names the one holding at least half of it)
    tkeyf = lambda a: (f"{FIPS}{clean(a['countyfips'])}|{clean(a['name'])}" if re.fullmatch(r"\d{3}", clean(a["countyfips"])) and clean(a["name"]) else None)      # noqa: E731
    tkeys, tpolys, *_r3 = rows_fabric(docs["townships"]["rows"], tkeyf)
    tname = {k: (f"Township {k.split('|', 1)[1]}" if re.fullmatch(r"[\d\s-]+", k.split("|", 1)[1]) else f"{k.split('|', 1)[1]} Township") for k in tkeys}
    ov_t = overlay_cached("townships", pre_rings, I.rings_xy(tpolys), stamp(gz("precincts"), gz("townships")) + cut_stamp, refresh, say)
    for p, got in zip(pre, ov_t):
        thick, _one, _out = thick_list([g for g in got if tkeys[g[0]].split("|")[0] == p["county"]], tkeys)
        best = thick[0] if thick and thick[0][1] >= HALF else None
        p["township"] = best[0] if best else None
        p["township_pct"] = round(100 * best[1], 1) if best and best[1] < WHOLE_SHARE else None
    t_counties = {k.split("|")[0] for k in tkeys}
    say(f"      townships: {len(tkeys)} in {len(t_counties)} counties (the GIS Office's layer); {sum(1 for p in pre if p['township']):,} precinct shapes "
        "lie at least half in one")

    # ---- school districts
    srows = docs["school"]["rows"]
    for a, _r in srows:
        if not re.fullmatch(r"\d{7}", clean(a["lea"])) or not clean(a["name"]):
            raise GeoError(f"    school districts: the row {a.get('objectid')!r} has no seven-digit LEA code or no name; stopping")
    for lea, (sid, nm) in SCHOOL_IN_DB.items():
        found = {clean(a["name"]) for a, _r in srows if clean(a["lea"]) == lea}
        if found != {nm}:
            raise GeoError(f"    school districts: LEA {lea} is named {sorted(found)}, not {nm!r}; check SCHOOL_IN_DB; stopping")
    skeyf = lambda a: SCHOOL_IN_DB[clean(a["lea"])][0] if clean(a["lea"]) in SCHOOL_IN_DB else f"{STATE}-S-{clean(a['lea'])}"      # noqa: E731
    sid_name, sid_lea = {}, {}
    for a, _r in srows:
        k = skeyf(a)
        nm = clean(a["name"])
        sid_name[k] = names.get(("school", k)) or (nm if re.search(r"school district", nm, re.I) else f"{nm} School District")
        sid_lea[k] = clean(a["lea"])
    schkeys, _schpolys, scharcs, schsides, _sr, schodd = rows_fabric(srows, skeyf)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(gz("precincts"), gz("school")) + cut_stamp + "s", refresh, say)
    split = none = edges = 0
    for p, got in zip(pre, o_sch):
        rows_ = [(schkeys[d], share, thick) for d, share, thick in got]
        keep = sorted(((k, s) for k, s, thick in rows_ if thick), key=lambda x: (-x[1], x[0]))
        if not keep and rows_:
            best = max(((k, s) for k, s, _t in rows_), key=lambda x: x[1])
            if best[1] >= 0.5:
                keep = [best]
        outside = max(0.0, 1.0 - sum(s for _k, s, _t in rows_))
        p["school"] = [k for k, _s in keep]
        p["school_pct"] = [round(100 * s, 1) for _k, s in keep] if len(keep) > 1 or (keep and outside >= 0.03) else None
        p["school_out"] = round(100 * outside, 1) if outside >= 0.03 else None
        p["school_edge"] = sorted({k for k, _s, _t in rows_} - set(p["school"]))
        split += len(keep) > 1
        none += not keep
        edges += bool(p["school_edge"]) and len(keep) < 2
    say(f"      school districts: {len(schkeys)} ({len(scharcs):,} lines); {split:,} precinct shapes are split between two or more, {none} lie in none, "
        f"{edges:,} others only brush a neighbouring district along a line" + (f"; odd: {dict(schodd)}" if schodd else ""))

    # ---- the area check: each county's precincts against the Census Bureau's county
    signed = lambda r: I.ring_area_m2(r) * (1 if G.area2(r) < 0 else -1)      # noqa: E731
    area_p = collections.Counter()
    for p, rings in zip(pre, pre_rings):
        for r in rings:
            area_p[p["county"]] += signed(r)
    area_c = collections.Counter()
    for r, rings in I.read_shapefile(COUNTY_ZIP, lambda r: r["STATEFP"] == FIPS):
        for ks in rings:
            area_c[FIPS + r["COUNTYFP"]] += signed([G.vxy(k) for k in ks])
    clist = sorted(area_c)
    if clist != sorted(county_short):
        raise GeoError("    area check: the precinct layer and the Census Bureau do not have the same 75 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws "
                       f"({', '.join(f'{100 * (area_p[c] / area_c[c] - 1):+.1f}%' for c in off[:5])}); stopping")
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's Arkansas (its 1:500,000 county file); the county furthest off is "
        f"{cname[worst]} ({worst_pct:+.2f}%)")

    vals = {"county": [p["county"] for p in pre], "com": [p["com"] for p in pre], "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre],
            "cd": [p["cd"] for p in pre], "judicial": [p["judicial"] for p in pre]}
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

    # ---- write (into a folder beside the target, moved into place only when everything is written)
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

    def other(arcs_, sides_, keys, tol):
        g, q, _l, _r = G.build_layer(arcs_, sides_, [keys], tol)
        return g, q

    PCT, HSE, SEN, CDS, JPD, CIR, MUN, WRD, SCH, TWP = (
        "ar-agio-election-precincts", "ar-agio-house-districts", "ar-agio-senate-districts", "ar-agio-congressional-districts",
        "ar-agio-justice-of-the-peace-districts", "ar-agio-circuit-court", "ar-agio-municipal-boundary", "ar-agio-municipal-wards",
        "ar-agio-public-school-districts", "ar-agio-township-political-division")
    layer("state", *own(None, G.TOL_WIDE, [[STATE] * len(pre)]), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, PCT)
    layer("county", *own("county", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, PCT)
    layer("cd", *other(carcs, csides, ckeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, CDS)
    layer("senate", *other(sarcs, ssides, skeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v}, SEN)
    layer("house", *other(harcs, hsides, hkeys, G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v}, HSE)
    layer("judicial", *own("judicial", G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": jname(v), "j": v, "d": v[5:], "counties": sorted(cname[c] for c in jd_counties[v])},
          f"{PCT}; which counties, from {CIR}")
    layer("com", *other(jarcs, jsides, jkeys, G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Justice of the Peace District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
          JPD)
    ckeys_, _cp, carcs_, csides_, _cr_, codd_ = K.fabric_keys([(k, rings) for k, rings in zip(pkeys, place_polys)])
    if codd_:
        say(f"      cities and towns as a layer: {dict(codd_)}")
    cg, cq, _l, _r = G.build_layer(carcs_, csides_, [ckeys_], TOL_MCD)
    layer("mcd", cg, cq, TOL_MCD, lambda v: {"id": v, "name": pname[v], "j": v, "d": None, "t": ptype[v]}, MUN, zoom=MCD_ZOOM)
    layer("ward", *other(warcs, wsides, wkeys, G.TOL_LOCAL), G.TOL_LOCAL, lambda v: {"id": v, "name": wname[v], "j": v.split("|")[0], "d": v.split("|")[1]}, WRD)
    sprops = lambda v: {"id": v, "name": sid_name[v], "j": v, "d": None, "lea": sid_lea[v]}      # noqa: E731
    layer("school", *other(scharcs, schsides, schkeys, G.TOL_LOCAL), G.TOL_LOCAL, sprops, SCH)
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
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "school": {}, "judicial": {}, "judicial_subdistrict": {}, "township": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": p["name"], "county": county, "precinct": p.get("precinct") or p["id"], "house": p["house"], "senate": p["senate"],
                  "cd": p["cd"], "com": p["com"], "judicial": p["judicial"], "school": p["school"]}
            used_names["com"][p["com"]] = f"Justice of the Peace District {p['com'].split('|')[1]}"
            used_names["judicial"][p["judicial"]] = jname(p["judicial"])
            if p.get("split"):
                pr["split"] = p["split"]
            if p["mcd"]:
                pr["mcd"] = p["mcd"]
                used_names["mcd"][p["mcd"]] = pname[p["mcd"]]
            if p["mcd_all"]:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
                for k in p["mcd_all"]:
                    used_names["mcd"][k] = pname[k]
            if p["ward_ids"]:
                pr["ward"] = p["ward_ids"]
                if p["ward_pct"]:
                    pr["ward_pct"] = p["ward_pct"]
                for w in p["ward_ids"]:
                    used_names["ward"][w] = w.split("|")[1]
            if p["sub"]:
                pr["judicial_subdistrict"] = p["sub"]
                used_names["judicial_subdistrict"][p["sub"]] = f"Subdistrict {p['sub'].split('-S')[-1]} of the {jname(p['judicial'])}"
                if p["sub_pct"]:
                    pr["judicial_subdistrict_pct"] = p["sub_pct"]
            if p["township"]:
                pr["township"] = p["township"]
                used_names["township"][p["township"]] = tname[p["township"]]
                if p["township_pct"]:
                    pr["township_pct"] = p["township_pct"]
            for k in ("school_pct", "school_out", "school_edge"):
                if p.get(k):
                    pr[k] = p[k]
            for k in p["school"] + p["school_edge"]:
                used_names["school"][k] = sid_name[k]
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
        cbox[county] = doc["bbox"]
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs)})

    polls = polling_places(put, say)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    check = check_ids(info, shape_ids, {j: list(cs) for j, cs in jd_counties.items()})
    check["split_precincts"] = [{"id": p["id"], "name": p["name"], "county": p["county"], **p["split"]} for p in pre if p.get("split")]
    check["split_precincts_left_whole"] = [{"id": i, "kinds": kinds, "why": why} for i, kinds, why in left_whole]
    check["sliver_precincts_left_out"] = tiny
    check["wards_without_a_number"] = odd_wards
    check["ward_cities_not_among_the_municipal_boundaries"] = ward_not_place
    check["not_drawn"] = [
        {"what": "townships as a layer", "why": f"constables are elected by township; the GIS Office's township layer has {len(tkeys)} townships in "
                 f"{len(t_counties)} of the 75 counties, so each precinct names the township holding at least half of it (township) where the layer has one"},
        {"what": "circuit court subdistricts as a layer", "why": "each precinct of a circuit with subdistricts names its subdistrict (judicial_subdistrict); "
                 "the circuit is drawn"},
        {"what": "school board zones", "why": "school boards are elected in March (Act 503 of 2025); November carries only runoffs, and the page "
                 "draws the whole district"},
        {"what": "fire, levee and water districts", "why": "no contest of these on the ballot database has lines the GIS Office publishes "
                 "under the contest's own district (the Beaver Water District's board is elected by its counties' voters)"}]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)

    def agio_source(sid, key, about_text):
        a = abouts.get(key) or {}
        d_ = docs[key]
        return {"id": sid, "agency": "Arkansas GIS Office" + (f" (credit: {a['credits']})" if a.get("credits") else ""),
                "title": f"{LAYERS[key][4]} (Boundaries feature service, layer {LAYERS[key][0]})", "about": about_text,
                "publisher_says": a.get("description"), "url": AGIO_HUB, "service": AGIO + str(LAYERS[key][0]),
                "current_to": a.get("current_to"), "fetched": d_.get("fetched"), "sha256": G.sha_file(gz(key)), "rows": len(d_["rows"])}

    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            agio_source(PCT, "precincts", "Every voting precinct's lines and name, as each county election commission assigns them, compiled for the "
                                          "Secretary of State. A precinct carries no district: its districts are worked out here from the lines below."),
            agio_source(HSE, "house", "State House districts (the plan in force since 2022)."),
            agio_source(SEN, "senate", "State Senate districts (the plan in force since 2022)."),
            agio_source(CDS, "cd", "Congressional districts (Act 1116 of 2021)."),
            agio_source(JPD, "jp", "Justice of the peace districts: each county's quorum court districts, redrawn after the 2020 census."),
            agio_source(CIR, "circuit", "Circuit court districts and their subdistricts; each county's circuit is read from these lines."),
            agio_source(MUN, "cities", "City and town limits, with each one's Census place code."),
            agio_source(WRD, "wards", "Council wards of cities and towns."),
            agio_source(SCH, "school", "Public school districts, with the Department of Education's LEA code."),
            agio_source(TWP, "townships", "Political townships (constables are elected by township)."),
            {"id": "ar-census-2020-place-names", "agency": "U.S. Census Bureau", "title": "2020 place names, Arkansas (st05_ar_place2020.txt)",
             "about": "The names of cities and towns where the ballot database has none of its own.", "url": PLACE_LIST_URL},
            {"id": "census-cb-2024-county-500k", "agency": "U.S. Census Bureau", "title": "Cartographic boundary file, counties, 1:500,000 (2024)",
             "about": "Used only to check that each county's precincts cover the county.", "url": "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip",
             "sha256": G.sha_file(COUNTY_ZIP)}],
        "notes": {
            "lines": f"Every precinct line is the Arkansas GIS Office's precinct layer's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of "
                     "0.00001 degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "The precinct layer is the voting precincts each county election commission assigns, compiled for the Secretary of State and "
                         "kept by the Arkansas GIS Office; counties send changes, so a precinct changed since the county last sent one is drawn as it was. "
                         "The county election commission is the authority on which precinct an address is in, and VoterView answers for one voter.",
            "districts": "Arkansas's precinct layer names no districts. Which House, Senate, congressional and justice of the peace district a precinct "
                         "lies in is worked out here by laying the GIS Office's district lines over it: a precinct one of those lines runs through "
                         "(3 percent or more of its area on the far side, in a part more than a hairline thick) is cut along the line into parts, "
                         "each named \"<precinct>, part <n>\" and lying in one district of each kind. A precinct that could not be cut keeps the district "
                         "holding most of it and lists the others under split. This is analysis of two official maps, not an official list.",
            "places": "Cities and towns are the GIS Office's municipal boundaries. A precinct lying wholly in one names it (mcd); one that reaches into "
                      "cities lists them (mcd_all, with each one's share of the precinct's area), and a precinct partly outside every city names no "
                      "place of its own: the mcd layer answers for a point.",
            "wards": "Council wards are the GIS Office's. A precinct lists the wards it reaches (ward, with ward_pct where it is split); the ward layer "
                     "answers for a point.",
            "judicial": "Circuit court districts are whole counties; each county's is read from the circuit court layer. Prosecuting attorneys are "
                        "elected by the same districts. In circuits with subdistricts, a precinct also names its subdistrict (judicial_subdistrict).",
            "com": "Arkansas's county board is the quorum court, whose justices of the peace are elected by district: the com layer holds those districts.",
            "school": "School district lines are the GIS Office's. Which districts a precinct lies in is analysis, not an official list: a district counts "
                      f"when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share of "
                      "the precinct's area (land and water, not voters). School boards are elected in March; November carries only runoffs.",
            "unopposed": "An unopposed candidate (other than for mayor and circuit clerk) is elected without being named on the ballot, so many county and "
                         "township offices up in 2026 have no contest here.",
            "authority": "For which precinct an address votes in, and where, the county election commission and the Secretary of State's VoterView "
                         "are the authority.",
            "precinct_ids": "A precinct's id is the county's five-digit code and the precinct's name as the county gives it, in small letters with "
                            "hyphens (05119-precinct-056); a part of a cut precinct adds .1, .2 and so on.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of its rings, a "
                     "negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct or part of a precinct. arcMask[i] has bit k set when line "
                            "i is an outline of arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a "
                            "precinct in another county's file, or one just across a hairline gap; -2: outside Arkansas); names gives the names of the "
                            "places the file's precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees from "
                     "the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {
                "name": "the precinct's name as the county gives it (Precinct 056; Hickory Grove), with \", part <n>\" for a part of a cut precinct",
                "county": "county id", "precinct": "the whole precinct's id (the same for every part of a cut precinct)",
                "mcd": "the city or town the precinct lies wholly in (absent where it lies partly outside every one)",
                "mcd_all": "list: every city or town the precinct reaches, largest share first",
                "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                "ward": "list: the council ward the precinct lies in; where it reaches several, every one, largest share first",
                "ward_pct": "list, with ward, where the precinct is not wholly in one ward: each ward's share of its area, in percent",
                "com": "justice of the peace district (the county's quorum court)",
                "house": "House district", "senate": "Senate district", "cd": "congressional district",
                "judicial": "circuit court district (circuit judges and the prosecuting attorney)",
                "judicial_subdistrict": "circuit court subdistrict (holding at least half of the precinct; in circuits that have them)",
                "judicial_subdistrict_pct": "the subdistrict's share of the precinct's area, in percent, where it is not wholly inside",
                "township": "township (holding at least half of the precinct; where the GIS Office's layer has the county's townships)",
                "township_pct": "the township's share of the precinct's area, in percent, where it is not wholly inside",
                "split": "only where a district line runs through the precinct and it could not be cut: for house, senate, cd or com, each district's share in percent",
                "school": "list: the school districts the precinct lies in, largest share first",
                "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "AR (j is 05)", "county": "the county's five-digit code (05119)",
                    "com": "<county>|<justice of the peace district> (05119|1)",
                    "house": "the district (35)", "senate": "the district (12)", "cd": "the district (2); properties.race is the race for Congress",
                    "judicial": "AR-JD and the circuit as the ballot database writes it (AR-JD6, AR-JD11-West)",
                    "judicial_subdistrict": "<circuit>-S<n> (AR-JD6-S1: subdistrict 6.1)",
                    "mcd": "AR-M- and the Census Bureau's place code (AR-M-41000); properties.t says city or town",
                    "ward": "<city>|Ward <n> (AR-M-41000|Ward 1)",
                    "school": "AR-S- and the Department of Education's LEA code (AR-S-6001000), or the ballot database's own id for a district it names "
                              "(AR-S-143-elkins-school-district-10); properties.lea is the code",
                    "township": "<county>|<township> (05119|Big Rock)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {},
        "polling_places": polls,
        "counts": {"precincts": whole_precincts - len(tiny), "shapes": len(pre), "counties": len(counties),
                   "precincts_cut": len({p["precinct"] for p in pre if p.get("parts", 1) > 1}),
                   "parts_of_cut_precincts": sum(1 for p in pre if p.get("parts", 1) > 1), "split_precincts_left_whole": len(left_whole),
                   "split_between_school_districts": split, "in_more_than_one_city": several, "rings_too_small_for_the_grid": dropped_rings,
                   "lines_with_a_precinct_on_one_side": lone, "with_a_precinct_across": len(seam), "sliver_rings_left_out": slivers,
                   "corners_moved_to_make_one_line": moved, "corners_added_to_make_one_line": added,
                   "area_against_census_counties_percent": {"state": round(state_pct, 3), "furthest_county": worst, "its_difference": round(worst_pct, 2)}},
        "check": check,
    }
    put("index.json", index)
    manifest = {"v": G.VERSION, "built": today, "files": dict(sorted(files.items()))}
    G.write_json(os.path.join(out, "manifest.json"), manifest)
    total = sum(f["bytes"] for f in files.values()) + os.path.getsize(os.path.join(out, "manifest.json"))
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(out, final)
    say(f"      {len(counties)} county files ({sum(c['bytes'] for c in counties) / 1e6:.1f} MB), {len(layers)} layers "
        f"({sum(l['bytes'] for l in layers) / 1e6:.1f} MB), {len(schkeys)} school district files ({school_bytes / 1e6:.1f} MB), "
        f"index {files['index.json']['bytes'] / 1e3:.0f} KB; {total / 1e6:.1f} MB in all, in {final}")
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Arkansas races have a shape"
        + (f"; {sum(e['races'] for e in check['no_shape'])} races in {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Arkansas ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

# name, longitude, latitude, what the precinct there must say, and the place the mcd layer must give the point (None:
# outside every city). The county, House, Senate and congressional district and the city are the Census Bureau's
# geocoder's answer for those coordinates (benchmark and vintage Current: its 2026 state legislative districts and 120th
# Congress districts, asked 2026-10-03), owing nothing to the files tested here; the precinct's id and justice of the
# peace district are what the GIS Office's own services answer for the point.
TEST_POINTS = [
    ("the State Capitol, Little Rock", -92.2890, 34.7466, {"county": "05119", "house": "74", "senate": "14", "cd": "2", "precinct": "05119-precinct-098", "com": "05119|6", "judicial": "AR-JD6"}, "AR-M-41000"),
    ("Fayetteville, the square", -94.1597, 36.0626, {"county": "05143", "house": "21", "senate": "30", "cd": "3", "precinct": "05143-fay-36", "com": "05143|12", "judicial": "AR-JD4"}, "AR-M-23290"),
    ("Fort Smith, downtown", -94.4226, 35.3859, {"county": "05131", "house": "49", "senate": "27", "cd": "3", "precinct": "05131-11-f2-17", "com": "05131|11", "judicial": "AR-JD12"}, "AR-M-24550"),
    ("Jonesboro, Craighead County courthouse", -90.7043, 35.8424, {"county": "05031", "house": "32", "senate": "20", "cd": "1", "precinct": "05031-26", "com": "05031|5", "judicial": "AR-JD2"}, "AR-M-35710"),
    ("Jacksonville, Pulaski County", -92.1102, 34.8665, {"county": "05119", "house": "66", "senate": "12", "cd": "2", "precinct": "05119-precinct-044", "com": "05119|11", "judicial": "AR-JD6"}, "AR-M-34750"),
    ("Pine Bluff, downtown", -92.0034, 34.2284, {"county": "05069", "house": "65", "senate": "8", "cd": "4", "precinct": "05069-0105", "com": "05069|1", "judicial": "AR-JD11-West"}, "AR-M-55310"),
    ("Bentonville square", -94.2088, 36.3726, {"county": "05007", "house": "10", "senate": "34", "cd": "3", "precinct": "05007-106", "com": "05007|8", "judicial": "AR-JD19-West"}, "AR-M-05320"),
    ("Texarkana, Arkansas side", -94.0400, 33.4300, {"county": "05091", "house": "100", "senate": "4", "cd": "4", "precinct": "05091-sandflat", "com": "05091|2", "judicial": "AR-JD8-South"}, "AR-M-68810"),
    ("Hot Springs, Central Avenue", -93.0551, 34.5130, {"county": "05051", "house": "84", "senate": "6", "cd": "4", "precinct": "05051-011", "com": "05051|1", "judicial": "AR-JD18-East"}, "AR-M-33400"),
    ("Conway, Faulkner County", -92.4421, 35.0887, {"county": "05045", "house": "55", "senate": "17", "cd": "2", "precinct": "05045-02", "com": "05045|7", "judicial": "AR-JD20"}, "AR-M-15190"),
    ("El Dorado, Union County", -92.6663, 33.2076, {"county": "05139", "house": "97", "senate": "2", "cd": "4", "precinct": "05139-ward-2", "com": "05139|4", "judicial": "AR-JD13"}, "AR-M-21070"),
    ("a field in rural Newton County", -93.20, 35.95, {"county": "05101", "house": "27", "senate": "28", "cd": "4", "precinct": "05101-jackson", "com": "05101|1", "judicial": "AR-JD14"}, None),
    ("a field in rural Desha County", -91.30, 33.85, {"county": "05041", "house": "62", "senate": "8", "cd": "1", "precinct": "05041-18-redfork", "com": "05041|5", "judicial": "AR-JD10"}, None),
    ("Elkins, Washington County", -94.0080, 36.0010, {"county": "05143", "house": "25", "senate": "29", "cd": "3", "precinct": "05143-elkins-1", "com": "05143|15", "judicial": "AR-JD4"}, "AR-M-21190"),
    ("Mountain Home, Baxter County", -92.3852, 36.3354, {"county": "05005", "house": "3", "senate": "23", "cd": "1", "precinct": "05005-05-4", "com": "05005|5", "judicial": "AR-JD14"}, "AR-M-47390"),
]
# spots on county lines (a point the two counties share in the Census Bureau's 1:500,000 county file)
LINE_POINTS = [("the Pulaski-Saline county line", -92.44329, 34.67204, ("05119", "05125")),
               ("the Washington-Benton county line", -94.01795, 36.21660, ("05143", "05007")),
               ("the Craighead-Greene county line", -90.51878, 35.96541, ("05031", "05055"))]
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
    check(total == index["counts"]["shapes"] == len(ids), "the county files do not hold as many precinct shapes as the index says, each with its own id")
    shapes_seen, layer_ids = 0, {}
    for L in index["layers"]:
        gs = files.topo(L["file"])[0]["objects"][L["kind"]]["geometries"]
        shapes_seen += len(gs)
        layer_ids[L["kind"]] = {g["id"] for g in gs}
        empty = [g["id"] for g in gs if g["type"] not in ("Polygon", "MultiPolygon")]
        check(len(gs) == L["shapes"] and not empty and len({g["id"] for g in gs}) == len(gs), f"layer {L['kind']}: {len(empty)} shapes without an outline ({', '.join(empty[:4])}), or ids repeated")
    empty = [i for i in index["school"]["ids"] if files.topo(f"school/{i}.json")[0]["objects"]["school"]["geometries"][0]["type"] not in ("Polygon", "MultiPolygon")]
    check(not empty, f"{len(empty)} school district files have no outline ({', '.join(empty[:4])})")
    check(len(index["counties"]) == 75, "there are not 75 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(all(len(layer_ids.get(k, ())) == n for k, n in COUNTS.items()), f"the layers do not have {', '.join(f'{n} {k}' for k, n in COUNTS.items())}")
    check(len(layer_ids.get("com", ())) >= 75 * 9 and {i.split("|")[0] for i in layer_ids.get("com", ())} == {c["id"] for c in index["counties"]},
          "the justice of the peace layer does not cover every county (nine districts at least in each)")
    check(layer_ids.get("ward", set()) >= {f"{STATE}-M-41000|Ward {n}" for n in range(1, 8)}, "the ward layer does not have Little Rock's seven wards")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precinct shapes, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree, asked = collections.defaultdict(list), collections.Counter()
    school, place, ward = collections.Counter(), collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com"}
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
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("mcd_all", "mcd"), ("school", "school"), ("ward", "ward")]:
                v = pr.get(prop)
                for one in (v if isinstance(v, list) else [v] if v else []):
                    no_shape[kind] += one not in layer_ids.get(kind, ())
            sid = G.school_at(files, g, lon, lat)
            school["in a district the precinct lies in" if sid in pr["school"] else "in a district the precinct only brushes" if sid else
                   "in none, in a precinct partly outside every district" if pr.get("school_out") else "in none"] += 1
            shape, _edge = G.shape_at(files, "mcd", lon, lat)
            listed = [pr["mcd"]] if pr.get("mcd") else []
            listed += pr.get("mcd_all") or []
            place["the precinct's own place, or one it lists" if shape and shape["id"] in listed else
                  "outside every city, in a precinct that names none" if shape is None and not pr.get("mcd") else
                  "a place the precinct does not name" if shape else "no place, in a precinct that names one"] += 1
            wshape, _e = G.shape_at(files, "ward", lon, lat)
            ward["a ward the precinct lists" if wshape and wshape["id"] in (pr.get("ward") or []) else
                 "in no ward, in a precinct listing none or partly outside" if wshape is None and (not pr.get("ward") or pr.get("ward_pct")) else
                 "a ward the precinct does not list" if wshape else "no ward, in a precinct wholly in one"] += 1
            for prop, kind in layer_for.items():
                if kind not in layer_ids or (i % 3 and kind != "com") or prop in (pr.get("split") or {}):
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
    check(not sum(no_shape.values()), f"precincts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["a place the precinct does not name"] + place["no place, in a precinct that names one"] <= 0.01 * tested, f"the place at a precinct's own point: {dict(place)}")
    check(ward["a ward the precinct does not list"] + ward["no ward, in a precinct wholly in one"] <= 0.01 * tested, f"the ward at a precinct's own point: {dict(ward)}")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precinct shapes found again from a point inside them; every id a precinct carries is a shape; "
        f"layers agree at {agree:,} of {sum(asked.values()):,} points ({skipped} too near a line to ask" + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items()))
        + "); school district at each precinct's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1]))
        + "; city at each precinct's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1]))
        + "; ward at each precinct's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(ward.items(), key=lambda x: -x[1])))

    # 3. known points
    for name, lon, lat, want, mcd in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: (found["geometry"]["id"] if k == "id" else pr.get(k)) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        ok &= check((shape is None and mcd is None) or (shape is not None and shape["id"] == mcd), f"{name}: the mcd layer gives {shape and shape['id']}, not {mcd}")
        for prop, kind in layer_for.items():
            if kind in layer_ids and pr.get(prop) is not None:
                shape2, _edge = G.shape_at(files, kind, lon, lat)
                ok &= check(shape2 is not None and shape2["id"] == pr.get(prop), f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {pr.get(prop)}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, House {pr['house']}, "
            f"Senate {pr['senate']}, CD {pr['cd']}, {pr['judicial']}, JP {pr['com'].split('|')[1]}" + (f", {', '.join(pr['ward'])}" if pr.get("ward") else "")
            + (f", {pr['judicial_subdistrict']}" if pr.get("judicial_subdistrict") else "") + (f", {pr['township']}" if pr.get("township") else "")
            + f"; {found['edge']:.0f} m from the precinct's line")
    check(len(TEST_POINTS) >= 10, "fewer than ten known points were tested")

    # 4. county lines: a spot on one county's own drawing of a county line, given to one of the two counties with the other at hand
    rel = {c["id"]: c["file"] for c in index["counties"]}
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
    check(len(LINE_POINTS) >= 2, "fewer than two county lines were tested")

    # 5. polling places say what they are
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Arkansas's ballot map -> ballot_geo/ar/")
    ap.add_argument("--out", default=None, help="build and test in this folder and leave it there (a trial run)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask every source again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    a = ap.parse_args(argv)
    if a.selftest:
        if not selftest(os.path.abspath(a.out or OUT)):
            raise SystemExit(1)
        return
    where = os.path.abspath(a.out or BUILDING)
    build(out=where, db=os.path.abspath(a.db), refresh=a.refresh)
    if not selftest(where):
        raise SystemExit(f"    the self-test failed; the files stay in {where} and ballot_geo/ar/ is unchanged")
    if a.out is None:
        K.put_in_place(where, OUT)


if __name__ == "__main__":
    main()
