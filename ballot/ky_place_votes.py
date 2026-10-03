"""
ballot/ky_place_votes.py - how each Kentucky place voted in past partisan general elections, so a page can show the
record of a county, a city or a district without anyone labelling a candidate. The Kentucky twin of
ballot/mn_place_votes.py; the output has the same shape (the Democratic count is "dem" here, as in the Dakotas',
Montana's and Wyoming's files, where Minnesota's is "dfl").

    python ballot/ky_place_votes.py               reads (or downloads) the files, writes ballot/lean/ky_place_votes.json
    python ballot/ky_place_votes.py --refresh     asks for everything again even when the cached copies are there
    python ballot/ky_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/ky_place_votes.py --selftest    the readers and the arithmetic on made-up pages; downloads nothing

What it is, and is not
----------------------
For President in 2024, Governor in 2023 and U.S. Senator in 2022 (Kentucky elects its Governor in the year before a
presidential election, elected no senator in 2024 and none in 2023): the votes for the Democratic ticket, the Republican
ticket, every other candidate and all write-ins together, and the total, for every one of the 120 counties and every
judicial circuit, judicial district and Supreme Court district (whole counties), and for 2022 and 2024 for every state
House and Senate district, city, city council ward and (2022) magisterial district whose precincts voted in it alone
(see below). It is how the people of a place voted then, on the lines in force at that election. It is not a
prediction, it says nothing about any candidate on a later ballot or about any voter, and it turns no nonpartisan office
into a partisan one. No database is opened for writing; ballot_local_2026.sqlite is opened read-only, to learn the ids
our pages give Kentucky's cities and to count how many of our places are covered.

Where the numbers come from
---------------------------
All from the Kentucky State Board of Elections (elect.ky.gov), which answers a plain script:

  - The "General Recap Sheets" of each general election (one page for each year, a PDF for each county): the county
    clerk's precinct-by-precinct report of the official results. THE DISTRICT AND CITY FIGURES ARE THESE PRECINCTS
    ADDED UP. Three report layouts occur, and all are read: most counties' "Precinct Results Report" (each contest's
    title names its district: "STATE REPRESENTATIVE 21st Representative District"; cast, under and over votes by
    contest), some counties' "Precinct Summary Results Report" (Electionware), whose legislative contests are titled
    with the county alone ("STATE REPRESENTATIVE Breathitt County") and which sometimes give no under and over votes, and
    a few 2022 "Precinct Report"s whose rows carry no party letters. Of each precinct only its label, its ballots cast,
    and each contest's title, candidates' vote totals (with the party letters, to tell which ticket a row is), and cast,
    under and over votes are kept. Write-ins the report counts for no declared write-in candidate ("Not Assigned",
    "Invalid") are left out, as the certified results leave them out. Many files are scanned pictures (most of 2022's),
    some hold county totals only or text that cannot be read in order, and a few do not add up to the county's certified
    figures (a report printed before an amendment, or one kind of ballot only): for each such county the county's own
    figures are the Secretary's certified row, and no district or city reaching into it is given that year; the file
    lists every one with its reason. The 2020 recap sheets are scanned pictures, so 2020 is not given.
  - The Secretary of State's county-by-county results document of each general election ("Official 2024 General
    Election Results" as amended on December 9, 2024; the 2023 certification; "2022 General Election Results"): every
    county's votes for each candidate in the statewide contests and in every State Representative and State Senator
    contest, with a Total Votes row. They are the control for the precincts, and for an Electionware county they say
    which district its legislative contest was (see below).
  - Missing recap sheets: the Board's 2022 page has no file for Rockcastle County (and links Butler County's to an
    address that answers 404); its 2023 page none for Owsley or Wolfe County (the file at Wolfe's usual address is that
    year's primary, and every report is checked to be of the general election's date). Those counties are treated as
    above: the Secretary's row (its columns told apart by the other counties, see the control).
  - Judicial circuits (KRS 23A.020), judicial districts (KRS 24A.030) and Supreme Court districts (KRS 21A.010, which
    are also the Court of Appeals districts by KRS 22A.010) are whole counties; each section is read from the
    Legislature's own copy (apps.legislature.ky.gov) and must equal the copy typed below. They are the counties as the
    statutes stand today, and every year's figures are those counties' votes.

Which district or city a precinct is in
----------------------------------------
A precinct's House district is the district of the State Representative contest on its ballot (all 100 seats are up
each even year, so a precinct lying in two districts carries two such contests). A precinct is whole in a district,
city, ward or magisterial district where that place's contest reached all its ballots: the contest's cast, under and
over votes come to the number to be elected times the precinct's full ballots, which is the figure most of the
precinct's one-seat contests come to (the President's contest can have a few more, ballots for President only, and the
ballot count the report prints a few more again, blank or spoiled ballots). Where a precinct lies in two places of a
kind, its votes for President, Senator or Governor are given whole and cannot be divided without an estimate, and every
place of that kind it touches is left out that year (the file names the precinct). Where a report gives no under and
over votes, a precinct is placed only in the one House district on its ballot. A Senate district is up every four years
(the odd ones in 2024, the even ones in 2022 and 2026), so a precinct's Senate district is read from the year its
district was on the ballot: its own year's contest where that reached all its ballots, else the same precinct of the
same county, with the same House district, in the other year's report; a precinct whose district is not shown so leaves
out the districts it could be in (those its ballot names, and those not up that year that reach its county in the
Secretary's documents). In an Electionware county a legislative contest is told by its candidates: its precincts' rows,
added up, must equal exactly one district's row for that county in the Secretary's document, or none of its precincts is
placed. A city is the precincts of its contests ("City of Columbia"; in Jefferson County "JEFFERSONTOWN COUNCILMEMBER
JEFFERSONTOWN", and Louisville Metro's mayor and council): given in a year only where a contest of it reached every one
of its precincts (its mayor, a council or commission elected citywide, or council seats headed by ward that every one of
its ballots carries, as Hopkinsville's, Madisonville's and Somerset's are), every precinct voted in it with all its
ballots, and every county it reaches has a precinct report used that year. A ward is the precincts of a contest
naming the city and a ward or district that only part of the city votes in (Louisville Metro's and Lexington's council
districts among them), on the same rule. A magisterial district (2022, when every county elected its magistrates and
constables) is the precincts of the magistrate or constable contest naming it, on the same rule. City names are matched
to the Census place names our pages use, by letters alone in the same county (Ft., Mt. and St. written out; one typed
spelling, Middlesborough for the Census's Middlesboro); a name that matches none, or more than one, is listed and not
given. A city our pages do not list is not given.

Not given: school districts (a board of education's seats are staggered, so a district has no contest every year that
covers all of it); soil and water conservation districts (their contests are printed only when more file than seats);
cities, wards and districts in 2023, which elected none of them; 2020 (scanned).

The control
-----------
Nothing is written unless all of this holds: in each report every page is read (the pages are numbered without a gap
and the report ends where it says it ends), every precinct is named once in its county, every contest's candidates add
up to its cast votes, and the report is of the general election's date; for every statewide contest every column of the
Secretary's county-by-county table equals one candidate's votes added up from the precincts of every county whose report
is used, the Democratic and Republican tickets each being one such column, and the counties (with the Secretary's row
for each county whose report is not read or does not add up to it; no more than twelve such in a year) add up to the
Secretary's Total Votes row; for President in 2024 and U.S. Senator in 2022 the totals also equal the Clerk of the U.S.
House of Representatives' "Statistics of the ... Election" (its under and over votes left out, as here); for 2022 and
2024 every State Representative and State Senator contest's precincts, county by county, are found in that contest's
county rows in the Secretary's document; every precinct read in those years carries a House contest; every kind of
place that covers the state adds up to the statewide sum, and the House districts given, with the precincts of those
left out and the counties not read, do too. The statewide figures this loader was checked against on 2026-10-03 are
typed below (CHECKED); the loader says so if a report reads differently later.
"""

import argparse
import collections
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
from ballot import mn_place_votes as M  # noqa: E402  the shared small things: fingerprints, days, the file writer
from ballot import wy_place_votes as W  # noqa: E402  the Clerk of the House's statistics reader

Stop = M.Stop
METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
PARSER = "8"                   # change how a report is read, and the parsed copies are read again
CACHE = os.path.join(HERE, "states_cache", "ky_local")
OUT = os.path.join(HERE, "ballot", "lean", "ky_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "21"
FEW = 20
SIDES = ("dem", "rep", "other", "total")
KEEP_DAYS = 3650               # official results of past elections do not change; --refresh asks again
HOUSE, SENATE = 100, 38
DISTRICT_YEARS = (2022, 2024)  # the elections held on today's House and Senate districts, with city contests

AGENCY = "Kentucky State Board of Elections"
SOS = "Kentucky Secretary of State (the Board's published copy)"
SITE = "https://elect.ky.gov"
RESULTS_PAGE = f"{SITE}/results/2020-2029/Pages/default.aspx"
ELECTIONS = {
    2024: {"date": "2024-11-05", "recaps": f"{SITE}/results/2020-2029/Pages/2024General-Recap-Sheets.aspx",
           "table": {"url": f"{SITE}/results/2020-2029/Documents/2024%20General%20Election%20Certification%20as%20Amended%20on%20December%209th%202024.pdf",
                     "file": "certification_2024.pdf", "title": "Official 2024 General Election Results (the certification as amended on December 9, 2024)",
                     "page": f"{SITE}/results/2020-2029/Pages/2024.aspx"}},
    2023: {"date": "2023-11-07", "recaps": f"{SITE}/results/2020-2029/Pages/2023General-Recap-Sheets.aspx",
           "table": {"url": f"{SITE}/results/2020-2029/Documents/Certification%20of%20Election%20Results%20for%202023%20General%20Election%20Final.pdf",
                     "file": "certification_2023.pdf", "title": "Official 2023 General Election Results (Certification of Election Results for 2023 General Election, Final)",
                     "page": f"{SITE}/results/2020-2029/Pages/2023.aspx"}},
    2022: {"date": "2022-11-08", "recaps": f"{SITE}/results/2020-2029/Pages/2022-General-Recap-Sheets.aspx",
           "table": {"url": f"{SITE}/results/2020-2029/Documents/2022%20General%20Election%20Results.pdf",
                     "file": "results_2022.pdf", "title": "Official 2022 General Election Results",
                     "page": f"{SITE}/results/2020-2029/Pages/2022.aspx"}},
}

# The 120 counties in the order of their FIPS codes (21001, 21003, ...).
COUNTIES = ("Adair|Allen|Anderson|Ballard|Barren|Bath|Bell|Boone|Bourbon|Boyd|Boyle|Bracken|Breathitt|Breckinridge|Bullitt|Butler|"
            "Caldwell|Calloway|Campbell|Carlisle|Carroll|Carter|Casey|Christian|Clark|Clay|Clinton|Crittenden|Cumberland|Daviess|Edmonson|"
            "Elliott|Estill|Fayette|Fleming|Floyd|Franklin|Fulton|Gallatin|Garrard|Grant|Graves|Grayson|Green|Greenup|Hancock|Hardin|Harlan|"
            "Harrison|Hart|Henderson|Henry|Hickman|Hopkins|Jackson|Jefferson|Jessamine|Johnson|Kenton|Knott|Knox|Larue|Laurel|Lawrence|Lee|"
            "Leslie|Letcher|Lewis|Lincoln|Livingston|Logan|Lyon|McCracken|McCreary|McLean|Madison|Magoffin|Marion|Marshall|Martin|Mason|"
            "Meade|Menifee|Mercer|Metcalfe|Monroe|Montgomery|Morgan|Muhlenberg|Nelson|Nicholas|Ohio|Oldham|Owen|Owsley|Pendleton|Perry|"
            "Pike|Powell|Pulaski|Robertson|Rockcastle|Rowan|Russell|Scott|Shelby|Simpson|Spencer|Taylor|Todd|Trigg|Trimble|Union|Warren|"
            "Washington|Wayne|Webster|Whitley|Wolfe|Woodford").split("|")


def bare(name):
    """A county's name for comparing only: small letters alone ('LaRue', 'Larue', 'LARUE COUNTY', 'Rockcastle%20County')."""
    s = re.sub(r"[^a-z]", "", urllib.parse.unquote(str(name or "")).lower())
    while s.endswith(("recap", "county")):
        s = s[:-5] if s.endswith("recap") else s[:-6]
    return s


FIPS = {bare(name): f"{STATE_FIPS}{2 * i + 1:03d}" for i, name in enumerate(COUNTIES)}
FIPS["muhlenburg"] = FIPS["muhlenberg"]       # the Board's 2022 primary page spells it so
COUNTY_NAME = {FIPS[bare(name)]: f"{name} County" for name in COUNTIES}

# The judicial geography as the Legislature's copies read on 2026-10-03 (read again at each run; it must be equal).
CIRCUITS = {1: "Ballard, Carlisle, Fulton, Hickman", 2: "McCracken", 3: "Christian", 4: "Hopkins", 5: "Crittenden, Union, Webster", 6: "Daviess",
            7: "Logan, Todd", 8: "Edmonson, Warren", 9: "Hardin", 10: "Hart, Larue, Nelson", 11: "Green, Marion, Taylor, Washington",
            12: "Henry, Oldham, Trimble", 13: "Garrard, Jessamine", 14: "Bourbon, Scott, Woodford", 15: "Carroll, Grant, Owen", 16: "Kenton",
            17: "Campbell", 18: "Harrison, Nicholas, Pendleton, Robertson", 19: "Bracken, Fleming, Mason", 20: "Greenup, Lewis",
            21: "Bath, Menifee, Montgomery, Rowan", 22: "Fayette", 23: "Estill, Lee, Owsley", 24: "Lawrence, Johnson, Martin", 25: "Clark, Madison",
            26: "Harlan", 27: "Knox, Laurel", 28: "Lincoln, Pulaski, Rockcastle", 29: "Adair, Casey", 30: "Jefferson", 31: "Floyd", 32: "Boyd",
            33: "Perry", 34: "Whitley, McCreary", 35: "Pike", 36: "Magoffin, Knott", 37: "Carter, Elliott, Morgan", 38: "Butler, Ohio, Hancock",
            39: "Breathitt, Wolfe, Powell", 40: "Clinton, Cumberland, Monroe", 41: "Clay, Jackson, Leslie", 42: "Calloway, Marshall",
            43: "Barren, Metcalfe", 44: "Bell", 45: "Muhlenberg, McLean", 46: "Breckinridge, Grayson, Meade", 47: "Letcher", 48: "Franklin",
            49: "Allen, Simpson", 50: "Boyle, Mercer", 51: "Henderson", 52: "Graves", 53: "Shelby, Anderson, Spencer", 54: "Boone, Gallatin",
            55: "Bullitt", 56: "Caldwell, Livingston, Lyon, Trigg", 57: "Russell, Wayne"}
DISTRICTS = {1: "Ballard, Carlisle, Fulton, Hickman", 2: "McCracken", 3: "Christian", 4: "Hopkins", 5: "Crittenden, Union, Webster", 6: "Daviess",
             7: "Logan, Todd", 8: "Warren", 9: "Hardin", 10: "Hart, Larue", 11: "Green, Marion, Taylor, Washington", 12: "Henry, Oldham, Trimble",
             13: "Garrard, Jessamine, Lincoln", 14: "Bourbon, Scott, Woodford", 15: "Carroll, Grant, Owen", 16: "Kenton", 17: "Campbell",
             18: "Harrison, Nicholas, Pendleton, Robertson", 19: "Bracken, Fleming, Mason", 20: "Greenup, Lewis", 21: "Bath, Menifee, Montgomery, Rowan",
             22: "Fayette", 23: "Estill, Lee, Owsley", 24: "Lawrence, Johnson, Martin", 25: "Clark, Madison", 26: "Harlan", 27: "Knox, Laurel",
             28: "Pulaski, Rockcastle", 29: "Adair, Casey", 30: "Jefferson", 31: "Floyd", 32: "Boyd", 33: "Perry", 34: "Whitley, McCreary", 35: "Pike",
             36: "Magoffin, Knott", 37: "Carter, Elliott, Morgan", 38: "Butler, Edmonson, Ohio, Hancock", 39: "Breathitt, Wolfe, Powell",
             40: "Clinton, Russell, Wayne", 41: "Clay, Jackson, Leslie", 42: "Calloway", 43: "Barren, Metcalfe", 44: "Bell", 45: "Muhlenberg, McLean",
             46: "Breckinridge, Grayson, Meade", 47: "Letcher", 48: "Franklin", 49: "Allen, Simpson", 50: "Boyle, Mercer", 51: "Henderson", 52: "Graves",
             53: "Shelby, Anderson, Spencer", 54: "Boone, Gallatin", 55: "Bullitt", 56: "Caldwell, Livingston, Lyon, Trigg", 57: "Nelson", 58: "Marshall",
             59: "Cumberland, Monroe"}
SUPREME = {1: "Ballard, Caldwell, Calloway, Carlisle, Christian, Crittenden, Daviess, Fulton, Graves, Henderson, Hickman, Hopkins, Livingston, Logan, "
              "Lyon, Marshall, McCracken, McLean, Muhlenberg, Todd, Trigg, Union, Webster",
           2: "Allen, Barren, Breckinridge, Bullitt, Butler, Edmonson, Grayson, Hancock, Hardin, Hart, Larue, Meade, Monroe, Simpson, Spencer, Ohio, Warren",
           3: "Adair, Anderson, Bell, Boyle, Casey, Clinton, Cumberland, Garrard, Green, Harlan, Knox, Laurel, Lincoln, Marion, McCreary, Mercer, "
              "Metcalfe, Nelson, Pulaski, Rockcastle, Russell, Taylor, Washington, Wayne, Whitley",
           4: "Jefferson",
           5: "Bourbon, Clark, Fayette, Franklin, Jessamine, Madison, Scott, Woodford",
           6: "Boone, Bracken, Campbell, Carroll, Gallatin, Grant, Henry, Kenton, Oldham, Owen, Pendleton, Shelby, Trimble",
           7: "Bath, Boyd, Breathitt, Carter, Clay, Elliott, Estill, Fleming, Floyd, Greenup, Harrison, Jackson, Johnson, Knott, Lawrence, Lee, Leslie, "
              "Letcher, Lewis, Magoffin, Martin, Mason, Menifee, Montgomery, Morgan, Nicholas, Owsley, Perry, Pike, Powell, Robertson, Rowan, Wolfe"}
STATUTES = [
    {"id": "ky-krs-23a-020", "key": "KY-JC", "typed": CIRCUITS, "file": "krs_23A.020.pdf", "url": "https://apps.legislature.ky.gov/LAW/STATUTES/statute.aspx?id=53357",
     "cite": "KRS 23A.020 (Judicial circuits)", "pattern": r"\((\d+)\)\s+[A-Za-z-]+ Judicial Circuit\.\s+(.*?)\.(?=\s*\(\d+\)|\s*Effective)",
     "name": "{} Judicial Circuit", "what": "Judicial circuits (circuit court and Commonwealth's attorney)"},
    {"id": "ky-krs-24a-030", "key": "KY-JD", "typed": DISTRICTS, "file": "krs_24A.030.pdf", "url": "https://apps.legislature.ky.gov/LAW/STATUTES/statute.aspx?id=48467",
     "cite": "KRS 24A.030 (Judicial districts; the section in force until January 1, 2031)",
     "pattern": r"\((\d+)\)\s+[A-Za-z-]+ Judicial District\.\s+(.*?)\.(?=\s*\(\d+\)|\s*Effective)",
     "name": "{} Judicial District", "what": "Judicial districts (district court)"},
    {"id": "ky-krs-21a-010", "key": "KY-SC", "typed": SUPREME, "file": "krs_21A.010.pdf", "url": "https://apps.legislature.ky.gov/LAW/STATUTES/statute.aspx?id=51896",
     "cite": "KRS 21A.010 (Supreme Court districts)", "pattern": r"\((\d+)\)\s+[A-Za-z-]+ District:\s+(.*?)\.(?=\s*\(\d+\)|\s*Effective)",
     "name": "Supreme Court District {}", "what": "Supreme Court districts, which are also the Court of Appeals districts"},
]
APPEALS = {"id": "ky-krs-22a-010", "file": "krs_22A.010.pdf", "url": "https://apps.legislature.ky.gov/LAW/STATUTES/statute.aspx?id=20560",
           "cite": "KRS 22A.010 (Court of Appeals districts)",
           "words": "The districts of the Court of Appeals shall correspond in geographical dimensions to the districts of the Supreme Court"}

# The contests. "title" begins the recap sheets' contest title; "dem" and "rep" are the tickets, whose first person's
# surname must be on the precinct row printed with that party's letters, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "office": "President and Vice President of the United States", "title": "PRESIDENT and VICE PRESIDENT",
     "table": "President and Vice President of the United States", "dem": "Kamala D. Harris and Tim Walz", "rep": "Donald J. Trump and J. D. Vance",
     "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2023-governor", "year": 2023, "office": "Governor and Lieutenant Governor", "title": "GOVERNOR and LIEUTENANT GOVERNOR",
     "table": "Governor", "dem": "Andy Beshear and Jacqueline Coleman", "rep": "Daniel Cameron and Robert M. Mills", "clerk": None},
    {"id": "2022-us-senate", "year": 2022, "office": "United States Senator", "title": ("UNITED STATES SENATOR", "U.S. SENATOR"), "table": "United States Senator",
     "dem": "Charles Booker", "rep": "Rand Paul", "clerk": "FOR UNITED STATES SENATOR"},
]
PARTY = {"DEM": "dem", "REP": "rep"}

# The statewide totals this loader was checked against on 2026-10-03 (the precincts added up, with the Secretary's row
# for a county whose report is missing; the Secretary's Total Votes rows and, for President and U.S. Senator, the Clerk
# of the House all read these).
CHECKED = {
    "2024-president": {"dem": 704043, "rep": 1337494, "other": 32993, "total": 2074530},
    "2023-governor": {"dem": 694482, "rep": 627457, "other": 83, "total": 1322022},
    "2022-us-senate": {"dem": 564311, "rep": 913326, "other": 193, "total": 1477830},
}
CLERK = {year: {"id": f"clerk-statistics-{year}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                "title": f"Statistics of the {'Presidential and ' if year % 4 == 0 else ''}Congressional Election from Official Sources for the Election of {day}",
                "url": f"https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf", "file": f"clerk_statistics{year}.pdf"}
         for year, day in ((2024, "November 5, 2024"), (2022, "November 8, 2022"))}

# A city's name as the reports print it, where it differs from the Census place's by more than spaces and capitals.
CITY_ALIASES = {("21013", "middlesborough"): "middlesboro"}

# The kinds of place: (kind, first election year given, what it is, what its key is)
KINDS = [
    ("county", 2022, "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("mcd", 2022, "Cities (and the consolidated and urban-county governments)", "KY-M- and the Census place code, as sl_places kind mcd and the jurisdiction_id of our city races"),
    ("ward", 2022, "City council wards or districts", "the city's key, a hyphen, the ward number (KY-M-37918-3)"),
    ("commissioner", 2022, "Magisterial districts (a county's magistrates, or its commissioners, and its constables are elected from them)",
     "five-digit county FIPS code, a hyphen, the district number"),
    ("house", 2022, "State House districts of the plan first used in 2022", "district number, as the district of our House races"),
    ("senate", 2022, "State Senate districts of the plan first used in 2022", "district number, as the district of our Senate races"),
    ("judicial", 2022, "Judicial circuits, judicial districts and Supreme Court districts, as whole counties",
     "KY-JC, KY-JD or KY-SC and the number (KY-JC29, KY-JD8, KY-SC3); KY-JC and KY-JD are the jurisdiction_id of our circuit and district court races"),
]
KIND_NAMES = [k[0] for k in KINDS]
WHAT = ("How each Kentucky place voted in three contests of the 2022, 2023 and 2024 general elections: the votes for the Democratic ticket, the "
        "Republican ticket, every other candidate and all write-ins together and the total, added up from the county clerks' official "
        "precinct reports as the Kentucky State Board of Elections publishes them.")
NOTE = ("What this is: how the people of a place voted in that election, in the official precinct reports, added up here by county, by "
        "judicial circuit and district and, for 2022 and 2024, by state House and Senate district, city, ward and (2022) magisterial district, "
        "on the lines in force at that election. A district or city is given only where every precinct of it voted in it alone: where a "
        "precinct lies in two the reports give its votes whole, and they are never divided by estimate. What this is not: it is not a "
        "prediction of any election; it says nothing about any candidate on a later ballot or about any voter; a nonpartisan office stays "
        "nonpartisan; and a place is not its lines for ever: where a district was drawn again or a city annexed land, the figures are for "
        "the lines of that year. Kentucky elected no senator in 2023 or 2024 and its Governor only in 2023. The tickets are named, as the "
        "reports name them, only to say which election this was. In a place with very few voters the split would come close to saying how "
        "particular people voted; those contests are listed in the place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every other "
               "candidate and all write-ins, together) and total (the votes for candidates and write-ins; over and under votes are left out). "
               "Minnesota's file calls the first count dfl. A contest a place does not have was not counted on its lines: districts, cities, "
               "wards and magisterial districts are given for 2022 and 2024 only (magisterial districts for 2022), and only where no precinct of "
               "the place lies in another place of the kind too.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("School districts: a board of education's seats are staggered, so no year has a contest covering a whole district. Soil and water "
             "conservation districts: their contests are printed only when more file than seats. Cities, wards and districts in 2023: no such "
             "contest was on that ballot. 2020: the Board's recap sheets for it are scanned pictures.")
REDRAWN = ("The 2023 ballot carried no legislative, city or magisterial contest, so which district or city a precinct lay in is not in its "
           "report, and 2023 is given for counties and judicial districts only. 2020 is not given: its reports are scanned pictures.")


# ---------------------------------------------------------------- reading a report

PAIR = r"([\d,]+) (\d+\.\d\d)%"
NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15}
PARTY_CODES = {"REP", "DEM", "KY", "KEN", "LIB", "IND", "GRN", "CON", "SWP", "SOC", "PSL", "NON", "NP", "RFM", "AMS"}


def _int(s):
    return int(str(s).replace(",", ""))


def _vote_for(title):
    m = re.search(r"\(Vote for (?:up to |not more than |no more than )?(\w+)\)", title, re.I)
    if not m:
        return 1
    w = m.group(1).lower()
    return NUMWORDS.get(w) or (int(w) if w.isdigit() else None)


def _new_contest(vote_for):
    return {"vote_for": vote_for, "cands": [], "cast": None, "under": 0, "over": 0, "other_lines": 0, "slots": None, "writein_total": None, "unassigned": 0}


def _cand(text, votes, layout):
    """[name, votes, party or '', write-in?] from a candidate row's text."""
    toks = text.split()
    party = ""
    if layout == "A" and toks and toks[-1] in PARTY_CODES:
        party = toks.pop()
    elif layout == "B" and toks and toks[0] in PARTY_CODES:
        party = toks.pop(0)
    name = " ".join(toks)
    return [name, votes, party, bool(re.search(r"\(W\)|^Write-In\b", name))]


def read_report_a(pages, what):
    """The "Precinct Results Report" layout: [(page number, [lines])] -> {"county", "precincts": {label: {"ballots",
    "contests": {title: contest}}}, "pages"}."""
    out = {"layout": "A", "county": None, "precincts": {}, "pages": len(pages), "end": False, "numbered": []}
    for p, lines in pages:
        pre, start = None, None
        for j, t in enumerate(lines):
            m = re.search(r"OFFICIAL BALLOT FOR (.+?) COUNTY$", t)
            if m:
                out["county"] = out["county"] or m.group(1)
            m = re.match(r"^Run Date \S+ Page (\d+)$", t)
            if m:
                out["numbered"].append(int(m.group(1)))
            m = re.match(r"^(.+?) ([\d,]+) ballots cast$", t) or re.match(r"^(.+?) ([\d,]+) of [\d,]+ registered voters = [\d.]+%$", t)
            if m:
                pre, start = (m.group(1), _int(m.group(2))), j + 1
                break
        if pre is None and any(t.startswith("*** End of report") for t in lines):
            out["end"] = True                              # a last page that carries only the end mark
            continue
        if pre is None:
            raise Stop(f"    {what}: page {p} names no precinct; the report is not laid out as this loader reads it; stopping")
        P = out["precincts"].setdefault(pre[0], {"ballots": pre[1], "contests": {}})
        if P["ballots"] != pre[1]:
            raise Stop(f"    {what}: precinct {pre[0]} is given two numbers of ballots; stopping")
        title, cur = [], None
        for t in lines[start:]:
            if t.startswith("*** End of report"):
                out["end"] = True
                continue
            if t.startswith("Choice Party"):
                name = " ".join(title)
                title = []
                c = P["contests"].get(name)
                if c is not None and c["cast"] is not None:
                    # a second contest of the same title (two unexpired seats of one board): kept apart, under a number
                    n = 2
                    while f"{name} #{n}" in P["contests"] and P["contests"][f"{name} #{n}"]["cast"] is not None:
                        n += 1
                    name = f"{name} #{n}"
                    c = P["contests"].get(name)
                if c is None:
                    c = P["contests"][name] = _new_contest(_vote_for(name))
                cur = c
                continue
            m = re.match(r"^(Cast Votes|Undervotes|Overvotes|Rejected write-in votes|Unresolved write-in votes):\s*(.*)$", t)
            if m and cur is not None:
                if m.group(1) == "Cast Votes":
                    cur["cast"] = _int(re.findall(PAIR, m.group(2))[-1][0])
                else:
                    nums = re.findall(r"[\d,]+", m.group(2))
                    key = {"Undervotes": "under", "Overvotes": "over"}.get(m.group(1), "other_lines")
                    cur[key] += _int(nums[-1])
                    cur.setdefault("seen", []).append(key)
                if m.group(1) == "Overvotes" and "under" in cur.get("seen", []):
                    cur["slots"] = cur["cast"] + cur["under"] + cur["over"]
                continue
            m = re.match(rf"^(.*?)\s*((?:{PAIR}\s*)+)$", t)
            if m and cur is not None and cur["cast"] is None:
                cur["cands"].append(_cand(m.group(1), _int(re.findall(PAIR, m.group(2))[-1][0]), "A"))
                continue
            if cur is not None and cur["cast"] is None:
                if cur["cands"]:
                    cur["cands"][-1][0] += " " + t          # a wrapped name or a running mate
                    cur["cands"][-1][3] = cur["cands"][-1][3] or "(W)" in t
                continue
            cur = None                                     # (a county that prints no under and over votes for a contest leaves its slots unknown)
            title.append(t)
    for P in out["precincts"].values():
        for c in P["contests"].values():
            c.pop("seen", None)
    return out


B_HEAD = re.compile(r"^(?:(?:Precinct )?Summary Results Report|Report generated with|(?:Precinct )?Summary - )")
B_SKIP = re.compile(r"^(?:TOTAL\b|Statistics\b|Registered Voters\b|Ballots Cast - Blank|Voter Turnout\b|Excused\b|\d+ Day\b|Day \(|\(\d+ ?Day\))")
B_DATE = re.compile(r"^\w+ \d{1,2}(?:st|nd|rd|th)?,? \d{4} (.+?) County,?(?: KY)?$", re.I)


def read_report_b(pages, what):
    """The Electionware "Precinct Summary Results Report" layout: the same shape as read_report_a. The first number on a
    row is its total (some counties print the voting methods after it)."""
    out = {"layout": "B", "county": None, "precincts": {}, "pages": len(pages), "end": False, "numbered": []}
    for p, lines in pages:
        k = next((j for j, t in enumerate(lines) if B_DATE.match(t)), None)
        if k is None or k + 1 >= len(lines):
            raise Stop(f"    {what}: page {p} has no date and county line; the report is not laid out as this loader reads it; stopping")
        out["county"] = out["county"] or B_DATE.match(lines[k]).group(1)
        label = lines[k + 1]
        for t in lines:
            m = re.match(r"^(?:Precinct )?Summary - .* ([\d,]+) of ([\d,]+)$", t)
            if m:
                out["numbered"].append(_int(m.group(1)))
                out["end"] = out["end"] or m.group(1) == m.group(2)
        P = out["precincts"].setdefault(label, {"ballots": None, "contests": {}})
        cur = P.get("_open")
        raw = [t for t in lines[k + 2:] if not B_HEAD.match(t)]
        body, j = [], 0
        while j < len(raw):           # a row whose figures are printed on the line below its label is put back together
            if (j + 1 < len(raw) and re.fullmatch(r"[\d,]+(?:\s+[\d,]+)*", raw[j + 1]) and re.search(r"[A-Za-z]", raw[j])
                    and not re.search(r"\d$", raw[j]) and raw[j] != "Ballots Cast - Total"):
                body.append(f"{raw[j]} {raw[j + 1]}")
                j += 2
            else:
                body.append(raw[j])
                j += 1
        pending = []
        for i, t in enumerate(body):
            if t == "Ballots Cast - Total":
                raise Unreadable("its figures are printed on lines apart from their labels")
            m = re.match(r"^Ballots Cast - Total ([\d,]+)", t)
            if m:
                if P["ballots"] not in (None, _int(m.group(1))):
                    raise Stop(f"    {what}: precinct {label} is given two numbers of ballots; stopping")
                P["ballots"] = _int(m.group(1))
                continue
            m = re.match(r"^Vote For (\d+)$", t)
            if m:
                name = " ".join(pending)
                pending = []
                old = P["contests"].get(name)
                n = 2
                while old is not None and (old["cast"] is not None or old["slots"] is not None or old["writein_total"] is not None):
                    name = f"{' '.join(name.split(' #')[:1])} #{n}"      # a second contest of the same title, kept apart
                    old, n = P["contests"].get(name), n + 1
                cur = old or _new_contest(int(m.group(1)))      # (a contest carried over a page may print its heading again)
                P["contests"][name] = cur
                P["_open"] = cur
                continue
            if B_SKIP.match(t):
                continue
            if i + 1 < len(body) and re.match(r"^Vote For \d+$", body[i + 1]):
                cur = P["_open"] = None                          # a contest's heading: whatever was open is finished
                pending = [t]
                continue
            m = re.match(r"^(.*?[A-Za-z)\].].*?)\s+([\d,]+)((?:\s+[\d,]+)*)$", t)
            if m and cur is not None:
                lab = m.group(1).strip()
                n = _int(m.group(2))
                if lab == "Contest Totals":
                    cur["slots"] = n
                    cur = P["_open"] = None
                elif lab == "Total Votes Cast":
                    cur["cast"] = n
                elif lab in ("Overvotes", "Undervotes"):
                    cur[{"Overvotes": "over", "Undervotes": "under"}[lab]] = n
                elif lab == "Write-In Totals":
                    cur["writein_total"] = n
                elif lab == "Not Assigned":
                    cur["unassigned"] = n                   # write-ins for names no declared candidate bears: not in the certified count
                elif re.match(r"^Write-In:\s*(?:Invalid|Unqualified|Uncertified|Other)\b", lab, re.I):
                    cur.setdefault("named", 0)              # write-ins the county itself sets aside as for no declared candidate
                elif lab.startswith("Write-In:"):
                    cur["named"] = cur.get("named", 0) + n  # a declared write-in candidate's own votes, part of the total
                elif cur["cast"] is None and cur["writein_total"] is None:
                    cur["cands"].append(_cand(lab, n, "B"))
                else:
                    raise Stop(f"    {what}: precinct {label}: a row after a contest's totals ({lab!r}); stopping")
                pending = []
                continue
            if cur is not None and cur["cands"] and cur["cast"] is None and cur["writein_total"] is None:
                cur["cands"][-1][0] += " " + t              # a wrapped ticket ("SHANAHAN")
                continue
            pending.append(t)
    for P in out["precincts"].values():
        P.pop("_open", None)
        for c in P["contests"].values():
            if c["writein_total"] is not None:
                # what the declared write-in candidates got: their own rows where the report gives them, else the total less
                # the votes it says were for no declared candidate
                got = c.pop("named") if "named" in c else c["writein_total"] - c["unassigned"]
                c["unassigned"] = c["writein_total"] - got
                if got:
                    c["cands"].append(["Write-in votes", got, "", True])
            if c["cast"] is None:
                c["cast"] = sum(x[1] for x in c["cands"]) + c["unassigned"]
    return out


def read_report_c(pages, what):
    """A third layout ("Precinct Report", some counties in 2022): precincts follow one another down the page ("Precinct
    A101 (Ballots Cast: 295)"), a contest's title ends ", Vote For 1", and candidate rows carry no party letters."""
    out = {"layout": "C", "county": None, "precincts": {}, "pages": len(pages), "end": False, "numbered": []}
    P, cur = None, None
    for p, lines in pages:
        for t in lines:
            m = re.search(r"OFFICIAL BALLOT FOR (.+?) COUNTY", t)
            if m:
                out["county"] = out["county"] or m.group(1)
                continue
            m = re.match(r"^Page ([\d,]+) of ([\d,]+)\b", t)
            if m:
                out["numbered"].append(_int(m.group(1)))
                out["end"] = out["end"] or m.group(1) == m.group(2)
                continue
            if re.match(r"^(?:Precinct Report|Total Number of Voters|Party Candidate )", t):
                continue
            m = re.match(r"^Precinct (.+) \(Ballots Cast: ([\d,]+)\)$", t)
            if m:
                P = out["precincts"].setdefault(m.group(1), {"ballots": _int(m.group(2)), "contests": {}})
                if P["ballots"] != _int(m.group(2)):
                    raise Stop(f"    {what}: precinct {m.group(1)} is given two numbers of ballots; stopping")
                continue
            m = re.match(r"^(.*), Vote For (\d+)$", t)
            if m and P is not None:
                name = m.group(1)
                old = P["contests"].get(name)
                n = 2
                while old is not None and old["cast"] is not None:
                    name = f"{m.group(1)} #{n}"
                    old, n = P["contests"].get(name), n + 1
                cur = old or _new_contest(int(m.group(2)))
                P["contests"][name] = cur
                continue
            m = re.match(r"^(Cast Votes|Over Votes|Under Votes):\s*(.*)$", t)
            if m and cur is not None:
                n = _int(re.findall(PAIR, m.group(2))[-1][0])
                key = {"Cast Votes": "cast", "Over Votes": "over", "Under Votes": "under"}[m.group(1)]
                cur[key] = n
                cur.setdefault("seen", []).append(key)
                if {"cast", "over", "under"} <= set(cur["seen"]):
                    cur["slots"] = cur["cast"] + cur["under"] + cur["over"]
                continue
            m = re.match(rf"^(.*?)\s*((?:{PAIR}\s*)+)$", t)
            if m and cur is not None and cur["cast"] is None:
                cur["cands"].append(_cand(m.group(1), _int(re.findall(PAIR, m.group(2))[-1][0]), "C"))
                continue
            if cur is not None and cur["cast"] is None and cur["cands"]:
                cur["cands"][-1][0] += " " + t
                cur["cands"][-1][3] = cur["cands"][-1][3] or "(W)" in t
                continue
            if P is None:
                continue
            raise Stop(f"    {what}: page {p}: a line this loader does not read ({t[:60]!r}); stopping")
    for P in out["precincts"].values():
        for c in P["contests"].values():
            c.pop("seen", None)
    return out


class Unreadable(Exception):
    """A county's report that holds no precinct figures this loader can read (a scan, text drawn out of order, county
    totals only). The county's own figures then come from the Secretary's row, and no place inside it is given."""


def read_report(path, what):
    from ballot import pdftext
    pages = collections.OrderedDict()
    for p, _y, t in pdftext.lines(path):
        t = " ".join(t.split())
        if t:
            pages.setdefault(p, []).append(t)
    pages = list(pages.items())
    if not pages:
        raise Unreadable("the file holds no text (a scanned picture)")
    first = pages[0][1]
    if any(t.startswith("Cumulative Results Report") for t in first[:3]):
        raise Unreadable("the file holds the county's totals only, not its precincts")
    if any(re.match(r"^Precinct .+ \(Ballots Cast: [\d,]+\)$", t) for t in first):
        doc = read_report_c(pages, what)
    elif any(re.fullmatch(r"Vote For \d+", t) for t in first):
        doc = read_report_b(pages, what)
    elif any(re.search(r"OFFICIAL BALLOT FOR .+ COUNTY$", t) for t in first):
        doc = read_report_a(pages, what)
    elif not any(re.search(r"\b(?:Results|Report|COUNTY|County)\b", t) for t in first):
        raise Unreadable("the file's text cannot be read in order (its words come out backwards)")
    else:
        raise Stop(f"    {what}: the report is laid out in a way this loader does not read; stopping")
    doc["head"] = " ".join(pages[0][1][:12])[:600]        # the first page's heading lines: which election the report is of
    return check_report(doc, what)


def of_election(rep, day):
    """Whether a report's heading names the general election of this day (11/5/2024, November 5, 2024, 241105...)."""
    import datetime as dt
    d = dt.date.fromisoformat(day)
    month = d.strftime("%B")
    pats = [rf"\b0?{d.month}/0?{d.day}/{d.year}\b", rf"\b{month} 0?{d.day}(?:st|nd|rd|th)?,? {d.year}\b", rf"\b{d:%y%m%d}\b"]
    return any(re.search(x, rep.get("head") or "", re.I) for x in pats)


def check_report(doc, what):
    """Every page read, every contest adding up; returns the report with its precincts' contests checked."""
    n = doc["numbered"]
    if not doc["end"] or n != list(range(1, len(n) + 1)) or len(n) != doc["pages"]:
        raise Stop(f"    {what}: the pages read ({doc['pages']}) are not numbered 1 to the end without a gap, or the report has no end; stopping")
    if not doc["county"] or bare(doc["county"]) not in FIPS:
        raise Stop(f"    {what}: the report names no Kentucky county ({doc['county']!r}); stopping")
    for label, P in doc["precincts"].items():
        if P["ballots"] is None:
            raise Stop(f"    {what}: precinct {label} gives no number of ballots; stopping")
        for title, c in P["contests"].items():
            if c["cast"] is None:
                raise Stop(f"    {what}: precinct {label}, {title}: the contest's totals were not read; stopping")
            if sum(x[1] for x in c["cands"]) + c.get("unassigned", 0) != c["cast"]:
                raise Stop(f"    {what}: precinct {label}, {title}: the candidates add up to {sum(x[1] for x in c['cands'])}, not the {c['cast']} cast; stopping")
    return doc


def report_cached(path, cache, what):
    """A report as read, from a parsed copy kept beside it when the file and this reader are the same."""
    sha = M._sha_file(path)
    keep = os.path.join(cache, "parsed", os.path.relpath(path, os.path.join(cache, "recaps")) + ".json")
    try:
        with open(keep, encoding="utf-8") as fh:
            got = json.load(fh)
        if got.get("sha256") == sha and got.get("parser") == PARSER:
            return got["report"], sha
    except (OSError, ValueError):
        pass
    rep = read_report(path, what)
    M._save(keep, {"sha256": sha, "parser": PARSER, "report": rep})
    return rep, sha


# ---------------------------------------------------------------- reading the Secretary's county-by-county document

def read_table(path, what):
    """[{"office", "district", "chamber", "unexpired", "parties", "rows": {county fips: [ints]}, "total": [ints]}]: every section
    of the document, the rows of each county and its Total Votes row."""
    from ballot import pdftext
    lines = [" ".join(t.split()) for _p, _y, t in pdftext.lines(path)]
    secs, head, cur = [], [], None
    row = re.compile(r"^([A-Z][A-Za-z.' ]*?)\s+((?:[\d,]+\s*)+)$")
    for t in lines:
        m = re.match(r"^Total Votes\s+((?:[\d,]+\s*)+)$", t)
        if m and cur is not None:
            cur["total"] = [_int(x) for x in m.group(1).split()]
            secs.append(cur)
            cur, head = None, []
            continue
        m = row.match(t)
        if m and bare(m.group(1)) in FIPS and not re.search(r"\d(?:st|nd|rd|th)\b", t):
            if cur is None:
                cur = section_head(head)
            code = FIPS[bare(m.group(1))]
            vals = [_int(x) for x in m.group(2).split()]
            if code in cur["rows"]:
                raise Stop(f"    {what}: {COUNTY_NAME[code]} is named twice in the section {cur['office']} {cur['district'] or ''}; stopping")
            cur["rows"][code] = vals
            continue
        if cur is None:
            head.append(t)
    if cur is not None:
        raise Stop(f"    {what}: the last section has no Total Votes row; stopping")
    return secs


def section_head(head):
    """A section's office, district and parties from the lines above its first row."""
    sec = {"office": None, "district": None, "chamber": None, "unexpired": False, "parties": [], "rows": {}, "total": None}
    for t in head:
        m = re.fullmatch(r"(\d+)(?:st|nd|rd|th) (Representative|Senatorial) District", t)
        if m:
            sec["district"], sec["chamber"] = int(m.group(1)), {"Representative": "house", "Senatorial": "senate"}[m.group(2)]
        if re.fullmatch(r"Unexpired Term", t):
            sec["unexpired"] = True
        if re.fullmatch(r"(?:(?:[A-Z][a-z]+ )?Party|Write-In|Independent|Nonpartisan|No Party|Political Organization)(?: (?:(?:[A-Z][a-z]+ )?Party|Write-In|Independent|Nonpartisan))*", t):
            sec["parties"] = re.findall(r"(?:[A-Z][a-z]+ )?Party|Write-In|Independent|Nonpartisan", t)
    offices = [c["table"] for c in CONTESTS] + ["State Representative", "State Senator"]
    sec["office"] = next((t for t in reversed(head) if t in offices), None) or next((t for t in head if t in offices), None)
    return sec


# ---------------------------------------------------------------- what a contest title says

def chamber_of(title):
    if title.upper().startswith("STATE REPRESENTATIVE"):
        return "house"
    if title.upper().startswith(("STATE SENATOR", "STATE SENATE")):
        return "senate"
    return None


def district_in(title):
    # "21st Representative District", "16th Senatorial District", Jefferson's 2022 "- 28th LD District 28"
    m = re.search(r"(\d+)(?:st|nd|rd|th) (?:Representative|Senatorial|Senate|Legislative|LD|SD)\b", title) or re.search(r"\bDistrict (\d+)\b", title)
    return int(m.group(1)) if m else None


def unexpired(title):
    return "(Unexpired Term)" in title


CITY_TITLE = re.compile(r"\b(?:City|CITY) of (.+?)(?:\s*\(Unexpired Term\))?\s*(?:-\s*\(Vote.*)?$")
WARD = re.compile(r"^(.*?)\s+(?:(\d+)(?:st|nd|rd|th)\s+(?:Ward|District|Council District|Councilmanic District)|(?:Ward|District)\s+(?:No\.\s*)?(\w+))$", re.I)
CITY_OFFICES = re.compile(r"^(?:MAYOR|CITY COUNCIL|CITY COMMISSIONERS?|COUNCIL ?MEMBERS?|MEMBERS? (?:of )?(?:the )?(?:CITY )?COUNCIL|COMMISSIONERS?|"
                          r"CITY LEGISLATIVE BODY|BOARD of ALDERMEN|ALDERM[AE]N|TRUSTEES?)\b", re.I)
# Jefferson County's reports name a small city before and after its office ("JEFFERSONTOWN COUNCILMEMBER JEFFERSONTOWN")
REPEATED = re.compile(r"^(?P<a>[A-Z][A-Z .'-]+?) (?:MAYOR|COUNCIL ?MEMBERS?|COUNCIL|COMMISSIONERS?) (?P=a)$")
# the two consolidated governments' councils, elected by district, and Louisville Metro's mayor, the one mayor every
# precinct of Jefferson County votes for (its 2022 report heads the contest "MAYOR" alone)
METRO = [("21111", re.compile(r"^LOUISVILLE METRO COUNCIL\b.*\bDistrict (\d+)$", re.I), "Louisville"),
         ("21067", re.compile(r"^URBAN COUNTY COUNCIL\b.*\bDistrict (\d+)\b", re.I), "Lexington"),
         ("21111", re.compile(r"^MAYOR$"), "Louisville"),
         ("21067", re.compile(r"^MAYOR\b.*\bURBAN COUNTY\b", re.I), "Lexington")]


def city_of(title, county=None):
    """(the city's name, the ward or None) for a contest of a city, or None."""
    t = re.sub(r"\s*-\s*\(Vote for.*$", "", title).strip()
    for code, rx, name in METRO:
        m = rx.match(t)
        if m and county == code:
            return name, (int(m.group(1)) if m.groups() else None)
    m = REPEATED.match(t)
    if m and county == "21111" and not t.startswith(("COUNTY ", "LOUISVILLE ", "STATE ", "MEMBER ")):
        return m.group("a"), None
    if not CITY_OFFICES.match(title):
        return None
    m = CITY_TITLE.search(title)
    if not m:
        return None
    name = re.sub(r"\s*\(Unexpired Term\)\s*", " ", m.group(1)).strip()
    name = re.split(r"\s+-\s+", name)[0]                      # "Campbellsville - Twelve (12) to be elected"
    w = WARD.match(name)
    if w:
        n = w.group(2) or w.group(3)
        n = int(n) if n.isdigit() else NUMWORDS.get(n.lower())
        if n:
            return w.group(1).strip(), n
    return name, None


def city_key(name):
    """A city's name for matching only: abbreviations written out (Ft., Mt., St.), letters alone."""
    s = re.sub(r"\bFt\b\.?", "Fort", str(name or ""), flags=re.I)
    s = re.sub(r"\bMt\b\.?", "Mount", s, flags=re.I)
    s = re.sub(r"\bSt\b\.?", "Saint", s, flags=re.I)
    return letters(s)


def magisterial_of(title):
    # (a county commissioner's contest can be on every ballot of the county, the district being where the member lives;
    # so only the magistrate's, justice of the peace's and constable's contests are read for which district a precinct is in)
    m = re.match(r"^(?:MAGISTRATE|JUSTICE of the PEACE|CONSTABLE)\s+(?:(\d+)(?:st|nd|rd|th)\s+Magisterial\s+District|"
                 r"(?:Magisterial )?District\s+(\d+))", title, re.I)
    return int(m.group(1) or m.group(2)) if m else None


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def letters(s):
    return re.sub(r"[^a-z]", "", str(s or "").lower())


# ---------------------------------------------------------------- adding up

def _add(into, v):
    for i in range(len(v)):
        into[i] += v[i]


def surname(ticket):
    return ticket.split(" and ")[0].split()[-1].upper()


def four(c, contest, what):
    """[dem, rep, other, total] of a statewide contest in one precinct."""
    out = {}
    lettered = any(x[2] for x in c["cands"])
    for side in ("dem", "rep"):
        if lettered:
            fits = [x for x in c["cands"] if PARTY.get(x[2]) == side]
        else:
            # a report that prints no party letters: the ticket's row is the one row bearing its first person's surname,
            # and the Secretary's columns check it county by county
            fits = [x for x in c["cands"] if not x[3] and re.search(rf"\b{re.escape(surname(contest[side]))}\b", x[0].upper())]
        if len(fits) != 1 or surname(contest[side]) not in fits[0][0].upper():
            raise Stop(f"    {what}, {contest['title']}: the {side.upper()} row is not the one ({contest[side]}) this loader was checked against; stopping")
        out[side] = fits[0][1]
    total = sum(x[1] for x in c["cands"])
    return [out["dem"], out["rep"], total - out["dem"] - out["rep"], total]


def ref_of(P, year=None):
    """A precinct's full ballots, for telling whether a contest reached all of them: the figure that most of its
    one-seat contests' votes, under and over votes come to (the larger, where two figures are as common). The ballot
    count the report prints can be a few more (blank or spoiled ballots in some counties), and the President's contest a
    few more than the rest (ballots for President only, which federal law lets a voter new to the state cast). None where
    the report gives no under and over votes."""
    n = collections.Counter(c["slots"] for t, c in P["contests"].items()
                            if c["vote_for"] == 1 and c["slots"] and not t.upper().startswith("STRAIGHT PARTY"))
    if not n:
        return None
    top = max(n.values())
    return max(v for v, k in n.items() if k == top)


def whole(c, ballots):
    """Whether all of a precinct's ballots voted in a contest: True, False, or None where the report gives no under and
    over votes for it (some Electionware counties), so that it cannot be told."""
    if c.get("slots") is None or ballots is None:
        return None
    return c["slots"] == c["vote_for"] * ballots


def few(rec):
    hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dem"], v["rep"], v["other"]) == v["total"]]
    if hold:
        rec["too_few"] = hold
    return rec


def fits(row, cands):
    """Whether a row of the Secretary's table is these candidates' sums (cands: {(party, name, write-in?): votes}): every
    named candidate's votes are one of the row's figures, each figure used once, and what is left of the row is the
    write-ins' (some reports give the write-ins as one total, the Secretary each write-in candidate apart)."""
    left = collections.Counter(x for x in row if x)
    for (_p, _n, w), v in cands.items():
        if v and not w:
            if not left[v]:
                return False
            left[v] -= 1
    return sum(k * n for k, n in left.items()) == sum(v for (_p, _n, w), v in cands.items() if w)


def fits_district(row, cands):
    """The check of a legislative contest's precincts against the Secretary's row for that county, which tells which
    district they voted in. As fits(), with two things the Secretary's legislative rows do: some leave the write-ins out
    (what is left of the row is then nothing), and one district's rows carry its write-in candidates alone (2024, Senate
    district 29: the candidates printed on the ballot are not among its columns, and what is left of the row is all the
    write-ins). At least one candidate's or the write-ins' figures
    must be found in the row, and the whole row must be accounted for."""
    left = collections.Counter(x for x in row if x)
    matched = missing = 0
    for (_p, _n, w), v in cands.items():
        if v and not w:
            if left[v]:
                left[v] -= 1
                matched += 1
            else:
                missing += 1
    rest = sum(k * n for k, n in left.items())
    writeins = sum(v for (_p, _n, w), v in cands.items() if w)
    if missing:
        return rest == writeins and writeins > 0
    return matched > 0 and rest in (writeins, 0)


def contest_of(P, prefix):
    prefixes = tuple(x.upper() for x in ((prefix,) if isinstance(prefix, str) else prefix))
    return [(t, c) for t, c in P["contests"].items() if t.upper().startswith(prefixes)]


def pkey(label):
    """A precinct's key for finding the same precinct in another year's report: its code (A102, B104A) where the label
    begins with one, else the whole label."""
    m = re.match(r"^([A-Z]{1,2}\d{2,4}[A-Z]?)\b", label)
    return m.group(1) if m else label


def map_columns(sec, mine, what):
    """{column: candidate index} of a statewide section: each column equal, in every county read, to one candidate's
    precinct sums (mine: {county: [candidate sums]}). Columns that are zero everywhere may go to any zero candidate."""
    cols = len(sec["total"])
    counties = [k for k in mine if k in sec["rows"]]
    out = {}
    for j in range(cols):
        fits = [i for i in range(len(next(iter(mine.values())))) if all(sec["rows"][k][j] == mine[k][i] for k in counties)]
        if not fits:
            raise Stop(f"    {what}: column {j + 1} of the Secretary's table equals no candidate's precinct sums; stopping")
        out[j] = fits
    return out


def build(years, tables, clerk, cities=None, contests=CONTESTS, statutes=None, houses=HOUSE, senates=SENATE, expect=True, fetched=None):
    """Everything added up and checked. years: {year: {county fips: report or None}}; tables: {year: [sections]}; clerk:
    {contest id: {dem, rep, other, total, where}}; cities: {(county fips, letters of the name): place id}. Returns (the file,
    what failed)."""
    statutes = statutes if statutes is not None else {s["key"]: {int(k): [x.strip() for x in v.split(",")] for k, v in s["typed"].items()} for s in STATUTES}
    cities = cities or {}
    failed, ctl, state = [], {}, {}
    unknown_slots, off_ballots = collections.Counter(), collections.Counter()
    differs = collections.defaultdict(dict)       # year -> {county: why its precinct report is not used}
    pack = lambda v: dict(zip(SIDES, v))                                                               # noqa: E731
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}
    ids = [c["id"] for c in contests]
    pre = {}            # (year, county, label) -> {"ballots", "v": {cid: [4]}}
    notes = []

    # ---- the statewide contests, precinct by precinct and county by county
    for c in contests:
        cid, year = c["id"], c["year"]
        reports = years[year]
        sec = next((s for s in tables[year] if s["office"] == c["table"] and s["district"] is None), None)
        if sec is None:
            failed.append(f"{cid}: the Secretary's document has no section headed {c['table']}")
            continue
        sums, cand_sums, n_pre, lacking = {}, {}, 0, collections.defaultdict(list)
        for code, rep in reports.items():
            if rep is None:
                continue
            what = f"{year} {COUNTY_NAME[code]}"
            s4, cs = [0] * 4, None
            for label, P in rep["precincts"].items():
                hits = contest_of(P, c["title"])
                if len(hits) != 1:
                    lacking[code].append(label)      # the county's figures will not reach the Secretary's row, and it is left out below
                    continue
                t, k = hits[0]
                if whole(k, P["ballots"]) is None:
                    unknown_slots[year] += 1
                elif whole(k, P["ballots"]) is False:
                    off_ballots[year] += 1         # a few ballots more than the contest's votes, under and over votes: noted, not a fault
                v = four(k, c, what)
                pre.setdefault((year, code, label), {"ballots": P["ballots"], "v": {}})["v"][cid] = v
                _add(s4, v)
                n_pre += 1
                cs = cs or collections.defaultdict(int)
                for x in k["cands"]:
                    cs[(x[2], letters(x[0])[:24], x[3])] += x[1]
            sums[code] = s4
            cand_sums[code] = cs or {}
        # the column check: each of the Secretary's columns is one candidate in every county read. A county whose precinct
        # report does not add up to its certified row (a report printed before an amendment, a report of one kind of ballot
        # only) has the Secretary's row for its figures, and none of its precincts is used for anything
        ok_cols, missing_rows = True, {}
        for code, rep in reports.items():
            row = sec["rows"].get(code)
            if row is None:
                failed.append(f"{cid}: the Secretary's table has no row for {COUNTY_NAME[code]}")
                ok_cols = False
                continue
            if rep is not None and (lacking.get(code) or not fits(row, cand_sums[code])):
                ours = sorted((v for (_p, _n, w), v in cand_sums[code].items() if v and not w), reverse=True)[:3]
                why = (f"{len(lacking[code])} of its precincts' reports carry no {c['office']} contest" if lacking.get(code) else
                       f"its precincts add up to {', '.join(f'{x:,}' for x in ours)} for the leading candidates and the Secretary's certified row reads "
                       f"{', '.join(f'{x:,}' for x in sorted(row, reverse=True)[:3])}" + ("" if ours != sorted(row, reverse=True)[:3] else ", the write-ins differing"))
                differs[year][code] = why
                del sums[code], cand_sums[code]
                for label in rep["precincts"]:
                    pre.pop((year, code, label), None)
                reports[code] = None
            if reports[code] is None:
                missing_rows[code] = row
        if len(differs[year]) > 12:
            failed.append(f"{cid}: {len(differs[year])} counties' precinct reports do not add up to their certified rows; more than a reader's slip would explain")
        # the Democratic and Republican columns, told by the counties read
        dcol = rcol = None
        if ok_cols:
            for side in ("dem", "rep"):
                cols = [j for j in range(len(sec["total"])) if all(sec["rows"][k][j] == sums[k][0 if side == "dem" else 1] for k in sums)
                        and sec["total"][j] == sum(sums[k][0 if side == "dem" else 1] for k in sums) + sum(r[j] for r in missing_rows.values())]
                if len(cols) != 1:
                    failed.append(f"{cid}: the {side} ticket is {len(cols)} of the Secretary's columns, not one")
                elif side == "dem":
                    dcol = cols[0]
                else:
                    rcol = cols[0]
        for code, row in missing_rows.items():
            if dcol is None or rcol is None:
                continue
            sums[code] = [row[dcol], row[rcol], sum(row) - row[dcol] - row[rcol], sum(row)]
        state[cid] = [sum(v[i] for v in sums.values()) for i in range(4)]
        official = None
        if dcol is not None and rcol is not None:
            t = sec["total"]
            official = [t[dcol], t[rcol], sum(t) - t[dcol] - t[rcol], sum(t)]
        rec = ctl[cid] = {"sum_of_precincts": pack(state[cid]), "precincts": n_pre,
                          "official": pack(official) if official else None,
                          "counties": {"compared": sum(1 for r in reports.values() if r is not None), "equal": ok_cols,
                                       "from_the_secretarys_row": [COUNTY_NAME[k] for k in sorted(missing_rows)],
                                       "precinct_report_differs": {COUNTY_NAME[k]: w for k, w in sorted(differs[year].items())}},
                          "equal": bool(official) and official == state[cid] and ok_cols,
                          "source": f"ky-sos-results-{year}", "where": f"the section headed {c['table']} of the Secretary's document, county rows and Total Votes row"}
        if official != state[cid]:
            failed.append(f"{cid}: the counties add up to {pack(state[cid])} and the Secretary's Total Votes row reads {pack(official) if official else None}")
        typed = CHECKED.get(cid) if expect else None
        if typed and typed != pack(state[cid]):
            failed.append(f"{cid}: the counties add up to {pack(state[cid])}; this loader was checked against {typed}")
        if clerk.get(cid):
            k = clerk[cid]
            same = all(k[s] == state[cid][i] for i, s in enumerate(SIDES))
            rec["clerk"] = {"official": {s: k[s] for s in SIDES}, "equal": same, "where": k.get("where")}
            if not same:
                failed.append(f"{cid}: the counties add up to {pack(state[cid])} and the Clerk of the House prints { {s: k[s] for s in SIDES} }")
        for code, v in sums.items():
            votes["county"][code][cid] = v
        for key, groups in statutes.items():
            for d, names in groups.items():
                v = [0] * 4
                for name in names:
                    _add(v, sums.get(FIPS[bare(name)], [0] * 4))
                votes["judicial"][f"{key}{d}"][cid] = v

    # ---- the legislative contests: which district each precinct voted in, checked against the Secretary's county rows
    leg_ctl, placed = {}, {}
    # every district the Secretary's documents list a county in, in either year (a Senate district is up in one of them)
    reaches = collections.defaultdict(lambda: collections.defaultdict(set))
    for y in [y for y in DISTRICT_YEARS if y in tables]:
        for s in tables[y]:
            if s["chamber"]:
                for code in s["rows"]:
                    reaches[s["chamber"]][code].add(s["district"])
    for year in [y for y in DISTRICT_YEARS if y in years]:
        reports = years[year]
        secs = {(s["chamber"], s["district"], s["unexpired"]): s for s in tables[year] if s["chamber"]}
        missing = [k for k, r in reports.items() if r is None]
        bad, seen, unplaced = [], {"house": set(), "senate": set()}, collections.defaultdict(set)
        # precinct -> {chamber: [(district or None, whole?)]}
        pl = {}
        for code, rep in reports.items():
            if rep is None:
                continue
            groups = collections.defaultdict(lambda: collections.defaultdict(int))     # (chamber, district or names, unexpired) -> {cand: sum}
            members = collections.defaultdict(list)
            for label, P in rep["precincts"].items():
                for t, k in P["contests"].items():
                    ch = chamber_of(t)
                    if not ch:
                        continue
                    d = district_in(t)
                    g = (ch, d if d is not None else tuple(sorted(letters(x[0]) for x in k["cands"] if not x[3])), unexpired(t))
                    for x in k["cands"]:
                        groups[g][(x[2], letters(x[0])[:24], x[3])] += x[1]
                    members[g].append((label, whole(k, ref_of(P, year))))
            here = set()
            for g, cs in groups.items():
                ch, d, ux = g
                if isinstance(d, int):
                    s = secs.get((ch, d, ux))
                    if not (s and code in s["rows"] and fits_district(s["rows"][code], cs)):
                        bad.append(f"{COUNTY_NAME[code]}, {ch} {d}{' (unexpired)' if ux else ''}")
                        d = None
                else:
                    # an Electionware contest: the one district whose row for this county its precincts add up to
                    cand = [s for (c2, _dd, u2), s in secs.items() if c2 == ch and u2 == ux and code in s["rows"] and fits_district(s["rows"][code], cs)]
                    d = cand[0]["district"] if len(cand) == 1 else None
                    if d is None:
                        unplaced[ch] |= {s["district"] for (c2, dd, u2), s in secs.items() if c2 == ch and code in s["rows"]}
                        bad.append(f"{COUNTY_NAME[code]}, a {ch} contest of the Electionware report matches no single district")
                if d is not None and not ux:
                    seen[ch].add(d)
                    here.add((ch, d))
                for label, ok in members[g]:
                    if not ux:
                        pl.setdefault((code, label), {"house": [], "senate": []})[ch].append((d, ok))
            # a county whose rows the Secretary lists in a district our precincts never placed there
            for (ch, d, ux), s in secs.items():
                if code in s["rows"] and not ux and (ch, d) not in here:
                    bad.append(f"{COUNTY_NAME[code]}: the Secretary lists it in {ch} district {d}, and no precinct of its report is placed there")
        for code in missing:
            for ch in ("house", "senate"):
                unplaced[ch] |= reaches[ch][code]
        placed[year] = (pl, unplaced)
        leg_ctl[str(year)] = {"house_contests": len(seen["house"]), "senate_contests": len(seen["senate"]), "precinct_rows_equal_the_secretary": not bad}
        if bad:
            failed.append(f"{year}: the legislative contests' precincts do not add up to the Secretary's county rows in {'; '.join(bad[:6])}"
                          + (f" (and {len(bad) - 6} more)" if len(bad) > 6 else ""))
        if expect and sorted(seen["house"] | unplaced["house"]) != list(range(1, houses + 1)):
            failed.append(f"{year}: House contests for {len(seen['house'] | unplaced['house'])} districts, not {houses}")
    dyears = [y for y in DISTRICT_YEARS if y in placed]
    if dyears and expect:
        both = set().union(*(set(d for lst in placed[y][0].values() for d, _ok in lst["senate"]) | placed[y][1]["senate"] for y in dyears))
        both.discard(None)
        if sorted(both) != list(range(1, senates + 1)):
            failed.append(f"Senate contests for {len(both)} districts in {dyears}, not {senates}")

    # ---- districts: whole precincts only; a precinct's Senate district from the year its district was up
    parity = {}
    for y in dyears:
        parity[y] = {d % 2 for lst in placed[y][0].values() for d, _ok in lst["senate"] if d is not None}
    for year in dyears:
        pl, unplaced = placed[year]
        others = [y for y in dyears if y != year]
        reports = years[year]
        out_h, out_s = set(unplaced["house"]), set(unplaced["senate"])
        split_h, split_s, unknown_s, hd_of, sd_of = {}, {}, {}, {}, {}
        index_other = {}
        for y in others:
            idx = collections.defaultdict(list)
            for (code, label), v in placed[y][0].items():
                idx[(code, pkey(label))].append(v)
            index_other[y] = idx
        touched, own_s = {}, {}
        for (code, label), v in pl.items():
            hs = {d for d, _ok in v["house"]}
            touched[(code, label)] = hs - {None}
            own_s[(code, label)] = {d for d, _ok in v["senate"] if d is not None}
            if not v["house"]:
                failed.append(f"{year}: precinct {label} of {COUNTY_NAME[code]} voted in no State Representative contest")
            # (one House contest whose under and over votes are not given is still the precinct's only district: every voter
            # votes in some House contest, all 100 being up, so a precinct lying in two would carry two)
            if len(v["house"]) != 1 or v["house"][0][1] is False or None in hs:
                split_h[(code, label)] = sorted(x for x in hs if x is not None)
                out_h |= {x for x in hs if x is not None}
                hd_of[(code, label)] = None
            else:
                hd_of[(code, label)] = next(iter(hs))
            sds, halves, partial = {d for d, _ok in v["senate"]}, set(parity[year]), any(ok is False for _d, ok in v["senate"]) or len(v["senate"]) > 1
            for y in others:
                same = index_other[y].get((code, pkey(label))) or []
                if len(same) == 1 and {d for d, _ok in same[0]["house"]} == hs and hd_of[(code, label)] is not None:
                    sds |= {d for d, _ok in same[0]["senate"]}
                    partial = partial or any(ok is False for _d, ok in same[0]["senate"]) or len(same[0]["senate"]) > 1
                    halves |= parity[y]
            sds.discard(None)
            own_whole = len(v["senate"]) == 1 and v["senate"][0][1] is True and v["senate"][0][0] is not None
            if own_whole and not partial and len(sds) == 1:
                halves = {0, 1}                    # its own year's contest reached all its ballots: it lies in that district alone
            if partial or len(sds) > 1:
                split_s[(code, label)] = sorted(sds)
                out_s |= sds
                if halves != {0, 1}:
                    unknown_s[(code, label)] = sorted(hs - {None})       # its other part may lie in a district not up that year
                sds = set()
            elif halves != {0, 1} or not sds:
                unknown_s[(code, label)] = sorted(hs - {None})
                sds = set()
            sd_of[(code, label)] = next(iter(sds)) if sds else None
        for (code, label) in [(c2, lab) for c2, r in reports.items() if r is not None for lab in r["precincts"] if (c2, lab) not in pl]:
            failed.append(f"{year}: precinct {label} of {COUNTY_NAME[code]} voted in no State Representative contest")
            hd_of[(code, label)] = sd_of[(code, label)] = None
            split_h[(code, label)] = []
        # which Senate districts a precinct of unknown Senate district could be in: those its House districts reach elsewhere
        reach = collections.defaultdict(set)
        for key, s in sd_of.items():
            if s is not None:
                for h in touched.get(key, ()):
                    reach[h].add(s)
        for key, hs in unknown_s.items():
            # it lies in the Senate districts its own ballot names and, perhaps, in districts not up that year that reach its
            # county (a part of it in a district that was up would have put that district's contest on its ballot)
            could = own_s.get(key, set()) | {d for d in reaches["senate"][key[0]] if d % 2 not in parity[year]}
            out_s |= could or set(range(1, senates + 1))
        for c in [c for c in contests if c["year"] == year]:
            cid = c["id"]
            hsum, ssum, rest = collections.defaultdict(lambda: [0] * 4), collections.defaultdict(lambda: [0] * 4), [0] * 4
            for (y2, code, label), pv in pre.items():
                if y2 != year or cid not in pv["v"]:
                    continue
                v = pv["v"][cid]
                h, s = hd_of.get((code, label)), sd_of.get((code, label))
                if h is not None and h not in out_h:
                    _add(hsum[h], v)
                else:
                    _add(rest, v)
                if s is not None and s not in out_s:
                    _add(ssum[s], v)
            for code in [k for k, r in reports.items() if r is None]:
                _add(rest, votes["county"][code].get(cid, [0] * 4))
            for h in range(1, houses + 1):
                if h not in out_h and h in hsum:
                    votes["house"][str(h)][cid] = hsum[h]
            for s in range(1, senates + 1):
                if s not in out_s and s in ssum:
                    votes["senate"][str(s)][cid] = ssum[s]
            back = [sum(v[i] for v in hsum.values()) + rest[i] for i in range(4)]
            if back != state.get(cid):
                failed.append(f"{cid}: the House districts given and the precincts left out add up to {back}, not {state.get(cid)}")
        name = lambda k: {"county": COUNTY_NAME[k[0]], "precinct": k[1]}                               # noqa: E731
        leg_ctl[str(year)].update(
            house_districts_given=houses - len(out_h & set(range(1, houses + 1))), house_districts_left_out=sorted(out_h),
            senate_districts_given=senates - len(out_s & set(range(1, senates + 1))), senate_districts_left_out=sorted(out_s),
            precincts_in_more_than_one_house_district=[dict(name(k), house_districts=v) for k, v in sorted(split_h.items()) if v],
            precincts_not_placed_in_a_house_district=[name(k) for k, v in sorted(split_h.items()) if not v],
            precincts_in_more_than_one_senate_district=[dict(name(k), senate_districts=v) for k, v in sorted(split_s.items())],
            precincts_whose_senate_district_is_not_shown=[dict(name(k), house_districts=v) for k, v in sorted(unknown_s.items())],
            counties_whose_report_is_missing=[COUNTY_NAME[k] for k, r in sorted(reports.items()) if r is None])
        placed[year] = (pl, unplaced, hd_of, sd_of)

    # ---- cities, wards and magisterial districts: the precincts of their own contests, whole
    local_ctl = {}
    for year in dyears:
        reports = years[year]
        by_title = collections.defaultdict(lambda: collections.defaultdict(dict))   # place id -> {(title, ward): {(code, label): whole?}}
        mag_pre = collections.defaultdict(dict)
        unmatched, ambiguous = collections.Counter(), collections.Counter()
        for code, rep in reports.items():
            if rep is None:
                continue
            for label, P in rep["precincts"].items():
                mags = {}
                ref = ref_of(P, year)
                for t, k in P["contests"].items():
                    cw = city_of(t, code)
                    if cw:
                        nm, ward = cw
                        key = CITY_ALIASES.get((code, city_key(nm)), city_key(nm))
                        pid = cities.get((code, key))
                        if pid is None:
                            (ambiguous if (code, key) in cities.get("_ambiguous", set()) else unmatched)[f"{nm} ({COUNTY_NAME[code]})"] += 1
                            continue
                        by_title[pid][(re.sub(r" #\d+$", "", t), ward)][(code, label)] = whole(k, ref)
                    if year == 2022:
                        m = magisterial_of(t)
                        if m is not None and not unexpired(t):
                            mags.setdefault(m, True)
                            mags[m] = mags[m] and whole(k, ref)
                if mags:
                    for m, ok in mags.items():
                        mk = f"{code}-{m}"
                        mag_pre[mk][(code, label)] = ok is True and len(mags) == 1
        given_c, given_w, given_m, left = 0, 0, 0, collections.Counter()

        def put(kind, key, members, cid_list):
            for c in cid_list:
                v = [0] * 4
                for (code, label) in members:
                    _add(v, pre[(year, code, label)]["v"][c["id"]])
                votes[kind][key][c["id"]] = v
        mine = [c for c in contests if c["year"] == year]
        for pid, titles in by_title.items():
            union = set().union(*(set(m) for m in titles.values()))
            reached = set(cities.get("_counties", {}).get(pid) or []) | {code for code, _l in union}
            if any(reports.get(c) is None for c in reached):
                left["city or ward: a county it reaches has no precinct report used that year"] += 1
                continue
            plain = [m for (t, w), m in titles.items() if w is None and set(m) == union]
            wards = {(t, w): m for (t, w), m in titles.items() if w is not None}
            at_large = len(wards) >= 2 and all(set(m) == union for m in wards.values())
            # a contest reaching every precinct of the city: its mayor or a council elected citywide; contests headed by
            # ward are citywide too where every ward's contest is on every one of the city's ballots (wards of residence)
            whole_city = plain + (list(wards.values()) if at_large else [])
            if whole_city and all(all(m.get(k) is True for m in whole_city if k in m) for k in union):
                put("mcd", pid, union, mine)
                given_c += 1
            elif whole_city:
                left["city: a precinct lies partly outside it, or the report does not say"] += 1
            else:
                left["city: no contest of it reached all its precincts that year"] += 1
            if wards and not at_large:
                for (t, w), m in wards.items():
                    if all(v is True for v in m.values()):
                        put("ward", f"{pid}-{w}", m, mine)
                        given_w += 1
                    else:
                        left["ward: a precinct lies partly outside it, or the report does not say"] += 1
        # a magisterial district is given only where none of its precincts is shared with another
        shared = {k for mk, mem in mag_pre.items() for k, ok in mem.items() if not ok}
        for mk, mem in mag_pre.items():
            if all(mem.values()) and not (set(mem) & shared):
                put("commissioner", mk, mem, mine)
                given_m += 1
            elif mem:
                left["magisterial district: a precinct lies in two"] += 1
        local_ctl[str(year)] = {"cities_given": given_c, "wards_given": given_w, "magisterial_districts_given": given_m,
                                "left_out": dict(left), "city_names_matched_to_no_place": sorted(unmatched),
                                "city_names_matched_to_more_than_one_place": sorted(ambiguous)}

    # ---- the places
    places = {k: {} for k in KIND_NAMES}
    packed = lambda d: {cid: pack(d[cid]) for cid in ids if cid in d}                                  # noqa: E731
    for code in sorted(votes["county"]):
        places["county"][code] = few({"name": COUNTY_NAME[code], "votes": packed(votes["county"][code])})
    names = cities.get("_names", {})
    counties_of = cities.get("_counties", {})
    for pid in sorted(votes["mcd"]):
        places["mcd"][pid] = few({"name": names.get(pid, pid), "type": "city", "counties": counties_of.get(pid, []), "votes": packed(votes["mcd"][pid])})
    for wk in sorted(votes["ward"]):
        pid, _, w = wk.rpartition("-")
        word = "Council District" if pid in ("KY-M-48003", "KY-M-46027") else "Ward"
        places["ward"][wk] = few({"name": f"{names.get(pid, pid)}, {word} {w}", "place": pid, "votes": packed(votes["ward"][wk])})
    for mk in sorted(votes["commissioner"], key=lambda k: (k.split("-")[0], int(k.split("-")[1]))):
        code, _, m = mk.partition("-")
        places["commissioner"][mk] = few({"name": f"{COUNTY_NAME[code]}, Magisterial District {m}", "counties": [code], "votes": packed(votes["commissioner"][mk])})
    for h in sorted(votes["house"], key=int):
        places["house"][h] = few({"name": f"House District {h}", "votes": packed(votes["house"][h])})
    for s in sorted(votes["senate"], key=int):
        places["senate"][s] = few({"name": f"Senate District {s}", "votes": packed(votes["senate"][s])})
    for key, groups in statutes.items():
        spec = next(x for x in STATUTES if x["key"] == key)
        for d in sorted(groups):
            places["judicial"][f"{key}{d}"] = few({"name": spec["name"].format(d if key == "KY-SC" else ordinal(d)),
                                                   "counties": sorted(FIPS[bare(x)] for x in groups[d]), "votes": packed(votes["judicial"][f"{key}{d}"])})
    kinds_ctl = {}
    for c in contests:
        cid = c["id"]
        if cid not in state:
            continue
        got = [sum(p["votes"][cid][s] for p in places["county"].values() if cid in p["votes"]) for s in SIDES]
        if got != state[cid]:
            failed.append(f"county: the counties do not add up to the statewide sum for {cid}")
        for key in statutes:
            got = [sum(p["votes"][cid][s] for k, p in places["judicial"].items() if k.startswith(key) and cid in p["votes"]) for s in SIDES]
            if got != state[cid]:
                failed.append(f"judicial: the {key} districts do not add up to the statewide sum for {cid}")
    kinds_ctl["county"] = kinds_ctl["judicial"] = "equal" if not [f for f in failed if f.startswith(("county:", "judicial:"))] else "differs"
    kinds_ctl["house"] = "not every district is given; the House districts given and the precincts of those left out add up to the statewide sum"
    kinds_ctl["senate"] = "not every district is given; each district given is whole precincts that voted in it alone"
    kinds_ctl["mcd"] = kinds_ctl["ward"] = kinds_ctl["commissioner"] = "each place given is whole precincts that voted in its own contest with all their ballots"
    if expect:
        for key, n in (("KY-JC", 57), ("KY-JD", 59), ("KY-SC", 7)):
            if len(statutes.get(key, {})) != n or sorted(bare(x) for v in statutes[key].values() for x in v) != sorted(b for b in FIPS if b != "muhlenburg"):
                failed.append(f"judicial: {key} is not {n} districts covering every county once")

    records = []
    for c in contests:
        if c["id"] not in state:
            continue
        rec = {"id": c["id"], "date": ELECTIONS[c["year"]]["date"], "office": c["office"], "table": f"ky-sbe-recaps-{c['year']}",
               "kinds": [k for k in KIND_NAMES if any(c["id"] in p["votes"] for p in places[k].values())]}
        for s, word in (("dem", "Democratic"), ("rep", "Republican")):
            rec[s] = {"party": word, "ticket": c[s], "column": f"the row printed with the party letters {s.upper()}"}
        rec["other"] = {"what": "every other candidate and all write-ins, together"}
        rec["total"] = {"what": "the votes cast for candidates and write-ins; the over and under votes the reports also give are left out"}
        rec["statewide"] = pack(state[c["id"]])
        rec["official_source"] = f"clerk-statistics-{c['year']}" if clerk.get(c["id"]) else f"ky-sos-results-{c['year']}"
        records.append(rec)
    kinds = {}
    for kind, _year, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]),
                       "contests": [c["id"] for c in contests if any(c["id"] in p["votes"] for p in places[kind].values())],
                       "covers_the_state": kind in ("county", "judicial"),
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if kind not in ("county", "judicial"):
            kinds[kind]["why_not_2023"] = REDRAWN
    for kind, word in (("house", "House"), ("senate", "Senate")):
        lc = {y: leg_ctl[str(y)][f"{kind}_districts_left_out"] for y in dyears}
        out_all = sorted(set().union(*map(set, lc.values()))) if lc else []
        kinds[kind]["note"] = (f"A {word} district is given only where every precinct of it voted in that district alone. "
                               + (f"Left out ({'; '.join(f'{y}: {len(v)}' for y, v in lc.items())}): districts {', '.join(str(x) for x in out_all)}, because "
                                  "a precinct of the district lies in another district too, or the record does not show which district a precinct it may "
                                  "share is in, or a county of it has no precinct report that year; the reports give a precinct's votes whole, and nothing "
                                  "is estimated." if out_all else "Every district is given."))
        kinds[kind]["left_out"] = {str(y): v for y, v in lc.items()}
    kinds["senate"]["note"] += (" A precinct's Senate district is read from the election its district was on the ballot (the odd districts in 2024, "
                                "the even ones in 2022): the same precinct of the same county, voting in the same House district, in the other "
                                "year's report.")
    kinds["mcd"]["note"] = ("A city is the precincts that voted in a contest of that city elected citywide (its mayor, or a council or commission "
                            "not elected by ward), given in a year only where it had such a contest and every one of its precincts voted in it with "
                            "all its ballots. A city most of whose precincts also hold voters outside it is therefore often left out; nothing is "
                            "estimated. Names are matched to the Census place names our pages use, by letters alone, in the same county.")
    kinds["ward"]["note"] = "A ward is the precincts that voted in the contest naming the city and the ward, each with all its ballots."
    kinds["commissioner"]["note"] = ("2022 only: every county elected its magistrates (or commissioners) and constables then, each by magisterial "
                                     "district. A district is the precincts of the contests naming it, each with all its ballots; one with a precinct "
                                     "shared with another district is left out.")
    kinds["judicial"]["note"] = ("The counties of each are those KRS 23A.020 (circuits), KRS 24A.030 (districts) and KRS 21A.010 (Supreme Court districts; "
                                 "KRS 22A.010 makes them the Court of Appeals districts too) list today. Every year's figures are those counties' votes.")
    control = {"result": "equal" if not failed else "differs",
               "statement": ("Every report used was read whole, and every contest's candidates add up to its cast votes; for every statewide contest "
                             "each column of the Secretary's county-by-county table equals one candidate's precincts added up, in every county whose "
                             "report is used, and the counties (the Secretary's certified row standing for each county whose report is not read or "
                             "does not add up to it, each named with its reason) add up to the Secretary's Total Votes row; for President and U.S. "
                             "Senator the totals equal the Clerk of the House's statistics; for 2022 and 2024 every State Representative and State "
                             "Senator contest's precincts are found in its county rows in the Secretary's document; counties and judicial districts "
                             "add up to the statewide sum, and the House districts given, with the precincts of those left out and the counties not "
                             "read, do too." if not failed else "The sums do not all agree; see the differences."),
               "precincts": {str(y): sum(len(r["precincts"]) for r in years[y].values() if r) for y in sorted(years)},
               "contests": ctl, "kinds": kinds_ctl, "districts": leg_ctl, "local": local_ctl, "notes": notes}
    for y in sorted(set(unknown_slots) | set(off_ballots)):
        if unknown_slots[y]:
            control["notes"].append(f"{y}: {unknown_slots[y]:,} precincts' reports give no under and over votes, so whether a contest reached all of "
                                    "their ballots cannot be told there; such a precinct is placed in a city, ward or magisterial district only "
                                    "where that can be told, and in a House district only as the one House contest on its ballot.")
        if off_ballots[y]:
            control["notes"].append(f"{y}: in {off_ballots[y]:,} precincts the statewide contest's votes, under and over votes come to a few less "
                                    "than the ballots the report prints for the precinct (blank or spoiled ballots, or ballots for President only); "
                                    "whether another contest reached all of a precinct's ballots is told against the figure most of its "
                                    "one-seat contests come to.")
    doc = {"what": WHAT, "note": NOTE, "state": "KY", "generated": M._now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": list(SIDES), "too_few": {"fewer_than": FEW, "why": TOO_FEW}, "contests": records, "kinds": kinds, "control": control,
           "coverage": {"not_given": NOT_GIVEN, "no_senate": "Kentucky elected no United States senator in 2023 or 2024.",
                        "governor": "Kentucky elected its Governor in 2023, not in 2022 or 2024."},
           "sources": [], "places": places}
    return doc, failed


# ---------------------------------------------------------------- the files

def recap_links(year, say):
    e = ELECTIONS[year]
    try:
        page = net.get(e["recaps"], timeout=90).decode("utf-8", "replace")
    except Exception as ex:  # noqa: BLE001
        raise Stop(f"    the Board's {year} recap page could not be read ({ex}); wait a few minutes and run this again")
    out = {}
    for href in re.findall(r'href="([^"]*ElectionReports[^"]*\.pdf)"', page, re.I):
        code = FIPS.get(bare(href.rsplit("/", 1)[1][:-4]))
        if code is None:
            raise Stop(f"    the Board's {year} recap page links {href!r}, which names no county; stopping")
        if code in out:
            raise Stop(f"    the Board's {year} recap page links {COUNTY_NAME[code]} twice; stopping")
        out[code] = urllib.parse.urljoin(SITE + "/", href)
    for name, url in (e.get("extra") or {}).items():
        out.setdefault(FIPS[bare(name)], url)
    return out


def fetch(url, path, refresh, say, magic=b"%PDF"):
    try:
        net.download(url, path, 0 if refresh else KEEP_DAYS, tries=4, say=say)
    except Exception as e:  # noqa: BLE001
        raise Stop(f"    {url}: could not be fetched ({e}) and no copy is on disk. Wait a few minutes and run this again.")
    with open(path, "rb") as fh:
        if not fh.read(8).startswith(magic):
            raise Stop(f"    {os.path.basename(path)}: what came back is not the file; stopping")
    return path


def read_statute(spec, path):
    from ballot import pdftext
    text = " ".join(" ".join(t.split()) for _p, _y, t in pdftext.lines(path))
    out = {}
    for m in re.finditer(spec["pattern"], text):
        s = re.sub(r"\b(?:Counties|County)\b", "", m.group(2))
        out[int(m.group(1))] = [x.strip() for x in re.split(r",|\band\b", s) if x.strip()]
    return out


def statutes(cache, refresh, say):
    """The three sections, read from the Legislature's copies and required to equal the typed copies (which stand in, and
    the file says so, where a copy cannot be read), and KRS 22A.010's sentence."""
    groups, recs = {}, []
    for s in STATUTES:
        typed = {k: [x.strip() for x in v.split(",")] for k, v in s["typed"].items()}
        rec = {"id": s["id"], "kind": "statute, as the Legislature publishes it", "agency": "Kentucky General Assembly, Legislative Research Commission",
               "title": s["cite"], "url": s["url"]}
        path = os.path.join(cache, s["file"])
        try:
            net.download(s["url"], path, 0 if refresh else 30, tries=3, say=say)
            got = read_statute(s, path)
            rec.update(fetched=M._day(path), sha256=M._sha_file(path))
            if {k: sorted(v) for k, v in got.items()} != {k: sorted(v) for k, v in typed.items()}:
                raise Stop(f"    {s['cite']} no longer reads as the copy this loader was checked against; nothing is written until a person has read the change")
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001
            say(f"      {s['cite']}: could not be read ({e}); the copy typed into this loader on 2026-10-03 is used")
            rec["unread"] = f"could not be read on {M._now()}; the copy typed into the loader on 2026-10-03 is used"
        groups[s["key"]] = typed
        recs.append(rec)
    a = APPEALS
    rec = {"id": a["id"], "kind": "statute, as the Legislature publishes it", "agency": "Kentucky General Assembly, Legislative Research Commission",
           "title": a["cite"], "url": a["url"]}
    try:
        path = os.path.join(cache, a["file"])
        net.download(a["url"], path, 0 if refresh else 30, tries=3, say=say)
        from ballot import pdftext
        text = " ".join(" ".join(t.split()) for _p, _y, t in pdftext.lines(path))
        if a["words"] not in text:
            raise Stop("    KRS 22A.010 no longer says the Court of Appeals districts are the Supreme Court's; nothing is written until a person has read it")
        rec.update(fetched=M._day(path), sha256=M._sha_file(path))
    except Stop:
        raise
    except Exception as e:  # noqa: BLE001
        rec["unread"] = f"could not be read on {M._now()} ({e})"
    recs.append(rec)
    return groups, recs


def clerk_totals(cache, refresh, say):
    out, recs = {}, []
    for year in (2024, 2022):
        src = CLERK[year]
        path = os.path.join(cache, src["file"])
        rec = {k: src[k] for k in ("id", "kind", "agency", "title", "url")}
        try:
            net.download(src["url"], path, 0 if refresh else KEEP_DAYS, tries=3, say=say)
            doc = W.read_clerk(path, state="KENTUCKY")
            rec.update(fetched=M._day(path), sha256=M._sha_file(path), where=doc["where"].replace("Wyoming", "Kentucky"),
                       read="The Kentucky lines for presidential electors and United States Senator; its under and over votes are left out.")
            for c in CONTESTS:
                if c["year"] == year and c.get("clerk"):
                    out[c["id"]] = dict(W.clerk_figures(doc, c["clerk"]), where=rec["where"])
        except Exception as e:  # noqa: BLE001  the Secretary's tables are the control; the Clerk's page is a second one
            say(f"      {src['title']}: could not be read ({e}); the Secretary's tables alone are the control for {year}")
            rec["unread"] = f"could not be read on {M._now()}: {e}"
        recs.append(rec)
    return out, recs


def city_index(db):
    """{(county fips, letters of the name): place id} of our Kentucky cities, with "_names", "_counties" and "_ambiguous";
    None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        idx, names, counties, amb = {}, {}, {}, set()
        for pid, name, cids in con.execute("SELECT id, name, county_ids FROM sl_places WHERE kind = 'mcd' AND id LIKE 'KY-M-%'"):
            names[pid] = name
            cs = json.loads(cids or "[]")
            counties[pid] = cs
            base = re.sub(r"\s+(?:city|town|urban county|metro government|consolidated government)\s*(?:\(balance\))?$", "", name, flags=re.I)
            keys = {city_key(base)}
            if "/" in base:
                keys.add(city_key(base.split("/")[0]))
            if re.search(r"urban county", name, re.I):
                keys.add(city_key(base.split("-")[0]))
            for c in cs:
                for k in keys:
                    if (c, k) in idx and idx[(c, k)] != pid:
                        amb.add((c, k))
                    idx[(c, k)] = pid
        for k in amb:
            idx.pop(k, None)
        idx.update({"_names": names, "_counties": counties, "_ambiguous": amb})
        return idx
    except sqlite3.Error:
        return None
    finally:
        con.close()


def our_places(db):
    """{kind: ids} of our Kentucky places and races, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'ky-%'"):
            out[kind].add(pid)
        for office, level, jid, district in con.execute("SELECT office_kind, level, jurisdiction_id, district FROM sl_races WHERE state = 'KY'"):
            if office == "state_senate":
                out["senate"].add(str(district))
            elif office == "state_house":
                out["house"].add(str(district))
            elif str(jid).startswith(("KY-JC", "KY-JD")):
                out["judicial"].add(str(jid))
            elif office in ("supreme_court", "court_of_appeals"):
                out["judicial"].add(f"KY-SC{jid}")
            elif level == "city" and district not in (None, ""):
                out["ward"].add(f"{jid}-{district}")
            elif office in ("magistrate", "county_commissioner", "constable") and district not in (None, ""):
                out["commissioner"].add(f"{jid}-{district}")
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Kentucky place votes: the State Board of Elections' recap sheets and the Secretary's results by county (elect.ky.gov)")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    years, tables, srcs, fetched = {}, {}, [], {}
    for year in sorted(ELECTIONS, reverse=True):
        e = ELECTIONS[year]
        links = recap_links(year, say)
        reps, shas, why = {}, {}, {}
        for code in sorted(set(FIPS.values())):
            if code not in links:
                reps[code], why[code] = None, "the Board's page links no report for it"
                continue
            path = os.path.join(cache, "recaps", str(year), bare(COUNTY_NAME[code]) + ".pdf")
            try:
                fetch(links[code], path, refresh, lambda *a: None)
            except Stop as ex:
                if "404" not in str(ex):
                    raise
                reps[code], why[code] = None, "the Board's page links a report that is not on its server (404)"
                continue
            try:
                rep, shas[code] = report_cached(path, cache, f"{year} {COUNTY_NAME[code]} recap")
            except Unreadable as ex:
                reps[code], why[code] = None, str(ex)
                shas[code] = M._sha_file(path)
                continue
            if not of_election(rep, e["date"]):
                reps[code], why[code] = None, "the file the Board links is the report of another election"
                continue
            if FIPS.get(bare(rep["county"])) != code:
                raise Stop(f"    {year}: the file linked as {COUNTY_NAME[code]} is the report of {rep['county']} County; stopping")
            reps[code] = rep
        years[year] = reps
        t = e["table"]
        path = fetch(t["url"], os.path.join(cache, t["file"]), refresh, say)
        tables[year] = read_table(path, f"{year} {t['file']}")
        fetched[year] = M._day(path)
        n = sum(len(r["precincts"]) for r in reps.values() if r)
        lay = collections.Counter(r["layout"] for r in reps.values() if r)
        say(f"      {year}: {n:,} precincts in {sum(1 for r in reps.values() if r)} county reports ({lay.get('B', 0)} in the Electionware layout); "
            f"not read: {'; '.join(f'{COUNTY_NAME[k]} ({w})' for k, w in sorted(why.items())) or 'none'}")
        srcs.append({"id": f"ky-sbe-recaps-{year}", "kind": "official results by precinct (each county's recap sheet)", "agency": AGENCY,
                     "title": f"{year} General Recap Sheets, one report for each county", "url": e["recaps"], "listed_on": RESULTS_PAGE,
                     "fetched": M._now(), "precincts": n, "counties": sum(1 for r in reps.values() if r),
                     "not_read": {COUNTY_NAME[k]: w for k, w in sorted(why.items())},
                     "not_linked_but_read": [f"{k} ({v})" for k, v in (e.get("extra") or {}).items()],
                     "files": {COUNTY_NAME[k]: {"url": links[k], "sha256": shas[k]} for k in sorted(shas)},
                     "read": "Of each precinct: its label and ballots cast, and of each contest its title, the candidates' vote totals with the "
                             "party letters printed beside them (to tell which ticket a row is), and the cast, under and over votes; the "
                             "candidates' names are compared only to tell contests and columns apart."})
        srcs.append({"id": f"ky-sos-results-{year}", "kind": "official results by county (the control)", "agency": SOS, "title": t["title"],
                     "url": t["url"], "listed_on": t["page"], "fetched": fetched[year], "sha256": M._sha_file(path),
                     "read": "The county rows and Total Votes row of the statewide contest and of every State Representative and State Senator contest."})
    groups, stat_recs = statutes(cache, refresh, say)
    srcs += stat_recs
    say("    the second control: Clerk of the U.S. House (President 2024, U.S. Senator 2022)")
    clerk, clerk_recs = clerk_totals(cache, refresh, say)
    cities = city_index(db)
    if cities is None:
        say("      the ballot database is not there, so cities and wards cannot be given the ids our pages use; they are left out")
    doc, failed = build(years, tables, clerk, cities=cities, statutes=groups, fetched=fetched)
    doc["sources"] = srcs + clerk_recs

    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['judicial'])} judicial circuits and districts; {len(p['house'])} House and "
        f"{len(p['senate'])} Senate districts; {len(p['mcd'])} cities, {len(p['ward'])} wards, {len(p['commissioner'])} magisterial districts")
    for y, d in doc["control"]["districts"].items():
        say(f"      {y}: House districts given {d.get('house_districts_given')}, left out {d.get('house_districts_left_out')}; Senate given "
            f"{d.get('senate_districts_given')}, left out {d.get('senate_districts_left_out')}")
    for y, d in doc["control"]["local"].items():
        say(f"      {y}: cities {d['cities_given']}, wards {d['wards_given']}, magisterial districts {d['magisterial_districts_given']}; left out {d['left_out']}; "
            f"names matched to no place: {len(d['city_names_matched_to_no_place'])}")
    for cid, k in doc["control"]["contests"].items():
        for county, w in (k.get("counties") or {}).get("precinct_report_differs", {}).items():
            say(f"      {cid}: {county}'s precinct report is not used ({w}); its figures are the Secretary's certified row")
    for c in doc["contests"]:
        k, s = doc["control"]["contests"].get(c["id"], {}), c["statewide"]
        say(f"    control, {c['id']}: Democratic {s['dem']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + ("equal to" if k.get("equal") else "DIFFERS from") + " the Secretary's county rows and Total Votes row"
            + (f"; Clerk of the House {'equal' if k['clerk']['equal'] else 'DIFFERS'}" if k.get("clerk") else ""))
    if failed:
        keep = os.path.join(cache, "last_checks.txt")
        with open(keep, "w", encoding="utf-8") as fh:
            fh.write("\n".join(failed) + "\n")
        for line in failed[:60]:
            say(f"    CHECK: {line}")
        say(f"    every difference is listed in {os.path.relpath(keep, HERE)}")
        raise Stop(f"    Kentucky place votes: the control did not hold ({len(failed)} differences); {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in KIND_NAMES:
            idset = ours.get(kind, set())
            without = sorted((i for i in idset if not p[kind].get(i, {}).get("votes")), key=lambda x: (len(x), x))
            covered[kind] = {"places": len(idset), "with_votes": len(idset) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(idset) - len(without):,} of {len(idset):,}")
        covered["not_given_kinds"] = {k: len(v) for k, v in sorted(ours.items()) if k not in KIND_NAMES}
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places and sl_races in {os.path.basename(db)}, opened read-only on {M._now()}")
    M.write(out, doc)
    say(f"    Kentucky place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.2f} MB)")
    return doc


# ---------------------------------------------------------------- the readers and the arithmetic on made-up pages

def selftest(say=print):
    checks = []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))

    head = ["Precinct Results Report Official Results", "OFFICIAL BALLOT FOR ADAIR COUNTY", "11/5/2024", "Run Date 11/14/2024 Page {p}"]
    chs = "Choice Party Absentee Early Voting Election Day Voting Total"

    def page(p, label, n, body):
        return (p, [h.format(p=p) for h in head] + [f"{label} {n} ballots cast"] + body)

    pres = lambda d, r, o, und=0: ["PRESIDENT and VICE PRESIDENT of the UNITED STATES - (Vote for One)", chs,                 # noqa: E731
                                   f"Donald J. TRUMP REP 0 0.00% 0 0.00% {r} 90.00% {r} 90.00%", "J. D. VANCE",
                                   f"Kamala D. HARRIS DEM 0 0.00% 0 0.00% {d} 9.00% {d} 9.00%", "Tim WALZ",
                                   f"Some ONE (W) 0 0.00% 0 0.00% {o} 1.00% {o} 1.00%",
                                   f"Cast Votes: 0 0.00% 0 0.00% {d + r + o} 100.00% {d + r + o} 100.00%", f"Undervotes: 0 0 {und} {und}", "Overvotes: 0 0 0 0"]
    house = lambda n, a, b, und=0: [f"STATE REPRESENTATIVE {n}st Representative District - (Vote for One)", chs,               # noqa: E731
                                    f"Ann ALDER REP 0 0.00% 0 0.00% {a} 50.00% {a} 50.00%", f"Bo BIRCH DEM 0 0.00% 0 0.00% {b} 50.00% {b} 50.00%",
                                    f"Cast Votes: 0 0.00% 0 0.00% {a + b} 100.00% {a + b} 100.00%", f"Undervotes: 0 0 {und} {und}", "Overvotes: 0 0 0 0"]
    city = lambda k: ["CITY COUNCIL City of Testville - (Vote for up to Two)", chs, f"Cy CEDAR 0 0.00% 0 0.00% {k} 100.00% {k} 100.00%",  # noqa: E731
                      f"Cast Votes: 0 0.00% 0 0.00% {k} 100.00% {k} 100.00%", f"Undervotes: 0 0 {k} {k}", "Overvotes: 0 0 0 0"]
    pages = [page(1, "A101", 100, pres(9, 90, 1) + house(1, 60, 40)), page(2, "A101", 100, city(100)),
             page(3, "A102", 50, pres(20, 30, 0) + house(1, 30, 10, und=10)), page(4, "A102", 50, city(60) + ["*** End of report ***"])]
    rep = check_report(read_report_a(pages, "made-up A"), "made-up A")
    check("a report is read by its contests, a running mate joined to its row", (sorted(rep["precincts"]), rep["precincts"]["A101"]["contests"][
        "PRESIDENT and VICE PRESIDENT of the UNITED STATES - (Vote for One)"]["cands"][0][:3]), (["A101", "A102"], ["Donald J. TRUMP J. D. VANCE", 90, "REP"]))
    k = rep["precincts"]["A102"]["contests"]["CITY COUNCIL City of Testville - (Vote for up to Two)"]
    check("a city contest of two seats is whole only where its slots are twice the ballots", (whole(k, 50), whole(
        rep["precincts"]["A101"]["contests"]["CITY COUNCIL City of Testville - (Vote for up to Two)"], 100)), (False, True))
    check("a city's name and a ward are read from a title", (city_of("CITY COUNCIL City of Columbia - (Vote for up to Six)"),
                                                             city_of("MAYOR City of Walton (Unexpired Term) - (Vote for One)"),
                                                             city_of("CITY COUNCIL City of Hopkinsville 3rd Ward - (Vote for One)")),
          (("Columbia", None), ("Walton", None), ("Hopkinsville", 3)))
    check("a magisterial district is read from a title", (magisterial_of("MAGISTRATE 3rd Magisterial District - (Vote for One)"),
                                                           magisterial_of("CONSTABLE 7th Magisterial District (Unexpired Term) - (Vote for One)")), (3, 7))
    bpages = [(1, ["Precinct Summary Results Report OFFICIAL RESULTS", "KY Test 241105 General 6110", "November 5, 2024 Adair County", "A101 Courthouse",
                   "Statistics TOTAL", "Ballots Cast - Total 102", "PRESIDENT and VICE PRESIDENT of the UNITED STATES", "Vote For 1", "TOTAL",
                   "REP Donald J. TRUMP/J.D. VANCE 78", "DEM Kamala D. HARRIS/Tim WALZ 22", "IND Robert F. KENNEDY JR./Nicole 0", "SHANAHAN",
                   "Write-In Totals 1", "Not Assigned 1", "Total Votes Cast 101", "Contest Totals 102", "Precinct Summary - 01/23/2025 11:34 AM 1 of 1"])]
    rb = check_report(read_report_b(bpages, "made-up B"), "made-up B")
    cb = rb["precincts"]["A101 Courthouse"]["contests"]["PRESIDENT and VICE PRESIDENT of the UNITED STATES"]
    check("an Electionware report: party first, write-ins for no declared candidate left out, the contest total as the slots",
          ([x[:3] for x in cb["cands"]], cb["cast"], cb["unassigned"], cb["slots"]),
          ([["Donald J. TRUMP/J.D. VANCE", 78, "REP"], ["Kamala D. HARRIS/Tim WALZ", 22, "DEM"], ["Robert F. KENNEDY JR./Nicole SHANAHAN", 0, "IND"]],
           101, 1, 102))
    try:
        bad = [page(1, "A101", 100, pres(9, 90, 1)), page(3, "A102", 50, pres(20, 30, 0) + ["*** End of report ***"])]
        check_report(read_report_a(bad, "made-up gap"), "made-up gap")
        caught = False
    except Stop:
        caught = True
    check("a page missing from a report stops the loader", caught, True)
    # the arithmetic, on a made-up state of one county
    code = FIPS["adair"]
    contests = [dict(CONTESTS[0], table="President and Vice President of the United States")]
    table = [{"office": "President and Vice President of the United States", "district": None, "chamber": None, "unexpired": False, "parties": [],
              "rows": {code: [120, 29, 1]}, "total": [120, 29, 1]},
             {"office": "State Representative", "district": 1, "chamber": "house", "unexpired": False, "parties": [], "rows": {code: [90, 50]}, "total": [90, 50]}]
    rep["county"] = "Adair"
    st = {"KY-JC": {1: ["Adair"]}, "KY-JD": {1: ["Adair"]}, "KY-SC": {1: ["Adair"]}}
    cities = {(code, "testville"): "KY-M-00001", "_names": {"KY-M-00001": "Testville city"}, "_counties": {"KY-M-00001": [code]}, "_ambiguous": set()}
    doc, failed = build({2024: {code: rep}}, {2024: table}, {}, cities=cities, contests=contests, statutes=st, houses=1, senates=1, expect=False)
    p = doc["places"]
    check("a county adds up its precincts, write-ins with the others", (failed, p["county"][code]["votes"]["2024-president"]),
          ([], {"dem": 29, "rep": 120, "other": 1, "total": 150}))
    check("a House district of whole precincts is given", p["house"].get("1", {}).get("votes", {}).get("2024-president"), {"dem": 29, "rep": 120, "other": 1, "total": 150})
    check("a city one of whose precincts lies partly outside it is left out", sorted(p["mcd"]), [])
    check("a judicial district is whole counties", p["judicial"]["KY-JD1"]["votes"]["2024-president"]["total"], 150)
    table2 = [dict(table[0], rows={code: [121, 29, 1]}, total=[121, 29, 1]), table[1]]
    doc2, failed2 = build({2024: {code: rep}}, {2024: table2}, {}, cities=cities, contests=contests, statutes=st, houses=1, senates=1, expect=False)
    check("a county whose precincts differ from the Secretary's row is caught", bool(failed2), True)
    check("county codes follow the Census order", (FIPS["adair"], FIPS["mccracken"], FIPS["madison"], FIPS["woodford"], FIPS[bare("LaRue")], len(COUNTIES)),
          ("21001", "21145", "21151", "21239", "21123", 120))
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Kentucky place voted in past partisan general elections -> ballot/lean/ky_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/ky_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/ky_local)")
    ap.add_argument("--db", default=DB, help="the ballot database whose city ids are used and whose places are counted, opened read-only")
    ap.add_argument("--refresh", action="store_true", help="ask for every file again, even when the cached copies are there")
    ap.add_argument("--selftest", action="store_true", help="check the readers and the arithmetic on made-up pages; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
