"""
ballot/oh_place_votes.py - how each Ohio place voted in past partisan general elections, added up from the Secretary
of State's official precinct results, so a page can show the record of a county, a city or a legislative district
without anyone labelling a candidate. Ohio's twin of ballot/mn_place_votes.py, and the file it writes has the same shape.

    python ballot/oh_place_votes.py               reads (or downloads) the workbooks, writes ballot/lean/oh_place_votes.json
    python ballot/oh_place_votes.py --refresh     reads every workbook again even when the extracts on disk are fresh
    python ballot/oh_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/oh_place_votes.py --selftest    the arithmetic on a made-up table; downloads nothing

What it is, and is not
----------------------
For President and U.S. Senator in 2024, Governor and U.S. Senator in 2022, and President in 2020: the votes for the
Democratic ticket, the Republican ticket, every other candidate printed on the ballot together, and the total of those,
for every county, for each city whose precincts the county board names after it, and (2024 only) for each state House
and Senate district made of whole precincts. It is how the people of a place voted then, on the precinct and district
lines in force at that election. It is not a prediction, it says nothing about any candidate on a later ballot or about
any voter, and it turns no nonpartisan office into a partisan one. No database is opened for writing;
ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Write-in votes are not in these counts. The Secretary's precinct workbook says so itself ("Precinct-level data is not
available for write-in candidates"); they are published by county only, in the summary workbook. So "other" is every
other candidate PRINTED on the ballot and "total" is the three counts together, at every level, and each contest's
record says how many write-in votes the state counted (13 to 8,964) so that nobody mistakes the total for the canvass's.

Where the numbers come from
---------------------------
The Ohio Secretary of State's "Official Canvass" workbooks for each general election: one with a row for every precinct
(sheet "Master": county, precinct name and code, registered voters, ballots counted, and the votes of every printed
candidate for every statewide, congressional and General Assembly contest) and one with a row for every county (the
same columns, write-ins included). The Secretary's own website (ohiosos.gov) answers this kit with a 403 and is never
requested. The workbooks are read from the copies the Internet Archive's Wayback Machine took of them at the
Secretary's own addresses (web.archive.org, which serves scripts; the capture's date is in each source's record), or
from a copy John saves by hand under the same file name in states_cache/oh_local/, which is used when it is there. The
file says which, with each workbook's SHA-256.

  - Which columns are the Democratic and the Republican ticket is read from the workbook's own headings ("Kamala D.
    Harris and Tim Walz (D)"); the surnames typed in CONTESTS must be in the heading that carries the party's letter, or
    the loader stops. Those surnames, saying which election this was, are the only names kept.
  - A precinct's state House district is the one whose "State Representative - District N" contest it has votes in;
    the workbook has no district column. In 2024, 117 of 8,878 precincts have votes in two or three House contests:
    they are split between districts, and the workbook does not say how their votes for President divide. A district
    touched by such a precinct is NOT given (61 of 99 House districts; 18 of 33 Senate districts, which 28 precincts
    split); the file lists them with the precincts concerned and with how many of the district's own votes for State
    Representative were cast in whole and in split precincts. Nothing is shared out or estimated.
  - A Senate district is three House districts. Which three is read from the Census Bureau's 2024 block equivalency
    files (every block's House and Senate district), and checked against the workbook: every precinct with votes in a
    State Senator contest must sit in a House district of that Senate district.
  - Districts are given for 2024 only: the 2022 election was held on another plan (the Commission's plan of February
    2022; the plan of September 2023 was first used in 2024 and is the one our 2026 races are on).
  - A city: the precincts of a county whose names are the city's name and then nothing but a ward or precinct mark
    ("MENTOR CITY 1A", "LIMA 3B"). Ohio's workbooks have no column for the city or township, and the 88 boards name
    precincts 88 ways, so this is done strictly: a city is given for a year only when every county the Census Bureau
    lists it in has such precincts, no precinct beginning with its name is left unexplained, and it cannot be mistaken
    for a township of the same name (the board must mark one of them: "XENIA CITY 1" / "XENIA TWP 2"). Anything else
    is left out and listed with the reason. Villages and townships are not given: a township precinct often takes in a
    village and the names do not say. A city's count is a sum of whole precincts named for it; the workbook has no
    city totals to check it against, and the record says how many precincts and registered voters went into it.

The control
-----------
Nothing is written unless all of this holds: for every contest and every printed candidate, the precincts of each of
the 88 counties add up to that county's row in the Secretary's summary workbook, and all of them to its Total row; the
write-in columns of the precinct workbook are empty; counties add up to the statewide sum; every precinct with votes
has a House district; and, for President and U.S. Senator, the Democratic and Republican sums and the total with the
summary's write-ins equal the Clerk of the U.S. House's "Statistics of the Presidential and Congressional Election"
(Ohio page, read from the PDF at each run with ballot/pdftext.py). Governor 2022 has the Secretary's own canvass as
its only control. The figures this loader was checked against on 2026-10-02 are typed below (CHECKED).
"""

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import sqlite3
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402

METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "oh_local")
OUT = os.path.join(HERE, "ballot", "lean", "oh_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "39"
FEW = 20                       # a contest with fewer votes than this in a place is marked too_few
AGENCY = "Ohio Secretary of State"

SOS = "https://www.ohiosos.gov/globalassets/elections/"
WAYBACK = "https://web.archive.org/web/{stamp}id_/{url}"
# Each election's two workbooks: the Secretary's own address, and the Wayback Machine capture read in its place.
WORKBOOKS = {
    2024: {"date": "2024-11-05", "title": "November 5, 2024 General Election Official Canvass",
           "precinct": ("2024/gen/official/statewide-races-precint-level.xlsx", "20241222221124"),
           "summary": ("2024/gen/official/statewide-race-summary.xlsx", "20241207004035")},
    2022: {"date": "2022-11-08", "title": "November 8, 2022 General Election Official Canvass",
           "precinct": ("2022/gen/statewide-races-by-precinct.xlsx", "20250312114330"),
           "summary": ("2022/gen/statewide-races-summary.xlsx", "20221229143511")},
    2020: {"date": "2020-11-03", "title": "November 3, 2020 General Election Official Canvass",
           "precinct": ("2020/gen/statewideresultsbyprecinct.xlsx", "20210128112908"),
           "summary": ("2020/gen/statewideresultsbycounty.xlsx", "20201127195210")},
}
CENSUS = "https://www2.census.gov/"
CODES = {
    "county": ("st39_oh_cou2020.txt", CENSUS + "geo/docs/reference/codes2020/cou/st39_oh_cou2020.txt"),
    "place": ("st39_oh_place2020.txt", CENSUS + "geo/docs/reference/codes2020/place/st39_oh_place2020.txt"),
    "cousub": ("st39_oh_cousub2020.txt", CENSUS + "geo/docs/reference/codes2020/cousub/st39_oh_cousub2020.txt"),
}
BEF = {"house": ("sldl24.zip", "39_OH_SLDL24.txt", CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip"),
       "senate": ("sldu24.zip", "39_OH_SLDU24.txt", CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip")}
PLAN_YEAR = 2024               # the first election on the plan our 2026 legislative races are on

# The contests. "dem" and "rep" are the tickets' surnames; the workbook heading with (D) or (R) must carry them.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States", "heading": "President and Vice President",
     "dem": "Harris/Walz", "rep": "Trump/Vance", "official": "clerk-statistics-2024", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2024-us-senate", "year": 2024, "office": "United States Senator", "heading": "U.S. Senator",
     "dem": "Brown", "rep": "Moreno", "official": "clerk-statistics-2024", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "office": "Governor and Lieutenant Governor", "heading": "Governor and Lieutenant Governor",
     "dem": "Whaley/Stephens", "rep": "DeWine/Husted", "official": None, "section": None},
    {"id": "2022-us-senate", "year": 2022, "office": "United States Senator", "heading": "U.S. Senator",
     "dem": "Ryan", "rep": "Vance", "official": "clerk-statistics-2022", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2020-president", "year": 2020, "office": "President and Vice President of the United States", "heading": "President and Vice President",
     "dem": "Biden/Harris", "rep": "Trump/Pence", "official": "clerk-statistics-2020", "section": "FOR PRESIDENTIAL ELECTORS"},
]
# The statewide sums this loader was checked against on 2026-10-02 (precincts = the summary workbook's Total row; dem
# and rep = the Clerk's statistics). A run that finds other figures says so.
CHECKED = {
    "2024-president": {"dem": 2533699, "rep": 3180116, "other": 51202, "total": 5765017},
    "2024-us-senate": {"dem": 2650949, "rep": 2857383, "other": 195648, "total": 5703980},
    "2022-governor": {"dem": 1545489, "rep": 2580424, "other": 0, "total": 4125913},
    "2022-us-senate": {"dem": 1939489, "rep": 2192114, "other": 0, "total": 4131603},
    "2020-president": {"dem": 2679165, "rep": 3154834, "other": 86381, "total": 5920380},
}
CLERK_DOCS = {
    y: {"id": f"clerk-statistics-{y}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
        "title": f"Statistics of the {'Presidential and ' if y % 4 == 0 else ''}Congressional Election from Official Sources for the Election of {d}",
        "url": f"https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf", "file": f"clerk_statistics{y}.pdf"}
    for y, d in ((2024, "November 5, 2024"), (2022, "November 8, 2022"), (2020, "November 3, 2020"))}

# A board's short name for a city, typed by hand where the precinct names leave no doubt (county, start of the name).
ALIASES = {("Franklin", "COLS"): "Columbus", ("Hamilton", "INDIAN HILL"): "The Village of Indian Hill"}
SWAPS = [("SAINT", "ST"), ("MOUNT", "MT"), ("NORTH", "N"), ("NORTH", "NO"), ("SOUTH", "S"), ("SOUTH", "SO"), ("EAST", "E"), ("WEST", "W"),
         ("HEIGHTS", "HTS")]
MUNI_MARK = {"CITY", "CORP", "VILLAGE", "VILL", "VIL", "VLG"}
TWP_MARK = {"TWP", "TOWNSHIP", "TP", "TS", "TWN", "TWSP", "TWPS", "TW"}
MARK_WORDS = {"WARD", "WD", "PCT", "PREC", "PRECINCT", "NO", "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL", "N", "S", "E", "W", "NE", "NW", "SE", "SW",
              "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
              "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH"}

KINDS = [
    ("county", "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("mcd", "Cities whose precincts the county board names after them", "OH-M- and the five-digit Census place code, as sl_places kind mcd"),
    ("senate", "State Senate districts of the plan first used in 2024, where made of whole precincts", "district number, as the district of our Senate races"),
    ("house", "State House districts of the plan first used in 2024, where made of whole precincts", "district number, as the district of our House races"),
]
KIND_NAMES = [k[0] for k in KINDS]
VOTE_KEYS = ["dem", "rep", "other", "total"]

WHAT = ("How each Ohio place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic ticket, the "
        "Republican ticket, every other candidate printed on the ballot together, and the total of those, added up from the Ohio Secretary of "
        "State's official precinct results.")
NOTE = ("What this is: how the people of a place voted in that election, in the Secretary of State's official canvass precinct by precinct, "
        "added up here by county, by city and, for 2024, by legislative district, on the precinct and district lines in force at that "
        "election. What this is not: it is not a prediction of any election; it says nothing about any candidate on a later ballot or about "
        "any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where land was annexed or a district was "
        "redrawn, the figures are for the lines of that year. Write-in votes are not in these counts: the Secretary publishes them by county "
        "only, so the total here is the total for the candidates printed on the ballot. A city is the precincts its county board names after "
        "it; a city whose precincts cannot be told apart by name is not given. A legislative district is given only where it is made of whole "
        "precincts; where a precinct is split between districts the official results do not say how its votes divide, and nothing is "
        "estimated. The tickets are named, as the Secretary's workbook names them, only to say which election this was. In a place with very "
        "few voters the split would come close to saying how particular people voted; those contests are listed in the place's too_few, and a "
        "page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every other "
               "candidate printed on the ballot; write-ins are not counted below the county and are left out everywhere) and total (the three "
               "together). Minnesota's file calls the first count dfl. A contest a place does not have was not held on its lines, or the place "
               "could not be added up for that year.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
WHY_NOT_EARLIER = ("The 2022 and 2020 elections were held on other district plans; the plan adopted in September 2023 was first used in 2024, "
                   "so only the 2024 contests are given.")


class Stop(SystemExit):
    pass


# ---------------------------------------------------------------- small things

def _now():
    return dt.date.today().isoformat()


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _save(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def sort_key(key):
    return [int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", key)]


def _count(v, what):
    if v is None or v == "":
        return 0
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or v < 0:
        raise Stop(f"    {what} is {v!r}, not a count of votes; stopping")
    return int(v)


# ---------------------------------------------------------------- the Secretary's workbooks

def fetch_workbook(year, which, cache, say):
    """The path of one workbook, its record for the sources list. A copy already in the cache (John's own save, or an
    earlier download) is used as it is; otherwise the Wayback Machine's capture is downloaded. ohiosos.gov is never asked."""
    rel, stamp = WORKBOOKS[year][which]
    path = os.path.join(cache, f"sos_{year}_statewide_{which}.xlsx")
    had = os.path.exists(path) and os.path.getsize(path) > 0
    url = WAYBACK.format(stamp=stamp, url=SOS + rel)
    if not had:
        net.download(url, path, 3650, tries=4, say=say)
        time.sleep(2.0)
    with open(path, "rb") as fh:
        if fh.read(2) != b"PK":
            raise Stop(f"    {os.path.basename(path)} is not a workbook; delete it and run this again")
    return path, {"address": SOS + rel, "read_from": url, "capture": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}", "file": os.path.basename(path),
                  "on_disk_since": _day(path), "sha256": _sha_file(path)}


def read_master(path, lead):
    """The "Master" sheet: (the note in its first cell, [(contest heading, candidate heading)] for each column, rows).
    `lead` is how many columns come before the first contest (8 in the precinct workbook, 6 in the summary)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    if "Master" not in wb.sheetnames:
        raise Stop(f"    {os.path.basename(path)} has no sheet named Master; stopping")
    it = wb["Master"].iter_rows(values_only=True)
    r0, r1 = next(it), next(it)
    cols, contest = [], None
    for i, (a, b) in enumerate(zip(r0, r1)):
        if i >= lead and a is not None:
            contest = _clean(a)
        cols.append((contest if i >= lead else None, _clean(b)))
    rows = [list(r) for r in it]
    wb.close()
    return _clean(r0[0]), cols, rows


def extract(year, cache, refresh, say):
    """What this loader needs of one election's two workbooks, kept as a small JSON beside them (reading the workbooks
    takes a minute; the extract carries their SHA-256s and is made again when either changes)."""
    recs, paths = {}, {}
    for which in ("precinct", "summary"):
        paths[which], recs[which] = fetch_workbook(year, which, cache, say)
    out = os.path.join(cache, f"sos_{year}_extract.json")
    if not refresh and os.path.exists(out):
        doc = _load(out)
        if doc.get("method") == METHOD and all(doc["workbooks"][w]["sha256"] == recs[w]["sha256"] for w in recs):
            doc["workbooks"] = recs
            return doc
    say(f"      {year}: reading the precinct and summary workbooks (about a minute)")
    mine = [c for c in CONTESTS if c["year"] == year]
    note, cols, rows = read_master(paths["precinct"], 8)
    want = ["County Name", "Precinct Name", "Precinct Code", "Region Name", "Media Market", "Registered Voters", "Ballots Counted"]
    if [b for _c, b in cols[:7]] != want:
        raise Stop(f"    {year} precinct workbook: the first columns are {[b for _c, b in cols[:7]]}, not {want}; stopping")
    if "write-in" not in note.lower() or "precinct-level data is not available" not in note.lower():
        raise Stop(f"    {year} precinct workbook: its note no longer says write-ins are left out of the precinct rows; stopping")
    by = collections.defaultdict(list)
    for i, (c, _b) in enumerate(cols):
        if c:
            by[c].append(i)
    heads = {c["id"]: [cols[i][1] for i in by.get(c["heading"], [])] for c in mine}
    for c in mine:
        if not heads[c["id"]]:
            raise Stop(f"    {year} precinct workbook: no columns under '{c['heading']}'; stopping")
    house = {int(m.group(1)): ix for c, ix in by.items() for m in [re.match(r"State Representative - District (\d+)$", c)] if m}
    senate = {int(m.group(1)): ix for c, ix in by.items() for m in [re.match(r"State Senator - District (\d+)$", c)] if m}
    if len(house) != 99:
        raise Stop(f"    {year} precinct workbook: {len(house)} State Representative contests, not 99; stopping")
    precincts, total = [], None
    for r in rows:
        if r[0] is None:
            continue
        name = _clean(r[0])
        if name == "Percentage":
            continue
        where = f"{year} {name} {_clean(r[1])}"
        votes = {c["id"]: [_count(r[i], where) for i in by[c["heading"]]] for c in mine}
        if name == "Total":
            total = votes
            continue
        hd = {str(d): n for d, n in ((d, sum(_count(r[i], where) for i in ix)) for d, ix in house.items()) if n}
        sd = {str(d): n for d, n in ((d, sum(_count(r[i], where) for i in ix)) for d, ix in senate.items()) if n}
        precincts.append({"county": name, "name": _clean(r[1]), "code": _clean(r[2]), "registered": _count(r[5], where), "ballots": _count(r[6], where),
                          "votes": votes, "house": hd, "senate": sd})
    _n, scols, srows = read_master(paths["summary"], 6)
    sby = collections.defaultdict(list)
    for i, (c, _b) in enumerate(scols):
        if c:
            sby[c].append(i)
    summary = {}
    for c in mine:
        sh = [scols[i][1] for i in sby.get(c["heading"], [])]
        if sh != heads[c["id"]]:
            raise Stop(f"    {year}: the summary workbook's columns under '{c['heading']}' are not the precinct workbook's; stopping")
    for r in srows:
        if r[0] is None or _clean(r[0]) == "Percentage":
            continue
        summary[_clean(r[0])] = {c["id"]: [_count(r[i], f"{year} summary {_clean(r[0])}") for i in sby[c["heading"]]] for c in mine}
    doc = {"method": METHOD, "year": year, "made": _now(), "workbooks": recs, "note": note, "headings": heads, "precincts": precincts,
           "precinct_total_row": total, "summary": summary, "senate_contests": sorted(senate)}
    _save(out, doc)
    return doc


# ---------------------------------------------------------------- Census code lists and the district plan

def read_codes(cache, say):
    """County names -> FIPS; each county's incorporated places and townships, from the Census Bureau's 2020 code lists."""
    text = {}
    for key, (name, url) in CODES.items():
        path = os.path.join(cache, name)
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            net.download(url, path, 3650, tries=4, say=say)
            time.sleep(1.0)
        with open(path, encoding="utf-8") as fh:
            text[key] = [ln.rstrip("\n").split("|") for ln in fh.read().splitlines()[1:] if ln.strip()]
    counties = {f[4].replace(" County", ""): STATE_FIPS + f[2] for f in text["county"]}
    places = collections.defaultdict(list)                # county name -> [(place code, name, type, [county names])]
    for f in text["place"]:
        m = re.match(r"^(.*) (city|village)$", f[4])
        if f[5] != "INCORPORATED PLACE" or not m:
            continue
        cs = [c.replace(" County", "").strip() for c in f[8].split("~~~")]
        for c in cs:
            places[c].append((f[2], m.group(1), m.group(2), cs))
    townships = collections.defaultdict(set)
    for f in text["cousub"]:
        m = re.match(r"^(.*) township$", f[6])
        if m:
            townships[f[3].replace(" County", "")].add(norm(m.group(1)))
    return {"counties": counties, "places": dict(places), "townships": dict(townships),
            "files": {k: {"file": n, "url": u, "sha256": _sha_file(os.path.join(cache, n))} for k, (n, u) in CODES.items()}}


def read_nesting(cache, refresh, say):
    """{House district: Senate district} of the 2024 plan, from the Census Bureau's block equivalency files: every block's
    House and Senate district, joined block by block. Kept as a small JSON."""
    out = os.path.join(cache, "oh_sld_nesting_2024.json")
    if not refresh and os.path.exists(out):
        return _load(out)
    blocks, files = {}, {}
    for kind in ("house", "senate"):
        name, member, url = BEF[kind]
        path = os.path.join(cache, name)
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            net.download(url, path, 3650, tries=4, say=say)
        files[kind] = {"file": name, "member": member, "url": url, "sha256": _sha_file(path)}
        with zipfile.ZipFile(path) as z, z.open(member) as fh:
            rd = io.TextIOWrapper(fh, encoding="utf-8")
            next(rd)
            blocks[kind] = dict(ln.strip().split(",")[:2] for ln in rd if ln.strip())
    pairs = collections.defaultdict(collections.Counter)
    for b, h in blocks["house"].items():
        s = blocks["senate"].get(b)
        if h.isdigit() and s and s.isdigit():
            pairs[int(h)][int(s)] += 1
    bad = {h: dict(c) for h, c in pairs.items() if len(c) != 1}
    if bad or len(pairs) != 99:
        raise Stop(f"    the block equivalency files do not put each of 99 House districts in one Senate district ({len(pairs)} districts; {bad}); stopping")
    doc = {"made": _now(), "blocks": len(blocks["house"]), "files": files, "senate_of": {str(h): next(iter(c)) for h, c in sorted(pairs.items())}}
    _save(out, doc)
    return doc


# ---------------------------------------------------------------- a city's precincts, by name

def norm(name):
    s = re.sub(r"^PRECINCT\s+", "", (name or "").upper())
    return re.sub(r"\s+", " ", s.replace(".", "").replace("'", "")).strip()


def variants(city):
    base = norm(re.sub(r"^The Village of ", "", city))
    out, words = {base}, base.split(" ")
    for long, short in SWAPS:
        if long in words and len(words) > 1:
            out.add(" ".join(short if w == long else w for w in words))
    return out


def tail_kind(tail):
    """What follows a place's name in a precinct's name: 'mark' (nothing, or only a ward or precinct mark), 'muni'
    (CITY, VILLAGE or CORP and then a mark), 'twp' (a township's precinct), or None (something else: not understood)."""
    toks = [t for t in re.split(r"[\s\-/#,&]+", tail) if t]
    kind = "mark"
    if toks and toks[0] in TWP_MARK:
        return "twp"
    if toks and toks[0] in MUNI_MARK:
        kind, toks = "muni", toks[1:]
    for t in toks:
        if t in TWP_MARK:
            return "twp"
        if not (t in MARK_WORDS or re.fullmatch(r"\d{1,3}[A-Z]{0,2}|[A-Z]{1,2}\d{0,3}", t)):
            return None
    return kind


def city_precincts(county, names, codes):
    """{place code: [precinct names]} for the cities of one county that can be told by name, and {place code: reason}
    for those that cannot. `names` are the county's precinct names in one year."""
    places = codes["places"].get(county, [])
    twps = codes["townships"].get(county, set())
    table = []                                              # (variant, place code)
    for fp, pname, _typ, _cs in places:
        table += [(v, fp) for v in variants(pname)]
    table += [(norm(a), fp) for (c, a), target in ALIASES.items() if c == county for fp, pname, _t, _cs in places if pname == target]
    table.sort(key=lambda x: -len(x[0]))
    hits = collections.defaultdict(list)                    # place code -> [(precinct, tail kind, variant)]
    for n in names:
        s = norm(n)
        for v, fp in table:                                 # the longest name that fits wins: BEDFORD HEIGHTS before BEDFORD
            if s == v or (s.startswith(v) and s[len(v)] in " -/#"):
                hits[fp].append((n, tail_kind(s[len(v):]), v))
                break
    good, why = {}, {}
    for fp, pname, typ, _cs in places:
        if typ != "city":
            continue
        got = hits.get(fp, [])
        if not got:
            why[fp] = f"no precinct of {county} County is named for it"
            continue
        unclear = [n for n, k, _v in got if k is None]
        if unclear:
            why[fp] = f"{len(unclear)} precinct{'s' if len(unclear) != 1 else ''} of {county} County beginning with its name could not be read as a ward or precinct mark"
            continue
        mine = [n for n, k, _v in got if k in ("mark", "muni")]
        if variants(pname) & twps:                          # a township of the same name: the board must mark one of them
            marked_twp = any(k == "twp" for _n, k, _v in got)
            if not marked_twp and any(k == "mark" for _n, k, _v in got):
                why[fp] = f"{county} County has a township of the same name and the precinct names do not say which is which"
                continue
        if not mine:
            why[fp] = f"the precincts of {county} County beginning with its name are a township's"
            continue
        good[fp] = mine
    return good, why


# ---------------------------------------------------------------- the Clerk's statistics

def read_clerk(path):
    """The Ohio page of the Clerk of the House's election statistics: {section heading: [(label, votes)]} for the
    presidential electors (by party) and United States Senator (candidate, party), and the page it is printed on."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == "OHIO"), None)
    if start is None:
        raise ValueError("no OHIO heading")
    page = lines[start][0]
    top = next(t.strip() for p, _y, t in lines if p == page)
    sections, section = {}, None
    for _p, _y, t in lines[start + 1:]:
        t = t.strip()
        if t.startswith("FOR UNITED STATES REPRESENTATIVE"):
            break
        if t.startswith("FOR "):
            section = t
            sections[section] = []
            continue
        m = re.match(r"^(.*?)\s*\.{3,}\s*([\d,]+)$", t)
        if section and m:
            sections[section].append((m.group(1).strip(), int(m.group(2).replace(",", ""))))
        elif section and t:
            raise ValueError(f"a line under {section} is not a name, dots and a number")
    return {"printed_page": int(top) if top.isdigit() else None, "pdf_page": page, "sections": sections}


def clerk_figures(parsed, section):
    lines = parsed["sections"].get(section) or []
    party = (lambda s: s) if section == "FOR PRESIDENTIAL ELECTORS" else (lambda s: s.rsplit(",", 1)[-1].strip())
    dem = [v for s, v in lines if party(s).lower().startswith("democrat")]
    rep = [v for s, v in lines if party(s) == "Republican"]
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{section}: {len(dem)} Democratic and {len(rep)} Republican lines, not one of each")
    return {"dem": dem[0], "rep": rep[0], "all_votes": sum(v for _s, v in lines)}


def clerk_totals(contests, cache, say):
    """{contest id: {dem, rep, all_votes, where, read}} for the contests the Clerk covers, and the documents' records."""
    out, docs = {}, []
    for year in sorted({c["year"] for c in contests if c.get("official")}, reverse=True):
        src = CLERK_DOCS[year]
        rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
        path = os.path.join(cache, src["file"])
        try:
            net.download(src["url"], path, 3650, tries=3, say=say)
            parsed = read_clerk(path)
            rec.update(fetched=_day(path), sha256=_sha_file(path),
                       where=f"Ohio, page {parsed['printed_page']}" if parsed["printed_page"] else f"Ohio, page {parsed['pdf_page']} of the PDF")
            for c in contests:
                if c.get("official") == src["id"]:
                    out[c["id"]] = dict(clerk_figures(parsed, c["section"]), source=src["id"], where=rec["where"], read=f"from the document on {rec['fetched']}")
        except Exception as e:  # noqa: BLE001  the Secretary's own canvass is the first control; the Clerk's is said to be unread
            say(f"      {src['title']}: could not be read ({e}); the control rests on the Secretary's summary workbook and the figures typed in on 2026-10-02")
            rec.update(unread=f"could not be read on {_now()}: {e}")
        docs.append(rec)
    return out, docs


# ---------------------------------------------------------------- adding up

def sides(c, heads):
    """Which of a contest's columns is the Democratic ticket, the Republican ticket, another printed candidate, a write-in."""
    def has(h, ticket):
        return all(re.search(rf"\b{re.escape(s)}\b", h) for s in ticket.split("/"))
    dem = [i for i, h in enumerate(heads) if h.endswith("(D)")]
    rep = [i for i, h in enumerate(heads) if h.endswith("(R)")]
    if len(dem) != 1 or len(rep) != 1 or not has(heads[dem[0]], c["dem"]) or not has(heads[rep[0]], c["rep"]):
        raise Stop(f"    {c['id']}: the workbook's headings {heads} do not carry one (D) column for {c['dem']} and one (R) column for {c['rep']}; stopping")
    wi = [i for i, h in enumerate(heads) if "(WI)" in h]
    return {"dem": dem[0], "rep": rep[0], "wi": wi, "others": [i for i in range(len(heads)) if i not in (dem[0], rep[0]) and i not in wi]}


def four(v, k):
    d, r, o = v[k["dem"]], v[k["rep"]], sum(v[i] for i in k["others"])
    return [d, r, o, d + r + o]


def few(rec):
    hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
    if hold:
        rec["too_few"] = hold
    return rec


def tally(tables, codes, nesting, contests):
    """Everything the workbooks say, added up. Returns (places, statewide sums, control lines that failed, the record of
    the control, coverage notes)."""
    failed, per, state, write_ins = [], {}, {}, {}
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    add = lambda kind, key, cid, v: votes[kind][key].__setitem__(cid, [a + b for a, b in zip(votes[kind][key].get(cid, [0, 0, 0, 0]), v)])  # noqa: E731
    city_meta = collections.defaultdict(lambda: {"precincts": {}, "registered": {}})
    city_why = collections.defaultdict(dict)                # place code -> {year: reason}
    split, not_given = {"house": {}, "senate": {}}, {"house": {}, "senate": {}}
    leg = {k: {False: collections.Counter(), True: collections.Counter()} for k in ("house", "senate")}
    counts = {}
    for year in sorted(tables, reverse=True):
        t = tables[year]
        mine = [c for c in contests if c["year"] == year]
        ks = {c["id"]: sides(c, t["headings"][c["id"]]) for c in mine}
        rows = t["precincts"]
        counts[str(year)] = len(rows)
        unknown = sorted({r["county"] for r in rows} ^ set(codes["counties"]))
        if unknown or set(t["summary"]) - {"Total"} != set(codes["counties"]):
            raise Stop(f"    {year}: the workbooks' counties are not Ohio's 88 ({unknown}); stopping")
        # counties, the statewide sum, and the control against the summary workbook
        county_sum = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
        for r in rows:
            for c in mine:
                v = r["votes"][c["id"]]
                cur = county_sum[r["county"]][c["id"]]
                county_sum[r["county"]][c["id"]] = v if cur is None else [a + b for a, b in zip(cur, v)]
        for c in mine:
            cid, k, heads = c["id"], ks[c["id"]], t["headings"][c["id"]]
            printed = [i for i in range(len(heads)) if i not in k["wi"]]
            tot = [sum(county_sum[n][cid][i] for n in county_sum) for i in range(len(heads))]
            off = t["summary"]["Total"][cid]
            wrong = [n for n in sorted(county_sum) if any(county_sum[n][cid][i] != t["summary"][n][cid][i] for i in printed)]
            if any(tot[i] for i in k["wi"]):
                failed.append(f"{cid}: the precinct workbook's write-in columns are not empty")
            if wrong:
                failed.append(f"{cid}: the precincts of {len(wrong)} counties do not add up to the summary workbook's rows ({', '.join(wrong[:8])})")
            if any(tot[i] != off[i] for i in printed):
                failed.append(f"{cid}: the precincts add up to {[tot[i] for i in printed]} and the summary's Total row is {[off[i] for i in printed]}")
            if t.get("precinct_total_row") and any(tot[i] != t["precinct_total_row"][cid][i] for i in printed):
                failed.append(f"{cid}: the precincts do not add up to the precinct workbook's own Total row")
            state[cid] = four(tot, k)
            write_ins[cid] = sum(off[i] for i in k["wi"])
            per[cid] = {"sum_of_precincts": dict(zip(VOTE_KEYS, state[cid])), "official": dict(zip(VOTE_KEYS, four(off, k))),
                        "equal": not wrong and all(tot[i] == off[i] for i in printed), "source": f"oh-sos-canvass-{year}",
                        "where": "the summary workbook's Total row, and its row for each of the 88 counties, candidate by candidate",
                        "counties_equal": 88 - len(wrong), "write_ins_in_the_summary_only": write_ins[cid]}
            for n in county_sum:
                add("county", codes["counties"][n], cid, four(county_sum[n][cid], k))
        # cities
        by_county = collections.defaultdict(list)
        for r in rows:
            by_county[r["county"]].append(r)
        found = collections.defaultdict(dict)                 # place code -> {county: [rows]}
        for n, rs in by_county.items():
            good, why = city_precincts(n, [r["name"] for r in rs], codes)
            for fp, reason in why.items():
                city_why[fp].setdefault(str(year), reason)
            for fp, pnames in good.items():
                keep = set(pnames)
                found[fp][n] = [r for r in rs if r["name"] in keep]
        whole = {fp: cs for n, ps in codes["places"].items() for fp, _p, typ, cs in ps if typ == "city"}
        for fp, got in found.items():
            if set(got) != set(whole[fp]):
                continue                                    # a county it lies in gave a reason above
            rs = [r for n in got for r in got[n]]
            for c in mine:
                for r in rs:
                    add("mcd", f"OH-M-{fp}", c["id"], four(r["votes"][c["id"]], ks[c["id"]]))
            city_meta[fp]["precincts"][str(year)] = len(rs)
            city_meta[fp]["registered"][str(year)] = sum(r["registered"] for r in rs)
        # legislative districts, on the plan's first election only
        if year == PLAN_YEAR and nesting:
            sen_of = {str(h): str(s) for h, s in nesting["senate_of"].items()}
            for r in rows:
                has_votes = any(sum(r["votes"][c["id"]]) for c in mine)
                hs = sorted(r["house"], key=int)
                if not hs:
                    if has_votes:
                        failed.append(f"{year} {r['county']} {r['name']}: votes, but none in any State Representative contest, so no district")
                    continue
                for s, n in r["senate"].items():
                    if n and s not in {sen_of[h] for h in hs}:
                        failed.append(f"{year} {r['county']} {r['name']}: votes for State Senator in district {s}, which the block equivalency files "
                                      f"do not put House district {', '.join(hs)} in")
                ss = sorted({sen_of[h] for h in hs}, key=int)
                label = f"{r['name']} ({r['county']} County)"
                for kind, ds in (("house", hs), ("senate", ss)):
                    for h in hs:                            # the district's own votes for State Representative, whole precincts and split ones
                        d = h if kind == "house" else sen_of[h]
                        leg[kind][len(ds) > 1][d] += r["house"][h]
                    if len(ds) == 1:
                        for c in mine:
                            add(kind, ds[0], c["id"], four(r["votes"][c["id"]], ks[c["id"]]))
                    else:
                        split[kind][label] = ds
                        for d in ds:
                            not_given[kind].setdefault(d, []).append(label)
            for kind in ("house", "senate"):
                for d in not_given[kind]:
                    votes[kind].pop(d, None)

    pack = lambda d: {cid: dict(zip(VOTE_KEYS, d[cid])) for cid in (c["id"] for c in contests) if cid in d}  # noqa: E731
    name_of = {v: k for k, v in codes["counties"].items()}
    places = {k: {} for k in KIND_NAMES}
    for key in sorted(votes["county"]):
        places["county"][key] = few({"name": f"{name_of[key]} County", "votes": pack(votes["county"][key])})
    pinfo = {fp: (p, cs) for n, ps in codes["places"].items() for fp, p, typ, cs in ps if typ == "city"}
    for key in sorted(votes["mcd"]):
        fp = key[5:]
        rec = few({"name": f"{pinfo[fp][0]} city", "type": "city", "counties": sorted(codes["counties"][c] for c in pinfo[fp][1]),
                   "precincts": city_meta[fp]["precincts"], "registered": city_meta[fp]["registered"], "votes": pack(votes["mcd"][key])})
        missing = {y: why for y, why in city_why.get(fp, {}).items() if y not in rec["precincts"]}
        if missing:
            rec["note"] = "Not added up for " + "; ".join(f"{y}: {why}" for y, why in sorted(missing.items())) + "."
        places["mcd"][key] = rec
    sen_members = collections.defaultdict(list)
    for h, s in sorted((nesting or {}).get("senate_of", {}).items(), key=lambda x: int(x[0])):
        sen_members[str(s)].append(str(h))
    for key in sorted(votes["senate"], key=int):
        places["senate"][key] = few({"name": f"Senate District {key}", "votes": pack(votes["senate"][key]), "house": sen_members.get(key, [])})
    for key in sorted(votes["house"], key=int):
        places["house"][key] = few({"name": f"House District {key}", "votes": pack(votes["house"][key]),
                                    "senate": str((nesting or {}).get("senate_of", {}).get(key, ""))})
    cities_out = {f"OH-M-{fp}": {"name": f"{pinfo[fp][0]} city", "why": why} for fp, why in sorted(city_why.items()) if f"OH-M-{fp}" not in places["mcd"]}
    for cid in state:
        if any(sum(p["votes"][cid][k] for p in places["county"].values()) != state[cid][i] for i, k in enumerate(VOTE_KEYS)):
            failed.append(f"county: the counties do not add up to the statewide sum for {cid}")
    coverage = {"cities_not_given": cities_out,
                "districts_not_given": {kind: {d: {"name": f"{'House' if kind == 'house' else 'Senate'} District {d}", "split_precincts": sorted(v),
                                                   "votes_for_state_representative": {"in_whole_precincts": leg[kind][False][d],
                                                                                      "in_split_precincts": leg[kind][True][d]}}
                                               for d, v in sorted(not_given[kind].items(), key=lambda x: int(x[0]))} for kind in ("house", "senate")},
                "split_precincts": {kind: len(split[kind]) for kind in ("house", "senate")}}
    return places, state, failed, {"precincts": counts, "contests": per}, coverage, write_ins


def build(tables, codes, nesting, clerk, clerk_docs, contests=CONTESTS):
    places, state, failed, ctl, coverage, write_ins = tally(tables, codes, nesting, contests)
    for c in contests:
        cid, got = c["id"], clerk.get(c["id"])
        if not got:
            continue
        mine = dict(zip(VOTE_KEYS, state[cid]))
        ok = mine["dem"] == got["dem"] and mine["rep"] == got["rep"] and mine["total"] + write_ins[cid] == got["all_votes"]
        ctl["contests"][cid]["clerk"] = {"dem": got["dem"], "rep": got["rep"], "all_votes_with_write_ins": got["all_votes"], "equal": ok,
                                         "source": got["source"], "where": got["where"], "read": got["read"]}
        if not ok:
            failed.append(f"{cid}: the precincts give Democratic {mine['dem']:,}, Republican {mine['rep']:,} and, with the summary's write-ins, "
                          f"{mine['total'] + write_ins[cid]:,} votes; the Clerk's statistics give {got['dem']:,}, {got['rep']:,} and {got['all_votes']:,}")
    if contests is CONTESTS:
        if len(places["county"]) != 88:
            failed.append(f"{len(places['county'])} counties, not 88")
        for cid, typed in CHECKED.items():
            if cid in state and dict(zip(VOTE_KEYS, state[cid])) != typed:
                failed.append(f"{cid}: the sums are {dict(zip(VOTE_KEYS, state[cid]))}; this loader was checked against {typed}")
    ctl = {"result": "equal" if not failed else "differs",
           "statement": ("For every contest and every candidate printed on the ballot, the precinct rows of each of the 88 counties add up to "
                         "that county's row in the Secretary's summary workbook and all of them to its Total row; the counties add up to the "
                         "statewide sum; for President and U.S. Senator the Democratic and Republican sums, and the total with the summary's "
                         "write-ins, equal the Clerk of the U.S. House's statistics; and every legislative district given is added up from "
                         "precincts that voted in that district alone." if not failed else "The sums do not all agree; see the differences."),
           "precincts": ctl["precincts"], "contests": ctl["contests"],
           "kinds": {"county": "equal to the statewide sum" if not failed else "see the differences",
                     "mcd": "no control: the workbooks have no city totals; each city's record gives its precincts and registered voters",
                     "senate": "whole precincts only; the districts a split precinct touches are left out",
                     "house": "whole precincts only; the districts a split precinct touches are left out"},
           "notes": ["Governor 2022 is not in the Clerk's statistics; its control is the Secretary's own canvass, county by county."]}
    given = {k: [c["id"] for c in contests if k in ("county", "mcd") or c["year"] == PLAN_YEAR] for k in KIND_NAMES}
    records = []
    for c in contests:
        t = tables[c["year"]]
        heads, k = t["headings"][c["id"]], sides(c, t["headings"][c["id"]])
        records.append({"id": c["id"], "date": WORKBOOKS.get(c["year"], {}).get("date") or c.get("date"), "office": c["office"],
                        "table": f"oh-sos-canvass-{c['year']}", "kinds": [kind for kind in KIND_NAMES if c["id"] in given[kind]],
                        "dem": {"party": "Democratic", "ticket": c["dem"], "column": heads[k["dem"]]},
                        "rep": {"party": "Republican", "ticket": c["rep"], "column": heads[k["rep"]]},
                        "other": {"what": "every other candidate printed on the ballot, together; write-ins are not counted",
                                  "columns": len(k["others"])},
                        "total": {"what": "the three counts together: the votes for candidates printed on the ballot"},
                        "write_ins": {"statewide": write_ins[c["id"]],
                                      "why_not_counted": "The Secretary publishes write-in votes by county only, not by precinct, so they are left out at every level here."},
                        "statewide": dict(zip(VOTE_KEYS, state[c["id"]])),
                        "official_source": f"oh-sos-canvass-{c['year']}"})
    kinds = {}
    for kind, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind], "covers_the_state": kind == "county",
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
    left = {k: len(coverage["districts_not_given"][k]) for k in ("house", "senate")}
    kinds["mcd"]["note"] = ("A city is the precincts its county board names after it (the city's name and then only a ward or precinct mark). "
                            f"{len(coverage['cities_not_given'])} cities whose precincts cannot be told apart by name are not given, nor are "
                            "villages and townships: the official results have no column for them.")
    for k in ("house", "senate"):
        kinds[k]["why_not_earlier"] = WHY_NOT_EARLIER
        kinds[k]["not_given"] = sorted(coverage["districts_not_given"][k], key=int)
        kinds[k]["note"] = (f"A precinct is in the district whose own contest for the Legislature it has votes in. {left[k]} of the "
                            f"{'99 House' if k == 'house' else '33 Senate'} districts take in a precinct that is split between districts; the "
                            "official results do not say how such a precinct's votes divide, so those districts are not given and nothing is estimated.")
    doc = {"what": WHAT, "note": NOTE, "state": "OH", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": VOTE_KEYS, "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": ctl,
           "coverage": dict(coverage, not_given="Villages and townships: the official results have no column for the city, village or township, "
                                                "and a township precinct often takes in a village. School districts likewise."),
           "sources": source_records(tables, codes, nesting, clerk_docs), "places": places}
    return doc, failed


def source_records(tables, codes, nesting, clerk_docs):
    out = []
    for year in sorted(tables, reverse=True):
        t, w = tables[year], WORKBOOKS.get(year, {})
        out.append({"id": f"oh-sos-canvass-{year}", "kind": "official results by precinct, and the official canvass by county", "agency": AGENCY,
                    "title": w.get("title") or t.get("note", "")[:60], "url": (t.get("workbooks") or {}).get("precinct", {}).get("address"),
                    "precincts": len(t["precincts"]), "workbooks": t.get("workbooks"),
                    "accuracy": "The workbooks are headed Official Canvass. Their own note: precinct-level data is not available for write-in candidates.",
                    "how_read": "The Secretary's website refuses scripts and is not requested. Each workbook is read from the copy the Internet "
                                "Archive's Wayback Machine took at the Secretary's own address on the capture date given, or from a copy saved by "
                                "hand under the same file name; the SHA-256 says which bytes were read.",
                    "read": "Of each precinct: its county, name and code, registered voters, ballots counted, the votes of every printed candidate "
                            "in the contests named here, and which State Representative and State Senator contests it has votes in."})
    if codes.get("files"):
        out.append({"id": "census-2020-code-lists-39", "kind": "official code lists", "agency": "U.S. Census Bureau",
                    "title": "2020 ANSI code lists for Ohio: counties, places, county subdivisions", "url": CODES["place"][1], "files": codes["files"],
                    "read": "County codes; each county's cities and villages (to tell a city's precincts by name); township names (to tell a city from a township of the same name)."})
    if nesting and nesting.get("files"):
        out.append({"id": "census-2024-legislative-bef", "kind": "official block equivalency files", "agency": "U.S. Census Bureau",
                    "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip)", "url": BEF["house"][2],
                    "files": nesting["files"], "read": "Which Senate district each House district lies in, joined block by block."})
    return out + clerk_docs


def write(path, doc):
    """The file: the short parts spread out to be read, the places one to a line."""
    head = json.dumps({k: v for k, v in doc.items() if k != "places"}, ensure_ascii=False, indent=1)
    kinds = []
    for kind, d in doc["places"].items():
        rows = ",\n".join(f"   {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, separators=(',', ':'))}" for k, v in d.items())
        kinds.append(f"  {json.dumps(kind)}: {{\n{rows}\n  }}")
    text = head[:head.rstrip().rfind("}")].rstrip() + ',\n "places": {\n' + ",\n".join(kinds) + "\n }\n}\n"
    json.loads(text)                                                    # it must read back
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def our_places(db):
    """{kind: ids} of our Ohio places and legislative districts, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'oh-%'"):
            out[kind].add(pid)
        for ok, d in con.execute("SELECT office_kind, district FROM sl_races WHERE state = 'OH' AND office_kind IN ('state_house', 'state_senate') AND district IS NOT NULL"):
            out["house" if ok == "state_house" else "senate"].add(str(d))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Ohio place votes: the Secretary of State's official canvass, precinct by precinct")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    tables = {}
    for year in sorted({c["year"] for c in CONTESTS}, reverse=True):
        tables[year] = extract(year, cache, refresh, say)
        say(f"      {year}: {len(tables[year]['precincts']):,} precincts (workbook on disk since {tables[year]['workbooks']['precinct']['on_disk_since']})")
    codes = read_codes(cache, say)
    nesting = read_nesting(cache, refresh, say)
    say("    the official statewide totals: the Secretary's summary workbook, and the Clerk of the U.S. House (President and U.S. Senator)")
    clerk, clerk_docs = clerk_totals(CONTESTS, cache, say)
    doc, failed = build(tables, codes, nesting, clerk, clerk_docs)
    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['mcd'])} cities ({len(doc['coverage']['cities_not_given'])} not told apart by name); "
        f"{len(p['senate'])} of 33 Senate and {len(p['house'])} of 99 House districts made of whole precincts")
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,} "
            f"(write-ins apart: {c['write_ins']['statewide']:,}): " + ("equal to" if ctl["equal"] else "DIFFERS from") + " the summary workbook, 88 counties"
            + (("; " + ("equal to" if ctl["clerk"]["equal"] else "DIFFERS from") + f" the Clerk's statistics ({ctl['clerk']['where']})") if "clerk" in ctl else ""))
    if failed:
        for line in failed[:40]:
            say(f"    CHECK: {line}")
        raise Stop(f"    Ohio place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES:
            ids = ours.get(kind, set())
            without = sorted((i for i in ids if not p[kind].get(i, {}).get("votes")), key=sort_key)
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}" + (f" (none for {', '.join(without[:14])}{' ...' if len(without) > 14 else ''})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {_now()}")
    write(out, doc)
    say(f"    Ohio place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.1f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic on a made-up table

def selftest(say=print):
    heads = ["Ann Able and Bo Best (D)", "Cy Cole (WI)*", "Di Dunn and Ed East", "Flo Fox and Gil Gray (R)"]
    contests = [{"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President", "heading": "President", "dem": "Able/Best", "rep": "Fox/Gray",
                 "official": "x", "section": "FOR PRESIDENTIAL ELECTORS"}]

    def pct(county, name, d, o, r, house, senate=None, reg=100):
        return {"county": county, "name": name, "code": "AAA", "registered": reg, "ballots": d + o + r,
                "votes": {"2024-president": [d, 0, o, r]}, "house": house, "senate": senate or {}}
    rows = [pct("Lake", "PRECINCT MENTOR CITY 1A", 30, 2, 20, {"1": 50}, {"1": 50}),
            pct("Lake", "PRECINCT MENTOR CITY 1B", 10, 0, 15, {"1": 25}, {"1": 25}),
            pct("Lake", "PRECINCT MENTOR-ON-THE-LAKE CITY A", 7, 1, 6, {"1": 9, "2": 4}),
            pct("Lake", "PRECINCT PAINESVILLE A", 5, 0, 9, {"2": 14}),
            pct("Lake", "PRECINCT PAINESVILLE B", 4, 0, 4, {"2": 8}),
            pct("Lake", "PRECINCT PERRY TWP", 0, 0, 12, {"3": 12}),
            pct("Stark", "ALLIANCE 1-A", 12, 1, 9, {"3": 20}),
            pct("Stark", "CANTON CITY 6-A", 40, 3, 22, {"4": 60}),
            pct("Stark", "CANTON TWP 6", 9, 0, 21, {"4": 30}),
            pct("Mahoning", "PRECINCT ALL 1", 3, 0, 2, {"4": 5})]

    def summ(*names):
        v = [[sum(r["votes"]["2024-president"][i] for r in rows if r["county"] in names) for i in range(4)]]
        return {"2024-president": v[0]}
    summary = {"Lake": summ("Lake"), "Stark": summ("Stark"), "Mahoning": summ("Mahoning"), "Total": summ("Lake", "Stark", "Mahoning")}
    summary["Total"]["2024-president"][1] = 3                 # write-ins are in the summary only
    tables = {2024: {"headings": {"2024-president": heads}, "precincts": rows, "summary": summary, "precinct_total_row": None, "workbooks": {}, "note": "made up"}}
    codes = {"counties": {"Lake": "39085", "Stark": "39151", "Mahoning": "39099"},
             "places": {"Lake": [("49056", "Mentor", "city", ["Lake"]), ("49098", "Mentor-on-the-Lake", "city", ["Lake"]),
                                 ("59416", "Painesville", "city", ["Lake"])],
                        "Stark": [("01420", "Alliance", "city", ["Stark", "Mahoning"]), ("12000", "Canton", "city", ["Stark"])],
                        "Mahoning": [("01420", "Alliance", "city", ["Stark", "Mahoning"])]},
             "townships": {"Lake": {"PAINESVILLE", "PERRY"}, "Stark": {"CANTON"}}, "files": {}}
    nesting = {"senate_of": {"1": 1, "2": 1, "3": 2, "4": 2}, "files": {}}
    clerk = {"2024-president": {"dem": 120, "rep": 120, "all_votes": 250, "source": "x", "where": "-", "read": "-"}}
    doc, failed = build(tables, codes, nesting, clerk, [], contests)
    p, checks = doc["places"], []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    check("the control holds on the made-up table", (doc["control"]["result"], failed), ("equal", []))
    check("a county adds up its precincts, write-ins left out", p["county"]["39085"]["votes"]["2024-president"], {"dem": 56, "rep": 66, "other": 3, "total": 125})
    check("the write-ins are counted apart", doc["contests"][0]["write_ins"]["statewide"], 3)
    check("a city is the precincts named for it", p["mcd"]["OH-M-49056"]["votes"]["2024-president"], {"dem": 40, "rep": 35, "other": 2, "total": 77})
    check("and says how many precincts that was", p["mcd"]["OH-M-49056"]["precincts"], {"2024": 2})
    check("a longer name is another city (Mentor-on-the-Lake)", p["mcd"]["OH-M-49098"]["votes"]["2024-president"]["total"], 14)
    check("a city with an unmarked township of its name is left out", "OH-M-59416" in p["mcd"], False)
    check("a city the board marks apart from its township is given", p["mcd"]["OH-M-12000"]["votes"]["2024-president"]["total"], 65)
    check("a city with no precinct by its name in one of its counties is left out", "OH-M-01420" in p["mcd"], False)
    check("and the reason is listed", "Mahoning" in doc["coverage"]["cities_not_given"]["OH-M-01420"]["why"]["2024"], True)
    check("a House district touched by a split precinct is not given", sorted(p["house"]), ["3", "4"])
    check("and is listed with the precinct", list(doc["coverage"]["districts_not_given"]["house"]), ["1", "2"])
    check("a precinct split inside one Senate district counts there", p["senate"]["1"]["votes"]["2024-president"]["total"], 113)
    check("a Senate district lists its House districts", p["senate"]["2"]["house"], ["3", "4"])
    check("a place where every vote went one way is marked too_few", p["house"]["3"].get("too_few"), None)
    one = build({2024: dict(tables[2024], precincts=[pct("Lake", "PRECINCT PERRY TWP", 0, 0, 12, {"3": 12}), pct("Stark", "A", 0, 0, 0, {}),
                                                         pct("Mahoning", "B", 0, 0, 0, {})],
                            summary={"Lake": {"2024-president": [0, 0, 0, 12]}, "Stark": {"2024-president": [0, 0, 0, 0]},
                                     "Mahoning": {"2024-president": [0, 0, 0, 0]}, "Total": {"2024-president": [0, 0, 0, 12]}})},
                codes, nesting, {}, [], contests)[0]
    check("every vote the same way is marked too_few", one["places"]["house"]["3"].get("too_few"), ["2024-president"])
    wrong = {"2024-president": dict(clerk["2024-president"], dem=121)}
    check("a wrong official total is caught", build(tables, codes, nesting, wrong, [], contests)[0]["control"]["result"], "differs")
    bad = dict(summary, Lake={"2024-president": [57, 0, 3, 66]})
    check("a county that does not add up to the summary is caught", build({2024: dict(tables[2024], summary=bad)}, codes, nesting, clerk, [], contests)[1] != [], True)
    check("tails: a ward mark, a marked city, a township, something else",
          [tail_kind(" 3-B"), tail_kind(" CITY 1A"), tail_kind(" TWP 2"), tail_kind(" HEIGHTS-01-A")], ["mark", "muni", "twp", None])
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Ohio place voted in past partisan general elections -> ballot/lean/oh_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/oh_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/oh_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="read every workbook again, even when the extracts on disk are fresh")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic on a made-up table; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
