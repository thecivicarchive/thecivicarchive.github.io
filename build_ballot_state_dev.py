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

What reaches the page, and nothing else (John, 2026-09-30): for every candidate the name as filed, the office, the
jurisdiction, the party for a partisan office or "Nonpartisan office", the ballot order, and write-in and special marks. No
photos, ages, websites, biographies, money or Wikipedia. A sitting legislator matched by the loader gets a link to their
existing record page on the state side and nothing more. The data is built field by field from those columns, and a
last check drops any text that looks like an e-mail address, a phone number, a web address or a street address; the
build names the race when it drops something and never prints the text itself.

One look, one code path: the site's stylesheet and the shared script parts (the changelog badge and the map arithmetic
behind "use my location") come from the federal page by the landmarks in build_state_dev.BORROWED, and the ballot pages'
own stylesheet (the arena, the cards, the primary fields, the maps) from build_ballot_dev.PAGE by the landmark below. If
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
SHELL_LIMIT = 300_000
DATA_WARN = 3_000_000      # a state's data file past this is said out loud by the build

# The ballot pages' own stylesheet, the second <style> of build_ballot_dev.PAGE: name -> (where it begins, where it ends).
BALLOT_BORROWED = {"BALLOT_CSS": (":root{--pR:var(--rep)", "</style>\n</head>")}


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
               "judge_of_probate", "assistant_judge", "magistrate", "justice_of_the_peace", "constable", "county_surveyor",
               "county_community_development_director", "county_elections_director", "county_school_trustee", "county_park"],
    "soil_water": ["soil_water"],
    "city": ["mayor", "vice_mayor", "council", "city_recorder", "city_clerk", "city_treasurer", "city_clerk_treasurer", "police_chief", "city_prosecutor",
             "justice_of_the_peace", "utility_board", "other"],
    "township": ["town_supervisor", "town_clerk", "town_treasurer", "town_clerk_treasurer", "justice_of_the_peace"],
    "school": ["school_superintendent", "school_board", "college_board"],
    "hospital": ["hospital_board"],
    "other": ["college_board", "utility_board", "water_board", "watershed_board", "sanitary_board", "public_service_board", "fire_board", "port_board",
              "highway_board", "development_district_board", "county_court_at_law", "district_attorney", "solicitor", "other"],
    # the higher court before the lower, the courts of general jurisdiction before the limited ones, the prosecutors and
    # the court's officers after the judges
    "court": ["supreme_court", "supreme_court_retention", "court_of_criminal_appeals", "court_of_civil_appeals", "court_of_appeals",
              "court_of_appeals_retention", "appellate_court", "appellate_court_retention", "superior_court", "superior_court_retention",
              "circuit_court", "chancery_court", "trial_court", "district_court", "district_court_retention", "parish_court", "family_court",
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
          "superior_court": "the superior courts", "circuit_court": "the circuit courts", "chancery_court": "the chancery courts",
          "trial_court": "the trial courts", "district_court": "the district courts", "family_court": "the family courts",
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
    m = re.search(r"\b(city|town|village|borough|township)$", name or "", re.I)
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


def build(db, code, lines):
    """Everything one state's page needs: (data, the page's words, warnings, candidate rows)."""
    lc = code.lower()
    P = place(code)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for t in ("sl_races", "sl_candidates", "sl_sources", "sl_places"):
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone():
            raise SystemExit(f"build_ballot_state_dev: {os.path.basename(db)} has no {t} table. Run the state and local ballot loader first.")
    guard = Guard()
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
        places[pk][key] = compact({"n": name, "c": county_list(cids, counties), "src": src, "t": t})

    links = roster_links(os.path.join(HERE, f"state_{lc}.sqlite"), P)
    roster_file = f"state_{lc}.sqlite"
    races, by_id, warn = [], {}, defaultdict(list)
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
                        **more, "date": r["election_date"] or GENERAL_DATE, "note": guard.ok(r["note"], rid, "race notes", strict=True), "el": {}},
                       keep=("pt", "el"))
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
    st = page_words(code, P, data, lines, nest, local, sources, off, prim_votes > 0, local_states)
    guard.report(code)
    return data, st, warn, n_cand


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


def county_kind_plural(word):
    """counties; counties and cities (Virginia); parishes; boroughs and census areas."""
    many = {"county": "counties", "city": "cities", "parish": "parishes", "borough": "boroughs", "census area": "census areas",
            "municipality": "municipalities", "planning region": "planning regions"}
    return and_list([many.get(w, w) for w in re.split(r", | or ", word or "county")])


def page_words(code, P, data, lines, nest, local, sources, off, prim_votes, local_states=()):
    """What the page says that differs from state to state, worked out from the record. Minnesota's page keeps its words."""
    mn = code == "MN"
    name = P["name"]
    lists = [s for s in sources.values() if s.get("kind") == "official candidate list"]
    agencies = list(dict.fromkeys((s.get("agency") or "").split(",")[0].strip() for s in lists if s.get("agency")))
    state_level = [a for a in agencies if not re.search(r"\bCounty\b", a)]
    county_level = [a for a in agencies if re.search(r"\bCounty\b", a)]
    partial = not state_level and len(county_level) > 1                     # Ohio: the November list is read county board by county board
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
        notice = (f"The November candidates come from the lists of the {number_word(len(county_level))} county boards of elections loaded so far, named "
                  "under Sources. A race that reaches only other counties shows no candidates until those counties&rsquo; lists are loaded.")
    st = {"code": code, "lc": code.lower(), "name": name, "agency": main, "lister": lister, "who": who, "fromWho": from_who, "partial": partial,
          "noGeneral": no_general, "notice": notice, "one": single, "up": up["name"], "lo": lo["name"],
          "upT": "Legislature" if up["name"] == "Legislature" else f"State {up['name']}", "loT": f"State {lo['name']}", "upD": up_d, "loD": lo_d,
          "upAbbr": up["name"][0] + "D", "loAbbr": lo["name"][0] + "D", "prim": pw, "local": local, "nest": bool(nest),
          "multi": multi, "zoom": and_list(zooms), "dOne": "a DFL member" if mn else one, "dMany": "DFL members" if mn else many,
          "off": off, "congress": congress, "congressShort": congress_short, "courts": courts,
          "unit": "seat" if mn else "race", "legNote": leg_note(P, nest, races, data["hds"]),
          "linesNote": ", the lines on the 2026 ballot" if mn else "", "fips": str(P.get("fips") or "")}
    cty = county_lines(code) if local else {}
    c_lines = bool(cty.get("counties"))
    local_parts = []
    if local:      # the county pages and the county, city or town and school district choices of "your ballot"
        words, local_parts = local_words(code, data, from_who, c_lines)
        st.update(words)
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
            "<b>Order.</b> Candidates appear in the ballot order the list gives, or by surname where it gives none. Never by money, polls or party.",
            (f"<b>Places.</b> A {c_one} or local contest is filed under every {st['countyWord']} it reaches. The names of cities, towns and districts come from "
             f"{and_list(['the ' + a if not a.lower().startswith('the ') else a for a in place_agencies])}, each named below"
             + ("; where something on a county&rsquo;s ballot could not be shown, that county&rsquo;s page says what and why."
                if any(g.get("sc") == "county" for g in data.get("gaps") or []) else ".")) if local and place_agencies else "",
            "<b>Who holds a seat today</b> (the Legislature and the statewide offices the roster carries) comes from the Open States roster the record side of this site uses. A candidate matched to a sitting legislator by district and name, one fit only, links to their record page and nothing more.",
            f"<b>Maps and &ldquo;use my location&rdquo;.</b> District lines are the Census Bureau&rsquo;s cartographic boundary files ({lines.get('vintage') or 'the current file'}), the lines the state pages draw"
            + (f", and the {c_one} lines are the Bureau&rsquo;s too ({cty.get('vintage')})" if c_lines and cty.get("vintage") else "")
            + f"; your {c_one}&rsquo;s sample ballot is the authority on your district. Your location is worked out on your own device and never sent anywhere; a rounded copy (about half a mile) is kept on the device, with your choices, until you tap &ldquo;Forget&rdquo;.",
            "<b>Nobody is scored or graded.</b> The cards show the record; the judging is yours."]
        st["methods"] = [m for m in st["methods"] if m]
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

/* ---------- the two switches, with the same saved choices as the rest of the site ---------- */
const calm = () => document.documentElement.classList.contains("calm");
const showMotion = () => $("#motion").setAttribute("aria-pressed", calm() ? "false" : "true");
showMotion();
$("#motion").addEventListener("click", () => { const off = !calm(); document.documentElement.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });

/* ---------- the state: its name, chambers and election office, worked out when the page was built ---------- */
const ST = BOOT.st, NM = esc(ST.name), WHO = ST.who, UP = esc(ST.up), LO = esc(ST.lo);
const EMPTY = ST.noGeneral ? `The ${WHO} list for November 3 is not loaded yet` : ST.partial ? `Not on the ${WHO} lists loaded so far` : "";      // what an empty November list means here
const NOTICE = ST.notice ? `<div class="notebox">${ST.notice}</div>` : "";
const dWord = key => (key === "upper" ? ST.upD : ST.loD).replace(/ District$/, " district");
const CO1 = ST.countyOne || "county", COS = ST.countyOnes || "counties";      // what a county is called here: a parish in Louisiana, a borough in Alaska

/* ---------- the data: races and candidates (data/<code>.json), and the lines, fetched when a map needs them ---------- */
let D = null, R = {}, LEG = {upper: {}, lower: {}}, LINES = null, linesP = null, MINE = {}, COUNTS = {}, SPLITS = new Set();
const needLines = () => LINES ? Promise.resolve(LINES) : (linesP || (linesP = fetch(BOOT.lines).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))))
  .then(d => (LINES = d), e => { linesP = null; throw e; })));

/* ---------- words ---------- */
const LV = {statewide: "Statewide offices", legislature: "The Legislature", county: "County offices", soil_water: ST.soilT || "Soil and water conservation", city: "City offices",
  township: "Township offices", school: ST.schoolT || "School districts", hospital: "Hospital districts", other: "Other districts", court: "Judges"};
const ORDER = ["statewide", "legislature", "county", "soil_water", "city", "township", "school", "hospital", "other", "court"];
const LOCAL = ["county", "soil_water", "city", "township", "school", "hospital", "other"];
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
const firstOf = n => String(n).split(/\s+(?:and|&)\s+/i)[0];
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
  if (r.k === "court_of_appeals") return /^\d+$/.test(r.d) ? `${ORD(+r.d)} Appellate District` : r.d;      // Michigan elects its appeals judges by district
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
const PRIVACY = `<p class="privacy"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg><span>Only the name, office and party each candidate filed under are shown. Addresses and contact details in the ${WHO} files are never read.</span></p>`;

/* ---------- small pieces ---------- */
const chip = (c, r) => `<span class="chip${serves(c, r) ? " inc" : ""}${c.wi ? " wi" : ""}" style="--pc:${pcVar(c)}" title="${esc(partyWords(c, r))}${serves(c, r) ? ", serves in this seat today" : ""}${c.wi ? ", write-in" : ""}"><i></i>${esc(c.n)}</span>`;
function raceRow(r, label, sub){
  const g = general(r), gap = g.length ? null : candGap(r);      // names the list holds but that could not be shown: said as such, with the reason on the race's page
  return `<a class="rrow wide" href="${hrefRace(r)}"><span class="rl">${label || esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}${sub ? `<small>${sub}</small>` : r.note ? `<small>${esc(r.note)}</small>` : ""}</span><span class="rc">${g.length ? g.map(c => chip(c, r)).join("") : `<span class="muted">${gap ? `Not here yet: ${esc(gap.w)}` : EMPTY || `No candidate on the ${WHO} list`}</span>`}</span><span class="go" aria-hidden="true">&rsaquo;</span></a>`;
}
const holderSmall = r => esc(plain(seatWords(r, false)));
const crumbs = parts => `<nav class="crumbs"><a href="#">${NM}</a>${parts.map(p => `<span>&rsaquo;</span>${p}`).join("")}</nav>`;
const srcItem = s => `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}<small><span class="tag fact">Fact</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : ""}${s.published ? ` &middot; published ${esc(s.published)}` : ""}${s.fetched ? ` &middot; read ${esc(s.fetched)}` : ""}${s.rows ? ` &middot; ${num(s.rows)} rows` : ""}${s.sha ? ` &middot; SHA-256 ${esc(String(s.sha).slice(0, 16))}&hellip;` : ""}${s.note ? " &middot; " + esc(s.note) : ""}</small></div>`;
const ROSTER_SRC = `<div class="srcitem"><b>Open States</b>: the roster of ${NM}&rsquo;s legislators and statewide officials (who holds each seat today), as the record side of this site loads it<small><span class="tag fact">Fact</span> <a href="https://github.com/openstates/people" target="_blank" rel="noopener">github.com/openstates/people</a> &middot; public domain (CC0)</small></div>`;
const LINES_SRC = () => `<div class="srcitem"><b>U.S. Census Bureau</b>: cartographic boundary files for ${NM}&rsquo;s legislative districts${ST.local && ST.cLines ? ` and ${esc(COS)}` : ""}, the lines the maps draw and &ldquo;use my location&rdquo; reads<small><span class="tag fact">Fact</span> <a href="https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html" target="_blank" rel="noopener">census.gov cartographic boundary files</a></small></div>`;

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
}

/* ---------- a candidate's card, and the arena ---------- */
function card(c, r, k){
  const sv = serves(c, r), href = c.m ? recordHref(c.m) : "", L = c.m && D.links[c.m];
  const flag = c.wi ? "Write-in" : sv ? "In this seat today" : c.inc ? "Incumbent" : "";
  const band2 = r.lv === "legislature" ? (r.k === "state_senate" ? `${ST.upAbbr} ${r.d}` : `${ST.loAbbr} ${r.d}`) : r.s ? seatWords2(r.s) : r.d ? (r.lv === "court" ? (/^court_of_appeals/.test(r.k) ? raceWhere(r) : judicialName(r.d)) : distWords(r.d)) : (r.lv === "statewide" ? "Statewide" : "");
  const rec = href ? `<a class="rec" href="${href}">${sv ? "Their record" : L && L[0] === "official" ? `${esc(L[1])} today: their record` : L ? `Serves in the ${NM} ${esc(L[1])} today: their record` : "Their record"}</a>` : (sv ? `<span class="rec">Serves in this seat today</span>` : "");
  const rows = [["Party", r.pt ? esc(partyShort(c, r)) : "Nonpartisan"], ["Ballot order", c.o != null ? esc(String(c.o)) : "Not given"]];
  return `<article class="bcard${c.wi ? " wi" : ""}${r.pt ? "" : " np"}" style="--pc:${pcVar(c)};--k:${k}" aria-label="${esc(c.n)}, ${esc(partyWords(c, r))}">
    <div class="band"><span>${esc(partyShort(c, r))}</span><span>${esc(band2)}</span></div>
    ${flag ? `<span class="flag">${esc(flag)}</span>` : ""}
    <div class="mono"><span aria-hidden="true">${esc(initials(c.n))}</span></div>
    <div class="who"><b>${esc(c.n)}</b><small>${esc(partyWords(c, r))}</small>${rec}</div>
    <dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`;
}
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
    <div class="ahead"><b>${title} &middot; ${esc(fmtDate(r.date))}</b><span>${unopp ? "Not printed on the ballot: nobody else qualified" : g.length === 1 ? "One name for this office" : `${g.length} candidates, ${ordered ? `in the ballot order the ${WHO} list gives` : "by surname: the list gives no ballot order"}`}</span></div>
    <div class="acards" data-n="${g.length}">${parts.join("")}</div>
    <p class="anote">Every card is the same size. A card holds what the ${WHO} list holds: the name as filed, the party it was filed under (or that the office is nonpartisan) and the ballot order. A candidate who serves in the Legislature or a statewide office today links to their record. No score or grade of any person.${ordered && !r.pt ? " The order printed on your own ballot can differ from precinct to precinct; your county&rsquo;s sample ballot shows it." : ""}</p>
  </section>`;
}
/* ---------- a partisan primary, and its field ---------- */
function field(r, key){
  const list = r.el[key] || []; if (!list.length) return "";
  const votes = list.some(c => c.v != null), max = Math.max(1, ...list.map(c => c.pct || 0));
  const rows = [...list].sort((a, b) => votes ? (b.v || 0) - (a.v || 0) : surname(a.n).localeCompare(surname(b.n)));
  const src = D.sources[list[0].src];
  return `<section class="field run"><div class="fh"><b>${esc(D.elections[key] || key)} &middot; ${esc(fmtDate(list[0].date))}</b><span>${plural(list.length, "candidate")} filed</span></div>
    <ol class="lanes">${rows.map((c, i) => { const href = c.m ? recordHref(c.m) : "";
      return `<li class="lane${c.out === "advanced" ? " won" : ""}${votes ? "" : " nobar"}" style="--pc:${pcVar(c)};--k:${i}"><span class="nm">${href ? `<a href="${href}">${esc(c.n)}</a>` : esc(c.n)}<small>${esc(c.p || "")}${serves(c, r) ? " &middot; serves in this seat today" : ""}</small></span>
      <span class="bar"><i style="--w:${votes ? (100 * (c.pct || 0) / max).toFixed(1) : 0}%"></i></span>
      <span class="vv">${votes ? `${num(c.v)} &middot; ${(c.pct || 0).toFixed(1)}%` : (c.out === "advanced" ? "On the November ballot" : c.out === "lost" ? "Not on the November ballot" : "")}</span></li>`; }).join("")}</ol>
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
    note.innerHTML = `District lines: ${esc(LINES.vintage || "the Census Bureau's current file")}${ST.linesNote}.${myDistrict(view) ? " Your district, as picked on this page, is outlined in gold." : ""}`;
  }
  function show(d, keep){ const r = legRace(view, d); if (keep) { sel = d; marks(); relabel(); jump.value = d; } side.innerHTML = r ? legPreview(r) : `<p class="held">No race for District ${esc(d)} is on the ${WHO} list for November 3.</p>`; }
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
const yoursHTML = () => ST.local ? `<section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Pick ${andList([`your ${esc(ST.countyWord)}`, ST.pickM ? `your ${esc(MUNI1)}` : "", ST.pickS ? `your ${esc(ST.schoolOne)}` : "", `your ${NM} ${esc(dWord(ST.one ? "upper" : "lower"))}`, twoPicks ? `your ${esc(dWord("upper"))}` : ""].filter(Boolean))}, or let this device work out ${ST.cLines ? `the ${esc(ST.countyWord)} and the district${twoPicks ? "s" : ""}` : `the district${twoPicks ? "s" : ""}`}. Your choices and your location stay on this device; nothing is sent anywhere.</p>
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
  if (m.c) {
    const county = byLv("county").filter(inC), soil = byLv("soil_water").filter(inC);
    out.push(level(`${esc(cName(m.c))}`, county, districted(county) ? DIST_NOTE : ""));
    const soilDistricts = new Set(soil.filter(r => r.pk).map(r => r.pk)).size + (soil.some(r => r.pk) && soil.some(r => !r.pk) ? 1 : 0);
    out.push(level(esc(LV.soil_water), soil, [districted(soil) ? DIST_NOTE : "", soilDistricts > 1 ? `More than one of these districts reaches the ${CO1}; only the one you live in is on your ballot.` : ""].filter(Boolean).join(" ")));
    if (ST.pickM) {      // the state's rows have city, town or township contests: the place the reader picked, or the ask
      const local = m.m ? D.races.filter(r => r.pk === m.m && LOCAL.includes(r.lv)) : [];
      if (m.m) out.push(local.length ? level(esc(placeName(m.m)), local, districted(local) ? DIST_NOTE : "") : note(esc(placeName(m.m)), `No ${esc(MUNI1)} contest for ${esc(placeName(m.m))} is on the ${WHO} list for November 3.`));
      else out.push(note(esc(capital(MUNI1)), `Pick your ${esc(MUNI1)} above to add its contests.`));
    }
    if (ST.pickS) {
      const sch = m.s ? D.races.filter(r => r.pk === m.s) : [];
      if (m.s) out.push(sch.length ? level(esc(placeName(m.s)), sch, !OLDER && districted(sch) ? DIST_NOTE : "") : note(esc(placeName(m.s)), ST.schoolOne === "school district" ? `No school board contest for this district is on the ${WHO} list for November 3.` : `No contest for this school board is on the ${WHO} list for November 3.`));
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
    const tied = courts.filter(localCourt), mine = tied.filter(inC), rest = courts.filter(r => !localCourt(r)), APPEAL = /^(supreme_court|court_of_|appellate_court)/;
    const whole = rest.filter(r => !r.d), byApp = rest.filter(r => r.d && APPEAL.test(r.k)), byOther = rest.filter(r => r.d && !APPEAL.test(r.k));
    const noun = tied.length ? courtNoun(tied) : "", list = whole.concat(byApp, mine);
    const words = [!tied.length ? "" : !m.c ? `Pick your ${esc(ST.countyWord)} to add its ${noun}.`
        : mine.length ? "" : `No race for ${noun} on the list is filed under ${esc(cName(m.c))}; <a href="#courts">see every ${noun === "district court judges" ? "district court" : "court"} race</a>.`,
      byApp.length ? "Where a court is elected by district, only your own district&rsquo;s seats are on your ballot." : "",
      byOther.length ? `${plural(byOther.length, "more court race")} ${byOther.length === 1 ? "is" : "are"} elected by district, and the list does not say which counties each district covers: <a href="#courts">see every court race</a>.` : ""].filter(Boolean).join(" ");
    out.push(list.length ? level(list.every(isJudge) ? "Judges" : capital(courtNoun(list)), list, words) : words ? note("Judges", words) : "");
  }
  else out.push(level("Judges", courts.filter(r => r.k !== "district_court"),
    [appeals.length ? "The Court of Appeals is elected by appellate district; only your own district&rsquo;s seats are on your ballot." : "",
     dc.length ? `District court judges are elected by judicial district: <a href="#courts">see every district court race</a>.` : ""].filter(Boolean).join(" ")));
  const where = [m.c ? cName(m.c) : "", m.m ? placeName(m.m) : "", m.s ? placeName(m.s) : "", m.hd && !ST.one ? `${ST.loD} ${m.hd}` : "", !ST.nest && sd ? `${ST.upD} ${sd}` : ""].filter(Boolean).map(esc).join(" &middot; ");
  return `<div class="bl-head"><h3>What&rsquo;s on your ballot</h3><p class="ynote">${where}. In the order a${/^[AEIOU]/.test(ST.name) ? "n" : ""} ${NM} ballot runs, level by level${BOOT.links.us && ST.congressShort ? `, below <a href="../us/#state=${esc(ST.code)}">${ST.congressShort}</a> at the top` : ""}. Your ${CO1}&rsquo;s sample ballot is the authority on your exact ballot.</p></div>${out.join("")}`;
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
  if (cty) {
    cty.addEventListener("change", () => { MINE = {c: cty.value, hd: MINE.hd, ...(ST.nest ? {} : {sd: MINE.sd || ""}), m: "", s: "", loc: !!MINE.loc}; save(); fill(); paint(); note.textContent = ""; });
    if (mcd) mcd.addEventListener("change", () => { MINE.m = mcd.value; save(); paint(); });
    if (sch) sch.addEventListener("change", () => { MINE.s = sch.value; save(); paint(); });
  }
  if (hd) hd.addEventListener("change", () => { MINE.hd = hd.value; save(); paint(); note.textContent = ""; });
  if (sdp) sdp.addEventListener("change", () => { MINE.sd = sdp.value; save(); paint(); note.textContent = ""; });
  forgetB.addEventListener("click", () => { MINE = {}; ["pin", "district", SLD, YKEY].forEach(k => store.del(k)); fill(); paint(); note.textContent = "Forgotten. Your location and your choices are no longer kept on this device."; });
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
    note.textContent = ST.local ? `Finding your ${ST.cLines ? ST.countyWord + " and " : ""}district${twoPicks ? "s" : ""}…` : "Finding your districts…";
    navigator.geolocation.getCurrentPosition(pos => {
      const lat = pos.coords.latitude, lon = pos.coords.longitude;
      placeFrom(lon, lat, "Worked out on this device; your location never leaves it.").then(ok => {
        if (ok) { store.set("pin", JSON.stringify({st: ST.code, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(pos.coords.accuracy || 0)})); store.set("state", ST.code); }      // rounded: about half a mile, the same kept pin the other pages use
      }, () => { note.textContent = "Couldn't load the district lines. Check your connection, or pick from the lists."; });
    }, () => { note.textContent = "Location wasn't shared. Pick from the lists instead."; }, {timeout: 10000, maximumAge: 600000});
  });
  fill(); paint();
  if (!MINE.c && !MINE.hd && !MINE.sd) {      // a rounded pin kept by the other pages of this site: place it here too
    try { const pj = JSON.parse(store.get("pin") || "null"); if (pj && pj.st === ST.code && isFinite(pj.lat) && isFinite(pj.lon)) placeFrom(pj.lon, pj.lat, "Placed from the rounded location this device already keeps (about half a mile).").catch(() => {}); } catch (e) {}
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
  ${ST.local ? `<section class="bsec" id="counties"><h2>${esc(capital(CO1))} by ${esc(CO1)}</h2><p class="sub">${ST.countySub}</p>
    ${noteBox("local_calendar")}${ST.cLines ? `<div class="cgrid"><figure class="cmapwrap" style="margin:0"><svg class="cmap" id="cmap" role="group" aria-label="Map of ${NM}&rsquo;s ${esc(COS)}"></svg></figure>
      <div class="sgrid">${cards}</div></div>` : `<div class="sgrid wide">${cards}</div>`}${noteKeys().filter(k => k !== "local_calendar").map(noteBox).join("")}${gapBox(GAPS.state, true)}${elsewhere ? `<p class="ynote">${elsewhere}</p>` : ""}</section>`
    : D.notes || GAPS.state.length ? `<section class="bsec" id="localnotes"><h2>County and local races</h2><p class="sub">No county or local contest is shown for ${NM}. The notes kept with the state&rsquo;s lists say why.</p>${noteKeys().map(noteBox).join("")}${gapBox(GAPS.state, true)}</section>` : ""}
  ${BOOT.links.us && ST.congress ? `<section class="bsec" id="congress"><h2>Congress</h2><p class="sub">${ST.congress}</p></section>` : ""}
  ${sourcesHTML()}`;
  mountYours(); if (ST.local && ST.cLines) mountCountyMap("cmap", MINE.c ? [MINE.c] : []);
  if (anchor && $("#" + anchor)) $("#" + anchor).scrollIntoView();
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
    <p class="lede">${localN ? `${plural(localN, `${CO1} or local contest`)} on the November 3 ballot ${localN === 1 ? "reaches" : "reach"} ${esc(cName(f))}${reachWords}. ${lines}` : `No ${CO1} or local contest reaching ${esc(cName(f))} is on the ${WHO} lists${judges.length ? `; ${plural(judges.length, "court contest")} ${judges.length === 1 ? "is" : "are"}` : ""}.`}</p>
    ${BOOT.links.county_page ? `<p class="holder">Who holds the county offices today: <a href="../../${ST.lc}/counties/#c=${esc(f)}">${esc(cName(f))} on the record side</a>.</p>` : ""}
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
function racePage(id){
  const r = R[id]; if (!r) { document.title = `Not found · On The Ballot: ${ST.name}`; $("#app").innerHTML = `${crumbs(["<span>Not found</span>"])}<div class="notebox">That race is not on the lists this page holds. <a href="#">Back to ${NM}</a></div>`; return; }
  document.title = `${raceTitle(r)}${r.lv === "legislature" || r.lv === "statewide" ? "" : ", " + raceWhere(r)} · On The Ballot: ${ST.name}`;
  const back = r.lv === "statewide" ? `<a href="#statewide">Statewide offices</a>` : r.lv === "legislature" ? `<a href="#legislature">The Legislature</a>` : r.lv === "court" ? `<a href="#courts">Judges</a>`
    : (r.c || []).length ? `<a href="#county=${esc(r.c[0])}">${esc(cName(r.c[0]))}</a>` : `<a href="#counties">${esc(capital(COS))}</a>`;
  const prim = primaries(r);
  const srcIds = [...new Set(Object.values(r.el || {}).flat().map(c => c.src).concat([(placeOf(r) || {}).src]).filter(Boolean))];
  const where = raceWhere(r), cs = (r.c || []).map(f => `<a href="#county=${esc(f)}">${esc(cName(f))}</a>`).join(", ");
  const loc = r.lv === "legislature" || (ST.cLines && (r.c || []).length && r.lv !== "statewide");
  const gaps = GAPS.race[r.id] || [], named = candGap(r);      // what the loader said is missing from this contest, and why
  $("#app").innerHTML = `${crumbs([back, `<span>${esc(raceTitle(r))}</span>`])}
  <section class="bhero${loc ? " withloc" : ""}"><div><span class="eyebrow">${esc(levelWords(r))} &middot; ${esc(fmtDate(r.date))}</span><h1>${esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</h1>
    <p class="holder">${esc(where)}${where !== ST.name && cs && !(r.lv === "county" && (r.c || []).length === 1) ? ` &middot; ${cs}` : ""}. ${r.pt ? "Elected on party lines: the party each candidate filed under is printed on the ballot." : "A nonpartisan office: no party is printed beside the names."}</p>
    ${r.lv === "legislature" || r.lv === "statewide" ? `<p class="holder">${seatWords(r, true)}</p>` : ""}
    ${r.sp ? `<p class="holder">A special election${r.note ? "" : ", for the rest of a term"}.</p>` : ""}${r.note && !gaps.some(g => g.r === r.note) ? `<p class="holder">${esc(r.note)}</p>` : ""}${PRIVACY}</div>${loc ? locatorHTML() : ""}</section>
  ${general(r).length ? arena(r) : named ? "" : `<div class="notebox">${EMPTY ? EMPTY + "." : `No candidate for this office is on the ${WHO} list for November 3.`}</div>`}${gapBox(gaps)}
  ${prim.length ? `<section class="bsec"><h2>How they got here</h2><p class="sub">${howTheyGotHere(r, prim)}</p>${prim.map(k => field(r, k)).join("")}</section>`
    : r.pt || !ST.npLine ? "" : `<p class="fnote">${ST.npLine}</p>`}
  <section class="bsec"><h2>Where this comes from</h2><div class="srclist">${srcIds.map(s => D.sources[s]).filter(Boolean).map(srcItem).join("")}${r.h ? ROSTER_SRC : ""}${loc ? LINES_SRC() : ""}</div></section>`;
  if (r.lv === "legislature") mountLegLocator(r); else if (loc) mountCountyMap("locsvg", r.c || [], "loccap");
}
function sourcesHTML(){
  return `<section class="bsec" id="sources"><h2>Sources and methods</h2>
    <ul class="method sub">
${ST.methods.map(m => `      <li>${m}</li>`).join("\n")}
    </ul>
    <div class="srclist">${Object.values(D.sources).map(srcItem).join("")}${ROSTER_SRC}${LINES_SRC()}</div></section>`;
}

/* ---------- the address decides the page ---------- */
function route(){
  if (!D) return;
  let h = ""; try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { h = location.hash.slice(1); }
  if (mapOff) { mapOff.abort(); mapOff = null; }
  if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("county=") && ST.local) countyPage(countyKey(h.slice(7)));
  else if (h === "statewide") statewidePage();
  else if (h === "legislature") legislaturePage();
  else if (h === "courts" && D.races.some(r => r.lv === "court")) courtsPage();
  else { home(h); if (!h) scrollTo(0, 0); return; }
  scrollTo(0, 0);
}
addEventListener("hashchange", () => { route(); const a = $("#app"); if (a && !/^(yours|counties|sources|levels|congress|localnotes)$/.test(location.hash.slice(1))) a.focus({preventScroll: true}); });
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
    <p class="privacy"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg><span>Only the name, office and party each candidate filed under are shown. Addresses and contact details in the states&rsquo; files are never read.</span></p>
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
  <p>On The Ballot, from The Civic Archive v__VERSION__. Each state&rsquo;s candidates come only from its own election office&rsquo;s official lists; the sources are named on each state&rsquo;s page. No photos, no money, no scores or ratings of any person. Built __GENERATED__.</p>
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
    return {"code": code, "name": place(code)["name"], "by": by, "state_races": state_races, "local_races": local_races, "cands": cands, "lcands": lcands,
            "partial": partial, "counties": len(reached), "unit": unit}


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
    page = STATES_PAGE.replace("__CSS__", css).replace("__BALLOT_CSS__", bcss).replace("__MAP__", "\n      ".join(marks)).replace("__CARDS__", cards)
    for key, value in words.items():
        page = page.replace(key, value)
    page = page.replace("__CHIPS__", chips).replace("__COUNT__", f"{number_word(n).capitalize()} state{'s' if n != 1 else ''}")
    page = page.replace("__NAMES__", html_esc(and_list([s["name"] for s in sorted(summaries, key=lambda s: s["name"])])))
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    write_if_changed(os.path.join(out_dir, "index.html"), page)
    copy_fonts(out_dir)
    return os.path.join(out_dir, "index.html")


def build_state(code, db, out, site_root, parts, changelog, version):
    """One state's page, its data and its lines."""
    css, bcss, clog, geo = parts
    lc = code.lower()
    out_dir = os.path.dirname(os.path.abspath(out))
    lines = lines_for(code)
    data, st, warn, n_cand = build(db, code, lines)
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
    page = PAGE.replace("__CSS__", css).replace("__BALLOT_CSS__", bcss).replace("__CHANGELOG__", clog).replace("__GEO__", geo)
    page = page.replace("__NAME__", html_esc(st["name"])).replace("__DESC__", html_esc(st["desc"])).replace("__NAV__", st["nav"])
    page = page.replace("__FOOT__", html_esc(st["foot"]).replace("&amp;rsquo;", "&rsquo;"))
    page = page.replace("__RECORD__", f' &middot; <a href="../../{lc}/">{html_esc(st["name"])}&rsquo;s Legislature on the record side</a>' if record else "")
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
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
    for what, ids in sorted(warn.items()):
        ids = sorted(set(ids))
        print(f"  note: {len(ids)} {what}: {', '.join(ids[:6])}{' ...' if len(ids) > 6 else ''}")
    if shell > SHELL_LIMIT:
        print(f"  WARNING: the shell is {shell / 1e3:,.0f} KB, over the {SHELL_LIMIT / 1e3:,.0f} KB budget")
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
    parts = (borrow("CSS"), borrow_ballot("BALLOT_CSS"), borrow("CHANGELOG"), borrow("GEO"))
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
