#!/usr/bin/env python3
"""
build_ballot_state_dev.py - On The Ballot, the state and local races, state by state: site/dev/ballot/<code>/index.html
for every state the state and local ballot database holds, and the chooser that lists them, site/dev/ballot/states/.

    python build_ballot_state_dev.py [--state all | mn | wi,ia] [--db ballot_local_2026.sqlite] [--root site/dev/ballot]
    python build_ballot_state_dev.py --state mn --out site/dev/ballot/mn/index.html      (one state, somewhere else)

--state all (the default) builds every state with rows in ballot_local_2026.sqlite. Every state's page carries the
statewide offices, the Legislature and whatever courts its list holds. A state whose rows reach the counties (Minnesota
first; then every state loaded under the conventions in ballot/check_local.py) also gets the county pages and the
county, city or town and school district choices of "your ballot". Whether a state has them is read from the rows,
never from a list of states kept here; a state without them says how many states have them and links to the chooser.

One small page per state, routed by its address, and the data it fetches:
  ""               home: the levels, "your ballot" and (where the list reaches them) every county
  #statewide       governor and the other offices the whole state elects
  #legislature     the upper and lower chambers' districts on the map, and every district's race
  #courts          the courts on the state's list (only where it holds some)
  #county=<fips>   every county, conservation district, city or town, township, school and other district contest
                   reaching that county, grouped by place, with the court contests whose counties include it
                   (the three-digit county code, #county=053; the five-digit code is understood too)
  #race=<race_id>  one contest: the candidates as same-size cards, the primary where there was one, the sources
  #map=<layer>:<id>  the home page with that shape on the map, where the state has its map files (#map=ward:00694|Ward 2)

Each state's folder holds index.html (the shell), data/<code>.json (the races and candidates), data/districts.json (the
legislative lines, and the county lines where the county pages are built, fetched only when a map or "use my
location" needs them) and fonts/ (the kit's own type, so the page asks nothing of any other server). It reads
ballot_local_2026.sqlite (the states' own lists, loaded by the ballot/state_local_<code>.py loaders; sl_notes and
sl_gaps say which local offices are on this ballot, what was read and what is not here yet, and the page shows them in
those words), state_<code>.sqlite (only to tell which ids are sitting legislators and statewide officials, for the
links to their record pages), state_<code>_districts.json (the same lines the state pages draw; which lower-chamber
district sits inside which upper-chamber one is worked out from them by build_state_dev.nesting, never from a numbering
scheme), states/places.py (each chamber's name, title and seats, the map's zooms) and us_states_albers.json. County
lines: Minnesota's are local_mn_counties.json; any other state's are made the same way (states/load_counties.py's own
reader, on the Census Bureau's national county file already in states_cache/census/) and kept in
states_cache/local_counties/; with no lines the page offers the list of counties and no map. It opens
ballot_2026.sqlite read-only, only to count each state's Congress races for one sentence. It downloads nothing and
writes nothing but the pages and those county lines.

Words come from the record, state by state: whether an office is on party lines is read from each row; a place is
called a city, a town or a village as its own name says, and filed with the cities or the townships as its races'
level says; the heading over a county's court contests fits the courts that are there; an office kind this file has
not placed yet keeps its own office title and is listed after the kinds it knows (the build names it). Minnesota's
rows keep their older ids and its page keeps its own words.

What reaches the page from the lists, and nothing else (John, 2026-09-30): for every candidate the name as filed, the
office, the jurisdiction, the party for a partisan office or "Nonpartisan office", the ballot order, and write-in and
special marks. A sitting legislator matched by the loader gets a link to their existing record page on the state side.
The data is built field by field from those columns, and a last check drops any text that looks like an e-mail address,
a phone number, a web address or a street address; the build names the race when it drops something and never prints
the text itself. A state that has only its lists shows no photos, ages, websites, biographies, money or Wikipedia.

Where a state has more (John, 2026-10-01; Minnesota first), the same page shows it, and a state without it keeps the
page it had: each part is read only if it is there, and the parts of the page only such a state needs are left out of
every other state's page (the marks <extras> and <plain> in PAGE).
  - The map (ballot_geo/<code>/, written by a builder of its own; index.json says what the files are). One map set into
    "your ballot" for every kind of line a ballot is made of, drawn in Web Mercator from the whole state down to a
    street: a layer's own file far out, each county's precinct file close in. Its files are copied to geo/ beside the
    page with the reader that was built with them and the map's own script (MAPKIT below, geo/mapkit.js), fetched when
    a map opens. "Use my location" finds the reader's precinct on their device and lists every district it is in; the
    ballot is then exactly that precinct's contests, because every race names the shape that draws its place
    (race_shape) and the precinct names the shapes it lies in. Street pictures (OpenStreetMap's standard tiles) are
    off until a reader switches them on. Polling places are shown only when polling_places.json says they are loaded
    and checked; otherwise the page says why not, in that file's words, with the state's own finder to open. The
    sources' notices are shown with the map, word for word.
  - Who the candidates are (the sl_websites, sl_found_facts, sl_issues and sl_photos tables; ballot/local_sites.py
    says who may show what). For the fuller offices a card may show a photo, an age, public offices held, the
    campaign's website and its issue headings, each with its source and the Congress pages' labels; every other
    candidate shows what they filed and a website if they listed one. A sitting member's birth date, terms and
    portrait come from the state roster first. Written to data/who.json and photos/, fetched by a race's page.
    Never: addresses, phone numbers, e-mail, family, religion, health, income, employers, schools; who_data() names
    every column it reads and every other text passes the last check for contact details.
  - The record, not a label (ballot/lean/<code>_endorsements.json and <code>_place_votes.json). On a nonpartisan
    office's page: a party's own published endorsement, an earlier run or office under a party label and the
    candidate's own words, each linked; and how the place voted in past partisan elections, as plain bars with counts
    and the file's own note (data/votes/, one small file for each kind of place). Nobody is called by a party here.
  - Polls and prediction markets of the statewide races (ballot/polls/polls_<code>_state_2026.json and the snapshot
    ballot/odds.py keeps of the markets named in ballot/odds_state_<code>.json), shown as the Congress pages show
    theirs: the part of build_ballot_dev.PAGE that draws them is borrowed whole.

One look, one code path: the site's stylesheet and the shared script parts (the changelog badge and the map arithmetic
behind "use my location") come from the federal page by the landmarks in build_state_dev.BORROWED, and the ballot pages'
own stylesheet (the arena, the cards, the primary fields, the maps) and the script that folds a page's sources (one
closed fold, a closed fold inside it for each kind of source) from build_ballot_dev.PAGE by the landmarks below. If
a landmark can no longer be found, the build stops and names it; nothing is copied by hand. Every state's page is the same
page: what differs (the state's name, its chambers, its election office, its primary date) is worked out here from the
record and handed to the page as BOOT.st.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_ballot_dev                                                    # noqa: E402  the Congress ballot page: its stylesheet and election names
from ballot.common import party_code                                      # noqa: E402
from build_site_dev import read_changelog, state_paths                    # noqa: E402
from build_state_dev import borrow, natural, nesting                      # noqa: E402
from states.places import place                                           # noqa: E402

try:
    from ballot.lists.mn import PARTY as MN_PARTY                         # the Secretary's party codes, written out
except Exception:                                                         # pragma: no cover - the words below are the same
    MN_PARTY = {"DFL": "Democratic-Farmer-Labor", "R": "Republican", "IND": "Independent", "LIB": "Libertarian", "GP": "Green",
                "LMN": "Legal Marijuana Now", "GLC": "Grassroots-Legalize Cannabis", "IA": "Independence-Alliance", "SWP": "Socialist Workers",
                "IP": "Independence"}

DB = os.path.join(HERE, "ballot_local_2026.sqlite")
ROOT = os.path.join(HERE, "site", "dev", "ballot")
FED_DB = os.path.join(HERE, "ballot_2026.sqlite")
GENERAL_DATE = "2026-11-03"
SHELL_LIMIT = 320_000      # the shell of a state that has its lists alone (raised from 300,000 at v4.0.088: the general code Ohio and Michigan needed brought it to 301-304 KB, about 78 KB as the server sends it)
SHELL_LIMIT_EXTRAS = 380_000      # ... and of a state that has every extra, polls and markets included (the map's own script is a file beside it, fetched when a map opens). Raised from 345,000 at v4.0.087: the five finished states sit at 350 to 366 KB (about 95 KB as the server sends it, compressed), and the warning should mean growth, not the settled size
# The parts of the page only a state with extras needs sit between these marks in PAGE and are left out of every other
# state's page, so a state without the data keeps the page (and the weight) it had; the "plain" part holds what stands
# in for them there.
EXTRAS_PART = re.compile(r"/\* <extras> \*/\n?(.*?)/\* </extras> \*/\n?", re.S)
PLAIN_PART = re.compile(r"/\* <plain> \*/\n?(.*?)/\* </plain> \*/\n?", re.S)


def page_for(extras):
    """The page's template, with or without the parts only a state with extras needs."""
    keep, drop = (EXTRAS_PART, PLAIN_PART) if extras else (PLAIN_PART, EXTRAS_PART)
    return drop.sub("", keep.sub(lambda m: m.group(1), PAGE))
DATA_WARN = 3_000_000      # a state's data file past this is said out loud by the build

# What a state can have beyond its lists (John, 2026-10-01; Minnesota first). Each is read only where it is there, so a
# state without it keeps the page it had: the map files (ballot_geo/<code>/, with index.json's own account of them),
# what a candidate's card may show beyond the list (the sl_websites, sl_found_facts, sl_issues and sl_photos tables,
# whose contract is ballot/local_sites.py's), the parties' own endorsement lists and how each place voted in past
# partisan elections (ballot/lean/), and the polls and prediction markets of its statewide races (ballot/polls/,
# ballot/odds_state_<code>.json and the snapshot ballot/odds.py keeps of them).
GEO_DIR = os.path.join(HERE, "ballot_geo")
LEAN_DIR = os.path.join(HERE, "ballot", "lean")
POLLS_DIR = os.path.join(HERE, "ballot", "polls")
ODDS_STATE = os.path.join(HERE, "ballot_cache", "odds", "odds_state_2026.json")
WHO_TABLES = ("sl_websites", "sl_found_facts", "sl_issues", "sl_photos")
FOUND_KINDS = ("official", "campaign", "secondary")
# an address a reader should not be sent to: sl_site_checks.status says what happened when the site was read
DEAD_SITE = re.compile(r"no such address|HTTP 40[4]|HTTP 410|holding page|social media page|names the candidate", re.I)

# What this page takes from build_ballot_dev.PAGE, name -> (where it begins, where it ends): the ballot pages' own
# stylesheet (its second <style>), the script that folds a page's sources (one closed fold, a closed fold inside it
# for each kind of source, a long list broken up again), so both kinds of ballot page fold their sources the same way,
# and the polls and betting markets of a race (the two tabs above the cards, the notice before a market, the helplines),
# so a statewide race here shows them exactly as a race for Congress does.
BALLOT_BORROWED = {"BALLOT_CSS": (":root{--pR:var(--rep)", "</style>\n</head>"),
                   "SOURCEFOLD": ("/* ---------- source folds", "/* ---------- end of source folds ---------- */"),
                   "MARKETS": ("/* ---------- betting markets: information only", "/* ---------- maps: the districts on the ballot")}


def borrow_ballot(name):
    start, end = BALLOT_BORROWED[name]
    page = build_ballot_dev.PAGE
    if page.count(start) != 1:
        raise SystemExit(f"build_ballot_state_dev: the Congress ballot page (build_ballot_dev.PAGE) no longer has exactly one '{start}' "
                         f"(it has {page.count(start)}). This page borrows the part called {name} from there; update BALLOT_BORROWED to match.")
    i = page.index(start)
    j = page.find(end, i)
    if j < 0:
        raise SystemExit(f"build_ballot_state_dev: could not find where the Congress ballot page's {name} part ends ('{end.strip()}'). "
                         "Update BALLOT_BORROWED in build_ballot_state_dev.py.")
    return page[i:j]


# A ballot runs from the top down: statewide offices, the Legislature, then county, conservation district, city or town,
# township, school, hospital and other district offices, and the courts last. Inside a level the offices keep this
# order, then jurisdiction, district and seat. Every office kind the database holds is placed here (the executive and
# the board before the row officers in a county; the mayor before the council in a city; the higher court before the
# lower, the prosecutors after the judges). A kind that is not here yet loses nothing: it keeps its own office title,
# is listed after the kinds of its level that are, and the build names it so that it can be placed.
LEVELS = ["statewide", "legislature", "county", "soil_water", "city", "township", "school", "hospital", "other", "court"]
LEVEL_KINDS = {
    "statewide": ["governor", "lieutenant_governor", "secretary_of_state", "state_auditor", "attorney_general", "state_treasurer", "comptroller",
                  "state_controller", "chief_financial_officer", "secretary_of_agriculture", "agriculture_commissioner", "tax_commissioner",
                  "insurance_commissioner", "labor_commissioner", "land_commissioner", "public_service_commissioner", "public_utilities_commissioner",
                  "corporation_commissioner", "railroad_commissioner", "state_mine_inspector", "school_and_public_lands_commissioner",
                  "superintendent_of_public_instruction", "state_board_of_education", "public_education_commission", "university_board",
                  "board_of_equalization", "executive_council", "governors_council", "oha_trustee"],
    "legislature": ["state_senate", "state_house"],
    # the executive and the board, the officers who keep the money and the records, the assessors and collectors, the
    # attorney and the sheriff's side, then the county's own judges and the offices elected by precinct or district
    "county": ["county_executive", "county_judge", "county_board_chair", "county_commissioner", "county_council", "county_budget_committee",
               "county_charter_commission", "county_auditor_treasurer", "county_auditor", "county_treasurer", "county_treasurer_recorder",
               "county_treasurer_recorder_clerk_of_court", "county_finance_officer", "county_clerk", "county_and_district_clerk", "clerk_of_court",
               "county_recorder", "county_recorder_clerk_of_court", "register_of_deeds", "register_of_wills", "register_of_probate", "county_assessor",
               "revenue_commissioner", "commissioner_of_revenue", "tax_assessor_collector", "tax_collector", "assistant_tax_assessor",
               "assistant_tax_collector", "license_commissioner", "racing_commissioner", "county_attorney", "commonwealths_attorney", "district_attorney", "sheriff",
               "sheriff_tax_assessor_collector", "jailer", "coroner", "high_bailiff", "county_court_at_law", "probate_court", "probate_judge",
               "judge_of_probate", "assistant_judge", "magistrate", "justice_of_the_peace", "constable", "county_engineer", "county_surveyor",
               "county_community_development_director", "county_elections_director", "county_school_trustee", "county_park"],
    "soil_water": ["soil_water"],
    "city": ["mayor", "vice_mayor", "council", "city_recorder", "city_clerk", "city_treasurer", "city_clerk_treasurer", "police_chief", "city_prosecutor",
             "justice_of_the_peace", "utility_board", "other"],
    "township": ["town_supervisor", "town_clerk", "town_treasurer", "town_clerk_treasurer", "justice_of_the_peace"],
    "school": ["school_superintendent", "school_board", "college_board"],
    "hospital": ["hospital_board"],
    "other": ["college_board", "utility_board", "water_board", "watershed_board", "sanitary_board", "public_service_board", "fire_board", "port_board",
              "highway_board", "development_district_board", "extension_council", "lighting_board", "lake_board", "county_court_at_law", "district_attorney", "solicitor", "other"],
    # the higher court before the lower, the courts of general jurisdiction before the limited ones, the prosecutors and
    # the court's officers after the judges
    "court": ["supreme_court", "supreme_court_retention", "court_of_criminal_appeals", "court_of_civil_appeals", "court_of_appeals",
              "court_of_appeals_retention", "appellate_court", "appellate_court_retention", "superior_court", "superior_court_retention",
              "circuit_court", "common_pleas_court", "chancery_court", "trial_court", "district_court", "district_court_retention", "parish_court", "family_court",
              "juvenile_court", "juvenile_court_retention", "orphans_court", "district_magistrate", "magistrate", "magistrate_retention",
              "metropolitan_court", "metropolitan_court_retention", "municipal_court", "city_court", "district_attorney", "commonwealth_attorney",
              "city_marshal", "constable"]}
KINDS = list(dict.fromkeys(k for lv in LEVELS for k in LEVEL_KINDS[lv]))      # every kind that is placed, level by level
KIND_RANK = {k: i for i, k in enumerate(KINDS)}


def kind_rank(level, kind):
    """Where an office sits inside its level: by the level's own order; a kind placed under another level comes after
    those, in the order of the whole list (Minnesota's utility board elected by a city); a kind not placed anywhere last."""
    own = LEVEL_KINDS.get(level) or []
    return own.index(kind) if kind in own else len(own) + KIND_RANK.get(kind, len(KINDS))


LOCAL = {"city": "M", "township": "M", "school": "S", "hospital": "H", "other": "X"}
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
HOLDER_WORDS = {"D": "Democratic-Farmer-Labor", "DFL": "Democratic-Farmer-Labor", "R": "Republican", "REP": "Republican"}      # Minnesota's holder column
# what the home page calls the courts a state's list holds, in the order above (retention votes count under their court)
COURTS = {"supreme_court": "the Supreme Court", "court_of_criminal_appeals": "the Court of Criminal Appeals",
          "court_of_civil_appeals": "the Court of Civil Appeals", "court_of_appeals": "the Court of Appeals", "appellate_court": "the Appellate Court",
          "superior_court": "the superior courts", "circuit_court": "the circuit courts", "common_pleas_court": "the courts of common pleas",
          "chancery_court": "the chancery courts", "trial_court": "the trial courts", "district_court": "the district courts", "family_court": "the family courts",
          "parish_court": "the parish courts", "juvenile_court": "the juvenile courts", "orphans_court": "the orphans&rsquo; courts",
          "district_magistrate": "district magistrate judges", "magistrate": "magistrate judges", "metropolitan_court": "the Metropolitan Court",
          "municipal_court": "the municipal courts", "city_court": "the city courts", "district_attorney": "district attorneys",
          "commonwealth_attorney": "commonwealth&rsquo;s attorneys", "city_marshal": "city marshals"}

# The local conventions of ballot/check_local.py: a city, town, village or township is <ST>-M-<key>, a school district
# <ST>-S-<key>, a hospital district <ST>-H-<key>, any other district <ST>-X-<key>; a county is its five-digit code.
# Minnesota's rows keep their older, shorter ids (a bare county subdivision code, ISD0001, HD00310) and their own reading.
NEW_ID = re.compile(r"^([A-Z]{2})-([MSHX])-([A-Za-z0-9][A-Za-z0-9-]*)$")
COUNTY_DIR = os.path.join(HERE, "states_cache", "local_counties")      # county lines made here for the states that have none yet
COUNTY_ZIPS = ("cb_2024_us_county_500k.zip", "cb_2023_us_county_500k.zip")      # the Bureau's national county file, as states/load_counties.py names it
MUNI_WORDS = ("city", "town", "village", "borough", "township")      # what a place's own name says it is
MUNI_PLURAL = {"city": "cities", "town": "towns", "village": "villages", "borough": "boroughs", "township": "townships"}

# the last check on every piece of text that reaches the page
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                    r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")


# A source's words without the names of this kit's own files (John, 2026-10-01): a reader needs the agency and the
# record, not how the site is put together. The loaders' source rows name the database a roster was loaded into and
# sometimes a program; those names are taken out here, where every state's sources pass on their way to the page.
FILE_PHRASE = re.compile(r",?\s*\(?\bas\s+(?:it\s+is\s+)?(?:loaded\s+into\s+)?[\w./\\-]+\.(?:sqlite|json)(?:\s+holds\s+(?:it|them))?\)?", re.I)
FILE_NAME = re.compile(r"\b[\w./\\-]+\.sqlite\b")
PROGRAM_NAME = re.compile(r"\b[\w./\\-]+\.py\b")


def plain_source(text):
    if not text:
        return text
    t = FILE_PHRASE.sub("", str(text))
    t = FILE_NAME.sub("the site's own records", t)
    t = PROGRAM_NAME.sub("the site's own reader", t)
    return re.sub(r"\s{2,}", " ", t).strip()


class Guard:
    """Drops any text that looks like contact details, and says which race it came from, never what it said."""

    def __init__(self):
        self.dropped = defaultdict(set)

    def ok(self, text, race, what, strict=False):
        if text is None or text == "":
            return text
        t = str(text)
        bad = EMAIL.search(t) or PHONE.search(t) or WEB.search(t)
        if strict and not bad:
            bad = STREET.search(t) or ZIP.search(t)
        if bad:
            self.dropped[what].add(race)
            return None
        return t

    def found(self, text, race, what):
        """The words of a found fact (an office held, a party unit, a heading, a quote, who states it). A page's name can
        be its address (lrl.mn.gov), so a web address is no reason to drop these; an e-mail address, a phone number, a
        post office box or a ZIP code is."""
        if text is None or text == "":
            return text
        t = str(text)
        if EMAIL.search(t) or PHONE.search(t) or POBOX.search(t) or ZIP.search(t):
            self.dropped[what].add(race)
            return None
        return t

    def report(self, code):
        for what, races in sorted(self.dropped.items()):
            ids = sorted(races)
            print(f"  {code} privacy check: left out {len(ids)} {what} that looked like contact details (races: {', '.join(ids[:8])}{' ...' if len(ids) > 8 else ''})")


def ddist(d):
    """A legislative district as the maps name it: 12, 12A (no leading zeros, capital letter)."""
    return re.sub(r"^0+(?=\d)", "", str(d or "").strip().upper())


def county_list(v, known):
    """county_ids as a sorted list of three-digit FIPS codes."""
    if v in (None, ""):
        return []
    arr = v
    if isinstance(v, str):
        try:
            arr = json.loads(v)
        except ValueError:
            arr = re.findall(r"\d+", v)
    if not isinstance(arr, (list, tuple)):
        arr = [arr]
    out = set()
    for x in arr:
        s = re.sub(r"\D", "", str(x))
        if s:
            out.add(s.zfill(3)[-3:])
    return sorted(out, key=lambda f: (f not in known, f))


def mcd_key(v):
    s = re.sub(r"\D", "", str(v or ""))
    return s[-5:].zfill(5) if s else ""


def school_key(v):
    """A school district's key keeps its type, because the numbers are not unique across types (Minneapolis is SSD 1,
    Aitkin ISD 1): ISD0001 -> ISD1, SSD0001 -> SSD1, CSD0323 -> CSD323; a bare number is taken as an ISD."""
    s = re.sub(r"[\s#.:-]", "", str(v or "").upper())
    m = re.fullmatch(r"(ISD|SSD|CSD|IS|SD|ID)?0*(\d+)", s)
    if not m:
        return s
    return {None: "ISD", "IS": "ISD", "SD": "ISD", "ID": "ISD"}.get(m.group(1), m.group(1)) + m.group(2)


def other_key(v):
    return re.sub(r"\s+", "", str(v or "").strip().upper())


def place_kind(kind):
    k = (kind or "").lower()
    if "school" in k or k in ("isd", "sd", "ssd"):
        return "S"
    if "hospital" in k:
        return "H"
    if "county" in k and "sub" not in k:
        return "C"
    if any(w in k for w in ("mcd", "cousub", "city", "town", "municip", "place", "unorg")):
        return "M"
    return "X"


def key_for(kind, v):
    return mcd_key(v) if kind == "M" else school_key(v) if kind == "S" else other_key(v)


def county_names(name):
    """A county's name as the page keeps it: (the short name, the whole name where it is not "<short> County").
    Virginia's independent cities ("Alexandria city"), Louisiana's parishes and Alaska's boroughs keep their own word;
    a bare name ("Adams") is a county."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    m = re.fullmatch(r"(.+?)\s+County", name)
    if m:
        return m.group(1), None
    m = re.fullmatch(r"(.+?)\s+(Parish|Borough|Census Area|Municipality|City and Borough|Planning Region|city)", name)
    if m:
        return m.group(1), name
    if re.search(r"\bCity$", name):
        return name, name                                         # Carson City, a county in its own right
    return name, None


def county_kind(full):
    """What a county-equivalent is called, from its own name: county, parish, borough, census area, municipality, city."""
    m = re.search(r"\b(County|Parish|City and Borough|Borough|Census Area|Municipality|Planning Region|city|City)$", full or "")
    return {"city and borough": "borough"}.get(m.group(1).lower(), m.group(1).lower()) if m else "county"


def muni_word(name):
    """What a place's own name says it is: Adairville city, Abingdon town, Bald Head Island village, Aitkin township."""
    m = re.match(r"(city|town|village|borough|township) of\b", name or "", re.I) or re.search(r"\b(city|town|village|borough|township)$", name or "", re.I)
    return m.group(1).lower() if m else ""


_county_lines = {}


def county_lines(code):
    """A state's county lines in the site's map space, with each county's name as the Census Bureau writes it. A file
    next to this script (local_<code>_counties.json: Minnesota's, written by run_local.py) is used as it is; otherwise the
    one in states_cache/local_counties/, made here when it is missing with states/load_counties.py's own reader, from the
    Bureau's national county file already in states_cache/census/ (same projection, same tolerance, same layout).
    Nothing is downloaded. With no lines the answer is {} and the page offers the list of counties without a map."""
    lc = code.lower()
    if lc in _county_lines:
        return _county_lines[lc]
    paths = [os.path.join(HERE, f"local_{lc}_counties.json"), os.path.join(COUNTY_DIR, f"local_{lc}_counties.json")]
    for path in paths:
        if os.path.exists(path):
            try:
                d = json.load(open(path, encoding="utf-8"))
            except ValueError:
                continue
            if d.get("counties"):
                _county_lines[lc] = d
                return d
    out = {}
    for name in COUNTY_ZIPS:
        src = os.path.join(HERE, "states_cache", "census", name)
        if not os.path.exists(src):
            continue
        try:
            from albers_usa import AlbersUsa                      # the same projection every map on the site uses
            from states.load_counties import read_counties
            from states.load_sld import Q
            proj = AlbersUsa()
            shapes, info, points = read_counties(src, str(place(code)["fips"]), lambda lon, lat: proj(lon, lat), 0.006)
        except Exception as e:      # noqa: BLE001  no lines is not a failure: the page lists the counties
            print(f"  {code}: the county lines could not be made from {name} ({type(e).__name__}: {e}); the page lists the counties without a map")
            break
        if not shapes:
            continue
        year = name[3:7]
        out = {"q": Q, "counties": shapes, "info": info, "vintage": f"{year} Census Bureau cartographic boundary file (counties, 1:500,000)",
               "source": {"file": name, "url": f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/{name}",
                          "sha256": hashlib.sha256(open(src, "rb").read()).hexdigest()},
               "generated": dt.date.today().isoformat()}
        os.makedirs(COUNTY_DIR, exist_ok=True)
        with open(paths[1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(out, separators=(",", ":")))
        print(f"  {code}: made the county lines from {name} ({len(shapes)} counties, {points:,} points): {os.path.relpath(paths[1], HERE)}")
        break
    _county_lines[lc] = out
    return out


def roster_links(path, P):
    """Which ids are sitting legislators (the member page) and statewide officials (the official page) on the state side.
    A legislator's chamber is named as the state names it (the Assembly in Wisconsin), not as the roster files it."""
    links = {}
    if not os.path.exists(path):
        return links
    words = {"Senate": P["upper"]["name"], "House": (P.get("lower") or {}).get("name", "House"), "Legislature": "Legislature"}
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    if has("legislators"):
        for bid, ch, d in con.execute("SELECT bioguide_id, chamber, district FROM legislators WHERE is_current = 1"):
            links[bid] = ["member", words.get(ch, ch or ""), ddist(d)]
    if has("officials"):
        for bid, label in con.execute("SELECT bioguide_id, office_label FROM officials"):
            links.setdefault(bid, ["official", label or ""])
    con.close()
    return links


def election_name(key, cands):
    if key == "general":
        return "General election"
    if key in build_ballot_dev.ELECTION_NAMES:
        return build_ballot_dev.ELECTION_NAMES[key]
    if key.startswith("primary-"):
        p = next((c.get("p") for c in cands if c.get("p")), None)
        return f"{p} primary" if p else f"{key[8:]} primary"
    return key


def compact(d, keep=()):
    return {k: v for k, v in d.items() if k in keep or v not in (None, "", [], {}, 0)}


def number_word(n):
    words = "no one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen".split()
    return words[n] if 0 <= n < len(words) else f"{n:,}"


def day_words(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%B} {d.day}"


def and_list(items):
    items = [i for i in items if i]
    if len(items) < 2:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def poss(s):
    """the Secretary of State's; the Department of Elections' (a name that ends in s takes the apostrophe alone)."""
    return s + ("&rsquo;" if s.endswith("s") else "&rsquo;s")


def lines_for(code):
    path = os.path.join(HERE, f"state_{code.lower()}_districts.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"q": 400, "upper": {}, "lower": {}, "vintage": ""}


def congress_counts(code):
    """How many U.S. House and Senate races the state has on the same ballot, for one sentence (read-only)."""
    if not os.path.exists(FED_DB):
        return {}
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    try:
        rows = dict(con.execute("SELECT office, COUNT(*) FROM races WHERE state = ? AND level = 'federal' GROUP BY office", (code,)).fetchall())
    except sqlite3.Error:
        rows = {}
    con.close()
    return {"house": rows.get("U.S. House", 0), "senate": rows.get("U.S. Senate", 0)}


def leg_race_key(d, have):
    """The race for a district on the map: its own, or where the lines split a district the list elects whole (North
    Dakota's 9A and 9B, both elected as District 9), the whole district's."""
    return d if d in have else (re.sub(r"[A-Z]$", "", d) if re.sub(r"[A-Z]$", "", d) in have else None)


# ---------------------------------------------------------------- what a state can have beyond its lists

_geo = {}


def geo_for(code):
    """A state's map files (ballot_geo/<code>/, made by a builder of their own): index.json, and every layer's shapes by
    id with the jurisdiction and district their races carry. None where a state has no such folder, or it cannot be read."""
    lc = code.lower()
    if lc in _geo:
        return _geo[lc]
    root, out = os.path.join(GEO_DIR, lc), None
    path = os.path.join(root, "index.json")
    if os.path.exists(path):
        try:
            idx = json.load(open(path, encoding="utf-8"))
            shapes = {}
            for L in idx.get("layers") or []:
                doc = json.load(open(os.path.join(root, L["file"]), encoding="utf-8"))
                shapes[L["kind"]] = {g["id"]: g.get("properties") or {} for g in doc["objects"][L["kind"]]["geometries"]}
            if shapes and idx.get("counties") and idx.get("transform"):
                out = {"root": root, "index": idx, "shapes": shapes, **geo_words(idx, shapes), "said": precincts_say(root, idx, shapes)}
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"  {code}: the map files in ballot_geo/{lc}/ could not be read ({type(e).__name__}: {e}); the page is built without them")
    _geo[lc] = out
    return out


def precincts_say(root, idx, shapes):
    """The districts a state's precincts name that no layer draws (a water development district in South Dakota): for
    each such property the files set out in index.json, the ids its precincts carry, what the files call it, and whether
    the precincts also name the part of it they lie in (<property>_area). A contest whose jurisdiction is one of those
    ids can then be put on a located reader's ballot by the precinct's own word, with no shape on the map. Only
    properties that hold a single id are read; names, counts and shares are not ids and match no jurisdiction."""
    told = ((idx.get("format") or {}).get("precinct_properties") or {})
    keys = [k for k in told if k not in shapes and k not in ("name", "county", "precinct", "split", "c")
            and not k.endswith(("_pct", "_area", "_all", "_edge", "_out", "_said"))]
    out = {k: {"ids": set(), "area": False} for k in keys}
    if not keys:
        return {}
    for c in idx.get("counties") or []:
        try:
            doc = json.load(open(os.path.join(root, c["file"]), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for obj in doc.get("objects", {}).values():
            for g in obj.get("geometries") or []:
                p = g.get("properties") or {}
                for k in keys:
                    if isinstance(p.get(k), str) and p[k]:
                        out[k]["ids"].add(p[k])
                        out[k]["area"] = out[k]["area"] or bool(p.get(f"{k}_area"))
    for k in keys:
        out[k]["word"] = re.sub(r"^the\s+", "", re.split(r"\s*\(|\s+(?:holding|that holds|with)\s+(?:most|the most|the largest)\b", str(told.get(k) or ""))[0]).strip()
    return {k: v for k, v in out.items() if v["ids"] and v["word"]}


def race_said(geo, jid):
    """"<property>:<id>" where the map's precincts name a contest's jurisdiction and no layer draws it; else None."""
    jid = str(jid or "").strip()
    for k, v in sorted((geo.get("said") or {}).items()):
        if jid and jid in v["ids"]:
            return f"{k}:{jid}"
    return None


def place_shape(geo, level, jid, district):
    """"mcd:<id>" for a city's or township's contest elected by a ward or district the map has no lines for, where the
    map does have the place itself: the page can then tell who lives in the place, if not in which part of it."""
    jid = str(jid or "").strip()
    return f"mcd:{jid}" if level in ("city", "township") and district not in (None, "") and jid in geo["shapes"].get("mcd", {}) else None


# What a state's map files call their own parts, where the page's usual words (Minnesota's, the first state to have
# such files) would be the wrong ones: index.json's own account of a precinct's properties says it.
GEO_SAID = {"com": "county commissioner district", "ward": "council district", "judicial": "judicial district", "swcd": "soil and water district"}


def geo_words(idx, shapes):
    """What a state's map files say of themselves, read from index.json and the layers and never from the state's name:
    "unit", what the smallest voting area is called there (a precinct; a ward in Wisconsin); "words", what the files
    call a kind of district where that is not the page's usual word; "muni", what the names of the map's cities, towns,
    villages and townships say they are; "county_keys", {the map's id for a county: the three digits the page files a
    county under} where the two differ."""
    said = ((idx.get("format") or {}).get("precinct_properties") or {})
    m = re.match(r"the (\w+)['’]s name", str(said.get("name") or ""))
    unit = str(idx.get("unit") or (m.group(1) if m else "precinct")).lower()
    words = {}
    for kind, usual in GEO_SAID.items():
        # what comes before a colon says where or how the property is given ("list:", "Cuyahoga County only:", "list, in a
        # city whose wards are drawn:"); the name of the thing follows it
        t = re.sub(r"^[^:]*:\s*", "", str(said.get(kind) or "")).strip()
        # the name of the thing alone: not the clause that says how a precinct comes by it ("... holding most of the precinct")
        t = re.sub(r"^the\s+", "", re.split(rf"\s+the {re.escape(unit)} lies in|\s+(?:holding|that holds|with)\s+(?:most|the most|the largest)\b|\s*\(", t)[0]).strip()
        t = re.sub(r"districts$", "district", t)
        if t and t.lower() != usual:
            words[kind] = t
    names = Counter(muni_word(p.get("name")) for p in (shapes.get("mcd") or {}).values())
    keys = {}
    for c in idx.get("counties") or []:
        three = re.sub(r"\D", "", str(c.get("fips") or c.get("id") or ""))[-3:]
        if three and str(c.get("id")) != three:
            keys[str(c["id"])] = three
    # a kind of place that lies inside another, whose voters vote in both, where the files' own note on places says so
    # ("a voter in a village is a voter of the township too"): [the inner kind, the kind around it]
    inside = re.search(r"\ba voter (?:in|of) an? (\w+) is a voter (?:in|of) the (\w+) too\b", str((idx.get("notes") or {}).get("places") or ""), re.I)
    return {"unit": unit, "words": words, "muni": [w for w in MUNI_WORDS if names.get(w)], "county_keys": keys,
            "within": [inside.group(1).lower(), inside.group(2).lower()] if inside else None}


def race_shape(geo, code, level, kind, jid, jur, district, counties=None):
    """The shape that draws a contest's place, as "layer:id", by the ids the map files set out in index.json under
    "format" (a county is its code; a ward <place>|<district>; a commissioner or park district <county>|<district>; a
    conservation district by its supervisor district, its name or the county's only one). None where no layer has it:
    the contest keeps its page, and the map says nothing about it."""
    S = geo["shapes"]
    jid = str(jid or "").strip()
    d = str(district).strip() if district not in (None, "") else ""
    hit = None
    if level == "statewide" or (kind in ("supreme_court", "court_of_appeals") and not d):
        hit = ("state", code)
    elif kind == "state_senate":
        hit = ("senate", ddist(d))
    elif kind == "state_house":
        hit = ("house", ddist(d))
    elif kind == "district_court" or (level == "court" and jid in S.get("judicial", {})):
        # a court elected by a district the map draws under the contest's own jurisdiction id (a district court's
        # judicial district; a court of appeals district that is a group of counties)
        hit = ("judicial", jid)
    elif kind in ("county_commissioner", "county_council"):      # the county's board, whatever the county calls it
        # a board seat's own district; the whole county where the seat has no district (elected at large), or where the
        # map files' own account of the county's plan says its districts are where members must live and every voter
        # of the county elects each of them. A district the files have no lines for stays unplaced, and the page says so.
        plan = ((geo["index"].get("supervisor_plans") or {}).get(jid) or {})
        whole = not d or (f"{jid}|{d}" not in S.get("com", {}) and plan.get("plan") == 2 and d in (plan.get("districts") or []))
        hit = ("county", jid) if whole else ("com", f"{jid}|{d}")
    elif kind == "county_park":
        hit = ("park", f"{jid}|{d}")
    elif level == "county":
        hit = ("county", jid)
    elif level == "soil_water":
        own = sorted(i for i, p in S.get("swcd", {}).items() if p.get("j") == jid)
        by_d = [i for i in own if d and S["swcd"][i].get("d") == d]
        by_n = [i for i in own if S["swcd"][i].get("jn") and S["swcd"][i]["jn"] == jur]
        whole = [i for i in own if S["swcd"][i].get("d") is None]
        hit = ("swcd", by_d[0]) if by_d else ("swcd", by_n[0]) if by_n else ("swcd", whole[0]) if len(whole) == 1 else None
    elif level in ("city", "township"):
        if not d and jid not in S.get("mcd", {}):
            # a list can file a place under a code the map does not have (a township the ballot names and an older
            # Census list does not): the one shape of the very same name whose middle lies inside the contest's county
            boxes = [c["bbox"] for c in geo["index"].get("counties") or [] if str(c.get("id")) in (counties or []) and c.get("bbox")]
            same = [i for i, p in S.get("mcd", {}).items() if str(p.get("name") or "").casefold() == str(jur or "").strip().casefold() and p.get("c")
                    and any(b[0] <= p["c"][0] <= b[2] and b[1] <= p["c"][1] <= b[3] for b in boxes)]
            jid = same[0] if len(same) == 1 and jur else jid
        hit = ("ward", f"{jid}|{d}") if d else ("mcd", jid)
    elif level == "school":
        hit = ("school", jid)
    elif level == "hospital":
        hit = ("hospital", jid)
    elif level == "court" and jid:      # a court of one city, town or county (a municipal court): the place itself
        hit = ("mcd", jid) if jid in S.get("mcd", {}) else ("county", jid) if jid in S.get("county", {}) else None
        if not hit and not d and len(counties or []) == 1:
            # a court of one county that the list files under an id of its own (a county's probate court): the county,
            # where the list ties the court to that county alone and the court's own name begins with the county's
            named = [str(c.get("id")) for c in geo["index"].get("counties") or []
                     if re.sub(r"\D", "", str(c.get("id")))[-3:] == str(counties[0]).zfill(3)[-3:]
                     and str(jur or "").casefold().startswith(re.sub(r"\s+county$", "", str(c.get("name") or ""), flags=re.I).casefold() + " county ")]
            hit = ("county", named[0]) if len(named) == 1 else None
    elif level == "other" and jid in S.get("county", {}):      # a district that is the county itself (its id is the county's code)
        hit = ("county", jid)
    elif level == "other" and d and len(counties or []) == 1:
        # a district's seat that one county's voters fill, the seat named for that county and filed under it alone: the county
        named = [str(c.get("id")) for c in geo["index"].get("counties") or []
                 if str(c.get("name") or "").casefold() == d.casefold() and re.sub(r"\D", "", str(c.get("id")))[-3:] == str(counties[0]).zfill(3)[-3:]]
        hit = ("county", named[0]) if len(named) == 1 else None
    return f"{hit[0]}:{hit[1]}" if hit and hit[1] in S.get(hit[0], {}) else None


ZERO_WIDTH = re.compile("[﻿​‌‍⁠]")
POBOX = re.compile(r"\bP\.?\s?O\.?\s+Box\b", re.I)


def tidy(text):
    """A found text as it should print: no byte-order or zero-width marks; the mark a page's wrong encoding left between
    two letters read as the apostrophe it stood for, and dropped anywhere else; one space between words."""
    t = ZERO_WIDTH.sub("", str(text or ""))
    t = re.sub(r"(?<=\w)�(?=\w)", "’", t).replace("�", "")
    return re.sub(r"\s+", " ", t).strip()


def web_url(u):
    """A page's address, only as an address: http or https, no spaces, nothing that could close an attribute."""
    u = str(u or "").strip()
    return u if re.fullmatch(r"https?://[^\s\"'<>]+", u) else None


def roster_facts(code):
    """A sitting legislator's or statewide official's own record on the state side (the Open States roster the state
    pages use): birth date, terms served and the legislature's portrait, by the roster's id. Official records come first,
    as on the Congress pages; what the open web says is shown only where these are blank."""
    path, out = os.path.join(HERE, f"state_{code.lower()}.sqlite"), {}
    if not os.path.exists(path):
        return out
    try:
        from ballot.people import spans, state_chamber
    except Exception:      # noqa: BLE001  without the reader of terms the roster's facts are left out, never guessed
        return out
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    label, name = state_chamber(code), place(code)["name"]
    if has("legislators"):
        terms = defaultdict(list)
        if has("member_terms"):
            for sid, kind, start, end in con.execute("SELECT bioguide_id, type, start, end FROM member_terms"):
                terms[sid].append((kind, start, end))
        for sid, birthday in con.execute("SELECT bioguide_id, birthday FROM legislators WHERE is_current = 1"):
            out[sid] = compact({"dob": birthday if re.fullmatch(r"\d{4}-\d\d-\d\d", str(birthday or "")) else None,
                                "off": [[s["office"], s["start"], s["end"], 1 if s["unsure"] else 0] for s in spans(terms.get(sid, []), label)]})
    if has("officials"):
        for sid, lab, start in con.execute("SELECT bioguide_id, office_label, term_start FROM officials"):
            if lab:
                out.setdefault(sid, {}).setdefault("off", []).append([f"{name} {lab}", start or "", "", 0 if start else 1])
    if has("photos"):
        for sid, webp, url in con.execute("SELECT bioguide_id, webp, source_url FROM photos WHERE webp IS NOT NULL"):
            if sid in out and webp:
                out[sid]["photo"] = (bytes(webp), web_url(url))
    con.close()
    return out


NOMINEE = "convention nominee"      # the one kind of other support that is shown, in its own words (see endorsement_lists)


def endorsement_lists(code):
    """The parties' own endorsement lists (ballot/lean/<code>_endorsements.json): {(race, name): [[party, unit, address]]}
    for candidates on the November list, each line as one party page states it, and the pages themselves for the
    sources. Support a page itself says is not an endorsement, and what is held for a person to decide, stay out, with
    one exception that is shown apart and never as an endorsement: a record the file keeps under other_support with the
    kind "convention nominee" (a party's convention nominated the candidate for an office the ballot prints without a
    party, and the party's page does not use the word "endorsed") is returned third, in the same form, so that a page
    which shows one party's endorsement of its nominees does not pass over the other party's nomination of its own."""
    path = os.path.join(LEAN_DIR, f"{code.lower()}_endorsements.json")
    if not os.path.exists(path):
        return {}, [], {}
    try:
        d = json.load(open(path, encoding="utf-8"))
    except ValueError:
        return {}, [], {}
    by, nominated = defaultdict(list), defaultdict(list)
    for into, rows in ((by, d.get("endorsements") or []),
                       (nominated, [e for e in d.get("other_support") or [] if str(e.get("kind") or "").strip().lower() == NOMINEE])):
        for e in rows:
            url = web_url(e.get("url"))
            if not url or e.get("election") or not e.get("party") or not e.get("race_id") or not e.get("name"):
                continue      # 'election' marks a candidate who is on a primary list and not on the November one
            into[(e["race_id"], e["name"])].append([tidy(e["party"]), tidy(e.get("unit") or e["party"]), url])
    pages = [compact({"party": tidy(x.get("party")), "unit": tidy(x.get("unit")), "title": tidy(x.get("title")), "url": web_url(x.get("url")),
                      "read": x.get("read_on")}) for x in d.get("lists") or [] if web_url(x.get("url"))]
    return by, pages, nominated


def who_data(con, code, races, raw, guard, out_dir):
    """What a candidate's card may show beyond the list (John, 2026-10-01), by race and by name, each fact with the page
    that states it: {race: {name: {...}}} and what was counted. For the offices ballot/local_sites.py's `full` names
    (statewide offices, the Legislature, judges, county offices, mayors and councils, school boards): a photo, a birth
    date or year, public offices held, the government's own page about an officeholder, the campaign's website and its
    issue headings; and, kept for the nonpartisan ones only, a party's own endorsement, an earlier run or office under
    a party label, and the candidate's own words. For every other office: the campaign website the candidate filed,
    and nothing else. A sitting legislator's birth date, terms and portrait come from the state roster first.

      dob, off [[office, start, end, unsure]], ph, pc, pu, ps     the roster's own (ps "State roster"), or the photo chosen from
                                                                  the campaign's site (ps "Campaign")
      fb [year, date or "", who states it, address, kind]         a found birth year, only where the roster has none
      fo [[office, from, to, who, address, kind]]                 found offices
      op [address, who]                                           the government's own page about an officeholder
      web address; wf 1 when it was found on the open web rather than filed
      iss [address, [headings]]
      en [[party, unit, address]]; pp [[what, year, party, who, address, kind]]; ow [quote, address]

    Every address comes from an address column and is kept only as an address; every other text passes the last check
    for contact details; nothing is taken from a column this function does not name."""
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    like = f"2026-{code}-%"
    # a state has this once its candidates have been set out for research (its scope file beside the findings), or once
    # anything found is loaded: until the findings come, a sitting member's own record on the state roster is what shows
    scoped = os.path.exists(os.path.join(HERE, "ballot", "found_local", f"{code.lower()}_scope.json"))
    if not scoped and not any(has(t) and con.execute(f"SELECT 1 FROM {t} WHERE race_id LIKE ? LIMIT 1", (like,)).fetchone() for t in WHO_TABLES):
        return {}, {}, set()
    try:
        from ballot.local_sites import full
    except Exception:      # noqa: BLE001  the same rule, written out, when that module cannot be loaded
        full = lambda level, kind: level in ("statewide", "legislature", "court", "county", "school") or (level == "city" and kind in ("mayor", "council"))
    src_name = build_ballot_dev.found_source
    by_id = {r["id"]: r for r in races}
    fuller = {rid for rid, (level, kind) in raw.items() if full(level, kind)}
    on_list = {(r["id"], c["n"]): c for r in races for c in r["el"].get("general", [])}
    who, n = defaultdict(dict), Counter()
    P = lambda rid, name: who[rid].setdefault(name, {})
    text = lambda t, rid, what: guard.found(tidy(t), rid, what)

    # the roster first: a sitting member's own record
    roster = roster_facts(code) if any(c.get("m") for c in on_list.values()) else {}
    for (rid, name), c in on_list.items():
        R = roster.get(c.get("m") or "")
        if not R or rid not in fuller:
            continue
        p = P(rid, name)
        if R.get("dob"):
            p["dob"] = R["dob"]
        if R.get("off"):
            p["off"] = R["off"]
        if R.get("photo") and out_dir:
            rel = f"photos/m-{re.sub(r'[^A-Za-z0-9_-]', '', c['m'])}.webp"
            write_bytes(os.path.join(out_dir, rel), R["photo"][0])
            p.update(compact({"ph": rel, "ps": "State roster", "pc": "Official legislature portrait, via Open States", "pu": R["photo"][1]}))
            n["roster portraits"] += 1

    dead = set()
    if has("sl_site_checks"):
        http_only = {}
        for rid, name, url, status, final in con.execute("SELECT race_id, name, url, status, final_url FROM sl_site_checks WHERE race_id LIKE ?", (like,)):
            if DEAD_SITE.search(status or ""):
                dead.add((rid, name))
            elif str(final or "").startswith("http://") and str(url or "").startswith("https://"):
                http_only[(rid, name)] = "http://" + url[len("https://"):]
    else:
        http_only = {}
    if has("sl_websites"):
        for rid, name, url, source in con.execute("SELECT race_id, name, url, source FROM sl_websites WHERE race_id LIKE ?", (like,)):
            url = web_url(http_only.get((rid, name), url))
            found = not str(source or "").startswith("Filed with")
            if (rid, name) not in on_list or not url or (found and rid not in fuller):
                continue
            if (rid, name) in dead:
                n["websites left out (the address no longer leads to the campaign)"] += 1
                continue
            p = P(rid, name)
            p["web"] = url
            if found:
                p["wf"] = 1
            n["websites found" if found else "websites filed"] += 1
    if has("sl_found_facts"):
        cols = "race_id, name, field, year, date, office, from_year, to_year, party, unit, what, quote, source, url, kind"
        for rid, name, field, year, date, office, y0, y1, party, unit, what, quote, source, url, kind in con.execute(
                f"SELECT {cols} FROM sl_found_facts WHERE race_id LIKE ? ORDER BY race_id, name, field, from_year IS NULL, from_year, office, year", (like,)):
            url = web_url(url)
            if (rid, name) not in on_list or rid not in fuller or not url:
                continue
            p, np_race = P(rid, name), not by_id[rid]["pt"]
            who_says = text(src_name(source, url), rid, "names of sources")
            if field == "born" and kind in FOUND_KINDS and year and not p.get("dob") and "fb" not in p and who_says:
                whole = date if date and re.fullmatch(rf"{int(year)}-\d\d-\d\d", str(date)) and kind != "secondary" else ""      # a full date only from an official or campaign page
                p["fb"] = [int(year), whole, who_says, url, kind]
                n["birth years found"] += 1
            elif field == "office" and kind in FOUND_KINDS and office and who_says:
                office = text(office, rid, "offices held")
                if office:
                    to = "now" if str(y1 or "").lower() == "now" else (int(y1) if str(y1 or "").isdigit() else None)
                    p.setdefault("fo", []).append([office, int(y0) if str(y0 or "").isdigit() else None, to, who_says, url, kind])
                    n["offices found"] += 1
            elif field == "official_page" and kind == "official" and who_says and "op" not in p:
                p["op"] = [url, who_says]
            elif field == "endorsed_by" and kind == "party" and party and np_race:
                short = text(re.split(r",| \(", str(unit or party))[0], rid, "party units")
                if short:
                    p.setdefault("en", []).append([tidy(party), short, url])
            elif field == "past_party" and kind in FOUND_KINDS and what and np_race and who_says:
                what = text(what, rid, "earlier runs and offices")
                if what:
                    p.setdefault("pp", []).append([what, int(year) if str(year or "").isdigit() else None, tidy(party), who_says, url, kind])
                    n["earlier runs or offices under a party label"] += 1
            elif field == "own_words" and kind == "campaign" and quote and np_race and "ow" not in p:
                quote = text(quote, rid, "candidates' own words")
                if quote and len(quote) <= 300:
                    p["ow"] = [quote, url]
                    n["candidates' own words"] += 1
    if has("sl_issues"):
        for rid, name, url, topics in con.execute("SELECT race_id, name, url, topics FROM sl_issues WHERE race_id LIKE ?", (like,)):
            url = web_url(url)
            if (rid, name) not in on_list or rid not in fuller or not url or (rid, name) in dead:
                continue
            try:
                heads = [text(t, rid, "issue headings") for t in json.loads(topics or "[]")]
            except ValueError:
                continue
            heads = [h for h in dict.fromkeys(heads) if h and len(h) <= 90][:14]
            if heads:
                P(rid, name)["iss"] = [url, heads]
                n["issue pages"] += 1
    if has("sl_photos") and out_dir:
        for rid, name, webp, credit, url in con.execute("SELECT race_id, name, webp, credit, url FROM sl_photos WHERE race_id LIKE ?", (like,)):
            if (rid, name) not in on_list or rid not in fuller or not webp:
                continue
            p = P(rid, name)
            if p.get("ph"):
                continue      # the roster's portrait stays
            rel = f"photos/{hashlib.sha1(f'{rid}|{name}'.encode('utf-8')).hexdigest()[:14]}.webp"
            write_bytes(os.path.join(out_dir, rel), bytes(webp))
            p.update(compact({"ph": rel, "ps": "Campaign", "pc": text(credit, rid, "photo credits") or "From the campaign's own website", "pu": web_url(url)}))
            n["campaign photos"] += 1
    lists, pages, nominated = endorsement_lists(code)
    for key, found_by in (("en", lists), ("nom", nominated)):      # nom: nominated at a party's convention, said so and never as an endorsement
        for (rid, name), found in found_by.items():
            if (rid, name) not in on_list or rid not in fuller or by_id[rid]["pt"]:
                continue
            p = P(rid, name)
            for party, unit, url in found:
                unit = text(unit, rid, "party units")
                have = p.setdefault(key, [])
                same = next((e for e in have if e[0] == party and e[2] == url), None)
                if same and unit:
                    same[1] = unit      # the list's own name for the unit is the shorter one
                elif unit:
                    have.append([party, unit, url])
    for rid, people in who.items():
        for p in people.values():
            if p.get("en"):
                n["candidates a party has endorsed (nonpartisan offices)"] += 1
            if p.get("nom"):
                n["candidates a party's convention nominated (offices printed without a party)"] += 1
    out = {rid: {name: p for name, p in people.items() if p} for rid, people in who.items()}
    out = {rid: people for rid, people in sorted(out.items()) if people}
    used = {e[2] for people in out.values() for p in people.values() for e in p.get("en", []) + p.get("nom", [])}
    out_pages = [x for x in pages if x.get("url") in used]
    return out, {"n": dict(n), "parties": out_pages}, fuller


def write_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) == len(data) and open(path, "rb").read() == data:
        return False
    with open(path, "wb") as fh:
        fh.write(data)
    return True


def votes_by(d):
    """"precinct" where a place-votes file's own account says its counts are precinct results (Wisconsin's are a bureau's
    ward tables of the clerks' reporting units, so there the page says "official results" and no more); else None."""
    return "precinct" if re.search(r"\bprecinct results\b", f"{d.get('what') or ''} {d.get('note') or ''}", re.I) else None


def votes_files(code, out_dir, geo):
    """How each place voted in past partisan elections (ballot/lean/<code>_place_votes.json: official precinct results
    added up by place, with the file's own note on what that is and is not), cut into small files a race's page fetches
    one of: data/votes/meta.json (the contests, the note, the sources with their notices) and one file for each kind of
    place, the cities and townships county by county. Keys are turned into the ids the page's races carry (a county's
    three digits; <county>|<district> for a commissioner district; the ward as the map names it). Returns what BOOT
    says about them, or None."""
    lc = code.lower()
    path = os.path.join(LEAN_DIR, f"{lc}_place_votes.json")
    if not os.path.exists(path):
        return None
    try:
        d = json.load(open(path, encoding="utf-8"))
        contests = d["contests"]
    except (ValueError, KeyError):
        return None
    fips = str(place(code).get("fips") or "")
    ids = [c["id"] for c in contests]
    sides = {c["id"]: [k for k, v in c.items() if isinstance(v, dict) and v.get("party") and v.get("ticket")] for c in contests}
    row = lambda cid, v: [int(v.get(k) or 0) for k in sides[cid]] + [int(v.get("other") or 0), int(v.get("total") or 0)]
    wards = set((geo or {}).get("shapes", {}).get("ward", {}))
    coms = set((geo or {}).get("shapes", {}).get("com", {}))

    def key_of(kind, key, pl):
        if kind == "county":
            return key[len(fips):] if fips and key.startswith(fips) and len(key) == len(fips) + 3 else key
        if kind == "commissioner":
            a, _, b = key.partition("-")
            if f"{a}|{b}" in coms:      # the map names the district by the county's whole code
                return f"{a}|{b}"
            return f"{a[len(fips):] if fips and a.startswith(fips) else a}|{b}"
        if kind == "ward":
            a, _, b = key.partition("-")
            fits = [f"{a}|{w} {b}" for w in ("Ward", "District", "Precinct") if f"{a}|{w} {b}" in wards]
            return fits[0] if len(fits) == 1 else None      # a ward the map does not name this way is left out, never guessed
        return key

    files, left = defaultdict(dict), Counter()
    for kind, places in (d.get("places") or {}).items():
        for key, pl in places.items():
            k2 = key_of(kind, key, pl)
            if not k2:
                left[kind] += 1
                continue
            few = set(pl.get("too_few") or [])
            entry = [pl.get("name") or "", [row(cid, pl["votes"][cid]) if cid in (pl.get("votes") or {}) else 0 for cid in ids]]
            if few:
                entry.append([ids.index(cid) for cid in ids if cid in few])
            if kind == "mcd":      # the cities and townships, county by county: a race's page fetches its own county's
                for c in pl.get("counties") or []:
                    files[f"mcd-{c[len(fips):] if fips and c.startswith(fips) else c}"][k2] = entry
            else:
                files[{"commissioner": "com"}.get(kind, kind)][k2] = entry
    # the file's note ends by telling a page what to do with a place's too_few list; the page does it, and says so in a reader's words
    note = re.sub(r";?\s*those contests are listed in the place's too_few, and a page should leave the split out\.?\s*$", ", so there the split is left out.",
                  str(d.get("note") or ""))
    meta = {"what": d.get("what"), "note": note, "generated": d.get("generated"),
            "few": d.get("too_few"), "not_given": (d.get("coverage") or {}).get("not_given"),
            "contests": [{"id": c["id"], "date": c.get("date"), "office": c.get("office"),
                          "sides": [[c[k].get("party"), c[k].get("ticket")] for k in sides[c["id"]]],
                          "state": row(c["id"], c["statewide"]) if c.get("statewide") else None} for c in contests],
            "kinds": {{"commissioner": "com"}.get(k, k): compact({"what": v.get("what"), "why_not": next((v[k] for k in sorted(v) if k.startswith("why_not")), None),"note": v.get("note")})
                      for k, v in (d.get("kinds") or {}).items()},
            "sources": [compact({"agency": plain_source(s.get("agency")), "title": plain_source(s.get("title")), "url": web_url(s.get("url")), "kind": s.get("kind"),
                                 "canvassed": s.get("canvassed"), "accuracy": s.get("accuracy"), "use": s.get("use"), "disclaimer": s.get("disclaimer")})
                        for s in d.get("sources") or []]}
    h = hashlib.sha1()
    base = os.path.join(out_dir, "data", "votes")
    for name, body in sorted([("meta", meta)] + list(files.items())):
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        write_if_changed(os.path.join(base, f"{name}.json"), text)
        h.update(text.encode("utf-8"))
    sizes = {name: len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) for name, body in files.items()}
    by = votes_by(d)
    return {"base": "data/votes/", "v": h.hexdigest()[:10], "by": by, "files": sorted(k for k in files if not k.startswith("mcd-")),
            "mcd": sorted(k[4:] for k in files if k.startswith("mcd-")), "_sizes": sizes, "_left": dict(left),
            "_src": [compact({"a": s.get("agency"), "t": s.get("title"), "u": s.get("url"), "k": s.get("kind")}) for s in meta["sources"] if s.get("agency")]}


HELD = re.compile(r"\bAsk John before showing\b", re.I)      # what the person who checked a market writes in its note when it is too thin to show


NAME_TAIL = re.compile(r"\s*\([^)]*\)\s*$|,?\s+(?:Jr\.?|Sr\.?|II|III|IV)\s*$", re.I)
PARTY_OUTCOME = re.compile(r"^(democrat|republican|independent|libertarian|green|constitution)(?:ic|s)?(?:\s+party)?$", re.I)


def on_november_list(label, race):
    """Whether an outcome a market lists stands for someone on a race's November list: its family name is a word of a
    listed candidate's name (a ticket's either name), or, where the outcome is a party and not a person ("Democratic
    party"), a candidate of that party is on the list. Letters only, so that a hyphen, an apostrophe or a mark a feed
    garbled does not part two spellings of one name."""
    letters = lambda w: re.sub(r"[^a-z]", "", w.lower())
    text = str(label or "").strip()
    while NAME_TAIL.search(text):
        text = NAME_TAIL.sub("", text).strip()
    cands = race.get("el", {}).get("general", [])
    party = PARTY_OUTCOME.match(text)
    if party:
        return any(str(c.get("p") or "").lower().startswith(party.group(1).lower()) for c in cands)
    family = letters(text.split()[-1]) if text.split() else ""
    if not family:
        return False
    for c in cands:
        if family in {letters(w) for w in re.split(r"[\s/]+", NAME_TAIL.sub("", str(c.get("n") or "")))}:
            return True
    return False


def polls_and_odds(code, races):
    """The polls and the prediction markets of a state's statewide races, by race id, as the Congress pages read
    theirs: ballot/polls/polls_<code>_state_2026.json (each poll checked against the pollster's own release) and the
    snapshot ballot/odds.py keeps of the markets named in ballot/odds_state_<code>.json. Statewide races only: a market
    on a county race waits for John's word, and so does one whose own note asks for it (HELD: too thinly traded to show
    without his say). ({} and {} where the state has neither file.) The third answer says whether the state has either
    file at all, so that a statewide race no market lists can say so; the fourth names the races a market does list and
    the page holds back, so that the page does not say of them that no market lists them."""
    lc = code.lower()
    # the races the whole state votes on: the statewide offices, and a court's seat that no district or county is named
    # for (a justice of the supreme court)
    statewide = {r["id"] for r in races if r["lv"] == "statewide" or (r["lv"] == "court" and not r.get("d") and not r.get("c") and not r.get("pk"))}
    polls, odds, any_file, held = {}, {}, False, []
    path = os.path.join(POLLS_DIR, f"polls_{lc}_state_2026.json")
    if os.path.exists(path):
        try:
            polls = {k: v for k, v in (json.load(open(path, encoding="utf-8")).get("races") or {}).items() if k in statewide}
            any_file = True
        except ValueError:
            polls = {}
    listed = os.path.join(HERE, "ballot", f"odds_state_{lc}.json")
    if os.path.exists(listed):
        any_file = True
        try:
            found = json.load(open(listed, encoding="utf-8"))
            names = set(found)
            lv = {r["id"]: r["lv"] for r in races}
            held = sorted(k for k, m in found.items() if k in lv and isinstance(m, dict) and (m.get("polymarket") or m.get("kalshi"))
                          and (k not in statewide or HELD.search(str(m.get("note") or ""))))
            snap = json.load(open(ODDS_STATE, encoding="utf-8")) if os.path.exists(ODDS_STATE) else {}
            odds = {k: v for k, v in snap.items() if k in statewide and k in names and k not in held
                    and any((v.get(m) or {}).get("rows") for m in ("polymarket", "kalshi"))}
            # a market the file names and the snapshot has no prices for yet (ballot/odds.py has not been run since the
            # file was written): the page shows nothing of it, and must not say that no market lists the race
            held = sorted(set(held) | {k for k, m in found.items() if k in statewide and k not in odds and isinstance(m, dict)
                                       and (m.get("polymarket") or m.get("kalshi"))})
            # an outcome a market lists that names nobody on the November list (someone who withdrew; a party with no
            # candidate there): no row is drawn for it, and the page says in one sentence that the market lists it
            by_id = {r["id"]: r for r in races}
            for k in list(odds):
                odds[k] = dict(odds[k])
                for m in ("polymarket", "kalshi"):
                    M = odds[k].get(m)
                    if not isinstance(M, dict) or not M.get("rows"):
                        continue
                    on = [row for row in M["rows"] if on_november_list(row[0], by_id[k])]
                    if len(on) != len(M["rows"]):
                        odds[k][m] = {**M, "rows": on, "off": [str(row[0]).strip() for row in M["rows"] if row not in on]}
                if not any((odds[k].get(m) or {}).get("rows") for m in ("polymarket", "kalshi")):
                    del odds[k]      # nothing of it can be drawn: the page says nothing of markets for the race
                    held = sorted(set(held) | {k})
        except ValueError:
            odds, held = {}, []
    return polls, odds, any_file, held


def geo_files(code, out_dir, geo):
    """The map's own files beside the page, in geo/: the layers, a file of precincts for each county and each school
    district's own lines, copied as they are (only when they change); index.json cut down to what the page reads; the
    reader that was built with the files; and the map's own script. Polling places are copied only when their file says
    they are loaded and were checked by a person; otherwise the page is told why they are not there, in the file's own
    words, with the state's own finder to send a reader to. Returns what BOOT says about the map."""
    src, dst, idx = geo["root"], os.path.join(out_dir, "geo"), geo["index"]
    school = idx.get("school") or {}
    names = [L["file"] for L in idx.get("layers") or []] + [c["file"] for c in idx.get("counties") or []] \
        + [str(school.get("files", "school/<id>.json")).replace("<id>", i) for i in school.get("ids") or []] + ["reader.js"]
    h, copied, total = hashlib.sha1(), 0, 0
    for rel in names:
        a = os.path.join(src, rel)
        if not os.path.exists(a):
            print(f"  {code}: the map file {rel} is named in index.json and is not there")
            continue
        data = open(a, "rb").read()
        total += len(data)
        h.update(rel.encode("utf-8"))
        h.update(hashlib.sha1(data).digest())
        copied += write_bytes(os.path.join(dst, rel), data)
    polls = {"status": "none"}
    pp = os.path.join(src, "polling_places.json")
    if os.path.exists(pp):
        try:
            d = json.load(open(pp, encoding="utf-8"))
        except ValueError:
            d = {}
        if d.get("status") == "loaded" and d.get("places"):
            body = {"finder": web_url(d.get("finder")), "source": d.get("source"), "precinct": d.get("precinct") or {}, "no_place": d.get("no_place") or {},
                    "places": [compact({"name": p.get("name"), "address": p.get("address"), "city": p.get("city"), "lonlat": p.get("lonlat"),
                                        "precincts": p.get("precincts")}) for p in d["places"]]}
            text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
            write_if_changed(os.path.join(dst, "polling_places.json"), text)
            h.update(text.encode("utf-8"))
            polls = compact({"status": "loaded", "file": "polling_places.json", "finder": web_url(d.get("finder")), "n": len(d["places"]),
                             "source": (d.get("source") or {}).get("title")})
        else:
            why = d.get("why") if d.get("status") == "waiting" else ("The state's list of polling places has been read and has not yet been checked by a "
                                                                    "person against the list itself, so it is not shown.")
            # a copy that is older than the election it would be shown for says so (its source's own "current to" date)
            upto = str((d.get("source") or {}).get("current_to") or "") if d.get("status") != "waiting" else ""
            if re.fullmatch(r"\d{4}-\d\d-\d\d", upto) and upto < str(d.get("election") or idx.get("election") or ""):
                day = dt.date.fromisoformat(upto)
                why += f" The copy read is current to {day:%B} {day.day}, {day.year}, and polling places can change before an election."
            polls = compact({"status": "waiting", "why": why, "finder": web_url(d.get("finder"))})
    slim = {"v": idx.get("v"), "state": code, "election": idx.get("election"), "built": idx.get("built"), "transform": idx.get("transform"),
            "bbox": idx.get("bbox"), "arc_kinds": idx.get("arc_kinds"), "tolerance_m": idx.get("tolerance_m"), "counts": idx.get("counts"),
            "counties": [{k: c[k] for k in ("id", "name", "bbox", "file", "bytes", "precincts") if k in c} for c in idx.get("counties") or []],
            "layers": [{k: L[k] for k in ("kind", "file", "bytes", "shapes", "good_to_zoom") if k in L} for L in idx.get("layers") or []],
            "school": {"files": school.get("files", "school/<id>.json")}, "notes": idx.get("notes"), "sources": idx.get("sources")}
    text = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    write_if_changed(os.path.join(dst, "index.json"), text)
    h.update(text.encode("utf-8"))
    write_if_changed(os.path.join(dst, "mapkit.js"), MAPKIT)
    h.update(MAPKIT.encode("utf-8"))
    sw = geo["shapes"].get("swcd", {})      # the conservation districts that are a whole county (the only one there, not a supervisor's own district)
    per_county = Counter(p.get("j") for p in sw.values())
    whole = sorted(i for i, p in sw.items() if p.get("d") is None and not p.get("jn") and per_county[p.get("j")] == 1)
    # a judicial district the files know by a name and not by a number (the East Central Judicial District): its name, by its id
    named = {i: p["name"] for i, p in geo["shapes"].get("judicial", {}).items() if p.get("name") and not re.search(r"\d", str(i))}
    own = compact({"unit": geo.get("unit") if geo.get("unit") != "precinct" else None, "words": geo.get("words"), "muni": geo.get("muni"),
                   "ck": geo.get("county_keys"), "names": {"judicial": named} if named else None, "within": geo.get("within")})      # the files' own words and county ids, where they are not the page's usual ones
    # Whose lines the smallest pieces are, and of which year, where they are not this election's own (the files give each
    # piece the year of its lines, as_of, and an older year than the election's): the files' own note on them, in a
    # reader's words (a sentence that names a field of the files is left for the fold of notices), said with the map
    as_of = re.search(r"\b((?:19|20)\d\d)\b", str(((idx.get("format") or {}).get("precinct_properties") or {}).get("as_of") or ""))
    if as_of and as_of.group(1) < str(idx.get("election") or "")[:4]:
        told = [s.strip() for s in re.split(r"(?<=[.!?])\s+", str((idx.get("notes") or {}).get("precincts") or "")) if s.strip() and not re.search(r"\b[a-z]+_\w+", s)]
        own["old"] = {"y": as_of.group(1), "t": told[:4]}
    return {"base": "geo/", "v": h.hexdigest()[:10], "kinds": [L["kind"] for L in idx.get("layers") or [] if L["kind"] != "state"], "polls": polls,
            "swWhole": whole, **own, "_copied": copied, "_files": len(names), "_bytes": total, "_index": len(text.encode("utf-8")), "_kit": len(MAPKIT.encode("utf-8"))}


def build(db, code, lines, out_dir=None):
    """Everything one state's page needs: (data, the page's words, warnings, candidate rows, the extras)."""
    lc = code.lower()
    P = place(code)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for t in ("sl_races", "sl_candidates", "sl_sources", "sl_places"):
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone():
            raise SystemExit(f"build_ballot_state_dev: {os.path.basename(db)} has no {t} table. Run the state and local ballot loader first.")
    guard = Guard()
    geo = geo_for(code)      # the map files, where the state has them: each race then names the shape that draws its place
    local = con.execute(f"SELECT COUNT(*) FROM sl_races WHERE state = ? AND level IN ({','.join('?' * len(LOCAL_LEVELS))})",
                        (code, *LOCAL_LEVELS)).fetchone()[0] > 0
    counties, cfull = {}, {}
    if local:      # the county pages: only where the list reaches the counties
        for f, info in (county_lines(code).get("info") or {}).items():
            counties[f] = info.get("name", f)
            full = (info.get("full") or "").strip()
            if full and full != f"{counties[f]} County":
                cfull[f] = full                                   # Alexandria city, Orleans Parish: not "<name> County"

    # Minnesota's county rows carry three-digit codes and its city codes are five digits; under the local conventions a
    # county is its five-digit code, and a local contest of the county itself has that code as its jurisdiction
    fips = str(P.get("fips") or "")
    five_digit = bool(fips) and con.execute("SELECT 1 FROM sl_places WHERE source_id LIKE ? AND kind = 'county' AND id LIKE ? AND LENGTH(id) = 5 LIMIT 1",
                                            (lc + "-%", fips + "%")).fetchone() is not None

    # places: cities, towns and townships, school districts, hospital and other districts
    places = {"M": {}, "S": {}, "H": {}, "X": {}}
    rows = con.execute("SELECT kind, id, name, county_ids, source_id FROM sl_places WHERE source_id LIKE ?", (lc + "-%",)) if local else []
    for kind, pid, name, cids, src in rows:
        m = NEW_ID.match(str(pid or ""))
        if m and m.group(1) == code:      # the local conventions: the letter in the id says what kind of place it is
            name = guard.ok(name, f"place {kind} {pid}", "place names")
            if name:      # what the place is called (a city, a town, a village) is read from its own name on the page, never guessed here
                places[m.group(2)][m.group(3)] = compact({"n": name, "c": county_list(cids, counties), "src": src})
            continue
        if (kind or "").lower() in ("house", "senate", "judicial", "judicial_district"):
            continue                                              # the districts come from the lines and the races themselves
        pk = place_kind(kind)
        if pk == "C":
            f = re.sub(r"\D", "", str(pid or ""))
            if f and f.zfill(3)[-3:] not in counties and name:
                counties[f.zfill(3)[-3:]], full = county_names(name)
                if full:
                    cfull[f.zfill(3)[-3:]] = full
            continue
        if pk == "X" and (kind or "").lower() != "special":
            continue                                              # the district of a state-level office (a board's, a court's): its races name it
        key = key_for(pk, pid)
        name = guard.ok(name, f"place {kind} {pid}", "place names")
        if not key or not name:
            continue
        t = "township" if re.search(r"\btown(ship)?\b", f"{kind} {name}", re.I) else "city" if re.search(r"\bcity\b", f"{kind} {name}", re.I) else ""
        shape = str(pid) if geo and pk == "S" and str(pid) != key and str(pid) in geo["shapes"].get("school", {}) else None      # the map's id for it, where the page's key is shorter
        places[pk][key] = compact({"n": name, "c": county_list(cids, counties), "src": src, "t": t, "g": shape})

    links = roster_links(os.path.join(HERE, f"state_{lc}.sqlite"), P)
    roster_file = f"state_{lc}.sqlite"
    races, by_id, warn, raw_kind = [], {}, defaultdict(list), {}
    cols = ("race_id", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special", "partisan",
            "holder_id", "holder_name", "holder_party", "election_date", "note")
    for row in con.execute(f"SELECT {', '.join(cols)} FROM sl_races WHERE state = ?", (code,)):
        r = dict(zip(cols, row))
        rid = r["race_id"]
        lv = r["level"] if r["level"] in LEVELS else "other"
        if lv != r["level"]:
            warn["level not known, shown under other districts"].append(rid)
        kind = (r["office_kind"] or "").strip() or "other"
        if kind not in KIND_RANK:      # it keeps its own office title and is listed after the kinds that are placed
            warn[f"office kind '{kind}' is not placed in KINDS yet: listed after the known ones of its level, under its own office title"].append(rid)
        pt = 1 if r["partisan"] else 0
        cids = county_list(r["county_ids"], counties) if local else []
        for f in cids:
            if f not in counties:
                warn["county id not in the county file"].append(rid)
        d = ddist(r["district"]) if lv == "legislature" else (str(r["district"]).strip() if r["district"] not in (None, "") else None)
        pk = None
        new_id = NEW_ID.match(str(r["jurisdiction_id"] or "")) if lv in LOCAL_LEVELS else None
        if new_id and new_id.group(1) == code:
            # the local conventions: a city, town, school, hospital or other district by its own id (a conservation
            # district with lines of its own too); a contest of the county itself carries the county's code and no place
            kind_p, k = new_id.group(2), new_id.group(3)
            pk = kind_p + k
            Pl = places[kind_p].setdefault(k, {})
            if not Pl.get("n"):
                Pl["n"] = guard.ok(r["jurisdiction"], rid, "jurisdiction names") or \
                    {"S": "School district", "M": "City or town", "H": "Hospital district"}.get(kind_p, "District")
            Pl["c"] = sorted(set(Pl.get("c") or []) | set(cids))
            if not cids and Pl.get("c"):
                cids = list(Pl["c"])
            if not cids:
                warn["local contest with no county, so it is on no county page"].append(rid)
        elif lv in LOCAL and five_digit and re.fullmatch(rf"{re.escape(fips)}\d{{3}}", str(r["jurisdiction_id"] or "")):
            if not cids:      # a district that is the county itself (the county's code is its id): filed under the county by its own name
                warn["local contest with no county, so it is on no county page"].append(rid)
        elif lv in LOCAL:      # Minnesota's older ids: a bare county subdivision code, ISD0001, HD00310
            raw = r["jurisdiction_id"] if r["jurisdiction_id"] not in (None, "") else rid.rsplit("-", 1)[-1]
            kind_p = LOCAL[lv]
            mk = mcd_key(raw)
            if (kind_p == "X" and len(re.sub(r"\D", "", str(raw))) == 5 and mk in places["M"]
                    and re.sub(r"\s+(city|township)$", "", places["M"][mk].get("n", ""), flags=re.I).lower() == (r["jurisdiction"] or "").strip().lower()):
                kind_p = "M"                                          # a city's own board (Farwell's sanitary district) sits with the city of that name and code
            k = key_for(kind_p, raw)
            if k:
                pk = kind_p + k
                Pl = places[kind_p].setdefault(k, {})
                if not Pl.get("n"):
                    j = guard.ok(r["jurisdiction"], rid, "jurisdiction names")
                    Pl["n"] = j or ({"S": f"School District {k}", "M": f"County subdivision {k}", "H": f"Hospital district {k}"}.get(kind_p) or f"District {k}")
                Pl["c"] = sorted(set(Pl.get("c") or []) | set(cids))
                if lv == "township" and not Pl.get("t"):
                    Pl["t"] = "township"
                elif lv == "city" and not Pl.get("t"):
                    Pl["t"] = "city"
                if not cids and Pl.get("c"):
                    cids = list(Pl["c"])
            if not cids:
                warn["local contest with no county, so it is on no county page"].append(rid)
        h, more = None, {}
        if r["holder_id"] or r["holder_name"]:
            ids = [x.strip() for x in re.split(r"[;,]", r["holder_id"] or "") if x.strip()]
            hname = guard.ok(r["holder_name"], rid, "holder names")
            if hname and len(ids) > 1:
                # a district that elects two members (the Dakotas' Houses) has two holders: ids, names and parties in step
                names = [n.strip() for n in re.split(r";\s*|\s+and\s+", hname) if n.strip()]
                parts = [p.strip() for p in re.split(r"[;,]", r["holder_party"] or "") if p.strip()]
                parts = parts * len(ids) if len(parts) == 1 else parts
                ok_names, ok_parts = len(names) == len(ids), len(parts) == len(ids)
                codes = [party_code(p) for p in parts] if ok_parts else []
                hc = (codes[0] if len(set(codes)) == 1 else "S") if codes else "I"      # S: the district's members are of two parties
                h = [ids[0], " and ".join(names) if ok_names else hname, " and ".join(dict.fromkeys(parts)) if ok_parts else "", hc]
                more = compact({"hs": ids, "hn": names if ok_names else [], "hp": parts if ok_parts else [], "hc": codes if hc == "S" else []})
            elif hname:
                hp = (r["holder_party"] or "").strip()
                hwords = HOLDER_WORDS.get(hp.upper(), MN_PARTY.get(hp, hp)) if code == "MN" else hp
                h = [ids[0] if ids else "", hname, hwords, party_code(hwords) if hwords else "I"]
            for i in ids:
                if i not in links:
                    warn[f"holder id not in {roster_file}, so no record link"].append(rid)
        race = compact({"id": rid, "lv": lv, "k": kind, "o": guard.ok(r["office"], rid, "office titles") or kind.replace("_", " ").title(),
                        "j": guard.ok(r["jurisdiction"], rid, "jurisdiction names"), "pk": pk, "c": cids, "d": d,
                        "s": str(r["seat"]).strip() if r["seat"] not in (None, "") else None, "sp": 1 if r["special"] else 0, "pt": pt, "h": h,
                        **more, "date": r["election_date"] or GENERAL_DATE, "note": guard.ok(r["note"], rid, "race notes", strict=True), "el": {},
                        "g": race_shape(geo, code, r["level"], kind, r["jurisdiction_id"], r["jurisdiction"], r["district"],
                                        re.findall(r"\d+", str(r["county_ids"] or ""))) if geo else None},
                       keep=("pt", "el"))
        if geo and not race.get("g"):      # no shape of its own: the place it is a part of, or the precincts' own word for its district
            race.update(compact({"gp": place_shape(geo, r["level"], r["jurisdiction_id"], r["district"]), "q": race_said(geo, r["jurisdiction_id"])}))
        raw_kind[rid] = (r["level"], kind)
        race["_sort"] = (LEVELS.index(lv), kind_rank(lv, kind), "" if kind in KIND_RANK else kind,
                         (race.get("j") or "").lower() if lv in LOCAL or lv in ("county", "soil_water") else "",
                         0 if "chief" in race["o"].lower() else 1, natural(d or ""), natural(race.get("s") or ""), race["o"].lower(), rid)
        races.append(race)
        by_id[rid] = race

    prim_row = con.execute("SELECT election_date, COUNT(*) FROM sl_candidates WHERE race_id LIKE ? AND election LIKE 'primary-%' AND election_date IS NOT NULL "
                           "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1", (f"2026-{code}-%",)).fetchone()
    primary = prim_row[0] if prim_row else ("2026-08-11" if code == "MN" else None)
    ccols = ("race_id", "election", "election_date", "name", "party", "party_code", "ballot_order", "incumbent", "write_in", "votes", "pct", "outcome",
             "state_member_id", "source_id", "note")
    orphans, n_cand = [], 0
    for row in con.execute(f"SELECT {', '.join(ccols)} FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{code}-%",)):
        c = dict(zip(ccols, row))
        race = by_id.get(c["race_id"])
        if not race:
            orphans.append(c["race_id"])
            continue
        name = guard.ok(c["name"], c["race_id"], "candidate names (the candidate is left out)")
        if not name:
            continue
        wi = 1 if c["write_in"] else 0
        if race["pt"]:
            p = (c["party"] or "").strip()
            p = (MN_PARTY.get(p, p) if code == "MN" else p) or ("Write-in" if wi else "")
            pc = (c["party_code"] or "").strip().upper()
            pc = pc if pc in ("D", "R", "L", "G", "I", "O", "W") else party_code(p)
        else:
            p, pc = "Nonpartisan office", "N"                      # nonpartisan by law, whatever a file's party column says
        m = c["state_member_id"] or None
        if m and m not in links:
            warn[f"candidate member id not in {roster_file}, so no record link"].append(c["race_id"])
        el = c["election"] or "general"
        race["el"].setdefault(el, []).append(compact({
            "n": name, "p": p, "pc": pc, "o": c["ballot_order"] if isinstance(c["ballot_order"], int) else (int(c["ballot_order"]) if str(c["ballot_order"] or "").isdigit() else None),
            "inc": 1 if c["incumbent"] else 0, "wi": wi, "v": c["votes"], "pct": c["pct"], "out": (c["outcome"] or "").lower() or None, "m": m,
            "src": c["source_id"], "note": guard.ok(c["note"], c["race_id"], "candidate notes", strict=True),
            "date": c["election_date"] or (GENERAL_DATE if el == "general" else primary)}, keep=("n",)))
        n_cand += 1
    if orphans:
        warn["candidate rows whose race is not in sl_races (left out)"].extend(orphans)

    races.sort(key=lambda r: r.pop("_sort"))
    for r in races:      # what the page can put back itself is left out of the file: the usual dates, one source per race, "Nonpartisan office"
        if r.get("date") == GENERAL_DATE:
            del r["date"]
        srcs = {c.get("src") for cs in r["el"].values() for c in cs}
        if len(srcs) == 1 and None not in srcs:
            r["src"] = srcs.pop()
        for key, cs in r["el"].items():
            for c in cs:
                if r.get("src"):
                    c.pop("src", None)
                if c.get("date") == ((r.get("date") or GENERAL_DATE) if key == "general" else primary):
                    del c["date"]
                if not r["pt"]:
                    c.pop("p", None)
    elections = {}
    for r in races:
        for key, cands in r["el"].items():
            elections.setdefault(key, election_name(key, cands))

    sources = {}
    for sid, st, kind, agency, title, url, published, fetched, sha, rows_n, note in con.execute(
            "SELECT source_id, state, kind, agency, title, url, published, fetched, sha256, rows, note FROM sl_sources WHERE state = ? OR state IS NULL "
            "ORDER BY rowid", (code,)):
        sources[sid] = compact({"kind": kind, "agency": plain_source(agency), "title": plain_source(title), "url": url if url and url.startswith("https://") else None,
                                "published": published, "fetched": fetched, "sha": sha, "rows": rows_n, "note": plain_source(note)})
    for sid in {p.get("src") for kind in places.values() for p in kind.values()} & set(sources):
        sources[sid]["names"] = 1      # the page takes a place's name from it: a boundary file read for its names is filed with the places, not the maps
    prim_votes = con.execute("SELECT COUNT(*) FROM sl_candidates WHERE race_id LIKE ? AND election <> 'general' AND votes IS NOT NULL",
                             (f"2026-{code}-%",)).fetchone()[0]

    # What the loaders wrote about the local lists, in their own words: which local offices are on this ballot and what
    # was read (sl_notes), and what could not be loaded, with the reason (sl_gaps). The text goes through the same guard
    # as everything else; the address of a source comes only from its url column and is shown as a link.
    https = lambda u: u if u and str(u).startswith("https://") else None
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    notes, gaps = {}, []
    if has("sl_notes"):
        for key, text, source, url in con.execute("SELECT key, text, source, url FROM sl_notes WHERE state = ? ORDER BY key", (code,)):
            text = guard.ok(text, f"note {key}", "notes on the local lists")
            if text:
                notes[key] = compact({"t": text, "s": guard.ok(source, f"note {key}", "sources named by a note on the local lists"), "u": https(url)})
    if has("sl_gaps"):
        for scope, pid, where, what, reason, url in con.execute("SELECT scope, place_id, place, what, reason, url FROM sl_gaps WHERE state = ? ORDER BY rowid", (code,)):
            gid = f"gap {scope} {pid}"
            what, reason = guard.ok(what, gid, "gaps (what is not here yet)"), guard.ok(reason, gid, "gaps (what is not here yet)")
            if not what or not reason:
                continue
            pid, key = str(pid or ""), ""
            if scope == "county":
                key = re.sub(r"\D", "", pid).zfill(3)[-3:]
                key = key if key in counties else ""
            elif scope == "place":
                m = NEW_ID.match(pid)
                key = m.group(2) + m.group(3) if m and m.group(1) == code and m.group(3) in places[m.group(2)] else ""
            elif scope == "race":
                key = pid if pid in by_id else ""
            if scope != "state" and not key:      # nothing on the page to put it beside: it is said with the state's own, the place named
                warn["gap whose county, place or race is not on the page: shown with the state's own gaps"].append(gid)
            gaps.append(compact({"sc": scope if key else "state", "id": key, "p": guard.ok(where, gid, "places named by a gap"), "w": what, "r": reason,
                                 "u": https(url)}))
    # what a state can have beyond its lists: who the candidates are (each fact with its source), and the polls and the
    # prediction markets of its statewide races. A race whose office may show the fuller facts is marked for the page.
    who, who_info, fuller = who_data(con, code, races, raw_kind, guard, out_dir)
    if who:
        for r in races:
            if r["id"] in fuller:
                r["f"] = 1
    polls, odds, market_files, held = polls_and_odds(code, races)
    extras = {"geo": geo, "who": who, "who_info": who_info, "polls": polls, "odds": odds, "markets": market_files, "held": held,
              "votes": os.path.exists(os.path.join(LEAN_DIR, f"{lc}_place_votes.json"))}
    if extras["votes"]:
        try:
            extras["votes_by"] = votes_by(json.load(open(os.path.join(LEAN_DIR, f"{lc}_place_votes.json"), encoding="utf-8")))
        except ValueError:
            pass
    ph = ",".join("?" * len(LOCAL_LEVELS))
    local_states = [s for (s,) in con.execute(f"SELECT DISTINCT state FROM sl_races WHERE level IN ({ph}) ORDER BY state", LOCAL_LEVELS)]
    con.close()

    used = {m for r in races for cs in r["el"].values() for c in cs for m in [c.get("m")] if m} \
        | {r["h"][0] for r in races if r.get("h") and r["h"][0]} | {i for r in races for i in r.get("hs", [])}
    upper = {ddist(k) for k in lines.get("upper", {})}
    lower = {ddist(k) for k in lines.get("lower", {})}
    nest = {ddist(k): ddist(v) for k, v in nesting(lines).items()} if upper and lower else {}
    have = {"upper": {r["d"] for r in races if r["k"] == "state_senate" and r.get("d")}, "lower": {r["d"] for r in races if r["k"] == "state_house" and r.get("d")}}
    off = {key: sum(1 for d in ds if not leg_race_key(d, have[key])) for key, ds in (("upper", upper), ("lower", lower))}
    data = {"generated": dt.date.today().isoformat(), "election": GENERAL_DATE, "primary": primary, "races": races, "places": places,
            "counties": dict(sorted(counties.items())), "sources": sources, "elections": elections, "pshort": party_short(code, races),
            "hds": sorted(lower, key=natural), "sds": sorted(upper, key=natural), "nest": dict(sorted(nest.items(), key=lambda kv: natural(kv[0]))),
            "links": {k: v for k, v in links.items() if k in used}}
    for key, value in (("cfull", dict(sorted(cfull.items()))), ("notes", notes), ("gaps", gaps)):
        if value:      # only where there is something to say: a state without them keeps the file it had
            data[key] = value
    st = page_words(code, P, data, lines, nest, local, sources, off, prim_votes > 0, local_states, extras)
    guard.report(code)
    return data, st, warn, n_cand, extras


def party_short(code, races):
    """The party as a card's band prints it: DFL for Democratic-Farmer-Labor, and Michigan's "Democratic Party" without "Party"."""
    out = {"Democratic-Farmer-Labor": "DFL"} if code == "MN" else {}
    for r in races:
        for cs in r["el"].values():
            for c in cs:
                p = c.get("p") or ""
                if p.endswith(" Party") and p != "Party":
                    out[p] = p[:-6]
    return out


def leg_note(P, nest, races, lower_keys):
    """How the two chambers' districts fit together, and which seats are up this year, from the lines and places.py."""
    up, lo = P["upper"], P.get("lower")
    out = []
    if nest and lo:
        same = sum(1 for k, v in nest.items() if k == v)
        per_up = Counter(nest.values())
        if same > len(nest) / 2:      # the Dakotas: one legislative district elects the senator and the representatives
            per = round(lo["seats"] / max(1, up["seats"]))
            s = f"Each legislative district elects one {up['title'].lower()} and {number_word(per)} {lo['title'].lower()}{'s' if per != 1 else ''}"
            if any(re.fullmatch(r"\d+[A-Z]", k) for k in lower_keys):
                s += f"; where a district is split into {lo['name']} districts A and B, each elects one"
            out.append(s + ".")
        elif len(set(per_up.values())) == 1:
            k = next(iter(per_up.values()))
            lettered = k == 2 and all(re.fullmatch(r"\d+[AB]", x) for x in nest)
            out.append(f"Each {up['name']} district holds {number_word(k)} {lo['name']} districts{', A and B' if lettered else ''}.")
    staggered = [key for key in ("upper", "lower") if isinstance((P.get(key) or {}).get("next"), dict)]
    if staggered:
        nxt = P[staggered[0]]["next"]
        parity = "odd" if nxt.get("odd") == 2026 else "even" if nxt.get("even") == 2026 else None
        kinds = {"upper": "state_senate", "lower": "state_house"}
        regular = [r for r in races if r["k"] in (kinds[k] for k in staggered) and not r.get("sp") and r.get("d")]
        fits = parity and regular and all((natural(r["d"])[0] % 2 == 1) == (parity == "odd") for r in regular)
        if fits:
            years = number_word(P[staggered[0]].get("term_years", 4))
            who = "Members of both chambers" if len(staggered) == 2 else f"{P[staggered[0]]['title']}s"
            out.append(f"{who} serve {years}-year terms, and the {parity}-numbered districts are up this year.")
    for key, kind in (("upper", "state_senate"), ("lower", "state_house")):
        sp = sorted({r["d"] for r in races if r["k"] == kind and r.get("sp") and r.get("d")}, key=natural)
        if sp and P.get(key):
            dname = P[key].get("district_name") or f"{P[key]['name']} District"
            out.append(f"Special elections fill the rest of a term in {dname}{'s' if len(sp) > 1 else ''} {and_list(sp)}.")
    return " ".join(out)


def or_list(items):
    items = [i for i in items if i]
    if len(items) < 2:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " or " + items[-1]


def local_words(code, data, from_who, c_lines):
    """What a state's county and local contests are called, read from its own rows: what its municipalities' names say
    they are (and which level their races are filed at), whether its school places are districts or boards, how its
    conservation districts are titled, what a county is called there, and which levels are on party lines. Nothing here
    is taken from Minnesota's case; Minnesota's page keeps the sentences it had."""
    mn = code == "MN"
    races = [r for r in data["races"] if r["lv"] in LOCAL_LEVELS]
    lv = Counter(r["lv"] for r in races)
    places = data["places"]
    pname = lambda r: (((places.get(r["pk"][0]) or {}).get(r["pk"][1:]) or {}).get("n") if r.get("pk") else "") or r.get("j") or ""
    said = {level: Counter(muni_word(pname(r)) for r in races if r["lv"] == level) for level in ("city", "township")}
    city_w = [w for w in MUNI_WORDS[:4] if said["city"].get(w)] or (["city"] if lv["city"] else [])      # the level decides: these are municipalities
    town_w = []
    if lv["township"]:
        town_w = ["town" if said["township"].get("town", 0) > said["township"].get("township", 0) else "township"]
    muni = city_w + [w for w in town_w if w not in city_w]
    s_names = [pname(r).lower() for r in races if r["lv"] == "school"]
    school = "school board" if s_names and not any("district" in n for n in s_names) and any("board" in n for n in s_names) else "school district"
    soil_titles = {r["o"].lower() for r in races if r["lv"] == "soil_water"}
    soil = ("Soil and water conservation" if not soil_titles or all("soil and water" in o for o in soil_titles)
            else "Soil conservation districts" if all("soil" in o for o in soil_titles) else "Conservation districts")
    cfull = data.get("cfull") or {}
    kinds = (["county"] if any(f not in cfull for f in data["counties"]) else []) + [county_kind(v) for _, v in sorted(cfull.items())]
    kinds = list(dict.fromkeys(kinds)) or ["county"]
    county_word, one = or_list(kinds), kinds[0]      # "county or city" in Virginia; and the one word the page's headings use: county, parish, borough
    nouns = {"county": [f"{one} offices"], "soil_water": ["soil and water conservation districts" if soil == "Soil and water conservation" else soil.lower()],
             "city": [MUNI_PLURAL[w] for w in city_w], "township": [MUNI_PLURAL[w] for w in town_w if w not in city_w] or [MUNI_PLURAL[w] for w in town_w],
             "school": [school + "s"], "hospital": ["hospital districts"], "other": ["other districts"]}
    have = [level for level in LOCAL_LEVELS if lv[level]]
    parts = list(dict.fromkeys(w for level in have for w in nouns[level]))
    by = {level: (sum(1 for r in races if r["lv"] == level and r["pt"]), sum(1 for r in races if r["lv"] == level and not r["pt"])) for level in have}
    on_lines = [w for level in have if by[level][0] and not by[level][1] for w in nouns[level]]
    off_lines = [w for level in have if by[level][1] and not by[level][0] for w in nouns[level]]
    mixed = [w for level in have if by[level][0] and by[level][1] for w in nouns[level]]
    cap = lambda s: s[:1].upper() + s[1:]
    if not races:
        party = ""
    elif not on_lines and not mixed:
        party = f"Every {one} and local contest here is for a nonpartisan office; the page says so instead of a party."
    elif not off_lines and not mixed:
        party = f"Every {one} and local contest here is elected on party lines, and the party each candidate filed under is written out."
    else:
        bits = ([f"{and_list(on_lines)} are elected on party lines"] if on_lines else []) + ([f"{and_list(off_lines)} are nonpartisan"] if off_lines else []) \
            + ([f"{and_list(mixed)} are some of each"] if mixed else [])
        party = f"Among the {one} and local contests here, {'; '.join(bits)}. Each contest&rsquo;s own page says which, from the list it was read from."
    out = {"muni": muni, "pickM": bool(lv["city"] or lv["township"]), "pickS": bool(lv["school"]), "schoolOne": school,
           "schoolT": cap(school) + "s", "soilT": soil, "countyWord": county_word, "countyMany": county_kind_plural(county_word),
           "countyOne": one, "countyOnes": county_kind_plural(one),
           "hasHosp": bool(lv["hospital"]), "hasOther": bool(lv["other"]), "cLines": c_lines, "localParty": party}
    if mn:      # Minnesota's sentences, as they were, and its older rows (a ward can sit in an office's title)
        out.update({"older": True, "lede": "Every state and local race", "localWhat": "county, city, township, school district and hospital district offices",
                    "localCard": "for county, soil and water, city, township, school and hospital district offices, county by county",
                    "countySub": ("Every county, soil and water, city, township, school district and hospital district contest, filed under the counties it "
                                  "reaches. Pick a county on the map or from the list."),
                    "everyBallot": "Statewide offices, the Legislature and the appeals courts are on every ballot in the county: see",
                    "partNote": "These districts cover parts of the county; they are on your ballot only if you live inside one.",
                    "npLine": "Nonpartisan primaries held on August 11 are not shown here yet."})
    else:
        out.update({"localWhat": f"the {one} and local contests those lists reach", "localCard": f"for {and_list(parts)}, {one} by {one}",
                    "countySub": (f"The {one} and local contests on {from_who} lists, filed under the {out['countyMany']} they reach. "
                                  f"Pick one {'on the map or ' if c_lines else ''}from the list."),
                    "everyBallot": "For the rest of the ballot here, see",
                    "partNote": f"A district can cover only part of the {one}; it is on your ballot only if you live inside it."})
    return out, parts


# The page's own rules ("methods"), each filed under the kind of source it is about and shown in that kind's fold, above
# its sources (the kinds are the keys of SOURCE_KINDS, in the part of build_ballot_dev.PAGE this page borrows). A rule is
# matched by how its bold title begins; one that is not listed here goes under "How this page works" until it is given a
# kind. A rule can also be written as (kind, words) where it is made.
METHOD_KINDS = (("Who is running", "lists"), ("What is read", "lists"), ("Parties", "lists"), ("Primaries", "lists"), ("Order", "lists"),
                ("Places", "places"), ("Who holds a seat today", "holders"), ("Maps", "maps"), ("Nobody is scored", "page"))


def method_kinds(methods):
    """[[kind, words], ...] for the page, empty rules left out."""
    out = []
    for m in methods:
        if not m:
            continue
        if isinstance(m, (tuple, list)):
            if m[1]:
                out.append([m[0], m[1]])
            continue
        title = re.sub(r"^<b>", "", m)
        out.append([next((kind for begins, kind in METHOD_KINDS if title.startswith(begins)), "page"), m])
    return out


def county_kind_plural(word):
    """counties; counties and cities (Virginia); parishes; boroughs and census areas."""
    many = {"county": "counties", "city": "cities", "parish": "parishes", "borough": "boroughs", "census area": "census areas",
            "municipality": "municipalities", "planning region": "planning regions"}
    return and_list([many.get(w, w) for w in re.split(r", | or ", word or "county")])


def extra_words(st, X, name, from_plain, local, has_courts, races):
    """What the page says where a state has more than its lists (the map files, who the candidates are, the record
    behind a nonpartisan office, polls and markets): the privacy sentence, the footer and the rules under Sources say
    what is now shown, where it comes from and what is never collected. A state with none of these keeps its words."""
    who, geo, votes = bool(X.get("who")), X.get("geo"), bool(X.get("votes"))
    markets = bool(X.get("polls") or X.get("odds") or X.get("markets"))
    methods = st["methods"]

    def swap(begins, new):      # the rule that begins so gives way to the new one; a rule that is not there is added
        for i, m in enumerate(methods):
            if isinstance(m, str) and m.startswith(begins):
                methods[i] = new
                return
        methods.append(new)

    if who:
        lv = {r["lv"] for r in races}
        full = and_list([w for w, on in (("statewide offices", "statewide" in lv), ("the Legislature", "legislature" in lv), ("judges", has_courts),
                                        ("county offices", "county" in lv), ("mayors", "city" in lv), ("city councils", "city" in lv),
                                        ("school boards", "school" in lv)) if on])
        small = and_list([w for w, on in (("township boards", "township" in lv), ("soil and water, hospital and other small district boards", bool(lv & {"soil_water", "hospital", "other"})),
                                         ("city clerks and treasurers", "city" in lv)) if on])
        never = ("home or mailing addresses, phone numbers, e-mail, family, marital status, religion, health, ethnicity, income, employers, schools or "
                 "legal troubles")
        st["whoN"] = X["who_info"]["n"]      # what was counted, for the Sources fold
        st["partyN"] = len(X["who_info"]["parties"])
        st["privacy"] = (f"Every candidate is shown as they filed: name, office, and party or &ldquo;nonpartisan office&rdquo;. For {full} a card may add "
                         "a photo, an age, public offices held, the campaign&rsquo;s website and its issue headings, each linked to the government page, "
                         f"campaign site or named news source it comes from. Never collected, for anyone: {never}. Nobody&rsquo;s politics is guessed.")
        # a race's own page says it shorter: what is on that page, where it comes from, what is never collected
        st["privacyRace"] = ("Each candidate is shown as they filed. What else is here (a photo, an age, offices held, a campaign website, issue headings) comes "
                             "from a government page, the campaign&rsquo;s own site or a named news source, and is linked to it. Never collected: home "
                             "addresses, phone numbers, e-mail, family, religion, health, income, employers or schools.")
        st["privacySmall"] = ("Candidates for this office are shown as they filed: name, office and, if they listed one, a campaign website. Addresses, phone "
                              + (f"numbers and e-mail in the {st['who']} files are never read." if not st.get("localWho") else
                                 "numbers and e-mail in the files the lists were read from are never read."))
        st["foot"] = (f"{name}'s state{' and local' if local else ''} candidates come from {from_plain} official lists. What else a card shows (a photo, an "
                      "age, offices held, a campaign website) is named with its source on the race's page. Home addresses, phone numbers and e-mail are "
                      "never read. No scores or ratings of any person.")
        swap("<b>What is read", "<b>What is read from the lists.</b> The office and the district or place it belongs to, the candidate&rsquo;s name, the party, "
             "the ballot order where the list gives one, the official primary vote counts where they are loaded, and the campaign website where a candidate "
             "listed one. Addresses, phone numbers and e-mail in the lists are never read, kept or shown.")
        swap("<b>Who holds a seat today", "<b>Who holds a seat today</b> (the Legislature and the statewide offices the roster carries) comes from the Open "
             "States roster the record side of this site uses. A candidate matched to a sitting legislator by district and name, one fit only, links to "
             "their record page, and their birth date, terms and portrait come from that roster before anything else.")
        methods.append(("people", f"<b>Who the candidates are.</b> For {full} a card may show a photo, an age, the public offices a candidate has held, "
                        "the government&rsquo;s own page about an officeholder, the campaign&rsquo;s website and the headings of its issues page. Official "
                        "records come first; the rest was found on the open web by one reader and confirmed against the page that states it by a second, "
                        "and a finding counts only when its source ties the person to this race. Each is labelled by its source and linked to it. "
                        + (f"Candidates for {small} show what they filed and, if they listed one, their campaign website. " if small else "")
                        + f"Never collected, for anyone: {never}. No social media profile, people-search site, data broker or voter file is ever a "
                        "source, and nobody was contacted."))
        methods.append(("web", "<b>Found on the open web.</b> A birth year or an office held is labelled by the kind of page that states it: "
                        "&ldquo;according to&rdquo; a government&rsquo;s own page or the campaign, &ldquo;as reported by&rdquo; Wikipedia or a named news "
                        "organization. An age from a birth year alone reads &ldquo;about&rdquo;, and offices found this way are listed, never added up into "
                        "years of service. A blank means nothing was found, not that there is nothing."))
        methods.append(("own", "<b>Campaign websites.</b> A candidate&rsquo;s website is the address they filed with the list, or the campaign&rsquo;s own "
                        "site found on the open web and checked against the race it names; the race&rsquo;s page says which. An address that no longer "
                        "leads to the campaign is left out."))
        methods.append(("own", "<b>In their own words.</b> The topics a campaign&rsquo;s issues page lists are shown as headings, with a link to the page; "
                        "nothing is summarized. Photos from a campaign&rsquo;s own site are credited to it and linked."))
        methods.append(("page", "<b>The record, not a label.</b> For a nonpartisan office a race&rsquo;s page shows only what is on the record: a "
                        "party&rsquo;s own published endorsement, an earlier run or office under a party label, and the candidate&rsquo;s own words on their "
                        "own campaign site, each linked to where it stands. This site never calls a person or a place by a party of its own choosing."))
    unit = (geo or {}).get("unit") or "precinct"      # what the smallest voting area is called here, by the map files' own account
    places = or_list((geo or {}).get("muni") or st.get("muni") or ["city", "township"])
    if votes:
        methods.append(("results", "<b>How a place has voted.</b> For a nonpartisan office the race&rsquo;s page shows how the place voted in past partisan "
                        f"elections: the official {X['votes_by'] + ' ' if X.get('votes_by') else ''}results, added up here by county, {places} and district on the lines in force at that "
                        "election. It is not a prediction, it says nothing about any candidate or voter, and where very few people voted the split is left out."))
    if markets:
        methods.append(("polls", "<b>Polls</b> of the statewide races are shown only from pollsters in the American Association for Public Opinion "
                        "Research&rsquo;s Transparency Initiative, who publish how each poll was done: the latest from up to five of them, each checked "
                        "against the pollster&rsquo;s own release, and our own average of the ten most recent, with the arithmetic shown. Polls by other "
                        "pollsters are counted and named, not shown. A poll is a measure of opinion when it was taken, with a margin of error, not a forecast."))
        methods.append(("polls", "<b>Betting markets.</b> Prices on two prediction markets, Polymarket and Kalshi, are shown for the statewide races they "
                        "list, as information only: not a poll, not a forecast and not an official record. They are read from each market&rsquo;s public "
                        "data, and prices move all day. A notice comes before any link to a market. The Civic Archive takes no money from either market "
                        "and uses no referral links."))
    if geo:
        agencies = list(dict.fromkeys(re.split(r"[;,]", plain_source(s.get("agency") or ""))[0].strip() for s in geo["index"].get("sources") or [] if s.get("agency")))
        st["geoWho"] = and_list(["the " + a if not a.lower().startswith("the ") else a for a in agencies[:2]]) if agencies else ""
        st["geoSrc"] = [compact({"a": plain_source(s.get("agency")), "t": plain_source(s.get("title")), "u": web_url(s.get("url"))})
                        for s in geo["index"].get("sources") or [] if s.get("agency")]
        swap("<b>Maps and", ("maps", "<b>The map and &ldquo;use my location&rdquo;.</b> The lines on the map of &ldquo;your ballot&rdquo; come from "
             + (and_list(["the " + a if not a.lower().startswith("the ") else a for a in agencies]) if agencies else "the files named below")
             + (f": {unit}s, the districts put together from whole {unit}s, and the larger districts&rsquo; own lines; each source"
                if any(L.get("lines_from") for L in geo["index"].get("layers") or []) else      # some layers are drawn from files of their own
                f": {unit}s, and every district put together from whole {unit}s; each source")
             + "&rsquo;s own notice is shown with the map. The Legislature&rsquo;s "
             f"page draws the Census Bureau&rsquo;s cartographic boundary files. Your location is used on your own device to find your {unit} and is "
             f"never sent anywhere. The exact spot is not kept: what stays on the device until you tap &ldquo;Forget&rdquo; is your {unit} with its "
             "districts and a rounded copy of the spot (about half a mile). Street pictures are off until you switch them on; then they come from "
             "OpenStreetMap&rsquo;s servers, which see which map squares are asked for. Your county&rsquo;s sample ballot is the authority on your ballot."))


def page_words(code, P, data, lines, nest, local, sources, off, prim_votes, local_states=(), extras=None):
    """What the page says that differs from state to state, worked out from the record. Minnesota's page keeps its words."""
    mn = code == "MN"
    X = extras or {}
    name = P["name"]
    lists = [s for s in sources.values() if s.get("kind") == "official candidate list"]
    agencies = list(dict.fromkeys((s.get("agency") or "").split(",")[0].strip() for s in lists if s.get("agency")))
    state_level = [a for a in agencies if not re.search(r"\bCounty\b", a)]
    county_level = [a for a in agencies if re.search(r"\bCounty\b", a)]
    partial = not state_level and len(county_level) > 1                     # Ohio: the November list is read county board by county board
    # every county office a November candidate was read from, whatever it published: its candidate list, or the election
    # notice it must post (Ohio's 46-day notice)
    readers = list(dict.fromkeys((s.get("agency") or "").split(",")[0].strip() for s in sources.values()
                                 if s.get("kind") in ("official candidate list", "official election notice") and re.search(r"\bCounty\b", s.get("agency") or "")))
    notices = any(s.get("kind") == "official election notice" for s in sources.values())
    if partial:
        main, lister = f"{name}'s county boards of elections", "county boards of elections"
        who, from_who = "county boards of elections&rsquo;", f"{name}&rsquo;s county boards of elections&rsquo;"
    else:
        official = [(x.get("agency") or "").split(",")[0].strip() for x in sources.values()      # never the roster or the Census Bureau
                    if x.get("kind") in ("official results", "official candidate list") and x.get("agency")
                    and not re.search(r"Open States|Census", x.get("agency") or "")]
        main = state_level[0] if state_level else (official[0] if official else f"{name}'s election office")
        lister = re.sub(rf"^{re.escape(name)}\s+", "", main)                # "Secretary of State", "Elections Commission"; Michigan's "Department of State"
        who, from_who = poss(lister), f"the {poss(main)}"
    from_plain = from_who.replace("&rsquo;", "'")
    no_general = not any(r["el"].get("general") for r in data["races"])
    single = not P.get("lower")
    up, lo = P["upper"], P.get("lower") or {"name": "House", "title": "Representative", "seats": 0}
    up_d = up.get("district_name") or f"{up['name']} District"
    lo_d = lo.get("district_name") or f"{lo['name']} District"
    races = data["races"]
    prim = data["primary"]
    pw = day_words(prim) if prim else ""
    zooms = [("the " + z["name"]) if z["name"].endswith("Cities") else z["name"] for z in P.get("zooms") or []]
    dshort = next((s for k, (c, s) in (P.get("parties") or {}).items() if c == "D"), "Democratic")
    one, many = ("a Democrat", "Democrats") if dshort == "Democratic" else (f"a {dshort} member", f"{dshort} members")
    counts = congress_counts(code)
    h, s = counts.get("house", 0), counts.get("senate", 0)
    parts = (["The U.S. Senate race" if s == 1 else f"The {number_word(s)} U.S. Senate races"] if s else []) \
        + ([f"{name}&rsquo;s U.S. House race" if h == 1 else f"{name}&rsquo;s {number_word(h)} U.S. House races"] if h else [])
    many_fed = len(parts) > 1 or h > 1 or s > 1
    congress = (f"{' and '.join(parts)} {'are' if many_fed else 'is'} at the top of the same ballot. "
                f"<a href=\"../us/#state={code}\">See {'them' if many_fed else 'it'} on the Congress pages</a>.") if parts else ""
    congress_short = "the U.S. Senate and House races" if s and h else "the U.S. House races" if h > 1 else "the U.S. House race" if h else "the U.S. Senate race"
    kinds = {r["k"].replace("_retention", "") for r in races if r["lv"] == "court"}
    courts = [words for k, words in COURTS.items() if k in kinds]      # the courts the list holds, by name; a kind with no name here is still counted and shown
    has_courts = any(r["lv"] == "court" for r in races)
    np_statewide = sorted({r["o"] for r in races if r["lv"] == "statewide" and not r["pt"]})
    multi = {key: bool(P.get(key)) and P[key]["seats"] > len(lines.get(key) or {}) > 0 for key in ("upper", "lower")}
    levels_words = and_list(["statewide offices", "the Legislature", "judges" if has_courts else ""])
    notice = ""
    if no_general:
        notice = (f"The {who} list of candidates for the November 3 general election is not loaded yet. The races, who holds each seat today and the "
                  "primaries that chose the nominees are shown.")
    elif partial:
        total = len(data["counties"])
        notice = (f"The November candidates come from the {'candidate lists and election notices' if notices else 'lists'} of the "
                  f"{number_word(len(readers))} county boards of elections loaded so far{f' (of {total})' if total > len(readers) else ''}, named "
                  "under Sources. A race that reaches only other counties shows no candidates until those counties&rsquo; lists are loaded: "
                  "that means the list is not loaded, not that nobody is running.")
    st = {"code": code, "lc": code.lower(), "name": name, "agency": main, "lister": lister, "who": who, "fromWho": from_who, "partial": partial,
          "noGeneral": no_general, "notice": notice, "one": single, "up": up["name"], "lo": lo["name"],
          "upT": "Legislature" if up["name"] == "Legislature" else f"State {up['name']}", "loT": f"State {lo['name']}", "upD": up_d, "loD": lo_d,
          "upAbbr": up["name"][0] + "D", "loAbbr": lo["name"][0] + "D", "prim": pw, "local": local, "nest": bool(nest),
          "multi": multi, "zoom": and_list(zooms), "dOne": "a DFL member" if mn else one, "dMany": "DFL members" if mn else many,
          "off": off, "congress": congress, "congressShort": congress_short, "courts": courts,
          "unit": "seat" if mn else "race", "legNote": leg_note(P, nest, races, data["hds"]),
          "linesNote": ", the lines on the 2026 ballot" if mn else "", "fips": str(P.get("fips") or "")}
    # a state whose lists give no ballot order at all (Ohio's names rotate from precinct to precinct): the page says so,
    # in the words of the note kept with the lists where it has a sentence about it
    no_order = not no_general and not any(c.get("o") is not None for r in races for c in r["el"].get("general", []))
    if no_order:
        said = [s.strip() for n in (data.get("notes") or {}).values() for s in re.split(r"(?<=[.!?])\s+", n.get("t") or "") if re.search(r"\bballot order\b", s, re.I)]
        if said:      # the sentence as far as what it says of the order: a clause after it, set off by a semicolon, is about something else
            clauses, keep = said[0].rstrip(".").split("; "), []
            for c in clauses:
                keep.append(c)
                if re.search(r"\bballot order\b", c, re.I):
                    break
            said = ["; ".join(keep) + "."]
        st["orderNote"] = said[0] if said else "The lists read here give no ballot order."
    cty = county_lines(code) if local else {}
    c_lines = bool(cty.get("counties"))
    local_parts = []
    if local:      # the county pages and the county, city or town and school district choices of "your ballot"
        words, local_parts = local_words(code, data, from_who, c_lines)
        st.update(words)
        # whose lists the county and local contests were read from, where it is not the state's own lister: every one of
        # them a county's office (Iowa's county auditors). The page then says "the county auditors' list" of those contests.
        mine = {(sources.get(r.get("src")) or {}).get("agency") for r in races if r["lv"] in LOCAL_LEVELS and r.get("src")}
        offices = {re.sub(r"^.*\bCounty\s+", "", a).strip().lower() for a in mine if a and re.search(r"\bCounty\s+\S", a)}
        if not partial and mine and None not in mine and all(re.search(r"\bCounty\s+\S", a) for a in mine) and offices:
            office = offices.pop() if len(offices) == 1 else "election office"
            lw = st["localWho"] = f"{st.get('countyOne') or 'county'} {office}s&rsquo;"
            st["localWhat"] = f"the {st.get('countyOne') or 'county'} and local contests on the {lw} lists loaded so far"
            st["countySub"] = str(st.get("countySub") or "").replace(f"on {from_who} lists", f"on the {lw} lists")
    else:          # no county or local rows for this state: how many states have them, counted from the database, and the way to them
        others = [place(c)["name"] for c in local_states]
        n = len(others)
        st["localElse"] = ("No state&rsquo;s county and local races are loaded yet." if not n else
                           f"Loaded for {number_word(n)} state{'s' if n != 1 else ''} so far{': ' + and_list(others) if n <= 6 else ''}.")
        st["localN"] = n
    if mn:
        st["primLine"] = "Where two or more people filed for the same party, that party&rsquo;s August 11 primary chose who went on to November."
        st["primLeg"] = "Where two or more people filed for the same party, that party&rsquo;s August 11 primary chose who went on."
        st["noVotes"] = ("Votes come when the official results are loaded. Who went on to November is read from the Secretary of State&rsquo;s list for "
                         "the general election; everyone who filed comes from its list of candidate filings.")
    else:
        line = f"Where a primary on {pw} had more candidates than places to fill, the race&rsquo;s page shows who went on to November." if pw else ""
        st["primLine"] = st["primLeg"] = line
        st["noVotes"] = (f"Vote counts for this primary are not loaded here. Who went on to November is read from the {who} list for the "
                         "general election; everyone who ran comes from the primary&rsquo;s own list.")
    if mn:
        st["desc"] = ("Every state and local race on Minnesota's November 3, 2026 ballot, from the Secretary of State's official candidate lists: statewide "
                      "offices, the Legislature, judges, and county, city, township, school and hospital district offices.")
        st["foot"] = ("Minnesota's state and local candidates come only from the Secretary of State's official lists. Only the name, office and party each "
                      "candidate filed under are shown; addresses and contact details in those files are never read. No photos, no money, no scores or "
                      "ratings of any person.")
        st["methods"] = [
            "<b>Who is running</b> comes only from the Minnesota Secretary of State&rsquo;s lists of candidates in the general election, one for federal, state and county offices and one for municipal, school and hospital district offices. The U.S. Senate and House races are on the Congress pages.",
            "<b>What is read.</b> From those files this site reads only the office, the candidate&rsquo;s name, the county, city or township and school district codes, the ballot order and the party. Addresses, phone numbers, e-mail and websites in the files are never read, kept or shown. No photos, ages, biographies or campaign money are shown for state and local candidates.",
            "<b>Parties.</b> Statewide offices and the Legislature are elected on party lines, and the party each candidate filed under is written out. Judges and every county, soil and water, city, township, school and hospital district office are nonpartisan by law; the page says so instead of a party.",
            "<b>Primaries.</b> Where two or more people filed for the same party, the August 11 partisan primary is shown: everyone who filed, from the Secretary of State&rsquo;s list of candidate filings, and who went on to November, from the general election list. Vote counts come when the official results are loaded. Nonpartisan primaries are not shown yet.",
            "<b>Order.</b> Candidates appear in the ballot order the list gives, or by surname where it gives none. Never by money, polls or party.",
            "<b>Places.</b> City and township names come from the Census Bureau&rsquo;s county subdivision codes; school district names from the Minnesota Department of Education. Where no official name was found, the code is shown.",
            "<b>Who holds a seat today</b> (the Legislature and the statewide offices only) comes from the Open States roster the record side of this site uses. A candidate matched to a sitting legislator by district and name, one fit only, links to their record page and nothing more.",
            "<b>Maps and &ldquo;use my location&rdquo;.</b> District and county lines are the Census Bureau&rsquo;s cartographic boundary files. Your location is worked out on your own device and never sent anywhere; a rounded copy (about half a mile) is kept on the device, with your choices, until you tap &ldquo;Forget&rdquo;.",
            "<b>Nobody is scored or graded.</b> The cards show the record; the judging is yours."]
    else:
        c_one = st.get("countyOne", "county")      # county; parish in Louisiana; borough in Alaska
        st["desc"] = (f"Every state race on {name}'s November 3, 2026 ballot, from {from_plain} official candidate lists: {levels_words}"
                      + (f"; and the {c_one} and local contests those lists reach ({and_list(local_parts)})." if local else "."))
        st["foot"] = (f"{name}'s state{' and local' if local else ''} candidates come only from {from_plain} official lists. Only the name, office and party "
                      "each candidate filed under are shown; addresses and contact details in those files are never read. No photos, no money, no scores "
                      "or ratings of any person.")
        courts_pt = has_courts and all(r["pt"] for r in races if r["lv"] == "court")
        leg_np = not any(r["pt"] for r in races if r["lv"] == "legislature")
        np_list = (["The Legislature"] if leg_np else []) + (["judges"] if has_courts and not courts_pt else []) \
            + [f"the {o}" if not o.lower().startswith("the ") else o for o in np_statewide]
        np_list = [np_list[0][0].upper() + np_list[0][1:]] + np_list[1:] if np_list else []
        parties = ("<b>Parties.</b> Offices elected on party lines show the party each candidate filed under, written out"
                   + (", judges included" if courts_pt else "") + ". "
                   + (f"{and_list(np_list)} {'are' if len(np_list) > 1 or np_list[0].startswith('Judges') else 'is'} on the nonpartisan ballot; the page says so instead of a party." if np_list else "")
                   + (f" {st['localParty']}" if local and st.get("localParty") else ""))
        if local:      # what the county and local rows are, in this state's own terms; what is missing is said where it is missing
            here = (f" {c_one.capitalize()} and local contests are read from the lists named below too: which local offices are on this ballot, what was "
                    f"read and what is not here yet are set out under <a href=\"#counties\">{c_one.capitalize()} by {c_one}</a>, in the words of the notes "
                    "kept with the lists.")
        elif data.get("notes") or data.get("gaps"):
            here = f" Why no county or local contest is shown for {name} is set out under <a href=\"#localnotes\">County and local races</a>."
        else:
            n = st["localN"]
            here = (f" County and local races are not loaded for {name} yet" + (f"; they are loaded for {number_word(n)} state{'s' if n != 1 else ''} so far, "
                    "shown on <a href=\"../states/#local\">the states page</a>." if n else "."))
        place_agencies = list(dict.fromkeys(a for a in ((sources.get(p.get("src")) or {}).get("agency", "").split(",")[0].strip()
                                                          for kind in data["places"].values() for p in kind.values()) if a))
        st["methods"] = [
            f"<b>Who is running</b> comes only from {from_who} own lists of candidates for the November 3 general election{f' and the {pw} primary' if pw else ''}, and the official primary results; each file is named below, with where it was read."
            + (" The November list is not loaded yet." if no_general else " Only the counties named below are loaded so far, so a race can be missing names from other counties." if partial else "")
            + " The U.S. Senate and House races are on the Congress pages." + here,
            f"<b>What is read.</b> From those lists this site reads only the office, the district{', the county and the city, town or district a contest belongs to' if local else ''}, the candidate&rsquo;s name, the party, the ballot order where the list gives one{', and the primary vote counts' if prim_votes else ''}. Addresses, phone numbers, e-mail and websites, where a list carries them, are never read, kept or shown. No photos, ages, biographies or campaign money are shown for state{' and local' if local else ''} candidates.",
            parties,
            (f"<b>Primaries.</b> Where more people ran in a primary ({pw}) than it could send on, everyone on that primary ballot is shown, with who went on to November, read from the general election list. "
             + ("Vote counts are the official results where they are loaded; where they are not, the race says so." if prim_votes else "Vote counts are not loaded yet.")) if pw else "",
            (f"<b>Order.</b> {html_esc(st['orderNote'])} Candidates appear by surname. Never by money, polls or party." if st.get("orderNote") else
             "<b>Order.</b> Candidates appear in the ballot order the list gives, or by surname where it gives none. Never by money, polls or party."),
            (f"<b>Places.</b> A {c_one} or local contest is filed under every {st['countyWord']} it reaches. The names of cities, towns and districts come from "
             f"{and_list(['the ' + a if not a.lower().startswith('the ') else a for a in place_agencies])}, each named among these sources"
             + ("; where something on a county&rsquo;s ballot could not be shown, that county&rsquo;s page says what and why."
                if any(g.get("sc") == "county" for g in data.get("gaps") or []) else ".")) if local and place_agencies else "",
            "<b>Who holds a seat today</b> (the Legislature and the statewide offices the roster carries) comes from the Open States roster the record side of this site uses. A candidate matched to a sitting legislator by district and name, one fit only, links to their record page and nothing more.",
            f"<b>Maps and &ldquo;use my location&rdquo;.</b> District lines are the Census Bureau&rsquo;s cartographic boundary files ({lines.get('vintage') or 'the current file'}), the lines the state pages draw"
            + (f", and the {c_one} lines are the Bureau&rsquo;s too ({cty.get('vintage')})" if c_lines and cty.get("vintage") else "")
            + f"; your {c_one}&rsquo;s sample ballot is the authority on your district. Your location is worked out on your own device and never sent anywhere; a rounded copy (about half a mile) is kept on the device, with your choices, until you tap &ldquo;Forget&rdquo;.",
            "<b>Nobody is scored or graded.</b> The cards show the record; the judging is yours."]
    extra_words(st, X, name, from_plain, local, has_courts, races)
    st["methods"] = method_kinds(st["methods"])      # each rule with the kind of source it is about: the page shows it in that kind's fold
    for k, v in (("upSeg", up_d), ("loSeg", lo_d)):
        st[k] = re.sub(r"\bDistrict$", "districts", v)
    nav = [("statewide", "Statewide", ""), ("legislature", "Legislature", "")] + ([("courts", "Judges", "x")] if has_courts else []) \
        + ([("counties", st.get("countyOnes", "counties").capitalize(), "")] if local else []) + [("sources", "Sources", "x")]
    st["nav"] = "".join((f'<a class="{c}" href="#{h}">{t}</a>' if c else f'<a href="#{h}">{t}</a>') for h, t, c in nav)
    return st


def lines_file(path, code, local):
    """The lines the maps draw: both chambers of the Legislature, the state's outline and, where the county pages are built,
    the counties, all in the site's Albers map space. Written only when they change."""
    leg = lines_for(code)
    cty = county_lines(code) if local else {}
    outline = state_paths(os.path.join(HERE, "us_states_albers.json")).get(code) or {"d": "", "bbox": [0, 0, 975, 610]}
    body = {"q": leg.get("q", 400), "upper": {ddist(k): v for k, v in leg.get("upper", {}).items()},
            "lower": {ddist(k): v for k, v in leg.get("lower", {}).items()}, "vintage": leg.get("vintage", ""),
            "outline": {"d": outline["d"], "bbox": outline["bbox"]}}
    if local:
        body.update({"cq": cty.get("q", 400), "counties": cty.get("counties", {}), "cvintage": cty.get("vintage", "")})
    text = json.dumps(body, separators=(",", ":"))
    write_if_changed(path, text)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def write_if_changed(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return True


def copy_fonts(out_dir):
    """The site's own type (Open Font License), beside the page, so nothing is fetched from another server."""
    src, dst = os.path.join(HERE, "fonts"), os.path.join(out_dir, "fonts")
    os.makedirs(dst, exist_ok=True)
    for name in ("InstrumentSans-Variable.ttf", "InstrumentSerif-Regular.ttf", "InstrumentSerif-Italic.ttf", "OFL-InstrumentSans.txt", "OFL-InstrumentSerif.txt"):
        a, b = os.path.join(src, name), os.path.join(dst, name)
        if os.path.exists(a) and (not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read()):
            shutil.copyfile(a, b)


# The map's own script, written beside the page as geo/mapkit.js and fetched when a map opens (a state with no map files
# never loads it). Two parts: BallotMap, which draws a state's map files in Web Mercator and knows nothing of this page;
# and GEOKIT, which sets the map into the page's "your ballot" (it uses the page's own words and helpers by name).
MAPKIT = r"""/* The ballot map (John, 2026-10-01). One map for every kind of line a ballot is made of, drawn in Web Mercator from the
   state's own map files (geo/index.json says what they are) with the reader that was built with them (geo/reader.js, MNGeo).
   A layer's own file is drawn while the view is far out; closer in, the precinct file of each county in view takes over, so
   the lines are the precincts' own down to a street. Nothing here asks any other server for anything, with one exception a
   reader has to switch on: the street pictures, which are OpenStreetMap's.
   No pointer capture anywhere: drags and pinches are followed with listeners on the window, dropped when the map goes. */
(function () {
"use strict";
const TILE = 256, MAXZ = 18, TILEZ = 19, TILES = "https://tile.openstreetmap.org/";
const mx = lon => (lon + 180) / 360 * TILE;
const my = lat => { const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180); return (.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE; };
const lonAt = x => x / TILE * 360 - 180;
const latAt = y => Math.atan(Math.sinh(Math.PI * (1 - 2 * y / TILE))) * 180 / Math.PI;
const holds = (v, id) => Array.isArray(v) ? v.indexOf(id) >= 0 : v === id;

function BallotMap(el, opt) {
  const IDX = opt.index, base = opt.base, q = opt.v ? "?v=" + opt.v : "";
  const canvas = el.querySelector("canvas"), ctx = canvas.getContext("2d");
  const tilesEl = el.querySelector(".gtiles"), pinEl = el.querySelector(".gpin"), attrEl = el.querySelector(".gattr"), busyEl = el.querySelector(".gbusy");
  const LAYER = {}, COUNTY = {};
  IDX.layers.forEach(L => { LAYER[L.kind] = L; });
  IDX.counties.forEach(c => { COUNTY[c.id] = c; });
  const KINDS = IDX.arc_kinds || [], bit = kind => { const i = KINDS.indexOf(kind); return i < 0 ? 0 : 1 << i; };
  const files = {}, waits = {}, failed = {}, tiles = new Map();
  const off = new AbortController(), sig = {signal: off.signal};
  let W = 0, H = 0, dpr = 1, view = null, fit = null, layer = LAYER[opt.layer] ? opt.layer : "county", sel = null, mine = null, pin = null,
    streets = false, dead = false, polls = null, sched = 0, tileTimer = 0, tilePending = 0, lastType = "", keys = false;

  /* ----- the files: each fetched once, its lines turned into map units once ----- */
  function world(f) {
    const t = f.transform, sx = t.scale[0], sy = t.scale[1], tx = t.translate[0], ty = t.translate[1];
    f._w = f._lines.map(L => { const a = new Float64Array(L.length); for (let k = 0; k < L.length; k += 2) { a[k] = mx(L[k] * sx + tx); a[k + 1] = my(L[k + 1] * sy + ty); } return a; });
    f._wb = f._w.map(a => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (let k = 0; k < a.length; k += 2) { if (a[k] < x0) x0 = a[k]; if (a[k] > x1) x1 = a[k]; if (a[k + 1] < y0) y0 = a[k + 1]; if (a[k + 1] > y1) y1 = a[k + 1]; }
      return [x0, y0, x1, y1]; });
    return f;
  }
  const busy = () => { if (busyEl) busyEl.hidden = !Object.keys(waits).length; };
  function load(path) {
    if (files[path]) return Promise.resolve(files[path]);
    if (!waits[path]) {
      waits[path] = fetch(base + path + q).then(r => r.ok ? r.json() : Promise.reject(new Error(path + ": " + r.status)))
        .then(d => { files[path] = world(MNGeo.open(d)); delete waits[path]; busy(); if (!dead) schedule(); return files[path]; },
          e => { delete waits[path]; failed[path] = Date.now(); busy(); throw e; });
      busy();
    }
    return waits[path];
  }
  const want = path => { if (!files[path] && !waits[path] && !(failed[path] && Date.now() - failed[path] < 8000)) load(path).catch(() => {}); return files[path] || null; };
  const schoolPath = id => IDX.school.files.replace("<id>", id);
  const byId = (f, kind) => f._ids || (f._ids = Object.fromEntries(f.objects[kind].geometries.map(g => [g.id, g])));
  function rings(f, g) {      // a shape's rings in map units, kept on the shape
    if (g._wr) return g._wr;
    const out = [];
    for (const poly of MNGeo.polygons(f, g)) for (const ring of poly) { const a = new Float64Array(ring.length * 2);
      for (let i = 0; i < ring.length; i++) { a[2 * i] = mx(ring[i][0]); a[2 * i + 1] = my(ring[i][1]); } out.push(a); }
    return g._wr = out;
  }

  /* ----- the view: its middle in map units, and a zoom ----- */
  const scale = () => Math.pow(2, view.z);
  const X = x => (x - view.x) * scale() + W / 2, Y = y => (y - view.y) * scale() + H / 2;
  const lonLat = (px, py) => [lonAt(view.x + (px - W / 2) / scale()), latAt(view.y + (py - H / 2) / scale())];
  const bounds = () => { const a = lonLat(0, H), b = lonLat(W, 0); return [a[0], a[1], b[0], b[1]]; };
  function fitTo(b, pad, most) {
    const x0 = mx(b[0]), x1 = mx(b[2]), y0 = my(b[3]), y1 = my(b[1]);
    const z = Math.log2(Math.min((W - 2 * pad) / Math.max(1e-9, x1 - x0), (H - 2 * pad) / Math.max(1e-9, y1 - y0)));
    return {x: (x0 + x1) / 2, y: (y0 + y1) / 2, z: Math.min(most || MAXZ, z)};
  }
  function clamp(v) {
    const b = IDX.bbox;
    v.z = Math.max(fit.z, Math.min(MAXZ, v.z));
    if (v.z <= fit.z + .01) { v.x = fit.x; v.y = fit.y; return v; }
    v.x = Math.max(mx(b[0]), Math.min(mx(b[2]), v.x)); v.y = Math.max(my(b[3]), Math.min(my(b[1]), v.y));
    return v;
  }
  function setView(v) { view = clamp({x: v.x, y: v.y, z: v.z}); schedule(); }
  function zoomTo(z, px, py) {
    z = Math.max(fit.z, Math.min(MAXZ, z));
    if (px == null) { px = W / 2; py = H / 2; }
    const k0 = scale(), wx = view.x + (px - W / 2) / k0, wy = view.y + (py - H / 2) / k0, k1 = Math.pow(2, z);
    setView({x: wx - (px - W / 2) / k1, y: wy - (py - H / 2) / k1, z});
  }
  const stepIn = (px, py) => zoomTo(Math.floor(view.z + 1e-6) + 1, px, py);      // whole steps, so the street pictures stay sharp
  const stepOut = (px, py) => zoomTo(Math.ceil(view.z - 1e-6) - 1, px, py);
  function schedule() {      // one drawing for however many changes; a timer stands in where a page that is not showing gets no frames
    if (sched || dead) return;
    sched = 1; let done = false;
    const run = () => { if (done) return; done = true; sched = 0; draw(); };
    requestAnimationFrame(run); setTimeout(run, 60);
  }
  function resize() {
    const r = el.getBoundingClientRect(), w = Math.round(r.width), h = Math.round(r.height);
    if (!w || !h || (w === W && h === H)) return;
    const whole = !view || Math.abs(view.z - fit.z) < .01;
    W = w; H = h; dpr = Math.min(2.5, window.devicePixelRatio || 1);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    fit = fitTo(IDX.bbox, 12);
    view = whole ? {x: fit.x, y: fit.y, z: fit.z} : clamp(view);
    draw();
  }

  /* ----- what the view needs: the layer's own file far out; each county's precinct file close in ----- */
  function plan() {
    const L = LAYER[layer] || {}, b = bounds(), close = view.z >= (L.good_to_zoom || 10.5) + .9;
    const cs = close ? IDX.counties.filter(c => c.bbox[0] <= b[2] && c.bbox[2] >= b[0] && c.bbox[1] <= b[3] && c.bbox[3] >= b[1]) : [];
    const near = close && cs.length > 0 && cs.length <= 9;
    let detail = false, cf = [], sf = [];
    if (near) {
      cf = cs.map(c => want(c.file)).filter(Boolean);
      detail = cf.length === cs.length;
      if (detail && layer === "school") {      // a school district's lines do not follow precincts: its own file, for each district the precincts in view lie in
        const ids = new Set();
        for (const f of cf) for (const g of f.objects.precincts.geometries) { const bb = g.bbox;
          if (bb[0] > b[2] || bb[2] < b[0] || bb[1] > b[3] || bb[3] < b[1]) continue;
          (g.properties.school || []).concat(g.properties.school_edge || []).forEach(i => ids.add(i)); }
        if (ids.size > 40) detail = false;
        else { sf = [...ids].map(i => want(schoolPath(i))).filter(Boolean); if (sf.length < ids.size) detail = false; }
      }
    }
    const lf = detail ? null : (near ? files[L.file] || null : (L.file ? want(L.file) : null));
    return {near, detail, cf, sf, lf, b};
  }

  /* ----- drawing ----- */
  function trace(a, k, ox, oy, shut) {
    ctx.moveTo(a[0] * k + ox, a[1] * k + oy);
    for (let i = 2; i < a.length; i += 2) ctx.lineTo(a[i] * k + ox, a[i + 1] * k + oy);
    if (shut) ctx.closePath();
  }
  function arcs(f, test) {      // a path of the lines of a file that pass the test and can be seen
    const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k, x0 = view.x - W / 2 / k, x1 = view.x + W / 2 / k, y0 = view.y - H / 2 / k, y1 = view.y + H / 2 / k;
    ctx.beginPath();
    for (let a = 0; a < f._w.length; a++) { const b = f._wb[a]; if (b[2] < x0 || b[0] > x1 || b[3] < y0 || b[1] > y1 || (test && !test(a))) continue; trace(f._w[a], k, ox, oy, false); }
  }
  function shapes(list) {      // a path of whole shapes: [[file, shape], ...]
    const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k;
    ctx.beginPath();
    for (const [f, g] of list) for (const a of rings(f, g)) trace(a, k, ox, oy, true);
  }
  function stroke(color, width, dash, under) {
    ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.setLineDash(dash || []);
    if (under) { ctx.strokeStyle = under; ctx.lineWidth = width + 2.6; ctx.stroke(); }
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke(); ctx.setLineDash([]);
  }
  function outline(P, kind, id) {      // the path of one shape's outline, from whichever files are in use; false when none has it
    if (P.detail && kind !== "school" && (kind === "county" || KINDS.indexOf(kind) >= 0)) {
      const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k, m = bit(kind);
      ctx.beginPath();
      for (const f of P.cf) { const gs = f.objects.precincts.geometries, S = f.arcSides;
        for (let a = 0; a < f._w.length; a++) { if (!(f.arcMask[a] & m)) continue;
          const r = S[2 * a], l = S[2 * a + 1];
          if ((r >= 0 && holds(gs[r].properties[kind], id)) === (l >= 0 && holds(gs[l].properties[kind], id))) continue;
          trace(f._w[a], k, ox, oy, false); } }
      return true;
    }
    const sf = kind === "school" ? files[schoolPath(id)] : null;
    if (sf) { shapes([[sf, sf.objects.school.geometries[0]]]); return true; }
    const lf = files[(LAYER[kind] || {}).file], g = lf && byId(lf, kind)[id];
    if (g) { shapes([[lf, g]]); return true; }
    return false;
  }
  function body(P, kind, id) {      // the path of one shape's inside
    if (P.detail && kind !== "school" && (kind === "county" || KINDS.indexOf(kind) >= 0)) {
      const list = [];
      for (const f of P.cf) for (const g of f.objects.precincts.geometries) if (holds(g.properties[kind], id)) list.push([f, g]);
      shapes(list); return list.length > 0;
    }
    return outline(P, kind, id);
  }
  const short = (kind, id, name) => opt.short ? opt.short(kind, id, name) : name;
  function labels(P, col) {
    const k = scale(), out = [], b = P.b;
    ctx.font = "600 12px " + (col.sans || "sans-serif"); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    if (P.detail) {
      const acc = {};
      for (const f of P.cf) for (const g of f.objects.precincts.geometries) {
        const c = g.properties.c; if (!c || c[0] < b[0] || c[0] > b[2] || c[1] < b[1] || c[1] > b[3]) continue;
        let v = g.properties[layer]; if (Array.isArray(v)) v = v[0]; if (v == null) continue;
        const e = acc[v] || (acc[v] = {x: 0, y: 0, n: 0}); e.x += X(mx(c[0])); e.y += Y(my(c[1])); e.n++; }
      for (const [id, e] of Object.entries(acc)) { const text = short(layer, id, nameOf(layer, id)); if (text) out.push({x: e.x / e.n, y: e.y / e.n, text, pri: e.n}); }
    } else if (P.lf) {
      for (const g of P.lf.objects[layer].geometries) { const bb = g.bbox, c = g.properties.c;
        if (!c || bb[0] > b[2] || bb[2] < b[0] || bb[1] > b[3] || bb[3] < b[1]) continue;
        const text = short(layer, g.id, g.properties.name); if (!text) continue;
        const w = (mx(bb[2]) - mx(bb[0])) * k, h = (my(bb[1]) - my(bb[3])) * k;
        if (w < ctx.measureText(text).width + 3 || h < 14) continue;
        out.push({x: X(mx(c[0])), y: Y(my(c[1])), text, pri: w * h}); }
    }
    out.sort((a, b2) => b2.pri - a.pri);
    const put = [];
    for (const L of out.slice(0, 400)) { const w = ctx.measureText(L.text).width / 2 + 4;
      if (L.x - w < 0 || L.x + w > W || L.y < 9 || L.y > H - 9) continue;
      if (put.some(p => Math.abs(p.x - L.x) < p.w + w && Math.abs(p.y - L.y) < 16)) continue;
      put.push({x: L.x, y: L.y, w});
      ctx.lineWidth = 3.5; ctx.strokeStyle = col.halo; ctx.lineJoin = "round"; ctx.strokeText(L.text, L.x, L.y);
      ctx.fillStyle = col.ink; ctx.fillText(L.text, L.x, L.y);
      if (put.length >= 70) break; }
  }
  function draw() {
    if (dead || !W || !view) return;
    const cs = getComputedStyle(document.documentElement), V = n => cs.getPropertyValue(n).trim();
    const col = {bg: V("--bg") || "#f4f4f0", surface: V("--surface") || "#fff", ink: V("--ink") || "#111", line: V("--line-strong") || "#bbb",
      accent: V("--accent") || "#0f7a6a", gold: V("--gold") || "#b8860b", sans: V("--sans")};
    col.halo = streets ? "rgba(255,255,255,.92)" : col.surface;
    if (streets) { col.ink = "#14171c"; col.accent = "#0b5d51"; col.gold = "#a36f00"; col.line = "#7d8590"; }      // the street pictures are light in both themes, so over them the lines keep one set of colours
    const P = plan(), under = streets ? "rgba(255,255,255,.85)" : null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const st = files[(LAYER.state || {}).file] || (LAYER.state ? want(LAYER.state.file) : null);
    if (!streets) { ctx.fillStyle = col.bg; ctx.fillRect(0, 0, W, H);
      if (st) { shapes(st.objects.state.geometries.map(g => [st, g])); ctx.fillStyle = col.surface; ctx.fill("evenodd"); } }
    const cbit = bit("county");
    if (layer !== "county") {      // the counties, faintly, to say where things are
      if (P.detail && cbit) { for (const f of P.cf) { arcs(f, a => f.arcMask[a] & cbit); stroke(col.line, 1, null, null); } }
      else { const cl = files[(LAYER.county || {}).file] || (LAYER.county ? want(LAYER.county.file) : null); if (cl) { arcs(cl); stroke(col.line, 1, null, null); } }
    }
    const lb = bit(layer);
    if (P.detail && layer === "school") { shapes(P.sf.map(f => [f, f.objects.school.geometries[0]])); stroke(col.accent, 1.8, null, under); }
    else if (P.detail) { for (const f of P.cf) { arcs(f, layer === "county" ? (a => f.arcMask[a] & cbit) : (a => f.arcMask[a] & lb)); stroke(col.accent, 1.8, null, under); } }
    else if (P.lf) { arcs(P.lf); stroke(col.accent, layer === "mcd" && view.z < 8 ? .7 : 1.3, null, under); }
    if (st && !P.detail) { shapes(st.objects.state.geometries.map(g => [st, g])); stroke(col.ink, 1.4, null, null); }      // close in, the state's own edge is among the county lines already drawn
    if (mine) {      // the reader's own: their precinct where its file is here, and their district of the kind being drawn
      const mf = mine.c && COUNTY[mine.c] ? files[COUNTY[mine.c].file] : null, mg = mf && mine.p ? byId(mf, "precincts")[mine.p] : null;
      if (mg && view.z >= 10.5) { shapes([[mf, mg]]); ctx.fillStyle = col.gold; ctx.globalAlpha = .16; ctx.fill("evenodd"); ctx.globalAlpha = 1; stroke(col.gold, 2, null, under); }
      const id = mine.ids && mine.ids[layer];
      if (id && outline(P, layer, id)) stroke(col.gold, 3, [7, 5], under);
      if (mine.at && !pin && (!mg || view.z < 10.5)) { const x = X(mx(mine.at[0])), y = Y(my(mine.at[1]));
        ctx.beginPath(); ctx.arc(x, y, 7, 0, 2 * Math.PI); ctx.fillStyle = col.gold; ctx.globalAlpha = .25; ctx.fill(); ctx.globalAlpha = 1; ctx.lineWidth = 2.5; ctx.strokeStyle = col.gold; ctx.stroke(); }
    }
    if (sel && sel.id != null) {
      if (body(P, sel.kind, sel.id)) { ctx.fillStyle = col.accent; ctx.globalAlpha = .17; ctx.fill("evenodd"); ctx.globalAlpha = 1; }
      if (outline(P, sel.kind, sel.id)) stroke(col.ink, 2.6, null, under);
    }
    if (polls && view.z >= 11.5) for (const p of polls.places) { if (!p.lonlat) continue; const x = X(mx(p.lonlat[0])), y = Y(my(p.lonlat[1])); if (x < -8 || x > W + 8 || y < -8 || y > H + 8) continue;
      ctx.beginPath(); ctx.rect(x - 5, y - 5, 10, 10); ctx.fillStyle = col.ink; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = col.halo; ctx.stroke(); }
    labels(P, col);
    if (keys) { ctx.beginPath(); ctx.moveTo(W / 2 - 9, H / 2); ctx.lineTo(W / 2 + 9, H / 2); ctx.moveTo(W / 2, H / 2 - 9); ctx.lineTo(W / 2, H / 2 + 9); stroke(col.ink, 2, null, "rgba(255,255,255,.9)"); }
    el.classList.toggle("zoomed", view.z > fit.z + .05);
    if (pinEl) { pinEl.hidden = !pin; if (pin) pinEl.style.transform = "translate(" + X(mx(pin[0])).toFixed(1) + "px," + Y(my(pin[1])).toFixed(1) + "px)"; }
    placeTiles();
    if (streets) { clearTimeout(tileTimer); tileTimer = setTimeout(askTiles, 140); }
    if (opt.onView) opt.onView({z: view.z, detail: P.detail, near: P.near, whole: view.z <= fit.z + .01, waiting: Object.keys(waits).length,
      failed: Object.keys(failed).some(p => !files[p] && Date.now() - failed[p] < 60000)});
  }

  /* ----- the street pictures (off until a reader asks): OpenStreetMap's standard tiles, only the squares in view, never ahead of the view ----- */
  function placeTiles() {
    const k = scale();
    for (const [key, im] of tiles) { const p = key.split("/"), u = TILE / Math.pow(2, +p[0]), s = u * k;
      im.style.width = im.style.height = (s + .5).toFixed(2) + "px";
      im.style.transform = "translate(" + X(+p[1] * u).toFixed(2) + "px," + Y(+p[2] * u).toFixed(2) + "px)"; }
  }
  let keepNow = new Set();      // the squares the view wants now; the ones it had stay underneath until these have come
  function sweep() { for (const [key, im] of tiles) if (!keepNow.has(key)) { im.remove(); tiles.delete(key); } }
  function askTiles() {
    if (!streets || dead) return;
    const z = Math.max(0, Math.min(TILEZ, Math.round(view.z))), n = Math.pow(2, z), u = TILE / n, k = scale();
    const x0 = Math.floor((view.x - W / 2 / k) / u), x1 = Math.floor((view.x + W / 2 / k) / u), y0 = Math.floor((view.y - H / 2 / k) / u), y1 = Math.floor((view.y + H / 2 / k) / u);
    const keep = new Set();
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) if (x >= 0 && y >= 0 && x < n && y < n) keep.add(z + "/" + x + "/" + y);
    if (keep.size > 48) return;      // never a flood of requests
    keepNow = keep;
    let asked = 0;
    for (const key of keep) { if (tiles.has(key)) continue;
      const im = new Image(); im.alt = ""; im.draggable = false; im.decoding = "async";
      const done = () => { tilePending = Math.max(0, tilePending - 1); if (!tilePending) sweep(); };
      im.onload = done; im.onerror = () => { im.style.visibility = "hidden"; done(); };
      tilePending++; asked++; tiles.set(key, im); tilesEl.appendChild(im); im.src = TILES + key + ".png"; }
    placeTiles();
    if (!asked && !tilePending) sweep();
    else setTimeout(() => { if (!dead && streets) sweep(); }, 4000);
  }
  function setStreets(on) {
    streets = !!on; el.classList.toggle("streets", streets);
    if (attrEl) attrEl.hidden = !streets;
    if (!streets) { clearTimeout(tileTimer); tilePending = 0; keepNow = new Set(); sweep(); }
    else if (Math.abs(view.z - Math.round(view.z)) > .01 && view.z > fit.z + .01) view.z = Math.round(view.z);
    schedule();
  }

  /* ----- which shape a spot is in ----- */
  function nameOf(kind, id) {
    const lf = files[(LAYER[kind] || {}).file], g = lf && byId(lf, kind)[id];
    if (g) return g.properties.name;
    for (const c of IDX.counties) { const f = files[c.file]; if (f && f.names && f.names[kind] && f.names[kind][id]) return f.names[kind][id]; }
    return opt.nameOf ? opt.nameOf(kind, id) : id;
  }
  function precinctAt(P, lon, lat) {
    for (const f of P.cf) { const bb = f.bbox; if (lon < bb[0] - .01 || lon > bb[2] + .01 || lat < bb[1] - .01 || lat > bb[3] + .01) continue;
      const h = MNGeo.precinctAt(f, lon, lat); if (h && h.inside) return {file: f, geometry: h.geometry, edge: h.edge}; }
    return null;
  }
  function at(px, py) {
    const ll = lonLat(px, py), lon = ll[0], lat = ll[1], P = plan();
    if (polls && view.z >= 11.5) { let best = null, bd = 15;
      for (const p of polls.places) { if (!p.lonlat) continue; const d = Math.hypot(X(mx(p.lonlat[0])) - px, Y(my(p.lonlat[1])) - py); if (d < bd) { bd = d; best = p; } }
      if (best) return {kind: "poll", place: best, lon, lat}; }
    let id = null, precinct = null;
    if (P.detail) {
      const h = precinctAt(P, lon, lat);
      if (h) { precinct = h.geometry; const p = precinct.properties;
        if (layer === "school") { const all = (p.school || []).concat(p.school_edge || []);
          if (all.length === 1 && !p.school_out) id = all[0];
          else for (const i of all) { const sf = files[schoolPath(i)]; if (sf && MNGeo.inside(sf, sf.objects.school.geometries[0], lon, lat)) { id = i; break; } } }
        else { const v = p[layer]; id = Array.isArray(v) ? (v[0] == null ? null : v[0]) : (v == null ? null : v);
          // a precinct that reaches more than one place (a village inside its township): the layer's own shapes answer for the spot, where they are at hand
          const all = layer === "mcd" && !p.city ? p.mcd_all : null, lf = all && all.length > 1 ? files[(LAYER.mcd || {}).file] : null;
          if (lf) { const hh = MNGeo.shapeAt(lf, "mcd", lon, lat); if (hh && all.indexOf(hh.geometry.id) >= 0) id = hh.geometry.id; } } }
    } else if (P.lf) { const h = MNGeo.shapeAt(P.lf, layer, lon, lat); if (h) id = h.geometry.id; }
    else return {kind: layer, id: null, loading: true, lon, lat};      // the lines for this view are still on their way
    return {kind: layer, id, name: id == null ? "" : nameOf(layer, id), lon, lat, precinct: precinct ? {id: precinct.id, name: precinct.properties.name} : null};
  }
  function pick(px, py) { const r = at(px, py); if (r.kind !== "poll") { sel = r.id == null ? null : {kind: r.kind, id: r.id}; schedule(); } if (opt.onPick) opt.onPick(r); }
  function locate(lon, lat) {      // the precinct a spot is in, worked out here: the county files whose box holds it, then the reader's own exact test
    const cs = IDX.counties.filter(c => lon >= c.bbox[0] - .003 && lon <= c.bbox[2] + .003 && lat >= c.bbox[1] - .003 && lat <= c.bbox[3] + .003);
    if (!cs.length) return Promise.resolve(null);
    return Promise.all(cs.map(c => load(c.file))).then(fs => {
      const hits = [];
      fs.forEach(f => { const h = MNGeo.precinctAt(f, lon, lat); if (!h) return; [h].concat(h.near || []).forEach(x => hits.push({file: f, geometry: x.geometry, edge: x.edge, inside: !!x.inside})); });
      if (!hits.length) return null;
      hits.sort((a, b) => (b.inside - a.inside) || (a.edge - b.edge));
      const best = hits[0], near = hits.slice(1).filter(x => x.edge <= MNGeo.NEAR && x.geometry !== best.geometry);
      const out = {lon, lat, county: best.file.county, file: best.file, precinct: best.geometry, inside: best.inside, edge: best.edge, near: near.map(x => x.geometry), school: null, schoolKnown: true};
      // a precinct that reaches more than one city or township does not say which one a spot is in: the layer of those places answers that
      // for a point (a precinct its own table puts in a city keeps that city); where the layer cannot be had, the page says the place is the largest one
      const bp = best.geometry.properties, many = (bp.mcd_all || []).length > 1 && !bp.city;
      const place = many && LAYER.mcd ? load(LAYER.mcd.file).then(lf => { const h = MNGeo.shapeAt(lf, "mcd", lon, lat);
        if (h && bp.mcd_all.indexOf(h.geometry.id) >= 0) { out.mcd = h.geometry.id; out.mcdName = (h.geometry.properties || {}).name || ""; } }).catch(() => {}) : Promise.resolve();
      if (many) out.mcdMany = true;
      return place.then(() => new Promise(res => {
        let over = false; const end = id => { if (over) return; over = true; out.school = id; res(out); };
        try { MNGeo.schoolAt(best.geometry, lon, lat, (id, cb) => { load(schoolPath(id)).then(cb).catch(() => { out.schoolKnown = false; end(null); }); }, end); }
        catch (e) { out.schoolKnown = false; end(null); }
      }));
    });
  }

  /* ----- one shape, found by its id: the layer, the view fitted to it, and it selected ----- */
  function boxOf(kind, id, counties) {
    if (kind === "county" && COUNTY[id]) return Promise.resolve(COUNTY[id].bbox);
    const lf = files[(LAYER[kind] || {}).file];
    if (lf) { const g = byId(lf, kind)[id]; return Promise.resolve(g ? g.bbox : null); }
    if (kind === "school") return load(schoolPath(id)).then(f => f.bbox, () => null);
    if (counties && counties.length && KINDS.indexOf(kind) >= 0 && counties.every(c => COUNTY[c]))
      return Promise.all(counties.map(c => load(COUNTY[c].file).catch(() => null))).then(fs => { let b = null;
        fs.forEach(f => { if (f) f.objects.precincts.geometries.forEach(g => { if (!holds(g.properties[kind], id)) return; const x = g.bbox;
          b = b ? [Math.min(b[0], x[0]), Math.min(b[1], x[1]), Math.max(b[2], x[2]), Math.max(b[3], x[3])] : x.slice(); }); });
        return b; });
    return LAYER[kind] ? load(LAYER[kind].file).then(f => { const g = byId(f, kind)[id]; return g ? g.bbox : null; }, () => null) : Promise.resolve(null);
  }
  function focus(kind, id, counties) {
    if (LAYER[kind]) layer = kind;
    sel = {kind, id};
    return boxOf(kind, id, counties).then(b => { if (dead) return false; if (b) { const v = fitTo(b, Math.min(48, W / 8), 15.5); if (streets) v.z = Math.floor(v.z); setView(v); } else schedule(); return !!b; });
  }

  /* ----- hands: one finger or the mouse moves the map, two fingers pinch, the wheel and a double tap zoom, the keyboard does all of it ----- */
  const ptr = new Map();
  let drag = null, pinch = null, lastTap = null, wheelSum = 0, wheelAt = 0;
  const local = e => { const r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  el.addEventListener("pointerdown", e => {
    if (e.button || e.target.closest("a, button")) return;      // the credit keeps its click
    lastType = e.pointerType || "";
    if (keys) { keys = false; schedule(); }
    if (e.isPrimary && ptr.size) { ptr.clear(); pinch = null; }      // a first finger while one is still counted: its lift was missed, so start afresh
    ptr.set(e.pointerId, local(e));
    if (ptr.size === 1) drag = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false, touch: e.pointerType === "touch"};
    else if (ptr.size === 2) { const p = [...ptr.values()], cx = (p[0][0] + p[1][0]) / 2, cy = (p[0][1] + p[1][1]) / 2, k = scale();
      pinch = {d: Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) || 1, z: view.z, wx: view.x + (cx - W / 2) / k, wy: view.y + (cy - H / 2) / k}; drag = null; }
  });
  addEventListener("pointermove", e => {
    if (!ptr.has(e.pointerId)) return;
    ptr.set(e.pointerId, local(e));
    if (pinch && ptr.size >= 2) { const p = [...ptr.values()], cx = (p[0][0] + p[1][0]) / 2, cy = (p[0][1] + p[1][1]) / 2;
      const z = Math.max(fit.z, Math.min(MAXZ, pinch.z + Math.log2((Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) || 1) / pinch.d))), k = Math.pow(2, z);
      view = clamp({x: pinch.wx - (cx - W / 2) / k, y: pinch.wy - (cy - H / 2) / k, z}); schedule(); return; }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true; el.classList.add("drag");
    const k = scale(); view = clamp({x: drag.vx - dx / k, y: drag.vy - dy / k, z: view.z}); schedule();
  }, sig);
  function lift(e) {
    if (!ptr.has(e.pointerId)) return;
    ptr.delete(e.pointerId);
    if (pinch) { if (ptr.size < 2) { pinch = null; if (streets) { view.z = Math.max(fit.z, Math.round(view.z)); view = clamp(view); } schedule(); } return; }
    const d = drag; drag = null; el.classList.remove("drag");
    if (!d || d.moved || e.type !== "pointerup") return;
    const p = local(e), now = Date.now();
    if (d.touch && lastTap && now - lastTap.t < 330 && Math.hypot(p[0] - lastTap.x, p[1] - lastTap.y) < 32) { lastTap = null; stepIn(p[0], p[1]); return; }      // a double tap
    lastTap = {t: now, x: p[0], y: p[1]};
    pick(p[0], p[1]);
  }
  addEventListener("pointerup", lift, sig);
  addEventListener("pointercancel", lift, sig);
  el.addEventListener("dblclick", e => { if (e.target.closest("a, button")) return; e.preventDefault(); if (lastType === "touch") return; const p = local(e); stepIn(p[0], p[1]); });
  let pageScroll = 0;
  addEventListener("scroll", () => { pageScroll = Date.now(); }, {passive: true, signal: off.signal});
  el.addEventListener("wheel", e => {
    const out = e.deltaY > 0;
    if (Date.now() - pageScroll < 400) return;      // a reader rolling the page past the map is not asking the map to zoom
    if ((out && view.z <= fit.z + 1e-6) || (!out && view.z >= MAXZ - 1e-6)) return;      // nothing left to zoom: the page scrolls on
    e.preventDefault();
    wheelSum += e.deltaY * (e.deltaMode === 1 ? 33 : 1) * (e.ctrlKey ? 5 : 1);
    const now = Date.now();
    if (Math.abs(wheelSum) < 50 || now - wheelAt < 120) return;      // a notch of the wheel is one step; a trackpad's small pushes add up to one
    wheelAt = now; const p = local(e), into = wheelSum < 0; wheelSum = 0;
    if (into) stepIn(p[0], p[1]); else stepOut(p[0], p[1]);
  }, {passive: false});
  el.addEventListener("keydown", e => {
    if (e.target !== el || e.ctrlKey || e.metaKey || e.altKey) return;
    const s = 90 / scale(), k = e.key; let used = true;
    if (k === "ArrowLeft") setView({x: view.x - s, y: view.y, z: view.z}); else if (k === "ArrowRight") setView({x: view.x + s, y: view.y, z: view.z});
    else if (k === "ArrowUp") setView({x: view.x, y: view.y - s, z: view.z}); else if (k === "ArrowDown") setView({x: view.x, y: view.y + s, z: view.z});
    else if (k === "+" || k === "=") stepIn(); else if (k === "-" || k === "_") stepOut(); else if (k === "0") setView(fit);
    else if (k === "Enter" || k === " ") pick(W / 2, H / 2); else if (k === "Escape") { sel = null; schedule(); if (opt.onPick) opt.onPick({kind: layer, id: null, cleared: true}); }
    else used = false;
    if (used) { e.preventDefault(); if (!keys) { keys = true; schedule(); } }
  });
  el.addEventListener("blur", () => { if (keys) { keys = false; schedule(); } });
  addEventListener("resize", resize, sig);
  const ro = typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null; if (ro) ro.observe(el);
  const mo = new MutationObserver(schedule); mo.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
  resize();
  if (!W) setTimeout(resize, 120);

  return {
    layer: () => layer, view: () => view && {z: view.z, lon: lonAt(view.x), lat: latAt(view.y)}, nameOf, locate, focus, load,
    setLayer(kind) { if (LAYER[kind] && kind !== layer) { layer = kind; if (sel && sel.kind !== kind) sel = null; schedule(); } },
    select(kind, id) { sel = id == null ? null : {kind, id}; schedule(); },
    setMine(m) { mine = m || null; if (mine && mine.c && COUNTY[mine.c] && view && view.z >= 10.5) want(COUNTY[mine.c].file); schedule(); },
    setPin(ll) { pin = ll || null; schedule(); },
    setPolls(doc) { polls = doc && doc.places ? doc : null; schedule(); },
    setStreets, streets: () => streets,
    zoomIn: () => stepIn(), zoomOut: () => stepOut(), whole: () => setView(fit),
    goTo(lon, lat, z) { setView({x: mx(lon), y: my(lat), z: z == null ? view.z : z}); },
    fitBox(b, most, least) { const v = fitTo(b, Math.min(60, W / 6), most); if (streets) v.z = Math.floor(v.z); if (least && v.z < least) v.z = least; setView(v); },
    pickAt(lon, lat) { pick(X(mx(lon)), Y(my(lat))); },
    entries(kind) { const f = files[(LAYER[kind] || {}).file]; return f ? f.objects[kind].geometries.map(g => [g.id, g.properties.name]) : null; },
    props(kind, id) { const f = files[(LAYER[kind] || {}).file], g = f && byId(f, kind)[id]; return g ? g.properties : null; },
    redraw: schedule, resize,
    destroy() { dead = true; off.abort(); if (ro) ro.disconnect(); mo.disconnect(); clearTimeout(tileTimer); keepNow = new Set(); sweep(); }
  };
}
window.BallotMap = BallotMap;
})();

/* ---------- the map set into the page's "your ballot": the switch for which lines to draw, the panel beside it, the pin, the
   notices that travel with the lines. It uses the page's own words and helpers by name (ST, D, raceTitle, legPreview ...). ---------- */
window.GEOKIT = (function () {
  const G = BOOT.geo;
  let map = null, IDX = null, POLLS = null, spot = null, box = null, ready = null, wanted = null, listed = "";
  /* the map files' own words and ids, where they are not the page's usual ones: what a kind of district is called there (GW), what its
     places' names say they are (GM), and a county's id in the files against the key the page files it under (pk, gk) */
  const GW = G.words || {}, GM = G.muni && G.muni.length ? G.muni : (ST.muni && ST.muni.length ? ST.muni : ["city"]), CK = G.ck || {}, KC = {};
  Object.keys(CK).forEach(k => { KC[CK[k]] = k; });
  const pk = id => CK[id] || id, gk = id => KC[id] || id;
  const GN = G.names || {}, atLarge = d => /^0+$/.test(String(d));      // names the files give where an id is not a number; a state with one seat in Congress
  const bare = w => String(w).replace(/^county\s+/i, ""), title = w => String(w).replace(/\b[a-z]/g, c => c.toUpperCase());
  const said = (kind, usual) => GW[kind] ? [capital(bare(GW[kind])) + "s", capital(GW[kind])] : usual;
  const KW = {county: [capital(COS), capital(CO1)], mcd: [capital(andList(GM.map(w => MUNIS[w] || w))), capital(orList(GM))],
    school: [capital(ST.schoolOne || "school district") + "s", capital(ST.schoolOne || "school district")], com: said("com", ["Commissioner districts", "County commissioner district"]),
    ward: said("ward", ["Wards", "City ward"]), house: [ST.loT, ST.loD], senate: [ST.upT, ST.upD], cd: ["Congress", "Congressional district"], judicial: said("judicial", ["Judicial districts", "Judicial district"]),
    swcd: said("swcd", ["Soil and water", "Soil and water district"]), hospital: ["Hospital districts", "Hospital district"], park: ["Park districts", "Park district"]};
  const ORDER = ["county", "mcd", "school", "com", "ward", "house", "senate", "cd", "judicial", "swcd", "hospital", "park"];
  const kinds = () => ORDER.filter(k => G.kinds.includes(k)).concat(G.kinds.filter(k => !ORDER.includes(k)));
  const words = k => KW[k] || [capital(k), capital(k)];
  const side = html => { const s = $("#gside"); if (s) s.innerHTML = html; };
  const feet = m => { const f = m * 3.2808; return f < 20 ? Math.max(5, Math.round(f / 5) * 5) : Math.round(f / 10) * 10; };
  const schoolWho = () => { const s = ((IDX && IDX.sources) || []).find(x => /school/i.test((x.id || "") + " " + (x.title || ""))); return s ? String(s.agency || "").split(/[;,]/)[0].trim() : "the state's school district map"; };
  const finder = () => { const P = G.polls || {}; return P.finder ? `<a href="${esc(P.finder)}" target="_blank" rel="noopener">Open the ${ST.partial ? "state&rsquo;s official" : WHO} polling place finder</a>` : ""; };      // where the lists are the counties' own, the finder is still the state's

  /* what a shape is called, from what the page already holds (the map's own files say it first, where they are here) */
  function dataName(kind, id) {
    const s = String(id), a = s.split("|")[0], b = s.split("|")[1];
    if (kind === "county") return cName(pk(s));
    if (kind === "mcd") return (D.places.M[mKey(s)] || {}).n || s;
    if (kind === "school") return SCHG[s] ? placeName(SCHG[s]) : s;
    if (kind === "house") return `${ST.loD} ${s}`;
    if (kind === "senate") return `${ST.upD} ${s}`;
    if (kind === "cd") return atLarge(s) ? "Congressional district, at large" : `Congressional District ${s}`;
    if (kind === "judicial" && GN.judicial && GN.judicial[s]) return GN.judicial[s];
    if (kind === "judicial") return GW.judicial ? `${capital(GW.judicial)} ${s.replace(/^\D+/, "")}` : judicialName(s.replace(/^\D+/, ""));
    if (kind === "com") return `${cName(pk(a))}, ${GW.com ? title(bare(GW.com)) : "Commissioner District"} ${b}`;
    if (kind === "ward") return `${(D.places.M[a] || {}).n || a}, ${b}`;
    if (kind === "hospital") return ((D.places.H || {})[s] || {}).n || s;
    const r = (BYG[kind + ":" + s] || [])[0];
    return r ? raceWhere(r) : s;
  }
  function short(kind, id, name) {      // what is written on the map itself
    const s = String(id), n = String(name || "");
    if (kind === "county") return n.replace(/ County$/, "");
    if (kind === "mcd") return n.replace(/ city$/i, "").replace(/^city of /i, "");
    if (kind === "cd" && atLarge(s)) return "At large";
    if (kind === "house" || kind === "senate" || kind === "cd") return s;
    if (kind === "judicial") return s.replace(/^\D+/, "") || n.replace(/\s+Judicial District$/i, "");
    if (kind === "com" || kind === "park") return s.split("|")[1] || s;
    if (kind === "ward") return s.split("|")[1] || s;
    if (kind === "school") return n.replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+(?:Public\s+)?School\s+Districts?$/i, "");
    return n;
  }
  function racesOf(kind, id) { return kind === "mcd" ? D.races.filter(r => r.pk === mPk(id) && LOCAL.includes(r.lv)) : (BYG[kind + ":" + id] || []); }
  function countiesOf(kind, id) {      // the counties whose precinct files hold a shape, so its lines can be found without the layer's whole file
    const s = String(id), a = s.split("|")[0];
    if (kind === "mcd") return (D.places.M[s] || {}).c || [];
    if (kind === "ward") return (D.places.M[a] || {}).c || [];
    if (kind === "com") return [a];
    if (kind === "park") return D.counties[a] ? [a] : (D.places.M[a] || {}).c || [];
    if (kind === "hospital") return ((D.places.H || {})[s] || {}).c || [];
    return [...new Set((BYG[kind + ":" + s] || []).flatMap(r => r.c || []))];
  }

  /* ----- the panel beside the map ----- */
  const BACK = () => `<p class="sidehint"><button type="button" class="linkbtn" data-side="home">${MINE && MINE.z ? "Back to where you are" : "Back to the map&rsquo;s key"}</button></p>`;
  function pollHTML(z) {
    const P = G.polls || {};
    if (P.status === "loaded" && POLLS) {
      const i = POLLS.precinct[z.p], pl = i == null ? null : POLLS.places[i], mail = (POLLS.no_place || {})[z.p];
      const tail = `<small>From the ${esc(P.source || "state's list of polling places")}. ${finder() ? `The finder is the authority: ${finder()}.` : ""}</small>`;
      if (pl) return `<div class="gpoll"><b>Your polling place</b>${esc(pl.name)}${pl.address ? `, ${esc(pl.address)}` : ""}${pl.city ? `, ${esc(pl.city)}` : ""}${tail}</div>`;
      return `<div class="gpoll"><b>Your polling place</b>${mail ? `Your ${UNIT} ${esc(mail)}.` : `This ${UNIT} is not on the list of polling places loaded here.`}${tail}</div>`;
    }
    return `<div class="gpoll"><b>Polling places are not shown here</b>${esc(P.why || `No list of polling places is loaded for ${ST.name}.`)}${finder() ? ` ${finder()}.` : ""}</div>`;
  }
  function zonesHTML(z) {      // every district a located reader is in, by name; a tap shows it on the map
    const row = (label, value, kind, id) => value ? `<div><dt>${label}</dt><dd>${kind ? `<button type="button" class="zbtn" data-zone="${esc(kind + ":" + id)}" title="Show it on the map">${esc(value)}</button>` : esc(value)}</dd></div>` : "";
    const nb = z.sch.length - (z.ov || 0), split = nb > 1;      // the districts that share the precinct out; any after them lie over those (a union high school district)
    // whole-number shares that add to 100 when the districts cover the precinct (largest remainders get the spare points);
    // where part of the precinct lies in no district the shares fall short of 100, and are only rounded
    const shares = (() => { const p = (z.pct || []).slice(0, nb).map(Number), sum = p.reduce((a, b) => a + b, 0), out = p.map(Math.floor);
      if (!p.length || p.some(isNaN) || Math.abs(sum - 100) > .6) return p.map(Math.round);
      let spare = 100 - out.reduce((a, b) => a + b, 0);
      p.map((v, i) => [v - out[i], i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).forEach(([, i]) => { if (spare > 0) { out[i]++; spare--; } });
      return out; })();
    const rows =[row(esc(capital(UNIT)), z.pn), row(esc(capital(CO1)), cName(z.c), "county", z.c), row(esc(KW.mcd[1]), z.mn || dataName("mcd", z.m), "mcd", z.m),
      z.mo ? row("", (z.mon || dataName("mcd", z.mo)) + ` (${z.mn || dataName("mcd", z.m)} lies inside it: you are a voter of both)`, "mcd", z.mo) : "",
      ...(z.w || []).map(w => row(GW.ward ? esc(capital(GW.ward)) : "City council", w.split("|")[1] || w, "ward", w)),
      z.com ? row(GW.com ? esc(capital(GW.com)) : "County commissioner", "District " + (z.com.split("|")[1] || z.com), "com", z.com) : "",
      ...z.sch.map((i, n) => row(n ? "" : esc(capital(ST.schoolOne || "school district")), ((z.schn || {})[i] || dataName("school", i)) + (n >= nb ? ` (it lies over the other${nb > 1 ? "s" : ""}: you are in it as well)` : split && (z.pct || [])[n] ? ` (${shares[n] ? "about " + shares[n] : "under 1"}% of the ${UNIT}’s area${i === z.s1 ? "; your spot" : ""})` : ""), "school", i)),
      row(esc(ST.loT), z.hd ? "District " + z.hd : "", "house", z.hd), row(esc(ST.upT), z.sd ? "District " + z.sd : "", "senate", z.sd), row("Congress", z.cd ? (atLarge(z.cd) ? "At large: the whole state" : "District " + z.cd) : "", "cd", z.cd),
      row(esc(KW.judicial[1]), z.jd ? (z.jdn || dataName("judicial", z.jd)) : "", "judicial", z.jd), row(GW.swcd ? esc(capital(GW.swcd)) : "Soil and water", z.sw ? (z.swn || dataName("swcd", z.sw)) : "", "swcd", z.sw),
      ...(z.sw2 || []).map((i, n) => row("", ((z.sw2n || [])[n] || dataName("swcd", i)) + ` (it holds a smaller part of the ${UNIT})`, "swcd", i)),
      ...((BOOT.geo || {}).says || []).map(([k, w]) => z.x && z.x[k] ? row(esc(capital(w)), (z.x[k + "_n"] || z.x[k]) + (z.x[k + "_area"] ? ", " + z.x[k + "_area"].join(" and ") : "") + (z.x[k + "_pct"] ? ` (about ${Math.round(z.x[k + "_pct"])}% of the ${UNIT} is inside it)` : "")) : ""),
      row("Hospital district", z.ho ? (z.hon || dataName("hospital", z.ho)) : "", "hospital", z.ho), row("Park district", z.pk ? (z.pkn || dataName("park", z.pk)) : "", "park", z.pk)].join("");
    const edge = !z.in ? `Your spot is on a ${UNIT} line, as near as this map can tell. ${esc(z.pn)} is the nearest ${UNIT}${z.nb ? `; ${esc(z.nb)} is on the other side` : ""}.`
      : z.edge <= 30 ? `Your spot is about ${feet(z.edge)} feet from this ${UNIT}&rsquo;s line${z.nb ? ` with ${esc(z.nb)}` : ""}; a spot that close can fall on either side of it.` : "";
    const acc = z.acc && z.acc > Math.max(40, z.edge) ? `Your device placed you to within about ${num(feet(z.acc))} feet, and the nearest ${UNIT} line is about ${num(feet(z.edge))} feet away, so the ${UNIT} could be a neighbouring one.` : "";
    const school = split ? `Your ${UNIT} is split between ${num(nb)} ${esc(ST.schoolOne || "school district")}s. ${z.s1 ? `By the ${esc(schoolWho())}&rsquo;s map your spot is in ${esc((z.schn || {})[z.s1] || z.s1)}` : "Which one your spot is in could not be settled here"}; ${nb === 2 ? "both are" : "all are"} on the list below, because those lines are generalised.`
      : z.out ? `Part of this ${UNIT} lies in no ${esc(ST.schoolOne || "school district")}.` : "";
    const placed = z.mq ? `This ${UNIT} reaches more than one ${esc(KW.mcd[1].toLowerCase())}, and which one your spot is in could not be settled here; the one named holds most of the ${UNIT}.` : "";
    // where the map's smallest pieces are an earlier year's (the files say which, and whose): said beside the reader's own
    const old = G.old ? `This ${UNIT} is drawn and named as it stood in ${esc(G.old.y)}${z.unl ? `, and the state&rsquo;s ${esc(z.unl)} list no longer carries it under that name or code, so it has been redrawn or renamed since` : ""}. ${esc((G.old.t || []).slice(2).join(" "))}` : "";
    return `<span class="kick">Where you are</span><h3>${esc(z.pn)}</h3>
      <p class="held">Your ${UNIT}${G.old ? ` (${esc(G.old.y)} lines)` : ""} and every district it is in, worked out on this device. Tap a name to see it on the map.</p>
      <dl class="zlist">${rows}</dl>
      ${[old, edge, acc, placed, school].filter(Boolean).map(t => `<p class="znote">${t}</p>`).join("")}
      ${pollHTML(z)}
      <p class="sidehint">${spot ? `The pin is your spot. The exact spot is used here and now and is not kept: after a reload your ${UNIT} stays marked in gold instead. A copy rounded to about half a mile stays on this device, for the site&rsquo;s other pages, until you tap &ldquo;Forget&rdquo;.` : `Your ${UNIT} is marked in gold. The exact spot was not kept; a copy rounded to about half a mile stays on this device until you tap &ldquo;Forget&rdquo;.`} &ldquo;Show streets&rdquo; draws the streets around it; OpenStreetMap&rsquo;s servers then see which map squares are asked for. <button type="button" class="linkbtn" data-zone="me">Go to my ${UNIT}</button></p>`;
  }
  function sideHome() {
    if (MINE && MINE.z) return zonesHTML(MINE.z);
    const k = map ? map.layer() : "county", P = G.polls || {};
    return `<span class="kick">${NM} &middot; the map</span><h3>${esc(words(k)[0])}</h3>
      <p class="held">Tap a place on the map to see its name and open its races. The switch above the map draws other lines; zoom in and the lines become each ${UNIT}&rsquo;s own, down to a street.</p>
      <p class="held"><b>Use my location</b> drops a pin at your spot, finds your ${UNIT} on this device and lists every district you are in.</p>
      ${P.status === "loaded" ? `<p class="held">Polling places appear as small squares once you zoom in.</p>` : `<div class="gpoll"><b>Polling places are not on this map</b>${esc(P.why || `No list of polling places is loaded for ${ST.name}.`)}${finder() ? ` ${finder()}.` : ""}</div>`}`;
  }
  function raceList(rs, more) {
    const top = rs.slice(0, 12), rest = rs.length - top.length;
    return `<ul class="glist">${top.map(r => { const g = general(r); return `<li><a href="${hrefRace(r)}"><b>${esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${g.length ? plural(g.length, "candidate") : (EMPTY || "no candidate on the list")}</span></a></li>`; }).join("")}</ul>${rest > 0 ? `<p class="sidehint">And ${num(rest)} more${more ? `: ${more}` : ""}.</p>` : ""}`;
  }
  function sideShape(kind, id, name, precinct) {
    const rs = racesOf(kind, id), kw = words(kind)[1], at = precinct ? `<p class="sidehint">The ${UNIT} at that spot: ${esc(precinct.name)}.</p>` : "";
    if (kind === "house" || kind === "senate") { const r = legRace(kind === "senate" ? "upper" : "lower", String(id));
      return (r ? legPreview(r) : `<span class="kick">${esc(kw)}</span><h3>${esc(name)}</h3><p class="held">${noLegRace(kind === "senate" ? "upper" : "lower", "this district")}</p>`) + at + BACK(); }
    let body;
    if (kind === "cd") { const p = (map && map.props("cd", id)) || {}, rid = p.race || `2026-${ST.code}-H${String(id).padStart(2, "0")}`;
      body = BOOT.links.us ? `<p class="held">The race for the U.S. House here is on the Congress pages.</p><a class="rpgo" href="../us/#race=${encodeURIComponent(rid)}">Open the race &rsaquo;</a>` : `<p class="held">The race for the U.S. House here is not on this page.</p>`; }
    else if (kind === "county") body = `<p class="held">${plural(COUNTS[pk(id)] || 0, "contest")} on the November 3 ballot reach${(COUNTS[pk(id)] || 0) === 1 ? "es" : ""} ${esc(name)}.${rs.length ? " The offices the whole county elects:" : ""}</p>${rs.length ? raceList(rs) : ""}<a class="rpgo" href="#county=${esc(pk(id))}">Open ${esc(name)} &rsaquo;</a>`;
    else if (kind === "judicial") body = rs.length ? raceList(rs, `<a href="#courts">see every ${rs.every(r => r.k === "district_court") ? "district court" : "court"} race</a>`) : `<p class="held">No seat of this district&rsquo;s court ${onList(WHO, " for November 3")}.</p>`;
    else { const cs = kind === "mcd" ? ((D.places.M[mKey(id)] || {}).c || []) : [];
      body = (rs.length ? raceList(rs) : `<p class="held">No contest for ${esc(name)} ${onList(LWHO, " for November 3", cs.length === 1 ? cs[0] : "")}.</p>`)
        + (cs.length ? `<p class="sidehint">Everything else on a ballot here: ${cs.map(f => `<a href="#county=${esc(f)}">${esc(cName(f))}</a>`).join(", ")}.</p>` : ""); }
    return `<span class="kick">${esc(kw)}</span><h3>${esc(name)}</h3>${body}${at}${BACK()}`;
  }
  function picked(r) {
    if (r.cleared) { side(sideHome()); return; }
    if (r.kind === "poll") { const p = r.place; side(`<span class="kick">Polling place</span><h3>${esc(p.name)}</h3><p class="held">${esc([p.address, p.city].filter(Boolean).join(", "))}</p><p class="sidehint">${finder() ? `Which ${UNIT}s vote here, and whether yours does, is for the finder to say: ${finder()}.` : ""}</p>${BACK()}`); return; }
    if (r.loading) side(`<span class="kick">${esc(words(r.kind)[1])}</span><p class="held">The lines for this part of the map are still loading. Tap again in a moment.</p>${BACK()}`);
    else if (r.id == null) side(`<span class="kick">${esc(words(r.kind)[1])}</span><p class="held">${r.precinct ? `No ${esc(words(r.kind)[1].toLowerCase())} at that spot (${UNIT} ${esc(r.precinct.name)}).` : `Nothing of ${NM}&rsquo;s is at that spot on the map.`}</p>${BACK()}`);
    else side(sideShape(r.kind, r.id, r.name, r.precinct));
    const s = $("#gside"); if (s && !matchMedia("(hover: hover)").matches && s.getBoundingClientRect().top > innerHeight - 90) s.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"});
  }

  /* ----- the switch, the Find box, the notices ----- */
  function findEntries(kind) {      // [[what a reader types, the shape's id]]
    const out = [];
    if (kind === "county") Object.keys(D.counties).forEach(f => out.push([cName(f), gk(f)]));
    else if (kind === "mcd" || kind === "school") {
      // the places the lists name, each under the map's own id for it (the page may file it under a shorter key); then every other
      // place the map draws, so that one with no contest on the lists loaded so far can still be found
      const got = map && map.entries(kind), ids = new Set((got || []).map(x => x[0])), seen = new Set(), L = kind === "mcd" ? "M" : "S";
      Object.entries(D.places[L] || {}).forEach(([k, P]) => { const long = `${ST.code}-${L}-${k}`, id = P.g || GID[L + k] || (ids.has(long) && !ids.has(k) ? long : k);
        seen.add(id); out.push([kind === "mcd" ? `${P.n}${(P.c || []).length ? ` (${P.c.map(cShort).join(", ")})` : ""}` : P.n, id]); });
      (got || []).forEach(([id, name]) => { if (!seen.has(id) && name) out.push([name, id]); });
    }
    else if (kind === "house") D.hds.forEach(d => out.push([`${ST.loD} ${d}`, d]));
    else if (kind === "senate") D.sds.forEach(d => out.push([`${ST.upD} ${d}`, d]));
    else { const got = map && map.entries(kind);
      if (got) got.forEach(([id, name]) => out.push([name, id]));
      else Object.keys(BYG).filter(k => k.startsWith(kind + ":")).forEach(k => out.push([dataName(kind, k.slice(kind.length + 1)), k.slice(kind.length + 1)])); }
    return out.sort((a, b) => a[0].localeCompare(b[0], undefined, {numeric: true}));
  }
  let found = [];
  function fillFind(force) {
    const inp = $("#gfind"), dl = $("#gfindlist"); if (!inp || !dl || !map) return;
    const k = map.layer(), key = k + (map.entries(k) ? "+" : "");      // listed again once the layer's own file has come
    if (listed === key && !force) return;
    listed = key; found = findEntries(k);
    dl.innerHTML = found.map(([label]) => `<option value="${esc(label)}"></option>`).join("");
  }
  function setLayer(kind, quiet) {
    if (!map) return;
    map.setLayer(kind);
    $$("#glayers button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.k === kind)));
    const sel = $("#glayer"); if (sel) sel.value = kind;
    const inp = $("#gfind"); if (inp) { inp.value = ""; inp.placeholder = `Find a${/^[aeiou]/i.test(words(kind)[1]) ? "n" : ""} ${words(kind)[1].toLowerCase()}`; inp.setAttribute("aria-label", inp.placeholder + " by name"); }
    listed = "";
    $("#gmap").setAttribute("aria-label", `Map of ${ST.name}: ${words(kind)[0].toLowerCase()}`);
    if (!quiet) side(sideHome());
  }
  function show(kind, id) {      // one shape, by its id: on the map and in the panel (with no id: that kind of line, drawn)
    if (!map) { wanted = [kind, id]; return; }
    if (id == null || id === "") { if (G.kinds.includes(kind)) setLayer(kind); return; }
    if (kind === "county") id = gk(id);      // the page names a county by its own key; the map's files by theirs
    setLayer(kind, true);
    const name = map.nameOf(kind, id);
    side(sideShape(kind, id, name, null));
    map.focus(kind, id, countiesOf(kind, id).map(gk)).then(ok => { if (!map || !$("#gside")) return;      // the page moved on while the lines were fetched
      if (!ok) side(`<span class="kick">${esc(words(kind)[1])}</span><h3>${esc(name)}</h3><p class="held">The map files hold no lines for it, so it cannot be drawn.</p>${racesOf(kind, id).length ? raceList(racesOf(kind, id)) : ""}${BACK()}`);
      else side(sideShape(kind, id, map.nameOf(kind, id), null)); }, () => {});
  }
  function aboutHTML() {
    const N = IDX.notes || {};
    const src = (IDX.sources || []).map(s => `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}${s.about ? `<small>${esc(s.about)}</small>` : ""}<small><span class="tag fact">Fact</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(hostOf(s.url))}</a>` : ""}${s.published ? ` &middot; published ${esc(s.published)}` : ""}${s.current_to ? ` &middot; current to ${esc(s.current_to)}` : ""}${s.fetched ? ` &middot; read ${esc(s.fetched)}` : ""}${s.rows ? ` &middot; ${num(s.rows)} rows` : ""}${s.sha256 ? ` &middot; SHA-256 ${esc(String(s.sha256).slice(0, 16))}&hellip;` : ""}</small>${s.use ? `<small><b>Its notice on use:</b> ${esc(s.use)}</small>` : ""}${s.disclaimer ? `<small><b>Its disclaimer, word for word:</b> ${esc(s.disclaimer)}</small>` : ""}</div>`).join("");
    const plainly = t => String(t).replace(/\bschool_pct is\b/, "the share shown beside a district is");      // the files' own note names a field; a reader is told what it is
    const notes = Object.keys(N).filter(k => !["disclaimers", "precinct_ids"].includes(k)).map(k => N[k]);      // every note the files carry about their lines; the sources' own disclaimers are shown with the sources below
    return `${notes.filter(t => t && typeof t === "string").map(t => `<p class="ynote">${esc(plainly(t))}</p>`).join("")}<div class="srclist" style="margin-top:12px">${src}</div>`;
  }
  const mineOf = z => ({c: z.gc || z.c, p: z.p, at: z.at, ids: {county: z.gc || z.c, mcd: z.m, ward: (z.w || [])[0], com: z.com, house: z.hd, senate: z.sd, cd: z.cd, judicial: z.jd, swcd: z.sw, hospital: z.ho, park: z.pk, school: z.s1 || z.sch[0]}});
  function zonesOf(r, acc) {      // what is kept of a located reader, on their device only: the precinct and its districts, each with its name; never the spot
    const p = r.precinct.properties, n = r.file.names || {}, nm = (k, id) => (id && (n[k] || {})[id]) || "";
    const sch = (p.school || []).slice(); if (r.school && !sch.includes(r.school)) sch.unshift(r.school);
    // districts that lie over others (a union high school district over the elementary ones that feed it) come last in the list, and
    // with them the shares pass 100: the first ones, up to 100, share the precinct out; the rest lie over those
    const pcts = (p.school || []).length === sch.length ? (p.school_pct || []).map(Number) : []; let nb = 0, sum = 0;
    while (nb < pcts.length && sum + pcts[nb] <= 101.5) sum += pcts[nb++];
    const over = pcts.length === sch.length && nb > 0 && nb < sch.length ? {ov: sch.length - nb} : {};
    // what the precinct says of districts no layer draws (BOOT.geo.says), and a second district of a kind that holds part of it (split)
    const says = (BOOT.geo || {}).says || [], x = {}, sp = p.split || {}, sw2 = Object.keys(sp.swcd || {}).filter(i => i !== p.swcd);
    says.forEach(([k]) => { x[k] = p[k] || ""; if (!p[k]) return; x[k + "_n"] = nm(k, p[k]);
      if (p[k + "_area"]) x[k + "_area"] = sp[k + "_area"] ? Object.keys(sp[k + "_area"]) : [p[k + "_area"]];
      if (p[k + "_pct"]) x[k + "_pct"] = p[k + "_pct"]; });
    const gone = Object.keys(p).find(k => /^listed_\d{4}$/.test(k) && p[k] === false);      // the files say the state's list of that year no longer carries this piece
    const jdn = nm("judicial", p.judicial);      // the files' own name for the court's district, where they give one
    // a place that lies inside another, where the files say a voter of the one is a voter of the other too (a village in its township,
    // BOOT.geo.within): the spot's own place is the inner one, and the precinct's the one around it
    const W = (BOOT.geo || {}).within, kindOf = t => (/\b(\w+)$/.exec(String(t || "")) || ["", ""])[1].toLowerCase();
    const mo = W && r.mcd && r.mcd !== p.mcd && (p.mcd_all || []).includes(p.mcd) && kindOf(r.mcdName || nm("mcd", r.mcd)) === W[0] && kindOf(nm("mcd", p.mcd)) === W[1] ? p.mcd : "";
    const more = {...(says.length ? {x} : {}), ...(sw2.length ? {sw2, sw2n: sw2.map(i => nm("swcd", i))} : {}), ...(gone ? {unl: gone.slice(7)} : {}), ...(jdn ? {jdn} : {}), ...(mo ? {mo, mon: nm("mcd", mo)} : {})};
    return {p: r.precinct.id, pn: p.name, at: p.c, c: pk(p.county), ...(pk(p.county) !== p.county ? {gc: p.county} : {}), ...over, m: r.mcd || p.mcd, mn: r.mcd ? (r.mcdName || nm("mcd", r.mcd)) : nm("mcd", p.mcd), ...(r.mcdMany && !r.mcd ? {mq: 1} : {}), w: p.ward || [], com: p.com || "", hd: p.house || "", sd: p.senate || "", cd: p.cd || "", jd: p.judicial || "",
      sw: p.swcd || "", swn: nm("swcd", p.swcd), ho: p.hospital || "", hon: nm("hospital", p.hospital), pk: p.park || "", pkn: nm("park", p.park),
      sch, schn: Object.fromEntries(sch.map(i => [i, nm("school", i)])), s1: r.school || "", pct: (p.school || []).length === sch.length ? (p.school_pct || []) : [], out: p.school_out || 0,
      edge: Math.round(r.edge), in: r.inside ? 1 : 0, nb: r.near.length ? r.near[0].properties.name : "", acc: Math.round(acc || 0), ...more};
  }
  function locate(lon, lat, acc) {      // a reader's spot, used here and now: the pin, the precinct, every district. The spot itself is never kept.
    return (ready || mount()).then(() => map.locate(lon, lat)).then(r => {
      if (!r) return null;
      const z = zonesOf(r, acc);
      spot = [lon, lat]; box = r.precinct.bbox;
      map.setMine(mineOf(z)); map.select(null); map.setPin(spot);
      map.fitBox([Math.min(box[0], lon), Math.min(box[1], lat), Math.max(box[2], lon), Math.max(box[3], lat)], 15, 11);      // the whole precinct, with the pin in it
      const pin = $("#gmap .gpin"); if (pin) { pin.classList.remove("drop"); void pin.offsetWidth; pin.classList.add("drop"); }
      return z;
    });
  }
  function toMine() {      // the view on a located reader's precinct: around the pin while the spot is known, else around the precinct's own middle
    const z = MINE && MINE.z; if (!z || !map) return;
    if (spot && box) map.fitBox([Math.min(box[0], spot[0]), Math.min(box[1], spot[1]), Math.max(box[2], spot[0]), Math.max(box[3], spot[1])], 15, 11);
    else if (z.at) map.goTo(z.at[0], z.at[1], 13);
  }
  function rough(lon, lat) {      // a rounded spot (about half a mile): good for the county and the legislative districts, not for a precinct
    return (ready || mount()).then(() => map.locate(lon, lat)).then(r => r ? {c: pk(r.precinct.properties.county), hd: r.precinct.properties.house || "", sd: r.precinct.properties.senate || ""} : null);
  }
  function mount() {
    const root = $("#gmapsec");
    if (!root) return Promise.reject(new Error("no map on this page"));
    if (map) { map.destroy(); map = null; }
    listed = "";
    const get = IDX ? Promise.resolve(IDX) : fetch(G.base + "index.json?v=" + G.v).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
    ready = get.then(idx => {
      IDX = idx;
      if (!root.isConnected) throw new Error("the page moved on");
      const ks = kinds();
      $("#glayers").innerHTML = ks.map(k => `<button type="button" data-k="${k}" aria-pressed="${k === "county"}">${esc(words(k)[0])}</button>`).join("");
      $("#glayer").innerHTML = ks.map(k => `<option value="${k}">${esc(words(k)[0])}</option>`).join("");
      map = BallotMap($("#gmap"), {index: idx, base: G.base, v: G.v, layer: "county", nameOf: dataName, short, onPick: picked,
        onView: v => { const n = $("#gline"); if (n) n.textContent = v.failed && !v.detail ? "Some of the map’s lines could not be loaded. Check your connection; the map asks again as you move it." : v.detail ? `Here the lines are each ${UNIT}’s own.` : v.near ? `Loading this area’s ${UNIT} lines…` : `Far out the lines are simplified; zoom in and each ${UNIT}’s own lines take over.`;
          const me = $("#gme"); if (me) me.hidden = !(MINE && MINE.z); }});
      $("#gabout .fbody").innerHTML = aboutHTML();
      setLayer("county", true);
      if (MINE && MINE.z) { map.setMine(mineOf(MINE.z)); if (spot) map.setPin(spot); toMine(); }      // a reader found before: the map opens on their precinct
      side(sideHome());
      if ((G.polls || {}).status === "loaded" && !POLLS) fetch(G.base + G.polls.file + "?v=" + G.v).then(r => r.ok ? r.json() : null).then(d => { if (d) { POLLS = d; if (map) map.setPolls(d); if ($("#gside") && MINE && MINE.z) side(sideHome()); } }, () => {});
      else if (POLLS) map.setPolls(POLLS);
      if (wanted) { const w = wanted; wanted = null; show(w[0], w[1]); }
    });
    root.addEventListener("click", e => {
      const b = e.target.closest("button, a"); if (!b || !map) return;
      if (b.dataset.k) setLayer(b.dataset.k);
      else if (b.dataset.z === "in") map.zoomIn(); else if (b.dataset.z === "out") map.zoomOut(); else if (b.dataset.z === "fit") map.whole();
      else if (b.dataset.z === "me" || b.dataset.zone === "me") { if (MINE && MINE.z) { toMine(); $("#gmap").scrollIntoView({block: "nearest"}); } }
      else if (b.dataset.zone) { const i = b.dataset.zone.indexOf(":"); show(b.dataset.zone.slice(0, i), b.dataset.zone.slice(i + 1)); }
      else if (b.dataset.side === "home") { map.select(null); side(sideHome()); }
      else if (b.id === "gstreets") { const on = !map.streets(); map.setStreets(on); b.setAttribute("aria-pressed", String(on));
        $("#gstreetnote").innerHTML = on ? `Street pictures: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap contributors</a>. They come from OpenStreetMap&rsquo;s servers, which see which map squares are asked for; everything else stays on this device.`
          : `Street pictures are off. Switched on, they come from OpenStreetMap&rsquo;s servers, which see which map squares are asked for; everything else stays on this device.`; }
    });
    $("#glayer").addEventListener("change", e => setLayer(e.target.value));
    const inp = $("#gfind");
    inp.addEventListener("focus", () => fillFind(false));
    const go = () => { fillFind(false); const v = inp.value.trim().toLowerCase(); if (!v) return;
      const hit = found.find(x => x[0].toLowerCase() === v) || (found.filter(x => x[0].toLowerCase().startsWith(v)).length === 1 ? found.find(x => x[0].toLowerCase().startsWith(v)) : null);
      if (hit) { inp.value = hit[0]; show(map.layer(), hit[1]); } else side(`<p class="held">Nothing called &ldquo;${esc(inp.value)}&rdquo; among ${esc(words(map.layer())[0].toLowerCase())}. Pick a name from the list as you type.</p>${BACK()}`); };
    inp.addEventListener("change", go);
    inp.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    return ready;
  }
  return {mount, locate, rough, show, view: () => map && map.view(), go: (lon, lat, z) => { if (map) map.goTo(lon, lat, z); }, layer: k => { if (k) setLayer(k); return map && map.layer(); },
    forget() { spot = box = null; if (map) { map.setPin(null); map.setMine(null); map.select(null); map.whole(); side(sideHome()); } },
    refresh() { if (map) { if (MINE && MINE.z) map.setMine(mineOf(MINE.z)); else { map.setMine(null); if (!spot) map.setPin(null); } side(sideHome()); } },
    unpin() { spot = box = null; if (map) map.setPin(null); },
    unmount() { if (map) { map.destroy(); map = null; } ready = null; }};
})();
"""

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>On The Ballot: __NAME__ · The Civic Archive</title>
<meta name="description" content="__DESC__">
<meta name="version" content="__VERSION__">
<meta name="theme-color" content="#0C0E12">
<link rel="icon" href="../../us/icon-192.png" type="image/png">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light";var mo=localStorage.getItem("motion");if(mo==="off"||(!mo&&matchMedia("(prefers-reduced-motion: reduce)").matches))document.documentElement.classList.add("calm")}catch(e){document.documentElement.dataset.theme="light"}</script>
<style>
@font-face{font-family:"Instrument Serif";font-style:normal;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Regular.ttf) format("truetype")}
@font-face{font-family:"Instrument Serif";font-style:italic;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Italic.ttf) format("truetype")}
@font-face{font-family:"Instrument Sans";font-style:normal;font-weight:400 700;font-display:swap;src:url(fonts/InstrumentSans-Variable.ttf) format("truetype")}
</style>
<style>__CSS__</style>
<style>__BALLOT_CSS__</style>
<style>
/* a state's state and local ballot: what this page adds to the ballot pages' look */
:root{--pN:#5B6875}
:root[data-theme="dark"]{--pN:#A3AEBA}
html,body{overflow-x:hidden}
#app:focus{outline:none}
@media (max-width:900px){.nav a.x{display:none}}
/* a phone: the shared stylesheet hides the section links below 760px; here they stay, as a second row of the header that slides sideways */
@media (max-width:760px){.top .wrap{flex-wrap:wrap;height:auto;min-height:62px;row-gap:0}
  .top .nav{display:flex;order:9;flex:0 0 100%;min-width:0;margin:0 -4px;padding:0 0 7px;gap:2px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .top .nav::-webkit-scrollbar{display:none}
  .top .nav a,.top .nav a.x{display:block;flex:0 0 auto;padding:7px 10px;font-size:14px}}
.bhero h1{overflow-wrap:break-word}
:root.calm .lvcard{transition:none}:root.calm .lvcard:hover{transform:none}
.privacy{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;line-height:1.45;color:var(--muted);border:1px solid var(--line);border-radius:14px;padding:10px 14px;background:var(--surface);margin:16px 0 0;max-width:82ch}
.privacy svg{flex:none;width:18px;height:18px;margin-top:1px;fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.lvgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));margin-top:14px}
.lvcard{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;transition:border-color .15s,transform .15s var(--ease)}
.lvcard:hover{border-color:var(--line-strong);transform:translateY(-1px)}
.lvcard b{display:block;font-family:var(--serif);font-weight:400;font-size:26px;line-height:1.05}.lvcard span{display:block;font-size:13px;color:var(--muted);margin-top:6px}
.lvcard .go{color:var(--accent);font-weight:700;font-size:13.5px;margin-top:10px}
.rrow.wide{grid-template-columns:minmax(140px,280px) minmax(0,1fr) auto}
.rrow .rl small{display:block;font-weight:400;color:var(--muted);font-size:12px;margin-top:2px}
@media (max-width:640px){.rrow.wide{grid-template-columns:minmax(0,1fr) auto}}
.rrow .rc{min-width:0}
.chip{max-width:100%;overflow:hidden;text-overflow:ellipsis}
.chip.wi{border-style:dashed}
.pick{height:44px;max-width:100%;min-width:0;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 14px;font:600 14.5px var(--sans)}
.pick:disabled{opacity:.55}
@media (max-width:640px){.mybar .pick{width:100%}}
.locbtn{all:unset;box-sizing:border-box;cursor:pointer;height:44px;padding:0 18px;border-radius:999px;background:var(--ink);color:var(--bg);font:700 14px var(--sans);display:inline-flex;align-items:center;gap:8px}
.locbtn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2}
.locbtn:focus-visible,.linkbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.linkbtn{all:unset;cursor:pointer;color:var(--accent);font-weight:600;font-size:14px;text-decoration:underline;text-underline-offset:3px}
.linkbtn[hidden]{display:none}
.ynote{font-size:13.5px;color:var(--muted);margin:10px 0 0;max-width:80ch;line-height:1.45}
.bl-head{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
.bl-head h3{font-family:var(--serif);font-weight:400;font-size:clamp(24px,2.8vw,32px);margin:0}
.bl-level{margin-top:18px}.bl-level h4{font:700 12px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0}
.cgrid{display:grid;grid-template-columns:minmax(0,400px) minmax(0,1fr);gap:18px;align-items:start;margin-top:14px}
@media (max-width:860px){.cgrid{grid-template-columns:1fr}.cgrid .cmapwrap{max-width:420px}}
.cmapwrap{border:1px solid var(--line);background:var(--surface);border-radius:20px;padding:10px}
.cmap{width:100%;height:auto;display:block}
.cmap path.cty{fill:var(--bg);stroke:var(--line-strong);stroke-width:.8;vector-effect:non-scaling-stroke;cursor:pointer;transition:fill .15s}
.cmap path.cty:hover,.cmap path.cty:focus-visible{fill:var(--accent-soft);outline:none}
.cmap path.cty.me{fill:var(--accent)}
.cmap path.cout{fill:none;stroke:var(--ink);stroke-width:1.2;vector-effect:non-scaling-stroke;pointer-events:none;opacity:.6}
.cgrid .sgrid{margin-top:0;grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}
.bstate path.mine{fill:none;stroke:var(--gold);stroke-width:3.5;vector-effect:non-scaling-stroke;pointer-events:none;stroke-dasharray:6 4}
.jump{margin-top:8px}
.jgroup{margin-top:18px}
.jgroup h3{font:700 16px var(--sans);margin:0;display:flex;gap:4px 10px;align-items:baseline;flex-wrap:wrap}
.jgroup h3 span{font-weight:400;font-size:12.5px;color:var(--muted)}
.jgroup .rlist{margin-top:8px}
.filterbar{margin-top:14px}
.filterbar input{box-sizing:border-box;height:44px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 16px;font:500 14.5px var(--sans);width:min(440px,100%)}
.filterbar input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.st .acards{align-items:stretch}
.st .vs{align-self:center}
.st .bcard{aspect-ratio:auto;min-height:clamp(250px,30vw,300px)}
.st .bcard .band span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st .bcard .who{display:block}      /* the record side's stylesheet lays its own .who out as a grid of 240px columns, wider than a card */
.st .bcard .who b{overflow-wrap:anywhere}
.st .bcard .rec{display:block;margin-top:6px;font-size:12px;font-weight:700;color:var(--accent-ink);text-decoration:underline;text-underline-offset:2px}
.st .bcard.np .mono span{border-style:dashed}
@media (max-width:640px){.st .bcard{min-height:0}}
.loading{padding:60px 0;text-align:center}
.lanes .lane .nm a{color:inherit}
.dist-counties{font-size:12.5px;color:var(--muted);margin:2px 0 0}
/* what the loaders wrote about the local lists: which offices are on this ballot, what was read, what is not here yet */
.lnote{border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:12px 16px;margin-top:14px;max-width:96ch;min-width:0}
.lnote h3{font:700 12px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0 0 6px}
.lnote p{margin:0;font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.lnote .lsrc{font-size:12.5px;color:var(--muted);margin-top:8px}
.lnote ul{margin:0;padding:0 0 0 18px;font-size:14px;line-height:1.5}
.lnote li{margin:6px 0;overflow-wrap:anywhere}
.lnote a{color:var(--accent);text-underline-offset:2px}
.jgroup .lnote{margin-top:8px}
details.lmore{margin-top:18px}
details.lmore summary{cursor:pointer;font:600 14.5px var(--sans);color:var(--accent);padding:6px 0;max-width:96ch}
details.lmore summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.cmap path.cty.off{cursor:default;pointer-events:none}
.sgrid.wide{margin-top:14px}
/* <extras> */
.sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
/* the one map of "your ballot" (John, 2026-10-01): every kind of line, from the whole state down to a street */
.gmapgrid{margin-top:16px}
.gmapgrid .mapbar{align-items:flex-start}
.glayers{display:flex;flex-wrap:wrap;gap:5px;min-width:0;flex:1}
.glayers button{all:unset;box-sizing:border-box;cursor:pointer;font:600 12.5px var(--sans);padding:6px 11px;border-radius:999px;border:1px solid var(--line-strong);color:var(--muted);background:var(--surface)}
.glayers button:hover{color:var(--ink);border-color:var(--ink)}
.glayers button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.glayers button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.glayersel{display:none;flex:1;min-width:0}.glayersel span{display:block;font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 4px 4px}
.glayersel .pick{width:100%}
@media (max-width:760px){.glayers{display:none}.glayersel{display:block}}
.gmapgrid .zoom{flex:none}
.zoom button[hidden]{display:none}
.zoom button svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2}
.gmap{position:relative;height:clamp(330px,62vh,640px);border-radius:14px;overflow:hidden;background:var(--bg);touch-action:pan-y;user-select:none;-webkit-user-select:none;cursor:pointer}
.gmap.zoomed{touch-action:none;cursor:grab}.gmap.drag{cursor:grabbing}
.gmap:focus{outline:none}.gmap:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.gmap canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.gmap .gtiles{position:absolute;inset:0;overflow:hidden;background:#e9e6df}
.gmap:not(.streets) .gtiles{display:none}
.gmap .gtiles img{position:absolute;left:0;top:0;max-width:none;transform-origin:0 0;pointer-events:none}
:root[data-theme="dark"] .gmap .gtiles{filter:brightness(.82) contrast(1.05)}
.gmap .gpin{position:absolute;left:0;top:0;width:26px;height:34px;margin:-33px 0 0 -13px;pointer-events:none;filter:drop-shadow(0 3px 3px rgba(0,0,0,.35))}
.gmap .gpin[hidden]{display:none}
.gmap .gpin svg{display:block;width:26px;height:34px}.gmap .gpin path{fill:#D8402F;stroke:#fff;stroke-width:1.6}.gmap .gpin circle{fill:#fff}
:root:not(.calm) .gmap .gpin.drop svg{animation:pindrop .55s cubic-bezier(.3,1.5,.5,1) both}
@keyframes pindrop{from{opacity:0;transform:translateY(-46px)}}
.gmap .gattr{position:absolute;right:6px;bottom:6px;font:600 11px var(--sans);color:#14171c;background:rgba(255,255,255,.88);padding:2px 7px;border-radius:6px;text-decoration:underline}
.gmap .gattr[hidden],.gmap .gbusy[hidden]{display:none}
.gmap .gbusy{position:absolute;left:8px;bottom:8px;font:600 11.5px var(--sans);color:var(--ink);background:var(--surface);border:1px solid var(--line);padding:3px 9px;border-radius:999px}
.gfindbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
.gfind{box-sizing:border-box;flex:1 1 220px;min-width:0;height:40px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 14px;font:500 14px var(--sans)}
.gfind:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.gstreets{cursor:pointer;flex:none;color:var(--ink)}.gstreets .lab{display:inline!important}.gstreets:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#gside{min-width:0;overflow-wrap:anywhere}
.zlist{margin:8px 0 10px;display:grid;gap:0}
.zlist>div{display:grid;grid-template-columns:minmax(92px,38%) minmax(0,1fr);gap:8px;padding:6px 0;border-top:1px solid var(--line);font-size:13.5px}
.zlist dt{color:var(--muted)}.zlist dd{margin:0;font-weight:600}
.zbtn{all:unset;cursor:pointer;color:inherit;font-weight:600;text-decoration:underline;text-decoration-color:var(--line-strong);text-underline-offset:3px}
.zbtn:hover{text-decoration-color:var(--ink)}.zbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.znote{font-size:13px;line-height:1.45;color:var(--muted);margin:8px 0 0}
.gpoll{font-size:13px;line-height:1.45;color:var(--muted);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:10px;padding:9px 12px;margin:10px 0 0}
.gpoll b{display:block;color:var(--ink);margin-bottom:2px}.gpoll small{display:block;margin-top:4px}.gpoll a,.mapside .sidehint a{color:var(--accent)}
.glist{list-style:none;margin:8px 0 12px;padding:0;display:grid;gap:6px}
.glist a{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:12px;padding:8px 11px}
.glist a:hover{border-color:var(--line-strong)}.glist b{display:block;font-size:14px;line-height:1.25}.glist span{font-size:12.5px;color:var(--muted)}
.mapside .linkbtn{font-size:13px}
/* who the candidates are, each fact with its source; and, for a nonpartisan office, the record and never a label */
.st .bcard.np .mono .ph{border-style:solid}
.wgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,270px),1fr));margin-top:14px}
.wcard{border:1px solid var(--line);border-top:4px solid var(--pc,var(--line-strong));background:var(--surface);border-radius:16px;padding:12px 14px;min-width:0}
.wcard h3{font-family:var(--serif);font-weight:400;font-size:22px;line-height:1.1;margin:0;overflow-wrap:anywhere}
.wcard .wfor{display:block;font-size:12px;color:var(--muted);margin-top:3px}
.wcard dl{margin:8px 0 0;font-size:13.5px}
.wcard dt{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:10px}
.wcard dd{margin:3px 0 0;overflow-wrap:anywhere}
.wcard dd small,.lrow small{display:block;color:var(--muted);font-size:12px;margin-top:2px;line-height:1.4}
.wcard a,.lrow a,.pvotes a{color:var(--accent-ink,var(--accent))}
.wcard .soon{color:var(--muted);font-style:italic}
.wcard .topics span{border-radius:10px;line-height:1.3;padding:3px 8px}
.wcard dd .item{display:block;margin-top:6px}.wcard dd .item:first-child{margin-top:0}
.lean{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));margin-top:14px}
.lrow{border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:11px 14px;min-width:0;overflow-wrap:anywhere}
.lrow h4{font:700 15px var(--sans);margin:0 0 4px}
.lrow ul{margin:0;padding:0;list-style:none;font-size:13.5px;line-height:1.45}.lrow li{margin-top:8px}.lrow p{margin:0;font-size:13.5px;color:var(--muted)}
.pvotes{margin-top:22px}
.pvotes h3{font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.6vw,30px);margin:0}
.pvgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr));margin-top:12px}
.pv{border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:11px 14px;min-width:0}
.pvh{display:flex;justify-content:space-between;gap:4px 10px;flex-wrap:wrap;align-items:baseline;margin-bottom:6px}.pvh b{font-size:14px}.pvh span{font-size:12.5px;color:var(--muted)}
.pvr{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(40px,1fr) auto;gap:8px;align-items:center;font-size:13px;margin-top:7px}
.pvn{min-width:0;line-height:1.2}.pvn i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.pvn small{display:block;color:var(--muted);font-size:11.5px;margin-left:15px}
.pvb{height:10px;border-radius:5px;background:var(--line);overflow:hidden}.pvb i{display:block;height:100%;background:var(--muted);border-radius:5px}
.pvv{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}.pvv small{display:block;font-weight:400;color:var(--muted);font-size:11.5px}
.nomarket{max-width:80ch}
/* </extras> */
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../" title="On The Ballot: every level" aria-label="Back to the On The Ballot door"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16v8H4z"/><path d="M8 12V5h8v7"/><path d="M10 8.6l1.5 1.5 2.8-2.9"/></svg><span>On The Ballot</span></a>
    <a class="brand" href="#" aria-label="On The Ballot: __NAME__, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections">__NAV__</nav>
    <div class="tools">
      <button class="mtog" id="motion" aria-pressed="true" title="Page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="app" class="bwrap" tabindex="-1"><p class="loading muted">Loading the candidate lists&hellip;</p></main>
<footer class="bwrap bfoot">
  <p>On The Ballot, from The Civic Archive v__VERSION__. __FOOT__ Built __GENERATED__.</p>
  <p><a href="../">On The Ballot: every level</a> &middot; <a href="../us/">Congress</a> &middot; <a href="../states/">Every state loaded</a> &middot; <a href="../../">The Civic Archive front door</a>__RECORD__</p>
</footer>
<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel"><span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span></button>
  <div class="cl-panel" id="clpanel" hidden><div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div><div class="cl-body" id="clbody"></div></div>
</div>
<script>
const BOOT = __BOOT__;
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
/* ===== parts shared with the federal page (taken from it when this page is built) ===== */
__CHANGELOG__
__GEO__
/* ===== end of the shared parts ===== */
/* ===== a part shared with the Congress ballot page (taken from it when this page is built): how a page's sources are folded ===== */
__SOURCEFOLD__
/* ===== end of that part ===== */
/* ===== another, only where a state has polls or markets of its statewide races: the two tabs above the cards, the notice before a market, the helplines ===== */
__MARKETS__
/* ===== end of that part ===== */

/* ---------- the two switches, with the same saved choices as the rest of the site ---------- */
const calm = () => document.documentElement.classList.contains("calm");
const showMotion = () => $("#motion").setAttribute("aria-pressed", calm() ? "false" : "true");
showMotion();
$("#motion").addEventListener("click", () => { const off = !calm(); document.documentElement.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });

/* ---------- the state: its name, chambers and election office, worked out when the page was built ---------- */
const ST = BOOT.st, NM = esc(ST.name), WHO = ST.who, UP = esc(ST.up), LO = esc(ST.lo);
const EMPTY = ST.noGeneral ? `The ${WHO} list for November 3 is not loaded yet` : ST.partial ? `Not on the ${WHO} lists loaded so far` : "";      // what an empty November list means here
/* a legislative district with no race: where some of the chamber's districts are not up this year (ST.off), that is what it is, as "your ballot" says of it */
const noLegRace = (key, what) => (ST.off || {})[key] ? `${capital(what)} is not on this year&rsquo;s ballot: no race for it is on the list for November 3.` : `No race for ${what} is on the ${WHO} list for November 3.`;
/* "No contest for it is on the <whose> list for November 3": where the lists are read one county at a time and only some are loaded, the page says that much and no more */
const onList = (who, tail, f) => !ST.partial && f && D.counties[f] && (GAPS.county[f] || []).length      // a county some of whose own lists are not loaded: no claim that nobody is running there
    ? `is on the ${who} lists loaded so far${tail || ""} (not loaded yet for ${esc(cName(f))}: ${GAPS.county[f].map(g => esc(g.w)).join("; ")})`
  : !ST.partial && !f && who !== WHO && Object.keys(GAPS.county).length      // a place whose county the page does not know, in a state where some counties' own lists are not loaded
    ? `is on the ${who} lists loaded so far${tail || ""} (some lists are not loaded yet, in ${plural(Object.keys(GAPS.county).length, ST.countyWord || "county", ST.countyMany || "counties")})`
  : !ST.partial ? `is on the ${who} list${tail || ""}`
  : f && D.counties[f] && !(GAPS.county[f] || []).length ? `is on the list read for ${esc(cName(f))}${tail || ""}`      // that county's own list is loaded
  : f && D.counties[f] ? `can be shown: ${esc(cName(f))}&rsquo;s own list is not loaded yet`
  : `is on the ${who} lists loaded so far (the other ${ST.countyMany || "counties"}&rsquo; lists are not loaded yet)`;
const NOTICE = ST.notice ? `<div class="notebox">${ST.notice}</div>` : "";
const dWord = key => (key === "upper" ? ST.upD : ST.loD).replace(/ District$/, " district");
const CO1 = ST.countyOne || "county", COS = ST.countyOnes || "counties";      // what a county is called here: a parish in Louisiana, a borough in Alaska

/* ---------- the data: races and candidates (data/<code>.json), and the lines, fetched when a map needs them ---------- */
let D = null, R = {}, LEG = {upper: {}, lower: {}}, LINES = null, linesP = null, MINE = {}, COUNTS = {}, SPLITS = new Set();
const needLines = () => LINES ? Promise.resolve(LINES) : (linesP || (linesP = fetch(BOOT.lines).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))))
  .then(d => (LINES = d), e => { linesP = null; throw e; })));
/* what a state can have beyond its lists (John, 2026-10-01), each fetched only when a page needs it: who the candidates are, each fact
   with its source (data/who.json); how a place has voted (data/votes/); and the map's own script and files (geo/) */
let FACTS = null, factsP = null, PARTY_PAGES = [], BYG = {}, SCHG = {}, VMETA = null, kitP = null;
/* a city's or township's place here by the map's id for it: the place its races name, else the id without the state's prefix (IA-M-90042: 90042) */
const GID = {}, MCDG = {}, mPk = id => MCDG[id] || "M" + String(id || "").replace(new RegExp("^" + ST.code + "-M-"), ""), mKey = id => mPk(id).slice(1);
const VFILES = {}, GEO_ON = !!(BOOT.geo && BOOT.st.local);
const UNIT = (BOOT.geo || {}).unit || "precinct";      // what the smallest voting area is called here, by the map files' own account (a ward in Wisconsin)
const getJSON = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
const needFacts = () => FACTS ? Promise.resolve(FACTS) : !BOOT.who ? Promise.resolve(FACTS = {}) : (factsP || (factsP = getJSON(BOOT.who).then(d => { PARTY_PAGES = d.parties || []; return (FACTS = d.r || {}); }, () => (FACTS = {}))));
const facts = (c, r) => ((FACTS || {})[r.id] || {})[c.n] || {};
const addScript = src => new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => no(new Error(src)); document.head.appendChild(s); });
const needKit = () => kitP || (kitP = addScript(BOOT.geo.base + "reader.js?v=" + BOOT.geo.v).then(() => addScript(BOOT.geo.base + "mapkit.js?v=" + BOOT.geo.v)).catch(e => { kitP = null; throw e; }));
const needMeta = () => VMETA ? Promise.resolve(VMETA) : getJSON(BOOT.votes.base + "meta.json?v=" + BOOT.votes.v).then(m => (VMETA = m));
const needVotes = name => Promise.all([needMeta(), VFILES[name] ? VFILES[name] : getJSON(BOOT.votes.base + name + ".json?v=" + BOOT.votes.v).then(f => (VFILES[name] = f))]).then(x => x[1]);

/* ---------- words ---------- */
const LV = {statewide: "Statewide offices", legislature: "The Legislature", county: "County offices", soil_water: ST.soilT || "Soil and water conservation", city: "City offices",
  township: "Township offices", school: ST.schoolT || "School districts", hospital: "Hospital districts", other: "Other districts", court: "Judges"};
const ORDER = ["statewide", "legislature", "county", "soil_water", "city", "township", "school", "hospital", "other", "court"];
const LOCAL = ["county", "soil_water", "city", "township", "school", "hospital", "other"];
const LWHO = ST.localWho || WHO, whoOf = r => r && LOCAL.includes(r.lv) ? LWHO : WHO;      // whose list a local contest was read from
/* a place is called what its own name says it is (Adairville city, Abingdon town); which section it sits in is its races' level */
const MUNI = ["city", "town", "village", "borough", "township"], MUNIS = {city: "cities", town: "towns", village: "villages", borough: "boroughs", township: "townships"};
const capital = s => String(s).charAt(0).toUpperCase() + String(s).slice(1);
const orList = a => a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " or " + a[a.length - 1];
const muniOf = n => { const m = /\b(city|town|village|borough|township)$/i.exec(n || ""); return m ? m[1].toLowerCase() : ""; };
const muniWords = (names, fallback) => { const said = new Set(names.map(muniOf)); const w = MUNI.filter(x => said.has(x)); return w.length ? w : [fallback]; };
const MUNI1 = orList(ST.muni || []);      // "city or township" in Minnesota, "city or town" in Virginia, "city" in Kentucky
const ORD = n => n + (["th", "st", "nd", "rd"][((n % 100) - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");
const fmtDate = iso => { const [y, m, d] = String(iso || "").split("-").map(Number); return y ? new Date(y, m - 1, d).toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}) : ""; };
const shortDate = iso => fmtDate(iso).replace(/, \d{4}$/, "");
const num = n => Number(n || 0).toLocaleString("en-US");
const plural = (n, one, many) => `${num(n)} ${n === 1 ? one : (many || one + "s")}`;
const firstOf = n => String(n).split(/\s+(?:and|&|\/)\s+/i)[0];      // a ticket's first name: "A and B", "A & B", or "A / B" as some lists write it
const surname = n => firstOf(n).replace(/,?\s+(Jr\.?|Sr\.?|II|III|IV)$/i, "").trim().split(/\s+/).pop().toLowerCase();
const inOrder = list => [...list].sort((a, b) => (a.o ?? 1e9) - (b.o ?? 1e9) || surname(a.n).localeCompare(surname(b.n)) || a.n.localeCompare(b.n));
const initials = n => { const w = firstOf(n).replace(/["“”(].*?["“”)]/g, "").replace(/,?\s+(Jr|Sr|II|III|IV)\.?$/i, "").trim().split(/\s+/);
  return (((w[0] || "")[0] || "") + ((w.length > 1 ? w[w.length - 1] : "")[0] || "")).toUpperCase(); };
const natKey = d => { const m = String(d ?? "").match(/^(\d+)(.*)$/); return m ? [+m[1], m[2]] : [1e9, String(d ?? "")]; };
const byDistrict = (a, b) => { const x = natKey(a), y = natKey(b); return x[0] - y[0] || x[1].localeCompare(y[1], undefined, {numeric: true}); };
const PV = {D: "var(--pD)", R: "var(--pR)", L: "var(--pL)", G: "var(--pG)", I: "var(--pI)", W: "var(--pW)", N: "var(--pN)", O: "var(--pO)"};
const pcVar = c => PV[c.pc] || PV.O;
const partyWords = (c, r) => r.pt ? (c.p || "No party given") : "Nonpartisan office";
const partyShort = (c, r) => r.pt ? ((D.pshort || {})[c.p] || c.p || "No party given") : "Nonpartisan";
const general = r => inOrder(((r.el || {}).general) || []);
const primaries = r => Object.keys(r.el || {}).filter(k => k !== "general").sort();
const cName = f => (D.cfull || {})[f] || (D.counties[f] ? `${D.counties[f]} County` : `County ${f}`);      // Alexandria city and Orleans Parish keep their own word
const cShort = f => (D.cfull || {})[f] || D.counties[f] || f;
const byCounty = (a, b) => D.counties[a].localeCompare(D.counties[b]) || cName(a).localeCompare(cName(b));
const countyKey = s => { s = String(s); if (D.counties[s]) return s; const n = s.replace(/\D/g, "");      // #county=053, and the five-digit code too
  return n.length === 5 && n.slice(0, 2) === ST.fips && D.counties[n.slice(2)] ? n.slice(2) : s.padStart(3, "0"); };
const hrefRace = r => "#race=" + encodeURIComponent(r.id);
const plain = html => String(html).replace(/<[^>]+>/g, "").replace(/&(amp|lt|gt|quot|#39|rsquo);/g, (m, k) => ({amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", rsquo: "’"}[k]));      // words out of HTML, for a label
const senateOf = hd => (hd != null && hd !== "" && (D.nest || {})[hd]) || "";      // which upper district holds a lower one, from the lines ("" where they do not nest)
const upperOf = m => ST.nest ? senateOf(m.hd) : (m.sd || "");
const legRace = (key, d) => d == null || d === "" ? null : (LEG[key][d] || LEG[key][String(d).replace(/[A-Z]$/, "")] || null);      // North Dakota's 9A and 9B are elected as District 9
const holders = r => r && r.h ? (r.hs || (r.h[0] ? [r.h[0]] : [])) : [];
const placeByKey = pk => pk ? ((D.places[pk[0]] || {})[pk.slice(1)] || null) : null;
const placeOf = r => r && r.pk ? placeByKey(r.pk) : null;
const placeName = pk => { const P = (D.places[pk[0]] || {})[pk.slice(1)]; return P ? P.n : pk.slice(1); };
/* the court contests of a county: the ones the list ties to counties, short of the whole state (those are on every ballot) */
let NCOUNTY = 0;
const localCourt = r => r.lv === "court" && (r.c || []).length > 0 && r.c.length < NCOUNTY;
const baseKind = r => r.k.replace(/_retention$/, "");
const PROSECUTOR = /attorney|prosecutor|solicitor/, isJudge = r => !PROSECUTOR.test(r.k) && !/clerk|marshal|constable/.test(r.k);
function courtNoun(list){      // what a set of court contests is, from the rows: district court judges; judges; judges and prosecutors
  const ks = [...new Set(list.map(baseKind))], OWN = {orphans_court: "orphans&rsquo; court judges", county_court_at_law: "county court at law judges"};
  if (list.every(isJudge)) return ks.length !== 1 ? "judges" : OWN[ks[0]] || (/_court$/.test(ks[0]) ? `${ks[0].replace(/_/g, " ")} judges` : "judges");
  return list.every(r => PROSECUTOR.test(r.k)) ? "prosecutors" : list.every(r => isJudge(r) || PROSECUTOR.test(r.k)) ? "judges and prosecutors" : "court offices";
}
const ownKind = f => { const m = /\b(city|parish|borough|municipality|census area|planning region)$/i.exec((D.cfull || {})[f] || ""); return m ? m[1].toLowerCase() : "county"; };      // Alexandria city's own offices are a city's
const levelWords = r => {      // what a race page calls its level, from the place's own name and the office itself
  if (r.lv === "city" || r.lv === "township") { const w = muniOf((placeOf(r) || {}).n || ""); return w ? `${capital(w)} offices` : LV[r.lv]; }
  if (r.lv === "county") return (r.c || []).length === 1 ? `${capital(ownKind(r.c[0]))} offices` : LV.county;
  if (r.lv === "court" && !isJudge(r)) return "Courts";
  return LV[r.lv] || "On the ballot"; };
/* what the loaders said is not here yet, and why: by county, by place and by race; the rest is the state's own */
let GAPS = {state: [], county: {}, place: {}, race: {}};
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "the source"; } };
const srcLink = u => u ? ` <a href="${esc(u)}" target="_blank" rel="noopener">${esc(hostOf(u))}</a>` : "";
const gapItem = (g, where) => `<li><b>${esc(capital(g.w))}</b>${where && g.p && g.p !== ST.name ? ` (${esc(g.p)})` : ""}. ${esc(g.r)}${srcLink(g.u)}</li>`;
const gapBox = (list, where, title) => list && list.length ? `<div class="lnote gaps"><h3>${title || "Not here yet, and why"}</h3><ul>${list.map(g => gapItem(g, where)).join("")}</ul></div>` : "";
const NOTE_T = {local_calendar: "Which local offices are on this ballot", local_coverage: "What was read, and what was left out"};
const noteBox = key => { const N = (D.notes || {})[key];
  return N ? `<div class="lnote"><h3>${NOTE_T[key] || "A note on these lists"}</h3><p>${esc(N.t)}</p>${N.s || N.u ? `<p class="lsrc">Source: ${esc(N.s || "")}${srcLink(N.u)}</p>` : ""}</div>` : ""; };
const noteKeys = () => { const ks = Object.keys(D.notes || {}); return ["local_calendar", "local_coverage"].filter(k => ks.includes(k)).concat(ks.filter(k => !NOTE_T[k]).sort()); };
const candGap = r => (GAPS.race[r.id] || []).find(g => /candidate/i.test(g.w));      // the list has names for this contest that could not be shown
const distWords = d => /^\d+$/.test(d) ? `District ${d}` : d;      // 2 -> District 2; the list's own words (Ward 2, Section II) as they are
const seatWords2 = s => /^(\d+|[A-Z])$/.test(s) ? `Seat ${s}` : s;
function raceTitle(r){      // the office with the district and seat that tell one contest from its neighbours
  if (r.k === "state_senate") return `${ST.upT}, District ${r.d}`;
  if (r.k === "state_house") return `${ST.loT}, District ${r.d}`;
  const bits = [];
  if (r.d && r.k !== "district_court") bits.push(distWords(r.d));      // a district court's number is already in its title
  if (r.s) bits.push(seatWords2(r.s));
  return bits.length ? `${r.o}, ${bits.join(", ")}` : r.o;
}
function raceWhere(r){
  if (r.lv === "statewide" || r.lv === "legislature" || r.k === "supreme_court" || (r.k === "court_of_appeals" && !r.d)) return ST.name;
  if (r.k === "court_of_appeals") return /district/i.test(r.j || "") ? r.j : /^\d+$/.test(r.d) ? `${ORD(+r.d)} Appellate District` : r.d;      // Michigan elects its appeals judges by district; the list's own name for the district where it gives one (Ohio's "10th District Court of Appeals")
  if (r.k === "district_court") return r.j || (/^\d+$/.test(r.d || "") ? `${ORD(+r.d)} Judicial District` : "District court");
  if (r.j) return r.j;
  const P = placeOf(r); if (P) return P.n;
  return (r.c || []).length === 1 ? cName(r.c[0]) : "";
}
const judicialName = d => /^\d+$/.test(d || "") ? `${ORD(+d)} Judicial District` : (d || "District court");
/* who holds a seat today (the Legislature and statewide offices only), from the state roster */
const recordHref = id => { const L = id && D.links[id]; return L && BOOT.links.state ? (L[0] === "official" ? `../../${ST.lc}/#official=` : `../../${ST.lc}/#member=`) + encodeURIComponent(id) : ""; };
const serves = (c, r) => !!(c.m && holders(r).includes(c.m));
function seatState(r){
  if (!r || !r.h) return "vacant";
  const hs = holders(r), g = general(r);
  if (ST.noGeneral || (ST.partial && !g.length)) return "unknown";      // the November list for this race is not loaded: no claim either way
  if (!hs.length) return g.some(c => c.inc) ? "running" : "open";      // a holder the list names without a roster id: its own incumbent mark
  return hs.every(id => g.some(c => c.m === id)) ? "running" : "open";      // two members, one not running: a seat is open
}
function seatWords(r, link){
  const s = seatState(r);
  if (s === "vacant") return r.lv === "legislature" ? "No member holds this seat in the state roster today." : "Who holds this office today is not in the roster this site draws on.";
  if (s === "unknown") { const hn = (r.hs || []).length > 1 && (r.hn || []).length === r.hs.length ? r.hs.map((id, i) => [id, r.hn[i]]) : [[r.h[0], r.h[1]]];
    return `Held today by ${hn.map(([id, n]) => { const href = link && id ? recordHref(id) : ""; return `<b>${href ? `<a href="${href}">${esc(n)}</a>` : esc(n)}</b>`; }).join(" and ")}${r.h[2] ? ` (${esc(r.h[2])})` : ""}. Whether ${hn.length > 1 ? "they are" : "they are"} on the November ballot shows when the list is loaded.`; }
  if ((r.hs || []).length > 1 && (r.hn || []).length === r.hs.length) {      // a district that elects two members
    const g = general(r), on = id => g.some(c => c.m === id);
    const nm = (id, i) => { const href = link ? recordHref(id) : ""; return `<b>${href ? `<a href="${href}">${esc(r.hn[i])}</a>` : esc(r.hn[i])}</b>${(r.hp || [])[i] && r.hc ? ` (${esc(r.hp[i])})` : ""}`; };
    const who = `Held today by ${r.hs.map(nm).join(" and ")}${r.h[2] && !r.hc ? ` (${esc(r.h[2])})` : ""}`;
    const yes = r.hs.map((id, i) => on(id) ? esc(r.hn[i]) : "").filter(Boolean), no = r.hs.map((id, i) => on(id) ? "" : esc(r.hn[i])).filter(Boolean);
    if (!no.length) return `${who}, who are both on the ballot again.`;
    if (!yes.length) return `${who}, neither of whom is on the November ballot for it: open seats.`;
    return `${who}. ${yes.join(" and ")} is on the ballot again; ${no.join(" and ")} is not: an open seat.`;
  }
  const href = link && r.h[0] ? recordHref(r.h[0]) : "";
  const who = `Held today by <b>${href ? `<a href="${href}">${esc(r.h[1])}</a>` : esc(r.h[1])}</b>${r.h[2] ? ` (${esc(r.h[2])})` : ""}`;
  const is = / and /.test(r.h[1]) ? "are" : "is";      // a governor and lieutenant governor hold the office together
  if (s === "running") return `${who}, who ${is} on the ballot again.`;
  const lost = primaries(r).find(k => (r.el[k] || []).some(c => c.m && c.m === r.h[0] && c.out === "lost"));
  const voted = lost && (r.el[lost] || []).some(c => c.v != null);
  return lost ? `${who}, who ${voted ? "lost" : "filed for"} the ${esc(D.elections[lost] || "primary")} on ${esc(shortDate((r.el[lost][0] || {}).date))}${voted ? "" : ` and ${is} not on the November ballot`}: ${r.lv === "statewide" ? "the office is open" : "an open seat"}.`
    : `${who}, who ${is} not on the November ballot for it: ${r.lv === "statewide" ? "the office is open" : "an open seat"}.`;
}
const days = () => { const [y, m, d] = D.election.split("-").map(Number), n = new Date(); return Math.round((new Date(y, m - 1, d) - new Date(n.getFullYear(), n.getMonth(), n.getDate())) / 864e5); };
const dayWords = () => { const n = days(); return n > 1 ? `Election Day in ${n} days` : n === 1 ? "Election Day is tomorrow" : n === 0 ? "Election Day is today" : `Election Day was ${fmtDate(D.election)}`; };
const PBOX = words => `<p class="privacy"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg><span>${words}</span></p>`;
const PRIVACY = PBOX(ST.privacy || `Only the name, office and party each candidate filed under are shown. Addresses and contact details in the ${WHO} files are never read.`);
const privacyFor = r => ST.privacyRace ? PBOX(r.f ? ST.privacyRace : ST.privacySmall) : PRIVACY;      // a race's page says what is on that page

/* ---------- small pieces ---------- */
const chip = (c, r) => `<span class="chip${serves(c, r) ? " inc" : ""}${c.wi ? " wi" : ""}" style="--pc:${pcVar(c)}" title="${esc(partyWords(c, r))}${serves(c, r) ? ", serves in this seat today" : ""}${c.wi ? ", write-in" : ""}"><i></i>${esc(c.n)}</span>`;
function raceRow(r, label, sub){
  const g = general(r), gap = g.length ? null : candGap(r);      // names the list holds but that could not be shown: said as such, with the reason on the race's page
  return `<a class="rrow wide" href="${hrefRace(r)}"><span class="rl">${label || esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}${sub ? `<small>${sub}</small>` : r.note ? `<small>${esc(r.note)}</small>` : ""}</span><span class="rc">${g.length ? g.map(c => chip(c, r)).join("") : `<span class="muted">${gap ? `Not here yet: ${esc(gap.w)}` : EMPTY || `No candidate on the ${whoOf(r)} list`}</span>`}</span><span class="go" aria-hidden="true">&rsaquo;</span></a>`;
}
const holderSmall = r => esc(plain(seatWords(r, false)));
const crumbs = parts => `<nav class="crumbs"><a href="#">${NM}</a>${parts.map(p => `<span>&rsaquo;</span>${p}`).join("")}</nav>`;
const srcItem = s => `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}<small><span class="tag fact">Fact</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : ""}${s.published ? ` &middot; published ${esc(s.published)}` : ""}${s.fetched ? ` &middot; read ${esc(s.fetched)}` : ""}${s.rows ? ` &middot; ${num(s.rows)} rows` : ""}${s.sha ? ` &middot; SHA-256 ${esc(String(s.sha).slice(0, 16))}&hellip;` : ""}${s.note ? " &middot; " + esc(s.note) : ""}</small></div>`;
const ROSTER_SRC = `<div class="srcitem"><b>Open States</b>: the roster of ${NM}&rsquo;s legislators and statewide officials (who holds each seat today), as the record side of this site loads it<small><span class="tag fact">Fact</span> <a href="https://github.com/openstates/people" target="_blank" rel="noopener">github.com/openstates/people</a> &middot; public domain (CC0)</small></div>`;
const LINES_SRC = () => `<div class="srcitem"><b>U.S. Census Bureau</b>: cartographic boundary files for ${NM}&rsquo;s legislative districts${ST.local && ST.cLines ? ` and ${esc(COS)}` : ""}, the lines the maps draw and &ldquo;use my location&rdquo; reads<small><span class="tag fact">Fact</span> <a href="https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html" target="_blank" rel="noopener">census.gov cartographic boundary files</a></small></div>`;
/* a page's sources, kind by kind, for the folds (sourceFold, shared with the Congress ballot page): a source with the office it comes from,
   and the roster behind "who holds each seat today" (the state's own row for it where its lists name one) */
const srcRow = s => ({h: srcItem(s), a: s.agency || ""});
const srcAdd = (parts, kind, x) => { (parts[kind] = parts[kind] || {items: []}).items.push(x); };
const srcKindOf = s => { const k = sourceKind(s); return s.names && /^(maps|rules|other)$/.test(k) ? "places" : k; };      // a boundary file the page reads only for the names of places is filed with the places
const rosterRows = () => { const rows = Object.values(D.sources).filter(s => sourceKind(s) === "holders").map(srcRow); return rows.length ? rows : [{h: ROSTER_SRC}]; };

function index(){
  D.races.forEach(r => { r.date = r.date || D.election;      // what the file leaves out because the page can put it back
    for (const [k, list] of Object.entries(r.el || {})) list.forEach(c => { c.date = c.date || (k === "general" ? r.date : D.primary); c.src = c.src || r.src; if (!r.pt) { c.p = "Nonpartisan office"; c.pc = "N"; } }); });
  R = Object.fromEntries(D.races.map(r => [r.id, r]));
  LEG = {upper: {}, lower: {}};
  D.races.forEach(r => { const key = r.k === "state_senate" ? "upper" : r.k === "state_house" ? "lower" : null;
    if (key && r.d && (!LEG[key][r.d] || LEG[key][r.d].sp)) LEG[key][r.d] = r; });      // a special election beside the regular one: the regular race is the district's
  SPLITS = new Set(D.races.filter(r => r.h && r.h[3] === "S").map(splitOf).filter(pr => pr.length === 2));
  COUNTS = {}; NCOUNTY = Object.keys(D.counties || {}).length;
  D.races.forEach(r => { if (LOCAL.includes(r.lv) || localCourt(r)) (r.c || []).forEach(f => { COUNTS[f] = (COUNTS[f] || 0) + 1; }); });
  GAPS = {state: [], county: {}, place: {}, race: {}};
  (D.gaps || []).forEach(g => { if (!g.id || !GAPS[g.sc] || g.sc === "state") GAPS.state.push(g); else (GAPS[g.sc][g.id] = GAPS[g.sc][g.id] || []).push(g); });
  BYG = {}; SCHG = {};      // the races of each shape on the map ("ward:00694|Ward 2"), and a school district's place by the map's id for it
  D.races.forEach(r => { r.st = ST.code; if (r.g) (BYG[r.g] = BYG[r.g] || []).push(r); if (r.g && r.g.startsWith("mcd:") && (r.pk || "")[0] === "M") MCDG[r.g.slice(4)] = r.pk;
    if (r.g && r.pk && ((r.g.startsWith("mcd:") && r.pk[0] === "M") || (r.g.startsWith("school:") && r.pk[0] === "S"))) GID[r.pk] = r.g.slice(r.g.indexOf(":") + 1); });      // the map's id for a place, by the page's key for it
  Object.entries((D.places || {}).S || {}).forEach(([k, P]) => { SCHG[P.g || k] = "S" + k; });
  Object.entries(GID).forEach(([key, id]) => { if (key[0] === "S" && !SCHG[id]) SCHG[id] = key; });
}

/* ---------- who a candidate is, beyond the list (John, 2026-10-01): the state roster's own record of a sitting member first, then what
   was found on the open web and confirmed against the page that states it, each labelled by its kind of source as the Congress pages
   label theirs (according to a government's page or their campaign; as reported by Wikipedia or a named news organization). Only a race
   whose office may show these is marked (r.f); every other candidate shows what they filed, and a website if they listed one. ---------- */
const ageOf = dob => { if (!dob) return null; const [y, m, d] = String(dob).split("-").map(Number), n = new Date(); let a = n.getFullYear() - y; if (n.getMonth() + 1 < m || (n.getMonth() + 1 === m && n.getDate() < d)) a--; return a; };
const fAge = fb => fb ? (fb[1] ? String(ageOf(fb[1])) : "about " + (new Date().getFullYear() - fb[0])) : null;
const fSrc = (who, url, kind) => { const a = t => `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">${t}</a>`;
  return kind === "campaign" ? `according to ${a("their campaign")}` : kind === "official" ? `according to ${a(esc(who))}` : `as reported by ${a(esc(who))}`; };
const fYears = o => o[2] === "now" ? (o[1] ? `, since ${o[1]}` : ", held today") : o[1] && o[2] ? (o[1] === o[2] ? `, ${o[1]}` : `, ${o[1]} to ${o[2]}`) : o[1] ? `, from ${o[1]}` : o[2] ? `, until ${o[2]}` : "";
const yearsIn = (start, end, unsure) => { if (!start) return "years not on record"; const y = ((end ? new Date(end) : new Date()) - new Date(start)) / (365.2425 * 864e5);
  return y < 1 ? (unsure ? "at least a few months" : "under a year") : `${unsure ? "at least " : ""}${Math.floor(y)} yr${Math.floor(y) === 1 ? "" : "s"}`; };
const ROSTER_NAME = "the Open States roster of state officials";
function nowOffice(p){      // the office a candidate holds today: the roster's, or one a government's own page states
  const o = (p.off || []).filter(x => !x[2]).sort((a, b) => String(b[1]).localeCompare(String(a[1])))[0];
  if (o) return `${esc(o[0])}, ${yearsIn(o[1], "", o[3])}`;
  const held = (p.fo || []).filter(x => x[2] === "now"), f = held.find(x => x[5] === "official") || held[0];      // a named source's word counts too; "Who they are" says which
  return f ? `${esc(f[0])}${f[1] ? `, since ${f[1]}` : ""}` : "";
}

/* ---------- a candidate's card, and the arena ---------- */
function card(c, r, k){
  const sv = serves(c, r), href = c.m ? recordHref(c.m) : "", L = c.m && D.links[c.m], p = facts(c, r), age = ageOf(p.dob);
  const flag = c.wi ? "Write-in" : sv ? "In this seat today" : c.inc ? "Incumbent" : "";
  const band2 = r.lv === "legislature" ? (r.k === "state_senate" ? `${ST.upAbbr} ${r.d}` : `${ST.loAbbr} ${r.d}`) : r.s ? seatWords2(r.s) : r.d ? (r.lv === "court" ? (/^court_of_appeals/.test(r.k) ? raceWhere(r) : judicialName(r.d)) : distWords(r.d)) : (r.lv === "statewide" ? "Statewide" : "");
  const rec = href ? `<a class="rec" href="${href}">${sv ? "Their record" : L && L[0] === "official" ? `${esc(L[1])} today: their record` : L ? `Serves in the ${NM} ${esc(L[1])} today: their record` : "Their record"}</a>` : (sv ? `<span class="rec">Serves in this seat today</span>` : "");
  const order = ["Ballot order", c.o != null ? esc(String(c.o)) : "Not given"];
  const rows = r.f ? [["Age", age != null ? String(age) : (fAge(p.fb) || "Not on record")], ["In office now", nowOffice(p) || (c.inc || sv ? "This office: marked incumbent on the list" : "No office on record")], order]
    : [["Party", r.pt ? esc(partyShort(c, r)) : "Nonpartisan"], order];
  return `<article class="bcard${c.wi ? " wi" : ""}${r.pt ? "" : " np"}" style="--pc:${pcVar(c)};--k:${k}" aria-label="${esc(c.n)}, ${esc(partyWords(c, r))}">
    <div class="band"><span>${esc(partyShort(c, r))}</span><span>${esc(band2)}</span></div>
    ${flag ? `<span class="flag">${esc(flag)}</span>` : ""}
    <div class="mono">${p.ph ? `<span class="ph"><img src="${esc(p.ph)}" alt="" loading="lazy" decoding="async"></span>` : `<span aria-hidden="true">${esc(initials(c.n))}</span>`}</div>
    <div class="who"><b>${esc(c.n)}</b><small>${esc(partyWords(c, r))}</small>${rec}</div>
    <dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`;
}
/* <plain> */
const tabsFor = () => "", whoHTML = () => "", leanHTML = () => "", moreSources = () => {}, mountVotes = () => {}, quietMarkets = () => {};      // a state with its lists alone: none of what follows is in its page
/* </plain> */
/* <extras> */
function whoHTML(r){      // what a record or a named source says about each candidate, with where it comes from
  const g = general(r); if (!g.length || !BOOT.who) return "";
  if (!r.f && !g.some(c => facts(c, r).web)) return "";      // an office that shows what was filed: only a website a candidate listed
  const ext = (url, words) => `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">${words}</a>`;
  const site = p => p.web ? `${ext(p.web, esc(hostOf(p.web)))}<small>${p.wf ? "The campaign&rsquo;s own website, found on the open web and checked against the race it names" : `The address the candidate gave the ${WHO} list`}</small>`
    : `<span class="soon">${r.f ? "None on the list or found" : "None on the list"}</span>`;
  const one = c => { const p = facts(c, r), age = ageOf(p.dob), rows = [], ticket = r.k === "governor" && firstOf(c.n) !== String(c.n);
    if (r.f) {
      rows.push(["Age", age != null ? `${age}<small>Born ${esc(String(p.dob).slice(0, 4))}, according to ${ROSTER_NAME}</small>`
        : p.fb ? `${fAge(p.fb)}<small>Born ${p.fb[0]}, ${fSrc(p.fb[2], p.fb[3], p.fb[4])}${p.fb[1] ? "" : "; the age is worked out from the year alone"}</small>`
        : `<span class="soon">Not on record</span>`]);
      // the roster often lacks the date a long-serving member began: then the earliest date it does give is "or earlier", never a start
      const when = o => { const a = o[1] ? esc(String(o[1]).slice(0, 4)) : "", b = o[2] ? esc(String(o[2]).slice(0, 4)) : "";
        return o[3] ? (b ? `${a ? a + " or earlier" : "start not on record"} to ${b}` : a ? `since ${a} or earlier` : "today; start not on record") : b ? `${a}&ndash;${b}` : `since ${a}`; };
      const held = (p.off || []).map(o => `<span class="item">${esc(o[0])}, ${when(o)}<small>${yearsIn(o[1], o[2], o[3])}; ${ROSTER_NAME}</small></span>`)
        .concat((p.fo || []).map(o => `<span class="item">${esc(o[0])}${fYears(o)}<small>${fSrc(o[3], o[4], o[5])}</small></span>`));
      rows.push(["Public offices held", held.length ? held.join("") : `<span class="soon">None on record</span>`]);
      if (p.op) rows.push(["Their official page", `${ext(p.op[0], esc(p.op[1]))}<small>A government&rsquo;s own page about an officeholder</small>`]);
    }
    rows.push(["Campaign website", site(p)]);
    if (r.f) rows.push(["In their own words", p.iss ? `<span class="topics">${p.iss[1].map(t => `<span>${esc(t)}</span>`).join("")}</span>${ext(p.iss[0], "Read them in their own words")}<small>The topics their campaign&rsquo;s issues page lists, as headings; nothing is summarized</small>`
      : `<span class="soon">${p.web ? "No issue headings read from their site" : "Nothing found"}</span>`]);
    if (r.f && p.ph) rows.push(["Photo", `${esc(p.pc || "")}${p.pu ? `<small>${ext(p.pu, "Where it comes from")}</small>` : ""}`]);
    return `<article class="wcard" style="--pc:${pcVar(c)}"><h3>${esc(c.n)}</h3>${ticket && r.f ? `<small class="wfor">These are about ${esc(firstOf(c.n))}, the candidate for governor</small>` : ""}<dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`; };
  return `<section class="bsec" id="who"><h2>${r.f ? "Who they are" : "Campaign websites"}</h2><p class="sub">${r.f ? "What a record or a named source says about each candidate, with where it comes from. A blank means nothing was found, not that there is nothing. Nobody is described, scored or graded."
    : `Candidates for this office are shown as they filed. Where one listed a campaign website with the ${WHO} office, it is linked here.`}</p><div class="wgrid">${g.map(one).join("")}</div></section>`;
}
/* ---------- a nonpartisan office: the record, never a label (John, 2026-10-01). A party's own published endorsement, an earlier run or
   office under a party label and a candidate's own words, each linked; and how the place itself has voted, from the official results ---------- */
function leanHTML(r){
  if (r.pt || (!BOOT.who && !BOOT.votes)) return "";
  const g = general(r), people = !!(r.f && BOOT.who && g.length);
  const link = (url, words) => `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">${words}</a>`;
  const person = c => { const p = facts(c, r), items = [], by = {};
    const seen = {};      // one party unit, named once, however many of its pages say it
    (p.en || []).forEach(([party, unit, url]) => { if (seen[party + "|" + unit]) return; seen[party + "|" + unit] = 1; (by[party] = by[party] || []).push(link(url, esc(unit))); });
    Object.entries(by).forEach(([party, units]) => items.push(`<li><b>Endorsed by a party.</b> ${esc(party)}: ${units.join(", ")}<small>as the party&rsquo;s own page says</small></li>`));
    // a party's convention nominated them for an office the ballot prints without a party, and its page does not say "endorsed": said in those words, apart
    (p.nom || []).forEach(([party, unit, url]) => items.push(`<li><b>Nominated at a party&rsquo;s convention.</b> Nominated by the ${link(url, esc(unit))} at its convention<small>as the party&rsquo;s own page says; the page does not call it an endorsement, and the ballot prints no party for this office</small></li>`));
    (p.pp || []).forEach(o => items.push(`<li><b>Earlier, under a party label.</b> ${esc(o[0])}${o[1] && !String(o[0]).includes(String(o[1])) ? ` (${o[1]})` : ""}<small>${o[2] ? `${esc(o[2])} &middot; ` : ""}${fSrc(o[3], o[4], o[5])}</small></li>`));
    if (p.ow) items.push(`<li><b>In their own words.</b> &ldquo;${esc(p.ow[0])}&rdquo;<small>on ${link(p.ow[1], "their campaign&rsquo;s own site")}</small></li>`);
    return `<div class="lrow"><h4>${esc(c.n)}</h4>${items.length ? `<ul>${items.join("")}</ul>` : `<p>Nothing of these kinds was found.</p>`}</div>`; };
  const any = people && g.some(c => { const p = facts(c, r); return (p.en || []).length || (p.nom || []).length || (p.pp || []).length || p.ow; });
  const noms = people && g.some(c => (facts(c, r).nom || []).length);
  return `<section class="bsec" id="lean"><h2>The record, not a label</h2>
    <p class="sub">This is a nonpartisan office, and this page never calls a person or a place by a party of its own choosing. ${people ? `What is on the record is shown instead: a party&rsquo;s own published endorsement${noms ? " or its convention&rsquo;s nomination" : ""}, an earlier run or office under a party label, and a candidate&rsquo;s own words on their own campaign site, each linked to where it stands. A blank means only that nothing was found.`
      : BOOT.votes ? "What the record holds about the place is shown instead." : "For this office the page would show how the place has voted before, from the official results."}</p>
    ${!people ? "" : any ? `<div class="lean">${g.map(person).join("")}</div>` : `<p class="ynote">Nothing of these kinds was found for ${g.length === 1 ? "the candidate" : "any candidate"} in this contest.</p>`}
    ${BOOT.votes ? `<div id="pvotes" class="pvotes"><p class="muted">Loading how this place has voted&hellip;</p></div>`
      : `<div class="pvotes"><h3>How this place has voted</h3><p class="ynote">Not loaded yet for ${NM}: the official results of past partisan elections have not been added up by place here, so no figures are shown. They will appear here once they are.</p></div>`}</section>`;
}
function votePlace(r){      // whose past votes a contest's page shows: [file, key, wider than the contest's own place?]; [null, kind] where the results are not added up for that kind of place
  const g = r.g || r.gp || "", i = g.indexOf(":"), kind = g.slice(0, i), id = g.slice(i + 1), V = BOOT.votes, c0 = (r.c || [])[0];      // gp: the place a ward with no lines is a part of
  if (!V || !g) return null;
  if (kind === "state") return ["state", "", 0];
  if (kind === "county" && c0 && V.files.includes("county")) return ["county", c0, 0];      // the county file is keyed as the page files a county
  if (kind === "mcd") return c0 && V.mcd.includes(c0) ? ["mcd-" + c0, id, r.g ? 0 : 1] : [null, kind];
  if (V.files.includes(kind)) return [kind, id, 0];
  if ((kind === "swcd" || kind === "park") && c0 && V.files.includes("county")) return ["county", c0, kind === "swcd" && ((BOOT.geo || {}).swWhole || []).includes(id) ? 0 : 1];      // a conservation district that is the whole county: the county's own figures
  return [null, kind];
}
function votesHTML(M, name, rows, few, wider, kind){
  const dot = party => /democrat/i.test(party) ? PV.D : /republican/i.test(party) ? PV.R : PV.O;
  const blocks = M.contests.map((c, i) => { const v = rows[i]; if (!v) return "";
    const total = v[v.length - 1], head = `<div class="pvh"><b>${esc(String(c.date || "").slice(0, 4))} &middot; ${esc(c.office)}</b><span>${num(total)} votes</span></div>`;
    if ((few || []).includes(i)) return `<div class="pv">${head}<p class="ynote">Very few people voted here, so the split is left out: it would come close to saying how particular people voted.</p></div>`;
    const lines = c.sides.map(([party, ticket], j) => [ticket, party, v[j], dot(party)]).concat([["Everyone else", "other candidates and write-ins, together", v[v.length - 2], PV.O]]);
    return `<div class="pv">${head}${lines.map(([t, p, n, col]) => { const pct = total ? (100 * n / total).toFixed(1) : "0.0";
      return `<div class="pvr"><span class="pvn"><i style="background:${col}"></i>${esc(t)}<small>${esc(p)}</small></span><span class="pvb" aria-hidden="true"><i style="width:${pct}%"></i></span><span class="pvv">${num(n)}<small>${pct}%</small></span></div>`; }).join("")}</div>`; }).filter(Boolean);
  const K = (M.kinds || {})[kind] || {}, missing = M.contests.some((c, i) => !rows[i]);
  const srcs = (M.sources || []).map(s => `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}<small>${/not itself an official record/i.test(s.kind || "") ? `<span class="tag analysis">Secondary</span>` : `<span class="tag fact">Fact</span>`}${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(hostOf(s.url))}</a>` : ""}${s.kind ? ` &middot; ${esc(s.kind)}` : ""}${s.canvassed ? ` &middot; canvassed ${esc(s.canvassed)}` : ""}</small>${s.use ? `<small><b>Its notice on use:</b> ${esc(s.use)}</small>` : ""}${s.disclaimer ? `<small><b>Its disclaimer, word for word:</b> ${esc(s.disclaimer)}</small>` : ""}</div>`).join("");
  return `<h3>How this place has voted</h3>
    <p class="ynote"><b>${esc(name)}</b>: the votes cast here in past partisan elections, added up from the official ${BOOT.votes.by ? BOOT.votes.by + " " : ""}results.${wider ? " These are for the whole of it: the results are not added up for the part that votes in this contest." : ""}${missing && K.why_not ? " " + esc(K.why_not) : ""}</p>
    ${blocks.length ? `<div class="pvgrid">${blocks.join("")}</div>` : `<p class="ynote">The official results hold no contest on this place&rsquo;s lines.</p>`}
    <p class="fnote">${esc(M.note || "")}</p>
    <details class="lmore"><summary>Where these counts come from, and the notices that travel with them</summary><div class="srclist" style="margin-top:8px">${srcs}</div></details>`;
}
function mountVotes(r){
  const box = $("#pvotes"); if (!box) return;
  const P = votePlace(r), put = html => { if (box.isConnected) box.innerHTML = html; };
  const none = why => put(`<h3>How this place has voted</h3><p class="ynote">${why}</p>`), fail = () => none("The past results could not be loaded. Check your connection and open the page again.");
  if (!P) { none("The map files do not say which place this contest belongs to, so no past votes are shown for it."); return; }
  if (P[0] === "state") { needMeta().then(M => put(votesHTML(M, ST.name, M.contests.map(c => c.state || 0), [], 0, "state")), fail); return; }
  if (!P[0]) { needMeta().then(M => none(P[1] === "school" && M.not_given ? `${esc(M.not_given)} So no figures are shown for a school district.` : "The official results are not added up for this kind of district, so none are shown."), fail); return; }
  needVotes(P[0]).then(F => {
    const e = F[P[1]], kind = P[0].replace(/-.*$/, "");
    if (e) { put(votesHTML(VMETA, e[0] || raceWhere(r), e[1], e[2] || [], P[2], kind)); return; }
    const c0 = (r.c || [])[0], city = P[0] === "ward" ? P[1].split("|")[0] : "";      // a ward the results do not name this way: the whole city's figures, said as such
    if (city && c0 && BOOT.votes.mcd.includes(c0)) return needVotes("mcd-" + c0).then(F2 => { const e2 = F2[city];
      if (e2) put(votesHTML(VMETA, e2[0], e2[1], e2[2] || [], 1, "mcd")); else none("The official results hold no figures for this place."); });
    none("The official results hold no figures for this place.");
  }).catch(fail);
}
const wideRace = r => r.lv === "statewide" || (BOOT.mkAlso || []).includes(r.id);      // the statewide offices, and a seat the whole state votes on that has a poll or a market (a supreme court seat)
const NO_MARKET = `<p class="fnote nomarket">No prediction market lists this race: the exchanges list races with wide national interest, a small race draws too few traders to hold a price, and some states restrict these markets.</p>`;
function tabsFor(r){      // polls and markets, on the statewide races of a state that has them: the tabs a race for Congress has
  // the sentence about a race no market lists: once, on a statewide or county office's page, and on no other
  if (!BOOT.mk || typeof raceTabs !== "function") return "";
  const held = (BOOT.mkHeld || []).includes(r.id);      // a market does list this race and it is held back (too thinly traded to show): nothing is said of markets
  if (r.lv === "county") return held ? "" : NO_MARKET;
  if (!wideRace(r)) return "";
  const O = (BOOT.odds || {})[r.id], listed = !!O && ["polymarket", "kalshi"].some(k => O[k] && (O[k].rows || []).length);
  return raceTabs(r) + (listed || held ? "" : NO_MARKET);
}
function quietMarkets(r){      // outcomes a market lists that nobody has traded yet: named, never given a price
  const O = (BOOT.odds || {})[r.id], box = $("#panel-odds"); if (!O || !box) return;
  [["polymarket", "Polymarket"], ["kalshi", "Kalshi"]].forEach(([k, name]) => { const q = (O[k] || {}).quiet || []; if (!q.length) return;
    const b = [...$$(".mkt", box)].find(x => (x.querySelector(".mh b") || {}).textContent === name);
    if (b) b.querySelector(".mgo").insertAdjacentHTML("beforebegin", `<p class="fnote">Also listed there, with no trade yet and so no price: ${q.map(esc).join(", ")}.</p>`); });
  // an outcome a market lists that names nobody on the November list: no row is drawn for it, and it is said once
  [["polymarket", "Polymarket"], ["kalshi", "Kalshi"]].forEach(([k, name]) => { const off = (O[k] || {}).off || []; if (!off.length) return;
    const b = [...$$(".mkt", box)].find(x => (x.querySelector(".mh b") || {}).textContent === name);
    if (b) b.querySelector(".mgo").insertAdjacentHTML("beforebegin", `<p class="fnote">${name} also lists ${andList(off.map(t => `&ldquo;${esc(t)}&rdquo;`))}, which ${off.length === 1 ? "names" : "name"} nobody on the November ballot: no row is drawn for ${off.length === 1 ? "it" : "them"} here.</p>`); });
}
/* </extras> */
function arena(r){
  const g = general(r); if (!g.length) return "";
  const parts = []; g.forEach((c, i) => { if (i && g.length === 2) parts.push(`<span class="vs" aria-hidden="true">vs</span>`); parts.push(card(c, r, i)); });
  const ordered = g.some(c => c.o != null);
  // What November 3 is for this contest, from the record: a loader marks a candidate elected with no vote as
  // "unopposed" (Louisiana, Florida: the name is not printed), and begins the race's note "Open primary" where the
  // day is an open primary with a later general election (Louisiana's local offices).
  const unopp = g.every(c => c.out === "unopposed"), openP = /^Open primary\b/.test(r.note || "");
  const title = unopp ? "Elected without a vote" : openP ? "Open primary" : r.sp ? "Special election" : "General election";
  return `<section class="arena deal st" id="arena" aria-label="${unopp ? "Elected without a vote" : openP ? "The open primary" : "The general election"}, ${esc(fmtDate(r.date))}">
    <div class="ahead"><b>${title} &middot; ${esc(fmtDate(r.date))}</b><span>${unopp ? "Not printed on the ballot: nobody else qualified" : g.length === 1 ? "One name for this office" : `${g.length} candidates, ${ordered ? `in the ballot order the ${whoOf(r)} list gives` : "by surname: the list gives no ballot order"}`}</span></div>
    <div class="acards" data-n="${g.length}">${parts.join("")}</div>
    <p class="anote">${r.f ? `Every card is the same size. A card shows the name as filed${r.pt ? " and the party it was filed under" : ""}, an age and the office a candidate holds today where a record or a named source gives them, and the ballot order. Where each comes from is set out under &ldquo;Who they are&rdquo; below; an age that reads &ldquo;about&rdquo; is worked out from a birth year alone. A candidate who serves in the Legislature or a statewide office today links to their record. No score or grade of any person.`
      : `Every card is the same size. A card holds what the ${whoOf(r)} list holds: the name as filed, the party it was filed under (or that the office is nonpartisan) and the ballot order. A candidate who serves in the Legislature or a statewide office today links to their record. No score or grade of any person.`}${ordered && !r.pt ? " The order printed on your own ballot can differ from precinct to precinct; your county&rsquo;s sample ballot shows it." : ""}${!ordered && ST.orderNote && g.length > 1 ? " " + esc(ST.orderNote) : ""}</p>
  </section>`;
}
/* ---------- a partisan primary, and its field ---------- */
function field(r, key){
  const list = r.el[key] || []; if (!list.length) return "";
  const votes = list.some(c => c.v != null), max = Math.max(1, ...list.map(c => c.pct || 0));
  const rows = [...list].sort((a, b) => votes ? (b.v || 0) - (a.v || 0) : surname(a.n).localeCompare(surname(b.n)));
  const src = D.sources[list[0].src];
  const runoff = /primary/.test(key) ? r.el[key.replace("primary", "runoff")] || [] : [], toRunoff = c => runoff.some(x => x.n === c.n);      // a primary that sent two on to a runoff sent neither to November yet
  return `<section class="field run"><div class="fh"><b>${esc(D.elections[key] || key)} &middot; ${esc(fmtDate(list[0].date))}</b><span>${plural(list.length, "candidate")} filed</span></div>
    <ol class="lanes">${rows.map((c, i) => { const href = c.m ? recordHref(c.m) : "";
      return `<li class="lane${c.out === "advanced" ? " won" : ""}${votes ? "" : " nobar"}" style="--pc:${pcVar(c)};--k:${i}"><span class="nm">${href ? `<a href="${href}">${esc(c.n)}</a>` : esc(c.n)}<small>${esc(c.p || "")}${serves(c, r) ? " &middot; serves in this seat today" : ""}</small></span>
      <span class="bar"><i style="--w:${votes ? (100 * (c.pct || 0) / max).toFixed(1) : 0}%"></i></span>
      <span class="vv">${votes ? `${num(c.v)} &middot; ${(c.pct || 0).toFixed(1)}%` : (c.out === "advanced" ? (toRunoff(c) ? "Went on to the runoff" : "On the November ballot") : c.out === "lost" ? "Not on the November ballot" : "")}</span></li>`; }).join("")}</ol>
    <p class="fnote">${votes ? `Votes as certified in the official results (${esc(src ? src.agency : ST.agency)}).` : ST.noVotes}</p></section>`;
}

/* ---------- maps: the lines, decoded once ---------- */
const shapeCache = {};
function shapeFrom(raw, q){
  const rings = raw.map(r => decodeRing(r, q)); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, best = null, bestA = 0;
  for (const r of rings) for (const [x, y] of r) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  for (const r of rings) { let a = 0, cx = 0, cy = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const f = r[j][0] * r[i][1] - r[i][0] * r[j][1]; a += f; cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f; }
    if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = a ? [cx / (3 * a), cy / (3 * a)] : r[0]; } }
  let at = best || [(x0 + x1) / 2, (y0 + y1) / 2]; const inside = inShape(at, rings); if (!inside) at = [(x0 + x1) / 2, (y0 + y1) / 2];
  return {rings, d: rings.map(r => "M" + r.map(p => p[0].toFixed(3) + "," + p[1].toFixed(3)).join("L") + "Z").join(""), bbox: [x0, y0, x1, y1], at, room: Math.sqrt(bestA / 2), inside};
}
function shapesOf(key){
  if (shapeCache[key]) return shapeCache[key];
  const src = key === "counties" ? LINES.counties : LINES[key], q = key === "counties" ? (LINES.cq || 400) : (LINES.q || 400), out = {};
  for (const [k, raw] of Object.entries(src || {})) out[k] = shapeFrom(raw, q);
  return shapeCache[key] = out;
}
function placeAt(lon, lat){      // on this device only: which county and which districts a point falls in
  const pt = albersUsa(lon, lat), out = {c: null, hd: null, sd: null}; if (!pt) return out;
  const hit = S => { for (const [k, s] of Object.entries(S)) { const b = s.bbox; if (pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) continue; if (inShape(pt, s.rings)) return k; } return null; };
  out.hd = hit(shapesOf("lower"));
  if (!ST.nest) out.sd = hit(shapesOf("upper"));      // where the chambers' lines do not nest, the upper district is looked up on its own
  if (ST.local && LINES.counties) out.c = hit(shapesOf("counties"));
  return out;
}
const aspectOf = b => Math.min(1.75, Math.max(.8, (b[2] - b[0]) / Math.max(1e-6, b[3] - b[1])));
const fitBox = (b, aspect, pad) => { let w = (b[2] - b[0]) * pad, h = (b[3] - b[1]) * pad; if (w / h > aspect) h = w / aspect; else w = h * aspect; return [(b[0] + b[2]) / 2 - w / 2, (b[1] + b[3]) / 2 - h / 2, w, h]; };
const HOLDP = ["D", "R", "I", "L", "G", "O"];
const openDefs = (id, w) => `<defs>${HOLDP.map(h => `<pattern id="${id}-open-${h}" class="stripe" patternUnits="userSpaceOnUse" width="${w.toFixed(4)}" height="${w.toFixed(4)}" patternTransform="rotate(45)"><rect class="s0" width="${w.toFixed(4)}" height="${w.toFixed(4)}" style="fill:${PV[h]};opacity:.28"/><rect class="s1" width="${(w * .42).toFixed(4)}" height="${w.toFixed(4)}" style="fill:${PV[h]}"/></pattern>`).join("")}${[...SPLITS].map(pr => `<pattern id="${id}-split-${pr}" patternContentUnits="objectBoundingBox" width="1" height="1"><rect width=".5" height="1" style="fill:${PV[pr[0]] || PV.O}"/><rect x=".5" width=".5" height="1" style="fill:${PV[pr[1]] || PV.O}"/></pattern>`).join("")}</defs>`;
const splitOf = r => [...new Set((r && r.hc) || [])].slice(0, 2).join("");      // a district whose two members are of two parties is drawn half and half
const swatch = (k, r) => k === "S" ? (pr => `linear-gradient(90deg,${PV[pr[0]] || PV.O} 50%,${PV[pr[1]] || PV.O} 50%)`)(splitOf(r) || "DR") : PV[k];
const sizeStripes = (svg, w) => $$("pattern.stripe", svg).forEach(p => { const v = w.toFixed(4); p.setAttribute("width", v); p.setAttribute("height", v); const [a, b] = p.children; if (a) { a.setAttribute("width", v); a.setAttribute("height", v); } if (b) { b.setAttribute("width", (w * .42).toFixed(4)); b.setAttribute("height", v); } });
const hcode = r => r && r.h ? (HOLDP.includes(r.h[3]) ? r.h[3] : r.h[3] === "S" && splitOf(r).length === 2 ? "S" : "I") : null;
const seatFill = (r, id) => { if (!r) return "var(--line)"; const h = hcode(r); return !h ? "var(--line-strong)" : h === "S" ? `url(#${id}-split-${splitOf(r)})` : seatState(r) === "open" ? `url(#${id}-open-${h})` : PV[h]; };
const ONE = {D: ST.dOne, S: "members of two parties", R: "a Republican", I: "a member of another party or none", L: "a Libertarian", G: "a Green", O: "a member of another party"};
const MANY = {D: ST.dMany, S: "members of two parties", R: "Republicans", I: "members of other parties or none", L: "Libertarians", G: "Greens", O: "members of other parties"};
const myDistrict = key => (key === "upper" ? upperOf(MINE) : MINE.hd) || null;
function legPreview(r){
  const g = general(r), h = hcode(r);
  return `<span class="kick">${NM} ${r.k === "state_senate" ? UP : LO}${r.sp ? " &middot; special election" : ""}</span>
    <h3><span class="dnum" style="--pc:${h ? (h === "S" ? PV[splitOf(r)[0]] : PV[h]) : "var(--line-strong)"}">${esc(r.d)}</span>District ${esc(r.d)}</h3>
    <p class="held">${seatWords(r, false)}</p>
    ${g.length ? `<ol class="plist">${g.map(c => `<li style="--pc:${pcVar(c)}"><span class="av">${esc(initials(c.n))}</span><span><b>${esc(c.n)}${serves(c, r) ? '<span class="star" title="Serves in this seat today">&#9733;</span>' : ""}</b><small>${esc(partyWords(c, r))}${c.wi ? " &middot; write-in" : ""}</small></span></li>`).join("")}</ol>` : `<p class="held">${EMPTY ? EMPTY + "." : `No candidate for this seat is on the ${WHO} list.`}</p>`}
    <a class="rpgo" href="${hrefRace(r)}">Open the race &rsaquo;</a>`;
}
function legSummary(key){
  const rs = Object.values(LEG[key]), n = {}; let open = 0, vac = 0, unk = 0;
  rs.forEach(r => { const h = hcode(r); if (!h) { vac++; return; } n[h] = (n[h] || 0) + 1; const s = seatState(r); if (s === "open") open++; else if (s === "unknown") unk++; });
  const split1 = rs.find(r => hcode(r) === "S");
  const rows = Object.entries(n).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<li><i style="background:${swatch(k, split1)}"></i>${num(v)} held by ${v === 1 ? ONE[k] : MANY[k]}</li>`);
  if (vac) rows.push(`<li><i style="background:var(--line-strong)"></i>${plural(vac, "seat")} with no member in the roster today</li>`);
  if ((ST.off || {})[key]) rows.push(`<li><i style="background:var(--line)"></i>${plural(ST.off[key], "district")} not on this year&rsquo;s ballot</li>`);
  if (unk) rows.push(`<li><i style="background:var(--surface);border:1px dashed var(--line-strong)"></i>${plural(unk, "district")} whose November candidates are not on the lists loaded yet, shown in the holder&rsquo;s colour</li>`);
  if (unk < rs.length) rows.push(`<li><i style="background:repeating-linear-gradient(45deg,var(--muted) 0 2px,transparent 2px 5px)"></i>${open ? `${plural(open, "open seat")}: the member who holds it is not on its November ballot` : unk ? "No open seat among the rest" : "No open seat: every member is on the ballot again"}</li>`);
  const hover = matchMedia("(hover: hover)").matches;
  return `<span class="kick">${NM} ${key === "upper" ? UP : LO}</span><h3>${plural(rs.length, "district")} on the ballot</h3>
    <ul class="tally">${rows.join("")}</ul><p class="sidehint">${hover ? "Point at a district to see who is running there; click to keep it here." : "Tap a district to see who is running there."}${ST.zoom ? ` Zoom in for ${esc(ST.zoom)}.` : ""}</p>`;
}
let mapOff = null;
const legMapHTML = () => `<section class="bsec" id="mapsec"><h2>On the map</h2><p class="sub">Each district in the colour of the party that holds it today; striped where the member who holds it is not on the November ballot for it. The colours say who holds a seat, never who will win it.</p>
  <div class="mapgrid"><div class="mapcol">
    <div class="mapbar">${ST.one ? "<span></span>" : `<div class="seg" role="group" aria-label="Which chamber"><button type="button" data-v="upper" aria-pressed="true">${esc(ST.upSeg)}</button><button type="button" data-v="lower" aria-pressed="false">${esc(ST.loSeg)}</button></div>`}
      <div class="zoom" role="group" aria-label="Zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">&minus;</button><button type="button" data-z="fit" aria-label="Show the whole state">&#10530;</button></div></div>
    <div class="svgbox" id="svgbox"><svg class="bstate" id="bstate" role="group" aria-label="Map of ${NM}&rsquo;s legislative districts"></svg></div>
    <select class="pick jump" id="djump" aria-label="Jump to a district"></select>
    <p class="mnote" id="bnote"></p></div>
  <aside class="mapside" id="mapside" aria-live="polite"></aside></div></section>`;
async function mountLegMap(){
  const svg = $("#bstate"), side = $("#mapside"), box = $("#svgbox"), note = $("#bnote"), jump = $("#djump"); if (!svg) return;
  let view = "upper", sel = null, drag = null, moved = false;
  side.innerHTML = legSummary(view);
  try { await needLines(); } catch (e) { note.textContent = "The district lines could not be loaded. Check your connection and open the page again."; return; }
  if (!svg.isConnected) return;      // the reader moved on while the lines loaded
  const B = LINES.outline.bbox, vb0 = fitBox(B, aspectOf(B), 1.04), hover = matchMedia("(hover: hover)").matches;
  let vb = vb0.slice();
  const S = () => shapesOf(view);
  const unitsPerPx = () => vb[2] / Math.max(1, svg.getBoundingClientRect().width || 640);
  function relabel(){      // browsers will not draw type below a minimum size: the numbers stay 12px and are scaled to the map
    const s = unitsPerPx(), sh = S();
    $$("text.dlab", svg).forEach(t => { const x = sh[t.dataset.d]; if (!x) return;
      t.setAttribute("transform", `translate(${x.at[0].toFixed(3)} ${x.at[1].toFixed(3)}) scale(${s.toFixed(5)})`);
      t.classList.toggle("tiny", t.dataset.d !== sel && (!x.inside || x.room / s < .9 * (8.5 * t.dataset.d.length + 8))); });
  }
  const setVB = v => { vb = v; svg.setAttribute("viewBox", v.map(x => x.toFixed(3)).join(" ")); box.classList.toggle("zoomed", v[2] < vb0[2] * .98); sizeStripes(svg, v[2] / 110); relabel(); };
  const clamp = v => [Math.min(Math.max(v[0], vb0[0]), vb0[0] + vb0[2] - v[2]), Math.min(Math.max(v[1], vb0[1]), vb0[1] + vb0[3] - v[3]), v[2], v[3]];
  function zoomAt(f, at){ const w = Math.min(vb0[2], Math.max(vb0[2] / 60, vb[2] / f)), k = w / vb[2], h = vb[3] * k, [px, py] = at || [vb[0] + vb[2] / 2, vb[1] + vb[3] / 2]; setVB(clamp([px - (px - vb[0]) * k, py - (py - vb[1]) * k, w, h])); }
  function zoomTo(d){ const x = S()[d]; if (!x) return; const b = x.bbox, c = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
    const w = Math.min(vb0[2], Math.max((b[2] - b[0]) * 3, (b[3] - b[1]) * 3 * vb0[2] / vb0[3], vb0[2] / 60)), h = w * vb0[3] / vb0[2]; setVB(clamp([c[0] - w / 2, c[1] - h / 2, w, h])); }
  function marks(){
    $$("path.ring, path.mine", svg).forEach(p => p.remove());
    const sh = S(), my = myDistrict(view);
    if (my && sh[my]) svg.insertAdjacentHTML("beforeend", `<path class="mine" d="${sh[my].d}"><title>Your district</title></path>`);
    if (sel != null && sh[sel]) svg.insertAdjacentHTML("beforeend", `<path class="ring" d="${sh[sel].d}"/>`);
  }
  function draw(){
    const sh = S(), keys = Object.keys(sh).sort(byDistrict);
    let body = openDefs("lg", vb0[2] / 110);
    body += keys.map(d => { const r = legRace(view, d), st = r ? seatState(r) : "none";
      return `<path class="dist${st === "vacant" ? " vac" : ""}" data-d="${esc(d)}" d="${sh[d].d}" style="fill:${seatFill(r, "lg")}" tabindex="0" role="button" aria-label="${esc(r ? raceTitle(r) : "District " + d)}. ${esc(r ? plain(seatWords(r, false)) : "No race for this district is on the list")}"/>`; }).join("");
    body += keys.map(d => `<text class="dlab tiny" data-d="${esc(d)}" dy=".36em">${esc(d)}</text>`).join("");
    body += `<path class="sout" d="${LINES.outline.d}"/>`;
    svg.innerHTML = body; setVB(vb); marks();
    jump.innerHTML = `<option value="">Jump to a${/^[AEIOU]/.test(view === "upper" ? ST.up : ST.lo) ? "n" : ""} ${view === "upper" ? UP : LO} district&hellip;</option>` + keys.map(d => `<option value="${esc(d)}"${d === sel ? " selected" : ""}>District ${esc(d)}</option>`).join("");
    note.innerHTML = `District lines: ${esc(LINES.vintage || "the Census Bureau's current file")}${ST.linesNote}.${myDistrict(view) ? " Your district, as picked on this page, is outlined in gold." : ""}${GEO_ON ? ` For these districts down to their streets, see <a href="#map=${view === "upper" ? "senate" : "house"}">the map under &ldquo;your ballot&rdquo;</a>.` : ""}`;
  }
  function show(d, keep){ const r = legRace(view, d); if (keep) { sel = d; marks(); relabel(); jump.value = d; } side.innerHTML = r ? legPreview(r) : `<p class="held">${noLegRace(view, `District ${esc(d)}`)}</p>`; }
  const rest = () => { side.innerHTML = sel != null && legRace(view, sel) ? legPreview(legRace(view, sel)) : legSummary(view); };
  const toUnits = e => { const b = svg.getBoundingClientRect(); return [vb[0] + (e.clientX - b.left) / b.width * vb[2], vb[1] + (e.clientY - b.top) / b.height * vb[3]]; };
  svg.addEventListener("click", e => { if (moved) { moved = false; return; } const p = e.target.closest("path.dist"); if (!p) return; show(p.dataset.d, true);
    if (!hover && side.getBoundingClientRect().top > innerHeight - 80) side.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); });
  svg.addEventListener("keydown", e => { if (e.key !== "Enter" && e.key !== " ") return; const p = e.target.closest("path.dist"); if (p) { e.preventDefault(); show(p.dataset.d, true); } });
  if (hover) {
    svg.addEventListener("pointerover", e => { const p = e.target.closest("path.dist"); if (!p || drag) return; $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")); p.classList.add("hl"); show(p.dataset.d, false); });
    svg.addEventListener("pointerleave", () => { $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")); rest(); });
  }
  if (mapOff) mapOff.abort();      // the window's listeners from the last map opened go with it
  mapOff = new AbortController();
  const sig = {signal: mapOff.signal};
  svg.addEventListener("dblclick", e => { e.preventDefault(); zoomAt(2, toUnits(e)); });
  svg.addEventListener("pointerdown", e => { moved = false; if (!box.classList.contains("zoomed") || e.button) return; drag = {x: e.clientX, y: e.clientY, vb: vb.slice()}; });
  addEventListener("pointermove", e => {      // no pointer capture: the map lets the page keep its clicks
    if (!drag || !svg.isConnected) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!moved && Math.hypot(dx, dy) < 4) return;
    moved = true; box.classList.add("drag"); const k = unitsPerPx(); setVB(clamp([drag.vb[0] - dx * k, drag.vb[1] - dy * k, vb[2], vb[3]]));
  }, sig);
  addEventListener("pointerup", () => { if (drag) { drag = null; box.classList.remove("drag"); } }, sig);
  addEventListener("resize", () => { if (svg.isConnected) relabel(); }, sig);
  $$(".zoom button", $("#mapsec")).forEach(b => b.addEventListener("click", () => { if (b.dataset.z === "fit") setVB(vb0.slice()); else zoomAt(b.dataset.z === "in" ? 1.8 : 1 / 1.8); }));
  $$(".seg button", $("#mapsec")).forEach(b => b.addEventListener("click", () => {
    if (b.dataset.v === view) return;
    view = b.dataset.v; sel = null; $$(".seg button", $("#mapsec")).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    draw(); rest();
  }));
  jump.addEventListener("change", () => { if (!jump.value) return; zoomTo(jump.value); show(jump.value, true); });
  draw();
}
/* the counties: a map to pick one from, and a locator on a county's or a race's page */
async function mountCountyMap(svgId, on, cap){
  const svg = $("#" + svgId); if (!svg) return;
  try { await needLines(); } catch (e) { const w = svg.closest(".cmapwrap, .loc"); if (w) w.hidden = true; return; }
  if (!svg.isConnected) return;
  const S = shapesOf("counties"), B = LINES.outline.bbox, vb = fitBox(B, aspectOf(B), 1.03), set = new Set(on || []);
  svg.classList.add("cmap"); svg.setAttribute("viewBox", vb.map(v => v.toFixed(3)).join(" "));
  svg.innerHTML = Object.entries(S).map(([f, s]) => !D.counties[f] ? `<path class="cty off" d="${s.d}"/>`      // a shape the lists do not name is drawn and nothing more
    : `<path class="cty${set.has(f) ? " me" : ""}" d="${s.d}" data-c="${esc(f)}" tabindex="0" role="link" aria-label="${esc(cName(f))}: ${plural(COUNTS[f] || 0, "contest")}"><title>${esc(cName(f))}: ${plural(COUNTS[f] || 0, "contest")}</title></path>`).join("")
    + `<path class="cout" d="${LINES.outline.d}"/>`;
  const go = p => { if (p && p.dataset.c) location.hash = "county=" + p.dataset.c; };
  svg.addEventListener("click", e => go(e.target.closest("path.cty")));
  svg.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { const p = e.target.closest("path.cty"); if (p) { e.preventDefault(); go(p); } } });
  if (cap && $("#" + cap)) $("#" + cap).textContent = set.size ? `${set.size === 1 ? `The ${CO1}` : `The ${set.size} ${COS}`} in colour. Tap another ${CO1} to open its page.` : `Tap a ${CO1} to open its page.`;
}
async function mountLegLocator(r){      // a legislative race's own district picked out on the state; a tap on another district opens its race
  const svg = $("#locsvg"); if (!svg) return;
  try { await needLines(); } catch (e) { const f = svg.closest(".loc"); if (f) f.hidden = true; return; }
  if (!svg.isConnected) return;
  const key = r.k === "state_senate" ? "upper" : "lower", S = shapesOf(key), B = LINES.outline.bbox;
  const mine = S[r.d] ? [r.d] : Object.keys(S).filter(k => k.replace(/[A-Z]$/, "") === r.d);      // a district the lines split in two (North Dakota's 9A and 9B)
  const me = mine.length ? mine.map(k => S[k]) : null;
  const b = me ? me.reduce((a, s) => [Math.min(a[0], s.bbox[0]), Math.min(a[1], s.bbox[1]), Math.max(a[2], s.bbox[2]), Math.max(a[3], s.bbox[3])], [1e9, 1e9, -1e9, -1e9]) : B;
  const zoom = me && (b[2] - b[0]) < (B[2] - B[0]) / 8;      // a small district: show it with its neighbours
  const vb = zoom ? fitBox([b[0] - (b[2] - b[0]) * 3, b[1] - (b[3] - b[1]) * 3, b[2] + (b[2] - b[0]) * 3, b[3] + (b[3] - b[1]) * 3], 1, 1) : fitBox(B, aspectOf(B), 1.04);
  let body = openDefs("lm", vb[2] / 60);
  const inView = s => s.bbox[2] >= vb[0] && s.bbox[0] <= vb[0] + vb[2] && s.bbox[3] >= vb[1] && s.bbox[1] <= vb[1] + vb[3];
  body += Object.entries(S).filter(([d, s]) => !mine.includes(d) && inView(s)).map(([d, s]) => `<path class="lot" data-d="${esc(d)}" d="${s.d}"><title>District ${esc(d)}</title></path>`).join("");
  if (me) body += me.map(s => `<path class="lme" d="${s.d}" style="fill:${seatFill(r, "lm")}"/>`).join("");
  body += `<path class="lout" d="${LINES.outline.d}"/>`;
  svg.setAttribute("viewBox", vb.map(v => v.toFixed(3)).join(" ")); svg.innerHTML = body;
  $("#loccap").textContent = me ? `${r.k === "state_senate" ? ST.upD : ST.loD} ${r.d}${zoom ? " and its neighbours" : ""}. Tap another district to open its race.` : "This district's lines are not in the file.";
  svg.addEventListener("click", e => { const p = e.target.closest("path.lot"); const rr = p && legRace(key, p.dataset.d); if (rr) location.hash = hrefRace(rr).slice(1); });
}
const locatorHTML = () => `<figure class="loc"><svg id="locsvg" role="img" aria-label="Where this is"></svg><figcaption id="loccap"></figcaption></figure>`;

/* ---------- your ballot: county, city or township, school district (where the list reaches them) and districts, kept on this device only ---------- */
const YKEY = "ballot:" + ST.lc, SLD = "sld:" + ST.lc;
function readMine(){
  let m = {}; try { m = JSON.parse(store.get(YKEY) || "{}") || {}; } catch (e) { m = {}; }
  const pin = store.get("pin");
  if (m.loc && !pin) m = {};      // the location was forgotten on another page: forget what came from it here too
  if (!m.hd) { try { const s = JSON.parse(store.get(SLD) || "null"); if (s && s.l && (s.from !== "pin" || pin)) { m.hd = String(s.l); if (!ST.nest && s.u) m.sd = String(s.u); } } catch (e) {} }
  if (m.c && !D.counties[m.c]) m = {};
  if (m.hd && !D.hds.includes(m.hd)) delete m.hd;
  if (m.sd && (ST.nest || !D.sds.includes(m.sd))) delete m.sd;
  if (m.z && (!GEO_ON || !m.z.p || !Array.isArray(m.z.sch) || m.z.c !== m.c)) delete m.z;      // the precinct found by location, kept only with the county it belongs to
  return m;
}
function placesIn(kind, f){
  return Object.entries(D.places[kind] || {}).filter(([, P]) => (P.c || []).includes(f)).map(([k, P]) => [kind + k, P]).sort((a, b) => a[1].n.localeCompare(b[1].n));
}
const placeLabel = P => P.t && !new RegExp(`\\b${P.t}$`, "i").test(P.n) ? `${P.n} (${P.t})` : P.n;
const LOC_BTN = `<button type="button" class="locbtn" id="yloc"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="11" r="3"/><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/></svg>Use my location</button><button type="button" class="linkbtn" id="yforget" hidden>Forget my location and choices</button>`;
/* where the list reaches the counties: the county, then the city or town or township and the school district the state's
   rows have (a state with no city contests on this ballot has no city to pick), then the legislative districts */
const twoPicks = !ST.one && !ST.nest;      // the two chambers' districts are drawn separately: one choice for each
const OLDER = !!ST.older;      // Minnesota's rows, loaded before the local conventions: its page reads them, and says what it said, as before
/* <extras> */
/* where a state has its map files (John, 2026-10-01): one map for every kind of line a ballot is made of, set into "your ballot". The
   map's own script (geo/mapkit.js) is fetched when this section is shown; the lists above it work without it. */
const PIN_SVG =`<svg viewBox="0 0 26 34" aria-hidden="true"><path d="M13 33C13 33 2 20.6 2 12.4 2 6.1 6.9 1 13 1s11 5.1 11 11.4C24 20.6 13 33 13 33z"/><circle cx="13" cy="12.2" r="4.3"/></svg>`;
const STREETS_OFF = `Street pictures are off. Switched on, they come from OpenStreetMap&rsquo;s servers, which see which map squares are asked for; everything else stays on this device.`;
const geoYoursHTML = () => `<section class="bsec" id="yours"><h2>Your ballot</h2>
  <p class="sub">Use your location and this device finds your ${UNIT}, lists every district you are in and puts your ballot together. Or pick ${andList([`your ${esc(ST.countyWord)}`, ST.pickM ? `your ${esc(MUNI1)}` : "", ST.pickS ? `your ${esc(ST.schoolOne)}` : "", `your ${NM} ${esc(dWord(ST.one ? "upper" : "lower"))}`, twoPicks ? `your ${esc(dWord("upper"))}` : ""].filter(Boolean))} by hand. Your location and your choices stay on this device; nothing is sent anywhere.</p>
  <div class="mybar">${LOC_BTN}</div>
  <div class="mybar"><select class="pick" id="ycty" aria-label="Your ${esc(ST.countyWord)}"></select>${ST.pickM ? `<select class="pick" id="ymcd" aria-label="Your ${esc(MUNI1)}"></select>` : ""}${ST.pickS ? `<select class="pick" id="ysch" aria-label="Your ${esc(ST.schoolOne)}"></select>` : ""}${ST.one ? "" : `<select class="pick" id="yhd" aria-label="Your ${NM} ${esc(dWord("lower"))}"></select>`}${ST.nest ? "" : `<select class="pick" id="ysd" aria-label="Your ${NM} ${esc(dWord("upper"))}"></select>`}</div>
  <p class="ynote" id="ynote" aria-live="polite"></p>
  <div class="mapgrid gmapgrid" id="gmapsec">
    <div class="mapcol">
      <div class="mapbar">
        <div class="glayers" id="glayers" role="group" aria-label="Which lines to draw"></div>
        <label class="glayersel"><span>Lines to draw</span><select class="pick" id="glayer"></select></label>
        <div class="zoom" role="group" aria-label="Zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">&minus;</button><button type="button" data-z="fit" aria-label="Show the whole state">&#10530;</button><button type="button" data-z="me" id="gme" aria-label="Go to my ${UNIT}" title="Go to my ${UNIT}" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="11" r="3"/><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/></svg></button></div>
      </div>
      <div class="gmap" id="gmap" tabindex="0" role="group" aria-roledescription="map" aria-label="Map of ${NM}" aria-describedby="gmaphelp">
        <div class="gtiles" aria-hidden="true"></div><canvas aria-hidden="true"></canvas>
        <div class="gpin" hidden aria-hidden="true">${PIN_SVG}</div>
        <a class="gattr" hidden href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap contributors</a>
        <span class="gbusy" hidden>Loading lines&hellip;</span>
      </div>
      <div class="gfindbar"><input type="search" class="gfind" id="gfind" list="gfindlist" autocomplete="off" placeholder="Find a ${esc(CO1)}" aria-label="Find a ${esc(CO1)} by name"><datalist id="gfindlist"></datalist>
        <button type="button" class="mtog gstreets" id="gstreets" aria-pressed="false"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Show streets</span></button></div>
      <p class="mnote" id="gstreetnote">${STREETS_OFF}</p>
      <p class="mnote"><span id="gline"></span>${ST.geoWho ? ` Lines: ${esc(ST.geoWho)}, provided as is and without warranty; their notices are below, word for word.` : ""}</p>
      ${(BOOT.geo || {}).old ? `<p class="mnote" id="gold"><b>The ${UNIT} lines here are ${esc(BOOT.geo.old.y)}&rsquo;s.</b> ${esc((BOOT.geo.old.t || []).join(" "))}</p>` : ""}
      <p class="sr" id="gmaphelp">The map is a picture of the lines. With the map in focus the arrow keys move it, plus and minus zoom, zero shows the whole state, Enter names the place under the cross in the middle and Escape lets go of it. Every place can also be found by name in the Find box, and its races are listed beside the map.</p>
    </div>
    <aside class="mapside" id="gside" aria-live="polite"><p class="held">Loading the map&hellip;</p></aside>
  </div>
  <details class="lmore" id="gabout"><summary>About these lines, and the notices that travel with them</summary><div class="fbody"></div></details>
  <div id="yballot"></div></section>`;
/* </extras> */
const yoursHTML = () => GEO_ON ? geoYoursHTML() : ST.local ? `<section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Pick ${andList([`your ${esc(ST.countyWord)}`, ST.pickM ? `your ${esc(MUNI1)}` : "", ST.pickS ? `your ${esc(ST.schoolOne)}` : "", `your ${NM} ${esc(dWord(ST.one ? "upper" : "lower"))}`, twoPicks ? `your ${esc(dWord("upper"))}` : ""].filter(Boolean))}, or let this device work out ${ST.cLines ? `the ${esc(ST.countyWord)} and the district${twoPicks ? "s" : ""}` : `the district${twoPicks ? "s" : ""}`}. Your choices and your location stay on this device; nothing is sent anywhere.</p>
  <div class="mybar"><select class="pick" id="ycty" aria-label="Your ${esc(ST.countyWord)}"></select>${ST.pickM ? `<select class="pick" id="ymcd" aria-label="Your ${esc(MUNI1)}"></select>` : ""}${ST.pickS ? `<select class="pick" id="ysch" aria-label="Your ${esc(ST.schoolOne)}"></select>` : ""}${ST.one ? "" : `<select class="pick" id="yhd" aria-label="Your ${NM} ${esc(dWord("lower"))}"></select>`}${ST.nest ? "" : `<select class="pick" id="ysd" aria-label="Your ${NM} ${esc(dWord("upper"))}"></select>`}</div>
  <div class="mybar">${LOC_BTN}</div>
  <p class="ynote" id="ynote" aria-live="polite"></p>
  <div id="yballot"></div></section>`
  : `<section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Pick your ${NM} ${ST.one ? esc(dWord("upper")) : esc(dWord("lower")) + (ST.nest ? "" : ` and your ${esc(dWord("upper"))}`)}, or let this device work ${ST.nest || ST.one ? "it" : "them"} out. Your choices and your location stay on this device; nothing is sent anywhere.</p>
  <div class="mybar">${ST.one ? "" : `<select class="pick" id="yhd" aria-label="Your ${NM} ${esc(dWord("lower"))}"></select>`}${ST.nest ? "" : `<select class="pick" id="ysd" aria-label="Your ${NM} ${esc(dWord("upper"))}"></select>`}</div>
  <div class="mybar">${LOC_BTN}</div>
  <p class="ynote" id="ynote" aria-live="polite"></p>
  <div id="yballot"></div></section>`;
function ballotHTML(m){
  if (!m.c && !m.hd && !m.sd) return "";
  const whereSub = r => r.lv === "hospital" || r.lv === "other" || r.k === "district_court" || localCourt(r) || (r.lv === "soil_water" && r.pk) ? esc(raceWhere(r)) : "";
  const rows = list => list.map(r => raceRow(r, "", whereSub(r))).join("");
  const level = (title, list, sub) => list.length ? `<div class="bl-level"><h4>${title}</h4>${sub ? `<p class="ynote">${sub}</p>` : ""}<div class="rlist">${rows(list)}</div></div>` : "";
  const note = (title, words) => `<div class="bl-level"><h4>${title}</h4><p class="ynote">${words}</p></div>`;
  const byLv = lv => D.races.filter(r => r.lv === lv);
  const inC = r => m.c && (r.c || []).includes(m.c);
  const districted = list => list.some(r => r.d || (OLDER && /\bward\b|\bdistrict\b/i.test(r.o || "")));      // elsewhere "District" in a title is the office's own name (Clerk of District Court)
  const DIST_NOTE = `Where an office is elected by district or ward, you vote only in your own; your ${CO1}&rsquo;s sample ballot shows which.`;
  /* a county with none of its own contests shown because its list could not be loaded: what is missing and why, in the loader's words, never an empty space */
  const countyGap = f => { const gs = GAPS.county[f] || []; return gs.length ? note(esc(cName(f)), gs.map(g => `<b>Not here yet: ${esc(g.w)}.</b> ${esc(g.r)}`).join(" ")) : ""; };
  const out = [];
  const sw = byLv("statewide");
  out.push(level("Statewide offices", sw, sw.some(r => r.d) ? "Some statewide boards are elected by district: only your own district&rsquo;s seat is on your ballot." : ""));
  const sd = upperOf(m), legs = [legRace("upper", sd), ST.one ? null : legRace("lower", m.hd)].filter(Boolean);
  const upOff = sd && !legRace("upper", sd) && (ST.off || {}).upper ? ` Your ${esc(ST.upD)} ${esc(sd)} is not on this year&rsquo;s ballot.` : "";
  const ask = ST.one ? `Pick your ${esc(dWord("upper"))}, or use your location, to see your race for the ${esc(ST.upT)}.`
    : ST.nest ? `Pick your ${esc(dWord("lower"))}, or use your location, to see your ${esc(ST.upT)} and ${esc(ST.loT)} races.`
    : `Pick your ${esc(dWord("lower"))} and your ${esc(dWord("upper"))}, or use your location, to see your ${esc(ST.loT)} and ${esc(ST.upT)} races.`;
  if (legs.length) out.push(level("The Legislature", legs, upOff.trim()));
  else if (m.hd || sd) out.push(note("The Legislature", `No ${esc(ST.upT)}${ST.one ? "" : ` or ${esc(ST.loT)}`} race for ${m.hd && !ST.one ? `District ${esc(m.hd)}` : `${esc(ST.upD)} ${esc(sd)}`} is on the ${WHO} list.${upOff}`));
  else out.push(note("The Legislature", ask));
  if (!ST.nest && !ST.one && legs.length && (!m.hd || !sd)) out.push(`<p class="ynote">${m.hd ? `Pick your ${esc(dWord("upper"))} too` : `Pick your ${esc(dWord("lower"))} too`}: the two chambers&rsquo; districts are drawn separately here.</p>`);
  const z = m.z && m.z.c === m.c ? m.z : null;      // a reader found by location: their precinct and every district it is in
  if (z) {      // exactly the contests of that precinct: each race names the shape that draws its place, and the precinct says which shapes it lies in
    const G = r => r.g || "", at = (kind, id) => id ? kind + ":" + id : "\u0000", LOOSE = "The map has no lines for the part of the place that elects this, so it is listed for everyone here; your county&rsquo;s sample ballot shows whether it is on yours.";
    const county = byLv("county").filter(r => inC(r) && (!G(r) || G(r) === at("county", z.gc || z.c) || G(r) === at("com", z.com) || G(r) === at("park", z.pk)));
    out.push(county.length ? level(esc(cName(m.c)), county, county.some(r => !G(r) && r.d) ? LOOSE : "") : countyGap(m.c));
    const soilAll = byLv("soil_water").filter(inC), soil = soilAll.filter(r => G(r) === at("swcd", z.sw) || (z.sw2 || []).some(i => G(r) === at("swcd", i))), soilLoose = soilAll.filter(r => !G(r));
    const soilSplit = soil.some(r => G(r) !== at("swcd", z.sw)) ? `Your ${UNIT} lies in more than one of these districts; only the one you live in is on your ballot.` : "";
    out.push(level(esc(LV.soil_water), soil.concat(soilLoose), [soilSplit, soilLoose.length ? LOOSE : ""].filter(Boolean).join(" ")));
    const mname = z.mn || placeName(mPk(z.m));
    const muni = D.races.filter(r => r.pk === mPk(z.m) && LOCAL.includes(r.lv) && (!G(r) || G(r) === at("mcd", z.m) || (G(r).startsWith("ward:") && (z.w || []).includes(G(r).slice(5)))));
    const elseM = D.races.filter(r => r.pk === mPk(z.m) && LOCAL.includes(r.lv) && !muni.includes(r));      // the place's contests in wards or districts that are not the reader's
    out.push(muni.length ? level(esc(mname), muni, muni.some(r => !G(r) && r.d) ? LOOSE : "") : elseM.length ? note(esc(mname), `${plural(elseM.length, "contest")} for ${esc(mname)} ${elseM.length === 1 ? "is" : "are"} on the list, in ${elseM.length === 1 ? "a ward or district" : "wards or districts"} other than yours: ${elseM.map(r => `<a href="${hrefRace(r)}">${esc(raceTitle(r))}</a>`).join("; ")}.`) : note(esc(mname), `No ${esc((ST.muni || []).includes(muniOf(mname)) ? MUNI1 : muniOf(mname) || "local")} contest for ${esc(mname)} ${onList(LWHO, " for November 3", m.c)}.`));
    let around = [];
    if (z.mo) {      // the place around the reader's own (the township a village lies in): its contests are on the same ballot
      const on = z.mon || placeName(mPk(z.mo)), both = `${esc(mname)} lies inside ${esc(on)}, and a voter here is a voter of both.`;
      around = D.races.filter(r => r.pk === mPk(z.mo) && LOCAL.includes(r.lv) && (!G(r) || G(r) === at("mcd", z.mo)));
      out.push(around.length ? level(esc(on), around, both) : note(esc(on), `${both} No ${esc(muniOf(on) || "local")} contest for ${esc(on)} ${onList(LWHO, " for November 3", m.c)}.`)); }
    const lostM = D.races.filter(r => (r.lv === "city" || r.lv === "township") && !G(r) && !r.gp && inC(r) && !muni.includes(r) && !around.includes(r));      // a place the map has, whose wards it has not, is known: its contests are listed only for those who live in it
    if (lostM.length) out.push(`<div class="bl-level"><h4>Places the map has no lines for</h4><p class="ynote">The map files have no lines for ${new Set(lostM.map(r => r.pk)).size === 1 ? "this place" : "these places"}, so this page cannot tell whether you live there. Your ${CO1}&rsquo;s sample ballot shows it.</p><div class="rlist">${lostM.map(r => raceRow(r, "", esc(raceWhere(r)))).join("")}</div></div>`);
    const nb = (z.sch || []).length - (z.ov || 0), split = nb > 1;      // the districts that share the precinct out; any after them lie over those, and a voter is in both
    (z.sch || []).forEach((sid, n) => { const rs = BYG["school:" + sid] || [], nm = (z.schn || {})[sid] || (SCHG[sid] ? placeName(SCHG[sid]) : sid);
      const sub = [n >= nb ? `This district lies over the other${nb > 1 ? "s" : ""} here, so a voter is in it as well.` : split ? (sid === z.s1 ? `Your ${UNIT} is split between ${esc(ST.schoolOne || "school district")}s; by the map your spot is in this one.` : `Your ${UNIT} is split between ${esc(ST.schoolOne || "school district")}s; this one reaches part of it. Only one of them is on your ballot.`) : "",
        rs.some(r => r.d) ? "Where board members are elected by district inside it, only your own district&rsquo;s seat is on your ballot; the map has no lines for those." : ""].filter(Boolean).join(" ");
      out.push(rs.length ? level(esc(nm), rs, sub) : note(esc(nm), `No school board contest for it ${onList(LWHO, " for November 3", m.c)}.${sub ? " " + sub : ""}`)); });
    const noLines = byLv("school").filter(r => !G(r) && inC(r));      // a district the map files have no lines for yet: it cannot be placed, so it is said, not hidden
    if (noLines.length) out.push(`<div class="bl-level"><h4>${esc(capital(ST.schoolOne || "school district"))}s the map has no lines for</h4><p class="ynote">The map files have no lines for ${noLines.length === 1 ? "this district" : "these districts"} yet, so this page cannot tell whether you live in ${noLines.length === 1 ? "it" : "one"}. Your ${CO1}&rsquo;s sample ballot shows it.</p><div class="rlist">${noLines.map(r => raceRow(r, "", esc(raceWhere(r)))).join("")}</div></div>`);
    const ownSeat = r => { const t = /-(\d{5})(?:-S)?$/.exec(r.id); return !t || t[1] === z.m; };      // a board seat for one city or township carries its code
    const hosp = D.races.filter(r => r.lv === "hospital" && z.ho && G(r) === at("hospital", z.ho) && ownSeat(r));
    out.push(level(esc(hosp.length ? raceWhere(hosp[0]) : "Hospital district"), hosp, hosp.some(r => r.s && !/^at large$/i.test(r.s) && !/-\d{5}(?:-S)?$/.test(r.id)) ? "A seat named for one part of the district is voted on only there." : ""));
    // a district no layer draws and the precinct names (r.q): 0, not this precinct's; 1, its district, the part that elects the seat not named;
    // 2, exactly its own; 3, the precinct is split between parts. null where the precinct says nothing of it: listed as before
    const saidOf = r => { if (!r.q || !z.x) return null; const i = r.q.indexOf(":"), k = r.q.slice(0, i), a = z.x[k + "_area"];
      if (!(k in z.x)) return null; if (z.x[k] !== r.q.slice(i + 1)) return 0;
      return !r.d ? 2 : !a ? 1 : !a.includes(r.d) ? 0 : a.length > 1 ? 3 : 2; };
    const loose = D.races.filter(r => inC(r) && ((r.lv === "hospital" && !G(r)) || (r.lv === "other" && !(r.pk && r.pk[0] === "M"))) && saidOf(r) !== 0);
    out.push(level("Other districts", loose, [loose.some(r => saidOf(r) === 1) ? `The map files say which district your ${UNIT} is in, not which part of it elects each seat: every seat of the district on the list is shown, and only your own part&rsquo;s is on your ballot.` : "",
      loose.some(r => saidOf(r) === 3) ? `Your ${UNIT} is split between parts of a district here; only your own part&rsquo;s seat is on your ballot.` : "",
      loose.some(r => saidOf(r) == null && G(r) !== at("county", z.gc || z.c)) ? ST.partNote : ""].filter(Boolean).join(" ")));      // a whole-county district is on every ballot in it
  }
  else if (m.c) {
    const county = byLv("county").filter(inC), soil = byLv("soil_water").filter(inC);
    out.push(county.length ? level(`${esc(cName(m.c))}`, county, districted(county) ? DIST_NOTE : "") : countyGap(m.c));
    const soilDistricts = new Set(soil.filter(r => r.pk).map(r => r.pk)).size + (soil.some(r => r.pk) && soil.some(r => !r.pk) ? 1 : 0);
    out.push(level(esc(LV.soil_water), soil, [districted(soil) ? DIST_NOTE : "", soilDistricts > 1 ? `More than one of these districts reaches the ${CO1}; only the one you live in is on your ballot.` : ""].filter(Boolean).join(" ")));
    if (ST.pickM) {      // the state's rows have city, town or township contests: the place the reader picked, or the ask
      const local = m.m ? D.races.filter(r => r.pk === m.m && LOCAL.includes(r.lv)) : [];
      if (m.m) out.push(local.length ? level(esc(placeName(m.m)), local, districted(local) ? DIST_NOTE : "") : note(esc(placeName(m.m)), `No ${esc(MUNI1)} contest for ${esc(placeName(m.m))} ${onList(LWHO, " for November 3", m.c)}.`));
      else out.push(note(esc(capital(MUNI1)), `Pick your ${esc(MUNI1)} above to add its contests.`));
    }
    if (ST.pickS) {
      const sch = m.s ? D.races.filter(r => r.pk === m.s) : [];
      if (m.s) out.push(sch.length ? level(esc(placeName(m.s)), sch, !OLDER && districted(sch) ? DIST_NOTE : "") : note(esc(placeName(m.s)), ST.schoolOne === "school district" ? `No school board contest for this district ${onList(WHO, " for November 3", m.c)}.` : `No contest for this school board ${onList(WHO, " for November 3", m.c)}.`));
      else out.push(note(esc(capital(ST.schoolOne)), `Pick your ${esc(ST.schoolOne)} above to add its contests.`));
    }
    const hosp = D.races.filter(r => (r.lv === "hospital" || (r.lv === "other" && !(r.pk && r.pk[0] === "M"))) && inC(r));      // a city's own board sits with the city
    out.push(level(ST.hasHosp ? (ST.hasOther ? "Hospital and other districts" : "Hospital districts") : "Other districts", hosp, ST.partNote));
  }
  const courts = byLv("court"), dc = courts.filter(r => r.k === "district_court");
  const appeals = courts.filter(r => r.k === "court_of_appeals" && r.d);      // appeals judges elected by district (Michigan): every district is listed, yours is on your ballot
  if (ST.local) {
    // the courts the whole state elects, the ones elected by a district the list does not tie to counties (yours is among
    // them), and the court contests the list files under the reader's county
    // (a located reader's precinct names its judicial district, so a court the map draws by district is placed by that, whatever the list ties it to;
    // a court drawn as one city is that city's; a court drawn as its county, a court of common pleas, is the county's like any contest filed under it)
    const drawn = r => !!z && /^judicial:/.test(r.g || "");
    const tied = courts.filter(r => localCourt(r) || drawn(r)), mine = tied.filter(r => z && /^judicial:/.test(r.g || "") ? r.g === "judicial:" + z.jd : z && /^mcd:/.test(r.g || "") ? r.g === "mcd:" + z.m : inC(r)), rest = courts.filter(r => !tied.includes(r)), APPEAL = /^(supreme_court|court_of_|appellate_court)/;
    const whole = rest.filter(r => !r.d), byApp = rest.filter(r => r.d && APPEAL.test(r.k)), byOther = rest.filter(r => r.d && !APPEAL.test(r.k));
    const noun = tied.length ? courtNoun(tied) : "", list = whole.concat(byApp, mine);
    const words = [!tied.length ? "" : !m.c ? `Pick your ${esc(ST.countyWord)} to add its ${noun}.`
        : mine.length ? "" : tied.every(drawn) ? `No race for ${noun} in the district your ${UNIT} is in ${onList(WHO)}; <a href="#courts">see every court race</a>.`
        : `No race for ${noun} on the list is filed under ${esc(cName(m.c))}; <a href="#courts">see every ${noun === "district court judges" ? "district court" : "court"} race</a>.`,
      byApp.length ? "Where a court is elected by district, only your own district&rsquo;s seats are on your ballot." : "",
      byOther.length ? `${plural(byOther.length, "more court race")} ${byOther.length === 1 ? "is" : "are"} elected by district, and the list does not say which counties each district covers: <a href="#courts">see every court race</a>.` : ""].filter(Boolean).join(" ");
    out.push(list.length ? level(list.every(isJudge) ? "Judges" : capital(courtNoun(list)), list, words) : words ? note("Judges", words) : "");
  }
  else out.push(level("Judges", courts.filter(r => r.k !== "district_court"),
    [appeals.length ? "The Court of Appeals is elected by appellate district; only your own district&rsquo;s seats are on your ballot." : "",
     dc.length ? `District court judges are elected by judicial district: <a href="#courts">see every district court race</a>.` : ""].filter(Boolean).join(" ")));
  const where = (z ? [new RegExp(`\\b${UNIT}\\b`, "i").test(z.pn) ? z.pn : `${capital(UNIT)} ${z.pn}`, cName(z.c), z.mn || "", z.mo ? z.mon || "" : "", ...(z.w || []).map(w => { const d = w.split("|")[1] || w, gw = ((BOOT.geo || {}).words || {}).ward;      // "Ward 2"; "Aldermanic District 4" where the files call it so
      return gw && /^District /.test(d) ? gw.replace(/ district$/i, "").replace(/\b[a-z]/g, c => c.toUpperCase()) + " " + d : d; }), ...(z.sch || []).map(i => (z.schn || {})[i] || i), m.hd && !ST.one ? `${ST.loD} ${m.hd}` : "", !ST.nest && sd ? `${ST.upD} ${sd}` : ""]
    : [m.c ? cName(m.c) : "", m.m ? placeName(m.m) : "", m.s ? placeName(m.s) : "", m.hd && !ST.one ? `${ST.loD} ${m.hd}` : "", !ST.nest && sd ? `${ST.upD} ${sd}` : ""]).filter(Boolean).map(esc).join(" &middot; ");
  return `<div class="bl-head"><h3>What&rsquo;s on your ballot</h3><p class="ynote">${where}. ${z ? `Exactly the contests of your ${UNIT}, in` : "In"} the order a${/^[AEIOU]/.test(ST.name) ? "n" : ""} ${NM} ballot runs, level by level${BOOT.links.us && ST.congressShort ? `, below <a href="../us/#state=${esc(ST.code)}">${ST.congressShort}</a> at the top` : ""}. Your ${CO1}&rsquo;s sample ballot is the authority on your exact ballot.</p></div>${out.join("")}`;
}
function mountYours(){
  const cty = $("#ycty"), mcd = $("#ymcd"), sch = $("#ysch"), hd = $("#yhd"), sdp = $("#ysd"), note = $("#ynote"), out = $("#yballot"), forgetB = $("#yforget"); if (!hd && !sdp && !cty) return;
  MINE = readMine();
  const save = () => {
    store.set(YKEY, JSON.stringify(MINE));
    if (MINE.hd || MINE.sd) store.set(SLD, JSON.stringify({u: upperOf(MINE), l: MINE.hd || "", from: MINE.loc ? "pin" : "pick"}));      // the same record of districts the state pages keep
  };
  const counties = Object.keys(D.counties).sort(byCounty);
  function fill(){
    if (cty) {
      cty.innerHTML = `<option value="">Your ${esc(ST.countyWord)}</option>` + counties.map(f => `<option value="${esc(f)}"${f === MINE.c ? " selected" : ""}>${esc(cName(f))}</option>`).join("");
      const ms = MINE.c ? placesIn("M", MINE.c) : [], ss = MINE.c ? placesIn("S", MINE.c) : [], first = ` (pick a ${esc(ST.countyWord)} first)`;
      if (mcd) { mcd.innerHTML = `<option value="">${MINE.c ? `Your ${esc(MUNI1)}` : esc(capital(MUNI1)) + first}</option>` + ms.map(([k, P]) => `<option value="${esc(k)}"${k === MINE.m ? " selected" : ""}>${esc(placeLabel(P))}</option>`).join(""); mcd.disabled = !MINE.c; }
      if (sch) { sch.innerHTML = `<option value="">${MINE.c ? `Your ${esc(ST.schoolOne)}` : esc(capital(ST.schoolOne)) + first}</option>` + ss.map(([k, P]) => `<option value="${esc(k)}"${k === MINE.s ? " selected" : ""}>${esc(P.n)}</option>`).join(""); sch.disabled = !MINE.c; }
    }
    if (hd) hd.innerHTML = `<option value="">Your ${esc(dWord("lower"))}</option>` + D.hds.map(d => `<option value="${esc(d)}"${d === MINE.hd ? " selected" : ""}>${esc(ST.loD)} ${esc(d)}${senateOf(d) ? ` (${UP} ${esc(senateOf(d))})` : ""}</option>`).join("");
    if (sdp) sdp.innerHTML = `<option value="">Your ${esc(dWord("upper"))}</option>` + D.sds.map(d => `<option value="${esc(d)}"${d === MINE.sd ? " selected" : ""}>${esc(ST.upD)} ${esc(d)}</option>`).join("");
  }
  function paint(){ out.innerHTML = ballotHTML(MINE); forgetB.hidden = !(MINE.c || MINE.hd || MINE.sd || MINE.m || MINE.s); const svg = $("#cmap"); if (svg) $$("path.cty", svg).forEach(p => p.classList.toggle("me", p.dataset.c === MINE.c)); }
  // a choice made by hand: the precinct found by location no longer stands, and where there is a map it shows what was picked
  const byHand = (kind, id) => { const had = !!MINE.z; delete MINE.z; note.textContent = had ? `You changed a choice by hand, so the ballot below is put together from your choices. Use your location again for your exact ${UNIT}.` : "";
    if (GEO_ON && window.GEOKIT) { GEOKIT.unpin(); GEOKIT.refresh(); if (kind && id) GEOKIT.show(kind, id); } };
  if (cty) {
    cty.addEventListener("change", () => { const had = MINE.z; MINE = {c: cty.value, hd: MINE.hd, ...(ST.nest ? {} : {sd: MINE.sd || ""}), m: "", s: "", loc: !!MINE.loc}; if (had) MINE.z = had; byHand("county", cty.value); save(); fill(); paint(); });
    if (mcd) mcd.addEventListener("change", () => { MINE.m = mcd.value; byHand("mcd", mcd.value.slice(1)); save(); paint(); });
    if (sch) sch.addEventListener("change", () => { MINE.s = sch.value; byHand("school", (placeByKey(sch.value) || {}).g || sch.value.slice(1)); save(); paint(); });
  }
  if (hd) hd.addEventListener("change", () => { MINE.hd = hd.value; byHand("house", hd.value); save(); paint(); });
  if (sdp) sdp.addEventListener("change", () => { MINE.sd = sdp.value; byHand("senate", sdp.value); save(); paint(); });
  forgetB.addEventListener("click", () => { MINE = {}; ["pin", "district", SLD, YKEY].forEach(k => store.del(k)); fill(); paint(); if (GEO_ON && window.GEOKIT) GEOKIT.forget(); note.textContent = "Forgotten. Your location and your choices are no longer kept on this device."; });
  // where the state has its map files: the precinct at the reader's spot, found on this device, and every district it is in
  const exact = (lon, lat, acc) => needKit().then(() => GEOKIT.locate(lon, lat, acc)).then(z => {
    if (!z) { note.textContent = `That spot isn't inside ${ST.name} on the map. Pick from the lists instead.`; return false; }
    MINE = {c: z.c, m: (D.places.M || {})[mKey(z.m)] ? mPk(z.m) : "", s: SCHG[z.s1 || z.sch[0]] || "", hd: ST.one ? "" : z.hd, ...(ST.nest ? {} : {sd: z.sd}), z, loc: true};
    save(); fill(); paint(); GEOKIT.refresh();
    note.textContent = `Worked out on this device; your location never leaves it. You are in ${new RegExp(`\\b${UNIT}\\b`, "i").test(z.pn) ? "" : UNIT + " "}${z.pn}, ${cName(z.c)}. Every district you are in is listed beside the map, and your ballot is below it.`;
    return true;
  });
  const rough = (lon, lat) => needKit().then(() => GEOKIT.rough(lon, lat)).then(h => {      // a rounded spot kept by the other pages: good for the county and the legislative districts only
    if (!h || !D.counties[h.c]) return false;
    MINE = {c: h.c, hd: ST.one ? "" : h.hd, ...(ST.nest ? {} : {sd: h.sd}), m: "", s: "", loc: true};
    save(); fill(); paint();
    note.textContent = `Placed from the rounded location this device already keeps (about half a mile): ${andList([cName(h.c), h.hd && !ST.one ? `${ST.loD} ${h.hd}` : ""].filter(Boolean))}. Near a line the guess can be off. Use your location for your exact ${UNIT} and ballot.`;
    return true;
  });
  const placeFrom = (lon, lat, how) => needLines().then(() => {
    const hit = placeAt(lon, lat);
    if (!hit.c && !hit.hd && !hit.sd) { note.textContent = `That spot isn't inside ${ST.name} on our map. Pick from the lists instead.`; return false; }
    const same = hit.c && hit.c === MINE.c;
    MINE = ST.local ? {c: hit.c || "", hd: ST.one ? "" : (hit.hd || ""), ...(ST.nest ? {} : {sd: hit.sd || ""}), m: same ? MINE.m : "", s: same ? MINE.s : "", loc: true} : {hd: ST.one ? "" : (hit.hd || ""), sd: ST.nest ? "" : (hit.sd || ""), loc: true};
    save(); fill(); paint();
    const more = [ST.pickM ? `your ${MUNI1}` : "", ST.pickS ? `your ${ST.schoolOne}` : ""].filter(Boolean);      // what the lines cannot tell: the reader picks those
    note.textContent = ST.local
      ? `${how} It looks like ${andList([hit.c ? cName(hit.c) : (ST.cLines ? `a spot outside the ${CO1} lines` : ""), hit.hd && !ST.one ? `${ST.loD} ${hit.hd}` : "", !ST.nest && hit.sd ? `${ST.upD} ${hit.sd}` : ""].filter(Boolean))}. Near a line the guess can be off.${more.length ? ` Now pick ${more.join(" and ")}.` : ""}`
      : `${how} It looks like ${[hit.hd && !ST.one ? `${ST.loD} ${hit.hd}` : "", !ST.nest && hit.sd ? `${ST.upD} ${hit.sd}` : ""].filter(Boolean).join(" and ") || "a spot outside the district lines"}, on the Census Bureau's ${LINES.vintage ? LINES.vintage.replace(/ Census Bureau.*$/, "") + " " : ""}lines. Near a line the guess can be off.`;
    return true;
  });
  $("#yloc").addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn't available in this browser. Pick from the lists instead."; return; }
    note.textContent = GEO_ON ? `Finding your ${UNIT}…` : ST.local ? `Finding your ${ST.cLines ? ST.countyWord + " and " : ""}district${twoPicks ? "s" : ""}…` : "Finding your districts…";
    navigator.geolocation.getCurrentPosition(pos => {
      const lat = pos.coords.latitude, lon = pos.coords.longitude;
      (GEO_ON ? exact(lon, lat, pos.coords.accuracy) : placeFrom(lon, lat, "Worked out on this device; your location never leaves it.")).then(ok => {
        if (ok) { store.set("pin", JSON.stringify({st: ST.code, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(pos.coords.accuracy || 0)})); store.set("state", ST.code); }      // rounded: about half a mile, the same kept pin the other pages use
      }, () => { note.textContent = GEO_ON ? "Couldn't load the map's lines. Check your connection, or pick from the lists." : "Couldn't load the district lines. Check your connection, or pick from the lists."; });
    }, () => { note.textContent = "Location wasn't shared. Pick from the lists instead."; }, GEO_ON ? {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000} : {timeout: 10000, maximumAge: 600000});
  });
  fill(); paint();
  /* arriving from "Insights on my location" (the bar at the top of every ballot page): the mark it left is followed once */
  try { const m = +sessionStorage.getItem("insights"); if (m) { sessionStorage.removeItem("insights"); if (Date.now() - m < 120000) setTimeout(() => { const y = $("#yloc"), s = $("#yours"); if (y) { if (s) s.scrollIntoView({block: "start"}); y.click(); } }, 0); } } catch (e) {}
  if (GEO_ON) needKit().then(() => { if ($("#gmapsec")) return GEOKIT.mount(); }).catch(() => { const s = $("#gside");
    if (s) s.innerHTML = `<p class="held">The map could not be loaded. Check your connection and open the page again; the lists above work without it.</p>`; });
  if (!MINE.c && !MINE.hd && !MINE.sd) {      // a rounded pin kept by the other pages of this site: place it here too
    try { const pj = JSON.parse(store.get("pin") || "null"); if (pj && pj.st === ST.code && isFinite(pj.lat) && isFinite(pj.lon)) (GEO_ON ? rough(pj.lon, pj.lat) : placeFrom(pj.lon, pj.lat, "Placed from the rounded location this device already keeps (about half a mile).")).catch(() => {}); } catch (e) {}
  }
}

/* ---------- pages ---------- */
const andList = a => a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
const commaAnd = a => a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + ", and " + a[a.length - 1];
const govTicket = () => D.races.some(r => r.k === "governor" && /lieutenant/i.test(r.o || ""));
function home(anchor){
  document.title = `On The Ballot: ${ST.name} · The Civic Archive`;
  const n = lv => D.races.filter(r => r.lv === lv).length;
  const local = D.races.filter(r => LOCAL.includes(r.lv)).length, cands = D.races.reduce((t, r) => t + general(r).length, 0);
  const leg = n("legislature"), courts = n("court"), sw = n("statewide"), counties = Object.keys(D.counties).sort(byCounty);
  const gov = govTicket(), govAny = D.races.some(r => r.k === "governor");
  const what = [!sw ? "" : govAny ? "the governor and the other statewide offices" : "the statewide offices", ST.unit === "seat" ? `${plural(leg, "seat")} in the Legislature` : `${plural(leg, "race")} for the Legislature`,
    courts ? "judges" : "", ST.local ? ST.localWhat : ""].filter(Boolean);
  const chip = (v, words, one) => `<div class="kchip"><b>${num(v)}</b><span>${v === 1 && one ? one : words}</span></div>`;
  // whether the ballot runs "party lines first, then nonpartisan" is read from the rows; where it does not, the page does not say so
  const partyFirst = D.races.every(r => (r.lv === "statewide" || r.lv === "legislature") === !!r.pt);
  const cards = counties.map(f => { const gaps = (GAPS.county[f] || []).length;
    return `<a class="scard2" href="#county=${esc(f)}"><b>${esc(cName(f))}</b><span>${COUNTS[f] ? plural(COUNTS[f], "contest") : "No contest on the list"}${gaps ? ` &middot; ${num(gaps)} not here yet` : ""}</span></a>`; }).join("");
  const gapCounties = Object.keys(GAPS.county).sort(byCounty), gapRaces = Object.keys(GAPS.race).length;
  const elsewhere = [gapCounties.length === 1 ? `Something of <a href="#county=${esc(gapCounties[0])}">${esc(cName(gapCounties[0]))}</a>&rsquo;s own is not here yet; its page says what and why.`
      : gapCounties.length ? `In ${num(gapCounties.length)} ${esc(ST.countyMany || "counties")} something of their own is not here yet, and each one&rsquo;s page says what and why: ${gapCounties.map(f => `<a href="#county=${esc(f)}">${esc(cShort(f))}</a>`).join(", ")}.` : "",
    gapRaces ? `${plural(gapRaces, "contest")} ${gapRaces === 1 ? "has" : "have"} something missing ${gapCounties.length ? "too" : "from the list"}; the contest&rsquo;s own page says what${gapRaces <= 6 ? `: ${Object.keys(GAPS.race).map(id => R[id]).filter(Boolean).map(r => `<a href="${hrefRace(r)}">${esc(raceTitle(r))}${raceWhere(r) ? `, ${esc(raceWhere(r))}` : ""}</a>`).join("; ")}` : ""}.` : ""].filter(Boolean).join(" ");
  $("#app").innerHTML = `<section class="bhero"><span class="eyebrow">On The Ballot &middot; ${NM}</span>
    <h1>Who&rsquo;s on <em>${NM}&rsquo;s</em> ballot</h1>
    <p class="lede">${ST.lede || "Every state race"} on the November 3, 2026 ballot, from ${ST.fromWho} official lists of candidates: ${commaAnd(what)}.</p>
    <span class="countdown"><i></i>${esc(dayWords())}</span>
    <div class="kchips">${sw ? chip(sw, "statewide races", "statewide race") : ""}${chip(leg, "legislative races", "legislative race")}${courts ? chip(courts, ST.unit === "seat" ? "judges&rsquo; seats" : "judicial races", ST.unit === "seat" ? "" : "judicial race") : ""}${ST.local ? chip(local, `${CO1} and local contests`, `${CO1} or local contest`) : ""}${ST.noGeneral ? "" : chip(cands, "candidates on the lists")}</div>
    ${PRIVACY}${NOTICE}</section>
  ${yoursHTML()}
  <section class="bsec" id="levels"><h2>Level by level</h2><p class="sub">${partyFirst ? "The ballot runs from the top down: offices elected on party lines first, then the nonpartisan ones." : "The ballot runs from the top down, level by level. Each race&rsquo;s page says whether it is elected on party lines."}</p>
    <div class="lvgrid">
      <a class="lvcard" href="#statewide"><b>Statewide offices</b><span>${sw ? `${plural(sw, "race")}: ${gov ? "the governor and lieutenant governor, elected together, and the offices the whole state elects" : "the offices the whole state elects"}` : "No statewide office is on the lists loaded here"}</span><span class="go">Open &rsaquo;</span></a>
      <a class="lvcard" href="#legislature"><b>The Legislature</b><span>${ST.one ? plural(Object.keys(LEG.upper).length, "district race") : `${plural(Object.keys(LEG.upper).length, `${UP} race`)} and ${plural(Object.keys(LEG.lower).length, `${LO} race`)}`}, district by district on the map</span><span class="go">Open &rsaquo;</span></a>
      ${courts ? `<a class="lvcard" href="#courts"><b>Judges</b><span>${plural(courts, ST.unit)}${ST.courts.length ? ` ${ST.unit === "seat" ? "on" : "for"} ${andList(ST.courts)}` : ""}</span><span class="go">Open &rsaquo;</span></a>` : ""}
      ${ST.local ? `<a class="lvcard" href="#counties"><b>${esc(capital(COS))} and local offices</b><span>${plural(local, "contest")} ${ST.localCard}</span><span class="go">Open &rsaquo;</span></a>`
        : D.notes || GAPS.state.length ? `<a class="lvcard" href="#localnotes"><b>County and local races</b><span>No county or local contest is shown for ${NM}. The notes kept with the state&rsquo;s lists say why.</span><span class="go">Read why &rsaquo;</span></a>`
        : `<a class="lvcard" href="${ST.localN ? "../states/#local" : "../states/"}"><b>County and local races</b><span>${ST.localElse} County, city, school board and other local races for ${NM} are not loaded yet; the state&rsquo;s own list here holds the state offices.</span><span class="go">${ST.localN ? "See the states that have them" : "Every state loaded"} &rsaquo;</span></a>`}
    </div></section>
  ${ST.local ? `<section class="bsec" id="counties"><h2>${esc(capital(CO1))} by ${esc(CO1)}</h2><p class="sub">${GEO_ON ? ST.countySub.replace(/Pick .*$/, `Pick one from the list, or on <a href="#yours">the map above</a>.`) : ST.countySub}</p>
    ${noteBox("local_calendar")}${ST.cLines && !GEO_ON ? `<div class="cgrid"><figure class="cmapwrap" style="margin:0"><svg class="cmap" id="cmap" role="group" aria-label="Map of ${NM}&rsquo;s ${esc(COS)}"></svg></figure>
      <div class="sgrid">${cards}</div></div>` : `<div class="sgrid wide">${cards}</div>`}${noteKeys().filter(k => k !== "local_calendar").map(noteBox).join("")}${gapBox(GAPS.state, true)}${elsewhere ? `<p class="ynote">${elsewhere}</p>` : ""}</section>`
    : D.notes || GAPS.state.length ? `<section class="bsec" id="localnotes"><h2>County and local races</h2><p class="sub">No county or local contest is shown for ${NM}. The notes kept with the state&rsquo;s lists say why.</p>${noteKeys().map(noteBox).join("")}${gapBox(GAPS.state, true)}</section>` : ""}
  ${BOOT.links.us && ST.congress ? `<section class="bsec" id="congress"><h2>Congress</h2><p class="sub">${ST.congress}</p></section>` : ""}
  ${sourcesHTML()}`;
  mountYours(); if (ST.local && ST.cLines && !GEO_ON) mountCountyMap("cmap", MINE.c ? [MINE.c] : []);
  if (anchor && $("#" + anchor)) { const t = $("#" + anchor); if (t.tagName === "DETAILS") t.open = true; t.scrollIntoView(); }      // "Sources" in the menu opens the fold it goes to
}
function statewidePage(){
  document.title = `Statewide offices · On The Ballot: ${ST.name}`;
  const rs = D.races.filter(r => r.lv === "statewide"), npR = rs.filter(r => !r.pt), np = [...new Set(npR.map(r => r.o))];
  const lede = `The offices the whole state elects${np.length ? "" : ", on party lines"}.${np.length ? ` All but ${npR.length === 1 ? "one" : num(npR.length)} of these races are elected on party lines; the ${esc(andList(np))} ${np.length === 1 && npR.length === 1 ? "is" : "are"} on the nonpartisan ballot.` : ""}${govTicket() ? " The governor and lieutenant governor are elected together, on one line of the ballot." : ""}${ST.primLine ? " " + ST.primLine : ""}`;
  $("#app").innerHTML = `${crumbs(["<span>Statewide offices</span>"])}
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${NM} &middot; ${esc(fmtDate(D.election))}</span><h1>Statewide offices</h1>
    <p class="lede">${lede}${rs.some(r => r.d) ? " Some boards are elected by district: only your own district&rsquo;s seat is on your ballot." : ""}</p>${PRIVACY}${NOTICE}</section>
  <section class="bsec"><div class="rlist">${rs.map(r => raceRow(r, "", holderSmall(r) + (!general(r).length && r.note ? " " + esc(r.note) : ""))).join("") || `<p class="muted">No statewide race is on the list.</p>`}</div></section>`;
}
function legislaturePage(){
  document.title = `The Legislature · On The Ballot: ${ST.name}`;
  const up = Object.keys(LEG.upper).sort(byDistrict), lo = Object.keys(LEG.lower).sort(byDistrict), unit = key => (ST.multi || {})[key] ? "race" : "seat";
  const lr = D.races.filter(r => r.lv === "legislature"), lpt = lr.filter(r => r.pt).length;
  const how = lpt === lr.length ? "elected on party lines" : lpt ? "most elected on party lines" : "elected on a nonpartisan ballot: no party is printed beside the names";
  const count = ST.one ? plural(up.length, `district ${unit("upper")}`) : `${plural(up.length, `${UP} ${unit("upper")}`)} and ${plural(lo.length, `${LO} ${unit("lower")}`)}`;
  $("#app").innerHTML = `${crumbs(["<span>The Legislature</span>"])}
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${NM} &middot; ${esc(fmtDate(D.election))}</span><h1>The Legislature</h1>
    <p class="lede">${count} on the November ballot, ${how}.${ST.legNote ? " " + esc(ST.legNote) : ""}${ST.primLeg ? " " + ST.primLeg : ""}</p>${PRIVACY}${NOTICE}</section>
  ${legMapHTML()}
  <section class="bsec" id="senate"><h2>${UP}</h2><div class="rlist">${up.map(d => raceRow(LEG.upper[d], `District ${esc(d)}`, holderSmall(LEG.upper[d]))).join("") || `<p class="muted">No ${UP} race is on the list.</p>`}</div></section>
  ${ST.one ? "" : `<section class="bsec" id="house"><h2>${LO}</h2><div class="rlist">${lo.map(d => raceRow(LEG.lower[d], `District ${esc(d)}`, holderSmall(LEG.lower[d]))).join("") || `<p class="muted">No ${LO} race is on the list.</p>`}</div></section>`}`;
  mountLegMap();
}
function courtsPage(){
  document.title = `Judges · On The Ballot: ${ST.name}`;
  const rs = D.races.filter(r => r.lv === "court"), K = k => rs.filter(r => r.k === k || r.k === k + "_retention");
  const dist = {}; K("district_court").forEach(r => (dist[r.d || r.j || "?"] = dist[r.d || r.j || "?"] || []).push(r));
  const other = rs.filter(r => !["supreme_court", "court_of_appeals", "district_court"].includes(r.k.replace("_retention", "")));
  const pt = rs.filter(r => r.pt).length, ret = rs.filter(r => /_retention$/.test(r.k)).length;
  const on = pt === rs.length ? "on party lines" : pt ? "partly on party lines" : "on the nonpartisan part of the ballot";
  const sec = (title, list, sub) => list.length ? `<section class="bsec"><h2>${title}</h2>${sub ? `<p class="sub">${sub}</p>` : ""}<div class="rlist">${list.map(r => raceRow(r)).join("")}</div></section>` : "";
  const cn = list => { const s = [...new Set(list.flatMap(r => r.c || []))].sort((a, b) => cName(a).localeCompare(cName(b))); return s.length ? `<p class="dist-counties">${s.map(f => `<a href="#county=${esc(f)}">${esc(cShort(f))}</a>`).join(", ")}</p>` : ""; };
  const whole = [["supreme_court", "the Supreme Court"], ["court_of_appeals", "the Court of Appeals"]].filter(([k]) => K(k).length && K(k).every(r => !r.d)).map(([, w]) => w);
  const coaByDistrict = K("court_of_appeals").some(r => r.d);
  const how = [whole.length ? `${andList(whole)} statewide` : "", coaByDistrict ? "the Court of Appeals by appellate district" : "", K("district_court").length ? "each district court judge by judicial district" : ""].filter(Boolean);
  const dcCounties = K("district_court").some(r => (r.c || []).length);
  $("#app").innerHTML = `${crumbs(["<span>Judges</span>"])}
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${NM} &middot; ${esc(fmtDate(D.election))}</span><h1>Judges</h1>
    <p class="lede">${ret === rs.length ? `${NM}&rsquo;s voters decide whether each judge on the list stays in office, a yes or no vote on the nonpartisan part of the ballot${how.length ? ": " + how.join(", ") : ""}` : `${NM} elects its judges ${on}${how.length ? ": " + how.join(", ") : ""}${ret ? `; ${plural(ret, "judge")} face${ret === 1 ? "s" : ""} a yes or no retention vote` : ""}`}. ${plural(rs.length, ST.unit)} on the list.</p>${PRIVACY}${NOTICE}</section>
  ${sec("Supreme Court", K("supreme_court"))}${sec("Court of Appeals", K("court_of_appeals"), coaByDistrict ? "Voters elect the judges of their own appellate district. Where one contest fills more than one seat, its note says how many." : "")}
  ${Object.keys(dist).length ? `<section class="bsec"><h2>District courts</h2><p class="sub">Voters elect the judges of their own judicial district.${dcCounties ? " The counties each district covers, as the list files its seats, are named under it." : ""}</p>
    ${Object.keys(dist).sort(byDistrict).map(d => `<div class="jgroup"><h3>${esc(dist[d][0].j || judicialName(d))}<span>${plural(dist[d].length, "seat")}</span></h3>${cn(dist[d])}<div class="rlist">${dist[d].map(r => raceRow(r)).join("")}</div></div>`).join("")}</section>` : ""}
  ${[...new Set(other.map(baseKind))].map(k => { const list = other.filter(r => baseKind(r) === k), titles = [...new Set(list.map(r => r.o))];      // a court this page has no heading for: its own office title is the heading
    return sec(esc(titles.length === 1 ? titles[0] : capital(k.replace(/_/g, " "))), list, list.some(r => (r.c || []).length) ? "Elected by the district or circuit each contest names; its counties are named on the contest&rsquo;s page." : ""); }).join("")}`;
}
function countyPage(f){
  if (!D.counties[f]) { home(); return; }
  document.title = `${cName(f)} · On The Ballot: ${ST.name}`;
  const here = D.races.filter(r => (r.c || []).includes(f));
  const county = here.filter(r => r.lv === "county"), judges = here.filter(localCourt);
  const soilNamed = here.some(r => r.lv === "soil_water" && r.pk);      // conservation districts with ids of their own are named, like any other district
  const soil = soilNamed ? [] : here.filter(r => r.lv === "soil_water");
  const groups = {};
  here.filter(r => ["city", "township", "school", "hospital", "other"].includes(r.lv) || (soilNamed && r.lv === "soil_water")).forEach(r => {
    const key = r.pk || "J" + (r.j || r.id);
    (groups[key] = groups[key] || {key, races: []}).races.push(r);
  });
  Object.keys(GAPS.place).forEach(pk => { const P = placeByKey(pk); if (P && (P.c || []).includes(f) && !groups[pk]) groups[pk] = {key: pk, races: []}; });      // a place with something missing and no contest shown
  const placeIn = g => g.races.length ? placeOf(g.races[0]) : placeByKey(g.key);
  const secOf = g => { const k = g.key[0], P = placeIn(g);
    if (g.races.some(r => r.lv === "soil_water")) return "soil";
    if (k === "M") return g.races.some(r => r.lv === "township") || (P && P.t === "township") ? "township" : "city";      // the races' level decides, not the place's name
    if (k === "S") return "school"; if (k === "H") return "hospital"; return g.races.some(r => r.lv === "hospital") ? "hospital" : g.races.some(r => r.lv === "school") ? "school" : "other"; };
  const bySec = {soil: [], city: [], township: [], school: [], hospital: [], other: []};
  Object.values(groups).forEach(g => { g.name = g.key[0] === "J" ? raceWhere(g.races[0]) || "Other" : placeName(g.key); bySec[secOf(g)].push(g); });
  const also = g => { const P = g.key[0] !== "J" ? placeIn(g) : null, cs = ((P && P.c) || (g.races[0] || {}).c || []).filter(x => x !== f); return cs.length ? `also in ${cs.map(x => esc(cName(x))).join(", ")}` : ""; };
  const group = g => `<div class="jgroup" data-name="${esc(g.name.toLowerCase())}"><h3>${esc(g.name)}<span>${plural(g.races.length, "contest")}${also(g) ? " &middot; " + also(g) : ""}</span></h3>${g.races.length ? `<div class="rlist">${g.races.map(r => raceRow(r)).join("")}</div>` : ""}${gapBox(GAPS.place[g.key])}</div>`;
  // what the places of a section are called is read from their own names: Cities; Cities and towns; Towns
  const cityW = muniWords(bySec.city.map(g => g.name), "city"), townW = muniWords(bySec.township.map(g => g.name), "township").filter(w => w === "town" || w === "township");
  const townWords = townW.length ? townW : ["township"];
  const SEC = [["soil", esc(LV.soil_water)], ["city", capital(andList(cityW.map(w => MUNIS[w])))], ["township", capital(andList(townWords.map(w => MUNIS[w])))], ["school", esc(LV.school)],
    ["hospital", "Hospital districts"], ["other", "Other districts"]];
  const DIST_NOTE = "Where an office is elected by district or ward, only the voters of that district or ward vote for it.";
  const plainSec = (id, title, list, sub) => list.length ? `<section class="bsec grp" id="${id}"><h2>${title}</h2>${sub ? `<p class="sub">${sub}</p>` : ""}<div class="rlist">${list.map(r => raceRow(r)).join("")}</div></section>` : "";
  const localRows = here.filter(r => LOCAL.includes(r.lv)), localN = localRows.length, onLines = localRows.filter(r => r.pt).length;
  const boards = ST.schoolOne !== "school district";      // contests reach a county "in 14 school districts", but "for 1 school board"
  const reach = [bySec.city.length ? plural(bySec.city.length, orList(cityW), andList(cityW.map(w => MUNIS[w]))) : "",
    bySec.township.length ? plural(bySec.township.length, orList(townWords), andList(townWords.map(w => MUNIS[w]))) : "", bySec.school.length && !boards ? plural(bySec.school.length, ST.schoolOne) : ""].filter(Boolean);
  const reachWords = (reach.length ? `, in ${andList(reach)}` : "") + (bySec.school.length && boards ? `${reach.length ? "," : ""} for ${plural(bySec.school.length, ST.schoolOne)}` : "");
  // on party lines or not is read from the rows of this county, never assumed
  const lines = !onLines ? (localN === 1 ? "It is a nonpartisan office: no party is printed beside the names." : "Every one of them is a nonpartisan office: no party is printed beside the names.")
    : onLines === localN ? (localN === 1 ? "It is elected on party lines: the party each candidate filed under is shown beside the name." : "Every one of them is elected on party lines: the party each candidate filed under is shown beside the name.")
    : `${onLines === 1 ? "One of them is" : `${num(onLines)} of them are`} elected on party lines, with the party each candidate filed under beside the name; the other ${localN - onLines === 1 ? "one is a nonpartisan office" : `${num(localN - onLines)} are nonpartisan offices`}, with no party printed.`;
  const noun = judges.length ? courtNoun(judges) : "", courtNames = [...new Set(judges.map(r => r.j || ""))];
  const here1 = ownKind(f);      // county; city for Baltimore city; parish in Louisiana
  const courtSub = courtNames.length === 1 && /judicial district/i.test(courtNames[0]) && judges.every(r => baseKind(r) === "district_court") ? `Elected by the whole judicial district this ${here1} belongs to.`
    : judges.every(r => (r.c || []).length === 1) ? `Elected by the voters of this ${here1}.`      // a court of the county's own (Oklahoma's associate district judge, Washington's county district court)
    : `Each is elected by the voters of the district or circuit it names; where that reaches beyond this ${here1}, the others are named with it.`;
  // one court whose seats' titles name it (Minnesota's "Judge, 4th District Court"): a plain list; otherwise each district or circuit under its own name
  const courtSec = !judges.length ? "" : courtNames.length === 1 && judges.every(r => /\d/.test(r.o)) ? plainSec("judges", capital(noun), judges, courtSub)
    : `<section class="bsec grp" id="judges"><h2>${capital(noun)}</h2><p class="sub">${courtSub}</p>${courtNames.map(j => { const list = judges.filter(r => (r.j || "") === j), cs = [...new Set(list.flatMap(r => r.c || []))].filter(x => x !== f);
        return `<div class="jgroup"><h3>${esc(j || "Court")}<span>${plural(list.length, "contest")}${cs.length ? ` &middot; also in ${cs.map(x => esc(cName(x))).join(", ")}` : ""}</span></h3><div class="rlist">${list.map(r => raceRow(r)).join("")}</div></div>`; }).join("")}</section>`;
  const about = noteKeys().map(noteBox).join("") + gapBox(GAPS.state, true, `Not here yet for ${NM} as a whole, and why`);
  const findWords = orList([...(ST.muni || []), ST.pickS ? ST.schoolOne : ""].filter(Boolean)) || "district";
  const elsewhere = [D.races.some(r => r.lv === "statewide") ? `<a href="#statewide">statewide offices</a>` : "", `<a href="#legislature">the Legislature</a>`, D.races.some(r => r.lv === "court") ? `<a href="#courts">judges</a>` : ""].filter(Boolean);
  $("#app").innerHTML = `${crumbs([`<a href="#counties">${esc(capital(ST.countyMany || "counties"))}</a>`, `<span>${esc(cName(f))}</span>`])}
  <section class="bhero${ST.cLines ? " withloc" : ""}"><div><span class="eyebrow">On The Ballot &middot; ${NM} &middot; ${esc(fmtDate(D.election))}</span><h1>${esc(cName(f))}</h1>
    <p class="lede">${localN ? `${plural(localN, `${CO1} or local contest`)} on the November 3 ballot ${localN === 1 ? "reaches" : "reach"} ${esc(cName(f))}${reachWords}. ${lines}` : (GAPS.county[f] || []).length ? `${esc(cName(f))}&rsquo;s own list is not loaded yet, so its ${CO1} contests are not shown: what is missing, and why, is set out below${judges.length ? `; ${plural(judges.length, "court contest")} that reach${judges.length === 1 ? "es" : ""} it ${judges.length === 1 ? "is" : "are"} shown` : ""}.`
      : `No ${CO1} or local contest reaching ${esc(cName(f))} is on the ${LWHO} lists${judges.length ? `; ${plural(judges.length, "court contest")} ${judges.length === 1 ? "is" : "are"}` : ""}.`}</p>
    ${BOOT.links.county_page ? `<p class="holder">Who holds the county offices today: <a href="../../${ST.lc}/counties/#c=${esc(f)}">${esc(cName(f))} on the record side</a>.</p>` : ""}
    ${GEO_ON ? `<p class="holder"><a href="#map=${encodeURIComponent("county:" + f)}">See ${esc(cName(f))} on the map</a>, with its ${esc(andList((BOOT.geo.muni && BOOT.geo.muni.length ? BOOT.geo.muni : ["city", "township"]).map(w => MUNIS[w] || w).concat("districts")))}, down to their streets.</p>` : ""}
    ${PRIVACY}</div>${ST.cLines ? locatorHTML() : ""}</section>
  ${plainSec("county", `${capital(ownKind(f))} offices`, county, districted(county) ? DIST_NOTE : "")}
  ${plainSec("soil", esc(LV.soil_water), soil, districted(soil) ? DIST_NOTE : "")}
  ${Object.values(groups).length > 3 ? `<div class="filterbar"><input type="search" id="cfilter" placeholder="Find a ${esc(findWords)}" aria-label="Find a ${esc(findWords)}"></div><p class="ynote" id="cnone" hidden>Nothing here matches.</p>` : ""}
  ${SEC.map(([k, title]) => bySec[k].length ? `<section class="bsec grp" id="g-${k}"><h2>${title}</h2>${(k === "city" || (!OLDER && k !== "soil")) && bySec[k].some(g => districted(g.races)) ? `<p class="sub">${DIST_NOTE}</p>` : k === "soil" && bySec[k].length > 1 ? `<p class="sub">More than one of these districts reaches ${esc(cName(f))}; a voter&rsquo;s ballot carries only the district the voter lives in.</p>` : ""}${bySec[k].sort((a, b) => a.name.localeCompare(b.name)).map(group).join("")}</section>` : "").join("")}
  ${courtSec}
  ${gapBox(GAPS.county[f])}${about ? `<details class="lmore"${localN ? "" : " open"}><summary>How ${NM}&rsquo;s ${esc(CO1)} and local lists were read, and what they leave out</summary>${about}</details>` : ""}
  <p class="fnote">${ST.everyBallot} ${andList(elsewhere)}, or put your whole ballot together under <a href="#yours">your ballot</a>.</p>`;
  const inp = $("#cfilter");
  if (inp) inp.addEventListener("input", () => {
    const q = inp.value.trim().toLowerCase(); let shown = 0;
    $$(".jgroup[data-name]").forEach(g => { const on = !q || g.dataset.name.includes(q); g.hidden = !on; if (on) shown++; });
    $$("section.grp").forEach(s => { const gs = $$(".jgroup[data-name]", s); if (gs.length) s.hidden = gs.every(g => g.hidden); else s.hidden = !!q; });
    $("#cnone").hidden = shown > 0 || !q;
  });
  if (ST.cLines) mountCountyMap("locsvg", [f], "loccap");
}
const districted = list => list.some(r => r.d || (OLDER && /\b(ward|district)\s+\w+/i.test(r.o || "")));      // under the local conventions the ward or district is its own field
function howTheyGotHere(r, prim){      // Minnesota's words as they were; elsewhere the dates and kinds of the fields this race has
  if (ST.code === "MN") return "Where two or more people filed for the same party, the party&rsquo;s primary on August 11 chose who went on to November. Everyone who filed is listed; the one on the November ballot is marked.";
  const dates = [...new Set(prim.map(k => ((r.el[k] || [])[0] || {}).date).filter(Boolean))].sort().map(shortDate);
  const party = prim.some(k => k !== "primary-NP"), runoff = prim.some(k => /^runoff/.test(k));
  const two = (r.hs || []).length > 1 || /\b(two|2) seats\b|\belect 2\b/i.test(r.note || "");
  return `Where more people ran${party ? " for a party" : ""} than it could send on, the ${runoff ? "primary and its runoff" : party ? "party&rsquo;s primary" : "primary"} on ${esc(andList(dates))} chose who went on to November. Everyone on that ballot is listed; ${two ? "those" : "the one"} on the November ballot ${two ? "are" : "is"} marked.`;
}
/* <extras> */
const SBOX = (who, what, tail) => `<div class="srcitem"><b>${who}</b>: ${what}<small>${tail}</small></div>`;
const T_FACT = `<span class="tag fact">Fact</span>`, T_SEC = `<span class="tag analysis">Secondary</span>`, tagNote = words => `<span class="tag note">${words}</span>`;
const outLink = (u, words) => `<a href="${esc(u)}" target="_blank" rel="noopener nofollow">${words || esc(hostOf(u))}</a>`;
const ROSTER_FACTS = () => ({h: SBOX("Open States", `its roster of ${NM}&rsquo;s legislators and statewide officials: a sitting member&rsquo;s birth date, the terms they have served and their legislature&rsquo;s own portrait`, `${T_FACT} ${outLink("https://github.com/openstates/people", "github.com/openstates/people")} &middot; public domain (CC0)`)});
const GEO_SRC = () => (ST.geoSrc || []).map(s => ({h: SBOX(esc(s.a), esc(s.t), `${T_FACT}${s.u ? ` ${outLink(s.u)}` : ""} &middot; the lines of the map under &ldquo;your ballot&rdquo;; its notice is shown with the map`)}));
const VOTE_SRC = () => (ST.votesSrc || []).map(s => ({h: SBOX(esc(s.a), esc(s.t), `${/not itself an official record/i.test(s.k || "") ? T_SEC : T_FACT}${s.u ? ` ${outLink(s.u)}` : ""} &middot; how a place has voted; its notice is shown with the counts`)}));
function pollSources(list){      // the polls and the markets of these races, as sources: [[race, its polls entry, its markets]]
  const out = []; if (!list.length) return out;
  const day = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}); };
  if (list.some(x => x[1])) out.push({h: SBOX("American Association for Public Opinion Research", "the Transparency Initiative&rsquo;s members, who publish how each poll was done: only their polls are shown", `${T_FACT} ${outLink("https://aapor.org/standards-and-ethics/transparency-initiative/", "aapor.org/standards-and-ethics/transparency-initiative")}`)});
  list.forEach(([r, P0, O]) => { const of = list.length > 1 ? `, ${esc(raceTitle(r))}` : "";
    ((P0 || {}).polls || []).forEach(p => out.push({h: SBOX(esc(p.pollster), `its poll ending ${esc(fmtDate(p.end))}${of}`, `${T_FACT} ${outLink(p.url)}${p.checked ? ` &middot; checked against the release ${esc(fmtDate(p.checked))}` : ""}`)}));
    const L = (P0 || {}).left_out; if (L && L.found_in) out.push({h: SBOX("Wikipedia", `its list of this race&rsquo;s polls${of}, used only to find them and to count those by pollsters outside the Initiative`, `${T_SEC} ${outLink(L.found_in)}${L.checked ? ` &middot; checked ${esc(fmtDate(L.checked))}` : ""}`)});
    [["polymarket", "Polymarket"], ["kalshi", "Kalshi"]].forEach(([k, name]) => { const M = (O || {})[k]; if (M && (M.rows || []).length) out.push({h: SBOX(name, `the market&rsquo;s own public data${M.title ? `: &ldquo;${esc(M.title)}&rdquo;` : ""}${of}`, `${tagNote("Bets, not facts")}${day(O.at) ? ` read ${esc(day(O.at))} &middot;` : ""} the way to the market is under &ldquo;What bettors are paying&rdquo;, behind a notice`)}); }); });
  return out;
}
function moreSources(r, src){      // what a race's page draws on beyond its lists: who its candidates are, the parties' own pages, polls and markets, the map
  const g = general(r), pages = new Map(), parties = new Map();
  const put = (c, who, url, kind, what) => { const x = pages.get(url) || {who, url, kind, by: new Map()}; pages.set(url, x); if (!x.by.has(c.n)) x.by.set(c.n, new Set()); x.by.get(c.n).add(what); };
  if (g.some(c => { const p = facts(c, r); return p.dob || (p.off || []).length || p.ps === "State roster"; })) srcAdd(src, "people", ROSTER_FACTS());
  g.forEach(c => { const p = facts(c, r);
    if (p.fb) put(c, p.fb[2], p.fb[3], p.fb[4], "birth year");
    (p.fo || []).forEach(o => put(c, o[3], o[4], o[5], "public offices held"));
    if (p.op) put(c, p.op[1], p.op[0], "official", "the government&rsquo;s own page about them");
    if (!r.pt) { (p.pp || []).forEach(o => put(c, o[3], o[4], o[5], "an earlier run or office under a party label"));
      (p.en || []).concat(p.nom || []).forEach(([party, unit, url]) => { const x = parties.get(url) || {party, unit, url, names: new Set()}; parties.set(url, x); x.names.add(c.n); }); }
    const own = !r.pt && p.ow, photo = p.ps === "Campaign";
    if (p.web || p.iss || photo || own) {
      const what = [p.web ? "its website" : "", p.iss ? "the issue headings on its issues page" : "", photo ? "the photograph" : "", own ? "the candidate&rsquo;s own words" : ""].filter(Boolean).join(", ");
      const links = [p.web ? outLink(p.web) : "", p.iss && p.iss[0] !== p.web ? outLink(p.iss[0], "the issues page") : "", photo && p.pu ? outLink(p.pu, "the photograph") : "", own && p.ow[1] !== p.web ? outLink(p.ow[1], "the page quoted") : ""].filter(Boolean).join(" &middot; ");
      srcAdd(src, "own", {h: SBOX(`${esc(c.n)}&rsquo;s campaign`, what, `${tagNote("The campaign&rsquo;s own")} ${links}${p.web ? ` &middot; ${p.wf ? "found on the open web and checked against the race it names" : `the address filed with the ${WHO} list`}` : ""}`)}); } });
  [...pages.values()].forEach(x => srcAdd(src, "web", {h: SBOX(esc(x.who), [...x.by].map(([n, f]) => `${esc(n)}: ${[...f].join(" and ")}`).join("; "), `${x.kind === "official" ? T_FACT : x.kind === "campaign" ? tagNote("The campaign&rsquo;s own site") : T_SEC} ${outLink(x.url)}`)}));
  if (parties.size) { [...parties.values()].forEach(x => srcAdd(src, "other", {h: SBOX(esc(x.unit), `${esc(x.party)}: its own page, which names ${[...x.names].map(esc).join(", ")}`, `${tagNote("The party&rsquo;s own page")} ${outLink(x.url)}`)})); src.other.label = "The parties&rsquo; own pages"; }
  if (BOOT.mk && wideRace(r)) pollSources([[r, (BOOT.polls || {})[r.id], (BOOT.odds || {})[r.id]]]).forEach(x => srcAdd(src, "polls", x));
  if (!r.pt && BOOT.votes) VOTE_SRC().forEach(x => srcAdd(src, "results", x));
  if (GEO_ON && r.g) GEO_SRC().forEach(x => srcAdd(src, "maps", x));
}
const GWORD = (kind, usual) => { const w = ((BOOT.geo || {}).words || {})[kind]; return w ? "this " + w.replace(/^county\s+/i, "") : usual; };      // what the map's files call it, where that is not the usual word
const SHAPE_WORD = {county: "the county", mcd: "this place", ward: GWORD("ward", "this ward"), com: GWORD("com", "this commissioner district"), house: "this district", senate: "this district", judicial: GWORD("judicial", "this judicial district"), swcd: "this district", hospital: "this hospital district", park: "this park district", school: "this school district"};
/* </extras> */
function racePage(id){
  const r = R[id]; if (!r) { document.title = `Not found · On The Ballot: ${ST.name}`; $("#app").innerHTML = `${crumbs(["<span>Not found</span>"])}<div class="notebox">That race is not on the lists this page holds. <a href="#">Back to ${NM}</a></div>`; return; }
  if (BOOT.who && !FACTS) {      // who the candidates are comes in a file of its own, fetched the first time a race is opened
    $("#app").innerHTML = `<p class="loading muted">Loading the candidates&hellip;</p>`;
    needFacts().then(() => { if (location.hash.slice(1, 6) === "race=") route(); });
    return;
  }
  document.title = `${raceTitle(r)}${r.lv === "legislature" || r.lv === "statewide" ? "" : ", " + raceWhere(r)} · On The Ballot: ${ST.name}`;
  const back = r.lv === "statewide" ? `<a href="#statewide">Statewide offices</a>` : r.lv === "legislature" ? `<a href="#legislature">The Legislature</a>` : r.lv === "court" ? `<a href="#courts">Judges</a>`
    : (r.c || []).length ? `<a href="#county=${esc(r.c[0])}">${esc(cName(r.c[0]))}</a>` : `<a href="#counties">${esc(capital(COS))}</a>`;
  const prim = primaries(r);
  const everyone = Object.values(r.el || {}).flat(), listIds = [...new Set(everyone.map(c => c.src).filter(Boolean))], placeSrc = (placeOf(r) || {}).src;
  const where = raceWhere(r), cs = (r.c || []).map(f => `<a href="#county=${esc(f)}">${esc(cName(f))}</a>`).join(", ");
  const loc = r.lv === "legislature" || (ST.cLines && (r.c || []).length && r.lv !== "statewide");
  const gaps = GAPS.race[r.id] || [], named = candGap(r);      // what the loader said is missing from this contest, and why
  // where this contest comes from, kind by kind: the lists its candidates were read from, the source of the place's name,
  // the roster where a seat's holder or a sitting member is named, and the lines where a map is drawn
  const src = {};
  listIds.map(s => D.sources[s]).filter(Boolean).forEach(s => srcAdd(src, srcKindOf(s), srcRow(s)));
  if (placeSrc && D.sources[placeSrc] && !listIds.includes(placeSrc)) srcAdd(src, "places", srcRow(D.sources[placeSrc]));
  if (r.h || everyone.some(c => c.m)) rosterRows().forEach(x => srcAdd(src, "holders", x));
  if (loc) srcAdd(src, "maps", {h: LINES_SRC()});
  moreSources(r, src);
  const gk = (r.g || "").split(":")[0], onMap = GEO_ON && r.g && gk !== "state" ? `<p class="holder"><a href="#map=${encodeURIComponent(r.g)}">See ${SHAPE_WORD[gk] || "this place"} on the map</a>, down to its streets.</p>`
    : GEO_ON && r.gp ? `<p class="holder"><a href="#map=${encodeURIComponent(r.gp)}">See ${esc(r.j || "this place")} on the map</a>; the map has no lines for the part of it that elects this.</p>` : "";
  $("#app").innerHTML = `${crumbs([back, `<span>${esc(raceTitle(r))}</span>`])}
  <section class="bhero${loc ? " withloc" : ""}"><div><span class="eyebrow">${esc(levelWords(r))} &middot; ${esc(fmtDate(r.date))}</span><h1>${esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</h1>
    <p class="holder">${esc(where)}${where !== ST.name && cs && !((r.c || []).length === 1 && (r.lv === "county" || where === cName(r.c[0]))) ? ` &middot; ${cs}` : ""}. ${r.pt ? "Elected on party lines: the party each candidate filed under is printed on the ballot." : "A nonpartisan office: no party is printed beside the names."}</p>
    ${r.lv === "legislature" || r.lv === "statewide" ? `<p class="holder">${seatWords(r, true)}</p>` : ""}
    ${r.sp ? `<p class="holder">A special election${r.note ? "" : ", for the rest of a term"}.</p>` : ""}${r.note && !gaps.some(g => g.r === r.note) ? `<p class="holder">${esc(r.note)}</p>` : ""}${onMap}${privacyFor(r)}</div>${loc ? locatorHTML() : ""}</section>
  ${tabsFor(r)}
  ${general(r).length ? arena(r) : named ? "" : `<div class="notebox">${EMPTY ? EMPTY + "." : `No candidate for this office is on the ${whoOf(r)} list for November 3.`}</div>`}${gapBox(gaps)}
  ${whoHTML(r)}${leanHTML(r)}
  ${prim.length ? `<section class="bsec"><h2>How they got here</h2><p class="sub">${howTheyGotHere(r, prim)}</p>${prim.map(k => field(r, k)).join("")}</section>`
    : r.pt || !ST.npLine ? "" : `<p class="fnote">${ST.npLine}</p>`}
  ${sourceFold("Where this comes from", src)}`;
  if (r.lv === "legislature") mountLegLocator(r); else if (loc) mountCountyMap("locsvg", r.c || [], "loccap");
  if ($("#rtabs")) { wireTabs(); quietMarkets(r); }
  mountVotes(r);
}
function sourcesHTML(){      // every source the state's lists were read from, kind by kind, each kind under the rules of the page that are about it
  const parts = {};
  Object.values(D.sources).forEach(s => srcAdd(parts, srcKindOf(s), srcRow(s)));
  Object.values(parts).forEach(p => { const offices = new Set(p.items.map(x => x.a));      // many sources from a few offices (a county's sample ballots, precinct by precinct): filed under the office
    if (p.items.length > 12 && offices.size > 1 && offices.size <= p.items.length / 3) p.items.forEach(x => { x.g = x.a; }); });
  if (!parts.holders) srcAdd(parts, "holders", {h: ROSTER_SRC});
  srcAdd(parts, "maps", {h: LINES_SRC()});
  // what the state has beyond its lists: the map's files, the past results, who the candidates are, the parties' own pages, polls and markets
  if (GEO_ON) GEO_SRC().forEach(x => srcAdd(parts, "maps", x));
  if (BOOT.votes) VOTE_SRC().forEach(x => srcAdd(parts, "results", x));
  if (BOOT.who) { const N = ST.whoN || {}, n = k => N[k] || 0, sites = n("websites filed") + n("websites found");
    if (n("roster portraits")) srcAdd(parts, "people", ROSTER_FACTS());
    if (sites) srcAdd(parts, "own", {h: SBOX("The campaigns&rsquo; own websites", `${num(sites)} of them: ${num(n("websites filed"))} as filed with the ${WHO} list, ${num(n("websites found"))} found on the open web and checked against the race each names${n("issue pages") ? `; the issue headings of ${num(n("issue pages"))}` : ""}${n("campaign photos") ? `; the photographs of ${num(n("campaign photos"))} candidates` : ""}. Each is linked on its candidate&rsquo;s race page`, tagNote("The campaigns&rsquo; own")), n: sites});
    if (n("birth years found") + n("offices found")) srcAdd(parts, "web", {h: SBOX("Pages found on the open web", `governments&rsquo; own pages, campaign sites, Wikipedia and named news organizations that state a birth year (${num(n("birth years found"))}) or a public office held (${num(n("offices found"))})${n("earlier runs or offices under a party label") ? `, or an earlier run or office under a party label (${num(n("earlier runs or offices under a party label"))})` : ""}. Each is named and linked on its race&rsquo;s page`, tagNote("Each labelled by its kind of source"))});
    if (ST.partyN) { srcAdd(parts, "other", {h: SBOX("The parties&rsquo; own pages", `${num(ST.partyN)} pages on which a party or one of its units publishes its endorsements; each is linked on the race page of the candidate it names`, tagNote("The parties&rsquo; own")), n: ST.partyN});
      if (parts.other.items.length === 1) parts.other.label = "The parties&rsquo; own pages"; } }
  if (BOOT.mk) pollSources(D.races.filter(wideRace).map(r => [r, (BOOT.polls || {})[r.id], (BOOT.odds || {})[r.id]]).filter(x => x[1] || x[2])).forEach(x => srcAdd(parts, "polls", x));
  (ST.methods || []).forEach(([kind, words]) => { const p = parts[kind] = parts[kind] || {items: []}; (p.notes = p.notes || []).push(words); });
  return sourceFold("Sources and methods", parts, "sources");
}

/* ---------- the address decides the page ---------- */
function route(){
  if (!D) return;
  let h = ""; try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { h = location.hash.slice(1); }
  if (mapOff) { mapOff.abort(); mapOff = null; }
  if (window.GEOKIT) GEOKIT.unmount();      // the map of "your ballot" goes with the page it was on
  if (h.startsWith("map=") && GEO_ON) {      // #map=ward:00694|Ward 2: the home page, with that shape on the map; #map=house: with that kind of line drawn
    const i = h.indexOf(":"); home("gmapsec");
    needKit().then(() => GEOKIT.show(i > 4 ? h.slice(4, i) : h.slice(4), i > 4 ? h.slice(i + 1) : "")).catch(() => {});
    return;
  }
  if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("county=") && ST.local) countyPage(countyKey(h.slice(7)));
  else if (h === "statewide") statewidePage();
  else if (h === "legislature") legislaturePage();
  else if (h === "courts" && D.races.some(r => r.lv === "court")) courtsPage();
  else { home(h); if (!h) scrollTo(0, 0); return; }
  scrollTo(0, 0);
}
addEventListener("hashchange", () => { route(); const a = $("#app"); if (a && !/^(yours|counties|sources|levels|congress|localnotes)$|^map=/.test(location.hash.slice(1))) a.focus({preventScroll: true}); });
fetch(BOOT.data).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status)))).then(d => { D = d; index(); route(); },
  () => { $("#app").innerHTML = `<div class="notebox" style="margin-top:30px">The candidate lists could not be loaded. Check your connection and open the page again.</div>`; });
</script>
</body>
</html>
"""


STATES_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>On The Ballot: the states · The Civic Archive</title>
<meta name="description" content="State races on the November 3, 2026 ballot, state by state, from each state's own official candidate lists: __NAMES__.__LOCAL_DESC__">
<meta name="version" content="__VERSION__">
<meta name="theme-color" content="#0C0E12">
<link rel="icon" href="../../us/icon-192.png" type="image/png">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light";var mo=localStorage.getItem("motion");if(mo==="off"||(!mo&&matchMedia("(prefers-reduced-motion: reduce)").matches))document.documentElement.classList.add("calm")}catch(e){document.documentElement.dataset.theme="light"}</script>
<style>
@font-face{font-family:"Instrument Serif";font-style:normal;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Regular.ttf) format("truetype")}
@font-face{font-family:"Instrument Serif";font-style:italic;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Italic.ttf) format("truetype")}
@font-face{font-family:"Instrument Sans";font-style:normal;font-weight:400 700;font-display:swap;src:url(fonts/InstrumentSans-Variable.ttf) format("truetype")}
</style>
<style>__CSS__</style>
<style>__BALLOT_CSS__</style>
<style>
/* the chooser: which states' state ballot pages are open */
html,body{overflow-x:hidden}
.bhero h1{overflow-wrap:break-word}
.chgrid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:22px;align-items:start;margin-top:14px}
@media (max-width:860px){.chgrid{grid-template-columns:1fr}}
.chmap{border:1px solid var(--line);background:var(--surface);border-radius:20px;padding:10px}
.chmap .usballot{margin-top:0}
.chmap .usballot a:focus-visible path{stroke:var(--ink);stroke-width:2.2}
.chmap .usballot path.off{cursor:default}.chmap .usballot path.off:hover{filter:none}
.chmap .usballot text{font:700 12px var(--sans);fill:#fff;pointer-events:none;text-anchor:middle}
.chlist{display:grid;gap:10px}
.chlist .scard2 b{font-family:var(--serif);font-weight:400;font-size:24px;line-height:1.1}
.chlist .scard2 span.lv{display:block;margin-top:4px}
.chnote{font-size:13.5px;color:var(--muted);margin:14px 0 0;max-width:80ch;line-height:1.45}
.privacy{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;line-height:1.45;color:var(--muted);border:1px solid var(--line);border-radius:14px;padding:10px 14px;background:var(--surface);margin:16px 0 0;max-width:82ch}
.privacy svg{flex:none;width:18px;height:18px;margin-top:1px;fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.mkey{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--muted);margin-top:8px}
.mkey i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:6px;border:1px solid var(--line-strong)}
/* the states whose lists reach the counties too: a gold outline on the map, a second pill on the card, a section of their own */
.chmap .usballot path.loc{stroke:var(--gold);stroke-width:2.6;stroke-linejoin:round}
.mkey i.loc{background:var(--accent);border:2px solid var(--gold)}
.scard2 .pill2.loc{margin-left:6px;background:rgba(184,134,11,.14);color:var(--gold)}
#local,#states{scroll-margin-top:84px}
#local .scard2 b{font-family:var(--serif);font-weight:400;font-size:22px;line-height:1.1}
#local .scard2 span.lv{display:block;margin-top:4px}
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../" title="On The Ballot: every level" aria-label="Back to the On The Ballot door"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16v8H4z"/><path d="M8 12V5h8v7"/><path d="M10 8.6l1.5 1.5 2.8-2.9"/></svg><span>On The Ballot</span></a>
    <a class="brand" href="./" aria-label="On The Ballot: the states"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections"><a href="../us/">Congress</a><a href="#states">The states</a>__LOCAL_NAV__</nav>
    <div class="tools">
      <button class="mtog" id="motion" aria-pressed="true" title="Page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="app" class="bwrap">
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; The states</span>
    <h1>Choose a <em>state</em></h1>
    <p class="lede">State races on the November 3, 2026 ballot, from each state&rsquo;s own official lists of candidates: the governor and the other statewide offices, the legislature, and the judges where the list holds them. __COUNT__ so far, loaded one state at a time.__LOCAL_LEDE__</p>
    <div class="kchips">__CHIPS__</div>
    <p class="privacy"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg><span>__PRIVACY__</span></p>
  </section>
  <section class="bsec" id="states"><h2>Open now</h2><p class="sub">Filled states have their state ballot page open. Pick one on the map or from the list.__LOCAL_SUB__</p>
    <div class="chgrid"><figure class="chmap" style="margin:0"><svg class="usballot" viewBox="0 0 975 610" role="group" aria-label="Map of the states; the states with a state ballot page are filled">
      <defs><pattern id="bhatch" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--surface)"/><rect width="2.5" height="7" fill="var(--accent)" opacity=".35"/></pattern></defs>
      __MAP__</svg>
      <div class="mkey"><span><i style="background:var(--accent)"></i>State ballot page open</span>__LOCAL_KEY__<span><i style="background:repeating-linear-gradient(45deg,var(--surface) 0 3px,rgba(15,122,106,.35) 3px 5px)"></i>Not loaded yet</span></div></figure>
      <div class="chlist">__CARDS__</div></div>
    <p class="chnote">__LOCAL_NOTE__ The U.S. Senate and House races for every state are on <a href="../us/">the Congress pages</a>.</p>
  </section>
  __LOCAL_SECTION__
</main>
<footer class="bwrap bfoot">
  <p>On The Ballot, from The Civic Archive v__VERSION__. Each state&rsquo;s candidates come only from its own election office&rsquo;s official lists; the sources are named on each state&rsquo;s page. __FOOT_SHOWN__ Built __GENERATED__.</p>
  <p><a href="../">On The Ballot: every level</a> &middot; <a href="../us/">Congress</a> &middot; <a href="../../">The Civic Archive front door</a></p>
</footer>
<script>
const $ = s => document.querySelector(s);
const store = {set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
const calm = () => document.documentElement.classList.contains("calm");
const showMotion = () => $("#motion").setAttribute("aria-pressed", calm() ? "false" : "true");
showMotion();
$("#motion").addEventListener("click", () => { const off = !calm(); document.documentElement.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });
</script>
</body>
</html>
"""


def html_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def state_summary(con, code):
    """What the chooser's card says about a state: its races by level and its November candidates, counted from the database."""
    ph = ",".join("?" * len(LOCAL_LEVELS))
    by = dict(con.execute("SELECT level, COUNT(*) FROM sl_races WHERE state = ? GROUP BY level", (code,)).fetchall())
    state_races = sum(n for lv, n in by.items() if lv not in LOCAL_LEVELS)
    local_races = sum(n for lv, n in by.items() if lv in LOCAL_LEVELS)
    cands = con.execute(f"SELECT COUNT(*) FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ? AND c.election = 'general' AND r.level NOT IN ({ph})",
                        (code, *LOCAL_LEVELS)).fetchone()[0]
    lcands = con.execute(f"SELECT COUNT(*) FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ? AND c.election = 'general' AND r.level IN ({ph})",
                         (code, *LOCAL_LEVELS)).fetchone()[0]
    agencies = [a for (a,) in con.execute("SELECT DISTINCT agency FROM sl_sources WHERE state = ? AND kind = 'official candidate list'", (code,))]
    partial = len(agencies) > 1 and all(re.search(r"\bCounty\b", a or "") for a in agencies)
    reached = set()      # the counties the state's county and local contests reach, from the rows' own county lists
    for (cids,) in con.execute(f"SELECT county_ids FROM sl_races WHERE state = ? AND level IN ({ph})", (code, *LOCAL_LEVELS)):
        reached.update(county_list(cids, ()))
    # what a county is called there, from the names of its county rows: parishes in Louisiana, counties nearly everywhere
    kinds = Counter(county_kind(county_names(n)[1] or "County") for (n,) in
                    con.execute("SELECT name FROM sl_places WHERE kind = 'county' AND source_id LIKE ?", (code.lower() + "-%",)))
    unit = "county" if not kinds or kinds.get("county") else kinds.most_common(1)[0][0]
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    rich = any(has(t) and con.execute(f"SELECT 1 FROM {t} WHERE race_id LIKE ? LIMIT 1", (f"2026-{code}-%",)).fetchone() for t in WHO_TABLES)      # its cards show more than the list holds
    return {"code": code, "name": place(code)["name"], "by": by, "state_races": state_races, "local_races": local_races, "cands": cands, "lcands": lcands,
            "partial": partial, "counties": len(reached), "unit": unit, "rich": rich}


def write_chooser(root, summaries, css, bcss, version):
    """site/dev/ballot/states/index.html: the states whose state ballot page exists, on a map and as cards, and which of
    them have their county and local races too (a gold outline on the map, a second pill on the card, and a section of
    their own, #local, that the ballot door's County and city card opens). All of it is counted from the database."""
    out_dir = os.path.join(root, "states")
    paths = {k: v for k, v in state_paths(os.path.join(HERE, "us_states_albers.json")).items()}
    open_ = {s["code"]: s for s in summaries}
    local = sorted((s for s in summaries if s["local_races"]), key=lambda s: s["name"])
    marks = []
    for with_local in (False, True):      # the outlined states are drawn last, so a neighbour's edge does not cover the outline
        for code, shape in sorted(paths.items()):
            s = open_.get(code)
            if bool(s and s["local_races"]) != with_local:
                continue
            title = html_esc(shape.get("name") or code)
            if s and s["local_races"]:
                marks.append(f'<a href="../{code.lower()}/" aria-label="{title}: state ballot page, with county and local races"><path class="on loc" d="{shape["d"]}">'
                             f'<title>{title}: open, with county and local races</title></path></a>')
            elif s:
                marks.append(f'<a href="../{code.lower()}/" aria-label="{title}: state ballot page"><path class="on" d="{shape["d"]}"><title>{title}: open</title></path></a>')
            else:
                marks.append(f'<path class="off" d="{shape["d"]}"><title>{title}: not loaded yet</title></path>')
    for code, shape in sorted(paths.items()):      # the open states' codes on the map, where their outline gives room
        if code in open_ and shape.get("bbox"):
            x0, y0, x1, y1 = shape["bbox"]
            marks.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{(y0 + y1) / 2 + 4:.1f}">{code}</text>')
    levels = lambda s: ", ".join(w for w, on in (("statewide offices", s["by"].get("statewide")), ("the Legislature", s["by"].get("legislature")),
                                                 ("judges", s["by"].get("court")), ("county and local races", s["local_races"])) if on)
    cards = []
    for s_ in sorted(summaries, key=lambda x: x["name"]):
        more = f"; and {s_['local_races']:,} county and local contests" if s_["local_races"] else ""
        nov = ("the November list is not loaded yet: the primaries are shown" if not s_["cands"]
               else f"{s_['cands']:,} candidates on the county lists loaded so far" if s_["partial"] else f"{s_['cands']:,} candidates on the November list")
        cards.append(f'<a class="scard2" href="../{s_["code"].lower()}/"><b>{html_esc(s_["name"])}</b><span class="lv">{s_["state_races"]:,} state '
                     f'race{"s" if s_["state_races"] != 1 else ""}, {nov}{more}</span>'
                     f'<span class="lv">{html_esc(levels(s_))}</span><span class="pill2{"" if s_["cands"] and not s_["partial"] else " no"}">'
                     f'{"Open" if s_["cands"] and not s_["partial"] else "Open, still filling in"}</span>'
                     + ('<span class="pill2 loc">County and local races too</span>' if s_["local_races"] else "") + '</a>')
    cards = "".join(cards)
    n, nl = len(summaries), len(local)
    chips = (f'<div class="kchip"><b>{n}</b><span>{"state" if n == 1 else "states"} open</span></div>'
             f'<div class="kchip"><b>{sum(s["state_races"] for s in summaries):,}</b><span>state races</span></div>'
             f'<div class="kchip"><b>{sum(s["cands"] for s in summaries):,}</b><span>candidates on the lists</span></div>')
    words = {"__LOCAL_DESC__": "", "__LOCAL_NAV__": "", "__LOCAL_LEDE__": "", "__LOCAL_SUB__": "", "__LOCAL_KEY__": "", "__LOCAL_SECTION__": "",
             "__LOCAL_NOTE__": "County and local races are not loaded for any state yet."}
    if local:      # how many states have their county and local races, which, and how to reach them: all counted here
        races, cands_l, counties = sum(s["local_races"] for s in local), sum(s["lcands"] for s in local), sum(s["counties"] for s in local)
        some = f"{number_word(nl)} of them" if nl < n else ("all of them" if n > 1 else "it")
        names = and_list([s["name"] for s in local])
        level_words = (("county", "county offices"), ("city", "city and town offices"), ("township", "township offices"), ("school", "school boards"),
                       ("soil_water", "conservation districts"), ("hospital", "hospital districts"), ("other", "other local districts"))
        kinds = and_list([w for lv, w in level_words if any(s["by"].get(lv) for s in local)])      # the levels the loaded states' rows hold
        chips += (f'<div class="kchip"><b>{nl}</b><span>{"state" if nl == 1 else "states"} with county and local races</span></div>'
                  f'<div class="kchip"><b>{races:,}</b><span>county and local contests</span></div>')
        local_cards = "".join(
            f'<a class="scard2" href="../{s["code"].lower()}/#counties"><b>{html_esc(s["name"])}</b>'
            f'<span class="lv">{s["local_races"]:,} county and local contest{"s" if s["local_races"] != 1 else ""} reaching {s["counties"]:,} '
            f'{s["unit"] if s["counties"] == 1 else county_kind_plural(s["unit"])}</span><span class="lv">{s["lcands"]:,} candidate{"s" if s["lcands"] != 1 else ""} on the lists</span>'
            f'<span class="pill2">Open its {county_kind_plural(s["unit"])}</span></a>' for s in local)
        units = and_list([county_kind_plural(u) for u, _n in Counter(s["unit"] for s in local).most_common()])      # counties; counties and parishes
        named = f": {html_esc(names)}" if nl <= 8 else ""      # a long list of names is the #local section's job
        words.update({
            "__LOCAL_DESC__": f" County and local races too in {some}{named}.",
            "__LOCAL_NAV__": '<a href="#local">Counties and cities</a>',
            "__LOCAL_LEDE__": f" {some.capitalize()} {'has' if nl == 1 else 'have'} {'its' if nl == 1 else 'their'} county and local races too.",
            "__LOCAL_SUB__": f' States outlined in gold have their county and local races too: <a href="#local">see {"it" if nl == 1 else f"all {number_word(nl)}"}</a>.',
            "__LOCAL_KEY__": '<span><i class="loc"></i>County and local races too</span>',
            "__LOCAL_NOTE__": (f'County and local races are loaded for {number_word(nl)} of the {number_word(n)} state{"s" if n != 1 else ""} here so far '
                               f'(<a href="#local">{html_esc(names) if nl <= 8 else "see which"}</a>).' if nl < n else
                               f'County and local races are loaded for {"every state" if n > 1 else "the state"} here (<a href="#local">see {"them" if n > 1 else "it"}</a>).'),
            "__LOCAL_SECTION__": (
                f'<section class="bsec" id="local"><h2>County and local races</h2><p class="sub">{html_esc(kinds[:1].upper() + kinds[1:])} '
                f'on the November 3 ballot, where a state&rsquo;s official lists reach them: '
                f'{number_word(nl)} state{"s" if nl != 1 else ""} so far, {races:,} contests reaching {counties:,} {units}, {cands_l:,} candidates. '
                f'Each state&rsquo;s page says which local offices are on this ballot, what was read and what is not there yet.</p>'
                f'<div class="sgrid">{local_cards}</div></section>')})
    # what is shown about a candidate: the list alone for most states; more, each with its source, where a state has it
    rich = [s["name"] for s in sorted(summaries, key=lambda s: s["name"]) if s.get("rich")]
    plain = "Only the name, office and party each candidate filed under are shown."
    words["__PRIVACY__"] = (plain if not rich else
                            f"For most states only the name, office and party each candidate filed under are shown. {html_esc(and_list(rich))}&rsquo;s "
                            f"page{'s' if len(rich) > 1 else ''} also show{'' if len(rich) > 1 else 's'}, for most offices, a photo, an age, offices held and a campaign "
                            "website, each with its source.") + " Addresses and contact details in the states&rsquo; files are never read."
    words["__FOOT_SHOWN__"] = ("No photos, no money, no scores or ratings of any person." if not rich else
                               "No money, no scores or ratings of any person; where a state&rsquo;s page shows more than its list holds, each fact is named with its source.")
    page = STATES_PAGE.replace("__CSS__", css).replace("__BALLOT_CSS__", bcss).replace("__MAP__", "\n      ".join(marks)).replace("__CARDS__", cards)
    for key, value in words.items():
        page = page.replace(key, value)
    page = page.replace("__CHIPS__", chips).replace("__COUNT__", f"{number_word(n).capitalize()} state{'s' if n != 1 else ''}")
    page = page.replace("__NAMES__", html_esc(and_list([s["name"] for s in sorted(summaries, key=lambda s: s["name"])])))
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    import page_extras      # "Take a break" in the header, and the "Insights on my location" bar every ballot page carries
    page = page_extras.add(page, root="../../", ballot="../", here="states")
    write_if_changed(os.path.join(out_dir, "index.html"), page)
    page_extras.write_where(root)      # the states with a page of their own, for the bar
    copy_fonts(out_dir)
    return os.path.join(out_dir, "index.html")


def build_state(code, db, out, site_root, parts, changelog, version):
    """One state's page, its data and its lines."""
    css, bcss, clog, geo_js, fold, markets = parts
    lc = code.lower()
    out_dir = os.path.dirname(os.path.abspath(out))
    lines = lines_for(code)
    data, st, warn, n_cand, X = build(db, code, lines, out_dir)
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    write_if_changed(os.path.join(out_dir, "data", f"{lc}.json"), body)
    data_v = hashlib.sha1(body.encode("utf-8")).hexdigest()[:10]
    lines_v = lines_file(os.path.join(out_dir, "data", "districts.json"), code, st["local"])
    copy_fonts(out_dir)
    record = os.path.exists(os.path.join(site_root, lc, "index.html"))
    boot = {"data": f"data/{lc}.json?v={data_v}", "lines": f"data/districts.json?v={lines_v}", "changelog": changelog,
            "links": {"state": record, "county_page": os.path.exists(os.path.join(site_root, lc, "counties", "index.html")),
                      "us": os.path.exists(os.path.join(site_root, "ballot", "us", "index.html"))},
            "st": {k: v for k, v in st.items() if k not in ("desc", "foot", "nav")}}
    # what the state has beyond its lists, each in a file of its own that a page fetches only when it needs it
    who_body = votes = geo = None
    if X["who"]:      # who the candidates are: fetched by a race's page
        who_body = json.dumps({"r": X["who"], "parties": X["who_info"]["parties"]}, ensure_ascii=False, separators=(",", ":"))
        write_if_changed(os.path.join(out_dir, "data", "who.json"), who_body)
        boot["who"] = f"data/who.json?v={hashlib.sha1(who_body.encode('utf-8')).hexdigest()[:10]}"
    if X["votes"]:      # how each place has voted: a race's page fetches the file of its own kind of place
        votes = votes_files(code, out_dir, X["geo"])
        if votes:
            boot["votes"] = {k: v for k, v in votes.items() if not k.startswith("_")}
            boot["st"]["votesSrc"] = votes["_src"]
    if X["geo"]:      # the map: its files are fetched as the view needs them
        geo = geo_files(code, out_dir, X["geo"])
        boot["geo"] = {k: v for k, v in geo.items() if not k.startswith("_")}
        # the districts the precincts name and no layer draws, where a contest on the list is in one: [property, the files' word for it, 1 where they name its parts too]
        used = sorted({r["q"].split(":", 1)[0] for r in data["races"] if r.get("q")})
        if used:
            boot["geo"]["says"] = [[k, X["geo"]["said"][k]["word"], 1 if X["geo"]["said"][k]["area"] else 0] for k in used]
    for key in ("polls", "odds"):
        if X[key]:
            boot[key] = X[key]
    if X["markets"]:
        boot["mk"] = 1
        if X["held"]:      # a market lists these races and the page holds it back: it must not say of them that none does
            boot["mkHeld"] = X["held"]
        # a race the whole state votes on that is not filed with the statewide offices (a supreme court seat) and has a
        # poll or a market to show: its page gets the same tabs
        level = {r["id"]: r["lv"] for r in data["races"]}
        also = sorted(k for k in set(X["polls"]) | set(X["odds"]) if level.get(k) != "statewide")
        if also:
            boot["mkAlso"] = also
    has_extras = bool(X["who"] or X["votes"] or X["geo"] or X["markets"])
    page = page_for(has_extras).replace("__CSS__", css).replace("__BALLOT_CSS__", bcss).replace("__CHANGELOG__", clog).replace("__GEO__", geo_js)
    page = page.replace("__SOURCEFOLD__", fold).replace("__MARKETS__", markets if X["markets"] else "")
    page = page.replace("__NAME__", html_esc(st["name"])).replace("__DESC__", html_esc(st["desc"])).replace("__NAV__", st["nav"])
    page = page.replace("__FOOT__", html_esc(st["foot"]).replace("&amp;rsquo;", "&rsquo;"))
    page = page.replace("__RECORD__", f' &middot; <a href="../../{lc}/">{html_esc(st["name"])}&rsquo;s Legislature on the record side</a>' if record else "")
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    import page_extras      # "Take a break" in the header, and the "Insights on my location" bar every ballot page carries
    page = page_extras.add(page, root="../../", ballot="../", here=lc)
    write_if_changed(os.path.abspath(out), page)

    by_level = defaultdict(int)
    for r in data["races"]:
        by_level[r["lv"]] += 1
    prim = sum(len(v) for r in data["races"] for k, v in r["el"].items() if k != "general")
    shell = len(page.encode("utf-8"))
    print(f"{st['name']}: wrote {os.path.relpath(os.path.abspath(out), HERE)}: shell {shell / 1e3:,.0f} KB, data/{lc}.json {len(body.encode('utf-8')) / 1e3:,.0f} KB")
    print(f"  {len(data['races']):,} races: " + ", ".join(f"{lv} {by_level[lv]:,}" for lv in LEVELS if by_level[lv]))
    print(f"  {n_cand:,} candidate rows ({prim:,} in primaries); "
          + (", ".join(f"places {k} {len(v):,}" for k, v in data["places"].items() if v) + f"; {len(data['counties'])} counties; " if st["local"] else "no county or local races; ")
          + f"{len(data['links'])} record links; districts nest: {'yes' if data['nest'] else 'no'}")
    if st["local"]:      # what the county pages carry: the contests, the counties they reach, and what the loader said about the lists
        local_races = [r for r in data["races"] if r["lv"] in LOCAL_LEVELS]
        reached = {f for r in local_races for f in r.get("c", [])}
        gaps = Counter(g["sc"] for g in data.get("gaps", []))
        print(f"  county and local: {len(local_races):,} contests reaching {len(reached)} of {len(data['counties'])} counties, "
              f"{sum(len(r['el'].get('general', [])) for r in local_races):,} November candidates; "
              f"{sum(1 for r in local_races if r['pt']):,} on party lines, {sum(1 for r in local_races if not r['pt']):,} nonpartisan; "
              f"county lines {'yes' if st.get('cLines') else 'no (the page lists the counties without a map)'}; "
              f"notes {', '.join(sorted(data.get('notes', {}))) or 'none'}; gaps " + (", ".join(f"{k} {v}" for k, v in sorted(gaps.items())) or "none"))
    print(f"  links: state side {'yes' if boot['links']['state'] else 'no'}, county record pages {'yes' if boot['links']['county_page'] else 'no'}, "
          f"Congress ballot {'yes' if boot['links']['us'] else 'no'}")
    kb = lambda n: f"{n / 1e3:,.0f} KB"
    if geo:      # what a phone fetches, and when
        idx = X["geo"]["index"]
        size = {L["kind"]: L.get("bytes", 0) for L in idx.get("layers") or []}
        cs = sorted(c.get("bytes", 0) for c in idx.get("counties") or [])
        matched = sum(1 for r in data["races"] if r.get("g"))
        print(f"  map: {geo['_files']:,} files in geo/ ({geo['_bytes'] / 1e6:,.1f} MB in all; {geo['_copied']:,} written this time). When the map opens: its script "
              f"{kb(geo['_kit'])}, the reader {kb(os.path.getsize(os.path.join(X['geo']['root'], 'reader.js')))}, index {kb(geo['_index'])}, the state's outline "
              f"{kb(size.get('state', 0))} and the county lines {kb(size.get('county', 0))}. A layer's file when its lines are first drawn far out: "
              + ", ".join(f"{k} {kb(v)}" for k, v in size.items() if k not in ("state", "county"))
              + f". Zoomed in: a county's precinct file, {kb(cs[0])} to {kb(cs[-1])} (half are under {kb(cs[len(cs) // 2])}), and a school district's own lines, about "
              f"{kb((idx.get('school') or {}).get('bytes', 0) / max(1, len((idx.get('school') or {}).get('ids') or [1])))} each.")
        print(f"  map: {matched:,} of {len(data['races']):,} races name the shape that draws their place; polling places: {boot['geo']['polls']['status']}")
    if who_body:
        n = X["who_info"]["n"]
        people = sum(len(v) for v in X["who"].values())
        print(f"  who the candidates are: data/who.json {kb(len(who_body.encode('utf-8')))} (fetched by a race's page), {people:,} candidates in {len(X['who']):,} races: "
              + ", ".join(f"{k} {v:,}" for k, v in sorted(n.items())) + f"; {len(X['who_info']['parties'])} party pages named")
    if votes:
        mcd = [v for k, v in votes["_sizes"].items() if k.startswith("mcd-")]
        print(f"  how places have voted: data/votes/ " + ", ".join(f"{k} {kb(v)}" for k, v in sorted(votes["_sizes"].items()) if not k.startswith("mcd-"))
              + (f"; cities and townships in {len(mcd)} county files, {kb(min(mcd))} to {kb(max(mcd))}" if mcd else "")
              + (f"; left out (no shape of that name): " + ", ".join(f"{k} {v}" for k, v in votes["_left"].items()) if votes["_left"] else ""))
    if X["markets"]:
        sw = [r["id"] for r in data["races"] if r["lv"] == "statewide"]
        also = [k for k in set(X["polls"]) | set(X["odds"]) if k not in sw]      # a seat the whole state votes on, filed with the courts
        print(f"  polls and markets (statewide races): polls entries for {len(X['polls'])} of {len(sw) + len(also)}, a market snapshot for {len(X['odds'])}"
              + (f", held back {len(X['held'])}" if X["held"] else "")
              + ("" if os.path.exists(ODDS_STATE) else " (no snapshot yet: run python run_ballot.py odds)"))
    for what, ids in sorted(warn.items()):
        ids = sorted(set(ids))
        print(f"  note: {len(ids)} {what}: {', '.join(ids[:6])}{' ...' if len(ids) > 6 else ''}")
    limit = SHELL_LIMIT_EXTRAS if has_extras else SHELL_LIMIT
    if shell > limit:
        print(f"  WARNING: the shell is {shell / 1e3:,.0f} KB, over the {limit / 1e3:,.0f} KB budget")
    if len(body.encode("utf-8")) > DATA_WARN:
        print(f"  WARNING: data/{lc}.json is {len(body.encode('utf-8')) / 1e6:,.1f} MB, a lot for one page to fetch; the county pages may need a file of their own")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--state", default="all", help="all (every state with rows in the database, the default), or two-letter codes, comma-separated")
    ap.add_argument("--root", default=ROOT, help="the On The Ballot folder; each state goes to <root>/<code>/ and the chooser to <root>/states/")
    ap.add_argument("--out", default=None, help="with one state: where to write its page (default <root>/<code>/index.html)")
    ap.add_argument("--site-root", default=None, help="the draft site's root, for the links to its other pages (default: the folder above the ballot folder)")
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit(f"No state and local ballot database yet ({args.db}). Run the state and local ballot loaders first (python run_ballot.py local).")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        have = [r[0] for r in con.execute("SELECT DISTINCT state FROM sl_races ORDER BY state")]
    except sqlite3.Error:
        sys.exit(f"{os.path.basename(args.db)} has no sl_races table. Run the state and local ballot loaders first (python run_ballot.py local).")
    want = have if args.state.strip().lower() == "all" else [c.strip().upper() for c in args.state.split(",") if c.strip()]
    missing = [c for c in want if c not in have]
    if missing:
        sys.exit(f"No rows for {', '.join(missing)} in {os.path.basename(args.db)} (it holds {', '.join(have) or 'nothing yet'}).")
    if args.out and len(want) != 1:
        sys.exit("--out names one page: give it with one --state.")
    root = os.path.abspath(args.root)
    parts = (borrow("CSS"), borrow_ballot("BALLOT_CSS"), borrow("CHANGELOG"), borrow("GEO"), borrow_ballot("SOURCEFOLD"), borrow_ballot("MARKETS"))
    changelog = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = (changelog[0].get("version") if changelog else "") or ""
    print(f"Version {version}")
    for code in want:
        out = os.path.abspath(args.out) if args.out else os.path.join(root, code.lower(), "index.html")
        site_root = os.path.abspath(args.site_root) if args.site_root else (
            os.path.abspath(os.path.join(os.path.dirname(out), "..", "..")) if args.out else os.path.dirname(root))
        build_state(code, args.db, out, site_root, parts, changelog, version)
    if not args.out:      # the chooser lists every state whose page is there, built now or before
        summaries = [state_summary(con, code) for code in have if os.path.exists(os.path.join(root, code.lower(), "index.html"))]
        path = write_chooser(root, summaries, parts[0], parts[1], version)
        print(f"Chooser: wrote {os.path.relpath(path, HERE)}: {len(summaries)} state(s) open ({', '.join(s['code'] for s in summaries)})")
        with_local = [s for s in summaries if s["local_races"]]
        print(f"  county and local races in {len(with_local)} of them ({', '.join(s['code'] for s in with_local) or 'none'}): "
              f"{sum(s['local_races'] for s in with_local):,} contests reaching {sum(s['counties'] for s in with_local):,} counties, "
              f"{sum(s['lcands'] for s in with_local):,} November candidates")
    con.close()


if __name__ == "__main__":
    main()
