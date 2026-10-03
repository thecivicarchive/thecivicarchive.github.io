"""
ballot/ut_place_votes.py - how each Utah place voted in past partisan general elections, so a page can show the record
of a county or a district without anyone labelling a candidate. The Utah twin of ballot/mn_place_votes.py; the output
has the same shape (the Democratic count is "dem" here, as in the other states' files, where Minnesota's is "dfl").

    python ballot/ut_place_votes.py               reads (or downloads) the files, writes ballot/lean/ut_place_votes.json
    python ballot/ut_place_votes.py --refresh     asks for everything again even when the cached copies are there
    python ballot/ut_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/ut_place_votes.py --selftest    the arithmetic and the district rules on made-up precincts; downloads nothing

What it is, and is not
----------------------
For President, U.S. Senator and Governor in 2024 (precinct by precinct), U.S. Senator in 2022 and President and
Governor in 2020 (county by county): the votes for the Democratic ticket, the Republican ticket, every other candidate
and all write-ins together, and the total, for every one of the 29 counties and the eight judicial districts; for 2024
also for every state House district and every state Senate district whose precincts voted in that district alone (see
below). Utah elected no Democratic nominee for U.S. Senator in 2022: the ballot printed Evan McMullin as unaffiliated,
and his votes are a count of their own ("una") rather than being folded into "other". It is how the people of a place
voted then, on the lines in force at that election. It is not a prediction, it says nothing about any candidate on a
later ballot or about any voter, and it turns no nonpartisan office into a partisan one. No database is opened for
writing; ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Where the numbers come from
---------------------------
  - 2024: the Lieutenant Governor's official results system, electionresults.utah.gov (election general11052024,
    marked official), which answers a plain script with JSON: /results/public/api/elections/<county>/general11052024/
    ballot-items lists each county's contests with the county's own summary of each, and /ballot-items/<id> gives a
    contest's results precinct by precinct ("breakdownResults"). Of each row only the precinct's name and each option's
    name, party abbreviation, write-in mark and count are read. A COUNTY'S FIGURES ARE ITS OWN SUMMARY (equal to the
    statewide contest's row for that county); A DISTRICT'S FIGURES ARE ITS PRECINCT ROWS ADDED UP. The precinct rows of
    22 counties add up to a little less than their summaries (about 1,100 votes of 1.49 million for President): the
    county counted those ballots and put them in no precinct's row, so they are in the county's figures and in no
    district's. Each county also reports its federal-only ballots (voters entitled to President, Senator and Congress
    alone) as a unit named Federal or FED; they too count in the county and in no district. Box Elder County lists
    "Write-in: Invalid" votes as an option; the state's figures leave them out, and so does this file.
  - 2022 and 2020: the State Board of Canvassers' statewide canvass, county by county (vote.utah.gov, "Historical
    election results"). 2020 is a workbook; 2022 is a signed scan with no text, so its U.S. Senate table (two pages) is
    typed below from the scan, with the scan's SHA-256, and must add up to the scan's own printed totals and equal the
    Clerk of the House's statistics. The state's precinct results for 2020 and 2022 are not published in a form a
    script can read (each county posted its own reports), so those years are given for counties and judicial districts
    only.
  - A state House or Senate district (2024) is the precincts that voted in its contest. Every House seat was on the
    2024 ballot, and no precinct row is listed in two House contests. A precinct listed in two contests lies in both,
    and its votes for President, Senator or Governor are given whole, so they cannot be divided without an estimate: a
    district with such a precinct is not given (one Kane County precinct, KA3, is listed in Senate 26 and 27). Only
    about half the Senate seats were on the 2024 ballot (the others, the seats on the 2026 ballot, in 2022). For a
    Senate district not on the 2024 ballot a precinct's district is read from the Legislature's 2022 district plan as
    the Utah Geospatial Resource Center publishes it ("District Combination Areas", one row for each piece of the state
    with its U.S. House, Senate, House and State School Board district): a precinct that voted in no Senate contest lies
    in none of the districts on the 2024 ballot; the pieces that carry the House district, the U.S. House district and
    the State School Board district it voted in (or, where it voted in no board contest, a board district not on that
    ballot) give the Senate districts it can lie in; when only one of them was not on the ballot, the precinct lies in
    that one. Otherwise the precinct is not placed, and no Senate district it may lie in is given; most Senate districts
    not on the 2024 ballot (the seats on the 2026 ballot) are therefore not given. The plan's county column is not used:
    it names one county for pieces that reach into several. The plan is checked on the Senate districts that were on
    the 2024 ballot: every precinct of their contests must lie in pieces that reach the district it voted in. A U.S.
    House or board contest the results system will not give precinct by precinct (it answers 404 for six) is used only
    where it is the county's one contest of its kind and covers every unit of the county.
  - A judicial district is whole counties, listed in section 78A-1-102, Utah Code (read from the Legislature's copy at
    each run and compared with the table below).

Not given: cities and towns. A Utah precinct may lie partly inside and partly outside a city (the law allows it, and the
state's ballot-area map divides such precincts into sub-precincts), most counties report each precinct whole, and the
2024 ballot carried a citywide contest in only a handful of cities; so a city's votes cannot be added up without an
estimate. County council and commission districts, school board, water and other districts: not added up here.

The control
-----------
Nothing is written unless all of this holds: every 2024 precinct row's options (with any invalid write-ins) add up to
the row's own total; each county's summary of a contest equals the statewide contest's row for that county, and its
precinct rows hold no more votes than it, option by option; the counties add up to the statewide summary, which equals
the Clerk of the U.S. House of Representatives' "Statistics of the Presidential and Congressional Election" for
President and U.S. Senator; for 2024 the counties of President and Governor equal the signed statewide canvass, where
its text layer can be read (its Senate pages are pictures without text); every precinct votes in exactly the three
statewide contests and in a House contest; the districts given, the precincts of those left out, the federal-only units
and the votes in no precinct's row add up to the statewide figures; the 2020 workbook's county rows add up to its
TOTAL row; the 2022 typed table adds up to its printed totals and equals the Clerk's 2022 statistics.
"""
import argparse
import collections
import datetime as dt
import hashlib
import html as H
import json
import os
import pathlib
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

METHOD = "1.0"                  # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "ballot_cache", "ut", "votes")
OUT = os.path.join(HERE, "ballot", "lean", "ut_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "49"
FEW = 20
KEEP_DAYS = 3650                # certified results of past elections do not change; --refresh asks again
PAUSE = 0.4                     # seconds between requests to the results system

API = "https://electionresults.utah.gov/results/public/api"
RESULTS_PAGE = "https://electionresults.utah.gov/results/public/Utah/elections/general11052024"
ELECTION_2024 = "general11052024"
AGENCY = "Utah Lieutenant Governor, Office of Elections"
HISTORICAL = "https://vote.utah.gov/historical-election-results/"
CANVASS = {
    2024: {"url": "https://vote.utah.gov/wp-content/uploads/2025/02/2024-General-Election-Statewide-Canvass-2.pdf", "file": "canvass_2024_general.pdf"},
    2022: {"url": "https://vote.utah.gov/wp-content/uploads/2022/12/Signed-2022-General-Election-State-Canvass-Certification.pdf", "file": "canvass_2022_general.pdf"},
    2020: {"url": "https://vote.utah.gov/wp-content/uploads/2021/02/2020-General-Election-Statewide-Canvass.xlsx", "file": "canvass_2020_general.xlsx"},
}
COMBOS = {
    "2022": "https://services1.arcgis.com/99lidPhWCzftIe9K/arcgis/rest/services/DistrictCombinationAreas2022/FeatureServer/0/query",
    "2026": "https://services1.arcgis.com/99lidPhWCzftIe9K/arcgis/rest/services/political_district_combination_areas_2026/FeatureServer/0/query",
}
COMBOS_PAGE = "https://gis.utah.gov/products/sgid/political/district-combination-areas/"
STATUTE = {"id": "ut-code-78a-1-102", "url": "https://le.utah.gov/xcode/Title78A/Chapter1/78A-1-S102.html",
           "title": "Section 78A-1-102, Utah Code (Trial courts of record -- Geographical divisions), as the Legislature publishes it"}
CLERK = {2024: ("November 5, 2024", "Presidential and Congressional"), 2022: ("November 8, 2022", "Congressional"),
         2020: ("November 3, 2020", "Presidential and Congressional")}

COUNTIES = ("Beaver|Box Elder|Cache|Carbon|Daggett|Davis|Duchesne|Emery|Garfield|Grand|Iron|Juab|Kane|Millard|Morgan|"
            "Piute|Rich|Salt Lake|San Juan|Sanpete|Sevier|Summit|Tooele|Uintah|Utah|Wasatch|Washington|Wayne|Weber").split("|")
FIPS = {name: f"{STATE_FIPS}{2 * i + 1:03d}" for i, name in enumerate(COUNTIES)}
COUNTY_NAME = {f: f"{n} County" for n, f in FIPS.items()}

# Section 78A-1-102(1), Utah Code, as read on 2026-10-03; the run reads the Legislature's copy and compares.
JUDICIAL = {1: ["Box Elder", "Cache", "Rich"], 2: ["Weber", "Davis", "Morgan"], 3: ["Salt Lake", "Summit", "Tooele"],
            4: ["Utah", "Wasatch", "Juab", "Millard"], 5: ["Beaver", "Iron", "Washington"],
            6: ["Garfield", "Kane", "Piute", "Sanpete", "Sevier", "Wayne"], 7: ["Carbon", "Emery", "Grand", "San Juan"],
            8: ["Daggett", "Duchesne", "Uintah"]}
ORDINAL = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6, "Seventh": 7, "Eighth": 8}

# The contests: id, year, office, the results system's contest name (2024) and the two nominees as the ballot printed them.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States", "api": r"U\.S\. President",
     "dem": ("Democratic", "Harris and Walz", "KAMALA D. HARRIS / TIM WALZ"), "rep": ("Republican", "Trump and Vance", "DONALD J. TRUMP / JD VANCE"),
     "clerk": "FOR PRESIDENTIAL ELECTORS", "canvass_page": "U.S. President and Vice President"},
    {"id": "2024-us-senate", "year": 2024, "date": "2024-11-05", "office": "United States Senator", "api": r"U\.S\. Senate",
     "dem": ("Democratic", "Gleich", "CAROLINE GLEICH"), "rep": ("Republican", "Curtis", "JOHN CURTIS"), "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2024-governor", "year": 2024, "date": "2024-11-05", "office": "Governor and Lieutenant Governor", "api": r"Governor",
     "dem": ("Democratic", "King and Cummings", "BRIAN SMITH KING REBEKAH CUMMINGS"), "rep": ("Republican", "Cox and Henderson", "SPENCER J. COX DEIDRE M. HENDERSON"),
     "canvass_page": "Governor, Lieutenant Governor"},
    {"id": "2022-us-senate", "year": 2022, "date": "2022-11-08", "office": "United States Senator",
     "rep": ("Republican", "Lee", "MIKE LEE (REP)"), "una": ("Unaffiliated", "McMullin", "EVAN MCMULLIN (UNA)"), "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States", "sheet": "President",
     "dem": ("Democratic", "Biden and Harris", "Joseph R. Biden, Kamala D. Harris (DEM)"), "rep": ("Republican", "Trump and Pence", "Donald J. Trump, Michael R. Pence (REP)"),
     "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-governor", "year": 2020, "date": "2020-11-03", "office": "Governor and Lieutenant Governor", "sheet": "State Offices", "block": "Governor & Lieutenant Governor",
     "dem": ("Democratic", "Peterson and Brown", "Chris Peterson, Karina Brown (DEM)"), "rep": ("Republican", "Cox and Henderson", "Spencer J. Cox, Deidre M. Henderson (REP)")},
]
SIDE_KEYS = ("dem", "rep", "una")
FEDERAL_ONLY = re.compile(r"^fed(?:eral)?\s*(?:district\s*)?\d*$", re.I)

# The 2022 State Board of Canvassers' U.S. Senate table, typed from the signed scan (pages 3 and 4 of the PDF), county by
# county in the scan's order: McMullin (UNA), Hansen (LIB), Lee (REP), Williams (IAP), and the write-ins Korb, Hamblin
# and Seguin. The scan's printed totals follow; the run checks the columns add up to them and equal the Clerk's figures.
SCAN_2022_SHA = "daf3cbd84381efaeb7c4d7af1d6425f93aa18cc2307dc7294b166dcb26b245a1"
SENATE_2022_COLUMNS = ("EVAN MCMULLIN (UNA)", "JAMES ARTHUR HANSEN (LIB)", "MIKE LEE (REP)", "TOMMY WILLIAMS (IAP)",
                       "ABRAHAM KORB (WRITE-IN)", "LAIRD FETZER HAMBLIN (WRITE-IN)", "MICHAEL SEGUIN (WRITE-IN)")
SENATE_2022 = """
Beaver 419 33 1971 24 0 0 0
Box Elder 4725 463 14434 276 0 4 1
Cache 15580 1228 24588 586 2 3 3
Carbon 2114 230 4265 119 0 1 0
Daggett 109 4 377 8 3 0 0
Davis 52806 2897 66385 1654 0 20 13
Duchesne 912 96 5170 103 0 1 1
Emery 712 70 3269 56 0 0 0
Garfield 520 33 1795 37 0 0 0
Grand 2421 250 1901 71 0 0 0
Iron 3755 437 12923 194 0 0 0
Juab 714 70 3886 61 0 0 0
Kane 946 104 2553 56 0 0 0
Millard 701 88 4279 62 0 0 0
Morgan 1358 79 3665 55 0 0 0
Piute 82 6 692 3 0 0 0
Rich 206 14 844 9 0 0 0
Salt Lake 218495 13902 144931 3780 10 57 20
San Juan 1815 338 3118 289 1 1 0
Sanpete 1912 150 7829 113 5 0 0
Sevier 1152 120 6411 92 0 0 0
Summit 12325 553 7305 171 0 1 3
Tooele 7487 809 13371 402 0 5 0
Uintah 1559 203 8905 166 0 0 0
Utah 72238 4949 127096 1762 13 31 11
Wasatch 5429 350 7528 157 0 0 0
Washington 17786 1526 49420 769 1 10 2
Wayne 415 26 1056 17 0 0 0
Weber 31265 2756 42007 1011 2 18 6
"""
SENATE_2022_PRINTED = {"columns": (459958, 31784, 571974, 12103, 37, 152, 60), "contest": 1076068}

KINDS = [
    ("county", "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("judicial", "Judicial districts, as whole counties (a district court's and a juvenile court's district are the same)",
     "JD and the district number (JD3), as the jurisdiction_id of our district and juvenile court races"),
    ("house", "State House districts of the plan first used in 2022", "district number, as the district of our House races"),
    ("senate", "State Senate districts of the plan first used in 2022", "district number, as the district of our Senate races"),
]
WHAT = ("How each Utah place voted in six contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic ticket, "
        "the Republican ticket (and in 2022, when no Democrat was on the ballot for U.S. Senator, the unaffiliated candidate), every other "
        "candidate and all write-ins together and the total, from the Lieutenant Governor's official results (2024: each county's summary, "
        "and the precinct results added up by district) and the State Board of Canvassers' county canvass (2020 and 2022).")
NOTE = ("What this is: how the people of a place voted in that election, in the official results: for 2024 the Lieutenant Governor's official "
        "results, each county's own summary, with the official precinct results added up here by state House and Senate district; for 2020 "
        "and 2022 the State Board of Canvassers' canvass, county by county, so those years are given for counties and judicial districts "
        "only. A judicial district is its counties added up. A district is given only where every precinct of it voted in that district alone: "
        "where a precinct lies in two districts the results give its votes whole, and they are never divided by estimate. A county puts a few "
        "ballots in no precinct's row (about 1 in 1,300 in 2024), and its federal-only ballots in a unit of their own: they are in the county's "
        "figures and in no district's. What this is not: it is not a prediction of any election; it says nothing about any candidate on a "
        "later ballot or about any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where a district was "
        "drawn again, the figures are for the lines of that year. Utah elected its Governor in 2020 and 2024, and in 2022 no Democrat was on "
        "its ballot for U.S. Senator. The tickets are named, as the results name them, only to say which election this was. In a place with "
        "very few voters the split would come close to saying how particular people voted; those contests are listed in the place's too_few, "
        "and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every "
               "other candidate and all write-ins, together) and total (the votes for candidates and counted write-ins). For U.S. Senator in "
               "2022, when no Democrat was on the ballot, the counts are una (Evan McMullin, printed on the ballot as unaffiliated), rep, other "
               "and total. Minnesota's file calls the first count dfl. A contest a place does not have was not counted on its lines: House "
               "and Senate districts are given for 2024 only, and only where no precinct of the district lies in another district too.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all "
           "the same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities and towns: a Utah precinct may lie partly inside and partly outside a city, the results give each precinct whole, and "
             "the 2024 ballot carried a citywide contest in only a handful of cities, so a city's votes cannot be added up without an "
             "estimate. County council and commission districts, school board, water and other districts are not added up here. House "
             "and Senate districts for 2020 and 2022: the state's results of those years are county by county.")
WHY_NOT = ("House and Senate districts are given for 2024 only: the official results of 2020 and 2022 that a script can read are county by "
           "county. A Senate district missing from 2024 has a precinct that lies in it and in another district too, or one that neither the "
           "2024 ballot nor the district plan places in a single district; most of the seats on the 2026 ballot are such districts.")


def say_default(msg):
    print(msg, flush=True)


def _now():
    return dt.date.today().isoformat()


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def _sha_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def fresh(path, refresh, days=KEEP_DAYS):
    return (not refresh) and os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < days * 86400


def get_json(url, path, refresh, waits=(5, 20, 60)):
    """A JSON answer, cached whole; written under another name and renamed, so a half-written copy is never read."""
    from states import net
    if fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    for wait in tuple(waits) + (None,):      # the results system now and then answers a contest it has with 404; asking again later gets it
        try:
            raw = net.get(url, accept="application/json")
            break
        except OSError:
            if wait is None:
                raise
            time.sleep(wait)
    data = json.loads(raw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as fh:
        fh.write(raw)
    os.replace(path + ".part", path)
    time.sleep(PAUSE)
    return data


def get_file(url, path, refresh, say):
    from states import net
    net.download(url, path, 0 if refresh else KEEP_DAYS, tries=4, say=say)
    return path


def text(names):
    return re.sub(r"\s+", " ", str((names or [{}])[0].get("text") or "")).strip()


def letters(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


# ---------- 2024: the results system, precinct by precinct ----------

INVALID = re.compile(r"\binvalid\b", re.I)      # Box Elder County lists "Write-in: Invalid"; the state's figures leave such votes out


def side_of(option, contest):
    """Which count an option of a 2024 contest belongs to: the nominee as the ballot printed the name (and, where the
    county gives one, with the party's abbreviation, brackets or not), else other; None for invalid write-ins."""
    name = letters(text(option.get("name")))
    party = letters((option.get("party") or {}).get("abbreviation") or "")
    if INVALID.search(text(option.get("name"))):
        return None
    for key, abbr in (("dem", "DEM"), ("rep", "REP")):
        if contest.get(key) and name == letters(contest[key][2]):
            if option.get("isWriteIn") or party not in ("", abbr):
                raise SystemExit(f"Utah: {contest['id']}: the option {text(option.get('name'))!r} is not printed as {abbr}")
            return key
        if contest.get(key) and party == abbr and not option.get("isWriteIn"):
            raise SystemExit(f"Utah: {contest['id']}: an {abbr} option is {text(option.get('name'))!r}, not {contest[key][2]!r}")
    return "other"


def four(options, contest, invalid=False):
    """The counts of one row; with invalid=True also the invalid write-ins the row holds (to compare with its own total)."""
    out = {k: 0 for k in SIDE_KEYS if contest.get(k)}
    out.update(other=0, total=0)
    bad, seen = 0, collections.Counter()
    for o in options:
        v = int(o.get("voteCount") or 0)
        k = side_of(o, contest)
        if k is None:
            bad += v
            continue
        seen[k] += 1
        out[k] += v
        out["total"] += v
    for k in SIDE_KEYS:
        if contest.get(k) and seen[k] != 1:
            raise SystemExit(f"Utah: {contest['id']}: the {k} nominee is not listed once in a row")
    return (out, bad) if invalid else out


def read_2024(cache, refresh, say):
    """{precincts: {(fips, name): {"votes": {cid: four}, "house": set, "senate": set}}, county_summary, state_rows, statewide}."""
    base = os.path.join(cache, "2024")
    state = get_json(f"{API}/elections/Utah/{ELECTION_2024}", os.path.join(base, "utah_election.json"), refresh)
    if not state.get("isOfficialResults") or state.get("electionDate") != "2024-11-05":
        raise SystemExit("Utah: the results system's 2024 general election is not marked official")
    items = get_json(f"{API}/elections/Utah/{ELECTION_2024}/ballot-items?limit=1000", os.path.join(base, "utah_items.json"), refresh)["data"]
    wanted = {}
    for c in CONTESTS:
        if c["year"] != 2024:
            continue
        hit = [x for x in items if re.fullmatch(c["api"], text(x["name"]))]
        if len(hit) != 1:
            raise SystemExit(f"Utah: the 2024 statewide contest {c['id']} is not listed once")
        wanted[hit[0]["id"]] = ("statewide", c)
    for x in items:
        m = re.fullmatch(r"(State House|State Senate|U\.S\. House|State School Board) (\d+)\s*(?:\((?:Multi-County|2 year term)\))?", text(x["name"]))
        if m:
            wanted[x["id"]] = ({"State House": "house", "State Senate": "senate", "U.S. House": "congress", "State School Board": "school"}[m.group(1)], int(m.group(2)))
    statewide, state_rows = {}, {}
    for pid, (what, c) in wanted.items():
        if what != "statewide":
            continue
        statewide[c["id"]] = four(next(x for x in items if x["id"] == pid)["summaryResults"]["ballotOptions"], c)
        det = get_json(f"{API}/elections/Utah/{ELECTION_2024}/ballot-items/{pid}", os.path.join(base, f"utah_{pid}.json"), refresh)
        for b in det["breakdownResults"]:
            name = text(b["locality"]["name"])
            fips = FIPS.get(re.sub(r" County$", "", name))
            if not fips or (fips, c["id"]) in state_rows:
                raise SystemExit(f"Utah: {c['id']}: the statewide contest's county row {name!r} is unknown or repeated")
            state_rows[(fips, c["id"])] = four(b["ballotOptions"], c)
    counties = get_json(f"{API}/jurisdictions/Utah", os.path.join(base, "utah_jurisdiction.json"), refresh)["childLocalities"]
    if len(counties) != 29:
        raise SystemExit("Utah: the results system does not list 29 counties")
    precincts = collections.defaultdict(lambda: {"votes": {}, "house": set(), "senate": set(), "congress": set(), "school": set()})
    unavailable = []
    county_summary, seen_items = {}, collections.Counter()
    for cty in counties:
        fips = FIPS[re.sub(r" County$", "", text(cty["name"]))]
        short = cty["shortName"]
        listing = get_json(f"{API}/elections/{short}/{ELECTION_2024}/ballot-items?limit=1000", os.path.join(base, f"{short}_items.json"), refresh)
        if listing.get("totalRecordCount") != len(listing["data"]):
            raise SystemExit(f"Utah: {short}: the contest list was not read whole")
        for x in listing["data"]:
            if x.get("parentId") not in wanted:
                continue
            what, c = wanted[x["parentId"]]
            seen_items[x["parentId"]] += 1
            url = f"{API}/elections/{short}/{ELECTION_2024}/ballot-items/{x['id']}"
            if what in ("congress", "school"):
                # used only to tell Senate districts apart; a contest the system will not give precinct by precinct is
                # used only where it is the county's one contest of its kind and covers every unit of the county
                try:
                    det = get_json(url, os.path.join(base, short, f"{x['id']}.json"), refresh, waits=(5,))
                except OSError:
                    unavailable.append((fips, what, c, int((x.get("reportingStatus") or {}).get("totalUnits") or 0), text(x["name"])))
                    continue
            else:
                det = get_json(url, os.path.join(base, short, f"{x['id']}.json"), refresh)
            rows = det.get("breakdownResults") or []
            if det.get("breakdownResultCount") not in (None, len(rows)):
                raise SystemExit(f"Utah: {short} {text(x['name'])}: not every precinct row came back")
            names = [text(b["precinct"]["name"]) for b in rows]
            if len(set(names)) != len(names):
                raise SystemExit(f"Utah: {short} {text(x['name'])}: a precinct is named twice")
            if what == "statewide":
                county_summary[(fips, c["id"])] = four(x["summaryResults"]["ballotOptions"], c)
                for b, name in zip(rows, names):
                    v, bad = four(b["ballotOptions"], c, invalid=True)
                    if v["total"] + bad != int(b.get("voteTotal") or 0):
                        raise SystemExit(f"Utah: {short} {name} {c['id']}: the options do not add up to the precinct's total")
                    if c["id"] in precincts[(fips, name)]["votes"]:
                        raise SystemExit(f"Utah: {short} {name} {c['id']}: counted twice")
                    precincts[(fips, name)]["votes"][c["id"]] = v
            else:
                for name in names:
                    precincts[(fips, name)][what].add(c)
        say(f"      {COUNTY_NAME[fips]}: {sum(1 for k in precincts if k[0] == fips)} precincts")
    whole = []
    for fips, what, c, units, name in unavailable:
        mine = [k for k in precincts if k[0] == fips and not FEDERAL_ONLY.match(k[1])]
        alone = sum(1 for f2, w2, *_ in unavailable if f2 == fips and w2 == what) == 1 and not any(precincts[k][what] for k in mine)
        # federal-only ballots carry the U.S. House contest too, so they are among that contest's units
        everyone = len(mine) + (sum(1 for k in precincts if k[0] == fips and FEDERAL_ONLY.match(k[1])) if what == "congress" else 0)
        if alone and units == everyone:
            for k in mine:
                precincts[k][what].add(c)
            whole.append({"county": COUNTY_NAME[fips], "contest": name, "units": units})
        else:
            whole.append({"county": COUNTY_NAME[fips], "contest": name, "units": units, "not_used": True})
    missing = [pid for pid, (what, _c) in wanted.items() if not seen_items[pid]]
    if missing:
        raise SystemExit(f"Utah: {len(missing)} contests of the statewide list were found in no county")
    return {"precincts": dict(precincts), "county_summary": county_summary, "state_rows": state_rows, "statewide": statewide,
            "as_of": str(state.get("lastUpdated") or "")[:10], "senates_on_ballot": sorted({c for w, c in wanted.values() if w == "senate"}),
            "schools_on_ballot": sorted({c for w, c in wanted.values() if w == "school"}),
            "congress_on_ballot": sorted({c for w, c in wanted.values() if w == "congress"}),
            "houses_on_ballot": sorted({c for w, c in wanted.values() if w == "house"}), "not_by_precinct": whole}


# ---------- 2024: the signed statewide canvass's text layer (a second control for President and Governor) ----------

def canvass_2024(path, contest, county_rows):
    """Compare each county's row of the canvass page headed contest['canvass_page'] with the results system's options in
    the same order. Returns {"compared", "equal", "unreadable": [counties whose printed line the text layer garbles]}."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == contest["canvass_page"]), None)
    if start is None:
        return None
    page = lines[start][0]
    out = {"compared": 0, "equal": 0, "unreadable": [], "page": page}
    for p, _y, t in lines[start:]:
        if p != page:
            break
        m = re.match(r"^([A-Za-z ]+?) Coun\S*\s+([\d, ]+)$", t.strip())
        if not m:
            continue
        name = m.group(1).strip()
        fips = FIPS.get(name)
        if not fips:
            continue
        printed = [int(x.replace(",", "")) for x in m.group(2).split()]
        mine = county_rows[fips]
        if len(printed) < len(mine) or any(not re.fullmatch(r"\d{1,3}(,\d{3})*", x) for x in m.group(2).split()):
            out["unreadable"].append(name)
            continue
        out["compared"] += 1
        # the printed candidates come first, in ballot order; the write-in columns after them differ between the two
        if printed[:len(mine)] == mine:
            out["equal"] += 1
        else:
            out.setdefault("differ", []).append(name)
    return out


# ---------- 2020 and 2022: the county canvass ----------

def read_2020(path, contest):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[contest["sheet"]].iter_rows(values_only=True))
    heads = [re.sub(r"\s+", " ", str(h or "")).strip() for h in rows[2]]
    first = rows[0]
    lo = 1
    if contest.get("block"):
        lo = next(i for i, h in enumerate(first) if str(h or "").strip() == contest["block"])
    hi = next((i for i in range(lo + 1, len(first)) if str(first[i] or "").strip()), len(first))
    cols = [i for i in range(lo, hi) if heads[i]]
    keys = {}
    for i in cols:
        keys[i] = "other"
        for k in SIDE_KEYS:
            if contest.get(k) and heads[i] == contest[k][2]:
                keys[i] = k
    for k in SIDE_KEYS:
        if contest.get(k) and list(keys.values()).count(k) != 1:
            raise SystemExit(f"Utah 2020: {contest['id']}: no single column headed {contest[k][2]!r}")
    out, total = {}, None
    for r in rows[3:]:
        label = str(r[0] or "").strip()
        if not label:
            continue
        v = {k: 0 for k in SIDE_KEYS if contest.get(k)}
        v.update(other=0, total=0)
        for i in cols:
            n = int(r[i] or 0)
            v[keys[i]] += n
            v["total"] += n
        if label == "TOTAL":
            total = v
            break
        if label not in FIPS:
            raise SystemExit(f"Utah 2020: {contest['id']}: a row is labelled {label!r}")
        out[FIPS[label]] = v
    if len(out) != 29 or total is None:
        raise SystemExit(f"Utah 2020: {contest['id']}: not 29 counties and a TOTAL row")
    return out, total, [heads[i] for i in cols if keys[i] == "other"]


def read_2022():
    out = {}
    for line in SENATE_2022.strip().splitlines():
        m = re.match(r"^([A-Za-z ]+?) ((?:\d+ ){6}\d+)$", line.strip())
        nums = [int(x) for x in m.group(2).split()]
        mc, hansen, lee, williams, *writes = nums
        out[FIPS[m.group(1)]] = {"una": mc, "rep": lee, "other": hansen + williams + sum(writes), "total": sum(nums), "_cols": nums}
    cols = [sum(v["_cols"][i] for v in out.values()) for i in range(7)]
    if tuple(cols) != SENATE_2022_PRINTED["columns"] or sum(cols) != SENATE_2022_PRINTED["contest"]:
        raise SystemExit("Utah 2022: the typed Senate table does not add up to the scan's printed totals")
    for v in out.values():
        del v["_cols"]
    return out


# ---------- the district plan (which Senate districts each House district reaches) ----------

def read_combos(cache, refresh):
    """Every piece of the 2022 plan (the lines of the 2024 election) as (U.S. House, Senate, House, State School Board)."""
    url = COMBOS["2022"]
    path = os.path.join(cache, "combos_2022.json")
    q = get_json(url + "?where=1%3D1&outFields=ComboID,Congress,Senate,House,School&returnGeometry=false&resultRecordCount=2000&f=json", path, refresh)
    if q.get("exceededTransferLimit") or not q.get("features"):
        raise SystemExit("Utah: the district combination areas were not read whole")
    rows = [f["attributes"] for f in q["features"]]
    pieces = {(int(r["Congress"]), int(r["Senate"]), int(r["House"]), int(r["School"])) for r in rows}
    if {p[2] for p in pieces} != set(range(1, 76)) or {p[1] for p in pieces} != set(range(1, 30)):
        raise SystemExit("Utah: the district combination areas do not hold 75 House and 29 Senate districts")
    return pieces, {"rows": len(rows), "file": path}


def possible_senates(p, pieces, on_ballot_school, school_known=True):
    """The Senate districts a precinct can lie in, by the plan: the pieces whose House district is one the precinct voted
    for, whose U.S. House district is one it voted for (when the results say), and whose State School Board district is
    the one it voted for, or (when it voted for none and every such contest of its county is known) one not on the ballot."""
    out = set()
    for cong, sen, house, school in pieces:
        if house not in p["house"]:
            continue
        if p["congress"] and cong not in p["congress"]:
            continue
        if p["school"]:
            if school not in p["school"]:
                continue
        elif school_known and school in on_ballot_school:
            continue
        out.add(sen)
    return out


def place_districts(precincts, pieces, senates_on_ballot, schools_on_ballot=(), school_unknown=()):
    """Each precinct's House and Senate district, or why not: returns (house_of, senate_of, notes). A precinct in two House
    contests has no House district. Its Senate district is the one whose contest it voted in (a precinct listed in two
    Senate contests has none); a precinct that voted in no Senate contest lies in none of the districts on the 2024
    ballot, and is placed when the plan leaves it only one other; else it is not placed."""
    house_of, senate_of, notes = {}, {}, collections.defaultdict(list)
    on_ballot, sch = set(senates_on_ballot), set(schools_on_ballot)
    for key, p in precincts.items():
        fips = key[0]
        hs = sorted(p["house"])
        if len(hs) == 1:
            house_of[key] = hs[0]
        elif len(hs) > 1:
            notes["house_split"].append({"county": COUNTY_NAME[fips], "precinct": key[1], "house_districts": hs})
        else:
            notes["no_house"].append({"county": COUNTY_NAME[fips], "precinct": key[1]})
        possible = possible_senates(p, pieces, sch, fips not in school_unknown)
        if not possible:
            # the results and the plan do not meet (a contest that does not list the precinct): fall back to the House district alone
            possible = possible_senates({"house": p["house"], "congress": set(), "school": set()}, pieces, sch, False)
            notes["plan_loose"].append({"county": COUNTY_NAME[fips], "precinct": key[1]})
        voted = sorted(p["senate"])
        if voted:
            if len(voted) > 1:
                notes["senate_split"].append({"county": COUNTY_NAME[fips], "precinct": key[1], "senate_districts": voted})
                senate_of[key] = None
                continue
            if voted[0] not in possible:
                notes["plan_disagrees"].append({"county": COUNTY_NAME[fips], "precinct": key[1], "voted_in": voted[0], "plan": sorted(possible)})
            senate_of[key] = voted[0]
        else:
            # it voted in no Senate contest, so no part of it lies in a district that was on the ballot
            off = possible - on_ballot
            if len(off) == 1:
                senate_of[key] = next(iter(off))
            else:
                senate_of[key] = None
                notes["senate_unplaced"].append({"county": COUNTY_NAME[fips], "precinct": key[1], "could_be": sorted(off)})
    return house_of, senate_of, notes


# ---------- adding up ----------

def add(into, v):
    for k, n in v.items():
        into[k] = into.get(k, 0) + n


def few(votes):
    out = []
    for cid, v in votes.items():
        parts = [n for k, n in v.items() if k != "total"]
        if v["total"] < FEW or (v["total"] and max(parts) == v["total"]):
            out.append(cid)
    return out


def selftest():
    p = {("49001", "A"): {"votes": {"c": {"dem": 5, "rep": 10, "other": 1, "total": 16}}, "house": {1}, "senate": set()},
         ("49001", "B"): {"votes": {"c": {"dem": 3, "rep": 2, "other": 0, "total": 5}}, "house": {1, 2}, "senate": {9}},
         ("49003", "C"): {"votes": {"c": {"dem": 1, "rep": 1, "other": 0, "total": 2}}, "house": {2}, "senate": {9}},
         ("49003", "D"): {"votes": {"c": {"dem": 1, "rep": 1, "other": 0, "total": 2}}, "house": {3}, "senate": set()},
         ("49003", "E"): {"votes": {"c": {"dem": 1, "rep": 1, "other": 0, "total": 2}}, "house": {3}, "senate": {9, 11}}}
    for v in p.values():
        v.setdefault("congress", set()); v.setdefault("school", set())
    pieces = {(1, 8, 1, 1), (1, 9, 2, 1), (1, 9, 3, 1), (1, 10, 3, 1), (1, 11, 3, 1), (1, 12, 3, 1)}
    h, s, notes = place_districts(p, pieces, [9, 11])
    assert h == {("49001", "A"): 1, ("49003", "C"): 2, ("49003", "D"): 3, ("49003", "E"): 3}, h
    assert s == {("49001", "A"): 8, ("49001", "B"): 9, ("49003", "C"): 9, ("49003", "D"): None, ("49003", "E"): None}, s
    assert notes["house_split"] and notes["senate_split"] and notes["senate_unplaced"][0]["could_be"] == [10, 12]
    assert not notes.get("plan_disagrees")
    assert few({"x": {"dem": 0, "rep": 19, "other": 0, "total": 19}, "y": {"dem": 1, "rep": 30, "other": 0, "total": 31}}) == ["x"]
    assert read_2022()[FIPS["Beaver"]] == {"una": 419, "rep": 1971, "other": 57, "total": 2447}
    print("selftest: ok")


# ---------- the run ----------

def statute(cache, refresh, say):
    from states import net
    path = os.path.join(cache, "ut_code_78a_1_102.html")
    if not fresh(path, refresh, 30):
        page = net.get(STATUTE["url"]).decode("utf-8", "replace")
        ver = re.search(r'versionDefault="([^"]+)"', page)
        if not ver:
            raise SystemExit("Utah: the Legislature's page for 78A-1-102 no longer names its current version")
        body = net.get(STATUTE["url"].rsplit("/", 1)[0] + "/" + ver.group(1) + ".html")
        with open(path + ".part", "wb") as fh:
            fh.write(body)
        os.replace(path + ".part", path)
    t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", open(path, encoding="utf-8", errors="replace").read())))
    read = {}
    for word, names in re.findall(r"\(\w\) (\w+) Judicial District, which includes ([A-Za-z ,]+?) Counties", t):
        read[ORDINAL[word]] = sorted(n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", names) if n.strip())
    if read != {k: sorted(v) for k, v in JUDICIAL.items()}:
        raise SystemExit(f"Utah: section 78A-1-102 as published does not list the counties typed here: {read}")
    return {"id": STATUTE["id"], "kind": "statute, as the Legislature publishes it", "agency": "Utah State Legislature, Utah Code",
            "title": STATUTE["title"], "url": STATUTE["url"], "fetched": _day(path), "sha256": _sha_file(path)}


def our_places(db):
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'ut-%'"):
            out[kind].add(pid)
        for office, level, jid, district in con.execute("SELECT office_kind, level, jurisdiction_id, district FROM sl_races WHERE state = 'UT'"):
            if office == "state_senate":
                out["senate"].add(str(district))
            elif office == "state_house":
                out["house"].add(str(district))
            elif level == "court" and re.fullmatch(r"JD\d+", str(jid or "")):
                out["judicial"].add(str(jid))
            elif level == "county":
                out["county"].add(str(jid))
        return dict(out)
    finally:
        con.close()


def run(out_path, cache, refresh, say=say_default):
    from ballot.wy_place_votes import read_clerk, clerk_figures
    os.makedirs(cache, exist_ok=True)
    say("Utah: past votes by place")
    sources, notes = [], []
    contests = {c["id"]: c for c in CONTESTS}

    # 2024
    say("   2024: the official results system, precinct by precinct")
    r24 = read_2024(cache, refresh, say)
    P = r24["precincts"]
    ids24 = [c["id"] for c in CONTESTS if c["year"] == 2024]
    federal = {}      # the federal-only ballots each county reports as a unit of its own (voters entitled to the federal contests alone)
    for key, p in P.items():
        if FEDERAL_ONLY.match(key[1]) and not p["house"] and not p["senate"] and sorted(p["votes"]) == ["2024-president", "2024-us-senate"]:
            federal[key] = p
        elif sorted(p["votes"]) != sorted(ids24):
            raise SystemExit(f"Utah 2024: precinct {key} does not vote in all three statewide contests")
    for key in federal:
        del P[key]
    # a county's figures are its own summary of the contest, which must equal the state's row for the county; its precinct
    # rows (and federal-only units) add up to no more than that, option by option: the rest is in no precinct's row
    county = {fips: {cid: r24["county_summary"][(fips, cid)] for cid in ids24} for fips in FIPS.values()}
    in_rows = collections.defaultdict(dict)
    for (fips, _n), p in list(P.items()) + list(federal.items()):
        for cid, v in p["votes"].items():
            in_rows[fips].setdefault(cid, {})
            add(in_rows[fips][cid], v)
    unassigned = {}
    control = {"result": "equal", "contests": {}, "precincts": {"2024": len(P)},
               "federal_only": {"units": len(federal), "counties": len({k[0] for k in federal}),
                                "votes": {cid: sum(p["votes"][cid]["total"] for p in federal.values()) for cid in ("2024-president", "2024-us-senate")},
                                "what": ("Each county reports the ballots of voters entitled to the federal contests alone (President, Senator and "
                                         "Representative in Congress) as a unit of its own, named Federal or FED. They are counted in the county, the "
                                         "judicial district and the state, and in no House or Senate district.")}}
    for cid in ids24:
        state_sum, gap_sum, gap_counties = {}, {}, {}
        for fips in FIPS.values():
            mine = county[fips][cid]
            if mine != r24["state_rows"][(fips, cid)]:
                raise SystemExit(f"Utah 2024: {cid} {COUNTY_NAME[fips]}: the county's summary differs from the state's row for the county")
            rows = in_rows[fips].get(cid, {})
            gap = {k: mine[k] - rows.get(k, 0) for k in mine}
            if any(n < 0 for n in gap.values()):
                raise SystemExit(f"Utah 2024: {cid} {COUNTY_NAME[fips]}: the precinct rows hold more votes than the county's summary")
            if gap["total"]:
                gap_counties[fips] = gap
            add(gap_sum, gap)
            add(state_sum, mine)
        if state_sum != r24["statewide"][cid]:
            raise SystemExit(f"Utah 2024: {cid}: the counties do not add up to the statewide summary")
        unassigned[cid] = gap_counties
        control["contests"][cid] = {"sum_of_counties": state_sum, "official": r24["statewide"][cid],
                                    "counties": {"compared": 29, "equal": 29}, "equal": True, "source": "ut-results-2024",
                                    "where": "the results system's statewide contest, its row for each county, and each county's own summary of the contest",
                                    "precinct_rows": {"precincts": len(P), "sum": {k: state_sum[k] - gap_sum[k] for k in state_sum},
                                                      "in_no_precinct_row": gap_sum, "counties_with_votes_in_no_precinct_row": len(gap_counties),
                                                      "by_county": {COUNTY_NAME[f]: g["total"] for f, g in gap_counties.items()}}}
    # the signed canvass, where its text layer can be read
    cpath = get_file(CANVASS[2024]["url"], os.path.join(cache, CANVASS[2024]["file"]), refresh, say)
    for cid in ids24:
        c = contests[cid]
        if not c.get("canvass_page"):
            control["contests"][cid]["canvass"] = "its pages for this contest are pictures with no text layer, so they are not compared by script"
            continue
        # each county's options in the results system's own order
        order = {}
        for fips in FIPS.values():
            short = COUNTY_NAME[fips].lower().replace(" ", "-") + "-ut"
            listing = json.load(open(os.path.join(cache, "2024", f"{short}_items.json"), encoding="utf-8"))["data"]
            item = next(x for x in listing if re.fullmatch(c["api"], text(x["name"])))
            opts = item["summaryResults"]["ballotOptions"]
            k = sum(1 for o in opts if not o.get("isWriteIn"))
            if any(o.get("isWriteIn") for o in opts[:k]):
                raise SystemExit(f"Utah 2024: {cid}: the write-in options are not listed after the printed candidates")
            order[fips] = [int(o.get("voteCount") or 0) for o in opts[:k]]      # the candidates printed on the ballot, in ballot order
        cmp = canvass_2024(cpath, c, order)
        if cmp is None or cmp.get("differ"):
            raise SystemExit(f"Utah 2024: {cid}: the signed canvass's county rows differ from the results system: {cmp}")
        control["contests"][cid]["canvass"] = {"compared": cmp["compared"], "equal": cmp["equal"], "page_of_pdf": cmp["page"],
                                               "not_read": cmp["unreadable"], "why_not_read": "the text layer of the scan garbles these lines" if cmp["unreadable"] else None}
        if cmp["compared"] < 20:
            raise SystemExit(f"Utah 2024: {cid}: fewer than 20 county rows of the canvass could be read")
    sources.append({"id": "ut-results-2024", "kind": "official results by precinct, with the county and statewide summaries", "agency": AGENCY,
                    "title": "2024 General Election, official results (electionresults.utah.gov), each county's contests precinct by precinct",
                    "url": RESULTS_PAGE, "fetched": _day(os.path.join(cache, "2024", "utah_items.json")), "results_last_updated": r24["as_of"],
                    "precincts": len(P),
                    "read": "Of each precinct row: the precinct's name and each option's name, party abbreviation, write-in mark and count, for "
                            "President, U.S. Senator, Governor and every state House and Senate contest; nothing else."})
    sources.append({"id": "ut-canvass-2024", "kind": "official canvass, county by county (a control)", "agency": "Utah State Board of Canvassers",
                    "title": "2024 General Election Statewide Canvass (signed)", "url": CANVASS[2024]["url"], "listed_on": HISTORICAL,
                    "fetched": _day(cpath), "sha256": _sha_file(cpath)})

    # districts, 2024
    pieces, crec = read_combos(cache, refresh)
    school_unknown = {FIPS[re.sub(r" County$", "", x["county"])] for x in r24["not_by_precinct"] if x.get("not_used") and x["contest"].startswith("State School Board")}
    house_of, senate_of, dnotes = place_districts(P, pieces, r24["senates_on_ballot"], r24["schools_on_ballot"], school_unknown)
    if dnotes.get("no_house"):
        raise SystemExit(f"Utah 2024: {len(dnotes['no_house'])} precincts voted in no House contest")
    if dnotes.get("plan_disagrees"):
        raise SystemExit(f"Utah 2024: the district plan places precincts in another Senate district than their contest: {dnotes['plan_disagrees'][:5]}")
    split_h = collections.defaultdict(list)
    for x in dnotes.get("house_split", []):
        for h in x["house_districts"]:
            split_h[h].append(x)
    house = {}
    for key, h in house_of.items():
        if h in split_h:
            continue
        for cid in ids24:
            house.setdefault(h, {}).setdefault(cid, {})
            add(house[h][cid], P[key]["votes"][cid])
    house_left = sorted(set(r24["houses_on_ballot"]) - set(house))
    # a Senate district is left out when any precinct that may lie in it is not placed
    senate_bad = set()
    for x in dnotes.get("senate_split", []):
        senate_bad |= set(x["senate_districts"])
    for x in dnotes.get("senate_unplaced", []):
        senate_bad |= set(x["could_be"])
    senate = {}
    for key, s in senate_of.items():
        if s is None or s in senate_bad:
            continue
        for cid in ids24:
            senate.setdefault(s, {}).setdefault(cid, {})
            add(senate[s][cid], P[key]["votes"][cid])
    all_senates = list(range(1, 30))
    senate_left = sorted(set(all_senates) - set(senate))
    # the districts given and the precincts of those left out add up to the statewide sum
    for kind, sums, assign, bad in (("house", house, house_of, set(split_h)), ("senate", senate, senate_of, senate_bad)):
        tot = {cid: {} for cid in ids24}
        for d, vv in sums.items():
            for cid, v in vv.items():
                add(tot[cid], v)
        for key, p in P.items():
            d = assign.get(key)
            if d is None or d in bad:
                for cid in ids24:
                    add(tot[cid], p["votes"][cid])
        for p in federal.values():
            for cid, v in p["votes"].items():
                add(tot[cid], v)
        for cid, gaps in unassigned.items():
            for g in gaps.values():
                add(tot[cid], g)
        if any(tot[cid] != r24["statewide"][cid] for cid in ids24):
            raise SystemExit(f"Utah 2024: the {kind} districts given and the precincts left out do not add up to the statewide figures")
    sources.append({"id": "ugrc-district-combination-areas", "kind": "the Legislature's district plan as the state's GIS office publishes it (used to place a precinct in a Senate district not on the 2024 ballot)",
                    "agency": "Utah Geospatial Resource Center", "title": "Political District Combination Areas, 2022 (the plan the 2024 election was held on; every piece read, no shapes)",
                    "url": COMBOS_PAGE, "fetched": _day(crec["file"]), "pieces": crec["rows"],
                    "read": "Of each piece: its U.S. House, state Senate, state House and State School Board district; nothing else. Its county column names one county for pieces reaching into several, so it is not used."})

    # 2020
    say("   2020: the statewide canvass workbook")
    p20 = get_file(CANVASS[2020]["url"], os.path.join(cache, CANVASS[2020]["file"]), refresh, say)
    y20 = {}
    for c in CONTESTS:
        if c["year"] != 2020:
            continue
        rows, total, others = read_2020(p20, c)
        s = {}
        for v in rows.values():
            add(s, v)
        if s != total:
            raise SystemExit(f"Utah 2020: {c['id']}: the county rows do not add up to the TOTAL row")
        y20[c["id"]] = rows
        c["_other_columns"] = others
        control["contests"][c["id"]] = {"sum_of_counties": s, "official": total, "counties": {"compared": 29, "equal": 29}, "equal": True,
                                        "source": "ut-canvass-2020", "where": f"the {c['sheet']} sheet of the workbook, its TOTAL row"}
    sources.append({"id": "ut-canvass-2020", "kind": "official canvass, county by county", "agency": "Utah State Board of Canvassers",
                    "title": "2020 General Election Statewide Canvass (workbook)", "url": CANVASS[2020]["url"], "listed_on": HISTORICAL,
                    "fetched": _day(p20), "sha256": _sha_file(p20),
                    "read": "The county rows and the TOTAL row of the President sheet, and of the Governor columns of the State Offices sheet."})

    # 2022
    say("   2022: the signed canvass (typed from the scan)")
    p22 = get_file(CANVASS[2022]["url"], os.path.join(cache, CANVASS[2022]["file"]), refresh, say)
    if _sha_file(p22) != SCAN_2022_SHA:
        raise SystemExit("Utah 2022: the signed canvass is not the scan the Senate table was typed from")
    y22 = {"2022-us-senate": read_2022()}
    s = {}
    for v in y22["2022-us-senate"].values():
        add(s, v)
    control["contests"]["2022-us-senate"] = {"sum_of_counties": s, "official": {"una": SENATE_2022_PRINTED["columns"][0], "rep": SENATE_2022_PRINTED["columns"][2],
                                             "other": SENATE_2022_PRINTED["contest"] - SENATE_2022_PRINTED["columns"][0] - SENATE_2022_PRINTED["columns"][2],
                                             "total": SENATE_2022_PRINTED["contest"]},
                                             "counties": {"compared": 29, "equal": 29}, "equal": s["total"] == SENATE_2022_PRINTED["contest"], "source": "ut-canvass-2022",
                                             "where": "pages 3 and 4 of the signed scan, typed county by county; each column adds up to the scan's printed Total Votes Cast Per Candidate, and they to its Total Votes Cast in Contest"}
    sources.append({"id": "ut-canvass-2022", "kind": "official canvass, county by county (a signed scan without text; its U.S. Senate table typed here)",
                    "agency": "Utah State Board of Canvassers", "title": "2022 General Election State Canvass Certification (signed)",
                    "url": CANVASS[2022]["url"], "listed_on": HISTORICAL, "fetched": _day(p22), "sha256": _sha_file(p22),
                    "read": "The U.S. Senate table on pages 3 and 4, county by county, typed from the scan."})

    # the Clerk of the House, a second statewide control
    for year, (day, kind) in CLERK.items():
        path = os.path.join(cache, f"clerk_statistics{year}.pdf")
        url = f"https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf"
        get_file(url, path, refresh, say)
        doc = read_clerk(path, "UTAH")
        top = re.search(r"page (\d+)", doc["where"])
        where = f"Utah, page {top.group(1)}" if top else "the Utah page"
        for c in CONTESTS:
            if c["year"] != year or not c.get("clerk"):
                continue
            lines = [(lab, v) for lab, v in doc["sections"].get(c["clerk"]) or [] if lab not in ("Under Votes", "Over Votes")]
            total = sum(v for _l, v in lines)
            mine = control["contests"][c["id"]]["sum_of_counties"]
            if c.get("dem"):
                figs = clerk_figures(doc, c["clerk"])
            else:
                rep = [v for lab, v in lines if lab.rsplit(",", 1)[-1].strip() == "Republican"]
                una = [v for lab, v in lines if lab.startswith("Evan McMullin")]
                figs = {"una": una[0], "rep": rep[0], "other": total - una[0] - rep[0], "total": total}
            if figs != mine:
                raise SystemExit(f"Utah {year}: {c['id']}: the Clerk of the House's statistics {figs} differ from {mine}")
            control["contests"][c["id"]]["clerk"] = {"official": figs, "equal": True, "where": where}
        sources.append({"id": f"clerk-statistics-{year}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                        "title": f"Statistics of the {kind} Election from Official Sources for the Election of {day}", "url": url,
                        "fetched": _day(path), "sha256": _sha_file(path), "where": where,
                        "read": "The Utah lines for presidential electors and United States Senator; its under and over votes are left out."})

    sources.append(statute(cache, refresh, say))

    # places
    places = {"county": {}, "judicial": {}, "house": {}, "senate": {}}
    for fips in FIPS.values():
        votes = {cid: county[fips][cid] for cid in ids24}
        votes["2022-us-senate"] = y22["2022-us-senate"][fips]
        for cid, rows in y20.items():
            votes[cid] = rows[fips]
        votes = {c["id"]: votes[c["id"]] for c in CONTESTS}
        places["county"][fips] = {"name": COUNTY_NAME[fips], "votes": votes}
    for n, names in JUDICIAL.items():
        votes = {}
        for name in names:
            for cid, v in places["county"][FIPS[name]]["votes"].items():
                votes.setdefault(cid, {})
                add(votes[cid], v)
        word = next(w for w, k in ORDINAL.items() if k == n)
        places["judicial"][f"JD{n}"] = {"name": f"{word} Judicial District", "counties": [FIPS[x] for x in names], "votes": votes}
    for h in sorted(house):
        places["house"][str(h)] = {"name": f"House District {h}", "votes": {cid: house[h][cid] for cid in ids24}}
    for s2 in sorted(senate):
        places["senate"][str(s2)] = {"name": f"Senate District {s2}", "votes": {cid: senate[s2][cid] for cid in ids24}}
    for kind in places:
        for pl in places[kind].values():
            f = few(pl["votes"])
            if f:
                pl["too_few"] = [c["id"] for c in CONTESTS if c["id"] in f]

    contest_out = []
    for c in CONTESTS:
        rec = {"id": c["id"], "date": c["date"], "office": c["office"],
               "table": {2024: "ut-results-2024", 2022: "ut-canvass-2022", 2020: "ut-canvass-2020"}[c["year"]],
               "kinds": ["county", "judicial", "house", "senate"] if c["year"] == 2024 else ["county", "judicial"]}
        for k in SIDE_KEYS:
            if c.get(k):
                rec[k] = {"party": c[k][0], "ticket": c[k][1], "column": f"the option {c[k][2]}" if c["year"] == 2024 else f"the column headed {c[k][2]}"}
        rec["other"] = {"what": "every other candidate and all write-ins, together"}
        rec["total"] = {"what": "the votes cast for candidates and counted write-ins" + ("; the signed canvass's column of invalid write-ins is left out" if c["id"] == "2024-governor" else "")}
        rec["statewide"] = control["contests"][c["id"]]["sum_of_counties"]
        rec["official_source"] = rec["table"]
        contest_out.append(rec)

    ours = our_places(DB)
    kinds = {}
    for kind, what, key in KINDS:
        k = {"what": what, "key": key, "places": len(places[kind]),
             "contests": [c["id"] for c in CONTESTS if kind in ("county", "judicial") or c["year"] == 2024],
             "covers_the_state": kind in ("county", "judicial") or (kind == "house" and not house_left) or (kind == "senate" and not senate_left),
             "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if kind in ("house", "senate"):
            left = house_left if kind == "house" else senate_left
            k["why_not_2020"] = WHY_NOT
            if left:
                k["note"] = (f"A {'House' if kind == 'house' else 'Senate'} district is given only where every precinct of it voted in that district "
                             f"alone. Left out (2024: {len(left)}): districts {', '.join(map(str, left))}, because a precinct of each lies in it "
                             f"and in another district too" + ("" if kind == "house" else ", or has a precinct that neither the 2024 ballot nor the district plan places in one Senate district") + ".")
                k["left_out"] = {"2024": left}
            k["rows"] = ("A district's figures are its precincts' rows added up; the few ballots a county put in no precinct's row, and its "
                         "federal-only ballots, are in no district's figures.")
            if kind == "senate":
                k["how"] = ("A Senate district on the 2024 ballot is the precincts that voted in its contest; one not on that ballot is the precincts "
                            "the Legislature's 2022 plan places in it: a precinct whose House, U.S. House and State School Board districts (as it "
                            "voted) are found together in pieces of only one Senate district that was not on that ballot.")
        kinds[kind] = k
    coverage = {"not_given": NOT_GIVEN, "no_2022_governor": "Utah elected its Governor in 2020 and 2024, not in 2022.",
                "no_2020_senate": "Utah elected no United States senator in 2020.",
                "no_democrat_2022_senate": "No Democrat was on Utah's 2022 ballot for U.S. Senator; Evan McMullin was printed as unaffiliated."}
    if ours is not None:
        cov = {}
        for kind in ("county", "judicial", "house", "senate"):
            want = sorted(ours.get(kind, set()), key=lambda x: (len(x), x))
            have = set(places[kind])
            cov[kind] = {"places": len(want), "with_votes": sum(1 for x in want if x in have), "without": [x for x in want if x not in have]}
        cov["not_given_kinds"] = {k: len(v) for k, v in ours.items() if k not in ("county", "judicial", "house", "senate")}
        cov["read"] = f"sl_places and sl_races in ballot_local_2026.sqlite, opened read-only on {_now()}"
        coverage["our_places"] = cov

    control["kinds"] = {"county": "equal", "judicial": "equal",
                        "house": "the House districts given, the precincts of those left out, the federal-only units and the votes in no precinct's row add up to the statewide sum",
                        "senate": "the Senate districts given, the precincts of those left out, the federal-only units and the votes in no precinct's row add up to the statewide sum; the plan agrees with every precinct of a 2024 Senate contest"}
    control["districts"] = {"2024": {
        "house_contests": len(r24["houses_on_ballot"]), "senate_contests": len(r24["senates_on_ballot"]),
        "senate_districts_on_the_ballot": r24["senates_on_ballot"],
        "house_districts_given": len(house), "house_districts_left_out": house_left,
        "senate_districts_given": len(senate), "senate_districts_left_out": senate_left,
        "precincts_in_more_than_one_house_district": dnotes.get("house_split", []),
        "precincts_in_more_than_one_senate_district": dnotes.get("senate_split", []),
        "precincts_not_placed_in_a_senate_district": dnotes.get("senate_unplaced", []),
        "precincts_placed_by_house_district_alone": dnotes.get("plan_loose", []),
        "contests_not_given_by_precinct": r24["not_by_precinct"],
        "plan_disagreements": dnotes.get("plan_disagrees", [])}}
    control["notes"] = [
        "The 2024 Governor's contest counts the write-in candidates the results system lists (Phil Lyman among them) with every other candidate.",
        "The signed 2024 canvass's text layer is the scanner's reading of the page; a county line it garbles is named under not_read and checked by the results system's own county rows instead.",
        "The 2022 U.S. Senate table was typed from the signed scan; its columns add up to the scan's printed totals and equal the Clerk of the House's statistics.",
    ]
    out = {"what": WHAT, "note": NOTE, "state": "UT", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": ["dem", "rep", "una", "other", "total"], "too_few": {"fewer_than": FEW, "why": TOO_FEW},
           "contests": contest_out, "kinds": kinds, "control": control, "coverage": coverage, "sources": sources,
           "places": places}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(out_path + ".part", out_path)
    say(f"   wrote {out_path}: {len(places['county'])} counties, {len(places['judicial'])} judicial districts, "
        f"{len(house)} of 75 House and {len(senate)} of 29 Senate districts; control equal")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    run(a.out, a.cache, a.refresh)


if __name__ == "__main__":
    main()
