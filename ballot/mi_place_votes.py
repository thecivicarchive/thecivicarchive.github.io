"""
ballot/mi_place_votes.py - how each Michigan place voted in past partisan general elections, added up from the Bureau
of Elections' official precinct results, so a page can show the record of a county, a city or township, or a state
House district without anyone labelling a candidate. Michigan's twin of ballot/mn_place_votes.py; the file it writes
has the same shape.

    python ballot/mi_place_votes.py               reads the saved files, writes ballot/lean/mi_place_votes.json
    python ballot/mi_place_votes.py --out x.json  writes somewhere else; --cache DIR reads the saved files from somewhere else
    python ballot/mi_place_votes.py --trial x.json   the whole loader on the 2018 general election (see below); never the real file
    python ballot/mi_place_votes.py --selftest    the arithmetic on made-up tables; reads and downloads nothing

Where the files come from
-------------------------
Michigan's Bureau of Elections publishes, for each general election, a precinct file (<year>GEN.zip: tab-delimited
votes, names, offices, cities and counties, with a readme giving the layout) and a county file ("County Results":
election_result_<year>GEN.txt, one row for each candidate in each county, whose last line says RESULTS: OFFICIAL). Both
are on the Michigan Voter Information Center (mvic.sos.state.mi.us/votehistory), which refuses scripts. This loader
never requests that site and works around nothing: it downloads no file of the Bureau's and reads what is in
states_cache/mi_local/. The files of 2024, 2022 and 2020 there were read through a browser on 2026-10-02 from the
Center's own links, "Download Precinct Results" (VoteHistory/GetPrecinctResultsFile?electionId=699, 691 and 683) and
the "County Results" download (VoteHistory/GetElectionResultFile?electionId=699, 691 and 683), and saved under the
Bureau's own names. Their SHA-256 fingerprints are typed in SAVED; the file this loader writes gives the fingerprint
of every file it read and says of each whether it is one of those. (The Bureau's old file host, miboecfr.nictusa.com,
is gone: the name now belongs to a people-search site, which this kit must never request, and this loader never does.)

The reader was first proved on the 2018 files, which the Internet Archive kept at the Bureau's own addresses:
--trial runs everything on them. If a file's layout differs from the readme's, the loader stops and says where. Two
differences found in the newer files are handled: the 2024 tables begin with a UTF-8 byte-order mark, and the 2024
county file numbers its offices otherwise than the precinct file does (U.S. Senator is 7 there and 5 in the precinct
file), so an office is found in the county file by its description, never by its number.

What it is, and is not
----------------------
For President and U.S. Senator in 2024, Governor in 2022, and President and U.S. Senator in 2020: the votes for the
Democratic ticket, the Republican ticket, everyone else together (write-ins as the file carries them) and the total,
for counties, cities and townships, and (2024 only) state House districts made of whole precincts, wherever the
control below holds. It is how the people of a place voted then, on the precinct and district lines in force at that
election. It is not a prediction, it says nothing about any candidate on a later ballot or about any voter, and it
turns no nonpartisan office into a partisan one. No database is opened for writing; ballot_local_2026.sqlite is opened
read-only at the end, only to count how many of our places are covered.

  - A county is the Bureau's county code (1 to 83, alphabetical), which is the Census code 26 and twice the number
    less one; the names must agree with the Census Bureau's list or the loader stops.
  - A city or township is the Bureau's "city/town" of a county, matched to the Census Bureau's county subdivision of
    the same name and kind in the same county (one fit only; "charter" set aside on both sides, since the 2024 file
    writes "Shelby Charter Township" where earlier files wrote "Shelby Township"; a city whose name ends in City, or
    that the Census calls "Village of X city", tried both ways). A city in two counties is one place. One that does
    not match is left out and listed, with its votes counted in the control. Villages are not given: a village votes
    in its township's precincts and the file has no village column.
  - Each county's "{Statistical Adjustments}" row (city code 9999) belongs to the county and to no city or district.
  - A precinct's state House district is the one whose "Representative in State Legislature" contest it has votes in;
    the file has no district column. A precinct with votes in two such contests is split, and a district it touches is
    NOT given; so is a district that shares a city or township with a precinct that has votes for the contest and none
    for the House. Nothing is shared out or estimated. Districts are given for 2024 only (HOUSE_YEAR): the 2022
    election was held on the Commission's first plan, and the plan redrawn by court order was first used in 2024.
  - State Senate districts are not given: the Senate was last elected in 2022, on lines redrawn by court order for
    2026, and a precinct's place on the new lines cannot be read from these files.
  - Of candidates only the two tickets' surnames are kept, to say which election this was; they must be the surnames
    typed in CONTESTS under the party the file gives, or the loader stops.

Some places have a handful of voters. There the split comes close to saying how particular people voted; the counts
stay in the file (the sums must be checkable) but each such contest is listed in the place's "too_few".

The control, county by county
-----------------------------
The Bureau's precinct files do not everywhere add up to the Bureau's own official county totals, so the control is
held county by county and nothing is given where it fails:

  - For each contest every county's precinct rows (its statistical adjustments with them) are added up and compared,
    candidate by candidate, with that county's rows in the Bureau's county file for the election.
  - Where the two are exactly equal the contest is given for the county, for the cities and townships in it and for a
    House district made of its precincts. Where they are not, the contest is LEFT OUT for that county, for every city
    and township with a precinct in it (a city in two counties is left out if either county fails) and for every House
    district reaching into it. The file lists each such county with both figures and the difference, in a sentence
    (coverage.counties_left_out). No number is changed, shared out or estimated to make anything fit.
  - The statewide line is stated as it is: the precinct files' sum, the official statewide total, and either "equal"
    or the difference and the counties it comes from. The official statewide totals are, for President and U.S.
    Senator, the Clerk of the U.S. House's "Statistics of the Presidential and Congressional Election" (Michigan page,
    read from the PDF with ballot/pdftext.py), and for Governor in 2022 the Bureau's own "2022 Michigan Election
    Results" page (STATE GENERAL, OFFICIAL, 83 of 83 counties) as the Internet Archive kept it on 2026-08-04, of which
    only each row's party and votes are kept. The county file's own sum is compared with that total as well; if the
    two ever disagree the file says so, gives no statewide figure for the contest and does not say which is right.
  - A contest's "statewide" figure in the file is the official statewide total (which the precinct files equal, or
    fall short of by the difference stated).

Nothing at all is written if the arithmetic itself fails (the counties, or the cities, townships, places left out and
adjustments, do not add up to the sum of the precinct rows), if a county file is not on disk or does not hold the
number of records its last line says, or if the two files do not name the counties or number the two tickets alike.

What the comparison found on 2026-10-02 (the file states the figures; this is only where to look):
  - 2024, President and U.S. Senator: 81 of 83 counties equal. Allegan is 14 votes short and Van Buren 14 over (10
    Democratic, 4 Republican), which cancel: the statewide sums equal the Clerk's.
  - 2022, Governor: 15 of 83 counties equal. In 58 counties only the smaller parties' and write-in candidates' counts
    differ (mostly a handful of votes short in the precinct file; Isabella 323 over); in 10 (Bay, Berrien, Branch,
    Midland, Newaygo, Oceana, St. Joseph, Sanilac, Van Buren, Washtenaw) the Democratic or Republican count differs
    too. Statewide the precinct file is 866 votes short of the official total.
  - 2020, President and U.S. Senator: 73 of 83 counties equal. Clinton (1,248 and 1,249 short) and Eaton (1,991 and
    1,972 short) carry nearly all of the statewide shortfall (3,285 and 3,224): their statistical-adjustment rows in
    the precinct file subtract exactly those votes. Allegan, Clare, Isabella, Kalamazoo, Lapeer, St. Clair, Sanilac
    and Van Buren differ by 1 to 57 votes.
In all five contests the Bureau's county file adds up exactly to the official statewide total. Several of the 2020 and
2024 counties share a city with a neighbour that differs the other way (South Haven lies in Allegan and Van Buren,
Clare in Clare and Isabella, Brown City in Lapeer and Sanilac; Lansing reaches into Eaton and East Lansing into
Clinton), which may mean the two files put such a city's votes under its counties differently. That is a guess; the
loader assumes nothing of the kind and moves no vote.
"""

import argparse
import collections
import gzip
import io
import json
import os
import pathlib
import re
import sqlite3
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402
from ballot import mn_place_votes as M  # noqa: E402  the shared small things: the file writer, fingerprints, Stop
from ballot import wi_place_votes as W  # noqa: E402  the reader of the Clerk of the House's statistics

METHOD = "1.1"                 # change how anything is added up or matched, and this goes up (1.1: the control county by county)
CACHE = os.path.join(HERE, "states_cache", "mi_local")
OUT = os.path.join(HERE, "ballot", "lean", "mi_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
COUSUB = os.path.join(HERE, "ballot_cache", "mi", "local", "census_st26_mi_cousub2020.txt")
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st26_mi_cousub2020.txt"
STATE_FIPS = "26"
FEW = 20
HOUSE_YEAR = 2024              # the election whose House plan our 2026 races are on
HOUSE_OFFICE = "8"
ADJUST = "9999"                # the Bureau's city code for a county's statistical adjustments
AGENCY = "Michigan Department of State, Bureau of Elections"
RESULTS_PAGE = "https://mvic.sos.state.mi.us/votehistory/"
WAYBACK = "https://web.archive.org/web/{stamp}id_/{url}"
NEEDED = (2024, 2022)          # without these no file is written; 2020 is added when it is there

# The office in the Bureau's county file is found by its description (county_office), never by its number: the 2024
# county file numbers its offices otherwise than the precinct file does. "Governor 4 Year Term" is not "Governor of
# Wayne State University".
PRESIDENT, SENATOR, GOVERNOR = r"\bPRESIDENT\b", r"^UNITED STATES SENATOR\b", r"^GOVERNOR \d+ YEAR TERM\b"
CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States",
     "code": "1", "dem": "Harris", "rep": "Trump", "official": "clerk-statistics-2024", "section": "FOR PRESIDENTIAL ELECTORS", "county_office": PRESIDENT},
    {"id": "2024-us-senate", "year": 2024, "date": "2024-11-05", "office": "United States Senator",
     "code": "5", "dem": "Slotkin", "rep": "Rogers", "official": "clerk-statistics-2024", "section": "FOR UNITED STATES SENATOR", "county_office": SENATOR},
    {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor and Lieutenant Governor",
     "code": "2", "dem": "Whitmer", "rep": "Dixon", "official": "mi-boe-results-page-2022", "section": "Governor 4 Year Term", "county_office": GOVERNOR},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States",
     "code": "1", "dem": "Biden", "rep": "Trump", "official": "clerk-statistics-2020", "section": "FOR PRESIDENTIAL ELECTORS", "county_office": PRESIDENT},
    {"id": "2020-us-senate", "year": 2020, "date": "2020-11-03", "office": "United States Senator",
     "code": "5", "dem": "Peters", "rep": "James", "official": "clerk-statistics-2020", "section": "FOR UNITED STATES SENATOR", "county_office": SENATOR},
]
# The trial: the same loader on the last election whose precinct file the Internet Archive kept.
TRIAL = [
    {"id": "2018-governor", "year": 2018, "date": "2018-11-06", "office": "Governor and Lieutenant Governor",
     "code": "2", "dem": "Whitmer", "rep": "Schuette", "official": "mi-boe-county-file-2018", "section": None, "county_office": GOVERNOR},
    {"id": "2018-us-senate", "year": 2018, "date": "2018-11-06", "office": "United States Senator",
     "code": "5", "dem": "Stabenow", "rep": "James", "official": "clerk-statistics-2018", "section": "FOR UNITED STATES SENATOR", "county_office": SENATOR},
]
ARCHIVED = {  # the Bureau's own files as the Internet Archive kept them, at the Bureau's own addresses of the time
    "2018GEN.zip": ("20240927070648", "https://miboecfr.nictusa.com/cfr/presults/2018GEN.zip"),
    "election_result_2018GEN.txt": ("20260429222549", "https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId=676"),
    "mvic_votehistory_2022-11-08.html": ("20260804145543", "https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-8-2022"),
}
# The Bureau's files of 2024, 2022 and 2020 as they were read through a browser on SAVED_ON from the Michigan Voter
# Information Center's own download links (the site refuses scripts and this loader never requests it): the link, and
# the SHA-256 of the bytes saved. A file on disk with another fingerprint is said to be a copy saved by hand.
SAVED_ON = "2026-10-02"
PRECINCT_LINK = "https://mvic.sos.state.mi.us/VoteHistory/GetPrecinctResultsFile?electionId={n}"
COUNTY_LINK = "https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId={n}"
SAVED = {
    "2024GEN.zip": (PRECINCT_LINK.format(n=699), "64f9285bbe94565ff8685d90fccb283a72f04f849bc3b16873af26e9ae34294a"),
    "2022GEN.zip": (PRECINCT_LINK.format(n=691), "0e1fd0a2ab5848eccb56bae9d5e5b4d192f98f414b3ea26b134e2c1e713144fa"),
    "2020GEN.zip": (PRECINCT_LINK.format(n=683), "7338b2419b0b7a9726cd2bdef0ee2853f72495991843bab351d7ac1f1b929c17"),
    "election_result_2024GEN.txt": (COUNTY_LINK.format(n=699), "4378742b9214d6c05ba87bcdba867000951acb43a308537ae9e619947fc3d1eb"),
    "election_result_2022GEN.txt": (COUNTY_LINK.format(n=691), "8f3c555e8be7e77f7050b9e3a922164bd37c508e9a1c6be69f3dfea1fcaf11cb"),
    "election_result_2020GEN.txt": (COUNTY_LINK.format(n=683), "b16680c2363ac27104ba0cd5ec149345e6861b0851430ddbee05e75bbc3aef12"),
}
CLERK = "https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf"
CLERK_DATES = {2024: "November 5, 2024", 2020: "November 3, 2020", 2018: "November 6, 2018"}

KINDS = [
    ("county", "Counties", "five-digit county FIPS code, as sl_places kind county"),
    ("mcd", "Cities and townships", "MI-M- and the five-digit Census county-subdivision code, as sl_places kind mcd"),
    ("house", "State House districts of the plan first used in 2024", "district number, as the district of our House races"),
]
WHAT = ("How each Michigan place voted in past partisan general elections: the votes for the Democratic ticket, the Republican ticket, "
        "everyone else together (write-ins as the file carries them) and the total, added up from the Michigan Bureau of Elections' official "
        "precinct results.")
NOTE = ("What this is: how the people of a place voted in that election, in the Bureau of Elections' official precinct results, added up "
        "here by county, by city or township and, for 2024, by state House district, on the precinct and district lines in force at that "
        "election. A contest is shown for a place only where its county's precincts add up exactly to the Bureau's own official total for "
        "that county; where they do not, the contest is left out rather than shown with figures that do not match. "
        "What this is not: it is not a prediction of any election; it says nothing about any candidate on a later ballot or about "
        "any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where land was annexed or a district was "
        "redrawn, the figures are for the lines of that year. A village votes in its township's precincts, so villages are not given. A House "
        "district is given only when it is made of whole precincts; nothing is shared out or estimated. The tickets are named only to say "
        "which election this was. In a place with very few voters the split would come close to saying how particular people voted; those "
        "contests are listed in the place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every "
               "other candidate, write-ins as the file carries them) and total. Minnesota's file calls the first count dfl. A contest a "
               "place does not have was not held on its lines, or is not given for it.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Villages (a village votes in its township's precincts); State Senate districts (last elected in 2022, on lines redrawn by court "
             "order for 2026); House districts for 2022 and 2020 (other plans); wards and single precincts; school districts (the file does "
             "not say which a precinct is in).")
JOHN = ("In a browser open {page} and choose the November general election of {years}. \"Download Precinct Results\" gives the precinct "
        "file (a zip holding <year>vote.txt, <year>name.txt, <year>offc.txt, <year>city.txt and county.txt), saved as <year>GEN.zip; the "
        "\"County Results\" download gives the county file, saved as election_result_<year>GEN.txt. Missing from states_cache/mi_local/: "
        "{files}. The site refuses scripts, so this loader does not request it.")
WHY_NOT = ("Where a contest is missing here, the precincts of the county do not add up exactly to the Bureau of Elections' own official total "
           "for that county in that contest, so it is left out rather than shown with figures that do not match.")
WHY_NOT_MCD = ("Where a contest is missing here, the precincts of a county this place lies in do not add up exactly to the Bureau of Elections' "
               "own official total for that county in that contest, so it is left out rather than shown with figures that do not match.")
Stop = M.Stop
VOTE = ("dem", "rep", "other", "total")
SIDES = (("dem", "Democratic"), ("rep", "Republican"), ("other", "other"))


# ---------------------------------------------------------------- reading the Bureau's files

def bare(name):
    """A name for comparing only: lower case, letters and digits, St. as Saint, Mt. as Mount, Gd. as Grand."""
    s = re.sub(r"\bst\.?\s", "saint ", re.sub(r"\bmt\.?\s", "mount ", re.sub(r"\bgd\.?\s", "grand ", (name or "").lower() + " ")))
    return re.sub(r"[^a-z0-9]", "", s)


def read_precinct_zip(path, year, offices):
    """The Bureau's <year>GEN.zip, as its readme lays it out. Returns {counties, cities, parties, surnames, house, rows}:
    rows are (office, district, candidate id, county, city, ward, precinct, label, votes) for the offices asked for and
    the State House; of candidates only the party is kept, and the surname of a Democratic or Republican candidate for
    an office asked for."""
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise Stop(f"    {os.path.basename(path)} is not a zip file ({e}); save the Bureau's precinct file again")
    members = {n.lower().rsplit("/", 1)[-1]: n for n in z.namelist()}

    def table(suffix, least):
        fits = [n for k, n in members.items() if k == suffix or k == f"{year}{suffix}"]
        if len(fits) != 1:
            raise Stop(f"    {os.path.basename(path)}: {len(fits)} files named like {year}{suffix}, not one; the layout is not the one "
                       "this loader was proved on (2018). Nothing was read.")
        with z.open(fits[0]) as peek:      # the 2024 tables begin with a UTF-8 byte-order mark; 2018 to 2022 have none
            marked = peek.read(3) == b"\xef\xbb\xbf"
        for line in io.TextIOWrapper(z.open(fits[0]), encoding="utf-8-sig" if marked else "latin-1", newline=""):
            f = [c.strip() for c in line.rstrip("\r\n").split("\t")]
            if len(f) >= least and any(f):
                yield f

    def mine(f):
        if f[0] != str(year) or f[1].upper() != "GEN":
            raise Stop(f"    {os.path.basename(path)}: a row is for {f[0]} {f[1]}, not the {year} general election; stopping")
        return f
    counties = {f[0]: f[1] for f in table("county.txt", 2)}
    cities = {(f[2], f[3]): f[4] for f in map(mine, table("city.txt", 5))}
    want = set(offices) | {HOUSE_OFFICE}
    parties, surnames = {}, collections.defaultdict(list)
    for f in map(mine, table("name.txt", 10)):
        if f[2] in want:
            parties[(f[2], f[3], f[5])] = f[9].upper()
            if f[2] in offices and f[9].upper() in ("DEM", "REP"):
                surnames[(f[2], f[9].upper())].append(f[6])
    house = {f[3]: f[5] for f in map(mine, table("offc.txt", 6)) if f[2] == HOUSE_OFFICE}
    rows = []
    for f in map(mine, table("vote.txt", 12)):
        if f[2] in want:
            try:
                n = int(f[11])
            except ValueError:
                raise Stop(f"    {os.path.basename(path)}: a precinct's votes read {f[11]!r}, not a number; stopping")
            if (f[2], f[3], f[5]) not in parties:
                raise Stop(f"    {os.path.basename(path)}: votes for a candidate number the names file does not have; stopping")
            rows.append((f[2], f[3], f[5], f[6], f[7], f[8], f[9], f[10], n))
    return {"counties": counties, "cities": cities, "parties": parties, "surnames": dict(surnames), "house": house, "rows": rows}


def read_cousub(path):
    """{county fips3: (county name, [(code, name)])} from the Census Bureau's 2020 county-subdivision code list."""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh.read().splitlines()[1:]:
            p = line.split("|")
            if len(p) >= 8 and p[1] == STATE_FIPS:
                e = out.setdefault(p[2], (p[3], []))
                if p[7] != "Z9":
                    e[1].append((p[4], p[6]))
    return out


def match_city(desc, subs):
    """The Census county subdivision a Bureau "city/town" description names: (code, name) or None. One fit only.
    "Charter" is set aside on both sides: the 2024 file writes SHELBY CHARTER TOWNSHIP (once CHARTER TWP) where the
    earlier files wrote SHELBY TOWNSHIP, and the Census Bureau writes "Shelby charter township"."""
    m = re.match(r"^(.*\S)\s+CHARTER\s+(TOWNSHIP|TWP)\.?$", desc.strip(), re.I) or re.match(r"^(.*\S)\s+(TOWNSHIP|CITY)$", desc.strip(), re.I)
    if not m:
        return None
    kind = "city" if m.group(2).lower() == "city" else "township"
    tries = [bare(m.group(1))] + ([bare(desc), bare("village of " + m.group(1))] if kind == "city" else [])
    for want in tries:
        fits = [(c, n) for c, n in subs if n.lower().endswith(" " + kind)
                and bare(re.sub(r"\s+(charter\s+)?township$|\s+city$", "", n, flags=re.I)) == want]
        if len(fits) == 1:
            return fits[0]
        if len(fits) > 1:
            return None
    return None


def house_number(code, desc):
    """'00100' and '1ST DISTRICT REPRESENTATIVE IN STATE LEGISLATURE ...' -> '1'; the two must agree."""
    m = re.match(r"^\s*(\d+)(?:ST|ND|RD|TH)\s+DISTRICT\s+REPRESENTATIVE IN STATE LEGISLATURE", desc or "", re.I)
    n = int(code) // 100 if code.isdigit() else None
    if not m or n != int(m.group(1)):
        raise Stop(f"    a State House contest is coded {code!r} and described as {desc!r}; the two do not agree, stopping")
    return str(n)


# ---------------------------------------------------------------- the official totals

def split_official(lines, what):
    """[(party, votes)] -> the four counts; one Democratic and one Republican line, or it stops."""
    dem = [v for p, v in lines if p.lower().startswith("democrat")]
    rep = [v for p, v in lines if p.lower() == "republican"]
    if len(dem) != 1 or len(rep) != 1:
        raise ValueError(f"{what}: {len(dem)} Democratic and {len(rep)} Republican lines, not one of each")
    total = sum(v for _p, v in lines)
    return {"dem": dem[0], "rep": rep[0], "other": total - dem[0] - rep[0], "total": total}


def read_results_page(path, heading):
    """The Bureau's official results page: for the office whose band begins with `heading`, each row's party and votes
    (nothing else is kept), and the page's own line saying what it is."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        t = fh.read()
    status = re.search(r"<b>Type:</b>\s*([^<]+?)\s*</div>", t)
    counties = re.search(r"<b>Counties:</b>\s*(\d+)/(\d+)", t)
    if not status or "OFFICIAL" not in status.group(1).upper() or "UNOFFICIAL" in status.group(1).upper() or not counties or counties.group(1) != counties.group(2):
        raise ValueError("the page does not say OFFICIAL with every county in")
    bands = [(m.start(), M._text(m.group(1))) for m in re.finditer(r'<div class="row" style="font-weight: 500;[^"]*background:[^"]*">(.*?)</div>', t, re.S)]
    mine = [i for i, (_s, title) in enumerate(bands) if title.lower().startswith(heading.lower())]
    if len(mine) != 1:
        raise ValueError(f"{len(mine)} bands on the page begin with {heading}, not one")
    start = bands[mine[0]][0]
    end = bands[mine[0] + 1][0] if mine[0] + 1 < len(bands) else len(t)
    rows = re.findall(r'<div class="col-md-2"[^>]*>([^<]*)</div>\s*<div class="col-md-4"[^>]*>[^<]*</div>\s*<div class="col-md-2 text-right"[^>]*>([\d,]+)</div>',
                      t[start:end])
    if not rows:
        raise ValueError(f"no rows of votes under {heading}")
    return {"lines": [(p.strip(), int(v.replace(",", ""))) for p, v in rows], "status": f"{status.group(1).strip()}, {counties.group(1)} of {counties.group(2)} counties"}


def parse_county_file(lines, wanted):
    """The Bureau's county file ("County Results"), from its lines. `wanted` is {the precinct file's office code: a
    pattern for the office's description here}: the county file's own office numbers are not the precinct file's in
    every year, so the office is found by its description among the statewide rows, and exactly one office must fit.
    Returns {votes: {office code as asked: {county code: {candidate id: votes}}}, party: {(office code, candidate id):
    party}, county: {county code: name}, office: {office code: the description found}, records, status}. The data rows
    must be as many as the file's last line says (RECORDS: n), or it stops. Candidates' names are not kept."""
    head = next((i for i, l in enumerate(lines[:5]) if l.startswith("ElectionDate\t")), None)
    if head is None:
        raise ValueError("no heading row")
    col = {re.sub(r"\(.*", "", n).strip(): i for i, n in enumerate(lines[head].split("\t"))}
    need = ("OfficeCode", "DistrictCode", "StatusCode", "CountyCode", "CountyName", "OfficeDescription", "PartyDescription", "CandidateID", "CandidateVotes")
    if any(n not in col for n in need):
        raise ValueError("the heading row has changed")
    last = max(i for i, l in enumerate(lines) if l.strip())
    m = re.match(r"^RECORDS:\s*(\d+)\s+RESULTS:\s*(\S.*?)\s*$", lines[last])
    if not m:
        raise ValueError("the last line does not give the number of records and the status of the results")
    rows = [l.split("\t") for l in lines[head + 1:last] if l.strip()]
    if len(rows) != int(m.group(1)) or any(len(f) <= max(col[n] for n in need) for f in rows):
        raise ValueError(f"{len(rows):,} whole rows, and the last line says {int(m.group(1)):,} records: the file is cut short or changed")
    statewide = [f for f in rows if f[col["DistrictCode"]].strip("0") == ""]
    votes, party, county, office = {}, {}, {}, {}
    for code, pattern in wanted.items():
        fits = sorted({(f[col["OfficeCode"]], f[col["StatusCode"]], f[col["OfficeDescription"]].strip()) for f in statewide
                       if re.search(pattern, f[col["OfficeDescription"]].strip(), re.I)})
        if len(fits) != 1:
            raise ValueError(f"{len(fits)} statewide offices are described like {pattern}, not one")
        office[code] = fits[0][2]
        votes[code] = collections.defaultdict(dict)
        for f in statewide:
            if (f[col["OfficeCode"]], f[col["StatusCode"]], f[col["OfficeDescription"]].strip()) != fits[0]:
                continue
            cc, cand = f[col["CountyCode"]].strip(), f[col["CandidateID"]].strip()
            if cand in votes[code][cc]:
                raise ValueError(f"county {cc} has two rows for one candidate of {fits[0][2]}")
            votes[code][cc][cand] = int(f[col["CandidateVotes"]])
            if party.setdefault((code, cand), f[col["PartyDescription"]].strip()) != f[col["PartyDescription"]].strip():
                raise ValueError(f"a candidate of {fits[0][2]} has two parties")
            if county.setdefault(cc, f[col["CountyName"]].strip()) != f[col["CountyName"]].strip():
                raise ValueError(f"county {cc} has two names")
    return {"votes": votes, "party": party, "county": county, "office": office, "records": len(rows), "status": m.group(2)}


def read_county_file(path, wanted):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return parse_county_file(fh.read().splitlines(), wanted)


def side_of(party):
    """dem, rep or other, from the precinct file's party code (DEM, REP) or the county file's description."""
    p = (party or "").strip().lower()
    return "dem" if p == "dem" or p.startswith("democrat") else "rep" if p in ("rep", "republican") else "other"


def came_from(name, path):
    """(the address a file of the Bureau's came from, how it was read), said only as far as the bytes on disk bear out."""
    if name in SAVED:
        url, sha = SAVED[name]
        if M._sha_file(path) == sha:
            return url, (f"the Michigan Voter Information Center's own download link, read through a browser on {SAVED_ON} because the site "
                         "refuses scripts (this loader never requests it); the SHA-256 says which bytes were read")
        return url, (f"a copy saved by hand, on disk since {M._day(path)}; it is not the copy this loader was checked against on {SAVED_ON}, "
                     "whose SHA-256 differs")
    if name in ARCHIVED:
        stamp, url = ARCHIVED[name]
        return url, f"the Internet Archive's copy of {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}, taken at the Bureau's own address of the time"
    return RESULTS_PAGE, "a copy saved by hand from the Bureau's results site, which refuses scripts"


def fetch_archived(name, cache, say):
    """One of the Bureau's files the Internet Archive kept (ARCHIVED), saved under `name` in the cache. A copy already
    on disk (John's, or an earlier fetch) is used as it is."""
    path = os.path.join(cache, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    stamp, url = ARCHIVED[name]
    data = net.get(WAYBACK.format(stamp=stamp, url=url))
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    os.makedirs(cache, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    say(f"      {name}: the Internet Archive's copy of {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} ({len(data):,} bytes)")
    return path


def official_totals(contests, tables, cache, say):
    """{contest id: the four counts, source, where, read} and the documents' records; also the county files on disk."""
    out, docs, county_files = {}, {}, {}
    for year in sorted({c["year"] for c in contests}):
        name = f"election_result_{year}GEN.txt"
        path = os.path.join(cache, name)
        if not os.path.exists(path) and name in ARCHIVED:
            try:
                fetch_archived(name, cache, say)
            except OSError as e:
                say(f"      {name}: the Archive's copy could not be fetched ({e})")
        if os.path.exists(path):
            try:
                cf = read_county_file(path, {c["code"]: c["county_office"] for c in contests if c["year"] == year})
            except ValueError as e:
                raise Stop(f"    {name}: {e}; nothing is written without the county control")
            county_files[year] = (path, cf)
            url, how = came_from(name, path)
            docs[f"mi-boe-county-file-{year}"] = {
                "id": f"mi-boe-county-file-{year}", "kind": "official results by county", "agency": AGENCY,
                "title": f"{year} Michigan General Election, County Results ({name})", "url": url,
                "fetched": M._day(path), "sha256": M._sha_file(path), "read_from": how,
                "records": cf["records"], "accuracy": f"The file's own last line: RECORDS: {cf['records']}, RESULTS: {cf['status']}.",
                "offices_read": cf["office"],
                "read": "Of each row: office, county, candidate number, party and votes. Names are not kept."}
    for c in contests:
        sid = c["official"]
        try:
            if sid.startswith("clerk-"):
                path = os.path.join(cache, f"clerk_statistics{c['year']}.pdf")
                net.download(CLERK.format(y=c["year"]), path, 3650, tries=3, say=say)
                page = W.read_clerk(path, "MICHIGAN")
                got = W.clerk_official(page, c["section"])
                where = page["where"].replace("Wisconsin", "Michigan")
                docs.setdefault(sid, {"id": sid, "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                                      "title": "Statistics of the Presidential and Congressional Election from Official Sources for the Election of "
                                               + CLERK_DATES[c["year"]],
                                      "url": CLERK.format(y=c["year"]), "fetched": M._day(path), "sha256": M._sha_file(path), "where": where})
            elif sid.startswith("mi-boe-results-page-"):
                name = next(n for n in ARCHIVED if n.startswith("mvic_votehistory_") and str(c["year"]) in n)
                path = fetch_archived(name, cache, say)
                page = read_results_page(path, c["section"])
                got, where = split_official(page["lines"], c["id"]), f"the page's {c['section']} rows ({page['status']})"
                docs.setdefault(sid, {"id": sid, "kind": "official statewide results", "agency": AGENCY, "title": f"{c['year']} Michigan Election Results",
                                      "url": ARCHIVED[name][1], "fetched": M._day(path), "sha256": M._sha_file(path), "where": where,
                                      "read_from": f"the Internet Archive's copy of {ARCHIVED[name][0][:4]}-{ARCHIVED[name][0][4:6]}-{ARCHIVED[name][0][6:8]} "
                                                   "(the Bureau's site refuses this kit's requests and is not requested)",
                                      "read": "Of each row under the office: the party and the votes. Names are not kept."})
            else:                                           # the Bureau's county file, added up
                if c["year"] not in county_files:
                    raise ValueError("the Bureau's county file is not on disk")
                cf = county_files[c["year"]][1]
                per = collections.Counter()
                for cands in cf["votes"][c["code"]].values():
                    for cid, n in cands.items():
                        per[cid] += n
                got = split_official([(cf["party"][(c["code"], cid)], n) for cid, n in per.items()], c["id"])
                where = "every county's rows for the office, added up"
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001
            raise Stop(f"    {c['id']}: the official total could not be read ({e}); nothing is written without the control")
        out[c["id"]] = dict(got, source=sid, where=where, read=f"from the document on {M._now()}")
    return out, list(docs.values()), county_files


# ---------------------------------------------------------------- adding up

def fips_of(code):
    """The Bureau's county code (1 to 83, alphabetical) as the Census code: 26 and twice the number less one."""
    return f"{STATE_FIPS}{2 * int(code) - 1:03d}"


def four(cands, side):
    """{candidate id: votes} -> the four counts, by each candidate's side."""
    out = dict.fromkeys(VOTE, 0)
    for cand, n in cands.items():
        out[side(cand)] += n
        out["total"] += n
    return out


def county_sums(tables, contests):
    """{contest id: {county code: {candidate id: votes}}}: every precinct row of each contest added up by county, the
    county's statistical adjustments with them."""
    out = {}
    for c in contests:
        per = out[c["id"]] = collections.defaultdict(collections.Counter)
        for office, district, cand, county, _city, _ward, _pct, _label, n in tables[c["year"]]["rows"]:
            if office == c["code"] and not district.strip("0"):
                per[county][cand] += n
    return out


def county_check(by_cand, county_files, contests, tables, cousub):
    """Each county's precincts against the Bureau's county file, candidate by candidate. Returns {contest id: {compared,
    equal, file: the county file's four counts added up, out: {county code: the record of a county that differs}}}.
    A contest whose election has no county file to hand is not in the answer. The two files must name the counties
    alike and give the two tickets the same candidate numbers, or it stops."""
    res = {}
    for c in contests:
        if c["year"] not in county_files:
            continue
        cid, t, cf = c["id"], tables[c["year"]], county_files[c["year"]][1]
        theirs, mine = cf["votes"][c["code"]], by_cand[cid]
        coded = {i: p for (o, d, i), p in t["parties"].items() if o == c["code"] and not d.strip("0")}
        mine_side = lambda cand: side_of(coded.get(cand))                                 # noqa: E731
        their_side = lambda cand: side_of(cf["party"].get((c["code"], cand)))             # noqa: E731
        for code in sorted(set(theirs) | set(mine), key=int):
            if code not in t["counties"] or code not in cf["county"] or bare(t["counties"][code]) != bare(cf["county"][code]):
                raise Stop(f"    {cid}: county {code} is {t['counties'].get(code)!r} in the precinct file and {cf['county'].get(code)!r} in the county "
                           "file; the two do not name the counties alike, stopping")
        for side in ("dem", "rep"):
            a = {cand for cs in mine.values() for cand in cs if mine_side(cand) == side}
            b = {cand for cs in theirs.values() for cand in cs if their_side(cand) == side}
            if len(a) != 1 or a != b:
                raise Stop(f"    {cid}: the precinct file and the county file do not give the {side.upper()} ticket the same candidate number; stopping")
        out, file_sum = {}, dict.fromkeys(VOTE, 0)
        for code in sorted(set(theirs) | set(mine), key=int):
            a, b = {k: v for k, v in mine.get(code, {}).items() if v}, {k: v for k, v in theirs.get(code, {}).items() if v}
            fa, fb = four(mine.get(code, {}), mine_side), four(theirs.get(code, {}), their_side)
            for n in VOTE:
                file_sum[n] += fb[n]
            if a == b:
                continue
            name = cousub[fips_of(code)[2:]][0] if fips_of(code)[2:] in cousub else t["counties"][code].title() + " County"
            diff = {n: fa[n] - fb[n] for n in VOTE}
            by_side = ", ".join(f"{label} {diff[n]:+,}" for n, label in SIDES if diff[n])
            gap = (f"The precinct file is {-diff['total']:,} vote{'s' if diff['total'] != -1 else ''} short" if diff["total"] < 0 else
                   f"The precinct file is {diff['total']:,} vote{'s' if diff['total'] != 1 else ''} over" if diff["total"] > 0 else
                   "The totals are equal but the candidates' counts are not")
            out[code] = {"county": fips_of(code), "name": name, "sum_of_precincts": fa, "county_file": fb, "difference": diff,
                         "candidates_differing": sum(1 for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)),
                         "statement": (f"{name}, {c['date'][:4]} {c['office']}: this county's precincts add up to {fa['total']:,} votes (Democratic "
                                       f"{fa['dem']:,}, Republican {fa['rep']:,}, other {fa['other']:,}) and the Bureau's county file gives it "
                                       f"{fb['total']:,} (Democratic {fb['dem']:,}, Republican {fb['rep']:,}, other {fb['other']:,}). {gap}"
                                       f"{' (precincts less county file: ' + by_side + ')' if by_side else ''}, so this contest is not given for the "
                                       "county, for the cities and townships in it, or for a House district reaching into it.")}
        res[cid] = {"compared": len(set(theirs) | set(mine)), "equal": len(set(theirs) | set(mine)) - len(out), "file": file_sum, "out": out}
    return res


def tally(tables, contests, cousub, house_year=HOUSE_YEAR, out=None):
    """Everything the precinct files say, added up; then each contest taken away from the counties named in `out`
    ({contest id: county codes whose precincts do not add up to the Bureau's county file}), from every city and
    township with a precinct in such a county and from every House district reaching into one. Returns (places,
    statewide sums of every precinct row, the record of what was left out and why, the sums that did not hold)."""
    out = out or {}
    votes = {k: collections.defaultdict(dict) for k in ("county", "mcd", "house")}
    names, mcd_counties, state = {"county": {}, "mcd": {}, "house": {}}, collections.defaultdict(set), {}
    cov = {"not_placed": {}, "adjustments": {}, "house_not_given": {}, "house_unassigned": {}, "precincts": {}}
    mcd_in, house_in = collections.defaultdict(set), collections.defaultdict(set)      # (place, contest) and district -> the county codes of its precincts
    for year in sorted(tables, reverse=True):
        t = tables[year]
        mine = [c for c in contests if c["year"] == year]
        code_of = {c["code"]: c for c in mine}
        for c in mine:                                      # the tickets must be the ones this loader was checked against
            for side, party in (("dem", "DEM"), ("rep", "REP")):
                got = t["surnames"].get((c["code"], party), [])
                if len(got) != 1 or c[side].lower() not in got[0].lower():
                    raise Stop(f"    {c['id']}: the file's {party} candidate is not the one ticket this loader names ({c[side]}); stopping")
        county_fips, city_code = {}, {}
        for code, name in t["counties"].items():
            f3 = f"{2 * int(code) - 1:03d}"
            if f3 not in cousub or bare(cousub[f3][0].replace(" County", "")) != bare(name):
                raise Stop(f"    {year}: the Bureau's county {code} ({name}) is not the Census Bureau's county 26{f3}; stopping")
            county_fips[code] = STATE_FIPS + f3
            names["county"].setdefault(STATE_FIPS + f3, cousub[f3][0])
        unmatched = {}
        for (county, city), desc in t["cities"].items():
            if city == ADJUST:
                continue
            fit = match_city(desc, cousub[county_fips[county][2:]][1]) if county in county_fips else None
            if fit:
                city_code[(county, city)] = "MI-M-" + fit[0]
                names["mcd"].setdefault("MI-M-" + fit[0], fit[1])
            else:
                unmatched[(county, city)] = f"{desc.title()}, {names['county'][county_fips[county]]}"
        # each precinct's House district, from the House contests it has votes in
        pre_house = collections.defaultdict(set)
        if year == house_year:
            numbers = {code: house_number(code, desc) for code, desc in t["house"].items()}
            for office, district, _cand, county, city, ward, pct, label, n in t["rows"]:
                if office == HOUSE_OFFICE and n > 0 and city != ADJUST:
                    pre_house[(county, city, ward, pct, label)].add(numbers[district])
            for d in numbers.values():
                names["house"].setdefault(d, f"House District {d}")
        per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))    # precinct -> contest -> counts
        for office, district, cand, county, city, ward, pct, label, n in t["rows"]:
            c = code_of.get(office)
            if c is None or district.strip("0"):
                continue
            if n < 0 and city != ADJUST:
                raise Stop(f"    {year}: a precinct has {n} votes for a candidate; stopping")
            party = t["parties"][(office, district, cand)]
            v = per[(county, city, ward, pct, label)][c["id"]]
            v[{"DEM": 0, "REP": 1}.get(party, 2)] += n
            v[3] += n
        cov["precincts"][str(year)] = sum(1 for k in per if k[1] != ADJUST)
        split, loose = collections.defaultdict(set), collections.defaultdict(set)       # district -> why it is not given
        hold = []
        for key, cs in per.items():
            county, city = key[0], key[1]
            for cid, v in cs.items():
                s = state.setdefault(cid, [0, 0, 0, 0])
                cur = votes["county"][county_fips[county]].setdefault(cid, [0, 0, 0, 0])
                for i in range(4):
                    s[i] += v[i]
                    cur[i] += v[i]
                if city == ADJUST:
                    a = cov["adjustments"].setdefault(cid, [0, 0, 0, 0])
                    for i in range(4):
                        a[i] += v[i]
                elif (county, city) in city_code:
                    mcd = city_code[(county, city)]
                    mcd_counties[mcd].add(county_fips[county])
                    mcd_in[(mcd, cid)].add(county)
                    cur = votes["mcd"][mcd].setdefault(cid, [0, 0, 0, 0])
                    for i in range(4):
                        cur[i] += v[i]
                else:
                    e = cov["not_placed"].setdefault(unmatched[(county, city)], {})
                    cur = e.setdefault(cid, [0, 0, 0, 0])
                    for i in range(4):
                        cur[i] += v[i]
            if year == house_year and city != ADJUST:
                ds = pre_house.get(key, set())
                if len(ds) == 1:
                    hold.append((next(iter(ds)), cs))
                    house_in[next(iter(ds))].add(county)
                elif len(ds) > 1:
                    for d in ds:
                        split[d].add(key)
                elif any(v[3] for v in cs.values()):
                    loose[(county, city)].add(key)
                    u = cov["house_unassigned"]
                    for cid, v in cs.items():
                        cur = u.setdefault(cid, [0, 0, 0, 0])
                        for i in range(4):
                            cur[i] += v[i]
        if year == house_year:
            near = collections.defaultdict(set)             # a city or township with such a precinct -> its districts
            for key, ds in pre_house.items():
                if (key[0], key[1]) in loose:
                    for d in ds:
                        near[d].add((key[0], key[1]))
            for d in sorted(set(split) | set(near), key=M.sort_key):
                why = []
                if d in split:
                    why.append(f"{len(split[d])} precinct{'s' if len(split[d]) != 1 else ''} with votes in two House contests")
                if d in near:
                    why.append("a city or township it reaches has a precinct with votes for these contests and none for the House")
                cov["house_not_given"][d] = "; ".join(why)
            for d, cs in hold:
                if d in cov["house_not_given"]:
                    continue
                for cid, v in cs.items():
                    cur = votes["house"][d].setdefault(cid, [0, 0, 0, 0])
                    for i in range(4):
                        cur[i] += v[i]

    ids = [c["id"] for c in contests]
    pack = lambda d: {cid: dict(zip(VOTE, d[cid])) for cid in ids if cid in d}                    # noqa: E731
    # the arithmetic, on every precinct row, before anything is taken away
    wrong, zero = [], [0, 0, 0, 0]
    for cid in ids:
        whole = state.get(cid, zero)
        counties = [sum(v.get(cid, zero)[i] for v in votes["county"].values()) for i in range(4)]
        if counties != whole:
            wrong.append(f"{cid}: the counties add up to {counties} and the precinct rows to {whole}")
        parts = [sum(v.get(cid, zero)[i] for v in votes["mcd"].values()) + cov["adjustments"].get(cid, zero)[i]
                 + sum(v.get(cid, zero)[i] for v in cov["not_placed"].values()) for i in range(4)]
        if parts != whole:
            wrong.append(f"{cid}: cities and townships, the places left out and the adjustments add up to {parts}, the precinct rows to {whole}")
    # taken away: each contest in a county whose precincts do not add up to the Bureau's county file, and with the
    # county every city and township with a precinct in it and every House district reaching into it
    gone = {k: collections.defaultdict(list) for k in votes}
    for cid in ids:
        bad = set(out.get(cid) or ())
        if not bad:
            continue
        for code in bad:
            if votes["county"].get(fips_of(code), {}).pop(cid, None) is not None:
                gone["county"][fips_of(code)].append(cid)
        for (mcd, c2), codes in mcd_in.items():
            if c2 == cid and codes & bad and votes["mcd"][mcd].pop(cid, None) is not None:
                gone["mcd"][mcd].append(cid)
        for d, codes in house_in.items():
            if codes & bad and d in votes["house"] and votes["house"][d].pop(cid, None) is not None:
                gone["house"][d].append(cid)
    for d in [d for d, v in votes["house"].items() if not v]:
        bad = {code for cid in gone["house"][d] for code in out.get(cid) or ()}
        reach = listed(names["county"][fips_of(k)] for k in sorted(house_in[d] & bad, key=int))
        cov["house_not_given"][d] = f"it reaches into {reach}, where the precincts do not add up to the Bureau's county file for these contests"
        del votes["house"][d]
    cov["taken_away"] = {k: {cid: sum(1 for v in gone[k].values() if cid in v) for cid in ids if any(cid in v for v in gone[k].values())}
                         for k in ("mcd", "house")}

    def few(rec, missing=None):
        hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
        if hold:
            rec["too_few"] = hold
        if missing:
            rec["not_given"] = missing
        return rec
    places = {"county": {}, "mcd": {}, "house": {}}
    for key in sorted(votes["county"]):
        places["county"][key] = few({"name": names["county"][key], "votes": pack(votes["county"][key])}, gone["county"].get(key))
    for key in sorted(votes["mcd"]):
        n = names["mcd"][key]
        places["mcd"][key] = few({"name": n, "type": "city" if n.lower().endswith(" city") else "township", "counties": sorted(mcd_counties[key]),
                                  "votes": pack(votes["mcd"][key])}, gone["mcd"].get(key))
    for key in sorted(votes["house"], key=M.sort_key):
        places["house"][key] = few({"name": names["house"][key], "votes": pack(votes["house"][key])}, gone["house"].get(key))
    cov["adjustments"] = pack(cov["adjustments"])
    cov["house_unassigned"] = pack(cov["house_unassigned"])
    cov["not_placed"] = {k: pack(v) for k, v in sorted(cov["not_placed"].items())}
    cov["house_districts"] = len(names["house"])
    return places, state, cov, wrong


def listed(names):
    names = list(names)
    return " and ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " and " + names[-1]


def by_side(diff):
    return ", ".join(f"{label} {diff[n]:+,}" for n, label in SIDES if diff.get(n))


def control(state, cov, wrong, check, official, contests):
    """The control's account, contest by contest, and the reasons (if any) why nothing may be written. `wrong` is the
    arithmetic that did not hold in the tally; `check` is county_check's answer. A county whose precincts do not add
    up to the Bureau's county file is not a reason to write nothing: the contest is left out there, and said so."""
    failed, per, plain, notes = list(wrong), {}, True, []
    for c in contests:
        cid = c["id"]
        mine = dict(zip(VOTE, state.get(cid, [0, 0, 0, 0])))
        off = official[cid]
        theirs = {n: off[n] for n in VOTE}
        diff = {n: mine[n] - theirs[n] for n in VOTE if mine[n] != theirs[n]}
        rec = {"sum_of_precincts": mine, "official": theirs, "equal": not diff, "source": off["source"], "where": off["where"], "read": off["read"]}
        if diff:
            rec["difference"] = diff
        d = mine["total"] - theirs["total"]
        gap = (f"{-d:,} vote{'s' if d != -1 else ''} short of it" if d < 0 else f"{d:,} vote{'s' if d != 1 else ''} over it" if d > 0
               else "equal to it in total but not side by side")
        chk = check.get(cid)
        if chk is None:                     # no county file to hand: the statewide total is the only control there is
            rec["statement"] = (f"The precinct rows add up to {mine['total']:,} votes, equal to the official statewide total." if not diff else
                                f"The precinct rows add up to {mine['total']:,} votes and the official statewide total is {theirs['total']:,}: {gap}"
                                f" ({by_side(diff)}). There is no county file to say where, so nothing is given.")
            if diff:
                failed.append(f"{cid}: the precincts add up to {mine} and the official totals ({off['source']}) are {theirs}; precincts minus "
                              f"official: {diff}; and there is no county file to say where")
        else:
            out, agrees = list(chk["out"].values()), chk["file"] == theirs
            names = [r["name"] for r in out]
            rec["county_file"] = {"sum": chk["file"], "equal_to_official": agrees, "source": f"mi-boe-county-file-{c['year']}"}
            rec["counties"] = {"compared": chk["compared"], "equal": chk["equal"], "left_out": names, "source": f"mi-boe-county-file-{c['year']}",
                               "what": "every county's precinct rows, its statistical adjustments with them, candidate by candidate"}
            if any(sum(r["difference"][n] for r in out) != mine[n] - chk["file"][n] for n in VOTE):
                failed.append(f"{cid}: the counties' differences do not add up to the difference between the precinct rows and the county file")
            if not agrees:
                f = chk["file"]
                state_line = (f"The Bureau's county file adds up to {f['total']:,} votes (Democratic {f['dem']:,}, Republican {f['rep']:,}, other "
                              f"{f['other']:,}) and the official statewide total named here is {theirs['total']:,} (Democratic {theirs['dem']:,}, "
                              f"Republican {theirs['rep']:,}, other {theirs['other']:,}). The two official figures disagree; this file does not say "
                              f"which is right and gives no statewide figure for the contest. The precinct rows add up to {mine['total']:,}.")
                notes.append(f"{cid}: the Bureau's county file and the official statewide total disagree; no statewide figure is given.")
            elif not diff:
                state_line = f"Statewide the precinct rows add up to {mine['total']:,} votes, equal to the official total, side by side."
            else:
                state_line = (f"Statewide the precinct rows add up to {mine['total']:,} votes and the official total is {theirs['total']:,}: the precinct "
                              f"files are {gap} ({by_side(diff)}), because the precinct rows of {len(out)} "
                              f"{'county' if len(out) == 1 else 'counties'} do not add up to the Bureau's own official county totals. The Bureau's "
                              "county file itself adds up to the official statewide total.")
            if not out:
                county_line = (f"In all {chk['compared']} counties the precinct rows add up exactly to the Bureau's county file, candidate by "
                               "candidate.")
            else:
                who = listed(names) if len(names) <= 12 else "named in counties.left_out"
                county_line = (f"In {chk['equal']} of {chk['compared']} counties the precinct rows add up exactly to the Bureau's county file, "
                               f"candidate by candidate, and the contest is given for them. It is left out for the other {len(out)} ({who}), for "
                               "the cities and townships in them and for any House district reaching into them; "
                               "coverage.counties_left_out gives both figures for each."
                               + (" Their differences cancel one another statewide." if agrees and not diff else ""))
            rec["statement"] = state_line + " " + county_line
            plain = plain and agrees and not diff and not out
        per[cid] = rec
    statement = ("For each contest every county's precinct rows (its statistical adjustments with them) were added up and compared, candidate by "
                 "candidate, with the Bureau of Elections' own official county file for that election. A contest is given for a county, and for "
                 "the cities, townships and House districts in it, only where the two are exactly equal; where they are not, the contest is left "
                 "out there, and coverage.counties_left_out states both figures and the difference. Each contest's statewide line is stated as "
                 "it is. Before anything was left out, the counties added up to the sum of the precinct rows, and so did the cities and "
                 "townships with the places left out and the adjustments. No number was changed to make anything fit.")
    if not check:
        statement = ("For every contest the precinct rows, with each county's statistical adjustments, add up to the official statewide totals "
                     "named here; the counties add up to the statewide sum; and cities and townships, the places left out and the adjustments "
                     "add up to it too.")
    if failed:
        statement = "The sums do not all agree; see the differences."
    left = {cid: f"{len(chk['out'])} of {chk['compared']} counties left out" for cid, chk in check.items() if chk["out"]}
    ctl = {"result": "differs" if failed else "equal" if plain else "equal where given", "statement": statement,
           "precincts": cov["precincts"], "contests": per,
           "kinds": {"county": ("equal to the Bureau's county file, candidate by candidate, for every contest given" if check else
                                "equal to the statewide sum") if not failed else "see the differences",
                     "mcd": "no control of their own: the Bureau publishes no city or township totals; a contest is given only inside counties that are equal",
                     "house": "whole precincts only, inside counties that are equal; the districts a split precinct touches are left out"},
           "notes": notes}
    if left:
        ctl["left_out"] = left
    return ctl, failed


def build(tables, contests, cousub, official, official_docs, county_files, house_year=HOUSE_YEAR, sources=None):
    check = county_check(county_sums(tables, contests), county_files, contests, tables, cousub)
    places, state, cov, wrong = tally(tables, contests, cousub, house_year, {cid: set(chk["out"]) for cid, chk in check.items()})
    ctl, failed = control(state, cov, wrong, check, official, contests)
    if len(places["county"]) != len(cousub):
        failed.append(f"{len(places['county'])} counties with votes, and the Census Bureau lists {len(cousub)}")
    given = {"county": [c["id"] for c in contests], "mcd": [c["id"] for c in contests], "house": [c["id"] for c in contests if c["year"] == house_year]}
    records = []
    for c in contests:
        t, per = tables[c["year"]], ctl["contests"][c["id"]]
        rec = {"id": c["id"], "date": c["date"], "office": c["office"], "table": f"mi-boe-precinct-results-{c['year']}",
               "kinds": [k for k in given if c["id"] in given[k]],
               "dem": {"party": "Democratic", "ticket": c["dem"], "column": "party DEM"},
               "rep": {"party": "Republican", "ticket": c["rep"], "column": "party REP"},
               "other": {"what": "every other candidate, and write-ins as the file carries them, together",
                         "parties": sorted({p or "none given" for (o, d, _i), p in t["parties"].items() if o == c["code"] and not d.strip("0")} - {"DEM", "REP"})},
               "total": {"what": "all of them together"}}
        # the statewide figure is the official statewide total: the precinct rows equal it, or fall short of it by the
        # difference the control states; where the Bureau's county file and that total disagree, none is given
        if per.get("county_file", {}).get("equal_to_official", True):
            rec["statewide"] = dict(per["official"])
            if not per["equal"]:
                rec["statewide_note"] = ("The official statewide total. The precinct rows add up to "
                                         f"{per['sum_of_precincts']['total']:,} votes; control.contests says where the difference lies.")
        else:
            rec["statewide_note"] = "Not given: the Bureau's county file and the official statewide total disagree (control.contests has both)."
        rec["official_source"] = official[c["id"]]["source"]
        if c["id"] in check:
            rec["counties_given"] = check[c["id"]]["equal"]
            rec["counties_left_out"] = len(check[c["id"]]["out"])
        records.append(rec)
    kinds, any_out = {}, any(chk["out"] for chk in check.values())
    for kind, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind],
                       "given": {cid: sum(1 for p in places[kind].values() if cid in p["votes"]) for cid in given[kind]},
                       "covers_the_state": kind == "county" and not any_out,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
    kinds["mcd"]["note"] = ("The Bureau's city or township of a county, matched to the Census Bureau's county subdivision of the same name and "
                            "kind. Before anything was left out they added up to the state with the places left out and each county's "
                            "statistical adjustments.")
    kinds["house"]["note"] = (f"A precinct's district is the one whose House contest it has votes in. {len(cov['house_not_given'])} of "
                              f"{cov['house_districts']} districts are not given (coverage.house_not_given says why).")
    kinds["house"]["why_not_earlier"] = "The 2022 and 2020 elections were held on other plans."
    if any_out:
        kinds["county"]["why_not_everywhere"] = WHY_NOT
        kinds["mcd"]["why_not_everywhere"] = WHY_NOT_MCD
        kinds["county"]["note"] = ("A contest is given for a county only where its precinct rows add up exactly to the Bureau's county file "
                                   "for that contest (coverage.counties_left_out lists the others, with both figures).")
    coverage = {"places_left_out": cov["not_placed"], "statistical_adjustments": cov["adjustments"],
                "house_not_given": cov["house_not_given"], "house_votes_in_precincts_with_no_house_contest": cov["house_unassigned"],
                "not_given": NOT_GIVEN}
    if check:
        coverage["counties_left_out"] = {cid: list(chk["out"].values()) for cid, chk in check.items() if chk["out"]}
        coverage["left_out_with_their_county"] = dict(cov["taken_away"], what=(
            "How many cities and townships, and House districts, lost each contest because a county they have precincts in was left out. "
            "Each such place lists the contests under not_given."))
        coverage["note"] = ("places_left_out and statistical_adjustments are sums over every precinct row of each contest, counties that were "
                            "left out included: they are the account of the arithmetic, not figures for a page.")
    doc = {"what": WHAT, "note": NOTE, "state": "MI", "generated": M._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(VOTE), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": ctl,
           "coverage": coverage, "sources": (sources or []) + official_docs, "places": places}
    return doc, failed


# ---------------------------------------------------------------- the run

def our_places(db):
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(dict)
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE source_id LIKE 'mi-%' AND kind IN ('county', 'mcd')"):
            out[kind][pid] = name
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, contests=None, trial=False):
    contests = contests or (TRIAL if trial else CONTESTS)
    say("    Michigan place votes: the Bureau of Elections' official precinct results")
    net.patient_lookups()
    if trial:
        fetch_archived("2018GEN.zip", cache, say)
    years = sorted({c["year"] for c in contests}, reverse=True)
    if trial and not os.path.exists(os.path.join(cache, "election_result_2018GEN.txt")):
        try:
            fetch_archived("election_result_2018GEN.txt", cache, say)
        except OSError as e:
            say(f"      election_result_2018GEN.txt: the Archive's copy could not be fetched ({e})")
    on_disk = lambda y: [n for n in (f"{y}GEN.zip", f"election_result_{y}GEN.txt") if not os.path.exists(os.path.join(cache, n))]     # noqa: E731
    have = [y for y in years if not on_disk(y)]
    need = [y for y in years if y not in have and (trial or y in NEEDED)]
    if need:
        say("    Michigan place votes: nothing written. Both of an election's files are needed, the precinct file and the county file it "
            "is held against, and for " + " and ".join(str(y) for y in need) + " they are not both on disk.")
        say("    " + JOHN.format(page=RESULTS_PAGE, years=", ".join(str(y) for y in need), files=", ".join(n for y in need for n in on_disk(y))))
        raise Stop("    Michigan place votes: waiting on the saved files.")
    for y in years:
        if y not in have:
            say(f"      {y}: left out of this run; not on disk: {', '.join(on_disk(y))}")
    contests = [c for c in contests if c["year"] in have]
    if not os.path.exists(COUSUB):
        net.download(COUSUB_URL, COUSUB, 3650, tries=3, say=say)
    cousub = read_cousub(COUSUB)
    tables, sources = {}, []
    for y in have:
        path = os.path.join(cache, f"{y}GEN.zip")
        tables[y] = read_precinct_zip(path, y, {c["code"] for c in contests if c["year"] == y})
        url, how = came_from(f"{y}GEN.zip", path)
        sources.append({"id": f"mi-boe-precinct-results-{y}", "kind": "official results by precinct", "agency": AGENCY,
                        "title": f"{y} Michigan Precinct-Level General Election Results ({y}GEN.zip)", "url": url, "read_from": how,
                        "fetched": M._day(path), "sha256": M._sha_file(path), "rows": len(tables[y]["rows"]),
                        "read": "Of each vote row: office, district, candidate number, county, city or township, ward, precinct and votes; of "
                                "each candidate, the party, and the surname of the Democratic and Republican candidates for the contests named here."})
        say(f"      {y}: {len(tables[y]['rows']):,} vote rows for the contests and the State House")
    sources.append({"id": "census-2020-cousub-26", "kind": "official place codes", "agency": "U.S. Census Bureau",
                    "title": "2020 county subdivision codes, Michigan", "url": COUSUB_URL, "fetched": M._day(COUSUB), "sha256": M._sha_file(COUSUB)})
    official, official_docs, county_files = official_totals(contests, tables, cache, say)
    doc, failed = build(tables, contests, cousub, official, official_docs, county_files, max(have) if trial else HOUSE_YEAR, sources)
    p, cov = doc["places"], doc["coverage"]
    say(f"    added up: {len(p['county'])} counties; {len(p['mcd']):,} cities and townships; {len(p['house'])} House districts "
        f"({len(cov['house_not_given'])} not given)")
    if cov["places_left_out"]:
        say("      left out, no one Census place of the name: " + "; ".join(f"{k} ({sum(v['total'] for v in vs.values()):,} votes)" for k, vs in cov["places_left_out"].items()))
    for c in doc["contests"]:
        ctl = doc["control"]["contests"][c["id"]]
        s = ctl["sum_of_precincts"]
        say(f"    control, {c['id']}: the precinct rows add up to Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total "
            f"{s['total']:,}: " + ("equal to" if ctl["equal"] else f"DIFFERS ({by_side(ctl['difference'])}) from") + f" {ctl['source']} ({ctl['where']})"
            + (f"; counties equal to the Bureau's county file: {ctl['counties']['equal']} of {ctl['counties']['compared']}" if "counties" in ctl else "")
            + ("; the county file adds up to the official statewide total" if ctl.get("county_file", {}).get("equal_to_official") else
               "; THE COUNTY FILE DOES NOT ADD UP TO THE OFFICIAL STATEWIDE TOTAL" if "county_file" in ctl else ""))
        for r in cov.get("counties_left_out", {}).get(c["id"], []):
            say(f"      left out: {r['name']}: precincts {r['sum_of_precincts']['total']:,}, county file {r['county_file']['total']:,}"
                f" ({by_side(r['difference']) or 'the totals are equal, the candidates are not'})")
        say(f"      given for: " + "; ".join(f"{doc['kinds'][k]['given'][c['id']]:,} of {len(p[k]):,} {label}" for k, label in
                                             (("county", "counties"), ("mcd", "cities and townships"), ("house", "House districts"))
                                             if c["id"] in doc["kinds"][k]["given"]))
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    Michigan place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in ("county", "mcd"):
            ids = ours.get(kind, {})
            without = sorted(i for i in ids if not p[kind].get(i, {}).get("votes"))
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": {i: ids[i] for i in without}}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}")
        covered["mcd"]["why_without"] = "A village votes in its township's precincts and is not given."
        cov["our_places"] = dict(covered, read=f"sl_places in {os.path.basename(db)}, opened read-only on {M._now()}")
    M.write(out, doc)
    say(f"    Michigan place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.1f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic on a made-up table

def selftest(say=print):
    cousub = {"001": ("Alcona County", [("01040", "Alcona township"), ("12460", "Carson City city"), ("50000", "Elm charter township"),
                                         ("50001", "Elm city")]),
              "003": ("Alger County", [("12460", "Carson City city"), ("70000", "Village of Oak city")])}
    parties = {("1", "00000", "10"): "DEM", ("1", "00000", "11"): "REP", ("1", "00000", "12"): "LIB",
               ("8", "00100", "20"): "DEM", ("8", "00200", "21"): "REP"}

    def rows(county, city, pct, d, r, o, house=()):
        out = [("1", "00000", "10", county, city, "0", pct, "", d), ("1", "00000", "11", county, city, "0", pct, "", r),
               ("1", "00000", "12", county, city, "0", pct, "", o)]
        return out + [("8", dist, {"00100": "20", "00200": "21"}[dist], county, city, "0", pct, "", 5) for dist in house]
    t = {"counties": {"1": "ALCONA", "2": "ALGER"},
         "cities": {("1", "2"): "ALCONA TOWNSHIP", ("1", "52"): "CARSON CITY", ("1", "4"): "ELM TOWNSHIP", ("1", "6"): "PINE TOWNSHIP",
                    ("2", "52"): "CARSON CITY", ("2", "54"): "OAK CITY", ("1", ADJUST): "{Statistical Adjustments}"},
         "parties": parties, "surnames": {("1", "DEM"): ["Aa"], ("1", "REP"): ["Bb"]},
         "house": {"00100": "1ST DISTRICT REPRESENTATIVE IN STATE LEGISLATURE 2 YEAR TERM", "00200": "2ND DISTRICT REPRESENTATIVE IN STATE LEGISLATURE 2 YEAR TERM"},
         "rows": (rows("1", "2", "1", 10, 20, 1, ["00100"]) + rows("1", "52", "1", 30, 5, 0, ["00100"]) + rows("2", "52", "1", 7, 3, 0, ["00100"])
                  + rows("1", "4", "1", 6, 6, 2, ["00100", "00200"]) + rows("1", "6", "1", 4, 0, 0, ["00200"]) + rows("2", "54", "1", 9, 9, 0, ["00200"])
                  + rows("1", ADJUST, "9999", 1, -1, 0))}
    contests = [{"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President", "code": "1", "dem": "Aa", "rep": "Bb", "official": "x"}]
    official = {"2024-president": {"dem": 67, "rep": 42, "other": 3, "total": 112, "source": "x", "where": "-", "read": "-"}}
    doc, failed = build({2024: t}, contests, cousub, official, [], {}, 2024)
    p, checks = doc["places"], []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    check("the control holds on the made-up table", (doc["control"]["result"], failed), ("equal", []))
    check("a county code becomes its FIPS code", sorted(p["county"]), ["26001", "26003"])
    check("a county takes its statistical adjustments", p["county"]["26001"]["votes"]["2024-president"], {"dem": 51, "rep": 30, "other": 3, "total": 84})
    check("a city in two counties is one place", p["mcd"]["MI-M-12460"]["votes"]["2024-president"], {"dem": 37, "rep": 8, "other": 0, "total": 45})
    check("and reaches both counties", p["mcd"]["MI-M-12460"]["counties"], ["26001", "26003"])
    check("a charter township is matched as a township, not the city of its name", p["mcd"]["MI-M-50000"]["type"], "township")
    check("a city the Census calls Village of X is matched", "MI-M-70000" in p["mcd"], True)
    check("a place with no Census namesake is left out and listed", list(doc["coverage"]["places_left_out"]), ["Pine Township, Alcona County"])
    check("a district touched by a split precinct is not given", (sorted(p["house"]), sorted(doc["coverage"]["house_not_given"])), ([], ["1", "2"]))
    check("a place of fewer than twenty votes is marked too_few", "too_few" in p["mcd"]["MI-M-70000"], True)
    t2 = dict(t, rows=[r for r in t["rows"] if not (r[0] == "8" and r[4] == "4")] + [("8", "00100", "20", "1", "4", "0", "1", "", 5)])
    d2 = build({2024: t2}, contests, cousub, official, [], {}, 2024)[0]
    check("whole precincts make a district", d2["places"]["house"]["1"]["votes"]["2024-president"], {"dem": 53, "rep": 34, "other": 3, "total": 90})
    wrong = {"2024-president": dict(official["2024-president"], dem=68, total=113)}
    check("a wrong official total is caught", build({2024: t}, contests, cousub, wrong, [], {}, 2024)[0]["control"]["result"], "differs")
    try:
        build({2024: dict(t, surnames={("1", "DEM"): ["Zz"], ("1", "REP"): ["Bb"]})}, contests, cousub, official, [], {}, 2024)
        caught = False
    except Stop:
        caught = True
    check("another ticket than the one named stops the loader", caught, True)
    check("a charter township is matched however the Bureau writes it",
          (match_city("ELM CHARTER TOWNSHIP", cousub["001"][1]), match_city("ELM CHARTER TWP", cousub["001"][1]), match_city("ELM TOWNSHIP", cousub["001"][1])),
          (("50000", "Elm charter township"),) * 3)

    # the control county by county, against a made-up county file
    def county_file(alger_rep):
        return {2024: ("-", {"votes": {"1": {"1": {"10": 51, "11": 30, "12": 3}, "2": {"10": 16, "11": alger_rep, "12": 0}}},
                             "party": {("1", "10"): "Democratic", ("1", "11"): "Republican", ("1", "12"): "Libertarian"},
                             "county": {"1": "ALCONA", "2": "ALGER"}, "office": {"1": "President"}, "records": 6, "status": "OFFICIAL"})}
    d3, f3 = build({2024: t2}, contests, cousub, official, [], county_file(12), 2024)
    check("every county equal to its county file: nothing is left out", (d3["control"]["result"], f3, d3["control"]["contests"]["2024-president"]["counties"]["equal"]),
          ("equal", [], 2))
    short = {"2024-president": dict(official["2024-president"], rep=43, total=113)}
    d4, f4 = build({2024: t2}, contests, cousub, short, [], county_file(13), 2024)
    q, c4 = d4["places"], d4["control"]["contests"]["2024-president"]
    check("a county one vote short of its county file: the file is written, the contest left out there", (d4["control"]["result"], f4), ("equal where given", []))
    check("the county that is equal keeps the contest", q["county"]["26001"]["votes"]["2024-president"]["total"], 84)
    check("the county that is not has no figure, and says which contest", (q["county"]["26003"]["votes"], q["county"]["26003"]["not_given"]), ({}, ["2024-president"]))
    check("nor has its city", q["mcd"]["MI-M-70000"]["votes"], {})
    check("nor a city with a precinct in it and in another county", q["mcd"]["MI-M-12460"]["votes"], {})
    check("a township of the county that is equal keeps its figure", q["mcd"]["MI-M-01040"]["votes"]["2024-president"]["total"], 31)
    check("a House district reaching into it is not given", (sorted(q["house"]), sorted(d4["coverage"]["house_not_given"])), ([], ["1", "2"]))
    r = d4["coverage"]["counties_left_out"]["2024-president"][0]
    check("the county is listed with both figures and the difference", (r["name"], r["sum_of_precincts"]["rep"], r["county_file"]["rep"], r["difference"]["total"]),
          ("Alger County", 12, 13, -1))
    check("the statewide line is stated as it is", (c4["equal"], c4["difference"], c4["county_file"]["equal_to_official"], d4["contests"][0]["statewide"]["total"]),
          (False, {"rep": -1, "total": -1}, True, 113))
    d5, f5 = build({2024: t2}, contests, cousub, wrong, [], county_file(12), 2024)
    check("a county file and a statewide total that disagree: said, neither chosen, no statewide figure",
          (f5, "statewide" in d5["contests"][0], d5["control"]["contests"]["2024-president"]["county_file"]["equal_to_official"]), ([], False, False))
    try:
        build({2024: t2}, contests, cousub, official, [], {2024: ("-", dict(county_file(12)[2024][1], party={("1", "10"): "Republican", ("1", "11"): "Democratic"}))}, 2024)
        caught = False
    except Stop:
        caught = True
    check("two files that number the tickets differently stop the loader", caught, True)
    head = ("ElectionDate\tOfficeCode(text)\tDistrictCode(Text)\tStatusCode\tCountyCode\tCountyName\tOfficeDescription\tPartyOrder\tPartyDescription\t"
            "CandidateID\tCandidateLastName\tCandidateFirstName\tCandidateMiddleName\tCandidateFormerName\tCandidateVotes\tWriteIn(W)/Uncommitted(Z)\t"
            "Recount(*)\tNomindated(N)/Elected(E)")
    line = lambda code, desc, party, cand, n: "\t".join(["2024-11-05", code, "0", "0", "1", "ALCONA", desc, "1", party, cand, "", "", "", "", str(n), "", "", ""])    # noqa: E731
    made = ["TOTAL VOTER TURNOUT: 1", head, line("7", "UNITED STATES SENATOR 6 YEAR TERM (1) POSITION", "DEMOCRATIC", "20", 9),
            line("7", "UNITED STATES SENATOR 6 YEAR TERM (1) POSITION", "REPUBLICAN", "21", 8),
            line("14", "GOVERNOR OF WAYNE STATE UNIVERSITY 8 YEAR TERMS (2) POSITIONS", "DEMOCRATIC", "30", 7), "RECORDS: 3\tRESULTS: OFFICIAL"]
    cf = parse_county_file(made, {"5": SENATOR})
    check("an office is found in the county file by its description, whatever its number", (dict(cf["votes"]["5"]), cf["status"]), ({"1": {"20": 9, "21": 8}}, "OFFICIAL"))

    def refuses(lines, wanted):
        try:
            parse_county_file(lines, wanted)
        except ValueError:
            return True
        return False
    check("a university's Governor is not the Governor", refuses(made, {"2": GOVERNOR}), True)
    check("a county file with fewer rows than its last line says is refused", refuses(made[:3] + made[4:], {"5": SENATOR}), True)
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Michigan place voted in past partisan general elections -> ballot/lean/mi_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/mi_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where the saved precinct files are (default: states_cache/mi_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only")
    ap.add_argument("--trial", metavar="FILE", help="run the loader on the 2018 general election (the Archive's copy of the Bureau's file) and write FILE")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic on a made-up table; reads and downloads nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if a.trial:
        if os.path.abspath(a.trial) == os.path.abspath(OUT):
            raise SystemExit("    --trial never writes the real file; name another")
        load(out=a.trial, cache=a.cache, db=a.db, trial=True)
        return
    load(out=a.out, cache=a.cache, db=a.db)


if __name__ == "__main__":
    main()
