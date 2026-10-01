"""
ballot/state_local_oh.py - Ohio's state races on the November 3, 2026 ballot: Governor and Lieutenant Governor (one
ticket), Attorney General, Auditor of State, Secretary of State, Treasurer of State, the two seats on the Supreme Court
(party labels are printed for the court in Ohio), the seventeen odd-numbered State Senate seats (four-year terms; the odd
half is up in 2026, as the May canvass confirms) and all 99 seats of the Ohio House, with each party's May 5 primary field
and its official votes; and, county by county, the county offices and the judges on the same ballot.

The county and local part
-------------------------
Ohio has no statewide list of county candidates: each of the 88 county boards of elections publishes its own. On
November 3, 2026 a county elects one commissioner and its auditor (a charter county its own officers), and the voters
choose judges of the courts of appeals, the courts of common pleas and the county courts; cities, villages, townships
and school boards elect in odd years, so only a stray unexpired term is on this ballot (R.C. 3501.02, 305.01, 319.01).
Read here:
  - the nine lists below, by the same readers that take their state races: the county commissioner and auditor,
    Cuyahoga's executive and council, a Mentor council seat on Lake's list, and the judges;
  - Hamilton's 46-day notice (the federal loader's copy) for its judges and county offices, and the 46-day notice of
    every other board whose own site a script could reach on 2026-10-01 (NOTICES: Warren, Delaware, Clermont, Trumbull,
    Wayne, Hancock, Sandusky, Mercer, Crawford, Guernsey, Williams, Morrow, Henry; for Ottawa, whose notice is a scan,
    the board's small candidate file). A notice is the "Election Notice for use with the Federal Write-In Absentee
    Ballot" every board must post 46 days out (R.C. 3511.16): names, offices, parties and precincts, no addresses. It is
    fetched once through states/net.py and kept whole in ballot_cache/oh/local/<county>/; a second run downloads
    nothing (--refresh fetches again). A board whose site is down or refuses is left alone and written down as a gap.
  - a notice someone has saved from a browser as ballot_cache/oh/local/<county>/<county>_46day_notice.pdf, for any
    county: most boards keep their pages on the state's shared site (boe.ohio.gov), and Summit, Lucas and Portage on
    sites of their own, all of which turn scripts away and are never asked. The file must name the county's board and
    November 3, 2026, or it is refused.
State races are still taken only from the nine lists (the state rows must not change); a notice's statewide candidates
are read back as a control instead, and its legislative districts are counted and left alone.
What is written: level county for county offices, city for a municipal seat, and court for every judge (kind
court_of_appeals with all the counties of its district from R.C. 2501.01, common_pleas_court and county_court with the
one county), each seat told apart by its division and by the day its term begins or ends, as the ballot words it
(R.C. 3505.04). A court of appeals race is on every list of its district: it is taken from the first that carries it,
the others are checked against it, and declared write-in candidates come from the first list that names them. Common
pleas and county court candidates are "Nonpartisan office": the lists print the party that nominated them, the
November ballot does not. sl_gaps names every county not read and why; sl_notes says which local offices are on this
ballot (local_calendar) and what was read (local_coverage). An office heading no pattern fits is written as a gap,
never guessed and never dropped; a withdrawn candidate is left off and counted; a name cell that is not a name is
blanked and counted, never shown.

Sources for the state races, every one official, every one already cached (for these the loader downloads nothing):
  - The county boards' candidate lists the federal loader reads (ballot/lists/oh.py, cached in ballot_cache/oh/): Franklin,
    Cuyahoga, Lake, Lorain, Stark, Wood, Butler, Union's 46-day notice and Hamilton's 46-day notice. The Secretary of State's
    site and the boards hosted on boe.ohio.gov answer scripts with a Cloudflare challenge and are not read. Each board's
    list carries the statewide races and the legislative districts that reach its county. A race is taken from the first
    list in the order above that carries it; every other list that carries it is checked against it (family names and
    parties). A district that no list read here carries is kept, with the reason in its note and its primary fields, and
    no November candidates: they are never guessed from the primary.
  - The Secretary of State's official canvass of the May 5, 2026 primary, one "Summary Level Official Results" workbook per
    party (Democratic, Republican, Libertarian; carried out of the Browser pane for the federal loader): the Statewide
    Offices, Justice of the Supreme Court and General Assembly sheets. Every candidate column's 88 county rows must add up
    to its Total row. A field is a party's primary with two printed candidates or more (as on the federal side); write-in
    votes count toward its total, and the top vote-getter advanced. The county rows also give the counties a district
    reaches: those where any candidate of any party's primary for it received a vote (Census codes from the Bureau's
    2024 county file).
  - Holders from the Open States roster in state_oh.sqlite (legislators, is_current = 1; the officials table for Governor,
    Lieutenant Governor, Attorney General and Secretary of State). The roster carries no Auditor, Treasurer or justices.

Privacy. The county lists print candidates' addresses, cities, ZIP codes, telephones, e-mail and websites beside the
names. Only these cells are ever turned into kept text: office headings, name, party, status and write-in marks (and
Franklin's term band for the court seats). Each reader takes the cells by position; a name cell stops at the first piece
that begins with a digit (Lake's list can start an address inside its name column), and a name that still holds a
digit, "Box", "@" or a web address stops the loader, which names the list, the race and the row number, never the text.
Nothing but name, office, district, party and write-in marks is stored; no ballot order (Ohio rotates names from precinct
to precinct, R.C. 3505.03, and the lists print them in different orders). The same holds for the county and court races:
no holder, age, photograph, website or money for anyone. The 46-day notices and Ottawa's file have no contact columns
at all, which is why they may be kept whole; every stored text is still passed through check_local.contact_like first.

    python -m ballot.state_local_oh --db <path to a test database> [--refresh]
"""

import collections
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists import oh as fed  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, Font, Ref, _mul, _ops, join, page_runs  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "OH", "39"
GENERAL, PRIMARY = "2026-11-03", "2026-05-05"
CACHE = os.path.join(HERE, "ballot_cache")
FOLDER = os.path.join(CACHE, "oh")
LOCAL_DIR = os.path.join(FOLDER, "local")
ROSTER = os.path.join(HERE, "state_oh.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
SRC_COUNTY, SRC_ROSTER = "oh-census-2024-county-codes", "oh-openstates-roster"
ORDER = ("franklin", "cuyahoga", "lake", "lorain", "stark", "wood", "butler", "union", "hamilton")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT,
  special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT,
  election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL,
  party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0,
  votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT,
  published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

# key -> (level, office_kind, office, roster office)
STATEWIDE = {
    "GOV": ("statewide", "governor", "Governor and Lieutenant Governor", "governor"),
    "AG": ("statewide", "attorney_general", "Attorney General", "attorney general"),
    "AUD": ("statewide", "state_auditor", "Auditor of State", None),
    "SOS": ("statewide", "secretary_of_state", "Secretary of State", "secretary of state"),
    "TREAS": ("statewide", "state_treasurer", "Treasurer of State", None),
}
COURT = {"SC-20270101": "Full term commencing January 1, 2027", "SC-20270102": "Full term commencing January 2, 2027"}
SENATE_UP = list(range(1, 34, 2))
HOUSE_SEATS = 99
PARTY_OF = {"DEM": "Democratic", "REP": "Republican", "LIB": "Libertarian"}
CODE_OF = {v: k for k, v in PARTY_OF.items()}
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."
CAPS_NOTE = "Union County's notice prints names in capitals; they are shown here in ordinary capitals."
NO_LIST = ("None of the county boards' candidate lists read here carries this district (the boards on the state's shared "
           "elections site and the Secretary of State's own site answer scripts with a Cloudflare challenge), so its November "
           "candidates are not shown yet; the May 5 primary is shown from the Secretary of State's official canvass.")


class ListError(SystemExit):
    pass


# ---------------------------------------------------------------- the office a heading names

EXCLUDE = re.compile(r"CONGRESS|UNITEDSTATES|U\.?S\.?SENAT|COUNTY|COMMONPLEAS|COURTOFAPPEALS|PROBATE|MUNICIPAL|CITY|VILLAGE|TOWNSHIP|"
                     r"COUNCIL|COMMISSIONER|SCHOOL|CENTRALCOMMITTEE|JUDGE|ISSUE")
DISTRICT = re.compile(r"(\d{1,2})(?:ST|ND|RD|TH)?(?:STATESENATE|OHIOSENATE|OHIOHOUSE|HOUSE|SENATE)?DISTRICT|DISTRICT(\d{1,2})(?!\d)")


def classify(text):
    """The race a heading names (2026-OH-GOV, 2026-OH-SS5, 2026-OH-SH44, 2026-OH-SC-20270101), or None for any other
    office. A court or legislative heading whose seat cannot be read stops the loader rather than being dropped."""
    t = re.sub(r"\s+", "", (text or "").upper())
    if not t or EXCLUDE.search(t):
        return None
    if "SUPREMECOURT" in t:
        m = re.search(r"0?1[/-]0?([12])[/-](?:20)?27", t)
        if not m:
            raise ListError(f"Ohio: a Supreme Court heading without its term date ({len(t)} characters)")
        return f"2026-{STATE}-SC-2027010{m.group(1)}"
    for key, pat in (("SS", r"STATESENAT"), ("SH", r"STATEREPRESENTATIVE|HOUSEOFREPRESENTATIVES|OHIOHOUSE")):
        if re.search(pat, t):
            m = DISTRICT.search(t)
            if not m:
                raise ListError(f"Ohio: a legislative heading without a district number ({key})")
            d = int(m.group(1) or m.group(2))
            if (key == "SS" and d not in SENATE_UP) or (key == "SH" and not 1 <= d <= HOUSE_SEATS):
                raise ListError(f"Ohio: a {key} district {d} that is not on the 2026 ballot")
            return f"2026-{STATE}-{key}{d}"
    if "GOVERNOR" in t:
        return f"2026-{STATE}-GOV"
    if "ATTORNEYGENERAL" in t:
        return f"2026-{STATE}-AG"
    if "SECRETARYOFSTATE" in t:
        return f"2026-{STATE}-SOS"
    if re.search(r"AUDITOR", t):
        return f"2026-{STATE}-AUD"
    if re.search(r"TREASURER", t):
        return f"2026-{STATE}-TREAS"
    return None


# ---------------------------------------------------------------- names: only a name ever leaves a reader

NAME_OK = re.compile(r"^[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f.'\u2019\- ,\"]*$")
NOT_A_NAME = re.compile(r"\d|@|www|\.com|\.org|\.net|\bbox\b|\bp\.?\s?o\.?\b|\bsuite\b|\bste\b", re.I)


def clean_name(text, where):
    """Spaces tidied, a ticket written 'Governor and Lieutenant Governor', and checked to be a name. The text is never
    shown when the check fails. A state race's cell that is not a name stops the loader; a county or court race's is
    blanked and counted (local_name), so one odd cell in a county's list cannot stop the state rows."""
    if "(" + LOCAL in where:
        return local_name(text, where)
    t = re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()
    t = re.sub(r"\s*(?:&|/)\s*|\s+(?:AND|And)\s+", " and ", t).strip()
    t = re.sub(r"\s+and$", "", t)
    if not t or NOT_A_NAME.search(t) or not NAME_OK.match(t):
        raise ListError(f"Ohio: {where} holds something other than a name (the text is not shown); the list's layout may have changed")
    return t


def cut_name(runs, lo, hi):
    """A name cell from the runs between lo and hi: stops at the first piece that starts with a digit or after a wide
    gap, so an address that begins inside the column is never taken in."""
    kept, end = [], None
    for r in sorted((r for r in runs if lo <= r[0] < hi), key=lambda r: r[0]):
        if r[3].strip()[:1].isdigit() or (end is not None and r[0] - end > 18):
            break
        kept.append(r)
        end = r[4]
    return re.split(r"\s\d", join(kept))[0].strip()


def party_word(p, write_in=False):
    p = re.sub(r"\s+", " ", (p or "").strip().strip('"').strip())
    p = fed.WORDS.get(p.upper(), p)
    if re.fullmatch(r"(?i)non-?party(?: candidate)?", p):
        p = "Nonparty"
    if re.fullmatch(r"(?i)other[- ]party(?: candidate)?", p):
        p = "Other-party"
    return p or ("Write-in" if write_in else "No party")


def cand(race, name, party, write_in=False, gone=False, note=None):
    if race.startswith(LOCAL):
        return {"race": race, "name": name, "party": local_party(party, write_in), "write_in": bool(write_in), "gone": bool(gone), "note": note}
    return {"race": race, "name": name, "party": party_word(party, write_in), "write_in": bool(write_in), "gone": bool(gone), "note": note}


# ---------------------------------------------------------------- county offices and judges: what a heading names
#
# A county, court or city office is carried from a reader to the loader as a key, "L|kind|district|division|term|date|
# place": the kind of office, the council district or ward, the division of the court, F (a full term) or U (the rest
# of an unexpired one), the day the term begins or ends, and the municipality. A state race stays its race id.

LOCAL = "L|"
BLANKED = collections.Counter()      # cells that were not names (never shown): list -> how many
UNNAMED = collections.Counter()      # write-in candidates a list prints without their names: (list, race) -> how many
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DATE_NUM = re.compile(r"(?<![\d/-])(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]+\s*(\d{4}|\d{2})(?![\d/-])")
DATE_WORD = re.compile(r"\b(" + "|".join(MONTHS) + r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
ORDINALS = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH", "ELEVENTH", "TWELFTH")
# The twelve court of appeals districts, R.C. 2501.01, read from codes.ohio.gov on 2026-10-01 (the loader checks this
# table against its cached copy of the section each time it runs).
APPELLATE = {
    1: ("Hamilton",),
    2: ("Darke", "Miami", "Montgomery", "Champaign", "Clark", "Greene"),
    3: ("Mercer", "Van Wert", "Paulding", "Defiance", "Henry", "Putnam", "Allen", "Auglaize", "Hancock", "Hardin", "Logan", "Union", "Seneca",
        "Shelby", "Marion", "Wyandot", "Crawford"),
    4: ("Adams", "Highland", "Pickaway", "Ross", "Pike", "Scioto", "Lawrence", "Gallia", "Jackson", "Meigs", "Vinton", "Hocking", "Athens",
        "Washington"),
    5: ("Morrow", "Richland", "Ashland", "Knox", "Licking", "Fairfield", "Perry", "Morgan", "Muskingum", "Guernsey", "Coshocton", "Holmes", "Stark",
        "Tuscarawas", "Delaware"),
    6: ("Williams", "Fulton", "Wood", "Lucas", "Ottawa", "Sandusky", "Erie", "Huron"),
    7: ("Mahoning", "Columbiana", "Carroll", "Jefferson", "Harrison", "Belmont", "Noble", "Monroe"),
    8: ("Cuyahoga",),
    9: ("Lorain", "Medina", "Wayne", "Summit"),
    10: ("Franklin",),
    11: ("Lake", "Ashtabula", "Geauga", "Trumbull", "Portage"),
    12: ("Brown", "Butler", "Clermont", "Clinton", "Fayette", "Madison", "Preble", "Warren"),
}
APPEALS_OF = {c: d for d, cs in APPELLATE.items() for c in cs}
STATE_WORDS = re.compile(r"GOVERNOR|ATTORNEY GENERAL|SECRE?TARY OF STATE|AUDITOR OF STATE|TREASURER OF STATE|STATE OF OHIO|SUPREME|JUSTICE|"
                         r"U\. ?S\.|\bUS (?:SENAT|CONGRESS|REP|HOUSE)|UNITED STATES|CONGRESS|SENAT|REPRESENTATIVE|HOUSE OF|HOUSE DISTRICT|"
                         r"GENERAL ASSEMBLY|STATE BOARD OF EDUCATION|CENTRAL COMMITTEE")
STATE_SECTIONS = re.compile(r"STATE EXECUTIVE|SUPREME COURT|U\. ?S\. ?SENATE|CONGRESS|GENERAL ASSEMBLY|^FEDERAL$|^STATE$")
QUESTION = re.compile(r"\bISSUES?\b|\bLEVY\b|\bTAX\b|REFERENDUM|LIQUOR|LOCAL OPTION|CHARTER AMENDMENT|\bBOND\b|\bQUESTION")      # not people
# words of a city, township, school or municipal court office this loader has no pattern for: reported, never dropped
LOCAL_HINT = re.compile(r"BOARD OF EDUCATION|SCHOOL|TOWNSHIP|TRUSTEE|MAYOR|COUNCIL|MUNICIPAL|VILLAGE|\bCITY\b|LAW DIRECTOR|SOLICITOR|"
                        r"EDUCATIONAL SERVICE|COUNTY COURT|AREA COURT|\bCLERK\b|MAGISTRATE")
COUNTY_OFFICES = (      # pattern in a heading -> (office kind, the office in plain words)
    (r"COUNTY EXECUTIVE", "county_executive", "County Executive"),
    (r"COUNTY COUNCIL|COUNCIL AT[- ]LARGE", "county_council", "Member of County Council"),
    (r"COMMISSIONER", "county_commissioner", "County Commissioner"),
    (r"AUDITOR", "county_auditor", "County Auditor"),
    (r"PROSECUT", "county_attorney", "Prosecuting Attorney"),
    (r"CLERK OF (?:THE )?(?:COURTS?|COMMON)", "clerk_of_court", "Clerk of the Court of Common Pleas"),
    (r"SHERIFF", "sheriff", "Sheriff"),
    (r"RECORDER", "county_recorder", "County Recorder"),
    (r"TREASURER", "county_treasurer", "County Treasurer"),
    (r"ENGINEER", "county_engineer", "County Engineer"),
    (r"CORONER", "coroner", "Coroner"),
    (r"FISCAL OFFICER", "county_fiscal_officer", "County Fiscal Officer"),
)
OFFICE_WORDS = {k: w for _p, k, w in COUNTY_OFFICES}
OFFICE_WORDS.update({"court_of_appeals": "Judge of the Court of Appeals", "common_pleas_court": "Judge of the Court of Common Pleas",
                     "county_court": "Judge of the County Court", "council": "Member of Council"})
DIVISIONS = (("General", "GEN", r"\bGENERAL\b|\bGEN\.?\s+DIV"), ("Domestic Relations", "DR", r"DOMESTIC|\bDOM\.?\s*REL"),
             ("Probate", "PROB", r"PROBATE|\bPROB\b"), ("Juvenile", "JUV", r"JUVENILE|\bJUV\b"), ("Drug Court", "DRUG", r"DRUG"))
DIV_CODE = {name: code for name, code, _p in DIVISIONS}
PARTY_ABBR = {"D": "Democratic", "DEM": "Democratic", "DEMOCRAT": "Democratic", "DEMOCRATIC": "Democratic",
              "R": "Republican", "REP": "Republican", "REPUBLICAN": "Republican",
              "L": "Libertarian", "LIB": "Libertarian", "LIBERTARIAN": "Libertarian", "G": "Green", "GRN": "Green", "GREEN": "Green",
              "OPC": "Other-party", "OTHER": "Other-party", "OTHER PARTY": "Other-party", "OTHER-PARTY": "Other-party",
              "OTHER PARTY CANDIDATE": "Other-party", "OTHER-PARTY CANDIDATE": "Other-party",
              "NONPARTY": "Nonparty", "NON-PARTY": "Nonparty", "NONPARTY CANDIDATE": "Nonparty", "NON-PARTY CANDIDATE": "Nonparty",
              "IND": "Independent", "INDEPENDENT": "Independent",
              "N/A": "", "NA": "", "N/P": "", "NONE": "", "NONPARTISAN": "", "NON-PARTISAN": "", "WRITE-IN": "", "WRITE IN": "",
              "WRITE-IN CANDIDATE": ""}
# NOT_A_NAME without its "P.O.": John P. O'Donnell is a name (a box is still caught by its own word)
LOCAL_NOT_A_NAME = re.compile(r"\d|@|www|\.com|\.org|\.net|\bbox\b|\bsuite\b|\bste\b", re.I)
KNOWN_PARTIES = {"Democratic", "Republican", "Libertarian", "Green", "Other-party", "Nonparty", "Independent", "No party", "Write-in"}


def lkey(kind, district="", division="", term="", date="", place=""):
    return LOCAL + "|".join((kind, str(district or ""), division or "", term or "", date or "", place or ""))


def kparts(key):
    kind, district, division, term, date, place = key[len(LOCAL):].split("|")
    return dict(kind=kind, district=district, division=division, term=term, date=date, place=place)


def local_party(p, write_in=False):
    """A party as a county's list writes it (D, Dem., REP, OPC, N/A ...), in the words the state rows use."""
    t = re.sub(r"\s+", " ", (p or "").strip().strip('"').strip()).rstrip(".").upper()
    word = PARTY_ABBR[t] if t in PARTY_ABBR else party_word(p, write_in)
    return word or ("Write-in" if write_in else "No party")


def tidy(text):
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")).strip()


def term_of(text):
    """('F' a full term, 'U' the rest of an unexpired one, or ''; the day it begins or ends as yyyy-mm-dd, or '')."""
    found = []
    for m in DATE_NUM.finditer(text):
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        if 1 <= mo <= 12 and 1 <= d <= 31 and 2026 <= y <= 2036:
            found.append((m.start(), f"{y:04d}-{mo:02d}-{d:02d}"))
    for m in DATE_WORD.finditer(text):
        mo = next(i for i, name in enumerate(MONTHS, start=1) if name.lower().startswith(m.group(1).lower()[:3]))
        if 2026 <= int(m.group(3)) <= 2036:
            found.append((m.start(), f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(2)):02d}"))
    found.sort()
    unexpired = re.search(r"(?i)unexpired|\bUTE\b|term\s+end", text)
    if unexpired:
        after = [d for at, d in found if at >= unexpired.start()]
        return "U", (after[0] if after else (found[-1][1] if found else ""))
    if found or re.search(r"(?i)full\s*term|\bFTC?\b|commenc", text):
        return "F", (found[0][1] if found else "")
    return "", ""


def day_words(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{MONTHS[m - 1]} {d}, {y}"


def seat_words(term, date):
    """As the ballot words a seat (R.C. 3505.04): Full term commencing ..., Unexpired term ending ..."""
    if term == "U":
        return "Unexpired term ending " + day_words(date) if date else "Unexpired term"
    return "Full term commencing " + day_words(date) if date else None


def division_of(text):
    t = text.upper()
    names = [name for name, _code, pat in DIVISIONS if re.search(pat, t)]
    return (" and ".join(names) + " Division") if names else ""


def district_number(text):
    t = text.upper()
    m = re.search(r"(?<!\d)(\d{1,2})\s*(?:ST|ND|RD|TH)?\s+DISTRICT|DISTRICT\s*(\d{1,2})(?!\d)", t)
    if m:
        return int(m.group(1) or m.group(2))
    m = re.search(r"\b(" + "|".join(ORDINALS) + r")\s+DISTRICT", t)
    return ORDINALS.index(m.group(1)) + 1 if m else None


def local_office(text, section="", county=""):
    """The county, court or city office a heading names, as a key, or None for a federal or state office and for a
    line that names no office. section is the title a notice or a list prints over a group of offices; county is the
    county whose board printed the list. An office in a county or city group that fits no pattern comes back as kind
    'unknown' with its own words, so that it is reported and never dropped."""
    t = re.sub(r"\(\s*HELD BY [^)]*\)", " ", tidy(text).upper())
    s = tidy(section).upper()
    appeals = bool(re.search(r"COURTS? OF APPEALS?|APPEALS? (?:COURT|JUDGE)|APPELLATE", t)) or ("COURT OF APPEALS" in s and "JUDGE" in t)
    trial = bool(re.search(r"COMMON PLEAS|COM\.? PLEAS|PROBATE|JUVENILE|DOMESTIC REL|DRUG COURT", t)) and not re.search(r"\bCLERK\b", t)
    if not appeals and not trial:
        if STATE_WORDS.search(t) or STATE_SECTIONS.search(s) or QUESTION.search(t):
            return None
    term, date = term_of(tidy(text))
    if appeals:
        named = district_number(s + " " + t)
        if county not in APPEALS_OF:
            raise ListError(f"Ohio: a court of appeals heading on a list whose county ({county or 'not given'}) is in no appellate district")
        if named is not None and named != APPEALS_OF[county]:
            raise ListError(f"Ohio: {county} County's list names court of appeals district {named}; R.C. 2501.01 puts the county in district "
                            f"{APPEALS_OF[county]}")
        return lkey("court_of_appeals", district=APPEALS_OF[county], term=term or "F", date=date)
    if trial or ("COMMON PLEAS" in s and "JUDGE" in t and not re.search(r"COUNTY COURT|AREA COURT|MUNICIPAL", t)):
        specific = s if re.search(r"COMMON PLEAS", s) and "OR COUNTY COURT" not in s else ""      # Guernsey titles the table with the division
        return lkey("common_pleas_court", division=division_of(specific + " " + t), term=term or "F", date=date)
    if re.search(r"COUNTY COURT|AREA COURT", t) and "JUDGE" in t:
        m = re.search(r"(AREA\s+(?:COURT\s+)?[IVX\d]+|(?:CENTRAL|EASTERN|WESTERN|NORTHERN|SOUTHERN)\s+(?:DISTRICT|AREA))", t)
        return lkey("county_court", district=m.group(1).title() if m else "", term=term or "F", date=date)
    m = re.match(r"^(.+?)\s+(CITY|VILLAGE)\b.*?\bCOUNCIL\b", t)
    if (s == "MUNICIPAL" or m) and "COUNTY COUNCIL" not in t:
        ward = re.search(r"WARD\s+(\d+)|AT[- ]LARGE", t)
        if m and ward:
            where = "At Large" if ward.group(1) is None else f"Ward {int(ward.group(1))}"
            return lkey("council", district=where, term=term, date=date, place=m.group(1).title() + " " + m.group(2).lower())
        return lkey("unknown", place=re.sub(r"[^A-Z0-9 /().,&'-]", "", t)[:90])
    for pat, kind, _words in COUNTY_OFFICES:
        if re.search(pat, t):
            district = ""
            if kind == "county_council":
                n = re.search(r"DISTRICT\s*(\d{1,2})(?!\d)|(?<!\d)(\d{1,2})\s*(?:ST|ND|RD|TH)?\s+DISTRICT", t)
                district = str(int(n.group(1) or n.group(2))) if n else ("At Large" if re.search(r"AT[- ]LARGE", t) else "")
            return lkey(kind, district=district, term="U" if term == "U" else "", date=date if term == "U" else "")
    in_local_group = re.search(r"COUNTY ADMINISTRATIVE|COUNTY EXECUTIVE OFFICES|COMMON PLEAS|^COUNTY$|^JUDICIAL$|^MUNICIPAL$|^TOWNSHIP$|^SCHOOL$|"
                               r"^VILLAGE$|^CITY$", s)
    if (in_local_group or LOCAL_HINT.search(t)) and re.search(r"[A-Z]{4}", t):
        return lkey("unknown", place=re.sub(r"[^A-Z0-9 /().,&'-]", "", t)[:90])
    return None


def office_key(text, section="", county=""):
    """A state race's id (classify), else the key of a county, court or city office, else None."""
    return classify(text) or local_office(text, section, county)


def local_name(text, where):
    """A local candidate's name tidied, or '' when the cell holds something other than a name: it is counted for the
    list it came from and never shown."""
    t = tidy(text).replace("\u2018", "'")
    t = re.sub(r"\s*(?:&|/)\s*|\s+(?:AND|And)\s+", " and ", t).strip()
    t = re.sub(r"\s+and$", "", t).strip(" -,")
    if not t or LOCAL_NOT_A_NAME.search(t) or not NAME_OK.match(t) or contact_like(t, True) or len(t) > 70:
        BLANKED[where.split(" ")[0]] += 1
        return ""
    return t


# ---------------------------------------------------------------- the nine readers

def franklin(path):
    """Printed turned on its side: each column is a band across the page, each candidate a position along it. Only the
    Name on Ballot, Party, Office, Write-In and term bands are read. A ticket's governor sits on the line before the
    line that carries the office; a name the printer broke into pieces is joined along the band."""
    pdf = PDF(open(path, "rb").read())
    keys = ("Name on Ballot", "Party", "Office", "Write-In", "Full Or Unexpired Term", "Term Commencing")
    band, out = {}, []      # county offices and judges are kept too, with the Full Or Unexpired Term band beside the term date
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        if not band:
            band = {r[3].strip(): r[1] for r in runs if r[0] < 70 and r[3].strip() in keys}
            if len(band) != len(keys) or not band["Name on Ballot"] < band["Party"] < band["Office"]:
                raise ListError(f"Ohio franklin: the list's bands changed (found {sorted(band)})")

        def cells(k):
            return [(r[0], r[3].strip()) for r in runs if abs(r[1] - band[k]) < 3 and r[0] >= 60 and r[3].strip() != k]
        office, party, wi, term = cells("Office"), cells("Party"), cells("Write-In"), cells("Term Commencing")
        whole = cells("Full Or Unexpired Term")
        lo, hi = band["Name on Ballot"] - 3, band["Party"] - 3
        pieces = {}
        for r in runs:
            if r[0] >= 60 and lo <= r[1] < hi and r[3].strip() != "Name on Ballot":
                x = next((x for x in pieces if abs(x - r[0]) < 1.5), r[0])
                pieces.setdefault(x, []).append((r[1], r[3]))
        names = {x: re.sub(r"\s+", " ", "".join(t for _y, t in sorted(v))).strip() for x, v in pieces.items()}
        oxs = [x for x, _t in office]
        lead = {}      # office x -> a governor line printed just before it
        for x in names:
            if any(abs(x - ox) < 3 for ox in oxs):
                continue
            nxt = [ox for ox in oxs if 0 < ox - x <= 13]
            if nxt:
                lead[min(nxt)] = names[x]
        for i, (x, text) in enumerate(office):
            tm = [t for x2, t in term if abs(x2 - x) < 3]
            race = classify(text + " " + " ".join(tm))
            if not race:
                race = local_office(" ".join([text] + [t for x2, t in whole if abs(x2 - x) < 3] + tm), county="Franklin")
            if not race:
                continue
            here = [t for x2, t in names.items() if abs(x2 - x) < 3]
            pty = [t for x2, t in party if abs(x2 - x) < 3]
            if len(here) != 1 or len(pty) > 1:
                raise ListError(f"Ohio franklin: row {i + 1} of page {n} does not line up across the list's bands ({race})")
            name = ((lead.get(x, "") + " ") if lead.get(x) else "") + here[0]
            w = any(abs(x2 - x) < 3 and t == "Yes" for x2, t in wi)
            out.append(cand(race, clean_name(name, f"franklin page {n} row {i + 1} ({race})"), pty[0] if pty else "", w))
    return out


def cuyahoga(path):
    """Candidate Name, Party, Filed and Valid columns (the list prints no contact details); each office's heading is a
    'For ...' line with its district and term on the lines under it."""
    out, head, race = [], [], None
    for p, _y, rs in fed.printed_rows(path):
        left = fed.col(rs, 0, 230)
        filed = fed.col(rs, 390, 470)
        if left.startswith("For "):
            head, race = [left], None
            continue
        if head and left.startswith("(") and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", filed):
            head.append(left)
            continue
        if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", filed) or not head:
            continue
        if race is None:
            race = office_key(" ".join(head), county="Cuyahoga") or ""
        if not race:
            continue
        valid = fed.col(rs, 470, 700)
        name = clean_name(fed.col(rs, 30, 230), f"cuyahoga page {p} ({race})")
        party = fed.col(rs, 230, 390).split("|")[0].strip()
        out.append(cand(race, name, party, "Write-In" in valid, not valid.startswith("Yes")))
    return out


LAKE_PARTY = {"D", "R", "L", "G", "Nonparty", "Non-Party", "Other-party", "Other Party", "Independent"}
LAKE_SECTION = re.compile(r"(FEDERAL|STATE|COUNTY|JUDICIAL|MUNICIPAL|TOWNSHIP|SCHOOL|VILLAGE|CITY)OFFICES(?:CONTINUED)?")


def lake(path):
    """Office, Party and Name columns; the address and city columns to the right are never taken in (a name cell stops
    at the first piece that starts with a digit). Offices are grouped under FEDERAL, STATE, COUNTY, JUDICIAL and
    MUNICIPAL OFFICES; only the STATE and JUDICIAL groups are read. A heading's lines run down the first column above
    and beside its PARTY / NAME row; a running mate follows on a line of its own that begins 'and'."""
    out, section, pending, race = [], None, [], None
    table = list(fed.printed_rows(path))
    for i, (p, y, rs) in enumerate(table):
        mid = re.sub(r"\s+", "", cut_name(rs, 250, 500)).upper()
        sec = LAKE_SECTION.fullmatch(mid)
        if sec:
            section, pending, race = sec.group(1), [], None
            continue
        left, party = fed.col(rs, 0, 185), fed.col(rs, 185, 250)
        if party.replace(" ", "") == "PARTY":
            below = [fed.col(r2, 0, 185) for p2, y2, r2 in table[i + 1:i + 3] if p2 == p and 0 < y - y2 <= 16]
            label = " ".join(pending + [left] + below)
            race = classify(label) if section in ("STATE", "JUDICIAL") else None
            if race is None and section in ("COUNTY", "JUDICIAL", "MUNICIPAL"):
                beside = []      # a county, court or city office: its heading can run on down the first column beside the candidates
                for p2, _y2, r2 in table[i + 1:]:
                    mid2 = re.sub(r"\s+", "", cut_name(r2, 250, 500)).upper()
                    if p2 != p or fed.col(r2, 185, 250).replace(" ", "") == "PARTY" or LAKE_SECTION.fullmatch(mid2):
                        break
                    left2 = fed.col(r2, 0, 185)
                    if left2 and not (fed.col(r2, 185, 250) or mid2):
                        break      # a line with nothing beside it opens the next office
                    if left2:
                        beside.append(left2)
                race = local_office(" ".join(pending + [left] + beside), section, "Lake")
            pending = []
            continue
        if party and party not in LAKE_PARTY:
            party = ""      # a long heading spilling into the party column
        name = cut_name(rs, 250, 500) if (party or race) else ""
        if not party and not name:
            if left:
                pending.append(left)
            continue
        pending = []
        if not race:
            continue
        where = f"lake page {p} ({race})"
        if race.startswith(LOCAL) and name.startswith("*"):
            if re.match(r"\*\s*Certified\b", name):
                continue      # the footnote under a block ("*Certified on ..."), not a candidate
            name = name.lstrip("* ")
        if not party and name.lower().startswith("and ") and out and out[-1]["race"] == race:
            out[-1]["name"] = clean_name(out[-1]["name"] + " " + name, where)
            continue
        wi = bool(re.search(r"\(\s*Write-?\s*in\s*\)", name, re.I))
        name = re.sub(r"\s*\(\s*Write-?\s*in\s*\)", "", name, flags=re.I)
        out.append(cand(race, clean_name(name, where), party, wi))
    return out


LORAIN_PARTY = fed.LORAIN_PARTY


def lorain(path):
    """Candidate and Party columns (the contact column is never read). Candidates start at the left margin; an office
    heading is set in a little and may run across the columns (read no further than the Filed column). A ticket's
    name can break after its slash onto the next row, which repeats the party."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        x0 = rs[0][0]
        if 25 <= x0 < 40:
            race = office_key(fed.col(rs, 0, 520), county="Lorain")
            continue
        if x0 >= 25:
            continue
        name, party = fed.col(rs, 15, 185), fed.col(rs, 185, 300)
        if not race or not name:
            continue
        if party not in LORAIN_PARTY and not (race.startswith(LOCAL) and not party):      # a judge can be listed with no party
            raise ListError(f"Ohio lorain: a candidate for {race} with a party the loader does not know (page {p})")
        where = f"lorain page {p} ({race})"
        if out and out[-1]["race"] == race and out[-1]["_open"]:
            out[-1]["name"] = clean_name(out[-1]["_raw"] + " " + name, where)
            out[-1]["_open"] = False
            continue
        wi = party == "Write-In"
        c = cand(race, "", "" if wi else party, wi)
        c["_raw"], c["_open"] = name, name.rstrip().endswith("/")
        c["name"] = name if c["_open"] else clean_name(name, where)
        out.append(c)
    for c in out:
        if c.pop("_open"):
            raise ListError(f"Ohio lorain: a ticket for {c['race']} breaks off at the end of the list")
        c.pop("_raw")
    return out


def stark(path):
    """Status and Name columns under a party heading (the address and telephone columns are never read). A name can wrap
    onto the next line (a line with no status just under a candidate); an office heading has text in the status
    column."""
    out, race, party, last, at = [], None, "", None, None
    for p, y, rs in fed.printed_rows(path):
        left, name = fed.col(rs, 0, 150), fed.col(rs, 150, 280)
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d\d:\d\d [AP]M|Page \d+.*", left):
            continue
        if left in fed.STARK_ON or left in fed.STARK_OFF:
            last = None
            if race and name:
                wi = left == "Write In"
                last = cand(race, name, "" if wi else party, wi, left in fed.STARK_OFF)
                out.append(last)
                at = (p, y)
            continue
        if left:
            race, party, last = office_key(join([r for r in rs if r[0] < 600]), county="Stark"), "", None
            continue
        if not name:
            continue
        if last is not None and at[0] == p and 0 < at[1] - y < 12:
            last["name"] += " " + name
            at = (p, y)
            continue
        party, last = name, None
    for i, c in enumerate(out):
        c["name"] = clean_name(c["name"], f"stark candidate {i + 1} ({c['race']})")
    return out


WOOD_PARTY = re.compile(r"^(Democratic|Republican|Libertarian|Green|Independent|Other-party candidate|Nonparty candidate|Write-In Candidate)$")


def wood(path):
    """A party (or Write-In Candidate) in the first column, the name after it (a running mate in a second name column);
    addresses sit on the next row, which has no party, and are never read."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        left = fed.col(rs, 0, 190)
        if WOOD_PARTY.match(left):
            if race:
                wi = left == "Write-In Candidate"
                where = f"wood page {p} ({race})"
                if race.endswith("-GOV"):
                    name = fed.col(rs, 190, 330) + " and " + fed.col(rs, 330, 480)
                else:
                    name = fed.col(rs, 190, 480)
                out.append(cand(race, clean_name(name, where), "" if wi else left, wi))
            continue
        if left and not re.match(r"(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day, ", left):
            race = office_key(join([r for r in rs if r[0] < 700]), county="Wood")
        elif not left and race and race.startswith(LOCAL + "common_pleas") and 188 <= rs[0][0] < 290 and rs[0][2] > 12.5:
            # a judge: no party in the first column, the name alone in the name column's larger type (addresses are smaller, further right)
            name = join([r for r in rs if 188 <= r[0] < 480 and r[2] > 12.5])
            out.append(cand(race, clean_name(name, f"wood page {p} ({race})"), "", False))
    return out


def butler(path):
    """One line per candidate: (party) name, then where the candidate files or the petition dates, and Withdrawn.
    Write-in candidates the report prints without names are not read; the report prints its blocks twice."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        text = join(rs)
        if not text.startswith("(") and re.search(r"Vote\s*for\s*not", text, re.I):
            race = office_key(text, county="Butler")
            continue
        m = re.match(r"^\((\w)\) (.+?)(?: Files with .*| \(P\) .*)?$", text)
        if not (m and race):
            continue
        name = m.group(2).strip()
        name = re.sub(r"\s+Withdrawn$", "", name)
        if name == "Write-in Candidate":
            UNNAMED["butler", race] += 1
            continue
        letter = m.group(1).upper()
        out.append(cand(race, clean_name(name, f"butler page {p} ({race})"), "" if letter == "N" else letter, False, "Withdrawn" in text))
    seen, kept = {}, []
    for c in out:
        k = (c["race"], c["name"])
        if k in seen:
            if seen[k]["gone"] != c["gone"]:
                if not c["race"].startswith(LOCAL):
                    raise ListError(f"Ohio butler: the two printings of {c['race']} disagree on who withdrew")
                seen[k]["gone"] = True      # a county or court race: the withdrawal one printing carries stands
            continue
        seen[k] = c
        kept.append(c)
    return kept


def union(path):
    """The notice's Name of Candidate (Party) and Office columns; each office's block opens on the row that names its
    precincts. Write-in candidates follow a WRITE-IN CANDIDATES line, each after a bullet, a long one wrapping onto the
    next line. The notice prints only the governor's name for a ticket. Reading stops at the issues."""
    blocks = []
    for _p, _y, rs in fed.printed_rows(path):
        name = fed.col(rs, 30, 245)
        if re.match(r"(State|District) Issues?\b", name):
            break
        right = join([r for r in rs if r[0] >= 245])
        if re.search(r"Precincts$", right) and "Name of Candidate" not in join(rs):
            blocks.append({"office": [], "names": []})
        if not blocks:
            continue
        blocks[-1]["office"].append(re.sub(r"\s*All Precincts$", "", right))
        if name:
            blocks[-1]["names"].append(name)
    out = []
    for b in blocks:
        race = office_key(" ".join(b["office"]), county="Union")
        if not race:
            continue
        wi, items = False, []
        for line in b["names"]:
            if line.upper().startswith("WRITE-IN CANDIDATES"):
                wi = True
                continue
            bullet = bool(re.match(r"^[\u2022\x95\ufffd\u00b7]", line))
            line = re.sub(r"^[\u2022\x95\ufffd\u00b7]\s*", "", line)
            if wi and not bullet and items and items[-1][1]:
                items[-1][0] += " " + line
                continue
            items.append([line, wi])
        for i, (line, w) in enumerate(items):
            m = re.match(r"^(.+?)\s*\((Dem|Rep|Lib|Grn)\)$", line)
            name = clean_name(proper(m.group(1) if m else line), f"union row {i + 1} ({race})")
            out.append(cand(race, name, m.group(2) if m else "", w, note=CAPS_NOTE))
    return out


HAM_OFFICE = re.compile(r"^(U\.\s?S\.|State |Judge|Justice|Member|County|Governor|Attorney|Auditor|Secretary|Treasurer|Ohio )")


def hamilton(path):
    """The notice's name (x 38-175), office (175-295) and party (295-385) columns; the precinct column is never read.
    Sections open with a title and a 'Name of Candidate' row; an office's block opens where its title starts. A name or
    party that wraps continues on the line just under it; candidates are about two lines apart. Reading stops at the
    county courts."""
    rows = []
    for p, y, rs in fed.printed_rows(path):
        whole = join([r for r in rs if r[0] < 385])
        if re.match(r"County Court|County Offices|Municipal|Township|School", whole):
            break
        rows.append((p, y, fed.col(rs, 38, 175), fed.col(rs, 175, 295), fed.col(rs, 295, 385), "Name of Candidate" in whole))
    drop = set()
    for i, (p, y, *_rest, header) in enumerate(rows):
        if header:
            drop.add(i)
            for j in range(i - 1, -1, -1):      # a section's title lines just above its header row
                if rows[j][0] != p or rows[j][1] - y > 50:
                    break
                drop.add(j)
    blocks, last = [], None
    for i, (p, y, name, office, party, header) in enumerate(rows):
        if i in drop:
            if header:
                last = None
            continue
        if office and HAM_OFFICE.match(office):
            blocks.append({"office": [], "cands": []})
            last = None
        if not blocks:
            continue
        b = blocks[-1]
        if office:
            b["office"].append(office)
        if name:
            if last is not None and last[0] == p and 0 < last[1] - y < 15:
                b["cands"][-1][0] += " " + name
            else:
                b["cands"].append([name, party])
            last = (p, y)
        elif party and b["cands"]:
            b["cands"][-1][1] = (b["cands"][-1][1] + " " + party).strip()
    out = []
    for b in blocks:
        race = classify(" ".join(b["office"]))
        if not race:
            continue
        for k, (name, party) in enumerate(b["cands"]):
            name = re.sub(r"\(Write-\s+In\)", "(Write-In)", name)
            wi = bool(re.search(r"\(Write-?\s?In\)", name, re.I))
            name = re.sub(r"\s*\(Write-?\s?In\)\s*", " ", name, flags=re.I).strip()
            out.append(cand(race, clean_name(name, f"hamilton {race} row {k + 1}"), party, wi))
    return out


READERS = {"franklin": franklin, "cuyahoga": cuyahoga, "lake": lake, "lorain": lorain, "stark": stark, "wood": wood,
           "butler": butler, "union": union, "hamilton": hamilton}


# ---------------------------------------------------------------- the 46-day notices: two layouts, read by their headings
#
# Every board posts an "Election Notice for use with the Federal Write-In Absentee Ballot" 46 days before the election
# (R.C. 3511.16): names, offices, parties and precincts, no addresses. Boards print it in one of two layouts. One has
# three columns, "Name of Candidate (Party) | Office, To Elect, Term | Precincts" (Union, Warren, Delaware, Wayne); the
# other is the Secretary of State's Form 120, a table for each group of offices under a title ("Ohio Court of Appeals
# (3rd District)"), with the columns "Name of Candidate | Office | Party | Precincts" in whatever order and width the
# board typed them. Both readers find their columns from the heading row of each table and never read the precincts.

TAG = re.compile(r"[\(\[]\s*(Dem(?:ocrat(?:ic)?)?|Rep(?:ublican)?|Lib(?:ertarian)?|Grn|Green|Other(?:[- ]?party)?(?:\s+candidate)?|"
                 r"Non-?party(?:\s+candidate)?|Independent|Ind|Write[- ]?In)\.?\s*[\)\]]", re.I)
JOINER = re.compile(r"(?:/|&|\band|,|-)$", re.I)
BULLET = re.compile(r"^[\u2022\x95\ufffd\xb7]\s*")
CELL_GAP = 18.5      # lines of one table cell sit closer than this; a new row of a typed table starts further down
FORM_TITLE = re.compile(r"(?i)\(?(StateExecutiveOffices|OhioSupremeCourt|U\.?S\.?SenateandU\.?S\.?Congress|OhioGeneralAssembly|"
                        r"OhioCourtofAppeals|CountyCourtofCommonPleas|CountyAdministrativeOffices|CountyExecutiveOffices)")


def xruns(pdf, page, res):
    """pdftext.page_runs, also following forms: some boards' notices draw each page's text inside a form (the page's
    own stream only places it), which page_runs does not open."""
    runs = []

    def draw(data, res, ctm, depth):
        fonts = {}
        r = pdf.get(res) or {}
        fres, xres = pdf.get(r.get("Font")) or {}, pdf.get(r.get("XObject")) or {}
        saved = []
        tm = tlm = [1, 0, 0, 1, 0, 0]
        font, size, tc, tw, th, tl, rise = None, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
        for op, a in _ops(data):
            if op == "q":
                saved.append(ctm[:])
            elif op == "Q":
                ctm = saved.pop() if saved else [1, 0, 0, 1, 0, 0]
            elif op == "cm" and len(a) == 6:
                ctm = _mul([float(x) for x in a], ctm)
            elif op == "BT":
                tm = tlm = [1, 0, 0, 1, 0, 0]
            elif op == "Tf" and len(a) == 2:
                name = str(a[0])
                if name not in fonts:
                    fonts[name] = Font(pdf, fres.get(name))
                font, size = fonts[name], float(a[1])
            elif op == "Tc" and a:
                tc = float(a[0])
            elif op == "Tw" and a:
                tw = float(a[0])
            elif op == "Tz" and a:
                th = float(a[0]) / 100
            elif op == "TL" and a:
                tl = float(a[0])
            elif op == "Ts" and a:
                rise = float(a[0])
            elif op in ("Td", "TD") and len(a) == 2:
                if op == "TD":
                    tl = -float(a[1])
                tlm = _mul([1, 0, 0, 1, float(a[0]), float(a[1])], tlm)
                tm = tlm
            elif op == "Tm" and len(a) == 6:
                tm = tlm = [float(x) for x in a]
            elif op == "T*" or op in ("'", '"'):
                tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
                tm = tlm
                if op == '"' and len(a) == 3:
                    tw, tc = float(a[0]), float(a[1])
            if op == "Do" and a and depth < 4:
                ref = xres.get(str(a[-1]))
                form = pdf.get(ref)
                if isinstance(ref, Ref) and isinstance(form, dict) and form.get("Subtype") == "Form":
                    m = pdf.get(form.get("Matrix")) or [1, 0, 0, 1, 0, 0]
                    draw(pdf.stream(ref) or b"", form.get("Resources") or res, _mul([float(x) for x in m], ctm), depth + 1)
                continue
            shown = [a[-1]] if op in ("Tj", "'", '"') and a else (a[-1] if op == "TJ" and a and isinstance(a[-1], list) else [])
            for item in shown:
                if isinstance(item, (int, float)):
                    tm = _mul([1, 0, 0, 1, -float(item) / 1000.0 * size * th, 0], tm)
                elif isinstance(item, (bytes, bytearray)) and font is not None:
                    text, codes = font.decode(item)
                    trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
                    adv = sum((font.width(c) * size + tc + (tw if (not font.two and c == 32) else 0)) * th for c in codes)
                    tm = _mul([1, 0, 0, 1, adv, 0], tm)
                    if text.strip():
                        runs.append((trm[4], trm[5], abs(trm[3]) or size, text, _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))[4]))

    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    draw(b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, Ref)), res, [1, 0, 0, 1, 0, 0], 0)
    return runs


def notice_rows(data):
    """[(page, y, runs left to right)] for every printed row of a notice, top to bottom."""
    pdf, out = PDF(data), []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        rows = []
        for r in sorted(xruns(pdf, page, res), key=lambda r: (-round(r[1], 1), r[0])):
            if rows and abs(rows[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
                rows[-1][1].append(r)
            else:
                rows.append([r[1], [r]])
        out.extend((n, y, sorted(rs, key=lambda r: r[0])) for y, rs in rows)
    return out


def squeeze(text):
    return re.sub(r"\s+", "", text or "")


def label_starts(rs, labels):
    """{label: x where it starts} for a heading row's column labels (each a pattern), whatever pieces the row was
    printed in."""
    whole, at = "", []
    for r in rs:
        at.append((len(whole), r[0]))
        whole += squeeze(r[3])
    out = {}
    for label in labels:
        m = re.search(label, whole)
        if m:
            out[label] = max(x for pos, x in at if pos <= m.start())
    return out


NAME_LABEL = r"Name\(?s?\)?of(?:Joint)?Candidate"      # "Name of Candidate", "Name(s) of Joint Candidates / Candidate"


def form_heading(t):
    """True for the heading row of a Form 120 table: the candidate and office columns, and a party or precinct column."""
    return bool(re.search(NAME_LABEL, t)) and "Office" in t and ("Party" in t or "Precincts" in t)


def notice_kind(rows):
    for _p, _y, rs in rows:
        t = squeeze(join(rs))
        if "NameofCandidate(Party)" in t:
            return "columns"
        if form_heading(t):
            return "form120"
    return None


def is_superscript(r):
    return r[2] < 8.6 and re.fullmatch(r"(?i)(st|nd|rd|th)", r[3].strip() or "x")


def cell(rs, lo, hi):
    return join([r for r in rs if lo <= r[0] < hi and not is_superscript(r)])


def mark_name(text):
    """(name, party as printed, write-in) from a name cell: 'Jane Roe (Rep)', '(Dem) Jane Roe', 'Write In- Jane Roe',
    'Jane Roe [WRITE-IN]', 'Jane Roe - Write-In', '(Jane Roe) (Write-in)'."""
    t, party, wi = tidy(text), "", False
    for m in TAG.finditer(t):
        if m.group(1).lower().startswith("write"):
            wi = True
        else:
            party = m.group(1)
    t = TAG.sub(" ", t)
    for pat in (r"(?i)^\s*write[- ]?in\s*[-:]?\s*", r"(?i)\s*-?\s*write[- ]?in\s*$"):
        if re.search(pat, t):
            wi, t = True, re.sub(pat, "", t)
    t = tidy(t).strip(" -")
    if t.startswith("(") and t.endswith(")") and t.count("(") == 1:
        t = t[1:-1].strip()
    return t, party, wi


def column_notice(rows, where):
    """The three-column notice. An office's block opens on the row that carries its title and runs until its term date
    has been printed; the candidates are the lines beside and below it in the first column. A name that wraps continues
    on the next line (a line that is only a party mark, a line after one that ends with 'and' or '/', a line set in a
    little, one word alone, or, where the notice leaves a blank line between candidates, any line close under the last)."""
    start = next((i for i, (_p, _y, rs) in enumerate(rows) if "NameofCandidate(Party)" in squeeze(join(rs))), None)
    if start is None:
        raise ListError(f"Ohio {where}: the notice has no 'Name of Candidate (Party)' heading row")
    x = label_starts(rows[start][2], ("Office", "Precincts"))
    if len(x) != 2 or not x["Office"] < x["Precincts"]:
        raise ListError(f"Ohio {where}: the notice's heading row does not name the Office and Precincts columns")
    x1, x2 = x["Office"] - 2, x["Precincts"] - 2
    blocks, cur = [], None
    for p, y, rs in rows[start + 1:]:
        name, office = cell(rs, 0, x1), cell(rs, x1, x2)
        both = cell(rs, 0, x2)
        if re.match(r"(?i)(all\s+)?issues?\b|(state|district|local|county)\s+issues?\b|entity, overlaps", name) or \
                re.fullmatch(r"(?i)(all\s+)?issues", both):
            break
        if re.match(r"Page \d+ of \d+", office) or re.match(r"Page \d+ of \d+", both) or "NameofCandidate(Party)" in squeeze(both):
            continue
        if office:
            if cur is None or cur["closed"]:
                cur = {"section": "", "office": [], "lines": [], "closed": False, "elect": False}
                blocks.append(cur)
            cur["office"].append(office)
            cur["elect"] = cur["elect"] or bool(re.search(r"(?i)to be elected", office))
            if cur["elect"] and DATE_NUM.search(office):
                cur["closed"] = True
        if name and cur is not None:
            cur["lines"].append((p, y, min(r[0] for r in rs if r[0] < x1), name))
    gaps = []      # how far under a candidate's closing party mark the next line sits: about a line (tight) or two (spaced)
    for b in blocks:
        for (p1, y1, _x1, t1), (p2, y2, _x2, t2) in zip(b["lines"], b["lines"][1:]):
            if p1 == p2 and re.search(r"[\)\]]\s*$", t1) and TAG.search(t1) and TAG.sub("", t2).strip():
                gaps.append(y1 - y2)
    spaced = bool(gaps) and sorted(gaps)[len(gaps) // 2] >= 20
    out = []
    for b in blocks:
        base = min((x0 for _p, _y, x0, _t in b["lines"]), default=0)
        cands, c, wi_mode, prev = [], None, False, None
        for p, y, x0, raw in b["lines"]:
            t = tidy(raw)
            if re.match(r"(?i)write-?in candidates?\s*:?$", t):
                wi_mode, c, prev = True, None, None
                continue
            bullet = bool(BULLET.match(t))
            t = BULLET.sub("", t)
            if re.match(r"(?i)(withdrawn|withdrew)\b", t):
                if c is not None:
                    c["gone"] = True
                prev = (p, y)
                continue
            if re.match(r"(?i)write[- ]?in\s*[-:]", t):
                wi_mode = True
            cont = False
            if c is not None and not bullet:
                last = c["parts"][-1]
                gap = prev[1] - y if prev and prev[0] == p else None
                if not TAG.sub("", t).strip(" ()[]") or re.fullmatch(r"(?i)candidate\)?", t) or last.count("(") > last.count(")"):
                    cont = True
                elif JOINER.search(last.strip()):
                    cont = True
                elif 4 < x0 - base < 16:
                    cont = True
                elif c["closed"]:
                    cont = False
                elif " " not in t.strip():
                    cont = True
                elif spaced and gap is not None and gap <= 16.5:
                    cont = True
            if cont:
                c["parts"].append(t)
            else:
                c = {"parts": [t], "wi": wi_mode, "gone": False, "closed": False}
                cands.append(c)
            if TAG.search(t) and re.search(r"[\)\]]\s*$", t):
                c["closed"] = True
            prev = (p, y)
        people = []
        for c in cands:
            name, party, wi = mark_name(" ".join(c["parts"]))
            people.append({"name": name, "party": party, "write_in": wi or c["wi"], "gone": c["gone"]})
        out.append({"section": "", "office": " ".join(b["office"]), "cands": people})
    return out


def form_notice(rows, where):
    """The Form 120 notice. Each table has its own heading row, which gives the columns; the title over the table says
    which group of offices it is. Lines closer together than CELL_GAP are one cell (an office's title and term, a name
    that wraps); a notice that sets its candidates one to a line, with a party beside each (Hancock) or after each name
    (Williams, whose tables have no party column), is read line by line. A candidate belongs to the office whose cell
    begins beside or above it. Reading stops at the issues."""
    heads, stop = [], len(rows)
    for i, (_p, _y, rs) in enumerate(rows):
        t = squeeze(join(rs))
        if form_heading(t):
            heads.append(i)
        elif re.fullmatch(r"(Number)?Title.*Precincts", t) or re.fullmatch(r"(?i)(local|state|county|district)?(questions?and)?issues?", t):
            stop = i
            break
    heads = [i for i in heads if i < stop]
    if not heads:
        raise ListError(f"Ohio {where}: the notice has no 'Name of Candidate' heading row")
    titles, title_rows = {}, set()
    for i in heads:      # the title lines just over each table's heading row
        lines, j = [], i - 1
        page = rows[i][0]
        while j >= 0 and rows[j][0] == page and j not in heads:
            if rows[j][1] - rows[j + 1][1] > (45 if j == i - 1 else CELL_GAP):
                break
            lines.append(j)
            j -= 1
        if not lines and i - 1 >= 0 and rows[i - 1][0] != page:      # a table that opens a page: its title can close the page before
            tail, j = [], i - 1
            while j >= 0 and rows[j][0] == rows[i - 1][0] and len(tail) < 4 and (not tail or rows[j][1] - rows[j + 1][1] <= CELL_GAP):
                tail.append(j)
                if FORM_TITLE.match(squeeze(join(rows[j][2]))):
                    lines = tail[:]
                    break
                j -= 1
        title_rows.update(lines)
        titles[i] = tidy(" ".join(join(rows[k][2]) for k in reversed(lines)))
    for i, (_p, _y, rs) in enumerate(rows[:stop]):      # and any line that is one of the form's own titles, wherever it falls
        if FORM_TITLE.match(squeeze(join(rs))):
            title_rows.add(i)
    tables, section = [], ""
    for n, i in enumerate(heads):
        cols = label_starts(rows[i][2], (NAME_LABEL, "Office", "Party", "Precincts"))
        cols["NameofCandidate"] = cols.pop(NAME_LABEL, None)
        if cols["NameofCandidate"] is None or "Office" not in cols:
            raise ListError(f"Ohio {where}: a table's heading row does not name the candidate and office columns")
        section = titles.get(i) or section      # a table that runs on under a repeated heading keeps its title
        order = sorted((xx, k) for k, xx in cols.items())
        span = {k: ((xx - 2) if a else 0, (order[a + 1][0] - 2) if a + 1 < len(order) else 99999) for a, (xx, k) in enumerate(order)}
        end = heads[n + 1] if n + 1 < len(heads) else stop
        body = [rows[k] for k in range(i + 1, end) if k not in title_rows]
        lines = {k: [(p, y, cell(rs, *span[k])) for p, y, rs in body if k in span and cell(rs, *span[k])]
                 for k in ("NameofCandidate", "Office", "Party")}
        lines["NameofCandidate"] = [x for x in lines["NameofCandidate"]      # the heading's own second lines are not candidates
                                    if not re.fullmatch(r"(?i)candidates?|\(?vote\s+for\b.*", x[2].strip())]
        tables.append((section, lines))

    def beside(party_lines, p, top, bot):
        return " ".join(t for pp, y, t in party_lines if pp == p and bot - 3 <= y <= top + 3)

    def closed(t):      # a line that ends with its party mark: "Jane Roe (Rep)"
        return bool(TAG.search(t)) and bool(re.search(r"[\)\]]\s*$", t))

    tight = False
    for _section, lines in tables:
        for (p1, y1, _t1), (p2, y2, _t2) in zip(lines["NameofCandidate"], lines["NameofCandidate"][1:]):
            if p1 == p2 and 0 < y1 - y2 < CELL_GAP and ((beside(lines["Party"], p1, y1, y1) and beside(lines["Party"], p2, y2, y2))
                                                         or (closed(_t1) and closed(_t2))):
                tight = True

    def cells(lines, each_line=False):
        out = []
        for p, y, t in lines:
            last = out[-1] if out else None
            near = last is not None and last["page"] == p and 0 <= last["bot"] - y <= CELL_GAP
            if near and each_line:
                before = last["lines"][-1]
                near = bool(JOINER.search(before.strip())) or not TAG.sub("", t).strip(" ()[]") or before.count("(") > before.count(")") \
                    or (" " not in TAG.sub("", t).strip() and not closed(before))
            if near:
                last["lines"].append(t)
                last["bot"] = y
            else:
                out.append({"page": p, "top": y, "bot": y, "lines": [t]})
        return out

    blocks, orphans = [], 0
    for section, lines in tables:
        offices = [dict(c, section=section, cands=[]) for c in cells(lines["Office"])]
        for c in cells(lines["NameofCandidate"], each_line=tight):
            here = [o for o in offices if o["page"] == c["page"] and o["top"] >= c["top"] - 6]
            before = [o for o in offices if o["page"] < c["page"]]
            home = min(here, key=lambda o: o["top"]) if here else (before[-1] if before else (blocks[-1] if blocks and not offices else None))
            person_here = cell_cand(" ".join(c["lines"]), beside(lines["Party"], c["page"], c["top"], c["bot"]))
            if person_here is None:
                continue
            if home is None:
                orphans += 1
                continue
            home["cands"].append(person_here)
        blocks.extend(offices)
    if orphans:
        raise ListError(f"Ohio {where}: {orphans} candidate cells of the notice sit under no office")
    return [{"section": o["section"], "office": " ".join(o["lines"]), "cands": o["cands"]} for o in blocks]


def cell_cand(text, pcell=""):
    """A candidate from a name cell and the party cell beside it, or None for a line that is no candidate ("No Valid
    Petition Filed", "No other candidates ... filed"). A cell that says the candidate withdrew is marked gone."""
    if re.match(r"(?i)no (other|valid)\b", text):
        return None
    gone = bool(re.search(r"(?i)withdr[ae]w|will not be counted", text))
    if gone:
        text = re.split(r"(?i)\s*[-(]?\s*(?:candidate\s+)?withdr[ae]w", text)[0]
    name, party, wi = mark_name(text)
    if re.fullmatch(r"(?i)write[- ]?in(\s+candidate)?", pcell.strip()):
        wi, pcell = True, ""
    return {"name": name, "party": pcell or party, "write_in": wi, "gone": gone}


WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_notice(data, where):
    """The Form 120 notice as a Word file (Sandusky): its tables row by row. A row of one cell is the title of a group
    of offices; the heading row names the columns; every other row is one candidate with the office and party beside
    the name. Returns the blocks and the document's own text (to see which election it is for)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml"))
    except (KeyError, zipfile.BadZipFile, ET.ParseError):
        raise ListError(f"Ohio {where}: the file is not a Word document the loader can open") from None

    def words(el):
        paras = ("".join(t.text or "" for t in p.iter(WORD + "t")) for p in el.iter(WORD + "p"))
        return tidy(" ".join(x for x in paras if x.strip()))

    blocks, section, cols, done = [], "", None, False
    for tbl in root.iter(WORD + "tbl"):
        for tr in tbl.findall(WORD + "tr"):
            cells = [words(tc) for tc in tr.findall(WORD + "tc")]
            filled = [c for c in cells if c]
            t = squeeze(" ".join(cells))
            if not filled or done:
                continue
            if re.fullmatch(r"(Number)?Title.*Precincts", t) or re.fullmatch(r"(?i)(local|state|county|district)?(questions?and)?issues?", t):
                done = True
            elif form_heading(t):
                cols = {k: next((i for i, c in enumerate(cells) if re.search(pat, squeeze(c))), None)
                        for k, pat in (("name", NAME_LABEL), ("office", "^Office"), ("party", "^Party"))}
                if cols["name"] is None or cols["office"] is None:
                    raise ListError(f"Ohio {where}: a table's heading row does not name the candidate and office columns")
            elif len(filled) == 1 and (len(cells) == 1 or cols is None):
                section, cols = filled[0], None
            elif cols is not None and len(cells) > max(v for v in cols.values() if v is not None):
                one = cell_cand(cells[cols["name"]], cells[cols["party"]] if cols["party"] is not None else "")
                if one is not None and cells[cols["name"]]:
                    blocks.append({"section": section, "office": cells[cols["office"]], "cands": [one]})
    return blocks, words(root)


def csv_list(data, where):
    """Ottawa's candidate file: one row a candidate, the columns found by their names. Only the district, office, term,
    status, write-in, ballot name, party and election date cells are read (the file has no contact columns)."""
    import csv
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig", "replace"))))
    if not rows or not all(c in rows[0] for c in CSV_COLUMNS):
        raise ListError(f"Ohio {where}: the candidate file's columns are not the ones the loader knows")
    blocks = []
    for r in rows:
        unexpired = (r["Unexpired Term (YES/NO)"] or "").strip().upper() == "YES"
        office = tidy(f"{r['Office Title 1']} {r.get('Office Title 2') or ''} "
                      + (f"Unexpired term ending {r['Term Ending Date']}" if unexpired else f"Full term commencing {r['Term Commencing Date']}"))
        status = (r["Office Filing Status"] or "").strip().lower()
        blocks.append({"section": "", "office": office, "cands": [{
            "name": tidy(r["Ballot Name"]), "party": tidy(r["Party"]), "write_in": (r["Write-In (YES/NO)"] or "").strip().upper() == "YES",
            "gone": bool(re.search(r"withdr|reject|invalid|disqual|not certified|removed|declin", status))}]})
    return blocks, " ".join(sorted({(r["Election Date"] or "").strip() for r in rows})), \
        " ".join(sorted({tidy(r.get("District Name 1") or "") for r in rows}))


def read_notice(data, where):
    """[{section, office, cands}] for every office of a 46-day notice, federal and state offices included."""
    rows = notice_rows(data)
    kind = notice_kind(rows)
    if kind == "columns":
        return column_notice(rows, where), kind
    if kind == "form120":
        return form_notice(rows, where), kind
    if not rows:
        raise ListError(f"Ohio {where}: the notice is a picture of the page (a scan) with no text to read")
    raise ListError(f"Ohio {where}: the notice's layout is not one the loader knows (no 'Name of Candidate' heading row)")


# The boards whose 46-day notice for November 3, 2026 a script could fetch from the board's own site, largest county
# first: county, the document as the board's page labels it, and its address. Each address was opened and read on
# 2026-10-01; none is guessed. (Hamilton's and Union's notices are the federal loader's, in ballot_cache/oh/.) Sandusky
# posts its notice as a Word file. Ottawa's notice is a scan, so its board's candidate file is read instead: a small
# table of district, office, term, status, name and party, with no contact columns.
NOTICES = {
    "warren": ("Warren", "46 day notice for November 3, 2026",
               "https://vote.warrencountyohio.gov/doc/Voting/46_Day_notice_for_November_3_2026.pdf"),
    "delaware": ("Delaware", "46 Day FWAB", "https://vote.delawarecountyohio.gov/wp-content/uploads/2026/09/46DayFWAB-Revised.pdf"),
    "clermont": ("Clermont", "46 Day Election Notice for use with the Federal Write-In Absentee Ballot (FWAB) for the November 3, 2026 General",
                 "https://boe.clermontcountyohio.gov/FWAB%2046%20day%20-%20November%203,%202026%20General%20rev2.pdf"),
    "trumbull": ("Trumbull", "46 Day Notice for the November 3, 2026 General Election", "https://boe.co.trumbull.oh.gov/pdfs/46%20day%20notice.pdf"),
    "wayne": ("Wayne", "46-Day Notice for Federal Write-In Absentee Ballots (Form 120)",
              "https://www.waynecountyoh.gov/wp-content/uploads/2026/09/Form-120-46-Day-FWAB-Gen-26-09172026-0930.pdf"),
    "hancock": ("Hancock", "46 Day Notice: 2026 November General",
                "https://hancockcountyohioelections.gov/wp-content/uploads/2026/09/46Day-Notice-G26-1.pdf"),
    "sandusky": ("Sandusky", "46 Day Notice for Federal Write-In Absentee Ballots November 3, 2026 General Election",
                 "https://sanduskycountyoh.gov/uploads/46%20day%20FWAB%20November%202026.docx"),
    "mercer": ("Mercer", "46 Day Election Notice",
               "https://www.mercercountyoh.gov/bskpdf/46-day--election-notice-for-use-with-the-fwab-for-the-november-3-2026-general-election/"),
    "crawford": ("Crawford", "46 Day Federal Write-In Absentee Ballot for General Election November 3, 2026",
                 "https://crawfordcountyohioboe.gov/wp-content/uploads/46-Day-notice-11-3-2026.pdf"),
    "ottawa": ("Ottawa", "Ottawa Co. Candidates : General Election \u2013 November 3, 2026",
               "https://boe.ottawa.oh.gov/wp-content/uploads/2026/09/Candidates-GN26-1.csv"),
    "guernsey": ("Guernsey", "Guernsey County November 3, 2026 General Election 46 Day Notice",
                 "https://boe.guernseycounty.gov/wp-content/uploads/2026/09/46-day-notice-Nov.-3-2026-General-2.pdf"),
    "williams": ("Williams", "November 3, 2026, 46 Day FWAB", "https://www.williamscountyoh.gov/DocumentCenter/View/4018"),
    "morrow": ("Morrow", "2026 General Election 46 Day Notice", "https://boe.morrowcountyohio.gov/2026/2026%20General%2046%20day%20notice.pdf"),
    "henry": ("Henry", "46 Day Notice to Federal Write-In Absentee Voters",
              "https://www.henrycountyohio.gov/DocumentCenter/View/1059/46-Day-Notice-PDF"),
}


def county_key(name):
    return name.lower().replace(" ", "_")


# Sites that answer scripts with a challenge page: the Secretary of State's, the boards' shared site, and three boards'
# own (tried twice on 2026-10-01). They are never asked, whatever address is put in NOTICES.
NEVER_ASK = ("ohiosos.gov", "boe.ohio.gov", "summitcountyboe.gov", "lucascountyohiovotes.gov", "portagecounty-oh.gov")
KEPT_AS = {"pdf": "{key}_46day_notice.pdf", "docx": "{key}_46day_notice.docx", "csv": "{key}_candidates.csv"}
CSV_COLUMNS = ("Office Title 1", "Ballot Name", "Party", "Election Date", "Unexpired Term (YES/NO)", "Write-In (YES/NO)", "Office Filing Status",
               "Term Commencing Date", "Term Ending Date")


def file_kind(data):
    """pdf, docx or csv (the candidate table Ottawa's board posts), from the file's own first bytes; else None."""
    if data.lstrip()[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK":
        return "docx"
    first = data[:600].decode("utf-8-sig", "replace").splitlines()[0] if data else ""
    return "csv" if all(c in first for c in CSV_COLUMNS) else None


def notice_path(key, kind="pdf"):
    return os.path.join(LOCAL_DIR, key, KEPT_AS[kind].format(key=key))


def kept_notice(key):
    """The copy of a board's notice or list kept in ballot_cache/oh/local/<county>/, or None."""
    for kind in KEPT_AS:
        path = notice_path(key, kind)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None


def get_notice(key, url, refresh=False):
    """(path, None) for a board's notice already kept in ballot_cache/oh/local/<county>/ or fetched now, else (None, why
    not). These files print no contact details, so they are kept whole, as fetched. One request, no retry: a site that
    refuses is left alone, and the county is written down as a gap."""
    have = kept_notice(key)
    if (have and not refresh) or not url:
        return (have, None) if have else (None, "no copy of the board's notice has been saved yet")
    host = (urlparse(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in NEVER_ASK):
        return (have, None) if have else (None, "its site turns scripts away and is never asked")
    try:
        data = net.get(url, timeout=120)
        time.sleep(1.5)
    except Exception as e:  # noqa: BLE001  a board's site can be down or refuse: the county waits, the loader goes on
        code = getattr(e, "code", None)
        why = f"the board's site answered {code}" if code else "the board's site could not be reached"
        return (have, None) if have else (None, why)
    kind = file_kind(data)
    if kind is None:
        return (have, None) if have else (None, "the board's address gave a page, not the notice")
    path = notice_path(key, kind)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as fh:
        fh.write(data)
    os.replace(path + ".part", path)
    return path, None


def statewide_key(office, section=""):
    """Which of the seven statewide races an office cell of a notice names, for the control only."""
    t, s = squeeze(office).upper(), squeeze(section).upper()
    if "GOVERNOR" in t:
        return f"2026-{STATE}-GOV"
    if "ATTORNEYGENERAL" in t:
        return f"2026-{STATE}-AG"
    if "AUDITOROFSTATE" in t:
        return f"2026-{STATE}-AUD"
    if re.search(r"SECRE?TARYOFSTATE", t):
        return f"2026-{STATE}-SOS"
    if "TREASUREROFSTATE" in t:
        return f"2026-{STATE}-TREAS"
    if "SUPREME" in t or ("SUPREME" in s and re.search(r"JUDGE|JUSTICE", t)):
        _term, date = term_of(tidy(office))
        if date in ("2027-01-01", "2027-01-02"):
            return f"2026-{STATE}-SC-{date.replace('-', '')}"
    return None


# ---------------------------------------------------------------- the May 5 canvass

SHEETS = ("Statewide Offices", "Justice of the Supreme Court", "General Assembly")


def canvass_race(office):
    o = re.sub(r"\s+", " ", office).strip()
    m = re.fullmatch(r"State Senator - District (\d+)", o)
    if m:
        return f"2026-{STATE}-SS{int(m.group(1))}"
    m = re.fullmatch(r"State Representative - District (\d+)", o)
    if m:
        return f"2026-{STATE}-SH{int(m.group(1))}"
    m = re.fullmatch(r"Justice of the Supreme Court Term Commencing 01/0([12])/2027", o)
    if m:
        return f"2026-{STATE}-SC-2027010{m.group(1)}"
    words = {"Governor and Lieutenant Governor": "GOV", "Attorney General": "AG", "Auditor of State": "AUD",
             "Secretary of State": "SOS", "Treasurer of State": "TREAS"}
    return f"2026-{STATE}-{words[o]}" if o in words else None


def canvass(problems):
    """{(race, party code): [(name, votes, write_in)]}, {race: set of county names}, and the workbooks read. Every
    candidate column's county rows must add up to its Total row."""
    import openpyxl
    fields, counties, files, cols = {}, {}, {}, 0
    for pcode, (fname, url) in fed.PRIMARY_BOOKS.items():
        path = os.path.join(FOLDER, fname)
        if not os.path.exists(path):
            problems.append(f"the {PARTY_OF[pcode]} canvass workbook is not in {FOLDER}")
            continue
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        n = 0
        for sheet in SHEETS:
            if sheet not in wb.sheetnames:
                continue
            rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
            head, names, total = rows[0], rows[1], rows[2]
            if "Official Canvass" not in str(head[0]) or str(total[0]).strip() != "Total" or str(names[0]).strip() != "County Name":
                raise ListError(f"Ohio: {fname} sheet {sheet} does not open with the official canvass, County Name and Total rows")
            body = [r for r in rows[4:] if r and r[0] not in (None, "")]
            if len(body) != 88:
                raise ListError(f"Ohio: {fname} sheet {sheet} has {len(body)} county rows, not 88")
            office = None
            for i in range(6, len(names)):
                if i < len(head) and head[i]:
                    office = re.sub(r"\s+", " ", str(head[i])).strip()
                if not names[i] or office is None:
                    continue
                race = canvass_race(office)
                if not race:
                    problems.append(f"canvass {pcode} {sheet}: an office the loader does not know ({office})")
                    continue
                label = re.sub(r"\s+", " ", str(names[i])).strip()
                wi = "(WI)" in label
                if not re.search(r"\((R|D|L)\)$", label):
                    raise ListError(f"Ohio: a candidate heading in {fname} ({sheet}) does not end with a party mark")
                person = re.sub(r"\s*\(WI\)\s*\*?|\s*\((?:R|D|L)\)$", " ", label).strip(" *")
                person = re.sub(r"\s*-\s+|\s+-\s*", "-", re.sub(r"\s+", " ", person))
                votes = int(total[i] or 0)
                county_sum = sum(int(r[i] or 0) for r in body)
                cols += 1
                if county_sum != votes:
                    problems.append(f"canvass {pcode} {race} {person}: county rows add to {county_sum}, Total row says {votes}")
                counties.setdefault(race, set()).update(str(r[0]).strip() for r in body if int(r[i] or 0) > 0)
                fields.setdefault((race, pcode), []).append((clean_name(person, f"canvass {pcode} {race}"), votes, wi))
                n += 1
        files[pcode] = (path, url, n)
    return fields, counties, files, cols


# ---------------------------------------------------------------- roster, counties, matching

def roster(path=ROSTER):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = {}
    for mid, full, first, last, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1"):
        members.setdefault((chamber, str(int(district))), []).append(
            dict(id=mid, name=full or f"{first} {last}", first=first or "", last=last or "", other=other or "", party=party))
    officials = {o: dict(id=i, name=n, party=p) for i, n, o, p in con.execute(
        "SELECT bioguide_id, official_full, office, party_name FROM officials")}
    con.close()
    return members, officials


def census_counties(path=COUNTY_ZIP):
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {r["NAME"]: r["GEOID"] for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def person(name):
    """The first person of a ticket, as (given names, family name)."""
    return name_parts(re.split(r"\s+and\s+", name)[0])


def member_forms(m):
    forms = [(fold(m["first"]).split(), fold(m["last"]))] if m.get("last") else []
    forms.append(name_parts(m["name"]))
    for o in (m.get("other") or "").split(";"):
        o = o.strip()
        if o and not re.search(r"\b[A-Z]\.$|^[A-Z]\.", o):
            forms.append(name_parts(o))
    return forms


def find_incumbent(names, member):
    """The one name that fits the sitting member, or None."""
    if not member:
        return None
    forms = member_forms(member)
    hits = [n for n in names if any(fits(person(n), f) for f in forms)]
    return hits[0] if len(set(hits)) == 1 else None


def same_person(a, b):
    return fits(person(a), person(b)) or fold(a) == fold(b)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- the county and local part

LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st39_oh_place2020.txt"
PLACE_FILE = os.path.join(LOCAL_DIR, "st39_oh_place2020.txt")
STATUTE_URL = "https://codes.ohio.gov/ohio-revised-code/section-2501.01"
STATUTE_FILE = os.path.join(LOCAL_DIR, "orc_2501_01.html")
CALENDAR_URL = "https://codes.ohio.gov/ohio-revised-code/section-3501.02"
SRC_PLACE, SRC_STATUTE = "oh-census-2020-place-codes", "oh-orc-2501-01"
WHAT = "county offices and common pleas judges"
NOT_YET = "This county's November list is not loaded yet. "
REFUSED = NOT_YET + "Its board of elections publishes it on a site that turns scripts away, so the list has to be saved from a browser."
# Boards whose list could not be read on 2026-10-01, with what was seen there (the address is the board's own page).
WAITING = {
    "Summit": (REFUSED, "https://www.summitcountyboe.gov/"),
    "Lucas": (REFUSED, "https://www.lucascountyohiovotes.gov/"),
    "Portage": (REFUSED, "https://www.portagecounty-oh.gov/board-elections"),
    "Mahoning": (NOT_YET + "On October 1, 2026 the board's candidates page still showed the May 5 primary, and no notice for November was found "
                 "on its site.", "https://vote.mahoningcountyoh.gov/225/State-and-Local-Candidates-Liquor-Option"),
}
SHARED = NOT_YET + ("Its board of elections publishes it; most Ohio boards keep their pages on the state's shared elections site, which turns "
                    "scripts away, so the list has to be saved from a browser.")
# the page's own guard also takes Court and Place for street words after a number; nothing stored may trip it
PAGE_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:Court|Pl|Place)\b\.?", re.I)
NO_PARTY_NOTE = "Ohio's November ballot prints no party beside the candidates for this court."
PARTY_NOTE = "Ohio prints the candidates' parties on the ballot for this court."
UNEXPIRED_NOTE = "An election for the rest of an unexpired term."
CALENDAR = ("On November 3, 2026 every Ohio county elects one county commissioner (the seat whose term begins January 1, 2027) and its county "
            "auditor, and the voters choose the judges of the courts of appeals, the courts of common pleas and the county courts whose terms "
            "are ending; a county with a charter elects its own officers instead (Cuyahoga County its executive and part of its council). The "
            "other two commissioners and the other county officers (prosecuting attorney, sheriff, clerk of the court of common pleas, recorder, "
            "treasurer, engineer and coroner) are elected in presidential years, next in 2028, and are on this ballot only to finish an "
            "unexpired term. Cities, villages, townships, boards of education and municipal courts elect in odd-numbered years, next in "
            "November 2027, again apart from unexpired terms. Soil and water conservation supervisors are chosen in elections run by the "
            "state's soil and water conservation commission, not on this ballot.")
CALENDAR_SOURCE = ("Ohio Revised Code 3501.02 (which offices are elected in even and in odd years), 305.01 (county commissioners), 319.01 (county "
                   "auditor), 2301.01 and 1907.13 (judges of the common pleas and county courts), 940.04 (soil and water supervisors)")


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def keep(url, path, refresh=False):
    """A reference page or file with no contact details in it, kept whole: True when a copy is on disk afterwards."""
    if os.path.exists(path) and os.path.getsize(path) > 0 and not refresh:
        return True
    try:
        data = net.get(url, timeout=120)
        time.sleep(1.5)
    except Exception:  # noqa: BLE001  the site is down: an older copy serves, or the caller does without
        return os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as fh:
        fh.write(data)
    os.replace(path + ".part", path)
    return True


def statute_districts(path=STATUTE_FILE):
    """{district number: set of county names} as the kept copy of R.C. 2501.01 lists them, or None when it cannot be read."""
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8", errors="replace").read()
    text = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)))
    out = {}
    for word, names in re.findall(r"\([A-L]\)\s*(\w+) district:\s*([^;.]+)[;.]", text):
        if word.upper() in ORDINALS:
            out[ORDINALS.index(word.upper()) + 1] = {n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", names) if n.strip()}
    return out or None


def census_places(path=PLACE_FILE):
    """{place name in lower case: [(place code, name, counties)]} for Ohio's incorporated places (Census Bureau, 2020 codes)."""
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace").read().splitlines()[1:]:
            f = line.split("|")
            if len(f) >= 9 and f[5] == "INCORPORATED PLACE":
                out.setdefault(f[4].lower(), []).append((f[2], f[4], f[8]))
    return out


def is_caps(name):
    return bool(re.search(r"[A-Z]{3}", name)) and name == name.upper()


def notice_list(key, county, path, problems):
    """One board's 46-day notice as a list record: the candidates of its county and court offices (as keys), how many
    entries it has in all, and its statewide candidates for the control. (None, why) when the file is not this
    election's notice or is in a layout the loader does not know."""
    data = open(path, "rb").read()
    kind, published = file_kind(data), ""
    not_this = "the file kept for it is not for the November 3, 2026 election"
    not_ours = "the file kept for it does not name this county's board of elections"
    name = squeeze(county).upper()      # "Issued by the Wayne Board of Elections", "Union County Board of Elections"
    board = re.compile(rf"{name}(?:COUNTY)?(?:,?OHIO)?BOARDOFELECTIONS|ISSUEDBY(?:THE)?{name}")
    try:
        if kind == "pdf":
            rows = notice_rows(data.lstrip())
            if not rows:
                return None, "the board posts its notice as a scan, a picture of the page with no text to read"
            front = squeeze(" ".join(join(rs) for p, _y, rs in rows if p <= 2)).upper()
            if "NOVEMBER3,2026" not in front:
                return None, not_this
            if not board.search(front):
                return None, not_ours
            blocks, kind = read_notice(data.lstrip(), key)
            for _p, _y, rs in rows:
                m = re.search(r"Revised:?\s*(\d{1,2})/(\d{1,2})/(\d{4})", join(rs))
                if m:
                    published = f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                    break
        elif kind == "docx":
            blocks, text = docx_notice(data, key)
            if "NOVEMBER3,2026" not in squeeze(text).upper():
                return None, not_this
            if not board.search(squeeze(text).upper()):
                return None, not_ours
        elif kind == "csv":
            blocks, dates, districts = csv_list(data, key)
            if dates != "11/3/2026":
                return None, not_this
            if districts != f"{county} County":
                return None, not_ours
        else:
            return None, "the file kept for it is not a notice the loader can open"
    except ListError as e:
        problems.append(str(e))
        return None, "its notice is in a layout the loader does not know"
    cands, control, entries, other, caps, empty = [], {}, 0, 0, False, []
    for b in blocks:
        try:
            lk = local_office(b["office"], b["section"], county)
        except ListError as e:
            problems.append(str(e))
            continue
        sk = None if lk else statewide_key(b["office"], b["section"])
        if lk and not b["cands"]:
            empty.append(lk)      # an office the notice prints with no candidate under it: the contest is kept, and says so
        for c in b["cands"]:
            entries += 1
            if lk:
                name, note = c["name"], None
                if is_caps(name):
                    name, caps = proper(name), True
                    note = f"{county} County's notice prints names in capitals; they are shown here in ordinary capitals."
                cands.append(cand(lk, local_name(name, f"{key} notice ({lk})"), c["party"], c["write_in"], c["gone"], note))
            elif sk:
                control.setdefault(sk, []).append(c)
            else:
                other += 1
    return dict(key=key, county=county, cands=cands, entries=entries, other=other, control=control, layout=kind, path=path,
                published=published, caps=caps, empty=empty), None      # layout: columns or form120 (a PDF notice), docx, csv


def control_of(record, chosen):
    """How a notice's statewide candidates compare with the lists the state rows were taken from: (races that agree,
    races compared, [those that differ]). The same seven races are on every county's notice, so this reads each
    notice a second way against lists that were read independently."""
    same, differ = 0, []
    for rid, cs in sorted(record["control"].items()):
        if rid not in chosen:
            continue
        truth = {(person(c["name"])[1], party_code(c["party"]) if party_code(c["party"]) in "DRLG" else "-")
                 for c in chosen[rid][1] if not c["write_in"]}
        here = set()
        for c in cs:
            if c["write_in"] or c["gone"]:
                continue
            word = local_party(c["party"])
            here.add((person(tidy(c["name"]).replace("/", " and ").replace("&", " and "))[1], party_code(word) if party_code(word) in "DRLG" else "-"))
        if here == truth:
            same += 1
        else:
            differ.append(short(rid))
    return same, same + len(differ), differ


def local_race(k, county, counties, places):
    """(race id, the race's fields) for a county, court or city office read from the list of one county's board."""
    fips = counties[county]
    kind, term, date = k["kind"], k["term"], k["date"]
    special, stamp, note = int(term == "U"), date.replace("-", ""), []
    if kind == "court_of_appeals":
        d = int(k["district"])
        rid = f"2026-{STATE}-CA{d}" + (f"-{stamp}" if stamp else "") + ("-S" if special else "")
        row = dict(level="court", kind=kind, jurisdiction=f"{ordinal(d)} District Court of Appeals", jid=f"{STATE}-CA{d}",
                   cids=sorted(counties[c] for c in APPELLATE[d]), district=str(d), seat=seat_words(term, date), partisan=1)
        note.append(PARTY_NOTE)
    elif kind in ("common_pleas_court", "county_court"):
        if kind == "common_pleas_court":
            where, code = k["division"], "-".join(c for n, c, _p in DIVISIONS if n in k["division"])
        else:
            where, code = k["district"], slug(k["district"]).upper()
        rid = f"2026-{STATE}-{'CP' if kind == 'common_pleas_court' else 'CC'}-{fips}" + (f"-{code}" if code else "") + \
            (f"-{stamp}" if stamp else "") + ("-S" if special else "")
        row = dict(level="court", kind=kind, jurisdiction=f"{county} County", jid=fips, cids=[fips], district=where or None,
                   seat=seat_words(term, date), partisan=0)
        note.append(NO_PARTY_NOTE)
    elif kind == "council":
        found = [p for p in places.get(k["place"].lower(), []) if f"{county} County" in p[2]]
        pkey = found[0][0] if len(found) == 1 else f"{fips[2:]}-{slug(k['place'])}"
        rid = f"2026-{STATE}-M-{pkey}-council" + (f"-{slug(k['district'])}" if k["district"] else "") + ("-S" if special else "")
        row = dict(level="city", kind=kind, jurisdiction=found[0][1] if len(found) == 1 else k["place"], jid=f"{STATE}-M-{pkey}", cids=[fips],
                   district=k["district"] or None, seat=seat_words(term, date) if special else None, partisan=None, census=len(found) == 1)
    else:
        rid = f"2026-{STATE}-{fips}-{kind.replace('_', '-')}" + (f"-{slug(k['district'])}" if k["district"] else "") + \
            ((f"-{stamp}" if stamp else "") + "-S" if special else "")
        row = dict(level="county", kind=kind, jurisdiction=f"{county} County", jid=fips, cids=[fips], district=k["district"] or None,
                   seat=seat_words(term, date) if special else None, partisan=1)
    if special:
        note.append(UNEXPIRED_NOTE)
    row.update(office=OFFICE_WORDS[kind], special=special, note=note)
    return rid, row


def build_local(lists, counties, why_not, problems, checks):
    """The county, court and city rows from every list read: races, candidates, places, gaps and notes, and the counts
    to report. lists is in reading order; a court of appeals race, which every county of its district prints, is taken
    from the first list that carries it and the others are checked against it (the write-in candidates from the first
    list that names them)."""
    places = census_places()
    races, order, unknown = {}, [], []
    for L in lists:
        groups = collections.OrderedDict()
        for c in L["cands"]:
            groups.setdefault(c["race"], []).append(c)
        for key in L.get("empty", ()):
            groups.setdefault(key, [])
        for key, cs in groups.items():
            k = kparts(key)
            if k["kind"] == "unknown":
                unknown.append((L, k["place"], len(cs)))
                continue
            rid, row = local_race(k, L["county"], counties, places)
            if rid not in races:
                races[rid] = dict(row=row, key=key, lists=[])
                order.append(rid)
            elif row["level"] != "court" or row["kind"] != "court_of_appeals" or races[rid]["key"] != key:
                problems.append(f"{rid}: read a second time, from the {L['key']} list")
                continue
            races[rid]["lists"].append((L, cs))

    def printed(cs):
        return sorted({(person(c["name"])[1], party_code(c["party"]) if party_code(c["party"]) in "DRLG" else "-")
                       for c in cs if c["name"] and not c["gone"] and not c["write_in"]})

    race_rows, cand_rows, gaps, gone_all = [], [], [], 0
    used = collections.Counter()      # list -> candidate rows taken from it
    tally = collections.Counter({"unknown": sum(n for _L, _w, n in unknown)})      # what became of every entry read: each is counted once
    for rid in order:
        R, row = races[rid], races[rid]["row"]
        L0, cs0 = R["lists"][0]
        people = [(L0, c) for c in cs0 if c["name"] and not c["gone"] and not c["write_in"]]
        named = next(((L, [c for c in cs if c["name"] and not c["gone"] and c["write_in"]]) for L, cs in R["lists"]
                      if any(c["name"] and not c["gone"] and c["write_in"] for c in cs)), None)
        if named:
            people += [(named[0], c) for c in named[1]]
        gone = {fold(c["name"]) for _L, cs in R["lists"] for c in cs if c["gone"] and c["name"]}
        blank = sum(1 for c in cs0 if not c["name"] and not c["gone"])
        gone_all += len(gone)
        taken = {id(c) for _L, c in people}
        for L, cs in R["lists"]:
            for c in cs:
                tally["withdrawn" if c["gone"] else "blank" if not c["name"] else "row" if id(c) in taken else "same"] += 1
            if L is not L0 and printed(cs) != printed(cs0):
                checks.append(f"{rid}: {L0['key']} prints {printed(cs0)}, {L['key']} prints {printed(cs)}")
        partisan = row["partisan"]
        if partisan is None:      # a city office: partisan only where the list gives its candidates parties
            partisan = int(any(c["party"] not in ("No party", "Write-in") for _L, c in people))
        note = list(row["note"])
        if gone:
            note.append(f"{len(gone)} candidate{'s' if len(gone) > 1 else ''} the board's list marks withdrawn or not valid "
                        f"{'are' if len(gone) > 1 else 'is'} left off.")
        unnamed = UNNAMED.get((L0["key"], R["key"]), 0)
        if unnamed and not named:
            note.append("The board's list shows that write-in candidates declared for this contest, without naming them.")
        if not people:
            note.append("The board's list has a candidate for this contest whose name could not be read here." if blank else
                        "The board's list shows no candidate for this contest.")
        if blank:
            gaps.append((STATE, "race", rid, row["jurisdiction"], "a candidate's name",
                         f"{blank} name cell{'s' if blank > 1 else ''} of the board's list could not be read as a name, so "
                         f"{'they are' if blank > 1 else 'it is'} not shown; the board's own list is the place to check.", L0.get("url")))
        race_rows.append([rid, STATE, row["level"], row["kind"], row["office"], row["jurisdiction"], row["jid"], json.dumps(row["cids"]),
                          row["district"], row["seat"], row["special"], partisan, None, None, None, GENERAL, " ".join(note) or None])
        seen = set()
        for L, c in people:
            if c["name"] in seen:
                problems.append(f"{rid}: {c['name']} twice on the {L['key']} list")
                tally["row"] -= 1
                tally["twice"] += 1
                continue
            seen.add(c["name"])
            if partisan:
                party = c["party"]
                code = "W" if c["write_in"] and party == "Write-in" else fed.code(party)
                if party not in KNOWN_PARTIES:
                    problems.append(f"{rid}: the {L['key']} list gives a party the loader does not know ({party})")
            else:
                party, code = "Nonpartisan office", "N"
            cnote = "; ".join(x for x in (c["note"], WRITE_IN_NOTE if c["write_in"] else None) if x) or None
            cand_rows.append([rid, "general", GENERAL, c["name"], party, code, None, 0, int(c["write_in"]), None, None, None, None,
                              L["source_id"], cnote])
            used[L["key"]] += 1

    # places: every county, and each city or village a race is in
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for n, g in sorted(counties.items())]
    for rid in order:
        row = races[rid]["row"]
        if row["level"] == "city":
            place_rows.append(("mcd", row["jid"], row["jurisdiction"], json.dumps(row["cids"]),
                               SRC_PLACE if row.get("census") else races[rid]["lists"][0][0]["source_id"]))
    place_rows = list({(p[0], p[1]): p for p in place_rows}.values())

    # gaps: the counties with no list, the offices no pattern fits, the appellate districts no list reaches
    loaded = {L["county"] for L in lists}
    for name, g in sorted(counties.items()):
        if name in loaded:
            continue
        if name in why_not:
            reason, url = NOT_YET + why_not[name][0], why_not[name][1]
        else:
            reason, url = WAITING.get(name, (SHARED, None))
        gaps.append((STATE, "county", g, f"{name} County", WHAT, reason, url))
    for L, words, n in unknown:
        shown = "" if re.search(r"\d", words) or contact_like(words, True) else f" ({words.title()[:60]})"      # office words only
        gaps.append((STATE, "county", counties[L["county"]], f"{L['county']} County", f"an office on the board's list{shown}",
                     f"The board's list has {n} candidate{'s' if n != 1 else ''} under a heading the loader does not know how to file, so "
                     "the contest is not shown; the board's own list has it.", L.get("url")))
    reached = {int(races[r]["row"]["district"]) for r in order if races[r]["row"]["kind"] == "court_of_appeals"}
    dark = [d for d in sorted(APPELLATE) if d not in reached]
    if dark:
        gaps.append((STATE, "state", STATE, "Ohio", f"court of appeals judges in the {and_list([ordinal(d) for d in dark])} district"
                     + ("s" if len(dark) > 1 else ""),
                     "No county of " + ("these districts" if len(dark) > 1 else "this district") + " has a list loaded yet, so "
                     + ("their" if len(dark) > 1 else "its") + " judges' races are not shown; each county board of elections in the district "
                     "prints them.", None))
    by_level = collections.Counter(r[2] for r in race_rows)
    by_kind = collections.Counter(r[3] for r in race_rows)
    return dict(races=race_rows, cands=cand_rows, places=place_rows, gaps=gaps, loaded=sorted(loaded), by_level=by_level, by_kind=by_kind,
                gone=gone_all, tally=tally, used=used, unknown=unknown, dark=dark, entries=sum(len(L["cands"]) for L in lists))


def and_list(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# ---------------------------------------------------------------- the load

def load(db_path, say=print, roster_db=ROSTER, county_zip=COUNTY_ZIP, refresh=False):
    problems, checks = [], []
    BLANKED.clear()
    UNNAMED.clear()

    # 1. the county lists: the state races, and beside them the county offices and judges (kept apart as keys)
    got, paths, local_raw, read_in = {}, {}, {}, {}
    for key in ORDER:
        path = os.path.join(FOLDER, fed.CARRIED.get(key, f"oh_{key}_2026_general.pdf"))
        paths[key] = path
        if not os.path.exists(path):
            problems.append(f"the {key} list is not in {FOLDER} (the federal loader keeps it there)")
            continue
        everything = READERS[key](path)
        got[key] = [c for c in everything if not c["race"].startswith(LOCAL)]
        local_raw[key] = [c for c in everything if c["race"].startswith(LOCAL)]
        read_in[key] = len(everything)
        if not any(c["race"].endswith("-GOV") for c in got[key]):
            problems.append(f"no Governor race read from the {key} list; its layout may have changed")

    def printed(cands):
        return sorted({(person(c["name"])[1], party_code(c["party"]) if party_code(c["party"]) in "DRLG" else "-")
                       for c in cands if not c["write_in"]})

    chosen, carried = {}, {}
    for key in ORDER:
        if key not in got:
            continue
        on = [c for c in got[key] if not c["gone"]]
        for race in sorted({c["race"] for c in got[key]}):
            carried.setdefault(race, []).append(key)
            here = [c for c in on if c["race"] == race]
            if race not in chosen:
                chosen[race] = (key, here)
                continue
            first_key, first = chosen[race]
            if printed(first) != printed(here):
                checks.append(f"{race}: {first_key} prints {printed(first)}, {key} prints {printed(here)}")
            extra = {person(c["name"])[1] for c in here if c["write_in"]} - {person(c["name"])[1] for c in first if c["write_in"]}
            if extra and key != "butler":
                checks.append(f"{race}: {key} names write-in candidates {sorted(extra)} that {first_key} does not")

    # 2. the canvass, the counties and the roster
    fields, reach, books, ncols = canvass(problems)
    counties = census_counties(county_zip)
    members, officials = roster(roster_db)
    senate_in_canvass = sorted({int(r.split("SS")[1]) for (r, _p) in fields if "-SS" in r})
    if senate_in_canvass != SENATE_UP:
        problems.append(f"the canvass's State Senate districts {senate_in_canvass} are not the odd seventeen")

    # 3. the races
    all_races = [f"2026-{STATE}-{k}" for k in STATEWIDE] + [f"2026-{STATE}-{k}" for k in COURT] + \
                [f"2026-{STATE}-SS{d}" for d in SENATE_UP] + [f"2026-{STATE}-SH{d}" for d in range(1, HOUSE_SEATS + 1)]
    unknown = sorted(set(chosen) - set(all_races))
    if unknown:
        problems.append(f"races read that are not on the 2026 ballot: {unknown}")
    race_rows, cands, holders = {}, [], {}
    for rid in all_races:
        key = rid.split(f"-{STATE}-", 1)[1]
        note, seat, district, cids, holder = [], None, None, None, None
        if key in STATEWIDE:
            level, kind, office, rk = STATEWIDE[key]
            holder = officials.get(rk) if rk else None
            if not rk:
                note.append("The member roster used here (Open States) does not carry this office, so today's holder is not shown.")
            if key == "GOV":
                note.append("The Governor and Lieutenant Governor are elected together, one ticket to a party; each ticket is written "
                            "governor first, as the Secretary of State's canvass writes it.")
                if officials.get("lt_governor"):
                    note.append(f"Lieutenant Governor today: {officials['lt_governor']['name']}.")
        elif key in COURT:
            level, kind, office, seat = "court", "supreme_court", "Justice of the Supreme Court", COURT[key]
            note.append(f"{seat}. Ohio prints the candidates' parties on the ballot for this court. The member roster used here "
                        "does not carry the justices, so today's holder is not shown.")
        else:
            chamber = "Senate" if key.startswith("SS") else "House"
            district = key[2:]
            level, kind = "legislature", ("state_senate" if chamber == "Senate" else "state_house")
            office = "State Senator" if chamber == "Senate" else "State Representative"
            sitting = members.get((chamber, district), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if not sitting:
                note.append("The seat is vacant on the member roster.")
            elif len(sitting) > 1:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster")
            names = sorted(reach.get(rid, ()))
            bad = [n for n in names if n not in counties]
            if bad:
                raise ListError(f"Ohio: county names in the canvass that are not in the Census file: {bad}")
            cids = json.dumps(sorted(counties[n][2:] for n in names)) if names else None
            if not names:
                problems.append(f"{rid}: no county in the canvass carries this district")
        if rid not in chosen:
            note.append(NO_LIST)
        holders[rid] = holder
        race_rows[rid] = [rid, STATE, level, kind, office, None if district else "Ohio", None if district else FIPS, cids, district,
                          seat, 0, 1, holder["id"] if holder else None, holder["name"] if holder else None,
                          holder["party"] if holder else None, GENERAL, " ".join(note) or None]

    # 4. November candidates
    for rid, (key, here) in sorted(chosen.items()):
        if rid not in race_rows:
            continue
        if not here:
            problems.append(f"{rid}: the {key} list carries the race with no candidate on it")
        holder = holders[rid]
        inc = find_incumbent([c["name"] for c in here], holder) if holder and "-SC-" not in rid else None
        seen = set()
        for c in here:
            if c["name"] in seen:
                problems.append(f"{rid}: {c['name']} twice on the {key} list")
                continue
            seen.add(c["name"])
            note = "; ".join(x for x in (c["note"], WRITE_IN_NOTE if c["write_in"] else None) if x) or None
            code = "W" if c["write_in"] and c["party"] == "Write-in" else fed.code(c["party"])
            is_inc = int(c["name"] == inc)
            cands.append([rid, "general", GENERAL, c["name"], c["party"], code, None, is_inc, int(c["write_in"]), None, None, None,
                          holder["id"] if is_inc else None, f"oh-{key}-2026-general-list", note])

    # 5. primary fields, and every November party nominee checked against the canvass
    nfields = 0
    for (rid, pcode), field in sorted(fields.items()):
        party = PARTY_OF[pcode]
        listed = [c for c in chosen.get(rid, ("", []))[1] if c["party"] == party]
        if listed and not any(same_person(c["name"], n) for c in listed for n, _v, _w in field):
            checks.append(f"{rid} {pcode}: the November list names {[c['name'] for c in listed]}, not among the primary's "
                          f"{[n for n, _v, _w in field]} (a replacement nominee?)")
            if rid in race_rows:
                won = max(field, key=lambda f: f[1])[0]
                extra = (f"The {party} candidate on the November list ({', '.join(c['name'] for c in listed)}) is not the candidate the "
                         f"May 5 primary nominated ({won}); the files read here do not say how the change was made.")
                race_rows[rid][16] = " ".join(x for x in (race_rows[rid][16], extra) if x)
        if sum(1 for _n, _v, wi in field if not wi) < 2:
            continue
        nfields += 1
        total = sum(v for _n, v, _w in field)
        top = max(field, key=lambda f: f[1])
        if sum(1 for f in field if f[1] == top[1]) > 1:
            problems.append(f"{rid} {pcode}: a tie at the top of the primary")
        replaced = bool(listed) and not any(same_person(c["name"], top[0]) for c in listed)
        holder = holders.get(rid)
        inc = find_incumbent([n for n, _v, _w in field], holder) if holder and rid in race_rows and "-SC-" not in rid else None
        for name, votes, wi in field:
            won = name == top[0]
            note = "; ".join(x for x in (
                "Write-in candidate: the name was not printed on the primary ballot." if wi else None,
                f"Won the primary; the November list names {listed[0]['name']} as the party's candidate instead." if won and replaced else None)
                if x) or None
            is_inc = int(name == inc)
            cands.append([rid, f"primary-{pcode}", PRIMARY, name, party, party_code(party), None, is_inc, int(wi), votes,
                          round(100 * votes / total, 1) if total else None, "advanced" if won else "lost",
                          holder["id"] if is_inc else None, f"oh-sos-2026-primary-{pcode.lower()}", note])
    for rid, (key, here) in chosen.items():
        for c in here:
            pc = CODE_OF.get(c["party"])
            if pc and (rid, pc) not in fields:
                checks.append(f"{rid}: {c['name']} is the {c['party']} candidate on the {key} list, but the canvass has no "
                              f"{c['party']} primary for the race")

    # 6. the last look at every stored text: no contact detail can reach the database
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        problems.append("two candidate rows share race, election and name")
    for c in cands:
        if NOT_A_NAME.search(c[3]) or (c[14] and re.search(r"@|www|\d{3}", c[14])):
            raise ListError(f"Ohio: a stored cell for {c[0]} failed the contact-detail check (not shown)")

    # 6b. the county and local part: the nine lists' county offices and judges, then the other boards' 46-day notices
    os.makedirs(LOCAL_DIR, exist_ok=True)
    net.patient_lookups()
    lists, why_not, notices = [], {}, {}
    for key in ORDER:
        if key not in got:
            continue
        L = dict(key=key, county=key.title(), source_id=f"oh-{key}-2026-general-list", cands=local_raw[key], url=fed.LISTS[key][2],
                 layout="notice" if key in ("union", "hamilton") else "list")
        if key == "hamilton":      # the notice's judges and county offices, by the reader that takes its columns from its own heading rows
            rec, why = notice_list(key, "Hamilton", paths[key], problems)
            if rec is None:
                problems.append(f"hamilton: {why}")
                continue
            notices[key] = rec
            L["cands"] = rec["cands"]
        lists.append(L)
    saved = {county_key(n): n for n in counties}
    for key in list(NOTICES) + sorted(k for k in saved if k not in NOTICES and k not in ORDER):
        county, title, url = NOTICES.get(key, (saved.get(key), "46-day election notice, saved from the board's site in a browser", None))
        if key not in NOTICES and not kept_notice(key):
            continue
        path, why = get_notice(key, url, refresh)
        if path is None:
            why_not[county] = (f"The board's notice could not be fetched when this was built ({why}); the loader asks again the next time "
                               "it runs.", None)
            checks.append(f"{key}: notice not fetched ({why})")
            continue
        rec, why = notice_list(key, county, path, problems)
        if rec is None:
            why_not[county] = (f"The board's notice was fetched, but {why}, so nothing was taken from it.", url)
            checks.append(f"{key}: {why}")
            continue
        rec.update(source_id=f"oh-{key}-2026-general-list" if rec["layout"] == "csv" else f"oh-{key}-2026-46day-notice", url=url, title=title)
        notices[key] = rec
        lists.append(rec)
    have_statute = keep(STATUTE_URL, STATUTE_FILE, refresh)
    in_statute = statute_districts() if have_statute else None
    if in_statute is not None and in_statute != {d: set(cs) for d, cs in APPELLATE.items()}:
        problems.append("the appellate districts in the kept copy of R.C. 2501.01 are not the loader's table: check APPELLATE")
    if any(c["race"].startswith(LOCAL + "council|") for L in lists for c in L["cands"]):
        keep(PLACE_URL, PLACE_FILE, refresh)
    local = build_local(lists, counties, why_not, problems, checks)
    controls = {key: control_of(rec, chosen) for key, rec in notices.items()}
    coverage = coverage_note(local, lists)
    local_notes = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, CALENDAR_URL),
                   (STATE, "local_coverage", coverage, "Ohio's county boards of elections: their candidate lists and their 46-day election "
                    "notices (Ohio Revised Code 3511.16), one board at a time", None)]
    for table, strict, rows in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in local["races"]]),
                                ("sl_candidates", True, [(c[0], (c[3], c[4], c[14])) for c in local["cands"]]),
                                ("sl_places", True, [(p[1], (p[2],)) for p in local["places"]]),
                                ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in local["gaps"]]),
                                ("sl_notes", False, [(n[1], (n[2], n[3])) for n in local_notes])):
        for ident, texts in rows:      # the last look: nothing that reads like contact details reaches the database
            if any(t and (contact_like(t, strict) or (strict and PAGE_STREET.search(str(t)))) for t in texts):
                raise ListError(f"Ohio: a {table} text for {ident} reads like contact details (not shown); it is not stored")
    ids = [r[0] for r in local["races"]]
    if len(ids) != len(set(ids)) or set(ids) & set(race_rows):
        raise ListError("Ohio: two local races share an id")

    # 7. write
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(race_rows.values()) + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local_notes)
        used = {}
        for rid, (key, _h) in chosen.items():
            used.setdefault(key, []).append(rid)
        for key in ORDER:
            if key not in got:
                continue
            board, title, url = fed.LISTS[key]
            mine = sorted(used.get(key, []))
            also = sorted(r for r in {c["race"] for c in got[key]} if r not in mine)
            gone = sum(1 for c in got[key] if c["gone"])
            took = local["used"].get(key, 0)
            note = (f"State races taken from this list: {', '.join(short(r) for r in mine) or 'none'}"
                    + (f"; also carries {', '.join(short(r) for r in also)}, checked against the list used" if also else "")
                    + (f". County offices and judges taken from it: {took} candidate{'s' if took != 1 else ''}" if key in local_raw else "")
                    + ". Only the office headings and the name, party, status and write-in cells are kept, chosen by position; the "
                      "addresses, cities, telephones, e-mail and websites on the same pages are dropped as the page is read and never "
                      "kept, printed or stored." + (f" Marked withdrawn or removed, left off: {gone}." if gone else "")
                    + (" Write-in candidates the report prints without names are not read." if key == "butler" else "")
                    + (" Carried out of the Browser pane for the federal loader: the board's site answers scripts with a Cloudflare challenge."
                       if key in fed.CARRIED else " Read from the federal loader's cached copy; it is not downloaded here."))
            if key in controls:
                note += control_words(controls[key])
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                f"oh-{key}-2026-general-list", STATE, "official candidate list", board, title, url, fed.printed_on(key, paths[key]),
                fetched(paths[key]), sha(paths[key]), notices[key]["entries"] if key in notices else read_in[key], note))
        for key, rec in notices.items():
            if key in ORDER:
                continue
            took = local["used"].get(key, 0)
            if rec["layout"] == "csv":
                kind, title = "official candidate list", f"{rec['title']} (the board's candidate file for the general election)"
                note = (f"The county's offices and judges are taken from this file: {took} candidate{'s' if took != 1 else ''}. It is a small "
                        "table with no contact columns: district, office, term, filing status, write-in, ballot name, party and election "
                        "date, found by the names of its columns. The board's 46-day notice is a scan with no text to read.")
            else:
                kind = "official election notice"
                title = ("Election Notice for use with the Federal Write-In Absentee Ballot, November 3, 2026 General Election (the 46-day "
                         f"notice; on the board's page as \"{rec['title']}\")")
                note = (f"The county's offices and judges are taken from this notice: {took} candidate{'s' if took != 1 else ''}. A 46-day "
                        "notice prints names, offices, parties and precincts and no contact details; its columns are found from the heading "
                        "row of each table, and the precinct column is never read." + control_words(controls[key])
                        + (" The notice prints names in capitals; they are shown in ordinary capitals." if rec["caps"] else "")
                        + (" The board posts it as a Word file." if rec["layout"] == "docx" else "")
                        + ("" if rec["url"] else " Saved from the board's site in a browser: the site turns scripts away."))
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                rec["source_id"], STATE, kind, f"{rec['county']} County Board of Elections", title, rec["url"], rec["published"],
                fetched(rec["path"]), sha(rec["path"]), rec["entries"], note))
        if os.path.exists(STATUTE_FILE):
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                SRC_STATUTE, STATE, "statute", "Ohio Laws and Administrative Rules (Legislative Service Commission)",
                "Ohio Revised Code 2501.01: the counties of the twelve court of appeals districts", STATUTE_URL, "",
                fetched(STATUTE_FILE), sha(STATUTE_FILE), len(APPELLATE),
                "Which counties a court of appeals race reaches. The loader's own table of the districts is checked against this copy "
                "of the section each time it runs."))
        if any(p[4] == SRC_PLACE for p in local["places"]):
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                SRC_PLACE, STATE, "place codes", "U.S. Census Bureau", "2020 Census place codes for Ohio (st39_oh_place2020.txt)", PLACE_URL,
                "2020", fetched(PLACE_FILE), sha(PLACE_FILE), sum(1 for p in local["places"] if p[4] == SRC_PLACE),
                "The code and name of a city or village with a contest on this ballot, matched by name and county; nothing else is read."))
        for pcode, (path, url, n) in books.items():
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                f"oh-sos-2026-primary-{pcode.lower()}", STATE, "official results", "Ohio Secretary of State",
                f"Summary Level Official Results for 2026 Primary Election - {PARTY_OF[pcode]} (Official Canvass, May 5, 2026; "
                "Statewide Offices, Justice of the Supreme Court and General Assembly sheets)", url, PRIMARY, fetched(path), sha(path), n,
                "Each candidate's statewide Total row; every column's 88 county rows reconciled to it. A field is two printed candidates "
                "or more; write-in votes count toward its total and the top vote-getter advanced. The counties a district reaches are "
                "those where any of its candidates in any party's primary received a vote (derived). Carried out of the Browser pane for "
                "the federal loader: the Secretary of State's file host answers scripts with a Cloudflare challenge."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
            "2024", fetched(county_zip), sha(county_zip), len(counties),
            "Five-digit county codes (GEOID) for Ohio's 88 counties, matched by name to the canvass's county rows."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_oh.sqlite",
            "Sitting Ohio legislators and statewide officials", "https://github.com/openstates/people", "", fetched(roster_db), "",
            sum(len(v) for v in members.values()) + len(officials),
            "Who holds each seat today and which candidate is the sitting member (same chamber and district, the name fits, one fit "
            "only); names, party and ids only. The roster carries no Auditor of State, Treasurer of State or justices."))
    con.close()

    # 8. say what happened
    gen = [c for c in cands if c[1] == "general"]
    ss_on = sorted(r for r in chosen if "-SS" in r)
    sh_on = sorted(r for r in chosen if "-SH" in r)
    sw = [r for r in chosen if "-SS" not in r and "-SH" not in r]
    say(f"    Ohio state offices: {len(race_rows)} races; November lists for {len(sw)} of 7 statewide and court races, "
        f"{len(ss_on)} of 17 Senate seats and {len(sh_on)} of 99 House seats, from {len(set(k for k, _ in chosen.values()))} county "
        f"boards' lists; {len(gen)} candidates on the November ballot ({sum(1 for c in gen if c[8])} certified write-ins, "
        f"{sum(1 for c in gen if c[7])} sitting members); {nfields} party primaries with a field, official votes "
        f"({ncols} canvass columns reconciled)")
    missing_ss = [r.split("SS")[1] for r in race_rows if "-SS" in r and r not in chosen]
    missing_sh = [r.split("SH")[1] for r in race_rows if "-SH" in r and r not in chosen]
    if missing_ss or missing_sh:
        say(f"      no reachable list: Senate {', '.join(missing_ss) or 'none'}; House {', '.join(missing_sh) or 'none'}")
    lv, kd = local["by_level"], local["by_kind"]
    lw = sum(1 for c in local["cands"] if c[8])
    say(f"    Ohio county offices and judges: {len(local['races'])} races and {len(local['cands'])} candidates ({lw} declared write-ins) "
        f"from {len(lists)} county boards ({len(local['loaded'])} of 88 counties): county {lv.get('county', 0)}, city {lv.get('city', 0)}, "
        f"judges {lv.get('court', 0)} (courts of appeals {kd.get('court_of_appeals', 0)}, common pleas {kd.get('common_pleas_court', 0)}, "
        f"county courts {kd.get('county_court', 0)})")
    tally = local["tally"]
    say(f"      entries read for these offices: {local['entries']} = {tally['row']} placed, each in one race + {tally['same']} the same "
        f"candidates on a second county's list of a court of appeals race (checked, not repeated) + {tally['withdrawn']} marked withdrawn "
        f"or not valid ({local['gone']} people) + {tally['blank']} cells that were not names + {tally['unknown']} under headings not filed "
        f"+ {tally['twice']} repeated"
        + ("" if sum(tally.values()) == local["entries"] else f"   CHECK the parts add to {sum(tally.values())}"))
    agree = sum(c[0] for c in controls.values())
    total = sum(c[1] for c in controls.values())
    say(f"      control: the {len(controls)} notices' statewide candidates, read back by the same readers, agree with the lists used for the "
        f"state rows in {agree} of {total} races"
        + ("; differences: " + "; ".join(f"{k} {', '.join(c[2])}" for k, c in controls.items() if c[2]) if agree != total else ""))
    say(f"      gaps: {sum(1 for g in local['gaps'] if g[1] == 'county')} county, {sum(1 for g in local['gaps'] if g[1] == 'race')} race, "
        f"{sum(1 for g in local['gaps'] if g[1] == 'state')} state; court of appeals districts with no list: "
        f"{', '.join(str(d) for d in local['dark']) or 'none'}")
    if BLANKED:
        say(f"      cells that were not names, blanked and never shown: {dict(BLANKED)}")
    for c in checks:
        say(f"      check: {c}")
    for p in problems:
        say(f"      CHECK {p}")
    return dict(races=len(race_rows), general=len(gen), senate_lists=len(ss_on), house_lists=len(sh_on), statewide_lists=len(sw),
                fields=nfields, missing_senate=missing_ss, missing_house=missing_sh, checks=checks, problems=problems,
                by_chamber={k: sum(1 for c in gen if k in c[0]) for k in ("-SS", "-SH")},
                local_races=len(local["races"]), local_candidates=len(local["cands"]), local_by_level=dict(lv), local_by_kind=dict(kd),
                local_counties=local["loaded"], local_tally=dict(tally), local_gone=local["gone"], controls=controls)


def control_words(control):
    same, total, differ = control
    if not total:
        return ""
    return (f" Control: its statewide candidates, read back the same way, agree with the lists used for the state rows in {same} of {total} "
            "races" + (f" (not in {', '.join(differ)}: the notice and those lists print them differently)" if differ else "") + ".")


def coverage_note(local, lists):
    lv, kd = local["by_level"], local["by_kind"]
    n = len(local["loaded"])
    unexpired = sum(1 for r in local["races"] if r[10])
    write_ins = sum(1 for c in local["cands"] if c[8])
    judges = lv.get("court", 0)
    own = sum(1 for L in lists if L["layout"] in ("list", "csv"))
    text = (f"Ohio has no statewide list of county candidates: each county's board of elections publishes its own. Loaded here from {n} of the "
            f"88 boards ({and_list(local['loaded'])}): {lv.get('county', 0)} contests for county offices (a commissioner and the auditor, "
            f"Cuyahoga County's executive and council, and a few unexpired terms of other offices), {judges} judges' seats on the courts of "
            "appeals and of common pleas"
            + (f", and {lv.get('city', 0)} city council seat" if lv.get("city") else "")
            + f", {unexpired} of them for the rest of an unexpired term; {len(local['cands'])} candidates, {write_ins} of them declared "
            f"write-ins. For {own} of the boards their own candidate list is read, and for the other {n - own} the 46-day election notice that "
            "every board must post. "
            "A court of appeals race is shown for every county of its district as soon as one county's list carries it; the other "
            f"{88 - n} counties' own offices and common pleas judges are not loaded yet and are named among the gaps. Left out: ballot "
            f"questions and tax issues; {local['gone']} candidates a list marks withdrawn or not valid; write-in candidates a list counts "
            "without naming. No ballot order is given: Ohio rotates the names from precinct to precinct. The lists print a party beside "
            "some common pleas candidates, but the November ballot does not, so none is shown for them.")
    return text


def short(rid):
    return rid.split(f"-{STATE}-", 1)[1]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write Ohio's rows into")
    ap.add_argument("--refresh", action="store_true", help="fetch the county boards' notices again instead of using the kept copies")
    a = ap.parse_args()
    load(a.db, refresh=a.refresh)
