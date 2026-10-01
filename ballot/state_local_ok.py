"""
ballot/state_local_ok.py - Oklahoma's state races in 2026: the Oklahoma Senate seats up this year (the 24 even-numbered
districts, plus any seat filled for the rest of a term), all 101 Oklahoma House seats, the statewide offices (Governor,
Lieutenant Governor, State Auditor and Inspector, Attorney General, State Treasurer, Superintendent of Public
Instruction, Commissioner of Labor, Insurance Commissioner, Corporation Commissioner), and the district court judges
on the November ballot, with the June 16 party primaries that chose the nominees; and the local contests on the
November ballot: county offices, city and town offices and fire protection district boards (see "The local rows"
below). Written into ballot_local_2026.sqlite (never ballot_2026.sqlite).

Sources, all the Oklahoma State Election Board's own, the same ones the federal loader (ballot/lists/ok.py) reads:

  NOVEMBER / 2026 List of Elections (hosting.okelections.us/electionlist.html): county by county, every office on each
  county's November 3 ballot and under it each candidate as "NAME, PARTY" (judges by name alone). It carries names,
  parties and offices only. A district that spans several counties is listed once per county, and every county's
  list of it must agree. The list's order is kept as the ballot order, as the federal loader keeps it.

  Candidates for Office 2026 (the Candidate List Book, a PDF): everyone who filed April 1-3, 2026, by office, district
  and party. Each entry is one line of fixed-width type: the filing number, the name and the candidate's city. Only
  the first thirty character columns (the filing number and the name) are ever placed into text; the city column is
  never read. The book is read from the federal loader's cached copy when there is one, otherwise fetched into
  memory; it is never written to disk by this loader. What was read (office, district, party, filing number, name)
  is kept as a small JSON extract with the file's SHA-256.

  2026 Candidate Withdrawals (Number, Name, Office, Date; the federal loader's extract) and 2026 Contests of Candidacy
  (cause, the case name, office and ruling; kept as a small extract). A candidate who withdrew or was stricken before
  the June 16 primary was not on its ballot.

Oklahoma leaves a seat off the November ballot when it was settled earlier, and the November list shows it: a seat
with one candidate left once filing closed (stored as that candidate with outcome "unopposed" and a note, as the
federal Florida loader does), and a seat for which only one party's candidates filed (settled in that party's June 16
primary or August 25 runoff: the field is stored, with no winner, because the Board publishes results only on
results.okelections.us, which refuses scripts with 403 Forbidden). No vote counts are loaded, and which primaries went
to the August 25 runoff is not read. A primary field is two or more of a party's candidates on its June 16 ballot; the
nominee is that party's candidate on the November list.

Judges: the November list names the district and associate district judge races still to be decided in November;
only those are loaded (a judicial seat with one candidate, or decided by a majority in June, is not on the list and is
counted in the report). The Supreme Court, Court of Criminal Appeals and Court of Civil Appeals retention questions are
on every ballot, but the list does not name the judges, so they are not loaded. No district attorney is on the
November list: the book's DISTRICT ATTORNEY section is read for its district headings and for how many filed under
each party (the filing number's five columns only), and the coverage note says how the 27 offices were settled.

The local rows (levels county, city and other), from the same November list
---------------------------------------------------------------------------
Under each county the list also prints the county offices on that county's ballot (inside "LEGISLATIVE, DISTRICT AND
COUNTY OFFICERS": COUNTY COMMISSIONER DISTRICT NO. n, COUNTY ASSESSOR, COUNTY TREASURER, and an unexpired term of a
sheriff or county clerk), each candidate as "NAME, PARTY", and a section for every city ("CITY OF X"), town ("TOWN OF
X") and fire protection district ("X FIRE") with something on the ballot: an office ("MAYOR", "COUNCILMEMBER -
COUNCILMEMBER WARD 3", "BOARD MEMBER - MEMBER OF THE BOARD OF DIRECTORS") with its candidates by name alone, or a
proposition. "X COUNTY QUESTIONS" sections hold propositions only. The page has no contact columns at all (no links,
no addresses), so a fetched copy is kept whole in ballot_cache/ok/local/.

Oklahoma prints only contested races (26 O.S. 6-102: an unopposed candidate's name is not printed on any ballot), so a
county office with one candidate left, or one settled in the June 16 primary or the August 25 runoff, is not on the
list and is not loaded; sl_notes and sl_gaps say so. Propositions and questions are counted, not loaded. A contest
printed under several counties (a city that lies in two) must read the same in each; one that does not is left out and
written to sl_gaps, as is an office or a section of a kind this loader has not been checked against, and a candidate
line that does not read as a name (the line itself is never printed). None of that stops the state rows from loading.

  race ids      2026-OK-<county GEOID>-<office kind>[-<district>][-S]; 2026-OK-M-<place code>-<office kind>[-<ward>][-S];
                2026-OK-X-<county code>-<name as printed>-fire-board[-S]. -S marks an unexpired term (special = 1).
  places        a county is its 5-digit GEOID, found by the county's name in the Census county file (the list numbers
                the counties 01 to 77 in alphabetical order; GEOID = 40 and 2n - 1 is checked). A city or town is
                OK-M-<Census place code>: matched in the Census Bureau's 2020 place codes file (st40_ok_place2020.txt,
                names, codes and counties only, kept whole in ballot_cache/ok/local/) by its name and kind word, exactly
                one entry, and named as the Bureau writes it ("Bartlesville city"). A fire protection district has no
                official code: OK-X-<the 3-digit code of the first county that prints it>-<its name as printed>, and it
                is named as the list prints it, with its kind in brackets ("Verdigris Fire (fire protection district)":
                19 O.S. 901.5 has such a district elect the members of its board of directors each November).
  parties       county offices are partisan (the party as the list prints it, in the state rows' words); city, town and
                fire district offices carry no party on the list and are stored as "Nonpartisan office".
  ballot order  kept for county offices, and only where the list's order is the one 26 O.S. 6-106 sets (recognized
                parties in the order of the Board's drawing, then independents) with no two candidates of one label;
                for the nonpartisan offices the list does not say its order is the ballot's, so none is stored.
  names         printed in capitals and shown in ordinary capitals, as the state rows are; a word the list itself prints
                in mixed case (NaRISSA, McCLENDON) keeps the list's own inner capitals. No local candidate is matched
                to any roster, and none carries a holder, a member id or an incumbent mark.
  also written  sl_gaps and sl_notes (ballot.check_local.EXTRA_SCHEMA): what is not here and why, and which local
                offices Oklahoma elects on November 3 and which at another time (19 O.S. 131 and 901.5, 11 O.S. 16-102
                and 16-103, and the Board's 2026 Voter Information Calendar, all read on 2026-09-30).

Today's holders come from the Open States roster in state_ok.sqlite (legislators by chamber and district; the
officials table for Governor, Lieutenant Governor and Attorney General); only id, name, party, chamber and district
are selected. A candidate is marked as the sitting member only when the name fits the roster's holder of that same
seat and no other candidate in the race fits.

Nothing but office, district, name, party, ballot order and status is read from any list; nothing else is printed,
logged, cached or stored.
"""

import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import zipfile
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import ok as fed                                          # noqa: E402
from ballot.lists.tx import proper                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                     # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "OK", "40", "Oklahoma"
GENERAL = "2026-11-03"
PRIMARY, RUNOFF = fed.PRIMARY, fed.RUNOFF
ROSTER_DB = os.path.join(HERE, "state_ok.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# statewide offices as both lists print them: (race key, office_kind, office shown, roster office in state_ok.sqlite)
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "STATE AUDITOR AND INSPECTOR": ("AUD", "state_auditor", "State Auditor and Inspector", None),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer", None),
    "SUPERINTENDENT OF PUBLIC INSTRUCTION": ("SPI", "superintendent_of_public_instruction", "Superintendent of Public Instruction", None),
    "COMMISSIONER OF LABOR": ("LAB", "labor_commissioner", "Commissioner of Labor", None),
    "INSURANCE COMMISSIONER": ("INS", "insurance_commissioner", "Insurance Commissioner", None),
    "CORPORATION COMMISSIONER": ("CC", "corporation_commissioner", "Corporation Commissioner", None),
}
# the book's office headings (12-point) and what this loader does with each
BOOK_OFFICES = {"UNITED STATES SENATOR": "skip", "UNITED STATES REPRESENTATIVE": "skip", "DISTRICT ATTORNEY": "skip",
                "DISTRICT JUDGE": "DJ", "ASSOCIATE DISTRICT JUDGE": "ADJ", "STATE SENATOR": "SS", "STATE REPRESENTATIVE": "SH",
                **{k: "SW" for k in STATEWIDE}}
PARTIES = fed.PARTIES                                    # REPUBLICAN Republican, DEMOCRAT Democrat, ...
CODES = fed.CODES                                        # Republican REP, Democrat DEM, Libertarian LIB
NONPARTISAN, NP_CODE = "Nonpartisan office", "N"
LEFT, CW = fed.LEFT, fed.CW
NUM_END, NAME_START, NAME_END = 5, 7, 30                 # filing number in columns 0-4, the name in 7-29; nothing after is read
COUNTY_LIST = re.compile(r"\*?[A-Za-z][A-Za-z .']*(?:, \*?[A-Za-z][A-Za-z .']*)*")
NAME_OK = re.compile(r"[^\W\d_][\w .,'\"()-]*")                  # letters of any alphabet (PEÑA, ASSÉO)

SRC_GENERAL = "ok-seb-2026-general-list"
SRC_BOOK = "ok-seb-2026-candidate-list-book"
SRC_WD = "ok-seb-2026-withdrawals"
SRC_CONTESTS = "ok-seb-2026-contests"
SRC_ROSTER = "ok-openstates-roster"
SRC_COUNTIES = "ok-census-cb-2024-county"

# the local rows
LOCAL_DIR = os.path.join(CACHE, "ok", "local")
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st40_ok_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
CALENDAR_URL = "https://oklahoma.gov/elections/elections-results/next-election/voter-information-calendar.html"
FILING_URL = "https://oklahoma.gov/elections/candidates/2026-candidate-filing-information.html"
SRC_LOCAL = "ok-seb-2026-general-list-local"
SRC_PLACES = "ok-census-2020-place"
STATE_SECTIONS = ("STATE OFFICERS", "CONGRESSIONAL OFFICERS", "JUDICIAL OFFICERS", "JUDICIAL RETENTION", "STATE QUESTIONS")
LEG_SECTION = "LEGISLATIVE, DISTRICT AND COUNTY OFFICERS"
UNEXPIRED_MARK = " (UNEXPIRED TERM)"
UNEXPIRED_NOTE = "An election for the rest of the term (the Board's list: unexpired term)."
NO_CANDIDATE = "The State Election Board's list shows no candidate for this office."
COUNTY_OFFICES = {"ASSESSOR": ("county_assessor", "County Assessor"), "TREASURER": ("county_treasurer", "County Treasurer"),
                  "SHERIFF": ("sheriff", "County Sheriff"), "CLERK": ("county_clerk", "County Clerk")}
COUNCIL_WORDS = {"COUNCILMEMBER": "Councilmember", "COUNCIL MEMBER": "Council Member", "COUNCILMAN": "Councilman",
                 "COUNCILWOMAN": "Councilwoman", "COUNCILPERSON": "Councilperson", "COUNCILOR": "Councilor",
                 "COUNCIL": "Councilmember"}                       # "COUNCILMEMBER - COUNCIL DISTRICT 1": the list's own office word
PARTY_RANK = {"Republican": 1, "Democrat": 2, "Libertarian": 3, "Independent": 4}      # 26 O.S. 6-106 and the Board's drawing
NOT_CHECKED = ("The State Election Board's November list prints this contest, but this loader has not been checked against "
               "an office of this kind, so it is not shown yet.")

UNOPPOSED = ("Unopposed: the only candidate for this seat once withdrawals and contests of candidacy were settled, so the seat "
             "is not on the State Election Board's November 3 list and this name is not printed on the ballot.")
RESULTS_REFUSED = ("The Board publishes who won only on its results site (results.okelections.us), which refuses scripts, so "
                   "the winner is not shown here.")


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def squash(name):
    return fold(name).replace(" ", "")


# ---------- races: one key for both lists ----------

def race_of(kind, district=None, office_no=None, county=None, special=False):
    """{race_id, level, office_kind, office, district, seat, special, partisan, chamber, roster, ...} for a race either
    list names."""
    if kind == "SW":
        key, okind, office, roster = STATEWIDE[district]
        return {"race_id": f"2026-{STATE}-{key}", "level": "statewide", "office_kind": okind, "office": office, "district": None,
                "seat": None, "special": 0, "partisan": 1, "chamber": None, "roster": roster, "jurisdiction": NAME,
                "jurisdiction_id": FIPS}
    if kind in ("SS", "SH"):
        d = str(int(district))
        return {"race_id": f"2026-{STATE}-{kind}{d}" + ("-UNEXP" if special else ""), "level": "legislature",
                "office_kind": "state_senate" if kind == "SS" else "state_house",
                "office": "State Senator" if kind == "SS" else "State Representative", "district": d, "seat": None,
                "special": 1 if special else 0, "partisan": 1, "chamber": "Senate" if kind == "SS" else "House", "roster": None,
                "jurisdiction": NAME, "jurisdiction_id": FIPS}
    if kind == "DJ":
        d, o = str(int(district)), str(int(office_no))
        return {"race_id": f"2026-{STATE}-DC-{d}-{o}", "level": "court", "office_kind": "district_court", "office": "District Judge",
                "district": d, "seat": f"Office {o}", "special": 0, "partisan": 0, "chamber": None, "roster": None,
                "jurisdiction": f"{ordinal(d)} Judicial District", "jurisdiction_id": f"{STATE}-JD{d}"}
    if kind == "ADJ":
        return {"race_id": f"2026-{STATE}-ADJ-{county[0]}" + (f"-{office_no}" if office_no else ""), "level": "court",
                "office_kind": "district_court", "office": "Associate District Judge", "district": None,
                "seat": f"Office {office_no}" if office_no else None, "special": 0, "partisan": 0, "chamber": None, "roster": None,
                "jurisdiction": county[1], "jurisdiction_id": county[0]}
    raise ValueError(kind)


# ---------- the Candidate List Book: filing number and name columns only ----------

def name_grid(runs):
    """The first thirty character columns of one printed line of the book (filing number and name), placed by where each
    run starts. Characters at column thirty and beyond (the candidate's city) are never placed."""
    g = [" "] * NAME_END
    for x0, _y, _size, t, _x1 in runs:
        c = round((x0 - LEFT) / CW)
        if c >= NAME_END:
            continue
        for i, ch in enumerate(t):
            if c + i >= NAME_END:
                break
            if c + i >= 0:
                g[c + i] = ch
    return "".join(g)


def read_book(data, cmap):
    """([{kind, race_id, party, number, name}] for the state offices in the book's order, {race_id: race with the counties
    its heading names}). Lines are
    either a candidate (read through name_grid only), a wrapped name (the same), or a heading compared against the
    heading patterns below; a heading's text is never printed or stored unless it is an office, district or party."""
    pdf = PDF(data)
    pages = pdf.pages()
    cover = " ".join(join(rs) for _y, rs in pdf_rows(pdf, *pages[0]))
    if "Board April 1-3, 2026" not in cover or "April 3, 2026" not in cover:
        raise SystemExit("Oklahoma (state races): the Candidate List Book's cover no longer reads as the April 1-3, 2026 filings")
    out, seen, races = [], [], {}
    kind = race = party = last = None
    for n, (page, res) in enumerate(pages, start=1):
        for y, runs in pdf_rows(pdf, page, res):
            g = name_grid(runs)
            cand = bool(re.fullmatch(r"\d{5}", g[:NUM_END])) and not g[NUM_END:NAME_START].strip()
            if not cand and max(r[2] for r in runs) >= 11.5:              # an office heading, 12-point
                heading = join(runs)
                if heading in BOOK_OFFICES:
                    kind, race, party, last = BOOK_OFFICES[heading], None, None, None
                    seen.append(heading)
                    if kind == "SW":
                        race = race_of("SW", heading)
                        races[race["race_id"]] = race
                elif kind is not None:
                    raise SystemExit(f"Oklahoma (state races): an office heading on page {n} of the book this loader does not know")
                continue
            if kind is None or kind == "skip":                            # the cover, federal offices, district attorneys
                continue
            if cand:
                near = [r for r in runs if round((r[0] - LEFT) / CW) < NAME_END]
                if abs(min(r[0] for r in runs) - LEFT) > 1 or any(len(r[3]) >= 5 and abs((r[4] - r[0]) / len(r[3]) - CW) > 0.05 for r in near):
                    raise SystemExit(f"Oklahoma (state races): the book's type or margin changed on page {n}; its columns cannot be read by position")
                if race is None or (kind in ("SW", "SS", "SH") and not party):
                    raise SystemExit(f"Oklahoma (state races): a candidate on page {n} of the book comes before its district or party heading")
                if g[NAME_END - 1] != " ":
                    raise SystemExit(f"Oklahoma (state races): a name on page {n} of the book reaches the edge of its column and may run on")
                rec = {"kind": kind, "race_id": race["race_id"], "party": party if kind in ("SW", "SS", "SH") else NONPARTISAN,
                       "number": int(g[:NUM_END]), "name": g[NAME_START:NAME_END].strip()}
                last = [rec, y]
                out.append(rec)
                continue
            x0 = min(r[0] for r in runs)
            if last and not g[:NAME_START].strip() and g[NAME_START:].strip() and abs(x0 - (LEFT + NAME_START * CW)) < 1.5 \
                    and 0 < last[1] - y < 15:
                if g[NAME_END - 1] != " ":
                    raise SystemExit(f"Oklahoma (state races): a name on page {n} of the book reaches the edge of its column and may run on")
                last[0]["name"] += " " + g[NAME_START:NAME_END].strip()   # a long name, wrapped in its own column
                last[1] = y
                continue
            heading = join(runs)                                          # compared only; never printed
            last = None
            if heading.upper() in PARTIES and len(heading) < 20:
                if kind not in ("SW", "SS", "SH"):
                    raise SystemExit(f"Oklahoma (state races): a party heading under a nonpartisan office on page {n} of the book")
                party = PARTIES[heading.upper()]
                continue
            m = re.fullmatch(r"DISTRICT (\d+)( \(unexpired\))? - (.+)", heading) if kind in ("SS", "SH") else None
            if m and COUNTY_LIST.fullmatch(m.group(3)):
                race, party = race_of(kind, m.group(1), special=bool(m.group(2))), None
                race["counties"] = counties_named(m.group(3), cmap, f"{kind} {m.group(1)}")
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            m = re.fullmatch(r"DISTRICT (\d+), OFFICE (\d+) - (.+)", heading) if kind == "DJ" else None
            if m and COUNTY_LIST.fullmatch(m.group(3)):
                race = race_of("DJ", m.group(1), m.group(2))
                race["counties"] = counties_named(m.group(3), cmap, f"district judge {m.group(1)}-{m.group(2)}")
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            m = re.fullmatch(r"([A-Z][A-Z .']*) COUNTY(?:,? (?:- )?OFFICE (?:NO\. )?(\d+))?", heading.upper()) if kind == "ADJ" else None
            if m:
                c = cmap.get(squash(m.group(1)))
                if not c:
                    raise SystemExit(f"Oklahoma (state races): a county in the book's associate district judge headings is not in the Census file ({m.group(1)})")
                race = race_of("ADJ", county=c, office_no=m.group(2))
                race["counties"] = [c[0]]
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            raise SystemExit(f"Oklahoma (state races): a line on page {n} of the candidate list book is not read (at {y:.0f} points)")
    for rec in out:
        rec["name"] = re.sub(r"\s+", " ", rec["name"]).strip()
        if not NAME_OK.fullmatch(rec["name"]):
            raise SystemExit(f"Oklahoma (state races): filing number {rec['number']} does not read as a name; the columns may have moved")
    missing = [h for h in STATEWIDE if h not in seen] + [h for h in ("STATE SENATOR", "STATE REPRESENTATIVE") if h not in seen]
    if missing:
        raise SystemExit(f"Oklahoma (state races): the book has no section for {missing}")
    return out, races


def counties_named(text, cmap, where):
    out = []
    for w in text.split(","):
        c = cmap.get(squash(w.replace("*", "")))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county named in the book for {where} is not in the Census file ({w.strip()})")
        out.append(c[0])
    return sorted(set(out))


def district_attorneys(data):
    """{"districts", "one_candidate", "one_party", "more_parties"}: how the book's DISTRICT ATTORNEY section stood when
    filing closed. Read: the section's district and party headings, and for each candidate line the five columns of
    the filing number, to count it. No name is kept, and the city column is never placed into text."""
    pdf = PDF(data)
    inside, done, district, party, count = False, False, None, None, {}
    for page, res in pdf.pages():
        for _y, runs in pdf_rows(pdf, page, res):
            g = name_grid(runs)
            cand = bool(re.fullmatch(r"\d{5}", g[:NUM_END])) and not g[NUM_END:NAME_START].strip()
            if not cand and max(r[2] for r in runs) >= 11.5:              # an office heading, 12-point
                done = done or inside
                inside = join(runs) == "DISTRICT ATTORNEY"
                continue
            if not inside:
                continue
            if cand:
                if district is None or party is None:
                    raise ValueError("a candidate before its district or party heading")
                count[district][party] = count[district].get(party, 0) + 1
                continue
            heading = join(runs)                                          # compared only; never printed or stored
            if heading.upper() in PARTIES and len(heading) < 20:
                party = PARTIES[heading.upper()]
                continue
            m = re.fullmatch(r"DISTRICT (\d+)( \(unexpired\))? - (.+)", heading)
            if m and COUNTY_LIST.fullmatch(m.group(3)):
                district, party = m.group(1) + (" unexpired" if m.group(2) else ""), None
                if district in count:
                    raise ValueError("a district with two headings")
                count[district] = {}
        if done and not inside:
            break
    if not count:
        raise ValueError("no DISTRICT ATTORNEY section")
    out = {"districts": len(count), "one_candidate": 0, "one_party": 0, "more_parties": 0}
    for c in count.values():
        out["one_candidate" if sum(c.values()) == 1 else "one_party" if len(c) == 1 else "more_parties"] += 1
    return out


def get_book(extract_dir, cmap, say):
    """The book's state-office entries: from the federal loader's cached copy, else fetched into memory (never saved)."""
    cached = os.path.join(CACHE, "ok", "ok_2026_candidate_list_book.pdf")
    extract = os.path.join(extract_dir, "sl_ok_book.json")
    data, how, fetched = None, None, None
    if os.path.exists(cached):
        data, how = open(cached, "rb").read(), "the federal loader's cached copy"
        fetched = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat()
    else:
        try:
            data, how, fetched = net.get(fed.BOOK_URL), "fetched into memory", dt.date.today().isoformat()
        except Exception as e:  # noqa: BLE001
            say(f"    Oklahoma (state races): could not fetch the Candidate List Book ({type(e).__name__})")
    if data is None:
        if not os.path.exists(extract):
            raise SystemExit("Oklahoma (state races): the Candidate List Book could not be read")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Oklahoma (state races): using the saved extract of the Candidate List Book ({ex['fetched']})")
        return ex["rows"], ex["races"], ex["sha256"], ex["fetched"], "the saved extract", ex.get("district_attorneys")
    if data[:5] != b"%PDF-":
        raise SystemExit(f"Oklahoma (state races): {fed.BOOK_URL} did not return a PDF")
    rows, races = read_book(data, cmap)
    try:
        da = district_attorneys(data)
    except Exception as e:  # noqa: BLE001  the count is one sentence of the coverage note; the races do not wait on it
        say(f"    CHECK Oklahoma (local races): the book's district attorney section could not be counted ({type(e).__name__})")
        da = None
    sha = hashlib.sha256(data).hexdigest()
    del data
    os.makedirs(extract_dir, exist_ok=True)
    keep = [{k: r[k] for k in ("kind", "race_id", "party", "number", "name")} for r in rows]
    with open(extract, "w", encoding="utf-8") as fh:              # office, party, filing number and name only; counts for district attorneys
        json.dump({"url": fed.BOOK_URL, "sha256": sha, "fetched": fetched, "rows": keep, "races": races, "district_attorneys": da},
                  fh, indent=0)
    return rows, races, sha, fetched, how, da


# ---------- the November list ----------

def list_office(text, cmap):
    """(kind, race) for an office heading of the November list; None for an office another loader reads (Congress,
    county offices); a SystemExit for anything else."""
    h = re.sub(r"\s+", " ", text).strip().upper()
    if h in STATEWIDE:
        return race_of("SW", h)
    m = re.fullmatch(r"STATE (SENATOR|REPRESENTATIVE) - DISTRICT (\d+)( \(UNEXPIRED TERM\))?", h)
    if m:
        return race_of("SS" if m.group(1) == "SENATOR" else "SH", m.group(2), special=bool(m.group(3)))
    m = re.fullmatch(r"DISTRICT JUDGE - DISTRICT (\d+), OFFICE (\d+)", h)
    if m:
        return race_of("DJ", m.group(1), m.group(2))
    m = re.fullmatch(r"ASSOCIATE DISTRICT JUDGE - ([A-Z .']+) COUNTY(?:,? (?:- )?OFFICE (?:NO\. )?(\d+))?", h)
    if m:
        c = cmap.get(squash(m.group(1)))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county on the November list is not in the Census file ({m.group(1)})")
        return race_of("ADJ", county=c, office_no=m.group(2))
    if fed.FEDERAL_OFFICE.search(h) or h.startswith("COUNTY "):
        return None
    raise SystemExit(f"Oklahoma (state races): an office on the November list this loader does not know ({text!r})")


def november(page, cmap):
    """({race_id: race}, {race_id: [(name, party)]}, {race_id: [county GEOIDs]}, disagreeing races, retention headings)."""
    counties = re.findall(r"<option value=\"#(\d+)\">", page)
    parts = re.split(r"<A NAME=(\d+)>([^<]*)</A>", page)
    races, listed, retention, seen = {}, {}, set(), 0
    for k in range(1, len(parts), 3):
        num, county, body = parts[k], parts[k + 1].strip(), parts[k + 2]
        if num == "00":
            continue
        seen += 1
        c = cmap.get(squash(county))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county section of the November list is not in the Census file ({county})")
        sec = race = None
        for m in re.finditer(r"<TD WIDTH=(\d+)>(.*?)</TD>", body, re.S):
            width, t = m.group(1), fed.text(m.group(2))
            if width == "990":
                sec, race = t, None
            elif width == "980":
                race = None
                if sec in ("STATE OFFICERS", "LEGISLATIVE, DISTRICT AND COUNTY OFFICERS", "JUDICIAL OFFICERS"):
                    race = list_office(t, cmap)
                    if race:
                        races.setdefault(race["race_id"], race)
                        listed.setdefault(race["race_id"], {}).setdefault(c[0], [])
                elif sec == "JUDICIAL RETENTION":
                    retention.add(t.upper())
            elif width == "970" and race:
                if race["partisan"]:
                    name, _, label = t.rpartition(",")
                    label = label.strip().upper()
                    if not name or label not in PARTIES:
                        raise SystemExit(f"Oklahoma (state races): a candidate line for {race['race_id']} in {county} County is not read")
                    entry = (re.sub(r"\s+", " ", name).strip(), PARTIES[label])
                else:
                    entry = (re.sub(r"\s+", " ", t).strip(), NONPARTISAN)
                listed[race["race_id"]][c[0]].append(entry)
    if seen != len(counties) or seen != 77:
        raise SystemExit(f"Oklahoma (state races): the November list has {seen} county sections for {len(counties)} counties (77 expected)")
    cands, where, disagree = {}, {}, []
    for rid, by_county in listed.items():
        versions = {tuple(v) for v in by_county.values()}
        if len(versions) == 1:
            cands[rid] = list(versions.pop())
            where[rid] = sorted(by_county)
        else:
            disagree.append(rid)
    return races, cands, where, disagree, retention


LIST_TITLE = re.compile(r"<TITLE>\s*NOVEMBER / 2026\s+List of Elections\s*</TITLE>", re.I)


def november_page(local_dir, say):
    """(the page's text, the SHA-256 the state rows' source records, the SHA-256 of the bytes as fetched, the day
    fetched, how it was read). The federal loader's cached copy when it is under a week old; else this loader's own
    copy in ballot_cache/ok/local/ when that is; else fetched, checked by its title (the address is reused for every
    election) and kept there, so that a re-run downloads nothing. The page carries sections, offices, names and
    parties only; a copy in which any candidate cell looked like contact details would not be kept."""
    fed_copy = os.path.join(CACHE, "ok", "ok_2026_general_list.html")
    own_copy = os.path.join(local_dir, "ok_2026_general_list.html")

    def fresh(p):
        return os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400

    def from_disk(p, how):
        raw = open(p, "rb").read()
        page = open(p, encoding="utf-8").read() if p == fed_copy else raw.decode("utf-8", "replace")
        return page, hashlib.sha256(raw).hexdigest(), dt.date.fromtimestamp(os.path.getmtime(p)).isoformat(), how

    got = None
    if fresh(fed_copy):
        got = from_disk(fed_copy, "the federal loader's cached copy")
    elif fresh(own_copy):
        got = from_disk(own_copy, "this loader's cached copy")
    else:
        older = [(p, how) for p, how in ((fed_copy, "the federal loader's cached copy (not refreshed)"),
                                         (own_copy, "this loader's cached copy (not refreshed)")) if os.path.exists(p)]
        older.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
        try:
            raw = net.get(fed.LIST_URL, accept="text/html")
            page = raw.decode("utf-8", "replace")
            if not LIST_TITLE.search(page):
                if not older:
                    raise SystemExit("Oklahoma (state races): the List of Elections is not the November 2026 list")
                say("    Oklahoma (state races): the Board's List of Elections address no longer shows the November 2026 list; "
                    "using the cached copy")
                got = from_disk(*older[0])
            else:
                got = (page, hashlib.sha256(raw).hexdigest(), dt.date.today().isoformat(), "fetched and cached")
                cells = re.findall(r"<TD WIDTH=970>(.*?)</TD>", page, re.S)
                if any(contact_like(fed.text(c), True) for c in cells):
                    got = got[:3] + ("fetched into memory",)
                    say("    CHECK Oklahoma (local races): a candidate cell of the November list looks like contact details; the page was not cached")
                else:
                    os.makedirs(local_dir, exist_ok=True)
                    with open(own_copy + ".part", "wb") as fh:
                        fh.write(raw)
                    os.replace(own_copy + ".part", own_copy)
                time.sleep(1.0)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            if not older:
                raise
            say(f"    Oklahoma (state races): could not refresh the November list ({type(e).__name__}); using the cached copy")
            got = from_disk(*older[0])
    page, raw_sha, fetched, how = got
    if not LIST_TITLE.search(page):
        raise SystemExit("Oklahoma (state races): the List of Elections is not the November 2026 list")
    return page, hashlib.sha256(page.encode("utf-8")).hexdigest(), raw_sha, fetched, how


# ---------- the November list: county, city and town offices and fire protection district boards ----------

def shown_local(caps):
    """A name the list prints in capitals, in ordinary capitals as the state rows show them. A word the list itself
    prints in mixed case (NaRISSA, McCLENDON) keeps the list's own inner capitals (NaRissa, McClendon)."""
    caps = re.sub(r"\s+", " ", caps).strip()
    out = []
    for src, std in zip(caps.split(" "), proper(caps.upper()).split(" ")):
        if src == src.upper():
            out.append(std)
        else:
            out.append("".join(p.capitalize() if len(p) > 1 and p.isupper() else p
                               for p in re.findall(r"[A-Z][a-z]+|[A-Z]+(?![a-z])|[a-z]+|[^A-Za-z]+", src)))
    t = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), " ".join(out))
    return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)


def slug(text):
    """Lower-case letters and digits with hyphens between, accents folded: for ids only."""
    t = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def read_places(local_dir, cmap, say):
    """({squashed "name kind": [(place code, name, [county GEOIDs])]}, the same by the bare name, SHA-256, day fetched,
    rows read) for Oklahoma's incorporated cities and towns, from the Census Bureau's 2020 place codes file. The file
    has names, codes and counties only; it is kept whole in ballot_cache/ok/local/ and asked for once."""
    path = os.path.join(local_dir, "st40_ok_place2020.txt")
    try:
        net.download(PLACE_URL, path, 3650, say=say)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"Oklahoma (local races): the Census Bureau's place codes file could not be fetched ({type(e).__name__}); "
                         "nothing was changed. Re-run.")
    by_full = {squash(full): geoid for geoid, full in cmap.values()}
    exact, bare, n = {}, {}, 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        if fh.readline().rstrip("\r\n").split("|") != PLACE_HEAD:
            raise SystemExit("Oklahoma (local races): st40_ok_place2020.txt: the header is not the one this loader was checked against")
        for ln, line in enumerate(fh, start=2):
            if not line.strip():
                continue
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(PLACE_HEAD) or f[1] != FIPS or not re.fullmatch(r"\d{5}", f[2]):
                raise SystemExit(f"Oklahoma (local races): st40_ok_place2020.txt: line {ln} does not fit the header")
            n += 1
            if f[5] != "INCORPORATED PLACE":
                continue
            cids = [by_full.get(squash(c)) for c in f[8].split("~~~")]
            if not all(cids):
                raise SystemExit(f"Oklahoma (local races): st40_ok_place2020.txt: line {ln} names a county the county file does not have")
            rec = (f[2], f[4], sorted(cids))
            exact.setdefault(squash(f[4]), []).append(rec)
            bare.setdefault(squash(re.sub(r"\s+(city|town)$", "", f[4])), []).append(rec)
    return exact, bare, sha_of(path), mdate(path), n


def local_office(section, heading):
    """What one office heading of the list is, by its section: ("question",), ("county", kind, office, district,
    special), ("city", kind, office, district, special), ("fire", special) or ("unknown",)."""
    s = re.sub(r"\s+", " ", section).strip().upper()
    h = re.sub(r"\s+", " ", heading).strip().upper()
    if re.match(r"(PROPOSITION|QUESTION)\b", h):
        return ("question",)
    special = h.endswith(UNEXPIRED_MARK)
    if special:
        h = h[:-len(UNEXPIRED_MARK)]
    if s == LEG_SECTION:
        m = re.fullmatch(r"COUNTY COMMISSIONER DISTRICT NO\. (\d+)", h)
        if m:
            return ("county", "county_commissioner", "County Commissioner", str(int(m.group(1))), special)
        if h.startswith("COUNTY ") and h[7:] in COUNTY_OFFICES:
            return ("county",) + COUNTY_OFFICES[h[7:]] + (None, special)
        return ("unknown",)
    if re.fullmatch(r"(CITY|TOWN) OF .+", s):
        if h == "MAYOR":
            return ("city", "mayor", "Mayor", None, special)
        m = re.fullmatch(r"COUNCILMEMBER - (" + "|".join(sorted(COUNCIL_WORDS, key=len, reverse=True)) + r") (WARD|DISTRICT) (\w+)", h)
        if m:
            n = m.group(3)                                             # 4, 3A and II as printed; ONE as One
            n = n.title() if n.isalpha() and len(n) > 2 and not re.fullmatch(r"[IVX]+", n) else n
            return ("city", "council", COUNCIL_WORDS[m.group(1)], f"{m.group(2).title()} {n}", special)
        return ("unknown",)
    if re.search(r"\bFIRE\b", s) and re.fullmatch(r"BOARD MEMBER - MEMBER OF (THE )?BOARD OF DIRECTORS", h):
        return ("fire", special)
    return ("unknown",)


def november_local(page, cmap, places):
    """The local contests of the November list: {"races": [sl_races rows], "cands": [sl_candidates rows], "places":
    [sl_places rows], "gaps": [sl_gaps rows], "checks": [words], and the counts the report and the notes use}. A contest
    is one office heading under one county, city, town or district; the same heading under the same city or district in
    another county is the same contest, and its candidate lines there must be the same lines in the same order."""
    exact, bare = places
    name_of = {geoid: full for geoid, full in cmap.values()}
    seen, order = {}, []                # (section key, office heading) -> {county GEOID: [candidate lines]}, in the list's order
    twice, questions, section_counties = set(), set(), {}      # section_counties: every county that prints a city's or district's section
    lines = Counter()
    checks = []

    def check(words):
        if words not in checks:
            checks.append(words)

    parts = re.split(r"<A NAME=(\d+)>([^<]*)</A>", page)
    for k in range(1, len(parts), 3):
        num, county, body = parts[k], parts[k + 1].strip(), parts[k + 2]
        if num == "00":
            continue
        geoid = cmap[squash(county)][0]
        if int(geoid[2:]) != 2 * int(num) - 1:
            check(f"{county} County is numbered {num} on the list, which is not its place in the Census county codes ({geoid})")
        sec = key = None
        nth = Counter()
        for m in re.finditer(r"<TD WIDTH=(\d+)>(.*?)</TD>", body, re.S):
            width, t = m.group(1), fed.text(m.group(2))
            if width == "990":
                sec, key = re.sub(r"\s+", " ", t).strip().upper(), None
                if sec not in STATE_SECTIONS and sec != LEG_SECTION:
                    section_counties.setdefault(sec, set()).add(geoid)
            elif width == "980":
                key = None
                h = re.sub(r"\s+", " ", t).strip().upper()
                if sec is None or sec in STATE_SECTIONS or (sec == LEG_SECTION and not h.startswith("COUNTY ")):
                    continue                                          # the federal and state loaders' offices
                skey = f"COUNTY {geoid}" if sec == LEG_SECTION else sec
                if local_office(sec, h)[0] == "question":
                    nth[(skey, h)] += 1
                    questions.add((skey, h, nth[(skey, h)]))
                    key = "question"
                    continue
                key = (skey, sec, h)
                if key not in seen:
                    seen[key] = {}
                    order.append(key)
                if geoid in seen[key]:
                    twice.add(key)
                seen[key].setdefault(geoid, [])
            elif width == "970":
                lines["all"] += 1
                if key is None:
                    lines["state"] += 1
                elif key == "question":
                    lines["under a question"] += 1
                else:
                    lines["local"] += 1
                    seen[key][geoid].append(re.sub(r"\s+", " ", t).strip())
    if lines["under a question"]:
        check(f"{lines['under a question']} candidate lines are printed under a proposition; they are not read")

    races, cands, place_rows, gaps = [], [], {}, []
    stats = Counter()
    used_ids = set()

    def gap(scope, place_id, place, what, reason):
        gaps.append((STATE, scope, place_id, place, what, reason, fed.LIST_URL))

    for key in order:
        skey, sec, h = key
        by_county = seen[key]
        cids = sorted(by_county)
        kind = local_office(sec, h)
        what = shown_local(h)
        n_lines = sum(len(v) for v in by_county.values())

        # where it is
        if sec == LEG_SECTION:
            jid, jname, level, pk = cids[0], name_of[cids[0]], "county", cids[0]
            where = ("county", jid, jname)
        elif re.fullmatch(r"(CITY|TOWN) OF .+", sec):
            word, bare_name = sec.split(" OF ", 1)
            word = word.lower()
            hit = exact.get(squash(f"{bare_name} {word}"), [])
            if len(hit) != 1:
                hit = bare.get(squash(bare_name), [])
            src = SRC_PLACES
            if len(hit) == 1:
                pk, jname, census = hit[0][0], hit[0][1], hit[0][2]
                if not re.search(rf"\s{word}$", jname):
                    jname = f"{shown_local(bare_name)} {word}"            # the Bureau's code, the Board's kind word
                listed = section_counties[sec]
                if not listed <= set(census):
                    check(f"{jname}: the list files it under a county the Census place file does not name for it")
                place_counties = sorted(set(census) | listed)
            else:
                pk, jname, src = f"{min(section_counties[sec])[2:]}-{slug(bare_name)}-{word}", f"{shown_local(bare_name)} {word}", SRC_LOCAL
                place_counties = sorted(section_counties[sec])
                check(f"{jname}: not exactly one entry in the Census place file; filed under the county code and its name")
            jid, level = f"{STATE}-M-{pk}", "city"
            pk = f"M-{pk}"
            where = ("place", jid, jname)
            place_row = ("mcd", jid, jname, json.dumps(place_counties), src)
        elif kind[0] == "fire":
            pk = f"{min(section_counties[sec])[2:]}-{slug(sec)}"         # no official code: the first county that prints it, and its name
            jid, jname, level = f"{STATE}-X-{pk}", f"{shown_local(sec)} (fire protection district)", "other"
            pk = f"X-{pk}"
            where = ("place", jid, jname)
            place_row = ("special", jid, jname, json.dumps(sorted(section_counties[sec])), SRC_LOCAL)
        else:
            for g in cids:                                              # a section of a kind this loader does not know
                gap("county", g, name_of[g], f"{shown_local(sec)}: {what}", NOT_CHECKED)
            check(f"a section this loader does not know is not loaded: {sec} / {h} ({n_lines} candidate lines)")
            stats["contests not loaded"] += 1
            stats["lines not placed"] += n_lines
            continue
        if kind[0] == "unknown":
            gap(where[0], where[1], where[2], what, NOT_CHECKED)
            check(f"an office this loader does not know is not loaded: {jname} / {h} ({n_lines} candidate lines)")
            stats["contests not loaded"] += 1
            stats["lines not placed"] += n_lines
            continue

        # what it is
        if kind[0] == "fire":
            okind, office, district, special = "fire_board", "Member of the Board of Directors", None, kind[1]
        else:
            _, okind, office, district, special = kind
        rid = f"2026-{STATE}-{pk}-{okind.replace('_', '-')}" + (f"-{slug(district)}" if district else "") + ("-S" if special else "")
        title = office + (f", {'District ' + district if district.isdigit() else district}" if district else "")

        def leave_out(reason):
            gap("race", rid, jname, title, reason)
            check(f"{rid}: {reason}")
            stats["contests not loaded"] += 1
            stats["lines not placed"] += n_lines

        if rid in used_ids or key in twice:
            leave_out("The State Election Board's November list prints this contest twice under one county, so its candidates cannot be "
                      "told apart; it is not shown.")
            continue
        versions = {tuple(v) for v in by_county.values()}
        if len(versions) != 1:
            leave_out("The State Election Board's November list prints this contest under several counties and their lists of "
                      "candidates do not agree, so it is not shown.")
            continue
        printed = list(versions.pop())

        # who is in it
        labelled = [ln.rpartition(",")[2].strip().upper() in PARTIES and bool(ln.rpartition(",")[0].strip()) for ln in printed]
        if level == "county" and not all(labelled):
            leave_out("A candidate line of this contest on the State Election Board's November list does not end with a party, "
                      "so the contest is not shown.")
            continue
        if level != "county" and any(labelled) and not all(labelled):
            leave_out("Some candidate lines of this contest on the State Election Board's November list carry a party and some "
                      "do not, so the contest is not shown.")
            continue
        partisan = 1 if printed and all(labelled) else (1 if level == "county" else 0)
        entries = []
        for ln in printed:
            if partisan:
                name, _, label = ln.rpartition(",")
                party = PARTIES[label.strip().upper()]
                entries.append((re.sub(r"\s+", " ", name).strip(), party, party_code(party)))
            else:
                entries.append((ln, NONPARTISAN, NP_CODE))
        if any(not NAME_OK.fullmatch(n) or contact_like(n, True) for n, _p, _c in entries):
            leave_out("A candidate line of this contest on the State Election Board's November list does not read as a name, "
                      "so the contest is not shown.")
            continue
        names = [shown_local(n) for n, _p, _c in entries]
        if len(set(names)) != len(names):
            leave_out("The State Election Board's November list prints the same name twice in this contest, so it is not shown.")
            continue
        ranks = [PARTY_RANK.get(p, 0) for _n, p, _c in entries]
        ordered = bool(level == "county" and partisan and all(ranks) and all(a < b for a, b in zip(ranks, ranks[1:])))
        if level == "county" and entries and not ordered:
            check(f"{rid}: the list's order is not the order of the parties' drawing, or two candidates share a label; no ballot order stored")
        used_ids.add(rid)
        note = " ".join(x for x in (UNEXPIRED_NOTE if special else None, None if entries else NO_CANDIDATE) if x) or None
        races.append((rid, STATE, level, okind, office, jname, jid, json.dumps(cids), district, None, 1 if special else 0, partisan,
                      None, None, None, GENERAL, note))
        for i, (shown_name, (_n, party, code)) in enumerate(zip(names, entries), start=1):
            cands.append((rid, "general", GENERAL, shown_name, party, code, i if ordered else None, 0, 0, None, None, None, None,
                          SRC_LOCAL, None))
        if level != "county":
            place_rows[place_row[1]] = place_row
        stats["contests"] += 1
        stats["candidates"] += len(entries)
        stats["lines placed"] += n_lines
        stats["printed"] += len(by_county)
        stats["in several counties"] += 1 if len(by_county) > 1 else 0
        stats[f"level {level}"] += 1
        stats[f"kind {okind}"] += 1
        stats["special"] += 1 if special else 0
        stats["with ballot order"] += 1 if ordered else 0
    return {"races": races, "cands": cands, "places": list(place_rows.values()), "gaps": gaps, "checks": checks, "stats": stats,
            "lines": lines, "questions": len(questions),
            "counties": sorted({c for r in races for c in json.loads(r[7])}),
            "cities": sorted({r[5] for r in races if r[2] == "city"})}


# ---------- withdrawals and contests of candidacy ----------

def get_withdrawals(say):
    path = os.path.join(CACHE, "ok", "ok_2026_withdrawals.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
        try:
            wp = net.get(fed.WITHDRAWALS_URL, accept="text/html").decode("utf-8", "replace")
            return {"url": fed.WITHDRAWALS_URL, "modified": fed.modified(wp), "fetched": dt.date.today().isoformat(),
                    "rows": [dict(zip(("number", "name", "office", "date"), r)) for r in fed.table(wp, ("Number", "Name", "Office", "Date"))]}
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"    Oklahoma (state races): could not refresh the withdrawals page ({type(e).__name__}); using the federal loader's extract")
    wd = json.load(open(path, encoding="utf-8"))
    wd["fetched"] = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    return wd


def get_contests(extract_dir, say):
    """[{cause, case, office, hearing, ruling}] from the Board's contests page (names and rulings only)."""
    path = os.path.join(extract_dir, "sl_ok_contests.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
        try:
            cp = net.get(fed.CONTESTS_URL, accept="text/html").decode("utf-8", "replace")
            rows, cur = [], None
            for r in fed.table(cp, ("Cause", "Name", "Office", "Hearing")):
                r = (r + ["", "", "", ""])[:4]
                if r[0]:
                    cur = {"cause": r[0], "case": r[1], "office": r[2], "hearing": r[3], "ruling": ""}
                    rows.append(cur)
                elif cur and r[1]:
                    cur["ruling"] = (cur["ruling"] + " " + r[1]).strip()
            os.makedirs(extract_dir, exist_ok=True)
            json.dump({"url": fed.CONTESTS_URL, "modified": fed.modified(cp), "fetched": dt.date.today().isoformat(), "rows": rows},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(1.0)
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"    Oklahoma (state races): could not refresh the contests page ({type(e).__name__}); using the saved extract")
    return json.load(open(path, encoding="utf-8"))


def office_race(text, cmap):
    """The race a withdrawal's or contest's office names ("State Representative, District 21"); None for other offices."""
    t = re.sub(r"\s+", " ", text).strip()
    if t.upper() in STATEWIDE:
        return race_of("SW", t.upper())["race_id"]
    m = re.fullmatch(r"State (Senator|Representative),? District (\d+)( \(Unexpired(?: Term)?\))?", t, re.I)
    if m:
        return race_of("SS" if m.group(1).lower() == "senator" else "SH", m.group(2), special=bool(m.group(3)))["race_id"]
    m = re.fullmatch(r"District Judge,? District (\d+),? Office (\d+)", t, re.I)
    if m:
        return race_of("DJ", m.group(1), m.group(2))["race_id"]
    return None


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row} and {roster office: row}, the roster's date, and the roster's
    own spelling of each sitting member's name. Only id, name, party, chamber, district and office are selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices, forms = {}, {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Oklahoma (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for h in list(seats.values()) + list(offices.values()):
        for form in (h["full"], f"{h['first']} {h['last']}"):
            if form:
                forms[squash(form)] = form
    return seats, offices, as_of, forms


def counties(path=COUNTY_ZIP):
    """{squashed county name: (GEOID, "Adair County")} for Oklahoma from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[squash(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 77:
        raise SystemExit(f"Oklahoma (state races): the county file gives {len(out)} Oklahoma counties, not 77")
    return out


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ok"), local_dir=LOCAL_DIR):
    net.patient_lookups()
    cmap = counties()
    seats, offices, as_of, forms = roster()
    filers, book_races, b_sha, b_fetched, b_how, da = get_book(extract_dir, cmap, say)
    page, l_sha, l_raw_sha, l_fetched, l_how = november_page(local_dir, say)
    l_races, l_cands, l_where, disagree, retention = november(page, cmap)
    place_lists = read_places(local_dir, cmap, say)
    loc = november_local(page, cmap, place_lists[:2])
    wd = get_withdrawals(say)
    ct = get_contests(extract_dir, say)
    checks = []

    # who filed for each race the book lists (every legislative and statewide seat up this year; judges too)
    by_race = {}
    for f in filers:
        by_race.setdefault(f["race_id"], []).append(f)

    # withdrawals and strikes
    by_number = {f["number"]: f for f in filers}
    wd_state = []
    for w in wd["rows"]:
        rid = office_race(w["office"], cmap)
        if rid is None:
            if not fed.FEDERAL_OFFICE.search(w["office"]):
                checks.append(f"a withdrawal for an office this loader does not read ({w['office']})")
            continue
        f = by_number.get(int(w["number"]))
        if not f or f["race_id"] != rid or name_parts(w["name"])[1] not in fold(f["name"]).split():
            raise SystemExit(f"Oklahoma (state races): the withdrawal numbered {w['number']} ({w['office']}) matches no filer of that office in the book")
        f["withdrew"] = dt.datetime.strptime(w["date"], "%m/%d/%Y").strftime("%Y-%m-%d")
        wd_state.append(f)
    struck, contest_words = [], []
    for c in ct["rows"]:
        rid = office_race(c["office"], cmap)
        ruling = c["ruling"]
        respondent = c["case"].split(" v. ", 1)[1].strip() if " v. " in c["case"] else ""
        if re.search(r"stricken from (the )?ballot", ruling, re.I):
            if rid is None:
                raise SystemExit(f"Oklahoma (state races): a candidate for an office this loader does not read was stricken ({c['office']})")
            hit = [f for f in by_race.get(rid, []) if name_parts(respondent)[1] and name_parts(respondent)[1] in fold(f["name"]).split()]
            if len(hit) != 1:
                raise SystemExit(f"Oklahoma (state races): contest {c['cause']} strikes a candidate who is not one filer for {rid}")
            hit[0]["struck"] = c["hearing"] and dt.datetime.strptime(c["hearing"], "%m/%d/%Y").strftime("%Y-%m-%d") or "before the primary"
            struck.append(hit[0])
            contest_words.append(f"{c['cause']} ({rid}): stricken")
        elif re.search(r"retained on (the )?ballot|contest withdrawn|has withdrawn", ruling, re.I):
            contest_words.append(f"{c['cause']} ({rid or c['office']}): {'retained' if 'retained' in ruling.lower() else 'withdrawn'}")
        else:
            raise SystemExit(f"Oklahoma (state races): contest {c['cause']} has a ruling this loader does not read")

    def on_primary_ballot(f):
        return not (f.get("withdrew") and f["withdrew"] < PRIMARY) and not f.get("struck")

    # the November list against the book
    for rid in disagree:
        checks.append(f"{rid}: the counties' November lists disagree; left out of the November candidates")
    for rid in l_races:
        if rid not in by_race:
            raise SystemExit(f"Oklahoma (state races): {rid} is on the November list but nobody filed for it in the book")
    general, nominee = {}, {}
    for rid, cands in l_cands.items():
        rows = []
        for order, (name, party) in enumerate(cands, start=1):
            filed = [f for f in by_race[rid] if f["party"] == party]
            match = [f for f in filed if squash(f["name"]) == squash(name)] or \
                    [f for f in filed if name_parts(f["name"])[1] == name_parts(name)[1]]
            if len(match) != 1:
                raise SystemExit(f"Oklahoma (state races): a November candidate for {rid} ({party}) is not one {party} filer in the book")
            f = match[0]
            if f.get("struck") or f.get("withdrew"):
                raise SystemExit(f"Oklahoma (state races): a November candidate for {rid} withdrew or was stricken")
            if party in CODES:
                if (rid, party) in nominee:
                    raise SystemExit(f"Oklahoma (state races): two {party} candidates for {rid} on the November list")
                nominee[(rid, party)] = f["number"]
            rows.append((name, party, order, f))
        general[rid] = rows
        where_book = set(book_races[rid].get("counties") or [])
        if where_book and set(l_where.get(rid, [])) != where_book and l_races[rid]["level"] == "legislature":
            checks.append(f"{rid}: the November list carries it in {len(l_where.get(rid, []))} counties, the book names {len(where_book)}")

    # which races: every legislative and statewide seat in the book; courts only where on the November list
    race_info, skipped_courts = {}, Counter()
    for rid, fs in by_race.items():
        info = dict(book_races[rid])
        if rid in l_races and l_races[rid]["special"] != info["special"]:
            checks.append(f"{rid}: the book and the November list disagree on whether it is for the rest of a term")
        if info["level"] == "court" and rid not in l_races:
            on = [f for f in fs if on_primary_ballot(f)]
            if len(on) == 1:
                skipped_courts["one candidate (unopposed)"] += 1
            elif len(on) >= 3:
                skipped_courts["three or more filed (settled by a majority in June)"] += 1
            else:
                skipped_courts[f"{len(on)} candidates on the filings, not on the November list ({rid})"] += 1
            continue
        race_info[rid] = info

    # seat checks
    sen = sorted(int(r["district"]) for r in race_info.values() if r["office_kind"] == "state_senate" and not r["special"])
    hou = sorted(int(r["district"]) for r in race_info.values() if r["office_kind"] == "state_house" and not r["special"])
    if hou != list(range(1, 102)):
        checks.append(f"House districts in the book are not all 101 (missing {sorted(set(range(1, 102)) - set(hou))})")
    if sen != list(range(2, 49, 2)):
        checks.append(f"Senate districts in the book are {sen}, not the 24 even-numbered ones")
    specials = sorted(rid for rid, r in race_info.items() if r["special"])

    # holders and the sitting member; a race's note is its special mark, then its status, then its holder, then the rest
    holders = {}
    n_special, n_status, n_holder, n_extra = {}, {}, {}, {}
    for rid, r in race_info.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
        elif r["level"] == "statewide":
            n_holder[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
        holders[rid] = h
        if r["special"]:
            n_special[rid] = "An election for the rest of the term (the Board's lists: unexpired term)."
    sitting = {}
    for rid, h in holders.items():
        if not h:
            continue
        names = {f["name"] for f in by_race[rid] if on_primary_ballot(f) or f.get("withdrew")} | {n for n, _p, _o, _f in general.get(rid, [])}
        fit = {squash(n) for n in names if holder_fits(n, h)}
        if len(fit) == 1:
            sitting[rid] = (fit.pop(), h["id"])

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps).strip()
        if squash(caps) in forms:
            return forms[squash(caps)]
        t = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)

    def inc_of(rid, name):
        return rid in sitting and squash(name) == sitting[rid][0]

    # rows
    cand, status = [], {}
    fields = Counter()
    for rid, r in sorted(race_info.items()):
        fs = by_race[rid]
        on = [f for f in fs if on_primary_ballot(f)]
        pt = bool(r["partisan"])
        slots = len({f["party"] for f in on if f["party"] in CODES}) + len([f for f in on if f["party"] not in CODES]) if pt else len(on)
        listed = rid in general
        if listed:
            status[rid] = "november"
            for name, party, order, f in general[rid]:
                inc = inc_of(rid, name)
                cand.append((rid, "general", GENERAL, shown(name), party if pt else NONPARTISAN, party_code(party) if pt else NP_CODE, order,
                             1 if inc else 0, 0, None, None, None, sitting[rid][1] if inc else None, SRC_GENERAL, None))
            if slots < 2:
                checks.append(f"{rid}: on the November list, though the filings leave only {slots} party or candidate")
        elif len(on) == 1:
            status[rid] = "unopposed"
            f = on[0]
            inc = inc_of(rid, f["name"])
            cand.append((rid, "general", GENERAL, shown(f["name"]), f["party"] if pt else NONPARTISAN,
                         party_code(f["party"]) if pt else NP_CODE, None, 1 if inc else 0, 0, None, None, "unopposed",
                         sitting[rid][1] if inc else None, SRC_BOOK, UNOPPOSED))
            n_status[rid] = ("Not on the November 3 ballot: only one candidate remained for this seat once withdrawals and "
                             "contests of candidacy were settled.")
        elif pt and slots == 1 and len(on) >= 2:
            status[rid] = "primary"
            party = on[0]["party"]
            n_status[rid] = (f"Not on the November 3 ballot: every candidate filed as a {party}, so the party's June 16 primary (and "
                             f"the August 25 runoff, where no one had a majority) settled the seat. " + RESULTS_REFUSED)
        else:
            status[rid] = "missing"
            checks.append(f"{rid}: not on the November list, though the filings leave {slots} parties or candidates")
            n_status[rid] = "Not on the State Election Board's November 3 list; the filings do not say why."

        # primaries: a field is two or more of a party's candidates on its June 16 ballot (judges: three or more filed)
        groups = {}
        for f in on:                                    # withdrawn after the primary: still on its ballot
            if pt and f["party"] not in CODES:
                continue
            groups.setdefault(f["party"] if pt else NONPARTISAN, []).append(f)
        for party, field in groups.items():
            if len(field) < (2 if pt else 3):
                continue
            fields[r["office_kind"] if r["level"] != "statewide" else "statewide"] += 1
            key = f"primary-{CODES[party]}" if pt else "primary-NP"
            if listed and pt:
                pick = {nominee.get((rid, party))}
            elif listed:
                pick = {f["number"] for _n, _p, _o, f in general[rid]}
            else:
                pick = None
            for f in field:
                inc = inc_of(rid, f["name"])
                note = []
                if f.get("withdrew"):
                    note.append(f"Withdrew on {f['withdrew']}, after the June 16 primary.")
                if pick is None:
                    out = None
                elif f["number"] in pick:
                    out = "advanced"
                else:
                    out = "lost"
                if pt and listed and (rid, party) not in nominee:
                    note.append(f"The November list has no {party} candidate for this seat.")
                    out = None
                cand.append((rid, key, PRIMARY, shown(f["name"]), party, party_code(party) if pt else NP_CODE, None, 1 if inc else 0, 0,
                             None, None, out, sitting[rid][1] if inc else None, SRC_BOOK, " ".join(note) or None))
            if not pt and listed:
                n_extra.setdefault(rid, []).append("Three or more filed, so the June 16 ballot carried a nonpartisan primary; the two "
                                                   "on the November list went on.")

    # every party with candidates on the primary ballot of a November race has its nominee there, unless one withdrew after it
    for (rid, party) in sorted({(f["race_id"], f["party"]) for f in filers if f["party"] in CODES and on_primary_ballot(f)}):
        if status.get(rid) == "november" and (rid, party) not in nominee:
            late = [f for f in by_race[rid] if f["party"] == party and f.get("withdrew") and f["withdrew"] >= PRIMARY]
            if late:
                n_extra.setdefault(rid, []).append(
                    f"The November list has no {party} candidate: "
                    + " and ".join(f"{shown(f['name'])} ({party}) withdrew on {f['withdrew']}" for f in late) + ", after the June 16 primary.")
            else:
                checks.append(f"{rid}: {party} candidates were on the June 16 ballot but the November list has no {party} candidate")

    race_rows = []
    for rid, r in sorted(race_info.items()):
        h = holders[rid]
        cids = ",".join(r["counties"]) if r.get("counties") and r["level"] != "statewide" else None
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], cids,
                          r["district"], r["seat"], r["special"], r["partisan"], h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL,
                          " ".join([x for x in (n_special.get(rid), n_status.get(rid), n_holder.get(rid)) if x] + n_extra.get(rid, [])) or None))

    county_rows = [("county", geoid, full, json.dumps([geoid]), SRC_COUNTIES) for geoid, full in sorted(cmap.values())]
    wd_before = [f for f in wd_state if f["withdrew"] < PRIMARY]
    wd_after = [f for f in wd_state if f["withdrew"] >= PRIMARY]
    n_gen = sum(1 for c in cand if c[1] == "general" and c[11] != "unopposed")
    n_state_filers = sum(1 for f in filers if f["race_id"] in race_info)

    # ---- the local rows: places, notes, gaps and their sources
    clash = {r[0] for r in race_rows} & {r[0] for r in loc["races"]}
    if clash:
        raise SystemExit(f"Oklahoma (local races): a local race id is also a state race's ({sorted(clash)[0]}); nothing was changed")
    ls, lines = loc["stats"], loc["lines"]
    place_rows = county_rows + sorted(loc["places"])
    _, _, p_sha, p_fetched, p_rows = place_lists

    def and_list(items):
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

    cities = [re.sub(r"\s+(city|town)$", "", n) for n in loc["cities"]]
    calendar = ("On November 3, 2026 every Oklahoma county elects a county assessor, a county treasurer and the county commissioners "
                "for Districts 1 and 3, by party; the county clerk, court clerk, sheriff and District 2 commissioner are elected in "
                "2028. Fire protection districts elect board members each November, without parties"
                + (f", and {and_list(cities)} {'has' if len(cities) == 1 else 'have'} city contests on this ballot. Most other "
                   if cities else ". Most ")
                + "cities and towns elect in April of odd-numbered years (a city with its own charter may choose another date), and "
                  "school boards were elected on February 10 and April 7, 2026.")
    if da and not da["more_parties"]:
        da_words = (f"; that is why no district attorney appears (of the {da['districts']} offices, {da['one_candidate']} had one "
                    f"candidate when filing closed and {da['one_party']} had candidates of one party only)")
    elif da:
        da_words = (f"; no district attorney is on the list, though {da['more_parties']} of the {da['districts']} offices drew "
                    "candidates of more than one party")
        loc["checks"].append(f"{da['more_parties']} district attorney offices drew candidates of more than one party, yet none is on the November list")
    else:
        da_words = "; no district attorney is on the list"
    coverage = ("From the State Election Board's November 3 list, read county by county for all 77 counties: every contest it prints "
                f"for a county office, a city or town office or a fire protection district board ({ls['contests']} contests, "
                f"{ls['candidates']} candidates, in {len(loc['counties'])} counties). Oklahoma prints only contested races: an office "
                "with one candidate left, or one settled in the June 16 primary or the August 25 runoff, is not on the ballot and is "
                f"not shown{da_words}. Not loaded: the {loc['questions']} local propositions and questions on the list.")
    note_rows = [
        (STATE, "local_calendar", calendar,
         "19 O.S. 131 (county officers) and 901.5 (fire protection districts); 11 O.S. 16-102 and 16-103 (cities and towns); "
         "Oklahoma State Election Board, 2026 Voter Information Calendar (school board election dates)", CALENDAR_URL),
        (STATE, "local_coverage", coverage,
         "Oklahoma State Election Board, NOVEMBER / 2026 List of Elections, and Candidates for Office 2026 (who filed for district "
         "attorney); 26 O.S. 6-102 (an unopposed candidate is not printed on the ballot)", fed.LIST_URL),
    ]
    gap_rows = loc["gaps"] + [
        (STATE, "state", STATE, NAME, "county officers elected without a November contest",
         "Oklahoma leaves an office off the ballot when one candidate is left or a primary or runoff settled it, so those county "
         "officers are not on the State Election Board's November list. Who filed and who won is published on the Board's filing "
         "portal and results site, which refuse scripts, so they are not shown here.", FILING_URL)]
    made = re.search(r"created on:\s*(\d{1,2})/(\d{1,2})/(\d{4})", page, re.I)
    l_published = f"{made.group(3)}-{int(made.group(1)):02d}-{int(made.group(2)):02d}" if made else ""
    kinds = ", ".join(f"{k[5:].replace('_', ' ')} {v}" for k, v in sorted(ls.items()) if k.startswith("kind "))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-OK-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'OK'")
        con.execute("DELETE FROM sl_sources WHERE state = 'OK'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ok-%' OR (kind = 'county' AND id GLOB '40[0-9][0-9][0-9]')")
        con.execute("DELETE FROM sl_gaps WHERE state = 'OK'")
        con.execute("DELETE FROM sl_notes WHERE state = 'OK'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + loc["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + loc["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT OR REPLACE INTO sl_gaps VALUES (?,?,?,?,?,?,?)", gap_rows)
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", note_rows)
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Oklahoma State Election Board",
             "NOVEMBER / 2026 List of Elections (November 3, 2026 General Election), county by county: state officers, "
             "legislative officers and judicial officers", fed.LIST_URL, "", l_fetched, l_sha, n_gen,
             f"Read for all 77 counties (from {l_how}); every county's list of each race agreed"
             + (f", except {', '.join(disagree)} (left out)" if disagree else "") + ". Names, parties and offices only. The list's "
             "order is kept as the ballot order (for partisan offices the Board's drawing: Republican, Democrat, Libertarian, then independents; for judges the list's own order). Names "
             "are printed in capitals and shown in ordinary capitals (a sitting member as the roster spells the name). The "
             f"list carries {len(retention)} judicial retention questions without the judges' names; they are not loaded."),
            (SRC_BOOK, STATE, "official candidate list", "Oklahoma State Election Board",
             "Candidates for Office 2026, filed April 1-3, 2026 (2026 Candidate List Book, compiled as of 5:00 p.m. April 3, "
             "2026): state officers, State Senator, State Representative, District Judge and Associate District Judge",
             fed.BOOK_URL, "2026-04-03", b_fetched, b_sha, n_state_filers,
             f"Read from {b_how}: the filing number and name columns only, by character position; the city column beside each "
             "name is never read. Who filed for each seat and who was on each party's June 16 primary ballot (less withdrawals "
             "and strikes). A seat with one candidate left is stored with that candidate marked unopposed; a seat only one "
             "party filed for was settled in its primary. Votes not loaded: the June 16 primary and August 25 runoff results "
             f"are published only on the Board's results site ({fed.RESULTS_URL}), which refuses scripts (403 Forbidden)."),
            (SRC_WD, STATE, "official candidate list", "Oklahoma State Election Board", "2026 Candidate Withdrawals", fed.WITHDRAWALS_URL,
             wd.get("modified", ""), wd.get("fetched", ""), "", len(wd_state),
             f"State-office withdrawals matched to the book by filing number: {len(wd_before)} before the June 16 primary (left off "
             f"its ballot), {len(wd_after)} after it (kept in the primary field, with a note). Columns kept: Number, Name, Office, Date."),
            (SRC_CONTESTS, STATE, "official candidate list", "Oklahoma State Election Board", "2026 Contests of Candidacy", fed.CONTESTS_URL,
             ct.get("modified", ""), ct.get("fetched", ""), "", len(ct["rows"]),
             "Rulings read: " + ("; ".join(contest_words) or "none") + ". A candidate stricken from the ballot is left off the primary."),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
             "Oklahoma legislators and statewide officials, as loaded into state_ok.sqlite", "https://github.com/openstates/people",
             as_of, as_of, "", len(seats) + len(offices),
             "Today's holder of each seat and office. The roster carries the Governor, Lieutenant Governor and Attorney General "
             "only among statewide offices. A candidate is marked as the sitting member only when the name fits the holder of that "
             "seat and no other candidate in the race fits."),
            (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
             "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
             sha_of(COUNTY_ZIP), len(county_rows), "Oklahoma's 77 counties: names and GEOIDs only; a race's county_ids are the "
             "counties the book names for its district."),
            (SRC_LOCAL, STATE, "official candidate list", "Oklahoma State Election Board",
             "NOVEMBER / 2026 List of Elections (November 3, 2026 General Election), county by county: county officers, city and "
             "town officers and fire protection district boards", fed.LIST_URL, l_published, l_fetched, l_raw_sha, ls["candidates"],
             f"Read for all 77 counties (from {l_how}): under each county, the county offices in the list's legislative, district "
             f"and county section and every city, town and fire district section. {ls['lines placed']} candidate lines in "
             f"{ls['printed']} printed contests gave {ls['candidates']} candidates in {ls['contests']} contests ({kinds}); "
             f"{ls['in several counties']} contests are printed under more than one county, and every county's copy agreed. Read: "
             "the section, the office and the candidate line (a name, and a party on county offices); the page has no contact "
             "columns. Names are printed in capitals and shown in ordinary capitals. County offices carry the ballot order: "
             "parties in the order of the Board's drawing, then independents, as 26 O.S. 6-106 sets it and the list follows. For "
             "city, town and fire district offices the list does not say that its order is the ballot's, so none is given. Only "
             f"contested races are printed. Not loaded: {loc['questions']} local propositions and questions"
             + (f"; {ls['contests not loaded']} contests this loader could not read (see the gaps)" if ls["contests not loaded"] else "")
             + ". The SHA-256 is of the page's bytes as fetched."),
            (SRC_PLACES, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Oklahoma (st40_ok_place2020.txt)",
             PLACE_URL, "", p_fetched, p_sha, p_rows,
             "Names and FIPS place codes of Oklahoma's incorporated cities and towns, and the counties each lies in. A city or "
             "town on the Board's November list is matched by its name and kind word to exactly one entry and named as the "
             f"Bureau writes it; {sum(1 for p in loc['places'] if p[4] == SRC_PLACES)} are used. Read: name, code, type and "
             "counties; the file has no contact columns and is kept whole."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # the report: counts only
    grp = lambda rid: race_info[rid]["office_kind"] if race_info[rid]["level"] == "legislature" else race_info[rid]["level"]
    by = Counter(grp(rid) for rid in race_info)
    st = {k: Counter(grp(rid) for rid, s in status.items() if s == k) for k in ("november", "unopposed", "primary", "missing")}
    gen_by = Counter(grp(c[0]) for c in cand if c[1] == "general" and c[11] != "unopposed")
    inc_by = Counter(grp(rid) for rid in sitting)
    sp = Counter(race_info[rid]["office_kind"] for rid in specials)
    say(f"    Oklahoma (state races): {by['state_senate']} Senate races ({sp['state_senate']} for the rest of a term), {by['state_house']} "
        f"House races ({sp['state_house']} for the rest of a term), {by['statewide']} statewide offices, {by['court']} judges' races on the November list; on the November ballot: "
        f"Senate {st['november']['state_senate']}, House {st['november']['state_house']}, statewide {st['november']['statewide']}, "
        f"judges {st['november']['court']} ({len([c for c in cand if c[1] == 'general' and c[11] != 'unopposed'])} candidates: Senate "
        f"{gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}, judges {gen_by['court']}); "
        f"unopposed at filing: Senate {st['unopposed']['state_senate']}, House {st['unopposed']['state_house']}, statewide "
        f"{st['unopposed']['statewide']}; settled in a one-party primary: Senate {st['primary']['state_senate']}, House "
        f"{st['primary']['state_house']}, statewide {st['primary']['statewide']}; sitting member in the race: Senate "
        f"{inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}; primary fields: Senate "
        f"{fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}, judges {fields['district_court']}; "
        f"withdrawals {len(wd_before)} before and {len(wd_after)} after the primary, {len(struck)} stricken")
    on_ballot = sum(1 for f in filers if f["race_id"] in race_info and on_primary_ballot(f))
    off = sum(1 for f in filers if f["race_id"] in race_info and not on_primary_ballot(f))
    say(f"    Oklahoma (state races): filings reconciled: {n_state_filers} filed for the races loaded = {on_ballot} on the June 16 "
        f"ballot + {off} withdrawn before it or stricken"
        + ("" if on_ballot + off == n_state_filers else "  (DOES NOT ADD UP)"))
    if skipped_courts:
        say(f"    Oklahoma (state races): judges' seats in the book not on the November list (not loaded): "
            + ", ".join(f"{v} {k}" for k, v in sorted(skipped_courts.items())))
    flagged = sum(1 for r in race_rows if r[16] and contact_like(r[16], True))
    if flagged:
        checks.append(f"{flagged} race notes name a web site (the Board's results site): ballot/check_local.py fails on them and the "
                      "page's privacy check leaves such notes out. They are written unchanged; rewording them (RESULTS_REFUSED in "
                      "this file) would change rows already loaded, so that is left for John to decide")
    for c in checks:
        say(f"    CHECK Oklahoma (state races): {c}")
    say(f"    Oklahoma (local races): {ls['contests']} contests, {ls['candidates']} candidates on the November list: county "
        f"{ls['level county']}, city and town {ls['level city']}, fire protection district boards {ls['level other']} ({kinds}); "
        f"{ls['special']} for the rest of a term; in {len(loc['counties'])} of 77 counties; ballot order kept for "
        f"{ls['with ballot order']} county contests; {len(loc['places'])} cities and districts, {len(gap_rows)} gap(s) written")
    placed = ls["lines placed"] + ls["lines not placed"]
    say(f"    Oklahoma (local races): reconciled: the list's {lines['all']:,} candidate lines = {lines['state']:,} under federal, state, "
        f"legislative and judicial offices + {lines['local']} under local offices"
        + (f" + {lines['under a question']} under propositions" if lines["under a question"] else "")
        + f"; of the local lines {ls['lines placed']} in {ls['printed']} printed contests gave {ls['candidates']} candidates in "
        f"{ls['contests']} contests ({ls['in several counties']} printed under more than one county, every copy agreeing), "
        f"{ls['lines not placed']} not placed; {loc['questions']} local propositions and questions not loaded"
        + ("" if placed == lines["local"] and lines["state"] + lines["local"] + lines["under a question"] == lines["all"] else "  (DOES NOT ADD UP)"))
    for c in loc["checks"]:
        say(f"    CHECK Oklahoma (local races): {c}")
    return len(cand) + len(loc["cands"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ok.py <database file>")
    load(sys.argv[1])
