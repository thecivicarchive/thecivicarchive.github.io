"""
ballot/state_local_ut.py - Utah's state races on the November 3, 2026 ballot, from the Lieutenant Governor's Office of
Elections, into ballot_local_2026.sqlite (the tables sl_races, sl_candidates, sl_sources and sl_places). The federal
ballot database (ballot_2026.sqlite) is never opened here, and U.S. House rows are left to ballot/lists/ut.py.

What is on the ballot: half the Utah Senate (the districts the certification lists, four-year terms, plus any seat
filled for the rest of an unexpired term), all 75 seats of the Utah House of Representatives, the State Board of
Education seats up this year (partisan: the certification prints each candidate's party), and the retention elections
of the Supreme Court, the Court of Appeals and the district and juvenile courts. No statewide executive office is on the
2026 certification. The justice courts' retention questions (municipal and county courts) and the two proposed
constitutional amendments are counted and left out.

Sources, the Lieutenant Governor's own and nothing else (the same files ballot/lists/ut.py reads for Congress, and its
cached copies in ballot_cache/ut/):

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
No photos, ages, websites, biographies or money reach the database.

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

from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists import ut as fed  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, lines, rows as pdf_rows  # noqa: E402
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
       "canvass": "ut-ltg-2026-state-primary-canvass", "roster": "ut-openstates-roster", "counties": "ut-census-cb-2024-county"}

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
                          jurisdiction=dname or NAME, jurisdiction_id=f"JD{dist}" if dist else FIPS,
                          county_ids=json.dumps(cids) if cids else None, district=str(dist) if dist else None,
                          seat=None, special=0, partisan=0, holder_id=None, holder_name=name, holder_party=None,
                          election_date=GENERAL, note=note)
        cand.append((rid, "general", GENERAL, name, "Nonpartisan office", "N", 1, 1, 0, None, None, None, None, SRC["general"],
                     "Standing for retention as the sitting judge. " + CAPS))
    unread = [q["name"] for i, q in enumerate(typed_q) if i not in used_q]
    if unread:
        checks.append(f"judges in the filings page's State Judicial table not found on the certification: {'; '.join(unread)}")
    n_retention = len(used_q)

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
    place_rows = [("county", g, full, json.dumps([g]), SRC["counties"]) for g, (_n, full) in sorted(cmap.items())]
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
         f"Retention: {n_retention} state-court judges loaded; {justice} justice-court questions (municipal and county courts) "
         f"and {amendments} proposed constitutional amendments are not loaded. Withdrawn, disqualified or deceased, left off: "
         f"{len(gone)}. Out at a party convention, not on any ballot: {convention}."),
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
         sha_of(COUNTY_ZIP), len(place_rows), "Utah's 29 counties: names and GEOIDs only."),
    ]
    for county, (spath, url, used_for) in sorted(county_files.items()):
        src.append((f"ut-{fold(county).replace(' ', '-')}-2026-state-primary-summary", STATE, "official results",
                    f"{county} Clerk (posted on the Lieutenant Governor's election results system)",
                    f"2026 Primary Election: final official summary results report ({county})", url, "", mdate(spath), sha_of(spath),
                    len(used_for), "The votes of the single-county state primaries the county certified: " + ", ".join(used_for) + "."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ut-%' OR (kind = 'county' AND id GLOB '49[0-9][0-9][0-9]')")
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    by_kind = Counter(r["office_kind"] for r in races.values())
    alone = Counter(races[rid]["office_kind"] for rid, rows in general_by_race.items() if len(rows) == 1)
    inc = Counter(races[c[0]]["office_kind"] for c in general if c[7] and races[c[0]]["level"] != "court")
    writes = sum(1 for c in general if c[8])
    senate = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    say(f"    Utah (state races): {by_kind['state_senate']} Senate seats (districts {', '.join(map(str, senate))}), "
        f"{by_kind['state_house']} House seats, {by_kind['state_board_of_education']} State Board of Education seats, "
        f"{n_retention} state-court retention elections; {len(general)} names on the November ballot (Senate "
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
