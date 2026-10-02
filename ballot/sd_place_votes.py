"""
ballot/sd_place_votes.py - how each South Dakota place voted in past partisan general elections, so a page can show
the record of a county or a legislative district without anyone labelling a candidate. The South Dakota twin of
ballot/mn_place_votes.py; the output has the same shape (the Democratic count is "dem" here, as in Wisconsin's,
Iowa's and North Dakota's files, where Minnesota's is "dfl").

    python ballot/sd_place_votes.py               reads (or downloads) the files, writes ballot/lean/sd_place_votes.json
    python ballot/sd_place_votes.py --refresh     asks for everything again even when the cached copies are there
    python ballot/sd_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/sd_place_votes.py --selftest    the arithmetic and the readers on made-up tables; downloads nothing

What it is, and is not
----------------------
For President in 2024, U.S. Senator and Governor in 2022, and President and U.S. Senator in 2020 (South Dakota
elected no senator in 2024): the votes for the Democratic ticket, the Republican ticket, everyone else together and
the total, for every one of the 66 counties and, for 2022 and 2024, for the legislative districts that can be added
up from whole precincts (see below: 14 of the 35 for 2022, and for President in 2024 only the few whose counties'
precinct figures equal the certified canvass). It is how the people of a place voted then. It is not a
prediction, it says nothing about any candidate on a later ballot or about any voter, and it turns no nonpartisan
office into a partisan one. No database is opened for writing; ballot_local_2026.sqlite is opened read-only at the
end, only to count how many of our places are covered.

Where the numbers come from
---------------------------
South Dakota publishes its results three ways, and they are not equally usable:

  - The State Canvass (sdsos.gov, Election History): the Board of Canvassers' certified record, a PDF with one row a
    county and a Total row for each statewide contest. The PDFs are scans with a text layer. THE COUNTY FIGURES IN
    THIS FILE ARE THESE ROWS. A scan's text layer can misread a digit, so a row is used only as part of a table that
    proves itself: all 66 counties present, and every column adding up to the Total row printed under it.
  - The county canvasses "with precinct level results" (same page): the official precinct record. For 2022 it is a
    PDF of real text (1,023 pages); for 2024 and 2020 the files are scans whose text layer misreads too much to add
    up (2t for 21, I for 1, cells missing), and they are not read. The 2022 file is read as a check only.
  - The Secretary's results site, electionresults.sd.gov: per contest a "Precinct Level" and a "County Level"
    workbook, the same system and layout as North Dakota's (ballot/nd_place_votes.py reads those). It is the only
    precinct record a script can read for 2024, but it stays headed "Unofficial Results" for good, and for 2024
    and 2020 it is a few votes short of the certified canvass in about a third of the counties (President, 2024: 24
    counties, 194 votes statewide; the 2022 site equals the canvass in all 66). Its 2024 presidential County Level
    workbook also heads the second column with the Republican ticket's names over another ticket's votes, so its
    columns are taken in the canvass's order, checked against the canvass, never by their headings alone.

So: counties come from the certified State Canvass. Legislative districts need precincts, and come from the results
site, under three conditions that keep anything uncertified out of the file:
  1. Which precincts a district has is read from the site's own legislative contests (the "Precinct Level" workbook
     of each State Senator and State Representative contest lists the precincts that voted in it; candidates' names
     in those workbooks are never kept).
  2. A district is given only if none of its precincts also voted in another district. Brown, Brookings, Hughes,
     Hyde, Potter, Sully, Yankton and other counties use vote centers (any voter of the county may vote at any of
     them), and some precincts elsewhere are split between districts; there the votes for President, Senator or
     Governor cannot be told apart by district, and the district is left out and named, never estimated.
  3. A district is given for a contest only if, in every county it reaches, the site's precincts add up to exactly
     the certified State Canvass row for that county, every column. So every figure given sits inside a county whose
     precinct record equals the certified one.
For 2022 the site's precinct rows are also compared, county by county, with the official county canvass PDF.

Not given: cities and towns (a South Dakota precinct is a number, a polling place or a vote center, and the results
do not say which city it is in); county commissioner districts, conservation, water and power districts, school
districts (the results do not name them); legislative districts for 2020 (the lines drawn in 2011).

The control
-----------
Nothing is written unless all of this holds: for every contest the State Canvass table has all 66 counties and each
column adds up to its own Total row; for President and U.S. Senator that Total equals the Clerk of the U.S. House of
Representatives' "Statistics of the ... Election" (clerk.house.gov, the South Dakota page, read from the PDF at each
run); for 2022 every county's row equals the Total row of the official county canvass (a second document; this is
the independent check for Governor, which the Clerk does not report; the Secretary's file has no pages for Yankton
County, and the output says so); the counties add up to the statewide total;
every site workbook's precincts add up to its own TOTALS rows and to its own County Level workbook; and every
precinct of the site is in at least one legislative district. The comparison of the site with the canvass is
recorded county by county; a difference there is not a failure (the canvass is the record), it only keeps
districts out.
The statewide figures this loader was checked against on 2026-10-02 are typed below (CHECKED); the loader says so
if a document reads differently later.
"""

import argparse
import collections
import datetime as dt
import html
import json
import os
import pathlib
import re
import sqlite3
import sys
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_place_votes as M  # noqa: E402  the shared small things: caching, fingerprints, the file writer
from ballot import nd_place_votes as N  # noqa: E402  the same results system: the visit, the workbook tables, the Clerk's page

Stop = M.Stop
METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "sd_local")
OUT = os.path.join(HERE, "ballot", "lean", "sd_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "46"
FEW = 20
SIDES = ("dem", "rep", "other", "total")
KEEP_DAYS = 3650               # certified results of past elections do not change; --refresh asks again

AGENCY = "South Dakota Secretary of State"
SITE = "https://electionresults.sd.gov/"
HISTORY = "https://sdsos.gov/elections-voting/election-resources/election-history/"
ASSETS = "https://sdsos.gov/elections-voting/assets/Archive/"
ELECTIONS = {
    2024: {"eid": "684", "date": "2024-11-05", "site_date": "11/5/2024", "link": "2024 General - Election Night Reporting",
           "history": HISTORY + "2024_Election_History.aspx",
           "canvass": {"path": "2024 Assets/Recount-Canvass-and-Canvass-Docs-General/2024GeneralElectionCanvassWithCert.pdf",
                       "title": "2024 General Election Canvass and Certificate"}},
    2022: {"eid": "471", "date": "2022-11-08", "site_date": "11/8/2022", "link": "2022 General - Election Night Reporting",
           "history": HISTORY + "2022_Election_History.aspx",
           "canvass": {"path": "2022 Assets/2022Generalcanvassreport.pdf", "title": "2022 General Election Official State Canvass Results"},
           "county_canvass": {"path": "2022 Assets/2022PrecintCanvass.pdf", "first_line": "General Election - November 8, 2022",
                              "title": "2022 General Election Official County Canvass Results (with precinct level results), PDF without certificates"}},
    2020: {"eid": "422", "date": "2020-11-03", "site_date": "11/3/2020", "link": "2020 General Election Unofficial Results",
           "history": HISTORY + "2020_Election_History.aspx",
           "canvass": {"path": "2020 Assests/2020GeneralStateCanvassFinal&Certificate.pdf", "title": "2020 General Election Official State Canvass Results"}},
}
DISTRICT_YEARS = (2022, 2024)  # the elections held on the legislative districts drawn in 2021
DISTRICTS = 35

# South Dakota's 66 counties and their FIPS codes (Oglala Lakota, once Shannon, is 46102; there is no 46113 or 46131).
_NAMES = ("Aurora 003|Beadle 005|Bennett 007|Bon Homme 009|Brookings 011|Brown 013|Brule 015|Buffalo 017|Butte 019|Campbell 021|Charles Mix 023|"
          "Clark 025|Clay 027|Codington 029|Corson 031|Custer 033|Davison 035|Day 037|Deuel 039|Dewey 041|Douglas 043|Edmunds 045|Fall River 047|"
          "Faulk 049|Grant 051|Gregory 053|Haakon 055|Hamlin 057|Hand 059|Hanson 061|Harding 063|Hughes 065|Hutchinson 067|Hyde 069|Jackson 071|"
          "Jerauld 073|Jones 075|Kingsbury 077|Lake 079|Lawrence 081|Lincoln 083|Lyman 085|McCook 087|McPherson 089|Marshall 091|Meade 093|"
          "Mellette 095|Miner 097|Minnehaha 099|Moody 101|Oglala Lakota 102|Pennington 103|Perkins 105|Potter 107|Roberts 109|Sanborn 111|"
          "Spink 115|Stanley 117|Sully 119|Todd 121|Tripp 123|Turner 125|Union 127|Walworth 129|Yankton 135|Ziebach 137")
FIPS = {x.rsplit(" ", 1)[0]: STATE_FIPS + x.rsplit(" ", 1)[1] for x in _NAMES.split("|")}
COUNTIES = list(FIPS)
PARTIES = {"DEM": "Democratic", "REP": "Republican", "LIB": "Libertarian", "IND": "independent"}
DEM_PARTY, REP_PARTY = "Democratic", "Republican"

# The contests. "heading" is the contest's title in the State Canvass, the county canvass and on the results site;
# "dem" and "rep" are surnames the canvass's own heading must carry, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States", "heading": "Presidential Electors",
     "dem": ("Harris", "Walz"), "rep": ("Trump", "Vance"), "clerk": "clerk-statistics-2024", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2022-us-senate", "year": 2022, "office": "United States Senator", "heading": "United States Senator",
     "dem": ("Bengs",), "rep": ("Thune",), "clerk": "clerk-statistics-2022", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "office": "Governor and Lieutenant Governor", "heading": "Governor and Lieutenant Governor",
     "dem": ("Smith", "Keintz"), "rep": ("Noem", "Rhoden"), "clerk": None, "section": None},
    {"id": "2020-president", "year": 2020, "office": "President and Vice President of the United States", "heading": "Presidential Electors",
     "dem": ("Biden", "Harris"), "rep": ("Trump", "Pence"), "clerk": "clerk-statistics-2020", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-us-senate", "year": 2020, "office": "United States Senator", "heading": "United States Senator",
     "dem": ("Ahlers",), "rep": ("Rounds",), "clerk": "clerk-statistics-2020", "section": "FOR UNITED STATES SENATOR"},
]

# The certified statewide totals this loader was checked against on 2026-10-02 (the State Canvass's Total rows).
CHECKED = {
    "2024-president": {"dem": 146859, "rep": 272081, "other": 9982, "total": 428922},
    "2022-us-senate": {"dem": 91007, "rep": 242316, "other": 14697, "total": 348020},
    "2022-governor": {"dem": 123148, "rep": 217035, "other": 9983, "total": 350166},
    "2020-president": {"dem": 150471, "rep": 261043, "other": 11095, "total": 422609},
    "2020-us-senate": {"dem": 143987, "rep": 276232, "other": 0, "total": 420219},
}
CLERK_DOCS = {k: dict(v) for k, v in N.OFFICIAL_DOCS.items()}

# The kinds of place: (kind, first election year given, covers the whole state, what it is, what its key is)
KINDS = [
    ("county", 2020, True, "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("senate", 2022, False, "Legislative districts (each elects one senator), where they can be added up from whole precincts",
     "district number, as the district of our Senate races"),
    ("house", 2022, False, "House districts (two representatives each; 26A, 26B, 28A and 28B one each), where they can be added up from whole precincts",
     "district number, with its letter where the district is divided, as the district of our House races"),
]
KIND_NAMES = [k[0] for k in KINDS]
REDRAWN = ("The 2020 election was held on the districts drawn in 2011; the districts drawn in 2021 were first used in 2022, so 2020 is not given.")

WHAT = ("How each South Dakota place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic ticket, "
        "the Republican ticket, everyone else together and the total. Counties are the rows of the State Canvass, the Board of Canvassers' "
        "certified record; legislative districts are added up from the Secretary of State's precinct results where those equal the canvass.")
NOTE = ("What this is: how the people of a place voted in that election. A county's figures are its row in the State Canvass, the record the "
        "State Board of Canvassers certified. A legislative district's figures (2022 and 2024, on the lines in force at that election) are its "
        "precincts added up from the Secretary of State's results site, and are given only where every precinct of the district voted in that "
        "district alone and where, in every county the district reaches, the precincts add up to exactly the certified canvass; in counties "
        "that use vote centers, and where a precinct is split between districts, a district cannot be added up and is left out, never "
        "estimated. What this is not: it is not a prediction of any election; it says nothing about any candidate on a later ballot or about "
        "any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where a district was drawn again, the "
        "figures are for the lines of that year. The tickets are named, as the canvass names them, only to say which election this was. In a "
        "place with very few voters the split would come close to saying how particular people voted; those contests are listed in the "
        "place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every other "
               "candidate on the ballot; South Dakota's results carry no write-in votes) and total. Minnesota's file calls the first count dfl. A "
               "contest a place does not have could not be added up on its lines: see the kind's note and coverage.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities and towns: a South Dakota precinct is a number, a polling place or a vote center, and the results do not say which city or "
             "town it is in. Legislative districts that take in a vote-center county (any voter of the county may vote at any center) or a "
             "precinct split between districts: the votes cannot be told apart by district. Legislative districts for 2020: other lines. County "
             "commissioner districts, conservation, water development and power districts, school districts: the results do not name them.")


def _clean(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def _key(name):
    return re.sub(r"[^a-z]", "", name.lower())


COUNTY_KEYS = {_key(c): c for c in COUNTIES}


# ---------------------------------------------------------------- the State Canvass and the county canvass (PDF text)

def _row(text):
    """'Bon Homme 697 16 2,236 43' -> ('Bon Homme', [697, 16, 2236, 43]); a line that does not end in numbers -> (text, [])."""
    parts, nums = text.split(), []
    while parts and re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", parts[-1]):
        nums.insert(0, int(parts.pop().replace(",", "")))
    return " ".join(parts), nums


def read_state_canvass(lines, heading):
    """One contest's table in the State Canvass: {"parties": [...], "header": text, "rows": {county: [votes]}, "total":
    [votes], "pages": [first, last]} from the PDF's lines (page, y, text). Stops unless the heading is found, the party
    line gives as many parties as there are columns, all 66 counties are there once, and every column adds up to the
    Total row. That arithmetic is what makes a scan's text layer safe to use."""
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == heading), None)
    if start is None:
        raise ValueError(f"no table headed '{heading}'")
    header, rows, total, last = [], {}, None, lines[start][0]
    for page, _y, t in lines[start + 1:]:
        name, nums = _row(t.strip())
        county = COUNTY_KEYS.get(_key(name)) if nums else None
        if county:
            if county in rows:
                raise ValueError(f"'{heading}': {county} appears twice before a Total row (the text layer may have lost the Total)")
            rows[county], last = nums, page
        elif nums and name == "Total":
            total, last = nums, page
            break
        elif not rows:
            header.append(t.strip())
    text = " ".join(header)
    parties = re.findall(r"\b(DEM|REP|LIB|IND)\b", text)
    if total is None:
        raise ValueError(f"'{heading}': no Total row")
    missing = [c for c in COUNTIES if c not in rows]
    if missing:
        raise ValueError(f"'{heading}': {len(missing)} counties could not be read ({', '.join(missing[:6])})")
    n = len(total)
    if len(parties) != n or parties.count("DEM") > 1 or parties.count("REP") != 1:
        raise ValueError(f"'{heading}': the heading names the parties {parties} for {n} columns")
    bad = [c for c in COUNTIES if len(rows[c]) != n]
    if bad:
        raise ValueError(f"'{heading}': {', '.join(bad[:6])} do not have {n} columns")
    sums = [sum(rows[c][i] for c in COUNTIES) for i in range(n)]
    if sums != total:
        raise ValueError(f"'{heading}': the county rows add up to {sums} and the Total row reads {total}")
    return {"parties": parties, "header": text, "rows": rows, "total": total, "pages": [lines[start][0], last]}


def read_county_canvass(lines, first_line, headings):
    """The official county canvass with precinct rows (a PDF of real text): {county: {heading: {"rows": [votes of each
    precinct], "total": [votes]}}} for the contests named; `headings` is {heading: number of columns}. Precinct names
    wrap over lines and can end in a number (Precinct 1, HS 2), so of each row only its last numbers, as many as the
    contest has columns, are kept; they are compared as a set of rows, and by their sum."""
    pages = collections.defaultdict(list)
    for page, _y, t in lines:
        pages[page].append(t.strip())
    out = collections.defaultdict(dict)
    for page in sorted(pages):
        ls = pages[page]
        if len(ls) < 4 or ls[0] != first_line or not ls[1].endswith(" County") or ls[2] not in headings:
            continue
        county = COUNTY_KEYS.get(_key(ls[1][:-7]))
        if county is None:
            raise ValueError(f"page {page}: '{ls[1]}' is not one of the 66 counties")
        table = out[county].setdefault(ls[2], {"rows": [], "total": None, "pages": []})
        table["pages"].append(page)
        n = headings[ls[2]]
        for name, nums in (_row(t) for t in ls[3:]):
            if name == "Total" and len(nums) == n:
                table["total"] = nums
            elif len(nums) >= n and name != "Total":
                table["rows"].append(nums[-n:])
    return {c: dict(v) for c, v in out.items()}


def canvass_contest(c, table):
    """Which canvass columns are the two tickets: stops unless the table's heading carries the surnames typed in CONTESTS."""
    parties = table["parties"]
    if parties.count("DEM") != 1:
        raise Stop(f"    {c['id']}: the canvass names {parties.count('DEM')} Democratic columns, not one; stopping")
    low = table["header"].lower()
    for side in ("dem", "rep"):
        if not all(s.lower() in low for s in c[side]):
            raise Stop(f"    {c['id']}: the canvass heading does not name the ticket this loader was checked against ({' and '.join(c[side])}); stopping")
    return parties.index("DEM"), parties.index("REP")


def _counties(names):
    """'Clay County' / 'Clay and Yankton Counties' / 'Aurora, Clay and Yankton Counties'."""
    names = list(names)
    return (names[0] + " County") if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]} Counties"


def pack(v, d, r):
    return [v[d], v[r], sum(v) - v[d] - v[r], sum(v)]


# ---------------------------------------------------------------- the results site

class Site(N.Site):
    def page(self, path, eid):
        url = SITE + path + ("&" if "?" in path else "?") + "eid=" + eid
        return url, self._open(url)[1].decode("utf-8", "replace")


def page_facts(page):
    find = lambda pat: _clean(html.unescape(re.sub(r"<[^>]+>", " ", (re.search(pat, page, re.S) or [None, ""])[1])))   # noqa: E731
    return {"date": find(r'id="hidElectionDate" value="([^"]*)"'), "precincts": find(r'id="hidPrecinctsReported" value="([^"]*)"'),
            "headed": "Unofficial Results" if re.search(r"<h1>\s*Unofficial Results\s*</h1>", page) else
                      "Official Results" if re.search(r"<h1>\s*Official Results\s*</h1>", page) else "",
            "election": find(r"<h1>\s*(?:Uno|O)fficial Results\s*</h1>\s*<h2>(.*?)</h2>")}


def page_contests(page):
    """[(heading, the Precinct Level button, the County Level button)] in page order."""
    heads = [(m.start(), _clean(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<span.*?</span>", "", m.group(1), flags=re.S)))))
             for m in re.finditer(r'<div class="display-results-box-a">\s*<h1>(.*?)</h1>', page, re.S)]
    buttons = [(m.start(), m.group(1), m.group(2)) for m in
               re.finditer(r'name="(ctl00\$MainContent\$rptRace\$ctl\d+\$ctl0\d)"[^>]*value="(Precinct Level|County Level)"', page)]
    out = []
    for i, (pos, name) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(page)
        mine = {kind: b for p, b, kind in buttons if pos < p < end}
        out.append((name, mine.get("Precinct Level"), mine.get("County Level")))
    return out


def book_path(cache, cid, kind):
    return os.path.join(cache, "results", f"{cid}_{kind}.xlsx")


def fetch_year(year, contests, cache, refresh, say, site):
    """The Precinct Level and County Level workbooks of one election's contests, and what the page says of the election."""
    mine = [c for c in contests if c["year"] == year]
    facts_path = os.path.join(cache, "results", f"{year}_page.json")
    paths = [book_path(cache, c["id"], k) for c in mine for k in ("precinct", "county")]
    have = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in paths + [facts_path])
    if have and all(M._fresh(p, refresh, KEEP_DAYS) for p in paths + [facts_path]):
        return M._load(facts_path)
    e = ELECTIONS[year]
    try:
        url, page = site().page("resultsSW.aspx?type=SWR&map=CTY", e["eid"])
        facts = dict(page_facts(page), url=url, fetched=M._now())
        if facts["date"] != e["site_date"]:
            raise OSError(f"the page is the election of {facts['date'] or 'no date'}, not {e['site_date']}")
        listed = page_contests(page)
        for c in mine:
            fits = [x for x in listed if x[0] == c["heading"]]
            if len(fits) != 1 or not fits[0][1] or not fits[0][2]:
                raise OSError(f"{len(fits)} contests headed '{c['heading']}' with both export buttons, not one")
            for kind, target in (("precinct", fits[0][1]), ("county", fits[0][2])):
                disposition, body = site().press(url, page, target=target)
                N._write(book_path(cache, c["id"], kind), N._workbook(body, disposition, f"{c['id']} {kind} export"))
            say(f"      {c['id']}: the site's precinct and county workbooks fetched")
        M._save(facts_path, facts)
        return facts
    except (OSError, ValueError) as err:
        if have:
            say(f"      {year} results site: could not be fetched again ({err}); using the copies of {M._day(paths[0])}")
            return M._load(facts_path)
        raise Stop(f"    {year} results site: could not be fetched ({err}) and no complete copy is on disk. Wait a few minutes and run this again.")


def book_precincts(data, what):
    """{county: [precinct names]} of a Precinct Level workbook: the names only."""
    out = {}
    for sheet, rows in N._sheets(data):
        _head, body, _totals = N._table(rows, "Precinct", f"{what}, sheet {sheet}")
        out[sheet] = [_clean(r[1]) for r in body]
    return out


def fetch_legislative(year, cache, refresh, say, site):
    """{"senate": {district: {county: [precinct names]}}, "house": {...}}: the precincts that voted in each legislative
    contest, from each contest's Precinct Level workbook. Only districts, counties and precinct names are kept."""
    path = os.path.join(cache, "results", f"{year}_legislative_precincts.json")
    if M._fresh(path, refresh, KEEP_DAYS):
        return M._load(path)
    try:
        url, page = site().page("resultsSW.aspx?type=LEG&map=DIST", ELECTIONS[year]["eid"])
        if page_facts(page)["date"] != ELECTIONS[year]["site_date"]:
            raise OSError("the legislative page is another election's")
        doc = {"url": url, "fetched": M._now(), "senate": {}, "house": {},
               "kept": "for each State Senator and State Representative contest: the district, and the counties and precinct names in its "
                       "Precinct Level workbook; no candidate's name and no legislative votes"}
        for heading, precinct, _county in page_contests(page):
            m = re.fullmatch(r"State (Senator|Representative) - District 0*(\d+[A-Za-z]?)", heading)
            if not m or not precinct:
                continue
            disposition, body = site().press(url, page, target=precinct)
            chamber = "senate" if m.group(1) == "Senator" else "house"
            doc[chamber][m.group(2).upper()] = book_precincts(N._workbook(body, disposition, heading), heading)
        if sorted(doc["senate"], key=int) != [str(i) for i in range(1, DISTRICTS + 1)]:
            raise OSError(f"the page lists {len(doc['senate'])} Senate contests, not the {DISTRICTS} districts")
        M._save(path, doc)
        say(f"      {year}: the precincts of {len(doc['senate'])} Senate and {len(doc['house'])} House contests read")
        return doc
    except (OSError, ValueError) as err:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      {year} legislative contests: could not be fetched again ({err}); using the extract of {M._day(path)}")
            return M._load(path)
        raise Stop(f"    {year} legislative contests: could not be fetched ({err}) and no extract is on disk. Wait a few minutes and run this again.")


def read_precinct_book(data, what):
    """{"says": [...], "candidates": [...], "counties": {county: [(precinct, [votes])]}}; every sheet's precincts must
    add up to its TOTALS row. A precinct name may appear twice in a county (two rooms of one hall), so rows keep their order."""
    out = {"says": None, "candidates": None, "counties": {}}
    for sheet, rows in N._sheets(data):
        head, body, totals = N._table(rows, "Precinct", f"{what}, sheet {sheet}")
        names = [_clean(x) for x in head[2:] if x is not None and _clean(x)]
        if out["candidates"] is None:
            out["says"], out["candidates"] = [_clean(r[0]) for r in rows[:3] if r and r[0]], names
        elif names != out["candidates"]:
            raise Stop(f"    {what}, sheet {sheet}: its candidate columns are not those of the first sheet; stopping")
        n = len(names)
        precincts = [(_clean(r[1]), N._votes(r[2:2 + n], f"{what}, sheet {sheet}, precinct {_clean(r[1])}")) for r in body]
        sums = [sum(v[i] for _p, v in precincts) for i in range(n)]
        if sums != N._votes(totals[2:2 + n], f"{what}, sheet {sheet}, TOTALS"):
            raise Stop(f"    {what}, sheet {sheet}: the precincts add up to {sums} and the sheet's TOTALS row is {totals[2:2 + n]}; stopping")
        if sheet not in FIPS:
            raise Stop(f"    {what}: the sheet '{sheet}' is not one of the 66 counties; stopping")
        out["counties"][sheet] = precincts
    return out


def read_county_book(data, what):
    """{"rows": {county: [votes]}, "totals": [votes], "vote_centers": [counties the workbook marks (Vote Center)]}."""
    sheets = list(N._sheets(data))
    if len(sheets) != 1:
        raise Stop(f"    {what}: {len(sheets)} sheets, not one; stopping")
    head, body, totals = N._table(sheets[0][1], "County", what)
    n = len([x for x in head[2:] if x is not None and _clean(x)])
    out = {"rows": {}, "totals": N._votes(totals[2:2 + n], f"{what}, TOTALS"), "vote_centers": [],
           "candidates": [_clean(x) for x in head[2:2 + n]]}
    for r in body:
        name = _clean(r[1])
        if name.endswith("(Vote Center)"):
            name = _clean(name[:-len("(Vote Center)")])
            out["vote_centers"].append(name)
        out["rows"][name] = N._votes(r[2:2 + n], f"{what}, {name}")
    return out


def site_table(c, pbook, cbook, canvass):
    """One contest as the results site has it, in the canvass's column order: stops unless the site has as many columns
    as the canvass, the two tickets' columns carry their surnames, the precincts add up to the site's own county rows,
    and each column's statewide sum is within one percent of the canvass's (so a column out of order is caught)."""
    n, (d, r) = len(canvass["total"]), canvass_contest(c, canvass)
    if len(pbook["candidates"]) != n:
        raise Stop(f"    {c['id']}: the results site has {len(pbook['candidates'])} columns and the canvass {n}; stopping")
    for side, at in (("dem", d), ("rep", r)):
        if not all(re.search(rf"\b{re.escape(s)}\b", pbook["candidates"][at]) for s in c[side]):
            raise Stop(f"    {c['id']}: the site's column {at + 1} is not headed with the ticket {' and '.join(c[side])}; stopping")
    if sorted(pbook["counties"]) != sorted(COUNTIES) or sorted(cbook["rows"]) != sorted(COUNTIES):
        raise Stop(f"    {c['id']}: the site's workbooks do not have the 66 counties; stopping")
    counties = {county: [sum(v[i] for _p, v in rows) for i in range(n)] for county, rows in pbook["counties"].items()}
    differ = [county for county in COUNTIES if counties[county] != cbook["rows"][county]]
    state = [sum(counties[county][i] for county in COUNTIES) for i in range(n)]
    if differ or state != cbook["totals"]:
        raise Stop(f"    {c['id']}: the site's precincts do not add up to its own County Level workbook ({', '.join(differ[:6]) or 'TOTALS'}); stopping")
    if any(abs(state[i] - canvass["total"][i]) > max(5, canvass["total"][i] // 100) for i in range(n)):
        raise Stop(f"    {c['id']}: the site's columns add up to {state} and the canvass's Total row is {canvass['total']}: not the same columns; stopping")
    mislabelled = [i + 1 for i, name in enumerate(cbook.get("candidates") or []) if name != pbook["candidates"][i]]
    return {"precincts": pbook["counties"], "counties": counties, "state": state, "says": pbook["says"], "vote_centers": sorted(cbook["vote_centers"]),
            "mislabelled_columns": mislabelled, "rows": sum(len(v) for v in pbook["counties"].values())}


# ---------------------------------------------------------------- adding up

def memberships(leg, precinct_names):
    """{chamber: {(county, precinct name): {districts}}} from the legislative extract; stops if a precinct of the
    statewide workbook voted in no Senate contest, or a legislative workbook names a precinct the statewide one lacks."""
    out = {}
    for chamber in ("senate", "house"):
        where = collections.defaultdict(set)
        for d, counties in leg[chamber].items():
            for county, names in counties.items():
                for name in names:
                    where[(county, name)].add(d)
        unknown = sorted(set(where) - precinct_names)
        missing = sorted(precinct_names - set(where))
        if unknown or missing:
            raise Stop(f"    {chamber} districts: {len(missing)} precincts voted in no {chamber} contest and {len(unknown)} are not in the statewide "
                       f"workbook ({(missing + unknown)[:4]}); stopping")
        out[chamber] = dict(where)
    return out


def tally(canvass, site, leg, contests):
    """(places, statewide, what the districts could and could not be given for)."""
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    state, cols = {}, {}
    for c in contests:
        d, r = canvass_contest(c, canvass[c["id"]])
        cols[c["id"]] = (d, r)
        state[c["id"]] = pack(canvass[c["id"]]["total"], d, r)
        for county in COUNTIES:
            votes["county"][FIPS[county]][c["id"]] = pack(canvass[c["id"]]["rows"][county], d, r)
    reach = {k: collections.defaultdict(dict) for k in ("senate", "house")}        # chamber -> district -> year -> counties
    left = {k: collections.defaultdict(dict) for k in ("senate", "house")}         # chamber -> district -> contest id or year -> why
    counts = {}
    for year in sorted(leg):
        mine = [c for c in contests if c["year"] == year]
        if not mine:
            continue
        first = site[mine[0]["id"]]
        keys = [(county, p) for county in COUNTIES for p, _v in first["precincts"][county]]
        for c in mine[1:]:
            if [(county, p) for county in COUNTIES for p, _v in site[c["id"]]["precincts"][county]] != keys:
                raise Stop(f"    {c['id']}: its precincts on the results site are not those of the other {year} contests; stopping")
        member = memberships(leg[year], set(keys))
        centers = set(first["vote_centers"])
        counts[str(year)] = {"precincts": len(keys), "vote_center_counties": sorted(centers)}
        for chamber in ("senate", "house"):
            districts = sorted({d for ds in member[chamber].values() for d in ds}, key=M.sort_key)
            shared = collections.defaultdict(set)
            for (county, _p), ds in member[chamber].items():
                for d in ds:
                    reach[chamber][d].setdefault(str(year), set()).add(county)
                    if len(ds) > 1:
                        shared[d].add(county)
            counts[str(year)][f"{chamber}_districts"] = len(districts)
            counts[str(year)][f"{chamber}_precincts_in_more_than_one_district"] = sum(1 for k in keys if len(member[chamber][k]) > 1)
            for d in districts:
                if shared[d]:
                    vc = sorted(shared[d] & centers)
                    other = sorted(shared[d] - centers)
                    left[chamber][d][str(year)] = ("; ".join(x for x in (
                        f"{_counties(vc)} use{'' if len(vc) > 1 else 's'} vote centers, where voters of several districts vote together" if vc else "",
                        f"in {_counties(other)} a precinct votes in more than one district" if other else "") if x))
                    continue
                for c in mine:
                    cid, (dd, rr) = c["id"], cols[c["id"]]
                    off = [county for county in sorted(reach[chamber][d][str(year)]) if site[cid]["counties"][county] != canvass[cid]["rows"][county]]
                    if off:
                        left[chamber][d][cid] = (f"in {_counties(off)} the results site's precincts do not add up to the certified canvass, "
                                                 "so its precinct figures there are not the certified ones")
                        continue
                    cur = [0, 0, 0, 0]
                    for county in reach[chamber][d][str(year)]:
                        for p, v in site[cid]["precincts"][county]:
                            if member[chamber][(county, p)] == {d}:
                                for i, x in enumerate(pack(v, dd, rr)):
                                    cur[i] += x
                    votes[chamber][d][cid] = cur
    order = [c["id"] for c in contests]
    packd = lambda d: {cid: dict(zip(SIDES, d[cid])) for cid in order if cid in d}                                      # noqa: E731

    def few(rec):
        hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
        if hold:
            rec["too_few"] = hold
        return rec
    places = {k: {} for k in KIND_NAMES}
    for county in COUNTIES:
        places["county"][FIPS[county]] = few({"name": f"{county} County", "votes": packd(votes["county"][FIPS[county]])})
    for chamber in ("senate", "house"):
        for d in sorted(votes[chamber], key=M.sort_key):
            rec = few({"name": ("Legislative District " if chamber == "senate" else "House District ") + d, "votes": packd(votes[chamber][d]),
                       "counties": {y: sorted(FIPS[c] for c in cs) for y, cs in sorted(reach[chamber][d].items())}})
            notes = []
            if len({tuple(x) for x in rec["counties"].values()}) > 1:
                notes.append("This district reaches different counties in the " + " and ".join(sorted(rec["counties"])) + " results; each year's "
                             "figures are for the precincts that voted in the district that year.")
            if left[chamber].get(d):
                rec["not_given"] = dict(sorted(left[chamber][d].items()))
                notes.append("Not given for " + "; ".join(f"{k}: {why}" for k, why in sorted(left[chamber][d].items())) + ".")
            if notes:
                rec["note"] = " ".join(notes)
            places[chamber][d] = rec
    not_given = {chamber: {d: dict(sorted(why.items())) for d, why in sorted(left[chamber].items(), key=lambda x: M.sort_key(x[0]))
                           if d not in places[chamber]} for chamber in ("senate", "house")}
    return places, state, {"counts": counts, "not_given": not_given}


def site_against_canvass(c, site, canvass):
    """County by county, the results site against the certified canvass, every column."""
    differ = {county: {"results_site": site["counties"][county], "canvass": canvass["rows"][county]}
              for county in COUNTIES if site["counties"][county] != canvass["rows"][county]}
    return {"compared": len(COUNTIES), "equal": len(COUNTIES) - len(differ), "differ": differ, "columns": [PARTIES[p] for p in canvass["parties"]],
            "statewide": {"results_site": site["state"], "canvass": canvass["total"]}}


def county_canvass_check(c, canvass, site, book):
    """2022 only: the official county canvass (a second document) against the State Canvass rows, and its precinct rows
    against the results site's, as sets of rows. Returns (record, failures)."""
    rows_equal, totals_equal, bad_total, bad_rows, absent, failed = 0, 0, [], [], [], []
    some = lambda rows: sorted(r for r in rows if any(r))                 # a precinct where nobody voted is a row of zeros on the site only  # noqa: E731
    for county in COUNTIES:
        t = (book.get(county) or {}).get(c["heading"])
        if not t:
            absent.append(county)
            continue
        if t["total"] is None:
            bad_total.append(county)
            continue
        if t["total"] == canvass["rows"][county] and [sum(r[i] for r in t["rows"]) for i in range(len(t["total"]))] == t["total"]:
            totals_equal += 1
        else:
            bad_total.append(county)
        if some(t["rows"]) == some(v for _p, v in site["precincts"][county]):
            rows_equal += 1
        else:
            bad_rows.append(county)
    if bad_total:
        failed.append(f"{c['id']}: the official county canvass does not equal the State Canvass row (or its own precincts) in {', '.join(bad_total[:8])}")
    return {"with": "the official county canvass with precinct level results (a PDF of text): each county's Total row and the sum of its precinct "
                    "rows against the State Canvass row; and its precinct rows against the results site's precinct rows, as a set of rows",
            "counties": len(COUNTIES), "counties_in_the_document": len(COUNTIES) - len(absent), "not_in_the_document": absent,
            "totals_equal_to_the_state_canvass": totals_equal, "totals_differ": bad_total,
            "precinct_rows_equal_to_the_results_site": rows_equal, "precinct_rows_differ": bad_rows}, failed


def control(canvass, site, places, state, clerk, contests, county_books, facts):
    failed, per = [], {}
    for c in contests:
        cid = c["id"]
        mine = dict(zip(SIDES, state[cid]))
        rec = {"state_canvass": mine, "source": f"sd-state-canvass-{c['year']}",
               "where": f"'{c['heading']}', pages {canvass[cid]['pages'][0]} to {canvass[cid]['pages'][1]} of the PDF: 66 county rows and the Total row",
               "counties_add_up_to_the_total_row": True,                       # read_state_canvass stops otherwise
               "results_site": site_against_canvass(c, site[cid], canvass[cid])}
        typed = CHECKED.get(cid)
        if typed and typed != mine:
            rec["typed_on_2026_10_02"] = typed
            failed.append(f"{cid}: the State Canvass now reads {mine}; this loader was checked against {typed}")
        off = clerk.get(cid)
        if off:
            theirs = {n: off[n] for n in SIDES}
            rec["official"] = theirs
            rec["equal"] = theirs == mine
            rec.update(second_source=off["source"], second_where=off["where"], read=off["read"])
            if theirs != mine:
                rec["difference"] = {n: mine[n] - theirs[n] for n in SIDES if mine[n] != theirs[n]}
                failed.append(f"{cid}: the State Canvass totals are {mine} and the Clerk of the House's are {theirs}")
        else:
            rec["official"], rec["equal"] = mine, True
            rec["second_source"] = "the official county canvass (see county_canvass)" if county_books.get(c["year"]) else None
        if county_books.get(c["year"]):
            rec["county_canvass"], bad = county_canvass_check(c, canvass[cid], site[cid], county_books[c["year"]])
            failed += bad
        elif not off:
            failed.append(f"{cid}: no second document to check the State Canvass against")
        sums = [sum(p["votes"][cid][x] for p in places["county"].values()) for x in SIDES]
        if sums != state[cid]:
            failed.append(f"{cid}: the counties add up to {sums} and the statewide total is {state[cid]}")
        per[cid] = rec
    for year, f in sorted(facts.items()):
        rows = {site[c["id"]]["rows"] for c in contests if c["year"] == year}
        if len(rows) != 1 or str(next(iter(rows))) != str(f.get("precincts")):
            failed.append(f"{year}: {sorted(rows)} precinct rows in the site's workbooks; its page says {f.get('precincts')}")
    if len(places["county"]) != len(COUNTIES):
        failed.append(f"{len(places['county'])} counties, not {len(COUNTIES)}")
    ctl = {"result": "equal" if not failed else "differs",
           "statement": ("For every contest the State Canvass has all 66 counties and each column adds up to its own Total row; for President and "
                         "U.S. Senator the Total equals the Clerk of the U.S. House's statistics; for 2022 every county's row equals the official "
                         "county canvass, for each county that document carries; the counties add up to the statewide total; and every legislative district given is added up from "
                         "precincts that voted in that district alone, in counties where the precincts add up to exactly the certified canvass."
                         if not failed else "The sums do not all agree; see the differences."),
           "precincts": {str(y): int(f.get("precincts") or 0) for y, f in sorted(facts.items())},
           "contests": per, "kinds": {"county": "equal" if not failed else "see the differences",
                                      "senate": "does not cover the state: only the districts that can be added up from whole precincts",
                                      "house": "does not cover the state: only the districts that can be added up from whole precincts"},
           "notes": ["The results site stays headed 'Unofficial Results' and its workbooks 'Unofficial General Election Results'. Where it is a "
                     "few votes off the certified canvass the difference is recorded under each contest's results_site; the canvass is the "
                     "record, and no district reaching such a county is given for that contest.",
                     "For Governor, 2022, the Clerk of the House reports nothing; the second document is the official county canvass, whose "
                     "Total rows are compared with the State Canvass county by county. The Secretary's file of county canvasses has no pages "
                     "for Yankton County (it runs from Walworth to Ziebach), so Yankton's 2022 rows are checked by the Total row's "
                     "arithmetic and, for U.S. Senator, by the Clerk's statewide total, not by a second document of their own.",
                     "The county canvasses of 2024 and 2020 are scans whose text layer misreads digits; they are not read."]}
    return ctl, failed


# ---------------------------------------------------------------- the official documents

def _pdf(url, path, refresh, say, latest=False):
    net.download(url, path, 0 if refresh else KEEP_DAYS, tries=3, say=say)
    from ballot import pdftext
    return pdf_lines(path) if latest else pdftext.lines(path)


def pdf_lines(path):
    """pdftext.lines for a PDF that was saved several times over (the 2022 county canvass grew from 1,023 to 1,420
    pages in five saves): each save packs newer copies of some objects, the page tree among them, into a later object
    stream, and the newest copy must win. pdftext keeps the first, which is right for the files it was written for."""
    from ballot import pdftext
    with open(path, "rb") as fh:
        data = fh.read()
    pdf = pdftext.PDF(data)
    direct = {int(m.group(1)) for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", data)}
    for num in list(pdf.raw):
        if b"/ObjStm" not in pdf.raw[num][:400]:
            continue
        d, s = pdf._obj(num)
        try:
            n, first = int(d["N"]), int(d["First"])
        except (KeyError, TypeError, ValueError):
            continue
        head = s[:first].split()
        for k in range(n):
            onum, off = int(head[2 * k]), int(head[2 * k + 1])
            nxt = int(head[2 * k + 3]) if k + 1 < n else len(s) - first
            if onum not in direct:
                pdf.raw[onum] = s[first + off:first + nxt]
    pdf.cache.clear()
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for y, rs in pdftext.rows(pdf, page, res):
            text = pdftext.join(rs)
            if text:
                out.append((n, round(y, 1), text))
    return out


def asset(path):
    return ASSETS + urllib.parse.quote(path)


def clerk_official(doc, section):
    """The Clerk's lines of one section as dem, rep, other, total: one line a party for the electors, "Name, Party" for
    a senator (the South Dakota page writes Democrat where North Dakota's writes Democratic-NPL)."""
    lines = doc["sections"].get(section) or []
    party = (lambda s: s) if section == "FOR PRESIDENTIAL ELECTORS" else (lambda s: s.rsplit(",", 1)[-1].strip())
    dem = [v for label, v in lines if party(label).startswith("Democrat")]
    rep = [v for label, v in lines if party(label) == "Republican"]
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{section}: {len(dem)} Democratic and {len(rep)} Republican lines, not one of each")
    total = sum(v for _label, v in lines)
    return {"dem": dem[0], "rep": rep[0], "other": total - dem[0] - rep[0], "total": total}


def clerk_totals(contests, cache, refresh, say):
    """({contest id: {dem, rep, other, total, source, where, read}}, the documents' records) from the Clerk's statistics."""
    out, recs = {}, []
    for sid in sorted({c["clerk"] for c in contests if c.get("clerk")}, reverse=True):
        src = CLERK_DOCS[sid]
        path = os.path.join(cache, src["file"])
        rec = {"id": sid, "kind": src["kind"], "agency": src["agency"], "title": src["title"], "url": src["url"]}
        try:
            net.download(src["url"], path, 0 if refresh else KEEP_DAYS, tries=3, say=say)
            parsed = N.read_clerk(path, state="SOUTH DAKOTA")
            rec.update(fetched=M._day(path), sha256=M._sha_file(path), where=parsed["where"].replace("North Dakota", "South Dakota"))
            for c in contests:
                if c.get("clerk") == sid:
                    out[c["id"]] = dict(clerk_official(parsed, c["section"]), source=sid, where=rec["where"], read=f"from the document on {rec['fetched']}")
        except Exception as e:  # noqa: BLE001  the control then has no second document for these contests, and stops
            say(f"      {src['title'][:60]}: could not be read ({e})")
            rec.update(unread=f"could not be read on {M._now()}: {e}")
        recs.append(rec)
    return out, recs


# ---------------------------------------------------------------- the file

def build(canvass, site, leg, clerk, county_books, facts, contests=CONTESTS, sources=None):
    places, state, districts = tally(canvass, site, leg, contests)
    ctl, failed = control(canvass, site, places, state, clerk, contests, county_books, facts)
    ctl["districts"] = districts["counts"]
    kinds = {}
    for kind, first, covers, what, key in KINDS:
        given = [c["id"] for c in contests if c["year"] >= first and any(c["id"] in p["votes"] for p in places[kind].values())]
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given, "covers_the_state": covers,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if first > min(c["year"] for c in contests):
            kinds[kind]["why_not_2020"] = REDRAWN
    lines = ("A district's precincts are those listed in the Precinct Level workbook of its own legislative contest on the Secretary's results "
             "site. A district is given only where none of its precincts also voted in another district, and only for a contest in which, in "
             "every county the district reaches, the site's precincts add up to exactly the certified State Canvass. The districts left out, "
             "and why, are under coverage. These files do not say which lines a later election uses.")
    kinds["senate"]["note"] = lines
    kinds["house"]["note"] = lines + (" A House district is the same ground as the Senate district of its number, except Districts 26 and 28, "
                                      "each divided into two single-member House districts (26A, 26B, 28A, 28B).")
    records = []
    for c in contests:
        t, (d, r) = canvass[c["id"]], canvass_contest(c, canvass[c["id"]])
        records.append({"id": c["id"], "date": ELECTIONS[c["year"]]["date"], "office": c["office"], "table": f"sd-state-canvass-{c['year']}",
                        "kinds": [k for k in KIND_NAMES if c["id"] in kinds[k]["contests"]],
                        "dem": {"party": DEM_PARTY, "ticket": " and ".join(c["dem"]), "column": f"column {d + 1} of the canvass table, headed DEM"},
                        "rep": {"party": REP_PARTY, "ticket": " and ".join(c["rep"]), "column": f"column {r + 1} of the canvass table, headed REP"},
                        "other": {"what": "every other candidate on the ballot, together; the results carry no write-in votes",
                                  "columns": [PARTIES[p] for i, p in enumerate(t["parties"]) if i not in (d, r)]},
                        "total": {"what": "the votes cast for candidates; the canvass tables give no under votes or over votes"},
                        "statewide": dict(zip(SIDES, state[c["id"]])),
                        "official_source": f"sd-state-canvass-{c['year']}"})
    doc = {"what": WHAT, "note": NOTE, "state": "SD", "generated": M._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(SIDES), "too_few": {"fewer_than": FEW, "why": TOO_FEW},
           "contests": records, "kinds": kinds, "control": ctl,
           "coverage": {"not_given": NOT_GIVEN, "districts_not_given": districts["not_given"]},
           "sources": sources or [], "places": places}
    return doc, failed


def our_places(db):
    """{kind: ids} of our South Dakota places and races, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'sd-%' AND kind IN ('county', 'mcd')"):
            out[kind].add(pid)
        for office, d in con.execute("SELECT office_kind, district FROM sl_races WHERE state = 'SD' AND office_kind IN ('state_senate', 'state_house')"):
            out["senate" if office == "state_senate" else "house"].add(str(d))
        for jid, in con.execute("SELECT DISTINCT jurisdiction_id FROM sl_races WHERE state = 'SD' AND level = 'county'"):
            out["county"].add(str(jid))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    South Dakota place votes: the State Canvass (counties) and the Secretary of State's precinct results (legislative districts)")
    net.patient_lookups()
    os.makedirs(os.path.join(cache, "results"), exist_ok=True)
    years = sorted({c["year"] for c in CONTESTS}, reverse=True)
    canvass, sources = {}, []
    for year in years:
        e = ELECTIONS[year]["canvass"]
        path = os.path.join(cache, f"sd_state_canvass_{year}.pdf")
        try:
            lines = _pdf(asset(e["path"]), path, refresh, say)
            for c in CONTESTS:
                if c["year"] == year:
                    canvass[c["id"]] = read_state_canvass(lines, c["heading"])
        except (OSError, ValueError) as err:
            raise Stop(f"    {year} State Canvass: could not be read ({err}); nothing was written. If it could not be fetched, wait and run this again.")
        sources.append({"id": f"sd-state-canvass-{year}", "kind": "certified statewide canvass, one row a county (a scan with a text layer)",
                        "agency": "South Dakota State Board of Canvassers; published by the " + AGENCY, "title": e["title"], "url": asset(e["path"]),
                        "linked_from": ELECTIONS[year]["history"], "fetched": M._day(path), "sha256": M._sha_file(path),
                        "read": "For each contest named here: the party line of the table's heading, the 66 county rows and the Total row. Used "
                                "only because every column of the county rows adds up to the Total row printed in the document."})
    visit = []

    def site_visit():                                                      # one visit, begun only if something must be fetched
        if not visit:
            visit.append(Site())
        return visit[0]
    facts = {year: fetch_year(year, CONTESTS, cache, refresh, say, site_visit) for year in years}
    site, files = {}, {}
    for c in CONTESTS:
        raw = {}
        for kind in ("precinct", "county"):
            with open(book_path(cache, c["id"], kind), "rb") as fh:
                raw[kind] = fh.read()
        site[c["id"]] = site_table(c, read_precinct_book(raw["precinct"], f"{c['id']} precinct workbook"),
                                   read_county_book(raw["county"], f"{c['id']} county workbook"), canvass[c["id"]])
        files[c["id"]] = {kind: {"file": os.path.basename(book_path(cache, c["id"], kind)), "sha256": M._sha(data),
                                 "fetched": M._day(book_path(cache, c["id"], kind))} for kind, data in raw.items()}
    leg = {year: fetch_legislative(year, cache, refresh, say, site_visit) for year in DISTRICT_YEARS}
    for year in years:
        f, mine = facts[year], [c for c in CONTESTS if c["year"] == year]
        say(f"      {year}: {f.get('precincts')} precincts on the results site ({f.get('headed')}; {f.get('election')}; copy of {f.get('fetched')})")
        sources.append({"id": f"sd-sos-results-site-{year}", "kind": "results by precinct, headed Unofficial by the site (used for legislative "
                                                                     "districts only, and only where it equals the certified canvass)",
                        "agency": AGENCY, "title": f"{f.get('election')}: the Precinct Level and County Level exports of "
                                                   f"{', '.join(c['heading'] for c in mine)}" + ("; the Precinct Level exports of the legislative "
                                                                                                "contests (precinct names only)" if year in leg else ""),
                        "url": f.get("url"), "linked_from": ELECTIONS[year]["history"], "linked_as": ELECTIONS[year]["link"],
                        "the_page_says": {"headed": f.get("headed"), "election": f.get("election"), "precincts": f.get("precincts")},
                        "the_workbooks_say": sorted({s for c in mine for s in site[c["id"]]["says"]}),
                        "vote_center_counties": site[mine[0]["id"]]["vote_centers"],
                        "column_headings_wrong": {c["id"]: f"column{'s' if len(site[c['id']]['mislabelled_columns']) > 1 else ''} "
                                                           f"{' and '.join(map(str, site[c['id']]['mislabelled_columns']))} of the County Level "
                                                           "workbook are not headed as in the Precinct Level workbook (a ticket's names stand "
                                                           "over another column's votes); the votes agree, and columns are taken in the "
                                                           "canvass's order, never by a heading alone"
                                                  for c in mine if site[c["id"]]["mislabelled_columns"]} or None,
                        "fetched": f.get("fetched"), "tables": {c["id"]: {"files": files[c["id"]]} for c in mine},
                        "legislative_extract": ({"url": leg[year].get("url"), "fetched": leg[year].get("fetched"), "kept": leg[year].get("kept")}
                                                if year in leg else None),
                        "read": "Of each precinct: its county (the sheet), its name, and each column's votes. Of the legislative contests: "
                                "which precincts are listed. Only the two tickets are named."})
    county_books = {}
    for year in years:
        e = ELECTIONS[year].get("county_canvass")
        if not e:
            continue
        path = os.path.join(cache, f"sd_county_canvass_{year}.pdf")
        try:
            lines = _pdf(asset(e["path"]), path, refresh, say, latest=True)
            county_books[year] = read_county_canvass(lines, e["first_line"], {c["heading"]: len(canvass[c["id"]]["total"]) for c in CONTESTS if c["year"] == year})
            sources.append({"id": f"sd-county-canvass-{year}", "kind": "official county canvasses with precinct level results (a PDF of text); a check only",
                            "agency": "the county boards of canvassers; published by the " + AGENCY, "title": e["title"], "url": asset(e["path"]),
                            "linked_from": ELECTIONS[year]["history"], "fetched": M._day(path), "sha256": M._sha_file(path),
                            "read": "For the contests named here: each county's precinct rows (numbers only) and its Total row."})
        except (OSError, ValueError) as err:
            say(f"      {year} county canvass: could not be read ({err})")
    say("    the second documents: Clerk of the U.S. House (President and U.S. Senator); the official county canvass (2022)")
    clerk, clerk_recs = clerk_totals(CONTESTS, cache, refresh, say)
    doc, failed = build(canvass, site, leg, clerk, county_books, facts, sources=sources + clerk_recs)

    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties (the State Canvass); {len(p['senate'])} Senate and {len(p['house'])} House districts from whole "
        f"precincts (2022 and 2024); {len(doc['coverage']['districts_not_given']['senate'])} Senate districts cannot be added up")
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        rs = ctl["results_site"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + (f"{'equal to' if ctl['equal'] else 'DIFFERS from'} {ctl['second_source']} ({ctl.get('second_where')})" if ctl.get("second_where")
               else "the Clerk reports no Governor")
            + (f"; county canvass: {ctl['county_canvass']['totals_equal_to_the_state_canvass']} of the {ctl['county_canvass']['counties_in_the_document']} "
               f"counties in the document equal" + (f" (it has no pages for {', '.join(ctl['county_canvass']['not_in_the_document'])})"
                                                    if ctl['county_canvass']['not_in_the_document'] else "")
               + f", precinct rows equal to the results site in {ctl['county_canvass']['precinct_rows_equal_to_the_results_site']}"
               if ctl.get("county_canvass") else "")
            + f"; results site equal to the canvass in {rs['equal']} of 66 counties" + (f" (not {', '.join(rs['differ'])})" if rs["differ"] else ""))
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    South Dakota place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES + ["mcd"]:
            ids = ours.get(kind, set())
            without = sorted((i for i in ids if not p.get(kind, {}).get(i, {}).get("votes")), key=M.sort_key)
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}" + (f" (none for {', '.join(without[:40])})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {M._now()}")
    M.write(out, doc)
    say(f"    South Dakota place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.2f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic and the readers on made-up tables

def selftest(say=print):
    checks = []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))

    def stops(make):
        try:
            make()
            return False
        except (Stop, ValueError):
            return True
    check("a canvass row is a name and its numbers", _row("Bon Homme 697 16 2,236 43"), ("Bon Homme", [697, 16, 2236, 43]))
    check("a misread digit is not a number", _row("Aurora 302 5 1,O56 30"), ("Aurora 302 5 1,O56", [30]))
    check("county codes", (FIPS["Aurora"], FIPS["Oglala Lakota"], FIPS["Pennington"], FIPS["Ziebach"], len(FIPS)), ("46003", "46102", "46103", "46137", 66))
    # a made-up canvass: every county 10 Democratic, 3 Libertarian, 20 Republican, except three
    rows = {c: [10, 3, 20] for c in COUNTIES}
    rows.update({"Aurora": [30, 1, 10], "Beadle": [5, 0, 5], "Brown": [100, 9, 120]})
    total = [sum(v[i] for v in rows.values()) for i in range(3)]

    def lines(rows=rows, total=total, heading="Governor"):
        out = [(2, 700, heading), (2, 690, "County"), (2, 680, "Ash and Birch - DEM Cedar and Dogwood - LIB Elm and Fir - REP")]
        out += [(2 if i < 40 else 3, 600 - i, f"{c} " + " ".join(f"{x:,}" for x in rows[c])) for i, c in enumerate(COUNTIES)]
        return out + [(3, 10, "Total " + " ".join(f"{x:,}" for x in total)), (4, 700, "Next Contest")]
    c = {"id": "2022-governor", "year": 2022, "office": "Governor", "heading": "Governor", "dem": ("Ash", "Birch"), "rep": ("Elm", "Fir"), "clerk": None}
    t = read_state_canvass(lines(), "Governor")
    check("the canvass table is read with its parties and pages", (t["parties"], t["rows"]["Brown"], t["total"] == total, t["pages"]),
          (["DEM", "LIB", "REP"], [100, 9, 120], True, [2, 3]))
    check("a canvass whose rows do not add up to its Total row is refused", stops(lambda: read_state_canvass(lines(total=[total[0] + 1] + total[1:]), "Governor")), True)
    check("a canvass with a county missing is refused", stops(lambda: read_state_canvass([x for x in lines() if not x[2].startswith("Hyde ")], "Governor")), True)
    check("a ticket other than the one typed in stops the loader", stops(lambda: canvass_contest(dict(c, dem=("Walnut",)), t)), True)
    check("counties are named in plain words", (_counties(["Clay"]), _counties(["Clay", "Yankton"]), _counties(["A", "B", "C"])),
          ("Clay County", "Clay and Yankton Counties", "A, B and C Counties"))
    # a made-up results site: Aurora two precincts in District 1; Beadle one precinct split between Districts 1 and 2;
    # Brown a vote-center county in District 3, one vote short of the canvass; every other county one precinct in District 4
    precincts = {county: [("P1", list(rows[county]))] for county in COUNTIES}
    precincts["Aurora"] = [("P1", [20, 1, 4]), ("P2", [10, 0, 6])]
    precincts["Brown"] = [("Hall", [99, 9, 120])]
    counties = {county: [sum(v[i] for _p, v in ps) for i in range(3)] for county, ps in precincts.items()}
    site = {"2022-governor": {"precincts": precincts, "counties": counties, "state": [sum(v[i] for v in counties.values()) for i in range(3)],
                              "says": ["made up"], "vote_centers": ["Brown"], "mislabelled_columns": [], "rows": sum(len(v) for v in precincts.values())}}
    rest = {county: ["P1"] for county in COUNTIES if county not in ("Aurora", "Beadle", "Brown")}
    leg = {2022: {"senate": {"1": {"Aurora": ["P1", "P2"], "Beadle": ["P1"]}, "2": {"Beadle": ["P1"]}, "3": {"Brown": ["Hall"]}, "4": rest},
                  "house": {"1": {"Aurora": ["P1", "P2"], "Beadle": ["P1"]}, "2": {"Beadle": ["P1"]}, "3": {"Brown": ["Hall"]},
                            "4A": {k: v for k, v in rest.items() if k < "M"}, "4B": {k: v for k, v in rest.items() if k >= "M"}}}}
    canvass = {"2022-governor": t}
    places, state, districts = tally(canvass, site, leg, [c])
    check("a county is its canvass row", places["county"]["46003"]["votes"]["2022-governor"], {"dem": 30, "rep": 10, "other": 1, "total": 41})
    check("the statewide total is the Total row", state["2022-governor"], [total[0], total[2], total[1], sum(total)])
    check("a district of whole precincts in counties equal to the canvass is added up", places["senate"]["4"]["votes"]["2022-governor"],
          {"dem": 630, "rep": 1260, "other": 189, "total": 2079})
    check("a district with a precinct shared with another district is left out, both of them",
          sorted(d for d in ("1", "2") if d in places["senate"]), [])
    check("and the reason is kept", "votes in more than one district" in districts["not_given"]["senate"]["1"]["2022"], True)
    check("a district in a county where the site is off the canvass is left out for that contest",
          ("3" in places["senate"], "do not add up to the certified canvass" in districts["not_given"]["senate"]["3"]["2022-governor"]), (False, True))
    check("a divided House district is given by its halves", sorted(places["house"]), ["4A", "4B"])
    check("and the halves add up to the whole", [places["house"]["4A"]["votes"]["2022-governor"][k] + places["house"]["4B"]["votes"]["2022-governor"][k]
                                                 for k in SIDES], [630, 1260, 189, 2079])
    check("a precinct in no district stops the loader",
          stops(lambda: tally(canvass, site, {2022: dict(leg[2022], senate={k: v for k, v in leg[2022]["senate"].items() if k != "3"})}, [c])), True)
    book = {county: {"Governor": {"rows": [v for _p, v in ps], "total": list(rows[county])}} for county, ps in precincts.items()}
    rec, bad = county_canvass_check(c, t, site["2022-governor"], book)
    check("the county canvass check finds the county whose precinct rows are not the certified ones",
          (rec["totals_equal_to_the_state_canvass"], rec["totals_differ"], rec["precinct_rows_equal_to_the_results_site"], len(bad)), (65, ["Brown"], 66, 1))
    rec, bad = county_canvass_check(c, t, site["2022-governor"], {k: v for k, v in book.items() if k not in ("Brown", "Yankton")})
    check("a county the document does not carry is said, and is not a failure", (rec["not_in_the_document"], bad), (["Brown", "Yankton"], []))
    ctl, failed = control(canvass, site, places, state, {}, [c], {2022: dict(book, Brown={"Governor": {"rows": [[100, 9, 120]], "total": [100, 9, 120]}})},
                          {2022: {"precincts": str(site["2022-governor"]["rows"])}})
    check("the control holds on the made-up tables, and records where the site is off the canvass",
          ([f for f in failed if "checked against" not in f], list(ctl["contests"]["2022-governor"]["results_site"]["differ"])), ([], ["Brown"]))
    wrong = {"2022-governor": dict(dict(zip(SIDES, state["2022-governor"])), dem=1, source="x", where="-", read="-")}
    check("a second document with another total is caught",
          any("Clerk" in f for f in control(canvass, site, places, state, wrong, [c], {}, {2022: {"precincts": str(site["2022-governor"]["rows"])}})[1]), True)
    cc = read_county_canvass([(1, 9, "General Election - X"), (1, 8, "Aurora County"), (1, 7, "Governor"), (1, 6, "Precinct Name DEM REP"),
                              (1, 5, "Courthouse Community"), (1, 4, "20 1 4"), (1, 3, "Room"), (1, 2, "Precinct-2 10 0 6"), (1, 1, "Total 30 1 10"),
                              (1, 0, "1 of 21"), (2, 9, "General Election - X"), (2, 8, "Beadle County"), (2, 7, "Governor"), (2, 6, "Precinct 1 5 0 5"),
                              (2, 5, "Total 5 0 5")], "General Election - X", {"Governor": 3})
    check("the county canvass keeps a wrapped precinct's numbers and the Total row", cc["Aurora"]["Governor"]["rows"] + [cc["Aurora"]["Governor"]["total"]],
          [[20, 1, 4], [10, 0, 6], [30, 1, 10]])
    check("and a precinct whose name ends in a number", cc["Beadle"]["Governor"]["rows"], [[5, 0, 5]])
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each South Dakota place voted in past partisan general elections -> ballot/lean/sd_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/sd_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/sd_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every workbook and document again, even when copies are on disk")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic and the readers on made-up tables; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
