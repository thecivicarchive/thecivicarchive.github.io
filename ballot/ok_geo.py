"""
ballot/ok_geo.py - the geography behind Oklahoma's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, and ballot/wi_geo.py,
ballot/ia_geo.py, ballot/nd_geo.py and ballot/ky_geo.py for the few things those added, and changes nothing in any of
them), so the same page and the same reader (ballot/mn_geo_reader.js) read them all.

    python ballot/ok_geo.py                 builds ballot_geo/_building_ok/, runs the self-test on it, and only when the
                                            self-test passes puts it in place as ballot_geo/ok/ (the page builder draws a
                                            map for any state whose folder exists)
    python ballot/ok_geo.py --selftest      runs the self-test on ballot_geo/ok/ as it stands
    python ballot/ok_geo.py --refresh       asks every source again even when the cached copies are fresh
    python ballot/ok_geo.py --out DIR       builds and tests somewhere else, and leaves it there (a trial run)
    python ballot/ok_geo.py --edw DIR       looks for John's saved Election Data Warehouse precinct file in another folder

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ok_local/geo/)
-------------------------------------------------------------------------------------------------------------------------
The Oklahoma State Election Board's own page "District and Precinct Maps" (oklahoma.gov/elections) says the Board
contracts with the University of Oklahoma's Center for Spatial Analysis for its mapping, and that the GIS files are in
the Center's data warehouse (csagis-uok.opendata.arcgis.com). Every layer below is the Center's, read through its public
feature services (services.arcgis.com/3xOwF6p0r7IHIjfn), in longitude and latitude at full detail.
  - Precincts: "Voter Precincts 2020" (State_Wide_2020_Precincts): 1,984 precincts, each with its six-digit precinct
    number as the Board writes it (the county's number in the alphabet, 01 to 77, and four digits), its county, and its
    House, Senate, congressional and county commissioner district. The Center: "Boundaries are based on information
    provided by the County Election Boards", merged for all 77 counties "in cooperation with the Oklahoma State Election
    Board". Its description says last updated 2022-06-07; the service was last edited 2025-11-05. The population columns
    are never asked for. Neighbouring counties' precincts share their lines almost everywhere; drawings of one line within
    a metre of each other are made one line (nd_geo.knit).
  - House, Senate, congressional and county commissioner districts as lines (House_Districts_2020, st_sen2020,
    Congressional_Districts_2020, Commissioner_Districts_2020), to check the precincts' own district numbers. The lines
    drawn are the precincts'.
  - City and town council wards: "Municipal Wards" (Municipal_Wards), compiled from the Tax Commission and the county
    election boards: each ward with its city's Census code and whether the city votes "By Ward" or "At Large". Only the
    wards of cities that vote by ward are drawn: in an at-large city every voter votes in every ward's contest.
  - Fire protection districts: "Title 19 Fire Protection Districts" (Fire_Protection_Districts), 35 districts as the
    Center has them (19 O.S. 901.1 and on). Not a layer: each precinct names the district holding at least half of it.
  - The electoral divisions of District Court Judicial Districts 7 (Oklahoma County) and 14 (Tulsa County):
    "Judicial Districts" (Judicial_Districts), nine divisions. Not a layer: each precinct there names its division.
  - School districts: "School Districts" (School_District_Full_Color), drawn county part by county part with the
    State Department of Education's district code; the parts of one district are put together here. School boards are
    elected in February and April (26 O.S. 13A-103), not on November's ballot; the lines are drawn for reference.
  - Cities and towns: the Census Bureau's TIGER/Line 2025 places of Oklahoma (tl_2025_40_place.zip), the active
    incorporated ones (the ids of the ballot database's cities are the Bureau's place codes).
  - Judicial districts (district judges): 20 O.S. 92.2 to 92.27, whole counties, as the Oklahoma State Courts Network's
    index of Title 20 titles each section (read 2026-10-03; oscn.net now shows scripts a verification page, so the
    table is typed into JUDICIAL below and checked here: every county in exactly one district, and every district
    judge contest's counties inside its district).
  - Polling places: the State Election Board's "Precinct/District Information" file in its OK Election Data Warehouse
    (precinct number, its districts, and its polling place's name and address). Basic access is free but needs an
    account the Board grants on a request form, so it is John's step. See POLLING PLACES below.

What is built (ballot_geo/ok/): index.json, manifest.json, precincts/<county>.json (77), layers/<kind>.json (state, county,
cd, senate, house, judicial, com, mcd, ward, school), school/<id>.json, polling_places.json and reader.js, each as
ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "OK" (j = "40")
  county    "40001"                 sl_places county id; jurisdiction_id of county offices and associate district judges
  mcd       "OK-M-04450"            OK-M- and the Census Bureau's place code
  ward      "OK-M-04450|Ward 1"     <city>|<district as the council race words it>: "Ward 1"; Tulsa's "District 1"
  com       "40001|1"               <county>|<commissioner district>
  house     "57"   senate "20"   cd "1" (properties.race is 2026-OK-H01)
  judicial  "OK-JD14"               the jurisdiction_id of district judge races (20 O.S. 92.2 to 92.27)
  school    "OK-S-68C050"           OK-S- and the Department of Education's code (county number, type letter, number)
  fire      "OK-X-051-bridge-creek-fire" (a precinct property): the jurisdiction_id the ballot database gives a fire
            district with a contest; the others "OK-X-FPD-<the Tax Commission's district number>"
  judicial_division "OK-JD14-ED3" (a precinct property): electoral division 3 of judicial district 14

POLLING PLACES
--------------
No statewide polling place list is published where a script may read it: the Board's OK Voter Portal answers for one
voter at a time. The Board's OK Election Data Warehouse "Basic Access" (free; an account granted on the Board's "Request
to Access OK Election Data Warehouse" form, valid a year) carries the statewide list of precincts with their polling
places, refreshed nightly. When John has access, he downloads only the Precinct/District Information file (CSV) and
saves it into states_cache/ok_local/geo/edw/ (any name ending .csv). This builder then reads only the columns
PrecinctCode, CongressionalDistrict, StateSenateDistrict, StateHouseDistrict, CountyCommissioner, PollSite,
PollSiteAddress, PollSiteAddress2, PollSiteCity and PollSiteZip (a polling place is a public building), refuses any file
whose headings name a voter (the warehouse's absentee and deleted-voter files do), checks every precinct's districts
against the map, and places each polling place with the Census Bureau's geocoder. Its output is marked "unchecked" until
a person has compared a dozen precincts with the file and set POLL_LAYOUT_CHECKED to True.
"""

import argparse
import collections
import csv
import datetime as dt
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
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import nd_geo as N  # noqa: E402
from ballot import ky_geo as K  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "OK", "40", "Oklahoma"
GEO_ROOT = os.path.join(HERE, "ballot_geo")
OUT = os.path.join(GEO_ROOT, "ok")
BUILDING = os.path.join(GEO_ROOT, "_building_ok")
CACHE = os.path.join(HERE, "states_cache", "ok_local", "geo")
EDW_DIR = os.path.join(CACHE, "edw")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://oklahoma.gov/elections/ovp.html"      # the Board's own "Find Your Polling Place" link (the OK Voter Portal)
SEB_MAPS = "https://oklahoma.gov/elections/candidates/district-and-precinct-maps.html"
EDW_PAGE = "https://oklahoma.gov/elections/candidates/voter-registration-list.html"
EDW_README = "https://oklahoma.gov/content/dam/ok/en/elections/ok-election-data-warehouse/readme-basic.pdf"

CSA_HUB = "https://csagis-uok.opendata.arcgis.com/"
CSA = "https://services.arcgis.com/3xOwF6p0r7IHIjfn/arcgis/rest/services/"
HUB_SEARCH = CSA_HUB + "api/search/v1/collections/all/items?limit=10&q="
ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/{}?f=json"
LAYERS = {      # key: (service, fields, object id field, page size, the Center's own title)
    "precincts": ("State_Wide_2020_Precincts", "OBJECTID_1,PCT_CEB,Precinct,COUNTY,COUNTY_NAM,CO_FIPS,St_house,St_senate,Comm,Uscong",
                  "OBJECTID_1", 250, "Voter Precincts 2020"),
    "house": ("House_Districts_2020", "OBJECTID,DISTRICT,COUNTYFP", "OBJECTID", 100, "House Districts 2020"),
    "senate": ("st_sen2020", "OBJECTID,DISTRICT,COUNTYFP", "OBJECTID", 100, "Senate Districts 2020"),
    "cd": ("Congressional_Districts_2020", "OBJECTID,DISTRICT,COUNTYFP", "OBJECTID", 100, "Congressional Districts 2020"),
    "com": ("Commissioner_Districts_2020", "OBJECTID,DISTRICT,NAME,COUNTYFP", "OBJECTID", 100, "Commissioner Districts 2020"),
    "wards": ("Municipal_Wards", "OBJECTID,CO_FIPS,MUNI_NAME,MUNI_CODE,WARD_CODE,VOTING_TYPE,EDIT_DATE", "OBJECTID", 100, "Municipal Wards"),
    "fire": ("Fire_Protection_Districts", "FID,FPD_ADV,FPD_NAME,CO_FIPS,EDIT_DATE", "FID", 100, "Title 19 Fire Protection Districts"),
    "divisions": ("Judicial_Districts", "OBJECTID,DISTRICT,NAME", "OBJECTID", 100, "Judicial Districts"),
    "school": ("School_District_Full_Color", "OBJECTID_1,CO_FIPS,COUNTY,SD_NAME,JOINT_CNTY,SD_CODE,EB_SD_CODE,EDIT_DATE", "OBJECTID_1", 250, "School Districts"),
}
FILE_OF = {"precincts": "csa_voter_precincts_2020", "house": "csa_house_districts_2020", "senate": "csa_senate_districts_2020",
           "cd": "csa_congressional_districts_2020", "com": "csa_commissioner_districts_2020", "wards": "csa_municipal_wards",
           "fire": "csa_fire_protection_districts", "divisions": "csa_judicial_election_divisions", "school": "csa_school_districts"}
TIGER = "https://www2.census.gov/geo/tiger/TIGER2025/"
PLACE_URL = TIGER + "PLACE/tl_2025_40_place.zip"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")      # the kit's own copy, for the area check
OSCN_INDEX = "https://www.oscn.net/applications/oscn/index.asp?ftdb=STOKST20&level=1"

# District Court Judicial Districts, 20 O.S. 92.2 to 92.27, as the section titles in the Oklahoma State Courts Network's
# index of Title 20 name their counties (District No. 7 and No. 14 from sections 92.8e and 92.15d). Read 2026-10-03.
JUDICIAL = {
    1: ("92.2", ["Cimarron", "Texas", "Beaver", "Harper"]),
    2: ("92.3", ["Washita", "Ellis", "Roger Mills", "Custer", "Beckham"]),
    3: ("92.4", ["Kiowa", "Jackson", "Tillman", "Harmon", "Greer"]),
    4: ("92.5", ["Dewey", "Blaine", "Kingfisher", "Garfield", "Major", "Woodward", "Woods", "Alfalfa", "Grant"]),
    5: ("92.6", ["Comanche", "Stephens", "Cotton", "Jefferson"]),
    6: ("92.7", ["Grady", "Caddo"]),
    7: ("92.8e", ["Oklahoma"]),
    8: ("92.9", ["Noble", "Kay"]),
    9: ("92.10", ["Logan", "Payne"]),
    10: ("92.11", ["Osage"]),
    11: ("92.12", ["Washington", "Nowata"]),
    12: ("92.13", ["Rogers", "Mayes", "Craig"]),
    13: ("92.14", ["Ottawa", "Delaware"]),
    14: ("92.15d", ["Tulsa", "Pawnee"]),
    15: ("92.16", ["Wagoner", "Cherokee", "Adair", "Muskogee", "Sequoyah"]),
    16: ("92.17", ["Haskell", "Le Flore", "Latimer"]),
    17: ("92.18", ["Pushmataha", "McCurtain", "Choctaw"]),
    18: ("92.19", ["McIntosh", "Pittsburg"]),
    19: ("92.20", ["Bryan"]),
    20: ("92.21", ["Love", "Carter", "Murray", "Johnston", "Marshall"]),
    21: ("92.22", ["Garvin", "McClain", "Cleveland"]),
    22: ("92.23", ["Seminole", "Hughes", "Pontotoc"]),
    23: ("92.24", ["Lincoln", "Pottawatomie"]),
    24: ("92.25", ["Okfuskee", "Okmulgee", "Creek"]),
    25: ("92.26", ["Coal", "Atoka"]),
    26: ("92.27", ["Canadian"]),
}
DIVISION_LAW = {"7": "20 O.S. 92.8e", "14": "20 O.S. 92.15d"}
DIVISION_COUNTY = {"Oklahoma": ("7", "40109"), "Tulsa": ("14", "40143")}

# The fire protection districts the ballot database has a contest for, by the Tax Commission's district number on the
# Center's layer: the database's own id, and the names on both sides (checked when the build runs).
FIRE_IN_DB = {"030": ("OK-X-051-bridge-creek-fire", "Bridge Creek Rural FPD"),
              "260": ("OK-X-081-southwest-lin-co-fire-1", "SW Lincoln Co FPD"),
              "280": ("OK-X-131-verdigris-fire", "Verdigris FPD")}

ARC_KINDS = ["county", "com", "house", "senate", "cd", "judicial"]      # not mcd or ward: precincts do not follow city or ward lines
TOL_MCD, MCD_ZOOM = I.TOL_MCD, I.MCD_ZOOM
WHOLE_SHARE = 0.98                # a precinct with this share of its area in one city (or ward) is that city's
HALF = 0.5                        # a precinct names the fire district or judicial division holding at least this share of it
TAKE_LINES = 0.99                 # where a precinct's own district number differs from the Center's district lines and those lines put this
                                  # share of it in one district, the lines' district is used (the Census Bureau's 2026 legislative districts
                                  # agreed with the lines at every such precinct when this was written) and the precinct is listed in check
KNIT_M = 1.0                      # metres: two precincts' drawings of one line this close together are made the same line
AREA_SLACK = 0.03
POLL_LAYOUT_CHECKED = False       # True only when a person has compared a dozen precincts of polling_places.json with the Board's file
COUNTS = {"county": 77, "house": 101, "senate": 48, "cd": 5, "judicial": 26}


def clean(v):
    return K.clean(v)


def letters(text):
    return re.sub(r"[^A-Z]", "", (text or "").upper())


def num(v):
    """'086' -> '86'; None for a blank."""
    s = re.sub(r"\D", "", str(v or ""))
    return str(int(s)) if s else None


def slug(t):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (t or "").lower())).strip("-")


# ---------------------------------------------------------------- sources

def fetch(key, refresh, say):
    service, fields, oid, page, _title = LAYERS[key]
    return W.fetch_full(CSA + service + "/FeatureServer/0", fields, os.path.join(CACHE, FILE_OF[key] + "_geometry_4326.json.gz"),
                        page, oid, refresh, say)


def about(key, refresh):
    """What the Center says of one of its layers (title, summary, description, credits, use), from its hub's record of
    the item, kept in a small cache. The lines do not depend on this record."""
    path = os.path.join(CACHE, f"about_{FILE_OF[key]}.json")
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    service, _f, _o, _p, title = LAYERS[key]
    out = {}
    try:
        net.patient_lookups()
        j = json.loads(net.get(HUB_SEARCH + quote(title), accept="application/json"))
        hit = next((f for f in j.get("features", []) if (f.get("properties") or {}).get("title") == title
                    and service in str((f.get("properties") or {}).get("url") or "")), None)
        if hit:
            it = json.loads(net.get(ITEM_URL.format(hit["id"]), accept="application/json"))
            strip = lambda t: re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", t or "")).strip() or None      # noqa: E731
            out = {"item": hit["id"], "page": f"{CSA_HUB}datasets/{hit['id']}", "title": strip(it.get("title")), "summary": strip(it.get("snippet")),
                   "description": strip(it.get("description")), "credits": strip(it.get("accessInformation")), "use": strip(it.get("licenseInfo")),
                   "modified": dt.datetime.fromtimestamp(it["modified"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if it.get("modified") else None,
                   "fetched": dt.date.today().isoformat()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    except Exception:  # noqa: BLE001
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
    return out


# ---------------------------------------------------------------- the ballot database

def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ok-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, office, jurisdiction, jurisdiction_id, district, county_ids "
                                         "FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def check_ids(info, shape_ids, said, judicial_counties):
    """Every Oklahoma race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape), then for a race no layer draws, against the districts the precincts name
    (race_said), and last, a court of one county by its county (the page lists it for readers in that county). A race
    without any is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "by_precinct_word": {}, "no_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, by_said, by_county, missing, matched = collections.Counter(), collections.Counter(), collections.Counter(), collections.OrderedDict(), 0
    narrower = []
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
        elif kind == "district_court" or (level == "court" and jid in S.get("judicial", {})):
            hit = ("judicial", jid)
            if jid in S.get("judicial", {}):
                own = set(judicial_counties.get(jid, ()))
                if cids and not set(cids) <= own:
                    raise GeoError(f"    {rid}: the list prints it in counties {cids} outside {jid} ({sorted(own)}); the judicial table is wrong; stopping")
                if cids and set(cids) != own:
                    narrower.append({"race": rid, "printed_in": cids, "district_counties": sorted(own)})
        elif kind in ("county_commissioner", "county_council"):
            hit = ("county", jid) if not d else ("com", f"{jid}|{d}")
        elif level == "county":
            hit = ("county", jid)
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d and hit[1] not in S.get("ward", {}):
                why = ("the city's wards are not on the Center's ward layer, or the city votes for every ward at large; the city is drawn, and "
                       "the page lists its contests for everyone in it" if jid in S.get("mcd", {}) else "the Census Bureau's 2025 places do not have this city")
        elif level == "school":
            hit = ("school", jid)
        if hit and hit[1] in S.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            continue
        q = next((k for k, v in sorted(said.items()) if jid and jid in v), None)
        if q:
            matched += 1
            by_said[q] += 1
            continue
        if level == "court" and len(cids) == 1 and cids[0] in S.get("county", {}):
            matched += 1
            by_county[kind] += 1
            continue
        key = (level, kind, jur, jid, district if level in ("city", "township") else None)
        e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": jur, "jurisdiction_id": jid, "district": key[4],
                                     "races": 0, "why": why or "no shape carries this id"})
        e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "by_precinct_word": dict(sorted(by_said.items())),
            "by_its_county": {k: f"{n} contests of one county's court (associate district judges, filed under the county): the page lists them for "
                                 "readers located in that county" for k, n in sorted(by_county.items())},
            "no_shape": list(missing.values()),
            "district_judge_contests_printed_in_part_of_their_district": narrower}


# ---------------------------------------------------------------- polling places (John's saved Election Data Warehouse file)

POLL_WAITING = {"why": "The Oklahoma State Election Board publishes its statewide list of precincts and polling places only in its OK "
                       "Election Data Warehouse, which needs an account. The OK Voter Portal answers for one voter at a time, and the "
                       "county election board is the authority."}
POLL_HEADS = {"precinct": "PrecinctCode", "cd": "CongressionalDistrict", "senate": "StateSenateDistrict", "house": "StateHouseDistrict",
              "com": "CountyCommissioner", "name": "PollSite", "address": "PollSiteAddress", "address2": "PollSiteAddress2",
              "city": "PollSiteCity", "zip": "PollSiteZip"}
POLL_REFUSE = ("lastname", "firstname", "voterid", "dateofbirth", "residence", "politicalaff", "mailing")      # a file naming voters is never read


def find_edw(folder):
    """The saved Precinct/District Information file: the newest .csv in the folder whose headings are the Board's
    precinct file's. None when there is none."""
    if not folder or not os.path.isdir(folder):
        return None
    best = None
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if not name.lower().endswith(".csv") or not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8-sig", errors="replace", newline="") as fh:
            head = next(csv.reader(fh), [])
        folded = [re.sub(r"[^a-z0-9]", "", h.lower()) for h in head]
        if any(w in h for h in folded for w in POLL_REFUSE):
            continue
        if {"precinctcode", "pollsite"} <= set(folded) and (best is None or os.path.getmtime(p) > os.path.getmtime(best)):
            best = p
    return best


def read_edw(path):
    """[{key: cell}] with only the columns in POLL_HEADS, found by their headings."""
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
        rd = csv.reader(fh)
        head = next(rd)
        folded = [re.sub(r"[^a-z0-9]", "", h.lower()) for h in head]
        if any(w in h for h in folded for w in POLL_REFUSE):
            raise GeoError(f"    {os.path.basename(path)} names voters; only the Precinct/District Information file is read; stopping")
        col = {k: folded.index(h.lower()) for k, h in POLL_HEADS.items() if h.lower() in folded}
        if set(col) != set(POLL_HEADS):
            raise GeoError(f"    {os.path.basename(path)}: headings missing ({sorted(set(POLL_HEADS) - set(col))}); the reader needs to be told the layout")
        out = []
        for r in rd:
            if not any(c.strip() for c in r):
                continue
            out.append({k: clean(r[i]) if i < len(r) else "" for k, i in col.items()})
    return out


def polling_places(pre, cname, cbox, put, say, folder):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    path = find_edw(folder)
    if path is None:
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say("      polling places: waiting. The State Election Board's precinct and polling place file is in its OK Election Data Warehouse, "
            "behind a free account granted on a request form (John's step); save the Precinct/District Information CSV into "
            f"{os.path.relpath(EDW_DIR, HERE)}\\ and build again")
        return {"file": "polling_places.json", "status": "waiting", "edw": None}
    rows = read_edw(path)
    by_id = {p["id"]: p for p in pre}
    places, key_of, precinct, unmatched, differ = [], {}, {}, set(), []
    for r in rows:
        code = re.sub(r"\D", "", r["precinct"]).zfill(6)
        p = by_id.get(code)
        if p is None:
            unmatched.add(code)
            continue
        for k in ("cd", "senate", "house", "com"):
            mine = p[k] if k != "com" else p["com_n"]
            if num(r[k]) and num(r[k]) != mine:
                differ.append({"id": code, "kind": k, "board": num(r[k]), "map": mine})
        if not r["name"]:
            continue
        street = " ".join(x for x in (r["address"], r["address2"]) if x)
        k = (r["name"].lower(), street.lower(), r["city"].lower())
        if k not in key_of:
            key_of[k] = len(places)
            places.append({"name": r["name"], "address": street, "city": r["city"].title() if r["city"].isupper() else r["city"], "zip": r["zip"][:5],
                           "lonlat": None, "precincts": [], "_county": p["county"]})
        n = key_of[k]
        if code not in places[n]["precincts"]:
            places[n]["precincts"].append(code)
        precinct[code] = n
    placed, far = place_points(places, cbox, say)
    for q in places:
        q.pop("_county", None)
    listed = {re.sub(r"\D", "", r["precinct"]).zfill(6) for r in rows}
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Oklahoma State Election Board", "title": "OK Election Data Warehouse, Precinct/District Information (saved by hand)",
                       "url": EDW_PAGE, "layout": EDW_README, "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"),
                       "sha256": G.sha_file(path)},
               places=places, precinct=dict(sorted(precinct.items())), no_place={},
               note="Each precinct on the Board's file has one polling place; precinct gives its number in places.")
    put("polling_places.json", doc)
    say(f"      polling places: {len(rows):,} rows, {len(places):,} places ({placed:,} placed by the Census Bureau's geocoder, {far} thrown out as outside "
        f"the county); {len(precinct):,} precincts with a place; {len(unmatched)} of the file's precincts are not on the map; "
        f"{sum(1 for p in pre if p['id'] not in listed)} of the map's are not on the file; districts differ at {len(differ)}")
    return {"file": "polling_places.json", "status": status, "edw": os.path.basename(path), "places": len(places),
            "with_coordinates": sum(1 for p in places if p["lonlat"]), "precincts_with_a_place": len(precinct),
            "on_the_file_not_on_the_map": sorted(unmatched), "on_the_map_not_on_the_file": sorted(p["id"] for p in pre if p["id"] not in listed),
            "districts_differ_from_the_map": differ[:200]}


def place_points(places, cbox, say):
    """ky_geo.place_points with Oklahoma's state code and its own cache."""
    cache_path = os.path.join(CACHE, "ok_geo_pollingplace_points.json")
    kept = {}
    if os.path.exists(cache_path):
        try:
            kept = json.load(open(cache_path, encoding="utf-8"))
        except (ValueError, OSError):
            kept = {}
    key = lambda p: f"{p['address']}|{p['city']}|{p['zip']}".lower()      # noqa: E731
    ask = [(str(n), p["address"], p["city"], p["zip"]) for n, p in enumerate(places) if p["address"] and key(p) not in kept]
    if ask:
        keep_state = K.STATE
        K.STATE = STATE
        try:
            got = K.census_geocode(ask, say)
            for rid, *_ in ask:
                kept[key(places[int(rid)])] = list(got[rid]) if rid in got else None
            with open(cache_path + ".part", "w", encoding="utf-8") as fh:
                json.dump(kept, fh, separators=(",", ":"))
            os.replace(cache_path + ".part", cache_path)
        except Exception as e:  # noqa: BLE001  the list is worth having without points on a map
            say(f"      polling places: the Census Bureau's geocoder could not be reached ({e}); places without coordinates stay off the map")
        finally:
            K.STATE = keep_state
    placed = far = 0
    for p in places:
        hit, b = kept.get(key(p)), cbox.get(p["_county"])
        if not hit or not b:
            continue
        if not (b[0] - 0.05 <= hit[0] <= b[2] + 0.05 and b[1] - 0.05 <= hit[1] <= b[3] + 0.05):
            far += 1
            continue
        p["lonlat"], p["from"] = [hit[0], hit[1]], "the Census Bureau's geocoder, from the street address"
        placed += 1
    return placed, far


# ---------------------------------------------------------------- helpers for the build

def knit(polys):
    """nd_geo.knit at Oklahoma's latitude."""
    keep = N.KX
    N.KX = G.M_PER_UNIT * math.cos(math.radians(35.5))
    try:
        return N.knit(polys, eps_m=KNIT_M)
    finally:
        N.KX = keep


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    path = os.path.join(CACHE, f"ok_geo_overlay_{name}.json")
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


# ---------------------------------------------------------------- the build

def build(out=BUILDING, db=DB, refresh=False, say=print, edw_dir=EDW_DIR):
    t0 = time.time()
    say("    Oklahoma ballot map: precinct, district, city, ward and school district lines (University of Oklahoma Center for Spatial Analysis "
        "for the State Election Board; Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    docs = {k: fetch(k, refresh, say) for k in LAYERS}
    abouts = {k: about(k, refresh) for k in LAYERS}
    net.download(PLACE_URL, path("tl_2025_40_place.zip"), 3650, say=say)
    edited = W.layer_edited(CSA + LAYERS["precincts"][0] + "/FeatureServer/0", path("ok_geo_about_precincts_edited.json"), refresh)
    gz = lambda k: path(FILE_OF[k] + "_geometry_4326.json.gz")      # noqa: E731

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")

    # ---- precincts
    rows = sorted(docs["precincts"]["rows"], key=lambda r: r[0]["PCT_CEB"])
    pre, polys, county_short, county_no = [], [], {}, {}
    for a, rings in rows:
        code, cf, cno = clean(a["PCT_CEB"]), clean(a["CO_FIPS"]), clean(a["COUNTY"])
        if not (re.fullmatch(r"\d{6}", code) and re.fullmatch(r"\d{3}", cf) and re.fullmatch(r"\d{2}", cno) and code[:2] == cno
                and int(cf) == 2 * int(cno) - 1 and clean(a["COUNTY_NAM"])):
            raise GeoError(f"    precinct layer: the row {code!r} does not fit the layout this builder was checked against; stopping")
        c = FIPS + cf
        if county_short.setdefault(c, clean(a["COUNTY_NAM"])) != clean(a["COUNTY_NAM"]):
            raise GeoError(f"    precinct layer: county {c} is given two names; stopping")
        county_no[c] = cno
        dist = {k: num(a[f]) for k, f in (("house", "St_house"), ("senate", "St_senate"), ("cd", "Uscong"), ("com_n", "Comm"))}
        if not all(dist.values()):
            raise GeoError(f"    precinct layer: precinct {code} has a blank district ({dist}); stopping")
        pre.append({"id": code, "county": c, "code": code, **dist})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    if len(county_short) != 77 or len({p["id"] for p in pre}) != len(pre):
        raise GeoError(f"    precinct layer: {len(county_short)} counties and {len(pre)} rows; 77 counties, one row a precinct, were expected; stopping")
    moved, added = knit(polys)
    slivers, gave = W.settle_overlaps(pre, polys)
    if any(not rings for rings in polys):
        raise GeoError("    a precinct has no ring left after its lines were set together; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precincts in 77 counties, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; "
        f"{sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); drawings of one line within {KNIT_M:.0f} m made one ({moved:,} corners moved, "
        f"{added:,} added); {lone:,} lines have a precinct on one side only, {len(seam):,} of them with another precinct just across; {slivers} sliver rings left out, "
        f"{sum(n for _w, n in gave)} points given up where two precincts ran the same way along a line" + (f"; odd: {dict(odd)}" if odd else ""))
    cname = {c: names.get(("county", c)) or f"{n.title()} County" for c, n in county_short.items()}
    cname = {c: re.sub(r"^Mcc", "McC", re.sub(r"^Mci", "McI", n)) for c, n in cname.items()}
    county_key = {letters(re.sub(r"\s+County$", "", n)): c for c, n in cname.items()}

    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *ps: hashlib.sha256(json.dumps([G.sha_file(p) for p in ps] + [G.TOL_PRECINCT, G.SCHOOL_THICK, KNIT_M, 1]).encode()).hexdigest()   # noqa: E731

    # ---- the Center's district lines laid over the precincts: a check of the precincts' own district numbers
    differs, leg_diff = collections.Counter(), []
    for k, want in (("house", 101), ("senate", 48), ("cd", 5)):
        keys, lpolys, *_rest = rows_fabric(docs[k]["rows"], lambda a: num(a["DISTRICT"]))
        if len(keys) != want:
            raise GeoError(f"    the Center's {k} districts: {len(keys)} shapes, not {want}; stopping")
        ov = overlay_cached(k, pre_rings, I.rings_xy(lpolys), stamp(gz("precincts"), gz(k)), refresh, say)
        for p, got in zip(pre, ov):
            got = sorted(got, key=lambda g: -g[1])
            best = keys[got[0][0]] if got else None
            if best != p[k] and (not got or got[0][1] >= 0.5):
                differs[k] += 1
                taken = bool(got) and got[0][1] >= TAKE_LINES
                if len(leg_diff) < 40:
                    leg_diff.append({"id": p["id"], "kind": k, "precinct_says": p[k], "district_layer": best, "share": round(100 * got[0][1], 1) if got else None,
                                     "used": "district_layer" if taken else "precinct"})
                if taken:
                    p[k] = best
    ckeys, cpolys, *_rest = rows_fabric(docs["com"]["rows"], lambda a: f"{FIPS}{clean(a['COUNTYFP'])}|{num(a['DISTRICT'])}")
    if len(ckeys) != 231:
        raise GeoError(f"    the Center's commissioner districts: {len(ckeys)} shapes, not 231 (three in each county); stopping")
    ov = overlay_cached("com", pre_rings, I.rings_xy(cpolys), stamp(gz("precincts"), gz("com")), refresh, say)
    for p, got in zip(pre, ov):
        got = sorted(got, key=lambda g: -g[1])
        best = ckeys[got[0][0]] if got else None
        p["com"] = f"{p['county']}|{p['com_n']}"
        if best != p["com"] and (not got or got[0][1] >= 0.5):
            differs["com"] += 1
            taken = bool(got) and got[0][1] >= TAKE_LINES
            if len(leg_diff) < 60:
                leg_diff.append({"id": p["id"], "kind": "com", "precinct_says": p["com"], "district_layer": best, "share": round(100 * got[0][1], 1) if got else None,
                                 "used": "district_layer" if taken else "precinct"})
            if taken:
                p["com"], p["com_n"] = best, best.split("|")[1]
    say(f"      House, Senate, congressional and commissioner districts: the precincts' own numbers agree with the Center's district lines laid over them at all but "
        f"{', '.join(f'{n} ({k})' for k, n in sorted(differs.items())) or 'none'} of {len(pre):,}")
    if any(n > 0.01 * len(pre) for n in differs.values()):
        raise GeoError("    the precincts' district numbers and the district lines disagree more than a stray precinct can explain; stopping")
    for k, want in (("house", 101), ("senate", 48), ("cd", 5)):
        if len({p[k] for p in pre}) != want:
            raise GeoError(f"    the precincts name {len({p[k] for p in pre})} {k} districts, not {want}; stopping")

    # ---- judicial districts (whole counties, 20 O.S. 92.2 to 92.27) and the electoral divisions in Oklahoma and Tulsa counties
    jd_of, jd_counties = {}, collections.defaultdict(list)
    for n, (_sec, cs) in JUDICIAL.items():
        for nm in cs:
            c = county_key.get(letters(nm))
            if c is None or c in jd_of:
                raise GeoError(f"    judicial districts: {nm!r} is not an Oklahoma county, or is in two districts; stopping")
            jd_of[c] = f"{STATE}-JD{n}"
            jd_counties[f"{STATE}-JD{n}"].append(c)
    if set(jd_of) != set(county_short):
        raise GeoError(f"    judicial districts: counties in none: {sorted(set(county_short) - set(jd_of))}; stopping")
    for p in pre:
        p["judicial"] = jd_of[p["county"]]
    dkeys, dpolys, *_rest = rows_fabric(docs["divisions"]["rows"], lambda a: (f"{STATE}-JD{DIVISION_COUNTY[clean(a['NAME'])][0]}-ED{num(a['DISTRICT'])}"
                                                                              if clean(a["NAME"]) in DIVISION_COUNTY else None))
    ov_d = overlay_cached("judicial_divisions", pre_rings, I.rings_xy(dpolys), stamp(gz("precincts"), gz("divisions")), refresh, say)
    div_split, div_none = 0, 0
    for p, got in zip(pre, ov_d):
        if p["county"] not in ("40109", "40143"):
            p["division"] = None
            continue
        thick, _one, _out = thick_list(got, dkeys)
        best = thick[0] if thick and thick[0][1] >= HALF else None
        p["division"] = best[0] if best and best[0].startswith(jd_of[p["county"]] + "-") else None
        p["division_pct"] = round(100 * best[1], 1) if best and best[1] < WHOLE_SHARE else None
        div_split += bool(best and best[1] < WHOLE_SHARE)
        div_none += p["division"] is None
    say(f"      judicial districts: 26 by statute; electoral divisions: {len(dkeys)} ({', '.join(dkeys)}); "
        f"{sum(1 for p in pre if p['division']):,} precincts of Oklahoma and Tulsa counties named, {div_split} of them split, {div_none} with none")

    # ---- cities and towns (the Census Bureau's 2025 places), and wards (the Center's), laid over the precincts
    places = sorted(I.read_shapefile(path("tl_2025_40_place.zip"), lambda r: r["STATEFP"] == FIPS and r["FUNCSTAT"] == "A" and r["CLASSFP"] == "C1"),
                    key=lambda x: x[0]["PLACEFP"])
    pkeys = [f"{STATE}-M-{r['PLACEFP']}" for r, _ in places]
    pname = {k: names.get(("mcd", k)) or r["NAMELSAD"] for k, (r, _) in zip(pkeys, places)}
    ptype = {k: "town" if r["NAMELSAD"].endswith(" town") else "city" for k, (r, _) in zip(pkeys, places)}
    ov_pl = overlay_cached("places", pre_rings, I.rings_xy([r for _a, r in places]), stamp(gz("precincts"), path("tl_2025_40_place.zip")), refresh, say)
    several = whole = 0
    for p, got in zip(pre, ov_pl):
        thick, one, _out = thick_list(got, pkeys)
        p["mcd"] = one
        p["mcd_all"] = [k for k, _s in thick] if thick and one is None else None
        p["mcd_pct"] = [round(100 * s, 1) for _k, s in thick] if p["mcd_all"] else None
        whole += one is not None
        several += len(thick) > 1
    say(f"      cities and towns: {len(places)} from the Census Bureau's 2025 places; {whole:,} precincts lie wholly in one, "
        f"{sum(1 for p in pre if p['mcd_all']):,} partly in one or more, {several:,} reach more than one")

    word_of = {}      # the council race's own word for a city's districts ("Ward", "District")
    for _rid, level, kind, _o, _jur, jid, district, _ci in info["races"]:
        m = re.match(r"^(\w+) \d+$", str(district or ""))
        if level == "city" and m:
            word_of[jid] = m.group(1)
    wrows = docs["wards"]["rows"]
    vote_type = collections.defaultdict(set)
    for a, _r in wrows:
        vote_type[f"{STATE}-M-{clean(a['MUNI_CODE']).zfill(5)}"].add(clean(a["VOTING_TYPE"]))
    mixed = sorted(k for k, v in vote_type.items() if len(v) > 1)
    if mixed:
        raise GeoError(f"    ward layer: cities whose wards are said to vote both ways: {mixed}; stopping")
    by_ward = {k for k, v in vote_type.items() if v == {"By Ward"}}
    at_large = sorted(k for k, v in vote_type.items() if v == {"At Large"})
    not_place = sorted(k for k in vote_type if k not in pname)
    wkeyf = lambda a: (f"{STATE}-M-{clean(a['MUNI_CODE']).zfill(5)}|{word_of.get(STATE + '-M-' + clean(a['MUNI_CODE']).zfill(5), 'Ward')} {num(a['WARD_CODE'])}"      # noqa: E731
                       if f"{STATE}-M-{clean(a['MUNI_CODE']).zfill(5)}" in by_ward and num(a["WARD_CODE"]) else None)
    wkeys, wpolys, warcs, wsides, wrings, wodd = rows_fabric(wrows, wkeyf)
    ov_w = overlay_cached("wards", pre_rings, I.rings_xy(wpolys), stamp(gz("precincts"), gz("wards")), refresh, say)
    wsplit = 0
    for p, got in zip(pre, ov_w):
        thick, _one, _out = thick_list(got, wkeys)
        p["ward_ids"] = [k for k, _s in thick]
        p["ward_pct"] = [round(100 * s, 1) for _k, s in thick] if len(thick) > 1 or (thick and thick[0][1] < WHOLE_SHARE) else None
        wsplit += len(thick) > 1
    wname = {}
    for a, _r in wrows:
        k = wkeyf(a)
        if k:
            wname[k] = f"{pname.get(k.split('|')[0]) or clean(a['MUNI_NAME'])}, {k.split('|')[1]}"
    say(f"      wards: {len(wkeys)} wards of {len(by_ward)} cities and towns that vote by ward (the Center's layer; {len(at_large)} more vote at large and are "
        f"not drawn); {sum(1 for p in pre if p['ward_ids']):,} precincts lie in one or more, {wsplit:,} in more than one"
        + (f"; cities not among the 2025 places: {', '.join(not_place)}" if not_place else "") + (f"; odd: {dict(wodd)}" if wodd else ""))

    # ---- fire protection districts
    def fire_key(a):
        adv = clean(a["FPD_ADV"])
        return FIRE_IN_DB[adv][0] if adv in FIRE_IN_DB else f"{STATE}-X-FPD-{adv}"
    fire_name = {}
    for a, _r in docs["fire"]["rows"]:
        adv = clean(a["FPD_ADV"])
        if adv in FIRE_IN_DB and clean(a["FPD_NAME"]) != FIRE_IN_DB[adv][1]:
            raise GeoError(f"    fire districts: district {adv} is now named {clean(a['FPD_NAME'])!r}, not {FIRE_IN_DB[adv][1]!r}; check FIRE_IN_DB; stopping")
        fire_name[fire_key(a)] = names.get(("special", fire_key(a))) or re.sub(r"\bFPD\b", "Fire Protection District", clean(a["FPD_NAME"]))
    fkeys, fpolys, *_rest = rows_fabric(docs["fire"]["rows"], fire_key)
    ov_f = overlay_cached("fire", pre_rings, I.rings_xy(fpolys), stamp(gz("precincts"), gz("fire")), refresh, say)
    for p, got in zip(pre, ov_f):
        thick, _one, _out = thick_list(got, fkeys)
        best = thick[0] if thick and thick[0][1] >= HALF else None
        p["fire"] = best[0] if best else None
        p["fire_pct"] = round(100 * best[1], 1) if best and best[1] < WHOLE_SHARE else None
        p["fire_edge"] = [k for k, _s in thick if not best or k != best[0]] or None
    say(f"      fire protection districts: {len(fkeys)} (the Center's layer); {sum(1 for p in pre if p['fire']):,} precincts lie at least half in one, "
        f"{sum(1 for p in pre if p['fire_edge']):,} reach into one they do not name")

    # ---- school districts (the Center's, county part by county part; one shape a district)
    srows = docs["school"]["rows"]
    sname_by = collections.defaultdict(collections.Counter)
    for a, _r in srows:
        nm = re.sub(r"\s*\d+$", "", clean(a["SD_NAME"]))
        sname_by[clean(a["SD_CODE"])][nm] += 2 if (clean(a["CO_FIPS"]) and int(clean(a["CO_FIPS"])) == 2 * int(clean(a["SD_CODE"])[:2]) - 1) else 1
    skeyf = lambda a: f"{STATE}-S-{clean(a['SD_CODE'])}" if re.fullmatch(r"\d{2}[A-Z]\d{3}", clean(a["SD_CODE"])) else None      # noqa: E731
    sid_name = {}
    for code, cnt in sname_by.items():
        nm = cnt.most_common(1)[0][0]
        sid_name[f"{STATE}-S-{code}"] = names.get(("school", f"{STATE}-S-{code}")) or f"{nm} school district ({code[:2]}-{code[2:]})"
    schkeys, schpolys, scharcs, schsides, _sr, schodd = rows_fabric(srows, skeyf)
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(gz("precincts"), gz("school")) + "s", refresh, say)
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
    say(f"      school districts: {len(schkeys)} ({len(scharcs):,} lines); {split:,} precincts are split between two or more, {none} lie in none, "
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
        raise GeoError("    area check: the precinct layer and the Census Bureau do not have the same 77 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws "
                       f"({', '.join(f'{100 * (area_p[c] / area_c[c] - 1):+.1f}%' for c in off[:5])}); stopping")
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's Oklahoma (its 1:500,000 county file); the county furthest off is "
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

    PCT, CENSUS, LAW, WRD, SCH = ("ok-csa-voter-precincts", "ok-census-tiger-2025-places", "ok-statutes-judicial-districts",
                                  "ok-csa-municipal-wards", "ok-csa-school-districts")
    layer("state", *own(None, G.TOL_WIDE, [[STATE] * len(pre)]), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, PCT)
    layer("county", *own("county", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, PCT)
    layer("cd", *own("cd", G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, f"{PCT}; which district, the precincts' own")
    layer("senate", *own("senate", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v},
          f"{PCT}; which district, the precincts' own")
    layer("house", *own("house", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v},
          f"{PCT}; which district, the precincts' own")
    layer("judicial", *own("judicial", G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{G.ordinal(v[5:])} Judicial District", "j": v, "d": v[5:], "counties": sorted(cname[c] for c in jd_counties[v])},
          f"{PCT}; which counties, from {LAW}")
    layer("com", *own("com", G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, Commissioner District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]},
          f"{PCT}; which district, the precincts' own")
    ckeys_, _cp, carcs, csides, _cr, codd = K.fabric_keys([(k, rings) for k, (_r0, rings) in zip(pkeys, places)])
    if codd:
        say(f"      cities and towns as a layer: {dict(codd)}")
    cg, cq, _l, _r = G.build_layer(carcs, csides, [ckeys_], TOL_MCD)
    layer("mcd", cg, cq, TOL_MCD, lambda v: {"id": v, "name": pname[v], "j": v, "d": None, "t": ptype[v]}, CENSUS, zoom=MCD_ZOOM)
    wg, wq, _l, _r = G.build_layer(warcs, wsides, [wkeys], G.TOL_LOCAL)
    layer("ward", wg, wq, G.TOL_LOCAL, lambda v: {"id": v, "name": wname[v], "j": v.split("|")[0], "d": v.split("|")[1]}, WRD)
    sprops = lambda v: {"id": v, "name": sid_name[v], "j": v, "d": None}      # noqa: E731
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
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "school": {}, "judicial": {}, "fire": {}, "judicial_division": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": f"Precinct {p['code']}", "county": county, "precinct": p["code"], "house": p["house"], "senate": p["senate"], "cd": p["cd"],
                  "com": p["com"], "judicial": p["judicial"], "school": p["school"]}
            used_names["com"][p["com"]] = f"Commissioner District {p['com_n']}"
            used_names["judicial"][p["judicial"]] = f"{G.ordinal(p['judicial'][5:])} Judicial District"
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
            if p["fire"]:
                pr["fire"] = p["fire"]
                used_names["fire"][p["fire"]] = fire_name[p["fire"]]
                if p["fire_pct"]:
                    pr["fire_pct"] = p["fire_pct"]
            if p["fire_edge"]:
                pr["fire_edge"] = p["fire_edge"]
                for k in p["fire_edge"]:
                    used_names["fire"][k] = fire_name[k]
            if p.get("division"):
                pr["judicial_division"] = p["division"]
                used_names["judicial_division"][p["division"]] = f"Electoral Division {p['division'].rsplit('ED', 1)[1]} of the {G.ordinal(p['judicial'][5:])} Judicial District"
                if p.get("division_pct"):
                    pr["judicial_division_pct"] = p["division_pct"]
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
        counties.append({"id": county, "fips": county, "name": cname[county], "bbox": doc["bbox"], "file": rel, "bytes": size, "precincts": len(idxs),
                         "board_number": county_no[county]})

    polls = polling_places(pre, cname, cbox, put, say, edw_dir)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    said = {"fire": {p["fire"] for p in pre if p["fire"]}, "judicial_division": {p["division"] for p in pre if p.get("division")}}
    check = check_ids(info, shape_ids, said, {j: list(cs) for j, cs in jd_counties.items()})
    check["districts_differ_from_the_district_lines"] = leg_diff
    check["fire_districts_with_a_contest"] = {v[0]: {"layer_name": v[1], "precincts_naming_it": sum(1 for p in pre if p["fire"] == v[0]),
                                                     "precincts_reaching_into_it": sum(1 for p in pre if v[0] in (p["fire_edge"] or []))}
                                              for v in FIRE_IN_DB.values()}
    check["ward_cities_not_among_the_places"] = not_place
    check["not_drawn"] = [
        {"what": "wards of cities and towns that elect every council seat at large", "why": f"{len(at_large)} cities and towns on the Center's ward layer vote "
                 "'At Large': every voter of the city votes in every ward's contest, so the page lists them for the whole city"},
        {"what": "fire protection districts as a layer", "why": "each precinct names the district holding at least half of it (fire); the "
                 "page puts a fire board contest on the ballot of a located reader by that word"},
        {"what": "which district judge offices are elected by an electoral division", "why": "the divisions of Districts 7 and 14 are named on "
                 "every precinct there (judicial_division), but no source read here says which office belongs to which division (20 O.S. "
                 "92.15a: five District 14 judges are nominated and elected from Divisions 1 to 5)"},
        {"what": "school board member districts (wards) inside a school district", "why": "school boards are elected in February and April, not on "
                 "November's ballot"},
        {"what": "technology center districts", "why": "their boards are not on November's ballot"}]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731

    def csa_source(sid, key, about_text):
        a = abouts.get(key) or {}
        d_ = docs[key]
        return {"id": sid, "agency": "University of Oklahoma, Center for Spatial Analysis, for the Oklahoma State Election Board",
                "title": f"{LAYERS[key][4]} ({LAYERS[key][0]})", "about": about_text, "publisher_says": a.get("description"), "credits": a.get("credits"),
                "use": a.get("use"), "url": a.get("page") or CSA_HUB, "service": CSA + LAYERS[key][0] + "/FeatureServer/0", "item_modified": a.get("modified"),
                "fetched": d_.get("fetched"), "sha256": G.sha_file(gz(key)), "rows": len(d_["rows"])}

    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict(csa_source(PCT, "precincts", "Every precinct's lines, its six-digit number and its House, Senate, congressional and county commissioner "
                                              "district. The State Election Board's own page sends readers to the Center for its maps."),
                 board_page=SEB_MAPS, **edited),
            csa_source("ok-csa-district-lines", "house", "House districts as lines, read to check the precincts' House numbers (and, from the same "
                                                         "data warehouse, Senate, congressional and commissioner districts: st_sen2020, "
                                                         "Congressional_Districts_2020, Commissioner_Districts_2020). The lines drawn are the precincts'."),
            csa_source(WRD, "wards", "Council wards of cities and towns, with the Census code of each city and whether it votes by ward or at large."),
            csa_source("ok-csa-fire-protection-districts", "fire", "Fire protection districts (19 O.S. 901.1 and on); each precinct names the one "
                                                                    "holding at least half of it."),
            csa_source("ok-csa-judicial-electoral-divisions", "divisions", "The electoral divisions of District Court Judicial Districts 7 "
                                                                            "(Oklahoma County) and 14 (Tulsa County)."),
            csa_source(SCH, "school", "School districts, county part by county part, with the State Department of Education's code; the parts of "
                                      "one district are put together here."),
            {"id": CENSUS, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025: places, Oklahoma (tl_2025_40_place.zip)",
             "about": "City and town limits (the active incorporated places) as the Bureau had them on January 1, 2025.",
             "url": PLACE_URL, "fetched": mtime(path("tl_2025_40_place.zip")), "sha256": G.sha_file(path("tl_2025_40_place.zip"))},
            {"id": LAW, "agency": "Oklahoma Legislature (Oklahoma Statutes, Title 20), as the Oklahoma State Courts Network indexes it",
             "title": "20 O.S. 92.2 to 92.27: District Court Judicial Districts No. 1 to No. 26", "url": OSCN_INDEX, "read": "2026-10-03",
             "about": "Which counties make up each judicial district, as the section titles name them (typed into the builder: oscn.net now shows "
                      "scripts a verification page). Every county is in exactly one district, and every district judge contest on the State "
                      "Election Board's list is printed only in counties of its district.",
             "sections": {f"{STATE}-JD{n}": f"20 O.S. {sec}" for n, (sec, _c) in JUDICIAL.items()}}],
        "notes": {
            "lines": f"Every line is the Center's precinct layer's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 degree "
                     "(about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "The precinct layer is the Center for Spatial Analysis's statewide merge of the county election boards' precinct maps, made "
                         "with the State Election Board. Its own description says it was last updated on June 7, 2022 (after the 2021 "
                         "redistricting); a precinct changed since then is drawn as it was. The county election board is the authority on which "
                         "precinct an address is in, and the OK Voter Portal answers for one voter.",
            "districts": "A precinct's House, Senate, congressional and county commissioner district are the precinct layer's own (the State "
                         "Election Board keeps every precinct inside one of each). They were checked against the Center's district lines laid "
                         "over the precincts: where the two differ and the lines put at least 99 percent of the precinct in one district, "
                         "the lines' district is used (the Census Bureau's 2026 legislative districts agreed with the lines at each such "
                         "precinct); every difference is listed in check.districts_differ_from_the_district_lines, with which was used.",
            "places": "Cities and towns are the Census Bureau's 2025 places. A precinct lying wholly in one names it (mcd); one that reaches into cities "
                      "lists them (mcd_all, with each one's share of the precinct's area), and a precinct partly outside every city names no place of "
                      "its own: the mcd layer answers for a point.",
            "wards": "Council wards are the Center's, drawn only for cities and towns that vote by ward. A precinct lists the wards it reaches (ward, with "
                     "ward_pct where it is split): precincts do not follow ward lines, so the ward layer answers for a point.",
            "judicial": "Judicial districts are whole counties (20 O.S. 92.2 to 92.27). In Oklahoma and Tulsa counties a precinct also names its "
                        "electoral division (judicial_division); associate district judges are elected by their county.",
            "fire": "Fire protection districts are the Center's layer. A precinct names the district holding at least half of it (fire, with fire_pct "
                    "when it is not wholly inside) and lists any other it reaches (fire_edge).",
            "school": "School district lines are the Center's. Which districts a precinct lies in is analysis, not an official list: a district counts "
                      f"when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share of "
                      "the precinct's area (land and water, not voters). School boards are not on November's ballot.",
            "unopposed": "Oklahoma prints only contested races (26 O.S. 6-102): an office whose only candidate was unopposed is not on the ballot, "
                         "so most county offices up in 2026 have no contest here.",
            "authority": "For which precinct an address votes in, and where, the county election board and the State Election Board's OK Voter "
                         "Portal are the authority.",
            "precinct_ids": "A precinct's id is its six-digit number as the State Election Board writes it: the county's number in the alphabet "
                            "(01 Adair to 77 Woodward) and four digits.",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of its rings, a "
                     "negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file, or one just across a hairline gap; -2: outside Oklahoma); names gives the names of the places the file's "
                            "precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees from "
                     "the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {
                "name": "the precinct's name (Precinct 550569)",
                "county": "county id", "precinct": "the precinct's six-digit number",
                "mcd": "the city or town the precinct lies wholly in (absent where it lies partly outside every one)",
                "mcd_all": "list: every city or town the precinct reaches, largest share first",
                "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                "ward": "list: the council district (ward) the precinct lies in; where it reaches several, every one, largest share first",
                "ward_pct": "list, with ward, where the precinct is not wholly in one ward: each ward's share of its area, in percent",
                "com": "county commissioner district",
                "house": "House district", "senate": "Senate district", "cd": "congressional district",
                "judicial": "judicial district (district judges)",
                "judicial_division": "electoral division of a district court judicial district (in Oklahoma and Tulsa counties only)",
                "judicial_division_pct": "the division's share of the precinct's area, in percent, where it is not wholly inside",
                "fire": "fire protection district (absent outside every one; the district holding at least half of the precinct)",
                "fire_pct": "the fire district's share of the precinct's area, in percent, where it is not wholly inside",
                "fire_edge": "list: other fire districts the precinct reaches",
                "school": "list: the school districts the precinct lies in, largest share first",
                "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "OK (j is 40)", "county": "the county's five-digit code (40001)",
                    "mcd": "OK-M- and the Census Bureau's place code (OK-M-04450); properties.t says city or town",
                    "ward": "<city>|<district as the council race words it> (OK-M-04450|Ward 1, OK-M-75000|District 1)",
                    "com": "<county>|<district> (40001|1)",
                    "house": "the district (57)", "senate": "the district (20)", "cd": "the district (1); properties.race is the race for Congress",
                    "judicial": "OK-JD and the district's number (OK-JD14)",
                    "school": "OK-S- and the State Department of Education's code (OK-S-55I089)",
                    "fire": "the ballot database's id for a district with a contest (OK-X-051-bridge-creek-fire), else OK-X-FPD- and the district's number",
                    "judicial_division": "OK-JD<district>-ED<division> (OK-JD14-ED3)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": {},
        "polling_places": polls,
        "counts": {"precincts": len(pre), "counties": len(counties), "split_between_school_districts": split,
                   "in_more_than_one_city": several, "rings_too_small_for_the_grid": dropped_rings,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Oklahoma races have a shape, a precinct word or their county"
        + (f"; {sum(e['races'] for e in check['no_shape'])} races in {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Oklahoma ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

# name, longitude, latitude, what the precinct there must say, and the place the mcd layer must give the point (None:
# outside every city). The county, House, Senate and congressional district and the city are the Census Bureau's
# geocoder's answer for those coordinates (its current 2026 legislative districts and 120th Congress districts, asked
# 2026-10-03), owing nothing to the files tested here; the precinct's number is the Center's own precinct service's answer
# for the point.
TEST_POINTS = [
    ("the State Capitol, Oklahoma City", -97.5034, 35.4923, {"id": "550569", "county": "40109", "house": "99", "senate": "48", "cd": "5"}, "OK-M-55000"),
    ("Tulsa City Hall", -95.9915, 36.1527, {"id": "720049", "county": "40143", "house": "72", "senate": "11", "cd": "1"}, "OK-M-75000"),
    ("Norman, Cleveland County courthouse", -97.4428, 35.2210, {"id": "140323", "county": "40027", "house": "44", "senate": "16", "cd": "4"}, "OK-M-52500"),
    ("Lawton City Hall", -98.3926, 34.6036, {"id": "160021", "county": "40031", "house": "64", "senate": "32", "cd": "4"}, "OK-M-41850"),
    ("Bartlesville, downtown", -95.9772, 36.7473, {"id": "740033", "county": "40147", "house": "10", "senate": "29", "cd": "2"}, "OK-M-04450"),
    ("Yukon, Main Street", -97.7625, 35.5067, {"id": "090210", "county": "40017", "house": "60", "senate": "18", "cd": "5"}, "OK-M-82950"),
    ("El Reno, downtown", -97.9550, 35.5323, {"id": "090116", "county": "40017", "house": "55", "senate": "23", "cd": "3"}, "OK-M-23700"),
    ("Clinton, downtown", -98.9673, 35.5159, {"id": "200001", "county": "40039", "house": "57", "senate": "26", "cd": "3"}, "OK-M-15400"),
    ("Guymon, Texas County", -101.4815, 36.6828, {"id": "700202", "county": "40139", "house": "61", "senate": "27", "cd": "3"}, "OK-M-31750"),
    ("a field in rural Cimarron County", -102.6, 36.7, {"id": "130004", "county": "40025", "house": "61", "senate": "27", "cd": "3"}, None),
    ("Idabel, McCurtain County", -94.8268, 33.8957, {"id": "450004", "county": "40089", "house": "1", "senate": "5", "cd": "2"}, "OK-M-36750"),
    ("Stillwater, Payne County", -97.0584, 36.1156, {"id": "600002", "county": "40119", "house": "34", "senate": "21", "cd": "3"}, "OK-M-70300"),
    ("Muskogee, downtown", -95.3697, 35.7479, {"id": "510017", "county": "40101", "house": "14", "senate": "9", "cd": "2"}, "OK-M-50050"),
    ("Enid, Garfield County", -97.8784, 36.3956, {"id": "240201", "county": "40047", "house": "40", "senate": "19", "cd": "3"}, "OK-M-23950"),
    ("Ardmore, Carter County", -97.1436, 34.1743, {"id": "100002", "county": "40019", "house": "48", "senate": "14", "cd": "4"}, "OK-M-02600"),
    ("a field in rural Osage County", -96.6, 36.6, {"id": "570301", "county": "40113", "house": "37", "senate": "10", "cd": "3"}, None),
    ("Broken Arrow, Rose District", -95.7908, 36.0526, {"id": "720163", "county": "40143", "house": "98", "senate": "33", "cd": "1"}, "OK-M-09050"),
    ("Bridge Creek, Grady County", -97.73, 35.25, {"id": "260037", "county": "40051", "house": "51", "senate": "23", "cd": "4"}, None),
]
# spots on county lines (a corner the two counties share in the Census Bureau's 1:500,000 county file)
LINE_POINTS = [("the Oklahoma-Cleveland county line", -97.4592, 35.3773, ("40109", "40027")),
               ("the Tulsa-Wagoner county line", -95.7617, 36.1337, ("40143", "40145")),
               ("the Garfield-Grant county line", -97.9116, 36.5935, ("40047", "40053"))]
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
    check(len(index["counties"]) == 77, "there are not 77 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(all(len(layer_ids.get(k, ())) == n for k, n in COUNTS.items()) and len(layer_ids.get("com", ())) == 231,
          f"the layers do not have {', '.join(f'{n} {k}' for k, n in COUNTS.items())} and 231 commissioner districts")
    check(layer_ids.get("ward", set()) >= {f"{STATE}-M-75000|District {n}" for n in range(1, 10)} | {f"{STATE}-M-41850|Ward {n}" for n in range(1, 9)},
          "the ward layer does not have Tulsa's nine council districts and Lawton's eight wards")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree, asked = collections.defaultdict(list), collections.Counter()
    school, place, ward = collections.Counter(), collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com"}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    fire_ids, div_ids = set(), set()
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
            if pr.get("fire"):
                fire_ids.add(pr["fire"])
            if pr.get("judicial_division"):
                div_ids.add(pr["judicial_division"])
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
                if kind not in layer_ids or (i % 3 and kind != "com"):
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
    check(set(v[0] for v in FIRE_IN_DB.values()) <= fire_ids, f"the fire districts with a contest are not all named by a precinct ({sorted(fire_ids)[:6]})")
    check(div_ids == {f"{STATE}-JD7-ED{n}" for n in range(1, 5)} | {f"{STATE}-JD14-ED{n}" for n in range(1, 6)},
          f"the precincts do not name District 7's four and District 14's five electoral divisions ({sorted(div_ids)})")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree "
        f"at {agree:,} of {sum(asked.values()):,} points ({skipped} too near a line to ask" + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items()))
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
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']}, {shape and shape['properties']['name']}, House {pr['house']}, Senate {pr['senate']}, "
            f"CD {pr['cd']}, {pr['judicial']}, commissioner {pr['com'].split('|')[1]}" + (f", {', '.join(pr['ward'])}" if pr.get("ward") else "")
            + (f", {pr['fire']}" if pr.get("fire") else "") + (f", {pr['judicial_division']}" if pr.get("judicial_division") else "")
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

    # 5. polling places say what they are, and name only precincts that are there
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values())
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])), "polling_places.json names a precinct or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|[\w.+-]+@[\w-]+\.\w", json.dumps(p)) for p in polls["places"]),
              "polling_places.json carries something that reads like a phone number or an e-mail address")
        say(f"      self-test: polling places: {polls.get('status')}; {len(polls['places']):,} places, {sum(1 for p in polls['places'] if p.get('lonlat')):,} with a point; "
            f"{len(polls['precinct']):,} precincts have a place")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Oklahoma's ballot map -> ballot_geo/ok/")
    ap.add_argument("--out", default=None, help="build and test in this folder and leave it there (a trial run)")
    ap.add_argument("--db", default=DB, help="ballot database to read names from, read-only")
    ap.add_argument("--refresh", action="store_true", help="ask every source again even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="only run the self-test on the files already built")
    ap.add_argument("--edw", default=EDW_DIR, help="the folder holding the saved Election Data Warehouse precinct file")
    a = ap.parse_args(argv)
    if a.selftest:
        if not selftest(os.path.abspath(a.out or OUT)):
            raise SystemExit(1)
        return
    where = os.path.abspath(a.out or BUILDING)
    build(out=where, db=os.path.abspath(a.db), refresh=a.refresh, edw_dir=os.path.abspath(a.edw))
    if not selftest(where):
        raise SystemExit(f"    the self-test failed; the files stay in {where} and ballot_geo/ok/ is unchanged")
    if a.out is None:
        K.put_in_place(where, OUT)


if __name__ == "__main__":
    main()
