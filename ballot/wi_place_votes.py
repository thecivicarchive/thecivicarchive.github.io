"""
ballot/wi_place_votes.py - how each Wisconsin place voted in past partisan general elections, added up from the
Legislative Technology Services Bureau's ward tables of the Wisconsin Elections Commission's results, so a page can
show the record of a county, a city, village or town, or a legislative district without anyone labelling a candidate.
The Wisconsin twin of ballot/mn_place_votes.py; the output has the same shape (the Democratic count is "dem" here,
where Minnesota's is "dfl").

    python ballot/wi_place_votes.py               reads (or downloads) the tables, writes ballot/lean/wi_place_votes.json
    python ballot/wi_place_votes.py --refresh     asks for everything again even when the cached copies are fresh
    python ballot/wi_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/wi_place_votes.py --selftest    the arithmetic on a made-up table; downloads nothing

What it is, and is not
----------------------
For President and U.S. Senator in 2024, Governor and U.S. Senator in 2022, and President in 2020 (Wisconsin elected no
senator that year): the votes for the Democratic ticket, the Republican ticket, everyone else together (write-ins and
scattering included) and the total, for every county, every city, village and town, and, for the 2024 contests, every
state Senate and Assembly district of the 2024 plan (2023 Wisconsin Act 94), the lines the 2026 Legislature is elected
on. It is how the people of a place voted then. It is not a prediction, it says nothing about any candidate on a later
ballot or about any voter, and it turns no nonpartisan office into a partisan one. No database is opened for writing;
ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Where the numbers come from
---------------------------
The Wisconsin Legislature's open-data site (data-ltsb.opendata.arcgis.com, the Legislative Technology Services
Bureau, LTSB) carries "2024 Election Data with 2025 Wards", "2022 Election Data with 2022 Wards" and "2012 to 2020
Election Data with 2020 Wards": one row per municipal ward, with the ward's county and municipality and the votes of
every candidate, which the Bureau collected from the Wisconsin Elections Commission after each general election. They
are read from the Bureau's own feature services, one polite request at a time, and cached in states_cache/wi_local/.
The Elections Commission's own website is never requested (elections.wi.gov answers scripts with a 403).

  - Wisconsin's clerks report results by reporting unit, which is often several wards together. The Bureau shares a
    reporting unit's votes out to its wards by population, then to census blocks, then adds the blocks up to the
    wards of its ward layer. So ONE WARD'S figures are the Bureau's allocation, not a count, and no ward is given
    here. The Bureau says the totals for reporting units, municipalities, counties and the state match the
    Commission's; a reporting unit never crosses a municipal line. That is why this file gives counties and
    municipalities and not supervisory or aldermanic districts (a November reporting unit may cross those).
  - Legislative districts. The 2024 table has no district column, so each ward of the Bureau's January 2025 layer is
    placed in the Assembly district of the Bureau's "WI Assembly Districts (2024)" layer that holds most of a grid of
    points inside the ward (ward and district lines are not snapped to each other, so a few points of 57 wards fall
    next door). Three Assembly districts make a Senate district, as the district layer itself says. The join is then
    CHECKED: each district's own Assembly votes (and Senate votes, in the sixteen districts that elected a senator in
    2024), added up this way, are compared with the district vote printed in the Wisconsin Blue Book 2025-2026 (from
    the Commission's records). Where they are not equal (a ward of the 2025 layer that is not the ward of election day)
    the district is marked "approximate" with the difference, and a page should say so or leave it out. Districts are
    given for the 2024 contests only: 2022 and 2020 were held on other plans.
  - Which column is which party is in the column's name (PREDEM24, PREREP24, PRETOT24); every other column of the
    contest is "other". The tickets are typed in CONTESTS, only to say which election this was.
  - A place is filed under its Census county-subdivision code (COUSUBFP), as "WI-M-" and the code, which is how
    sl_places keys a Wisconsin municipality; a city or village in several counties is one place. Where today's table
    ("WI Cities, Towns, and Villages (Current)") no longer has a code and exactly one of today's places in the same
    county has the same name and was not in that year's table (a town that became a village under a new code: Rib
    Mountain, Lisbon, Greenville), the votes are filed under today's code and the place says so. A code with no such
    namesake stays, marked "former" (the towns of Madison and Campbell). The 2022 table calls two new villages' wards
    "County subdivisions not defined"; the code says which village they are.
  - 140 wards of the January 2025 layer carry no figures at all (wards made after the election); they count as zero.

The control
-----------
Nothing is written unless: every ward's candidates add up to the ward's own total; counties, municipalities and (for
2024) districts each add up to the statewide sum; and the statewide sum equals the official statewide totals:
  - President and U.S. Senator 2024, U.S. Senator 2022: the Clerk of the U.S. House of Representatives, "Statistics of
    the Presidential and Congressional Election" / "of the Congressional Election" (compiled from official sources).
  - Governor 2022: the Wisconsin Blue Book 2023-2024 (Legislative Reference Bureau; "Source: Official records of the
    Wisconsin Elections Commission"), "County vote for Wisconsin governor and lieutenant governor": all 72 county rows
    are compared with this file's counties, and the statewide total is the sum of the county totals, because the
    table's own Total row leaves out the scattered votes its county rows include (it says so in its note).
  - President 2020: the Federal Election Commission's "Federal Elections 2020". Not the Clerk's Statistics nor the
    Blue Book 2021-2022: both print 1,630,673 and 1,610,065, the county canvass before the recount in Dane and
    Milwaukee counties; the Commission's final figures, which the Bureau's table and the FEC carry, are 1,630,866
    and 1,610,184.
The figures this loader was checked against on 2026-10-02 are typed below (CHECKED); they are used, and the file says
so, when a document cannot be read again. From the documents only parties and vote counts are kept, never names.
"""

import argparse
import collections
import json
import os
import pathlib
import re
import sqlite3
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_place_votes as M  # noqa: E402  the shared small things: caching, the feature-service reader, the file writer

Stop = M.Stop
METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "wi_local")
OUT = os.path.join(HERE, "ballot", "lean", "wi_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "55"
FEW = 20
SIDES = ("dem", "rep", "other", "total")
GRID = 7                       # a ward is sampled on a GRID by GRID lattice over its bounding box, doubled until 8 points are inside
STRADDLE = 0.9                 # a ward with less than this share of its points in one district is listed as straddling

HUB = "https://data-ltsb.opendata.arcgis.com/datasets/"
SERVICES = "https://services1.arcgis.com/FDsAtKBk8Hy4cAH0/arcgis/rest/services/"
AGENCY = "Wisconsin Legislative Technology Services Bureau (LTSB), from the Wisconsin Elections Commission's results"
TABLES = {
    2024: {"item": "878d8826218f42509e07437a82ef6b6e", "service": SERVICES + "2024_Election_Data_with_2025_Wards/FeatureServer",
           "title": "2024 Election Data with 2025 Wards", "wards": "January 2025"},
    2022: {"item": "d753839138d4448182b2fa85c89fcbd1", "service": SERVICES + "2022_Election_Data_wtih_2022_Wards/FeatureServer",
           "title": "2022 Election Data with 2022 Wards", "wards": "July 2022"},
    2020: {"item": "f0a85ed1d34e474681ec3a7478ab9d6a", "service": SERVICES + "2012_to_2020_Election_Data_with_2020_Wards/FeatureServer",
           "title": "2012 to 2020 Election Data with 2020 Wards", "wards": "2020"},
}
TODAY = {"item": "73fd079ff80d4d64882d5445c7d7b05a", "service": SERVICES + "WI_Cities_Towns_and_Villages_Current/FeatureServer",
         "title": "WI Cities, Towns, and Villages (Current)"}
DISTRICTS = {"item": "55e24ed7087e4d0492381713d770eafb", "service": SERVICES + "WI_Assembly_Districts_2024/FeatureServer",
             "title": "WI Assembly Districts (2024)"}

# what is read of each ward besides the votes, and of each municipality today. Allowlists: the layers also carry a
# county contact column, which is never asked for.
PLACE_FIELDS = ["GEOID", "CNTY_FIPS", "CNTY_NAME", "COUSUBFP", "MCD_NAME", "CTV", "LABEL"]
TODAY_FIELDS = ["GEOID", "CNTY_FIPS", "CNTY_NAME", "COUSUBFP", "MCD_NAME", "CTV"]
CHECK_PREFIXES = ("WSA", "WSS")            # the Assembly and state Senate votes of 2024, read only to check the district join
UNDEFINED = "county subdivisions not defined"
TYPES = {"C": "city", "V": "village", "T": "town"}

CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States",
     "prefix": "PRE", "dem": "Harris/Walz", "rep": "Trump/Vance", "official": "clerk-statistics-2024", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2024-us-senate", "year": 2024, "date": "2024-11-05", "office": "United States Senator",
     "prefix": "USS", "dem": "Baldwin", "rep": "Hovde", "official": "clerk-statistics-2024", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor and Lieutenant Governor",
     "prefix": "GOV", "dem": "Evers/Rodriguez", "rep": "Michels/Roth", "official": "blue-book-2023-governor", "section": None},
    {"id": "2022-us-senate", "year": 2022, "date": "2022-11-08", "office": "United States Senator",
     "prefix": "USS", "dem": "Barnes", "rep": "Johnson", "official": "clerk-statistics-2022", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States",
     "prefix": "PRE", "dem": "Biden/Harris", "rep": "Trump/Pence", "official": "fec-federal-elections-2020", "section": None},
]

# The official statewide totals this loader was checked against on 2026-10-02, read from the documents in OFFICIAL_DOCS.
CHECKED = {
    "2024-president": {"dem": 1668229, "rep": 1697626, "other": 57063, "total": 3422918},
    "2024-us-senate": {"dem": 1672777, "rep": 1643996, "other": 74014, "total": 3390787},
    "2022-governor": {"dem": 1358774, "rep": 1268535, "other": 29181, "total": 2656490},
    "2022-us-senate": {"dem": 1310467, "rep": 1337185, "other": 4825, "total": 2652477},
    "2020-president": {"dem": 1630866, "rep": 1610184, "other": 56991, "total": 3298041},
}
BLUE = "https://docs.legis.wisconsin.gov/misc/lrb/blue_book/"
OFFICIAL_DOCS = {
    "clerk-statistics-2024": {
        "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
        "title": "Statistics of the Presidential and Congressional Election from Official Sources for the Election of November 5, 2024",
        "url": "https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf", "file": "clerk_statistics2024.pdf"},
    "clerk-statistics-2022": {
        "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
        "title": "Statistics of the Congressional Election from Official Sources for the Election of November 8, 2022",
        "url": "https://clerk.house.gov/member_info/electionInfo/2022/statistics2022.pdf", "file": "clerk_statistics2022.pdf"},
    "blue-book-2023-governor": {
        "kind": "official state publication, from the official records of the Wisconsin Elections Commission",
        "agency": "Wisconsin Legislative Reference Bureau", "title": "Wisconsin Blue Book 2023-2024, Statistics and Reference: Elections, "
        "\"County vote for Wisconsin governor and lieutenant governor, November 8, 2022 general election\"",
        "url": BLUE + "2023_2024/200_elections_and_political_parties.pdf", "file": "bluebook_2023_2024_elections.pdf",
        "why": "The table's county totals include scattered votes and its own Total row does not (its note says so), so the statewide total "
               "is the sum of the 72 county totals; the Democratic and Republican figures are the Total row's, and equal the county sums."},
    "fec-federal-elections-2020": {
        "kind": "official federal compilation", "agency": "Federal Election Commission",
        "title": "Federal Elections 2020: Election Results for the U.S. President, the U.S. Senate and the U.S. House of Representatives, "
                 "\"2020 Presidential Electoral and Popular Vote\"",
        "url": "https://www.fec.gov/resources/cms-content/documents/federalelections2020.pdf", "file": "fec_federalelections2020.pdf",
        "why": "The Clerk of the House's Statistics for 2020 and the Wisconsin Blue Book 2021-2022 print 1,630,673 and 1,610,065, the county "
               "canvass before the recount in Dane and Milwaukee counties; the final figures are 1,630,866 and 1,610,184."},
}
DISTRICT_DOC = {
    "id": "blue-book-2025-district-votes", "kind": "official state publication, from the official records of the Wisconsin Elections Commission",
    "agency": "Wisconsin Legislative Reference Bureau", "title": "Wisconsin Blue Book 2025-2026, Statistics and Reference: Elections, "
    "\"District vote for Wisconsin state representatives\" and \"for Wisconsin state senators, general and special elections\"",
    "url": BLUE + "2025_2026/200_elections_and_political_parties.pdf", "file": "bluebook_2025_2026_elections.pdf",
    "extract": "bluebook_2025_2026_district_votes.json"}

# Seen on 2026-10-02 and said, not decided: the district stays marked approximate, with this note, only while the
# difference is exactly the one described.
BOOK_NOTES = {("house", "12"): {"when": {"dem": -540, "rep": 0}, "note": (
    "The Blue Book prints 18,931 for the Democratic candidate where the wards add up to 18,391. The book's own percentages for the district's "
    "two candidates (82.83 and 18.95) add up to more than 100, and the ward table's total for the district (22,856) fits 18,391, so this looks "
    "like two digits changed places in the book; this loader does not decide that, and the district stays marked.")}}

# The kinds of place: (kind, the election years it is given for, what it is, what its key is)
KINDS = [
    ("county", (2020, 2022, 2024), "Counties", "five-digit county FIPS code, as sl_places kind county"),
    ("mcd", (2020, 2022, 2024), "Cities, villages and towns", "WI-M- and the five-digit Census county-subdivision code, as sl_places kind mcd"),
    ("senate", (2024,), "State Senate districts of the 2024 plan (2023 Wisconsin Act 94)", "district number, as the jurisdiction_id of our Senate races"),
    ("house", (2024,), "State Assembly districts of the 2024 plan (2023 Wisconsin Act 94)", "district number, as the jurisdiction_id of our Assembly races"),
]
KIND_NAMES = [k[0] for k in KINDS]
REDRAWN = ("The 2022 and 2020 elections were held on other district plans; the 2024 plan (2023 Wisconsin Act 94) was first used in 2024, so "
           "only the 2024 contests are given.")

WHAT = ("How each Wisconsin place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic "
        "ticket, the Republican ticket, everyone else together (write-ins and scattering included) and the total, added up from the "
        "Legislative Technology Services Bureau's ward tables of the Wisconsin Elections Commission's results.")
NOTE = ("What this is: how the people of a place voted in that election, in the Wisconsin Elections Commission's results as the "
        "Legislature's technology bureau publishes them ward by ward, added up here by county, by city, village or town and, for 2024, by "
        "legislative district. What this is not: it is not a prediction of any election; it says nothing about any candidate on a later "
        "ballot or about any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where land was annexed "
        "or a town became a village, the figures are for the lines of that year. Wisconsin counts votes by reporting unit, often several "
        "wards together, and the bureau shares those out to wards by population, so no single ward is given here; counties and "
        "municipalities are whole reporting units. A district marked approximate is one where this adding-up of wards does not equal "
        "the official district vote for the Legislature exactly, by the difference shown. The tickets are named only to say which "
        "election this was. In a place with very few voters the split would come close to saying how particular people voted; those "
        "contests are listed in the place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every "
               "other candidate, write-ins and scattering) and total. Minnesota's file calls the first count dfl. A contest a place does not "
               "have was not held on its lines, or the place is newer than that election.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")


# ---------------------------------------------------------------- the tables

def results_table(year, prefixes, cache, refresh, say):
    yy = str(year)[2:]

    def want(have):
        missing = [f for f in PLACE_FIELDS if f not in have]
        votes = [f for f in have if f.endswith(yy) and any(f.startswith(p) for p in prefixes)]
        for p in prefixes:
            for need in (p + "DEM" + yy, p + "REP" + yy, p + "TOT" + yy):
                if need not in votes:
                    missing.append(need)
        if missing:
            raise OSError(f"the {year} table has no column {', '.join(missing)}")
        return PLACE_FIELDS + votes
    return M.fetch_layer(TABLES[year]["service"], lambda layers: layers if len(layers) == 1 else [], want,
                         os.path.join(cache, f"ltsb_election_data_{year}.json"), refresh, say, f"{year} ward table")


def today_table(cache, refresh, say):
    def want(have):
        missing = [f for f in TODAY_FIELDS if f not in have]
        if missing:
            raise OSError(f"today's municipal table has no column {', '.join(missing)}")
        return TODAY_FIELDS
    return M.fetch_layer(TODAY["service"], lambda layers: layers if len(layers) == 1 else [], want,
                         os.path.join(cache, "ltsb_municipalities_today.json"), refresh, say, "today's municipal table")


# ---------------------------------------------------------------- which Assembly district a ward is in

class Shape:
    """A polygon (rings, even-odd) with its edges filed in bands of latitude, so that asking whether a point is inside
    looks at a few edges only."""
    BANDS = 256

    def __init__(self, rings):
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        self.box = (min(xs), min(ys), max(xs), max(ys))
        self.h = (self.box[3] - self.box[1]) / self.BANDS or 1e-9
        self.bands = [[] for _ in range(self.BANDS)]
        for r in rings:
            for i in range(len(r) - 1):
                x1, y1, x2, y2 = r[i][0], r[i][1], r[i + 1][0], r[i + 1][1]
                if y1 == y2:
                    continue
                lo, hi = int((min(y1, y2) - self.box[1]) / self.h), int((max(y1, y2) - self.box[1]) / self.h)
                for k in range(max(lo, 0), min(hi, self.BANDS - 1) + 1):
                    self.bands[k].append((x1, y1, x2, y2))

    def has(self, x, y):
        b = self.box
        if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
            return False
        inside = False
        for x1, y1, x2, y2 in self.bands[min(int((y - b[1]) / self.h), self.BANDS - 1)]:
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside


def lattice(rings, n=GRID):
    """Points inside a polygon: an n by n lattice over its bounding box, doubled until at least eight are inside."""
    shape = Shape(rings)
    x0, y0, x1, y1 = shape.box
    while True:
        pts = [(x0 + (i + .5) * (x1 - x0) / n, y0 + (j + .5) * (y1 - y0) / n) for i in range(n) for j in range(n)]
        pts = [p for p in pts if shape.has(*p)]
        if len(pts) >= 8 or n >= GRID * 8:
            return pts
        n *= 2


def place_ward(rings, districts):
    """[points inside the ward, [[assembly, senate, points in that district], ...]] with the district of most points first."""
    pts = lattice(rings)
    hits = collections.Counter()
    for x, y in pts:
        for asm, sen, shape in districts:
            if shape.has(x, y):
                hits[(asm, sen)] += 1
    return [len(pts), [[a, s, n] for (a, s), n in sorted(hits.items(), key=lambda kv: (-kv[1], int(kv[0][0])))]]


def ward_districts(geoids, cache, refresh, say):
    """{ward GEOID: [points, [[assembly, senate, points], ...]]} for the wards of the 2024 table, worked out from the
    Bureau's ward and district shapes (about 60 MB of ward shapes, read page by page and not kept; only this small
    table is cached). The 2024 table's ward layer is a snapshot that does not change, so the table is kept until
    --refresh or until a ward of the table is missing from it."""
    path = os.path.join(cache, "ltsb_wards_2025_in_assembly_2024.json")
    if not refresh and os.path.exists(path):
        doc = M._load(path)
        if set(geoids) <= set(doc["wards"]):
            return doc
    try:
        base = DISTRICTS["service"] + "/0/query?where=" + quote("1=1")
        raw = net.get(base + "&outFields=ASM2024,SEN2024&returnGeometry=true&outSR=4326&geometryPrecision=6&f=json", accept="application/json")
        feats = json.loads(raw).get("features", [])
        districts = [(str(int(f["attributes"]["ASM2024"])), str(int(f["attributes"]["SEN2024"])), Shape(f["geometry"]["rings"])) for f in feats]
        per = collections.Counter(s for _a, s, _shape in districts)
        if len(districts) != 99 or len({a for a, _s, _x in districts}) != 99 or len(per) != 33 or set(per.values()) != {3}:
            raise OSError(f"the district layer has {len(districts)} Assembly districts in {len(per)} Senate districts, not 99 in 33 by threes")
        wards, offset = {}, 0
        say("      placing each ward of the January 2025 layer in its Assembly district (about 60 MB of shapes, eight requests)")
        while True:
            time.sleep(1.0)
            j = json.loads(net.get(f"{TABLES[2024]['service']}/0/query?where={quote('1=1')}&outFields=GEOID&returnGeometry=true&outSR=4326"
                                   f"&geometryPrecision=6&orderByFields=OBJECTID&resultOffset={offset}&resultRecordCount=1000&f=json",
                                   accept="application/json"))
            if "error" in j:
                raise OSError(str(j["error"]))
            feats = j.get("features", [])
            for f in feats:
                rings = (f.get("geometry") or {}).get("rings")
                wards[f["attributes"]["GEOID"]] = place_ward(rings, districts) if rings else [0, []]
            offset += len(feats)
            if not feats or not j.get("exceededTransferLimit"):
                break
        missing = sorted(set(geoids) - set(wards))
        if missing:
            raise OSError(f"{len(missing)} wards of the table have no shape")
        doc = {"what": "Which 2024 Assembly district each ward of the 2024 table's ward layer lies in: points inside the ward, then the "
                       "districts holding them, most first.", "fetched": M._now(), "grid": GRID, "districts": DISTRICTS["service"],
               "districts_sha256": M._sha(raw), "senate_of": {a: s for a, s, _x in districts}, "wards": wards}
        M._save(path, doc)
        return doc
    except (OSError, ValueError, KeyError) as e:
        if os.path.exists(path):
            say(f"      ward shapes: could not be fetched ({e}); using the table of {M._day(path)}")
            return M._load(path)
        raise Stop(f"    ward shapes: could not be fetched ({e}) and no table is on disk. Wait a few minutes and run this again.")


# ---------------------------------------------------------------- the official figures

def _dots(t):
    return re.sub(r"(?:\. ?){3,}", " ... ", t.replace("�", "."))


def _n(s):
    return int(s.replace(",", ""))


def split_official(lines, is_dem, is_rep, what):
    dem = [v for label, v in lines if is_dem(label)]
    rep = [v for label, v in lines if is_rep(label)]
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{what}: {len(dem)} Democratic and {len(rep)} Republican lines, not one of each")
    total = sum(v for _label, v in lines)
    return {"dem": dem[0], "rep": rep[0], "other": total - dem[0] - rep[0], "total": total}


def read_clerk(path, state="WISCONSIN"):
    """The state's page of the Clerk of the House's election statistics: {section heading: [(label, votes)]} for the
    presidential electors (by party) and United States Senator (candidate, party), up to the representatives."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == state), None)
    if start is None:
        raise ValueError(f"no {state} heading")
    page = lines[start][0]
    top = next(t.strip() for p, _y, t in lines if p == page)
    sections, section = {}, None
    for _p, _y, t in lines[start + 1:]:
        t = t.strip()
        if t.startswith("FOR UNITED STATES REPRESENTATIVE") or (t.isupper() and not t.startswith("FOR ") and section):
            break
        if t.startswith("FOR "):
            section = t
            sections[section] = []
            continue
        m = re.match(r"^(.*?)\s*\.{3,}\s*([\d,]+)$", t)
        if section and m:
            sections[section].append((m.group(1).strip(), _n(m.group(2))))
        elif section and t:
            raise ValueError(f"a line under {section} is not a name, dots and a number")
    return {"where": f"Wisconsin, page {top}" if top.isdigit() else f"Wisconsin, page {page} of the PDF", "sections": sections}


def clerk_official(doc, section):
    lines = doc["sections"].get(section) or []
    if section == "FOR PRESIDENTIAL ELECTORS":           # one line a party
        return split_official(lines, lambda s: s == "Democratic", lambda s: s == "Republican", section)
    party = lambda s: s.rsplit(",", 1)[-1].strip()                                                  # noqa: E731  "..., Democrat"
    return split_official(lines, lambda s: party(s) == "Democrat", lambda s: party(s) == "Republican", section)


def county_key(name):
    return re.sub(r"[^a-z]", "", name.lower())


def read_blue_governor(path):
    """The Blue Book 2023-2024's county table for Governor, 2022: {"counties": {name: [dem, rep, total]}, "row": the
    table's own Total row}. Only the county's name and the three counts are kept."""
    from ballot import pdftext
    lines = [(p, _dots(t)) for p, _y, t in pdftext.lines(path)]
    start = next((i for i, (_p, t) in enumerate(lines) if t.startswith("County vote for Wisconsin governor and lieutenant governor")), None)
    if start is None or "November 8, 2022 general election" not in lines[start + 1][1]:
        raise ValueError("no county table for Governor, November 8, 2022")
    counties, order = {}, False
    for _p, t in lines[start:]:
        if re.search(r"\(Dem\.\).*\(Rep\.\).*\(Ind\.\) Total$", t):
            order = True
        m = re.match(r"^([A-Z][A-Za-z. ]*?) +\.\.\. +([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if not m:
            continue
        name, dem, rep, _ind, total = m.group(1).strip(), _n(m.group(2)), _n(m.group(3)), _n(m.group(4)), _n(m.group(5))
        if name == "Total":
            if not order or len(counties) != 72:
                raise ValueError(f"{len(counties)} county rows before the Total row, or the columns are not Democratic, Republican, Independent, Total")
            if (dem, rep) != (sum(c[0] for c in counties.values()), sum(c[1] for c in counties.values())):
                raise ValueError("the county rows do not add up to the table's Total row")
            return {"where": "the county table; statewide total = the sum of the 72 county totals", "counties": counties, "row": [dem, rep, total]}
        counties[name] = [dem, rep, total]
    raise ValueError("the county table has no Total row")


def blue_official(doc):
    dem, rep = doc["row"][0], doc["row"][1]
    total = sum(c[2] for c in doc["counties"].values())
    return {"dem": dem, "rep": rep, "other": total - dem - rep, "total": total}


def read_fec(path):
    """Wisconsin's row of the FEC's table of the 2020 presidential popular vote: Biden (D), Trump (R), all others, total."""
    from ballot import pdftext
    lines = [t.strip() for _p, _y, t in pdftext.lines(path)]
    start = next((i for i, t in enumerate(lines) if t == "2020 PRESIDENTIAL ELECTORAL AND POPULAR VOTE"), None)
    if start is None or not re.search(r"Biden \(D\) Trump \(R\) All Others Total Vote$", lines[start + 2]):
        raise ValueError("no table of the 2020 presidential popular vote with Biden, Trump, All Others, Total")
    for t in lines[start:start + 70]:
        m = re.match(r"^WI \d+ ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if m:
            dem, rep, other, total = (_n(x) for x in m.groups())
            if dem + rep + other != total:
                raise ValueError("Wisconsin's row does not add up")
            return {"where": "the table \"2020 Presidential Electoral and Popular Vote\", Wisconsin's row", "row": {"dem": dem, "rep": rep, "other": other, "total": total}}
    raise ValueError("no Wisconsin row in the table")


def official_totals(contests, cache, refresh, say):
    """({contest id: {dem, rep, other, total, source, where, read}}, the documents' records, the Governor table's counties or None)."""
    docs, out, gov_counties = {}, {}, None
    for sid, src in OFFICIAL_DOCS.items():
        if not any(c["official"] == sid for c in contests):
            continue
        path = os.path.join(cache, src["file"])
        rec = {"id": sid, "kind": src["kind"], "agency": src["agency"], "title": src["title"], "url": src["url"]}
        if "why" in src:
            rec["why"] = src["why"]
        try:
            net.download(src["url"], path, 0 if refresh else 3650, tries=3, say=say)
            if sid.startswith("clerk-"):
                parsed = read_clerk(path)
                reader = lambda c, parsed=parsed: clerk_official(parsed, c["section"])                # noqa: E731
            elif sid.startswith("blue-"):
                parsed = read_blue_governor(path)
                gov_counties = parsed["counties"]
                reader = lambda c, parsed=parsed: blue_official(parsed)                               # noqa: E731
            else:
                parsed = read_fec(path)
                reader = lambda c, parsed=parsed: dict(parsed["row"])                                 # noqa: E731
            rec.update(fetched=M._day(path), sha256=M._sha_file(path), where=parsed["where"])
            docs[sid] = (rec, reader)
        except Exception as e:  # noqa: BLE001  the control then runs on the typed figures, and the file says so
            say(f"      {src['title'][:60]}: could not be read again ({e}); the control uses the figures typed in on 2026-10-02")
            rec.update(unread=f"could not be read on {M._now()}: {e}")
            docs[sid] = (rec, None)
    for c in contests:
        rec, reader = docs[c["official"]]
        typed, got, read = CHECKED.get(c["id"]), None, None
        if reader:
            try:
                got, read = reader(c), f"from the document on {rec.get('fetched')}"
            except Exception as e:  # noqa: BLE001
                say(f"      {rec['title'][:60]}: {e}; the control uses the figures typed in on 2026-10-02")
        if got is None:
            if typed is None:
                raise Stop(f"    {c['id']}: no official total could be read and none is typed in this loader")
            got, read = dict(typed), "typed into the loader from the document on 2026-10-02; the document could not be read again today"
        elif typed is not None and got != typed:
            say(f"      {c['id']}: the document now reads {got}; this loader was checked against {typed}")
        out[c["id"]] = dict(got, source=c["official"], where=rec.get("where", ""), read=read)
    return out, [rec for rec, _reader in docs.values()], gov_counties


def read_district_votes(lines, title, expected):
    """One Blue Book table of district votes, the November 5, 2024 general election only: {district: [dem, rep]}.
    `lines` are the PDF's lines in order; `expected` the district numbers in the order the table must give them (a
    number printed with a footnote mark after it, "12" for district 1, is read as the number expected). Only the
    party word and the votes of a row are read."""
    out, cur, queue, on, seen = {}, None, list(expected), False, False
    for t in lines:
        if title in t:
            seen = True
            continue
        if not seen:
            continue
        if re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4} .*election", t):
            on = t.startswith("November 5, 2024 general election")
            continue
        if not on:
            continue
        if t.startswith("Source:") or not queue and re.match(r"^(District|County) vote", t):
            break
        m = re.match(r"^(?:(\d{1,3}) +(?:\.\.\. +)?(?:\d+(?:, \d+)* +)?)?([A-Z][a-z]+)\.? .*?([\d,]+) \d+\.\d+$", t)
        if not m:
            continue
        if m.group(1):
            if not queue or not m.group(1).startswith(queue[0]):
                raise ValueError(f"{title}: district {m.group(1)} where {queue[0] if queue else 'the end'} was expected")
            cur = queue.pop(0)
            out[cur] = [0, 0]
        if cur is None:
            raise ValueError(f"{title}: a row of votes before any district")
        word = m.group(2).lower()
        if word.startswith("dem"):                                     # the book prints "Demcoratic" once
            out[cur][0] += _n(m.group(3))
        elif word.startswith("rep"):
            out[cur][1] += _n(m.group(3))
    if queue:
        raise ValueError(f"{title}: {len(out)} districts read, {len(queue)} not found")
    return out


def district_votes(cache, refresh, say):
    """The official 2024 district votes for the Legislature, by party: {"house": {district: [dem, rep]}, "senate": {...}}
    with the document's record, or (None, record) when neither the book nor an earlier extract can be read."""
    src = DISTRICT_DOC
    path, extract = os.path.join(cache, src["file"]), os.path.join(cache, src["extract"])
    rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
    try:
        from ballot import pdftext
        net.download(src["url"], path, 0 if refresh else 3650, tries=3, say=say)
        lines = [_dots(t) for _p, _y, t in pdftext.lines(path)]
        doc = {"fetched": M._day(path), "sha256": M._sha_file(path),
               "house": read_district_votes(lines, "District vote for Wisconsin state representatives, general and", [str(i) for i in range(1, 100)]),
               "senate": read_district_votes(lines, "District vote for Wisconsin state senators, general and", [str(i) for i in range(2, 34, 2)])}
        M._save(extract, doc)
    except Exception as e:  # noqa: BLE001
        if not os.path.exists(extract):
            say(f"      the Blue Book's district votes could not be read ({e}); the districts cannot be checked and are all marked unchecked")
            return None, dict(rec, unread=f"could not be read on {M._now()}: {e}")
        say(f"      the Blue Book's district votes could not be read again ({e}); using the extract of {M._day(extract)}")
        doc = M._load(extract)
    rec.update(fetched=doc["fetched"], sha256=doc["sha256"], where="the rows under \"November 5, 2024 general election\"; only each row's party and votes are kept")
    return doc, rec


# ---------------------------------------------------------------- adding up

def contest_columns(c, fields):
    p, yy = c["prefix"], str(c["year"])[2:]
    cols = [f for f in fields if f.startswith(p) and f.endswith(yy)]
    named = (p + "DEM" + yy, p + "REP" + yy, p + "TOT" + yy)
    return {"dem": named[0], "rep": named[1], "total": named[2], "others": [f for f in cols if f not in named]}


def _int(v, what):
    if isinstance(v, bool) or (isinstance(v, float) and v != int(v)) or not isinstance(v, (int, float)) or v < 0:
        raise Stop(f"    {what} is {v!r}, not a count of votes; stopping")
    return int(v)


def nice(name):
    return " ".join(w.capitalize() if w.isupper() else w for w in (name or "").strip().split()) if (name or "").isupper() else (name or "").strip()


def mcd_codes(rows):
    """{county-subdivision code: {names, types, counties}} as one table writes them. A row the table calls 'County
    subdivisions not defined' gives its code and county but no name or type."""
    out = {}
    for r in rows:
        code = (r["COUSUBFP"] or "").strip()
        e = out.setdefault(code, {"names": set(), "types": set(), "counties": set()})
        e["counties"].add(r["CNTY_FIPS"].strip())
        if (r["MCD_NAME"] or "").strip().lower() != UNDEFINED and (r["CTV"] or "").strip() in TYPES:
            e["names"].add(nice(r["MCD_NAME"]))
            e["types"].add(TYPES[r["CTV"].strip()])
    return out


def same(a, b):
    return {M.bare(n) for n in a["names"]} == {M.bare(n) for n in b["names"]}


def carry_map(then, today):
    """{code of an earlier table: today's code} for a code today's table no longer has, when exactly one of today's
    places has the same name in the same county and was not in that table."""
    out = {}
    for code, e in then.items():
        if code in today or len({M.bare(n) for n in e["names"]}) != 1:
            continue
        fits = [z for z, t in today.items() if z not in then and len(t["names"]) == 1 and same(t, e) and t["counties"] & e["counties"]]
        if len(fits) == 1:
            out[code] = fits[0]
    return out


def mcd_name(e):
    return f"{' / '.join(sorted(e['names']))} {' / '.join(sorted(e['types']))}".strip()


def mkey(code):
    return "WI-M-" + code


def tally(tables, today_rows, contests, wards):
    """Everything the tables say, added up: (places, statewide sums, per-kind sums, carried codes, the contests each
    kind is given for, the district check's own sums, notes on the wards)."""
    today = mcd_codes(today_rows) if today_rows is not None else None
    years_of = {k[0]: k[1] for k in KINDS}
    given = {k: [c["id"] for c in contests if c["year"] in years_of[k] and (k in ("county", "mcd") or wards is not None)] for k in KIND_NAMES}
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    names = {"county": {}, "senate": {}, "house": {}}
    state, carried, then_of = {}, collections.defaultdict(dict), {}
    own = {"house": collections.defaultdict(lambda: [0, 0]), "senate": collections.defaultdict(lambda: [0, 0])}
    info = {"empty": {}, "straddling": [], "unplaced": []}
    for year in sorted(tables, reverse=True):
        rows, fields = tables[year]["rows"], tables[year]["fields"]
        yy = str(year)[2:]
        if len({r["GEOID"] for r in rows}) != len(rows):
            raise Stop(f"    {year} ward table: a ward id appears twice; stopping")
        then = then_of[year] = mcd_codes(rows)
        if "" in then:
            raise Stop(f"    {year} ward table: a ward has no county-subdivision code; stopping")
        moved = carry_map(then, today) if today is not None else {}
        mine = [c for c in contests if c["year"] == year]
        cols = {c["id"]: contest_columns(c, fields) for c in mine}
        vote_fields = [f for f in fields if f not in PLACE_FIELDS]
        districts = year == 2024 and wards is not None
        for r in rows:
            where = f"{year} ward {r['GEOID']} ({(r['LABEL'] or '').strip()})"
            if all(r[f] is None for f in vote_fields):          # a ward the layer has and the election did not
                info["empty"][str(year)] = info["empty"].get(str(year), 0) + 1
                continue
            county, old = r["CNTY_FIPS"].strip(), r["COUSUBFP"].strip()
            if not re.fullmatch(STATE_FIPS + r"\d{3}", county):
                raise Stop(f"    {where}: county code {county!r}; stopping")
            mcd = moved.get(old, old)
            keys = {"county": county, "mcd": mcd}
            names["county"].setdefault(county, f"{(r['CNTY_NAME'] or '').strip()} County")
            if districts:
                n, hits = wards["wards"].get(r["GEOID"], [0, []])
                if hits:
                    keys["house"], keys["senate"] = hits[0][0], hits[0][1]
                    names["house"].setdefault(hits[0][0], f"Assembly District {hits[0][0]}")
                    names["senate"].setdefault(hits[0][1], f"Senate District {hits[0][1]}")
                    if hits[0][2] < STRADDLE * sum(h[2] for h in hits):
                        info["straddling"].append({"ward": (r["LABEL"] or "").strip(), "county": names["county"][county],
                                                   "points": {h[0]: h[2] for h in hits}})
                    for kind, pre in (("house", "WSA"), ("senate", "WSS")):
                        if pre + "DEM" + yy in r:
                            own[kind][keys[kind]][0] += _int(r[pre + "DEM" + yy], where)
                            own[kind][keys[kind]][1] += _int(r[pre + "REP" + yy], where)
                else:
                    info["unplaced"].append(where)
            for c in mine:
                k = cols[c["id"]]
                what = f"{where}, {c['office']}"
                dem, rep, total = (_int(r[k[x]], what) for x in ("dem", "rep", "total"))
                others = sum(_int(r[f], what) for f in k["others"])
                if dem + rep + others != total:
                    raise Stop(f"    {what}: the candidates add up to {dem + rep + others:,} and the table's total is {total:,}; stopping")
                v = (dem, rep, others, total)
                s = state.setdefault(c["id"], [0, 0, 0, 0])
                for i in range(4):
                    s[i] += v[i]
                for kind, key in keys.items():
                    if c["id"] not in given[kind]:
                        continue
                    cur = votes[kind][key].setdefault(c["id"], [0, 0, 0, 0])
                    for i in range(4):
                        cur[i] += v[i]
                if old != mcd:
                    e = carried[mcd].setdefault(old, {"name": mcd_name(then[old]), "contests": []})
                    if c["id"] not in e["contests"]:
                        e["contests"].append(c["id"])

    pack = lambda d: {cid: dict(zip(SIDES, d[cid])) for cid in (c["id"] for c in contests) if cid in d}             # noqa: E731

    def few(rec):
        hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
        if hold:
            rec["too_few"] = hold
        return rec
    places = {k: {} for k in KIND_NAMES}
    for kind in ("county", "senate", "house"):
        for key in sorted(votes[kind], key=M.sort_key):
            places[kind][key] = few({"name": names[kind][key], "votes": pack(votes[kind][key])})
    years = sorted(tables, reverse=True)
    def tables_of(ys):
        ys = sorted({str(y) for y in ys})
        return f"{' and '.join(ys) if len(ys) < 3 else ', '.join(ys[:-1]) + ' and ' + ys[-1]} table{'s' if len(ys) > 1 else ''}"
    for code in sorted(set(votes["mcd"]) | set(today or {})):
        e = (today or {}).get(code) or next((then_of[y][code] for y in years if code in then_of[y] and then_of[y][code]["names"]), None) \
            or {"names": {"A place the table does not name"}, "types": set(), "counties": set().union(*(then_of[y][code]["counties"] for y in years if code in then_of[y]))}
        rec = few({"name": mcd_name(e), "type": " / ".join(sorted(e["types"])), "counties": sorted(e["counties"]), "votes": pack(votes["mcd"].get(code, {}))})
        notes = []
        if today is not None and code in today:
            renamed = {str(y): mcd_name(then_of[y][code]) for y in sorted(tables) if code in then_of[y] and then_of[y][code]["names"]
                       and (not same(then_of[y][code], today[code]) or then_of[y][code]["types"] != today[code]["types"])}
            if renamed:
                rec["named_then"] = renamed
                notes.append(f"The {tables_of(renamed)} had this code as {' and '.join(sorted(set(renamed.values())))}; today's table has it as "
                             f"{rec['name']}. The code is the same; whether the ground is exactly the same the tables do not say.")
        if code in carried:
            rec["earlier"] = {mkey(old): {"name": x["name"], "contests": sorted(x["contests"])} for old, x in sorted(carried[code].items())}
            was = "; ".join(f"filed as {x['name']} ({mkey(old)}) in the {tables_of(cid[:4] for cid in x['contests'])}" for old, x in sorted(carried[code].items()))
            notes.append(f"The same place under an earlier code: {was}. Today's table has no such code and has this one place of that name in "
                         "the same county; the votes are the earlier place's, on its lines of that year.")
        elif today is not None and code not in today:
            rec["former"] = True
            notes.append("Today's table has no place under this code and no one place of this name in the same county; the name and the "
                         f"lines are those of the {tables_of(y for y in tables if code in then_of[y])}.")
        elif not rec["votes"]:
            notes.append(f"No ward carried this code in these elections: the place, or its code, is newer than {max(tables)}.")
        if notes:
            rec["note"] = " ".join(notes)
        places["mcd"][mkey(code)] = rec
    sums = {kind: {cid: [sum(p["votes"][cid][x] for p in places[kind].values() if cid in p["votes"]) for x in SIDES] for cid in given[kind]}
            for kind in KIND_NAMES}
    return places, state, sums, {mkey(k): {mkey(o): x for o, x in v.items()} for k, v in carried.items()}, given, own, info


def check_districts(places, own, official):
    """Marks each district whose own 2024 vote for the Legislature, added up from its wards, is not the official
    district vote. Returns the record for the control."""
    if official is None:
        for kind in ("house", "senate"):
            for p in places[kind].values():
                p["unchecked"] = True
        return {"result": "not checked", "statement": "The official district votes could not be read, so no district's wards could be checked."}
    out = {"result": "checked", "source": DISTRICT_DOC["id"]}
    for kind, label in (("house", "Assembly"), ("senate", "state Senate")):
        differs = {}
        for d, (dem, rep) in sorted(official[kind].items(), key=lambda kv: int(kv[0])):
            mine = own[kind].get(d, [0, 0])
            if d in places[kind] and (mine[0] != dem or mine[1] != rep):
                differs[d] = {"dem": mine[0] - dem, "rep": mine[1] - rep}
                places[kind][d]["approximate"] = {"contest": f"the district's own 2024 vote for the {label}", "wards_minus_official": differs[d],
                                                  "official": {"dem": dem, "rep": rep}}
                if BOOK_NOTES.get((kind, d), {}).get("when") == differs[d]:
                    places[kind][d]["approximate"]["note"] = BOOK_NOTES[(kind, d)]["note"]
                    out.setdefault("notes", []).append(f"{label} District {d}: {BOOK_NOTES[(kind, d)]['note']}")
        out[kind] = {"districts": len(places[kind]), "checked": len(official[kind]), "equal": len(official[kind]) - len(differs),
                     "approximate": differs, "largest_difference": max((max(abs(v["dem"]), abs(v["rep"])) for v in differs.values()), default=0)}
    for d, p in places["senate"].items():                               # a Senate district not on the 2024 ballot stands on its three Assembly districts
        if d not in official["senate"]:
            parts = [a for a, x in places["house"].items() if x.get("approximate") and a in p.get("assembly", [])]
            if parts:
                p["approximate"] = {"contest": "no Senate election here in 2024; its Assembly districts' own 2024 votes", "assembly_districts": parts}
    out["statement"] = ("Each district's own 2024 vote for the Legislature, added up from the wards placed in it, was compared with the district "
                        "vote in the Wisconsin Blue Book 2025-2026. A district where they differ is marked approximate, with the difference: its "
                        "other contests are off by about as much.")
    return out


def control(state, sums, official, contests, tables, gov_counties, places):
    failed, per = [], {}
    for c in contests:
        mine = dict(zip(SIDES, state[c["id"]]))
        off = official[c["id"]]
        theirs = {n: off[n] for n in SIDES}
        diff = {n: mine[n] - theirs[n] for n in SIDES if mine[n] != theirs[n]}
        per[c["id"]] = {"sum_of_wards": mine, "official": theirs, "equal": not diff, "source": off["source"], "where": off["where"], "read": off["read"]}
        if diff:
            per[c["id"]]["difference"] = diff
            failed.append(f"{c['id']}: the wards add up to {mine} and the official totals ({off['source']}) are {theirs}; wards minus official: {diff}")
    kinds = {}
    for kind in KIND_NAMES:
        bad = [cid for cid, s in sums[kind].items() if s != state[cid]]
        kinds[kind] = "equal" if not bad else f"differs for {', '.join(bad)}"
        failed += [f"{kind}: its places add up to {sums[kind][cid]} for {cid}, and the wards to {state[cid]}" for cid in bad]
    rec = {"result": "equal" if not failed else "differs",
           "statement": ("For every contest the ward rows add up to the official statewide totals named here; in every ward the candidates add "
                         "up to the ward's own total; and counties, municipalities and districts each add up to the statewide sum."
                         if not failed else "The sums do not all agree; see the differences."),
           "wards": {str(y): len(t["rows"]) for y, t in sorted(tables.items())}, "contests": per, "kinds": kinds, "notes": []}
    if gov_counties is not None and any(c["id"] == "2022-governor" for c in contests):
        by = {county_key(p["name"].replace(" County", "")): p["votes"].get("2022-governor") for p in places["county"].values()}
        bad = [n for n, (dem, rep, total) in gov_counties.items()
               if not by.get(county_key(n)) or (by[county_key(n)]["dem"], by[county_key(n)]["rep"], by[county_key(n)]["total"]) != (dem, rep, total)]
        rec["counties_2022_governor"] = {"compared": len(gov_counties), "equal": len(gov_counties) - len(bad), "differ": bad,
                                         "source": "blue-book-2023-governor"}
        failed += [f"2022-governor, {n} County: this file's county is not the Blue Book's row" for n in bad]
        if bad:
            rec["result"] = "differs"
    return rec, failed


# ---------------------------------------------------------------- the file

def build(tables, today, wards, official, official_docs, gov_counties, district_official, district_doc, contests=CONTESTS, strict=True):
    places, state, sums, carried, given, own, info = tally(tables, today["rows"] if today else None, contests, wards)
    if wards is not None:
        for a, p in places["house"].items():
            p["senate"] = wards["senate_of"][a]
        for s, p in places["senate"].items():
            p["assembly"] = sorted((a for a, x in wards["senate_of"].items() if x == s), key=int)
    ctl, failed = control(state, sums, official, contests, tables, gov_counties, places)
    if info["unplaced"]:
        failed.append(f"{len(info['unplaced'])} wards with votes lie in no Assembly district: {'; '.join(info['unplaced'][:5])}")
    if wards is not None:
        ctl["districts"] = check_districts(places, own, district_official)
        for kind in ("house", "senate"):
            d = ctl["districts"].get(kind) or {}
            if strict and (len(d.get("approximate", {})) > 20 or d.get("largest_difference", 0) > 600):
                failed.append(f"{kind}: {len(d['approximate'])} districts differ from the official district vote, by up to {d['largest_difference']:,} votes: "
                              "the wards are not in the right districts")
    if strict:
        if len(places["county"]) != 72:
            failed.append(f"{len(places['county'])} counties, not 72")
        if wards is not None and (len(places["senate"]) != 33 or len(places["house"]) != 99):
            failed.append(f"{len(places['senate'])} Senate and {len(places['house'])} Assembly districts, not 33 and 99")
        failed += [f"{len(t['rows'])} wards in {y}, not about 7,000" for y, t in tables.items() if not 6000 <= len(t["rows"]) <= 8500]
    records = []
    for c in contests:
        k = contest_columns(c, tables[c["year"]]["fields"])
        records.append({"id": c["id"], "date": c["date"], "office": c["office"], "table": f"wi-ltsb-election-data-{c['year']}",
                        "kinds": [kind for kind in KIND_NAMES if c["id"] in given[kind]],
                        "dem": {"party": "Democratic", "ticket": c["dem"], "column": k["dem"]},
                        "rep": {"party": "Republican", "ticket": c["rep"], "column": k["rep"]},
                        "other": {"what": "every other candidate, write-ins and scattering, together", "columns": k["others"]},
                        "total": {"column": k["total"]}, "statewide": dict(zip(SIDES, state[c["id"]])), "official_source": official[c["id"]]["source"]})
    kinds = {}
    for kind, years, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind], "covers_the_state": True,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if len(years) == 1:
            kinds[kind]["why_not_earlier"] = REDRAWN
            kinds[kind]["approximate"] = sorted((d for d, p in places[kind].items() if p.get("approximate")), key=int)
            kinds[kind]["note"] = ("A district's wards are those of the Bureau's January 2025 ward layer with most of their area in it. A district "
                                   "with \"approximate\" is one whose own vote for the Legislature, added up this way, is not the official district "
                                   "vote; a page should say so or leave its figures out.")
    doc = {"what": WHAT, "note": NOTE, "state": "WI", "generated": M._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(SIDES), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": ctl,
           "coverage": {"carried_to_todays_code": {new: {old: x["name"] for old, x in sorted(olds.items())} for new, olds in sorted(carried.items())},
                        "former_places": {code: p["name"] for code, p in places["mcd"].items() if p.get("former")},
                        "todays_places_without_votes": {code: p["name"] for code, p in places["mcd"].items() if not p["votes"]},
                        "wards_without_figures": info["empty"], "wards_straddling_districts": info["straddling"],
                        "not_given": "Single wards (the Bureau's allocation, not a count); county supervisory and aldermanic districts (a "
                                     "November reporting unit may cross them); school districts (the tables do not say which a ward is in); "
                                     "legislative districts for 2022 and 2020 (other plans)."},
           "sources": source_records(tables, today, wards, official_docs, district_doc), "places": places}
    return doc, failed


def source_records(tables, today, wards, official_docs, district_doc):
    out = []
    for y in sorted(tables, reverse=True):
        t, src = tables[y], TABLES.get(y, {})
        out.append({"id": f"wi-ltsb-election-data-{y}", "kind": "official results, shared out to wards by the legislature's technology bureau",
                    "agency": AGENCY, "title": src.get("title"), "url": HUB + src["item"] if src else None, "service": src.get("service"),
                    "ward_layer": src.get("wards"), "layer": t.get("layer_name"), "wards": len(t["rows"]), "fetched": t.get("fetched"),
                    "rows_sha256": M.rows_fingerprint(t["rows"]),
                    "licence": "The Bureau: \"This is open and publicly available data. Use this data at your own risk.\"",
                    "read": "Of each ward: its id and label, county, municipality and county-subdivision code, and the votes of every candidate "
                            "in the contests named here" + (" and, to check the district join, for the Assembly and state Senate." if y == 2024 else ".")})
    if today is not None:
        out.append({"id": "wi-ltsb-municipalities-today", "kind": "official municipal boundary table (attributes)", "agency": "Wisconsin Legislative "
                    "Technology Services Bureau", "title": TODAY["title"], "url": HUB + TODAY["item"], "service": TODAY["service"],
                    "layer": today.get("layer_name"), "rows": len(today["rows"]), "fetched": today.get("fetched"),
                    "rows_sha256": M.rows_fingerprint(today["rows"]),
                    "read": "Of each municipality: its code, name, kind and county. Used only to say which places exist today."})
    if wards is not None:
        out.append({"id": "wi-ltsb-assembly-districts-2024", "kind": "official district lines", "agency": "Wisconsin Legislative Technology Services "
                    "Bureau", "title": DISTRICTS["title"], "url": HUB + DISTRICTS["item"], "service": DISTRICTS["service"],
                    "fetched": wards.get("fetched"), "sha256": wards.get("districts_sha256"),
                    "read": "The 99 Assembly districts' lines and the Senate district each belongs to, to place each ward of the 2024 table."})
    return out + official_docs + ([district_doc] if district_doc else [])


def our_places(db):
    """{kind: ids} of our Wisconsin places and legislative races, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'wi-%' AND kind IN ('county', 'mcd')"):
            out[kind].add(pid)
        for office, jid in con.execute("SELECT office_kind, jurisdiction_id FROM sl_races WHERE state = 'WI' AND office_kind IN ('state_senate', 'state_house')"):
            out["senate" if office == "state_senate" else "house"].add(str(jid))
        for jid, in con.execute("SELECT DISTINCT jurisdiction_id FROM sl_races WHERE state = 'WI' AND level = 'county'"):
            out["county"].add(str(jid))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Wisconsin place votes: the Elections Commission's results in the Legislative Technology Services Bureau's ward tables")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    tables = {}
    for year in sorted({c["year"] for c in CONTESTS}, reverse=True):
        prefixes = sorted({c["prefix"] for c in CONTESTS if c["year"] == year}) + (list(CHECK_PREFIXES) if year == 2024 else [])
        tables[year] = results_table(year, prefixes, cache, refresh, say)
        say(f"      {year}: {len(tables[year]['rows']):,} wards ({tables[year].get('layer_name')}; copy of {tables[year].get('fetched')})")
    today = today_table(cache, refresh, say)
    wards = ward_districts([r["GEOID"] for r in tables[2024]["rows"]], cache, refresh, say)
    say("    the official figures: Clerk of the U.S. House (2024, and U.S. Senator 2022); Wisconsin Blue Book (Governor 2022, by county; "
        "2024 district votes); Federal Election Commission (President 2020)")
    official, official_docs, gov_counties = official_totals(CONTESTS, cache, refresh, say)
    district_official, district_doc = district_votes(cache, refresh, say)
    doc, failed = build(tables, today, wards, official, official_docs, gov_counties, district_official, district_doc)

    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['mcd']):,} cities, villages and towns; {len(p['senate'])} Senate and "
        f"{len(p['house'])} Assembly districts")
    for new, olds in doc["coverage"]["carried_to_todays_code"].items():
        say(f"      the same place under an earlier code: {'; '.join(f'{n} ({o})' for o, n in olds.items())} is filed under {p['mcd'][new]['name']} ({new})")
    if doc["coverage"]["former_places"]:
        say("      no longer places today (kept under their old codes): " + "; ".join(f"{n} ({c})" for c, n in doc["coverage"]["former_places"].items()))
    if doc["coverage"]["todays_places_without_votes"]:
        say("      today's places with no ward in these elections: " + "; ".join(f"{n} ({c})" for c, n in doc["coverage"]["todays_places_without_votes"].items()))
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + ("equal to" if ctl["equal"] else "DIFFERS from") + f" {ctl['source']} ({ctl['where']}; {ctl['read']})")
    g = doc["control"].get("counties_2022_governor")
    if g:
        say(f"    control, Governor 2022 county by county: {g['equal']} of {g['compared']} counties equal to the Blue Book")
    d = doc["control"].get("districts", {})
    for kind in ("house", "senate"):
        if kind in d:
            say(f"    district check, {kind}: {d[kind]['equal']} of {d[kind]['checked']} districts' own 2024 votes equal to the Blue Book; "
                f"{len(d[kind]['approximate'])} marked approximate (largest difference {d[kind]['largest_difference']:,} votes)"
                + (": " + ", ".join(d[kind]["approximate"]) if d[kind]["approximate"] else ""))
    for kind, result in doc["control"]["kinds"].items():
        if result != "equal":
            say(f"    control, {kind}: {result}")
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    Wisconsin place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES:
            ids = ours.get(kind, set())
            without = sorted(i for i in ids if not p[kind].get(i, {}).get("votes"))
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}" + (f" (none for {', '.join(without[:12])})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {M._now()}")
    M.write(out, doc)
    say(f"    Wisconsin place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.1f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic on a made-up table

def selftest(say=print):
    def row(geoid, name, code, ctv, county, cname, **v):
        return dict({"GEOID": geoid, "CNTY_FIPS": county, "CNTY_NAME": cname, "COUSUBFP": code, "MCD_NAME": name, "CTV": ctv, "LABEL": f"{name} - {ctv}"}, **v)

    def pres(d, r, o, yy="24"):
        return {f"PRETOT{yy}": d + r + o, f"PREDEM{yy}": d, f"PREREP{yy}": r, f"PRESCT{yy}": o}

    def leg(ad, ar, sd, sr):
        return {"WSATOT24": ad + ar, "WSADEM24": ad, "WSAREP24": ar, "WSSTOT24": sd + sr, "WSSDEM24": sd, "WSSREP24": sr}

    def gov(d, r, o):
        return {"GOVTOT22": d + r + o, "GOVDEM22": d, "GOVREP22": r, "GOVSCT22": o}
    f24 = PLACE_FIELDS + list(pres(0, 0, 0)) + list(leg(0, 0, 0, 0))
    f22 = PLACE_FIELDS + list(gov(0, 0, 0))
    none = {f: None for f in f24 if f not in PLACE_FIELDS}
    t24 = [row("w1", "Alder", "00001", "C", "55001", "Adams", **pres(20, 10, 1), **leg(18, 12, 0, 0)),
           row("w2", "Alder", "00001", "C", "55003", "Ashland", **pres(3, 7, 0), **leg(4, 6, 5, 5)),
           row("w3", "ELM", "00012", "V", "55003", "Ashland", **pres(40, 30, 5), **leg(35, 40, 36, 39)),
           row("w4", "PINE", "00041", "T", "55001", "Adams", **pres(0, 25, 0), **leg(0, 25, 0, 0)),
           row("w5", "Alder", "00001", "C", "55001", "Adams", **none)]
    t22 = [row("v1", "Alder", "00001", "C", "55001", "Adams", **gov(11, 9, 0)),
           row("v2", "ELM", "00011", "T", "55003", "Ashland", **gov(10, 20, 1)),
           row("v3", "County subdivisions not defined", "00051", " ", "55003", "Ashland", **gov(1, 1, 0)),
           row("v4", "FIR", "00021", "T", "55003", "Ashland", **gov(2, 4, 0))]
    today = [{"GEOID": g, "CNTY_FIPS": c, "CNTY_NAME": cn, "COUSUBFP": code, "MCD_NAME": n, "CTV": k} for g, c, cn, code, n, k in (
        ("a", "55001", "Adams", "00001", "Alder", "C"), ("b", "55003", "Ashland", "00001", "Alder", "C"), ("c", "55003", "Ashland", "00012", "Elm", "V"),
        ("d", "55003", "Ashland", "00031", "Gum", "T"), ("e", "55001", "Adams", "00041", "Pine", "V"), ("f", "55003", "Ashland", "00051", "Oak", "V"))]
    wards = {"senate_of": {"1": "1", "2": "2"}, "wards": {"w1": [9, [["1", "1", 9]]], "w2": [9, [["2", "2", 6], ["1", "1", 3]]], "w3": [9, [["2", "2", 9]]],
                                                          "w4": [9, [["1", "1", 9]]], "w5": [9, [["1", "1", 9]]]}}
    contests = [{"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President", "prefix": "PRE", "dem": "A/B", "rep": "C/D", "official": "x"},
                {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor", "prefix": "GOV", "dem": "E/F", "rep": "G/H", "official": "x"}]
    tables = {2024: {"fields": f24, "rows": t24, "layer_name": "made up", "fetched": "-"}, 2022: {"fields": f22, "rows": t22, "layer_name": "made up", "fetched": "-"}}
    official = {"2024-president": {"dem": 63, "rep": 72, "other": 6, "total": 141, "source": "x", "where": "-", "read": "-"},
                "2022-governor": {"dem": 24, "rep": 34, "other": 1, "total": 59, "source": "x", "where": "-", "read": "-"}}
    district = {"house": {"1": [18, 37], "2": [39, 45]}, "senate": {"2": [41, 44]}}
    args = (tables, {"rows": today, "layer_name": "made up", "fetched": "-"}, wards, official, [], None, district, None, contests, False)
    doc, failed = build(*args)
    p, checks = doc["places"], []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    check("the control holds on the made-up table", (doc["control"]["result"], failed), ("equal", []))
    check("a city in two counties is one place", p["mcd"]["WI-M-00001"]["votes"]["2024-president"], {"dem": 23, "rep": 17, "other": 1, "total": 41})
    check("and reaches both counties", p["mcd"]["WI-M-00001"]["counties"], ["55001", "55003"])
    check("a county adds up its wards", p["county"]["55003"]["votes"]["2024-president"], {"dem": 43, "rep": 37, "other": 5, "total": 85})
    check("a town that became a village under a new code is filed under today's code",
          p["mcd"]["WI-M-00012"]["votes"]["2022-governor"], {"dem": 10, "rep": 20, "other": 1, "total": 31})
    check("rows the table does not name take the name today's table gives their code", p["mcd"]["WI-M-00051"]["name"], "Oak village")
    check("and says which code it was", list(p["mcd"]["WI-M-00012"]["earlier"]), ["WI-M-00011"])
    check("the old code is not kept beside it", "WI-M-00011" in p["mcd"], False)
    check("names in capitals are written ordinarily", p["mcd"]["WI-M-00021"]["name"], "Fir town")
    check("a place with no namesake today stays under its code, marked former", p["mcd"]["WI-M-00021"].get("former"), True)
    check("a place newer than the elections is listed without votes", p["mcd"]["WI-M-00031"]["votes"], {})
    check("a town that became a village under the same code says what it was", p["mcd"]["WI-M-00041"].get("named_then"), {"2024": "Pine town"})
    check("a ward with no figures counts as nothing", doc["coverage"]["wards_without_figures"], {"2024": 1})
    check("a ward goes to the district holding most of it", p["house"]["2"]["votes"]["2024-president"], {"dem": 43, "rep": 37, "other": 5, "total": 85})
    check("and is listed as straddling", [w["points"] for w in doc["coverage"]["wards_straddling_districts"]], [{"2": 6, "1": 3}])
    check("districts are given for 2024 only", list(p["senate"]["1"]["votes"]), ["2024-president"])
    check("a district whose own vote equals the official one is not marked", (p["house"]["1"].get("approximate"), p["senate"]["2"].get("approximate")), (None, None))
    check("a district whose own vote differs is marked approximate, with the difference", p["house"]["2"]["approximate"]["wards_minus_official"], {"dem": 0, "rep": 1})
    check("a contest where every vote went the same way is marked too_few", p["mcd"]["WI-M-00041"].get("too_few"), ["2024-president"])
    check("and so is one with fewer than twenty votes", p["mcd"]["WI-M-00021"].get("too_few"), ["2022-governor"])
    wrong = dict(official, **{"2024-president": dict(official["2024-president"], dem=64, total=142)})
    check("a wrong official total is caught", build(*(args[:3] + (wrong,) + args[4:]))[0]["control"]["result"], "differs")
    try:
        build({2024: dict(tables[2024], rows=[dict(t24[0], PRETOT24=99)] + t24[1:]), 2022: tables[2022]}, *args[1:])
        caught = False
    except Stop:
        caught = True
    check("a ward whose candidates do not add up to its total stops the loader", caught, True)
    book = ["District vote for Wisconsin state representatives, general and", "July 30, 2024 special election", "2 ... Democratic A B ... 9 90.00",
            "November 5, 2024 general election", "12 ... Republican A B* ... 24,101 61.91", "Democratic C D ... 14,801 38.02",
            "2 Republican E F ... 1,000 50.00", "Demcoratic G H ... 900 45.00", "Independent I J ... 100 5.00", "Source: made up"]
    check("the Blue Book's district rows are read by party, the general election only", read_district_votes([_dots(t) for t in book], book[0], ["1", "2"]),
          {"1": [14801, 24101], "2": [900, 1000]})
    square = [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]
    left, right = Shape([[[-1, -1], [7, -1], [7, 11], [-1, 11], [-1, -1]]]), Shape([[[7, -1], [11, -1], [11, 11], [7, 11], [7, -1]]])
    check("a ward's points are counted district by district", place_ward(square, [("1", "1", left), ("2", "1", right)]), [49, [["1", "1", 35], ["2", "1", 14]]])
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Wisconsin place voted in past partisan general elections -> ballot/lean/wi_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/wi_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/wi_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every table and document again, even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic on a made-up table; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
