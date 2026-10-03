"""
ballot/co_place_votes.py - how each Colorado place voted in past partisan general elections, so a page can show the
record of a county or a district without anyone labelling a candidate. The Colorado twin of ballot/mn_place_votes.py;
the output has the same shape (the Democratic count is "dem" here, as in the Dakotas', Montana's and Wyoming's files,
where Minnesota's is "dfl").

    python ballot/co_place_votes.py               reads (or downloads) the files, writes ballot/lean/co_place_votes.json
    python ballot/co_place_votes.py --refresh     asks for everything again even when the cached copies are there
    python ballot/co_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/co_place_votes.py --selftest    the arithmetic and the readers on made-up tables; downloads nothing

What it is, and is not
----------------------
For President in 2024 and 2020, United States Senator in 2022 and 2020, and Governor in 2022 (Colorado elected no
senator in 2024 and its Governor only in 2022): the votes for the Democratic ticket, the Republican ticket, every other
candidate together (certified write-in candidates included) and the total, for every one of the 64 counties and the 23
judicial districts, and for 2022 and 2024 for every congressional district, state Senate district and state House
district. It is how the people of a place voted then, on the lines in force at that election. It is not a prediction,
it says nothing about any candidate on a later ballot or about any voter, and it turns no nonpartisan office into a
partisan one. No database is opened for writing; ballot_local_2026.sqlite is opened read-only at the end, only to count
how many of our places are covered.

Where the numbers come from
---------------------------
  - The Colorado Secretary of State's Historical Elections Database (historicalelectiondata.coloradosos.gov, "State of
    Colorado Elections Database"), whose robots.txt disallows nothing. Each contest has a results download that the
    database serves from its own file host, co.elstats2.civera.com (the address the database itself gives for its
    files): one CSV for each contest, a column for each candidate as "name, line break, party" and a "Total Votes Cast"
    column, then a Totals row, each county's row followed by that county's precinct rows ("Precinct 4215601243"), and
    the Totals row again. THE PLACE FIGURES ARE THE PRECINCT ROWS ADDED UP. The contests are found on the database's
    own search pages (office and year, general election only), whose rows give the contest number, the date, the office
    and the district; the loader stops unless each statewide contest is found once and every district once.
  - The district a precinct lies in. A Colorado precinct votes in exactly one congressional, state Senate and state
    House district, and its ten-digit number says which: the first digit is the congressional district, the next two
    the Senate district, the next two the House district, then two for the county and three for the precinct (the
    layout as Jefferson County's own precinct archive describes it, gisportal.jeffco.us). This loader takes a
    precinct's districts from the contests it voted in and uses the number as a check: every precinct that cast votes
    must vote in the congressional and House contests, and the Senate contest where its seat was up, of the districts
    its number gives, or the loader stops. Three cases are taken from the number and listed in the file: a precinct
    that cast no votes at all, which a contest's file may leave out; and, since half the Senate is elected each time
    (17 or 18 seats of 35), a precinct whose Senate seat was not on the ballot that year, given the Senate district its
    number names once the number has named the district of every precinct whose seat was up, in both years. A precinct
    counted in two contests of a kind (in 2022 a Jefferson County precinct of House district 28 had three votes in
    House district 38's contest) is named, and both districts are left out for that year: the precinct's other votes
    cannot be divided between them without an estimate.
  - A judicial district is whole counties: sections 13-5-102 to 13-5-123.1, C.R.S., in the Office of Legislative Legal
    Services' own file of Title 13, as ballot/state_local_co.py read and kept them (23 districts; the 23rd, Douglas,
    Elbert and Lincoln, was taken out of the 18th in January 2025, so every year's figures are today's districts'
    counties added up).

The control
-----------
Nothing is written unless all of this holds: in each contest's file every row's candidates add up to its Total Votes
Cast, each county's precincts add up to that county's row, the counties to the Totals row, and every precinct is named
once; each statewide contest of a year has the same precincts; for every statewide contest the counties equal the
Secretary of State's Abstract of Votes Cast county by county (the Democratic ticket, the Republican ticket and the
total), read from coloradosos.gov (the 2020 and 2022 abstracts as web pages, the 2023-2024 biennial abstract as a PDF);
for President and U.S. Senator the Democratic and Republican figures equal the Clerk of the U.S. House of
Representatives' "Statistics of the ... Election" (clerk.house.gov; the Clerk leaves out some write-in candidates, so
its total is not compared); the districts behave as described above; and every kind of place adds up to the statewide
sum. The statewide figures this loader was checked against on 2026-10-02 are typed below (CHECKED); the loader says so
if the database reads differently later.

Not given: cities and towns (a Colorado precinct's number names no city or town, and the results do not say which one
it lies in); county commissioner districts, the Regional Transportation District's director districts, school,
special and other districts (the results do not say which of them a precinct lies in, and a precinct can lie partly
inside one; RTD's director contests are counted only from the voters inside it); 2020 by district (the 2020 election
was held on the lines of 2011; today's eight congressional, 35 Senate and 65 House districts were first used in 2022).
"""

import argparse
import collections
import csv
import html as H
import io
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

from states import net  # noqa: E402
from ballot import mn_place_votes as M  # noqa: E402  the shared small things: fingerprints, days, the file writer

Stop = M.Stop
METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "co_local")
OUT = os.path.join(HERE, "ballot", "lean", "co_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
JUDICIAL_KEPT = os.path.join(HERE, "ballot_cache", "co", "local", "co_crs_2026_judicial_districts.json")   # kept by state_local_co.py
STATE_FIPS = "08"
FEW = 20
SIDES = ("dem", "rep", "other", "total")
KEEP_DAYS = 3650               # certified results of past elections do not change; --refresh asks again
PAUSE = 1.0                    # seconds between requests that are not already on disk
CD, SENATE, HOUSE = 8, 35, 65
DISTRICT_YEARS = (2022, 2024)  # the elections held on today's districts

AGENCY = "Colorado Secretary of State, Elections Division"
DATABASE = "https://historicalelectiondata.coloradosos.gov"
FILES = "https://co.elstats2.civera.com/eng"                 # the database's own file host, as its file links give it
ABSTRACT = "https://www.coloradosos.gov/pubs/elections/Results"
NUMBER_LAYOUT = {"id": "jeffco-precinct-number-layout", "kind": "official description (a county's own GIS archive), used as a check only",
                 "agency": "Jefferson County, Colorado, GIS",
                 "title": "County Precinct Archive: the ten-digit precinct code (congressional district, Senate district, House district, county, precinct)",
                 "url": "https://gisportal.jeffco.us/server/rest/services/County_Precinct_Archive_2010/FeatureServer"}

OFFICES = {"president": 102, "us_senate": 9, "governor": 4, "congress": 10, "state_senate": 5, "state_house": 13}
OFFICE_WORDS = {"president": "President", "us_senate": "United States Senator", "governor": "Governor",
                "congress": "United States Congressperson", "state_senate": "State Senate", "state_house": "State Representative"}
ELECTIONS = {
    2024: {"date": "2024-11-05", "event": 159, "abstract": {"kind": "pdf", "file": "co_2024_biennial_abstract.pdf",
                                                            "url": f"{ABSTRACT}/2024/2024BiennialAbstract.pdf",
                                                            "title": "2023 - 2024 Biennial Abstract of Votes Cast"}},
    2022: {"date": "2022-11-08", "event": 154, "abstract": {"kind": "html", "base": f"{ABSTRACT}/Abstract/2022/general/",
                                                            "title": "2022 General Election Results (the Abstract of Votes Cast)"}},
    2020: {"date": "2020-11-03", "event": 11, "abstract": {"kind": "html", "base": f"{ABSTRACT}/Abstract/2020/general/",
                                                           "title": "2020 General Election Results (the Abstract of Votes Cast)"}},
}

# The contests. "dem" and "rep" are the tickets: the first person's family name must be in the one column of that party
# in the database's file, in the abstract's and (for President and Senator) in the Clerk's, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States", "key": "president",
     "dem": "Harris and Walz", "rep": "Trump and Vance", "abstract": "Presidential Electors", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2022-us-senate", "year": 2022, "office": "United States Senator", "key": "us_senate",
     "dem": "Michael Bennet", "rep": "Joe O'Dea", "abstract": "usSenator.html", "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "office": "Governor and Lieutenant Governor", "key": "governor",
     "dem": "Polis and Primavera", "rep": "Ganahl and Moore", "abstract": "governor.html", "clerk": None},
    {"id": "2020-president", "year": 2020, "office": "President and Vice President of the United States", "key": "president",
     "dem": "Biden and Harris", "rep": "Trump and Pence", "abstract": "president.html", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-us-senate", "year": 2020, "office": "United States Senator", "key": "us_senate",
     "dem": "John W. Hickenlooper", "rep": "Cory Gardner", "abstract": "usSenator.html", "clerk": "FOR UNITED STATES SENATOR"},
]

# The statewide totals this loader was checked against on 2026-10-02 (the precincts added up, the database's Totals
# rows and the Secretary's abstracts all read these).
CHECKED = {
    "2024-president": {"dem": 1728159, "rep": 1377441, "other": 87145, "total": 3192745},
    "2022-us-senate": {"dem": 1397170, "rep": 1031693, "other": 71338, "total": 2500201},
    "2022-governor": {"dem": 1468481, "rep": 983040, "other": 57309, "total": 2508830},
    "2020-president": {"dem": 1804352, "rep": 1364607, "other": 88021, "total": 3256980},
    "2020-us-senate": {"dem": 1731114, "rep": 1429492, "other": 75184, "total": 3235790},
}
CLERK = {year: {"id": f"clerk-statistics-{year}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                "title": f"Statistics of the {'Presidential and ' if year != 2022 else ''}Congressional Election from Official Sources for the Election of {day}",
                "url": f"https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf", "file": f"clerk_statistics{year}.pdf"}
         for year, day in ((2024, "November 5, 2024"), (2022, "November 8, 2022"), (2020, "November 3, 2020"))}

# The 64 counties in the order of their FIPS codes; Broomfield (08014) was made a county in 2001 and fits between.
COUNTIES = [("001", "Adams"), ("003", "Alamosa"), ("005", "Arapahoe"), ("007", "Archuleta"), ("009", "Baca"), ("011", "Bent"),
            ("013", "Boulder"), ("014", "Broomfield"), ("015", "Chaffee"), ("017", "Cheyenne"), ("019", "Clear Creek"), ("021", "Conejos"),
            ("023", "Costilla"), ("025", "Crowley"), ("027", "Custer"), ("029", "Delta"), ("031", "Denver"), ("033", "Dolores"),
            ("035", "Douglas"), ("037", "Eagle"), ("039", "Elbert"), ("041", "El Paso"), ("043", "Fremont"), ("045", "Garfield"),
            ("047", "Gilpin"), ("049", "Grand"), ("051", "Gunnison"), ("053", "Hinsdale"), ("055", "Huerfano"), ("057", "Jackson"),
            ("059", "Jefferson"), ("061", "Kiowa"), ("063", "Kit Carson"), ("065", "Lake"), ("067", "La Plata"), ("069", "Larimer"),
            ("071", "Las Animas"), ("073", "Lincoln"), ("075", "Logan"), ("077", "Mesa"), ("079", "Mineral"), ("081", "Moffat"),
            ("083", "Montezuma"), ("085", "Montrose"), ("087", "Morgan"), ("089", "Otero"), ("091", "Ouray"), ("093", "Park"),
            ("095", "Phillips"), ("097", "Pitkin"), ("099", "Prowers"), ("101", "Pueblo"), ("103", "Rio Blanco"), ("105", "Rio Grande"),
            ("107", "Routt"), ("109", "Saguache"), ("111", "San Juan"), ("113", "San Miguel"), ("115", "Sedgwick"), ("117", "Summit"),
            ("119", "Teller"), ("121", "Washington"), ("123", "Weld"), ("125", "Yuma")]


def bare(name):
    """A county's name for comparing only: capitals, letters alone ('El Paso', 'EL PASO COUNTY')."""
    return re.sub(r"COUNTY$", "", re.sub(r"[^A-Z]", "", H.unescape(name or "").upper()))


FIPS = {bare(name): STATE_FIPS + code for code, name in COUNTIES}
COUNTY_NAME = {STATE_FIPS + code: f"{name} County" for code, name in COUNTIES}
COUNTY_NAME["08031"] = "City and County of Denver"
COUNTY_NAME["08014"] = "City and County of Broomfield"

KINDS = [
    ("county", 2020, "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("judicial", 2020, "Judicial districts, as whole counties", "CO-JD and the district number (CO-JD18), as sl_places kind judicial"),
    ("congressional", 2022, "Congressional districts of the plan first used in 2022",
     "CO-CD and the district number (CO-CD7), as the jurisdiction_id of our State Board of Education and Regent races"),
    ("senate", 2022, "State Senate districts of the plan first used in 2022", "district number, as the district of our Senate races"),
    ("house", 2022, "State House districts of the plan first used in 2022", "district number, as the district of our House races"),
]
KIND_NAMES = [k[0] for k in KINDS]
REDRAWN = ("The 2020 election was held on the districts of 2011 (seven congressional districts, and the Senate and House districts of "
           "that plan); the districts drawn after the 2020 census were first used in 2022, so 2020 is not given.")
WHAT = ("How each Colorado place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic ticket, "
        "the Republican ticket, every other candidate together and the total, added up from the precinct results in the Colorado "
        "Secretary of State's Historical Elections Database.")
NOTE = ("What this is: how the people of a place voted in that election, in the precinct results of the Secretary of State's Historical "
        "Elections Database, checked county by county against the Secretary's Abstract of Votes Cast, added up here by county and by "
        "judicial district and, for 2022 and 2024, by congressional, state Senate and state House district, on the lines in force at that "
        "election. A Colorado precinct lies in one district of each kind, so nothing is divided or estimated. What this is not: it is not "
        "a prediction of any election; it says nothing about any candidate on a later ballot or about any voter; a nonpartisan office "
        "stays nonpartisan; and a place is not its lines for ever: where a district was drawn again, the figures are for the lines of "
        "that year. Colorado elected no senator in 2024, and its Governor only in 2022. The tickets are named, as the Secretary's own "
        "results name them, only to say which election this was. In a place with very few voters the split would come close to saying "
        "how particular people voted; those contests are listed in the place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every "
               "other candidate, certified write-in candidates included) and total (the votes cast for candidates; Colorado counts a write-in "
               "only for a certified write-in candidate, and the results give no over or under votes). Minnesota's file calls the first count "
               "dfl. A contest a place does not have was not counted on its lines: congressional, Senate and House districts are given for "
               "2022 and 2024 only.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities and towns: a Colorado precinct's number names no city or town, and the results do not say which one it lies in. County "
             "commissioner districts, the Regional Transportation District's director districts, school, special and other districts: the "
             "results do not say which of them a precinct lies in, and a precinct can lie partly inside one.")


# ---------------------------------------------------------------- the files

_last = [0.0]


def fetch(url, path, refresh, say, what, magic=None):
    """One file through states/net.py (its honest User-Agent), kept on disk; a pause between requests that are not."""
    fresh = refresh or not (os.path.exists(path) and os.path.getsize(path) > 0)
    if fresh:
        time.sleep(max(0.0, PAUSE - (time.time() - _last[0])))
    try:
        net.download(url, path, 0 if refresh else KEEP_DAYS, tries=3, say=say)
    except Exception as e:  # noqa: BLE001
        raise Stop(f"    {what}: could not be fetched ({e}) and no copy is on disk. Wait a few minutes and run this again.")
    finally:
        if fresh:
            _last[0] = time.time()
    if magic is not None:
        with open(path, "rb") as fh:
            if not fh.read(len(magic)).startswith(magic):
                raise Stop(f"    {what}: what came back is not the file (it does not begin {magic!r}); stopping")
    return path


def number(cell, what):
    s = (cell or "").strip().replace(",", "")
    if not re.fullmatch(r"\d+", s):
        raise Stop(f"    {what}: a cell is {cell!r}, not a count of votes; stopping")
    return int(s)


def read_contest(text, what):
    """One contest's CSV: {"heads": [(name, party)], "totals": [...], "counties": {fips: [...]}, "precincts": {number:
    (fips, [...])}}; the last count of each row is its Total Votes Cast. Every sum the file allows is checked."""
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    if not rows or rows[0][0].strip() != "County" or rows[0][-1].strip() != "Total Votes Cast":
        raise Stop(f"    {what}: the file is not laid out as County, the candidates, Total Votes Cast; stopping")
    heads = []
    for h in rows[0][1:-1]:
        parts = [p.strip() for p in h.split("\n")]
        heads.append((" ".join(parts[0].split()), " ".join(" ".join(parts[1:]).split())))
    width = len(rows[0])
    totals, counties, precincts, cur = [], {}, {}, None
    for r in rows[1:]:
        if len(r) != width:
            raise Stop(f"    {what}: a row has {len(r)} cells, not {width}; stopping")
        lab = r[0].strip()
        vals = [number(c, f"{what}, {lab}") for c in r[1:]]
        if sum(vals[:-1]) != vals[-1]:
            raise Stop(f"    {what}, {lab}: the candidates add up to {sum(vals[:-1])}, the row's Total Votes Cast is {vals[-1]}; stopping")
        if lab == "Totals":
            totals.append(vals)
            continue
        m = re.fullmatch(r"Precinct (\d{10})", lab)
        if m:
            if cur is None:
                raise Stop(f"    {what}: precinct {m.group(1)} stands under no county; stopping")
            if m.group(1) in precincts:
                raise Stop(f"    {what}: precinct {m.group(1)} is named twice; stopping")
            precincts[m.group(1)] = (cur, vals)
            continue
        code = FIPS.get(bare(lab))
        if code is None or code in counties:
            raise Stop(f"    {what}: a row is named {lab!r}, not a Colorado county once; stopping")
        cur = code
        counties[code] = vals
    if not totals or any(t != totals[0] for t in totals):
        raise Stop(f"    {what}: no Totals row, or two that differ; stopping")
    for code, vals in counties.items():
        mine = [sum(v[i] for c, v in precincts.values() if c == code) for i in range(width - 1)]
        if mine != vals:
            raise Stop(f"    {what}: the precincts of {COUNTY_NAME[code]} do not add up to its row; stopping")
    if [sum(v[i] for v in counties.values()) for i in range(width - 1)] != totals[0]:
        raise Stop(f"    {what}: the counties do not add up to the Totals row; stopping")
    return {"heads": heads, "totals": totals[0], "counties": counties, "precincts": precincts}


def read_search(text, date):
    """The database's search page for one office and year: [(contest number, office, district)] of the general election
    held on that date."""
    out = []
    for m in re.finditer(r'<tr id="contest-id-(\d+)" class="([^"]*)">(.*?)</tr>\s*<!--// END tr#contest-id', text, re.S):
        if "event_type__general" not in m.group(2).split():
            continue
        body = m.group(3)
        day = re.search(r'data-sort="(\d{8})"', body)
        office = re.search(r'<td class="office"[^>]*>(.*?)</td>', body, re.S)
        div = re.search(r'<td class="division"[^>]*>(.*?)</td>', body, re.S)
        if not (day and office and div):
            raise ValueError(f"contest {m.group(1)}: a row without its date, office or district")
        if day.group(1) != date.replace("-", ""):
            continue
        clean = lambda s: " ".join(H.unescape(re.sub(r"<[^>]+>", " ", s)).split())   # noqa: E731
        out.append((m.group(1), clean(office.group(1)), clean(div.group(1))))
    return out


def find_contests(year, cache, refresh, say):
    """{office key: [(contest number, district or None)]} for one general election, from the database's search pages."""
    e = ELECTIONS[year]
    found = {}
    keys = ["president", "us_senate", "governor"] if year not in DISTRICT_YEARS else list(OFFICES)
    for key in keys:
        if not any(c["year"] == year and c["key"] == key for c in CONTESTS) and key in ("president", "us_senate", "governor"):
            continue
        url = f"{FILES}/contests/search/year_from:{year}/year_to:{year}/office_id:{OFFICES[key]}/stage:General"
        path = fetch(url, os.path.join(cache, "elstats", f"search_{year}_{OFFICES[key]}.html"), refresh, say, f"the database's {year} {OFFICE_WORDS[key]} contests")
        try:
            rows = read_search(open(path, encoding="utf-8", errors="replace").read(), e["date"])
        except ValueError as x:
            raise Stop(f"    the database's {year} {OFFICE_WORDS[key]} contests: {x}; stopping")
        got = []
        for cid, office, div in rows:
            if office != OFFICE_WORDS[key]:
                raise Stop(f"    the database's {year} search for {OFFICE_WORDS[key]} lists contest {cid} as {office!r}; stopping")
            if key in ("president", "us_senate", "governor"):
                if div != "State of Colorado":
                    raise Stop(f"    the database's {year} {office} contest {cid} is for {div!r}, not the state; stopping")
                got.append((cid, None))
            else:
                m = re.fullmatch(r"District (\d+)", div)
                if not m:
                    raise Stop(f"    the database's {year} {office} contest {cid} is for {div!r}, not a numbered district; stopping")
                got.append((cid, int(m.group(1))))
        found[key] = got
    return found


def contest_file(cid, cache, refresh, say, what):
    path = fetch(f"{FILES}/contests/download/{cid}/.csv", os.path.join(cache, "elstats", f"contest_{cid}.csv"), refresh, say, what)
    with open(path, encoding="utf-8") as fh:
        return path, read_contest(fh.read(), what)


# ---------------------------------------------------------------- the Secretary's abstracts

def read_abstract_html(text, what):
    """One office's page of a year's abstract: (headings, {county fips or 'Total': [cells]})."""
    heads = [" ".join(H.unescape(re.sub(r"<[^>]+>", " ", h)).split()) for h in re.findall(r'<th scope="col">(.*?)</th>', text, re.S)]
    body = text[text.find("<tbody"):text.find("</tbody>")]
    rows = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = [" ".join(H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r'<span class="ADAhidden">.*?</span>', "", c, flags=re.S))).split())
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not cells:
            continue
        key = "Total" if cells[0] == "Total" else FIPS.get(bare(cells[0]))
        if key is None or key in rows or len(cells) != len(heads):
            raise ValueError(f"{what}: a row reads {cells[0]!r} with {len(cells)} cells, not a county once with {len(heads)}")
        rows[key] = cells
    if len(rows) != len(COUNTIES) + 1:
        raise ValueError(f"{what}: {len(rows)} rows, not the 64 counties and the Total")
    return heads, rows


def abstract_three(heads, rows, c, what):
    """{county fips or 'Total': [dem, rep, total]} from an abstract page: the one (DEM) and one (REP) column whose names carry
    the tickets' family names, and the Total column."""
    col = {}
    for s, mark in (("dem", "(DEM)"), ("rep", "(REP)")):
        fits = [i for i, h in enumerate(heads) if mark in h and "Write-In" not in h]
        if len(fits) != 1 or surname(c[s]) not in fold(heads[fits[0]]):
            raise ValueError(f"{what}: the {mark} column is not the one ({c[s]}) this loader was checked against")
        col[s] = fits[0]
    if heads.count("Total") != 1:
        raise ValueError(f"{what}: no one Total column")
    col["total"] = heads.index("Total")
    return {k: [number(cells[col[s]], what) for s in ("dem", "rep", "total")] for k, cells in rows.items()}


def read_abstract_pdf(path, c, what):
    """The President pages of the 2023-2024 biennial abstract: {county fips or 'Total': [dem, rep, total]}. The table runs
    over several pages headed 'Presidential Electors' and '(continued)'; the first page's columns begin Registered
    Voters, Ballots Cast, the Democratic ticket, the Republican ticket, and the last page's end Total, Turnout %."""
    from ballot import pdftext
    lines = [(p, t.strip()) for p, _y, t in pdftext.lines(path)]
    heading, more = c["abstract"], f"{c['abstract']} (continued)"
    start = [i for i, (_p, t) in enumerate(lines) if t == heading]
    if len(start) != 1:
        raise ValueError(f"{what}: the heading {heading!r} is on {len(start)} lines, not one")
    # the table runs from its heading to the next table's heading (a line, not ours, followed by a line of column names)
    run = []
    for i in range(start[0], len(lines)):
        t = lines[i][1]
        if i > start[0] and t not in (heading, more) and i + 1 < len(lines) and lines[i + 1][1].startswith("County "):
            break
        run.append(lines[i])
    first = " ".join(t for _p, t in run[:6])
    a = first.find("Registered Voters Ballots Cast")
    names = first[a:a + 160]
    if a < 0 or not (0 < names.find(surname(c["dem"]).title()) < names.find(surname(c["rep"]).title())) or "(DEM)" not in names or "(REP)" not in names:
        raise ValueError(f"{what}: the first page's columns do not begin with the Democratic and Republican tickets this loader was checked against")
    nums = collections.defaultdict(list)
    for _p, t in run:
        m = re.fullmatch(r"([A-Z][A-Za-z .]+?) ((?:[\d,]+ ?)+?)(?: ([\d.]+%))?", t)
        key = m and ("Total" if m.group(1) == "Total" else FIPS.get(bare(m.group(1))))
        if key:
            nums[key] += [int(x.replace(",", "")) for x in m.group(2).split()]
    out = {}
    for k, v in nums.items():
        if len(v) < 5 or sum(v[2:-1]) != v[-1]:
            raise ValueError(f"{what}: the row {k} does not read as voters, ballots, the candidates and a Total that adds up")
        out[k] = [v[2], v[3], v[-1]]
    if len(out) != len(COUNTIES) + 1:
        raise ValueError(f"{what}: {len(out)} rows, not the 64 counties and the Total")
    return out, [run[0][0], run[-1][0]]


def abstract_figures(c, cache, refresh, say):
    """(the abstract's {county or 'Total': [dem, rep, total]}, its source record) for one contest."""
    a = ELECTIONS[c["year"]]["abstract"]
    what = f"the {c['year']} abstract, {c['office']}"
    if a["kind"] == "pdf":
        path = fetch(a["url"], os.path.join(cache, a["file"]), refresh, say, what, magic=b"%PDF")
        figs, run = read_abstract_pdf(path, c, what)
        rec = {"url": a["url"], "pages": f"{run[0]} to {run[-1]} of the PDF"}
    else:
        url = a["base"] + c["abstract"]
        path = fetch(url, os.path.join(cache, f"co_{c['year']}_abstract_{c['abstract']}"), refresh, say, what)
        with open(path, encoding="utf-8", errors="replace") as fh:
            heads, rows = read_abstract_html(fh.read(), what)
        figs = abstract_three(heads, rows, c, what)
        rec = {"url": url}
    rec.update(fetched=M._day(path), sha256=M._sha_file(path))
    return figs, rec


# ---------------------------------------------------------------- adding up

def fold(s):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", H.unescape(s or "")) if not unicodedata.combining(ch)).upper().replace("’", "'")


def surname(ticket):
    return fold(ticket.split(" and ")[0].split()[-1])


def sides_of(c, heads, what):
    """Which columns of a contest's file are the two tickets: the one column of the party whose first name carries the
    ticket's family name."""
    side = {}
    for s, party in (("dem", "Democratic"), ("rep", "Republican")):
        fits = [i for i, (name, p) in enumerate(heads) if p == party and surname(c[s]) in fold(name)]
        if len(fits) != 1:
            raise Stop(f"    {what}: the {party} candidate is not the one ({c[s]}) this loader was checked against; stopping")
        side[s] = fits[0]
    return side


def four(vals, side):
    dem, rep, total = vals[side["dem"]], vals[side["rep"]], vals[-1]
    return [dem, rep, total - dem - rep, total]


def _add(into, v):
    for i in range(len(v)):
        into[i] += v[i]


def few(rec):
    hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
    if hold:
        rec["too_few"] = hold
    return rec


def digits(p):
    """What a precinct's number says: (congressional, Senate, House district, county number)."""
    return int(p[0]), int(p[1:3]), int(p[3:5]), int(p[5:7])


KIND_OF = {"congress": "congressional", "state_senate": "senate", "state_house": "house"}


def districts_of(year_files, empty, failed, year):
    """{precinct: {kind: {districts}}} for one year, and what was read from where. year_files: {"congress": {d: precincts},
    "state_senate": {...}, "state_house": {...}, "all": precincts of the statewide contests}; empty: the precincts that
    cast no vote in the statewide contests (a contest's file can leave them out). A precinct's districts are the
    contests it voted in, which must include the one its number names; a precinct in two contests of a kind is named,
    and those districts are left out for the year. The number alone gives the district of an empty precinct, and the
    Senate district of a precinct whose Senate seat was not on the ballot."""
    member = {}
    for key in KIND_OF:
        member[key] = collections.defaultdict(set)
        for d, ps in year_files[key].items():
            for p in ps:
                member[key][p].add(d)
    allp = year_files["all"]
    for key in KIND_OF:
        stray = sorted(set(member[key]) - set(allp))
        if stray:
            failed.append(f"{year}: {len(stray)} precincts vote in a {OFFICE_WORDS[key]} contest and not in the statewide contests (first {stray[0]})")
    out = {}
    info = {"senate_from_number": 0, "empty_from_number": collections.defaultdict(list), "split": collections.defaultdict(dict)}
    for p in sorted(allp):
        cd, sd, hd, _county = digits(p)
        out[p] = {}
        for key, dnum in (("congress", cd), ("state_senate", sd), ("state_house", hd)):
            ds = member[key].get(p, set())
            held = key != "state_senate" or dnum in year_files[key]
            if ds and dnum not in ds:
                failed.append(f"{year}: precinct {p} votes in {OFFICE_WORDS[key]} contests {sorted(ds)}; its number says {dnum}")
            elif len(ds) > 1:
                info["split"][KIND_OF[key]][p] = sorted(ds)
            elif not ds and held:
                if p in empty:
                    info["empty_from_number"][KIND_OF[key]].append(p)
                else:
                    failed.append(f"{year}: precinct {p} cast votes and voted in no {OFFICE_WORDS[key]} contest; its number says {dnum}, which was on the ballot")
            elif not ds:
                info["senate_from_number"] += 1
            out[p][KIND_OF[key]] = ds or {dnum}
    return out, info


def build(years, abstracts, clerk, judicial, contests=CONTESTS, expect=True, sources=None):
    """Everything added up and checked. years: {year: {"statewide": {contest id: table}, "congress": {d: precincts},
    "state_senate": {...}, "state_house": {...}}} (the district parts for DISTRICT_YEARS only); abstracts: {contest id:
    {county or 'Total': [dem, rep, total]}}; clerk: {contest id: {dem, rep, other, total, where}}; judicial: {n:
    [county names]}. Returns (the file, what failed)."""
    failed, ctl, state = [], {}, {}
    pack = lambda v: dict(zip(SIDES, v))                                                               # noqa: E731
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    ids = [c["id"] for c in contests]
    first = {k[0]: k[1] for k in KINDS}
    district_years = [y for y in DISTRICT_YEARS if y in years and years[y].get("state_house")]
    given = {k: [c["id"] for c in contests if c["year"] >= first[k] and (first[k] == 2020 or c["year"] in district_years)] for k in KIND_NAMES}
    precinct_sets, dist, from_number, county_of = {}, {}, {}, {}

    for c in contests:
        cid, year = c["id"], c["year"]
        t = years[year]["statewide"][cid]
        side = sides_of(c, t["heads"], f"{year} {c['office']}")
        c["_side"] = side
        ps = set(t["precincts"])
        if year in precinct_sets and precinct_sets[year] != ps:
            failed.append(f"{cid}: the precincts are not those of the year's other statewide contest")
        precinct_sets.setdefault(year, ps)
        for p, (code, _v) in t["precincts"].items():
            if county_of.setdefault((year, p), code) != code:
                failed.append(f"{cid}: precinct {p} stands under two counties")
        sums = collections.defaultdict(lambda: [0] * 4)
        for p, (code, vals) in t["precincts"].items():
            _add(sums[code], four(vals, side))
        state[cid] = [sum(v[i] for v in sums.values()) for i in range(4)]
        if expect and sorted(sums) != sorted(COUNTY_NAME):
            failed.append(f"{cid}: precincts in {len(sums)} counties, not 64")
        rec = ctl[cid] = {"sum_of_precincts": pack(state[cid]), "precincts": len(t["precincts"]),
                          "database": {"counties_equal_their_precincts": True, "totals_row_equal": four(t["totals"], side) == state[cid]},
                          "source": f"co-sos-elstats-{year}"}
        if four(t["totals"], side) != state[cid]:
            failed.append(f"{cid}: the precincts add up to {pack(state[cid])}, the database's Totals row to {pack(four(t['totals'], side))}")
        ab = abstracts.get(cid)
        if ab:
            differ = [COUNTY_NAME[k] for k in sums if ab.get(k) != [sums[k][0], sums[k][1], sums[k][3]]]
            tot_ok = ab.get("Total") == [state[cid][0], state[cid][1], state[cid][3]]
            rec["abstract"] = {"compared": "the Democratic ticket, the Republican ticket and the total, county by county and the Total row",
                               "counties": {"compared": len(sums), "equal": len(sums) - len(differ)}, "total_row_equal": tot_ok,
                               "official": {"dem": ab["Total"][0], "rep": ab["Total"][1], "total": ab["Total"][2]} if "Total" in ab else None,
                               "source": f"co-sos-abstract-{year}"}
            if differ or not tot_ok:
                failed.append(f"{cid}: the precincts differ from the Secretary's abstract in {', '.join(differ) or 'the Total row'}")
        elif expect:
            failed.append(f"{cid}: the Secretary's abstract was not read")
        typed = CHECKED.get(cid) if expect else None
        if typed and typed != pack(state[cid]):
            failed.append(f"{cid}: the precincts add up to {pack(state[cid])}; this loader was checked against {typed}")
        if clerk.get(cid):
            k = clerk[cid]
            same = k["dem"] == state[cid][0] and k["rep"] == state[cid][1]
            rec["clerk"] = {"official": {s: k[s] for s in ("dem", "rep")}, "equal": same, "where": k.get("where"),
                            "compared": "the Democratic and Republican figures; the Clerk's page leaves out some certified write-in "
                                        f"candidates (its lines add up to {k['total']:,})"}
            if not same:
                failed.append(f"{cid}: the precincts give Democratic {state[cid][0]} and Republican {state[cid][1]}; the Clerk of the House prints {k['dem']} and {k['rep']}")
        rec["equal"] = not [f for f in failed if f.startswith(cid)]
        for code, v in sums.items():
            votes["county"][code][cid] = v
        for d, names in judicial.items():
            v = [0] * 4
            for name in names:
                _add(v, sums.get(FIPS[bare(name)], [0] * 4))
            votes["judicial"][f"CO-JD{d}"][cid] = v

    # ---- the districts of 2022 and 2024
    leg_ctl, left_out = {}, {k: {} for k in ("congressional", "senate", "house")}
    for year in district_years:
        y = years[year]
        if expect:
            for key, n in (("congress", CD), ("state_house", HOUSE)):
                if sorted(y[key]) != list(range(1, n + 1)):
                    failed.append(f"{year}: {OFFICE_WORDS[key]} contests for {len(y[key])} districts, not {n}")
        mine = [c for c in contests if c["year"] == year]
        empty = {p for p in precinct_sets[year] if all(years[year]["statewide"][c["id"]]["precincts"][p][1][-1] == 0 for c in mine)}
        files = {"congress": y["congress"], "state_senate": y["state_senate"], "state_house": y["state_house"], "all": precinct_sets[year]}
        dist[year], info = districts_of(files, empty, failed, year)
        counties_seen = collections.defaultdict(set)
        for p in precinct_sets[year]:
            counties_seen[digits(p)[3]].add(county_of[(year, p)])
        if any(len(v) != 1 for v in counties_seen.values()) or len({next(iter(v)) for v in counties_seen.values()}) != len(counties_seen):
            failed.append(f"{year}: the precinct numbers' county digits do not name one county each")
        out_d = {k: set().union(*map(set, info["split"].get(k, {}).values())) for k in left_out}
        for k in left_out:
            left_out[k][year] = sorted(out_d[k])
        leg_ctl[str(year)] = {"congressional_contests": len(y["congress"]), "senate_contests": len(y["state_senate"]),
                              "house_contests": len(y["state_house"]), "precincts": len(precinct_sets[year]),
                              "precincts_with_no_votes": len(empty),
                              "precincts_whose_senate_seat_was_not_on_the_ballot_read_from_their_number": info["senate_from_number"],
                              "precincts_with_no_votes_left_out_of_a_contest_file_read_from_their_number":
                                  {k: v for k, v in info["empty_from_number"].items()},
                              "precincts_in_two_districts_of_a_kind": [{"precinct": p, "county": COUNTY_NAME[county_of[(year, p)]], "kind": k,
                                                                        "districts": ds, "number_says": {"congressional": digits(p)[0], "senate": digits(p)[1],
                                                                                                         "house": digits(p)[2]}[k]}
                                                                       for k, d in info["split"].items() for p, ds in sorted(d.items())],
                              "districts_left_out": {k: v[year] for k, v in left_out.items() if v[year]}}
        for c in mine:
            t = years[year]["statewide"][c["id"]]
            sums = {k: collections.defaultdict(lambda: [0] * 4) for k in left_out}
            rest = {k: [0] * 4 for k in left_out}
            for p, (_code, vals) in t["precincts"].items():
                v = four(vals, c["_side"])
                for k in left_out:
                    ds = dist[year][p][k]
                    if len(ds) == 1 and next(iter(ds)) not in out_d[k]:
                        _add(sums[k][f"CO-CD{next(iter(ds))}" if k == "congressional" else str(next(iter(ds)))], v)
                    else:
                        _add(rest[k], v)
            for k, d in sums.items():
                for key, v in d.items():
                    votes[k][key][c["id"]] = v
                back = [sum(v[i] for v in d.values()) + rest[k][i] for i in range(4)]
                if back != state[c["id"]]:
                    failed.append(f"{c['id']}: the {k} districts given and the precincts left out add up to {back}, not {state[c['id']]}")
    if district_years and expect:
        both = set()
        for year in district_years:
            both |= set(years[year]["state_senate"])
            seen = {int(k) for k in votes["senate"] if any(cid.startswith(str(year)) for cid in votes["senate"][k])} | set(left_out["senate"].get(year, []))
            if sorted(seen) != list(range(1, SENATE + 1)):
                failed.append(f"{year}: the precincts' Senate districts are not the 35")
        if sorted(both) != list(range(1, SENATE + 1)):
            failed.append(f"Senate contests for {len(both)} districts in {district_years}, not {SENATE}")
    if expect:
        if sorted(bare(x) for names in judicial.values() for x in names) != sorted(FIPS) or len(judicial) != 23:
            failed.append("judicial districts: the statute's lists are not 23 districts holding every county once")

    # ---- the places
    places = {k: {} for k in KIND_NAMES}
    packed = lambda d: {cid: pack(d[cid]) for cid in ids if cid in d}                                  # noqa: E731
    for code in sorted(votes["county"]):
        places["county"][code] = few({"name": COUNTY_NAME[code], "votes": packed(votes["county"][code])})
    for d in sorted(judicial, key=int):
        places["judicial"][f"CO-JD{d}"] = few({"name": f"{M.ordinal(int(d))} Judicial District",
                                               "counties": sorted(FIPS[bare(x)] for x in judicial[d]), "votes": packed(votes["judicial"][f"CO-JD{d}"])})
    reach = {k: collections.defaultdict(set) for k in ("congressional", "senate", "house")}
    for year in district_years:
        for p, ds in dist[year].items():
            code = county_of[(year, p)]
            for k, nums in ds.items():
                for n in nums:
                    reach[k][f"CO-CD{n}" if k == "congressional" else str(n)].add(code)
    for kind, word in (("congressional", "Congressional District"), ("senate", "Senate District"), ("house", "House District")):
        for k in sorted(votes[kind], key=lambda x: int(re.sub(r"\D", "", x))):
            n = re.sub(r"\D", "", k)
            places[kind][k] = few({"name": f"{word} {n}", "counties": sorted(reach[kind][k]), "votes": packed(votes[kind][k])})
    kinds_ctl = {}
    for kind in KIND_NAMES:
        if any(left_out.get(kind, {}).values()):
            kinds_ctl[kind] = "not every district is given every year; the districts given and the precincts of those left out add up to the statewide sum"
            continue
        bad = [cid for cid in given[kind] if [sum(p["votes"][cid][s] for p in places[kind].values() if cid in p["votes"]) for s in SIDES] != state[cid]]
        kinds_ctl[kind] = "equal" if not bad else f"differs for {', '.join(bad)}"
        failed += [f"{kind}: its places do not add up to the statewide sum for {cid}" for cid in bad]

    records = []
    for c in contests:
        t = years[c["year"]]["statewide"][c["id"]]
        rec = {"id": c["id"], "date": ELECTIONS[c["year"]]["date"], "office": c["office"], "table": f"co-sos-elstats-{c['year']}",
               "kinds": [k for k in KIND_NAMES if c["id"] in given[k] and any(c["id"] in p["votes"] for p in places[k].values())]}
        for s, word in (("dem", "Democratic"), ("rep", "Republican")):
            name, party = t["heads"][c["_side"][s]]
            rec[s] = {"party": word, "ticket": c[s], "column": f"the column headed {name} ({party})"}
        rec["other"] = {"what": "every other candidate, certified write-in candidates included, together",
                        "columns": [f"{n} ({p})" if p else n for i, (n, p) in enumerate(t["heads"]) if i not in c["_side"].values()]}
        rec["total"] = {"what": "the file's Total Votes Cast: the votes for all the candidates; the results give no over or under votes"}
        rec["statewide"] = pack(state[c["id"]])
        rec["official_source"] = f"co-sos-abstract-{c['year']}"
        if c.get("contest_number"):
            rec["database_contest"] = c["contest_number"]
        records.append(rec)
    kinds = {}
    for kind, year, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind],
                       "covers_the_state": True, "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if year > min(c["year"] for c in contests):
            kinds[kind]["why_not_2020"] = REDRAWN
    kinds["judicial"]["note"] = ("The counties of each district are those sections 13-5-102 to 13-5-123.1, C.R.S. list today. The 23rd (Douglas, "
                                 "Elbert and Lincoln) was part of the 18th until January 2025; every year's figures are today's districts' "
                                 "counties added up.")
    for kind in ("congressional", "senate", "house"):
        lo = {str(y): v for y, v in left_out[kind].items() if v}
        kinds[kind]["covers_the_state"] = not lo
        kinds[kind]["left_out"] = {str(y): v for y, v in left_out[kind].items()}
        kinds[kind]["note"] = ("A Colorado precinct is drawn inside one congressional, one Senate and one House district, and a district is "
                               "the precincts that voted in its contest. "
                               + (f"Left out ({'; '.join(f'{y}: {len(v)}' for y, v in lo.items())}): districts "
                                  f"{', '.join(str(x) for x in sorted(set().union(*map(set, lo.values()))))}, because a precinct's voters were "
                                  "counted in two of them that year (control.districts names it), and the results give that precinct's other "
                                  "votes whole; nothing is divided or estimated." if lo else "Every district is given."))
    kinds["senate"]["note"] += (" Half the Senate is elected each time; a precinct whose Senate seat was not on the ballot that year is given the "
                                "Senate district its ten-digit number names, after the number was found to name the district of every precinct "
                                "whose seat was on the ballot, in 2022 and in 2024.")
    control = {"result": "equal" if not failed else "differs",
               "statement": ("For every contest each row's candidates add up to its Total Votes Cast, each county's precincts to the county's "
                             "row and the counties to the Totals row of the database's file; the counties equal the Secretary of State's "
                             "Abstract of Votes Cast county by county; for President and U.S. Senator the Democratic and Republican figures "
                             "equal the Clerk of the House's statistics; in 2022 and 2024 every precinct that cast votes voted in the "
                             "congressional and House contests, and the Senate contest where its seat was up, of the districts its number "
                             "names (one precinct also in a second House contest, named in districts); and the counties, the judicial "
                             "districts and the districts given, with the precincts of those left out, add up to the statewide sum."
                             if not failed else "The sums do not all agree; see the differences."),
               "precincts": {str(y): len(precinct_sets[y]) for y in sorted(precinct_sets)},
               "contests": ctl, "kinds": kinds_ctl, "districts": leg_ctl,
               "notes": ["The database's 2022 Governor file carries one minor ticket on two lines (Paul Noel Fiorino with no party, "
                         "holding its votes, and the whole ticket under the Unity Party of Colorado with none); both lines are counted in "
                         "other, and the totals equal the abstract's."]}
    doc = {"what": WHAT, "note": NOTE, "state": "CO", "generated": M._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(SIDES), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": control,
           "coverage": {"not_given": NOT_GIVEN, "no_2024_senate": "Colorado elected no United States senator in 2024.",
                        "governor": "Colorado elected its Governor in 2022, not in 2020 or 2024."},
           "sources": [], "places": places}
    for c in contests:
        c.pop("_side", None)
    return doc, failed


# ---------------------------------------------------------------- the run

def clerk_totals(contests, cache, refresh, say):
    from ballot import wy_place_votes as W                      # its reader of the Clerk's pages, given the state's heading
    out, recs = {}, []
    for year in sorted({c["year"] for c in contests if c.get("clerk")}, reverse=True):
        src = CLERK[year]
        path = os.path.join(cache, src["file"])
        rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
        try:
            fetch(src["url"], path, refresh, say, src["title"], magic=b"%PDF")
            doc = W.read_clerk(path, state="COLORADO")
            where = doc["where"].replace("Wyoming", "Colorado")
            rec.update(fetched=M._day(path), sha256=M._sha_file(path), where=where,
                       read="The Colorado lines for presidential electors and United States Senator; its under and over votes are left out.")
            for c in contests:
                if c["year"] == year and c.get("clerk"):
                    f = W.clerk_figures(doc, c["clerk"])
                    out[c["id"]] = dict(f, where=where)
        except (Stop, Exception) as e:  # noqa: BLE001  the abstracts are the control; the Clerk's page is a second one
            say(f"      {src['title']}: could not be read ({e}); the Secretary's abstract alone is the control for {year}")
            rec["unread"] = f"could not be read on {M._now()}: {e}"
        recs.append(rec)
    return out, recs


def judicial_districts(say):
    """{n: [county names]} from the statute as ballot/state_local_co.py read and kept it, and the source record."""
    if not os.path.exists(JUDICIAL_KEPT):
        from ballot import state_local_co as L
        cmap = {L.ckey(name): (STATE_FIPS + code, name) for code, name in COUNTIES}
        L.read_judicial(os.path.dirname(JUDICIAL_KEPT), cmap, say)
    with open(JUDICIAL_KEPT, encoding="utf-8") as fh:
        kept = json.load(fh)
    out = {int(n): d["counties"] for n, d in kept["districts"].items()}
    rec = {"id": "co-crs-2026-title-13-judicial-districts", "kind": "statute, as the Office of Legislative Legal Services publishes it",
           "agency": "Colorado General Assembly, Office of Legislative Legal Services",
           "title": f"Colorado Revised Statutes {kept['edition']}, Title 13: sections 13-5-101 to 13-5-123.1, the judicial districts",
           "url": kept["url"], "sha256": kept["sha256"], "fetched": kept["read"],
           "read": "The one sentence of each section that names the district's counties, as ballot/state_local_co.py read and kept them."}
    return out, rec


def our_places(db):
    """{kind: ids} of our Colorado places and races, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'co-%'"):
            out[kind].add(pid)
        for office, level, jid, district in con.execute("SELECT office_kind, level, jurisdiction_id, district FROM sl_races WHERE state = 'CO'"):
            if office == "state_senate":
                out["senate"].add(str(district))
            elif office == "state_house":
                out["house"].add(str(district))
            elif str(jid).startswith("CO-CD"):
                out["congressional"].add(str(jid))
            elif str(jid).startswith("CO-JD"):
                out["judicial"].add(str(jid))
            elif level == "county" or re.fullmatch(r"08\d{3}", str(jid)):
                out["county"].add(str(jid))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Colorado place votes: the Secretary of State's Historical Elections Database (historicalelectiondata.coloradosos.gov), precinct results")
    net.patient_lookups()
    os.makedirs(os.path.join(cache, "elstats"), exist_ok=True)
    contests = [dict(c) for c in CONTESTS]
    years, srcs, files = {}, [], collections.defaultdict(list)
    for year in sorted(ELECTIONS, reverse=True):
        e = ELECTIONS[year]
        found = find_contests(year, cache, refresh, say)
        y = years[year] = {"statewide": {}}
        for c in [c for c in contests if c["year"] == year]:
            got = found.get(c["key"], [])
            if len(got) != 1:
                raise Stop(f"    the database lists {len(got)} {year} general election contests for {OFFICE_WORDS[c['key']]}, not one; stopping")
            c["contest_number"] = got[0][0]
            path, y["statewide"][c["id"]] = contest_file(got[0][0], cache, refresh, say, f"{year} {c['office']}")
            files[year].append((got[0][0], path))
        if year in DISTRICT_YEARS:
            for key in ("congress", "state_senate", "state_house"):
                y[key] = {}
                for cid, d in found[key]:
                    path, t = contest_file(cid, cache, refresh, say, f"{year} {OFFICE_WORDS[key]} District {d}")
                    files[year].append((cid, path))
                    y[key][d] = set(y[key].get(d, set())) | set(t["precincts"])
            say(f"      {year}: {len(y['congress'])} congressional, {len(y['state_senate'])} Senate and {len(y['state_house'])} House contests")
        n = len(next(iter(y["statewide"].values()))["precincts"])
        say(f"      {year}: {n:,} precincts")
        digest = M._sha("".join(f"{cid}:{M._sha_file(p)}\n" for cid, p in sorted(files[year], key=lambda x: int(x[0]))).encode())
        srcs.append({"id": f"co-sos-elstats-{year}", "kind": "official results by precinct", "agency": AGENCY,
                     "title": f"State of Colorado Elections Database (Historical Elections Database), {year} General Election, each contest's results download",
                     "url": f"{DATABASE}/event/{e['event']}", "files": f"{FILES}/contests/download/<contest>/.csv",
                     "files_note": "The database serves its downloads from its own file host, the address its file links give.",
                     "contests": sorted(int(cid) for cid, _p in files[year]), "fetched": min(M._day(p) for _c, p in files[year]),
                     "sha256_of_the_files": digest, "precincts": n,
                     "read": "Of each file: the candidates' names and parties in the heading (only to check which ticket a column is), the "
                             "county and precinct labels and the counts. For the congressional, Senate and House contests only which "
                             "precincts voted in them."})
    abstracts, arecs = {}, {}
    for c in contests:
        try:
            abstracts[c["id"]], rec = abstract_figures(c, cache, refresh, say)
        except ValueError as e:
            raise Stop(f"    {e}; stopping")
        arecs.setdefault(c["year"], []).append(rec)
    for year, recs in sorted(arecs.items(), reverse=True):
        a = ELECTIONS[year]["abstract"]
        srcs.append({"id": f"co-sos-abstract-{year}", "kind": "official results by county (the control)", "agency": AGENCY, "title": a["title"],
                     "url": a.get("url") or a["base"] + "index.html", "listed_on": f"{ABSTRACT}/Archives.html", "read_from": recs,
                     "read": "Of each county's row and the Total row: the Democratic ticket, the Republican ticket and the total."})
    judicial, jrec = judicial_districts(say)
    srcs.append(jrec)
    srcs.append(dict(NUMBER_LAYOUT, read="Only the layout of the number; the districts themselves are read from the contests each precinct voted in."))
    say("    the second control: Clerk of the U.S. House (President and U.S. Senator)")
    clerk, clerk_recs = clerk_totals(contests, cache, refresh, say)
    doc, failed = build(years, abstracts, clerk, judicial, contests=contests)
    doc["sources"] = srcs + clerk_recs

    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['judicial'])} judicial districts; for 2022 and 2024, {len(p['congressional'])} congressional, "
        f"{len(p['senate'])} Senate and {len(p['house'])} House districts")
    for c in doc["contests"]:
        k, s = doc["control"]["contests"].get(c["id"], {}), c["statewide"]
        ab = k.get("abstract") or {}
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + ("equal to" if k.get("equal") else "DIFFERS from") + f" the database's Totals and the abstract ({(ab.get('counties') or {}).get('equal')} of "
            f"{(ab.get('counties') or {}).get('compared')} counties)"
            + (f"; Clerk of the House {'equal' if k['clerk']['equal'] else 'DIFFERS'}" if k.get("clerk") else ""))
    if failed:
        for line in failed[:40]:
            say(f"    CHECK: {line}")
        raise Stop(f"    Colorado place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES:
            idset = ours.get(kind, set())
            without = sorted((i for i in idset if not p[kind].get(i, {}).get("votes")), key=lambda x: (len(x), x))
            covered[kind] = {"places": len(idset), "with_votes": len(idset) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(idset) - len(without):,} of {len(idset):,}" + (f" (none for {', '.join(without[:16])})" if without else ""))
        covered["not_given_kinds"] = {k: len(v) for k, v in sorted(ours.items()) if k not in KIND_NAMES}
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {M._now()}")
    M.write(out, doc)
    say(f"    Colorado place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.2f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic and the readers on made-up tables

def selftest(say=print):
    checks = []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))

    def csv_text(heads, counties):
        """counties: [(name, [(precinct, [counts])])]; the Totals rows and county rows are added up here."""
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["County"] + [f"{n}\n{p}" for n, p in heads] + ["Total Votes Cast"])
        rows, tot = [], [0] * (len(heads) + 1)
        for name, pcs in counties:
            crow = [0] * (len(heads) + 1)
            for _p, v in pcs:
                v = list(v) + [sum(v)]
                _add(crow, v)
            _add(tot, crow)
            rows.append([name] + [f"{x:,}" for x in crow])
            rows += [[f"Precinct {p}"] + [f"{x:,}" for x in list(v) + [sum(v)]] for p, v in pcs]
        w.writerow(["Totals"] + [f"{x:,}" for x in tot])
        for r in rows:
            w.writerow(r)
        w.writerow(["Totals"] + [f"{x:,}" for x in tot])
        w.writerow([])
        return out.getvalue()

    heads = [("Ann Alder/ Bo Bay", "Democratic"), ("Cy Cedar/ Di Dale", "Republican"), ("Ed Elm", "Libertarian"), ("Al Ash", "Democratic")]
    # Adams: two precincts, House 1 and 2, Senate 1 (up) ; Alamosa: one precinct, House 2, Senate 2 (not up)
    pa = [("1010101001", [30, 50, 2, 0]), ("1010201002", [10, 5, 0, 1])]
    pb = [("1020202001", [0, 12, 0, 0])]
    t = read_contest(csv_text(heads, [("Adams", pa), ("Alamosa", pb)]), "made-up statewide")
    check("a contest file is read: counties, precincts, the Total Votes Cast column",
          (sorted(t["counties"]), t["precincts"]["1010101001"], t["totals"][-1]), (["08001", "08003"], ("08001", [30, 50, 2, 0, 82]), 110))
    bad = csv_text(heads, [("Adams", pa)]).replace("\n30,50,2,0,82", "\n30,50,2,0,83")
    try:
        read_contest(bad.replace("Precinct 1010101001,30,50,2,0,82", "Precinct 1010101001,30,50,2,0,83"), "made-up wrong")
        caught = False
    except Stop:
        caught = True
    check("a row whose candidates do not add up to its Total Votes Cast stops the loader", caught, True)
    c = {"id": "2022-governor", "year": 2022, "office": "Governor", "key": "governor", "dem": "Ann Alder and Bay", "rep": "Cy Cedar and Dale"}
    check("the tickets are found by party and family name, a write-in of the same party passed over", sides_of(c, heads, "made-up"), {"dem": 0, "rep": 1})
    years = {2022: {"statewide": {"2022-governor": t},
                    "congress": {1: {"1010101001", "1010201002", "1020202001"}},
                    "state_senate": {1: {"1010101001", "1010201002"}},
                    "state_house": {1: {"1010101001"}, 2: {"1010201002", "1020202001"}}}}
    ab = {"08001": [40, 55, 98], "08003": [0, 12, 12], "Total": [40, 67, 110]}
    jud = {1: ["Adams"], 2: ["Alamosa"]}
    doc, failed = build(years, {"2022-governor": ab}, {}, jud, contests=[dict(c)], expect=False)
    p = doc["places"]
    check("the control holds on the made-up tables", (doc["control"]["result"], failed), ("equal", []))
    check("a county adds up its precincts, the write-in with the others", p["county"]["08001"]["votes"]["2022-governor"],
          {"dem": 40, "rep": 55, "other": 3, "total": 98})
    check("a House district is the precincts that voted in its contest", p["house"]["2"]["votes"]["2022-governor"], {"dem": 10, "rep": 17, "other": 1, "total": 28})
    check("a Senate seat not on the ballot is read from the precinct's number", p["senate"]["2"]["votes"]["2022-governor"], {"dem": 0, "rep": 12, "other": 0, "total": 12})
    check("and is counted", doc["control"]["districts"]["2022"]["precincts_whose_senate_seat_was_not_on_the_ballot_read_from_their_number"], 1)
    check("a judicial district is whole counties", p["judicial"]["CO-JD2"]["votes"]["2022-governor"], {"dem": 0, "rep": 12, "other": 0, "total": 12})
    check("a place where every vote went one way is marked too_few", p["county"]["08003"].get("too_few"), ["2022-governor"])
    wrong = dict(years[2022], state_house={1: {"1010101001", "1010201002"}, 2: {"1020202001"}})
    check("a precinct voting in a House contest its number does not name is caught",
          build({2022: wrong}, {"2022-governor": ab}, {}, jud, contests=[dict(c)], expect=False)[0]["control"]["result"], "differs")
    split = dict(years[2022], state_house={1: {"1010101001", "1010201002"}, 2: {"1010201002", "1020202001"}})
    d2, f2 = build({2022: split}, {"2022-governor": ab}, {}, jud, contests=[dict(c)], expect=False)
    check("a precinct counted in two House contests leaves both districts out, and the sums still hold",
          (f2, sorted(d2["places"]["house"]), d2["control"]["districts"]["2022"]["districts_left_out"]), ([], [], {"house": [1, 2]}))
    check("a county that differs from the abstract is caught",
          build(years, {"2022-governor": dict(ab, **{"08003": [0, 11, 12]})}, {}, jud, contests=[dict(c)], expect=False)[0]["control"]["result"], "differs")
    page = ('<table><thead><tr><th scope="col">County</th><th scope="col">Ballots cast</th><th scope="col">Ann Alder / Bo Bay (DEM)</th>'
            '<th scope="col">Cy Cedar / Di Dale (REP)</th><th scope="col">Al Alder (DEM) (Write-In)</th><th scope="col">Total</th></tr></thead><tbody>'
            '<tr><td aria-label="County">Adams</td><td>120</td><td><span class="ADAhidden">Ann Alder</span>40</td><td>55</td><td>1</td><td>99</td></tr>'
            + "".join(f'<tr><td>{n}</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>' for _c, n in COUNTIES[1:]) +
            '<tr><td><strong>Total</strong></td><td>120</td><td>40</td><td>55</td><td>1</td><td>99</td></tr></tbody></table>')
    hh, rr = read_abstract_html(page, "made-up abstract")
    check("an abstract page is read by its headings, a write-in of the same party passed over", abstract_three(hh, rr, c, "made-up")["08001"], [40, 55, 99])
    check("county codes follow the Census order, Broomfield in its place",
          (FIPS["ADAMS"], FIPS[bare("Broomfield")], FIPS[bare("El Paso County")], FIPS["YUMA"], len(FIPS)), ("08001", "08014", "08041", "08125", 64))
    check("a precinct's number is read as districts and county", digits("6222630071"), (6, 22, 26, 30))
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Colorado place voted in past partisan general elections -> ballot/lean/co_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/co_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/co_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every file again, even when the cached copies are there")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic and the readers on made-up tables; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
