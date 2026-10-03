"""
ballot/ok_place_votes.py - how each Oklahoma place voted in past partisan general elections, so a page can show the
record of a county or a district without anyone labelling a candidate. The Oklahoma twin of ballot/mn_place_votes.py;
the output has the same shape (the Democratic count is "dem" here, as in the Dakotas', Kentucky's and Wyoming's files,
where Minnesota's is "dfl").

    python ballot/ok_place_votes.py               reads the Board's files on disk, writes ballot/lean/ok_place_votes.json
    python ballot/ok_place_votes.py --refresh     asks again for the precinct map and the control documents
    python ballot/ok_place_votes.py --out x.json  writes somewhere else; --cache DIR reads and keeps files somewhere else
    python ballot/ok_place_votes.py --selftest    the readers and the arithmetic on made-up files; downloads nothing

What it is, and is not
----------------------
For President in 2024 and 2020, Governor in 2022, and United States Senator in 2022 (both contests: the full term and
the unexpired term) and 2020: the votes for the Democratic ticket, the Republican ticket, every other candidate together
(Oklahoma allows no write-in votes) and the total, for every one of the 77 counties, and for 2022 and 2024 for every
state House and Senate district and county commissioner district whose precincts can be added up whole (see below), in
each case wherever the control below holds. It is how the people of a place voted then, on the lines in force at that
election. It is not a prediction, it says nothing about any candidate on a later ballot or about any voter, and it turns
no nonpartisan office into a partisan one. No database is opened for writing; ballot_local_2026.sqlite is opened
read-only, to count how many of our places are covered.

Where the numbers come from
---------------------------
The Oklahoma State Election Board publishes its official results only through its results site
(results.okelections.gov/OKER/?elecDate=<yyyymmdd>, linked from each election's page on oklahoma.gov/elections). That
site refuses scripts, so this loader never asks it for anything and downloads none of its files: it reads what is in
ballot_cache/ok/place_votes/<yyyymmdd>/. The files of 20241105, 20221108 and 20201103 there were read through a browser
on 2026-10-03 from each election's page, which was marked "Official Results", through its "Export" menu: "Precinct Level
Results - CSV (Zipped)" (<date>_PrecinctResults_csv.zip) and "County Level Results - CSV (Zipped)"
(<date>_CountyResults_csv.zip), saved under the Board's own names. Their SHA-256 fingerprints are typed in SAVED; the
file this loader writes gives the fingerprint of every file it read and says of each whether it is one of those. A year
with no precinct-level file on disk is left out and named; the file is written only when at least one year is there.

The layout, as the exports have it (one CSV in each zip, one line per candidate per precinct, or per county, per
contest): elec_date (11/5/2024), precinct (in the county-level file: county, the county's name), entity_description (whose
ballot the contest is on: "FEDERAL, STATE AND COUNTY", a county, a city, a school district), race_number,
race_description, race_party (empty in a general election), tot_race_prec, race_prec_reporting, cand_number (the
candidate's number in the contest; the two files number alike), cand_name, cand_party (DEM, REP, LIB, IND, or empty),
cand_absmail_votes, cand_early_votes, cand_elecday_votes, cand_tot_votes (the three added up, on every line of the
contests read here) and race_county_owner (the county a contest belongs to, where it belongs to one). Only these are
ever read: the precinct code (or
the county's name), the contest's number and title, the party letters, the candidate number, the candidate's name (kept
only on the Democratic and Republican lines of the contests named here, to check which election it is), the line's
total votes and the date; the rest is skipped unread. The Board's older precinct files (20141104_prec.csv:
county_name, precinct_code, cand_name, cand_party, cand_tot_votes and others) are read too, by their own headings.

The precinct code is six digits: two for the Board's county number and four for the precinct. The Board numbers the
counties 01 to 77 alphabetically with the Mc counties placed as if spelled Mac (McClain 44, McCurtain 45, McIntosh 46,
then Major 47), and the county's FIPS code is 40 and twice that number less one. The export has no county column; the
county is read from the code, and where an older file names the county the name must agree. Oklahoma County (55) and
Tulsa County (72) count every absentee, mail and early vote in one county-wide unit numbered 9999 (55-9999, 72-9999);
their precincts carry election-day votes only.

Which district a precinct is in is not in the results: a state House, state Senate or county commissioner contest
appears only where it was contested, and the files have no district column. So it comes from "Voter Precincts 2020"
(services.arcgis.com, the University of Oklahoma's Center for Spatial Analysis, "prepared ... in cooperation with the
Oklahoma State Election Board"; the Board's District and Precinct Maps page sends readers there): every precinct's six-
digit code, its state House, state Senate and county commissioner district. Only those attributes are fetched, never the
map's shapes. The layer is today's precincts (1,984 of them, last edited 2025-11-05) on the lines drawn in 2021, first
used in 2022, so districts are given for 2022 and 2024 and not for 2020. It is checked against the results themselves:
every precinct that carried a state House, state Senate or county commissioner contest must lie, on the layer, in that
contest's district, and every precinct the layer puts in such a district must have carried its contest. Oklahoma prints
a contest only when it is contested, so a district whose seat was settled earlier is checked by the precincts of its
neighbours only.

A district is given in a year only where every precinct voting in it can be placed: a precinct the layer does not know
(a precinct drawn or renumbered since, or a county's 9999 unit of absentee and early votes), or one that the check above
finds on the wrong side of a line, leaves out every district of that kind reaching its county, for that year, and the
file names it. Nothing is divided by estimate. The 9999 units alone leave out every House, Senate and commissioner
district reaching Oklahoma or Tulsa County.

Not given: cities and towns and their wards (a precinct may lie partly inside a city, and neither the results nor the
precinct layer says how its votes divide at the city line), school and fire protection districts, judicial districts (a
district judge's office can be elected from part of its district's counties; the counties are given), and districts for
2020 (other lines).

The control, county by county
-----------------------------
  - For each contest every county's precinct lines are added up and compared, candidate by candidate (by the Board's
    candidate number), with that county's lines in the Board's county-level file for the same election.
  - Where the two are exactly equal the contest is given for the county and for a state House, state Senate or county
    commissioner district reaching into it. Where they are not, the contest is LEFT OUT for that county and for every
    such district reaching into it, and the file lists the county with both figures and the difference, in a sentence
    (coverage.counties_left_out; the places that lost a contest are in coverage.left_out_with_their_county). No number
    is changed, shared out or estimated to make anything fit.
  - The statewide line is stated as it is: the sum of the precinct lines, the official statewide total, and either
    "equal" or the difference and the counties it comes from. The official statewide totals are the Clerk of the U.S.
    House of Representatives' "Statistics of the ... Election" for President and Senator, read from its PDF at each run,
    and for Governor in 2022 the Board's own certified summary in the packet of its meeting of November 15, 2022, whose
    numbers are typed below with the packet's SHA-256 and found in the packet's text at each run. The county-level
    file's own sum is compared with that total as well; if the two ever disagree the file says so, gives no statewide
    figure for the contest and does not say which is right.

Nothing at all is written if a file is not of its election's date; a precinct line is in a file twice; a contest is not
found exactly once, with one Democratic and one Republican line whose candidates are the ones typed below; the two files
do not number the two tickets alike; an election with no county-level file does not add up exactly to the official
statewide figures; or the arithmetic itself fails (the counties, or each kind of district with the precincts it leaves
out, do not add up to the sum of the precinct lines; the counties' differences do not add up to the difference between
the precinct lines and the county-level file).

What the run of 2026-10-03 found (the file states the figures; this is only where to look): in all six contests the
precinct lines of every one of the 77 counties equal the Board's county-level file candidate by candidate, and both
equal the official statewide figures, so nothing is left out by the control. Districts given: 2024, 51 of 101 House, 21
of 48 Senate and 219 of 231 commissioner districts; 2022, 44, 20 and 210. Precinct units not on the layer: 2024, the two
9999 units and one precinct each in Harmon and McClain counties; 2022, the two 9999 units and seven precincts in Harmon
(2), Kiowa (2), McClain (2) and Washington (1) counties. In 2022 a Wagoner County precinct the layer puts in House
district 13 did not vote in its contest,
and an Osage County precinct voted for commissioner in district 1 where the layer has district 3 (the layer is of
today's precincts); the districts of those kinds reaching those counties are left out for 2022.
"""

import argparse
import collections
import csv
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

METHOD = "1.1"                 # change how anything is added up or matched, and this goes up (1.1: the county-by-county control)
CACHE = os.path.join(HERE, "ballot_cache", "ok", "place_votes")
OUT = os.path.join(HERE, "ballot", "lean", "ok_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
KEEP_DAYS = 30
STATE_FIPS = "40"
FEW = 20                       # a contest with fewer votes than this in a place is marked too_few (see TOO_FEW)
SIDES = ("dem", "rep", "other", "total")

RESULTS_SITE = "https://results.okelections.gov/OKER/?elecDate={day}"
# The Board's files of 2024, 2022 and 2020 as they were read through a browser on SAVED_ON from the results site's own
# Export menu (the site refuses scripts and this loader never requests it), with the SHA-256 of the bytes saved. A file
# on disk with another fingerprint is said to be another copy, not the one this loader was checked against.
SAVED_ON = "2026-10-03"
EXPORT = {"precinct": "Precinct Level Results - CSV (Zipped)", "county": "County Level Results - CSV (Zipped)"}
SAVED = {
    "20241105_PrecinctResults_csv.zip": "5b3abeae71aa1d21683adb9f4a6e7e1304b0cd7ee4923c7d1dbf63ae2cedc643",
    "20241105_CountyResults_csv.zip": "f3a8370a49385910c825b01006ce33bcf6fc0c18b796cf01188ae2caa1e4527b",
    "20221108_PrecinctResults_csv.zip": "0bb68226c7c3f1fb1b66d33d3944506dc5fee6c2cbf28593ab6e6ae8ee93f2b0",
    "20221108_CountyResults_csv.zip": "e7f69a229a891a55bd786a84d66f4061f4ce9c734d8da1fe752ae86491f0cb53",
    "20201103_PrecinctResults_csv.zip": "8d9de3e38a188d31444e19dc48f2c45df0f15977f5d66a1db42ed0f60190d7ad",
    "20201103_CountyResults_csv.zip": "bb7c95a9237cf5ae8fe1c4bd756a1f2e3e3b82bb5408a596afdcb85f219c03b9",
}
YEAR_PAGES = {
    2024: "https://oklahoma.gov/elections/elections-results/election-results/2024-election-results/november-general-election.html",
    2022: "https://oklahoma.gov/elections/elections-results/election-results/2022-election-results/2022-november-general-election.html",
    2020: "https://oklahoma.gov/elections/elections-results/election-results/2020-election-results/2020-november-general-election.html",
}
DAYS = {2024: "20241105", 2022: "20221108", 2020: "20201103"}
DISTRICT_YEARS = (2022, 2024)  # the lines drawn in 2021 were first used in 2022

LAYER = {
    "id": "ou-csa-voter-precincts-2020",
    "kind": "precinct lines and their districts",
    "agency": "Center for Spatial Analysis, University of Oklahoma, in cooperation with the Oklahoma State Election Board",
    "title": "Voter Precincts 2020 (statewide voting precincts)",
    "url": "https://csagis-uok.opendata.arcgis.com/datasets/8c2c841e2eb54007bd1872c4274d6e07",
    "service": "https://services.arcgis.com/3xOwF6p0r7IHIjfn/arcgis/rest/services/State_Wide_2020_Precincts/FeatureServer/0",
    "listed_on": "https://oklahoma.gov/elections/candidates/district-and-precinct-maps.html",
    "fields": ["PCT_CEB", "COUNTY", "COUNTY_NAM", "CO_FIPS", "St_house", "St_senate", "Comm"],
}

CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States",
     "race": r"^(FOR )?(ELECTORS FOR )?PRESIDENT", "first": True,
     "dem": ("Democratic", "Kamala D. Harris and Tim Walz", "HARRIS"), "rep": ("Republican", "Donald J. Trump and JD Vance", "TRUMP"),
     "clerk": ("FOR PRESIDENTIAL ELECTORS", None)},
    {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor",
     "race": r"^(FOR )?GOVERNOR$",
     "dem": ("Democratic", "Joy Hofmeister", "HOFMEISTER"), "rep": ("Republican", "Kevin Stitt", "STITT"),
     "packet": "packet-2022"},
    {"id": "2022-us-senate", "year": 2022, "date": "2022-11-08", "office": "United States Senator (full term)",
     "race": r"^(FOR )?UNITED STATES SENATOR\b(?!.*UNEXPIRED)",
     "dem": ("Democratic", "Madison Horn", "HORN"), "rep": ("Republican", "James Lankford", "LANKFORD"),
     "clerk": ("FOR UNITED STATES SENATOR", "(For full term")},
    {"id": "2022-us-senate-unexpired", "year": 2022, "date": "2022-11-08", "office": "United States Senator (unexpired term ending January 3, 2027)",
     "race": r"^(FOR )?UNITED STATES SENATOR\b.*UNEXPIRED",
     "dem": ("Democratic", "Kendra Horn", "HORN"), "rep": ("Republican", "Markwayne Mullin", "MULLIN"),
     "clerk": ("FOR UNITED STATES SENATOR", "(For unexpired term")},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States",
     "race": r"^(FOR )?(ELECTORS FOR )?PRESIDENT", "first": True,
     "dem": ("Democratic", "Joseph R. Biden and Kamala D. Harris", "BIDEN"), "rep": ("Republican", "Donald J. Trump and Michael R. Pence", "TRUMP"),
     "clerk": ("FOR PRESIDENTIAL ELECTORS", None)},
    {"id": "2020-us-senate", "year": 2020, "date": "2020-11-03", "office": "United States Senator",
     "race": r"^(FOR )?UNITED STATES SENATOR\b(?!.*UNEXPIRED)",
     "dem": ("Democratic", "Abby Broyles", "BROYLES"), "rep": ("Republican", "James M. Inhofe", "INHOFE"),
     "clerk": ("FOR UNITED STATES SENATOR", None)},
]

# The official statewide figures this loader was checked against on 2026-10-03 (the Clerk's statistics and, for
# Governor, the Board's certified summary). A run reads the documents again and stops if they read differently.
CHECKED = {
    "2024-president": {"dem": 499599, "rep": 1036213, "other": 30361, "total": 1566173},
    "2022-governor": {"dem": 481904, "rep": 639484, "other": 31896, "total": 1153284},
    "2022-us-senate": {"dem": 369370, "rep": 739960, "other": 41402, "total": 1150732},
    "2022-us-senate-unexpired": {"dem": 405389, "rep": 710643, "other": 34449, "total": 1150481},
    "2020-president": {"dem": 503890, "rep": 1020280, "other": 36529, "total": 1560699},
    "2020-us-senate": {"dem": 509763, "rep": 979140, "other": 67458, "total": 1556361},
}
CLERK = {year: {"id": f"clerk-statistics-{year}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                "title": f"Statistics of the {'Presidential and ' if year % 4 == 0 else ''}Congressional Election from Official Sources for the Election of {day}",
                "url": f"https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf", "file": f"clerk_statistics{year}.pdf"}
         for year, day in ((2024, "November 5, 2024"), (2022, "November 8, 2022"), (2020, "November 3, 2020"))}
PACKETS = {
    "packet-2022": {"id": "ok-seb-meeting-packet-2022-11-15", "kind": "official certified summary",
                    "agency": "Oklahoma State Election Board",
                    "title": "Meeting packet, November 15, 2022: Election Summary Results of the November 8, 2022 General Election",
                    "url": "https://oklahoma.gov/content/dam/ok/en/elections/meeting-packets/2022-meeting-packets/meeting-packet-11152022.pdf",
                    "listed_on": "https://oklahoma.gov/elections/about-us/meeting-notices-agendas-and-minutes-archives/2022-agendas-and-minutes.html",
                    "file": "meeting-packet-11152022.pdf",
                    "sha256": "f01d27e300ee218ec29dfcaa03dbab80197bab3cf8449ffae9486fa5db29b147",
                    # the Governor's figures as page 1 of the packet prints them (Stitt, Hofmeister, Yen, Bruno, Total)
                    "figures": {"2022-governor": {"page": 1, "lines": ["639,484", "481,904", "16,243", "15,653", "1,153,284"]}}},
}

# The kinds of place: (kind, years given, what it is, what its key is)
KINDS = [
    ("county", (2020, 2022, 2024), "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("house", DISTRICT_YEARS, "State House districts of the plan first used in 2022", "district number, as the district of our House races"),
    ("senate", DISTRICT_YEARS, "State Senate districts of the plan first used in 2022", "district number, as the district of our Senate races"),
    ("commissioner", DISTRICT_YEARS, "County commissioner districts", "five-digit county FIPS code, a hyphen, the district number"),
]
KIND_NAMES = [k[0] for k in KINDS]
LEG = {"house": re.compile(r"\bSTATE REPRESENTATIVE\b.*?\bDISTRICT\s*(?:NO\.?\s*)?0*(\d+)"),
       "senate": re.compile(r"\bSTATE SENATOR\b.*?\bDISTRICT\s*(?:NO\.?\s*)?0*(\d+)"),
       "commissioner": re.compile(r"\bCOUNTY COMMISSIONER\b.*?\bDISTRICT\s*(?:NO\.?\s*)?0*(\d+)")}
LAYER_FIELD = {"house": "St_house", "senate": "St_senate", "commissioner": "Comm"}

# Only these headings are ever read (a few spellings each); everything else in a file is skipped unread. The Board's
# old precinct files (20141104_prec.csv) carry county_name and precinct_code; the results site's exports carry precinct
# (the six-digit code, no county name) in the precinct-level file and county (the name) in the county-level file.
COLUMNS = {
    "county": ("county_name", "county", "countyname", "county_desc"),
    "precinct": ("precinct_code", "precinct", "pct_code", "precinctcode", "precinct_number"),
    "race_number": ("race_number", "race_id", "racenumber", "raceid"),
    "race": ("race_description", "race", "race_desc", "contest", "racedescription"),
    "party": ("cand_party", "party", "candidate_party", "candparty"),
    "candidate_number": ("cand_number", "candidate_number", "candnumber", "cand_no"),
    "name": ("cand_name", "candidate", "candidate_name", "candname"),
    "votes": ("cand_tot_votes", "total_votes", "tot_votes", "votes", "cand_total_votes", "candtotvotes"),
    "date": ("elec_date", "election_date", "elecdate"),
}
NEED_PRECINCT = ("precinct", "race", "party", "votes")      # the county is read from the precinct code; a name, where given, must agree
NEED_COUNTY = ("county", "race", "party", "votes")

WHAT = ("How each Oklahoma place voted in six contests of the 2020, 2022 and 2024 general elections: the votes for the "
        "Democratic ticket, the Republican ticket, every other candidate together and the total, added up from the Oklahoma "
        "State Election Board's official precinct results.")
NOTE = ("What this is: how the people of a place voted in that election, in the State Election Board's official precinct "
        "results, added up here by county and, for 2022 and 2024, by state House and Senate district and county commissioner "
        "district, on the lines in force at that election. A district is given only where every precinct voting in it can be "
        "placed in it; nothing is divided by estimate. What this is not: it is not a prediction of any election; it says "
        "nothing about any candidate on a later ballot or about any voter; a nonpartisan office stays nonpartisan; and a "
        "place is not its lines for ever: where a district was drawn again, the figures are for the lines of that year. "
        "Oklahoma allows no write-in votes, so every vote counted here went to a candidate printed on the ballot. The "
        "tickets are named only to say which election this was. In a place with very few voters the split would come "
        "close to saying how particular people voted; those contests are listed in the place's too_few, and a page should "
        "leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), "
               "other (every other candidate, together) and total (the votes for candidates; Oklahoma counts no write-ins). "
               "Minnesota's file calls the first count dfl. A contest a place does not have was not counted on its lines: "
               "districts are given for 2022 and 2024 only, and only where every precinct voting in them could be placed.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same "
           "way. There the split comes close to saying how particular people voted, so a page should leave it out. The counts "
           "are the official record all the same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities and towns, and their wards: a precinct may lie partly inside a city, and neither the Board's precinct "
             "results nor the precinct map says how its votes divide at the city line. School and fire protection districts: "
             "the results do not name them. Judicial districts: a district judge's office can be elected from part of its "
             "district's counties; the counties are given. Districts in 2020: other lines.")
MISSING = ("No precinct-level results file of the State Election Board's for this election is on disk in {folder}, so the "
           "year is left out.")
WHY_NOT = ("A contest is given for a county only where the county's precinct lines add up exactly, candidate by candidate, to "
           "the State Election Board's own county-level file for that contest; coverage.counties_left_out lists any county "
           "where they do not, with both figures and the difference.")


class Stop(Exception):
    """A check failed: nothing is written."""


# ---------------------------------------------------------------- small things

def _now():
    return dt.date.today().isoformat()


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _sha_file(path):
    with open(path, "rb") as fh:
        return _sha(fh.read())


def _save(path, doc):
    """Whole or not at all: written beside the target and renamed into place."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(tmp, path)


def county_fips(n):
    """The Board numbers the counties 01 to 77 alphabetically; the county FIPS code is 40 and 2n-1 in three digits."""
    return f"{STATE_FIPS}{2 * int(n) - 1:03d}"


def long_day(day):
    d = dt.datetime.strptime(day, "%Y%m%d")
    return f"{d:%B} {d.day}, {d.year}"


def bare(name):
    return re.sub(r"[^A-Z]", "", str(name or "").upper())


def fmt(v):
    return ", ".join(f"{v[s]:,}" for s in SIDES)


# ---------------------------------------------------------------- the precinct layer

def fetch_layer(cache, refresh, say):
    """{precinct code: {county, county_name, house, senate, commissioner}} from the Center for Spatial Analysis's layer,
    attributes only, cached as fetched. Returns (precincts, source record)."""
    path = os.path.join(cache, "precincts_layer.json")
    fresh = (not refresh) and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < KEEP_DAYS * 86400
    if fresh:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
    else:
        say("      fetching the precinct layer's attributes (no shapes)")
        meta = json.loads(net.get(LAYER["service"] + "?f=json", accept="application/json"))
        rows, offset = [], 0
        while True:
            q = (f"{LAYER['service']}/query?where=1%3D1&outFields={','.join(LAYER['fields'])}&returnGeometry=false"
                 f"&orderByFields=PCT_CEB&resultOffset={offset}&resultRecordCount=1000&f=json")
            j = json.loads(net.get(q, accept="application/json"))
            if "error" in j:
                raise Stop(f"the precinct layer answered with an error: {j['error']}")
            feats = [f["attributes"] for f in j.get("features") or []]
            rows += [{k: a.get(k) for k in LAYER["fields"]} for a in feats]
            if not j.get("exceededTransferLimit") and len(feats) < 1000:
                break
            offset += len(feats)
        got = {"fetched": _now(), "last_edit": (meta.get("editingInfo") or {}).get("dataLastEditDate"), "rows": rows}
        _save(path, got)
    precincts = {}
    for a in got["rows"]:
        code = str(a.get("PCT_CEB") or "").strip()
        if not re.fullmatch(r"\d{6}", code):
            raise Stop(f"the precinct layer has a precinct code that is not six digits: {code!r}")
        if code in precincts:
            raise Stop(f"the precinct layer lists precinct {code} twice")
        if code[:2] != str(a.get("COUNTY") or "").zfill(2) or county_fips(code[:2])[2:] != str(a.get("CO_FIPS") or "").zfill(3):
            raise Stop(f"precinct {code}: its code, county number and county FIPS code disagree")
        precincts[code] = {"county": county_fips(code[:2]), "county_name": str(a.get("COUNTY_NAM") or "").strip(),
                           "house": str(int(a["St_house"])), "senate": str(int(a["St_senate"])), "commissioner": str(int(a["Comm"]))}
    if len({p["county"] for p in precincts.values()}) != 77:
        raise Stop("the precinct layer does not reach all 77 counties")
    last = got.get("last_edit")
    rec = dict({k: LAYER[k] for k in ("id", "kind", "agency", "title", "url", "service", "listed_on")},
               fetched=got["fetched"], precincts=len(precincts),
               last_edited=dt.datetime.fromtimestamp(last / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if last else None,
               rows_sha256=_sha(json.dumps(got["rows"], sort_keys=True, separators=(",", ":")).encode("utf-8")),
               read="Each precinct's code, county and House, Senate and county commissioner districts; not its shape.")
    return precincts, rec


# ---------------------------------------------------------------- the Board's results files on disk

def came_from(fn, sha, path, level):
    """How a file of the Board's came to be on disk, said only as far as its bytes bear out."""
    if SAVED.get(fn) == sha:
        return (f"the results site's Export menu, \"{EXPORT.get(level, level)}\", read through a browser on {SAVED_ON} because the "
                "site refuses scripts (this loader never requests it); the page was marked Official Results; the SHA-256 says "
                "which bytes were read")
    if fn in SAVED:
        return (f"a copy on disk since {_day(path)}; it is not the copy this loader was checked against on {SAVED_ON}, whose "
                "SHA-256 differs")
    return f"a file on disk since {_day(path)}, not one this loader was checked against"


def _csv_texts(path):
    """(name, text) of each table in a file on disk: a .csv or .txt as it is, a .zip's .csv and .txt members."""
    def text(b):
        for enc in ("utf-8-sig", "cp1252"):
            try:
                return b.decode(enc)
            except UnicodeDecodeError:
                continue
        return b.decode("latin-1")
    low = path.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith((".csv", ".txt")):
                    yield f"{os.path.basename(path)}:{n}", text(z.read(n))
    elif low.endswith((".csv", ".txt")):
        with open(path, "rb") as fh:
            yield os.path.basename(path), text(fh.read())


def _columns(header):
    """{our name: index} for the allowlisted headings found in a header row."""
    norm = [re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_") for h in header]
    out = {}
    for ours, spellings in COLUMNS.items():
        hits = [i for i, h in enumerate(norm) if h in spellings]
        if len(hits) > 1:
            raise Stop(f"two columns could be the {ours}: {[header[i] for i in hits]}")
        if hits:
            out[ours] = hits[0]
    return out


def _date(v):
    v = str(v or "").strip()
    for f in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(v.split(" ")[0], f).strftime("%Y%m%d")
        except ValueError:
            continue
    return None


def read_folder(folder, day, say):
    """The tables on disk for one election: {"precinct": [rows], "county": [rows], "files": {file name: {"sha256",
    "path", "levels", "lines"}}}. Each row is a dict of the allowlisted columns only. A table is precinct-level when it
    has a precinct column, county-level when it has a county column and none for the precinct."""
    out = {"precinct": [], "county": [], "files": {}}
    if not os.path.isdir(folder):
        return out
    for fn in sorted(os.listdir(folder)):
        path = os.path.join(folder, fn)
        if not os.path.isfile(path) or not fn.lower().endswith((".zip", ".csv", ".txt")):
            continue
        info = out["files"][fn] = {"sha256": _sha_file(path), "path": path, "levels": [], "lines": 0}
        for name, text in _csv_texts(path):
            reader = csv.reader(io.StringIO(text))
            header = next(reader, None)
            if not header:
                continue
            cols = _columns(header)
            level = "precinct" if "precinct" in cols else "county"
            need = NEED_PRECINCT if level == "precinct" else NEED_COUNTY
            if any(k not in cols for k in need):
                say(f"      {name}: not a results table this loader knows; its headings are {header}")
                continue
            n = 0
            for row in reader:
                if not row or all(not c.strip() for c in row):
                    continue
                r = {k: (row[i].strip() if i < len(row) else "") for k, i in cols.items()}
                if "date" in r and r["date"] and _date(r["date"]) != day:
                    raise Stop(f"{name}: a row is dated {r['date']}, not the election of {day}")
                out[level].append(r)
                n += 1
            info["levels"].append(level)
            info["lines"] += n
            say(f"      {name}: {n:,} {level} lines")
    return out


def _votes(v, what):
    v = str(v).replace(",", "").strip()
    if not re.fullmatch(r"\d+", v):
        raise Stop(f"{what}: votes {v!r} is not a whole number")
    return int(v)


def find_contests(rows, contests, where):
    """{contest id: race key} for each contest, found by its title; exactly one race may match. The race key is the
    race number where the file has one, else the title."""
    titles = collections.defaultdict(set)
    for r in rows:
        titles[(r.get("race_number") or "", re.sub(r"\s+", " ", r["race"].upper()).strip())].add(r.get("county"))
    out = {}
    for c in contests:
        hits = [k for k in titles if re.search(c["race"], k[1])]
        if c.get("first"):
            hits = [k for k in hits if not re.search(r"^(FOR )?VICE", k[1])]
        if len({k[1] for k in hits}) != 1:
            near = sorted({k[1] for k in titles if re.search(r"PRESIDENT|GOVERNOR|SENATOR", k[1]) and not re.search(r"STATE SENATOR|LIEUTENANT", k[1])})
            raise Stop(f"{where}: {c['office']}: {'no contest' if not hits else 'more than one contest'} matches; the titles near it are {near}")
        out[c["id"]] = hits[0][1]
    return out


def side_of(party):
    """0 for the Democratic line, 1 for the Republican, 2 for any other."""
    party = str(party or "").upper().strip()
    return 0 if party in ("DEM", "D", "DEMOCRATIC") else 1 if party in ("REP", "R", "REPUBLICAN") else 2


def cand_key(r):
    """Which candidate a line is for, so that the two files can be compared candidate by candidate: the Board's number for
    the candidate in the contest where the file gives one, else the name as letters only. Kept in memory, never written."""
    num = str(r.get("candidate_number") or "").strip()
    return ("number", num) if num else ("name", bare(r.get("name")))


def tally_year(year, data, contests, precincts, say):
    """Everything one election's files give: per precinct per contest the four counts; which precincts carried which
    House, Senate and commissioner contests; per county per contest the votes of each candidate in the precinct file;
    and the county-level file's lines, by county and contest, as four counts and candidate by candidate. A precinct's
    county is the first two digits of its code (the Board's county number); where a file also names the county, the name
    must agree."""
    where = f"the {DAYS[year]} precinct file"
    rows = data["precinct"]
    if not rows:
        raise Stop(f"{where}: no precinct lines")
    mine = [c for c in contests if c["year"] == year]
    race_of = find_contests(rows, mine, where)
    want = {t: cid for cid, t in race_of.items()}
    county_no = {bare(p["county_name"]): p["county"] for p in precincts.values()}
    per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))   # precinct -> contest -> counts
    seen, names, leg = set(), collections.defaultdict(lambda: collections.defaultdict(set)), collections.defaultdict(set)
    cand, sides = collections.defaultdict(collections.Counter), collections.defaultdict(dict)
    county_of = {}
    for r in rows:
        title = re.sub(r"\s+", " ", r["race"].upper()).strip()
        code = re.sub(r"\D", "", r["precinct"]).zfill(6)
        if len(code) != 6:
            raise Stop(f"{where}: precinct code {r['precinct']!r} is not a precinct code")
        cty = county_fips(code[:2]) if 1 <= int(code[:2]) <= 77 else None
        named = county_no.get(bare(r["county"])) if r.get("county") else None
        if cty is None or (named and named != cty):
            raise Stop(f"{where}: precinct {code} is filed under {r.get('county') or 'no county'}, which its code does not name")
        county_of[code] = cty
        for kind, rx in LEG.items():
            m = rx.search(title)
            if m:
                leg[(kind, m.group(1), cty if kind == "commissioner" else "")].add(code)
        cid = want.get(title)
        if not cid:
            continue
        ck = cand_key(r)
        key = (code, title, r.get("race_number"), r["party"].upper(), ck)
        if key in seen:
            raise Stop(f"{where}: precinct {code} has the same line twice in {title}")
        seen.add(key)
        v = _votes(r["votes"], f"{where}, precinct {code}, {title}")
        side = side_of(r["party"])
        if sides[cid].setdefault(ck, side) != side:
            raise Stop(f"{where}: {title}: one candidate's lines carry two parties")
        if side < 2:
            names[cid][("dem", "rep")[side]].add((r.get("name") or "").upper())
        cnt = per[code][cid]
        cnt[side] += v
        cnt[3] += v
        cand[(cty, cid)][ck] += v
    for c in mine:
        for side in ("dem", "rep"):
            got = {n for n in names[c["id"]][side] if n}
            if len(got) > 1:
                raise Stop(f"{where}: {c['office']}: more than one {c[side][0]} line ({sorted(got)})")
            if got and c[side][2] not in next(iter(got)):
                raise Stop(f"{where}: {c['office']}: the {c[side][0]} line names {next(iter(got))}, not {c[side][1]}")
            if not names[c["id"]][side]:
                raise Stop(f"{where}: {c['office']}: no {c[side][0]} line")
    county_rows = collections.defaultdict(lambda: [0, 0, 0, 0])
    ccand, csides = collections.defaultdict(collections.Counter), collections.defaultdict(dict)
    if data["county"]:
        cwhere = f"the {DAYS[year]} county file"
        crace = find_contests(data["county"], mine, cwhere)
        cwant = {t: cid for cid, t in crace.items()}
        for r in data["county"]:
            cid = cwant.get(re.sub(r"\s+", " ", r["race"].upper()).strip())
            if not cid:
                continue
            cty = county_no.get(bare(r["county"]))
            if not cty:
                raise Stop(f"{cwhere} names a county the precinct layer does not: {r['county']!r}")
            side, ck = side_of(r["party"]), cand_key(r)
            if csides[cid].setdefault(ck, side) != side:
                raise Stop(f"{cwhere}: {r['race']}: one candidate's lines carry two parties")
            v = _votes(r["votes"], f"{cwhere}, {r['county']}")
            county_rows[(cty, cid)][side] += v
            county_rows[(cty, cid)][3] += v
            ccand[(cty, cid)][ck] += v
        for c in mine:                      # the two files must number the two tickets alike, or nothing can be compared
            for s, label in ((0, "Democratic"), (1, "Republican")):
                a = {k for k, x in sides[c["id"]].items() if x == s}
                b = {k for k, x in csides[c["id"]].items() if x == s}
                if len(a) != 1 or a != b:
                    raise Stop(f"{c['office']}, {year}: the precinct file and the county file do not give the {label} ticket the same "
                               "candidate number")
    say(f"      {year}: {len(per):,} precinct units carry the contests; {len(leg):,} House, Senate and commissioner contests on the ballot"
        + (f"; county file: {len({k[0] for k in county_rows}):,} counties" if county_rows else "; no county file"))
    return {"per": per, "leg": leg, "county_of": county_of, "county_rows": county_rows, "race_of": race_of,
            "cand": cand, "ccand": ccand}


def place_precincts(year, t, precincts):
    """Which districts of each kind can be given for one year: {kind: {district key: [precinct codes]}} and
    {kind: {district key: reason}} for those left out. A precinct the layer does not know, or one that the year's own
    House, Senate or commissioner contests put on another side of a line than the layer does, leaves out every district
    of that kind reaching its county."""
    voting = set(t["per"])
    unknown = sorted(p for p in voting if p not in precincts)
    reach = collections.defaultdict(lambda: collections.defaultdict(set))       # kind -> county -> districts reaching it (layer)
    members = collections.defaultdict(lambda: collections.defaultdict(list))
    for code, p in precincts.items():
        for kind in ("house", "senate", "commissioner"):
            key = p[kind] if kind != "commissioner" else f"{p['county']}-{p[kind]}"
            reach[kind][p["county"]].add(key)
            if code in voting:
                members[kind][key].append(code)
    bad = collections.defaultdict(lambda: collections.defaultdict(set))        # kind -> county -> why
    for code in unknown:
        cty = t["county_of"][code]
        for kind in ("house", "senate", "commissioner"):
            bad[kind][cty].add(f"precinct {code[:2]}-{code[2:]} is not on the precinct map")
    wrong = collections.defaultdict(list)
    for (kind, num, cty), codes in t["leg"].items():
        key = num if kind != "commissioner" else f"{cty}-{num}"
        on_map = {c for c, p in precincts.items() if (p[kind] if kind != "commissioner" else f"{p['county']}-{p[kind]}") == key}
        for code in codes:
            if code in precincts and code not in on_map:
                wrong[kind].append(code)
                bad[kind][precincts[code]["county"]].add(f"precinct {code[:2]}-{code[2:]} voted in {kind} district {num}, which the map does not put it in")
        for code in on_map & voting - codes:
            wrong[kind].append(code)
            bad[kind][precincts[code]["county"]].add(f"precinct {code[:2]}-{code[2:]} lies in {kind} district {num} on the map but did not vote in its contest")
    checked = sum(len(v) for v in t["leg"].values())
    flagged = sum(len(set(v)) for v in wrong.values())
    if checked and flagged > 0.05 * checked:
        raise Stop(f"{year}: {flagged} of {checked} precinct-contest pairs disagree with the precinct map; the map is not this election's lines")
    given, left = {}, {}
    for kind in ("house", "senate", "commissioner"):
        given[kind], left[kind] = {}, {}
        out_counties = bad[kind]
        for key, codes in members[kind].items():
            hit = sorted(c for c in out_counties if key in reach[kind][c])
            if hit:
                left[kind][key] = "; ".join(sorted({w for c in hit for w in out_counties[c]}))
            else:
                given[kind][key] = sorted(codes)
    return given, left, unknown


# ---------------------------------------------------------------- the official totals

def read_clerk(path, state="OKLAHOMA"):
    """The state's page of the Clerk's statistics: {(section, subsection): [(label, votes)]}."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, tx) in enumerate(lines) if tx.strip() == state), None)
    if start is None:
        raise Stop(f"{os.path.basename(path)}: no {state} heading")
    page = lines[start][0]
    out, section, sub = collections.defaultdict(list), None, None
    for p, _y, tx in lines[start + 1:]:
        tx = tx.strip()
        if p != page or tx.startswith("FOR UNITED STATES REPRESENTATIVE"):
            break
        if tx.startswith("FOR "):
            section, sub = tx, None
            continue
        if tx.startswith("(For"):
            sub = tx
            continue
        m = re.match(r"^(.*?)\s*\.{3,}\s*([\d,]+)$", tx)
        if section and m:
            out[(section, sub)].append((m.group(1).strip(), int(m.group(2).replace(",", ""))))
    top = next((tx.strip() for p, _y, tx in lines if p == page and tx.strip().isdigit()), None)
    return {"where": f"Oklahoma, page {top}" if top else f"Oklahoma, page {page} of the PDF", "sections": dict(out)}


def clerk_figures(doc, c):
    section, sub = c["clerk"]
    rows = [v for k, v in doc["sections"].items() if k[0] == section and (sub is None and k[1] is None or sub and k[1] and k[1].startswith(sub))]
    if len(rows) != 1:
        raise Stop(f"the Clerk's {section} {sub or ''}: found {len(rows)} sections")
    lines = [(lab, v) for lab, v in rows[0] if lab not in ("Under Votes", "Over Votes")]
    party = (lambda s: s) if section == "FOR PRESIDENTIAL ELECTORS" else (lambda s: s.rsplit(",", 1)[-1].strip())
    dem = [(lab, v) for lab, v in lines if party(lab).startswith("Democrat")]
    rep = [(lab, v) for lab, v in lines if party(lab) == "Republican"]
    if len(dem) != 1 or len(rep) != 1:
        raise Stop(f"the Clerk's {section}: not one Democratic and one Republican line")
    if section != "FOR PRESIDENTIAL ELECTORS":
        for side, (lab, _v) in (("dem", dem[0]), ("rep", rep[0])):
            if c[side][2] not in lab.upper():
                raise Stop(f"the Clerk's {section}: the {c[side][0]} line names {lab}, not {c[side][1]}")
    total = sum(v for _l, v in lines)
    return {"dem": dem[0][1], "rep": rep[0][1], "other": total - dem[0][1] - rep[0][1], "total": total}


def official_totals(contests, cache, refresh, say):
    """{contest id: figures} from the Clerk's statistics and the Board's packet, each checked against CHECKED."""
    out, recs = {}, []
    for year in sorted({c["year"] for c in contests if c.get("clerk")}, reverse=True):
        src = CLERK[year]
        path = os.path.join(cache, src["file"])
        net.download(src["url"], path, 0 if refresh else 365, tries=3, say=say)
        doc = read_clerk(path)
        for c in contests:
            if c["year"] == year and c.get("clerk"):
                out[c["id"]] = dict(clerk_figures(doc, c), source=src["id"], where=doc["where"])
        recs.append(dict({k: src[k] for k in ("id", "kind", "agency", "title", "url")}, fetched=_day(path), sha256=_sha_file(path),
                         where=doc["where"], read="The Oklahoma lines for presidential electors and United States Senator."))
    for key in sorted({c["packet"] for c in contests if c.get("packet")}):
        src = PACKETS[key]
        path = os.path.join(cache, src["file"])
        net.download(src["url"], path, 0 if refresh else 365, tries=3, say=say)
        sha = _sha_file(path)
        if sha != src["sha256"]:
            raise Stop(f"{src['title']}: the packet has changed (SHA-256 {sha}); read it again and type its figures")
        from ballot import pdftext
        text = collections.defaultdict(str)
        for p, _y, tx in pdftext.lines(path):
            text[p] += " " + tx
        for cid, f in src["figures"].items():
            missing = [n for n in f["lines"] if n not in text[f["page"]]]
            if missing:
                raise Stop(f"{src['title']}: page {f['page']} does not print {missing}")
            out[cid] = dict(CHECKED[cid], source=src["id"], where=f"page {f['page']}, the column headed FOR GOVERNOR")
        recs.append(dict({k: src[k] for k in ("id", "kind", "agency", "title", "url", "listed_on")}, fetched=_day(path), sha256=sha,
                         read="Only the Governor's column of page 1; its figures are typed in the loader and found in the packet's text at each run."))
    for cid, v in out.items():
        if {s: v[s] for s in SIDES} != CHECKED[cid]:
            raise Stop(f"{cid}: the official figures now read {fmt(v)}, not the {fmt(CHECKED[cid])} this loader was checked against")
    return out, recs


# ---------------------------------------------------------------- our places

def our_places(db):
    """{kind: {key: name}} of our Oklahoma places and races, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(dict)
        for kind, pid, name in con.execute("SELECT kind, id, name FROM sl_places WHERE (kind = 'county' AND id LIKE '40___') OR id LIKE 'OK-%'"):
            out[kind][pid] = name
        for office, jid, district, jur in con.execute("SELECT office_kind, jurisdiction_id, district, jurisdiction FROM sl_races WHERE state = 'OK'"):
            if office == "state_senate":
                out["senate"][str(district)] = f"Senate District {district}"
            elif office == "state_house":
                out["house"][str(district)] = f"House District {district}"
            elif office == "county_commissioner" and district:
                out["commissioner"][f"{jid}-{district}"] = f"{jur}, District {district}"
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


# ---------------------------------------------------------------- adding up

def listed(items):
    items = list(items)
    return " and ".join(items) if len(items) < 3 else ", ".join(items[:-1]) + " and " + items[-1]


def by_side(diff):
    return ", ".join(f"{label} {diff[s]:+,}" for s, label in (("dem", "Democratic"), ("rep", "Republican"), ("other", "other"), ("total", "total"))
                     if diff.get(s))


def county_check(t, mine, county_name, by_county):
    """Each county's precinct lines against the Board's county-level file, candidate by candidate, contest by contest:
    {contest id: {"compared", "equal", "file": the county file's four counts added up, "out": {county: the record of a
    county whose precincts do not add up to it}}}. Empty when the election has no county-level file on disk."""
    if not t["county_rows"]:
        return {}
    res = {}
    for c in mine:
        cid = c["id"]
        counties = sorted({k[0] for k in t["cand"] if k[1] == cid} | {k[0] for k in t["ccand"] if k[1] == cid})
        out, file_sum = {}, [0, 0, 0, 0]
        for cty in counties:
            fb_l = t["county_rows"].get((cty, cid), [0, 0, 0, 0])
            file_sum = [x + y for x, y in zip(file_sum, fb_l)]
            a = {k: v for k, v in t["cand"].get((cty, cid), {}).items() if v}
            b = {k: v for k, v in t["ccand"].get((cty, cid), {}).items() if v}
            if a == b:
                continue
            fa = dict(zip(SIDES, by_county.get(cty, {}).get(cid, [0, 0, 0, 0])))
            fb = dict(zip(SIDES, fb_l))
            diff = {s: fa[s] - fb[s] for s in SIDES}
            d = diff["total"]
            gap = (f"The precinct lines are {-d:,} vote{'s' if d != -1 else ''} short" if d < 0 else
                   f"The precinct lines are {d:,} vote{'s' if d != 1 else ''} over" if d > 0 else
                   "The totals are equal but the candidates' counts are not")
            name = county_name.get(cty, cty)
            out[cty] = {"county": cty, "name": name, "sum_of_precincts": fa, "county_file": fb, "difference": diff,
                        "candidates_differing": sum(1 for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)),
                        "statement": (f"{name}, {c['date'][:4]} {c['office']}: this county's precinct lines add up to {fa['total']:,} votes "
                                      f"(Democratic {fa['dem']:,}, Republican {fa['rep']:,}, other {fa['other']:,}) and the State Election "
                                      f"Board's county-level file gives it {fb['total']:,} (Democratic {fb['dem']:,}, Republican {fb['rep']:,}, "
                                      f"other {fb['other']:,}). {gap}"
                                      + (f" (precinct lines less county file: {by_side(diff)})" if by_side(diff) else "")
                                      + ", so this contest is not given for the county, or for a state House, state Senate or county "
                                        "commissioner district reaching into it.")}
        res[cid] = {"compared": len(counties), "equal": len(counties) - len(out), "file": dict(zip(SIDES, file_sum)), "out": out}
    return res


def statewide_control(c, got, n_units, off, chk, county_source):
    """The statewide line of one contest, stated as it is, with the county-by-county account where a county-level file
    was read. Raises Stop where the arithmetic itself fails, or where the precincts differ from the official figures and
    there is no county-level file to say where."""
    cid = c["id"]
    theirs = {s: off[s] for s in SIDES}
    diff = {s: got[s] - theirs[s] for s in SIDES if got[s] != theirs[s]}
    rec = {"sum_of_precincts": got, "precincts": n_units, "official": theirs, "equal": not diff, "source": off["source"], "where": off["where"]}
    if diff:
        rec["difference"] = diff
    d = got["total"] - theirs["total"]
    gap = (f"{-d:,} vote{'s' if d != -1 else ''} short of it" if d < 0 else f"{d:,} vote{'s' if d != 1 else ''} over it" if d > 0
           else "equal to it in total but not side by side")
    if chk is None:
        if diff:
            raise Stop(f"{cid}: the precincts add up to {fmt(got)}, the official figures are {fmt(theirs)}, and no county-level file is on "
                       "disk to say where the difference lies")
        rec["statement"] = (f"Statewide the precinct lines add up to {got['total']:,} votes, equal to the official total side by side. "
                            "No county-level file was read for this election.")
        return rec, True
    out = list(chk["out"].values())
    fsum = chk["file"]
    if any(sum(r["difference"][s] for r in out) != got[s] - fsum[s] for s in SIDES):
        raise Stop(f"{cid}: the counties' differences do not add up to the difference between the precinct lines and the county-level file")
    agrees = fsum == theirs
    rec["county_file"] = {"sum": fsum, "equal_to_official": agrees, "source": county_source}
    rec["counties"] = {"compared": chk["compared"], "equal": chk["equal"], "left_out": [r["name"] for r in out], "source": county_source,
                       "what": "every county's precinct lines against the same county's lines in the Board's county-level file, candidate by candidate"}
    if not agrees:
        state_line = (f"The Board's county-level file adds up to {fsum['total']:,} votes (Democratic {fsum['dem']:,}, Republican {fsum['rep']:,}, "
                      f"other {fsum['other']:,}) and the official statewide total named here is {theirs['total']:,} (Democratic "
                      f"{theirs['dem']:,}, Republican {theirs['rep']:,}, other {theirs['other']:,}). The two official figures disagree; this "
                      f"file does not say which is right and gives no statewide figure for the contest. The precinct lines add up to "
                      f"{got['total']:,}.")
    elif not diff:
        state_line = (f"Statewide the precinct lines add up to {got['total']:,} votes, equal to the official total side by side, and so does "
                      "the Board's county-level file.")
    else:
        state_line = (f"Statewide the precinct lines add up to {got['total']:,} votes and the official total is {theirs['total']:,}: the "
                      f"precinct lines are {gap} ({by_side(diff)}), because the precinct lines of {len(out)} "
                      f"{'county' if len(out) == 1 else 'counties'} do not add up to the Board's own county-level file, which itself adds "
                      "up to the official statewide total.")
    if not out:
        county_line = (f"In all {chk['compared']} counties the precinct lines add up exactly to the Board's county-level file, candidate by "
                       "candidate.")
    else:
        names = [r["name"] for r in out]
        who = listed(names) if len(names) <= 12 else "named in coverage.counties_left_out"
        county_line = (f"In {chk['equal']} of {chk['compared']} counties the precinct lines add up exactly to the Board's county-level file, "
                       f"candidate by candidate, and the contest is given for them. It is left out for the other {len(out)} ({who}) and for "
                       "any state House, state Senate or county commissioner district reaching into them; coverage.counties_left_out gives "
                       "both figures for each." + (" Their differences cancel one another statewide." if agrees and not diff else ""))
    rec["statement"] = state_line + " " + county_line
    return rec, agrees and not diff and not out


def build(years, contests, precincts, official, ours=None):
    """The document, from {year: tally} (the years whose files are on disk), checked. Raises Stop when the arithmetic
    fails; a county whose precincts do not add up to the Board's county-level file is not a reason to stop: the contest
    is left out there, and said so."""
    contests = [c for c in contests if c["year"] in years]
    names = {"county": {}, "house": {}, "senate": {}, "commissioner": {}}
    for p in precincts.values():
        names["county"][p["county"]] = ((ours or {}).get("county", {}).get(p["county"])
                                         or f"{p['county_name'].title().replace('Mcc', 'McC').replace('Mci', 'McI')} County")
    reach_of = {"county": collections.defaultdict(set), "house": collections.defaultdict(set),
                "senate": collections.defaultdict(set), "commissioner": collections.defaultdict(set)}   # place -> counties (map)
    for p in precincts.values():
        names["house"][p["house"]] = f"House District {p['house']}"
        names["senate"][p["senate"]] = f"Senate District {p['senate']}"
        names["commissioner"][f"{p['county']}-{p['commissioner']}"] = f"{names['county'][p['county']]}, District {p['commissioner']}"
        for kind in ("house", "senate"):
            reach_of[kind][p[kind]].add(p["county"])
        reach_of["commissioner"][f"{p['county']}-{p['commissioner']}"].add(p["county"])
        reach_of["county"][p["county"]].add(p["county"])
    full = {k: collections.defaultdict(dict) for k in KIND_NAMES}          # every sum, before any contest is left out anywhere
    control, coverage_left, unknown_all, checks, plain = {}, {k: {} for k in ("house", "senate", "commissioner")}, {}, {}, True
    add = lambda a, b: [x + y for x, y in zip(a, b)]                                        # noqa: E731
    for year, t in sorted(years.items(), reverse=True):
        mine = [c for c in contests if c["year"] == year]
        by_county = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))
        state = collections.defaultdict(lambda: [0, 0, 0, 0])
        for code, cs in t["per"].items():
            for cid, v in cs.items():
                by_county[t["county_of"][code]][cid] = add(by_county[t["county_of"][code]][cid], v)
                state[cid] = add(state[cid], v)
        chk = county_check(t, mine, names["county"], by_county)
        checks.update(chk)
        for c in mine:
            n_units = sum(1 for cs in t["per"].values() if c["id"] in cs)
            control[c["id"]], ok = statewide_control(c, dict(zip(SIDES, state[c["id"]])), n_units, official[c["id"]], chk.get(c["id"]),
                                                     f"ok-seb-counties-{year}")
            plain = plain and ok
        for cty, cs in by_county.items():
            for cid, v in cs.items():
                full["county"][cty][cid] = v
        if year in DISTRICT_YEARS:
            given, left, unknown = place_precincts(year, t, precincts)
            unknown_all[str(year)] = [f"{u[:2]}-{u[2:]}" for u in unknown]
            for kind in ("house", "senate", "commissioner"):
                for key, codes in given[kind].items():
                    for c in mine:
                        tot = [0, 0, 0, 0]
                        for code in codes:
                            tot = add(tot, t["per"][code].get(c["id"], [0, 0, 0, 0]))
                        full[kind][key][c["id"]] = tot
                for key, why in left[kind].items():
                    coverage_left[kind].setdefault(key, {})[str(year)] = why
                # the kind adds up: districts given, plus the precincts of those left out and of unknown precincts
                for c in mine:
                    s = [0, 0, 0, 0]
                    for key in given[kind]:
                        s = add(s, full[kind][key][c["id"]])
                    placed = {code for codes in given[kind].values() for code in codes}
                    for code, cs in t["per"].items():
                        if code not in placed:
                            s = add(s, cs.get(c["id"], [0, 0, 0, 0]))
                    if s != state[c["id"]]:
                        raise Stop(f"{year} {kind}: the districts and the precincts left out do not add up to the statewide sum")
    # counties add up to the state
    for c in contests:
        s = [0, 0, 0, 0]
        for cty in full["county"]:
            s = add(s, full["county"][cty].get(c["id"], [0, 0, 0, 0]))
        if dict(zip(SIDES, s)) != control[c["id"]]["sum_of_precincts"]:
            raise Stop(f"{c['id']}: the counties do not add up to the statewide sum")
    # a contest is left out for a county whose precincts do not add up to the county-level file, and for every
    # district reaching into it; nothing is moved or shared out
    out_of = {cid: set(chk["out"]) for cid, chk in checks.items()}
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    not_given = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    for kind in KIND_NAMES:
        for key, cs in full[kind].items():
            for cid, v in cs.items():
                bad = out_of.get(cid, set()) & reach_of[kind].get(key, {key} if kind == "county" else set())
                if bad:
                    not_given[kind][key][cid] = ("the precinct lines of " + listed(sorted(names["county"].get(x, x) for x in bad))
                                                 + " do not add up to the Board's county-level file for this contest")
                    continue
                votes[kind][key][cid] = v

    def few(rec):
        hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
        if hold:
            rec["too_few"] = hold
        return rec
    order = [c["id"] for c in contests]
    sort_key = lambda k: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", k)]    # noqa: E731
    places, taken = {}, {}
    for kind in KIND_NAMES:
        places[kind] = {}
        for key in sorted(set(votes[kind]) | set(not_given[kind]), key=sort_key):
            v = {cid: dict(zip(SIDES, votes[kind][key][cid])) for cid in order if cid in votes[kind].get(key, {})}
            ng = {cid: not_given[kind][key][cid] for cid in order if cid in not_given[kind].get(key, {})}
            if ng:
                taken.setdefault(kind, {})[key] = {"name": names[kind].get(key, key), "contests": ng}
            if not v:
                continue
            rec = {"name": names[kind].get(key, key), "votes": v}
            if ng:
                rec["not_given"] = ng
            if kind == "commissioner":
                rec["counties"] = [key.split("-")[0]]
            places[kind][key] = few(rec)
    any_out = any(chk["out"] for chk in checks.values())
    kinds = {}
    for kind, yrs, what, keytext in KINDS:
        cids = [c["id"] for c in contests if c["year"] in yrs]
        k = {"what": what, "key": keytext, "places": len(places[kind]), "contests": cids,
             "given": {cid: sum(1 for p in places[kind].values() if cid in p["votes"]) for cid in cids},
             "covers_the_state": kind == "county" and not any_out,
             "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if kind == "county" and any_out:
            k["why_not_everywhere"] = WHY_NOT
        if kind != "county":
            k["why_not_2020"] = ("The 2020 election was held on the lines drawn in 2011; the lines drawn in 2021 were first used "
                                 "in 2022, and the precinct map is of today's precincts, so 2020 is given for counties only.")
            n_left = {y: sum(1 for v in coverage_left[kind].values() if y in v) for y in (str(x) for x in DISTRICT_YEARS)}
            k["note"] = (f"A district is given in a year only where every precinct voting in it can be placed in it, on the precinct "
                         f"map and by the year's own contests. Left out: {', '.join(f'{y}: {n}' for y, n in n_left.items() if y in {str(x) for x in years})}; "
                         "each is named under coverage with the reason."
                         + (" A contest is also left out for a district reaching into a county whose precinct lines do not add up to the "
                            "Board's county-level file for it (coverage.left_out_with_their_county)." if any_out else ""))
        kinds[kind] = k
    cov = {"not_given": NOT_GIVEN, "districts_not_given": {k: dict(sorted(v.items(), key=lambda kv: sort_key(kv[0]))) for k, v in coverage_left.items() if v},
           "precincts_not_on_the_map": unknown_all,
           "write_ins": "Oklahoma counts no write-in votes, so other is every other candidate printed on the ballot."}
    if checks:
        cov["counties_left_out"] = {cid: list(chk["out"].values()) for cid, chk in checks.items() if chk["out"]}
        cov["left_out_with_their_county"] = dict(taken, what=(
            "Each county or district that lost a contest because its precinct lines, or those of a county it reaches into, do not add up "
            "to the Board's county-level file, with the contests and why. Nothing was moved or shared out."))
    if ours is not None:
        cov["our_places"] = {}
        for kind in ("county", "house", "senate", "commissioner"):
            ids = sorted(ours.get(kind, {}), key=sort_key)
            have = [i for i in ids if i in places[kind]]
            cov["our_places"][kind] = {"places": len(ids), "with_votes": len(have), "without": [i for i in ids if i not in places[kind]]}
        cities = sorted(ours.get("mcd", {}))
        cov["our_places"]["mcd"] = {"places": len(cities), "with_votes": 0, "without": cities, "why": "Cities are not given (see not_given)."}
        cov["our_places"]["read"] = f"sl_places and sl_races in ballot_local_2026.sqlite, opened read-only on {_now()}"
    return {"contests": contests, "places": places, "kinds": kinds, "control": control, "coverage": cov, "checks": checks, "plain": plain}


CONTROL_COUNTY = ("For each contest every county's precinct lines were added up and compared, candidate by candidate, with the same "
                  "county's lines in the State Election Board's own county-level results file for that election. A contest is given "
                  "for a county, and for a state House, state Senate or county commissioner district reaching into it, only where the "
                  "two are exactly equal; where they are not, it is left out there and coverage.counties_left_out states both figures "
                  "and the difference. Each contest's statewide line is stated as it is, against the Clerk of the House's statistics "
                  "(for Governor in 2022, the Board's certified summary). Before anything was left out, the counties added up to the "
                  "sum of the precinct lines, and so did each kind of district with the precincts it leaves out; every precinct that "
                  "carried a state House, Senate or county commissioner contest lies in that district on the precinct map, or every "
                  "district of that kind reaching its county is left out. No number was changed to make anything fit.")
CONTROL_PLAIN = ("For every contest the precinct lines add up exactly to the official statewide figures (the Clerk of the House's "
                 "statistics; for Governor, the Board's certified summary); counties add up to the statewide sum, and each kind of "
                 "district, with the precincts it leaves out, does too; every precinct that carried a state House, Senate or county "
                 "commissioner contest lies in that district on the precinct map.")


def document(built, sources, years_read, years_missing):
    contests = []
    for c in built["contests"]:
        ctl = built["control"][c["id"]]
        rec = {"id": c["id"], "date": c["date"], "office": c["office"], "table": f"ok-seb-precincts-{c['year']}",
               "kinds": [k for k, yrs, _w, _k in KINDS if c["year"] in yrs],
               "dem": {"party": c["dem"][0], "ticket": c["dem"][1], "column": "the lines with the party letters DEM"},
               "rep": {"party": c["rep"][0], "ticket": c["rep"][1], "column": "the lines with the party letters REP"},
               "other": {"what": "every other candidate, together (Oklahoma counts no write-ins)"},
               "total": {"what": "the votes cast for candidates"}}
        # the statewide figure is the official statewide total: the precinct lines equal it, or differ from it by what the
        # control states; where the Board's county-level file and that total disagree, none is given
        if ctl.get("county_file", {}).get("equal_to_official", True):
            rec["statewide"] = dict(ctl["official"])
            if not ctl["equal"]:
                rec["statewide_note"] = ("The official statewide total. The precinct lines add up to "
                                         f"{ctl['sum_of_precincts']['total']:,} votes; control.contests says where the difference lies.")
        else:
            rec["statewide_note"] = "Not given: the Board's county-level file and the official statewide total disagree (control.contests has both)."
        rec["official_source"] = ctl["source"]
        if c["id"] in built["checks"]:
            rec["counties_given"] = built["checks"][c["id"]]["equal"]
            rec["counties_left_out"] = len(built["checks"][c["id"]]["out"])
        contests.append(rec)
    left = {cid: f"{len(chk['out'])} of {chk['compared']} counties left out" for cid, chk in built["checks"].items() if chk["out"]}
    every_year_checked = all(c["id"] in built["checks"] for c in built["contests"])
    control = {"result": "equal" if built["plain"] else "equal where given",
               "statement": CONTROL_COUNTY if built["checks"] else CONTROL_PLAIN,
               "years_read": sorted(years_read), "contests": built["control"]}
    if built["checks"] and not every_year_checked:
        control["statement"] += (" An election with no county-level file on disk is checked against the official statewide figures only, "
                                 "and its precinct lines must equal them.")
    if left:
        control["left_out"] = left
    if years_missing:
        control["years_missing"] = years_missing
    return {"what": WHAT, "note": NOTE, "state": "OK", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
            "vote_keys": list(SIDES), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": contests, "kinds": built["kinds"],
            "control": control, "coverage": built["coverage"], "sources": sources, "places": built["places"]}


# ---------------------------------------------------------------- the run

def run(cache=CACHE, out=OUT, refresh=False, db=DB, say=print):
    os.makedirs(cache, exist_ok=True)
    years, sources, missing = {}, [], {}
    for year in sorted(DAYS, reverse=True):
        folder = os.path.join(cache, DAYS[year])
        os.makedirs(folder, exist_ok=True)
        data = read_folder(folder, DAYS[year], say)
        if not data["precinct"]:
            rel = os.path.relpath(folder, HERE)
            missing[str(year)] = {"results_site": RESULTS_SITE.format(day=DAYS[year]), "folder": rel, "why": MISSING.format(folder=rel)}
            say(f"   {year}: no precinct-level results file in {rel}; the year is left out")
            continue
        years[year] = data
    if not years:
        say("   nothing to add up: no year's precinct-level results file is on disk; nothing written")
        return None
    precincts, layer_rec = fetch_layer(cache, refresh, say)
    official, official_recs = official_totals([c for c in CONTESTS if c["year"] in years], cache, refresh, say)
    tallies = {y: tally_year(y, d, CONTESTS, precincts, say) for y, d in years.items()}
    built = build(tallies, CONTESTS, precincts, official, our_places(db))
    read = {"precinct": ("Only the precinct code (two digits for the county, four for the precinct), the contest's number and title, "
                         "each line's party letters and candidate number, the candidate's name (kept only on the Democratic and "
                         "Republican lines of the contests named here, to check which election it is), the line's total votes, the "
                         "election date, and the county's name where an older file carries one."),
            "county": ("Only the county's name, the contest's number and title, each line's party letters and candidate number, the "
                       "candidate's name (as for the precinct file), the line's total votes and the election date.")}
    for y, d in sorted(years.items(), reverse=True):
        for fn, info in d["files"].items():
            level = "precinct" if "precinct" in info["levels"] else "county" if "county" in info["levels"] else None
            if level is None:
                continue
            rec = {"id": f"ok-seb-{'precincts' if level == 'precinct' else 'counties'}-{y}",
                   "kind": f"official results by {level}", "agency": "Oklahoma State Election Board",
                   "title": (f"Official results of the general election of {long_day(DAYS[y])}, {level} level "
                             f"(the results site's Export menu: \"{EXPORT[level]}\")"),
                   "url": RESULTS_SITE.format(day=DAYS[y]), "listed_on": YEAR_PAGES[y], "file": fn, "sha256": info["sha256"],
                   "how": came_from(fn, info["sha256"], info["path"], level), "lines": info["lines"], "read": read[level]}
            if level == "precinct":
                rec["precinct_units"] = len(tallies[y]["per"])
            sources.append(rec)
    sources += [layer_rec] + official_recs
    doc = document(built, sources, list(years), missing)
    _save(out, doc)
    say(f"   wrote {os.path.relpath(out, HERE)}: " + ", ".join(f"{k} {len(v)}" for k, v in doc["places"].items()))
    for cid, k in built["control"].items():
        cc = k.get("counties")
        say(f"      {cid}: precincts {fmt(k['sum_of_precincts'])}; official {'equal' if k['equal'] else 'DIFFERS ' + by_side(k['difference'])}"
            + (f"; counties equal to the county file {cc['equal']} of {cc['compared']}" if cc else "; no county file")
            + ("" if k.get("county_file", {}).get("equal_to_official", True) else "; the county file DISAGREES with the official total"))
    for cid, recs in doc["coverage"].get("counties_left_out", {}).items():
        for r in recs:
            say(f"         left out: {r['statement']}")
    for kind, p in doc["kinds"].items():
        say(f"      {kind}: {p['places']} places; given per contest {p['given']}")
    return doc


# ---------------------------------------------------------------- the self-test

def selftest():
    import tempfile
    fails = []

    def check(what, got, want):
        if got != want:
            fails.append(f"{what}: got {got!r}, want {want!r}")
    check("county 01 is 40001", county_fips("01"), "40001")
    check("county 77 is 40153", county_fips(77), "40153")
    check("a date written the Board's way", _date("11/08/2022"), "20221108")
    check("headings are matched by name", sorted(_columns(["elec_date", "county_name", "race_description", "cand_party", "precinct_code", "cand_tot_votes", "cand_name", "race_number", "cand_early_votes"])),
          sorted(["date", "county", "race", "party", "precinct", "votes", "name", "race_number"]))
    # a made-up state of two counties, five precincts, House districts 1 and 2, commissioner districts
    P = {"010001": {"county": "40001", "county_name": "ADAIR", "house": "1", "senate": "1", "commissioner": "1"},
         "010002": {"county": "40001", "county_name": "ADAIR", "house": "1", "senate": "1", "commissioner": "2"},
         "020001": {"county": "40003", "county_name": "ALFALFA", "house": "2", "senate": "1", "commissioner": "1"},
         "020002": {"county": "40003", "county_name": "ALFALFA", "house": "2", "senate": "1", "commissioner": "1"},
         "020003": {"county": "40003", "county_name": "ALFALFA", "house": "1", "senate": "1", "commissioner": "2"}}
    C = [dict(CONTESTS[0], year=2022, id="t-president"), dict(CONTESTS[2], id="t-senate")]
    hdr = "elec_date,county_name,race_number,race_description,cand_name,cand_party,precinct_code,cand_absmail_votes,cand_tot_votes\n"
    lines = []
    for code, (d, r, o) in {"10001": (10, 30, 1), "10002": (5, 5, 0), "20001": (7, 20, 2), "20002": (1, 2, 0), "20003": (8, 9, 1)}.items():
        cty = "ADAIR" if code.startswith("1") else "ALFALFA"
        lines += [f"11/08/2022,{cty},10,FOR PRESIDENT AND VICE PRESIDENT,HARRIS / WALZ,DEM,{code},99,{d}",
                  f"11/08/2022,{cty},10,FOR PRESIDENT AND VICE PRESIDENT,TRUMP / VANCE,REP,{code},99,{r}",
                  f"11/08/2022,{cty},10,FOR PRESIDENT AND VICE PRESIDENT,SOMEONE,IND,{code},0,{o}",
                  f"11/08/2022,{cty},20,FOR UNITED STATES SENATOR,MADISON HORN,DEM,{code},0,{d}",
                  f"11/08/2022,{cty},20,FOR UNITED STATES SENATOR,JAMES LANKFORD,REP,{code},0,{r}"]
    for code in ("10001", "10002", "20003"):
        lines.append(f"11/08/2022,{'ADAIR' if code.startswith('1') else 'ALFALFA'},30,FOR STATE REPRESENTATIVE DISTRICT 1,X,REP,{code},0,3")
    for code in ("20001", "20002"):
        lines.append(f"11/08/2022,ALFALFA,40,FOR COUNTY COMMISSIONER DISTRICT NO. 1,Y,REP,{code},0,3")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(os.path.join(tmp, "export.zip"), "w") as z:
            z.writestr("20221108_prec.csv", hdr + "\n".join(lines) + "\n")
        data = read_folder(tmp, "20221108", lambda *_: None)
    check("the zip's table is read as precinct lines", len(data["precinct"]), len(lines))
    check("columns not on the allowlist are not kept", "cand_absmail_votes" in json.dumps(data), False)
    t = tally_year(2022, data, C, P, lambda *_: None)
    check("a precinct's president counts", t["per"]["010001"]["t-president"], [10, 30, 1, 41])
    official = {"t-president": {"dem": 31, "rep": 66, "other": 4, "total": 101, "source": "x", "where": "y"},
                "t-senate": {"dem": 31, "rep": 66, "other": 0, "total": 97, "source": "x", "where": "y"}}
    b = build({2022: t}, C, P, official)
    check("Adair County adds up", b["places"]["county"]["40001"]["votes"]["t-president"], {"dem": 15, "rep": 35, "other": 1, "total": 51})
    check("House district 1 is three precincts across two counties", b["places"]["house"]["1"]["votes"]["t-president"], {"dem": 23, "rep": 44, "other": 2, "total": 69})
    check("a commissioner district is keyed by county", b["places"]["commissioner"]["40003-1"]["votes"]["t-senate"], {"dem": 8, "rep": 22, "other": 0, "total": 30})
    check("a place with fewer than twenty votes is too_few", b["places"]["commissioner"]["40001-2"].get("too_few"), ["t-president", "t-senate"])
    # a precinct not on the map leaves out its county's districts of every kind
    data2 = {"precinct": data["precinct"] + [dict(data["precinct"][0], precinct="29999", county="ALFALFA", votes="4")], "county": [], "files": {}}
    t2 = tally_year(2022, data2, C, P, lambda *_: None)
    official2 = {k: dict(v) for k, v in official.items()}
    official2["t-president"].update(dem=35, total=105)
    b2 = build({2022: t2}, C, P, official2)
    check("an unknown unit leaves out the districts reaching its county", sorted(b2["places"]["house"]), [])
    check("and Adair's commissioner districts stay", sorted(b2["places"]["commissioner"]), ["40001-1", "40001-2"])
    check("and the unit is named", b2["coverage"]["precincts_not_on_the_map"], {"2022": ["02-9999"]})
    # a precinct on the wrong side of a line by its own contest
    bad = [dict(r, precinct="20001") if r["race"].startswith("FOR STATE REP") and r["precinct"] == "20003" else r for r in data["precinct"]]
    t3 = tally_year(2022, {"precinct": bad, "county": [], "files": {}}, C, P, lambda *_: None)
    try:
        place_precincts(2022, t3, P)
        fails.append("a map that disagrees with most contests should stop the run")
    except Stop:
        pass
    # the officials must agree
    try:
        build({2022: t}, C, P, dict(official, **{"t-senate": dict(official["t-senate"], rep=67, total=98)}))
        fails.append("a sum that differs from the official figures should stop the run")
    except Stop:
        pass
    # a contest found twice stops the run
    try:
        find_contests([{"race": "FOR UNITED STATES SENATOR", "race_number": "1"}, {"race": "FOR UNITED STATES SENATOR (FULL TERM)", "race_number": "2"}], [C[1]], "test")
        fails.append("two matching contests should stop the run")
    except Stop:
        pass
    # the Clerk's sections with a subsection
    doc = {"sections": {("FOR UNITED STATES SENATOR", "(For unexpired term ending January 3, 2027)"): [("Markwayne Mullin, Republican", 7), ("Kendra Horn, Democrat", 4), ("R. M., Libertarian", 1)],
                        ("FOR UNITED STATES SENATOR", "(For full term beginning January 3, 2023)"): [("James Lankford, Republican", 9), ("Madison Horn, Democrat", 3)]}}
    check("the Clerk's unexpired term", clerk_figures(doc, CONTESTS[3]), {"dem": 4, "rep": 7, "other": 1, "total": 12})
    check("the Clerk's full term", clerk_figures(doc, CONTESTS[2]), {"dem": 3, "rep": 9, "other": 0, "total": 12})
    for c in CONTESTS:
        v = CHECKED[c["id"]]
        check(f"{c['id']}: the typed figures add up", v["dem"] + v["rep"] + v["other"], v["total"])
    # the results site's exports: a precinct-level file with no county column (the county is the code's first two
    # digits) and a county-level file; the control holds county by county
    tail = "cand_number,cand_name,cand_party,cand_absmail_votes,cand_early_votes,cand_elecday_votes,cand_tot_votes,race_county_owner\n"
    new_p = "elec_date,precinct,entity_description,race_number,race_description,race_party,tot_race_prec,race_prec_reporting," + tail
    new_c = "elec_date,county,entity_description,race_number,race_description,race_party,tot_race_prec,race_prec_reporting," + tail
    check("the export's precinct headings", sorted(_columns(new_p.strip().split(","))),
          sorted(["date", "precinct", "race_number", "race", "candidate_number", "name", "party", "votes"]))
    check("the export's county headings", sorted(_columns(new_c.strip().split(","))),
          sorted(["date", "county", "race_number", "race", "candidate_number", "name", "party", "votes"]))
    pres, sen = "ELECTORS FOR PRESIDENT AND VICE PRESIDENT", "FOR UNITED STATES SENATOR"

    def lines_for(where, ent, d, r, o, sd, sr):
        return [f'11/8/2022,{where},"{ent}",10001,{pres},,5,5,1,SOMEONE | ELSE,IND,0,0,{o},{o},',
                f'11/8/2022,{where},"{ent}",10001,{pres},,5,5,2,DONALD J. TRUMP | JD VANCE,REP,0,{r},0,{r},',
                f'11/8/2022,{where},"{ent}",10001,{pres},,5,5,3,KAMALA D. HARRIS | TIM WALZ,DEM,{d},0,0,{d},',
                f'11/8/2022,{where},"{ent}",10010,{sen},,5,5,2,JAMES LANKFORD,REP,0,0,{sr},{sr},',
                f'11/8/2022,{where},"{ent}",10010,{sen},,5,5,3,MADISON HORN,DEM,0,0,{sd},{sd},']
    plines = []
    for code, (d, r, o) in {"010001": (10, 30, 1), "010002": (5, 5, 0), "020001": (7, 20, 2), "020002": (1, 2, 0), "020003": (8, 9, 1)}.items():
        plines += lines_for(code, "FEDERAL, STATE AND COUNTY", d, r, o, d, r)
    for code in ("010001", "010002", "020003"):
        plines.append(f'11/8/2022,{code},"FEDERAL, STATE AND COUNTY",20001,FOR STATE REPRESENTATIVE DISTRICT 1,,3,3,1,X,REP,0,0,3,3,')
    for code in ("020001", "020002"):
        plines.append(f'11/8/2022,{code},ALFALFA COUNTY,30001,FOR COUNTY COMMISSIONER DISTRICT NO. 1,,2,2,1,Y,REP,0,0,3,3,ALFALFA')

    def exports(alfalfa_rep):
        clines = lines_for("ADAIR", "ADAIR COUNTY", 15, 35, 1, 15, 35) + lines_for("ALFALFA", "ALFALFA COUNTY", 16, alfalfa_rep, 3, 16, 31)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(os.path.join(tmp, "20221108_PrecinctResults_csv.zip"), "w") as z:
                z.writestr("20221108_PrecinctResults.csv", new_p + "\n".join(plines) + "\n")
            with zipfile.ZipFile(os.path.join(tmp, "20221108_CountyResults_csv.zip"), "w") as z:
                z.writestr("20221108_CountyResults.csv", new_c + "\n".join(clines) + "\n")
            return read_folder(tmp, "20221108", lambda *_: None)
    d6 = exports(31)
    check("the export's precinct file is read, with no county column", len(d6["precinct"]), len(plines))
    check("and its county file as county lines", len(d6["county"]), 10)
    check("each file's level is recorded", sorted(lv for f in d6["files"].values() for lv in f["levels"]), ["county", "precinct"])
    check("the export's other columns are not kept", any(w in json.dumps(d6["precinct"]) for w in ("FEDERAL", "ALFALFA")), False)
    t6 = tally_year(2022, d6, C, P, lambda *_: None)
    check("a precinct's county is read from its code", (t6["county_of"]["020003"], t6["per"]["020003"]["t-president"]), ("40003", [8, 9, 1, 18]))
    b6 = build({2022: t6}, C, P, official)
    doc6 = document(b6, [], [2022], {})
    check("every county equal to the county file: the result is equal and counties cover the state",
          (doc6["control"]["result"], doc6["kinds"]["county"]["covers_the_state"], doc6["control"]["contests"]["t-president"]["counties"]["equal"]),
          ("equal", True, 2))
    d7 = exports(32)                        # Alfalfa's county file gives Trump one vote more than its precincts
    t7 = tally_year(2022, d7, C, P, lambda *_: None)
    official7 = dict(official, **{"t-president": dict(official["t-president"], rep=67, total=102)})
    b7 = build({2022: t7}, C, P, official7)
    doc7 = document(b7, [], [2022], {})
    pl = b7["places"]
    check("a county whose precincts differ from the county file loses the contest", sorted(pl["county"]["40003"]["votes"]), ["t-senate"])
    check("and says why", list(pl["county"]["40003"].get("not_given", {})), ["t-president"])
    check("the other county keeps it", pl["county"]["40001"]["votes"]["t-president"], {"dem": 15, "rep": 35, "other": 1, "total": 51})
    check("so does every district reaching into it, and only those",
          (sorted(pl["house"]["1"]["votes"]), sorted(pl["house"]["2"]["votes"]), sorted(pl["commissioner"]["40003-1"]["votes"]),
           sorted(pl["commissioner"]["40001-1"]["votes"]), sorted(pl["senate"]["1"]["votes"])),
          (["t-senate"], ["t-senate"], ["t-senate"], ["t-president", "t-senate"], ["t-senate"]))
    r = doc7["coverage"]["counties_left_out"]["t-president"][0]
    check("the county is listed with both figures and the difference", (r["name"], r["sum_of_precincts"]["rep"], r["county_file"]["rep"], r["difference"]["total"]),
          ("Alfalfa County", 31, 32, -1))
    c7 = doc7["control"]["contests"]["t-president"]
    check("the statewide line is stated as it is", (c7["equal"], c7["difference"], c7["county_file"]["equal_to_official"], doc7["contests"][0]["statewide"]["total"],
                                                    doc7["control"]["result"], doc7["kinds"]["county"]["covers_the_state"]),
          (False, {"rep": -1, "total": -1}, True, 102, "equal where given", False))
    doc8 = document(build({2022: t7}, C, P, official), [], [2022], {})
    check("a county file and a statewide total that disagree: said, neither chosen, no statewide figure",
          ("statewide" in doc8["contests"][0], doc8["control"]["contests"]["t-president"]["county_file"]["equal_to_official"]), (False, False))
    try:
        renumbered = [dict(x, candidate_number="9") if x["party"] == "DEM" and x["race"] == pres else x for x in d6["county"]]
        tally_year(2022, dict(d6, county=renumbered), C, P, lambda *_: None)
        fails.append("two files that number a ticket differently should stop the run")
    except Stop:
        pass
    print("self-test:", "all passed" if not fails else f"{len(fails)} failed")
    for f in fails:
        print("   ", f)
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    try:
        doc = run(a.cache, a.out, a.refresh, a.db)
    except Stop as e:
        print(f"   STOPPED, nothing written: {e}")
        return 1
    return 0 if doc else 2


if __name__ == "__main__":
    sys.exit(main())
