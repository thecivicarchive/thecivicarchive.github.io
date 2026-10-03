"""
ballot/local_sites.py - what a state or local candidate's card may show beyond the list itself, each with its source
(John, 2026-10-01; Minnesota first): the campaign website, photo options and issue headings read from that website, and
the facts an open-web sweep found and a second reader confirmed. Everything lands in ballot_local_2026.sqlite, in tables
of its own; the list tables (sl_races, sl_candidates, sl_places) are only read.

    python -m ballot.local_sites scope       who the sweep should research: ballot/found_local/mn_scope.json, with
                                             mn_scope_counts.json and mn_scope_places.json beside it
    python -m ballot.local_sites files       campaign websites as filed with the Secretary of State -> sl_websites
    python -m ballot.local_sites found       verified findings in ballot/found_local/MN-*.json -> sl_websites, sl_found_facts
    python -m ballot.local_sites choices     ballot/photo_choice_local.json -> sl_photos
    python -m ballot.local_sites fetch       reads each candidate's website: photo options and issue headings (network)
                                             [--limit N] [--only "race|name;race|name"] [--again failed|all]
    python -m ballot.local_sites headings    applies the furniture rule again to the issue headings already stored
                                             (nothing is downloaded)
    python -m ballot.local_sites sheets      numbered contact sheets of the photo options nobody has looked at yet
    ... --db <file>                          works on another copy of ballot_local_2026.sqlite
    ... --state WI                           scope, found: another state (Minnesota when left out). Its files are
                                             <code>_scope*.json and <ST>-*.json, and its sheet for a person to read is
                                             REVIEW-<ST>.md; Minnesota's is REVIEW.md

Other states (Wisconsin first, 2026-10-02). Only Minnesota's candidate files carry a campaign website cell, so `files`
reads Minnesota alone. Any other state gets its websites from verified findings: `python run_ballot.py localfacts`
loads the findings of every state in STATES that has a scope file beside the findings (`found_states()`), after
Minnesota's, each state touching only its own rows. Fetch, headings, choices and sheets never were Minnesota's alone.
A new state is added to STATES with its name and the words its roster's legislative service is found by
(Iowa and North Dakota, 2026-10-02, also give "why_no_local": why the November list has no city or school race, said in
the scope files). South Dakota (2026-10-02) has a few city races in November and no school race: its "local_note" says
why in the scope files, its city races carry the Census place code as SD-M-<code> (`_place_code`), and its ticket for
Governor is written with "&" (`_first_named`). Ohio (2026-10-02) has no statewide list of county candidates and no
website cell; its "local_note" says why a city seat is on the list only for an unexpired term and that the county
rows are those of the boards read so far, and its legislative races, which carry no jurisdiction, are named by
district in the scope file. Michigan (2026-10-02) has no website cell either; its "local_note" says the city, village
and school rows are those of the nine county clerks' lists read so far, and its Court of Appeals races, which carry no
jurisdiction, are named by district in the scope file as its legislative races are. Missouri (2026-10-02) has no
website cell either; its "local_note" says its cities and schools vote in April and that the county rows are those of
the 13 election authorities read so far; its legislative races, whose jurisdiction is the state's own name, are named
by district in the scope file, and the City of St. Louis Board of Education is tied to the Census Bureau's row by name. Montana (2026-10-02) has no
website cell either; its "local_note" says the county rows are those of the nine county election offices read so far
and that its cities vote in odd years and its school trustees in May. Wyoming (2026-10-02) has no website cell either;
its "local_note" says the county, city and school rows are those of the 16 county clerks read so far (and Fremont's
school filings), and that judges are in the scope as the one name on a retention vote. Colorado (2026-10-02) has no
website cell either, and no county, city or school rows yet; its "why_no_local" says when those offices are elected
and that the scope is the Secretary of State's own list (statewide, the General Assembly and the judges' retention
votes), the Regional Transportation District's directors being a district board outside the rule. Kentucky (2026-10-03)
has no website cell either and no statewide race; its "local_note" says what its November ballot holds and which
contests the Secretary of State's list leaves unplaced, and its "place_codes" ties Louisville's consolidated city
(48003) to the Census Bureau's row for its balance (48006), the only part of it among the file's places. Utah
(2026-10-03) has no website cell either, and no county, city or school rows yet; its "why_no_local" says when those
offices are elected and that the scope is the Lieutenant Governor's certification (the State Board of Education, the
Legislature and the judges' retention votes, justice courts included). Arkansas (2026-10-03) has no website cell
either; its "local_note" says the county, city and school rows are those of Pulaski and Washington Counties so far.
Its ballot names carry filed titles ("State Representative Jane Doe"), kept as printed: its "titles" pattern lets
`_first_named` find the person behind the title for the family-name check and the issue-heading filter, and only for
a state that has such a pattern, so every other state's names are read exactly as before.

    python run_ballot.py localfacts          files, found and choices (nothing is downloaded)
    python run_ballot.py localfetch          fetch and sheets

Who may show what (John's order of 2026-10-01, which replaced the stricter rule for these offices)
------------------------------------------------------------------------------------------------
Statewide offices, the Legislature, judges, county offices, mayors and city councils, and school boards (`full()`) may
show a campaign website, a photo, a birth year, public offices held and issue headings, each with its source. Township
boards and the small district boards (soil and water, hospital, sanitary), and a city's clerk or treasurer, show only
what they filed, plus a campaign website if they listed one: nothing is fetched from their sites and no finding is
loaded for them.

Never, for anyone: home or mailing addresses, phone numbers, e-mail, family, marital status, religion, health,
ethnicity, income, employers, schools, legal troubles, or any description of a person's views or character; never a
social media profile as a source, a people-search site, a data broker or a voter file. Political lean is only the
record: a party's own published endorsement, an earlier run or office under a party label, and the candidate's own
words on their own campaign site. Nobody's politics is guessed or labelled here.

The Secretary of State's files
------------------------------
John saved the Secretary's candidate files into states_cache/mn_local/sos/20261103/ (their layouts are in the
docstring of ballot/state_local_mn.py). `file_websites()` reads the two November lists with that loader's own
`allowed_cells`: each line is cut, on the spot, to the cells that say whose line it is (name, office ID, office title,
county ID, MCD code, school district number) and the campaign website cell (cell 16 of both files), and the rest of the
line (residence and campaign addresses, cities, ZIP codes, phones, e-mail, a running mate's details) is dropped before
anything else sees it; nothing of a line is ever printed. A website cell that holds an e-mail address, a social media
profile, a link page or anything that is not a web address is not a campaign website: it is counted and not kept. A
line is tied to its race by the office ID and the exact name, and the place cells must agree with the race.

The tables (the contract the page builder reads)
------------------------------------------------
  sl_websites       race_id, name, url, source. source begins "Filed with" (the Secretary's list) or "Found on the open
                    web" (the sweep, with the sentence saying what ties the site to the race). A filed site is never
                    replaced by a found one.
  sl_found_facts    race_id, name, field, year, date, office, from_year, to_year, party, unit, what, quote, source, url,
                    kind, verified_on. One row per finding; the columns a field uses:
                      born           year, date (a full date only from an official or campaign page), source, url, kind
                      office         office, from_year, to_year (a year, 'now', or empty when the source does not say)
                      official_page  url, source: the candidate's page on a government's own site
                      endorsed_by    party, unit (the party body that endorsed), url: the party's own published page
                      past_party     what (the earlier run or office), year, party, source, url, kind
                      own_words      quote (300 characters at most), url: on the candidate's own campaign site
                    kind is official (a government's own page), campaign (the candidate's own site), secondary (Wikipedia
                    with a citation, or a named news organization) or party (a party's own page).
  sl_site_checks    race_id, name, url, checked, answered, status, final_url, names_candidate, options, topics: what
                    happened when the site was read, so a run can be picked up again and the page can leave out a dead
                    address. status is 'ok' or a few words saying why nothing was taken; final_url is where the address
                    led that day (a site filed without http or https is kept as https; when only http answered, this
                    says so).
  sl_photo_options  race_id, name, opt (a, b, c), url, site, webp: up to three pictures from the candidate's own site,
                    for a person to look at. None reaches a page by itself.
  sl_issues         race_id, name, url, topics (a JSON list of headings), fetched: the headings of the campaign's own
                    issues page, a few words each; nothing longer is copied and nothing is summarized.
  sl_photos         race_id, name, webp, credit, url: the option ballot/photo_choice_local.json picked
                    ({"race_id|name": {"pick": "a" | "b" | "c" | "none", "note": "..."}}), credited to the site.

The findings files, and what the loader will not take
-----------------------------------------------------
ballot/found_local/<ST>-<k>.json, written by the sweep and then marked by a second reader who re-opened every source:
  {"part": k, "of": n, "verified_on": "2026-10-02", "candidates": [{"race_id", "name",
    "website": {"url", "how"}, "official_page": {"url", "source"},
    "born": {"year", "date", "source", "url", "kind"}, "offices": [{"office", "from", "to", "source", "url", "kind"}],
    "endorsed_by": [{"party", "unit", "url"}], "past_party": [{"what", "year", "party", "source", "url", "kind"}],
    "own_words": {"quote", "url"}, "review": [{"shows", "problem", "url"}]}]}
with "verified": true on each finding the second reader confirmed. race_id and name are the scope file's, letter for
letter; on a ticket for Governor the findings are about the candidate for Governor. `load_found()` reads only verified
findings whose candidate is still on the November list and holds an office that may show them, and leaves out, with
a count: a finding with no page; one that cites a social media page, a link page, a people-search or family-records
site; a birth year that is not a whole number or a kind that is not one of the three; an endorsement cited from the
candidate's own site (the party must publish it); own words that are not on the candidate's own site (the filed one,
or the verified found one). It holds back for a person to read, in REVIEW.md beside the files and without repeating
the wording: text that reads like contact details or touches family, religion, health, money or legal matters, and a
quote over 300 characters. Review items and a found website that differs from the filed one go to REVIEW.md too.

Reading the websites
--------------------
`fetch()` uses ballot/campaign.py's own readers (the ones the Congress pages use): `photos` and `issues` run against a
small in-memory table of one person at a time and their results are copied here. Three courtesies are added around
campaign._fetch for the length of the run: a site's robots.txt is read first and obeyed, a page already read for this
candidate is not asked for twice, and requests to one host are at least a second apart. Always the kit's honest
User-Agent, one request at a time. A site that does not answer (a 403 or 429 to scripts included), shows a bot check
or a holding page (parked, for sale, suspended), asks scripts to stay out, leads to a social media page, or does not
name the candidate (in its address or on its home page) gives nothing, and the reason is kept in sl_site_checks, so a
page can leave such an address out; nothing is ever worked around, and a site is asked again only when someone runs
the step with --again. Nobody's likeness is recognised or matched: the options are
pictures the candidate's own site labels and publishes, and the choice is only which of them shows one person.

Official records stay first, as on the Congress pages. A candidate the list loader tied to a sitting member
(sl_candidates.state_member_id) has a record in state_<code>.sqlite: where that roster has the member's portrait no
photo options are taken from the campaign site (the page should use the roster's portrait), and a found birth year or
a found seat in the Legislature is held back where the roster gives one (listed in REVIEW.md beside the findings).

On John's network the home router answers a first address lookup for an unfamiliar name with "not found" and has the
answer seconds later, so the fetch asks for the next few sites' addresses while it reads the current one (`_tickle`);
a name still without an address after that is recorded as not found. An address lookup is not a request to the site.

Each step deletes and rewrites only its own rows, so it can be run again and gives the same result. The fetch saves
each site as it finishes and picks up where it stopped; about seven seconds a site.
"""

import argparse
import collections
import contextlib
import datetime as dt
import glob
import hashlib
import json
import math
import os
import re
import socket
import sqlite3
import sys
import time
import urllib.parse
import urllib.robotparser
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot import campaign  # noqa: E402
from ballot.check_local import EMAIL, PHONE, POBOX, ZIP  # noqa: E402
from ballot.common import fold, name_parts  # noqa: E402
from states import net  # noqa: E402

DB = os.path.join(HERE, "ballot_local_2026.sqlite")
FOUND_DIR = os.path.join(HERE, "ballot", "found_local")
CHOICE = os.path.join(HERE, "ballot", "photo_choice_local.json")
SHEETS = os.path.join(HERE, "ballot_cache", "campaign_local")
NOVEMBER = ("general", "open-primary")      # Louisiana's November 3 contest is an open primary
FILED = "Filed with"
MARK = "Found on the open web"
KINDS = ("official", "campaign", "secondary")
PER_PART = 30
QUOTE_MAX = 300
# the states this module serves: the name a reader would say, and (beyond the general words) how a finding names a
# seat in that state's legislature, so a sitting member's service is left to the state roster
STATES = {"MN": {"name": "Minnesota"},
          "WI": {"name": "Wisconsin", "legislature": r"\bwisconsin (?:state )?(?:senate|assembly|legislat\w+)|\b(?:state )?assembly\b"},
          # Iowa (2026-10-02): the Secretary of State's list stops at the Legislature and the county lists are the 99
          # auditors' own, none with a website cell this module reads; "why_no_local" is the sentence its scope files carry
          "IA": {"name": "Iowa", "legislature": r"\biowa (?:state )?(?:house|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "why_no_local": "Iowa elects its mayors, city councils and school boards in November of odd years (Iowa Code 376.1 and 277.1; "
                                 "last on November 4, 2025, next in 2027)."},
          # North Dakota (2026-10-02): the Secretary of State's list (vip.sos.nd.gov) has contact columns the list loader
          # never reads and this module does not read either, so its websites come from verified findings only
          "ND": {"name": "North Dakota", "legislature": r"\bnorth dakota (?:state )?(?:house|senate|legislat\w+)|\blegislative assembly\b",
                 "why_no_local": "North Dakota elects its city officers and park boards in June of even years (N.D.C.C. 40-21-02; "
                                 "June 9, 2026) and its school boards between April and June (N.D.C.C. 15.1-09-22); townships vote in March."},
          # South Dakota (2026-10-02): the Secretary of State's list (vip.sdsos.gov) has mailing address columns the list
          # loader never reads and no website cell, so its websites come from verified findings only. "local_note" is the
          # sentence its scope files carry about the city and school races that are not on the November list
          "SD": {"name": "South Dakota", "legislature": r"\bsouth dakota (?:state )?(?:house|senate|legislat\w+)",
                 "local_note": "South Dakota's cities and school boards choose between a June and a November election (SDCL 9-13-1 and "
                               "13-7-10): most cities and every school board found voted on June 2, 2026, so the Secretary of State's "
                               "November 3, 2026 list carries the councils of ten cities and no school board. Townships elect at their "
                               "annual meeting in March (SDCL 8-3-1). A local candidate with no opponent is elected without being printed "
                               "on the ballot (SDCL 12-16-1.1) and is on the list all the same."},
          # Ohio (2026-10-02): no statewide list of county candidates and no website cell anywhere (each county board's own
          # list or 46-day notice is read by ballot/state_local_oh.py), so its websites come from verified findings only.
          # Its legislative races carry no jurisdiction, so the scope names the district (`scope`)
          "OH": {"name": "Ohio", "legislature": r"\bohio (?:state )?(?:house|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "local_note": "Ohio elects its mayors, city and village councils, township officers, boards of education and municipal "
                               "court judges in November of odd-numbered years (R.C. 3501.02; next in 2027), so the November 3, 2026 lists "
                               "carry a city or school seat only to finish an unexpired term. Ohio has no statewide list of county "
                               "candidates: the county offices and common pleas judges here are those of the county boards of elections "
                               "read so far, and the other counties' are not loaded yet."},
          # Michigan (2026-10-02): the Bureau of Elections' listing has no contact columns and no website cell, and the county
          # clerks' lists have address columns the list loader never reads and this module does not read either, so its
          # websites come from verified findings only. Its legislative and Court of Appeals races carry no jurisdiction,
          # so the scope names the district (`scope`); its ticket for Governor is written with "/"
          # "school_names": districts the state's list (CEPI) and the Census Bureau name too differently for the spelling
          # rule, read side by side on 2026-10-02 (CEPI adds the county in brackets where a name repeats, and writes
          # "School District of the City of X" where the Bureau writes "X City School District"). Madison District Public
          # Schools (MI-S-63140) is left out: the Bureau has two Madisons and neither name settles which is Oakland County's
          "MI": {"name": "Michigan", "legislature": r"\bmichigan (?:state )?(?:house|senate|legislat\w+)|\bhouse of representatives\b",
                 "school_names": {"MI-S-33130": "Mason Public Schools", "MI-S-50120": "Lake Shore Public Schools",
                                  "MI-S-50130": "Lakeview Public Schools", "MI-S-59090": "Lakeview Community Schools",
                                  "MI-S-61010": "Muskegon City School District", "MI-S-63010": "Birmingham City School District",
                                  "MI-S-63040": "Royal Oak City School District", "MI-S-63130": "Hazel Park City School District",
                                  "MI-S-63180": "Brandon School District", "MI-S-63250": "Oak Park City School District",
                                  "MI-S-63270": "Clawson City School District", "MI-S-73010": "Saginaw City School District",
                                  "MI-S-82045": "Melvindale-North Allen Park School District", "MI-S-82060": "Hamtramck Public Schools",
                                  "MI-S-82090": "Lincoln Park Public Schools", "MI-S-82110": "Redford Union School District",
                                  "MI-S-82120": "River Rouge School District", "MI-S-82170": "Wyandotte City School District",
                                  "MI-S-82320": "Harper Woods City Schools"},
                 "local_note": "Michigan has no statewide list of local candidates: the city, village and school board races here are those "
                               "on the November 3, 2026 lists of the nine county clerks read so far (Wayne, Oakland, Macomb, Kent, Ottawa, "
                               "Ingham, Kalamazoo, Saginaw and Muskegon), and the other counties' are not loaded yet. Every school district "
                               "elects board members in November of even years (MCL 168.642c); most cities elect in November of odd years, "
                               "so only villages and the cities whose charters say so are on this list. County officers, county "
                               "commissioners and township boards were elected for four years in 2024 (MCL 168.200, 46.410, 168.358), so "
                               "the county rows are the two county executives and seats filled for the rest of a term. Township offices, "
                               "community college trustees, library boards, village presidents and a city's clerk, treasurer or assessor "
                               "are outside the scope's rule and are not in it."},
          # Missouri (2026-10-02): the Secretary of State's certification has no contact columns and no website cell, and the
          # election authorities' notices and sample ballots have none this module reads, so its websites come from verified
          # findings only. Its legislative races give "Missouri" as their jurisdiction, so the scope names the district
          # (`scope`). "school_names": the City of St. Louis Board of Education governs the district the Census Bureau
          # names "St. Louis City School District" (read side by side on 2026-10-02)
          "MO": {"name": "Missouri", "legislature": r"\bmissouri (?:state )?(?:house|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "school_names": {"MO-S-510-city-of-st-louis-board-of-education": "St. Louis City School District"},
                 "local_note": "Missouri's cities, school districts and special districts elect their officers on the general municipal "
                               "election day in April (RSMo 115.121; April 7, 2026), so the November 3, 2026 lists carry a city or school "
                               "seat only where a charter or a vacancy puts one there. Missouri has no statewide list of county "
                               "candidates: the county offices and the associate circuit judges elected by party here are those on the "
                               "lists of the 13 election authorities read so far, and the other counties' are not loaded yet. In six "
                               "judicial circuits, and for the appellate courts, voters answer Yes or No on keeping each judge: those "
                               "judges are in the scope as the one name on a retention vote."},
          # Nebraska (2026-10-02): the Secretary of State's filing list has contact columns the list loader never reads and
          # this module does not read either, and the county election offices' notices have no website cell, so its
          # websites come from verified findings only. One chamber: its legislative races give "Nebraska" as their
          # jurisdiction, and the scope names each "Legislative District N" ("district_words"). City races carry the
          # Census place code as NE-M-<code>. 70 of its 73 school districts carry the Census Bureau's own names; the three
          # the county notices name differently (Lawrence-Nelson, Sandy Creek, Exeter-Milligan-Friend) are small rural
          # districts and stay without a figure, so "school_names" is empty
          "NE": {"name": "Nebraska", "legislature": r"\bnebraska (?:state )?(?:legislat\w+|senate|unicameral)|\bunicameral\b",
                 "district_words": "Legislative District",
                 "school_names": {},
                 "local_note": "Nebraska has no statewide list of county, city or school candidates: the county offices, mayors, city "
                               "councils, village boards and school boards here are those on the notices of election and sample ballots "
                               "of the 10 county election offices read so far (Adams, Buffalo, Cherry, Douglas, Lancaster, Madison, "
                               "Phelps, Sarpy, Washington and York), and the other 83 counties' are not loaded yet. Omaha and Lincoln "
                               "elect their city officers, and Lincoln its school board, in the spring of odd-numbered years (Neb. Rev. "
                               "Stat. 14-201, 15-301 and 32-544), so they are not on this ballot. Judges are in the scope as the one name "
                               "on a yes-or-no retention vote. The Board of Regents, the State Board of Education and the Public Service "
                               "Commission are elected by district and are in the scope with the statewide offices. Township boards and "
                               "the boards of natural resources, public power, reclamation, community college, educational service "
                               "unit and other districts are outside the scope's rule and are not in it."},
          # Montana (2026-10-02): the Secretary of State's candidate grid has contact columns the list loader never reads
          # and this module does not read either, and the county election offices' sample ballots and candidate lists
          # have no website cell this module reads, so its websites come from verified findings only. Its legislative,
          # court and Public Service Commission races carry their own district as the jurisdiction, so the scope needs no
          # district words; city races carry the Census place code as MT-M-<code>. No school race is on the list
          "MT": {"name": "Montana", "legislature": r"\bmontana (?:state )?(?:house|senate|legislat\w+)|\bhouse of representatives\b",
                 "school_names": {},
                 "local_note": "Montana has no statewide list of county candidates before Election Day: the county offices and justices "
                               "of the peace here are those on the sample ballots and candidate lists of the 9 county election offices "
                               "read so far (Beaverhead, Carbon, Cascade, Fergus, Flathead, Gallatin, Madison, Richland and Sanders), and "
                               "the other 47 counties' are not loaded yet. Cities and towns elect their officers in November of "
                               "odd-numbered years (MCA 13-1-104) and school trustees on the school election day in May (MCA 20-20-105), "
                               "so the November 3, 2026 lists carry a city seat only where a special election was called (three council "
                               "seats in Red Lodge, a city under the scope's 10,000) and no school board. The two Public Service "
                               "Commission seats are elected by district and are in the scope with the statewide offices; a judge "
                               "nobody filed against is the one name in the race, on a yes-or-no retention vote (MCA 13-14-212). Conservation district supervisors are "
                               "outside the scope's rule and are not in it."},
          # Wyoming (2026-10-02): the Secretary of State's candidate file has contact columns the list loader never reads
          # and this module does not read either, and the county clerks' sample ballots and rosters have no website cell
          # this module reads, so its websites come from verified findings only. Its legislative races carry "Senate
          # District N" or "House District N" as their jurisdiction and its district and circuit court retention votes
          # the judicial district, so the scope needs no district words; city and town races carry the Census place code
          # as WY-M-<code>, and school districts the Census Bureau's own names once "#" is set aside. Wyoming elects no
          # Lieutenant Governor, so a candidate for Governor runs alone ("no_ticket": the scope says nothing of a ticket)
          "WY": {"name": "Wyoming", "legislature": r"\bwyoming (?:state )?(?:house|senate|legislat\w+)|\bhouse of representatives\b",
                 "no_ticket": True, "school_names": {},
                 "local_note": "Wyoming has no statewide list of county, city or school candidates: the county offices, mayors, city and "
                               "town councils and school boards here are those on the sample ballots and candidate rosters of the 16 "
                               "county clerks read so far (Albany, Big Horn, Carbon, Converse, Crook, Goshen, Hot Springs, Johnson, "
                               "Laramie, Natrona, Park, Platte, Sublette, Sweetwater, Teton and Uinta), with Fremont County's list of "
                               "school and special district filings, and the other counties' are not loaded yet (Campbell and Sheridan "
                               "among them, so Gillette and Sheridan are not in the scope). A town that has chosen by charter ordinance to "
                               "vote in May (W.S. 22-23-202) is not on this ballot. Judges do not run against anyone: each is in the "
                               "scope as the one name on a yes-or-no retention vote. Community college trustees, conservation district "
                               "supervisors and the boards of hospital, fire, cemetery and other special districts are outside the "
                               "scope's rule and are not in it."},
          # Colorado (2026-10-02): the Secretary of State's Official Candidate List has no contact columns and no website
          # cell, so its websites come from verified findings only. Its legislative races carry "House District N" or
          # "Senate District N" as their jurisdiction and its retention votes the judicial district or the county, so the
          # scope needs no district words. The list loader has no county, city or school rows yet (the county clerks'
          # own lists are its 64 county gaps), so "why_no_local" says why the scope stops at the state's own list. Its
          # Governor's race is a ticket, but the list names the candidate for Governor alone
          "CO": {"name": "Colorado", "legislature": r"\bcolorado (?:state )?(?:house|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "school_names": {},
                 "why_no_local": "Colorado elects its school boards in November of odd-numbered years (C.R.S. 22-31-104; next in 2027); "
                                 "its towns regularly vote in April of even-numbered years and its cities in November of odd-numbered "
                                 "years (C.R.S. 31-10-109), unless a town's or city's voters have moved the election to November of "
                                 "even-numbered years. The county offices, and the town and city contests that do share this ballot, "
                                 "are on each county clerk and recorder's own list, and no county's list is loaded yet, so the scope "
                                 "is the Secretary of State's list: the statewide offices, the Regents and the State Board of "
                                 "Education (elected by district), the General Assembly, and the judges on a yes-or-no retention vote, "
                                 "each the one name in the race. The Regional Transportation District's directors (10 candidates) are "
                                 "a district board, outside the scope's rule, and are not in it."},
          # Kentucky (2026-10-03): the Secretary of State's "Candidate Filings with the County Clerk" list has contact
          # columns the list loader never reads and this module does not read either, and no website cell, so its
          # websites come from verified findings only. Its legislative races carry "Senate District N" or "House District
          # N" and its court races their own district or circuit as the jurisdiction, so the scope needs no district
          # words; city races carry the Census place code as KY-M-<code>, and school districts the Census Bureau's own
          # names. "place_codes": a race's place code the Bureau's file of places does not carry, and the row read in its
          # stead: Louisville/Jefferson County Metro Government is a consolidated city (48003), and the file's places
          # hold only its balance (48006), the county outside its other incorporated cities, read side by side 2026-10-03
          "KY": {"name": "Kentucky", "legislature": r"\bkentucky (?:state )?(?:house|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "school_names": {}, "place_codes": {"KY-M-48003": "48006"},
                 "local_note": "Kentucky elects no statewide officer in 2026 (the Governor and the other statewide officers are elected in "
                               "2027). On November 3, 2026 it elects every county's officers (judge/executive, magistrates or "
                               "commissioners, county clerk, county attorney, sheriff, jailer, coroner, surveyor, property valuation "
                               "administrator and constables), its district judges, every city council and commission, the mayors and "
                               "school board members whose four-year terms are ending, and soil and water conservation district "
                               "supervisors (Kentucky State Board of Elections, Kentucky Election Schedule 2026-2036). Circuit judges, "
                               "circuit court clerks and Commonwealth's attorneys are elected in 2030, so the few such seats on this "
                               "ballot are filled for the time left until then. The county, city and school rows are those of the "
                               "Secretary of State's list of candidates filed with the county clerks, which covers all 120 counties; "
                               "where it files a candidate without naming the city or school district, the contest is not loaded "
                               "(Owensboro's and Versailles's city races among them, so those cities are not in the scope), and in "
                               "thirty-five contests where it still shows the May primary's field no name is loaded. Louisville's "
                               "population figure is the Census Bureau's row for the Metro Government's balance, the county outside "
                               "its other incorporated cities. Soil and water conservation district supervisors are outside the "
                               "scope's rule and are not in it."},
          # Oklahoma (2026-10-03): the State Election Board's November list and Candidate List Book have no contact columns
          # and no website cell, so its websites come from verified findings only. Its legislative races give "Oklahoma" as
          # their jurisdiction, so the scope names the district (`scope`); its court races carry the judicial district or
          # the county, city races the Census place code as OK-M-<code>. Oklahoma elects its Lieutenant Governor
          # separately, so a candidate for Governor runs alone ("no_ticket"). No school race is on the list
          "OK": {"name": "Oklahoma", "legislature": r"\boklahoma (?:state )?(?:house(?: of representatives)?|senate|legislat\w+)",
                 "no_ticket": True, "school_names": {},
                 "local_note": "Oklahoma prints only contested races on its ballot (26 O.S. 6-102). A statewide or legislative candidate "
                               "left alone once filing, withdrawals and contests closed is elected without being printed, and is in "
                               "the scope all the same (from the State Election Board's Candidate List Book); county, city and judicial "
                               "offices come from the Board's November 3, 2026 list, which prints contested races only, so a county "
                               "officer with no opponent, or one settled in the June 16 primary or the August 25 runoff, is not loaded "
                               "and is not in it. Every county elects its assessor, its treasurer and its commissioners for Districts 1 "
                               "and 3 this year (19 O.S. 131); the county clerk, court clerk, sheriff and District 2 commissioner in "
                               "2028, so the one sheriff's race here fills the rest of a term. Most cities and towns elect in April of "
                               "odd-numbered years (11 O.S. 16-103) and school boards were elected on February 10 and April 7, 2026, "
                               "so the November list carries the contests of six cities (Bartlesville, Clinton, El Reno, Lawton, Tulsa "
                               "and Yukon; Clinton, of about 8,400 people, is under the scope's 10,000) and no school board. The appellate judges' yes-or-no retention votes are printed on the list "
                               "without the judges' names and are not loaded. Fire protection district boards are outside the scope's "
                               "rule and are not in it."},
          # Utah (2026-10-03): the Lieutenant Governor's General Election Certification (a signed scan with a text layer)
          # and the Master Ballot Position List have no contact columns and no website cell, so its websites come from
          # verified findings only. Its legislative races carry "House District N" or "Senate District N", the State Board
          # of Education races their own district, and its retention votes the court's district, city or county, so the
          # scope needs no district words. No county, city or school rows are loaded (each county clerk certifies those),
          # so "why_no_local" says why the scope stops at the state's own list. No race for Governor is on the 2026 ballot
          "UT": {"name": "Utah", "legislature": r"\butah (?:state )?(?:house(?: of representatives)?|senate|legislat\w+)",
                 "school_names": {},
                 "why_no_local": "Utah elects its city and town officers in November of odd-numbered years (Utah Code 20A-1-202; next "
                                 "in 2027) and has no township governments. Its county officers and about half of each local school "
                                 "board are elected on November 3, 2026 (Utah Code 17-66-202 and 20A-14-202), but each county clerk "
                                 "certifies and posts those candidates for the county alone (Utah Code 20A-5a-210), and no county's "
                                 "list is loaded yet, so the scope is the Lieutenant Governor's General Election Certification: the "
                                 "State Board of Education (elected by district, with the statewide offices), the Legislature, and the "
                                 "judges on a yes-or-no retention vote, each the one name in the race, the justice court judges of "
                                 "cities and counties among them."},
          # Arkansas (2026-10-03): the Secretary of State's Candidate Search, Pulaski County's ballot position draw and
          # Washington County's candidate list give no website cell this module reads (Washington County's contact
          # columns are never read by the list loader), so its websites come from verified findings only. Its legislative
          # races give "Arkansas" as their jurisdiction, so the scope names the district (`scope`); its court races carry
          # the judicial district, city races the Census place code as AR-M-<code>. Arkansas elects its Lieutenant
          # Governor separately, so a candidate for Governor runs alone ("no_ticket"). Names are kept as filed for the
          # ballot, and many carry a title ("State Representative", "Mayor", "Councilman"): "titles" is the pattern of
          # those words, set aside where the module needs the person (the family name a site must show, and the given
          # name an issue heading must not use); the name itself is never changed. A bare "Justice" is not in it, since
          # it is also a given name. "school_names": the Washington County list writes the Elkins district with its
          # number ("Elkins School District #10"), which the Census Bureau's row does not carry
          "AR": {"name": "Arkansas", "legislature": r"\barkansas (?:state )?(?:house(?: of representatives)?|senate|legislat\w+|general assembly)|\bgeneral assembly\b",
                 "no_ticket": True,
                 "titles": r"^(?:(?:state )?(?:senator|representative|treasurer)|rep\.|sen\.|governor|lieutenant governor|attorney general|"
                           r"auditor of state|secretary of state|commissioner of state lands|justice of the peace|council ?(?:member|man|woman)|"
                           r"alderman|alderwoman|director|mayor|sheriff|constable|coroner|assessor|(?:county |circuit )?(?:clerk|judge|collector)|"
                           r"county treasurer|prosecuting attorney)\s+",
                 "school_names": {"AR-S-143-elkins-school-district-10": "Elkins School District"},
                 "local_note": "Arkansas has no statewide list of county, city or school candidates: those file with each county, and the "
                               "county, city and school rows here are those of the two county election commissions read so far, Pulaski "
                               "County's ballot position draw (contested contests only, so an office with one candidate there is not "
                               "loaded) and Washington County's candidate list (its unopposed candidates included); the other 73 "
                               "counties' are not loaded yet. School boards were elected at the annual school election on March 3, 2026, "
                               "and circuit judges and prosecuting attorneys at the nonpartisan general election the same day, so only "
                               "their runoffs are on the November ballot. Names are as filed for the ballot, and many carry a title "
                               "(State Representative, Mayor, Councilman): the scope keeps each name as printed, and a finding is about "
                               "the person named after the title. City offices are nonpartisan. City clerks, treasurers and attorneys, "
                               "and the Beaver Water District's directors, are outside the scope's rule and are not in it."}}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_websites (race_id TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL, source TEXT, PRIMARY KEY (race_id, name));
CREATE TABLE IF NOT EXISTS sl_found_facts (race_id TEXT NOT NULL, name TEXT NOT NULL, field TEXT NOT NULL, year INTEGER, date TEXT, office TEXT,
  from_year INTEGER, to_year, party TEXT, unit TEXT, what TEXT, quote TEXT, source TEXT, url TEXT, kind TEXT, verified_on TEXT);
CREATE INDEX IF NOT EXISTS idx_sl_found_facts ON sl_found_facts (race_id, name);
CREATE TABLE IF NOT EXISTS sl_site_checks (race_id TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL, checked TEXT, answered INTEGER NOT NULL DEFAULT 0,
  status TEXT, final_url TEXT, names_candidate INTEGER, options INTEGER NOT NULL DEFAULT 0, topics INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (race_id, name));
CREATE TABLE IF NOT EXISTS sl_photo_options (race_id TEXT NOT NULL, name TEXT NOT NULL, opt TEXT NOT NULL, url TEXT, site TEXT, webp BLOB,
  PRIMARY KEY (race_id, name, opt));
CREATE TABLE IF NOT EXISTS sl_issues (race_id TEXT NOT NULL, name TEXT NOT NULL, url TEXT, topics TEXT, fetched TEXT, PRIMARY KEY (race_id, name));
CREATE TABLE IF NOT EXISTS sl_photos (race_id TEXT NOT NULL, name TEXT NOT NULL, webp BLOB, credit TEXT, url TEXT, PRIMARY KEY (race_id, name));
"""

# ---------------------------------------------------------------- who may show what

FULL_LEVELS = {"statewide", "legislature", "court", "county", "school"}
FULL_CITY = {"mayor", "council"}


def full(level, office_kind):
    """True for the offices whose candidates may show a photo, a birth year, offices held and issue headings (statewide
    offices, the Legislature, judges, county offices, mayors and city councils, school boards). Everyone else shows what
    they filed and, if they listed one, a campaign website."""
    return level in FULL_LEVELS or (level == "city" and office_kind in FULL_CITY)


def connect(path=DB):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def _races(con, state=None):
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special"]
    sql = f"SELECT {', '.join(cols)} FROM sl_races" + (" WHERE state = ?" if state else "")
    return {r[0]: dict(zip(cols, r)) for r in con.execute(sql, (state,) if state else ())}


def _november(con, state=None):
    """{(race_id, name): state member id or None} for the candidates on the November lists."""
    sql = (f"SELECT c.race_id, c.name, c.state_member_id FROM sl_candidates c JOIN sl_races r USING (race_id) "
           f"WHERE c.election IN ({','.join('?' * len(NOVEMBER))})" + (" AND r.state = ?" if state else ""))
    return {(r, n): m for r, n, m in con.execute(sql, NOVEMBER + ((state,) if state else ()))}


def _first_named(name, office_kind, state=None):
    """The person a site or a finding is about: on a ticket for Governor and Lieutenant Governor, the one named first;
    in a state whose names carry a filed title (Arkansas: "State Representative Jane Doe"), the name after the title."""
    who = re.split(r"\s+and\s+|\s+/\s+|\s+&\s+", name)[0] if office_kind == "governor" else name
    titles = STATES.get(state or "", {}).get("titles")
    if titles:
        bare = re.sub(titles, "", who, count=1, flags=re.I).strip()
        who = bare if len(bare.split()) >= 2 else who      # never cut a name down to one word
    return who


def _family(name):
    parts = name_parts(name)[1].split()
    return parts[-1] if parts else ""


# ---------------------------------------------------------------- web addresses

# social networks, and the link pages and shorteners that only pass a reader on to them
SOCIAL = {"facebook.com", "fb.com", "fb.me", "messenger.com", "instagram.com", "twitter.com", "x.com", "t.co", "tiktok.com", "youtube.com",
          "youtu.be", "linkedin.com", "lnkd.in", "threads.net", "threads.com", "bsky.app", "nextdoor.com", "snapchat.com", "pinterest.com",
          "reddit.com", "truthsocial.com", "rumble.com", "tumblr.com", "whatsapp.com", "wa.me", "t.me", "discord.gg", "discord.com",
          "mastodon.social", "gettr.com", "parler.com", "twitch.tv", "vimeo.com"}
LINK_PAGES = {"linktr.ee", "linkin.bio", "beacons.ai", "campsite.bio", "bio.site", "lnk.bio", "flow.page", "tinyurl.com", "bit.ly", "goo.gl",
              "ow.ly", "rb.gy", "tiny.cc", "is.gd", "buff.ly", "shorturl.at", "cutt.ly", "forms.gle", "g.co"}
# never a source: people-search sites, data brokers, voter-file and family-record sites
BROKERS = {"spokeo.com", "whitepages.com", "beenverified.com", "truepeoplesearch.com", "fastpeoplesearch.com", "radaris.com", "mylife.com",
           "intelius.com", "peoplefinders.com", "instantcheckmate.com", "truthfinder.com", "zabasearch.com", "usphonebook.com", "nuwber.com",
           "clustrmaps.com", "voterrecords.com", "peekyou.com", "pipl.com", "thatsthem.com", "anywho.com", "411.com", "addresses.com",
           "ancestry.com", "familysearch.org", "legacy.com", "findagrave.com", "myheritage.com", "rocketreach.co", "zoominfo.com",
           "signalhire.com", "contactout.com", "apollo.io", "lead411.com", "officialusa.com", "peoplelooker.com", "ussearch.com",
           "cyberbackgroundchecks.com", "searchpeoplefree.com", "smartbackgroundchecks.com", "publicrecordsnow.com", "voterly.com"}
# a mail provider's own address, or an e-mail address typed without its @ (name + gmail.com run together)
MAIL_HOSTS = re.compile(r"^(?:gmail|googlemail|yahoo|ymail|hotmail|outlook|live|icloud|me|protonmail|proton|aol|msn|comcast|charter|frontiernet|"
                        r"centurylink|q|mchsi|arvig|paulbunyan|gvtel|hickorytech|midco)\.(?:com|net|me)$|"
                        r"(?:gmail|googlemail|yahoo|hotmail|icloud|protonmail)\.(?:com|net)$", re.I)
WEBLIKE = re.compile(r"^(?:https?://)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?::\d{2,5})?(?:[/?#]\S*)?$", re.I)
SHARED_HOSTS = {"sites.google.com"}      # one host, many people's sites: the path says whose it is


def _host(url):
    return re.sub(r"^(?:www|m|mobile)\.", "", urllib.parse.urlsplit(url).netloc.lower().split("@")[-1].split(":")[0])


def _registrable(host):
    return ".".join(host.split(".")[-2:])


def social(host):
    return _registrable(host) in SOCIAL


def site_cell(cell):
    """What a website cell holds: ('web', the address, tidied) for a web address; ('email', None) for an e-mail address,
    whole or mangled; ('social', None) for a social media profile or handle; ('link', None) for a link page or a
    shortened link, which hides where it leads; ('other', None) for anything else; ('', None) for an empty cell.
    Only the 'web' kind is ever kept or shown."""
    t = (cell or "").strip().strip("<>\"'").rstrip(".,;")
    if not t:
        return "", None
    if t.startswith("@"):
        return "social", None
    head = re.sub(r"(?i)^https?://", "", t).split("/", 1)[0]
    if "@" in head:
        return "email", None
    if not WEBLIKE.match(t):
        return "other", None
    p = urllib.parse.urlsplit(t if re.match(r"(?i)^https?://", t) else "https://" + t)
    host = p.netloc.lower()
    bare = _host("//" + host)
    if MAIL_HOSTS.search(_registrable(bare)):
        return "email", None
    if social(bare):
        return "social", None
    if _registrable(bare) in LINK_PAGES or (_registrable(bare) == "google.com" and bare not in SHARED_HOSTS):
        return "link", None
    path = "" if p.path in ("", "/") else p.path
    return "web", urllib.parse.urlunsplit((p.scheme.lower(), host, path, p.query, ""))


def same_site(site, url):
    """True when `url` is a page of the site at `site`: the same host and, on a host many people share, the same
    first two parts of the path."""
    if not site or not url or _host(site) != _host(url):
        return False
    if _host(site) in SHARED_HOSTS:
        a = [x for x in urllib.parse.urlsplit(site).path.split("/") if x][:2]
        b = [x for x in urllib.parse.urlsplit(url).path.split("/") if x][:2]
        return bool(a) and a == b
    return True


def _web(url):
    url = (url or "").strip() if isinstance(url, str) else ""
    return url if re.match(r"(?i)^https?://[^\s/]+\.[^\s/]+", url) else None


def _rel(path):
    """A path as a reader of the log would say it: from the kit's folder when it is inside it."""
    path = os.path.abspath(path)
    try:
        inside = os.path.commonpath([path, HERE]) == HERE
    except ValueError:      # another drive
        inside = False
    return os.path.relpath(path, HERE) if inside else path


def _line(text):
    return re.sub(r"\s+", " ", str(text or "")).replace("|", "/").strip()


# ---------------------------------------------------------------- 1. the websites the candidates filed (Minnesota)

MN_FILES = (
    ("mn-sos-2026-general-statecounty", "*Candidates in the General Election - Federal, State, and County Offices*", 21,
     {"name": 1, "office_id": 2, "title": 3, "county": 4, "site": 16},
     "Campaign websites as filed: Candidates in the General Election: Federal, State, and County Offices (November 3, 2026)"),
    ("mn-sos-2026-general-local", "*Candidates in the General Election - Local Offices*", 18,
     {"name": 1, "office_id": 2, "title": 3, "county": 4, "mcd": 5, "sd": 6, "site": 16},
     "Campaign websites as filed: Candidates in the General Election: Local Offices (November 3, 2026)"))
MN_FILED = f"{FILED} the Minnesota Secretary of State: the campaign website on the candidate list for the November 3, 2026 general election"
NOT_KEPT = {"email": "e-mail addresses", "social": "social media profiles", "link": "link pages or shortened links", "other": "not web addresses"}
# the two list sources' notes said websites were never read; that changed on 2026-10-01 (see ballot/state_local_mn.py)
OLD_NOTES = (("phones, websites, e-mail and running mates' contact details are never read.",
              "phones, e-mail and running mates' contact details are never read; the campaign website a candidate listed is read apart."),
             ("phones, websites and e-mail are never read.",
              "phones and e-mail are never read; the campaign website a candidate listed is read apart."))


def file_websites(con, say=print):
    """Minnesota: the campaign website cell of the Secretary of State's two November candidate lists -> sl_websites, for
    every candidate who listed one, townships included. Returns the counts."""
    from ballot import state_local_mn as mn
    con.executescript(SCHEMA)
    races = _races(con, "MN")
    november = _november(con, "MN")
    by = collections.defaultdict(list)
    for (rid, name) in november:
        by[(rid.split("-")[2], name)].append(rid)

    def place(r, name):
        """The race this line is: the office ID and the exact name, with the place cells agreeing."""
        special = bool(re.match(r"^Special Election for ", r["title"], re.I))
        fips = None if r["county"] == "88" else f"{2 * int(r['county']) - 1:03d}"
        sd, mcd = r.get("sd") or "", r.get("mcd") or ""

        def agrees(x):
            return (bool(x["special"]) == special and (not sd or x["jurisdiction_id"] in ("ISD" + sd, "SSD" + sd))
                    and (fips is None or not x["county_ids"] or fips in json.loads(x["county_ids"])))
        cand = [c for c in by.get((r["office_id"], name), []) if agrees(races[c])]
        if len(cand) > 1 and mcd:
            cand = [c for c in cand if races[c]["jurisdiction_id"] == mcd or mcd in c.split("-")] or cand
        return cand[0] if len(cand) == 1 else None

    rows, seen, unplaced = {}, collections.Counter(), []
    not_kept, per_file, sources = collections.Counter(), {}, []
    for source_id, pattern, width, keep, title in MN_FILES:
        path = mn._file(pattern)
        lines = kept = filled = odd = 0
        for n, r in mn.allowed_cells(path, width, keep):
            mn._check(re.fullmatch(r"\d{4}", r["office_id"]), path, n, "office ID is four digits")
            mn._check(r["county"].isdigit() and 1 <= int(r["county"]) <= 88, path, n, "county ID is 1-88")
            mn._check(not r.get("mcd") or re.fullmatch(r"\d{5}", r["mcd"]), path, n, "MCD FIPS is empty or five digits")
            mn._check(not r.get("sd") or re.fullmatch(r"\d{4}", r["sd"]), path, n, "school district number is empty or four digits")
            mn._check(bool(r["name"]) and bool(r["title"]), path, n, "name and office title present")
            kind, url = site_cell(r.pop("site"))
            filled += bool(kind)
            odd += kind == "other"
            if mn.is_congress(r["title"]):      # U.S. Senator and U.S. Representative are the federal pages' rows
                continue
            lines += 1
            name = mn.clean_name(r["name"])
            rid = place(r, name)
            if not rid:
                unplaced.append(f"{os.path.basename(path)[:40]}... line {n}")
                continue
            seen[(rid, name)] += 1
            if kind == "web":
                rows[(rid, name)] = url
                kept += 1
            elif kind:
                not_kept[kind] += 1
        if filled >= 20 and odd > 0.1 * filled:      # a shifted layout would put cities or phones in this cell
            raise mn.LayoutError(f"    {os.path.basename(path)}: cell 16 does not read as the campaign website cell "
                                 f"({odd} of {filled} filled cells are not web addresses); stopping (no line is printed)")
        per_file[source_id] = (lines, kept)
        sources.append((source_id + "-websites", "MN", "official candidate list", "Minnesota Secretary of State", title, mn.CANDIDATE_SITE, "",
                        mn._day(path), mn._sha(path), kept,
                        "The campaign website cell of the same file, read beside the cells that say whose line it is (name, office and place). "
                        "A cell holding an e-mail address, a social media profile, a link page or anything that is not a web address is not "
                        "kept. Residence and campaign addresses, cities, ZIP codes, phones and e-mail are never read."))
    missing = sorted(k for k in november if not seen[k])
    twice = sorted(k for k, v in seen.items() if v > 1)
    with con:
        con.execute("DELETE FROM sl_websites WHERE race_id LIKE '2026-MN-%' AND source LIKE ?", (FILED + "%",))
        con.executemany("INSERT OR REPLACE INTO sl_websites VALUES (?,?,?,?)", [(r, n, u, MN_FILED) for (r, n), u in sorted(rows.items())])
        con.executemany("INSERT OR REPLACE INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        for old, new in OLD_NOTES:
            con.execute("UPDATE sl_sources SET note = replace(note, ?, ?) WHERE state = 'MN' AND note LIKE ?", (old, new, f"%{old}%"))
        _prune(con)
    by_level = collections.Counter(races[r]["level"] for (r, _n) in rows)
    total = sum(v[0] for v in per_file.values())
    say(f"    Minnesota: {total:,} candidates on the Secretary of State's two November lists read (name, office, place and the campaign "
        f"website cell only); {len(rows):,} listed a campaign website: " + ", ".join(f"{k} {v:,}" for k, v in by_level.most_common()))
    say("    not kept, because the cell is not a campaign website: " + (", ".join(f"{v:,} {NOT_KEPT[k]}" for k, v in sorted(not_kept.items())) or "none"))
    if unplaced or missing or twice:
        say(f"    check: {len(unplaced)} lines fit no race on the loaded list, {len(missing)} listed candidates are on no line, {len(twice)} are on two: "
            "the list in the database and the files differ; run python run_ballot.py local mn, then this again")
        for u in unplaced[:10]:
            say(f"      no race for {u}")
    else:
        say(f"    check: every line fits one race, and each of the {len(november):,} candidates on the loaded list is on exactly one line")
    return {"lines": total, "websites": len(rows), "by_level": dict(by_level), "not_kept": dict(not_kept), "unplaced": len(unplaced),
            "missing": len(missing), "twice": len(twice)}


def _prune(con):
    """Drop what was read from a site for someone who has left the November list or whose website is another one now."""
    for table in ("sl_site_checks", "sl_photo_options", "sl_issues", "sl_photos"):
        con.execute(f"""DELETE FROM {table} WHERE NOT EXISTS (SELECT 1 FROM sl_websites w JOIN sl_candidates c ON c.race_id = w.race_id AND c.name = w.name
                        WHERE w.race_id = {table}.race_id AND w.name = {table}.name AND c.election IN ({','.join('?' * len(NOVEMBER))}))""", NOVEMBER)
    for table in ("sl_photo_options", "sl_issues", "sl_photos"):
        con.execute(f"""DELETE FROM {table} WHERE EXISTS (SELECT 1 FROM sl_site_checks k JOIN sl_websites w USING (race_id, name)
                        WHERE k.race_id = {table}.race_id AND k.name = {table}.name AND k.url <> w.url)""")
    con.execute("DELETE FROM sl_site_checks WHERE EXISTS (SELECT 1 FROM sl_websites w WHERE w.race_id = sl_site_checks.race_id AND w.name = sl_site_checks.name AND w.url <> sl_site_checks.url)")
    con.execute(f"DELETE FROM sl_websites WHERE NOT EXISTS (SELECT 1 FROM sl_candidates c WHERE c.race_id = sl_websites.race_id AND c.name = sl_websites.name "
                f"AND c.election IN ({','.join('?' * len(NOVEMBER))}))", NOVEMBER)


# ---------------------------------------------------------------- 2. what the sweep found and a second reader confirmed

# words the loader holds back for a person to read, whoever wrote them: contact details, and the things never shown
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:[A-Za-z0-9.'-]+\s){1,3}(?:Street|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Lane|Ln|Parkway|"
                    r"Pkwy|Highway|Hwy|Trail|Terrace|Circle)\b", re.I)
NEVER = re.compile(r"\b(?:my|his|her|their|our) (?:wife|husband|spouse|partner|fianc[ée]e?|children|kids|sons?|daughters?|family|parents|father|"
                   r"mother|dad|mom|faith|church|parish|congregation|pastor|diagnosis|illness)\b|"
                   r"\b(?:married|divorced|widow(?:er|ed)?|(?:father|mother|dad|mom|parent|grandfather|grandmother|grandparent) (?:of|to)|"
                   r"grandchildren|born[- ]again|christian|catholic|lutheran|methodist|baptist|evangelical|muslim|jewish|mormon|"
                   r"cancer|diagnosed|rehab|sobriety|disabilit(?:y|ies)|arrest(?:ed)?|convict(?:ed|ion)|felony|misdemeanor|dui|dwi|"
                   r"indicted|lawsuit|sued|bankruptcy|salary|net worth)\b", re.I)
LEGISLATURE = re.compile(r"\b(?:state|minnesota) (?:house|senate|legislat\w+)|\bstate (?:representative|senator)\b|\blegislat(?:or|ure)\b", re.I)


def _held(*texts):
    """Why a finding's wording may not go on a page, or None."""
    for t in texts:
        t = str(t or "")
        if EMAIL.search(t) or PHONE.search(t) or POBOX.search(t) or STREET.search(t) or ZIP.search(t):
            return "reads like contact details"
        if NEVER.search(t):
            return "touches family, religion, health, money or legal matters"
    return None


def _year(text, end=False):
    """A year from the sweep's 'from' or 'to': '2019', '2019 (elected 2018)' -> 2019; 'now' (an end only) -> 'now';
    'elected 2018', 'not stated' and blanks -> None, since an election year is not the year a term began."""
    t = str(text if text is not None else "").strip().lower()
    if end and re.match(r"^(now|present|today|current|currently|incumbent)\b", t):      # "present (term expires 2026)" too
        return "now"
    if end:      # "term expires January 1, 2027": a term that has not run out is held today
        m = re.match(r"^(?:present )?term (?:expires|ends|runs (?:through|to|until))\b.*?\b(20\d\d)\b", t)
        if m and int(m.group(1)) >= 2026:
            return "now"
    m = re.match(r"^(\d{4})\b", t)
    return int(m.group(1)) if m and 1900 <= int(m.group(1)) <= 2026 else None


_rosters = {}


def _roster(state):
    """What the state's own roster database (state_<code>.sqlite, opened read-only) already gives for its sitting
    members: {'legislators': ids, 'birthdays': {id: date}, 'portraits': ids}. Official records stay the first source,
    so a found birth year, a found seat in the Legislature or a campaign photo is not taken where these speak."""
    code = (state or "").lower()
    if code not in _rosters:
        out = {"legislators": set(), "birthdays": {}, "portraits": set()}
        path = os.path.join(HERE, f"state_{code}.sqlite")
        if code and os.path.exists(path):
            try:
                rcon = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                for member, born in rcon.execute("SELECT bioguide_id, birthday FROM legislators"):
                    out["legislators"].add(member)
                    if born:
                        out["birthdays"][member] = born
                out["portraits"] = {m for (m,) in rcon.execute("SELECT bioguide_id FROM photos WHERE webp IS NOT NULL")}
                rcon.close()
            except sqlite3.Error:
                pass
        _rosters[code] = out
    return _rosters[code]


def _in_legislature(state):
    """A test for words naming a seat in the state's legislature: the general ones, and the state's own (STATES)."""
    more = STATES.get(state, {}).get("legislature")
    if not more:
        return LEGISLATURE.search
    own = re.compile(more, re.I)
    return lambda text: LEGISLATURE.search(text) or own.search(text)


def review_name(state):
    """The sheet for a person to read: REVIEW.md for Minnesota (as it always was), REVIEW-<ST>.md for another state."""
    return "REVIEW.md" if state == "MN" else f"REVIEW-{state}.md"


def party_hosts(state):
    """The hosts of the parties' own pages in this state: every address in ballot/lean/<code>_endorsements.json, which
    the endorsement step read from the parties themselves. A candidate's page on one of them is the party's page about
    them, not their campaign's own website (RULES.md), whoever paid for it. Hosts many people share are left out."""
    out = set()
    path = os.path.join(HERE, "ballot", "lean", f"{state.lower()}_endorsements.json")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (ValueError, OSError):
        return out

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and re.match(r"(?i)^https?://", x):
            h = _host(x)
            if h and h not in SHARED_HOSTS and not h.startswith("assets."):
                out.add(h)

    walk(d)
    return out


def load_found(con, say=print, folder=FOUND_DIR, state="MN"):
    """Verified findings in <folder>/<ST>-*.json -> sl_websites and sl_found_facts. Each finding is tied to a candidate by
    race and the exact name on the November list; only findings a second reader marked "verified": true are read.
    Only this state's rows are rewritten, and its sheet for a person to read is `review_name(state)`."""
    con.executescript(SCHEMA)
    in_legislature = _in_legislature(state)
    sheet = review_name(state)
    lead = "" if state == "MN" else f"{STATES.get(state, {}).get('name', state)}: "
    like = f"2026-{state}-%"
    with con:      # only this step's own rows
        con.execute("DELETE FROM sl_websites WHERE race_id LIKE ? AND source LIKE ?", (like, MARK + "%"))
        con.execute("DELETE FROM sl_found_facts WHERE race_id LIKE ?", (like,))
    paths = sorted(glob.glob(os.path.join(folder, f"{state}-*.json")))
    races, november = _races(con, state), _november(con, state)
    filed = {(r, n): u for r, n, u in con.execute("SELECT race_id, name, url FROM sl_websites WHERE race_id LIKE ?", (like,))}
    roster = _roster(state)
    parties = party_hosts(state)
    n = collections.Counter()
    by = {f: collections.Counter() for f in ("born", "office", "official_page", "endorsed_by", "past_party", "own_words")}
    review, differs, on_record, held, facts, sites, on_party = [], [], [], [], [], {}, []

    def cited(f):
        """The page a verified finding rests on, or None (and the reason counted)."""
        if not isinstance(f, dict) or f.get("verified") is not True:
            n["not verified"] += 1
            return None
        url = _web(f.get("url"))
        if not url:
            n["no page given"] += 1
        elif social(_host(url)) or _registrable(_host(url)) in LINK_PAGES:
            n["a social media page as the source"] += 1
        elif _registrable(_host(url)) in BROKERS:
            n["a people-search or records site as the source"] += 1
        else:
            return url
        return None

    def hold(race, name, field, why, url):
        held.append(f"- {race} | {_line(name)} | {field} | held back: {why} | {url}")

    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            people = d["candidates"] if isinstance(d, dict) and isinstance(d.get("candidates"), list) else None
        except (ValueError, OSError):
            people = None
        if people is None:      # one unreadable file is not everyone's: say which, and go on
            say(f"    {os.path.basename(path)} is not a findings file this loader can read (not JSON, or no list of candidates); skipped")
            n["files that could not be read"] += 1
            continue
        n["files"] += 1
        checked = str(d.get("verified_on") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", checked):      # the day the second reader last wrote the file
            checked = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()
        for c in people:
            if not isinstance(c, dict):
                n["malformed"] += 1
                continue
            race, name = c.get("race_id"), c.get("name")
            key = (race, name)
            if key not in november:
                n["no longer on the November list"] += 1
                continue
            r = races[race]
            if not full(r["level"], r["office_kind"]):
                n["an office that shows only what was filed"] += 1
                continue
            member = november[key]
            w = c.get("website")
            if isinstance(w, dict):
                url = cited(w)
                kind, clean = site_cell(url) if url else ("", None)
                if url and kind != "web":
                    n["a found website that is not a campaign website"] += 1
                elif url and _host(clean) in parties:      # the party's page about them, not their own site
                    on_party.append(f"- {race} | {_line(name)} | {clean}")
                elif url:
                    had = filed.get(key)
                    if had and same_site(had, clean):
                        n["confirmed the filed website"] += 1
                    elif had:
                        differs.append(f"- {race} | {_line(name)} | filed with the Secretary of State: {had} | the sweep found: {clean}")
                    else:
                        how = _line(w.get("how"))
                        sites[key] = (clean, f"{MARK} and checked {checked}" + (f": {how}" if how and not _held(how) else ""))
            site = filed.get(key) or sites.get(key, (None,))[0]
            o = c.get("official_page")
            if isinstance(o, dict):
                url = cited(o)
                if url and site and same_site(site, url):
                    n["an official page that is the campaign's own site"] += 1
                elif url:
                    src = _line(o.get("source"))
                    facts.append((race, name, "official_page", None, None, None, None, None, None, None, None, None,
                                  src if not _held(src) else "", url, "official", checked))
                    by["official_page"]["official"] += 1
            b = c.get("born")
            if isinstance(b, dict):
                url, year, kind = cited(b), b.get("year"), b.get("kind")
                if url and (kind not in KINDS or not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2008):
                    n["malformed"] += 1
                elif url and member and roster["birthdays"].get(member):
                    on_record.append(f"- {race} | {_line(name)} | birth year {year} | the state roster already gives a birth date | {url}")
                elif url:
                    date = b.get("date") if kind in ("official", "campaign") else None      # a full date only from the record or the candidate
                    date = date if isinstance(date, str) and re.fullmatch(rf"{year}-\d\d-\d\d", date) else None
                    facts.append((race, name, "born", year, date, None, None, None, None, None, None, None, _line(b.get("source")), url, kind, checked))
                    by["born"][kind] += 1
            for o in c.get("offices") or []:
                url = cited(o)
                if not url:
                    continue
                kind, office, src = o.get("kind"), _line(o.get("office")), _line(o.get("source"))
                why = _held(office, src)
                if kind not in KINDS or not office:
                    n["malformed"] += 1
                elif why:
                    hold(race, name, "office", why, url)
                elif member in roster["legislators"] and in_legislature(office):
                    on_record.append(f"- {race} | {_line(name)} | {office}, {_line(o.get('from')) or 'start not stated'} to {_line(o.get('to')) or 'end not stated'} "
                                     f"({kind}) | the state roster already gives this member's service in the Legislature | {url}")
                else:
                    facts.append((race, name, "office", None, None, office, _year(o.get("from")), _year(o.get("to"), end=True), None, None, None, None,
                                  src, url, kind, checked))
                    by["office"][kind] += 1
            for e in c.get("endorsed_by") or []:
                url = cited(e)
                if not url:
                    continue
                party, unit = _line(e.get("party")), _line(e.get("unit"))
                why = _held(party, unit)
                if not party:
                    n["malformed"] += 1
                elif site and same_site(site, url):      # the candidate saying so is not the party publishing it
                    n["an endorsement cited from the candidate's own site, not the party's"] += 1
                elif why:
                    hold(race, name, "endorsed_by", why, url)
                else:
                    facts.append((race, name, "endorsed_by", None, None, None, None, None, party, unit or None, None, None, unit or party, url, "party", checked))
                    by["endorsed_by"]["party"] += 1
            for p in c.get("past_party") or []:
                url = cited(p)
                if not url:
                    continue
                kind, what, party, src, year = p.get("kind"), _line(p.get("what")), _line(p.get("party")), _line(p.get("source")), _year(p.get("year"))
                why = _held(what, party, src)
                if kind not in KINDS or not what or not party or not year:
                    n["malformed"] += 1
                elif why:
                    hold(race, name, "past_party", why, url)
                else:
                    facts.append((race, name, "past_party", year, None, None, None, None, party, None, what, None, src, url, kind, checked))
                    by["past_party"][kind] += 1
            q = c.get("own_words")
            if isinstance(q, dict):
                url, quote = cited(q), _line(q.get("quote")).strip("\"“” ")
                if not url:
                    pass
                elif not quote:
                    n["malformed"] += 1
                elif not site or not same_site(site, url):
                    n["words that are not on the candidate's own campaign site"] += 1
                elif len(quote) > QUOTE_MAX:
                    hold(race, name, "own_words", f"longer than {QUOTE_MAX} characters", url)
                elif _held(quote):
                    hold(race, name, "own_words", _held(quote), url)
                else:
                    facts.append((race, name, "own_words", None, None, None, None, None, None, None, None, quote, "their campaign's own website", url, "campaign", checked))
                    by["own_words"]["campaign"] += 1
            for v in c.get("review") or []:
                if isinstance(v, dict) and v.get("verified") is True:
                    shows, problem = _line(v.get("shows")), _line(v.get("problem"))
                    if _held(shows, problem):
                        shows, problem = "(wording held back)", "(wording held back: read the page)"
                    review.append(f"- {race} | {_line(name)} | our record shows: {shows} | the source says: {problem} | {_line(v.get('url'))}")
    facts = list(dict.fromkeys(facts))
    with con:
        con.executemany("INSERT OR IGNORE INTO sl_websites VALUES (?,?,?,?)", [(r, nm, u, s) for (r, nm), (u, s) in sorted(sites.items())])
        con.executemany(f"INSERT INTO sl_found_facts VALUES ({','.join('?' * 16)})", facts)
        _prune(con)      # what was read from a found site that is no longer among the verified findings
    if paths:
        lines = ["# Found on the open web, state and local candidates: for a person to read", "",
                 "Written when the verified findings are loaded. Nothing on this sheet is loaded into the database or shown on a page.", "",
                 f"## Where a source disagrees with our record ({len(review)})", "", "race | name | what our record shows | what the source says | address", ""] + review
        lines += ["", f"## A website that differs from the one the candidate filed ({len(differs)}; the filed one is kept)", ""] + differs
        lines += ["", f"## A candidate's page on a party's own site ({len(on_party)}; not shown as a campaign website, and no photo is taken from it)", ""] + on_party
        lines += ["", f"## Held back by the loader's own guards ({len(held)}; the wording is not repeated here)", ""] + held
        lines += ["", f"## Found, but an official record already covers it ({len(on_record)}; not loaded, since a found fact fills a blank only)", ""] + on_record
        with open(os.path.join(folder, sheet), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    kinds = lambda f: ", ".join(f"{v} {k}" for k, v in sorted(by[f].items())) or "0"      # noqa: E731
    say(f"    {lead}Found on the open web ({n['files']} files in {_rel(folder)}): {len(sites)} websites added, "
        f"{n['confirmed the filed website']} confirmed the filed one, {len(differs)} differ (the filed one kept); "
        f"birth years: {kinds('born')}; offices: {kinds('office')}; official pages: {sum(by['official_page'].values())}; "
        f"party endorsements: {sum(by['endorsed_by'].values())}; earlier runs under a party label: {kinds('past_party')}; "
        f"own words: {sum(by['own_words'].values())}")
    if on_party:
        n["a page on a party's own site, not a campaign website"] = len(on_party)
    left = {k: v for k, v in n.items() if k not in ("files", "confirmed the filed website") and v}
    if left or held or on_record or review:
        say("    not loaded: " + (", ".join(f"{v} {k}" for k, v in sorted(left.items())) or "none")
            + f"; {len(held)} held back by the guards, {len(on_record)} already on an official record, {len(review)} review items"
            + (f" (see {sheet} beside the findings)" if paths else ""))
    return {"websites": len(sites), "facts": {f: dict(c) for f, c in by.items()}, "held": len(held), "review": len(review),
            "differs": len(differs), "on_record": len(on_record), "skipped": dict(left)}


# ---------------------------------------------------------------- 3. reading the websites

ROBOTS = "its robots.txt asks scripts not to read this page"
# a page that is a bot check and not the site: told by its title, or by marks only a challenge page carries (the scripts
# Cloudflare and Imperva add to ordinary pages are not such marks)
BOT_CHECK = re.compile(r"<title>\s*(?:just a moment|attention required|access denied|security check|are you (?:a )?(?:human|robot)|human verification|"
                       r"verif(?:y|ying) (?:you are|that you are) human|pardon our interruption|request unsuccessful|robot check|captcha|ddos-guard)|"
                       r"cf-browser-verification|_cf_chl_opt|px-captcha|/\.well-known/sgcaptcha", re.I)
# an address that now shows a holding page: parked, for sale or suspended
PARKED = re.compile(r"domain (?:name )?(?:is|may be) for sale|buy this domain|domain (?:name )?(?:has )?expired|parked (?:free|domain)|hugedomains|"
                    r"sedoparking|parkingcrew|afternic|account (?:has been )?suspended|this site is (?:currently )?unavailable", re.I)
OPEN = sqlite3.connect      # the small in-memory tables campaign.py's readers work against


class _Polite:
    """campaign._fetch with three courtesies added: a site's robots.txt is read first and obeyed for its pages (and for
    pictures on the site's own host), a page already read is handed back rather than asked for twice (the photo reader
    and the issue reader both begin at the home page), and requests to one host are at least `gap` seconds apart."""

    def __init__(self, plain, gap=1.0):
        self.plain, self.gap = plain, gap
        self.pages, self.rules, self.last = collections.OrderedDict(), {}, {}
        self.own, self.asked = set(), 0

    def _get(self, url, limit, timeout):
        host = urllib.parse.urlsplit(url).netloc.lower()
        wait = self.gap - (time.time() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            return self.plain(url, limit=limit, timeout=timeout)
        finally:
            self.last[host] = time.time()
            self.asked += 1

    def allowed(self, url):
        p = urllib.parse.urlsplit(url)
        root = f"{p.scheme}://{p.netloc.lower()}"
        if root not in self.rules:
            rp = urllib.robotparser.RobotFileParser()
            try:
                data, final, _ctype = self._get(root + "/robots.txt", 500_000, 20)
                text = data.decode("utf-8", "replace")
                rp.parse(text.splitlines() if "robots.txt" in final.lower() and "<html" not in text[:500].lower() else [])
            except HTTPError as e:      # a refused robots.txt is read as "stay out", as urllib.robotparser itself reads it
                rp.parse(["User-agent: *", "Disallow: /"] if e.code in (401, 403) else [])
            except Exception:  # noqa: BLE001  no robots.txt could be read; the page request itself says whether the site answers
                rp.parse([])
            self.rules[root] = rp
        return self.rules[root].can_fetch(net.UA, url)

    def __call__(self, url, limit=4_000_000, timeout=30):
        page = limit <= 4_000_000
        if page and url in self.pages:
            return self.pages[url]
        if (page or _host(url) in self.own) and not self.allowed(url):
            raise PermissionError(ROBOTS)
        got = self._get(url, limit, timeout)
        if page:
            self.pages[url] = got
            while len(self.pages) > 12:
                self.pages.popitem(last=False)
        return got


@contextlib.contextmanager
def polite_fetch(gap=1.0):
    """For the length of the block, campaign.py's readers fetch through _Polite; afterwards they are as they were."""
    plain = campaign._fetch
    web = _Polite(plain, gap)
    campaign._fetch = web
    try:
        yield web
    finally:
        campaign._fetch = plain


# what happened at a site, as sl_site_checks.status says it and as the run's last lines count it
STATUS = {"ok": ("ok", "were read"),
          "robots": ("asks scripts to stay out (robots.txt); not read", "ask scripts to stay out (robots.txt)"),
          "bot check": ("showed a bot check instead of the site; not read further", "showed a bot check instead of the site"),
          "social": ("leads to a social media page; nothing taken from it", "lead to a social media page"),
          "parked": ("shows a holding page (parked, for sale or suspended); nothing taken from it", "show a holding page (parked, for sale or suspended)"),
          "unnamed": ("neither its address nor its home page names the candidate; nothing taken from it",
                      "do not name the candidate in the address or on the home page"),
          "no answer": ("did not answer", "did not answer"),
          "error": ("could not be read through", "could not be read through")}


# A heading that is the site's furniture and not a topic, for the state and local pages. campaign.topic() has already
# dropped the plainest furniture (Donate, Volunteer, Get involved); the Congress pages keep exactly that rule, and this
# stricter one is applied here only. A heading is furniture when it is a label for the list itself ("On the issues",
# "My priorities", "Key issues"), a part of the page ("Quick links", "Recent posts", "Sign in"), an appeal or a question
# to the reader (it ends with ? or !), a fragment that leads into a list (it ends with a comma, "include" or "to"), a
# byline, a line about giving, an advertisement, a town and ZIP code, or a heading that names the candidate.
FURNITURE = re.compile(
    r"^(?:quick links|connect(?: with us)?|explore(?: the issues)?|navigate|close|site|your|we need|support(?: our efforts)?|"
    r"campaign(?: office)?|get updates|stay (?:updated|in the loop|in touch)|get in touch|drop us a line|on this page|sign in(?: to comment)?|"
    r"create an account|facebook|instagram|youtube|tiktok|twitter|linkedin|blog|recent (?:posts|responses|comments)|more information|"
    r"more coming on the blog|resources|sources|location|position title|take action|be part of the campaign|latest from the campaign|"
    r"receive campaign updates|get on our email list|frequently asked questions|faqs?|mail your check to|election information|"
    r"learn more|read more|share|comments?|archives?|categories|tags|newsletter|updates|links|gallery|photos|videos?|calendar|"
    r"focus areas|our focus|polic(?:y|ies)(?: positions)?|platform positions|positions)$|"
    r"^(?:on |the |our |my |some |explore )*(?:campaign['’]?s? )?(?:top |key |core |main |priority |near term )*"
    r"(?:issues?|priorities|positions|commitments)(?: (?:and|&) (?:issues|priorities|positions))?(?: in \d{4})?$|"
    r"^[\w.-]+['’]s? +(?:top |key |priority )*(?:issues?|priorities|positions|commitments|plan|approach|agenda|platform)\b|"
    r"[?!,]$|\b(?:include|includes|to|for)$|^[—–-]\s|powered by|\breactions?$|\bpaypal\b|\bdollar helps\b|\byour (?:vote|support)\b|"
    r"\bradio ads?\b|\badvertisements?\b|\b\d{5}(?:-\d{4})?$", re.I)
INVISIBLE = re.compile("[﻿​‌‍⁠­]")


def heading(t, given=""):
    """A stored heading as the local pages show it: invisible characters and a leading "+" set aside, runs of spaces
    closed up; None when it is the site's furniture (FURNITURE) or names the candidate by given name."""
    t = re.sub(r"\s+", " ", INVISIBLE.sub("", t or "")).strip()
    t = re.sub(r"^\+\s*", "", t).strip()
    if len(t) < 4 or FURNITURE.search(t.rstrip(":. ")) or FURNITURE.search(t):
        return None
    if given and len(given) >= 3 and re.search(rf"\b{re.escape(given)}(?:['’]s)?\b", t, re.I):
        return None
    return t


def _headings(topics, who):
    """A JSON list of headings cut to the ones that are topics; `who` is the person the site is about."""
    given = (name_parts(who)[0] or [""])[0]
    kept, seen = [], set()
    for t in json.loads(topics or "[]"):
        if _held(t) or "@" in t:      # reads like contact details, or touches what is never shown
            continue
        t = heading(t, given)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            kept.append(t)
    return kept


def reread_headings(con, say=print, state=None):
    """Apply the furniture rule again to the headings already stored in sl_issues (the campaign pages are not asked for
    again: nothing is downloaded). A candidate left with no topic loses the row. Returns the counts."""
    con.executescript(SCHEMA)
    races = _races(con, state)
    before = after = gone = 0
    with con:
        for rid, name, topics in con.execute("SELECT race_id, name, topics FROM sl_issues").fetchall():
            if rid not in races:
                continue
            had = json.loads(topics or "[]")
            kept = _headings(topics, _first_named(name, races[rid]["office_kind"], races[rid]["state"]))
            before, after = before + len(had), after + len(kept)
            if kept == had:
                continue
            if kept:
                con.execute("UPDATE sl_issues SET topics = ? WHERE race_id = ? AND name = ?", (json.dumps(kept, ensure_ascii=False), rid, name))
            else:
                gone += 1
                con.execute("DELETE FROM sl_issues WHERE race_id = ? AND name = ?", (rid, name))
            con.execute("UPDATE sl_site_checks SET topics = ? WHERE race_id = ? AND name = ?", (len(kept), rid, name))
    say(f"    Issue headings read again from what is stored (nothing downloaded): {before:,} headings before, {after:,} kept, "
        f"{before - after:,} set aside as the site's furniture; {gone:,} candidates are left with no topic")
    return {"before": before, "after": after, "emptied": gone}


def _why(e):
    """(kind, sentence) for a request that failed."""
    if isinstance(e, PermissionError):
        return "robots", STATUS["robots"][0]
    if isinstance(e, HTTPError):
        return "no answer", f"did not answer (HTTP {e.code})"
    text = str(getattr(e, "reason", e))
    if "getaddrinfo" in text or "Name or service" in text or "11001" in text:
        return "no answer", "did not answer (no such address was found)"
    if "CERTIFICATE" in text.upper() or "SSL" in text.upper():
        return "no answer", "did not answer (its security certificate could not be checked)"
    if "timed out" in text.lower():
        return "no answer", "did not answer (timed out)"
    return "no answer", f"did not answer ({type(e).__name__})"


def _names(family, final, text):
    """True when the site names the candidate: the family name (four letters or more) in the host's name, or in the path
    on a host many people share, or as a word anywhere in the home page."""
    if not family:
        return False
    p = urllib.parse.urlsplit(final)
    where = p.netloc + (p.path if _host(final) in SHARED_HOSTS else "")
    if len(family) >= 4 and family in re.sub(r"[^a-z]", "", where.lower()):
        return True
    return f" {family} " in f" {fold(text)} "


def _tickle(url):
    """Ask the home router for a site's address ahead of time. On John's network a first ask for a name nobody has
    asked for lately fails at once and the answer arrives seconds later (measured 2026-10-01: 2 of 160 names answered
    at the first ask, 157 within twenty seconds of asking again, one never), so the names of the next few sites are
    asked for while the current site is read. An address lookup is not a request to the site."""
    h = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    for name in (h, h[4:] if h.startswith("www.") else "www." + h):      # a site often passes a reader from one to the other
        try:
            socket.gethostbyname(name)
        except OSError:
            pass


def _resolves(url, tries=9):
    """True once the site's name has an address: asked up to nine times over about fourteen seconds, after the asks
    _tickle already made. A name with no address by then is taken as not existing."""
    h = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    for i in range(tries):
        try:
            socket.gethostbyname(h)
            return True
        except OSError:
            time.sleep(0.5 + 0.25 * i)
    return False


def _look(web, url):
    """The home page: (kind, sentence, the address asked, the address it led to, its text). When an https address
    does not answer for a reason other than the server's own refusal or a missing address, plain http is tried once
    (most candidates file an address without either)."""
    if not _resolves(url):
        return "no answer", "did not answer (no such address was found)", url, None, ""
    tries = [url] + (["http://" + url[len("https://"):]] if url.startswith("https://") else [])
    first = None
    for u in tries:
        try:
            data, final, _ctype = web(u)
            return "ok", STATUS["ok"][0], u, final, data.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            first = first or _why(e)
            if isinstance(e, (PermissionError, HTTPError)) or "no such address" in first[1] or not isinstance(e, (URLError, OSError)):
                break
    return first[0], first[1], url, None, ""


def fetch(con, say=print, only=None, limit=None, again="", pause=0.5, state=None):
    """Read each candidate's website once: photo options into sl_photo_options and issue headings into sl_issues, for
    the offices that may show them, with what happened kept in sl_site_checks. `only` is a set of "race_id|name" keys;
    `limit` stops after that many sites; `again` is "" (sites not yet read), "failed" (also those that did not answer)
    or "all"; `pause` is the rest between one site and the next (requests to one host are a second apart whatever it
    is). Each site's results are saved as it is finished, so a run that stops can simply be started again. About seven
    seconds a site (five real sites took 32 seconds on 2026-10-01). Returns the counts."""
    con.executescript(SCHEMA)
    with con:
        _prune(con)
    races = _races(con, state)
    november = _november(con, state)
    checks = {(r, n): (u, a) for r, n, u, a in con.execute("SELECT race_id, name, url, answered FROM sl_site_checks")}
    todo, small = [], 0
    for rid, name, url in con.execute("SELECT race_id, name, url FROM sl_websites ORDER BY race_id, name").fetchall():
        key = (rid, name)
        if key not in november or rid not in races or (only is not None and f"{rid}|{name}" not in only):
            continue
        if not full(races[rid]["level"], races[rid]["office_kind"]):
            small += 1
            continue
        had = checks.get(key)
        if had and had[0] == url and again != "all" and not (again == "failed" and not had[1]):
            continue
        todo.append((rid, name, url))
    if limit is not None:
        todo = todo[:max(0, int(limit))]
    say(f"    {len(todo):,} campaign websites to read this run ({small:,} belong to offices that show only the address, and are not read)")
    if not todo:
        return {"asked": 0}
    net.patient_lookups()      # the home router drops lookups; ask again rather than give up on a site
    quiet = lambda *_a, **_k: None      # noqa: E731  campaign.py's own running commentary; this step prints its own
    tally, today = collections.Counter(), dt.date.today().isoformat()
    with polite_fetch() as web:
        for i, (rid, name, url) in enumerate(todo, 1):
            for ahead in todo[i - 1:i + 5]:      # this site's name and the next five, asked for early (see _tickle)
                _tickle(ahead[2])
            person = f"{rid}|{name}"
            who = _first_named(name, races[rid]["office_kind"], races[rid]["state"])
            family = _family(who)
            member = november[(rid, name)]      # a sitting member with a portrait on the state roster needs no campaign photo
            portrait = bool(member) and member in _roster(races[rid]["state"])["portraits"]
            web.own = {_host(url)}
            kind, status, used, final, text = _look(web, url)
            names, opts, topics = None, [], None
            if kind == "ok":
                web.own.add(_host(final))
                if BOT_CHECK.search(text[:6000]):
                    kind = "bot check"
                elif social(_host(final)):
                    kind = "social"
                elif PARKED.search(text[:30000]):
                    kind = "parked"
                else:
                    names = _names(family, final, text)
                    kind = "ok" if names else "unnamed"
                status = STATUS[kind][0]
            if kind == "ok":
                mem = OPEN(":memory:")
                mem.executescript("CREATE TABLE people (person TEXT PRIMARY KEY, name TEXT, website TEXT, photo BLOB, photo_src TEXT);")
                mem.execute("INSERT INTO people VALUES (?,?,?,NULL,NULL)", (person, who, used))
                try:      # campaign.py's own pauses are not needed here: _Polite spaces every request to a host a second apart
                    if not portrait:
                        campaign.photos(mem, say=quiet, pause=0, only={person})
                        opts = mem.execute("SELECT opt, url, site, webp FROM photo_options WHERE person = ? ORDER BY opt", (person,)).fetchall()
                    campaign.issues(mem, say=quiet, pause=0, only={person})
                    topics = mem.execute("SELECT url, topics, fetched FROM issues WHERE person = ?", (person,)).fetchone()
                except Exception as e:  # noqa: BLE001  one site's trouble is not everyone's
                    kind, status = "error", f"{STATUS['error'][0]} ({type(e).__name__})"
                mem.close()
                if topics:      # a heading that reads like contact details, or touches what is never shown, is not a topic
                    kept = _headings(topics[1], who)      # and the site's furniture is not one either
                    topics = (topics[0], json.dumps(kept, ensure_ascii=False), topics[2]) if kept else None
            with con:
                con.execute("DELETE FROM sl_photo_options WHERE race_id = ? AND name = ?", (rid, name))
                con.execute("DELETE FROM sl_issues WHERE race_id = ? AND name = ?", (rid, name))
                con.executemany("INSERT INTO sl_photo_options VALUES (?,?,?,?,?,?)", [(rid, name, o, u, s, w) for o, u, s, w in opts])
                if topics:
                    con.execute("INSERT INTO sl_issues VALUES (?,?,?,?,?)", (rid, name, topics[0], topics[1], today))
                con.execute("INSERT OR REPLACE INTO sl_site_checks VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (rid, name, url, today, int(final is not None), status, final, None if names is None else int(names), len(opts),
                             len(json.loads(topics[1])) if topics else 0))
            tally["asked"] += 1
            tally["answered"] += final is not None
            tally["portrait on the roster"] += portrait and kind == "ok"
            tally["with photo options"] += bool(opts)
            tally["with issue headings"] += bool(topics)
            tally[kind] += 1
            if i % 25 == 0:
                say(f"      {i:,} of {len(todo):,} looked at; {tally['with photo options']:,} with photo options, {tally['with issue headings']:,} with issue headings")
            time.sleep(pause)
        tally["requests"] = web.asked
    say(f"    Campaign websites looked at: {tally['asked']:,} ({tally['answered']:,} answered, {tally['ok']:,} read); photo options kept for "
        f"{tally['with photo options']:,} (not looked for where the state roster already has the member's portrait: {tally['portrait on the roster']:,}), "
        f"issue headings for {tally['with issue headings']:,}; {tally['requests']:,} requests in all, one at a time")
    rest = [(tally[k], STATUS[k][1]) for k in STATUS if k != "ok" and tally[k]]
    if rest:
        say("    nothing taken from the sites that " + "; ".join(f"{words} ({v:,})" for v, words in sorted(rest, reverse=True)))
    return dict(tally)


# ---------------------------------------------------------------- 4. the photo options a person looked at

def apply_choices(con, say=print, path=CHOICE):
    """ballot/photo_choice_local.json -> sl_photos: for each "race_id|name", the option picked, credited to the site it
    came from. An option nobody has looked at never reaches a page, and "none" leaves the card without a photo."""
    con.executescript(SCHEMA)
    choice = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    races, november = _races(con), _november(con)
    used = 0
    with con:
        con.execute("DELETE FROM sl_photos")
        for key, c in sorted(choice.items()):
            rid, _, name = key.partition("|")
            pick = (c or {}).get("pick", "none") if isinstance(c, dict) else "none"
            if pick in (None, "", "none") or (rid, name) not in november or not full(races[rid]["level"], races[rid]["office_kind"]):
                continue
            row = con.execute("SELECT url, site, webp FROM sl_photo_options WHERE race_id = ? AND name = ? AND opt = ?", (rid, name, pick)).fetchone()
            if not row:
                continue
            con.execute("INSERT OR REPLACE INTO sl_photos VALUES (?,?,?,?,?)", (rid, name, row[2], f"From the campaign's own website, {row[1]}", row[0]))
            used += 1
    have = {f"{r}|{n}" for r, n in con.execute("SELECT DISTINCT race_id, name FROM sl_photo_options")}
    say(f"    Campaign photos chosen for the state and local pages: {used:,}; {len(have - set(choice)):,} candidates' options still to be looked at"
        + ("" if os.path.exists(path) else f" ({_rel(path)} is not there yet)"))
    return used


def contact_sheets(con, say=print, out_dir=SHEETS, path=CHOICE):
    """Every candidate's photo options nobody has chosen among yet, on numbered sheets (7a, 7b, 7c) drawn by
    campaign.contact_sheet, with index.json beside them saying which number is which "race_id|name"."""
    con.executescript(SCHEMA)
    done = set(json.load(open(path, encoding="utf-8"))) if os.path.exists(path) else set()
    races = _races(con)
    mem = OPEN(":memory:")
    mem.executescript(campaign.OPTIONS + "CREATE TABLE people (person TEXT PRIMARY KEY, name TEXT);")
    for rid, name, opt, url, site, webp in con.execute("SELECT race_id, name, opt, url, site, webp FROM sl_photo_options ORDER BY race_id, name, opt"):
        key = f"{rid}|{name}"
        if key in done or rid not in races:
            continue
        mem.execute("INSERT OR IGNORE INTO people VALUES (?,?)", (key, name))
        mem.execute("INSERT INTO photo_options VALUES (?,?,?,?,?)", (key, opt, url, site, webp))
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "contact-*.png")):
        os.remove(old)
    sheets, index = campaign.contact_sheet(mem, out_dir=out_dir, only_new=False)
    rows = []
    for n, key, name in index:
        rid = key.split("|", 1)[0]
        opts = mem.execute("SELECT opt, site FROM photo_options WHERE person = ? ORDER BY opt", (key,)).fetchall()
        rows.append({"n": n, "key": key, "name": name, "office": office_words(races[rid]), "jurisdiction": races[rid]["jurisdiction"],
                     "site": opts[0][1] if opts else None, "options": [o for o, _s in opts]})
    mem.close()
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"sheets": [os.path.basename(s) for s in sheets], "people": rows}, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    say(f"    {len(rows):,} candidates' photo options wait to be looked at: {len(sheets)} sheets in {_rel(out_dir)}, numbered in index.json")
    return sheets, rows


# ---------------------------------------------------------------- 5. who the open-web sweep should research (Minnesota)

ACS_DIR = os.path.join(HERE, "states_cache", "acs2024")
ACS_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/"
ACS_FILES = (("documentation/Geos20245YR.txt", "Geos20245YR.txt"), ("data/5YRData/acsdt5y2024-b01003.dat", "acsdt5y2024-b01003.dat"))
ACS_TITLE = ("American Community Survey 2020-2024 five-year estimates, table B01003 (total population), table-based summary file "
             "(acsdt5y2024-b01003.dat, with Geos20245YR.txt saying which row is which place)")
THRESHOLD = 10_000
NEAR = 9_000


def office_words(r):
    """The office as a reader would say it, with its district or seat: 'County Commissioner, District 1'."""
    out = [r["office"]]
    if r["district"] and r["level"] != "legislature" and r["office_kind"] != "district_court":
        d = str(r["district"])
        out.append(f"District {d}" if re.fullmatch(r"\d+[A-Z]?", d) else d)
    if r["seat"]:
        s = str(r["seat"])
        out.append(f"Seat {s}" if re.fullmatch(r"\d+|[A-Z]", s) else s)
    return ", ".join(out) + (" (special election)" if r["special"] else "")


def census_population(say=print, stusab="MN"):
    """The Census Bureau's ACS 2020-2024 total population (table B01003) for one state's places, county subdivisions
    and school districts: {'place': {code: row}, 'cousub': {(county, code): row}, 'school': {geo id: row}} with each row
    {'name', 'population', 'margin'} (margin None where the Bureau gives none), and the two files read. The files are
    the ones the districting lenses already keep in states_cache/acs2024/; a missing one is downloaded, without a key."""
    paths = []
    for remote, local in ACS_FILES:
        path = os.path.join(ACS_DIR, local)
        net.download(ACS_URL + remote, path, 1800, say=say)
        paths.append(path)
    geo = {}
    with open(paths[0], encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        ix = {h: i for i, h in enumerate(head)}
        for line in fh:
            if f"|{stusab}|" not in line[:16]:
                continue
            f = line.rstrip("\r\n").split("|")
            if f[ix["SUMLEVEL"]] in ("160", "060", "970", "950", "960") and f[ix["COMPONENT"]] == "00":
                geo[f[ix["GEO_ID"]]] = (f[ix["SUMLEVEL"]], re.sub(r", [A-Za-z ]+$", "", f[ix["NAME"]]) if f[ix["SUMLEVEL"]] != "060" else f[ix["NAME"]])
    out = {"place": {}, "cousub": {}, "school": {}}
    with open(paths[1], encoding="utf-8") as fh:
        if fh.readline().strip() != "GEO_ID|B01003_E001|B01003_M001":
            raise SystemExit("    acsdt5y2024-b01003.dat: the header is not the one this reader was checked against; stopping")
        for line in fh:
            g, e, m = line.rstrip("\r\n").split("|")
            if g not in geo:
                continue
            level, name = geo[g]
            row = {"name": name, "population": int(e), "margin": int(m) if m.lstrip("-").isdigit() and int(m) >= 0 else None}
            code = g.split("US", 1)[1]
            if level == "160":
                out["place"][code[2:]] = row
            elif level == "060":
                out["cousub"][(code[2:5], code[5:])] = row
            elif not name.startswith("Remainder of"):
                out["school"][g] = row
    sources = [{"file": os.path.basename(p), "url": ACS_URL + remote, "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
                "on_disk_since": dt.date.fromtimestamp(os.path.getmtime(p)).isoformat()} for p, (remote, _l) in zip(paths, ACS_FILES)]
    return out, sources


def _place_code(jurisdiction_id):
    """The Census place code a city race carries: the jurisdiction id itself (Minnesota, whose list gives the code), or
    its last five digits where a state's loader writes the id as <ST>-M-<code> (South Dakota)."""
    m = re.fullmatch(r"[A-Z]{2}-M-(\d{5})", jurisdiction_id or "")
    return m.group(1) if m else jurisdiction_id


def _bare_place(name):
    t = re.sub(r"\s*\(.*?\)", "", name or "").split(",")[0]
    t = re.sub(r"^(?:Village|City|Town) of ", "", t.strip(), flags=re.I)
    t = re.sub(r"\s+(?:city|township|village|town|unorganized territory|UT)$", "", t, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", t.lower().replace("saint ", "st ").replace("st. ", "st "))


def _school_key(name):
    t = re.sub(r"\s*\((?:ISD|SSD|Common School District) #\d+\)$", "", name or "").lower().replace("&", "and").replace("saint ", "st. ")
    t = re.sub(r"\b(?:public school district|public schools|public school|school district|community schools|community school|area schools|schools|"
               r"school|district|public|area)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def school_crosswalk(places, census, say=print):
    """{school place id: Census geo id}, tying the state's school district list to the Census Bureau's rows by name: the
    same name, or the same name once the words both lists vary (Public, Area, Schools, School District) are set aside,
    and only when exactly one district on each side fits. Every pair that is not letter for letter the same is printed
    for reading."""
    exact = collections.defaultdict(list)
    loose = collections.defaultdict(list)
    for g, row in census.items():
        exact[row["name"].lower()].append(g)
        loose[_school_key(row["name"])].append(g)
    ours = collections.Counter(_school_key(n) for n in places.values())
    out, pairs = {}, []
    for sid, name in sorted(places.items()):
        plain = re.sub(r"\s*\((?:ISD|SSD|Common School District) #\d+\)$", "", name)
        if len(exact[plain.lower()]) == 1:
            out[sid] = exact[plain.lower()][0]
        elif len(loose[_school_key(name)]) == 1 and ours[_school_key(name)] == 1:
            out[sid] = loose[_school_key(name)][0]
            pairs.append((sid, plain, census[out[sid]]["name"]))
    if len(set(out.values())) != len(out):
        raise SystemExit("    school districts: two districts were tied to one Census row; stopping")
    say(f"    school districts tied to the Census Bureau's rows by name: {len(out):,} of {len(places):,} ({len(out) - len(pairs):,} letter for letter; "
        f"{len(pairs)} once Public, Area, Schools and School District are set aside, listed in the scope's places file)")
    return out, pairs


def scope(con, say=print, out_dir=FOUND_DIR, threshold=THRESHOLD, state="MN"):
    """One state (Minnesota when not said): who the open-web sweep should research, written to <code>_scope.json
    (race_id, name, level, office, jurisdiction; by race, then name), with <code>_scope_counts.json (counts by level,
    and how many parts of thirty) and <code>_scope_places.json (the Census file, and which cities and school districts
    are in). In: every statewide, legislative and court race, every county-level race, and the mayor, council and
    school board races of cities and school districts with at least `threshold` people in the Census Bureau's file.
    A city is found in that file by its place code (the race's jurisdiction_id) with the names agreeing, a school
    district by name; a state whose November list has no city or school race (Wisconsin, which votes on them in
    April) gets a sentence saying so in the counts and places files."""
    st_code, words = state.lower(), STATES.get(state, {}).get("name", state)
    races, november = _races(con, state), _november(con, state)
    pop, sources = census_population(say=say, stusab=state)
    per_race = collections.Counter(r for (r, _n) in november)
    cities, schools = {}, {}
    for r in races.values():
        if r["level"] == "city" and r["office_kind"] in FULL_CITY:
            cities.setdefault(r["jurisdiction_id"], {"name": r["jurisdiction"], "counties": set(), "races": []})
            cities[r["jurisdiction_id"]]["counties"] |= set(json.loads(r["county_ids"] or "[]"))
            cities[r["jurisdiction_id"]]["races"].append(r["race_id"])
        elif r["level"] == "school":
            schools.setdefault(r["jurisdiction_id"], {"name": r["jurisdiction"], "races": []})["races"].append(r["race_id"])
    school_places = dict(con.execute("SELECT id, name FROM sl_places WHERE kind = 'school' AND source_id LIKE ?", (st_code + "-%",)))
    walk, pairs = school_crosswalk(school_places, pop["school"], say=say)
    # a state's own table of school districts the two lists name too differently for the spelling rule (Michigan): each
    # is tied only when the Census file has exactly one row of the name given and no other district has taken it
    by_name = collections.defaultdict(list)
    for g, row in pop["school"].items():
        by_name[row["name"]].append(g)
    for sid, census_name in sorted(STATES.get(state, {}).get("school_names", {}).items()):
        if sid in school_places and sid not in walk and len(by_name[census_name]) == 1 and by_name[census_name][0] not in walk.values():
            walk[sid] = by_name[census_name][0]
            pairs.append((sid, school_places[sid], census_name))
            say(f"    tied by {words}'s own table of names: {school_places[sid]} = {census_name}")

    def count(entry):
        return {"races": len(entry["races"]), "candidates": sum(per_race[r] for r in entry["races"])}

    city_rows, school_rows, no_figure = [], [], []
    aliases = STATES.get(state, {}).get("place_codes", {})      # Kentucky: a consolidated city read by its balance's row
    for code, c in sorted(cities.items()):
        row, how = pop["place"].get(aliases.get(code) or _place_code(code)), None
        if code in aliases and row:
            how = f"the Census place code {_place_code(code)} is not among the file's places; read by {state}'s own table as {aliases[code]}"
        if row and _bare_place(row["name"]) != _bare_place(c["name"]):
            row = None
        if not row:      # a code the Census file has under another number or kind: the same name among the county's subdivisions
            parts = [v for (county, _sub), v in pop["cousub"].items() if county in c["counties"] and _bare_place(v["name"]) == _bare_place(c["name"])]
            if parts and len(parts) <= len(c["counties"]):
                row = {"name": "; ".join(p["name"] for p in parts), "population": sum(p["population"] for p in parts),
                       "margin": parts[0]["margin"] if len(parts) == 1 else None}
                how = "not under this code among the file's places; found by name among the county subdivisions"
        if not row:
            no_figure.append({"kind": "city", "id": code, "name": c["name"], **count(c), "note": "no row of this code or name in the Census file"})
            continue
        city_rows.append({"id": code, "name": c["name"], "census_name": row["name"], "population": row["population"], "margin": row["margin"], **count(c),
                          **({"note": how} if how else {})})
    for sid, s in sorted(schools.items()):
        g = walk.get(sid)
        if not g:
            no_figure.append({"kind": "school district", "id": sid, "name": s["name"], **count(s),
                              "note": "not in the Census file, whose school districts are those of an earlier school year"})
            continue
        row = pop["school"][g]
        school_rows.append({"id": sid, "name": s["name"], "census_name": row["name"], "census_geo_id": g, "population": row["population"],
                            "margin": row["margin"], **count(s)})
    in_city = {c["id"] for c in city_rows if c["population"] >= threshold}
    in_school = {s["id"] for s in school_rows if s["population"] >= threshold}

    rows = []
    for (rid, name) in sorted(november):
        r = races[rid]
        if (r["level"] in ("statewide", "legislature", "court", "county")
                or (r["level"] == "city" and r["office_kind"] in FULL_CITY and r["jurisdiction_id"] in in_city)
                or (r["level"] == "school" and r["jurisdiction_id"] in in_school)):
            office = office_words(r)
            if r["office_kind"] == "governor" and not STATES.get(state, {}).get("no_ticket"):      # Wyoming has no Lieutenant Governor
                office +=" (one ticket: findings are about the candidate for Governor, who is named first)"
            where = r["jurisdiction"]
            if where == words and state != "MN" and r["level"] == "legislature":      # Missouri's give the state's own name
                where = ""
            if not where and r["level"] == "legislature" and r["district"]:      # Ohio's legislative races name no jurisdiction
                where = (f"{STATES[state]['district_words']} {r['district']}" if STATES.get(state, {}).get("district_words") else      # Nebraska
                         f"{'Senate' if r['office_kind'] == 'state_senate' else 'House'} District {r['district']}")
            elif not where and r["office_kind"] == "court_of_appeals" and r["district"]:      # Michigan's, likewise
                where = f"Court of Appeals District {r['district']}"
            rows.append({"race_id": rid, "name": name, "level": r["level"], "office": office, "jurisdiction": where})
    rows.sort(key=lambda x: (x["race_id"], x["name"]))
    levels = ["statewide", "legislature", "court", "county", "city", "school"]
    by_level = collections.Counter(x["level"] for x in rows)
    races_by_level = collections.Counter(races[rid]["level"] for rid in {x["race_id"] for x in rows})
    parts = math.ceil(len(rows) / PER_PART)
    made = dt.date.today().isoformat()
    rule = (f"Every statewide, legislative and court race; every county-level race; and the mayor, city council and school board races of "
            f"cities and school districts with at least {threshold:,} people in the Census Bureau's ACS 2020-2024 estimate (table B01003).")
    just_under = ([{"kind": "city", **c} for c in city_rows if NEAR <= c["population"] < threshold]
                  + [{"kind": "school district", **s} for s in school_rows if NEAR <= s["population"] < threshold])
    big_quiet = sorted(v["name"] for code, v in pop["place"].items() if v["population"] >= threshold
                       and code not in {aliases.get(c) or _place_code(c) for c in cities})
    other_city = collections.Counter(r["office"] for r in races.values() if r["level"] == "city" and r["office_kind"] not in FULL_CITY
                                     and pop["place"].get(_place_code(r["jurisdiction_id"]), {"population": 0})["population"] >= threshold)
    none_local = (None if state == "MN" or by_level["city"] or by_level["school"] or cities or schools else
                  f"No city or school board race is on {words}'s November 3, 2026 list in the database, so no place was "
                  f"picked by its population; the Census file is named so that the cities of {threshold:,} or more can be read from it."
                  + (" " + STATES[state]["why_no_local"] if STATES.get(state, {}).get("why_no_local") else ""))
    where = ("A city is found by its place code, which the candidate list's MCD code equals for Minnesota's cities, and "
             "the two names must agree; a school district by its name." if state == "MN" else
             "A city is found by its Census place code, where the race carries one, and the two names must agree; a school district by its name.")
    places = {
        "state": state, "made": made, "threshold": threshold, "rule": rule,
        "population_source": {"agency": "U.S. Census Bureau", "title": ACS_TITLE, "fetched_without_a_key": True, "files": sources,
                              "note": "Estimates from a survey, each with the Bureau's 90 percent margin of error (margin; null where the Bureau gives "
                                      "none). " + where},
        "cities": sorted([c for c in city_rows if c["id"] in in_city], key=lambda c: -c["population"]),
        "school_districts": sorted([s for s in school_rows if s["id"] in in_school], key=lambda s: -s["population"]),
        "just_under": sorted(just_under, key=lambda c: -c["population"]),
        "no_population_figure": no_figure,
        "cities_found_by_name_not_code": [c for c in city_rows if c.get("note")],
        "cities_of_that_size_with_no_mayor_or_council_race_on_this_ballot": big_quiet,
        "other_city_offices_in_those_cities_left_out": dict(other_city),
        "school_names_tied_after_setting_words_aside": [{"id": sid, "state_list": a, "census": b} for sid, a, b in pairs]}
    counts = {"state": state, "made": made, "rule": rule, "candidates": len(rows), "by_level": {lv: by_level[lv] for lv in levels},
              "races_by_level": {lv: races_by_level[lv] for lv in levels}, "races": sum(races_by_level.values()),
              "on_the_november_list_in_all": len(november), "per_part": PER_PART, "parts": parts,
              "cities_in": len(in_city), "city_candidates": by_level["city"], "school_districts_in": len(in_school), "school_candidates": by_level["school"],
              "just_under": {"places": len(just_under), "candidates": sum(c["candidates"] for c in just_under)}}
    if none_local:
        places["note"] = counts["note"] = none_local
    elif STATES.get(state, {}).get("local_note"):
        places["note"] = counts["note"] = STATES[state]["local_note"]
    os.makedirs(out_dir, exist_ok=True)
    for fname, obj in ((f"{st_code}_scope.json", rows), (f"{st_code}_scope_counts.json", counts), (f"{st_code}_scope_places.json", places)):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    say(f"    {words} scope for the open-web sweep: {len(rows):,} candidates in {counts['races']:,} races: "
        + ", ".join(f"{lv} {by_level[lv]:,}" for lv in levels))
    say(f"    cities of {threshold:,} or more with a mayor or council race: {len(in_city)} ({by_level['city']:,} candidates); school districts: "
        f"{len(in_school)} ({by_level['school']:,} candidates); just under ({NEAR:,} to {threshold - 1:,}): {len(just_under)} places, "
        f"{counts['just_under']['candidates']} candidates; no population figure: {len(no_figure)}")
    say(f"    PARTS: {parts} (at {PER_PART} candidates a part); written to {_rel(out_dir)}")
    return counts


# ---------------------------------------------------------------- the two stages, and the command line

def found_states(folder=FOUND_DIR):
    """The states beyond Minnesota whose findings are loaded: those in STATES with a scope file in the folder."""
    return [st for st in sorted(STATES) if st != "MN" and os.path.exists(os.path.join(folder, f"{st.lower()}_scope.json"))]


def stage_facts(db=DB, say=print, folder=FOUND_DIR):
    """python run_ballot.py localfacts: the filed websites (Minnesota, whose files carry them), the verified findings
    (Minnesota, then every other state with a scope file) and the photo choices. No network."""
    con = connect(db)
    try:
        try:
            file_websites(con, say=say)
        except SystemExit as e:      # the Secretary's files are not there, or no longer fit: say so and go on
            say(str(e) or "    Minnesota: the Secretary of State's candidate files could not be read")
        load_found(con, say=say, folder=folder)
        for st in found_states(folder):
            load_found(con, say=say, folder=folder, state=st)
        apply_choices(con, say=say)
    finally:
        con.close()


def stage_fetch(db=DB, say=print, only=None, limit=None, again=""):
    """python run_ballot.py localfetch: read the campaign websites, then draw the contact sheets (for a trial copy of
    the database, in a folder beside that copy, so a trial never replaces the real sheets)."""
    con = connect(db)
    try:
        out = fetch(con, say=say, only=only, limit=limit, again=again)
        sheets = SHEETS if os.path.abspath(db) == os.path.abspath(DB) else os.path.join(os.path.dirname(os.path.abspath(db)), "campaign_local")
        contact_sheets(con, say=say, out_dir=sheets)
        return out
    finally:
        con.close()


def _say(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="State and local candidates: filed websites, verified findings, photo options and issue headings")
    ap.add_argument("what", choices=["scope", "files", "found", "choices", "fetch", "sheets", "headings"])
    ap.add_argument("--db", default=DB, help="another copy of ballot_local_2026.sqlite (for a trial run)")
    ap.add_argument("--folder", default=FOUND_DIR, help="found: the folder of findings files; scope: where the scope files go")
    ap.add_argument("--choice", default=CHOICE, help="choices, sheets: another photo choice file")
    ap.add_argument("--sheets", default=SHEETS, help="sheets: another folder for the contact sheets")
    ap.add_argument("--state", default="MN", help="scope, found: the state (two letters; Minnesota when left out)")
    ap.add_argument("--limit", type=int, default=None, help="fetch: stop after this many websites")
    ap.add_argument("--only", default="", help='fetch: only these candidates, "race_id|name;race_id|name"')
    ap.add_argument("--again", default="", choices=["", "failed", "all"], help="fetch: also re-read sites that did not answer, or every site")
    a = ap.parse_args(argv)
    db = os.path.abspath(a.db)
    state = a.state.upper()
    if state not in STATES:
        raise SystemExit(f"    {state} is not a state this module serves yet (STATES in ballot/local_sites.py)")
    if a.what == "scope":      # reads the list, writes three files; the database is not changed
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        scope(con, say=_say, out_dir=a.folder, state=state)
        con.close()
        return
    con = connect(db)
    if a.what == "files":
        file_websites(con, say=_say)
    elif a.what == "found":
        load_found(con, say=_say, folder=a.folder, state=state)
    elif a.what == "choices":
        apply_choices(con, say=_say, path=a.choice)
    elif a.what == "fetch":
        fetch(con, say=_say, only={p.strip() for p in a.only.split(";") if p.strip()} or None, limit=a.limit, again=a.again)
    elif a.what == "sheets":
        contact_sheets(con, say=_say, out_dir=a.sheets, path=a.choice)
    elif a.what == "headings":
        reread_headings(con, say=_say)
    con.close()


if __name__ == "__main__":
    main()
