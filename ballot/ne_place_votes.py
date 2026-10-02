"""
ballot/ne_place_votes.py - how each Nebraska place voted in past partisan general elections, from the Board of State
Canvassers' official results, so a page can show the record of a county or a legislative district without anyone
labelling a candidate. Nebraska's twin of ballot/mn_place_votes.py; the file it writes has the same shape (the
Democratic count is "dem" here, as in Missouri's, Iowa's and Wisconsin's files, where Minnesota's is "dfl").

    python ballot/ne_place_votes.py               reads (or downloads) the documents, writes ballot/lean/ne_place_votes.json
    python ballot/ne_place_votes.py --refresh     asks for every document again even when the cached copies are there
    python ballot/ne_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/ne_place_votes.py --selftest    the reader and the arithmetic on made-up lines; downloads nothing

What it is, and is not
----------------------
For President and U.S. Senator (the two-year term) in 2024, Governor in 2022, and President and U.S. Senator in 2020:
the votes for the Democratic ticket, the Republican ticket, everyone else together (write-ins included) and the total,
for every one of the 93 counties and, for the 2022 and 2024 contests, for each legislative district that is made of
whole counties. It is how the people of a place voted then. It is not a prediction, it says nothing about any
candidate on a later ballot or about any voter, and it turns no nonpartisan office into a partisan one (Nebraska's
Legislature is elected without party labels, and stays so here). No database is opened for writing;
ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

The 2024 election for the six-year Senate term is not given: no Democratic candidate was on that ballot (the
Republican candidate's opponent ran by petition, without a party), and a file whose counts are Democratic, Republican
and other would file that opponent's votes under "other" and so say something untrue about the place.

Why counties, and not precincts
-------------------------------
Nebraska's official results are the "Official Report of the Board of State Canvassers" (the canvass book,
sos.nebraska.gov, Previous Elections): a PDF of real text with one row a county and a Total row for each contest. It
has no precincts. The Secretary of State's results site (electionresults.nebraska.gov) can export a contest precinct
by precinct, but on 2026-10-02 it answered for the 2020 general election only (its election number 25): the numbers
where the 2022 and 2024 general elections would be (27, 28, 31) answer "An error has occured", for every page. The
2020 election was held on the legislative districts of 2011, and a Nebraska precinct's name does not say which city
or village it is in, so the 2020 precincts would add no place our pages use; they are not read. The counties' own
results pages (countyelectionresults.nebraska.gov, and four counties' own sites) are 93 separate postings in many
layouts, some still marked unofficial, and are not read either. If the Secretary's site serves 2022 and 2024 again, a
precinct reader belongs here (ballot/sd_place_votes.py reads the same results system), and every district follows.

  - A legislative district is given only when it is made of whole counties: then its votes are its counties' votes,
    exactly. Which counties a district has is read two ways that must agree: from the Census Bureau's 2024 block
    equivalency file (every census block's district) and from the canvass book's own "Member of the Legislature"
    tables (each district elected in that year lists its counties; the odd districts in 2024, the even in 2022; the
    tables are printed two side by side, so the page is read by halves; candidates' names there are never kept). A
    district that shares a county with another district is NOT given, and is listed: nothing is shared out or
    estimated.
  - Districts are given for the 2022 and 2024 contests: both elections were held on the plan of 2021 (LB 3, first
    used in 2022), the plan our 2026 races are on. 2020 was held on the plan of 2011, so 2020 is for counties only.
  - Not given: cities, villages and townships, wards, county board districts, school, natural resources, power and
    other districts, and the congressional districts (the book has President by congressional district; no place of
    ours is one).
  - Of candidates only the two tickets' surnames are kept, to say which election this was; they must be the surnames
    typed in CONTESTS, printed over the columns the book heads (Republican) and (Democratic), or the loader stops.

The control
-----------
Nothing is written unless all of this holds: for every contest all 93 counties are there once, each with as many
columns as the Total row; every column adds up to the Total row printed in the table; the counties add up to the
statewide sum; and for President and U.S. Senator the Republican and Democratic totals equal the Clerk of the U.S.
House of Representatives' "Statistics of the ... Election" (clerk.house.gov, the Nebraska page, read from the PDF at
each run; a second, federal document). Governor is not in the Clerk's statistics: its control is the canvass book's
own Total row, and the file says so. Every district given has the same whole counties in the Census Bureau's file
and, where the book lists it, in the canvass book. The statewide figures this loader was checked against on
2026-10-02 are typed below (CHECKED); the loader says so if a document reads differently later.
"""

import argparse
import collections
import io
import json
import os
import pathlib
import re
import shutil
import sqlite3
import sys
import glob
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mo_place_votes as MO  # noqa: E402  the shared small things: whole-county districts, the Clerk's page, the file writer

Stop = MO.Stop
METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "ne_local")
OUT = os.path.join(HERE, "ballot", "lean", "ne_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "31"
FEW = 20
KEEP_DAYS = 3650               # certified results of past elections do not change; --refresh asks again
COUNTIES_N = 93
SEATS = 49
PLAN_YEAR = 2022               # the legislative plan our 2026 races are on was first used in 2022
VOTE_KEYS = ("dem", "rep", "other", "total")
MID = 306.0                    # the middle of a letter page, in points: the Legislature tables are printed two side by side

AGENCY = "Nebraska Secretary of State, Elections Division; Board of State Canvassers"
SOS = "https://sos.nebraska.gov/sites/default/files/doc/elections/"
SOS_PAGE = "https://sos.nebraska.gov/elections/previous-elections"
BOOKS = {
    2024: {"url": SOS + "2024/2024%20General%20Canvass%20Book.pdf", "file": "ne_2024_general_canvass_book.pdf", "date": "2024-11-05",
           "title": "Official Report of the Board of State Canvassers, General Election, November 5, 2024"},
    2022: {"url": SOS + "2022/2022%20General%20Canvass%20Book.pdf", "file": "ne_2022_general_canvass_book.pdf", "date": "2022-11-08",
           "title": "Official Report of the Board of State Canvassers, General Election, November 8, 2022"},
    2020: {"url": SOS + "2020/2020-General-Canvass-Book.pdf", "file": "ne_2020_general_canvass_book.pdf", "date": "2020-11-03",
           "title": "Official Report of the Board of State Canvassers, General Election, November 3, 2020"},
}
CENSUS = "https://www2.census.gov/"
COUNTY_LIST = (CENSUS + "geo/docs/reference/codes2020/cou/st31_ne_cou2020.txt", "st31_ne_cou2020.txt")
BEF = ("sldu24.zip", "SLDU24", CENSUS + "programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip")
CLERK = {y: {"id": f"clerk-statistics-{y}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
             "title": f"Statistics of the Presidential and Congressional Election from Official Sources, {y}",
             "url": f"https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf", "file": f"clerk_statistics{y}.pdf"}
         for y in (2024, 2020)}

# The contests. "heading" is the contest's title line in the canvass book; "after" is a line that must follow it within
# the table's heading (None: nothing asked); "dem" and "rep" are surnames the table's heading must carry, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States",
     "heading": "President and Vice President of the United States", "after": None,
     "dem": "Harris/Walz", "rep": "Trump/Vance", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2024-us-senate-special", "year": 2024, "office": "United States Senator (two-year term)",
     "heading": "Member of the United States Senate – Two Year Term", "after": None,
     "dem": "Love", "rep": "Ricketts", "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "office": "Governor and Lieutenant Governor",
     "heading": "Governor and Lieutenant Governor", "after": None, "dem": "Blood/Davis", "rep": "Pillen/Kelly", "clerk": None},
    {"id": "2020-president", "year": 2020, "office": "President and Vice President of the United States",
     "heading": "President and Vice President of the United States", "after": None,
     "dem": "Biden/Harris", "rep": "Trump/Pence", "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-us-senate", "year": 2020, "office": "United States Senator",
     "heading": "Member of the United States Senate", "after": "Six Year Term", "dem": "Janicek", "rep": "Sasse", "clerk": "FOR UNITED STATES SENATOR"},
]

# The canvass books' Total rows this loader was checked against on 2026-10-02.
CHECKED = {
    "2024-president": {"dem": 369995, "rep": 564816, "other": 17371, "total": 952182},
    "2024-us-senate-special": {"dem": 349902, "rep": 585103, "other": 0, "total": 935005},
    "2022-governor": {"dem": 242006, "rep": 398334, "other": 32253, "total": 672593},
    "2020-president": {"dem": 374583, "rep": 556846, "other": 24954, "total": 956383},
    "2020-us-senate": {"dem": 227191, "rep": 583507, "other": 119314, "total": 930012},
}

KINDS = [   # (kind, first election year given, covers the whole state, what it is, what its key is)
    ("county", 2020, True, "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("senate", PLAN_YEAR, False, "Legislative districts of the 2021 plan (each elects one senator), where made of whole counties",
     "district number, as the district of our Legislature races"),
]
KIND_NAMES = [k[0] for k in KINDS]

WHAT = ("How each Nebraska county, and each legislative district made of whole counties, voted in five contests of the 2020, 2022 and 2024 "
        "general elections: the votes for the Democratic ticket, the Republican ticket, everyone else together (write-ins included) and the "
        "total, from the official report of the Board of State Canvassers.")
NOTE = ("What this is: how the people of a place voted in that election, in the official report of Nebraska's Board of State Canvassers, "
        "given here for each county and added up for each legislative district that is made of whole counties. What this is not: it is not a "
        "prediction of any election; it says nothing about any candidate on a later ballot or about any voter; a nonpartisan office stays "
        "nonpartisan (the Legislature is elected without party labels); and it is not the record of a city, a village, a ward or a district "
        "that shares a county with another: the official report stops at the county, and the Secretary of State's results site did not "
        "serve the 2022 and 2024 general elections voting place by voting place when this was made, so those places are not given and nothing "
        "is estimated for them. The tickets are named, as the report names them, only to say which election this was. In a place with very "
        "few voters the split would come close to saying how particular people voted; those contests are listed in the place's too_few, and "
        "a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every other "
               "candidate and all write-ins) and total. Minnesota's file calls the first count dfl. A contest a place does not have was held "
               "on other district lines.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities, villages, townships and wards, county board districts, school and other districts, and every legislative district that "
             "shares a county with another district: the official report gives results by county only, so these cannot be added up from it, "
             "and nothing is estimated. The 2024 election for the six-year Senate term: no Democratic candidate was on that ballot.")
WHY_NOT_2020 = "The 2020 election was held on the legislative districts of 2011; the plan of 2021 is the one our 2026 races are on, so 2020 is not given."
SITE_NOTE = ("The Secretary of State's results site can export a contest by precinct, but on 2026-10-02 it answered for the 2020 general election "
             "only; where the 2022 and 2024 general elections would be it answered with an error page. The 2020 precincts are on the "
             "legislative districts of 2011 and do not say which city they are in, so they are not read.")


# ---------------------------------------------------------------- small things

def fetch(url, path, refresh, say):
    try:
        net.download(url, path, 0 if refresh else KEEP_DAYS, tries=3, say=say)
    except Exception as e:  # noqa: BLE001
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      {os.path.basename(path)}: could not be fetched again ({e}); using the copy of {MO._day(path)}")
            return path
        raise Stop(f"    {os.path.basename(path)} could not be fetched ({e}) and no copy is on disk. Wait a few minutes and run this again.")
    return path


def read_counties(path):
    """{county name without 'County': FIPS} from the Census Bureau's county list; stops unless there are 93."""
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        head = fh.readline().strip().split("|")
        for line in fh:
            r = dict(zip(head, line.rstrip("\n").split("|")))
            if r.get("STATEFP") == STATE_FIPS:
                out[re.sub(r"\s+County$", "", r["COUNTYNAME"])] = STATE_FIPS + r["COUNTYFP"]
    if len(out) != COUNTIES_N or out.get("Adams") != "31001" or out.get("York") != "31185":
        raise Stop(f"    the Census county list gives {len(out)} Nebraska counties, or not the codes this loader expects; stopping")
    return out


def _num(s):
    return int(s.replace(",", ""))


def row_finder(names):
    """A function that finds, in one printed line, every (county or 'Total', [numbers]) on it. The book prints some
    tables two side by side, so a line can carry two counties. A name counts only at the start of the line or right
    after a number, and only when numbers follow it."""
    alt = "|".join(re.escape(n) for n in sorted(list(names) + ["Total"], key=len, reverse=True))
    rx = re.compile(rf"(?:^|(?<=\d)\s)({alt})((?:\s+\d[\d,]*)+)(?=\s|$)")

    def find(text):
        text = text.strip()
        found, covered = [], 0
        for m in rx.finditer(text):
            found.append((m.group(1), [_num(x) for x in m.group(2).split()]))
            covered += len(m.group(0).strip())
        return found if found and covered >= len(text.replace("  ", " ")) - len(found) else []     # the whole line must be rows
    return find


# ---------------------------------------------------------------- the canvass book

def contest_table(lines, c, counties):
    """One contest's table in the canvass book: {"rows": {county: {dem, rep, other, total}}, "total": {...}, "columns": n,
    "pages": [first, last], "header": text}. `lines` are the book's (page, y, text). Stops unless the heading is
    found, the two tickets' surnames stand in the table's heading, the party line heads one column (Republican) and
    one (Democratic), all 93 counties are there once with as many columns as the Total row, and every column adds up
    to the Total row."""
    find = row_finder(counties)
    texts = [(p, t.strip()) for p, _y, t in lines]
    start = None
    for i, (_p, t) in enumerate(texts):
        if t != c["heading"]:
            continue
        nxt = [x for _q, x in texts[i + 1:i + 8]]
        if "Results by Congressional District" in nxt[:2] or not any(x.startswith("County ") for x in nxt):
            continue
        if c.get("after") and c["after"] not in nxt[:2]:
            continue
        start = i
        break
    if start is None:
        raise Stop(f"    {c['id']}: no table headed '{c['heading']}' in the canvass book; stopping")
    header, party_line, rows, total, last = [], None, {}, None, texts[start][0]
    for p, t in texts[start + 1:start + 260]:
        got = find(t)
        if not got:
            if not rows and total is None:
                header.append(t)
                if t.startswith("County ") and party_line is None:
                    party_line = t
            continue
        for name, nums in got:
            if name == "Total":
                if total is not None:
                    raise Stop(f"    {c['id']}: a second Total row before all {COUNTIES_N} counties were read; stopping")
                total = nums
            elif name in rows:
                raise Stop(f"    {c['id']}: {name} appears twice in the table; stopping")
            else:
                rows[name] = nums
            last = p
        if total is not None and len(rows) == len(counties):
            break
    missing = [n for n in counties if n not in rows]
    if total is None or missing:
        raise Stop(f"    {c['id']}: " + ("no Total row" if total is None else f"{len(missing)} counties could not be read ({', '.join(missing[:6])})") + "; stopping")
    n = len(total)
    bad = [name for name, v in rows.items() if len(v) != n]
    if bad:
        raise Stop(f"    {c['id']}: {', '.join(bad[:6])} do not have the Total row's {n} columns; stopping")
    sums = [sum(v[i] for v in rows.values()) for i in range(n)]
    if sums != total:
        raise Stop(f"    {c['id']}: the county rows add up to {sums} and the Total row reads {total}; stopping")
    # which columns are the two tickets: the party line, up to where a second table's "County" begins
    line = (party_line or "")[len("County "):].split(" County ")[0]
    at = {}
    for label, side in (("(Republican)", "rep"), ("(Democratic)", "dem")):
        if line.count(label) != 1:
            raise Stop(f"    {c['id']}: the table heads {line.count(label)} columns {label}, not one; stopping")
        before = line[:line.index(label)].strip()
        if re.sub(r"\([^()]*\)", "", before).strip():
            raise Stop(f"    {c['id']}: the column headings before {label} cannot be counted ('{before}'); stopping")
        at[side] = len(re.findall(r"\([^()]*\)", before))
    head = " ".join(header)
    for side in ("dem", "rep"):
        if not MO.has_ticket(head, c[side]):
            raise Stop(f"    {c['id']}: the table's heading does not name the ticket this loader was checked against ({c[side]}); stopping")
    pack = lambda v: {"dem": v[at["dem"]], "rep": v[at["rep"]], "other": sum(v) - v[at["dem"]] - v[at["rep"]], "total": sum(v)}   # noqa: E731
    return {"rows": {name: pack(v) for name, v in rows.items()}, "total": pack(total), "columns": n,
            "write_in_column": "Scatterings" in line or "Scattering" in line, "pages": [texts[start][0], last], "header": head}


def half_lines(path, first, last, mid=MID):
    """[(page, 'L' or 'R', text)]: the text of pages first..last read by halves, the left half of each page top to
    bottom and then the right, for tables printed two side by side."""
    from ballot import pdftext
    pdf = pdftext.PDF(open(path, "rb").read())
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        if n < first or n > last:
            continue
        runs = pdftext.page_runs(pdf, page, res)
        for side, mine in (("L", [r for r in runs if r[0] < mid]), ("R", [r for r in runs if r[0] >= mid])):
            grouped = []
            for r in sorted(mine, key=lambda r: (-round(r[1], 1), r[0])):
                if grouped and abs(grouped[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
                    grouped[-1][1].append(r)
                else:
                    grouped.append([r[1], [r]])
            out += [(n, side, t) for t in (pdftext.join(rs) for _y, rs in grouped) if t]
    return out


def district_counties(halves, counties):
    """{district: sorted county names} from the half-page lines of the 'Member of the Legislature' tables: under each
    'Legislative District N' heading, the counties of its rows. Only the district number and the county names are
    kept; a candidate's name is never read into anything."""
    find = row_finder(counties)
    out, cur = {}, None
    for _p, _side, t in halves:
        t = t.strip()
        m = re.match(r"^Legislative District\s*(\d+)\b", t)
        if m:
            cur = str(int(m.group(1)))
            if cur in out:
                raise Stop(f"    the canvass book lists Legislative District {cur} twice; stopping")
            out[cur] = set()
            continue
        if t.startswith("Member of ") or t.startswith("General Election"):
            cur = None if t.startswith("Member of ") and "Legislature" not in t else cur
            continue
        if cur is None:
            continue
        for name, _nums in find(t):
            if name != "Total":
                out[cur].add(name)
    return {d: sorted(v) for d, v in out.items()}


def legislature_pages(lines):
    """(first, last) pages of the book's 'Member of the Legislature' tables."""
    texts = [(p, t.strip()) for p, _y, t in lines]
    first = next((p for p, t in texts if t == "Member of the Legislature"), None)
    if first is None:
        raise ValueError("no section headed 'Member of the Legislature'")
    after = next((p for p, t in texts if p > first and t.startswith("Member of the State Board of Education") and "..." not in t), None)
    if after is None:
        raise ValueError("no section after the Legislature's")
    return first, after


def read_book(path, year, contests, counties, say):
    from ballot import pdftext
    lines = pdftext.lines(path)
    tables = {c["id"]: contest_table(lines, c, counties) for c in contests if c["year"] == year}
    districts, why = None, None
    if year >= PLAN_YEAR:
        try:
            first, last = legislature_pages(lines)
            districts = district_counties(half_lines(path, first, last), counties)
        except (ValueError, OSError) as e:
            why = str(e)
            say(f"      {year}: the Legislature tables could not be read ({e}); the districts rest on the Census Bureau's file alone")
    return tables, districts, why


# ---------------------------------------------------------------- the Clerk of the House, and the Census Bureau's block file

def clerk_figures(parsed, c):
    """The Clerk's Democratic and Republican figures for one contest. Nebraska elected two senators in 2024 and the
    Clerk lists both under one heading, so a senator's line is found by surname and party."""
    lines = parsed["sections"].get(c["clerk"]) or []
    if c["clerk"] == "FOR PRESIDENTIAL ELECTORS":
        dem = [v for s, v in lines if s.lower().startswith("democrat")]
        rep = [v for s, v in lines if s == "Republican"]
    else:
        side = lambda who, party: [v for s, v in lines if re.search(rf"\b{re.escape(who.split('/')[0])}\b", s)             # noqa: E731
                                   and s.rsplit(",", 1)[-1].strip().lower().startswith(party)]
        dem, rep = side(c["dem"], "democrat"), side(c["rep"], "republican")
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{c['clerk']}: {len(dem)} Democratic and {len(rep)} Republican lines for this contest, not one of each")
    return {"dem": dem[0], "rep": rep[0]}


def clerk_totals(contests, cache, refresh, say):
    out, docs = {}, []
    for year in sorted({c["year"] for c in contests if c.get("clerk")}, reverse=True):
        src = CLERK[year]
        rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
        path = os.path.join(cache, src["file"])
        try:
            if not os.path.exists(path):                       # a copy another state's loader already keeps is the same document
                near = sorted(glob.glob(os.path.join(os.path.dirname(cache), "*_local", src["file"])))
                if near:
                    os.makedirs(cache, exist_ok=True)
                    shutil.copyfile(near[0], path)
            net.download(src["url"], path, 0 if refresh else KEEP_DAYS, tries=2, say=say)
            parsed = MO.read_clerk(path, "NEBRASKA")
            where = parsed["where"].replace("Missouri", "Nebraska")
            rec.update(fetched=MO._day(path), sha256=MO._sha_file(path), where=where)
            for c in contests:
                if c["year"] == year and c.get("clerk"):
                    out[c["id"]] = dict(clerk_figures(parsed, c), source=src["id"], where=where)
        except Exception as e:  # noqa: BLE001  the canvass book is the first control; the Clerk's is said to be unread
            say(f"      {src['title']}: could not be read ({e}); the control rests on the canvass book")
            rec.update(unread=f"could not be read on {MO._now()}: {e}")
        docs.append(rec)
    return out, docs


def read_bef(cache, refresh, say):
    """{"districts": {district: {county FIPS: blocks}}, "file": {...}} for Nebraska. The national zip is large; a copy
    another state's loader already keeps is read where it is, and a small extract is kept here."""
    extract = os.path.join(cache, "census_bef_2024_ne_extract.json")
    if not refresh and os.path.exists(extract):
        with open(extract, encoding="utf-8") as fh:
            return json.load(fh)
    name, tag, url = BEF
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        near = sorted(glob.glob(os.path.join(os.path.dirname(cache), "*_local", name)))
        path = near[0] if near else fetch(url, path, refresh, say)
    table = collections.defaultdict(collections.Counter)
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.startswith(f"{STATE_FIPS}_") and tag in n] or [n for n in z.namelist() if n.startswith("National")]
        if len(members) != 1:
            raise Stop(f"    {name}: no one file for Nebraska or the nation in it; stopping")
        with z.open(members[0]) as raw:
            fh = io.TextIOWrapper(raw, encoding="utf-8-sig")
            fh.readline()
            for line in fh:
                if line.startswith(STATE_FIPS):
                    geoid, _, d = line.strip().partition(",")
                    if len(geoid) == 15 and d.isdigit():
                        table[str(int(d))][geoid[:5]] += 1
    doc = {"fetched": MO._now(),
           "file": {"file": name, "member": members[0], "url": url, "sha256": MO._sha_file(path), "on_disk_since": MO._day(path)},
           "districts": {d: dict(sorted(cs.items())) for d, cs in sorted(table.items(), key=lambda kv: int(kv[0]))}}
    say(f"      {name}: {sum(sum(cs.values()) for cs in table.values()):,} Nebraska blocks in {len(table)} districts")
    os.makedirs(cache, exist_ok=True)
    with open(extract + ".part", "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    os.replace(extract + ".part", extract)
    return doc


# ---------------------------------------------------------------- adding up

def few(rec):
    hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
    if hold:
        rec["too_few"] = hold
    return rec


def build(tables, book_districts, counties, bef, official, clerk=None, contests=CONTESTS, expect=True):
    """tables: {contest id: contest_table()}; book_districts: {year: {district: [county names]} or None}; counties:
    {name: FIPS}; bef: {district: {county FIPS: blocks}}; official: {contest id: {dem, rep, other, total, source,
    where, read}}. Returns (doc, failed)."""
    failed, ids = [], [c["id"] for c in contests]
    name_of = {f: f"{n} County" for n, f in counties.items()}
    places = {k: {} for k in KIND_NAMES}
    for name, f in sorted(counties.items(), key=lambda kv: kv[1]):
        places["county"][f] = few({"name": name_of[f], "votes": {cid: dict(tables[cid]["rows"][name]) for cid in ids}})
    state = {cid: dict(tables[cid]["total"]) for cid in ids}

    given = {k: [c["id"] for c in contests if c["year"] >= first] for k, first, *_ in KINDS}
    census = {d: sorted(cs) for d, cs in bef.items()}
    if expect and len(census) != SEATS:
        failed.append(f"{len(census)} legislative districts in the Census Bureau's file, not {SEATS}")
    whole = MO.whole_county_districts(census)
    in_book, differ = {}, []
    for year, ds in sorted((book_districts or {}).items()):
        for d, names in (ds or {}).items():
            in_book[d] = (year, sorted(counties[n] for n in names))
    if expect and book_districts and all(book_districts.values()) and len(in_book) != SEATS:
        failed.append(f"{len(in_book)} legislative districts in the canvass books' Legislature tables, not {SEATS}")
    for d, (year, cs) in in_book.items():
        if d not in census:
            failed.append(f"legislative district {d} is in the {year} canvass book and not in the Census Bureau's file")
        elif cs != census[d]:
            differ.append(d)
    whole = {d: cs for d, cs in whole.items() if d not in differ}
    for d in sorted(whole, key=int):
        votes = {}
        for cid in given["senate"]:
            v = {}
            for f in whole[d]:
                MO.add(v, places["county"][f]["votes"][cid])
            votes[cid] = v
        rec = {"name": f"Legislative District {d}", "counties": whole[d], "county_names": [name_of[f] for f in whole[d]], "votes": votes}
        rec["counties_read_from"] = (["census block file", f"{in_book[d][0]} canvass book"] if d in in_book else ["census block file"])
        places["senate"][d] = few(rec)
    not_given = sorted((d for d in census if d not in whole), key=int)

    per = {}
    for c in contests:
        mine, off = state[c["id"]], official[c["id"]]
        theirs = {k: off[k] for k in VOTE_KEYS}
        sums = {k: sum(p["votes"][c["id"]][k] for p in places["county"].values()) for k in VOTE_KEYS}
        diff = {k: mine[k] - theirs[k] for k in VOTE_KEYS if mine[k] != theirs[k]}
        per[c["id"]] = {"sum_of_counties": sums, "official": theirs, "equal": not diff and sums == mine, "source": off["source"],
                        "where": off["where"], "read": off["read"], "counties": len(tables[c["id"]]["rows"])}
        if diff:
            per[c["id"]]["difference"] = diff
            failed.append(f"{c['id']}: the table's Total row is {mine} and the figures to check it against are {theirs}; difference: {diff}")
        if sums != mine:
            failed.append(f"{c['id']}: the counties add up to {sums} and the Total row is {mine}")
        if expect and len(tables[c["id"]]["rows"]) != COUNTIES_N:
            failed.append(f"{c['id']}: {len(tables[c['id']]['rows'])} counties, not {COUNTIES_N}")
        ck = (clerk or {}).get(c["id"])
        if ck:
            ok = ck["dem"] == mine["dem"] and ck["rep"] == mine["rep"]
            per[c["id"]]["clerk"] = dict(ck, equal=ok)
            if not ok:
                failed.append(f"{c['id']}: the Clerk of the House gives {ck['dem']:,} Democratic and {ck['rep']:,} Republican votes; "
                              f"the canvass book {mine['dem']:,} and {mine['rep']:,}")
    notes = []
    if differ:
        notes.append(f"District{'s' if len(differ) > 1 else ''} {', '.join(sorted(differ, key=int))}: the canvass book and the Census Bureau's "
                     "block file do not list the same counties, so not given.")
    whole_note = ("made of whole counties only, by the Census Bureau's block file, and by the canvass book's Legislature tables wherever they "
                  "list the district; a district that shares a county is left out")
    ctl = {"result": "equal" if not failed else "differs",
           "statement": (f"For every contest all {COUNTIES_N} counties are present once; every column adds up to the Total row printed in the "
                         "table; the counties add up to that Total row; for President and U.S. Senator the Democratic and Republican totals "
                         "equal the Clerk of the U.S. House's statistics; and every legislative district given is whole counties."
                         if not failed else "The sums do not all agree; see the differences."),
           "counties": COUNTIES_N, "contests": per, "kinds": {"county": "equal to the statewide sum" if not failed else "see the differences",
                                                             "senate": whole_note}, "notes": notes}
    kinds = {}
    for kind, first, covers, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind], "covers_the_state": covers,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
    kinds["senate"].update(why_not_2020=WHY_NOT_2020, not_given=not_given,
                           note=(f"A district is given when every county it reaches lies wholly inside it; its votes are then its counties' "
                                 f"votes. {len(not_given)} of the {len(census)} districts share a county with another district; the official "
                                 "report has no results below the county, so those are not given and nothing is estimated. Nebraska has one "
                                 "chamber; its members are senators, elected without party labels."))
    records = []
    for c in contests:
        t = tables[c["id"]]
        records.append({"id": c["id"], "date": BOOKS.get(c["year"], {}).get("date", str(c["year"])), "office": c["office"],
                        "table": f"ne-sos-canvass-book-{c['year']}", "pages": t["pages"],
                        "kinds": [k for k in KIND_NAMES if c["id"] in given[k]],
                        "dem": {"party": "Democratic", "ticket": c["dem"], "column": "the column headed (Democratic)"},
                        "rep": {"party": "Republican", "ticket": c["rep"], "column": "the column headed (Republican)"},
                        "other": {"what": "every other candidate and all write-ins, together", "columns": t["columns"] - 2},
                        "total": {"what": "the candidates' columns added up; the book prints no total column"},
                        "statewide": dict(state[c["id"]]), "official_source": official[c["id"]]["source"]})
    doc = {"what": WHAT, "note": NOTE, "state": "NE", "generated": MO._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(VOTE_KEYS), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": ctl,
           "coverage": {"not_given": NOT_GIVEN, "districts_not_given": {"senate": not_given}, "why_no_precincts": SITE_NOTE},
           "sources": [], "places": places}
    return doc, failed


def our_places(db):
    """What our Nebraska places and races use, read only: {kind: ids}; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'ne-%'"):
            out[kind].add(pid)
        for (district,) in con.execute("SELECT district FROM sl_races WHERE state = 'NE' AND level = 'legislature' AND office_kind = 'state_senate'"):
            if district:
                out["senate"].add(str(district))
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Nebraska place votes: the Board of State Canvassers' official report (the canvass book), county by county")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    counties = read_counties(fetch(COUNTY_LIST[0], os.path.join(cache, COUNTY_LIST[1]), refresh, say))
    tables, book_districts, official, sources = {}, {}, {}, []
    for year in sorted(BOOKS, reverse=True):
        b = BOOKS[year]
        path = fetch(b["url"], os.path.join(cache, b["file"]), refresh, say)
        got, districts, why = read_book(path, year, CONTESTS, counties, say)
        tables.update(got)
        if year >= PLAN_YEAR:
            book_districts[year] = districts
        for cid, t in got.items():
            mine = t["total"]
            if mine != CHECKED[cid]:
                say(f"      {cid}: the canvass book now reads {mine}; this loader was checked against {CHECKED[cid]}")
            official[cid] = dict(mine, source=f"ne-sos-canvass-book-{year}", where=f"the Total row of the table on page {t['pages'][0]}",
                                 read=f"from the document on {MO._day(path)}")
        say(f"      {year}: " + ", ".join(f"{cid} {t['total']['total']:,}" for cid, t in got.items())
            + (f"; {len(districts)} legislative districts' counties" if districts else ""))
        rec = {"id": f"ne-sos-canvass-book-{year}", "kind": "official results by county", "agency": AGENCY, "title": b["title"], "url": b["url"],
               "listed_on": SOS_PAGE, "fetched": MO._day(path), "sha256": MO._sha_file(path),
               "read": "Of each county: its name and the votes of every candidate in the contests named here; of the tables for Member of "
                       "the Legislature only which counties each district lists."}
        if why:
            rec["legislature_tables_unread"] = why
        sources.append(rec)
    bef = read_bef(cache, refresh, say)
    sources.append({"id": "census-2024-legislative-bef", "kind": "official block equivalency file", "agency": "U.S. Census Bureau",
                    "title": "2024 State Legislative District Block Equivalency File, upper chamber (sldu24.zip)", "url": BEF[2], "file": bef["file"],
                    "read": "Of each Nebraska census block: its county and its legislative district. Used only to say which districts are whole counties."})
    sources.append({"id": "census-2020-counties", "kind": "official list of counties", "agency": "U.S. Census Bureau",
                    "title": "2020 FIPS codes for counties, Nebraska", "url": COUNTY_LIST[0], "sha256": MO._sha_file(os.path.join(cache, COUNTY_LIST[1]))})
    clerk, clerk_docs = clerk_totals(CONTESTS, cache, refresh, say)
    doc, failed = build(tables, book_districts, counties, bef["districts"], official, clerk)
    doc["sources"] = sources + clerk_docs
    if not all(c["id"] in clerk for c in CONTESTS if c.get("clerk")):
        doc["control"]["notes"].append("A Clerk of the House document could not be read at this run; for its contests the control is the canvass book alone.")
    doc["control"]["notes"].append("Governor is not in the Clerk's statistics; its control is the canvass book's own Total row: the county rows "
                                   "must add up to it, column by column. That is one document checked against itself, not two.")
    doc["control"]["notes"].append("The official figure each contest is compared with is the Total row of its own table in the canvass book; the "
                                   "Clerk of the House's figures are the second document.")
    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['senate'])} of {SEATS} legislative districts are whole counties")
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: counties "
            + ("equal to" if ctl["equal"] else "DIFFER from") + " the Total row"
            + (f"; the Clerk's two-party figures {'agree' if ctl['clerk']['equal'] else 'DIFFER'}" if "clerk" in ctl else ""))
    for note in doc["control"]["notes"]:
        if note.startswith("District"):
            say(f"      {note}")
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    Nebraska place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in ("county", "senate", "mcd"):
            ids = ours.get(kind, set())
            without = sorted((i for i in ids if not p.get(kind, {}).get(i, {}).get("votes")), key=MO.sort_key)
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}"
                + (f" (none for {', '.join(without[:12])}{' and more' if len(without) > 12 else ''})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {MO._now()}")
    MO.write(out, doc)
    say(f"    Nebraska place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e3:.0f} kB)")
    return doc


# ---------------------------------------------------------------- the reader and the arithmetic on made-up lines

def selftest(say=print):
    counties = {"Adams": "31001", "Box Butte": "31013", "Cass": "31025", "Douglas": "31055", "York": "31185"}
    text = """President and Vice President of the United States
Results by Congressional District
County (Republican) (Democratic) Scatterings
Total 1 1 1
President and Vice President of the United States
Ann Alpha Bo Beta Cy Gamma & Di
& Ed Epsilon & Flo Zeta Delta (Some Write-In
County (Republican) (Democratic) (Libertarian) Party) Scatterings
Total 145 219 9 3 2
Adams 30 20 2 0 1
Box Butte 25 0 0 0 0
Cass 40 60 3 1 0
General Election - November 5, 2024 Page | 11
Ann Alpha Bo Beta Cy Gamma & Di
County (Republican) (Democratic) (Libertarian) Party) Scatterings
Douglas 40 130 3 2 1
York 10 9 1 0 0
Member of the United States Senate - Two Year Term
Gil Eta Hal Theta Gil Eta Hal Theta
County (Republican) (Democratic) County (Republican) (Democratic)
Total 150 220 Douglas 45 131
Adams 31 21 York 9 9
Box Butte 25 0
Cass 40 59"""
    lines = [(11, 0.0, t) for t in text.split("\n")]
    c = {"id": "2024-president", "year": 2024, "office": "President", "heading": "President and Vice President of the United States",
         "after": None, "dem": "Beta/Zeta", "rep": "Alpha/Epsilon", "clerk": None}
    s = {"id": "2024-us-senate-special", "year": 2024, "office": "Senator", "heading": "Member of the United States Senate - Two Year Term",
         "after": None, "dem": "Theta", "rep": "Eta", "clerk": "FOR UNITED STATES SENATOR"}
    checks = []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    t = contest_table(lines, c, counties)
    u = contest_table(lines, s, counties)
    check("the table by congressional district is passed over", t["total"], {"dem": 219, "rep": 145, "other": 14, "total": 378})
    check("a table that runs over a page is one table", len(t["rows"]), 5)
    check("a county of two words is read", t["rows"]["Box Butte"], {"dem": 0, "rep": 25, "other": 0, "total": 25})
    check("a heading broken over two lines does not move the two tickets' columns", t["rows"]["Cass"], {"dem": 60, "rep": 40, "other": 4, "total": 104})
    check("a table printed two side by side is read across", (u["rows"]["York"], u["rows"]["Adams"]),
          ({"dem": 9, "rep": 9, "other": 0, "total": 18}, {"dem": 21, "rep": 31, "other": 0, "total": 52}))
    check("and its Total row is the one on the first line", u["total"], {"dem": 220, "rep": 150, "other": 0, "total": 370})
    halves = [(21, "L", x) for x in ("Member of the Legislature", "Legislative District 1", "Io Kay", "County Iota Kappa", "Total 9 9", "Adams 5 4",
                                     "Box Butte 4 5", "Legislative District3", "County Lo Mu", "Total 7 7", "Douglas 7 7")] + \
             [(21, "R", x) for x in ("Legislative District 2", "County Nu Xi", "Total 8 8", "Cass 3 3", "Douglas 5 5")]
    d = district_counties(halves, counties)
    check("a district's counties are read from its own table, by halves", d, {"1": ["Adams", "Box Butte"], "3": ["Douglas"], "2": ["Cass", "Douglas"]})
    official = {x["id"]: dict(y["total"], source="x", where="-", read="-") for x, y in ((c, t), (s, u))}
    bef = {"1": {"31001": 5, "31013": 4}, "2": {"31025": 3, "31055": 9}, "3": {"31055": 4}, "4": {"31185": 2}}
    clerk = {s["id"]: {"dem": 220, "rep": 150, "source": "y", "where": "-"}}
    doc, failed = build({c["id"]: t, s["id"]: u}, {2024: d}, counties, bef, official, clerk, [c, s], expect=False)
    p = doc["places"]
    check("the control holds on the made-up tables", (doc["control"]["result"], failed), ("equal", []))
    check("a district of whole counties is its counties added up", p["senate"]["1"]["votes"][c["id"]], {"dem": 20, "rep": 55, "other": 3, "total": 78})
    check("a district that shares a county is not given", (sorted(p["senate"]), doc["kinds"]["senate"]["not_given"]), (["1", "4"], ["2", "3"]))
    check("a district the book does not list rests on the Census file, and says so", p["senate"]["4"]["counties_read_from"], ["census block file"])
    check("a place where every vote went one way is marked too_few", p["county"]["31013"].get("too_few"), [c["id"], s["id"]])
    check("a place of fewer than twenty votes is marked too_few", p["county"]["31185"].get("too_few"), [s["id"]])
    check("a place of twenty votes or more, not all one way, is not", p["county"]["31001"].get("too_few"), None)
    d2 = dict(d, **{"1": ["Adams"]})
    doc2, _f = build({c["id"]: t, s["id"]: u}, {2024: d2}, counties, bef, official, clerk, [c, s], expect=False)
    check("a district the book lists otherwise than the Census file is left out", sorted(doc2["places"]["senate"]), ["4"])
    wrong = dict(clerk, **{s["id"]: dict(clerk[s["id"]], dem=221)})
    check("a Clerk's figure that differs is caught", build({c["id"]: t, s["id"]: u}, {2024: d}, counties, bef, official, wrong, [c, s], expect=False)[0]
          ["control"]["result"], "differs")
    for what, old, new in (("a column that does not add up to the Total row stops the loader", "Adams 30 20 2 0 1", "Adams 31 20 2 0 1"),
                           ("a county missing from the table stops the loader", "York 10 9 1 0 0", "Yorke 10 9 1 0 0")):
        try:
            contest_table([(11, 0.0, x.replace(old, new)) for x in text.split("\n")], c, counties)
            caught = False
        except Stop:
            caught = True
        check(what, caught, True)
    try:
        contest_table(lines, dict(c, dem="Alpha/Epsilon", rep="Beta/Zeta"), counties)
        caught = False
    except Stop:
        caught = True
    check("the heading names both tickets, so tickets typed under the other party pass it (the Clerk's figures catch that)", caught, False)
    try:
        contest_table(lines, dict(c, dem="Omega"), counties)
        caught = False
    except Stop:
        caught = True
    check("a ticket the heading does not name stops the loader", caught, True)
    parsed = {"sections": {"FOR UNITED STATES SENATOR": [("Gil Eta, Republican", 150), ("Hal Theta, Democrat", 220), ("Pat Rho, Republican", 99),
                                                         ("Sam Tau, By Petition", 80)]}}
    check("of two Senate elections under one heading the Clerk's line is found by surname", clerk_figures(parsed, s), {"dem": 220, "rep": 150})
    check("the note never calls these precinct results", bool(re.search(r"\bprecinct results\b", WHAT + " " + NOTE, re.I)), False)
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Nebraska place voted in past partisan general elections -> ballot/lean/ne_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/ne_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/ne_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every document again, even when the cached copies are there")
    ap.add_argument("--selftest", action="store_true", help="check the reader and the arithmetic on made-up lines; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
