"""
ballot/state_local_ut.py - Utah's state races on the November 3, 2026 ballot, and the local contests the statewide list
carries, from the Lieutenant Governor's Office of Elections, into ballot_local_2026.sqlite (the tables sl_races,
sl_candidates, sl_sources, sl_places, sl_gaps and sl_notes). The federal ballot database (ballot_2026.sqlite) is never
opened here, and U.S. House rows are left to ballot/lists/ut.py.

What is on the ballot: half the Utah Senate (the districts the certification lists, four-year terms, plus any seat
filled for the rest of an unexpired term), all 75 seats of the Utah House of Representatives, the State Board of
Education seats up this year (partisan: the certification prints each candidate's party), and the retention elections
of the Supreme Court, the Court of Appeals and the district and juvenile courts. No statewide executive office is on the
2026 certification. The two proposed constitutional amendments are counted and left out.

The local level (a narrow pass, 2026-10-01: only what the statewide list carries). The certification's last judicial
group, "Justice Courts", holds the retention questions of the judges of the county and city justice courts. Each is
stored as one contest, level court, kind justice_court_retention, beside the district and juvenile court judges:

  - The court. A question reads "Shall NAME be retained in the office of Judge of the Draper Municipal Justice Court?";
    some name several courts ("Naples City and Uintah County Justice Courts") or one court shared by two places
    ("Roy/Weber County", "Uintah-Huntsville Municipal"). The words are read into places: "X County" is one of the 29
    counties; anything else is a city or town on the Census Bureau's 2020 place list for Utah (st49_ut_place2020.txt,
    kept whole in ballot_cache/ut/local/: names, codes and counties, no people), matched letter for letter (capitals
    set aside, and i, l and 1 read as one letter) and to exactly one entry, with "City" and "Municipal" read as the
    court's kind words where the place's own name does not have them (Ogden City, but Salt Lake City). Machine reading
    misreads a letter now and then (Eme1y County, Justice Comt), so a name of five letters or more may differ by one
    letter when exactly one place then fits, and the office title is written again from the places matched. A question
    whose court cannot be matched is not loaded: it is counted in a gap, never guessed.
  - The counties (county_ids). The certification names the court, not the county: a county court's county, and for a
    city or town the county or counties the Census Bureau's list puts it in (Draper lies in two). Who votes is the
    law's, not the list's: Utah Code 78A-7-203 and 20A-12-201(7) put a county justice court judge, and a municipal one
    in a town or a city of the fourth or fifth class, on ballots throughout the county, and a judge of a larger city's
    court only on that city's ballots; the certification leaves the placing to election officers, and each contest's
    note says so.
  - The names. The Candidate Filings page has no table for justice court judges, so the name is the certification's
    own reading (capitals; machine reading's l, 1 and 0 inside a name are I and O), shown in ordinary capitals.
    Controls: the group is read twice by two routes and must agree, and its Yes/No answer lines are counted against
    the questions; and each judge is looked up in the Lieutenant Governor's 2026 Voter Information Pamphlet, whose
    Judicial Performance Evaluation Commission pages give a typed "Honorable NAME" and "Locations Served". The pamphlet
    is read in memory and never saved: it carries profiles and other matter this archive does not read. Only those two
    lines of each justice court page are kept (ballot_cache/ut/local/ut_2026_pamphlet_justice_courts.json), and they
    change nothing: a judge it does not have, or courts it lists differently, is printed as a CHECK line.
  - ids. A county court's jurisdiction is the county (its 5-digit code); a single city's or town's court is the place,
    UT-M-<Census place code>, with a row in sl_places (kind mcd); a question naming several places has no single id.
    race_id is 2026-UT-JCRET-<place and county codes>-<FAMILY NAME>.
  - The candidate row is written as Utah's other retention rows are (order 1, incumbent 1: a retention election is by
    law the sitting judge's), but the contest's holder_* columns stay empty, as for every local office.

Not loaded, and said so in sl_gaps and sl_notes: county offices and local school board contests. Utah has no statewide
list of them: each county clerk certifies and posts the county's own (Utah Code 20A-5a-210), so every one of the 29
counties has a county gap, and special district boards have a state one. City and town offices are elected in odd
years (20A-1-202). Ballot questions are never loaded.

Sources for the state races, the Lieutenant Governor's own and nothing else (the same files ballot/lists/ut.py reads for
Congress, and its cached copies in ballot_cache/ut/):

  - The "2026 General Election Certification" (the ***AMENDED*** copy signed September 21, 2026, linked as "Official
    Certified Candidates" from vote.utah.gov's Current Election Information page). It says the names "shall appear on the
    2026 General Election ballot as written and in the order listed", so its order is the ballot order. Each race is
    headed "Utah Senate District N." / "Utah House of Representatives District N." / "Utah State Board of Education
    District N.", followed by a sentence naming the counties the district reaches, and lists Candidate and Party only:
    the certification prints no address, telephone, e-mail or website at all. It is a signed scan with a machine-read
    text layer, so every name is matched to the office's own typed "2026 Candidate Filings" page in the same race and
    party, and the typed spelling is kept. The counties in each heading sentence are a race's county_ids.
  - "2026 Candidate Filings" (vote.utah.gov/2026-candidate-filings/): its State Senate, State House and State School
    Board tables (Candidate, Office, Party, Status: the only columns they have) and its State Judicial table (Judicial
    Retention, Status). The page is read in memory and the column headings are checked before any cell is kept; only those
    columns are saved, as ballot_cache/ut/ut_2026_candidate_filings_state.json. It gives the typed spelling, who withdrew,
    was disqualified or died (left off and counted), who went out at a party convention, and who went out in the primary.
  - The "2026 Write-In Certification": declared write-in candidates under each district heading, stored as write-ins
    (no party, no ballot position; their names are not printed on the ballot), each matched to a Write-In row of the
    filings page.
  - The June 23 primary. A party primary is held only where two or more qualify for that party's ballot. Multi-county
    races: the results system's "All Results Excel" workbook (electionresults.utah.gov, Primary06232026), Summary Results
    sheet, with ballots cast, over- and undervotes; controls: its Precinct Results sheet (one row per county) sums to every
    total, candidates + over + under = ballots cast, and the signed statewide canvass ("2026 Primary Election
    Certification") agrees candidate by candidate, in total and county by county. Single-county races, which the canvass
    says were certified by the county and lists by nominee only: the county's own final official summary report posted
    on the same results system (Salt Lake, Davis and Utah counties this year); controls: the candidates are the filings
    page's nominee and those it marks Out in Primary, the printed contest total where there is one, and the leader is the
    canvass's nominee and the certification's candidate. No write-in votes are reported.

Today's holders come from state_ut.sqlite (the Open States roster): current legislators by chamber and district (only
ids, names, parties and districts are read; the roster's contact columns are never selected). A candidate is the
sitting member (incumbent 1, state_member_id) only when the name fits that seat's holder and no other candidate in the
race fits. The roster does not carry the State Board of Education. A judge standing for retention is by law the sitting
judge, so that name is the holder and is marked incumbent.

The privacy rule: only office, district, candidate name, party, ballot order, status and votes are read from any list.
Names are printed in capitals; the page shows ordinary capitals (a sitting member as the roster spells them) and says so.
No photos, ages, websites, biographies or money reach the database. The loader's own notes, gap reasons and source notes
are tried against the page's contact scan before they are written, and a name or court that looks like contact details
is left out and counted, never printed. When a layout does not read, the message names the file and the check, never
the line.

Usage: python ballot/state_local_ut.py <database file> [--cache <folder>]
"""

import datetime as dt
import difflib
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import openpyxl  # noqa: E402

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import SUFFIXES, fold, name_parts, party_code  # noqa: E402
from ballot.lists import ut as fed  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, join, lines, rows as pdf_rows  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS, NAME = "UT", "49", "Utah"
GENERAL, PRIMARY = "2026-11-03", "2026-06-23"
CACHE = os.path.join(HERE, "ballot_cache", "ut")
ROSTER_DB = os.path.join(HERE, "state_ut.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
AGENCY = "Utah Office of the Lieutenant Governor, Office of Elections"

# the three partisan bodies: certification section, heading, filings table, results and canvass words, and the keys
BODIES = {
    "SENATE": dict(key="SS", kind="state_senate", level="legislature", office="State Senator", place="Senate District",
                   seats=29, roster="Senate", section="STATESENATOR", head=r"Utah\w{0,2}?Senate", filings="State Senate",
                   results="State Senate", canvass="Utah Senate", summary=("SENATE", "Senate")),
    "HOUSE": dict(key="SH", kind="state_house", level="legislature", office="State Representative", place="House District",
                  seats=75, roster="House", section="STATEREPRESENTATIVE", head=r"UtahHouseof\w{12,18}?",
                  filings="State House", results="State House", canvass="Utah House", summary=("HOUSE", "House")),
    "SBOE": dict(key="SBOE", kind="state_board_of_education", level="statewide", office="Member of the State Board of Education",
                 place="State Board of Education District", seats=15, roster=None, section="STATEBOARDOFEDUCATIONMEMBER",
                 head=r"UtahStateBoardof\w{7,11}?", filings="State School Board", results="State Board of Education",
                 canvass="State Board of Education", summary=("SCHOOL BOARD", "Board of Education")),
}
OTHER_SECTIONS = {"FEDERALOFFICE": "FEDERAL", "NONPARTISANJUDICIALRETENTIONELECTIONS": "JUDICIAL",
                  "PROPOSEDCONSTITUTIONALAMENDMENTS": "AMEND", "REGISTEREDPOLITICALPARTIES": "PARTIES"}
PARTIES = ["Democratic", "Republican", "Libertarian", "Constitution", "Independent American", "Forward", "Unaffiliated",
           "Green", "Peoples' Freedom"]
CODES = dict(fed.CODES)                                   # results' party codes -> party names
ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]
FILINGS_HEADS = ["Candidate", "Office", "Party", "Status"]
JUDICIAL_HEADS = ["Judicial Retention", "Status"]
GONE = re.compile(r"withdr|disqual|remov|deceas", re.I)
KNOWN_STATUS = {"Election Candidate", "Out in Convention", "Out in Primary", "Write-In"}

CAPS = "Utah's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "Utah's results print names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
RETENTION = ("A retention election (Utah Code 20A-12-201, as the certification cites): voters answer Yes or No on whether "
             "the judge stays in office. There is no opponent.")

SRC = {"general": "ut-ltg-2026-state-general-certification", "write_in": "ut-ltg-2026-state-write-in-certification",
       "filings": "ut-ltg-2026-state-candidate-filings", "results": "ut-ltg-2026-state-primary-results",
       "canvass": "ut-ltg-2026-state-primary-canvass", "roster": "ut-openstates-roster", "counties": "ut-census-cb-2024-county",
       "places": "ut-census-2020-place-codes", "pamphlet": "ut-ltg-2026-voter-information-pamphlet"}

# ---- the local level: the justice courts' retention questions, and what is not loaded yet
LOCAL_DIR = "local"                                       # ballot_cache/ut/local/
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st49_ut_place2020.txt"
PLACE_FILE = "census_st49_ut_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
PAMPHLET_URL = "https://vote.utah.gov/wp-content/uploads/2026/09/2026-Voter-Information-Pamphlet.pdf"
PAMPHLET_FILE = "ut_2026_pamphlet_justice_courts.json"
PAMPHLET_NAME = re.compile(r"^Honorable\s+([A-Z][A-Za-z.'\- ]{2,50})$")
CLERKS_URL = "https://vote.utah.gov/contact-your-county-election-officials/"
CODE_URL = "https://le.utah.gov/xcode/"
LAW = {"general": CODE_URL + "Title20A/Chapter1/20A-1-S201.html", "justice": CODE_URL + "Title78A/Chapter7/78A-7-S203.html",
       "notice": CODE_URL + "Title20A/Chapter5a/20A-5a-S210.html", "districts": CODE_URL + "Title17B/Chapter1/17B-1-S306.html"}
JUSTICE_KIND = "justice_court_retention"
JUSTICE_COUNTY = "A county's justice court: voters throughout {where} decide (Utah Code 78A-7-203)."
JUSTICE_PLACED = ("Who votes depends on the court (Utah Code 78A-7-203): the whole county for a county's justice court or one in a "
                  "town or a city of the fourth or fifth class, only the city's own voters in a larger city. The certification "
                  "leaves that placing to election officers.")
CALENDAR = ("On November 3, 2026 Utah's counties elect the county officers whose four-year terms end this year (as a rule, "
            "commission or council seats and the county clerk, auditor, sheriff and attorney), local school boards elect about "
            "half their members, special districts on the even-year cycle fill board seats, and justice court judges whose terms "
            "end face a yes or no retention vote. City and town offices, and special districts on the municipal cycle, are "
            "elected in November of odd-numbered years, next in 2027. The county treasurer, recorder, surveyor and assessor are, "
            "as a rule, on the other four-year cycle, next in 2028.")
CALENDAR_SOURCE = ("Utah Code 20A-1-201 and 20A-1-202 (what each November election fills), 17-66-202 (county officers' terms), "
                   "20A-14-202 (local school boards), 17B-1-306 (special districts) and 78A-7-203 (justice court judges)")
GAP_WHAT = "county offices and local school board races"
GAP_REASON = ("{county}'s clerk certifies and posts the candidates for county office and local school boards for the county alone "
              "(Utah Code 20A-5a-210); the statewide list does not carry them, and the county's notice has not been read into this "
              "archive yet.")
DISTRICT_GAP = ("Special districts that elect board members in even years certify their candidates to their own county clerks "
                "(Utah Code 17B-1-306); there is no statewide list of them, and none has been read into this archive yet.")
UNREAD_GAP = ("Some retention questions for justice court judges on the Lieutenant Governor's certification ({n} in all) could not be "
              "read from its machine-read text and matched to a county, city or town, so they are left out rather than guessed.")
# what the page's own guard drops from a note (build_ballot_state_dev.py): a number, then within a few words a street word
PAGE_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|"
                         r"Ln|Lane|Way|Ct|Court|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def fail(msg):
    raise SystemExit(f"Utah (state races): {msg}")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mdate(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def compact(t):
    return re.sub(r"[^A-Za-z0-9]", "", t or "")


def digits(t):
    return int(t.replace("l", "1").replace("I", "1").replace("O", "0").replace("o", "0"))


def race_id(body, district):
    return f"2026-{STATE}-{BODIES[body]['key']}{district}"


def ratio(a, b):
    return difflib.SequenceMatcher(None, fed.letters(a), fed.letters(b)).ratio()


def ordinary(caps):
    """KIRK CULLIMORE -> Kirk Cullimore; "CJ" CHRISTINA HERNANDEZ -> "CJ" Christina Hernandez; JR BIRD -> JR Bird;
    JASON O'DELL -> Jason O'Dell; ANNETTE MCRAE -> Annette McRae. A two-letter word with no vowel is initials run
    together and stays in capitals; JR, SR and Roman numerals after the first word are suffixes."""
    words_ = caps.split()
    out = []
    for i, w in enumerate(words_):
        core = re.sub(r"[^A-Za-z]", "", w)
        if i and re.fullmatch(r"(JR|SR)\.?,?", w):
            out.append(w.title())
        elif i and re.fullmatch(r"[IVX]+,?", w):
            out.append(w)
        elif len(core) == 2 and not re.search(r"[AEIOUY]", core.upper()):
            out.append(w)
        else:
            parts = []
            for p in w.split("-"):
                p2 = p.capitalize()
                p2 = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p2)
                p2 = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), p2)
                parts.append(p2)
            out.append("-".join(parts))
    return " ".join(out)


def get_page(url):
    """A page in memory, asked at most three times."""
    for attempt in range(3):
        try:
            return fed.decode(net.get(url, accept="text/html"))
        except Exception as e:                               # noqa: BLE001
            if attempt == 2:
                fail(f"{url} did not answer after three tries ({type(e).__name__}); a browser would be needed")
            time.sleep(5 * (attempt + 1))


# ---------------------------------------------------------------- the filings page

def state_filings(folder, say, refresh=False):
    """{"rows": [{body, district, flags, name, party, status}], "judicial": [{question, status}], "updated"} from the
    State Senate, State House, State School Board and State Judicial tables; allowed columns only, kept two days."""
    path = os.path.join(folder, "ut_2026_candidate_filings_state.json")
    if not refresh and fed.fresh(path, 2):
        return json.load(open(path, encoding="utf-8"))
    page = get_page(fed.FILINGS_URL)
    m = re.search(r"Last updated:\s*(\d{1,2})/(\d{1,2})/(\d{4})", page)
    updated = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    want = {BODIES[b]["filings"]: b for b in BODIES}
    rows, judicial, seen = [], [], set()
    for hm in re.finditer(r"<h3[^>]*>(.*?)</h3>", page, re.S):
        title = fed.text(hm.group(1))
        if title not in want and title != "State Judicial":
            continue
        table = re.search(r"<table.*?</table>", page[hm.end():], re.S)
        if not table:
            fail(f"the filings page's {title} heading has no table")
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S)
        heads = [fed.text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", trs[0], re.S)]
        expect = JUDICIAL_HEADS if title == "State Judicial" else FILINGS_HEADS
        if heads != expect:                 # checked before a single cell is kept: a new column could be contact data
            fail(f"the filings page's {title} table no longer has exactly the columns {expect} ({len(heads)} columns)")
        seen.add(title)
        for n, tr in enumerate(trs[1:], start=1):
            cells = [fed.text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) != len(heads):
                fail(f"row {n} of the filings page's {title} table does not line up with its headings")
            rec = dict(zip(heads, cells))
            if title == "State Judicial":
                judicial.append({"question": rec["Judicial Retention"], "status": rec["Status"]})
                continue
            m = re.fullmatch(r"State (Senate|House|School Board) District (\d+)((?: \([^)]*\))*)", rec["Office"])
            if not m or m.group(1) != title.replace("State ", ""):
                fail(f"an office on the filings page's {title} table that is not read ({rec['Office']!r})")
            flags = re.findall(r"\(([^)]*)\)", m.group(3))
            rows.append({"body": want[title], "district": int(m.group(2)), "flags": flags, "name": rec["Candidate"],
                         "party": rec["Party"], "status": rec["Status"]})
    missing = sorted((set(want) | {"State Judicial"}) - seen)
    if missing:
        fail(f"the filings page no longer has its {', '.join(missing)} table(s)")
    kept = {"url": fed.FILINGS_URL, "updated": updated, "rows": rows, "judicial": judicial}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Candidate Filings (updated {updated}): {len(rows)} rows for the Legislature and the State Board, "
        f"{len(judicial)} judicial retention rows")
    return kept


RETAIN = re.compile(r"^Shall (.+?) be retained in the office of (.+?)\??$")


def court_of(office):
    """(office_kind, district number or None) from the words after 'the office of', typed or machine-read."""
    o = re.sub(r"\s+", " ", office)
    c = compact(o).lower()
    if "supremecourt" in c:
        return "supreme_court_retention", None
    if "courtofappeals" in c:
        return "court_of_appeals_retention", None
    m = re.search(r"of the (\w+) (Judicial|Juvenile Co\w*) District", o)
    if m and m.group(1) in ORDINALS:
        kind = "district_court_retention" if "districtco" in c and m.group(2) == "Judicial" else "juvenile_court_retention"
        if kind == "juvenile_court_retention" and "juvenileco" not in c:
            return None, None
        return kind, ORDINALS.index(m.group(1)) + 1
    if "justice" in c:
        return "justice_court_retention", None
    return None, None


# ---------------------------------------------------------------- places

def counties():
    """{GEOID: (name, 'Salt Lake County')} for Utah's 29 counties, from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, max_age_days=3650, tries=3)
    z = zipfile.ZipFile(COUNTY_ZIP)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[str(rec["GEOID"])] = (str(rec["NAME"]), str(rec["NAMELSAD"]))
    if len(out) != 29:
        fail(f"the county file gives {len(out)} Utah counties, not 29")
    return out


def counties_in(text, cmap):
    """The counties a heading's sentence names ('... consists of Beaver and Iron Counties as well as portions of Juab
    ...'), read up to the sentence's end. Machine reading misreads a letter now and then (Eme1y), so a county name of five
    letters or more that is not found as written is accepted with one letter different. Returns (GEOIDs, read loosely)."""
    m = re.search(r"cons\w*\s*of\s*(.*)", text or "")
    if not m:
        return set(), set()
    desc = re.split(r"\.(?:\s|$)", m.group(1), maxsplit=1)[0]
    L = fed.letters(desc)
    found, loose = set(), set()
    for geoid, (name, _full) in cmap.items():
        if fed.letters(name) in L:
            found.add(geoid)
    # one letter misread: compared word for word (one or two words, for Box Elder and Salt Lake), never across the
    # joins between words, where "Elder and" would pass for Grand
    words_ = [w for w in (fed.letters(x) for x in re.split(r"[\s,]+", desc)) if w]
    spans = {"".join(words_[i:i + n]) for n in (1, 2) for i in range(len(words_) - n + 1)}
    for geoid, (name, _full) in cmap.items():
        key = fed.letters(name)
        if geoid in found or len(key) < 5:
            continue
        if any(len(s) == len(key) and sum(a != b for a, b in zip(s, key)) == 1 for s in spans):
            loose.add(geoid)
    return found | loose, loose


# ---------------------------------------------------------------- the certifications

def section_of(t):
    c = compact(t).upper()
    if t != t.upper() or not c:
        return None
    for b, spec in BODIES.items():
        if c == spec["section"]:
            return b
    return OTHER_SECTIONS.get(c)


def head_of(body, t):
    """The district of a heading 'Utah Senate District 12. Utah Senate District 12 consists of ...' (machine reading
    splits and misreads letters: Distl'ict, Di stric t), or None."""
    m = re.match(BODIES[body]["head"] + r"D\w{3,6}?ct([0-9lIO]{1,2})(?![0-9])", compact(t))
    return digits(m.group(1)) if m else None


def party_of(read):
    c = compact(read).lower()
    hit = difflib.get_close_matches(c, [compact(p).lower() for p in PARTIES], n=1, cutoff=0.75)
    return PARTIES[[compact(p).lower() for p in PARTIES].index(hit[0])] if hit else None


def general_list(path, cmap):
    """Everything the certification lists for the state: races {(body, district): {"head", "counties", "loose",
    "special", "rows": [(name as read, party)]}} in the certification's order, retention questions [(group, district,
    name as read, office as read, county GEOIDs)], the count of amendments, the date it was signed and whether it is
    amended."""
    races, retention, section, race, edge, group = {}, [], None, None, None, None
    signed, amended, day, amendments, pending, head_parts = "", False, None, 0, None, []
    jd_text, last_edge = {}, None
    for page, cells in fed.scan_rows(path):
        t = fed.words(cells)
        if page == 1:
            amended = amended or "AMENDED" in t
            m = re.search(r"this (\d{1,2})(?:st|nd|rd|th)\b", t)
            day = int(m.group(1)) if m else day
            m = re.search(r"day of ([A-Z][a-z]+), (\d{4})", t)
            if m and m.group(1) in fed.MONTHS and day:
                signed = f"{m.group(2)}-{fed.MONTHS.index(m.group(1)) + 1:02d}-{day:02d}"
            continue
        sec = section_of(t)
        if sec:
            section, race, edge, group, pending = sec, None, None, None, None
            continue
        if section in BODIES:
            d = head_of(section, t)
            if d is not None:
                if (section, d) in races:
                    fail(f"the certification lists {BODIES[section]['place']} {d} twice")
                race, edge, head_parts = (section, d), None, [t]
                races[race] = {"rows": [], "head": ""}
                continue
            if race and edge is None:
                if difflib.SequenceMatcher(None, compact(t).lower()[:9], "candidate").ratio() >= 0.75:
                    # the Candidate / Party heading (machine-read: Ca11didate, Candidale, Candi date)
                    # the Party heading's position: the first piece well to the right of "Candidate" (it can be split: Pa rty)
                    right = [p for p, w in cells if p > cells[0][0] + 100 and w.strip()]
                    if right:
                        edge = last_edge = min(right) - 15
                    elif last_edge is not None:                    # "Party" not read at all: the column has not moved
                        edge = last_edge
                    else:
                        fail(f"the Candidate/Party heading under {BODIES[race[0]]['place']} {race[1]} is not read")
                    races[race]["head"] = " ".join(head_parts)
                else:
                    head_parts.append(t)
                continue
            if race and edge is not None:
                name = fed.words([c for c in cells if c[0] < edge])
                party = fed.words([c for c in cells if c[0] >= edge])
                if name and party:
                    races[race]["rows"].append((name, party))
                elif name or party:
                    fail(f"a row under {BODIES[race[0]]['place']} {race[1]} on the certification has a name or a party but not both")
            continue
        if section == "JUDICIAL":
            m = re.match(r"^(Supreme Court and Court of Appeals|Justice Courts|(\w+) Judicial District)\.", t)
            if m and not t.startswith("Shall"):
                if m.group(2):
                    if m.group(2) not in ORDINALS:
                        fail(f"a judicial district heading that is not read ({m.group(1)})")
                    group = ("district", ORDINALS.index(m.group(2)) + 1)
                    jd_text[group[1]] = t
                else:
                    group = ("appellate", None) if m.group(1).startswith("Supreme") else ("justice", None)
                pending = None
                continue
            if group and group[0] == "district" and pending is None and not t.startswith("Shall") and "?" not in t \
                    and not compact(t).lower().startswith("yes"):
                jd_text[group[1]] += " " + t                       # the heading's sentence runs on to a second line
                continue
            if t.startswith("Shall"):
                pending = t
            elif pending is not None and not compact(t).lower().startswith("yes"):
                pending += " " + t
            if pending is not None and pending.rstrip().endswith("?"):
                q = re.sub(r"\s+", " ", pending).strip()
                m = RETAIN.match(q)
                if not m or not group:
                    fail("a retention question on the certification that is not read")
                retention.append((group[0], group[1], m.group(1), m.group(2)))
                pending = None
            continue
        if section == "AMEND" and re.match(r"^Constitutional Amendment [A-Z]\.", t):
            amendments += 1
    for race, r in races.items():
        head = r["head"]
        found, loose = counties_in(head, cmap)
        r["counties"], r["loose"] = sorted(found), sorted(loose)
        m = re.search(r"District\s*([0-9lIO]{1,2})\s*cons", head)
        if m and digits(m.group(1)) != race[1]:
            fail(f"{BODIES[race[0]]['place']} {race[1]}'s heading names district {m.group(1)} in its sentence")
        r["special"] = 1 if re.search(r"unexpired\s*term", head, re.I) else 0
    jd_counties = {d: sorted(counties_in(t, cmap)[0]) for d, t in jd_text.items()}
    retention = [(g, d, n, o, jd_counties.get(d, []) if g == "district" else []) for g, d, n, o in retention]
    return races, retention, amendments, signed, amended


def write_in_list(path):
    """[((body, district), name as read)] from the state parts of the Write-In Certification, and the date it was signed."""
    out, section, race, day, signed = [], None, None, None, ""
    for page, cells in fed.scan_rows(path):
        t = fed.words(cells)
        if page == 1:
            m = re.search(r"\bthis (\d{1,2})(?:st|nd|rd|th)\b", t)
            day = day or (int(m.group(1)) if m else None)
            m = re.search(r"(ugust|eptember|ctober),? (\d{4})", t)
            if m and day and not signed:
                signed = f"{m.group(2)}-{ {'ugust': 8, 'eptember': 9, 'ctober': 10}[m.group(1)]:02d}-{day:02d}"
            continue
        sec = section_of(t)
        if sec:
            section, race = sec, None
            continue
        if section in BODIES:
            d = head_of(section, t)
            if d is not None:
                race = (section, d)
                continue
            if race and re.search(r"[a-z]", t) is None and re.search(r"[A-Z]", t):
                out.append((race, t))
    return out, signed


# ---------------------------------------------------------------- the primary

RESULTS_OFFICE = re.compile(r"^([A-Z]{3}) (State Senate|State House|State Board of Education) District (\d+)$")
RESULTS_BODY = {BODIES[b]["results"]: b for b in BODIES}


def primary_book(path):
    """{(body, district, party code): {"names": {name: votes}, "cast", "over", "under", "write_ins", "counties": {county: {name: votes}}}}
    for the state contests of the All Results workbook (the multi-county ones)."""
    if open(path, "rb").read(2) != b"PK":
        fail("the All Results workbook is not a workbook")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    def sheet(title, need):
        it = wb[title].iter_rows(values_only=True)
        heads = [str(c or "").strip() for c in next(it)]
        if not all(k in heads for k in need):
            fail(f"the All Results workbook's {title} columns changed")
        idx = {k: heads.index(k) for k in need}
        for r in it:
            yield {k: r[i] for k, i in idx.items()}

    def key_of(office):
        o = re.sub(r"\s+", " ", str(office or "")).strip()
        m = RESULTS_OFFICE.fullmatch(o)
        if m:
            return RESULTS_BODY[m.group(2)], int(m.group(3)), m.group(1)
        if o and "U.S." not in o:
            fail(f"a contest in the All Results workbook that is not read ({o!r})")
        return None

    out = {}
    for r in sheet("Summary Results", ("Office Name", "Ballot Name", "Party", "Total")):
        key = key_of(r["Office Name"])
        if not key:
            continue
        f = out.setdefault(key, {"names": {}, "cast": None, "over": 0, "under": 0, "write_ins": 0, "counties": {}, "blank_party": []})
        name, votes = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip(), int(r["Total"] or 0)
        if name == "Ballots Cast":
            f["cast"] = votes
        elif name in ("Over Votes", "Under Votes"):
            f[name.split()[0].lower()] = votes
        elif "write" in name.lower():
            f["write_ins"] += votes
        else:
            if r["Party"] and CODES.get(key[2]) != str(r["Party"]).strip():
                fail(f"{name} is listed as {r['Party']} in the {key[2]} primary for {key[0]} {key[1]}")
            if not r["Party"]:
                f["blank_party"].append(name)
            f["names"][name] = votes
    for r in sheet("Precinct Results", ("Precinct", "Office Name", "Ballot Name", "Total")):
        key = key_of(r["Office Name"])
        if key in out:
            cell = out[key]["counties"].setdefault(str(r["Precinct"]).strip(), {})
            name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
            cell[name] = cell.get(name, 0) + int(r["Total"] or 0)
    wb.close()
    return out


CANVASS_HEAD = re.compile(r"^(Utah Senate|Utah House|State Board of Education) District (\d+)$")
CANVASS_BODY = {BODIES[b]["canvass"]: b for b in BODIES}


def canvass(path, counts):
    """From the statewide canvass: {(body, district, party): {"names", "votes", "county_sums", "total"}} for the
    multi-county state primaries, and {(body, district): (party, nominee)} for the single-county ones it lists by
    nominee only. A page's candidates run across the page in its races' order; counts gives each race's number of
    candidates (from the workbook), and the names must then agree."""
    pdf = PDF(open(path, "rb").read())
    multi, single = {}, {}
    for page, res in pdf.pages():
        heads, parties, names, per, contest, cnty, want, single_page = [], [], [], [], [], [], None, False
        for _y, runs in pdf_rows(pdf, page, res):
            row = fed.cells(runs)
            texts = [c[2] for c in row]
            if "Single-County Races" in " ".join(texts):
                single_page = True
            if single_page:
                m = CANVASS_HEAD.fullmatch(texts[0]) if texts else None
                if m and len(texts) == 3:
                    single[(CANVASS_BODY[m.group(1)], int(m.group(2)))] = (texts[1], texts[2])
                elif m:
                    fail("a single-county line of the statewide canvass that is not read")
                continue
            hs = [(c[0], CANVASS_BODY[m.group(1)], int(m.group(2))) for c in row for m in [CANVASS_HEAD.fullmatch(c[2])] if m]
            if hs:
                heads = sorted(hs)
                continue
            if not heads:
                continue
            nums = [fed.number(c[2]) for c in row]
            if not parties and texts and all(t in CODES.values() for t in texts):
                parties = texts
            elif texts and texts[0].startswith("Total Votes Cast Per"):
                want = "per"
            elif texts and texts[0].startswith("Total Votes Cast in"):
                want = "contest"
            elif texts and texts[0].endswith("County"):
                cnty.append([(c[1], fed.number(c[2])) for c in row[1:] if fed.number(c[2]) is not None])
            elif row and all(n is not None for n in nums) and want:
                if want == "per":
                    per = [(c[1], n) for c, n in zip(row, nums)]
                else:
                    contest = nums
                want = None
            elif parties and not names and row and all(t == t.upper() and re.search(r"[A-Z]", t) for t in texts):
                names = texts
        if not heads:
            continue
        if not (len(parties) == len(heads) == len(contest) and names and len(names) == len(per)):
            fail("a state page of the statewide canvass was not read whole")
        sums = [0] * len(per)
        for row in cnty:
            for end, n in row:
                k = min(range(len(per)), key=lambda i: abs(per[i][0] - end))
                if abs(per[k][0] - end) > 12:
                    fail("a county figure on the statewide canvass lines up with no candidate's column")
                sums[k] += n
        at = 0
        for (_x, body, district), party, total in zip(heads, parties, contest):
            n = counts.get((body, district, party), 0)
            span = range(at, at + n)
            at += n
            multi[(body, district, party)] = {"names": [names[i] for i in span if i < len(names)],
                                              "votes": [per[i][1] for i in span if i < len(per)],
                                              "county_sums": [sums[i] for i in span if i < len(sums)], "total": total}
        if at != len(names):
            fail("the statewide canvass's candidates do not add up to the workbook's races on a state page")
    return multi, single


LABELS = re.compile(r"^(Vote For|Times Cast|Total|TOTAL|Candidate|Overvotes|Undervotes|Over Votes|Under Votes|Contest Totals|"
                    r"Registered|Ballots|Precincts|Summary Results|Election Summary|Results)\b")
PAGE_MARK = re.compile(r"\bPage:? \d+ of \d+")


def summary_head(t):
    """(body, district, party code) of a state contest heading in a county summary report, in any of the three layouts
    posted this year: 'STATE SENATE DISTRICT 13 (DEM) (Vote for 1)' (Salt Lake), 'REP State House District 14' (Davis),
    'REP Republican for Senate District 21' (Utah)."""
    words_ = {BODIES[b]["summary"][0]: b for b in BODIES}
    m = re.match(r"^STATE (SENATE|HOUSE|SCHOOL BOARD) DISTRICT (\d+) \(([A-Z]{3})\)", t)
    if m:
        return words_[m.group(1)], int(m.group(2)), m.group(3)
    words2 = {BODIES[b]["summary"][1]: b for b in BODIES}
    m = re.match(r"^([A-Z]{3}) (?:State |(?:Republican|Democratic) for )(Senate|House|Board of Education) District (\d+)\b", t)
    if m:
        return words2[m.group(2)], int(m.group(3)), m.group(1)
    return None


def county_summary(path):
    """{(body, district, party code): {"names": {name: votes}, "total", "over", "under", "contest"}} for the state contests
    of a county's final official summary report."""
    out, cur = {}, None
    for _page, _y, t in lines(path):
        t = re.sub(r"\s+", " ", t).strip()
        if PAGE_MARK.search(t):
            continue
        key = summary_head(t)
        if key:
            cur = out.setdefault(key, {"names": {}, "total": None, "over": None, "under": None, "contest": None})
            continue
        if cur is None:
            continue
        if re.match(r"^(REP|DEM|LIB|CON|IAP|FWD|GRN|UNA|NON|NP) [A-Z][a-z]", t) or re.search(r"\(Vote for \d+\)$", t, re.I):
            cur = None                                           # another contest begins
            continue
        m = re.match(r"^(Total Votes|Contest Totals|Overvotes|Undervotes) ([\d,]+)$", t)
        if m:
            cur[{"Total Votes": "total", "Contest Totals": "contest", "Overvotes": "over", "Undervotes": "under"}[m.group(1)]] = \
                int(m.group(2).replace(",", ""))
            if m.group(1) in ("Total Votes", "Contest Totals"):
                cur = None
            continue
        if LABELS.match(t):
            continue
        m = re.fullmatch(r"(.+?) ([\d,]+)(?: [\d.]+%)?", t)
        if m and fed.number(m.group(2)) is not None:
            cur["names"][m.group(1).strip()] = fed.number(m.group(2))
    return out


# ---------------------------------------------------------------- holders

def roster():
    """{(chamber, district): {id, name, party, forms}} for today's legislators; only ids, names, parties and districts."""
    con = sqlite3.connect(f"file:{ROSTER_DB}?mode=ro", uri=True)
    seats = {}
    for bid, first, last, full, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1 AND state = 'UT'"):
        forms = [f for f in [full, f"{first or ''} {last or ''}".strip()] + [o.strip() for o in (other or "").split(";")] if f]
        key = (chamber, str(district))
        if key in seats:
            fail(f"the roster has two current members for {chamber} District {district}")
        seats[key] = {"id": bid, "name": full or f"{first} {last}", "party": party, "forms": forms,
                      "first": first or "", "last": last or ""}
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, as_of


def fits_holder(name, holder):
    cand = name_parts(name)
    return any(fits(cand, name_parts(f)) for f in holder["forms"])


# ---------------------------------------------------------------- the local level: justice courts

def own_words(text, what):
    """The loader's own sentence, tried against the contact scan the check and the page apply (the strict one: no web
    address, e-mail or telephone, and no number followed within a few words by a street word such as Court or Place). A
    sentence that would be dropped there is a mistake in this file, so it stops the load and says which sentence."""
    if contact_like(text, True) or PAGE_STREET.search(text):
        fail(f"the loader's own words for {what} would be dropped by the page's contact scan; reword them")
    return text


def bare(text):
    """Letters only, for comparing a machine-read word with a typed one whatever the capitals: i, l, L and 1 all read as
    one letter, 0 as O (fed.letters, which keeps capital L apart, after lower-casing)."""
    return fed.letters((text or "").lower())


def near(word, target, cutoff=0.8):
    return difflib.SequenceMatcher(None, bare(word), bare(target)).ratio() >= cutoff


def and_words(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def read_places(folder, cmap, say):
    """({letters of a place's bare name: [{code, name, base, cids}]}, rows in the file) for Utah's incorporated cities
    and towns, from the Census Bureau's 2020 place codes file: names, codes and the counties each lies in, nothing about
    people, so the file is kept whole and asked for once."""
    path = os.path.join(folder, PLACE_FILE)
    net.download(PLACE_URL, path, max_age_days=3650, tries=3, say=say)
    geoid_of = {full: g for g, (_n, full) in cmap.items()}
    out, n = defaultdict(list), 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        if fh.readline().rstrip("\r\n").split("|") != PLACE_HEAD:
            fail(f"{PLACE_FILE}: the header is not the one this loader was checked against")
        for k, line in enumerate(fh, start=2):
            if not line.strip():
                continue
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(PLACE_HEAD) or f[1] != FIPS or not re.fullmatch(r"\d{5}", f[2]):
                fail(f"{PLACE_FILE}: line {k} does not fit the header")
            n += 1
            if f[5] != "INCORPORATED PLACE":
                continue
            cids = [geoid_of.get(c) for c in f[8].split("~~~")]
            if not all(cids):
                fail(f"{PLACE_FILE}: line {k} names a county the county file does not have")
            base = re.sub(r"\s+(?:metro township|township|city|town)$", "", f[4])
            out[bare(base)].append({"code": f[2], "name": f[4], "base": base, "cids": sorted(cids)})
    return out, n, path


def place_named(base, places, loose=False):
    """The one city or town of that name (letters only), or None. Loose: a name of five letters or more with exactly one
    letter read differently, when exactly one place fits."""
    key = bare(base)
    if not key:
        return None
    if not loose:
        hits = places.get(key, [])
        return hits[0] if len(hits) == 1 else None
    if len(key) < 5:
        return None
    hits = [p for k, ps in places.items() if len(k) == len(key) and sum(a != b for a, b in zip(k, key)) == 1 for p in ps]
    return hits[0] if len(hits) == 1 else None


def county_named(base, cmap):
    """(GEOID, 1 if read loosely else 0) for 'Emery' or the machine-read 'Eme1y', or (None, 0)."""
    key = bare(base)
    exact = [g for g, (name, _full) in cmap.items() if bare(name) == key]
    if len(exact) == 1:
        return exact[0], 0
    if len(key) >= 5:
        hits = [g for g, (name, _full) in cmap.items()
                if len(bare(name)) == len(key) and sum(a != b for a, b in zip(bare(name), key)) == 1]
        if len(hits) == 1:
            return hits[0], 1
    return None, 0


def one_court_place(text, cmap, places):
    """One name in a court's title, with its kind words: 'Davis County', 'Draper Municipal', 'Ogden City', 'Salt Lake City
    Municipal', 'Santa Clara', or two places of one shared court joined by a hyphen ('Uintah-Huntsville Municipal').
    Returns {"label": the words as they are written again, "parts": [("C", GEOID) or ("M", place)], "loose": n} or None."""
    words_ = text.split()
    if not words_:
        return None
    muni = len(words_) > 1 and near(words_[-1], "Municipal")
    if muni:
        words_ = words_[:-1]
    tail = " Municipal" if muni else ""
    if not muni and len(words_) > 1 and near(words_[-1], "County"):
        geoid, loose = county_named(" ".join(words_[:-1]), cmap)
        return {"label": cmap[geoid][1], "parts": [("C", geoid)], "loose": loose} if geoid else None
    tries = [(" ".join(words_), "")]
    if len(words_) > 1 and near(words_[-1], "City", 0.75):
        tries.append((" ".join(words_[:-1]), " City"))                 # the place's own name first: Salt Lake City, Plain City
    for base, city in tries:
        p = place_named(base, places)
        if p:
            return {"label": p["base"] + city + tail, "parts": [("M", p)], "loose": 0}
    for base, city in tries:
        bits = [b.strip() for b in base.split("-")]
        if len(bits) > 1:
            ps = [place_named(b, places) for b in bits]
            if all(ps):
                return {"label": "-".join(p["base"] for p in ps) + city + tail, "parts": [("M", p) for p in ps], "loose": 0}
    for base, city in tries:
        p = place_named(base, places, loose=True)
        if p:
            return {"label": p["base"] + city + tail, "parts": [("M", p)], "loose": 1}
    return None


def court_list(body, cmap, places):
    """The courts in '<names> Justice Court(s)' with those last words taken off: names divided by commas and 'and', and
    the places of one shared court by '/'. Returns {"label", "parts", "courts": how many, "loose"} or None."""
    pieces = re.split(r"(\s*,\s*and\s+|\s*,\s*|\s+and\s+)", re.sub(r"\s+", " ", body or "").strip())
    label, parts, loose = "", [], 0
    for k, piece in enumerate(pieces):
        if k % 2:
            label += (", and " if "," in piece else " and ") if "and" in piece else ", "
            continue
        subs = [one_court_place(s.strip(), cmap, places) for s in piece.split("/")]
        if not all(subs):
            return None
        label += "/".join(s["label"] for s in subs)
        loose += sum(s["loose"] for s in subs)
        for s in subs:
            for part in s["parts"]:
                if part not in parts:
                    parts.append(part)
    return {"label": label, "parts": parts, "courts": len(pieces[0::2]), "loose": loose}


def justice_office(office, cmap, places):
    """A justice court question's office, 'Judge of the Naples City and Uintah County Justice Courts' as machine-read
    (Justice Comt, Cou1t, Com1s), into its courts; adds "plural_read", whether the scan's last word ends in s."""
    m = re.match(r"^Judge\s+of\s+the\s+(.+)$", re.sub(r"\s+", " ", office or "").strip())
    words_ = m.group(1).split(" ") if m else []
    if len(words_) < 3 or not near(words_[-2], "Justice") or not re.fullmatch(r"C[A-Za-z0-9]{3,5}", words_[-1]):
        return None
    got = court_list(" ".join(words_[:-2]), cmap, places)
    if got:
        got["plural_read"] = words_[-1].lower().endswith("s")
    return got


def served_list(text, cmap, places):
    """The pamphlet's 'Locations Served' line into places: courts divided by commas, each ending 'Justice Court', a court's
    seat after a dash set aside ('Daggett County Justice Court - Manila'). Returns the parts or None."""
    parts = []
    for item in re.split(r"\s*,\s*", re.sub(r"\s+", " ", text or "").strip().rstrip(",")):
        item = re.sub(r"\s+[-" + chr(0x2013) + r"]\s+.*$", "", item).strip()        # a hyphen or an en dash
        if not item.endswith(" Justice Court"):
            return None
        got = court_list(item[:-len(" Justice Court")], cmap, places)
        if not got:
            return None
        parts += [p for p in got["parts"] if p not in parts]
    return parts


def caps_name(read):
    """A judge's name as the certification prints it, in capitals. Inside a word that is otherwise capitals, machine
    reading's l and 1 are I and its 0 is O. None when anything but a name's own characters is left."""
    out = []
    for w in re.sub(r"\s+", " ", read or "").strip().split(" "):
        if not re.search(r"[a-km-z]", w):
            w = w.replace("l", "I").replace("1", "I").replace("0", "O")
        out.append(w)
    t = " ".join(out)
    return t if re.fullmatch(r"[A-Za-z][A-Za-z .'\"-]*[A-Za-z.]", t) and not contact_like(t, True) else None


def family_key(caps):
    """The family name's letters for a race id: the last word of the name as printed, a trailing JR or III set aside, a
    hyphen closed up (VO-DUC -> VODUC)."""
    words_ = [w for w in caps.split() if fold(w).replace(" ", "") not in SUFFIXES] or caps.split()
    return re.sub(r"[^A-Z]", "", words_[-1].upper())


def justice_section(path):
    """A second, separate reading of the certification's Justice Courts group, to check the first against: the questions
    [(name as read, office as read) or None] and the number of Yes/No answer lines printed under them."""
    out, answers, section, on, pending = [], 0, None, False, None
    for page, cells in fed.scan_rows(path):
        if page == 1:
            continue
        t = fed.words(cells)
        sec = section_of(t)
        if sec:
            section, on, pending = sec, False, None
            continue
        if section != "JUDICIAL":
            continue
        if not t.startswith("Shall") and re.match(r"^(Supreme Court and Court of Appeals|Justice Courts|\w+ Judicial District)\.", t):
            on, pending = t.startswith("Justice Courts"), None
            continue
        if not on:
            continue
        if compact(t).lower() == "yesno":
            answers += 1
            continue
        if t.startswith("Shall"):
            pending = t
        elif pending is not None:
            pending += " " + t
        if pending is not None and pending.rstrip().endswith("?"):
            m = RETAIN.match(re.sub(r"\s+", " ", pending).strip())
            out.append((m.group(1), m.group(2)) if m else None)
            pending = None
    return out, answers


def pamphlet_link():
    """The Voter Information Pamphlet's address as the Current Election Information page links it today, or None."""
    try:
        page = fed.decode(net.get(fed.INFO_URL, accept="text/html"))
    except Exception:                                        # noqa: BLE001
        return None
    for href, body in re.findall(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.S):
        if "Voter Information Pamphlet" in fed.text(body) and href.startswith("https://vote.utah.gov/"):
            return href
    return None


def pamphlet_judges(folder, say):
    """The justice court judges' pages of the Lieutenant Governor's 2026 Voter Information Pamphlet, as a control: each
    page's "Honorable NAME" line and its "Locations Served" line, and nothing else. The pamphlet is read in memory and
    never saved (it carries profiles and other matter this archive does not read); only these two cells per page are
    kept, for thirty days. Returns the kept record, or None when the pamphlet cannot be had (the control is then skipped)."""
    path = os.path.join(folder, PAMPHLET_FILE)
    if fed.fresh(path, 30):
        try:
            return json.load(open(path, encoding="utf-8"))
        except ValueError:                                   # a kept copy that does not read: ask again
            pass
    try:
        url = pamphlet_link() or PAMPHLET_URL
        time.sleep(1.0)                                      # one request at a time, a second apart
        raw = net.get(url, timeout=300, accept="application/pdf")
        time.sleep(1.0)
        if raw[:5] != b"%PDF-":
            raise ValueError("not a PDF")
        pdf = PDF(raw)
        judges, pages, unread, blanked = [], 0, 0, 0
        for page, res in pdf.pages():
            pages += 1
            try:
                rows_ = [re.sub(r"\s+", " ", join(runs) or "").strip() for _y, runs in pdf_rows(pdf, page, res)]
            except Exception:                                # noqa: BLE001  a page of pictures or an odd font: not a judge's page
                unread += 1
                continue
            at = next((i for i, t in enumerate(rows_) if t.startswith("Locations Served:")), None)
            if at is None:
                continue
            name = next((m.group(1).strip() for t in reversed(rows_[max(0, at - 3):at]) for m in [PAMPHLET_NAME.match(t)] if m), None)
            courts = rows_[at].split(":", 1)[1].strip()
            for t in rows_[at + 1:at + 4]:                   # a list that runs on: only lines made of court names
                if "Justice Court" in t and re.fullmatch(r"[A-Za-z/.', -]+", t):
                    courts += " " + t
                else:
                    break
            if not name or "Justice Court" not in courts:
                continue                                     # a judge of another court
            if contact_like(name, True) or contact_like(courts, True):
                blanked += 1
                continue
            judges.append({"name": name, "courts": courts})
        kept = {"url": url, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "pages": pages, "pages_unread": unread, "blanked": blanked, "judges": judges}
        json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        say(f"      Voter Information Pamphlet: {pages} pages read in memory, {len(judges)} justice court judges' names and courts kept")
        return kept
    except Exception as e:                                   # noqa: BLE001
        try:
            kept = json.load(open(path, encoding="utf-8"))
            say(f"      Voter Information Pamphlet: not refreshed ({type(e).__name__}); using the names and courts kept earlier")
            return kept
        except (OSError, ValueError):
            say(f"      Voter Information Pamphlet: not read ({type(e).__name__}); the justice court names are not checked against it")
            return None


def local_rows(folder, gpath, justice_read, cmap, general_url, signed, amended, say):
    """The local level, as far as the statewide list goes: the justice courts' retention questions (level court), the
    places they name, and the gaps and notes saying what is not loaded. Returns the rows and the report's lines."""
    os.makedirs(folder, exist_ok=True)
    out = {"races": {}, "cands": [], "places": [], "src": [], "gaps": [], "notes": [], "report": [], "checks": []}
    try:                                                     # a layout that does not read stops the load (fail); a server that does not answer does not
        places, place_rows_n, ppath = read_places(folder, cmap, say)
    except Exception as e:                                   # noqa: BLE001  the Census file did not answer and none is kept
        places, place_rows_n, ppath = {}, 0, None
        out["checks"].append(f"the Census Bureau's place list could not be had ({type(e).__name__}); city and town courts are left out")

    # the group read a second time, and its answer lines counted
    second, answers = justice_section(gpath)
    same = second == list(justice_read)
    if not same:
        out["checks"].append(f"the Justice Courts group does not read the same way twice ({len(justice_read)} questions one way, "
                             f"{len(second)} the other); none is loaded")
    elif answers != len(justice_read):
        out["checks"].append(f"the Justice Courts group has {len(justice_read)} questions and {answers} Yes/No answer lines")

    used_places, ids, unread, loose, plural_off, blanked = {}, set(), 0, 0, 0, 0
    judges = defaultdict(list)                               # (family name, first given name) -> its contests' parts
    for k, (read_name, read_office) in enumerate(justice_read if same else [], start=1):
        caps = caps_name(read_name)
        got = justice_office(read_office, cmap, places)
        if not caps or not got or not got["parts"]:
            unread += 1
            continue
        name = ordinary(caps)
        given, family = name_parts(caps)
        plural = got["courts"] > 1
        plural_off += 1 if plural != got["plural_read"] else 0
        loose += got["loose"]
        court = f"{got['label']} Justice Court{'s' if plural else ''}"
        office = f"Judge of the {court} (retention election)"
        cids = sorted({c for kind, p in got["parts"] for c in ([p] if kind == "C" else p["cids"])})
        names = [cmap[p][1] if kind == "C" else p["name"] for kind, p in got["parts"]]
        keys = [p[2:] if kind == "C" else p["code"] for kind, p in got["parts"]]
        for kind, p in got["parts"]:
            if kind == "M":
                used_places[p["code"]] = p
        only = got["parts"][0] if len(got["parts"]) == 1 else None
        jid = None if not only else only[1] if only[0] == "C" else f"{STATE}-M-{only[1]['code']}"
        if all(kind == "C" for kind, _p in got["parts"]):
            who = JUSTICE_COUNTY.format(where=and_words(names))
        else:
            who = JUSTICE_PLACED
        rid = f"2026-{STATE}-JCRET-{'-'.join(keys)}-{family_key(caps)}"
        if rid in ids:
            rid += re.sub(r"[^A-Z]", "", "".join(w[:1] for w in given).upper())
        if rid in ids or not re.fullmatch(rf"2026-{STATE}-JCRET-[0-9-]+-[A-Z]+", rid):
            fail(f"justice court question {k} of the certification does not give a race id of its own")
        if contact_like(office, True) or contact_like(and_words(names), True):
            unread, blanked = unread + 1, blanked + 1
            continue
        ids.add(rid)
        judges[(bare(family), bare(given[0]) if given else "")].append((name, got["parts"]))
        out["races"][rid] = dict(race_id=rid, state=STATE, level="court", office_kind=JUSTICE_KIND, office=office,
                                 jurisdiction=and_words(names), jurisdiction_id=jid, county_ids=json.dumps(cids), district=None,
                                 seat=None, special=0, partisan=0, holder_id=None, holder_name=None, holder_party=None,
                                 election_date=GENERAL, note=own_words(f"{RETENTION} {who}", "a justice court contest"))
        out["cands"].append((rid, "general", GENERAL, name, "Nonpartisan office", "N", 1, 1, 0, None, None, None, None, SRC["general"],
                             "Standing for retention as the sitting judge. " + CAPS))
    n = len(out["races"])
    if not same:
        unread = max(len(justice_read), len(second), answers)
    missed = unread + (max(0, answers - len(justice_read)) if same else 0)

    # the control: the pamphlet's typed names and the courts it lists for each judge
    pam = pamphlet_judges(folder, say) if n else None
    in_pam, same_courts, pam_unread, not_there, differ = 0, 0, 0, [], []
    if pam:
        typed = []
        for j in pam["judges"]:
            typed.append((name_parts(j["name"]), served_list(j["courts"], cmap, places)))
        for (_fam, _first), rows_ in sorted(judges.items()):
            shown_name = rows_[0][0]
            mine = name_parts(shown_name)
            hits = [t for t in typed if bare(t[0][1]) == bare(mine[1]) and fits(mine, t[0])]
            if len(hits) != 1:
                not_there.append(shown_name)
                continue
            in_pam += 1
            ours = {(kind, p if kind == "C" else p["code"]) for _nm, parts in rows_ for kind, p in parts}
            theirs = hits[0][1]
            if theirs is None:
                pam_unread += 1
            elif {(kind, p if kind == "C" else p["code"]) for kind, p in theirs} == ours:
                same_courts += 1
            else:
                differ.append(shown_name)
        extra = len(typed) - in_pam
        if not_there:
            out["checks"].append("justice court judges on the certification with no page of their own in the Voter Information Pamphlet "
                                 f"(nothing is changed): {'; '.join(not_there)}")
        if differ:
            out["checks"].append("the Voter Information Pamphlet lists other courts than the certification for (the certification is "
                                 f"followed): {'; '.join(differ)}")
        if extra:
            out["checks"].append(f"{extra} justice court judge page(s) in the Voter Information Pamphlet match no question on the certification")

    # places, sources, gaps and notes
    for code, p in sorted(used_places.items()):
        out["places"].append(("mcd", f"{STATE}-M-{code}", p["name"], json.dumps(p["cids"]), SRC["places"]))
    if ppath:
        out["src"].append((SRC["places"], STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Utah (st49_ut_place2020.txt)",
                           PLACE_URL, "2020", mdate(ppath), sha_of(ppath), place_rows_n,
                           own_words("City and town names, codes and the counties each lies in, read for the cities and towns the justice "
                                     f"courts' retention questions name ({len(used_places)} of them). The file is about places only: no "
                                     "people and no contact columns.", "the place list's source note")))
    if pam:
        out["src"].append((SRC["pamphlet"], STATE, "official voter pamphlet", AGENCY,
                           "2026 Utah Voter Information Pamphlet: the pages on justice court judges standing for retention",
                           pam["url"], "", pam["fetched"], pam["sha256"], len(pam["judges"]),
                           own_words("A control only; nothing is taken from it. Read in memory and not kept: from each justice court judge's "
                                     f"page ({len(pam['judges'])} of them), only the line with the judge's name and the line of courts served. "
                                     f"{in_pam} of the certification's {len(judges)} judges have a page there; the courts listed are "
                                     f"the same for {same_courts} and differ for {len(differ)}"
                                     + (f", with {pam_unread} not read" if pam_unread else "") + ". The pamphlet's profiles and evaluations, "
                                     "and every other page, are never read or stored.", "the pamphlet's source note")))
    for geoid, (_name, full) in sorted(cmap.items()):
        out["gaps"].append((STATE, "county", geoid, full, GAP_WHAT, own_words(GAP_REASON.format(county=full), "a county gap"), CLERKS_URL))
    out["gaps"].append((STATE, "state", STATE, NAME, "special district board races", own_words(DISTRICT_GAP, "the special district gap"),
                        LAW["districts"]))
    if missed:
        out["gaps"].append((STATE, "state", STATE, NAME, "justice court retention questions",
                            own_words(UNREAD_GAP.format(n=missed), "the unread questions gap"), general_url))
    reached = sorted({c for r in out["races"].values() for c in json.loads(r["county_ids"])})
    out["notes"].append((STATE, "local_calendar", own_words(CALENDAR, "the calendar note"), own_words(CALENDAR_SOURCE, "the calendar note's source"),
                         LAW["general"]))
    coverage = ("Loaded for Utah's local level so far: the justice court judges' retention questions on the Lieutenant Governor's "
                f"{'amended ' if amended else ''}General Election Certification ({n} of them, for county and city courts alike), filed "
                f"with the other judges and tied to the counties where those courts sit ({len(reached)} of the 29). " if n else
                "No local contest is loaded for Utah yet. ")
    coverage += ("Not loaded yet: county offices and local school board contests, which each county clerk certifies and posts for the "
                 "county alone, and special district boards. Ballot questions are not loaded: the proposed constitutional amendments "
                 "and local propositions.")
    out["notes"].append((STATE, "local_coverage", own_words(coverage, "the coverage note"),
                         own_words(f"{AGENCY}: 2026 General Election Certification" + (f", signed {signed}" if signed else ""),
                                   "the coverage note's source"), general_url))

    kinds = Counter("county" if all(k == "C" for k, _p in parts) else "city" if all(k == "M" for k, _p in parts) else "both"
                    for rows_ in judges.values() for _nm, parts in rows_)
    out.update(n=n, loose=loose, answers=answers)
    out["report"].append(
        f"    Utah (county and local): {n} justice court retention questions loaded under level court ({kinds['county']} for a county's "
        f"court, {kinds['city']} for city or town courts, {kinds['both']} naming both), {len(judges)} judges, {len(used_places)} cities and "
        f"towns named, {len(reached)} of 29 counties reached; read twice ({len(second)} and {len(justice_read)} questions, {answers} answer "
        f"lines); {loose} place or county name(s) read with one letter misread; "
        + (f"Voter Information Pamphlet: {in_pam} of {len(judges)} judges found, same courts for {same_courts}" if pam
           else "Voter Information Pamphlet not read") + f"; {len(out['gaps'])} gaps recorded (29 counties: {GAP_WHAT})")
    if plural_off:
        out["checks"].append(f"{plural_off} justice court question(s) read 'Court' where several courts are named, or 'Courts' for one")
    if blanked:
        out["checks"].append(f"{blanked} justice court question(s) left out: a name or court that looked like contact details")
    if missed:
        out["checks"].append(f"{missed} justice court question(s) not loaded; a gap says so")
    return out


# ---------------------------------------------------------------- the load

def load(db_path, say=print, cache=CACHE, refresh=False):
    net.patient_lookups()
    folder = cache
    os.makedirs(folder, exist_ok=True)
    found = fed.links(folder, say)
    gpath = os.path.join(folder, "ut_" + found["general"].rsplit("/", 1)[-1].lower())
    wpath = os.path.join(folder, "ut_" + found["write_in"].rsplit("/", 1)[-1].lower())
    cpath = os.path.join(folder, "ut_2026_primary_state_canvass.pdf")
    net.download(found["general"], gpath, max_age_days=2, tries=3, say=say)
    net.download(found["write_in"], wpath, max_age_days=2, tries=3, say=say)
    net.download(found["canvass"], cpath, max_age_days=30, tries=3, say=say)
    for p in (gpath, wpath, cpath):
        if open(p, "rb").read(4) != b"%PDF":
            fail(f"{os.path.basename(p)} is not a PDF")
    kept = state_filings(folder, say, refresh=refresh)
    filed, judicial_filed, updated = kept["rows"], kept["judicial"], kept["updated"]
    odd = sorted({r["status"] for r in filed if r["status"] not in KNOWN_STATUS and not GONE.search(r["status"])})
    if odd:
        fail(f"a status on the filings page that is not read ({odd})")
    cmap = counties()
    seats, as_of = roster()
    checks = []

    roster_case = {}
    for h in seats.values():
        for form in (h["name"], f"{h['first']} {h['last']}"):
            roster_case[form.upper()] = h["name"]

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps.strip())
        return roster_case.get(caps) or ordinary(caps)

    def code_of(party):
        return "O" if party == "Independent American" else party_code(party)   # a party of its own, not an independent

    # ---- the November list
    races_read, retention_read, amendments, signed, amended = general_list(gpath, cmap)
    by_race = defaultdict(list)
    for r in filed:
        by_race[(r["body"], r["district"])].append(r)
    races, cand, loose_counties, fuzzy, race_body = {}, [], [], [], {}
    general_by_race = defaultdict(list)
    for (body, d), r in races_read.items():
        spec = BODIES[body]
        rid = race_id(body, d)
        race_body[rid] = body
        pool = [x for x in by_race.get((body, d), []) if x["status"] == "Election Candidate"]
        if not pool and r["rows"]:
            fail(f"{spec['place']} {d} is on the certification but has no election candidate on the filings page")
        used = set()
        for order, (read, party_read) in enumerate(r["rows"], start=1):
            party = party_of(party_read)
            if not party:
                fail(f"a party on the certification that is not read, under {spec['place']} {d}")
            same = [i for i, x in enumerate(pool) if x["party"] == party and i not in used]
            exact = [i for i in same if fed.letters(pool[i]["name"]) == fed.letters(read)]
            if len(exact) == 1:
                pick = exact[0]
            elif len(same) == 1 and ratio(pool[same[0]]["name"], read) >= 0.6:
                pick = same[0]
                fuzzy.append(f"{spec['place']} {d} ({party})")
            elif len(same) > 1:
                best = sorted(same, key=lambda i: -ratio(pool[i]["name"], read))
                if ratio(pool[best[0]]["name"], read) >= 0.8 and ratio(pool[best[1]]["name"], read) < 0.6:
                    pick = best[0]
                    fuzzy.append(f"{spec['place']} {d} ({party})")
                else:
                    fail(f"the certification's {party} name under {spec['place']} {d} fits more than one filing")
            else:
                fail(f"the certification's {party} candidate under {spec['place']} {d} is not an election candidate of that "
                     "party on the filings page")
            used.add(pick)
            name = shown(pool[pick]["name"])
            general_by_race[rid].append((name, party, order, pool[pick]["name"]))
        left = [x["name"] for i, x in enumerate(pool) if i not in used]
        if left:
            checks.append(f"{spec['place']} {d}: on the filings page as election candidates but not on the certification: "
                          + "; ".join(left))
        flags = {f for x in by_race.get((body, d), []) for f in x["flags"]}
        multi_flag = "Multi-County" in flags
        if not r["counties"]:
            checks.append(f"{spec['place']} {d}: no county read from the certification's heading")
        elif multi_flag != (len(r["counties"]) > 1):
            checks.append(f"{spec['place']} {d}: the heading names {len(r['counties'])} counties; the filings page "
                          f"{'says' if multi_flag else 'does not say'} Multi-County")
        if r["loose"]:
            loose_counties.append(f"{spec['place']} {d}")
        two_year = any(re.fullmatch(r"\d-Year Term", f) for f in flags)
        if body == "SBOE" and two_year != bool(r["special"]):
            checks.append(f"{spec['place']} {d}: the filings page and the certification disagree on a shortened term")
        holder = seats.get((spec["roster"], str(d))) if spec["roster"] else None
        note = []
        if r["special"]:
            note.append("The certification says the member elected here serves a two-year term, the rest of an unexpired term.")
        if body == "SBOE":
            note.append("The roster this archive reads does not carry the State Board of Education, so today's member is not shown.")
        races[rid] = dict(race_id=rid, state=STATE, level=spec["level"], office_kind=spec["kind"], office=spec["office"],
                          jurisdiction=f"{spec['place']} {d}", jurisdiction_id=FIPS,
                          county_ids=json.dumps(r["counties"]) if r["counties"] else None, district=str(d), seat=None,
                          special=r["special"], partisan=1, holder_id=holder["id"] if holder else None,
                          holder_name=holder["name"] if holder else None, holder_party=holder["party"] if holder else None,
                          election_date=GENERAL, note=" ".join(note) or None)

    # the chambers: every House seat, and the Senate and State Board seats the filings page and the certification agree on
    for body, spec in BODIES.items():
        on_list = {d for (b, d) in races_read if b == body}
        on_filings = {r["district"] for r in filed if r["body"] == body}
        if on_list - on_filings or on_filings - on_list:
            checks.append(f"{spec['place']}s: certification {sorted(on_list)}, filings page {sorted(on_filings)}")
        if body == "HOUSE" and on_list != set(range(1, 76)):
            checks.append(f"House districts missing from the certification: {sorted(set(range(1, 76)) - on_list)}")
        empty = sorted(d for (b, d), r in races_read.items() if b == body and not r["rows"])
        if empty:
            checks.append(f"{spec['place']}s with no candidate on the certification: {empty}")

    # sitting members, one fit only
    for rid, rows in general_by_race.items():
        race = races[rid]
        ids = {}
        if race["holder_id"]:
            h = seats[(BODIES[race_body[rid]]["roster"], race["district"])]
            hits = [n for n, _p, _o, _t in rows if fits_holder(n, h)]
            if len(hits) == 1:
                ids[hits[0]] = h["id"]
            elif len(hits) > 1:
                checks.append(f"{race['jurisdiction']}: {len(hits)} candidates fit the sitting member's name; none marked")
        for name, party, order, _typed in rows:
            cand.append((rid, "general", GENERAL, name, party, code_of(party), order, 1 if name in ids else 0, 0, None, None,
                         None, ids.get(name), SRC["general"], CAPS))

    # ---- declared write-ins
    write_ins, wsigned = write_in_list(wpath)
    declared = [r for r in filed if r["status"] == "Write-In"]
    for (body, d), read in write_ins:
        rid = race_id(body, d)
        if rid not in races:
            fail(f"a write-in candidate for {BODIES[body]['place']} {d}, a race not on the certification")
        hits = [r for r in declared if r["body"] == body and r["district"] == d
                and (fed.letters(r["name"]) == fed.letters(read) or ratio(r["name"], read) >= 0.85)]
        if len(hits) != 1:
            fail(f"a write-in name under {BODIES[body]['place']} {d} matches {len(hits)} Write-In rows on the filings page")
        cand.append((rid, "general", GENERAL, shown(hits[0]["name"]), None, party_code("write-in"), None, 0, 1, None, None,
                     None, None, SRC["write_in"], f"{WRITE_IN} {CAPS}"))
    if len(declared) != len(write_ins):
        checks.append(f"the filings page lists {len(declared)} state write-in(s); the Write-In Certification lists {len(write_ins)}")

    # ---- retention elections of the state courts
    typed_q = []
    for j in judicial_filed:
        m = RETAIN.match(re.sub(r"\s+", " ", j["question"]).strip())
        if not m:
            fail("a question in the filings page's State Judicial table that is not read")
        kind, d = court_of(m.group(2))
        if not kind or kind == "justice_court_retention":
            fail(f"a court in the filings page's State Judicial table that is not read ({m.group(2)!r})")
        typed_q.append({"name": m.group(1), "office": m.group(2), "kind": kind, "district": d, "status": j["status"]})
    if any(q["status"] != "Election Candidate" for q in typed_q):
        checks.append("a judge in the filings page's State Judicial table has a status other than Election Candidate")
    justice, used_q, ret_ids = 0, set(), set()
    for group, gd, read_name, read_office, cids in retention_read:
        if group == "justice":
            justice += 1
            continue
        kind, d = court_of(read_office)
        want_kind = {"appellate": ("supreme_court_retention", "court_of_appeals_retention"),
                     "district": ("district_court_retention", "juvenile_court_retention")}[group]
        pool = [i for i, q in enumerate(typed_q) if i not in used_q and q["kind"] in want_kind
                and (group == "appellate" or q["district"] == gd)]
        exact = [i for i in pool if fed.letters(typed_q[i]["name"]) == fed.letters(read_name)]
        best = exact or sorted([i for i in pool if ratio(typed_q[i]["name"], read_name) >= 0.8],
                               key=lambda i: -ratio(typed_q[i]["name"], read_name))[:1]
        if len(best) != 1:
            fail(f"a retention question on the certification ({group} court{f', district {gd}' if gd else ''}) matches "
                 f"{len(best)} rows of the filings page's State Judicial table")
        q = typed_q[best[0]]
        used_q.add(best[0])
        # the court: the signed certification's words where they can be read (it is what the ballot prints), else the typed page's
        court, dist = (kind, gd if group == "district" else None) if kind in want_kind else (q["kind"], q["district"])
        if group == "district" and d is not None and d != gd:
            fail(f"a retention question under the {ORDINALS[gd - 1]} Judicial District names another district")
        note = RETENTION
        if court != q["kind"]:
            words_ = {"district_court_retention": "the District Court", "juvenile_court_retention": "the Juvenile Court",
                      "supreme_court_retention": "the Supreme Court", "court_of_appeals_retention": "the Court of Appeals"}
            note += (f" The Candidate Filings page lists this judge under {words_[q['kind']]}; the signed certification, followed "
                     f"here, under {words_[court]}.")
            checks.append(f"the certification puts {q['name']} in {words_[court]}, the filings page in {words_[q['kind']]} "
                          "(the certification is followed)")
        name = ordinary(q["name"])
        family = re.sub(r"[^A-Z]", "", name_parts(q["name"])[1].upper())
        tag = {"supreme_court_retention": "SCRET", "court_of_appeals_retention": "COARET",
               "district_court_retention": f"DCRET{dist}", "juvenile_court_retention": f"JVRET{dist}"}[court]
        rid = f"2026-{STATE}-{tag}-{family}"
        if rid in ret_ids:
            rid += re.sub(r"[^A-Z]", "", "".join(w[:1] for w in name_parts(q["name"])[0]).upper())
        ret_ids.add(rid)
        dname = f"{ORDINALS[dist - 1]} Judicial District" if dist else None
        office = {"supreme_court_retention": "Justice of the Supreme Court (retention election)",
                  "court_of_appeals_retention": "Judge of the Court of Appeals (retention election)",
                  "district_court_retention": f"Judge of the District Court, {dname} (retention election)",
                  "juvenile_court_retention": f"Judge of the Juvenile Court, {ORDINALS[(dist or 1) - 1]} Juvenile Court "
                                              "District (retention election)"}[court]
        races[rid] = dict(race_id=rid, state=STATE, level="court", office_kind=court, office=office,
                          jurisdiction=dname or NAME, jurisdiction_id=f"{STATE}-JD{dist}" if dist else FIPS,      # sl_places is shared: a district id carries its state (Minnesota's are JD1 to JD10)
                          county_ids=json.dumps(cids) if cids else None, district=str(dist) if dist else None,
                          seat=None, special=0, partisan=0, holder_id=None, holder_name=name, holder_party=None,
                          election_date=GENERAL, note=note)
        cand.append((rid, "general", GENERAL, name, "Nonpartisan office", "N", 1, 1, 0, None, None, None, None, SRC["general"],
                     "Standing for retention as the sitting judge. " + CAPS))
    unread = [q["name"] for i, q in enumerate(typed_q) if i not in used_q]
    if unread:
        checks.append(f"judges in the filings page's State Judicial table not found on the certification: {'; '.join(unread)}")
    n_retention = len(used_q)

    # ---- the local level: the justice courts' retention questions, the places they name, the gaps and the notes
    local = local_rows(os.path.join(folder, LOCAL_DIR), gpath, [(n, o) for g, _d, n, o, _c in retention_read if g == "justice"],
                       cmap, found["general"], signed, amended, say)
    for rid, r in local["races"].items():
        if rid in races:
            fail(f"a justice court contest's race id is already a state race's ({rid})")
        races[rid] = r
    cand.extend(local["cands"])

    nominee = {}
    for rid, rows in general_by_race.items():
        for name, party, _o, typed in rows:
            nominee[(rid, party)] = typed

    # ---- the June 23 primary
    rl = fed.results_links(folder, say)
    bpath = os.path.join(folder, "ut_2026_primary_all_results.xlsx")
    net.download(rl["all_results"], bpath, max_age_days=30, tries=3, say=say)
    book = primary_book(bpath)
    multi, single = canvass(cpath, {(b, d, CODES.get(c)): len(f["names"]) for (b, d, c), f in book.items()})
    problems, checked, county_files, fields = [], [], {}, Counter()

    def primary_set(body, d, party):
        return {x["name"] for x in by_race.get((body, d), []) if x["party"] == party and x["status"] == "Out in Primary"}

    def typed_of(body, d, read, party):
        """The filings page's spelling of a name printed in the results (same race and party; same letters)."""
        pool = [x["name"] for x in by_race.get((body, d), []) if x["party"] == party]
        hits = sorted({n for n in pool if fed.letters(n) == fed.letters(read)})
        return hits[0] if len(hits) == 1 else read

    def add_field(body, d, code, names, counted, src, note, extra=None):
        rid, party = race_id(body, d), CODES.get(code)
        want = primary_set(body, d, party) | ({nominee[(rid, party)]} if (rid, party) in nominee else set())
        got = {typed_of(body, d, n, party) for n in names}
        if {fed.letters(n) for n in got} != {fed.letters(n) for n in want}:
            problems.append(f"{BODIES[body]['place']} {d} {code}: the primary's candidates are not the filings page's nominee "
                            "and those out in the primary")
        if len(names) < 2:
            return
        fields[BODIES[body]["kind"]] += 1
        top = max(names, key=names.get)
        winner = nominee.get((rid, party))
        if winner is None:
            problems.append(f"{BODIES[body]['place']} {d} {code}: no {party} candidate on the November certification")
        elif fed.letters(winner) != fed.letters(top):
            problems.append(f"{BODIES[body]['place']} {d} {code}: the November nominee is not the primary's leader")
        h = seats.get((BODIES[body]["roster"], str(d))) if BODIES[body]["roster"] else None
        hits = [n for n in names if h and fits_holder(typed_of(body, d, n, party), h)]
        for n, votes in sorted(names.items(), key=lambda kv: (-kv[1], kv[0])):
            typed = typed_of(body, d, n, party)
            won = winner is not None and fed.letters(winner) == fed.letters(typed)
            sitting = len(hits) == 1 and hits[0] == n
            cand.append((rid, f"primary-{code}", PRIMARY, shown(typed), party, code_of(party), None, 1 if sitting else 0, 0,
                         votes, round(100 * votes / counted, 1) if counted else None, "advanced" if won else "lost",
                         h["id"] if sitting else None, src, note + ((extra or {}).get(n) or "")))

    for (body, d, code), f in sorted(book.items()):
        place = f"{BODIES[body]['place']} {d} {code}"
        if code not in CODES:
            fail(f"a party code in the primary results that is not read ({code})")
        rid = race_id(body, d)
        if rid not in races:
            problems.append(f"{place}: a primary for a race not on the November certification")
            continue
        counted = sum(f["names"].values()) + f["write_ins"]
        if f["cast"] is not None and counted + f["over"] + f["under"] != f["cast"]:
            problems.append(f"{place}: candidates, over- and undervotes {counted + f['over'] + f['under']:,} against {f['cast']:,} ballots cast")
        for n, votes in f["names"].items():
            summed = sum(c.get(n, 0) for c in f["counties"].values())
            if summed != votes:
                problems.append(f"{place}: a candidate's county rows sum to {summed:,}, the total is {votes:,}")
        race_counties = {cmap[g][1] for g in json.loads(races[rid]["county_ids"] or "[]")}
        if set(f["counties"]) != race_counties:
            problems.append(f"{place}: the results report counties {sorted(f['counties'])}; the certification's heading names "
                            f"{sorted(race_counties)}")
        c = multi.get((body, d, CODES[code]))
        if not c:
            problems.append(f"{place}: the statewide canvass does not list this multi-county primary")
        else:
            theirs = {fold(n): (v, cs) for n, v, cs in zip(c["names"], c["votes"], c["county_sums"])}
            ours = {fold(n): v for n, v in f["names"].items()}
            if set(theirs) != set(ours) or any(theirs[n][0] != v or theirs[n][1] != v for n, v in ours.items()) \
                    or c["total"] != sum(f["names"].values()):
                problems.append(f"{place}: the statewide canvass does not agree with the workbook")
            else:
                checked.append(place)
        blank = {n: " The results print no party beside this name on the party's ballot; the filings page lists the candidate "
                    "under the party." for n in f["blank_party"]}
        add_field(body, d, code, f["names"], counted, SRC["results"], CAPS_RESULTS, blank)

    # the single-county primaries, from each county's final official summary
    summaries = {}
    for (body, d), (cparty, cname) in sorted(single.items()):
        place = f"{BODIES[body]['place']} {d}"
        rid = race_id(body, d)
        if rid not in races:
            problems.append(f"{place}: a single-county primary for a race not on the November certification")
            continue
        code = next((k for k, v in CODES.items() if v == cparty), None)
        if not code:
            fail(f"a party on the canvass's single-county page that is not read ({cparty})")
        cids = json.loads(races[rid]["county_ids"] or "[]")
        if len(cids) != 1:
            problems.append(f"{place}: the canvass lists it as single-county; the certification's heading names {len(cids)} counties")
            continue
        county = cmap[cids[0]][1]
        url = rl["counties"].get(county)
        if not url:
            problems.append(f"{place} {code}: no final official summary from {county} on the results system")
            continue
        if county not in summaries:
            spath = os.path.join(folder, f"ut_2026_primary_{fold(county).replace(' ', '_')}_summary.pdf")
            net.download(url, spath, max_age_days=30, tries=3, say=say)
            if open(spath, "rb").read(4) != b"%PDF":
                fail(f"{os.path.basename(spath)} is not a PDF")
            summaries[county] = (spath, url, county_summary(spath))
        spath, url, got = summaries[county]
        s = got.get((body, d, code))
        if not s or not s["names"]:
            problems.append(f"{place} {code}: not found in {county}'s final official summary")
            continue
        total = sum(s["names"].values())
        if s["total"] is not None and s["total"] != total:
            problems.append(f"{place} {code}: {county}'s summary prints Total Votes {s['total']:,}; its candidates add up to {total:,}")
        if s["contest"] is not None and s["contest"] != total + (s["over"] or 0) + (s["under"] or 0):
            problems.append(f"{place} {code}: {county}'s summary prints a contest total that its figures do not add up to")
        top = max(s["names"], key=s["names"].get)
        if fed.letters(top) != fed.letters(cname):
            problems.append(f"{place} {code}: the canvass names {cname} as the nominee; {county}'s summary's leader is {top}")
        county_files.setdefault(county, (spath, url, []))[2].append(f"{place} {code}")
        checked.append(f"{place} {code} ({county})")
        add_field(body, d, code, s["names"], total, f"ut-{fold(county).replace(' ', '-')}-2026-state-primary-summary", CAPS_RESULTS)

    fields_by_race = {(c[0], c[1]) for c in cand if c[1].startswith("primary")}
    out_in_primary = {BODIES[b]["kind"]: sum(1 for r in filed if r["body"] == b and r["status"] == "Out in Primary") for b in BODIES}
    lost = Counter(races[c[0]]["office_kind"] for c in cand if c[1].startswith("primary") and c[11] == "lost")
    for kind, n in out_in_primary.items():
        if lost[kind] != n:
            problems.append(f"{kind}: the filings page marks {n} Out in Primary; the results give {lost[kind]} who lost")

    # ---- the rows
    gone = [f"{r['name']} ({BODIES[r['body']]['place']} {r['district']}, {r['status'].lower()})" for r in filed if GONE.search(r["status"])]
    convention = sum(1 for r in filed if r["status"] == "Out in Convention")
    race_rows = [tuple(r[k] for k in ("race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id",
                                      "county_ids", "district", "seat", "special", "partisan", "holder_id", "holder_name",
                                      "holder_party", "election_date", "note")) for r in races.values()]
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dupes = [k for k, v in keys.items() if v > 1]
    if dupes:
        fail(f"two rows for one candidate in one election: {dupes[:3]}")
    place_rows = [("county", g, full, json.dumps([g]), SRC["counties"]) for g, (_n, full) in sorted(cmap.items())] + local["places"]
    judicial = {r["jurisdiction_id"]: (r["jurisdiction"], r["county_ids"]) for r in races.values()
                if str(r["jurisdiction_id"] or "").startswith(f"{STATE}-JD")}      # each judicial district's own place row
    place_rows += [("judicial", jid, nm, cids, SRC["general"]) for jid, (nm, cids) in sorted(judicial.items())]
    general = [c for c in cand if c[1] == "general"]
    per_kind = Counter(races[c[0]]["office_kind"] for c in general)
    listed = {b: sum(len(r["rows"]) for (bb, _d), r in races_read.items() if bb == b) for b in BODIES}
    filed_ec = {b: sum(1 for r in filed if r["body"] == b and r["status"] == "Election Candidate") for b in BODIES}
    for b in BODIES:
        if listed[b] != filed_ec[b]:
            checks.append(f"{BODIES[b]['place']}s: {listed[b]} names on the certification, {filed_ec[b]} election candidates on the filings page")

    src = [
        (SRC["general"], STATE, "official candidate list", AGENCY,
         ("***AMENDED*** " if amended else "") + "2026 General Election Certification" + (f" (signed {signed})" if signed else "")
         + ": Utah Senate, Utah House of Representatives, State Board of Education, judicial retention",
         found["general"], signed, mdate(gpath), sha_of(gpath), sum(listed.values()) + len(retention_read),
         "A signed scan read through its machine-read text layer. It prints candidate and party only, and says its order is the "
         "ballot order. Every name matched to the office's typed Candidate Filings page in the same race and party, whose spelling "
         f"is kept ({len(fuzzy)} names matched by race and party where machine reading had misread a letter). A race's county_ids "
         f"are the counties its heading sentence names ({len(loose_counties)} heading(s) with a county name misread by one letter). "
         f"Retention: {n_retention} state-court judges loaded, and {local['n']} of the {justice} justice-court questions (county and "
         "city courts): for those, only the judge's name and the court are read, the name is the scan's own reading because the "
         "filings page has no table of them, the court is matched to a county or to a city or town on the Census Bureau's place "
         f"list ({local['loose']} name(s) with one letter misread), and the group is read twice and its {local['answers']} answer "
         f"lines counted. The {amendments} proposed constitutional amendments are not loaded. Withdrawn, disqualified or deceased, "
         f"left off: {len(gone)}. Out at a party convention, not on any ballot: {convention}. The certification prints no contact "
         "columns."),
        (SRC["write_in"], STATE, "official candidate list", AGENCY,
         "2026 Write-In Candidate Certification" + (f" (signed {wsigned})" if wsigned else "") + ": state offices",
         found["write_in"], wsigned, mdate(wpath), sha_of(wpath), len(write_ins),
         "Declared write-in candidates for November 3, 2026; their names are not printed on the ballot. Each matched to a Write-In "
         "row of the filings page."),
        (SRC["filings"], STATE, "official candidate list", AGENCY,
         "2026 Candidate Filings: State Senate, State House, State School Board, State Judicial" + (f" (last updated {updated})" if updated else ""),
         fed.FILINGS_URL, updated, mdate(os.path.join(folder, "ut_2026_candidate_filings_state.json")),
         sha_of(os.path.join(folder, "ut_2026_candidate_filings_state.json")), len(filed) + len(judicial_filed),
         "Its columns Candidate, Office, Party and Status (and Judicial Retention, Status) only, checked before any cell was kept; "
         "used for the typed spelling of each certified name, who withdrew, was disqualified or died, and who went out at "
         "convention or in the primary."),
        (SRC["results"], STATE, "official results", f"{AGENCY} (election results system)",
         "2026 Utah Primary Election (June 23, 2026): All Results Excel", fed.RESULTS_PAGE, rl.get("last_updated", ""), mdate(bpath),
         sha_of(bpath), sum(len(f["names"]) for f in book.values()),
         "Summary Results sheet: the multi-county state primaries. Every total equals the sum of the Precinct Results sheet's county "
         "rows, candidates plus over- and undervotes equal ballots cast, and the statewide canvass agrees. No write-in votes are "
         "reported." + (f" Did not reconcile: {'; '.join(problems)}." if problems else "")),
        (SRC["canvass"], STATE, "official results", AGENCY,
         "2026 Primary Election Certification: June 23, 2026 Primary Election Statewide Canvass", found["canvass"], "", mdate(cpath),
         sha_of(cpath), len(multi) + len(single),
         "The signed statewide canvass. Multi-county state races: candidate totals, contest totals and county columns checked "
         "against the workbook. Single-county races are certified by the county and listed by nominee only; each nominee checked "
         "against the county's summary and the November certification."),
        (SRC["roster"], STATE, "roster", "Open States people project (CC0)",
         "Utah legislators serving today, as loaded into state_ut.sqlite", "https://github.com/openstates/people", as_of, as_of,
         "", len(seats), "Today's holder of each legislative seat (ids, names, parties and districts only), and which candidates "
         "are those members. The roster does not carry the State Board of Education."),
        (SRC["counties"], STATE, "official boundaries", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "", mdate(COUNTY_ZIP),
         sha_of(COUNTY_ZIP), len(cmap), "Utah's 29 counties: names and GEOIDs only."),
    ] + local["src"]
    for county, (spath, url, used_for) in sorted(county_files.items()):
        src.append((f"ut-{fold(county).replace(' ', '-')}-2026-state-primary-summary", STATE, "official results",
                    f"{county} Clerk (posted on the Lieutenant Governor's election results system)",
                    f"2026 Primary Election: final official summary results report ({county})", url, "", mdate(spath), sha_of(spath),
                    len(used_for), "The votes of the single-county state primaries the county certified: " + ", ".join(used_for) + "."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:      # Utah's rows only, in one transaction
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ut-%' OR (kind = 'county' AND id GLOB '49[0-9][0-9][0-9]')")
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    # ---- the report: counts only
    by_kind = Counter(r["office_kind"] for r in races.values())
    alone = Counter(races[rid]["office_kind"] for rid, rows in general_by_race.items() if len(rows) == 1)
    inc = Counter(races[c[0]]["office_kind"] for c in general if c[7] and races[c[0]]["level"] != "court")
    writes = sum(1 for c in general if c[8])
    senate = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    say(f"    Utah (state races): {by_kind['state_senate']} Senate seats (districts {', '.join(map(str, senate))}), "
        f"{by_kind['state_house']} House seats, {by_kind['state_board_of_education']} State Board of Education seats, "
        f"{n_retention} state-court retention elections; {len(general) - len(local['cands'])} names on the November ballot (Senate "
        f"{per_kind['state_senate']}, House {per_kind['state_house']}, State Board {per_kind['state_board_of_education']}, "
        f"retention {n_retention}; {writes} declared write-ins; {len(gone)} withdrawn, disqualified or deceased left off); "
        f"unopposed: Senate {alone['state_senate']}, House {alone['state_house']}, State Board {alone['state_board_of_education']}; "
        f"sitting member on the ballot: Senate {inc['state_senate']}, House {inc['state_house']}; primary fields: Senate "
        f"{fields['state_senate']}, House {fields['state_house']}, State Board {fields['state_board_of_education']} "
        f"({len(fields_by_race)} fields, {sum(1 for c in cand if c[1].startswith('primary'))} rows, official votes; "
        f"{len(checked)} checked against the canvass or the county's summary)")
    for p in problems:
        say(f"    CHECK Utah (state races): primary: {p}")
    for c in checks:
        say(f"    CHECK Utah (state races): {c}")
    for line in local["report"]:
        say(line)
    for c in local["checks"]:
        say(f"    CHECK Utah (county and local): {c}")
    return len(general)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_ut.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
