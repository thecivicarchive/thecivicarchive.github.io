"""
ballot/mo_place_votes.py - how each Missouri place voted in past partisan general elections, added up from the
Secretary of State's official results, so a page can show the record of a county or a legislative district without
anyone labelling a candidate. Missouri's twin of ballot/mn_place_votes.py; the file it writes has the same shape (the
Democratic count is "dem" here, as in Ohio's, Iowa's and Wisconsin's files, where Minnesota's is "dfl").

    python ballot/mo_place_votes.py               reads (or downloads) the documents, writes ballot/lean/mo_place_votes.json
    python ballot/mo_place_votes.py --refresh     asks for every document again even when the cached copies are fresh
    python ballot/mo_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/mo_place_votes.py --selftest    the reader and the arithmetic on made-up lines; downloads nothing

What it is, and is not
----------------------
For President, U.S. Senator and Governor in 2024, U.S. Senator in 2022, and President and Governor in 2020 (Missouri
elects its Governor in presidential years, so there is no Governor's race of 2022): the votes for the Democratic
ticket, the Republican ticket, everyone else together (write-ins included) and the total, for every county and the City
of St. Louis, and, for the 2022 and 2024 contests, for each state Senate and House district that is made of whole
counties. It is how the people of a place voted then. It is not a prediction, it says nothing about any candidate on a
later ballot or about any voter, and it turns no nonpartisan office into a partisan one. No database is opened for
writing; ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Why counties, and not precincts
-------------------------------
Missouri does not publish its results precinct by precinct. The Secretary of State's results page says so in these
words: "Precinct-level election results are available for general (November) elections from 1996 to 2024. To purchase
precinct data files ... please contact the Elections Division". Buying a file is John's step, not this loader's, and
compilations made by others from the 116 election authorities' own reports are not official records. So this loader
reads what the Secretary publishes freely: "Results by County" (a PDF headed OFFICIAL RESULTS, one row for each of
the 116 election authorities, for every contest) and "Grand Totals" (the returns as announced by the Board of State
Canvassers). If John buys the precinct files, a reader for them belongs here, and cities and every district follow.

  - A county is an election authority's row, with one exception: Jackson County has two authorities, the Kansas City
    Board of Election Commissioners (the part of Kansas City in Jackson County) and the Jackson County Board (the rest
    of the county). The county's figures are the two rows together, and the county's record gives each part. The parts
    of Kansas City in Clay, Platte and Cass counties are counted by those counties and cannot be told apart, so Kansas
    City as a whole is not given. The City of St. Louis is no part of any county: it is filed as a county (29510), as
    our places file it, and once more as the city it is.
  - A legislative district is given only when it is made of whole counties: then its votes are its counties' votes,
    exactly. Which counties a district has is read two ways that must agree: from the results themselves (the "State
    Senator, District N" and "State Representative, District N" contests list the authorities that voted in them) and
    from the Census Bureau's 2024 block equivalency files (every census block's district). A district that shares a
    county with another district is NOT given, and is listed: nothing is shared out or estimated.
  - Districts are given for the 2022 and 2024 contests: both elections were held on the plans drawn in 2022, which are
    the plans our 2026 races are on (the House contests of the two years must list the same counties, or the loader
    stops). 2020 was held on the plans of 2012, so 2020 is given for counties only.
  - Not given: cities, towns and townships (other than the City of St. Louis), wards, judicial circuits' own sums
    (a circuit is whole counties; a page can add them from the counties), school and other districts.
  - Of candidates only the two tickets' surnames are kept, to say which election this was; they must be the surnames
    typed in CONTESTS under the party the documents give, or the loader stops.

The control
-----------
Nothing is written unless all of this holds: every column (each candidate's, and the Total column's own sum of
candidates) adds up to the Total row printed under it; all 116 authorities are there for every contest; the counties
add up to the statewide sum; the statewide sums equal the Grand Totals, party by party (Republican, Democratic, the rest, the
total); and every district given has the same whole counties in the results and in the Census Bureau's files. For
President and U.S. Senator the Republican and Democratic sums are also compared with the Clerk of the U.S. House's
"Statistics of the ... Election" (a second control: if a Clerk's document cannot be read the file says so and the
first control stands). The 2020 Grand Totals document is headed "Unofficial Election Returns" (printed 01/26/2021,
after the canvass), while the 2020 Results by County are headed OFFICIAL RESULTS; the two agree, and the file says
which heading each carries.

A place's total here is its candidates added up, not the Total cell printed at the end of its row. The two are
compared, and a row where they differ is listed in the file (control, printed_row_totals_that_differ), never changed:
in the 2022 Results by County, Cole County's row for U.S. Senator prints a Total of 28,532 beside candidates who add up
to 28,538 (six write-in votes for one candidate are in their column, in the Total row and in the Grand Totals, but
not in the row's Total cell). The figures this loader was checked against on 2026-10-02 are typed below (CHECKED).
"""

import argparse
import collections
import datetime as dt
import glob
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
CACHE = os.path.join(HERE, "states_cache", "mo_local")
OUT = os.path.join(HERE, "ballot", "lean", "mo_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
MAX_AGE_DAYS = 3650            # certified results of past elections do not change; --refresh asks again
STATE_FIPS = "29"
FEW = 20
AUTHORITIES = 116              # 114 counties, the City of St. Louis, and Kansas City's board
JACKSON, STL_CITY, STL_CITY_PLACE = "29095", "29510", "MO-M-65000"
KC = "Kansas City"
PLAN_YEAR = 2022               # the legislative plans our 2026 races are on were first used in 2022
SEATS = {"senate": 34, "house": 163}

SOS = "https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/"
SOS_PAGE = "https://www.sos.mo.gov/elections/results"
AGENCY = "Missouri Secretary of State, Elections Division"
DOCS = {
    2024: {"county": "ActualResults-November52024.pdf", "canvass": "2024GeneralElection.pdf", "date": "2024-11-05",
           "title": "General Election, November 5, 2024"},
    2022: {"county": "ActualResults-November82022.pdf", "canvass": "2022GeneralElection.pdf", "date": "2022-11-08",
           "title": "General Election, November 8, 2022"},
    2020: {"county": "ActualResults-November32020.pdf", "canvass": "November3_2020GeneralElection.pdf", "date": "2020-11-03",
           "title": "General Election, November 3, 2020"},
}
CENSUS = "https://www2.census.gov/"
COUNTY_LIST = (CENSUS + "geo/docs/reference/codes2020/cou/st29_mo_cou2020.txt", "st29_mo_cou2020.txt")
BEF = {"house": ("sldl24.zip", "SLDL24", CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip"),
       "senate": ("sldu24.zip", "SLDU24", CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip")}
CLERK = {y: {"id": f"clerk-statistics-{y}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
             "title": f"Statistics of the {'Presidential and ' if y % 4 == 0 else ''}Congressional Election from Official Sources, {y}",
             "url": f"https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf", "file": f"clerk_statistics{y}.pdf"}
         for y in (2024, 2022, 2020)}

# The contests. "labels" are the office as the Results by County heads it; "canvass" as the Grand Totals head it; "dem"
# and "rep" are the tickets' surnames, which both documents must give under those parties, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States", "labels": ["U.S. President"],
     "canvass": "U.S. President and Vice President", "dem": "Harris/Walz", "rep": "Trump/Vance", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2024-us-senate", "year": 2024, "office": "United States Senator", "labels": ["U.S. Senator", "United States Senator"],
     "canvass": "U.S. Senator", "dem": "Kunce", "rep": "Hawley", "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2024-governor", "year": 2024, "office": "Governor", "labels": ["Governor"], "canvass": "Governor", "dem": "Quade", "rep": "Kehoe"},
    {"id": "2022-us-senate", "year": 2022, "office": "United States Senator", "labels": ["U.S. Senator", "United States Senator"],
     "canvass": "U.S. Senator", "dem": "Valentine", "rep": "Schmitt", "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2020-president", "year": 2020, "office": "President and Vice President of the United States", "labels": ["U.S. President"],
     "canvass": "President & Vice President", "dem": "Biden/Harris", "rep": "Trump/Pence", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-governor", "year": 2020, "office": "Governor", "labels": ["Governor"], "canvass": "Governor", "dem": "Galloway", "rep": "Parson"},
]

# The Grand Totals this loader was checked against on 2026-10-02; they stand in, and the file says so, only when a
# Grand Totals document cannot be read again.
CHECKED = {
    "2024-president": {"dem": 1200599, "rep": 1751986, "other": 42742, "total": 2995327},
    "2024-us-senate": {"dem": 1243728, "rep": 1651907, "other": 76924, "total": 2972559},
    "2024-governor": {"dem": 1146173, "rep": 1750802, "other": 63291, "total": 2960266},
    "2022-us-senate": {"dem": 872694, "rep": 1146966, "other": 49470, "total": 2069130},
    "2020-president": {"dem": 1253014, "rep": 1718736, "other": 54212, "total": 3025962},
    "2020-governor": {"dem": 1225771, "rep": 1720202, "other": 66314, "total": 3012287},
}

KINDS = [   # (kind, first election year given, covers the whole state, what it is, what its key is)
    ("county", 2020, True, "Counties and the City of St. Louis",
     "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races (the City of St. Louis is 29510)"),
    ("mcd", 2020, False, "The City of St. Louis, the one city that is no part of any county", "MO-M- and the five-digit Census place code, as sl_places kind mcd"),
    ("senate", PLAN_YEAR, False, "State Senate districts of the 2022 plan, where made of whole counties", "district number, as the district of our Senate races"),
    ("house", PLAN_YEAR, False, "State House districts of the 2022 plan, where made of whole counties", "district number, as the district of our House races"),
]
KIND_NAMES = [k[0] for k in KINDS]
VOTE_KEYS = ("dem", "rep", "other", "total")

WHAT = ("How each Missouri county, and each legislative district made of whole counties, voted in six contests of the 2020, 2022 and 2024 general "
        "elections: the votes for the Democratic ticket, the Republican ticket, everyone else together (write-ins included) and the total, from "
        "the Missouri Secretary of State's official results by county.")
NOTE = ("What this is: how the people of a place voted in that election, in the Secretary of State's official results by county, as the Board "
        "of State Canvassers announced them, given here for each county and the City of St. Louis and added up for each legislative district "
        "that is made of whole counties. What this is not: it is not a prediction of any election; it says nothing about any candidate on a "
        "later ballot or about any voter; a nonpartisan office stays nonpartisan; and it is not the record of a city, a ward or a district that "
        "shares a county with another: Missouri sells its results by voting place and does not publish them, so those places are not given and "
        "nothing is estimated for them. The tickets are named, as the Secretary's own documents name them, only to say which election this was. "
        "In a place with very few voters the split would come close to saying how particular people voted; those contests are listed in the "
        "place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every other "
               "candidate and all write-ins) and total. A contest a place does not have was held on other district lines.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities, towns, townships and wards (other than the City of St. Louis), Kansas City as a whole, and every legislative district "
             "that shares a county with another district: the Secretary of State publishes results by county only and sells the results by "
             "voting place, so these cannot be added up from a published official record, and nothing is estimated.")
WHY_NOT_2020 = "The 2020 election was held on the district plans of 2012; the plans drawn in 2022 are the ones our 2026 races are on, so 2020 is not given."


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


def bare(name):
    """A name for comparing only: lower case, letters alone ('De Kalb' and 'DeKalb' are one)."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def sort_key(key):
    return [int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", key)]


def has_ticket(text, ticket):
    return all(re.search(rf"\b{re.escape(s)}\b", text) for s in ticket.split("/"))


def fetch(url, path, refresh, say):
    try:
        net.download(url, path, 0 if refresh else MAX_AGE_DAYS, tries=3, say=say)
    except Exception as e:  # noqa: BLE001
        raise Stop(f"    {os.path.basename(path)} could not be fetched ({e}) and no copy is on disk. Wait a few minutes and run this again.")
    return path


# ---------------------------------------------------------------- the counties and the election authorities

def read_counties(path):
    """{bare name as the Results by County write it: (FIPS, name)} from the Census Bureau's county list, and the
    authorities' map: each county under its name without 'County', the City of St. Louis as 'St. Louis City'."""
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        head = fh.readline().strip().split("|")
        for line in fh:
            r = dict(zip(head, line.rstrip("\n").split("|")))
            if r.get("STATEFP") != STATE_FIPS:
                continue
            name = r["COUNTYNAME"]
            fips = STATE_FIPS + r["COUNTYFP"]
            short = re.sub(r"\s+County$", "", name)
            key = bare(short)
            if key in out:
                raise Stop(f"    the Census county list has two counties that read {short}; stopping")
            out[key] = (fips, "City of St. Louis" if fips == STL_CITY else name)
    if len(out) != 115 or bare("St. Louis City") not in out or out[bare("St. Louis City")][0] != STL_CITY or out.get(bare("Jackson"), ("",))[0] != JACKSON:
        raise Stop(f"    the Census county list gives {len(out)} Missouri counties, or not the codes this loader expects; stopping")
    return out


# ---------------------------------------------------------------- the Results by County

PAGE_HEAD = re.compile(r"^(Missouri Office of Secretary of State|OFFICIAL RESULTS|(General|Special|Primary) Election - .*\d{4})$")
ROW = re.compile(r"^(\D+?)((?:\s\d+)+)$")


def read_blocks(lines, known):
    """The document as blocks: {heading lines (a tuple): {"rows": {authority as written: [numbers]}, "total": [numbers]}},
    in the order they appear. A row is an authority's name (one of `known`, compared bare) or 'Total', then numbers;
    every other line is part of a heading. A block that runs over a page comes back under the same heading."""
    blocks, head, in_rows = collections.OrderedDict(), [], False
    cur = None
    for _p, _y, t in lines:
        t = t.strip()
        if not t or PAGE_HEAD.match(t):
            continue
        m = ROW.match(t)
        name = m.group(1).strip() if m else None
        if m and (name == "Total" or bare(name) in known):
            if not in_rows:
                cur = blocks.setdefault(tuple(head), {"rows": collections.OrderedDict(), "total": None})
                in_rows = True
            nums = [int(x) for x in m.group(2).split()]
            if name == "Total":
                if cur["total"] is not None:
                    raise Stop(f"    {' / '.join(head)}: two Total rows; stopping")
                cur["total"] = nums
            else:
                if name in cur["rows"]:
                    raise Stop(f"    {' / '.join(head)}: {name} appears twice; stopping")
                cur["rows"][name] = nums
        else:
            if in_rows:
                head, in_rows = [], False
            head.append(t)
    return blocks


def contest_table(blocks, c):
    """One statewide contest out of the blocks: {authority: {"dem", "rep", "other", "total"}}, the Total row the same
    way, and what the headings said. A wide contest is printed in several runs of columns; they are put side by side."""
    chunks = [(h, b) for h, b in blocks.items() if any(line in c["labels"] for line in h)]
    if not chunks:
        raise Stop(f"    {c['id']}: no contest headed {' or '.join(c['labels'])} in the Results by County; stopping")
    parties, names = [], []
    for i, (h, b) in enumerate(chunks):
        if h[0] in c["labels"] or re.search(r"\d", h[0]):
            raise Stop(f"    {c['id']}: the heading does not begin with a line of parties ('{h[0]}'); stopping")
        last = i == len(chunks) - 1
        if h[-1].endswith(" Total") != last and not (last and h[-1] == "Total"):
            raise Stop(f"    {c['id']}: the Total column is not where it is expected (the last run of columns); stopping")
        parties.append(h[0].split())
        names.append(" ".join(x for x in h[1:] if x not in c["labels"]))
    flat = [p for run in parties for p in run]
    rep = [i for i, p in enumerate(flat) if p == "Republican"]
    dem = [i for i, p in enumerate(flat) if p == "Democratic"]
    if len(rep) != 1 or len(dem) != 1 or len(parties[0]) <= max(rep[0], dem[0]):
        raise Stop(f"    {c['id']}: {len(rep)} Republican and {len(dem)} Democratic columns in the first run, not one of each; stopping")
    if not has_ticket(names[0], c["rep"]) or not has_ticket(names[0], c["dem"]):
        raise Stop(f"    {c['id']}: the heading does not name the tickets this loader was checked against ({c['rep']}, {c['dem']}); stopping")
    first = lambda ticket: names[0].index(ticket.split("/")[0])                                    # noqa: E731
    if (first(c["rep"]) < first(c["dem"])) != (rep[0] < dem[0]):
        raise Stop(f"    {c['id']}: the tickets are not printed in the order of their parties; stopping")
    widths = [len(run) for run in parties]
    widths[-1] += 1                                                     # the Total column
    printed = []

    def side_by_side(pick, what):
        nums = []
        for (h, b), w in zip(chunks, widths):
            got = pick(b)
            if got is None or len(got) != w:
                raise Stop(f"    {c['id']}, {what}: {0 if got is None else len(got)} numbers under {w} columns; stopping")
            nums += got
        cand, total = nums[:-1], sum(nums[:-1])                         # a place's total is its candidates added up
        if nums[-1] != total:
            printed.append({"row": what, "printed_total": nums[-1], "candidates_add_up_to": total})
        return {"dem": cand[dem[0]], "rep": cand[rep[0]], "other": total - cand[dem[0]] - cand[rep[0]], "total": total}, cand
    order = list(chunks[0][1]["rows"])
    for h, b in chunks[1:]:
        if list(b["rows"]) != order:
            raise Stop(f"    {c['id']}: the runs of columns do not list the same authorities; stopping")
    rows, cols = {}, [0] * len(flat)
    for a in order:
        rows[a], cand = side_by_side(lambda b, a=a: b["rows"].get(a), a)
        cols = [x + y for x, y in zip(cols, cand)]
    total, cand = side_by_side(lambda b: b["total"], "the Total row")
    if cols != cand:
        raise Stop(f"    {c['id']}: the columns add up to {cols} and the Total row reads {cand}; stopping")
    if any(x["row"] == "the Total row" for x in printed):
        raise Stop(f"    {c['id']}: the Total row's candidates do not add up to its own Total; stopping")
    if len(printed) > 3:
        raise Stop(f"    {c['id']}: {len(printed)} rows print a Total their candidates do not add up to; that is a misreading, not a slip; stopping")
    return {"rows": rows, "total": total, "printed_differs": printed, "parties": flat, "write_ins": sum(v for p, v in zip(flat, cand) if p.lower() == "write-in"),
            "columns": len(flat)}


def district_authorities(blocks):
    """{chamber: {district: [authorities]}} from the legislative contests' own lists of who voted in them."""
    out = {"senate": {}, "house": {}}
    for h, b in blocks.items():
        kind = "senate" if h[0].startswith("State Senator") else "house" if h[0].startswith("State Representative") else None
        m = re.match(r"^District (\d+)\b", h[1]) if kind and len(h) > 1 else None
        if kind and not m:
            raise Stop(f"    a contest headed '{h[0]}' names no district; stopping")
        if m:
            if m.group(1) in out[kind]:
                raise Stop(f"    {h[0].split()[1]} district {m.group(1)} is printed under two headings; stopping")
            out[kind][m.group(1)] = list(b["rows"])
    return out


def read_results(path, known):
    from ballot import pdftext
    blocks = read_blocks(pdftext.lines(path), known)
    del known
    return blocks


# ---------------------------------------------------------------- the Grand Totals, and the Clerk's statistics

def read_canvass(path):
    """{office heading: {"lines": [(candidates, party, votes)], "total": n}} and the document's own heading lines."""
    from ballot import pdftext
    lines = [t.strip() for _p, _y, t in pdftext.lines(path)]
    out, cur = {}, None
    for t in lines:
        m = re.match(r"^(.*?) \(\d+ of \d+ Precincts Reported\)$", t)
        if m:
            cur = out.setdefault(m.group(1), {"lines": [], "total": None})
            continue
        if cur is None:
            continue
        m = re.match(r"^Total Votes ([\d,]+)$", t)
        if m:
            cur["total"] = int(m.group(1).replace(",", ""))
            cur = None
            continue
        m = re.match(r"^(.*?) ([A-Z][A-Za-z-]+) ([\d,]+) \d+\.\d%$", t)
        if m:
            cur["lines"].append((m.group(1), m.group(2), int(m.group(3).replace(",", ""))))
    heading = [t for t in lines[:6] if re.search(r"(?i)election returns|board of state canvassers", t)]
    return out, heading


def canvass_official(parsed, c):
    sec = parsed.get(c["canvass"])
    if not sec or sec["total"] is None:
        raise ValueError(f"no '{c['canvass']}' with a Total Votes line")
    pick = {}
    for side, party in (("dem", "Democratic"), ("rep", "Republican")):
        got = [(label, v) for label, p, v in sec["lines"] if p == party]
        if len(got) != 1 or not has_ticket(got[0][0], c[side]):
            raise ValueError(f"'{c['canvass']}': not one {party} line naming {c[side]}")
        pick[side] = got[0][1]
    if sum(v for _l, _p, v in sec["lines"]) != sec["total"]:
        raise ValueError(f"'{c['canvass']}': its lines do not add up to its Total Votes")
    return {"dem": pick["dem"], "rep": pick["rep"], "other": sec["total"] - pick["dem"] - pick["rep"], "total": sec["total"]}


def read_clerk(path, state="MISSOURI"):
    """The state's page of the Clerk of the House's election statistics: {section heading: [(label, votes)]}."""
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
            sections[section].append((m.group(1).strip(), int(m.group(2).replace(",", ""))))
    return {"where": f"Missouri, page {top}" if top.isdigit() else f"Missouri, page {page} of the PDF", "sections": sections}


def clerk_figures(parsed, section):
    lines = parsed["sections"].get(section) or []
    party = (lambda s: s) if section == "FOR PRESIDENTIAL ELECTORS" else (lambda s: s.rsplit(",", 1)[-1].strip())
    dem = [v for s, v in lines if party(s).lower().startswith("democrat")]
    rep = [v for s, v in lines if party(s) == "Republican"]
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{section}: {len(dem)} Democratic and {len(rep)} Republican lines, not one of each")
    return {"dem": dem[0], "rep": rep[0], "all_votes": sum(v for _s, v in lines)}


def clerk_totals(contests, cache, refresh, say):
    out, docs = {}, []
    for year in sorted({c["year"] for c in contests if c.get("clerk")}, reverse=True):
        src = CLERK[year]
        rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
        path = os.path.join(cache, src["file"])
        try:
            net.download(src["url"], path, 0 if refresh else MAX_AGE_DAYS, tries=2, say=say)
            parsed = read_clerk(path)
            rec.update(fetched=_day(path), sha256=_sha_file(path), where=parsed["where"])
            for c in contests:
                if c["year"] == year and c.get("clerk"):
                    out[c["id"]] = dict(clerk_figures(parsed, c["clerk"]), source=src["id"], where=parsed["where"])
        except Exception as e:  # noqa: BLE001  the Grand Totals are the first control; the Clerk's is said to be unread
            say(f"      {src['title']}: could not be read ({e}); the control rests on the Grand Totals")
            rec.update(unread=f"could not be read on {_now()}: {e}")
        docs.append(rec)
    return out, docs


# ---------------------------------------------------------------- the Census Bureau's block equivalency files

def read_bef(cache, refresh, say):
    """{chamber: {district: {county FIPS: blocks}}} for Missouri, and the files' records. The national zip is large
    (25 MB); a copy another state's loader already keeps is read where it is, and a small extract is kept here."""
    extract = os.path.join(cache, "census_bef_2024_mo_extract.json")
    if not refresh and os.path.exists(extract):
        with open(extract, encoding="utf-8") as fh:
            return json.load(fh)
    doc = {"fetched": _now(), "files": {}, "districts": {}}
    for kind, (name, tag, url) in BEF.items():
        path = os.path.join(cache, name)
        if not os.path.exists(path):
            near = sorted(glob.glob(os.path.join(os.path.dirname(cache), "*_local", name)))
            path = near[0] if near else fetch(url, path, refresh, say)
        with zipfile.ZipFile(path) as z:
            members = [n for n in z.namelist() if n.startswith(f"{STATE_FIPS}_") and tag in n] or [n for n in z.namelist() if n.startswith("National")]
            if len(members) != 1:
                raise Stop(f"    {name}: no one file for Missouri or the nation in it; stopping")
            table = collections.defaultdict(collections.Counter)
            with z.open(members[0]) as raw:
                fh = io.TextIOWrapper(raw, encoding="utf-8-sig")
                fh.readline()
                for line in fh:
                    if line.startswith(STATE_FIPS):
                        geoid, _, d = line.strip().partition(",")
                        if len(geoid) == 15 and d.isdigit():
                            table[str(int(d))][geoid[:5]] += 1
        doc["files"][kind] = {"file": name, "member": members[0], "url": url, "sha256": _sha_file(path), "on_disk_since": _day(path)}
        doc["districts"][kind] = {d: dict(sorted(c.items())) for d, c in sorted(table.items(), key=lambda kv: int(kv[0]))}
        say(f"      {name}: {sum(sum(c.values()) for c in table.values()):,} Missouri blocks in {len(table)} districts")
    os.makedirs(cache, exist_ok=True)
    with open(extract + ".part", "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    os.replace(extract + ".part", extract)
    return doc


def whole_county_districts(counties_of):
    """{district: sorted counties} for the districts that share no county with another district.
    counties_of is {district: iterable of county FIPS}."""
    seen = collections.defaultdict(set)
    for d, cs in counties_of.items():
        for c in cs:
            seen[c].add(d)
    return {d: sorted(set(cs)) for d, cs in counties_of.items() if cs and all(seen[c] == {d} for c in cs)}


# ---------------------------------------------------------------- adding up

def add(into, v):
    for k in VOTE_KEYS:
        into[k] = into.get(k, 0) + v[k]
    return into


def few(rec):
    hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
    if hold:
        rec["too_few"] = hold
    return rec


def build(tables, districts_by_year, counties, bef, official, clerk=None, contests=CONTESTS, expect=True):
    """tables: {contest id: contest_table()}; districts_by_year: {year: district_authorities()}; counties: read_counties();
    bef: read_bef()["districts"] or None; official: {contest id: {dem, rep, other, total, ...}}. Returns (doc, failed)."""
    failed, ids = [], [c["id"] for c in contests]
    fips_of = lambda a: JACKSON if a == KC else counties[bare(a)][0]                              # noqa: E731
    name_of = {f: n for f, n in counties.values()}
    county, parts, state = {}, collections.defaultdict(dict), {}
    for c in contests:
        t = tables[c["id"]]
        if expect and len(t["rows"]) != AUTHORITIES:
            failed.append(f"{c['id']}: {len(t['rows'])} election authorities, not {AUTHORITIES}")
        for a, v in t["rows"].items():
            f = fips_of(a)
            add(county.setdefault(f, {}).setdefault(c["id"], {}), v)
            if f == JACKSON:
                parts[a][c["id"]] = v
        state[c["id"]] = dict(t["total"])
    places = {k: {} for k in KIND_NAMES}
    for f in sorted(county):
        rec = few({"name": name_of[f], "votes": {cid: county[f][cid] for cid in ids if cid in county[f]}})
        if f == JACKSON and parts:
            rec["parts"] = {("Kansas City, the part in Jackson County (counted by the Kansas City Board of Election Commissioners)" if a == KC
                             else "Jackson County outside Kansas City (counted by the Jackson County Board of Election Commissioners)"):
                            {cid: v[cid] for cid in ids if cid in v} for a, v in sorted(parts.items(), key=lambda kv: kv[0] != KC)}
            rec["note"] = ("Two election authorities count Jackson County's votes; the county's figures are the two together, and each is given "
                           "under parts. The parts of Kansas City in Clay, Platte and Cass counties are counted by those counties.")
        if f == STL_CITY:
            rec["note"] = "The City of St. Louis is no part of any county; Missouri's records file it beside the counties."
            places["mcd"][STL_CITY_PLACE] = few({"name": "St. Louis city", "type": "city", "counties": [STL_CITY], "votes": dict(rec["votes"]),
                                                 "note": "The same figures as the county record 29510: the city is its own county."})
        places["county"][f] = rec

    # the districts made of whole counties, read from the results and from the Census Bureau's files
    given = {k: [cid for cid, c in zip(ids, contests) if c["year"] >= first] for k, first, *_ in KINDS}
    not_given, district_notes = {}, {}
    plan_years = sorted(y for y in districts_by_year if y >= PLAN_YEAR)
    for kind in ("senate", "house"):
        by_year = {y: {d: sorted({fips_of(a) for a in auths}) for d, auths in districts_by_year[y][kind].items()} for y in plan_years}
        merged = {}
        for y in plan_years:
            for d, cs in by_year[y].items():
                if d in merged and merged[d] != cs:
                    failed.append(f"{kind} district {d}: the results of {y} list other counties than those of another year on the same plan")
                merged[d] = cs
        if expect and len(merged) != SEATS[kind]:
            failed.append(f"{len(merged)} {kind} districts in the results of {', '.join(map(str, plan_years))}, not {SEATS[kind]}")
        whole = whole_county_districts(merged)
        if bef is not None:
            census = {d: sorted(cs) for d, cs in bef[kind].items()}
            census_whole = whole_county_districts(census)
            if expect and len(census) != SEATS[kind]:
                failed.append(f"{len(census)} {kind} districts in the Census Bureau's file, not {SEATS[kind]}")
            differ = sorted((d for d in set(whole) | set(census_whole) if whole.get(d) != census_whole.get(d)), key=int)
            if differ:
                district_notes[kind] = (f"District{'s' if len(differ) > 1 else ''} {', '.join(differ)}: the results and the Census Bureau's block "
                                        "file do not give the same whole counties, so not given.")
            whole = {d: cs for d, cs in whole.items() if census_whole.get(d) == cs}
        label = "Senate" if kind == "senate" else "House"
        for d in sorted(whole, key=int):
            votes = {}
            for cid in given[kind]:
                v = {}
                for f in whole[d]:
                    add(v, county[f][cid])
                votes[cid] = v
            places[kind][d] = few({"name": f"{label} District {d}", "counties": whole[d],
                                   "county_names": [name_of[f] for f in whole[d]], "votes": votes})
        not_given[kind] = sorted((d for d in merged if d not in whole), key=int)

    # the control
    per, row_notes = {}, []
    for c in contests:
        mine, off = state[c["id"]], official[c["id"]]
        theirs = {k: off[k] for k in VOTE_KEYS}
        sums = {k: sum(p["votes"][c["id"]][k] for p in places["county"].values() if c["id"] in p["votes"]) for k in VOTE_KEYS}
        diff = {k: mine[k] - theirs[k] for k in VOTE_KEYS if mine[k] != theirs[k]}
        per[c["id"]] = {"sum_of_counties": sums, "official": theirs, "equal": not diff and sums == mine, "source": off["source"],
                        "where": off["where"], "read": off["read"], "authorities": len(tables[c["id"]]["rows"]),
                        "write_ins_counted_in_other": tables[c["id"]]["write_ins"]}
        if tables[c["id"]].get("printed_differs"):
            per[c["id"]]["printed_row_totals_that_differ"] = tables[c["id"]]["printed_differs"]
            row_notes.append(f"{c['id']}: " + "; ".join(f"the row of {x['row']} prints a Total of {x['printed_total']:,} and its candidates add up to "
                                                         f"{x['candidates_add_up_to']:,}" for x in tables[c["id"]]["printed_differs"])
                             + ". The candidates' columns equal the Total row and the Grand Totals, so the place's total here is its candidates "
                               "added up; the document is not changed.")
        if diff:
            per[c["id"]]["difference"] = diff
            failed.append(f"{c['id']}: the Results by County add up to {mine} and the Grand Totals are {theirs}; county minus Grand Totals: {diff}")
        if sums != mine:
            failed.append(f"{c['id']}: the counties add up to {sums} and the Total row is {mine}")
        ck = (clerk or {}).get(c["id"])
        if ck:
            ok = ck["dem"] == mine["dem"] and ck["rep"] == mine["rep"]
            per[c["id"]]["clerk"] = dict(ck, equal=ok)
            if not ok:
                failed.append(f"{c['id']}: the Clerk of the House gives {ck['dem']:,} Democratic and {ck['rep']:,} Republican votes; "
                              f"the Results by County {mine['dem']:,} and {mine['rep']:,}")
    whole_note = "made of whole counties only, the same in the results and in the Census Bureau's block file; a district that shares a county is left out"
    ctl = {"result": "equal" if not failed else "differs",
           "statement": ("For every contest all 116 election authorities are present; every candidate's column adds up to the Total row printed "
                         "under it, and the Total row's candidates to its own Total; the counties add up to that Total row; the Total row equals the Grand "
                         "Totals announced by the Board of State Canvassers, for the Democratic ticket, the Republican ticket, the rest and the "
                         "total; and every legislative district given is whole counties, read the same from the results and from the Census "
                         "Bureau's block equivalency file." if not failed else "The sums do not all agree; see the differences."),
           "authorities": AUTHORITIES, "contests": per,
           "kinds": {"county": "equal to the statewide sum" if not failed else "see the differences", "mcd": "the City of St. Louis is its county record",
                     "senate": whole_note, "house": whole_note},
           "notes": [v for _k, v in sorted(district_notes.items())] + row_notes}

    kinds = {}
    for kind, first, covers, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind], "covers_the_state": covers,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if kind in ("senate", "house"):
            kinds[kind]["why_not_2020"] = WHY_NOT_2020
            kinds[kind]["not_given"] = not_given[kind]
            kinds[kind]["note"] = (f"A district is given when every county it reaches lies wholly inside it; its votes are then its counties' votes. "
                                   f"{len(not_given[kind])} of the {len(not_given[kind]) + len(places[kind])} districts share a county with another "
                                   "district; Missouri does not publish results below the county, so those are not given and nothing is estimated.")
    kinds["county"]["note"] = ("Jackson County is the Kansas City board's row and the Jackson County board's row together; the City of St. Louis "
                               "is filed as a county.")
    kinds["mcd"]["note"] = "No other city, town or township is given: the published official results stop at the county."
    records = []
    for c in contests:
        t = tables[c["id"]]
        rec = {"id": c["id"], "date": DOCS.get(c["year"], {}).get("date", str(c["year"])), "office": c["office"], "table": f"mo-sos-results-by-county-{c['year']}",
               "kinds": [k for k in KIND_NAMES if c["id"] in given[k]],
               "dem": {"party": "Democratic", "ticket": c["dem"], "column": "the column headed Democratic"},
               "rep": {"party": "Republican", "ticket": c["rep"], "column": "the column headed Republican"},
               "other": {"what": "every other candidate and all write-ins, together", "columns": t["columns"] - 2, "of_which_write_in_votes": t["write_ins"]},
               "total": {"what": "the row's own Total column"},
               "statewide": dict(state[c["id"]]), "official_source": official[c["id"]]["source"]}
        records.append(rec)
    doc = {"what": WHAT, "note": NOTE, "state": "MO", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(VOTE_KEYS), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": ctl,
           "coverage": {"not_given": NOT_GIVEN, "districts_not_given": not_given,
                        "why_no_precincts": "The Secretary of State's results page offers the precinct data files for purchase and publishes "
                                            "results by county; this file is made from what is published."},
           "sources": [], "places": places}
    return doc, failed


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
    """What our Missouri places and races use, read only: {kind: ids}; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'mo-%'"):
            out[kind].add(pid)
        for kind, district in con.execute("SELECT office_kind, district FROM sl_races WHERE state = 'MO' AND level = 'legislature'"):
            if district and kind in ("state_senate", "state_house"):
                out["senate" if kind == "state_senate" else "house"].add(str(district))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Missouri place votes: the Secretary of State's official Results by County and the Board of State Canvassers' Grand Totals")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    counties = read_counties(fetch(COUNTY_LIST[0], os.path.join(cache, COUNTY_LIST[1]), refresh, say))
    known = set(counties) | {bare(KC)}
    tables, districts, official, sources = {}, {}, {}, []
    for year in sorted(DOCS, reverse=True):
        d = DOCS[year]
        cpath = fetch(SOS + d["county"], os.path.join(cache, d["county"]), refresh, say)
        time.sleep(1.0)
        gpath = fetch(SOS + d["canvass"], os.path.join(cache, d["canvass"]), refresh, say)
        blocks = read_results(cpath, known)
        mine = [c for c in CONTESTS if c["year"] == year]
        for c in mine:
            tables[c["id"]] = contest_table(blocks, c)
        if year >= PLAN_YEAR:
            districts[year] = district_authorities(blocks)
        heading = []
        try:
            parsed, heading = read_canvass(gpath)
        except Exception as e:  # noqa: BLE001
            parsed = None
            say(f"      {d['canvass']}: could not be read ({e}); the control uses the figures typed in on 2026-10-02")
        for c in mine:
            got = None
            if parsed is not None:
                try:
                    got = dict(canvass_official(parsed, c), read=f"from the document on {_day(gpath)}")
                except ValueError as e:
                    say(f"      {c['id']}: {e}; the control uses the figures typed in on 2026-10-02")
            if got is None:
                got = dict(CHECKED[c["id"]], read="typed into the loader from the document on 2026-10-02; the document could not be read again today")
            elif {k: got[k] for k in VOTE_KEYS} != CHECKED[c["id"]]:
                say(f"      {c['id']}: the Grand Totals now read {got}; this loader was checked against {CHECKED[c['id']]}")
            official[c["id"]] = dict(got, source=f"mo-sos-grand-totals-{year}", where=f"Grand Totals, '{c['canvass']}'")
        say(f"      {year}: {len(blocks)} tables in the Results by County; " + ", ".join(f"{c['id']} {tables[c['id']]['total']['total']:,}" for c in mine))
        sources.append({"id": f"mo-sos-results-by-county-{year}", "kind": "official results by county", "agency": AGENCY,
                        "title": f"{d['title']}: Results by County (headed OFFICIAL RESULTS)", "url": SOS + d["county"], "listed_on": SOS_PAGE,
                        "fetched": _day(cpath), "sha256": _sha_file(cpath),
                        "read": "Of each election authority: its name and the votes of every candidate in the contests named here; of the "
                                "contests for State Senator and State Representative only which authorities voted in each district."})
        sources.append({"id": f"mo-sos-grand-totals-{year}", "kind": "official statewide returns", "agency": AGENCY,
                        "title": f"{d['title']}: Grand Totals", "url": SOS + d["canvass"], "listed_on": SOS_PAGE, "fetched": _day(gpath),
                        "sha256": _sha_file(gpath), "headed": heading,
                        "canvassed": next((re.sub(r"^As announced", "Announced", h) for h in heading if "Canvassers" in h), None)})
    bef = read_bef(cache, refresh, say)
    sources.append({"id": "census-2024-legislative-bef", "kind": "official block equivalency files", "agency": "U.S. Census Bureau",
                    "title": "2024 State Legislative District Block Equivalency Files (sldl24.zip, sldu24.zip)", "url": BEF["house"][2],
                    "files": bef["files"], "read": "Of each Missouri census block: its county and its district. Used only to say which districts are whole counties."})
    sources.append({"id": "census-2020-counties", "kind": "official list of counties", "agency": "U.S. Census Bureau",
                    "title": "2020 FIPS codes for counties, Missouri", "url": COUNTY_LIST[0], "sha256": _sha_file(os.path.join(cache, COUNTY_LIST[1]))})
    clerk, clerk_docs = clerk_totals(CONTESTS, cache, refresh, say)
    doc, failed = build(tables, districts, counties, bef["districts"], official, clerk)
    doc["sources"] = sources + clerk_docs
    if not all(c["id"] in clerk for c in CONTESTS if c.get("clerk")):
        doc["control"]["notes"].append("A Clerk of the House document could not be read at this run; for its contests the control is the Grand Totals alone.")
    doc["control"]["notes"].append("The 2020 Grand Totals document is headed 'Unofficial Election Returns' and was printed on 01/26/2021, after the "
                                   "canvass; the 2020 Results by County are headed OFFICIAL RESULTS, and the two agree.")
    doc["control"]["notes"].append("Governor is not in the Clerk's statistics; its control is the Grand Totals.")
    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties (the City of St. Louis among them); {len(p['senate'])} of {SEATS['senate']} Senate and "
        f"{len(p['house'])} of {SEATS['house']} House districts are whole counties")
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + ("equal to" if ctl["equal"] else "DIFFERS from") + f" the Grand Totals ({ctl['read']})"
            + (f"; the Clerk's two-party figures {'agree' if ctl['clerk']['equal'] else 'DIFFER'}" if "clerk" in ctl else ""))
    for note in doc["control"]["notes"]:
        if note.startswith("District") or "prints a Total" in note:
            say(f"      {note}")
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    Missouri place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES:
            ids = ours.get(kind, set())
            without = sorted((i for i in ids if not p[kind].get(i, {}).get("votes")), key=sort_key)
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}"
                + (f" (none for {', '.join(without[:12])}{' and more' if len(without) > 12 else ''})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {_now()}")
    write(out, doc)
    say(f"    Missouri place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e3:.0f} kB)")
    return doc


# ---------------------------------------------------------------- the reader and the arithmetic on made-up lines

def selftest(say=print):
    counties = {bare("Adair"): ("29001", "Adair County"), bare("De Kalb"): ("29063", "DeKalb County"), bare("Jackson"): (JACKSON, "Jackson County"),
                bare("St. Louis"): ("29189", "St. Louis County"), bare("St. Louis City"): (STL_CITY, "City of St. Louis")}
    known = set(counties) | {bare(KC)}
    text = """Missouri Office of Secretary of State
OFFICIAL RESULTS
General Election - November 5, 2024
Republican Democratic Green Write-in
U.S. President
Ann Alpha Bo Beta Cy Gamma Di Delta
& Vice President
Ed Epsilon Flo Zeta Gil Eta Hal Theta
Adair 30 20 2 0
De Kalb 25 0 0 0
Jackson 40 60 3 1
Kansas City 10 90 4 0
Missouri Office of Secretary of State
OFFICIAL RESULTS
General Election - November 5, 2024
Republican Democratic Green Write-in
U.S. President
Ann Alpha Bo Beta Cy Gamma Di Delta
& Vice President
Ed Epsilon Flo Zeta Gil Eta Hal Theta
St. Louis 50 70 5 0
St. Louis City 5 9 1 0
Total 160 249 15 1
Write-in
U.S. President
Io Iota
& Vice President
Kay Kappa Total
Adair 1 53
De Kalb 0 25
Jackson 0 104
Kansas City 0 104
St. Louis 2 127
St. Louis City 0 15
Total 3 428
State Senator Republican
District 1 Lo Lambda Total
Adair 40 40
De Kalb 20 20
Total 60 60
State Senator Democratic
District 2 Mo Mu Total
Jackson 90 90
Kansas City 95 95
St. Louis 60 60
Total 245 245
State Senator Democratic
District 3 Nu Nu Total
St. Louis 50 50
St. Louis City 14 14
Total 64 64
State Representative Republican
District 1 Xi Xi Total
Adair 44 44
Total 44 44"""
    lines = [(1, 0.0, t) for t in text.split("\n")]
    c = {"id": "2024-president", "year": 2024, "office": "President", "labels": ["U.S. President"], "canvass": "President", "dem": "Beta/Zeta",
         "rep": "Alpha/Epsilon"}
    checks = []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    blocks = read_blocks(lines, known)
    t = contest_table(blocks, c)
    check("a contest printed in two runs of columns is put side by side", t["rows"]["Adair"], {"dem": 20, "rep": 30, "other": 3, "total": 53})
    check("a table that runs over a page is one table", len(t["rows"]), 6)
    check("the Total row is read", t["total"], {"dem": 249, "rep": 160, "other": 19, "total": 428})
    check("write-in votes are counted, in other", t["write_ins"], 4)
    d = district_authorities(blocks)
    check("a district's authorities are read from its own contest", d["senate"]["2"], ["Jackson", "Kansas City", "St. Louis"])
    official = {c["id"]: {"dem": 249, "rep": 160, "other": 19, "total": 428, "source": "x", "where": "-", "read": "-"}}
    bef = {"senate": {"1": {"29001": 5, "29063": 4}, "2": {JACKSON: 9, "29189": 3}, "3": {"29189": 4, STL_CITY: 6}}, "house": {"1": {"29001": 5}}}
    doc, failed = build({c["id"]: t}, {2024: d}, counties, bef, official, None, [c], expect=False)
    p = doc["places"]
    check("the control holds on the made-up tables", (doc["control"]["result"], failed), ("equal", []))
    check("Jackson County is its two authorities together", p["county"][JACKSON]["votes"][c["id"]], {"dem": 150, "rep": 50, "other": 8, "total": 208})
    check("and gives each part", sorted(v[c["id"]]["total"] for v in p["county"][JACKSON]["parts"].values()), [104, 104])
    check("the City of St. Louis is a county and a city", p["mcd"][STL_CITY_PLACE]["votes"], p["county"][STL_CITY]["votes"])
    check("a district of whole counties is its counties added up", p["senate"]["1"]["votes"][c["id"]], {"dem": 20, "rep": 55, "other": 3, "total": 78})
    check("a district that shares a county is not given", (sorted(p["senate"]), doc["kinds"]["senate"]["not_given"]), (["1"], ["2", "3"]))
    check("a place where every vote went one way is marked too_few", p["county"]["29063"].get("too_few"), [c["id"]])
    check("a place of fewer than twenty votes is marked too_few", p["county"][STL_CITY].get("too_few"), [c["id"]])
    check("a place of twenty votes or more, not all one way, is not", p["county"]["29001"].get("too_few"), None)
    bef2 = dict(bef, senate=dict(bef["senate"], **{"1": {"29001": 5}, "4": {"29063": 4}}))
    doc2, _f = build({c["id"]: t}, {2024: d}, counties, bef2, official, None, [c], expect=False)
    check("a district the Census file draws otherwise is left out", sorted(doc2["places"]["senate"]), [])
    wrong = {c["id"]: dict(official[c["id"]], dem=250, total=429)}
    check("a wrong Grand Total is caught", build({c["id"]: t}, {2024: d}, counties, bef, wrong, None, [c], expect=False)[0]["control"]["result"], "differs")
    try:
        contest_table(read_blocks([(1, 0.0, x.replace("Adair 30 20 2 0", "Adair 31 20 2 0")) for x in text.split("\n")], known), c)
        caught = False
    except Stop:
        caught = True
    check("a column that does not add up to the Total row stops the loader", caught, True)
    slip = contest_table(read_blocks([(1, 0.0, x.replace("Adair 1 53", "Adair 1 52")) for x in text.split("\n")], known), c)
    check("a row whose printed Total differs from its candidates is listed, and the candidates stand",
          (slip["rows"]["Adair"]["total"], slip["printed_differs"]), (53, [{"row": "Adair", "printed_total": 52, "candidates_add_up_to": 53}]))
    try:
        contest_table(blocks, dict(c, dem="Alpha/Epsilon", rep="Beta/Zeta"))
        caught = False
    except Stop:
        caught = True
    check("tickets printed under the other party stop the loader", caught, True)
    check("the note never calls these precinct results", bool(re.search(r"\bprecinct results\b", WHAT + " " + NOTE, re.I)), False)
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Missouri place voted in past partisan general elections -> ballot/lean/mo_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/mo_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/mo_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every document again, even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="check the reader and the arithmetic on made-up lines; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
