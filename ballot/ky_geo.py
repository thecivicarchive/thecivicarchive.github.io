"""
ballot/ky_geo.py - the geography behind Kentucky's ballot map, in the same files and formats ballot/mn_geo.py writes for
Minnesota (it imports that module for the geometry, the topology and the TopoJSON writer, ballot/wi_geo.py,
ballot/ia_geo.py and ballot/nd_geo.py for the few things those added, and ballot/state_local_ky.py for reading the
judicial statutes, and changes nothing in any of them), so the same page and the same reader (ballot/mn_geo_reader.js)
read them all.

    python ballot/ky_geo.py                 builds ballot_geo/_building_ky/, runs the self-test on it, and only when the
                                            self-test passes puts it in place as ballot_geo/ky/ (the page builder draws a
                                            map for any state whose folder exists)
    python ballot/ky_geo.py --selftest      runs the self-test on ballot_geo/ky/ as it stands
    python ballot/ky_geo.py --refresh       asks every source again even when the cached copies are fresh
    python ballot/ky_geo.py --out DIR       builds and tests somewhere else, and leaves it there (a trial run)

Nothing here writes a database. ballot_local_2026.sqlite is opened read-only, for place names and for the check that
every shape's id is one the races carry.

Sources (downloaded with states/net.py, an honest User-Agent, one request at a time, cached in states_cache/ky_local/geo/)
-------------------------------------------------------------------------------------------------------------------------
  - Precincts: the State Board of Elections' "SBE Voting Precinct Boundaries" (kygisserver.ky.gov, Temp_Services/
    SBE_VotingPrecinctboundaries), compiled by the Board with the Division of Geographic Information from the files
    each county board of elections must file (KRS 117.055 to 117.0557), and "current through the November 3, 2026
    General Election" in the publisher's own words: 3,193 precincts, each with its county, its precinct code (a letter
    and three digits) and its name. Asked for in longitude and latitude at full detail. Neighbouring counties' precincts
    share their lines almost everywhere; drawings of one line within a metre of each other are made one line
    (nd_geo.knit).
  - Which districts each precinct is in: the State Board of Elections' Voter Registration Statistics Report by precinct
    (the newest month's, linked from elect.ky.gov/Resources/Pages/Registration-Statistics.aspx). Each precinct's row
    carries "C-S-LD-SC": its congressional, Senate, House and Supreme Court district, and the precincts are grouped
    under "Totals for Magistrate District" by the precinct code's letter. Only the precinct code and that cell are
    read; the voter counts never are. A precinct must lie wholly inside one congressional, Senate, House, justice of the
    peace or commissioner district (KRS 117.055), so these are exact for the precinct.
  - Magisterial districts: the letter of the precinct code, A for the first district, B for the second and so on, as the
    report groups them. Checked against the State Board's own 2026 primary recap sheets (each precinct's page lists the
    contests on its ballot: "MAGISTRATE 3rd Magisterial District", "CONSTABLE District 1"), county by county wherever
    such a contest was held, and against Lexington-Fayette's own precinct table. Jefferson County's precinct letters
    are not magisterial districts (they follow its House districts); its commissioner districts are drawn by LOJIC and
    are not drawn here (see below).
  - The House, Senate and congressional districts as lines, to check the report: the Legislative Research Commission's
    districts on the state's GIS server (Ky_Legislative_Districts_WGS84WM). Only the district number is asked for. The
    lines drawn are the precincts'.
  - Louisville Metro Council districts: LOJIC's precinct table (gis.lojic.org, LojicApps/PoliticalDistricts, layer 1).
    Only the precinct code, the council district and the House, Senate and congressional district (to check it is the
    2026 table) are asked for.
  - Lexington-Fayette Urban County Council districts: the Urban County Government's own precinct table (its "Voting
    Precinct" layer). Only the precinct code, the council district, the magisterial district and the House and Senate
    district are asked for; the columns naming office holders never are.
  - Cities: the Census Bureau's TIGER/Line 2025 places of Kentucky (tl_2025_21_place.zip), the active incorporated
    places and Lexington-Fayette urban county. The Louisville/Jefferson County metro government is all of Jefferson
    County (KRS 67C.101); the home rule cities inside it are cities of their own, and a voter in one is a voter of the
    metro government too.
  - School districts: TIGER/Line 2025 unified and elementary school districts (tl_2025_21_unsd.zip, tl_2025_21_elsd.zip).
    The Bureau's secondary "districts" that only say which county district teaches an elementary district's high
    school pupils are not school boards anyone elects and are not read.
  - Judicial districts and circuits: KRS 24A.030 and 23A.020 (whole counties), as ballot/state_local_ky.py reads them.
  - Polling places: the State Board of Elections' "All Polling Locations - Spreadsheet" (elect.ky.gov, Voters,
    Polling Locations), sheet "G26 - Election Day November 3": county, the location's title, street, city, zip, hours,
    whether it is a polling location or a voting center, and the precincts it serves ("ALL": any voter of the county).
    Its last column is a staff note and is never read.

What is built (ballot_geo/ky/): index.json, manifest.json, precincts/<county>.json (120), layers/<kind>.json (state,
county, cd, senate, house, judicial, mcd, ward, com, swcd, school), school/<id>.json, polling_places.json and reader.js,
each as ballot/mn_geo.py describes.

Ids (the ballot database's own; a county is its five-digit code)
----------------------------------------------------------------
  state     "KY" (j = "21")
  county    "21001"                 sl_places county id; jurisdiction_id of county offices
  mcd       "KY-M-00298"            KY-M- and the Census Bureau's place code; KY-M-48003 is the Louisville/Jefferson County
                                    metro government (the Bureau's consolidated city), KY-M-46027 Lexington-Fayette
  ward      "KY-M-48003|1"          <city>|<district as the council race words it>: Louisville Metro Council and the
                                    Lexington-Fayette Urban County Council
  com       "21001|4, magistrates and constables"
                                    <county>|<district>, the magisterial (justice of the peace) district. In the counties
                                    whose fiscal court is three commissioners the commissioner districts are the same
                                    lines (KRS 67.060), but commissioners are elected by the whole county, so their races
                                    are the county's: supervisor_plans says which counties those are
  house     "57"   senate "20"   cd "1" (properties.race is 2026-KY-H01)
  judicial  "KY-JD29"               the jurisdiction_id of district judge races (KRS 24A.030)
  circuit   "KY-JC18"               a precinct property, not a layer: the jurisdiction_id of circuit judge and
                                    Commonwealth's attorney races (KRS 23A.020)
  sc        "3"                     a precinct property, not a layer: the Supreme Court district, which is also the Court
                                    of Appeals district (KRS 21A.010, 22A.020); the jurisdiction_id of those races
  swcd      "KY-X-SWCD-21001"       the county's soil and water conservation district (j is the county: the list files
                                    every supervisor contest under its county)
  school    "KY-S-00030"            KY-S- and the Bureau's five-digit district code

Not drawn, because no statewide source has the lines: school board member districts inside a county school district
(KRS 160.210), city council wards outside Louisville and Lexington (Hopkinsville, Madisonville and the rest), and
Jefferson County's justice of the peace districts. index.json lists every race without a shape under "check".
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
import uuid
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_geo as G  # noqa: E402
from ballot import wi_geo as W  # noqa: E402
from ballot import ia_geo as I  # noqa: E402,E741
from ballot import nd_geo as N  # noqa: E402
from ballot import pdftext as P  # noqa: E402

GeoError = G.GeoError
STATE, FIPS, STATE_NAME = "KY", "21", "Kentucky"
GEO_ROOT = os.path.join(HERE, "ballot_geo")
OUT = os.path.join(GEO_ROOT, "ky")
BUILDING = os.path.join(GEO_ROOT, "_building_ky")
CACHE = os.path.join(HERE, "states_cache", "ky_local", "geo")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
READER_JS = G.READER_JS
ELECTION = "2026-11-03"
FINDER = "https://vrsws.sos.ky.gov/ovrweb/govoteky"

KYGIS = "https://kygisserver.ky.gov/arcgis/rest/services/"
PCT_SERVICE = KYGIS + "Temp_Services/SBE_VotingPrecinctboundaries/FeatureServer/0"
PCT_ITEM = KYGIS + "Temp_Services/Ky_Districts_Identify_WGS84WM/MapServer/0/iteminfo?f=pjson"
PCT_FIELDS = "OBJECTID,StCoFIPS,CountyName,PrecinctCode,PrecinctName,PrecinctID,last_edited_date"
LEG_SERVICE = KYGIS + "WGS84WM_Services/Ky_Legislative_Districts_WGS84WM/MapServer/"      # 0 House, 1 Senate, 2 Congress
STATS_PAGE = "https://elect.ky.gov/Resources/Pages/Registration-Statistics.aspx"
RECAP_PAGE = "https://elect.ky.gov/results/2020-2029/Pages/2026Primary-Recap-Sheets.aspx"
POLL_URL = "https://elect.ky.gov/Voters/Documents/All%20Polling%20Locations%20-%20Spreadsheet.xlsx"
POLL_PAGE = "https://elect.ky.gov/Voters/Pages/Polling-Locations.aspx"
LOJIC_SERVICE = "https://gis.lojic.org/maps/rest/services/LojicApps/PoliticalDistricts/MapServer/1"
LOJIC_FIELDS = "PRECINCT,COUNDIST,LEGISDIST,SENDIST,CONGDIST"
LFUCG_SERVICE = "https://services1.arcgis.com/Mg7DLdfYcSWIaDnu/ArcGIS/rest/services/Voting_Precinct/FeatureServer/0"
LFUCG_FIELDS = "CODE,COUNCIL,MAGISTERIAL,LEGISLATIVE,SENATORIAL"      # never the *REP columns, which name office holders
TIGER = "https://www2.census.gov/geo/tiger/TIGER2025/"
PLACE_URL, UNSD_URL, ELSD_URL = TIGER + "PLACE/tl_2025_21_place.zip", TIGER + "UNSD/tl_2025_21_unsd.zip", TIGER + "ELSD/tl_2025_21_elsd.zip"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")      # the kit's own copy, for the area check
STATUTES = {"districts": ("krs_24A_030_judicial_districts.pdf", "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=48467", "24A.030", "District"),
            "circuits": ("krs_23A_020_judicial_circuits.pdf", "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=53357", "23A.020", "Circuit")}

METRO, LEXINGTON, JEFFERSON, FAYETTE = "KY-M-48003", "KY-M-46027", "21111", "21067"
METRO_NAME = "Louisville/Jefferson County metro government"
COM_WORDS = "magistrates and constables"
ARC_KINDS = ["county", "ward", "com", "house", "senate", "cd", "judicial", "swcd"]      # not mcd: precincts do not follow city limits
TOL_MCD, MCD_ZOOM, MCD_THICK = I.TOL_MCD, I.MCD_ZOOM, I.MCD_THICK
WHOLE_SHARE = 0.98                # a precinct with this share of its area in one city, and no other city's thick part, is that city's
SPLIT_SHARE = W.SPLIT_SHARE
KNIT_M = 1.0                      # metres: two precincts' drawings of one line this close together are made the same line
AREA_SLACK = 0.03
MAX_AGE_DAYS = 30
POLL_LAYOUT_CHECKED = False       # True only when a person has compared a dozen precincts of polling_places.json with the Board's spreadsheet
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def clean(v):
    return re.sub(r"\s+", " ", G.blank(str(v) if v is not None else "")).strip()


def letters(text):
    return re.sub(r"[^A-Z]", "", (text or "").upper())


def mag_name(d):
    """Magisterial District 4; East Magisterial District."""
    return f"Magisterial District {d}" if str(d).isdigit() else re.sub(r" District$", " Magisterial District", str(d))


def say_nothing(*_a, **_k):
    pass


# ---------------------------------------------------------------- sources

def fetch_attrs(service, fields, oid, path, refresh, say):
    """A layer's attribute rows only (no geometry), every row, page by page, kept as JSON."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    try:
        net.patient_lookups()
        rows, offset = [], 0
        while True:
            url = (f"{service}/query?where={quote('1=1')}&outFields={fields}&returnGeometry=false&orderByFields={oid}"
                   f"&resultOffset={offset}&resultRecordCount=1000&f=json")
            j = json.loads(net.get(url, timeout=180, accept="application/json"))
            if "error" in j:
                raise GeoError(f"    {service}: {j['error']}")
            feats = j.get("features", [])
            rows += [{k: f["attributes"].get(k) for k in fields.split(",")} for f in feats]
            offset += len(feats)
            if not feats or not j.get("exceededTransferLimit"):
                break
            time.sleep(1.0)
        count = json.loads(net.get(f"{service}/query?where={quote('1=1')}&returnCountOnly=true&f=json", accept="application/json")).get("count")
        if count != len(rows):
            raise GeoError(f"    {service}: {len(rows):,} rows came, but the service counts {count}; stopping")
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path):
            say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        raise
    out = {"service": service, "fields": fields, "fetched": dt.date.today().isoformat(), "rows": rows}
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(path)}: {len(rows):,} rows")
    return out


def item_about(path, refresh):
    """What the publisher says of the precinct layer (title, summary, and its use note, which must travel with copies)."""
    if G._fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    out = {}
    try:
        j = json.loads(net.get(PCT_ITEM, accept="application/json"))
        strip = lambda t: re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", t or "")).strip() or None      # noqa: E731
        out = {"title": strip(j.get("title")), "summary": strip(j.get("summary")), "description": strip(j.get("description")),
               "credits": strip(j.get("accessInformation")), "use": strip(j.get("licenseInfo")), "fetched": dt.date.today().isoformat()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    except Exception:  # noqa: BLE001  the lines do not depend on this record
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
    return out


def newest_report(refresh, say):
    """The newest month's Voter Registration Statistics Report by precinct: (local path, address, month)."""
    keep = os.path.join(CACHE, "sbe_voterstatsprecinct_newest.json")
    if G._fresh(keep, refresh) or (not refresh and os.path.exists(keep) and time.time() - os.path.getmtime(keep) < 7 * 86400):
        k = json.load(open(keep, encoding="utf-8"))
        if os.path.exists(k["path"]):
            return k["path"], k["url"], k["month"]
    try:
        page = net.get(STATS_PAGE).decode("utf-8", "replace")
        found = []
        for h in set(re.findall(r'href="([^"]*voterstatsprecinct-([A-Za-z]+)(?:%20| )(\d{4})\.pdf)"', page)):
            if h[1] in MONTHS:
                found.append((int(h[2]), MONTHS.index(h[1]), h[0], f"{h[1]} {h[2]}"))
        if not found:
            raise GeoError("    the State Board's statistics page no longer links a monthly report by precinct")
        year, mon, href, month = max(found)
        url = "https://elect.ky.gov" + href if href.startswith("/") else href
        path = os.path.join(CACHE, f"sbe_voterstatsprecinct_{year}-{mon + 1:02d}.pdf")
        net.download(url.replace(" ", "%20"), path, 3650, say=say)
        with open(keep, "w", encoding="utf-8") as fh:
            json.dump({"path": path, "url": url, "month": month}, fh)
        return path, url, month
    except Exception as e:  # noqa: BLE001
        if os.path.exists(keep):
            say(f"      could not read the statistics page again ({e}); using the report on disk")
            k = json.load(open(keep, encoding="utf-8"))
            return k["path"], k["url"], k["month"]
        raise


REPORT_ROW = re.compile(r"^([A-Z]\d{3}) .*? (\d)-(\d{1,2})-(\d{3})-(\d)\b")
REPORT_COUNTY = re.compile(r"^(\d{3}) ([A-Z][A-Z .']+)$")
REPORT_TOTAL = re.compile(r"^([A-Z]) Totals for Magistrate District\b")


def read_report(path, county_key):
    """{county fips: {precinct code: (cd, senate, house, supreme court district)}} and {county fips: {letters grouped
    under "Totals for Magistrate District"}}. Only the code and the district cell of a row are read."""
    rows, groups, cty = collections.defaultdict(dict), collections.defaultdict(set), None
    for _pg, _y, s in P.lines(path):
        s = s.strip()
        m = REPORT_COUNTY.match(s)
        if m:
            cty = county_key.get(letters(m.group(2)))
            if cty is None:
                raise GeoError(f"    statistics report: a county heading names {m.group(2)!r}, which is not a Kentucky county; stopping")
            continue
        m = REPORT_ROW.match(s)
        if m and cty:
            rows[cty][m.group(1)] = (str(int(m.group(2))), str(int(m.group(3))), str(int(m.group(4))), str(int(m.group(5))))
            continue
        m = REPORT_TOTAL.match(s)
        if m and cty:
            groups[cty].add(m.group(1))
    if len(rows) != 120:
        raise GeoError(f"    statistics report: {len(rows)} counties read, not 120; the reader needs to be told the layout")
    return rows, groups


# ---------------------------------------------------------------- the 2026 primary recap sheets (a check on the letters)

RECAP_HEAD = re.compile(r"^([A-Z]\d{3})[A-Z]?\b.*?\s[\d,]+ ballots cast")
RECAP_TOP = re.compile(r"^([A-Z]\d{3})[A-Z]?\b")
RECAP_CONTEST = re.compile(r"\b(MAGISTRATE|CONSTABLE|COUNTY COMMISSIONER|JUSTICE OF THE PEACE|STATE REPRESENTATIVE)\b(.*)$", re.I)
RECAP_NUMBER = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)\b|\bDistrict\s*(\d{1,3})\b|\b((?:North|South)?(?:east|west)|North|South|East|West|Central)\b", re.I)
RECAPS = {"2026 primary": ("recaps_2026_primary", RECAP_PAGE, "PrimaryRecaps"),
          "2022 general": ("recaps_2022_general", "https://elect.ky.gov/results/2020-2029/Pages/2022-General-Recap-Sheets.aspx", "GeneralRecaps")}
RECAP_MAX_BYTES = 15_000_000      # larger files are scanned pages with no text to read


def recap_sheets(which, refresh, say):
    """The State Board's recap sheets of one election, one PDF a county (fetched once, one at a time)."""
    sub, page_url, mark = RECAPS[which]
    folder = os.path.join(CACHE, sub)
    os.makedirs(folder, exist_ok=True)
    have = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".pdf"))
    if len(have) >= 118 and not refresh:
        return have
    try:
        page = net.get(page_url).decode("utf-8", "replace")
        for h in sorted(set(h for h in re.findall(r'href="([^"]+\.pdf)"', page, re.I) if mark in h)):
            name = h.rsplit("/", 1)[1].replace("%20", " ")
            try:
                net.download("https://elect.ky.gov" + h.replace(" ", "%20"), os.path.join(folder, name), 3650, tries=2, say=say_nothing)
            except Exception:  # noqa: BLE001  a link the Board's page names and its server does not have (Butler, 2022)
                pass
    except Exception as e:  # noqa: BLE001  only the numbering of magisterial districts depends on these
        say(f"      the {which} recap sheets could not all be read ({e}); those on disk are used")
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".pdf"))


def district_word(text):
    """A magistrate's or constable's district as the ballot list words it: "3" for "3rd Magisterial District" or
    "District 3"; "East District" for "East Magisterial District"."""
    n = RECAP_NUMBER.search(text)
    if not n:
        return None
    if n.group(1) or n.group(2):
        return str(int(n.group(1) or n.group(2)))
    return n.group(3).title() + " District"


def read_recap(path):
    """{(office, district): {precinct codes}} from one county's recap sheet: each contest heading is filed under the
    precinct whose page it is on (a page begins with "<code> <n> ballots cast", or with the precinct's code and name
    above its first contest). Candidates' names are never read."""
    pages = collections.defaultdict(list)
    for pg, y, s in P.lines(path):
        pages[pg].append((y, s))
    cur, out = None, collections.defaultdict(set)
    for pg in sorted(pages):
        seen_contest, here = False, collections.defaultdict(set)
        for _y, s in sorted(pages[pg], key=lambda t: -t[0]):
            s = s.strip()
            m = RECAP_HEAD.match(s) or (None if seen_contest else RECAP_TOP.match(s))
            if m:
                cur = m.group(1)
                continue
            if "Vote for" in s or re.search(r"District\s*\d+\s*$", s):
                seen_contest = True
            else:
                continue
            m = RECAP_CONTEST.search(s)
            if not m or not cur:
                continue
            office = m.group(1).upper()
            office = "MAGISTRATE" if office == "JUSTICE OF THE PEACE" else office
            d = district_word(m.group(2))
            if d:
                here[(cur, office)].add(d)
        for (code, office), ds in here.items():
            if len(ds) == 1 or office == "COUNTY COMMISSIONER":      # one precinct votes in one district's contest: a page with several is a summary page
                for d in ds:
                    out[(office, d)].add(code)
    return out


def recap_read(which, paths, county_key, say):
    """Every county's {"<office>|<district>": [precinct codes]} from one election's recap sheets, kept in a small cache
    keyed by the files' fingerprints."""
    cache = os.path.join(CACHE, f"ky_geo_recaps_{which.replace(' ', '_')}.json")
    stamp = hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [4]).encode()).hexdigest()
    if os.path.exists(cache):
        try:
            kept = json.load(open(cache, encoding="utf-8"))
            if kept.get("stamp") == stamp:
                return kept["counties"]
        except (ValueError, OSError):
            pass
    say(f"      reading {len(paths)} recap sheets of the {which} (which precinct votes in which magisterial district's contests; kept for the next build)")
    out = {}
    for p in paths:
        c = county_key.get(letters(re.sub(r"(?i)\s*county\s*$", "", os.path.basename(p)[:-4])))
        if c is None or os.path.getsize(p) > RECAP_MAX_BYTES:
            continue
        try:
            got = read_recap(p)
        except Exception:  # noqa: BLE001  a sheet the reader cannot open adds nothing
            continue
        out[c] = {f"{o}|{d}": sorted(v) for (o, d), v in sorted(got.items())}
    with open(cache + ".part", "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "counties": out}, fh, separators=(",", ":"))
    os.replace(cache + ".part", cache)
    return out


# ---------------------------------------------------------------- the ballot database

def read_db(db):
    info = {"names": {}, "races": [], "found": False}
    if not os.path.exists(db):
        return info
    con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'ky-%'"):
            info["names"][(kind, pid)] = name
        info["races"] = list(con.execute("SELECT race_id, level, office_kind, jurisdiction, jurisdiction_id, district, county_ids FROM sl_races WHERE state = ?", (STATE,)))
    finally:
        con.close()
    info["found"] = True
    return info


def check_ids(info, shape_ids, said, plans):
    """Every Kentucky race in the ballot database against the shapes, by the rule the page builder uses
    (build_ballot_state_dev.race_shape), and, for a race no layer draws, against the districts the precincts name
    (build_ballot_state_dev.race_said). A race without either is listed with the reason."""
    if not info["found"]:
        return {"races": 0, "matched": 0, "by_layer": {}, "by_precinct_word": {}, "no_shape": [], "note": "not checked in this build"}
    S = shape_ids
    by_layer, by_said, missing, matched = collections.Counter(), collections.Counter(), collections.OrderedDict(), 0
    county_wide = collections.Counter()
    for rid, level, kind, jur, jid, district, county_ids in sorted(info["races"], key=lambda r: r[0]):
        jid = str(jid or "").strip()
        d = str(district).strip() if district not in (None, "") else ""
        hit, why = None, None
        if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
            hit = ("state", STATE)
        elif kind == "state_senate":
            hit = ("senate", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "state_house":
            hit = ("house", re.sub(r"^0+(?=\d)", "", d))
        elif kind == "district_court" or (level == "court" and jid in S.get("judicial", {})):
            hit = ("judicial", jid)
        elif kind in ("county_commissioner", "county_council"):
            plan = plans.get(jid) or {}
            whole = not d or (f"{jid}|{d}" not in S.get("com", {}) and plan.get("plan") == 2 and d in (plan.get("districts") or []))
            hit = ("county", jid) if whole else ("com", f"{jid}|{d}")
            if not whole:
                why = "the commissioner district is not one the precinct letters give for this county"
        elif level == "county":
            hit = ("county", jid)
            if kind in ("magistrate", "constable") and d:
                county_wide[kind] += 1
        elif level == "soil_water":
            own = sorted(i for i, p in S.get("swcd", {}).items() if p.get("j") == jid)
            hit = ("swcd", own[0]) if len(own) == 1 else None
            why = None if hit else ("this conservation district is one of two in its county (North and South Logan); no source read here draws the "
                                    "line between them" if jid.startswith(f"{STATE}-X-") else "no soil and water district shape carries this county")
        elif level in ("city", "township"):
            hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
            if d and hit[1] not in S.get("ward", {}):
                why = ("no statewide source draws this city's wards or council districts; the city is drawn, and the page lists its "
                       "contests for everyone in it" if jid in S.get("mcd", {}) else "the Census Bureau's 2025 places do not have this city")
        elif level == "school":
            hit = ("school", jid)
        if hit and hit[1] in S.get(hit[0], {}):
            matched += 1
            by_layer[hit[0]] += 1
            continue
        q = next((k for k, v in sorted(said.items()) if jid and jid in v), None)
        if level == "court" and q:
            matched += 1
            by_said[q] += 1
            continue
        key = (level, kind, jur if level not in ("court",) else None, jid if level not in ("court",) else None, district if level in ("city", "township") else None)
        e = missing.setdefault(key, {"level": level, "office_kind": kind, "jurisdiction": key[2], "jurisdiction_id": key[3], "district": key[4],
                                     "races": 0, "why": why or "no shape carries this id"})
        e["races"] += 1
    return {"races": len(info["races"]), "matched": matched, "by_layer": dict(sorted(by_layer.items())), "by_precinct_word": dict(sorted(by_said.items())),
            "no_shape": list(missing.values()),
            "drawn_as_the_county": {k: f"{n} {k} races are elected by magisterial district; the page builder's rule draws a {k} race as its county, "
                                       f"though the com layer has every magisterial district (ids '<county>|<district>, {COM_WORDS}')" for k, n in sorted(county_wide.items())}}


# ---------------------------------------------------------------- polling places (the State Board's spreadsheet)

POLL_WAITING = {"why": "The Kentucky State Board of Elections' list of Election Day polling locations for November 3, 2026 could not be read when "
                       "these files were built. GoVoteKY, the Board's voter information center, answers for one voter at a time, and the county "
                       "clerk is the authority."}
POLL_HEADS = {"county": "County", "name": "Polling Location Title", "address": "Polling Location Street", "city": "Polling Location City",
              "zip": "Polling Location Zip", "hours": "Polling Location Date/Time", "precincts": "Precincts"}      # the type column has no heading


def read_polls(path):
    """The Election Day sheet, cut down on the spot to the columns in POLL_HEADS and the unheaded type column."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = next((ws for ws in wb.worksheets if re.match(r"G26 - Election Day November 3\b", ws.title or "")), None)
    if sheet is None:
        raise GeoError(f"    polling places: the spreadsheet has no sheet for Election Day, November 3 ({[ws.title for ws in wb.worksheets]})")
    rows = list(sheet.iter_rows(values_only=True))
    head = [clean(h) for h in rows[0]]
    col = {k: head.index(h) for k, h in POLL_HEADS.items() if h in head}
    if set(col) != set(POLL_HEADS) or "" not in head:
        raise GeoError(f"    polling places: the sheet's headings are now {head}; the reader needs to be told the layout")
    col["type"] = head.index("")
    out = []
    for r in rows[1:]:
        if not any(r):
            continue
        out.append({k: clean(r[i]) for k, i in col.items()})
    wb.close()
    return out


def census_geocode(rows, say):
    """[(id, street, city, zip)] -> {id: (lon, lat)}: the Census Bureau's batch geocoder for Kentucky addresses (no key).
    Polling places are public buildings; nothing else is ever sent."""
    net.patient_lookups()
    out = {}
    for start in range(0, len(rows), 1000):
        buf = io.StringIO()
        w = csv.writer(buf)
        for rid, street, city, zipc in rows[start:start + 1000]:
            w.writerow([rid, street, city, STATE, zipc])
        boundary = "----kygeo" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"places.csv\"\r\n"
                f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n").encode("utf-8")
        req = Request(G.GEOCODER, data=body, headers={"User-Agent": net.UA, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urlopen(req, timeout=900) as r:
            text = r.read().decode("utf-8", "replace")
        for rec in csv.reader(io.StringIO(text)):
            if len(rec) >= 6 and rec[2].strip() == "Match":
                try:
                    lon, lat = (float(v) for v in rec[5].split(","))
                except ValueError:
                    continue
                out[rec[0].strip()] = (round(lon, 5), round(lat, 5))
        say(f"      polling places: {min(start + 1000, len(rows)):,} of {len(rows):,} addresses asked of the Census Bureau's geocoder, {len(out):,} matched so far")
        time.sleep(1.0)
    return out


def place_points(places, cbox, say):
    cache_path = os.path.join(CACHE, "ky_geo_pollingplace_points.json")
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
        except Exception as e:  # noqa: BLE001  the list is worth having without points on a map
            say(f"      polling places: the Census Bureau's geocoder could not be reached ({e}); places without coordinates stay off the map")
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


def polling_places(pre, cname, county_key, cbox, put, say, refresh):
    doc = {"v": G.VERSION, "election": ELECTION, "finder": FINDER}
    path = os.path.join(CACHE, "sbe_all_polling_locations.xlsx")
    try:
        net.download(POLL_URL, path, 2 if not refresh else 0, say=say)
        rows = read_polls(path)
    except Exception as e:  # noqa: BLE001  the map does not depend on this list
        doc.update(status="waiting", **POLL_WAITING)
        put("polling_places.json", doc)
        say(f"      polling places: waiting; the State Board's spreadsheet could not be read ({e})")
        return {"file": "polling_places.json", "status": "waiting"}
    ids_of = collections.defaultdict(dict)
    for p in pre:
        ids_of[p["county"]][p["code"]] = p["id"]
    places, assigned, anyone, unmatched, bad_rows = [], collections.defaultdict(list), collections.defaultdict(list), set(), 0
    for r in rows:
        c = county_key.get(letters(r["county"]))
        if c is None:
            bad_rows += 1
            continue
        cell = r["precincts"].upper()
        codes = re.findall(r"\b[A-Z]\d{3}[A-Z]?\b", cell)
        everyone = cell.strip() == "ALL"
        if not everyone and not codes:
            bad_rows += 1
            continue
        n = len(places)
        places.append({"name": r["name"], "address": r["address"], "city": r["city"].title() if r["city"].isupper() else r["city"], "zip": r["zip"][:5],
                       "type": r["type"] or None, "hours": r["hours"] or None, "lonlat": None, "precincts": [], "_county": c,
                       **({"any_voter_of_the_county": True} if everyone else {})})
        if everyone:
            anyone[c].append(n)
            continue
        for code in codes:
            pid = ids_of[c].get(code) or ids_of[c].get(code[:4])
            if pid is None:
                unmatched.add(f"{c}{code}")
                continue
            if n not in assigned[pid]:
                assigned[pid].append(n)
    for c, ns in anyone.items():
        for n in ns:
            places[n]["precincts"] = sorted(ids_of[c].values())
    for pid, ns in assigned.items():
        for n in ns:
            if pid not in places[n]["precincts"]:
                places[n]["precincts"].append(pid)
    precinct, several = {}, {}
    for p in pre:
        own, centres = assigned.get(p["id"], []), anyone.get(p["county"], [])
        allp = own + [n for n in centres if n not in own]
        if len(allp) == 1:
            precinct[p["id"]] = allp[0]
        elif allp:
            def nm(n):
                q = places[n]
                return f"{q['name']} ({q['address']}, {q['city']})"
            if own and centres:
                several[p["id"]] = (f"is listed with {'its own polling place' if len(own) == 1 else f'{len(own)} polling places'} ({'; '.join(nm(n) for n in own)}), and any voter "
                                    f"of {cname[p['county']]} may also vote at its {len(centres)} voting center{'s' if len(centres) > 1 else ''} on the State Board of Elections' list "
                                    "(shown on the map); the county clerk is the authority")
            elif centres:
                several[p["id"]] = (f"is in {cname[p['county']]}, where any voter may vote at any of the county's {len(centres)} Election Day voting centers on the "
                                    "State Board of Elections' list (shown on the map); the county clerk is the authority")
            else:
                several[p["id"]] = f"is listed with {len(own)} polling places on the State Board of Elections' list ({'; '.join(nm(n) for n in own)}); the county clerk says which serves your address"
    placed, far = place_points(places, cbox, say)
    for q in places:
        q.pop("_county", None)
    without = sorted(p["id"] for p in pre if p["id"] not in precinct and p["id"] not in several)
    status = "loaded" if POLL_LAYOUT_CHECKED else "unchecked"
    doc.update(status=status,
               source={"agency": "Kentucky State Board of Elections", "title": "All Polling Locations (spreadsheet), sheet G26 - Election Day November 3",
                       "url": POLL_URL, "page": POLL_PAGE, "saved": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "sha256": G.sha_file(path)},
               places=places, precinct=dict(sorted(precinct.items())), no_place=dict(sorted(several.items())),
               note="A precinct with one polling place on the list is in precinct; a precinct with several, or in a county whose voting centers serve "
                    "any voter of the county, is in no_place, in words. A place whose precinct cell reads ALL serves every precinct of its county "
                    "(any_voter_of_the_county).")
    put("polling_places.json", doc)
    say(f"      polling places: {len(rows):,} rows, {len(places):,} places ({placed:,} placed by the Census Bureau's geocoder, {far} matches thrown out as "
        f"outside the county); {len(precinct):,} precincts with one place, {len(several):,} with several or with voting centers, {len(without):,} not on "
        f"the list{(' (e.g. ' + ', '.join(without[:5]) + ')') if without else ''}; {len(unmatched)} listed codes not on the map"
        + (f" (e.g. {', '.join(sorted(unmatched)[:6])})" if unmatched else "") + (f"; {bad_rows} rows not read" if bad_rows else ""))
    if not POLL_LAYOUT_CHECKED:
        say("      polling places: marked 'unchecked', so a page does not show them yet. Compare a dozen precincts of polling_places.json with the "
            "State Board's spreadsheet (elect.ky.gov, Voters, Polling Locations), then set POLL_LAYOUT_CHECKED = True in ballot/ky_geo.py and build again.")
    return {"file": "polling_places.json", "status": status, "places": len(places), "with_coordinates": sum(1 for p in places if p["lonlat"]),
            "rows": len(rows), "precincts_with_one_place": len(precinct), "precincts_with_several_or_voting_centers": len(several),
            "on_the_map_and_not_listed": without, "listed_and_not_on_the_map": sorted(unmatched)}


# ---------------------------------------------------------------- the build

def knit(polys):
    """nd_geo.knit at Kentucky's latitude (its metres per 1e-7 degree east are set for the middle of the state while it
    runs, and put back)."""
    keep = N.KX
    N.KX = G.M_PER_UNIT * math.cos(math.radians(37.8))
    try:
        return N.knit(polys, eps_m=KNIT_M)
    finally:
        N.KX = keep


def fabric_keys(items):
    """ia_geo.fabric for shapes whose rings are already vertex keys (a Census shapefile read by ia_geo.read_shapefile):
    (keys, polygons, arcs, sides, rings, anything odd)."""
    items = sorted(items, key=lambda x: G.natkey(x[0]))
    keys = [k for k, _r in items]
    if len(set(keys)) != len(keys):
        raise GeoError(f"    two shapes share the id {[k for k, n in collections.Counter(keys).items() if n > 1][0]!r}; stopping")
    polys = [[list(r) for r in rings] for _k, rings in items]
    slivers, gave = W.settle_overlaps([{"id": k} for k in keys], polys)
    arcs, sides, rings, odd = G.topology(polys)
    odd = collections.Counter(odd)
    odd["sliver rings left out"] += slivers
    odd["points given up where two shapes overlapped"] += sum(n for _k, n in gave)
    if any(not r for r in rings):
        raise GeoError(f"    the shape {keys[[i for i, r in enumerate(rings) if not r][0]]!r} has no ring left after cleaning; stopping")
    return keys, polys, arcs, sides, rings, collections.Counter({k: v for k, v in odd.items() if v})


def overlay_cached(name, pre_rings, districts, stamp, refresh, say):
    path = os.path.join(CACHE, f"ky_geo_overlay_{name}.json")
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


def judicial_maps(county_key, refresh, say):
    """{"districts": {n: [fips]}, "circuits": {n: [fips]}} from KRS 24A.030 and 23A.020, read the way the Kentucky
    loader reads them, and {key: (path, url)}."""
    from ballot import state_local_ky as L
    out, src = {}, {}
    for key, (fname, url, section, word) in STATUTES.items():
        path = os.path.join(CACHE, fname)
        try:
            net.download(url, path, 3650 if not refresh else 0, say=say)
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise GeoError(f"    KRS {section} could not be fetched ({e}); stopping")
        got, why = L.judicial_counties(path, section, word, county_key)
        if got is None:
            raise GeoError(f"    KRS {section} could not be read into counties ({why}); stopping")
        out[key], src[key] = got, (path, url, section)
    return out, src


def build(out=BUILDING, db=DB, refresh=False, say=print):
    t0 = time.time()
    say("    Kentucky ballot map: precinct, district, city and school district lines (State Board of Elections, LRC, LOJIC, LFUCG, Census Bureau)")
    os.makedirs(CACHE, exist_ok=True)
    path = lambda name: os.path.join(CACHE, name)      # noqa: E731
    ppath = path("sbe_voting_precincts_geometry_4326.json.gz")
    pdoc = W.fetch_full(PCT_SERVICE, PCT_FIELDS, ppath, 500, "OBJECTID", refresh, say)
    about = item_about(path("sbe_voting_precincts_about.json"), refresh)
    legdocs = {k: W.fetch_full(LEG_SERVICE + str(i), "OBJECTID,District", path(f"lrc_{k}_districts_geometry_4326.json.gz"), 20, "OBJECTID", refresh, say)
               for k, i in (("house", 0), ("senate", 1), ("cd", 2))}
    lojic = fetch_attrs(LOJIC_SERVICE, LOJIC_FIELDS, "PRECINCT", path("lojic_precincts_attributes.json"), refresh, say)
    lfucg = fetch_attrs(LFUCG_SERVICE, LFUCG_FIELDS, "CODE", path("lfucg_voting_precincts_attributes.json"), refresh, say)
    for url, fname in ((PLACE_URL, "tl_2025_21_place.zip"), (UNSD_URL, "tl_2025_21_unsd.zip"), (ELSD_URL, "tl_2025_21_elsd.zip")):
        net.download(url, path(fname), 3650, say=say)
    rpath, rurl, rmonth = newest_report(refresh, say)
    edited = W.layer_edited(PCT_SERVICE, path("ky_geo_about_precincts.json"), refresh)

    # ---- precincts
    rows = sorted(pdoc["rows"], key=lambda r: r[0]["PrecinctID"])
    pre, polys, county_short = [], [], {}
    for a, rings in rows:
        pid, c, code = clean(a["PrecinctID"]), clean(a["StCoFIPS"]), clean(a["PrecinctCode"])
        if not (re.fullmatch(r"21\d{3}", c) and re.fullmatch(r"[A-Z]\d{3}", code) and pid == c + code and clean(a["CountyName"])):
            raise GeoError(f"    precinct layer: the row {pid!r} does not fit the layout this builder was checked against; stopping")
        if county_short.setdefault(c, clean(a["CountyName"])) != clean(a["CountyName"]):
            raise GeoError(f"    precinct layer: county {c} is given two names; stopping")
        name = clean(a["PrecinctName"])
        pre.append({"id": pid, "county": c, "code": code, "pname": name if name and name != code else ""})
        polys.append([k for k in (G.clean_ring(r) for r in rings) if k])
    if len(county_short) != 120 or len({p["id"] for p in pre}) != len(pre):
        raise GeoError(f"    precinct layer: {len(county_short)} counties and {len(pre)} rows; 120 counties, one row a precinct, were expected; stopping")
    county_key = {letters(n): c for c, n in county_short.items()}
    moved, added = knit(polys)
    slivers, gave = W.settle_overlaps(pre, polys)
    if any(not rings for rings in polys):
        raise GeoError("    a precinct has no ring left after its lines were set together; stopping")
    arcs, sides, rings_of, odd = G.topology(polys)
    fine, _restored = G.simplify_arcs(arcs, rings_of, G.TOL_PRECINCT)
    qfine = G.quantise(fine)
    seam = W.across(arcs, sides, pre)
    lone = sum(1 for r, l in sides if r < 0 or l < 0)
    say(f"      {len(pre):,} precincts in 120 counties, {sum(len(r) for r in rings_of):,} rings, {len(arcs):,} lines between them ({sum(len(a) for a in arcs):,} points; "
        f"{sum(len(a) for a in qfine if a):,} after generalising to {G.TOL_PRECINCT} m); drawings of one line within {KNIT_M:.0f} m made one ({moved:,} corners moved, "
        f"{added:,} added); {lone:,} lines have a precinct on one side only, {len(seam):,} of them with another precinct just across; {slivers} sliver rings left out, "
        f"{sum(n for _w, n in gave)} points given up where two precincts ran the same way along a line" + (f"; odd: {dict(odd)}" if odd else ""))

    info = read_db(db)
    names = info["names"]
    if not info["found"]:
        say(f"      {os.path.basename(db)} is not there: places are named from the sources alone")
    cname = {c: names.get(("county", c)) or f"{n} County" for c, n in county_short.items()}

    # ---- the State Board's report: districts of every precinct, and the magisterial letters
    report, groups = read_report(rpath, county_key)
    on_report = 0
    for p in pre:
        r = report.get(p["county"], {}).get(p["code"])
        p["listed"] = r is not None
        on_report += r is not None
        if r:
            p["cd"], p["senate"], p["house"], p["sc"] = r
    rep_only = sorted(f"{c}{code}" for c, rows_ in report.items() for code in rows_ if f"{c}{code}" not in {p["id"] for p in pre})
    say(f"      statistics report ({rmonth}): {on_report:,} of {len(pre):,} precincts of the map are on it; {len(rep_only)} of its precincts are not on the map"
        + (f" ({', '.join(rep_only)})" if rep_only else ""))

    # ---- the LRC's districts laid over the precincts: a check of the report, and the districts of precincts it does not list
    pre_rings = [[G.ring_xy(refs, fine) for refs in rings] for rings in rings_of]
    stamp = lambda *paths: hashlib.sha256(json.dumps([G.sha_file(p) for p in paths] + [G.TOL_PRECINCT, G.SCHOOL_THICK, KNIT_M, 1]).encode()).hexdigest()   # noqa: E731
    differs, fromlrc = collections.Counter(), collections.Counter()
    leg_diff = []
    for k in ("house", "senate", "cd"):
        doc = legdocs[k]
        keyf = lambda a: str(int(re.sub(r"\D", "", str(a["District"])) or 0))      # noqa: E731  "H057" -> "57"
        keys, lpolys, *_rest = I.fabric(N.merge_rows(doc["rows"], keyf), keyf)
        want = {"house": 100, "senate": 38, "cd": 6}[k]
        if len(keys) != want:
            raise GeoError(f"    LRC {k} districts: {len(keys)} shapes, not {want}; stopping")
        ov = overlay_cached(f"lrc_{k}", pre_rings, I.rings_xy(lpolys), stamp(ppath, path(f"lrc_{k}_districts_geometry_4326.json.gz")), refresh, say)
        for p, got in zip(pre, ov):
            got = sorted(got, key=lambda g: -g[1])
            best = keys[got[0][0]] if got else None
            if not p["listed"]:
                if best is None:
                    raise GeoError(f"    precinct {p['id']} is on no list and in no LRC {k} district; stopping")
                p[k] = best
                fromlrc[k] += 1
            elif best != p[k] and (not got or got[0][1] >= 0.5):
                differs[k] += 1
                if len(leg_diff) < 40:
                    leg_diff.append({"id": p["id"], "kind": k, "report": p[k], "lrc_layer": best, "share": round(100 * got[0][1], 1) if got else None})
    say(f"      House, Senate and congressional districts: the report's agree with the LRC's lines laid over the precincts at all but "
        f"{', '.join(f'{n} ({k})' for k, n in sorted(differs.items())) or 'none'}; {sum(fromlrc.values()) // 3} precincts not on the report take the LRC's")

    # Supreme Court districts are whole counties (KRS 21A.010): a precinct the report does not list takes its county's
    # (a stray digit on one row is set right to its county's, and listed; more than that stops the build)
    sc_of = collections.defaultdict(collections.Counter)
    for p in pre:
        if p.get("sc"):
            sc_of[p["county"]][p["sc"]] += 1
    sc_fixed = []
    for c, cnt in sc_of.items():
        if len(cnt) > 1:
            (top, n), rest = cnt.most_common(1)[0], sum(cnt.values()) - cnt.most_common(1)[0][1]
            if rest > 2 or n < 10 * rest:
                raise GeoError(f"    statistics report: Supreme Court districts are whole counties, but county {c} carries {dict(cnt)}; stopping")
    if len(sc_of) != 120:
        raise GeoError("    statistics report: not every county has a Supreme Court district; stopping")
    for p in pre:
        top = sc_of[p["county"]].most_common(1)[0][0]
        if p.get("sc") and p["sc"] != top:
            sc_fixed.append({"id": p["id"], "report": p["sc"], "county": top})
        p["sc"] = top
    if sc_fixed:
        say(f"      Supreme Court districts: {len(sc_fixed)} report row{'s' if len(sc_fixed) > 1 else ''} give another district than the rest of the county "
            f"({', '.join(x['id'] + ': ' + x['report'] for x in sc_fixed)}); the county's is used")

    # ---- judicial districts and circuits (whole counties, by statute)
    jmaps, jsrc = judicial_maps(county_key, refresh, say)
    jd_of = {f: f"KY-JD{n}" for n, fs in jmaps["districts"].items() for f in fs}
    jc_of = {f: f"KY-JC{n}" for n, fs in jmaps["circuits"].items() for f in fs}
    for p in pre:
        p["judicial"], p["circuit"] = jd_of[p["county"]], jc_of[p["county"]]

    # ---- magisterial districts. A precinct code's letter is its magisterial district, as the State Board's report groups
    # them; which district a letter is (its number, or its name: Daviess County's East District) is read from the State
    # Board's recap sheets, where each precinct's page names its magistrate's and constable's contests. In most counties
    # A is the first district, B the second; in some it is not (Jessamine's B precincts vote in the 4th district). A
    # letter no recap sheet shows is given the alphabet's number only where every letter the sheets do show follows the
    # alphabet. Jefferson County's letters are not magisterial districts.
    lfucg_by = {clean(r["CODE"]): r for r in lfucg["rows"]}
    lojic_by = {clean(r["PRECINCT"]): r for r in lojic["rows"]}
    letter_count = collections.defaultdict(set)
    for p in pre:
        L_ = p["code"][0]
        p["letter"] = None if p["county"] == JEFFERSON or L_ == "X" else L_
        if p["letter"]:
            letter_count[p["county"]].add(L_)
    db_words = collections.defaultdict(set)      # the districts the ballot list gives magistrates and constables, county by county
    for _rid, level, kind, _jur, jid, district, _ci in info["races"]:
        if level == "county" and kind in ("magistrate", "constable") and district not in (None, ""):
            db_words[jid].add(str(int(district)) if str(district).isdigit() else str(district))
    pre_by = {p["id"]: p for p in pre}
    ev = {w: collections.defaultdict(lambda: collections.defaultdict(collections.Counter)) for w in RECAPS}      # election -> county -> letter -> district -> pages
    house_ok, house_bad, recap_files = 0, [], {}
    for which in RECAPS:
        paths = recap_sheets(which, refresh, say)
        recap_files[which] = paths
        rc = recap_read(which, paths, county_key, say)
        for c, contests in rc.items():
            for key, codes in contests.items():
                office, d = key.split("|")
                for code in codes:
                    p = pre_by.get(c + code)
                    if office == "STATE REPRESENTATIVE":
                        if which == "2026 primary" and p is not None and d.isdigit():
                            if p.get("house") == d:
                                house_ok += 1
                            else:
                                house_bad.append(f"{p['id']} (House {d} on the recap, {p.get('house')} here)")
                        continue
                    if office not in ("MAGISTRATE", "CONSTABLE") or c == JEFFERSON or code[0] == "X":
                        continue
                    ev[which][c][code[0]][d] += 1
    numbering, letter_word, conflicts, years_differ = {}, {}, [], []
    for c in sorted(county_short):
        if c == JEFFERSON:
            continue
        lets = sorted(letter_count.get(c, ()))
        mine, bad = {}, set()
        for which in RECAPS:                       # the 2026 primary first; the 2022 general only for letters it does not show
            for L_ in lets:
                got = ev[which].get(c, {}).get(L_)
                if not got or L_ in mine or L_ in bad:
                    if got and L_ in mine and got.most_common(1)[0][0] != mine[L_]:
                        years_differ.append(f"{cname[c]} {L_}: {mine[L_]} in 2026, {got.most_common(1)[0][0]} in 2022")
                    continue
                (top, n), total = got.most_common(1)[0], sum(got.values())
                if n < 0.8 * total:
                    conflicts.append(f"{cname[c]} {L_} ({which}): {dict(got)}")
                    bad.add(L_)
                    continue
                if top in mine.values():           # the 2022 sheets give a letter a district the 2026 sheets give another letter
                    years_differ.append(f"{cname[c]} {L_}: {top} in {which}, already another letter's")
                    bad.add(L_)
                    continue
                mine[L_] = top
        if len(set(mine.values())) != len(mine):
            conflicts.append(f"{cname[c]}: two letters read as one district ({mine})")
            mine = {}
        alpha = {L_: str(i + 1) for i, L_ in enumerate(lets)}
        follows = all(mine[L_] == alpha[L_] for L_ in mine) and not bad
        named = any(not w.isdigit() for w in db_words.get(c, ())) or any(not w.isdigit() for w in mine.values())
        rest = [L_ for L_ in lets if L_ not in mine]
        if rest and follows and not named:
            for L_ in rest:
                mine[L_] = alpha[L_]
            how = "recap sheets, the rest in letter order" if len(rest) < len(lets) else "letter order (no contest of the county on a recap sheet read here)"
        elif len(rest) == 1:
            left = sorted((db_words.get(c, set()) | ({alpha[x] for x in lets} if not named else set())) - set(mine.values()))
            if len(left) == 1:
                mine[rest[0]] = left[0]
                how = "recap sheets, the last letter by elimination"
            else:
                how = "recap sheets; one letter not known"
        else:
            how = "recap sheets" if not rest else ("recap sheets; some letters not known" if mine else "not known (districts named, no recap sheet read)")
        letter_word[c] = mine
        numbering[c] = {"how": how, "letters": {L_: mine.get(L_) for L_ in lets}}
    for p in pre:
        p["com_n"] = letter_word.get(p["county"], {}).get(p["letter"]) if p["letter"] else None
    unknown = sorted(f"{cname[c]} {L_}" for c, v in numbering.items() for L_, w in v["letters"].items() if w is None)
    permuted = sorted(cname[c] for c, v in numbering.items() if any(w and w.isdigit() and w != str(i + 1) for i, (L_, w) in enumerate(sorted(v["letters"].items()))))
    by_how = collections.Counter(v["how"] for v in numbering.values())
    say(f"      magisterial districts: {len(set(ev['2026 primary']) | set(ev['2022 general'])):,} counties' recap sheets show which district a letter is; "
        + "; ".join(f"{n} counties by {h}" for h, n in sorted(by_how.items(), key=lambda x: -x[1]))
        + f"; letters not in alphabet order in {', '.join(permuted) or 'none'}"
        + (f"; not known: {', '.join(unknown)}" if unknown else "") + (f"; conflicting pages: {', '.join(conflicts)}" if conflicts else "")
        + (f"; 2022 and 2026 differ: {', '.join(years_differ)}" if years_differ else "")
        + f"; House districts on the 2026 recap sheets: {house_ok:,} agree" + (f", {len(house_bad)} do not ({', '.join(house_bad[:4])})" if house_bad else ""))
    if len(house_bad) > 3:
        raise GeoError("    the recap sheets disagree with the report's House districts more than a stray page can explain; stopping")
    beyond = sorted(f"{cname[c]} {w}" for c, ws in db_words.items() if c != JEFFERSON for w in ws if w not in set(letter_word.get(c, {}).values()))

    # Lexington-Fayette's own table: council districts, and a check of its magisterial districts
    fay_bad, fay_council = [], 0
    for p in pre:
        p["ward_ids"] = []
        if p["county"] == FAYETTE:
            r = lfucg_by.get(p["code"])
            if r is None:
                continue
            if str(r.get("MAGISTERIAL") or "").strip() and str(int(float(r["MAGISTERIAL"]))) != p["com_n"]:
                fay_bad.append(p["id"])
            if r.get("COUNCIL") not in (None, ""):
                p["ward_ids"] = [f"{LEXINGTON}|{int(float(r['COUNCIL']))}"]
                fay_council += 1
        elif p["county"] == JEFFERSON:
            r = lojic_by.get(p["code"])
            if r is not None and r.get("COUNDIST") not in (None, ""):
                p["ward_ids"] = [f"{METRO}|{int(float(r['COUNDIST']))}"]
    jef_n = sum(1 for p in pre if p["county"] == JEFFERSON)
    jef_council = sum(1 for p in pre if p["county"] == JEFFERSON and p["ward_ids"])
    jef_check = sum(1 for p in pre if p["county"] == JEFFERSON and p["code"] in lojic_by and p.get("house")
                    and str(lojic_by[p["code"]]["LEGISDIST"]) == p["house"] and str(lojic_by[p["code"]]["SENDIST"]) == p["senate"])
    say(f"      council districts: Louisville Metro {jef_council} of {jef_n} Jefferson precincts from LOJIC's table (whose House and Senate districts agree with "
        f"the report at {jef_check}); Lexington-Fayette {fay_council} of {sum(1 for p in pre if p['county'] == FAYETTE)} from the Urban County Government's "
        f"(whose magisterial districts differ from those read here at {len(fay_bad)})")
    if fay_bad:
        raise GeoError(f"    Fayette County: the Urban County Government's magisterial districts differ from those read here at {fay_bad[:5]}; stopping")

    # the fiscal courts: commission counties (three commissioners, elected by the whole county) and justice of the peace counties
    kinds_of = collections.defaultdict(set)
    dists_of = collections.defaultdict(set)
    for rid, level, kind, jur, jid, district, _ci in info["races"]:
        if level == "county" and kind in ("county_commissioner", "magistrate"):
            kinds_of[jid].add(kind)
            if kind == "county_commissioner" and district:
                dists_of[jid].add(str(district))
    plans = {}
    for c in sorted(county_short):
        words = sorted({w for w in letter_word.get(c, {}).values() if w}, key=G.natkey)
        if "county_commissioner" in kinds_of[c] or c == JEFFERSON:
            plans[c] = {"plan": 2, "districts": sorted(dists_of[c], key=G.natkey) or words,
                        "commissioners_elected": "by the voters of the whole county, one from each district (Kentucky Constitution, section 144; KRS 67.060)"}
        else:
            plans[c] = {"plan": 3, "districts": words, "magistrates_elected": "each by the voters of their own magisterial district"}
        if c in numbering:
            plans[c]["magisterial_districts"] = numbering[c]
    for p in pre:
        p["com"] = f"{p['county']}|{p['com_n']}, {COM_WORDS}" if p["com_n"] else None
        p["swcd"] = f"{STATE}-X-SWCD-{p['county']}"

    # ---- cities: the Census Bureau's 2025 places, laid over the precincts; the metro government is all of Jefferson County
    places = sorted(I.read_shapefile(path("tl_2025_21_place.zip"), lambda r: r["STATEFP"] == FIPS and r["FUNCSTAT"] == "A" and r["CLASSFP"] == "C1"),
                    key=lambda x: x[0]["PLACEFP"])
    pkeys = [f"{STATE}-M-{r['PLACEFP']}" for r, _ in places]
    pname = {k: names.get(("mcd", k)) or r["NAMELSAD"] for k, (r, _) in zip(pkeys, places)}
    pname[METRO] = names.get(("mcd", METRO)) or METRO_NAME
    ov_pl = overlay_cached("places", pre_rings, I.rings_xy([r for _a, r in places]), stamp(ppath, path("tl_2025_21_place.zip")), refresh, say)
    several = whole = 0
    for p, got in zip(pre, ov_pl):
        got = sorted(((pkeys[d], s, t) for d, s, t in got), key=lambda g: (-g[1], g[0]))
        thick = [(k, s) for k, s, t in got if t]
        if p["county"] == JEFFERSON:
            p["mcd"] = METRO
            p["mcd_all"] = [METRO] + [k for k, _s in thick] if thick else None
            p["mcd_pct"] = [100.0] + [round(100 * s, 1) for _k, s in thick] if thick else None
        else:
            if len(thick) == 1 and thick[0][1] >= WHOLE_SHARE:
                p["mcd"] = thick[0][0]
                whole += 1
            else:
                p["mcd"] = None
            p["mcd_all"] = [k for k, _s in thick] if (thick and p["mcd"] is None) or len(thick) > 1 else None
            p["mcd_pct"] = [round(100 * s, 1) for _k, s in thick] if p["mcd_all"] else None
        several += len(thick) > 1
    say(f"      cities: {len(places)} from the Census Bureau's 2025 places; {whole:,} precincts outside Jefferson County lie wholly in one city, "
        f"{sum(1 for p in pre if p['county'] != JEFFERSON and p['mcd'] is None and p['mcd_all']):,} partly in one or more, {several:,} reach more than one; "
        f"every Jefferson County precinct is in the metro government")

    # ---- school districts
    sch_rows = [(r, rings, f"{STATE}-S-{r['UNSDLEA']}") for r, rings in I.read_shapefile(path("tl_2025_21_unsd.zip"), lambda r: r["STATEFP"] == FIPS)]
    sch_rows += [(r, rings, f"{STATE}-S-{r['ELSDLEA']}") for r, rings in I.read_shapefile(path("tl_2025_21_elsd.zip"), lambda r: r["STATEFP"] == FIPS)]
    sid_name = {k: names.get(("school", k)) or r["NAME"] for r, _x, k in sch_rows}
    schkeys, schpolys, scharcs, schsides, _sr, schodd = fabric_keys([(k, rings) for _r, rings, k in sch_rows])
    schfine, _ = G.simplify_arcs(scharcs, _sr, G.TOL_SCHOOL)
    schdistricts = [[G.ring_xy(refs, schfine) for refs in rings] for rings in _sr]
    o_sch = overlay_cached("school", pre_rings, schdistricts, stamp(ppath, path("tl_2025_21_unsd.zip"), path("tl_2025_21_elsd.zip")) + "s", refresh, say)
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
        raise GeoError("    area check: the precinct layer and the Census Bureau do not have the same 120 counties; stopping")
    worst = max(clist, key=lambda c: abs(area_p[c] / area_c[c] - 1))
    worst_pct = 100 * (area_p[worst] / area_c[worst] - 1)
    state_pct = 100 * (sum(area_p.values()) / sum(area_c.values()) - 1)
    off = [c for c in clist if abs(area_p[c] / area_c[c] - 1) > AREA_SLACK]
    if off:
        raise GeoError(f"    area check: the precincts of {', '.join(cname[c] for c in off[:5])} do not cover the county the Census Bureau draws "
                       f"({', '.join(f'{100 * (area_p[c] / area_c[c] - 1):+.1f}%' for c in off[:5])}); stopping")
    say(f"      area check: the precincts cover {100 + state_pct:.3f}% of the Census Bureau's Kentucky (its 1:500,000 county file); the county furthest off is "
        f"{cname[worst]} ({worst_pct:+.2f}%)")

    vals = {"county": [p["county"] for p in pre], "ward": [p["ward_ids"][0] if p["ward_ids"] else None for p in pre], "com": [p["com"] for p in pre],
            "house": [p["house"] for p in pre], "senate": [p["senate"] for p in pre], "cd": [p["cd"] for p in pre], "judicial": [p["judicial"] for p in pre],
            "swcd": [p["swcd"] for p in pre]}
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

    def layer(kind, geoms, qlines, tol, props, source, zoom=None, keep_order=False):
        gl = []
        for v, polys_ in (geoms if keep_order else sorted(geoms, key=lambda x: G.natkey(x[0]))):
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

    PCT, RPT, LRC, CENSUS, LOJ, LFU, LAW = ("ky-sbe-voting-precincts", "ky-sbe-voter-registration-statistics-by-precinct", "ky-lrc-legislative-districts",
                                            "ky-census-tiger-2025", "ky-lojic-precincts", "ky-lfucg-voting-precincts", "ky-krs-judicial-districts-and-circuits")
    jd_counties = collections.defaultdict(list)
    for f, j in jd_of.items():
        jd_counties[j].append(cname[f])
    layer("state", *own(None, G.TOL_WIDE, [[STATE] * len(pre)]), G.TOL_WIDE, lambda v: {"id": STATE, "name": STATE_NAME, "j": FIPS, "d": None}, PCT)
    layer("county", *own("county", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": cname[v], "j": v, "d": None, "fips": v}, PCT)
    layer("cd", *own("cd", G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"Congressional District {v}", "j": None, "d": v, "race": f"2026-{STATE}-H{int(v):02d}"}, f"{PCT}; which district, from {RPT}")
    layer("senate", *own("senate", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": names.get(("senate", v)) or f"Senate District {v}", "j": v, "d": v},
          f"{PCT}; which district, from {RPT}")
    layer("house", *own("house", G.TOL_WIDE), G.TOL_WIDE, lambda v: {"id": v, "name": names.get(("house", v)) or f"House District {v}", "j": v, "d": v},
          f"{PCT}; which district, from {RPT}")
    layer("judicial", *own("judicial", G.TOL_WIDE), G.TOL_WIDE,
          lambda v: {"id": v, "name": f"{G.ordinal(v[5:])} Judicial District", "j": v, "d": v[5:], "counties": sorted(jd_counties[v])}, f"{PCT}; which counties, from {LAW}")
    # cities first, then the metro government (all of Jefferson County): a point in a home rule city is in that city
    ckeys, _cp, carcs, csides, _cr, codd = fabric_keys([(k, rings) for k, (_r0, rings) in zip(pkeys, places)])
    cg, cq, _l, _r = G.build_layer(carcs, csides, [ckeys], TOL_MCD)
    mg, mq, _l, _r = G.build_layer(arcs, sides, [[METRO if p["county"] == JEFFERSON else None for p in pre]], TOL_MCD)
    shift = len(cq)
    mcd_geoms = (sorted(cg, key=lambda x: G.natkey(x[0]))
                 + [(v, [[[r + shift if r >= 0 else ~(~r + shift) for r in ring] for ring in poly] for poly in polys_]) for v, polys_ in mg])
    mkind = lambda v: "metro government" if v == METRO else "urban county" if v == LEXINGTON else "city"      # noqa: E731
    layer("mcd", mcd_geoms, cq + mq, TOL_MCD, lambda v: {"id": v, "name": pname[v], "j": v, "d": None, "t": mkind(v)},
          f"{CENSUS} (cities, first in the file); {PCT} (the metro government: all of Jefferson County)", zoom=MCD_ZOOM, keep_order=True)
    ward_name = lambda v: {"id": v, "name": f"{pname[v.split('|')[0]]}, Council District {v.split('|')[1]}", "j": v.split("|")[0], "d": v.split("|")[1]}      # noqa: E731
    layer("ward", *own("ward", G.TOL_LOCAL), G.TOL_LOCAL, ward_name, f"{PCT}; which district, from {LOJ} and {LFU}")
    layer("com", *own("com", G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v.split('|')[0]]}, {mag_name(v.split('|')[1].split(',')[0])}", "j": v.split("|")[0],
                     "d": v.split("|")[1].split(",")[0]}, f"{PCT}; which district, from the precinct codes' letters as {RPT} groups them")
    layer("swcd", *own("swcd", G.TOL_LOCAL), G.TOL_LOCAL,
          lambda v: {"id": v, "name": f"{cname[v[-5:]]} soil and water conservation district", "j": v[-5:], "d": None}, PCT)
    sprops = lambda v: {"id": v, "name": sid_name[v], "j": v, "d": None}      # noqa: E731
    sg, sq, _l, _r = G.build_layer(scharcs, schsides, [schkeys], G.TOL_LOCAL)
    layer("school", sg, sq, G.TOL_LOCAL, sprops, CENSUS)
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
        geoms, used_names = [], {"mcd": {}, "ward": {}, "com": {}, "school": {}, "swcd": {}, "judicial": {}}
        for i in idxs:
            p = pre[i]
            pr = {"name": f"{p['pname']} ({p['code']})" if p["pname"] else f"Precinct {p['code']}", "county": county, "precinct": p["code"],
                  "house": p["house"], "senate": p["senate"], "cd": p["cd"], "judicial": p["judicial"], "circuit": p["circuit"], "sc": p["sc"],
                  "swcd": p["swcd"], "school": p["school"], "listed_2026": p["listed"]}
            if p["mcd"]:
                pr["mcd"] = p["mcd"]
                used_names["mcd"][p["mcd"]] = pname[p["mcd"]]
            if p["mcd_all"]:
                pr["mcd_all"], pr["mcd_pct"] = p["mcd_all"], p["mcd_pct"]
                for k in p["mcd_all"]:
                    used_names["mcd"][k] = pname[k]
            if p["com"]:
                pr["com"] = p["com"]
                used_names["com"][p["com"]] = mag_name(p["com_n"])
            if p["ward_ids"]:
                pr["ward"] = p["ward_ids"]
                for w in p["ward_ids"]:
                    used_names["ward"][w] = f"Council District {w.split('|')[1]}"
            used_names["swcd"][p["swcd"]] = f"{cname[county]} soil and water conservation district"
            used_names["judicial"][p["judicial"]] = f"{G.ordinal(p['judicial'][5:])} Judicial District"
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

    polls = polling_places(pre, cname, county_key, cbox, put, say, refresh)
    if os.path.exists(READER_JS):
        shutil.copyfile(READER_JS, os.path.join(out, "reader.js"))
        files["reader.js"] = {"bytes": os.path.getsize(os.path.join(out, "reader.js")), "sha256": G.sha_file(os.path.join(out, "reader.js"))}

    said = {"circuit": {p["circuit"] for p in pre}, "sc": {p["sc"] for p in pre}}
    check = check_ids(info, shape_ids, said, plans)
    check["districts_differ_from_the_lrc_lines"] = leg_diff
    check["supreme_court_district_differs_from_its_county"] = sc_fixed
    check["precincts_on_the_report_not_on_the_map"] = rep_only
    check["precincts_on_the_map_not_on_the_report"] = sorted(p["id"] for p in pre if not p["listed"])
    check["magisterial_districts_read_from_the_recap_sheets"] = {"counties_with_a_contest_read": len(set(ev["2026 primary"]) | set(ev["2022 general"])),
                                                                 "letters_not_in_alphabet_order": permuted, "letters_not_known": unknown,
                                                                 "conflicting_pages": conflicts, "2022_and_2026_differ": years_differ}
    check["house_districts_against_the_2026_primary_recaps"] = {"agree": house_ok, "disagree": house_bad}
    check["magistrate_districts_on_the_ballot_with_no_letter"] = beyond
    check["not_drawn"] = [
        {"what": "school board member districts inside a school district", "why": "elected by division inside a county school district (KRS 160.210); no statewide source has the lines, so the page lists every seat of the district"},
        {"what": "Jefferson County's justice of the peace and commissioner districts", "why": "its precinct letters follow House districts, not magisterial ones; LOJIC draws the three commissioner districts (A, B, C), whose commissioners the whole county elects, and no source read here says which justice of the peace district is which"},
        {"what": "city wards and council districts outside Louisville and Lexington", "why": "each city keeps its own; no statewide source has them"}]
    with open(os.path.join(out, "layers", "state.json"), encoding="utf-8") as fh:
        state_doc = json.load(fh)
    mtime = lambda p: dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")      # noqa: E731
    index = {
        "v": G.VERSION, "state": STATE, "election": ELECTION, "built": today, "unit": "precinct",
        "transform": {"scale": [G.SCALE, G.SCALE], "translate": [G.ORIGIN[0], G.ORIGIN[1]]}, "bbox": state_doc.get("bbox"),
        "sources": [
            dict({"id": PCT, "agency": "Kentucky State Board of Elections, with the Division of Geographic Information and each county board of elections",
                  "title": "SBE Voting Precinct Boundaries (VTD_Boundaries)", "about": about.get("summary"),
                  "url": "https://kygisserver.ky.gov/arcgis/rest/services/Temp_Services/SBE_VotingPrecinctboundaries/FeatureServer", "service": PCT_SERVICE,
                  "fetched": pdoc.get("fetched"), "sha256": G.sha_file(ppath), "rows": len(pre), "use": about.get("use")}, **edited),
            {"id": RPT, "agency": "Kentucky State Board of Elections", "title": f"Voter Registration Statistics Report by precinct, {rmonth}",
             "about": "Each precinct's congressional, Senate, House and Supreme Court district (its C-S-LD-SC cell), and the precincts grouped by "
                      "magisterial district under their code's letter. The voter counts are not read.",
             "url": rurl, "page": STATS_PAGE, "fetched": mtime(rpath), "sha256": G.sha_file(rpath), "rows": on_report + len(rep_only)},
            {"id": "ky-sbe-recap-sheets", "agency": "Kentucky State Board of Elections", "title": "2026 Primary and 2022 General Recap Sheets (one per county)",
             "about": "Read for which magisterial district's contests (magistrate, constable) each precinct's page lists, so that each precinct letter is given "
                      "its district's number or name, and as a check on the House districts. Candidates' names and votes are not read. Sheets that are "
                      "scanned pages, with no text, add nothing.",
             "url": RECAP_PAGE, "url_2022": RECAPS["2022 general"][1],
             "files": {w: len(v) for w, v in recap_files.items()},
             "sha256_of_the_set": hashlib.sha256("".join(G.sha_file(p) for v in recap_files.values() for p in v).encode()).hexdigest()},
            {"id": LRC, "agency": "Kentucky Legislative Research Commission; published on the Commonwealth's GIS server",
             "title": "Kentucky House, Senate and Congressional Districts (Ky_Legislative_Districts_WGS84WM)",
             "about": "Read to check the report's districts, and for the districts of the few precincts the report does not list; the lines drawn are the precincts'.",
             "url": LEG_SERVICE, "fetched": legdocs["house"].get("fetched"),
             "sha256": hashlib.sha256("".join(G.sha_file(path(f"lrc_{k}_districts_geometry_4326.json.gz")) for k in ("house", "senate", "cd")).encode()).hexdigest()},
            {"id": LOJ, "agency": "Louisville/Jefferson County Information Consortium (LOJIC)", "title": "Political Districts, layer Precincts (attributes only)",
             "about": "Each Jefferson County precinct's Metro Council district.", "url": LOJIC_SERVICE, "fetched": lojic.get("fetched"),
             "sha256": G.sha_file(path("lojic_precincts_attributes.json")), "rows": len(lojic["rows"])},
            {"id": LFU, "agency": "Lexington-Fayette Urban County Government", "title": "Voting Precinct (attributes only)",
             "about": "Each Fayette County precinct's Urban County Council district, and its magisterial district as a check.", "url": LFUCG_SERVICE,
             "fetched": lfucg.get("fetched"), "sha256": G.sha_file(path("lfucg_voting_precincts_attributes.json")), "rows": len(lfucg["rows"])},
            {"id": CENSUS, "agency": "U.S. Census Bureau", "title": "TIGER/Line Shapefiles 2025: places, unified and elementary school districts, Kentucky",
             "about": "City limits (the active incorporated places and Lexington-Fayette urban county) and school districts as the Bureau had them on January 1, 2025.",
             "url": PLACE_URL, "school_urls": [UNSD_URL, ELSD_URL], "fetched": mtime(path("tl_2025_21_place.zip")),
             "sha256": G.sha_file(path("tl_2025_21_place.zip")), "school_sha256": [G.sha_file(path("tl_2025_21_unsd.zip")), G.sha_file(path("tl_2025_21_elsd.zip"))]},
            {"id": LAW, "agency": "Kentucky General Assembly (Legislative Research Commission)", "title": "KRS 24A.030 (judicial districts) and KRS 23A.020 (judicial circuits)",
             "url": jsrc["districts"][1], "circuits_url": jsrc["circuits"][1], "sha256": G.sha_file(jsrc["districts"][0]), "circuits_sha256": G.sha_file(jsrc["circuits"][0])}],
        "notes": {
            "lines": f"Every line is the State Board of Elections' precinct layer's, generalised by at most {G.TOL_PRECINCT} metres and set on a grid of 0.00001 "
                     "degree (about a metre). A point within a few metres of a line can fall on either side of it.",
            "precincts": "The precinct layer is the State Board of Elections' compilation of the county boards' own precinct files; the publisher says it is "
                         "current through the November 3, 2026 general election, that the county's own precinct records control where they differ, and that "
                         "the county clerk is the authority on which precinct an address is in.",
            "districts": "A precinct's congressional, Senate and House district and its Supreme Court district are the State Board of Elections' own word "
                         "for it (its monthly registration report by precinct). A precinct may not cross any of those lines, or a justice of the peace or "
                         "commissioner district's (KRS 117.055), so each is exact for the whole precinct.",
            "magisterial": "A precinct code's letter is its magisterial district, as the State Board's report groups them. Which district a letter is "
                           "was read from the State Board's 2026 primary and 2022 general recap sheets, whose precinct pages name the magistrate's and "
                           "constable's contests on that precinct's ballot: usually A is the first district and B the second, but not in every county. A "
                           "letter no sheet shows takes the alphabet's number only where every letter the sheets show follows it (supervisor_plans gives, "
                           "county by county, each letter's district and how it was read; a letter not known has no com). Lexington-Fayette's own precinct "
                           "table agrees with every Fayette precinct. Magistrates (justices of the peace) and constables are elected by the voters "
                           "of their district. In a county whose fiscal court is three commissioners, the commissioner districts are the same lines (KRS "
                           "67.060), but each commissioner is elected by the whole county; supervisor_plans says which counties those are. Jefferson "
                           "County's letters follow its House districts and give no magisterial district.",
            "places": "Cities are the Census Bureau's 2025 places. A precinct lying wholly in one city names it (mcd); one that reaches into cities lists them "
                      "(mcd_all, with each one's share of the precinct's area), and a precinct partly outside every city names no place of its own: the mcd "
                      "layer answers for a point, cities first. In Jefferson County a voter in a city is a voter of the government too: every precinct "
                      "there names the Louisville/Jefferson County metro government, which is all of the county, and the home rule cities it reaches.",
            "wards": "Council districts are drawn for Louisville Metro (LOJIC's precinct table) and Lexington-Fayette (the Urban County Government's). Other "
                     "cities' wards are not drawn.",
            "judicial": "Judicial districts and circuits are whole counties (KRS 24A.030, 23A.020). The judicial layer draws the districts; a precinct also "
                        "names its circuit, and its Supreme Court district, which is also its Court of Appeals district (KRS 22A.020).",
            "school": "School district lines are the Census Bureau's 2025. Which districts a precinct lies in is analysis, not an official list: a district "
                      f"counts when its piece of the precinct is at least {G.SCHOOL_THICK:.0f} metres thick somewhere; school_pct is each district's share "
                      "of the precinct's area (land and water, not voters). An independent district's voters elect its board and not the county "
                      "district's (KRS 160.210).",
            "soil": "Every soil and water conservation supervisor contest on the list is filed under its county; the swcd layer draws the county.",
            "authority": "For which precinct an address votes in, and where, the county clerk and the State Board of Elections' GoVoteKY are the authority.",
            "precinct_ids": "A precinct's id is its county's five-digit code and its precinct code (21001A102), as the State Board writes it. listed_2026 is "
                            f"false for the {sum(1 for p in pre if not p['listed'])} precincts of the map that the State Board's {rmonth} report does not list "
                            "(a military reservation, a lake, a precinct since renamed).",
        },
        "format": {
            "files": "Every file is TopoJSON on one grid (transform above): arcs are delta-encoded lines; a shape's arcs name the lines of its rings, a "
                     "negative number n meaning line ~n backwards; outer rings run counter-clockwise, holes clockwise.",
            "county_files": "precincts/<county>.json, object 'precincts': one shape per precinct. arcMask[i] has bit k set when line i is an outline of "
                            "arc_kinds[k]; arcSides[2i] and arcSides[2i+1] are the precincts on the right and left of line i (-1: a precinct in another "
                            "county's file, or one just across a hairline gap; -2: outside Kentucky); names gives the names of the places the file's "
                            "precincts lie in.",
            "boxes": "boxes[county] holds four whole numbers a precinct, in the file's order: west, south, east, north in steps of box_step degrees from "
                     "the transform's translate, rounded outwards. A point is tried against every precinct whose box (widened by half a step) holds it.",
            "precinct_properties": {
                "name": "the precinct's name (Clark Hill (D102)): its name and code in the State Board's layer",
                "county": "county id", "precinct": "the precinct's code (a letter and three digits)",
                "mcd": "the city the precinct lies wholly in, or in Jefferson County the metro government (absent where it lies partly outside every city)",
                "mcd_all": "list: every city the precinct reaches (in Jefferson County the metro government first), largest share first",
                "mcd_pct": "list, with mcd_all: each place's share of the precinct's area, in percent",
                "ward": "list: the council district the precinct lies in (Louisville Metro Council or Lexington-Fayette Urban County Council)",
                "com": "magisterial district (the justice of the peace district; magistrates and constables are elected by it; absent where the letter's district is not known)",
                "house": "House district", "senate": "Senate district", "cd": "congressional district",
                "judicial": "judicial district (district judges)",
                "circuit": "judicial circuit (circuit judges and Commonwealth's attorneys; KY-JC1 to KY-JC57)",
                "sc": "supreme court district (also the Court of Appeals district: 1 to 7, KRS 21A.010 and 22A.020)",
                "swcd": "soil and water conservation district (the county's)",
                "listed_2026": "whether the State Board's newest registration report by precinct lists the precinct",
                "school": "list: the school districts the precinct lies in, largest share first",
                "school_pct": "list, when the precinct is in more than one: each district's share of its area, in percent",
                "school_out": "percent of the precinct's area that lies in no school district (given from 3 percent up)",
                "school_edge": "list: neighbouring districts that only brush the precinct along a line (try them too when placing a point)",
                "c": "a point inside the precinct's largest piece, for a label: [longitude, latitude]"},
            "ids": {"every layer": "a shape's properties j and d are the jurisdiction id and the district its races carry on the ballot pages",
                    "state": "KY (j is 21)", "county": "the county's five-digit code (21001)",
                    "mcd": "KY-M- and the Census Bureau's place code (KY-M-00298); KY-M-48003 the metro government; properties.t says what it is",
                    "ward": "<city>|<district as the council race words it> (KY-M-48003|1, KY-M-46027|12)",
                    "com": f"<county>|<district>, {COM_WORDS} (21001|4, {COM_WORDS})",
                    "house": "the district (57)", "senate": "the district (20)", "cd": "the district (1); properties.race is the race for Congress",
                    "judicial": "KY-JD and the district's number (KY-JD29)", "swcd": "KY-X-SWCD- and the county's code; j is the county",
                    "school": "KY-S- and the Bureau's five-digit district code (KY-S-00030)"},
        },
        "counties": counties, "box_step": G.BOX_STEP * G.SCALE, "boxes": boxes,
        "layers": layers,
        "school": {"files": "school/<id>.json", "ids": sorted(schkeys, key=G.natkey), "bytes": school_bytes, "tolerance_m": G.TOL_SCHOOL},
        "tolerance_m": {"precincts": G.TOL_PRECINCT, "school": G.TOL_SCHOOL},
        "arc_kinds": ARC_KINDS,
        "supervisor_plans": plans,
        "polling_places": polls,
        "counts": {"precincts": len(pre), "counties": len(counties), "on_the_report": on_report, "split_between_school_districts": split,
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
    say(f"      ids against the ballot database: {check['matched']:,} of {check['races']:,} Kentucky races have a shape or a precinct word"
        + (f"; {sum(e['races'] for e in check['no_shape'])} races in {len(check['no_shape'])} kinds of place without one (listed in index.json)" if check["no_shape"] else ""))
    say(f"    Kentucky ballot map: built in {time.time() - t0:.0f} s")
    return index


# ---------------------------------------------------------------- the self-test: what a device does, done here

# name, longitude, latitude, what the precinct there must say, and the place the mcd layer must give the point (None:
# outside every city). The precinct, its House, Senate and congressional district and the city are the Commonwealth's
# own boundary service's answer for those coordinates (LocateVoterBoundaries on kygisserver.ky.gov, asked 2026-10-03),
# an answer that owes nothing to the files tested here; the judicial district is the county's (KRS 24A.030).
# Where the service said the point lies within 60 feet of the precinct's line, the precinct's id is not asked ("id" left
# out); where it said so of the city's line, the city is not asked ("skip"). Louisville's answer (the Bureau's metro
# "balance") is the metro government here.
TEST_POINTS = [
    ("the State Capitol, Frankfort", -84.8753, 38.1867, {"id": "21073A103", "county": "21073", "house": "57", "senate": "20", "cd": "1"}, "KY-M-28900"),
    ("Louisville Metro Hall", -85.7597, 38.254, {"county": "21111", "house": "43", "senate": "33", "cd": "3"}, "KY-M-48003"),
    ("St. Matthews City Hall, Jefferson County", -85.639, 38.253, {"county": "21111", "house": "34", "senate": "26", "cd": "3"}, "skip"),
    ("Lexington's government center", -84.4973, 38.0446, {"county": "21067", "house": "75", "senate": "13", "cd": "6"}, "KY-M-46027"),
    ("Bowling Green, Fountain Square", -86.4436, 36.9947, {"id": "21227B101", "county": "21227", "house": "20", "senate": "9", "cd": "2"}, "KY-M-08902"),
    ("Owensboro riverfront", -87.1112, 37.7745, {"id": "21059B101", "county": "21059", "house": "13", "senate": "8", "cd": "2"}, "KY-M-58620"),
    ("Paducah, Broadway at 2nd", -88.5982, 37.087, {"id": "21145A119", "county": "21145", "house": "1", "senate": "2", "cd": "1"}, "KY-M-58836"),
    ("Covington city building", -84.51, 39.0837, {"county": "21117", "house": "65", "senate": "24", "cd": "4"}, "KY-M-17848"),
    ("Pikeville, Main Street", -82.5188, 37.4793, {"id": "21195B101", "county": "21195", "house": "95", "senate": "31", "cd": "5"}, "KY-M-60852"),
    ("Hazard, Main Street", -83.1932, 37.2498, {"id": "21193B110", "county": "21193", "house": "84", "senate": "30", "cd": "5"}, "KY-M-35362"),
    ("a field in rural Adair County", -85.2, 37.05, {"id": "21001B104", "county": "21001", "house": "21", "senate": "16", "cd": "1"}, None),
    ("Murray, court square", -88.315, 36.6103, {"id": "21035B101", "county": "21035", "house": "5", "senate": "1", "cd": "1"}, "KY-M-54642"),
    ("Richmond, Madison County courthouse", -84.2946, 37.7479, {"id": "21151C114", "county": "21151", "house": "91", "senate": "34", "cd": "6"}, "KY-M-65226"),
    ("Florence, Boone County", -84.6266, 38.999, {"id": "21015C124", "county": "21015", "house": "69", "senate": "11", "cd": "4"}, "KY-M-27982"),
    ("Elizabethtown, Hardin County", -85.8591, 37.6939, {"id": "21093E001", "county": "21093", "house": "25", "senate": "10", "cd": "2"}, "KY-M-24274"),
    ("Ashland, Boyd County", -82.6379, 38.4784, {"id": "21019B101", "county": "21019", "house": "100", "senate": "18", "cd": "5"}, "KY-M-02368"),
]
LINE_POINTS = [("the Franklin-Woodford county line in the Kentucky River", -84.8651, 38.1241, ("21073", "21239")),
               ("the Jefferson-Oldham county line on I-71", -85.5150, 38.3480, ("21111", "21185"))]
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
    check(len(index["counties"]) == 120, "there are not 120 county files")
    check(bad_side == 0, f"{bad_side} rings use a line whose sides do not name them")
    check(bad_mask == 0, f"{bad_mask} outline marks disagree with the precincts on the two sides of a line")
    check(len(layer_ids.get("senate", ())) == 38 and len(layer_ids.get("house", ())) == 100 and len(layer_ids.get("cd", ())) == 6
          and len(layer_ids.get("judicial", ())) == 59 and len(layer_ids.get("county", ())) == 120,
          "there are not 38 Senate, 100 House and 6 congressional districts, 59 judicial districts (KRS 24A.030) and 120 counties")
    check(layer_ids.get("ward", set()) >= {f"{METRO}|{n}" for n in range(1, 27)} | {f"{LEXINGTON}|{n}" for n in range(1, 13)},
          "the ward layer does not have Louisville Metro's 26 and Lexington-Fayette's 12 council districts")
    say(f"      self-test: {len(index['counties'])} county files, {total:,} precincts, every one with a shape; {lines_seen:,} lines "
        f"({edge_lines:,} on a file's edge), sides and outline marks all in order; {len(index['layers'])} layers, {shapes_seen:,} shapes and "
        f"{len(index['school']['ids'])} school district files, every one with an outline")

    # 2. every precinct is found again from a point inside it; every id it carries is a shape of that layer; the layers agree with it
    wrong, tested, agree, skipped, no_shape = 0, 0, 0, 0, collections.Counter()
    disagree, asked = collections.defaultdict(list), collections.Counter()
    school, place = collections.Counter(), collections.Counter()
    layer_for = {"county": "county", "house": "house", "senate": "senate", "cd": "cd", "judicial": "judicial", "com": "com", "swcd": "swcd", "ward": "ward"}
    tol_of = {l["kind"]: l["tolerance_m"] for l in index["layers"]}
    said = collections.defaultdict(set)
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
            said["circuit"].add(pr["circuit"])
            said["sc"].add(pr["sc"])
            for prop, kind in list(layer_for.items()) + [("mcd", "mcd"), ("mcd_all", "mcd"), ("school", "school")]:
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
            for prop, kind in layer_for.items():
                if kind not in layer_ids or (i % 3 and kind not in ("com", "ward")):
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
    check(wrong <= 3, f"{wrong} of {tested} precincts are not found again from a point inside them")
    check(not sum(no_shape.values()), f"precincts carry ids that are no shape of their layer: {dict(no_shape)}")
    for kind, bad in disagree.items():
        check(len(bad) <= max(2, int(LAYER_SLACK * asked[kind])), f"layer {kind}: {len(bad)} of {asked[kind]} shapes disagree with the precinct at a point well inside it, e.g. {bad[:3]}")
    check(school["in none"] <= 0.005 * tested, f"{school['in none']} precincts' own points fall in no school district though the precinct is said to lie in one")
    check(place["a place the precinct does not name"] + place["no place, in a precinct that names one"] <= 0.01 * tested, f"the place at a precinct's own point: {dict(place)}")
    check(said["circuit"] == {f"KY-JC{n}" for n in range(1, 58)} and said["sc"] == {str(n) for n in range(1, 8)},
          "the precincts do not name the 57 circuits and 7 Supreme Court districts")
    say(f"      self-test: {tested - wrong:,} of {tested:,} precincts found again from a point inside them; every id a precinct carries is a shape; layers agree "
        f"at {agree:,} of {sum(asked.values()):,} points ({skipped} too near a line to ask" + "".join(f"; {kind}: {len(bad)} of {asked[kind]} differ" for kind, bad in sorted(disagree.items()))
        + "); school district at each precinct's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(school.items(), key=lambda x: -x[1]))
        + "; city at each precinct's point: " + "; ".join(f"{n:,} {what}" for what, n in sorted(place.items(), key=lambda x: -x[1])))

    # 3. known points
    for name, lon, lat, want, mcd in TEST_POINTS:
        found, _near = locate(files, lon, lat)
        if not check(found is not None, f"{name}: in no precinct"):
            continue
        pr = found["geometry"]["properties"]
        got = {k: (found["geometry"]["id"] if k == "id" else pr.get(k)) for k in want}
        ok = check(got == want, f"{name}: lands in {got}, not {want}")
        shape, _edge = G.shape_at(files, "mcd", lon, lat)
        if mcd != "skip":
            ok &= check((shape is None and mcd is None) or (shape is not None and shape["id"] == mcd), f"{name}: the mcd layer gives {shape and shape['id']}, not {mcd}")
        for prop, kind in layer_for.items():
            if kind in layer_ids and pr.get(prop) is not None and kind not in ("com", "ward"):
                shape2, _edge = G.shape_at(files, kind, lon, lat)
                mine = pr.get(prop)
                ok &= check(shape2 is not None and (shape2["id"] in mine if isinstance(mine, list) else shape2["id"] == mine),
                            f"{name}: layer {kind} gives {shape2 and shape2['id']}, the precinct says {mine}")
        say(f"      self-test: {name}: {'ok' if ok else 'FAIL'}: {pr['name']} ({found['geometry']['id']}), {shape and shape['properties']['name']}, "
            f"House {pr['house']}, Senate {pr['senate']}, CD {pr['cd']}, {pr['judicial']}, {pr['circuit']}, Supreme Court district {pr['sc']}"
            + (f", {pr['com'].split('|')[1]}" if pr.get("com") else "") + (f", ward {', '.join(w for w in pr['ward'])}" if pr.get("ward") else "")
            + f"; {found['edge']:.0f} m from the precinct's line")
    check(len(TEST_POINTS) >= 10, "fewer than ten known points were tested")

    # 4. county lines: the spot on one county's own drawing of the line nearest to a chosen point
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

    # 5. polling places say what they are, and name only precincts that are there
    polls = files.load("polling_places.json")
    check(polls.get("status") in ("waiting", "unchecked", "loaded"), "polling_places.json has no status")
    if polls.get("status") in ("unchecked", "loaded"):
        check(all(v in ids for p in polls["places"] for v in p["precincts"]) and all(0 <= i < len(polls["places"]) for i in polls["precinct"].values())
              and all(v in ids for v in list(polls["precinct"]) + list(polls["no_place"])) and not set(polls["precinct"]) & set(polls["no_place"]),
              "polling_places.json names a precinct or a place that is not there")
        check(not any(re.search(r"\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|[\w.+-]+@[\w-]+\.\w", json.dumps(p)) for p in polls["places"]), "polling_places.json carries something that reads like a phone number or an e-mail address")
        inside = 0
        for p in polls["places"]:
            if p.get("lonlat"):
                f3, _n = locate(files, p["lonlat"][0], p["lonlat"][1])
                inside += bool(f3) and f3["county"] in {county_of[v] for v in p["precincts"]}
        say(f"      self-test: polling places: {polls.get('status')}; {len(polls['places']):,} places, {sum(1 for p in polls['places'] if p.get('lonlat')):,} with a point "
            f"({inside:,} of them inside the county of a precinct that votes there); {len(polls['precinct']):,} precincts have one place, {len(polls['no_place']):,} several")
    else:
        say(f"      self-test: polling places: {polls.get('status')}")
    say("    self-test: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
    return not fails


def put_in_place(src, dst, say=print):
    """The tested folder becomes ballot_geo/ky/: the old one (if any) is moved aside first and removed after, so the
    page builder never finds a half-written folder."""
    old = dst.rstrip("\\/") + ".old"
    if os.path.isdir(old):
        shutil.rmtree(old)
    if os.path.isdir(dst):
        os.replace(dst, old)
    os.replace(src, dst)
    if os.path.isdir(old):
        shutil.rmtree(old)
    say(f"    put in place: {dst}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="The geography behind Kentucky's ballot map -> ballot_geo/ky/")
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
        raise SystemExit(f"    the self-test failed; the files stay in {where} and ballot_geo/ky/ is unchanged")
    if a.out is None:
        put_in_place(where, OUT)


if __name__ == "__main__":
    main()
