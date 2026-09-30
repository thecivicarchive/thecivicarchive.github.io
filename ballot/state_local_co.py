"""
ballot/state_local_co.py - Colorado's state races on the November 3, 2026 ballot: the Colorado Senate seats up this year,
all 65 House seats, Governor with Lieutenant Governor, Secretary of State, State Treasurer, Attorney General, the State
Board of Education and University of Colorado Regent seats elected by congressional district, and the retention votes
for the Supreme Court and the Court of Appeals, with the June 30 party primaries that chose the nominees. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), Colorado's rows only.

    python ballot/state_local_co.py <database file> [--cache <folder>]

Sources, all the Colorado Secretary of State's own (the lists are the ones the federal loader, ballot/lists/co.py,
reads for Congress; this loader keeps the state rows):
  * the "2026 General Election Official Candidate List" (vote/generalCandidates.html, "official and reflects what was
    certified to the counties on September 4"): the page's table, where a withdrawn candidate is struck through, and its
    "Excel version (XLSX)", which must list the same seats, parties and write-in marks. Five columns exist and five are
    read, by their headings: Candidate name, Office, District, Party, Write in?. Nothing else is printed or kept.
  * the "2026 Official Primary Election Candidate List" (vote/primaryCandidates.html, certified to the counties May 1),
    read the same way.
  * the "2026 General Election Ballot Order for Major & Minor Party Candidates" workbook (lot drawing of July 28,
    2026): one position per party per office. Colorado law (1-5-404, C.R.S.) orders a race in three tiers, major
    parties, then minor parties, then unaffiliated candidates, each tier by lot, except Governor and Lieutenant
    Governor, ordered by the family name of the candidate for Governor (the page's own words); the drawing's numbers
    already carry both rules. A party that drew a position but has no candidate is not printed, so the positions
    stored are places on the printed ballot (gaps closed); a race's one unaffiliated candidate follows the parties.
    Where a name on the list is struck through, whether it is still printed is not in the list, so that race gets no
    positions. Certified write-in candidates (Write in? = Y) are not printed: write_in 1, no position.
  * the "2026 State Primary Election Statewide Abstract of Votes Cast", certified July 24, 2026: a scan with no text
    layer (JBIG2 images). Its Total row for every state primary with a field was read by eye on 2026-09-30 from the
    scan's pages decoded to pictures outside the kit (scan pages 6, 7, 9, 11, 13-19, 26, 29, 31-33, 35-40, 42 and 43)
    and is written below as ABSTRACT, with the scan's SHA-256. The stored votes are the machine-readable figures of the
    Secretary's election night reporting site (results.enr.clarityelections.com/CO, election 126592, reports/
    detailxml.zip, headed "Unofficial Results"); a field's votes are stored only when every candidate's figure equals
    the abstract's and each candidate's county figures add up to the total. Otherwise the field is stored without votes
    and the loader says why.
  * the "2026 State Primary Election Certified Write-In Results" workbook: Colorado counts write-in votes only for
    certified write-in candidates; they count in a field's total and are shown with write_in 1.
  * the 2022 Abstract of Votes Cast, General Election, State Senate page (Results/Abstract/2022/general/
    stateSenate.html): which seventeen Senate seats were elected in 2022 for four years, so are up in 2026 as a matter
    of course. Colorado senators serve four years (the same abstract's "Terms of office" page). A Senate seat on the
    2026 list that is not one of them was last elected in 2024 for a term that runs to January 2029, and the 2026
    election fills the two years left of it (special = 1); the district headings are the only cells read.

Who holds each seat today comes from state_co.sqlite (the Open States roster the state pages use): legislators serving
now, by chamber and district, and the officials table (Governor, Attorney General, Secretary of State). Only ids, names,
parties, districts and start dates are read from it; its contact columns are never selected. A candidate is marked as
the incumbent only when the name fits exactly one sitting member of the same chamber and district, or the holder of the
same statewide office. The roster does not carry the Treasurer, the State Board of Education or the Regents, so those
races show no holder. A judge standing for retention is by definition the sitting judge of that seat, so that one name
is the holder and the incumbent.

Not loaded, and counted in the source note: district, county, juvenile and probate court retention votes (courts of a
judicial district or county) and the Regional Transportation District's board (a regional district). Congress is left
to the federal loader.

A field is a party primary with two or more names printed on that party's ballot for the race; a certified write-in
beside one printed name does not make a field. pct is the share of that party primary's votes, certified write-ins
included. The party's candidate on the November list (the one row of that party, struck through or not) advanced.

The privacy rule: only office, district, name, party, ballot order, status and votes are read from any file. None of
these lists carries an address, telephone number, website or e-mail, and the code would not read one if it did.
"""

import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.error import HTTPError, URLError

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl                                                              # noqa: E402

from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists.co import fetch, links, updated                           # noqa: E402
from ballot.match import fits                                               # noqa: E402
from states import net                                                     # noqa: E402

STATE, NAME, FIPS = "CO", "Colorado", "08"
GENERAL, PRIMARY = "2026-11-03", "2026-06-30"
SOS = "https://www.coloradosos.gov/pubs/elections/"
PAGES = {"general": SOS + "vote/generalCandidates.html", "primary": SOS + "vote/primaryCandidates.html",
         "order": SOS + "vote/generalBallotOrder.html", "archive": SOS + "Results/Archives.html",
         "senate2022": SOS + "Results/Abstract/2022/general/stateSenate.html"}
TITLES = {"general": "2026 General Election Official Candidate List", "primary": "2026 Official Primary Election Candidate List",
          "order": "2026 General Election Ballot Order for Major & Minor Party Candidates"}
ABSTRACT_LABEL = "2026 State Primary Election Statewide Abstract of Votes Cast"
WRITE_IN_LABEL = "2026 State Primary Election Certified Write-In Results"
ENR = "https://results.enr.clarityelections.com/CO/126592/"
ROSTER = os.path.join(HERE, "state_co.sqlite")
DEFAULT_CACHE = os.path.join(CACHE, "co")
HEADS = ("candidate name", "office", "district", "party", "write in?")
CODES = {"Democratic Party": "DEM", "Republican Party": "REP", "Libertarian Party": "LIB", "Unity Party": "UNI",
         "American Constitution Party": "ACN", "Approval Voting Party": "APV", "Forward Party": "FWD", "Center Party": "CCP",
         "Unaffiliated": "UNA"}
WRITEIN_PARTY = {"democrat": "DEM", "democratic": "DEM", "republican": "REP", "libertarian": "LIB", "unity": "UNI",
                 "american": "ACN", "approval": "APV", "forward": "FWD", "center": "CCP", "unaffiliated": "UNA"}
MAJOR = {"Democratic Party", "Republican Party"}
NONPARTISAN = "Nonpartisan office"
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
OFFICIALS = {"governor": "governor", "attorney_general": "attorney general", "secretary_of_state": "secretary of state"}
SRC = {"general": "co-sos-2026-sl-general-list", "primary": "co-sos-2026-sl-primary-list", "order": "co-sos-2026-sl-ballot-order",
       "abstract": "co-sos-2026-sl-primary-abstract", "enr": "co-sos-2026-sl-primary-enr", "writeins": "co-sos-2026-sl-primary-writeins",
       "senate2022": "co-sos-2022-senate-abstract", "roster": "co-openstates-roster-2026"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# The certified abstract (a scan; see above), read by eye on 2026-09-30: the Total row of every state party primary
# with a field, candidate by candidate, certified write-ins included. A control only: the stored votes are the site's.
ABSTRACT_SHA = "807e10067804ca143853d15d13c8a0807dde64aed918a645ffd9428f035ff7aa"
ABSTRACT = {
    ("2026-CO-GOV", "DEM"): {"Phil Weiser": 505459, "Michael Bennet": 383138},
    ("2026-CO-GOV", "REP"): {"Scott Bottoms": 108535, "Victor Marx": 208458, "Barb Kirkmeyer": 205992, 'Kelvin "K-Man" Wimberly': 93},
    ("2026-CO-GOV", "UNI"): {"Paul Noël Fiorino": 126, "Jeff Peckman": 146},
    ("2026-CO-SOS", "DEM"): {"Amanda Gonzalez": 530312, "Jessie Danielson": 293358},
    ("2026-CO-SOS", "LIB"): {"Sean Vadney": 1357, "Alex Astley": 2204},
    ("2026-CO-AG", "DEM"): {"Jena Griswold": 385795, "David Seligman": 172834, "Michael Dougherty": 170271, "Hetal Doshi": 143669},
    ("2026-CO-AG", "REP"): {"Michael J. Allen": 287522, "David Willson": 192533},
    ("2026-CO-REGENT-CD2", "DEM"): {"Kubs Lalchandani": 36439, "Edie Hooton": 50556, "Murray Smith": 38791},
    ("2026-CO-REGENT-CD7", "REP"): {"Joan Poston": 23885, "Paul Mueller": 37258},
    ("2026-CO-SS3", "DEM"): {"Aaron Gutierrez": 12445, "Taylor Voss": 9740},
    ("2026-CO-SS9", "REP"): {"Lynda Zamora Wilson": 9620, "Terri Carver": 18163},
    ("2026-CO-SS21", "DEM"): {"Adrienne Benavidez": 10783, "Alex Ryckman": 6059},
    ("2026-CO-SS27", "REP"): {"Danielle Lammon": 6650, "Darryl Gibbs": 6261},
    ("2026-CO-SS34", "DEM"): {"Chela Garcia Irlando": 22015, "Andrés Carrera": 9754},
    ("2026-CO-SH5", "DEM"): {"Justine Sandoval": 11994, "Sterling Thomas Simms": 3623},
    ("2026-CO-SH6", "DEM"): {"Sean Camacho": 10123, "Iris Halpern": 12420},
    ("2026-CO-SH9", "DEM"): {"Monica VanBuskirk": 9572, "Neal Walia": 6670},
    ("2026-CO-SH13", "DEM"): {"Chris Floyd": 7046, "Consuelo Redhorse": 7217},
    ("2026-CO-SH14", "REP"): {"Ava Flanell": 11007, "Troy Vanderhule": 4001},
    ("2026-CO-SH16", "REP"): {"Jill Haffley": 5126, "Jamie Koch": 2830},
    ("2026-CO-SH17", "DEM"): {"Chauncy Johnson": 2232, "Regina English": 3701},
    ("2026-CO-SH19", "DEM"): {"Anil Pesaramelli": 5413, "Jillaire McMillan": 7714, "Colton Jonjak Plahn": 2665},
    ("2026-CO-SH21", "REP"): {"Brenda Miller": 4107, "Alexander M. Africa": 1420},
    ("2026-CO-SH31", "DEM"): {'Jacqueline "Jacque" Phillips': 4089, "Gabriel Cervantes": 4892},
    ("2026-CO-SH32", "REP"): {"Michelle D. Lee": 2265, "Damon L Scordo": 1186},
    ("2026-CO-SH33", "DEM"): {"Heidi Henkel": 8656, "Kenny Van Nguyen": 10261},
    ("2026-CO-SH41", "DEM"): {"Jamie Jackson": 6549, "Anne Keke": 5479},
    ("2026-CO-SH42", "DEM"): {"Mandy Lindsay": 2422, "Sarah Amelia Woodson": 4825},
    ("2026-CO-SH44", "REP"): {"Anthony Hartsook": 6081, "Bob Davis": 4541},
    ("2026-CO-SH51", "REP"): {"Amy Parks": 7255, "Nancy Rumfelt": 4096},
    ("2026-CO-SH54", "REP"): {"Jason Bias": 8644, "Nina Anderson": 8106},
    ("2026-CO-SH60", "REP"): {"Michelle Gray": 8450, "Matt Alexander": 8700},
}

INLINE = re.compile(r"</?(?:span|b|i|u|em|strong|s|strike|del|font|a|abbr|small)\b[^>]*>", re.I)


def cell(c):
    """A table cell's text: inline tags dropped whole (the primary list writes Esc<span>&#225;</span>rcega), others as spaces."""
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", INLINE.sub("", c or ""))).replace("\xa0", " ")).strip()


def nkey(name):
    """For matching one spelling of a name to another: letters only (the results site writes ''Jacque'' for "Jacque")."""
    return " ".join(fold(name or "").split())


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


# ---------------------------------------------------------------- offices

def office_class(office):
    """'load', 'federal' or 'skip' for an office as the lists print it; anything unknown stops the loader."""
    o = (office or "").strip()
    if o in ("US Senate", "US House of Representatives", "US House"):
        return "federal"
    if o in ("Governor", "Lt. Governor", "Secretary of State", "State Treasurer", "Attorney General", "State Board of Education",
             "University of Colorado Board of Regents", "State Senate", "State House of Representatives",
             "Colorado Supreme Court", "Colorado Court of Appeals"):
        return "load"
    if re.search(r"\bCourt\b", o) or o == "RTD Board of Directors":
        return "skip"
    raise SystemExit(f"Colorado (state races): the list names an office this loader does not know: {o!r}")


def board_district(office, district):
    d = str(district or "").strip()
    if d.isdigit():
        return int(d)
    if re.fullmatch(r"(?i)at[- ]?large", d):
        return "AL"
    raise SystemExit(f"Colorado (state races): {office} is listed with a district that is not read ({d!r})")


def race_for(office, district, name=None):
    """The race a list row belongs to (Lt. Governor rows belong to the Governor's race)."""
    o, d = office.strip(), str(district or "").strip()
    statewide = {"Governor": ("GOV", "governor", "Governor and Lieutenant Governor"), "Lt. Governor": ("GOV", "governor", "Governor and Lieutenant Governor"),
                 "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State"),
                 "State Treasurer": ("TREAS", "state_treasurer", "State Treasurer"), "Attorney General": ("AG", "attorney_general", "Attorney General")}
    base = {"state": STATE, "jurisdiction": NAME, "jurisdiction_id": FIPS, "district": None, "seat": None, "chamber": None, "partisan": 1}
    if o in statewide:
        k, kind, title = statewide[o]
        return dict(base, race_id=f"2026-{STATE}-{k}", level="statewide", office_kind=kind, office=title)
    if o in ("State Board of Education", "University of Colorado Board of Regents"):
        n = board_district(o, d)
        k, kind, title = (("SBE", "state_board_of_education", "Member of the State Board of Education") if o == "State Board of Education"
                          else ("REGENT", "university_board", "Regent of the University of Colorado"))
        if n == "AL":
            return dict(base, race_id=f"2026-{STATE}-{k}-AL", level="statewide", office_kind=kind, office=title, seat="At Large")
        return dict(base, race_id=f"2026-{STATE}-{k}-CD{n}", level="statewide", office_kind=kind, office=title,
                    jurisdiction=f"Congressional District {n}", jurisdiction_id=f"{STATE}-CD{n}", district=f"Congressional District {n}")
    if o in ("State Senate", "State House of Representatives"):
        if not re.fullmatch(r"\d+", d):
            raise SystemExit(f"Colorado (state races): a legislative district written {d!r} is not read")
        d = str(int(d))
        senate = o == "State Senate"
        return dict(base, race_id=f"2026-{STATE}-{'SS' if senate else 'SH'}{d}", level="legislature",
                    office_kind="state_senate" if senate else "state_house", office="State Senator" if senate else "State Representative",
                    jurisdiction=f"{'Senate' if senate else 'House'} District {d}", jurisdiction_id=d, district=d,
                    chamber="Senate" if senate else "House")
    if o in ("Colorado Supreme Court", "Colorado Court of Appeals"):
        fam = re.sub(r"[^A-Z]", "", name_parts(name)[1].upper())
        sc = o == "Colorado Supreme Court"
        return dict(base, race_id=f"2026-{STATE}-{'SCRET' if sc else 'COARET'}-{fam}", level="court",
                    office_kind="supreme_court_retention" if sc else "court_of_appeals_retention",
                    office="Justice of the Supreme Court (retention vote)" if sc else "Judge of the Court of Appeals (retention vote)",
                    partisan=0)
    raise SystemExit(f"Colorado (state races): no race for {o!r}")


def order_race(office, district):
    """The race a ballot order workbook row belongs to, None for Congress."""
    o = (office or "").strip().rstrip("*")
    if o in ("US Senate", "US House of Representatives", "US House"):
        return None
    table = {"Governor/Lt. Governor": "Governor", "Secretary of State": "Secretary of State", "State Treasurer": "State Treasurer",
             "Attorney General": "Attorney General", "State Board of Education": "State Board of Education",
             "CU Regent": "University of Colorado Board of Regents", "State Senate": "State Senate", "State House": "State House of Representatives"}
    if o not in table:
        raise SystemExit(f"Colorado (state races): the ballot order workbook names an office this loader does not know: {o!r}")
    return race_for(table[o], district)["race_id"]


def results_race(title):
    """(race_id, party label) from a results-site contest title; None for Congress; raises for anything else."""
    if title.startswith("United States Senator") or title.startswith("Representative to the 120th United States Congress"):
        return None
    m = re.fullmatch(r"(Governor|Secretary of State|State Treasurer|Attorney General) - (.+)", title)
    if m:
        return race_for(m.group(1), "")["race_id"], m.group(2)
    m = re.fullmatch(r"(State Board of Education Member|Regent of the University of Colorado) - (?:Congressional District (\d+)|(At Large)) - (.+)", title)
    if m:
        office = "State Board of Education" if m.group(1).startswith("State Board") else "University of Colorado Board of Regents"
        return race_for(office, m.group(2) or m.group(3))["race_id"], m.group(4)
    m = re.fullmatch(r"(State Senator|State Representative) - District (\d+) - (.+)", title)
    if m:
        return race_for("State Senate" if m.group(1) == "State Senator" else "State House of Representatives", m.group(2))["race_id"], m.group(3)
    raise SystemExit(f"Colorado (state races): a results contest this loader does not know: {title!r}")


# ---------------------------------------------------------------- the lists

def page_rows(page):
    """The five named cells of every row of a candidate list page, struck through or not, and a count of each office."""
    tables = re.findall(r"<table.*?</table>", page, re.S | re.I)
    if len(tables) != 1:
        raise SystemExit(f"Colorado (state races): the candidate list page has {len(tables)} tables, not one")
    heads = [cell(h).lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", tables[0], re.S | re.I)]
    if not all(h in heads for h in HEADS):
        raise SystemExit(f"Colorado (state races): the candidate list's columns changed ({heads})")
    idx = {h: heads.index(h) for h in HEADS}
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tables[0], re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        if not cells:
            continue
        if len(cells) != len(heads):
            raise SystemExit("Colorado (state races): a row of the candidate list does not line up with its headings")
        rec = {h: cell(cells[i]) for h, i in idx.items()}
        rows.append({"name": rec["candidate name"], "office": rec["office"], "district": rec["district"], "party": rec["party"],
                     "write_in": rec["write in?"].upper() == "Y", "struck": "line-through" in tr.lower()})
    return rows


def book_rows(data):
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    heads = [str(c or "").strip().lower() for c in next(it)]
    if not all(h in heads for h in HEADS):
        raise SystemExit(f"Colorado (state races): the candidate list workbook's columns changed ({heads})")
    idx = {h: heads.index(h) for h in HEADS}
    out = []
    for r in it:
        rec = {h: (str(r[i]).strip() if i < len(r) and r[i] is not None else "") for h, i in idx.items()}
        if not rec["office"]:
            continue
        out.append({"name": rec["candidate name"], "office": rec["office"], "district": rec["district"], "party": rec["party"],
                    "write_in": rec["write in?"].upper() == "Y"})
    wb.close()
    return out


def read_list(kind, folder, say, max_age_days):
    """A candidate list's state rows (page and workbook compared) as JSON in the cache, with counts of the rest."""
    path = os.path.join(folder, f"co_{kind}_list_2026_state.json")
    if fresh(path, max_age_days):
        return path, json.load(open(path, encoding="utf-8"))
    url = PAGES[kind]
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    time.sleep(1.5)
    if TITLES[kind] not in cell(page):
        raise SystemExit(f"Colorado (state races): {url} is no longer the {TITLES[kind]}")
    everything = page_rows(page)
    classes = Counter()
    skipped = Counter()
    rows = []
    for r in everything:
        c = office_class(r["office"])
        classes[c] += 1
        if c == "load":
            rows.append(r)
        elif c == "skip":
            skipped[r["office"]] += 1
    book_url = links(page, url).get("Excel version (XLSX)")
    differ, book_sha = [], ""
    if book_url:
        data = fetch(book_url, b"PK", say)
        book_sha = hashlib.sha256(data).hexdigest()
        book = [b for b in book_rows(data) if office_class(b["office"]) == "load"]
        tup = lambda r: (r["office"], str(r["district"]), r["name"], r["party"], r["write_in"])
        mine, theirs = [tup(r) for r in rows], [tup(b) for b in book]
        differ += [f"page {r[2]!r} ({r[0]} {r[1]}) not in the workbook as written" for r in mine if r not in theirs]
        differ += [f"workbook {r[2]!r} ({r[0]} {r[1]}) not on the page as written" for r in theirs if r not in mine]
        loose = lambda rs: sorted((r[0], r[1], r[3], r[4]) for r in rs)
        if loose(mine) != loose(theirs):
            raise SystemExit(f"Colorado (state races): the {TITLES[kind]} page and its workbook list different candidates: {'; '.join(differ)}")
    else:
        differ.append("the page no longer links its Excel version")
    kept = {"url": url, "workbook": book_url, "page_sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(), "workbook_sha256": book_sha,
            "updated": updated(page), "read": dt.date.today().isoformat(), "differ": differ, "federal_rows": classes["federal"],
            "not_loaded": dict(skipped), "rows": rows}
    os.makedirs(folder, exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {TITLES[kind]}: {len(rows)} state rows ({sum(r['struck'] for r in rows)} struck through)")
    return path, kept


def read_order(folder, say):
    """{race_id: {party: drawn position}} from the ballot order workbook's state rows, as JSON in the cache."""
    path = os.path.join(folder, "co_2026_general_ballot_order_state.json")
    if fresh(path, 30):
        return path, json.load(open(path, encoding="utf-8"))
    url = PAGES["order"]
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    time.sleep(1.5)
    if TITLES["order"] not in cell(page):
        raise SystemExit(f"Colorado (state races): {url} is no longer the {TITLES['order']}")
    book_url = links(page, url).get("Excel version (XLSX)")
    if not book_url:
        raise SystemExit(f"Colorado (state races): {url} no longer links its Excel version")
    data = fetch(book_url, b"PK", say)
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if heads[:2] != ["Office", "District"]:
        raise SystemExit(f"Colorado (state races): the ballot order workbook's columns changed ({heads})")
    parties = [(i, h) for i, h in enumerate(heads) if i >= 2 and h]
    order = {}
    for r in it:
        office = str(r[0] or "").strip()
        if not office or office.lower().startswith("end of worksheet"):
            continue
        rid = order_race(office, r[1])
        if rid:
            order[rid] = {h: int(r[i]) for i, h in parties if i < len(r) and r[i] not in (None, "")}
    wb.close()
    kept = {"url": url, "workbook": book_url, "workbook_sha256": hashlib.sha256(data).hexdigest(), "updated": updated(page),
            "read": dt.date.today().isoformat(), "order": order}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, kept


def read_senate_2022(folder, say):
    """The Senate districts elected in November 2022 (four-year terms), from the 2022 abstract's district headings."""
    path = os.path.join(folder, "co_2022_general_senate_districts.json")
    if os.path.exists(path):
        return path, json.load(open(path, encoding="utf-8"))
    url = PAGES["senate2022"]
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    time.sleep(1.5)
    heads = [cell(h) for h in re.findall(r"<h\d[^>]*>(.*?)</h\d>", page, re.S | re.I)]
    if "State Senator" not in heads or "2022 General Election Results" not in cell(page):
        raise SystemExit(f"Colorado (state races): {url} is no longer the 2022 general election's State Senate results")
    districts = sorted({int(m.group(1)) for h in heads for m in [re.fullmatch(r"District (\d+)", h)] if m})
    if not 15 <= len(districts) <= 20:
        raise SystemExit(f"Colorado (state races): the 2022 State Senate page gives {len(districts)} districts")
    kept = {"url": url, "sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(), "read": dt.date.today().isoformat(), "districts": districts}
    os.makedirs(folder, exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), indent=1)
    return path, kept


def read_enr(folder, say):
    """The state contests of the results site's county detail file, as JSON in the cache; None if it cannot be had."""
    path = os.path.join(folder, "co_2026_primary_enr_state.json")
    if fresh(path, 30):
        return path, json.load(open(path, encoding="utf-8"))
    try:
        ver = net.get(ENR + "current_ver.txt", accept="text/plain").decode("ascii").strip()
        time.sleep(1.5)
        if not ver.isdigit():
            raise SystemExit(f"Colorado (state races): the results site's version is not read ({ver[:40]!r})")
        url = ENR + ver + "/reports/detailxml.zip"
        data = fetch(url, b"PK", say)
    except (HTTPError, URLError, OSError) as e:
        say(f"      the results site could not be read ({e})")
        return (path, json.load(open(path, encoding="utf-8"))) if os.path.exists(path) else (None, None)
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("detail.xml"))
    if root.findtext("ElectionName") != "2026 Primary" or root.findtext("ElectionDate") != "6/30/2026":
        raise SystemExit(f"Colorado (state races): the results site holds {root.findtext('ElectionName')!r} of {root.findtext('ElectionDate')}")
    contests = []
    for c in root.iter("Contest"):
        found = results_race(c.get("text", ""))
        if not found:
            continue
        choices = []
        for ch in c.findall("Choice"):
            vt = ch.findall("VoteType")
            if len(vt) != 1:
                raise SystemExit(f"Colorado (state races): {c.get('text')} splits its votes by type; one Total Votes line is read")
            choices.append({"name": ch.get("text"), "total": int(ch.get("totalVotes")),
                            "counties": {k.get("name"): int(k.get("votes")) for k in vt[0].findall("County")}})
        contests.append({"title": c.get("text"), "race": found[0], "party": found[1], "counties": int(c.get("countiesParticipating")),
                         "reported": int(c.get("countiesReported")), "choices": choices})
    kept = {"url": url, "version": ver, "sha256": hashlib.sha256(data).hexdigest(), "written": root.findtext("Timestamp"),
            "read": dt.date.today().isoformat(), "contests": contests}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      results site, version {ver} ({kept['written']}): {len(contests)} state party primaries")
    return path, kept


def read_writeins(folder, found, say):
    """{"<race>|<code>|<name key>": {...}} for the certified write-in candidates for state offices, as JSON."""
    path = os.path.join(folder, "co_2026_primary_writeins_state.json")
    if fresh(path, 30):
        return path, json.load(open(path, encoding="utf-8"))
    url = found.get(f"{WRITE_IN_LABEL} (XLSX)")
    if not url:
        raise SystemExit(f"Colorado (state races): the results archive no longer links \"{WRITE_IN_LABEL}\"")
    data = fetch(url, b"PK", say)
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    want = ("Office", "Candidate", "Party", "County", "Votes")
    if not all(h in heads for h in want):
        raise SystemExit(f"Colorado (state races): the write-in results workbook's columns changed ({heads})")
    idx = {h: heads.index(h) for h in want}
    out = {}
    for r in it:
        office = str(r[idx["Office"]] or "").strip()
        if not office or office.startswith("US ") or office.lower().startswith("end of"):
            continue
        rid = results_race(office + " - x")[0]
        party = str(r[idx["Party"]] or "").strip()
        code = WRITEIN_PARTY.get(fold(party).split()[0] if fold(party) else "")
        if not code:
            raise SystemExit(f"Colorado (state races): a write-in party that is not read ({party!r})")
        name, county = str(r[idx["Candidate"]]).strip(), str(r[idx["County"]] or "").strip()
        rec = out.setdefault(f"{rid}|{code}|{nkey(name)}", {"race": rid, "code": code, "name": name, "total": None, "counties": {}})
        if county == "Total Votes":
            rec["total"] = int(r[idx["Votes"]])
        elif county != "Votes %":
            rec["counties"][county] = int(r[idx["Votes"]] or 0)
    wb.close()
    for rec in out.values():
        if rec["total"] is None or sum(rec["counties"].values()) != rec["total"]:
            raise SystemExit(f"Colorado (state races): {rec['name']}'s county write-in votes do not add up to the Total Votes line")
    kept = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "read": dt.date.today().isoformat(), "candidates": out}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, kept


# ---------------------------------------------------------------- who holds each seat

def roster(path=ROSTER):
    """Sitting legislators and statewide officials: id, name, party and start date only."""
    if not os.path.exists(path):
        return [], []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "start"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, term_start "
        "FROM legislators WHERE is_current = 1")]
    officials = [dict(zip(("id", "office", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, first_name, last_name, official_full, party_name FROM officials")]
    con.close()
    return members, officials


def one_fit(name, people):
    parts = name_parts(name)
    hits = [p for p in people if fits(parts, (fold(p["first"]).split(), " ".join(fold(p["last"]).split())))
            or fits(parts, name_parts(p["full"]))]
    return hits[0] if len(hits) == 1 else None


def holders(race, members, officials):
    if race["chamber"]:
        return [m for m in members if m["chamber"] == race["chamber"] and str(m["district"]) == race["district"]]
    office = OFFICIALS.get(race["office_kind"])
    return [o for o in officials if office and o["office"] == office]


# ---------------------------------------------------------------- load

def source_row(source_id, kind, agency, title, url, published, fetched, sha256, rows, note):
    return (source_id, STATE, kind, agency, title, url, published or "", fetched or "", sha256 or "", rows, note)


def load(db_path, say=print, cache=DEFAULT_CACHE, roster_path=ROSTER):
    net.patient_lookups()
    folder = cache
    os.makedirs(folder, exist_ok=True)
    gpath, gen = read_list("general", folder, say, 2)
    ppath, pri = read_list("primary", folder, say, 30)
    opath, order = read_order(folder, say)
    spath, s2022 = read_senate_2022(folder, say)
    archive = net.get(PAGES["archive"], accept="text/html").decode("utf-8", "replace")
    time.sleep(1.5)
    found = links(archive, PAGES["archive"])
    abstract_url = found.get(f"{ABSTRACT_LABEL} (PDF)")
    if not abstract_url:
        raise SystemExit(f"Colorado (state races): the results archive no longer links \"{ABSTRACT_LABEL}\"")
    abstract = os.path.join(folder, "co_2026_primary_abstract.pdf")         # the same scan the federal loader keeps
    net.download(abstract_url, abstract, max_age_days=30, say=say)
    if not open(abstract, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit(f"Colorado (state races): {abstract_url} did not give a PDF")
    abstract_sha = sha_file(abstract)
    wpath, wins = read_writeins(folder, found, say)
    epath, enr = read_enr(folder, say)
    members, officials = roster(roster_path)

    problems, notes_out = [], []
    races, listed, off = {}, {}, {}                          # race_id -> race; race_id -> [rows]; race_id -> [struck rows]
    mates = {}                                               # party -> [Lt. Governor names]
    for r in gen["rows"]:
        race = race_for(r["office"], r["district"], r["name"])
        rid = race["race_id"]
        if rid in races and races[rid]["office"] != race["office"]:
            raise SystemExit(f"Colorado (state races): two offices share the race key {rid}")
        races.setdefault(rid, race)
        if r["office"] == "Lt. Governor":
            if not r["struck"]:
                mates.setdefault(r["party"], []).append(r["name"])
            continue
        (off if r["struck"] else listed).setdefault(rid, []).append(r)
    for rid in [k for k in races if k not in listed]:
        problems.append(f"{rid}: every candidate on the November list is struck through")
        listed[rid] = []

    # which Senate seats are up for four years, and which for the two years left of a term
    regular = {str(d) for d in s2022["districts"]}
    senate = {r["district"] for r in races.values() if r["office_kind"] == "state_senate"}
    for d in sorted(regular - senate, key=int):
        problems.append(f"Senate District {d} was elected in 2022 for four years but is not on the 2026 list")
    for rid, race in races.items():
        race["notes"] = []
        if race["office_kind"] == "state_senate" and race["district"] not in regular:
            race["special"] = 1
            race["notes"].append("This seat's four-year term runs to January 2029 (it was not among the seats elected in 2022, by the "
                                 "Secretary of State's 2022 abstract); this election fills the two years left of it.")
        else:
            race["special"] = 0
    house = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if house != list(range(1, 66)):
        problems.append(f"House: the November list does not name all 65 districts (missing {sorted(set(range(1, 66)) - set(house))})")

    # primary ballots, by race and party
    ballots = {}                                             # (race_id, code) -> {"party", "printed", "write_in", "struck"}
    for r in pri["rows"]:
        if r["office"] == "Lt. Governor":
            continue
        race = race_for(r["office"], r["district"], r["name"])
        code = CODES.get(r["party"])
        if not code:
            raise SystemExit(f"Colorado (state races): a party on the primary list that is not read ({r['party']!r})")
        if race["race_id"] not in races:
            problems.append(f"{race['race_id']} had a June 30 primary but is not on the November list")
            continue
        b = ballots.setdefault((race["race_id"], code), {"party": r["party"], "printed": [], "write_in": [], "struck": []})
        b["struck" if r["struck"] else ("write_in" if r["write_in"] else "printed")].append(r["name"])

    # the results site's contests, checked against the primary list, and each field against the certified abstract
    contests = {}
    for c in (enr or {}).get("contests", []):
        code = CODES.get(c["party"])
        if not code:
            raise SystemExit(f"Colorado (state races): a party on the results site that is not read ({c['party']!r})")
        contests[(c["race"], code)] = c
    scan_ok = abstract_sha == ABSTRACT_SHA
    if not scan_ok:
        problems.append("the Secretary's abstract is not the scan whose totals were read (its SHA-256 changed): read it again and update ABSTRACT")
    if enr is None:
        problems.append("the results site could not be read: primary fields are stored without votes")
    field_votes, checked, alone_with_write_in = {}, 0, []
    for key in sorted(set(ballots) | set(contests)):
        rid, code = key
        b = ballots.get(key, {"printed": [], "write_in": [], "struck": []})
        c = contests.get(key)
        bad = []
        if c:
            checked += 1
            if c["reported"] != c["counties"]:
                bad.append(f"{c['reported']} of {c['counties']} counties reported")
            if sorted(nkey(ch["name"]) for ch in c["choices"]) != sorted(nkey(n) for n in b["printed"]):
                bad.append(f"the results name {sorted(ch['name'] for ch in c['choices'])}, the primary list {sorted(b['printed'])}")
            for ch in c["choices"]:
                if sum(ch["counties"].values()) != ch["total"]:
                    bad.append(f"{ch['name']}'s county votes do not add up to the total")
        elif enr is not None and b["printed"]:
            bad.append("on the primary list but not on the results site")
        if bad:
            problems.append(f"{rid} {code}: " + "; ".join(bad))
        if len(b["printed"]) < 2:
            if b["write_in"] and len(b["printed"]) == 1:
                alone_with_write_in.append(f"{rid} {code}: {b['printed'][0]} and the certified write-in {', '.join(b['write_in'])}")
            continue
        if not c or bad or not scan_ok:
            continue
        votes = {nkey(ch["name"]): ch["total"] for ch in c["choices"]}
        for n in b["write_in"]:
            w = wins["candidates"].get(f"{rid}|{code}|{nkey(n)}")
            if w is None:
                problems.append(f"{rid} {code}: the certified write-in {n} has no line in the write-in results")
                votes = None
                break
            votes[nkey(n)] = w["total"]
        if votes is None:
            continue
        control = {nkey(n): v for n, v in (ABSTRACT.get(key) or {}).items()}
        if votes != control:
            problems.append(f"{rid} {code}: the results site's votes {votes} are not the certified abstract's {control or 'None (not read)'}")
            continue
        field_votes[key] = votes
    for key in ABSTRACT:
        if key not in ballots or len(ballots[key]["printed"]) < 2:
            problems.append(f"{key[0]} {key[1]}: in ABSTRACT but not a field on the primary list")

    # the November rows
    cands, write_ins, withdrawn, incumbents = [], [], [], 0
    for rid in sorted(listed):
        race = races[rid]
        people = holders(race, members, officials)
        if race["level"] == "court":
            judge = listed[rid][0]["name"] if len(listed[rid]) == 1 else None
            if not judge:
                problems.append(f"{rid}: a retention vote with {len(listed[rid])} names")
            race.update(holder_id=None, holder_name=judge, holder_party=None)
            race["notes"].append("A retention vote: voters answer Yes or No on keeping this judge in office.")
        else:
            race.update(holder_id="; ".join(p["id"] for p in people) or None, holder_name="; ".join(p["full"] for p in people) or None,
                        holder_party="; ".join(p["party"] or "" for p in people) or None)
            if not people:
                race["notes"].append("The roster used here does not list who holds this office today." if race["level"] != "legislature"
                                     else "The roster used here lists nobody in this seat today.")
        if race["office_kind"] == "governor":
            race["notes"].append("The Governor and Lieutenant Governor are elected together, one ticket to a party; the Secretary of "
                                 "State's list names each candidate for Lieutenant Governor on a row of its own.")
        if race["office_kind"] in ("state_board_of_education", "university_board") and race["district"]:
            race["notes"].append(f"Only the voters of {race['district']} elect this seat.")
        struck = off.get(rid, [])
        for r in struck:
            withdrawn.append(f"{r['name']} ({rid})")
        if struck:
            race["notes"].append("Withdrawn (struck through on the Secretary of State's list): "
                                 + "; ".join(f"{r['name']} ({r['party']})" for r in struck)
                                 + ". Whether the name is still printed is not in the list, so no ballot positions are given for this race.")
        # ballot positions
        printed = [r for r in listed[rid] if not r["write_in"]]
        position = {}
        drawn = order["order"].get(rid)
        if race["partisan"] and not struck:
            parties = [r["party"] for r in printed if r["party"] != "Unaffiliated"]
            missing = [p for p in parties if drawn is not None and p not in drawn]
            minors = [p for p in parties if p not in MAJOR]
            # a lone minor-party candidate whose party drew no line: the three-tier rule alone puts it after the major parties
            lone_minor = bool(missing) and missing == minors and len(minors) == 1
            if drawn is None:
                problems.append(f"{rid}: the ballot order drawing has no row for this race")
            elif len(parties) != len(set(parties)):
                problems.append(f"{rid}: two printed candidates of one party; no ballot positions given")
            elif missing and not lone_minor:
                problems.append(f"{rid}: candidates of parties with no drawn position ({missing}); no positions given")
            else:
                if lone_minor:
                    drawn = dict(drawn, **{missing[0]: max([drawn[p] for p in parties if p in MAJOR] or [0]) + 0.5})
                    race["notes"].append(f"The {missing[0]} has no line in the July 28 drawing for this race; as the race's only minor-party "
                                         "candidate, its candidate is placed after the major parties by the three-tier rule the Secretary's "
                                         "page cites (1-5-404, C.R.S.).")
                    notes_out.append(f"{rid}: the {missing[0]} drew no position; its lone minor-party candidate placed after the major parties")
                placed = sorted((r for r in printed if r["party"] != "Unaffiliated"), key=lambda r: drawn[r["party"]])
                independents = [r for r in printed if r["party"] == "Unaffiliated"]
                if len(independents) == 1:
                    placed.append(independents[0])
                elif independents:
                    notes_out.append(f"{rid}: {len(independents)} unaffiliated candidates; their order is not in the drawing, so no positions")
                    placed = []
                position = {id(r): n for n, r in enumerate(placed, start=1)}
        for r in sorted(listed[rid], key=lambda r: (r["write_in"], position.get(id(r), 99), r["name"])):
            if race["level"] == "court":
                party, pcode, inc, mid, note = NONPARTISAN, "N", 1, None, "Standing for retention as the sitting judge."
            else:
                party, pcode = r["party"], party_code(r["party"])
                who = one_fit(r["name"], people) if people else None
                inc, mid = (1, who["id"]) if who else (0, None)
                note = None
                code = CODES.get(r["party"])
                b = ballots.get((rid, code))
                on_primary = b and any(nkey(n) == nkey(r["name"]) for n in b["printed"] + b["write_in"])
                if not r["write_in"] and ((b and not on_primary) or (code in ("DEM", "REP") and not b)):
                    note = "Not on the party's June 30 primary ballot."
                if race["office_kind"] == "governor":
                    ms = mates.get(r["party"], [])
                    if len(ms) == 1:
                        note = " ".join(x for x in (f"Running mate for Lieutenant Governor: {ms[0]}.", note) if x)
                    else:
                        notes_out.append(f"{rid}: {r['party']} has {len(ms)} candidates for Lieutenant Governor on the list")
            if r["write_in"]:
                write_ins.append(f"{r['name']} ({rid})")
                note = " ".join(x for x in (WRITE_IN, note) if x)
            incumbents += inc
            cands.append((rid, "general", GENERAL, r["name"], party, pcode, None if r["write_in"] else position.get(id(r)), inc,
                          1 if r["write_in"] else 0, None, None, None, mid, SRC["general"], note))
        if not printed:
            problems.append(f"{rid}: no printed candidate on the November list")
    for rid, d in order["order"].items():
        if rid not in races:
            problems.append(f"{rid}: in the ballot order drawing but not on the November list")

    # the primary fields
    fields, general_notes = 0, {}
    for key in sorted(ballots):
        rid, code = key
        b = ballots[key]
        if len(b["printed"]) < 2:
            continue
        fields += 1
        race = races[rid]
        people = holders(race, members, officials)
        names = b["printed"] + b["write_in"]
        votes = field_votes.get(key)
        total = sum(votes.values()) if votes else 0
        nominee = [r["name"] for r in listed[rid] + off.get(rid, []) if CODES.get(r["party"]) == code and not r["write_in"]]
        on_list = nominee[0] if len(nominee) == 1 and any(nkey(n) == nkey(nominee[0]) for n in names) else None
        top = max(votes, key=votes.get) if votes else None
        top_name = next((n for n in names if nkey(n) == top), None) if top else None
        won = top_name or on_list                            # the certified votes decide; without them, the November list
        if not won:
            problems.append(f"{rid} {code}: no certified votes, and the party's November candidate ({', '.join(nominee) or 'none'}) "
                            "is not one name on its primary ballot; no outcome stored")
        elif top_name and nkey(top_name) != nkey(nominee[0] if len(nominee) == 1 else ""):
            later = nominee[0] if len(nominee) == 1 else None
            notes_out.append(f"{rid} {code}: {top_name} had the most votes, but the party's November candidate is {later or 'nobody'}")
            if later:
                general_notes[(rid, nkey(later))] = (f"The party's candidate on the November list, though {top_name} had the most votes in "
                                                     f"its June 30 primary and is not on the November list.")
        for n in sorted(names, key=lambda n: (-(votes or {}).get(nkey(n), 0), n)):
            v = votes.get(nkey(n)) if votes else None
            who = one_fit(n, people) if people and race["level"] != "court" else None
            wi = n in b["write_in"]
            note = WRITE_IN if wi else None
            if won and nkey(n) == nkey(won) and any(nkey(r["name"]) == nkey(n) for r in off.get(rid, [])):
                note = " ".join(x for x in (note, "Withdrew from the November ballot after the primary.") if x)
            elif won and nkey(n) == nkey(won) and top_name and not any(nkey(x) == nkey(n) for x in nominee):
                note = " ".join(x for x in (note, "Had the most votes; not on the November list.") if x)
            cands.append((rid, f"primary-{code}", PRIMARY, n, b["party"], party_code(b["party"]), None, 1 if who else 0, int(wi), v,
                          round(100 * v / total, 1) if v is not None and total else None,
                          ("advanced" if nkey(n) == nkey(won) else "lost") if won else None, who["id"] if who else None,
                          SRC["abstract"] if votes else SRC["primary"], note))
    withdrew_primary = [f"{n} ({k[0]} {k[1]})" for k, b in sorted(ballots.items()) for n in b["struck"]]
    for i, c in enumerate(cands):
        extra = general_notes.get((c[0], nkey(c[3]))) if c[1] == "general" else None
        if extra:
            cands[i] = c[:14] + (" ".join(x for x in (c[14], extra) if x),)

    # counts read = counts stored
    gen_rows = [c for c in cands if c[1] == "general"]
    loaded_general = [r for r in gen["rows"] if r["office"] != "Lt. Governor"]
    if len(gen_rows) + len(withdrawn) != len(loaded_general):
        problems.append(f"November: {len(loaded_general)} state rows read (Lt. Governor aside), {len(gen_rows)} stored and {len(withdrawn)} withdrawn")
    placed = sum(len(b["printed"]) + len(b["write_in"]) + len(b["struck"]) for b in ballots.values())
    if placed + sum(1 for p in problems if "had a June 30 primary but is not on the November list" in p) != len(pri["rows"]):
        problems.append(f"primary: {len(pri['rows'])} state rows read, {placed} placed on a party's ballot")
    # a lone name on a party's primary ballot (no field) that is not that party's candidate in November: reported, not stored
    gone = [f"{n} ({rid}, {b['party']})" for (rid, code), b in sorted(ballots.items()) if len(b["printed"]) == 1
            for n in b["printed"] if not any(nkey(r["name"]) == nkey(n) for r in listed.get(rid, []) + off.get(rid, []))]
    by_kind = Counter(r["office_kind"] for r in races.values())
    gen_by_kind = Counter(races[c[0]]["office_kind"] for c in gen_rows)

    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], None,
                  r["district"], r["seat"], r["special"], r["partisan"], r.get("holder_id"), r.get("holder_name"), r.get("holder_party"),
                  GENERAL, " ".join(r["notes"]) or None) for r in races.values()]
    not_loaded = gen.get("not_loaded", {})
    agency = "Colorado Secretary of State"
    sources = [
        source_row(SRC["general"], "official candidate list", agency,
                   "2026 General Election Official Candidate List (certified to the counties September 4, 2026): state offices",
                   gen["url"], gen["updated"], gen["read"], gen["page_sha256"], len(gen["rows"]),
                   f"The web page's table read (a struck-through name has withdrawn), columns Candidate name, Office, District, Party, Write in?, "
                   f"by their headings; its workbook (SHA-256 {gen['workbook_sha256'][:16]}...) lists the same seats, parties and write-in marks"
                   + (f", written differently: {'; '.join(gen['differ'])}; the page's spelling is kept" if gen["differ"] else "")
                   + f". Withdrawn, left off: {'; '.join(withdrawn) or 'none'}. Certified write-ins, not printed: {'; '.join(write_ins) or 'none'}. "
                   f"Each Lieutenant Governor row is named as the running mate of its party's candidate for Governor. Not loaded: "
                   + ("; ".join(f"{o} {n}" for o, n in sorted(not_loaded.items())) or "nothing")
                   + f" (courts of a judicial district or county, and the Regional Transportation District's board); {gen.get('federal_rows', 0)} "
                   "rows for Congress are left to the federal loader."),
        source_row(SRC["order"], "official ballot order", agency,
                   "2026 General Election Ballot Order for Major & Minor Party Candidates (lot drawing of July 28, 2026): state offices",
                   order["workbook"], order["updated"], order["read"], order["workbook_sha256"], len(order["order"]),
                   "Major parties, then minor parties, then unaffiliated candidates (1-5-404, C.R.S.), each tier by lot, Governor and Lieutenant "
                   "Governor by the family name of the candidate for Governor; the positions stored are places on the printed ballot, a party "
                   "with no candidate left out, a race's one unaffiliated candidate after the parties. No positions where a name is struck "
                   "through or for retention votes."),
        source_row(SRC["primary"], "official candidate list", agency,
                   "2026 Official Primary Election Candidate List (certified to the counties May 1, 2026): state offices",
                   pri["url"], pri["updated"], pri["read"], pri["page_sha256"], len(pri["rows"]),
                   f"Read the same way as the November list. Party primaries with a field (two or more printed names): {fields}. Withdrawn "
                   f"(struck through): {'; '.join(withdrew_primary) or 'none'}. Every printed name is checked against the results site's "
                   f"choices, {checked} party primaries in all. Alone on a party's primary ballot but not on the November list: "
                   f"{'; '.join(gone) or 'none'}."),
        source_row(SRC["abstract"], "official results", agency,
                   "2026 State Primary Election Statewide Abstract of Votes Cast (June 30, 2026), certified July 24, 2026",
                   abstract_url, "2026-07-24", dt.datetime.fromtimestamp(os.path.getmtime(abstract)).strftime("%Y-%m-%d"), abstract_sha,
                   sum(len(v) for v in field_votes.values()),
                   f"A scan with no text layer. The Total row of every state field was read by eye on 2026-09-30; {len(field_votes)} of {fields} "
                   "fields' figures on the results site equal it candidate by candidate, so the votes stored are the certified ones. pct is of "
                   "the party primary's votes, certified write-ins included (Colorado counts no other write-ins)."
                   + (f" One printed name and a certified write-in, not a field: {'; '.join(alone_with_write_in)}." if alone_with_write_in else "")),
        source_row(SRC["writeins"], "official results", agency, "2026 State Primary Election Certified Write-In Results: state offices",
                   wins["url"], "", wins["read"], wins["sha256"], len(wins["candidates"]),
                   "Certified write-in candidates for state offices, county by county; the counties add up to each Total Votes line."),
        source_row(SRC["senate2022"], "official results", agency, "2022 Abstract of Votes Cast, General Election (November 8, 2022): State Senate",
                   s2022["url"], "", s2022["read"], s2022["sha256"], len(s2022["districts"]),
                   f"Only the district headings read: the seats elected in 2022 for four years, up again in 2026 ({', '.join(map(str, s2022['districts']))}). "
                   f"Senate seats on the 2026 list that are not among them fill the two years left of a term: "
                   f"{', '.join(sorted((r['district'] for r in races.values() if r['office_kind'] == 'state_senate' and r['special']), key=int)) or 'none'}."),
    ]
    if enr:
        sources.append(source_row(SRC["enr"], "results data, checked against the certified abstract", "Colorado Secretary of State (election night reporting, Clarity)",
                                  f"2026 Primary: county detail (detail.xml), version {enr['version']}, written {enr['written']}: state contests",
                                  enr["url"], "", enr["read"], enr["sha256"], sum(len(c["choices"]) for c in enr["contests"]),
                                  f"From the site at {ENR}, headed \"Unofficial Results\". The state party primaries kept, every county's votes per "
                                  "candidate; each candidate's counties add up to the total."))
    if members or officials:
        sources.append(source_row(SRC["roster"], "roster", "Open States (people project, CC0)",
                                  "Legislators serving now and statewide officials (state_co.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", "", dt.datetime.fromtimestamp(os.path.getmtime(roster_path)).strftime("%Y-%m-%d"),
                                  sha_file(roster_path), len(members) + len(officials),
                                  "Used only to say who holds each seat today and to mark incumbents: ids, names, parties, districts and start dates. "
                                  "Not an official record."))

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?", (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'co-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
    finally:
        con.close()

    seats = {"statewide": sum(1 for r in races.values() if r["level"] == "statewide"),
             "Senate": by_kind["state_senate"], "House": by_kind["state_house"], "court": sum(1 for r in races.values() if r["level"] == "court")}
    say(f"    Colorado: {len(races)} state races on the November ballot (statewide {seats['statewide']}, Senate {seats['Senate']} "
        f"[{sum(1 for r in races.values() if r['special'])} for the rest of a term], House {seats['House']}, retention {seats['court']}), "
        f"{len(gen_rows)} candidates ({len(write_ins)} certified write-ins, {len(withdrawn)} withdrawn left off); {fields} primary fields, "
        f"{len(field_votes)} with certified votes; {incumbents} incumbents marked")
    for p in problems:
        say(f"      CHECK {p}")
    for n in notes_out:
        say(f"      note: {n}")
    if gone:
        say(f"      note: alone on a party's June 30 primary ballot but not on the November list: {'; '.join(gone)}")
    return {"races": len(races), "candidates": len(gen_rows), "by_kind": dict(by_kind), "general_by_kind": dict(gen_by_kind),
            "fields": fields, "voted_fields": len(field_votes), "checked_primaries": checked, "problems": problems, "notes": notes_out,
            "withdrawn": withdrawn, "write_ins": write_ins, "withdrew_primary": withdrew_primary, "alone_with_write_in": alone_with_write_in,
            "not_loaded": not_loaded, "incumbents": incumbents, "gone": gone}


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = DEFAULT_CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_co.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
