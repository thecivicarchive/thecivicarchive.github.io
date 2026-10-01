"""
ballot/state_local_il.py - Illinois's state races on the November 3, 2026 ballot: Governor and Lieutenant Governor (one
ticket), Attorney General, Secretary of State, Comptroller and Treasurer; the 39 State Senate seats on this year's ballot
(Illinois senators serve terms of four, four and two years in each ten-year cycle, so about two thirds of the 59 seats
are up in 2026); all 118 seats of the House of Representatives; and the Appellate Court seats on the State Board's list
(vacancies, elected by party, and retention questions). Each party's March 17 primary field comes with its official votes.

Sources, all the Illinois State Board of Elections' own (the same files the federal loader, ballot/lists/il.py, reads):
  - The Website Candidate List for the General Election of November 3, 2026 (the Candidate List page's "Print This
    List" PDF, every office, "All Candidates as of" the moment it is printed). Office headings are set in a larger type;
    under each, one row per candidate: party (left column), name (middle column), filing date and time (right column).
    Candidates who filed by petition have their address on the rows beneath, and the Board's status ("REMOVED
    7/21/2026", "WITHDRAWN ...") is printed in the right column of those rows. For Governor, the running mate for
    Lieutenant Governor has a row of their own under the candidate for Governor, with no party.
  - The Official Canvass of the March 17, 2026 General Primary (2026GPOfficialVote.pdf, "Candidate Totals" on the
    Downloadable Vote Totals page): per office and district, a summary (the (Won) mark, name in capitals, party code,
    votes, share of the party's vote, W-I for a declared write-in; a running mate in brackets) and county tables whose
    rows must add up to the summary. These county rows also give each district's counties.
  - The Board's Election Results pages for the primary (ElectionVoteTotals.aspx: Federal / Statewide, Senate, District
    All and Judicial), from which only candidate, party and total votes are kept, to check every canvass name and total.
Holders come from the Open States roster in state_il.sqlite (legislators with is_current = 1; the officials table for
the Governor and the Attorney General; the roster does not carry the Secretary of State, the Comptroller or the
Treasurer). County codes come from the Census Bureau's county file (states_cache/census/cb_2024_us_county_500k.zip).

Privacy: from the candidate list only the office headings, the party and name cells of a candidate's row, and the
status word in the right-hand column are ever turned into text; an address row's middle column (street, city, ZIP, or
"Redaction Requested") is never joined, read or printed, and the filing date is matched, not kept. The PDF is read in
memory and never saved by this loader; only those cells go to ballot_cache/il/sl_il_general_list.json with the PDF's
SHA-256. When the Board's site cannot be reached, the federal loader's copy of the same list is read the same way.

A note on reading the list: pdftext.page_runs keeps the font across q/Q, but the PDF format saves and restores it
there, and this list selects a font inside q...Q (the "All Candidates as of" line) and then draws candidate rows with
the font restored by Q. Read with pdftext's own runs those rows come out as nonsense in the heading font (page 4: a
Governor ticket). page_runs() below is pdftext's with the text state saved and restored by q and Q.

The county and local part (a narrow first pass; John, 2026-09-30)
-----------------------------------------------------------------
Illinois has no statewide list of county candidates: each of its 108 election authorities (102 counties and six city
boards of election commissioners) publishes its own. This pass loads what the State Board's own list carries below the
state level and what two election authorities that answer scripts publish, and says for every other county, in
sl_gaps, that its list is not loaded yet.

  - The State Board's list (the same cached cells as above, nothing new downloaded): the Regional Superintendents of
    Schools of the 24 multi-county regions and the judges of the circuit courts (vacancies, elected by party; retention
    questions, nonpartisan). A regional superintendent is filed under level "other" with one "special" place per
    region: a regional office of education is not a school district but an office serving every district of its
    counties (Nebraska's educational service units are filed the same way). Circuit judges stay under level "court".
    The counties of each region, each vacancy's own words ("To fill the vacancy of the Hon. ...") and the counties
    each contest reaches come from the State Board's Official Canvass of the March primary (headings and county
    tables only; no local primary vote is loaded); the counties of each judicial circuit, for the retention questions,
    from Section 1 of the Circuit Courts Act (705 ILCS 35/1) on the General Assembly's site.
  - The Cook County Clerk's contest list for November 3, 2026 (JSON; ballot numbers; no contact fields at all): the
    county's own offices (board president, clerk, sheriff, treasurer, assessor, the 17 commissioners, the Board of
    Review), the Metropolitan Water Reclamation District, suburban sanitary districts, and the regional
    superintendents of three neighbouring one-county regions that parts of Cook County vote on. It is read twice, whole
    and party by party, and the two readings are compared line for line; a line that reads "No Candidate" is the
    Clerk's way of saying nobody filed, and is counted, not stored.
  - The Chicago Board of Election Commissioners' "Candidate Filings in Ballot Order" (a PDF linked from its Candidates
    page; ballot numbers, candidate, party, status; no contact columns): the Chicago Board of Education, and a second
    reading of every Cook County contest that reaches the city.
  - The names in the State Board's list of election jurisdictions (which cities have their own board of election
    commissioners), for the reasons given in sl_gaps.

Only allowed cells are ever kept: contest headings, names, party, ballot number, status. The two local lists are cut
down to those cells in memory and kept as JSON in ballot_cache/il/local/ (never the PDF itself); a kept cell that
reads like contact details is blanked and counted, never printed. Ballot questions are not loaded.

    python -m ballot.state_local_il <path to a test database> [--refresh]
"""

import collections
import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import zipfile
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit, urlunsplit

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ballot.pdftext as P  # noqa: E402
from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import il as IL  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "IL", "17"
GENERAL, PRIMARY = "2026-11-03", "2026-03-17"
ROSTER = os.path.join(HERE, "state_il.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
RESULTS_BASE = "https://www.elections.il.gov/ElectionOperations/ElectionVoteTotals.aspx?ID=Z2J%2fvYpKX8w%3d&OfficeType="
RESULT_PAGES = {"Federal / Statewide": "LpWf6lpbWOfBN3kEuxRi3A%3d%3d", "Senate": "XmLrbPr2rU0jTLF%2f7%2fJHNA%3d%3d",
                "District All": "TPsWaFcg2f%2bZHFrYI%2b6FR0aY47e3tS2y", "Judicial": "OIPn0DmJsHWCRPQwcCA4%2bK%2bzeOSGzX4E"}
SRC_LIST, SRC_CANVASS, SRC_RESULTS = "il-sbe-2026-state-general-list", "il-sbe-2026-state-primary-canvass", "il-sbe-2026-state-primary-results"
SRC_ROSTER, SRC_COUNTY = "il-openstates-roster", "il-census-counties"
COUNTIES = 102

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0,
  partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT,
  party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL,
  outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT,
  fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

# The statewide offices: list heading / canvass heading / results label -> (race suffix, office_kind, office, roster officials.office)
STATEWIDE = {"GOVERNOR AND LIEUTENANT GOVERNOR": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),
             "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
             "SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State", None),
             "COMPTROLLER": ("COMP", "comptroller", "Comptroller", None),
             "TREASURER": ("TREAS", "state_treasurer", "Treasurer", None)}
CANVASS_SENATE, CANVASS_HOUSE, CANVASS_APPELLATE = "STATE SENATOR", "REPRESENTATIVE IN THE GENERAL ASSEMBLY", "JUDGE OF THE APPELLATE COURT"
PARTY_WORD = {"DEM": "Democratic", "REP": "Republican"}
ORD = r"(\d{1,3})(?:ST|ND|RD|TH)"
L_SENATE, L_HOUSE = re.compile(rf"^{ORD} SENATE$"), re.compile(rf"^{ORD} REPRESENTATIVE$")
L_COURT = re.compile(rf"^{ORD} (APPELLATE|SUPREME) - (?:(RETAIN) (.+)|(.+) VACANCY)$")
L_FEDERAL = re.compile(rf"^(UNITED STATES SENATOR|{ORD} CONGRESS)$")
L_LOCAL = re.compile(r"CIRCUIT|SUPERINTENDENT|SUPT\.?|SUP OF SCHOOLS|SUPERENTENDENT")
DATETIME = re.compile(r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d\d ?[AP]M$")
STATUS = re.compile(r"\b(REMOVED|WITHDRAWN|DISQUALIFIED)\b")
NAME_PART = re.compile(r"^[A-Z][A-Za-z .,'\"()\[\]-]*$")
NOT_A_NAME = re.compile(r"\d|@|www|\.com|\.org|\.net|\bbox\b|\bp\.?\s?o\.?\b|\bsuite\b|\bste\b", re.I)

ONES = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9,
        "TENTH": 10, "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14, "FIFTEENTH": 15, "SIXTEENTH": 16,
        "SEVENTEENTH": 17, "EIGHTEENTH": 18, "NINETEENTH": 19, "TWENTIETH": 20, "THIRTIETH": 30, "FORTIETH": 40, "FIFTIETH": 50,
        "SIXTIETH": 60, "SEVENTIETH": 70, "EIGHTIETH": 80, "NINETIETH": 90, "HUNDREDTH": 100}
TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50, "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90}
SMALL = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9}
ORDINAL_WORD = {v: k.title() for k, v in ONES.items() if v <= 5}

GOV_NOTE = "The Governor and Lieutenant Governor are elected together, one ticket to a party."
SENATE_NOTE = ("Illinois senators serve terms of four, four and two years in each ten-year cycle, so about two thirds of the "
               "Senate's 59 seats are on the ballot in 2026; this is one of the 39 districts on the State Board's list and in its "
               "March primary.")
RETAIN_NOTE = ("A retention question: voters answer yes or no on keeping the judge, who needs three fifths of the votes cast on "
               "the question; no one runs against the judge. Nonpartisan.")
NO_ROSTER = "The Open States roster does not carry this office, so no holder is shown."
CAPS_NOTE = IL.CAPS
WRITE_IN_NOTE = IL.WRITE_IN


def ordinal_number(words):
    """FIFTY-NINTH -> 59; ONE HUNDRED EIGHTEENTH -> 118; None when the words are not an ordinal."""
    ws = words.replace("-", " ").split()
    total = 0
    if len(ws) == 2 and ws[0] in SMALL and ws[1] == "HUNDREDTH":
        return 100 * SMALL[ws[0]]
    if len(ws) >= 2 and ws[0] in SMALL and ws[1] == "HUNDRED":
        total, ws = 100 * SMALL[ws[0]], ws[2:]
        if ws and ws[0] == "AND":
            ws = ws[1:]
    if not ws:
        return None
    if len(ws) == 1 and ws[0] in ONES:
        return total + ONES[ws[0]]
    if len(ws) == 2 and ws[0] in TENS and ws[1] in ONES and ONES[ws[1]] < 10:
        return total + TENS[ws[0]] + ONES[ws[1]]
    return None


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def family_key(name):
    """The letters of a family name as the race id carries it: McDADE -> MCDADE; BARBERIS, JR. -> BARBERIS."""
    name = re.sub(r",?\s+(JR|SR|II|III|IV)\.?$", "", name.strip(), flags=re.I)
    return re.sub(r"[^A-Z]", "", fold(name.split()[-1] if " " in name and not name.isupper() else name).upper())


# ---------------------------------------------------------------------------------------------- reading a PDF's text

def page_runs(pdf, page, res):
    """pdftext.page_runs with the text state (font, size, spacing) saved by q and restored by Q, as the PDF format has it."""
    fonts, runs = {}, []
    fres = pdf.get((pdf.get(res) or {}).get("Font")) or {}
    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, P.Ref))
    st = {"ctm": [1, 0, 0, 1, 0, 0], "font": None, "size": 1.0, "tc": 0.0, "tw": 0.0, "th": 1.0, "tl": 0.0, "rise": 0.0}
    saved = []
    tm = tlm = [1, 0, 0, 1, 0, 0]

    def show(s):
        nonlocal tm
        font, size, th = st["font"], st["size"], st["th"]
        if font is None:
            return
        text, codes = font.decode(s if isinstance(s, (bytes, bytearray)) else b"")
        trm = P._mul([size * th, 0, 0, size, 0, st["rise"]], P._mul(tm, st["ctm"]))
        adv = 0.0
        for code in codes:
            adv += (font.width(code) * size + st["tc"] + (st["tw"] if (not font.two and code == 32) else 0)) * th
        x0, y0 = trm[4], trm[5]
        tm = P._mul([1, 0, 0, 1, adv, 0], tm)
        x1 = P._mul(P._mul([size * th, 0, 0, size, 0, st["rise"]], P._mul(tm, st["ctm"])), [1, 0, 0, 1, 0, 0])[4]
        if text.strip():
            runs.append((x0, y0, abs(trm[3]) or size, text, x1))

    for op, a in P._ops(data):
        if op == "q":
            saved.append(dict(st, ctm=st["ctm"][:]))
        elif op == "Q":
            st = saved.pop() if saved else dict(st, ctm=[1, 0, 0, 1, 0, 0])
        elif op == "cm" and len(a) == 6:
            st["ctm"] = P._mul([float(x) for x in a], st["ctm"])
        elif op == "BT":
            tm = tlm = [1, 0, 0, 1, 0, 0]
        elif op == "Tf" and len(a) == 2:
            name = str(a[0])
            if name not in fonts:
                fonts[name] = P.Font(pdf, fres.get(name))
            st["font"], st["size"] = fonts[name], float(a[1])
        elif op == "Tc" and a:
            st["tc"] = float(a[0])
        elif op == "Tw" and a:
            st["tw"] = float(a[0])
        elif op == "Tz" and a:
            st["th"] = float(a[0]) / 100
        elif op == "TL" and a:
            st["tl"] = float(a[0])
        elif op == "Ts" and a:
            st["rise"] = float(a[0])
        elif op in ("Td", "TD") and len(a) == 2:
            tx, ty = float(a[0]), float(a[1])
            if op == "TD":
                st["tl"] = -ty
            tlm = P._mul([1, 0, 0, 1, tx, ty], tlm)
            tm = tlm
        elif op == "Tm" and len(a) == 6:
            tm = tlm = [float(x) for x in a]
        elif op == "T*":
            tlm = P._mul([1, 0, 0, 1, 0, -st["tl"]], tlm)
            tm = tlm
        elif op == "Tj" and a:
            show(a[-1])
        elif op in ("'", '"') and a:
            tlm = P._mul([1, 0, 0, 1, 0, -st["tl"]], tlm)
            tm = tlm
            if op == '"' and len(a) == 3:
                st["tw"], st["tc"] = float(a[0]), float(a[1])
            show(a[-1])
        elif op == "TJ" and a and isinstance(a[-1], list):
            for item in a[-1]:
                if isinstance(item, (bytes, bytearray)):
                    show(item)
                elif isinstance(item, (int, float)):
                    tm = P._mul([1, 0, 0, 1, -float(item) / 1000.0 * st["size"] * st["th"], 0], tm)
    return runs


def rows(pdf, page, res):
    """A page's runs grouped into printed rows, top to bottom: [(y, [runs])] (as pdftext.rows)."""
    out = []
    for r in sorted(page_runs(pdf, page, res), key=lambda r: (-round(r[1], 1), r[0])):
        if out and abs(out[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return out


# ------------------------------------------------------------------------------------------------ the candidate list

def read_list(data):
    """The candidate list's office headings and, under each, each candidate's party, name and status: nothing else is
    turned into text. {"asof", "election", "offices": [{"heading", "cands": [{"party", "name", "status"}]}], "odd"}."""
    pdf = P.PDF(data)
    head, offices, odd = [], [], {"name rows without a date": 0, "rows with a party and no name": 0, "status with no candidate": 0}
    cur, cur_y, cur_page = None, None, None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for y, rs in rows(pdf, page, res):
            if y >= 685:                         # the page head: the Board's name, the print time, the list's title
                if n == 1:
                    head.append(P.join(rs))
                continue
            if y < 40:                           # the page number
                continue
            if min(round(r[2], 1) for r in rs) >= 9.5:          # an office heading (larger type)
                t = P.join(rs)
                if cur is not None and cur_page == n and not cur["cands"] and 0 < cur_y - y <= 16:
                    cur["heading"] += " " + t    # a long heading runs on to the next line
                else:
                    cur = {"heading": t, "cands": []}
                    offices.append(cur)
                cur_y, cur_page = y, n
                continue
            if cur is None:
                continue
            left = [r for r in rs if r[0] < 150]
            mid = [r for r in rs if 150 <= r[0] < 440]
            right = [r for r in rs if r[0] >= 440]
            if mid and min(r[0] for r in mid) < 158:            # a candidate's row: name at the column's edge
                if not DATETIME.match(P.join(right) if right else ""):
                    odd["name rows without a date"] += 1
                cur["cands"].append({"party": P.join(left) if left else "", "name": P.join(mid), "status": None})
                continue
            if left and not mid:
                odd["rows with a party and no name"] += 1
                continue
            # an address row (or a status line of its own): only the right-hand column is read, for the Board's status
            m = STATUS.search(P.join(right)) if right else None
            if m:
                if cur["cands"]:
                    cur["cands"][-1]["status"] = m.group(1).lower()
                else:
                    odd["status with no candidate"] += 1
    asof = next((re.search(r"as of (\d{1,2}/\d{1,2}/\d{4})", t).group(1) for t in head if re.search(r"as of \d", t)), "")
    election = next((t for t in head if t.startswith("General Election")), "")
    return {"asof": asof, "election": election, "offices": offices, "odd": odd}


def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            return net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url[:80]}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def candidate_list(folder, cache, say):
    """The list's allowed cells as JSON (sl_il_general_list.json), refreshed when older than two days. The PDF is read in
    memory; if the Board cannot be reached, the federal loader's copy on disk is read instead, else the JSON kept."""
    path = os.path.join(folder, "sl_il_general_list.json")
    if fresh(path, 2):
        return path
    data, origin = None, IL.URL
    try:
        data = fetch(IL.URL, say=say)
        if not data.startswith(b"%PDF"):
            raise ValueError("the Board's answer is not a PDF")
    except (OSError, ValueError) as e:
        fed = os.path.join(cache, "il_2026_general_candidate_list.pdf")
        say(f"      the candidate list was not fetched ({e}); " + ("reading the federal loader's copy" if os.path.exists(fed) else "keeping the copy read earlier"))
        if os.path.exists(fed):
            data, origin = open(fed, "rb").read(), "the federal loader's copy: " + os.path.basename(fed)
        elif os.path.exists(path):
            return path
        else:
            raise SystemExit("Illinois (state races): the candidate list could not be fetched and no copy is on disk")
    got = read_list(data)
    got.update(url=IL.URL, origin=origin, sha256=hashlib.sha256(data).hexdigest(), read=dt.date.today().isoformat(),
               kept="office headings; each candidate's party, name and status (removed or withdrawn); nothing else")
    json.dump(got, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def classify_heading(h):
    """A list heading -> ("state", race dict pieces) | ("federal"|"local", None) | ("unknown", None)."""
    h = re.sub(r"\s+", " ", h).strip()
    if h in STATEWIDE:
        suffix, kind, office, _ = STATEWIDE[h]
        return "state", {"race_id": f"2026-{STATE}-{suffix}", "level": "statewide", "office_kind": kind, "office": office}
    m = L_SENATE.match(h) or L_HOUSE.match(h)
    if m:
        senate = bool(L_SENATE.match(h))
        return "state", {"race_id": f"2026-{STATE}-{'SS' if senate else 'SH'}{int(m.group(1))}", "level": "legislature",
                         "office_kind": "state_senate" if senate else "state_house", "district": str(int(m.group(1)))}
    m = L_COURT.match(h)
    if m:
        d, court, retain = int(m.group(1)), m.group(2), bool(m.group(3))
        who = m.group(4) if retain else m.group(5)
        tag = ("APPRET" if retain else "APP") if court == "APPELLATE" else ("SCRET" if retain else "SC")
        return "state", {"race_id": f"2026-{STATE}-{tag}{d}-{family_key(who)}", "level": "court",
                         "office_kind": f"{'appellate' if court == 'APPELLATE' else 'supreme'}_court{'_retention' if retain else ''}",
                         "court": court, "district": str(d), "retain": retain, "who": who}
    if L_FEDERAL.match(h):
        return "federal", None
    if L_LOCAL.search(h):
        return "local", None
    return "unknown", None


# ------------------------------------------------------------------------------------------------------- the canvass

def canvass_lines(path):
    pdf = P.PDF(open(path, "rb").read())
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for y, rs in rows(pdf, page, res):
            text = IL.tight_join(rs)
            if text:
                yield n, y, text


def canvass(path):
    """{race_id: {"cands": [{name, mate, code, votes, pct, small, won, wi}], "bands": [...], "counties": set}} for the
    statewide offices, the State Senate, the House and the Appellate Court vacancies, and the problems found."""
    cover, headings, bases, sections, problems = "", set(), set(), {}, []
    office = sec = pending = app_d = None
    after_cand = False
    for page, _y, t in canvass_lines(path):
        if page == 1:
            cover += " " + t
            continue
        if page == 3 and re.search(r"(?:\. ?){5,}", t):
            headings.add(re.sub(r"\s*(?:\. ?){5,}.*$", "", t).strip().upper())
            bases = {re.sub(r"\s*\(.*\)$", "", h) for h in headings}      # JUDGE OF THE CIRCUIT COURT (COOK COUNTY) is headed without its bracket
            continue
        if t.upper() in headings or t.upper() in bases:
            office, sec, pending, after_cand, app_d = t.upper(), None, None, False, None
            if office in STATEWIDE:
                sec = sections.setdefault(f"2026-{STATE}-{STATEWIDE[office][0]}", {"cands": [], "bands": []})
            continue
        if office is None:
            continue
        if office in (CANVASS_SENATE, CANVASS_HOUSE):
            m = re.fullmatch(r"([A-Z -]+?) (LEGISLATIVE|REPRESENTATIVE)(?: DISTRICT)?", t)
            if m and ((m.group(2) == "LEGISLATIVE") == (office == CANVASS_SENATE)):
                d = ordinal_number(m.group(1))
                if d is None:
                    problems.append(f"a district heading not read: {t}")
                    sec = None
                    continue
                sec = sections.setdefault(f"2026-{STATE}-{'SS' if office == CANVASS_SENATE else 'SH'}{d}", {"cands": [], "bands": []})
                pending, after_cand = None, False
                continue
        elif office == CANVASS_APPELLATE:
            m = re.fullmatch(r"([A-Z -]+?) JUDICIAL DISTRICT", t)
            if m:
                app_d, sec = ordinal_number(m.group(1)), None
                continue
            m = re.fullmatch(r"\(To fill the vacancy of the Hon\. (.+)\)", t)
            if m and app_d:
                sec = sections.setdefault(f"2026-{STATE}-APP{app_d}-{family_key(m.group(1))}", {"cands": [], "bands": [], "vacancy": m.group(1)})
                pending, after_cand = None, False
                continue
        elif office not in STATEWIDE:
            continue
        if sec is None:
            continue
        m = IL.SUMMARY.match(t)
        if m and not sec["bands"]:
            sec["cands"].append({"name": m.group("name"), "code": m.group("code"), "votes": int(m.group("votes").replace(",", "")),
                                 "pct": 0.0 if m.group("pct").startswith("<") else float(m.group("pct")),
                                 "small": m.group("pct").startswith("<"), "won": bool(m.group("won")), "wi": bool(m.group("wi"))})
            after_cand = True
            continue
        words = t.split()
        codes = {c["code"] for c in sec["cands"]}
        if codes and all(w in codes for w in words):
            pending, after_cand = words, False
            continue
        if t.startswith("COUNTY ") and pending:
            head = (tuple(pending), t)
            if not sec["bands"] or sec["bands"][-1]["head"] != head:
                sec["bands"].append({"head": head, "codes": pending, "rows": {}})
            pending = None
            continue
        if after_cand and NAME_PART.match(t) and not IL.COUNTY_ROW.match(t):
            sec["cands"][-1]["name"] += " " + t      # a long name runs on to the next line
            continue
        after_cand = False
        m = IL.COUNTY_ROW.match(t)
        if m and sec["bands"]:
            band = sec["bands"][-1]
            nums = [int(x.replace(",", "")) for x in m.group("nums").split()]
            if len(nums) != len(band["codes"]):
                problems.append(f"a county row with {len(nums)} numbers under a band of {len(band['codes'])}: {m.group('county')}")
                continue
            if m.group("county") in band["rows"]:
                band = {"head": band["head"], "codes": band["codes"], "rows": {}}
                sec["bands"].append(band)
            band["rows"][m.group("county")] = nums
    if "OFFICIAL CANVASS" not in cover or "General Primary Election" not in cover or "March 17, 2026" not in cover:
        raise SystemExit("Illinois (state races): the primary file is no longer the Official Canvass of the March 17, 2026 General Primary")
    missing = ({CANVASS_SENATE, CANVASS_HOUSE, CANVASS_APPELLATE} | set(STATEWIDE)) - headings
    if missing:
        raise SystemExit(f"Illinois (state races): the canvass's table of contents no longer names {sorted(missing)}")
    for race, s in sorted(sections.items()):
        for c in s["cands"]:                     # JB PRITZKER [CHRISTIAN MITCHELL]: the running mate in brackets
            mm = re.fullmatch(r"(.+?) ?\[(.+)\]", c["name"])
            c["mate"] = mm.group(2).strip() if mm else None
            c["name"] = mm.group(1).strip() if mm else c["name"]
        seq = [code for b in s["bands"] for code in b["codes"]]
        if seq != [c["code"] for c in s["cands"]]:
            problems.append(f"{race}: the county tables' party codes {seq} do not follow the summary's candidates")
            s["counties"] = set()
            continue
        counties = [sorted(b["rows"]) for b in s["bands"]]
        if any(c != counties[0] for c in counties):
            problems.append(f"{race}: the county tables' bands do not list the same counties")
        s["counties"] = set(counties[0]) if counties else set()
        if race.endswith(tuple(f"-{v[0]}" for v in STATEWIDE.values())) and len(s["counties"]) != COUNTIES:
            problems.append(f"{race}: {len(s['counties'])} counties listed, not {COUNTIES}")
        k = 0
        for b in s["bands"]:
            for j in range(len(b["codes"])):
                summed = sum(v[j] for v in b["rows"].values())
                if summed != s["cands"][k]["votes"]:
                    problems.append(f"{race}: {s['cands'][k]['name']}'s county rows add to {summed:,}, the summary says {s['cands'][k]['votes']:,}")
                k += 1
        for code in {c["code"] for c in s["cands"]}:
            mine = [c for c in s["cands"] if c["code"] == code]
            total = sum(c["votes"] for c in mine)
            for c in mine:
                share = 100 * c["votes"] / total if total else 0
                if (c["small"] and share >= 0.01) or (not c["small"] and abs(share - c["pct"]) > 0.006):
                    problems.append(f"{race} {code}: {c['name']}'s printed share {c['pct']}% is not {share:.2f}% of the party's votes")
    return sections, problems


# ------------------------------------------------------------------------------------------------ the results pages

def text_of(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def results_label(label):
    """A results page's office label -> race id, or None for an office this loader does not store."""
    label = label.strip()
    if label in STATEWIDE:
        return f"2026-{STATE}-{STATEWIDE[label][0]}"
    m = re.fullmatch(rf"{ORD} (SENATE|REPRESENTATIVE)", label)
    if m:
        return f"2026-{STATE}-{'SS' if m.group(2) == 'SENATE' else 'SH'}{int(m.group(1))}"
    m = re.fullmatch(rf"{ORD} APPELLATE - (.+) VACANCY", label)
    if m:
        return f"2026-{STATE}-APP{int(m.group(1))}-{family_key(m.group(2))}"
    return None


def results_pages(folder, say):
    """{race: [[name, party, votes]]} from the Board's Election Results pages for the primary: candidate, party and total
    votes only (kept on disk for 30 days as sl_il_primary_results.json)."""
    path = os.path.join(folder, "sl_il_primary_results.json")
    if fresh(path, 30):
        return path
    out, digests = {}, {}
    for label, code in RESULT_PAGES.items():
        raw = fetch(RESULTS_BASE + code, accept="text/html", say=say)
        digests[label] = hashlib.sha256(raw).hexdigest()
        page = raw.decode("utf-8", "replace")
        chosen = re.search(r'<option selected="selected" value="[^"]*">([^<]*)</option>', page)
        if not chosen or chosen.group(1).strip() != "2026 GENERAL PRIMARY":
            raise SystemExit(f"Illinois (state races): the Election Results page ({label}) is no longer the 2026 General Primary's")
        for m in re.finditer(r'<asp:Label runat="server"[^>]*>([^<]*)</asp:Label>(.*?)(?=<asp:Label runat="server"|$)', page, re.S):
            race = results_label(m.group(1))
            if not race:
                continue
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(2), re.S):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if len(tds) != 4 or text_of(tds[0]) == "Vote Totals":
                    continue
                out.setdefault(race, []).append([text_of(tds[0]), text_of(tds[1]), int(text_of(tds[2]).replace(",", "") or 0)])
    json.dump({"base": RESULTS_BASE, "pages": {k: RESULTS_BASE + v for k, v in RESULT_PAGES.items()}, "sha256": digests,
               "election": "2026 GENERAL PRIMARY", "read": dt.date.today().isoformat(),
               "columns": ["Candidate", "Party", "Total Votes"], "rows": out},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


# ----------------------------------------------------------------------------------------------- roster and counties

def roster(path):
    """Sitting legislators and statewide officials: ids, names, party, chamber and district only (the roster's contact
    columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def squash(family):
    return re.sub(r"[^a-z]", "", family)


def name_fits(cand, form):
    """fits(), and two things it leaves out: initials written together (JB Pritzker, J. B. Pritzker) and a family name
    written with or without its space (Du Buclet, DuBuclet)."""
    if not form[1]:
        return False
    if fits(cand, form) or fits(form, cand):
        return True
    if squash(cand[1]) != squash(form[1]) or not cand[0] or not form[0]:
        return False
    a, b = "".join(cand[0]), "".join(form[0])
    ia, ib = "".join(w[0] for w in cand[0]), "".join(w[0] for w in form[0])
    return fits((cand[0], form[1]), form) or a == ib or b == ia or cand[0][0] == form[0][0]


def person_fits(name, p):
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    if p.get("full"):
        forms.append(name_parts(p["full"]))
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(name_fits(cand, f) for f in forms)


def county_codes(path):
    """{letters of the county's name: (5-digit FIPS, name)} for Illinois, from the Census county file's attributes only."""
    import io
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        r = dict(zip(fields, rec))
        if str(r.get("STATEFP")) == FIPS:
            out[re.sub(r"[^A-Z]", "", str(r["NAME"]).upper())] = (str(r["GEOID"]), str(r["NAME"]))
    return out


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------------------- the county and local part

LOCAL_DIR = os.path.join(CACHE, "il", "local")
SRC_COOK, SRC_CHI, SRC_CHI_PAGE = "il-cook-clerk-2026-general-contests", "il-chicago-board-2026-general-list", "il-chicago-board-candidates-page"
SRC_ACT, SRC_AUTH = "il-ilga-circuit-courts-act", "il-sbe-election-authorities"
COOK_URL = "https://www.cookcountyclerkil.gov/api/Candidate/GetAllCandidates?language=en&electionCode=110326&partyCode="
CHI_PAGE = "https://chicagoelections.gov/getting-ballot/candidates"
CHI_FILES = "cboeprod.blob.core.usgovcloudapi.net"          # the Chicago Board's own file store
ACT_URL = "https://www.ilga.gov/Documents/legislation/ilcs/documents/070500350K1.htm"
AUTH_URL = "https://www.elections.il.gov/ElectionOperations/ElectionAuthorities.aspx"
CALENDAR_URL = "https://www.ilga.gov/Documents/legislation/ilcs/documents/001000050K2A-1.2.htm"
LIST_DAYS, LAW_DAYS, PAUSE = 2, 30, 1.2                    # how long a kept copy is used; seconds between two requests
# A regional superintendent's contest is also voted on in parts of neighbouring counties: the March primary's canvass
# counts votes for it there, beside the region's own counties. True files the contest under those counties too
# (county_ids: every county the contest reaches); False files it under the region's own counties only. Either way the
# place row holds the region's own counties and the contest's note names the others.
REGION_SLICES = True
NONPARTISAN = "Nonpartisan office"
CANVASS_ROE, CANVASS_CIRCUIT = "REGIONAL SUPERINTENDENT OF SCHOOLS", "JUDGE OF THE CIRCUIT COURT"
ORD_L = r"(\d{1,2})(?:st|nd|rd|th)"
L_ROE = re.compile(r"^(?P<names>.+?)(?P<etc>,\s*ETC\.?)?\s*(?:-\s*)?(?:SUPERINTENDENT|SUPERENTENDENT|SUPT\.?|SUP)\s+OF\s+SCHOOLS$")
L_CIRCUIT = re.compile(r"^(?:(?P<cook>COOK)|(?P<n>\d{1,2})(?:ST|ND|RD|TH)) CIRCUIT - (?:(?P<sub>\d{1,2})(?:ST|ND|RD|TH) SUBCIRCUIT - )?"
                       r"(?:RETAIN (?P<ret>.+)|(?P<vac>.+) VACANCY)$")
# the page builder's own test for a street address (wider than check_local's: Court, Pl, Place), so that nothing
# written here is dropped there
PAGE_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                         r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)

# The Cook County Clerk's list: the party codes it prints, written out as the Chicago Board's list and the State Board's
# write them (every code below is on both local lists for the same candidates)
PARTY_COOK = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "IND": "Independent", "ACP": "American Center Party",
              "WCP": "Working Class Party", "NON": "Nonpartisan"}
COOK_STATE = {"Senator", "U.S. Representative", "Governor and Lieutenant Governor", "Attorney General", "Secretary of State", "Comptroller",
              "State Senator", "State Representative"}
COOK_COUNTY = {"Board President": "county_board_chair", "Clerk": "county_clerk", "Sheriff": "sheriff", "Treasurer": "county_treasurer",
               "Assessor": "county_assessor"}
CHI_COUNTY = {"President of County Board": "county_board_chair", "County Clerk": "county_clerk", "County Sheriff": "sheriff",
              "County Treasurer": "county_treasurer", "County Assessor": "county_assessor"}
CHI_STATE = re.compile(r"^(?:United States Senator|Governor & Lieutenant Governor|Attorney General|Secretary of State|Comptroller|Treasurer|"
                       r"U\.S\. Representative, .+ District|State Senator, .+ District|State Representative, .+ District)$")
CHI_CAND = re.compile(r"^\((\d{1,3})\)\s+(.+?)\s+\(([^()]+)\)$")                      # the left-hand columns of a candidate's row
CHI_LINE = re.compile(r"^\((\d{1,3})\)\s+(.+)\s+\(([^()]+)\)\s+([A-Za-z][A-Za-z /-]*)$")      # the whole row, status and all
CHI_OFF = re.compile(r"withdr|remov|disqual|invalid|not certified|off the ballot", re.I)
NO_CANDIDATE = re.compile(r"^no candidates?\b", re.I)          # a list's own words where nobody filed
COUNTY_OFFICE = {"county_board_chair": "President of the County Board", "county_clerk": "County Clerk", "sheriff": "Sheriff",
                 "county_treasurer": "County Treasurer", "county_assessor": "County Assessor"}
# the cities the State Board lists as election jurisdictions of their own, and the county each lies in
CITY_BOARDS = {"BLOOMINGTON": "McLean", "CHICAGO": "Cook", "DANVILLE": "Vermilion", "EAST ST. LOUIS": "St. Clair", "GALESBURG": "Knox",
               "ROCKFORD": "Winnebago"}

CALENDAR = ("On November 3, 2026 each Illinois county elects its county clerk, treasurer and sheriff and the county board members whose terms "
            "are ending; Cook County also elects its board president, its assessor and members of its Board of Review. On the same ballot are "
            "the regional superintendents of schools, the commissioners of the Metropolitan Water Reclamation District and elected trustees of "
            "other sanitary districts, the Chicago Board of Education, and circuit judges, both to fill vacancies and on the question of "
            "retention; state's attorneys, circuit clerks, coroners and county auditors are elected in presidential years, next in 2028. "
            "Cities, villages, townships, park, library, fire protection and community college districts and the other school boards are "
            "elected, with few exceptions, at the consolidated election on the first Tuesday in April of odd-numbered years, next in 2027.")
CALENDAR_SOURCE = ("Illinois Election Code, 10 ILCS 5/2A-1.1 and 2A-1.2 (which offices are filled at which election) and 2A-14 through 2A-23 "
                   "(the years each county office is elected)")
GAP_WHAT = "county offices and local districts"
GAP_REASON = ("This county's November list is not loaded yet. Illinois has no statewide list of county candidates: each county's election "
              "authority, the county clerk in most counties, certifies and publishes its own.")
WRITE_IN_LINE = "The Chicago Board's list shows a write-in line for this contest and names no write-in candidate."
RETAIN_CIRCUIT = " The question is asked of the voters of the whole circuit."
RETAIN_CAND = "The judge whose retention is on the ballot."


def and_words(items):
    items = [str(x) for x in items]
    return "" if not items else items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def plain(text):
    """Accents folded: for keys and for matching, never for showing."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in t if not unicodedata.combining(c))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", plain(text).lower()).strip("-")


def letters(name):
    """A name's letters alone, in capitals: how two lists' spellings of one name are compared."""
    return re.sub(r"[^A-Z]", "", plain(name).upper())


def reads_like_contact(text, strict=True):
    """check_local's test, and on strict text the page builder's wider one for street words."""
    t = str(text or "")
    return bool(t) and (contact_like(t, strict) or bool(strict and PAGE_STREET.search(t)))


def cell(value, blanked):
    """A kept cell as plain text. A cell that reads like contact details is blanked and counted, never shown."""
    t = re.sub(r"\s+", " ", str("" if value is None else value)).strip()
    if t and reads_like_contact(t):
        blanked[0] += 1
        return ""
    return t


def unquoted(value):
    """'John Doe, Jr.' -> John Doe, Jr.; Robert ''Bob'' Rita -> Robert "Bob" Rita. The Clerk's list wraps a cell that holds
    a comma in single quotes and writes a quotation mark as two apostrophes; the Chicago Board's list prints the same
    names with the quotation marks themselves."""
    t = str("" if value is None else value).strip()
    lead, trail = len(t) - len(t.lstrip("'")), len(t) - len(t.rstrip("'"))
    if len(t) >= 2 and lead % 2 == 1 and trail % 2 == 1:        # an odd run of apostrophes at each end: one of them is the wrapper
        t = t[1:-1].strip()
    return t.replace("''", '"')


def keep(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)


def kept(path):
    try:
        return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    except ValueError:
        return None


def tail_words(full, key):
    """The last words of a full name whose letters are the key: Curry, Jr. of John J. Curry, Jr. for CURRYJR."""
    ws = full.split()
    for k in range(len(ws) - 1, -1, -1):
        if letters(" ".join(ws[k:])) == key:
            return " ".join(ws[k:])
    return None


# ---- the March primary's canvass, read for places only

def canvass_places(path, counties):
    """From the Official Canvass of the March primary, for places only (no vote is kept): each Regional Superintendent of
    Schools section (the counties its heading names; the counties its county tables list) and each Judge of the Circuit
    Court section (the circuit, the subcircuit or the one county of a resident judgeship, the words naming the vacancy,
    the counties its county tables list)."""
    def fips(name):
        hit = counties.get(re.sub(r"[^A-Z]", "", str(name).upper()))
        return hit[0] if hit else None

    headings, bases, secs, cur, problems = set(), set(), [], None, []
    for page, _y, t in canvass_lines(path):
        if page == 1:
            continue
        if page == 3 and re.search(r"(?:\. ?){5,}", t):
            headings.add(re.sub(r"\s*(?:\. ?){5,}.*$", "", t).strip().upper())
            bases = {re.sub(r"\s*\(.*\)$", "", h) for h in headings}
            continue
        u = t.upper()
        if u in headings or u in bases:
            cur = None
            if u in (CANVASS_ROE, CANVASS_CIRCUIT):
                cur = {"office": u, "head": [], "n": 0, "counties": [], "unknown": 0}
                secs.append(cur)
            continue
        if cur is None:
            continue
        if IL.SUMMARY.match(t):
            cur["n"] += 1
            continue
        m = IL.COUNTY_ROW.match(t)
        if not cur["n"]:
            if not m and len(cur["head"]) < 6:
                cur["head"].append(t)
            continue
        if m:
            f = fips(m.group("county"))
            if f is None:
                cur["unknown"] += 1
            elif f not in cur["counties"]:
                cur["counties"].append(f)
    regions, circuits = [], []
    for k, s in enumerate(secs, start=1):
        if s["unknown"]:
            problems.append(f"canvass section {k}: {s['unknown']} county rows whose county is not in the Census file")
        if s["office"] == CANVASS_ROE:
            m = re.fullmatch(r"\((.+?) COUNT(?:Y|IES)\)", " ".join(s["head"]).strip())
            named = [fips(x) for x in re.split(r",\s*|\s+AND\s+", m.group(1))] if m else []
            if not named or None in named or len(set(named)) != len(named):
                problems.append(f"canvass section {k}: a regional superintendent heading whose counties were not read")
                continue
            if not set(named) <= set(s["counties"]):
                problems.append(f"canvass section {k}: a region's own counties are not all in its county tables")
            regions.append({"named": named, "table": list(s["counties"]), "used": 0})
            continue
        head = list(s["head"])
        if not head:
            problems.append(f"canvass section {k}: a circuit judge section with no heading")
            continue
        m = re.fullmatch(r"([A-Z -]+?) JUDICIAL CIRCUIT", head[0])
        circuit = "COOK" if head[0] == "COOK COUNTY JUDICIAL CIRCUIT" else ordinal_number(m.group(1)) if m else None
        sub = resident = who = None
        kind, words = "other", ""
        for line in head[1:]:
            ms, mc = re.fullmatch(r"([A-Z -]+?) SUBCIRCUIT", line), re.fullmatch(r"(.+?) COUNTY", line)
            if words or line.startswith("("):
                words = (words + " " + line).strip()
            elif ms:
                sub = ordinal_number(ms.group(1))
            elif mc and fips(mc.group(1)):
                resident = fips(mc.group(1))
            else:
                words = (words + " " + line).strip()
        words = re.sub(r"^\(|\)$", "", words).strip()
        m1, m2 = re.fullmatch(r"To fill the vacancy of the Hon\. (.+)", words), re.fullmatch(r"Converted from Associate Judgeship of (.+)", words)
        if m1:
            kind, who = "vacancy", m1.group(1).strip()
        elif m2:
            kind, who = "converted", m2.group(1).strip()
        if circuit is None or not s["counties"] or (resident and s["counties"] != [resident]):
            problems.append(f"canvass section {k}: a circuit judge section whose circuit or counties were not read")
            continue
        circuits.append({"circuit": circuit, "sub": sub, "resident": resident, "kind": kind, "who": who, "words": words,
                         "counties": list(s["counties"]), "used": 0})
    return {"regions": regions, "circuits": circuits, "problems": problems}


# ---- the counties of each judicial circuit (705 ILCS 35/1)

def circuits_act(folder, counties, say, refresh=False):
    """{"circuits": {"COOK" or the circuit's number as text: [county FIPS]}, ...} from Section 1 of the Circuit Courts
    Act on the General Assembly's site. A statute's text has no contact details, so the page is kept whole."""
    path = os.path.join(folder, "il_circuit_courts_act_sec1.htm")
    if refresh or not fresh(path, LAW_DAYS):
        try:
            raw = fetch(ACT_URL, accept="text/html", say=say)
            time.sleep(PAUSE)
            if b"Judicial circuits created" not in raw:
                raise ValueError("the page is not Section 1 of the Circuit Courts Act")
            os.makedirs(folder, exist_ok=True)
            with open(path + ".part", "wb") as fh:
                fh.write(raw)
            os.replace(path + ".part", path)
        except (OSError, ValueError) as e:
            say(f"      the Circuit Courts Act was not fetched ({e}); " + ("keeping the copy read earlier" if os.path.exists(path) else "the circuits' counties come from the canvass alone"))
            if not os.path.exists(path):
                return None
    raw = open(path, "rb").read()
    text = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))).replace("\xa0", " ")
    text = text.split("(Source:")[0]
    out, problems = {}, []
    if re.search(r"The county of Cook shall be one judicial circuit", text) and "COOK" in counties:
        out["COOK"] = [counties["COOK"][0]]
    parts = re.split(r"\b([A-Z][a-z]+(?:-[a-z]+)?) Circuit--", text)
    for word, body in zip(parts[1::2], parts[2::2]):
        n = ordinal_number(word.upper())
        hits = list(re.finditer(r"\bthe count(?:y|ies) of ", body, re.I))
        later = [int(y) for y in re.findall(r"On and after [A-Z][a-z]+ \d{1,2}, (\d{4})", body)]
        if n is None or not hits or any(y > 2026 for y in later):
            problems.append(f"the {word} Circuit's counties were not read from the Act")
            continue
        tail = body[hits[-1].end():].strip().rstrip(".").strip()
        got = [counties.get(re.sub(r"[^A-Z]", "", x.upper())) for x in re.split(r",\s*and\s+|\s+and\s+|,\s*", tail) if x.strip()]
        if not got or None in got:
            problems.append(f"the {word} Circuit names a county that is not in the Census file")
            continue
        out[str(n)] = [g[0] for g in got]
    seen = [f for v in out.values() for f in v]
    if sorted(out, key=str) != sorted(["COOK"] + [str(n) for n in range(1, 25)], key=str):
        problems.append(f"the Act gives {len(out)} circuits, not Cook and the 1st to the 24th")
    if len(seen) != len(set(seen)) or len(set(seen)) != COUNTIES:
        problems.append(f"the Act's circuits hold {len(set(seen))} different counties ({len(seen)} named), not each of the {COUNTIES} once")
    return {"circuits": out, "problems": problems, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": mtime(path), "bytes": len(raw)}


# ---- the State Board's list of election jurisdictions (names only)

def election_authorities(folder, say, refresh=False):
    """The names in the drop-down of the State Board's Election Authorities page: the 102 counties and the cities with a
    board of election commissioners of their own. Only those names are kept (il_election_authorities.json)."""
    path = os.path.join(folder, "il_election_authorities.json")
    if not refresh and fresh(path, LAW_DAYS) and kept(path):
        return kept(path)
    try:
        raw = fetch(AUTH_URL, accept="text/html", say=say)
        time.sleep(PAUSE)
        labels = [text_of(x) for x in re.findall(r"<option[^>]*>(.*?)</option>", raw.decode("utf-8", "replace"), re.S)]
        names = [x for x in labels if re.fullmatch(r"[A-Za-z .'-]{3,40}", x) and not re.match(r"(?i)(please|all)\b", x) and not reads_like_contact(x)]
        if len(names) < COUNTIES:
            raise ValueError(f"the page lists {len(names)} jurisdictions")
    except (OSError, ValueError) as e:
        say(f"      the State Board's list of election authorities was not read ({e})" + ("; keeping the names read earlier" if kept(path) else ""))
        return kept(path)
    out = {"url": AUTH_URL, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "names": names,
           "kept": "the names in the page's list of jurisdictions; nothing else on the page"}
    keep(path, out)
    return out


# ---- the Cook County Clerk's contest list

def cook_cut(rows, blanked):
    """The Clerk's contests cut down to the allowed cells: the contest's number, office, district words, vacancy words,
    how many to vote for, the term and whether it is a retention question; each candidate's name, party code and
    ballot numbers. Nothing else in the file is kept."""
    out = []
    for c in rows:
        if not isinstance(c, dict):
            continue
        out.append({"race": cell(c.get("RaceNumber"), blanked), "office": cell(c.get("Office"), blanked), "name": cell(c.get("Name"), blanked),
                    "vacancy": cell(unquoted(c.get("Vacancy")), blanked), "vote": cell(c.get("Vote"), blanked), "term": cell(c.get("Term"), blanked),
                    "term_shown": bool(c.get("TermDisplay")), "retention": bool(c.get("Retention")),
                    "cands": [{"name": cell(unquoted(i.get("Name")), blanked), "party": cell(i.get("Pty"), blanked), "num": cell(i.get("Num"), blanked),
                               "no_num": cell(i.get("NoNum"), blanked)} for i in (c.get("item") or []) if isinstance(i, dict)]})
    return out


def cook_lines(contests):
    """Every candidate line as (contest number, vacancy words, name, party, ballot number): what two readings must share."""
    return collections.Counter((c["race"], c["vacancy"], k["name"], k["party"], k["num"]) for c in contests for k in c["cands"])


def cook_list(folder, say, refresh=False):
    """The Clerk's list as kept cells (cook_clerk_2026_general_contests.json), fetched afresh when the kept copy is older
    than two days. Read twice: the whole list, then party by party (the same address with each party code the whole
    list holds); the candidate lines of the two readings are compared and the result is kept with the cells."""
    path = os.path.join(folder, "cook_clerk_2026_general_contests.json")
    if not refresh and fresh(path, LIST_DAYS) and kept(path):
        return kept(path)
    try:
        raw = fetch(COOK_URL, accept="application/json", say=say)
        time.sleep(PAUSE)
        if not raw.lstrip().startswith(b"{"):
            raise ValueError("the answer is not the contest list")
        rows = json.loads(raw.decode("utf-8")).get("Candidates")
        if not isinstance(rows, list) or not rows:
            raise ValueError("the answer holds no contests")
        blanked = [0]
        contests = cook_cut(rows, blanked)
        if not any(c["office"] == "Clerk" and c["name"] == "Cook County" for c in contests):
            raise ValueError("the answer is not the general election's list (no County Clerk contest)")
    except (OSError, ValueError) as e:
        say(f"      the Cook County Clerk's list was not fetched ({e})" + ("; keeping the copy read earlier" if kept(path) else ""))
        return kept(path)
    whole, again, per, done = cook_lines(contests), collections.Counter(), {}, True
    try:                                                       # the second reading; if it cannot be finished the first still stands, and the report says so
        for code in sorted({k["party"] for c in contests for k in c["cands"]}):
            if not re.fullmatch(r"[A-Z]{2,5}", code):
                raise ValueError("a party code that is not a few capital letters")
            part = json.loads(fetch(COOK_URL + code, accept="application/json", say=say).decode("utf-8")).get("Candidates") or []
            time.sleep(PAUSE)
            mine = cook_lines(cook_cut(part, [0]))
            per[code] = sum(mine.values())
            again += mine
    except (OSError, ValueError) as e:
        say(f"      the Cook County Clerk's list was not read a second time, party by party ({e})")
        done = False
    out = {"url": COOK_URL, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
           "kept": "contest number, office, district words, vacancy words, votes allowed, term, retention mark; each candidate's name, party code "
                   "and ballot numbers; nothing else",
           "blanked": blanked[0], "second": {"by_party": per, "lines": sum(again.values()), "done": done, "agrees": done and again == whole,
                                             "differ": sum(((again - whole) + (whole - again)).values()) if done else None},
           "contests": contests}
    keep(path, out)
    return out


def cook_key(c):
    """What a contest on the Clerk's list is: ("state",) for the federal and state offices the State Board's list carries,
    ("judge",), or the key of a county or local contest; None for a contest this loader does not know."""
    office, name = c["office"], c["name"]
    if office in COOK_STATE or (office == "Treasurer" and name == "State of Illinois"):
        return ("state",)
    if office == "Judge":
        return ("judge",)
    if office == "Commissioner" and name == "Metropolitan Water Reclamation District":
        return ("mwrd", "unexpired" if re.search(r"unexpired", c["vacancy"], re.I) else "full", c["term"])
    if name == "Cook County" and office in COOK_COUNTY:
        return ("county", COOK_COUNTY[office])
    m = re.fullmatch(rf"{ORD_L} County Board District", name)
    if m and office == "Commissioner":
        return ("commissioner", int(m.group(1)))
    m = re.fullmatch(rf"Board of Review {ORD_L} District", name)
    if m and office == "Commissioner":
        return ("review", int(m.group(1)))
    m = re.fullmatch(r"(.+) County Regional Office of Education", name)
    if m and office == "Superintendent":
        return ("roe", m.group(1))
    if office == "Trustee" and re.search(r"\bSanitary District$", name, re.I):
        return ("sanitary", name, c["term"])
    return None


# ---- the Chicago Board of Election Commissioners' candidate filings in ballot order

def read_chicago(data):
    """The Board's PDF as kept cells. Contests: a heading in larger type, "Vote for ...", then one row per candidate,
    "(ballot number) name (party)" on the left and the status on the right, and for some contests a write-in line.
    Retention pages: the court, the judge's name, and the Yes and No ballot numbers. The pages of ballot questions that
    follow are only counted. The file has no contact columns; only these cells are turned into text."""
    pdf = P.PDF(data)
    out = {"title": "", "asof": "", "unofficial": False, "pages": 0, "contests": [], "retention": [], "question_rows": 0}
    odd, second = collections.Counter(), collections.Counter()
    mode = cur = rcur = None
    blanked = [0]
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        out["pages"] = n
        for _y, rs in rows(pdf, page, res):
            size = min(r[2] for r in rs)
            if size >= 13.5:                                   # a section's title
                t = P.join(rs)
                if "Candidate Filings in Ballot Order" in t:
                    mode, out["title"] = "contests", cell(t, blanked)
                elif "Judicial Retention" in t:
                    mode = "retention"
                else:
                    mode = "questions"
                cur = rcur = None
                continue
            if mode is None:                                   # the lines above the title on the first page
                t = P.join(rs)
                m = re.search(r"Status as of (\d{1,2}/\d{1,2}/\d{4})", t)
                if m:
                    out["asof"] = m.group(1)
                if re.search(r"\bUnofficial candidate list\b", t, re.I):
                    out["unofficial"] = True
                continue
            if mode == "questions":
                out["question_rows"] += 1
                continue
            if mode == "contests":
                if size >= 12.5:                               # a contest's heading
                    t = cell(P.join(rs), blanked)
                    if cur is not None and not cur["vote"] and not cur["cands"] and cur["page"] == n:
                        cur["heading"] = (cur["heading"] + " " + t).strip()      # a long heading runs on
                    else:
                        cur = {"heading": t, "vote": "", "write_in_line": False, "cands": [], "page": n}
                        out["contests"].append(cur)
                    continue
                if size >= 8.5:
                    if P.join(rs) != "Ballot No. Candidate Status":
                        odd["rows in the heading type that are not the column heading"] += 1
                    continue
                left, right = [r for r in rs if r[0] < 480], [r for r in rs if r[0] >= 480]
                lt, rt = (P.join(left) if left else ""), (P.join(right) if right else "")
                if cur is None:
                    odd["rows before the first contest"] += 1
                elif lt.startswith("Vote for") and not rt:
                    cur["vote"] = cell(lt, blanked)
                elif lt == "Write-in":
                    cur["write_in_line"] = True
                elif CHI_CAND.match(lt) and rt:
                    m = CHI_CAND.match(lt)
                    cur["cands"].append({"num": int(m.group(1)), "name": cell(m.group(2), blanked), "party": cell(m.group(3), blanked),
                                         "status": cell(rt, blanked)})
                    m2 = CHI_LINE.match(P.join(rs))            # the same row read whole, without the column edge: a second reading
                    second["lines"] += 1
                    second["alike"] += int(bool(m2) and (m2.group(1), m2.group(2), m2.group(3), m2.group(4).strip()) ==
                                           (m.group(1), m.group(2), m.group(3), rt))
                else:
                    odd["rows under a contest that were not read"] += 1
                continue
            # the retention pages
            t = P.join(rs)
            if size < 7.5:
                rcur = {"court": cell(t, blanked), "name": "", "yes": None, "no": None}
                out["retention"].append(rcur)
            elif rcur is None:
                odd["retention rows before the first judge"] += 1
            elif size >= 11.5:
                rcur["name"] = (rcur["name"] + " " + cell(t, blanked)).strip()
            else:
                m = re.fullmatch(r"\((\d{1,3})\) (Yes|No)", t)
                if m:
                    rcur[m.group(2).lower()] = int(m.group(1))
                else:
                    odd["retention rows that were not read"] += 1
    for c in out["contests"]:
        del c["page"]
    out["odd"], out["blanked"] = dict(odd), blanked[0]
    out["second"] = {"lines": second["lines"], "alike": second["alike"]}
    return out


def chicago_list(folder, say, refresh=False):
    """The Board's list as kept cells (chicago_board_2026_general_list.json), fetched afresh when the kept copy is older
    than two days. The PDF's address is read from the Board's Candidates page: the one link to the Board's own file
    store whose words name the candidate list for November 3, 2026. The PDF itself is read in memory and not kept."""
    path = os.path.join(folder, "chicago_board_2026_general_list.json")
    if not refresh and fresh(path, LIST_DAYS) and kept(path):
        return kept(path)
    try:
        page_raw = fetch(CHI_PAGE, accept="text/html", say=say)
        time.sleep(PAUSE)
        hits = []
        for m in re.finditer(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', page_raw.decode("utf-8", "replace"), re.S):
            u, label = urlsplit(H.unescape(m.group(1)).strip()), text_of(m.group(2))
            if (u.scheme == "https" and u.netloc.lower() == CHI_FILES and u.path.lower().endswith(".pdf")
                    and re.search(r"candidate list", label, re.I) and re.search(r"November\s+3,\s+2026", label)):
                hits.append(urlunsplit((u.scheme, u.netloc, quote(u.path, safe="/%"), "", "")))
        hits = list(dict.fromkeys(hits))
        if len(hits) != 1:
            raise ValueError(f"the Candidates page links {len(hits)} candidate lists for November 3, 2026, not one")
        raw = fetch(hits[0], say=say)
        time.sleep(PAUSE)
        if not raw.startswith(b"%PDF"):
            raise ValueError("the Board's answer is not a PDF")
        got = read_chicago(raw)
        if "November 3, 2026" not in got["title"] or not got["contests"]:
            raise ValueError("the file is not the candidate filings in ballot order for November 3, 2026")
    except (OSError, ValueError) as e:
        say(f"      the Chicago Board's list was not fetched ({e})" + ("; keeping the copy read earlier" if kept(path) else ""))
        return kept(path)
    got.update(page=CHI_PAGE, page_sha256=hashlib.sha256(page_raw).hexdigest(), url=hits[0], sha256=hashlib.sha256(raw).hexdigest(),
               bytes=len(raw), fetched=dt.date.today().isoformat(),
               kept="contest headings, votes allowed, write-in line; each candidate's ballot number, name, party and status; each retention "
                    "judge's court, name and Yes and No numbers; nothing else")
    keep(path, got)
    return got


def chicago_key(heading):
    """What a contest on the Chicago Board's list is, in the same keys as cook_key()."""
    h = re.sub(r"\s+", " ", heading).strip()
    if CHI_STATE.match(h):
        return ("state",)
    m = re.fullmatch(r"Metropolitan Water Reclamation District Commissioners (Full|Unexpired) (\d+)-Year Term", h)
    if m:
        return ("mwrd", m.group(1).lower(), m.group(2))
    if h in CHI_COUNTY:
        return ("county", CHI_COUNTY[h])
    m = re.fullmatch(rf"County Commissioner, {ORD_L} District", h)
    if m:
        return ("commissioner", int(m.group(1)))
    m = re.fullmatch(rf"Board of Review, {ORD_L} District", h)
    if m:
        return ("review", int(m.group(1)))
    if re.match(r"Judge\b", h):
        return ("judge",)
    if h == "President of the Chicago Board of Education":
        return ("boe", "")
    m = re.fullmatch(r"Member of the Chicago Board of Education, Subdistrict (\d{1,2}[A-Z])", h)
    if m:
        return ("boe", m.group(1))
    return None


# ---- the local rows

def local_level(offices, glist, cpath, counties, folder, say=print, refresh=False):
    """Illinois's rows below the state level, ready to be written: the regional superintendents and circuit judges on
    the State Board's list (offices: the list's headings this loader's state part sets aside as local, with their
    candidates), Cook County's contests from the Clerk's list and the Chicago Board's, and for every other county a gap.
    Returns {"races", "cands", "places", "sources", "gaps", "notes", "problems", "counts", ...}; nothing is written here."""
    os.makedirs(folder, exist_ok=True)
    name_of = {g: n for g, n in counties.values()}             # FIPS -> the county's name as the Census Bureau writes it
    cook = counties["COOK"][0]
    problems, gaps, races, cands, places, sources = [], [], [], [], {}, []
    n, hidden, circuits_used = collections.Counter(), collections.Counter(), set()

    def fips(name):
        hit = counties.get(re.sub(r"[^A-Z]", "", str(name).upper()))
        return hit[0] if hit else None

    def cty(ids):
        return f"{and_words(name_of[f] for f in ids)} {'counties' if len(ids) > 1 else 'County'}"

    def add_race(rid, level, kind, office, jur, jid, cids, district, seat, special, partisan, note):
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid) or any(r[0] == rid for r in races):
            raise SystemExit(f"Illinois (local): the race id {rid} is not usable or is used twice")
        races.append((rid, STATE, level, kind, office, jur, jid, json.dumps(sorted(cids)) if cids else None, district, seat, special, partisan,
                      None, None, None, GENERAL, (note or "").strip() or None))

    def add_cand(rid, name, party, order, src, inc=0, note=None):
        """party None: a nonpartisan office. A name that is empty (blanked) or reads like contact details is left out."""
        if not name or reads_like_contact(name) or NOT_A_NAME.search(name):
            n["names not shown"] += 1
            hidden[rid] += 1
            return
        words, code = (NONPARTISAN, "N") if party is None else (party, party_code(party))
        cands.append([rid, "general", GENERAL, name, words, code, order, inc, 0, None, None, None, None, src, note])

    # ---------------------------------------------------------------- 1. the State Board's list: regions and circuits
    canv = canvass_places(cpath, counties)
    problems += [f"canvass: {p}" for p in canv["problems"]]
    act = circuits_act(folder, counties, say, refresh)
    if act:
        problems += [f"Circuit Courts Act: {p}" for p in act["problems"]]
    by_circuit = dict(act["circuits"]) if act else {}
    for s in canv["circuits"]:                                 # a circuit the Act did not give: its counties from a contest of the whole circuit
        if s["sub"] is None and s["resident"] is None:
            by_circuit.setdefault(str(s["circuit"]), list(s["counties"]))
    court_names = {"vacancy": set(), "retention": set()}       # Cook County's judges by the letters of their names, to check the local lists
    for off in offices:
        h = re.sub(r"\s+", " ", off["heading"]).strip()
        live, gone = [c for c in off["cands"] if not c["status"]], [c for c in off["cands"] if c["status"]]
        n["list headings"] += 1
        n["list candidates"] += len(off["cands"])
        n["list removed or withdrawn"] += len(gone)
        m = L_ROE.match(h) if "CIRCUIT" not in h else None
        if m:
            want = [fips(x) for x in m.group("names").split("/")]
            fit = [r for r in canv["regions"] if None not in want and r["named"][:len(want)] == want and (m.group("etc") or len(r["named"]) == len(want))]
            if None in want or (len(fit) != 1 and m.group("etc")) or len(fit) > 1:
                n["list headings not placed"] += 1
                n["list candidates not placed"] += len(off["cands"])
                gaps.append((STATE, "state", STATE, "Illinois", f"one regional superintendent contest (heading {n['list headings not placed']})",
                             "The State Board's list names this region by its first counties only, and the region could not be matched to one "
                             "region of the March primary's canvass, so the contest is not shown.", glist["url"]))
                problems.append(f"a regional superintendent heading was not matched to one region of the canvass (heading {n['list headings']})")
                continue
            if fit:
                fit[0]["used"] += 1
                own, reach, src = fit[0]["named"], set(fit[0]["named"]) | set(fit[0]["table"]), SRC_CANVASS
            else:                                              # every county is in the heading itself
                own, reach, src = want, set(want), SRC_LIST
                problems.append(f"a region on the list is not in the March primary's canvass; its counties are the heading's own (heading {n['list headings']})")
            key = "roe-" + "-".join(slug(name_of[f]) for f in own)
            jid = f"{STATE}-X-{key}"
            jur = f"{and_words(name_of[f] for f in own)} {'Counties' if len(own) > 1 else 'County'} Regional Office of Education"
            extra = sorted(reach - set(own), key=lambda f: name_of[f])
            if not REGION_SLICES:                              # the contest filed under the region's own counties only; the note still names the rest
                reach = set(own)
            note = f"One regional superintendent for {cty(own)}."
            if extra:
                note += (f" The official canvass of the March primary also lists {cty(extra)} under this office, so some ballots there "
                         "carry it too.")
            if not live:
                note += " The State Board's list shows no candidate still standing for this office."
            rid = f"2026-{jid}-regional-superintendent"
            add_race(rid, "other", "regional_superintendent_of_schools", "Regional Superintendent of Schools", jur, jid, reach, None, None, 0, 1, note)
            places[("special", jid)] = (jur, list(own), src)
            n["regions"] += 1
            for c in live:
                if not c["party"]:
                    problems.append(f"{rid}: a candidate with no party on the list")
                add_cand(rid, c["name"], c["party"].title() or "No party on the list", None, SRC_LIST)
            continue
        m = L_CIRCUIT.match(h)
        if not m:
            n["list headings not placed"] += 1
            n["list candidates not placed"] += len(off["cands"])
            gaps.append((STATE, "state", STATE, "Illinois", f"one office on the State Board's list (heading {n['list headings not placed']})",
                         "The State Board's list files this office with the circuit courts and regional superintendents, under a heading "
                         "this loader does not know, so its candidates are not shown.", glist["url"]))
            problems.append(f"a local heading on the State Board's list was not read (heading {n['list headings']})")
            continue
        circ = "COOK" if m.group("cook") else int(m.group("n"))
        sub = int(m.group("sub")) if m.group("sub") else None
        jur = "Cook County Judicial Circuit" if circ == "COOK" else f"{ordinal(circ)} Judicial Circuit"
        jid = f"{STATE}-JC{circ}"
        dwords = ("Cook Circuit" if circ == "COOK" else f"{ordinal(circ)} Circuit") + (f", {ordinal(sub)} Subcircuit" if sub else "")
        tag = f"{circ}" + (f"-S{sub}" if sub else "")
        whole = by_circuit.get(str(circ))
        if m.group("ret"):
            if not live:                                       # the judge withdrew the declaration: no question is on the ballot
                n["retention withdrawn"] += 1
                continue
            circuits_used.add(str(circ))
            rid = f"2026-{STATE}-CCRET{tag}-{letters(m.group('ret'))}"
            if any(r[0] == rid for r in races):                # two judges of one circuit under the same heading words
                rid += "-" + letters(live[0]["name"])
            if len(live) != 1 or any(c["party"] for c in live):
                problems.append(f"{rid}: a retention heading with {len(live)} names or with a party printed")
            if not whole:
                problems.append(f"{rid}: the circuit's counties are not known")
                gaps.append((STATE, "race", rid, jur, "the counties of this circuit",
                             "The counties of this judicial circuit could not be read from the Circuit Courts Act today, so the question is "
                             "listed with the courts but not under its counties.", ACT_URL))
            add_race(rid, "court", "circuit_court_retention", "Judge of the Circuit Court (retention)", jur, jid, whole, dwords, None, 0, 0,
                     RETAIN_NOTE + RETAIN_CIRCUIT)
            n["retention"] += 1
            for c in live:
                add_cand(rid, c["name"], None, None, SRC_LIST, inc=1, note=RETAIN_CAND)
                if circ == "COOK":
                    court_names["retention"].add(letters(c["name"]))
            continue
        who = m.group("vac")
        key = letters(who)
        fit = [s for s in canv["circuits"] if s["circuit"] == circ and s["sub"] == sub and s["who"] and letters(s["who"]).endswith(key)]
        sec = fit[0] if len(fit) == 1 else None
        rid = f"2026-{STATE}-CC{tag}-{key}"
        circuits_used.add(str(circ))
        if sec:
            sec["used"] += 1
            seat = f"{tail_words(sec['who'], key) or IL.shown(who)} vacancy"
            note = (f"To fill the vacancy of the Hon. {sec['who']}." if sec["kind"] == "vacancy" else
                    f"A circuit judgeship converted from the associate judgeship of {sec['who']}.")
            cids = list(sec["counties"])
            if sub:
                note += f" Elected by the voters of the {ordinal(sub)} Subcircuit alone; the March primary's canvass counts its votes in {cty(cids)}."
                if whole and not set(cids) <= set(whole):
                    problems.append(f"{rid}: the canvass's counties for the subcircuit are not all in the circuit")
            elif sec["resident"]:
                note += (f" A resident judgeship of {name_of[sec['resident']]} County: the March primary's canvass counts its votes in that "
                         "county alone.")
            else:
                note += " Elected by the voters of the whole circuit."
                if whole and set(cids) != set(whole):
                    problems.append(f"{rid}: the canvass's counties for the circuit are not the Circuit Courts Act's")
        else:
            seat = f"{IL.shown(who)} vacancy"
            note = f"The State Board's list files this seat as the {IL.shown(who)} vacancy."
            cids = list(whole or [])
            problems.append(f"{rid}: {len(fit)} sections of the March primary's canvass fit this vacancy; its counties are the whole circuit's")
            if sub:
                note += " The subcircuit is a part of the circuit; which of the circuit's counties it reaches is not in the record read here."
        if not live:
            note += " The State Board's list shows no candidate still standing for this seat."
        add_race(rid, "court", "circuit_court", "Judge of the Circuit Court", jur, jid, cids, dwords, seat, 0, 1, note)
        n["vacancies"] += 1
        for c in live:
            if not c["party"]:
                problems.append(f"{rid}: a candidate with no party on the list")
            add_cand(rid, c["name"], c["party"].title() or "No party on the list", None, SRC_LIST)
            if circ == "COOK":
                court_names["vacancy"].add(letters(c["name"]))
    for kind, label in (("regions", "regional superintendent"), ("circuits", "circuit judge")):
        loose = sum(1 for s in canv[kind] if s["used"] != 1)
        if loose:
            problems.append(f"{loose} {label} sections of the March primary's canvass are not matched to exactly one heading of the November list")
    for c in sorted(circuits_used, key=lambda x: (x != "COOK", int(x) if x != "COOK" else 0)):
        places[("judicial", f"{STATE}-JC{c}")] = ("Cook County Judicial Circuit" if c == "COOK" else f"{ordinal(int(c))} Judicial Circuit",
                                                 list(by_circuit.get(c) or []),
                                                 SRC_ACT if act and c in act["circuits"] else SRC_CANVASS if c in by_circuit else SRC_LIST)
    list_stored = len(cands)

    # ------------------------------------------------- 2. Cook County: the Clerk's list, and the Chicago Board's beside it
    clerk = cook_list(folder, say, refresh)
    board = chicago_list(folder, say, refresh)
    PARTY_WORDS = dict(PARTY_COOK)

    def clerk_cands(c):
        """[(ballot number or None, name, party words or None for a nonpartisan office)]. A line that reads "No Candidate"
        is the Clerk's way of saying nobody filed: it is counted, not stored."""
        out = []
        for k in c["cands"]:
            code = k["party"]
            if NO_CANDIDATE.match(k["name"]):
                clerk_n["no candidate lines"] += 1
                continue
            if code not in PARTY_WORDS:
                problems.append(f"the Clerk's list prints a party code this loader does not know for contest {c['race']}; shown as printed")
            out.append((int(k["num"]) if k["num"].isdigit() else None, k["name"], None if code == "NON" else PARTY_WORDS.get(code, code)))
        return out

    def board_cands(c):
        return [(k["num"], k["name"], None if k["party"] == "Nonpartisan" else k["party"]) for k in c["cands"]
                if not CHI_OFF.search(k["status"]) and not NO_CANDIDATE.match(k["name"])]

    def same(a, b):
        f = lambda rows_: sorted((x[0] or 0, letters(x[1]), x[2] or "") for x in rows_)
        return f(a) == f(b)

    def ranks(rows_):
        nums = [x[0] for x in rows_]
        if None in nums or len(set(nums)) != len(nums):
            return {}
        return {num: k for k, num in enumerate(sorted(nums), start=1)}

    board_by, board_n = {}, collections.Counter()
    if board:
        for c in board["contests"]:
            key = chicago_key(c["heading"])
            board_n["contests"] += 1
            board_n["lines"] += len(c["cands"])
            board_n["off"] += sum(1 for k in c["cands"] if CHI_OFF.search(k["status"]))
            board_n["status not known"] += sum(1 for k in c["cands"] if k["status"] != "Candidate" and not CHI_OFF.search(k["status"]))
            board_n["write-in lines"] += int(c["write_in_line"])
            if key is None:
                board_n["not known"] += 1
                gaps.append((STATE, "county", cook, "Cook County", f"one contest on the Chicago Board's list (contest {board_n['contests']})",
                             "The Chicago Board of Election Commissioners' list carries a contest under a heading this loader does not know, so "
                             "it is not shown.", board["url"]))
                continue
            board_n[key[0]] += 1
            board_n[key[0] + " lines"] += len(c["cands"])
            if key[0] not in ("state", "judge"):
                if key in board_by:
                    problems.append(f"the Chicago Board's list carries a contest twice (contest {board_n['contests']})")
                board_by[key] = c
        if board_n["status not known"]:
            problems.append(f"the Chicago Board's list marks {board_n['status not known']} candidates with a status this loader does not know; they are kept")

    clerk_n, twice, stored_from = collections.Counter(), 0, collections.Counter()
    if clerk:
        sanitary = collections.Counter(cook_key(c)[1] for c in clerk["contests"] if (cook_key(c) or ("",))[0] == "sanitary")
        for c in clerk["contests"]:
            key = cook_key(c)
            clerk_n["contests"] += 1
            clerk_n["lines"] += len(c["cands"])
            if key is None:
                clerk_n["not known"] += 1
                gaps.append((STATE, "county", cook, "Cook County", f"one contest on the Cook County Clerk's list (contest {clerk_n['contests']})",
                             "The Cook County Clerk's list carries a contest under a heading this loader does not know, so it is not shown.",
                             clerk["url"]))
                continue
            clerk_n[key[0]] += 1
            clerk_n[key[0] + " lines"] += len(c["cands"])
            if key[0] == "state":
                continue
            if key[0] == "judge":                              # the State Board's list is the record; this list is a second reading of Cook County's
                if "Appellate" in c["name"]:
                    clerk_n["appellate lines"] += len(c["cands"])
                    continue
                pool = court_names["retention" if c["retention"] else "vacancy"]
                clerk_n["judge lines found"] += sum(1 for k in c["cands"] if letters(k["name"]) in pool)
                clerk_n["judge lines checked"] += len(c["cands"])
                continue
            rows_ = clerk_cands(c)
            partisan = int(key[0] != "sanitary") if not rows_ else 0 if all(x[2] is None for x in rows_) else 1
            vote = int(c["vote"]) if c["vote"].isdigit() else 1
            note, district, seat, special, order_ok = [], None, None, 0, True
            if key[0] == "county":
                kind, level, office = key[1], "county", COUNTY_OFFICE[key[1]]
                jur, jid, cids, rid = "Cook County", cook, [cook], f"2026-{STATE}-{cook}-{key[1].replace('_', '-')}"
            elif key[0] in ("commissioner", "review"):
                kind, office = ("county_commissioner", "County Commissioner") if key[0] == "commissioner" else ("board_of_review", "Commissioner of the Board of Review")
                level, district = "county", str(key[1])
                jur, jid, cids, rid = "Cook County", cook, [cook], f"2026-{STATE}-{cook}-{kind.replace('_', '-')}-{key[1]}"
                if key[0] == "review" and c["term_shown"] and c["term"].isdigit():
                    note.append(f"Elected for a {c['term']}-year term.")
            elif key[0] == "mwrd":
                level, kind, office = "other", "sanitary_board", "Commissioner of the Metropolitan Water Reclamation District"
                jur = c["name"]
                jid, cids = f"{STATE}-X-{cook[2:]}-{slug(jur)}", [cook]
                special = int(key[1] == "unexpired")
                seat = f"Unexpired {key[2]}-year term" if special else f"{key[2]}-year term"
                rid = f"2026-{jid}-sanitary-board-{slug(seat)}" + ("-S" if special else "")
                if special:
                    note.append("An election for the rest of an unexpired term.")
                places[("special", jid)] = (jur, [cook], SRC_COOK)
            elif key[0] == "sanitary":
                level, kind, office = "other", "sanitary_board", "Sanitary District Trustee"
                jur = IL.shown(key[1]) if key[1] == key[1].upper() else key[1]
                jid, cids = f"{STATE}-X-{cook[2:]}-{slug(jur)}", [cook]
                if sanitary[key[1]] > 1:                       # two contests for one board: the terms tell them apart
                    seat = f"{key[2]}-year term"
                rid = f"2026-{jid}-sanitary-board" + (f"-{slug(seat)}" if seat else "")
                places[("special", jid)] = (jur, [cook], SRC_COOK)
            else:                                              # a neighbouring one-county region's superintendent, on some Cook County ballots
                home = fips(key[1])
                if home is None or home == cook:
                    clerk_n["not known"] += 1
                    gaps.append((STATE, "county", cook, "Cook County", f"one contest on the Cook County Clerk's list (contest {clerk_n['contests']})",
                                 "The Cook County Clerk's list carries a regional superintendent contest whose region this loader could not "
                                 "place, so it is not shown.", clerk["url"]))
                    continue
                level, kind, office = "other", "regional_superintendent_of_schools", "Regional Superintendent of Schools"
                jur = f"{name_of[home]} County Regional Office of Education"
                jid, cids, order_ok = f"{STATE}-X-roe-{slug(name_of[home])}", [cook, home], False
                rid = f"2026-{jid}-regional-superintendent"
                note.append(f"The regional superintendent for {name_of[home]} County, a region of one county. Read from the Cook County Clerk's list, "
                            f"which carries the contest for the part of Cook County that votes on it; the {name_of[home]} County Clerk publishes the "
                            "list for the rest of the region. The Cook list's ballot numbers are those of Cook County's own ballots, so no ballot "
                            "order is given here.")
                if ("special", jid) in places:
                    problems.append(f"{rid}: the region is on the State Board's list too")
                    continue
                places[("special", jid)] = (jur, [home], SRC_COOK)
            if vote > 1:
                note.insert(0, f"Voters choose {vote}.")
            other = board_by.get(key)
            if other is not None:
                if other["write_in_line"]:
                    note.append(WRITE_IN_LINE)
                if same(rows_, board_cands(other)):
                    twice += 1
                else:
                    order_ok = False
                    problems.append(f"{rid}: the Cook County Clerk's list and the Chicago Board's do not agree on the candidates, their parties or their "
                                    "ballot numbers; the Clerk's are shown, without a ballot order")
                board_by[key] = None                           # read
            if not rows_:
                note.append("The Cook County Clerk's list shows no candidate for this contest.")
            rank = ranks(rows_) if order_ok else {}
            add_race(rid, level, kind, office, jur, jid, cids, district, seat, special, partisan, " ".join(note))
            before = len(cands)
            for num, name, party in rows_:
                add_cand(rid, name, None if not partisan else (party or "No party on the list"), rank.get(num), SRC_COOK)
            stored_from["clerk"] += len(cands) - before
            stored_from["clerk contests"] += 1
        if clerk_n["judge lines found"] != clerk_n["judge lines checked"]:
            problems.append(f"the Cook County Clerk's list names {clerk_n['judge lines checked']} circuit judges; {clerk_n['judge lines found']} of them "
                            "are on the State Board's list under the same contest kind")
        if not clerk["second"].get("done", True):
            problems.append("the Cook County Clerk's list could not be read a second time, party by party; the whole list stands alone")
        elif not clerk["second"]["agrees"]:
            problems.append(f"the Cook County Clerk's list read party by party differs from the whole list in {clerk['second']['differ']} candidate lines")
    else:
        gaps.append((STATE, "county", cook, "Cook County", "county offices, sanitary districts and the Metropolitan Water Reclamation District",
                     "The Cook County Clerk's contest list could not be read when this was loaded, so the county's own offices and districts are "
                     "not shown yet.", COOK_URL))

    if board:
        left = {k: c for k, c in board_by.items() if c is not None}
        for key, c in left.items():
            if key[0] != "boe":
                if clerk:                                      # on the Board's list but not on the Clerk's
                    board_n["alone"] += 1
                    problems.append(f"the Chicago Board's list carries a county contest the Cook County Clerk's does not ({key[0]})")
                    gaps.append((STATE, "county", cook, "Cook County", f"one county contest on the Chicago Board's list alone (number {board_n['alone']})",
                                 "The Chicago Board of Election Commissioners' list carries a county contest that the Cook County Clerk's list "
                                 "does not, so it is not shown until the two agree.", board["url"]))
                continue
            rows_ = board_cands(c)
            jur = "Chicago Board of Education"
            jid = f"{STATE}-S-{cook[2:]}-{slug(jur)}"
            places[("school", jid)] = (jur, [cook], SRC_CHI)
            office = "Member of the Chicago Board of Education" if key[1] else "President of the Chicago Board of Education"
            rid = f"2026-{jid}-school-board-" + (f"subdistrict-{key[1].lower()}" if key[1] else "president")
            if any(x[2] is not None for x in rows_):
                problems.append(f"{rid}: the Board's list prints a party for a Board of Education candidate; the office is nonpartisan by law")
            vm = re.fullmatch(r"Vote for (?:One|not more than (\w+))", c["vote"])
            note = [] if vm and not vm.group(1) else [f"The Board's list says: {c['vote']}."] if c["vote"] else []
            if not rows_:
                note.append("The Chicago Board's list shows no candidate for this contest.")
            if c["write_in_line"]:
                note.append(WRITE_IN_LINE)
            add_race(rid, "school", "school_board", office, jur, jid, [cook], f"Subdistrict {key[1]}" if key[1] else None, None, 0, 0, " ".join(note))
            rank = ranks(rows_)
            before = len(cands)
            for num, name, _party in rows_:
                add_cand(rid, name, None, rank.get(num), SRC_CHI)
            stored_from["board"] += len(cands) - before
            stored_from["board contests"] += 1
        # the Board's judges: a second reading of Cook County's, as the Clerk's list is
        for c in board["contests"]:
            if chicago_key(c["heading"]) == ("judge",) and "Appellate" not in c["heading"]:
                board_n["judge lines checked"] += len(c["cands"])
                board_n["judge lines found"] += sum(1 for k in c["cands"] if letters(k["name"]) in court_names["vacancy"])
        for r in board["retention"]:
            if "Circuit" in r["court"]:
                board_n["retention checked"] += 1
                board_n["retention found"] += int(letters(r["name"]) in court_names["retention"])
        if board_n["judge lines found"] != board_n["judge lines checked"] or board_n["retention found"] != board_n["retention checked"]:
            problems.append(f"the Chicago Board's list names {board_n['judge lines checked']} candidates for circuit judge and {board_n['retention checked']} "
                            f"circuit judges for retention; {board_n['judge lines found']} and {board_n['retention found']} are on the State Board's list")
        if board["odd"]:
            problems.append(f"the Chicago Board's list has rows that were not read: {board['odd']}")
        b2 = board.get("second") or {"lines": 0, "alike": 0}
        if b2["lines"] != board_n["lines"] or b2["alike"] != b2["lines"]:
            problems.append(f"the Chicago Board's list: {b2['alike']} of {b2['lines']} candidate rows read the same by columns and as whole lines "
                            f"({board_n['lines']} rows stored)")
    else:
        gaps.append((STATE, "county", cook, "Cook County", "the Chicago Board of Education",
                     "The Chicago Board of Election Commissioners' candidate list could not be read when this was loaded, so the Chicago Board of "
                     "Education contests are not shown yet.", CHI_PAGE))

    # --------------------------------------------------------------------------- 3. every other county: named as a gap
    auth = election_authorities(folder, say, refresh)
    city_of = {}
    if auth:
        for label in auth["names"]:
            m = re.fullmatch(r"CITY OF (.+)", label.strip(), re.I)
            if not m:
                continue
            home = fips(CITY_BOARDS.get(m.group(1).upper(), ""))
            if home is None:
                problems.append("the State Board's list of election authorities names a city this loader does not know")
            elif home != cook:
                city_of[home] = m.group(1).title()
    for rid, k in sorted(hidden.items()):                      # a name the official list holds that could not be shown: said, never dropped silently
        gaps.append((STATE, "race", rid, None, f"{k} candidate name{'s' if k != 1 else ''}",
                     "The official list's cell for a candidate of this contest held something that reads like contact details, so the candidate "
                     "is not shown here.", None))
    for f in sorted(name_of):
        if f == cook:
            continue
        reason = GAP_REASON
        if f in city_of:
            reason += f" The city of {city_of[f]} has its own board of election commissioners, which publishes the ballots for the city."
        gaps.append((STATE, "county", f, f"{name_of[f]} County", GAP_WHAT, reason, AUTH_URL))
    n_gap = sum(1 for g in gaps if g[1] == "county" and g[4] == GAP_WHAT)

    # ------------------------------------------------------------------------------------------------- sources and notes
    by_kind = collections.Counter(r[3] for r in races)
    if clerk:
        s2 = clerk["second"]
        sources.append((SRC_COOK, STATE, "official candidate list", "Cook County Clerk",
                        "Contests and candidates, General Election of November 3, 2026 (the list behind the Clerk's candidate pages)", clerk["url"], "",
                        clerk["fetched"], clerk["sha256"], stored_from["clerk"],
                        f"Read: each contest's office, district words, vacancy words, term, votes allowed and retention mark; each candidate's name, "
                        f"party code and ballot number. The file has no contact fields. It wraps a cell that holds a comma in single quotes and "
                        f"writes a quotation mark as two apostrophes; names are shown without the wrapper and with the quotation marks, as the "
                        f"Chicago Board's list prints them. {clerk_n['contests']} contests, {clerk_n['lines']} candidate "
                        f"lines: {stored_from['clerk contests']} county and local contests with {stored_from['clerk']} candidates are stored from it "
                        f"(lines of theirs that only say no candidate filed: {clerk_n['no candidate lines']}); "
                        f"{clerk_n['judge']} judges' contests are the State Board's ({clerk_n['judge lines found']} of {clerk_n['judge lines checked']} "
                        f"circuit names found on its list, {clerk_n['appellate lines']} appellate names left to the state part); {clerk_n['state']} federal "
                        f"and state contests with {clerk_n['state lines']} lines are only counted; {clerk_n['not known']} contests not known. "
                        + ("The second reading, party by party, could not be finished when this was fetched. " if not s2.get("done", True) else
                           f"Read twice, whole and party by party ({', '.join(f'{k} {v}' for k, v in sorted(s2['by_party'].items()))}): "
                           + ("the two readings agree line for line. " if s2["agrees"] else f"the two readings differ in {s2['differ']} lines. "))
                        + f"{twice} of the stored contests are also on the Chicago Board's list with the same names, parties and ballot numbers. "
                        "Ballot order is a candidate's place by ballot number within the contest. Cells set aside as contact-like: "
                        f"{clerk['blanked']}."))
    if board:
        asof = ""
        try:
            asof = dt.datetime.strptime(board["asof"], "%m/%d/%Y").date().isoformat() if board["asof"] else ""
        except ValueError:
            pass
        sources.append((SRC_CHI, STATE, "candidate list", "Chicago Board of Election Commissioners",
                        f"{board['title']}" + (f" (status as of {board['asof']})" if board["asof"] else ""), board["url"], asof, board["fetched"],
                        board["sha256"], stored_from["board"],
                        ("The Board heads the file as an unofficial candidate list that is updated when filings change. " if board["unofficial"] else "")
                        + f"A PDF of {board['pages']} pages, read in memory and not kept. Read: contest headings, votes allowed, and each candidate's "
                        f"ballot number, name, party and status; on the retention pages each judge's court, name and Yes and No numbers. The file "
                        f"has no contact columns. Each candidate row was read twice, by its columns and as a whole line: "
                        f"{(board.get('second') or {}).get('alike', 0)} of {(board.get('second') or {}).get('lines', 0)} alike. "
                        f"{board_n['contests']} contests, {board_n['lines']} candidate lines: the Chicago Board of Education's "
                        f"{stored_from['board contests']} contests with {stored_from['board']} candidates are stored from it; {twice} county and district "
                        f"contests are a second reading of the Cook County Clerk's; {board_n['judge']} judges' contests and {len(board['retention'])} "
                        f"retention judges are the State Board's ({board_n['judge lines found']} of {board_n['judge lines checked']} circuit candidates and "
                        f"{board_n['retention found']} of {board_n['retention checked']} circuit retention judges found on its list); {board_n['state']} "
                        f"federal and state contests are only counted. {board_n['write-in lines']} contests carry a write-in line with no name; "
                        f"{board_n['off']} candidates marked withdrawn or removed are left off. The {board['question_rows']} rows of ballot questions "
                        f"on the last pages are not read. Cells set aside as contact-like: {board['blanked']}."))
        sources.append((SRC_CHI_PAGE, STATE, "web page", "Chicago Board of Election Commissioners", "Candidates (the page that links the candidate list)",
                        board["page"], "", board["fetched"], board["page_sha256"], 1,
                        "Read only for the address of the candidate list for November 3, 2026: the one link to the Board's own file store whose "
                        "words name that list. Nothing else on the page is read or kept."))
    if act:
        sources.append((SRC_ACT, STATE, "statute", "Illinois General Assembly",
                        "Circuit Courts Act, Section 1 (705 ILCS 35/1): judicial circuits created", ACT_URL, "", act["fetched"], act["sha256"],
                        len(act["circuits"]),
                        "The counties of each judicial circuit: where a retention question is asked (the whole circuit), and a check on the "
                        "canvass's counties for a vacancy filled by the whole circuit. A statute's text, kept whole; it has no contact details."))
    if auth:
        sources.append((SRC_AUTH, STATE, "list of election authorities", "Illinois State Board of Elections", "Election Authorities (the list of jurisdictions)",
                        AUTH_URL, "", auth["fetched"], auth["sha256"], len(auth["names"]),
                        "Only the names in the page's list of jurisdictions are kept: the 102 counties and the cities that have a board of election "
                        "commissioners of their own. The offices' addresses and telephone numbers on the page are never read."))

    n_cook_county = sum(1 for r in races if r[2] == "county")
    n_san = sum(1 for (k, i) in places if k == "special" and "sanitary-district" in i)
    n_roe_cook = sum(1 for r in races if r[3] == "regional_superintendent_of_schools") - n["regions"]
    coverage = (
        f"Illinois has no statewide list of county candidates: each of its election authorities publishes its own. Loaded here from the State Board "
        f"of Elections' candidate list: the regional superintendents of schools of the {n['regions']} regions of more than one county and the "
        f"circuit judges ({n['vacancies']} vacancies and {n['retention']} retention questions), {list_stored} candidates. "
        + (f"From the Cook County Clerk's list, in the order of its ballot numbers: Cook County's own offices ({n_cook_county} contests: the board "
           f"president, clerk, sheriff, treasurer, assessor, {by_kind['county_commissioner']} commissioners and {by_kind['board_of_review']} Board of "
           f"Review seats), the Metropolitan Water Reclamation District, {n_san} suburban sanitary districts and the regional superintendents of "
           f"{n_roe_cook} neighbouring one-county regions (these without an order: the Clerk's ballot numbers are those of Cook County's own "
           f"ballots), "
           f"{stored_from['clerk']} candidates. " if clerk else "")
        + (f"From the Chicago Board of Election Commissioners' list, which the Board calls unofficial while filings can still change: the Chicago "
           f"Board of Education ({stored_from['board contests']} contests, {stored_from['board']} candidates). " if board else "")
        + "Left out: ballot questions; write-in candidates"
        + (f" (the Chicago list marks {board_n['write-in lines']} contests with a write-in line and names no one)" if board else "")
        + f"; {n['retention withdrawn']} judges who withdrew from retention; and the county offices of the other {n_gap} counties, each named among "
        "the gaps. The State Board's list is not in ballot order, so no order is given for its contests.")
    notes = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, CALENDAR_URL),
             (STATE, "local_coverage", coverage, "The State Board of Elections' candidate list, the Cook County Clerk's contest list and the Chicago "
              "Board of Election Commissioners' candidate list, each named among the sources", None)]

    place_rows = [(k, i, nm, json.dumps(sorted(ids)) if ids else None, src) for (k, i), (nm, ids, src) in sorted(places.items())]

    # ---- the last look before anything is written: nothing that reads like contact details, by the trial check's test and the page builder's
    for table, strict, items in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in races]),
                                 ("sl_candidates", True, [(c[0], (c[3], c[4], c[14])) for c in cands]),
                                 ("sl_places", True, [(p[1], (p[2],)) for p in place_rows]),
                                 ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                                 ("sl_notes", False, [(x[1], (x[2], x[3])) for x in notes]),
                                 ("sl_sources", False, [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(reads_like_contact(t, strict) for t in texts if t):
                raise SystemExit(f"Illinois (local): a text for {table} ({ident}) reads like contact details; stopping (the text is not printed)")
    seen = collections.Counter((c[0], c[1], c[3]) for c in cands)
    if any(v > 1 for v in seen.values()):
        raise SystemExit("Illinois (local): a candidate is stored twice in one contest; stopping")
    if len({(g[1], g[2], g[4]) for g in gaps}) != len(gaps):
        raise SystemExit("Illinois (local): two gaps share scope, place and words; stopping")

    n["list stored"] = list_stored
    return {"races": races, "cands": cands, "places": place_rows, "sources": sources, "gaps": gaps, "notes": notes, "problems": problems,
            "counts": n, "clerk": clerk_n, "board": board_n, "stored_from": stored_from, "twice": twice, "by_kind": by_kind,
            "have": {"clerk": bool(clerk), "board": bool(board), "act": bool(act), "auth": bool(auth)}, "gap_counties": n_gap,
            "second": clerk["second"] if clerk else None, "board_second": (board.get("second") or {"lines": 0, "alike": 0}) if board else None,
            "court_names": {k: len(v) for k, v in court_names.items()}}


# ------------------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, local_cache=None, refresh=False):
    net.patient_lookups()
    folder = os.path.join(cache, "il")
    os.makedirs(folder, exist_ok=True)
    report = []

    lpath = candidate_list(folder, cache, say)
    glist = json.load(open(lpath, encoding="utf-8"))
    if "11/ 3/2026" not in glist["election"].replace("11/3/2026", "11/ 3/2026"):
        raise SystemExit(f"Illinois (state races): the candidate list is not the November 3, 2026 General Election's ({glist['election']!r})")
    for k, v in glist["odd"].items():
        if v:
            report.append(f"candidate list: {v} {k}")
    cpath = os.path.join(folder, "il_2026_primary_official_canvass.pdf")
    net.download(IL.CANVASS_URL, cpath, max_age_days=90, say=say)
    if not open(cpath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Illinois (state races): the Official Canvass on disk is not a PDF; read the Downloadable Vote Totals page again")
    sections, cproblems = canvass(cpath)
    report += [f"canvass: {p}" for p in cproblems]
    try:
        rpath = results_pages(folder, say)
        rpage = json.load(open(rpath, encoding="utf-8"))
    except (OSError, ValueError) as e:
        say(f"      the Election Results pages were not read ({e}); names and totals are the canvass's own")
        rpath, rpage = None, None
    legs, offs = roster(roster_db)
    counties = county_codes(COUNTY_ZIP)
    if len(counties) != COUNTIES:
        report.append(f"the Census county file has {len(counties)} Illinois counties, not {COUNTIES}")

    # ---- the races on the list
    races, listed, skipped, unknown = {}, {}, {"federal": 0, "local": 0}, []
    local_offices = []                            # the circuit court and regional superintendent headings: the local part reads them
    for off in glist["offices"]:
        kind, info = classify_heading(off["heading"])
        if kind in skipped:
            skipped[kind] += 1
            if kind == "local":
                local_offices.append(off)
            continue
        if kind == "unknown":
            unknown.append(off["heading"])
            continue
        rid = info["race_id"]
        if rid in races:
            raise SystemExit(f"Illinois (state races): {off['heading']} is on the list twice")
        races[rid] = dict(info, heading=off["heading"])
        listed[rid] = off["cands"]
    if unknown:
        report.append(f"list headings not read (not loaded): {unknown}")
    # a race in the primary but not on the November list (nobody left standing) is still on the ballot
    for rid in sections:
        if rid not in races:
            m = re.fullmatch(rf"2026-{STATE}-(SS|SH)(\d+)", rid)
            if m:
                races[rid] = {"race_id": rid, "level": "legislature", "office_kind": "state_senate" if m.group(1) == "SS" else "state_house",
                              "district": m.group(2), "heading": None}
                listed[rid] = []
            else:
                report.append(f"{rid} is in the primary canvass but not on the November list")

    nsen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    nhouse = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    csen = sorted(int(k.rsplit("SS", 1)[1]) for k in sections if re.fullmatch(rf"2026-{STATE}-SS\d+", k))
    if nsen != csen:
        report.append(f"the Senate districts on the list {nsen} are not those in the primary canvass {csen}")
    if len(nsen) != 39:
        report.append(f"{len(nsen)} Senate districts on the list, not 39")
    if nhouse != list(range(1, 119)):
        report.append(f"the list's House districts are not 1 to 118: {len(nhouse)} listed")
    for suffix, *_ in STATEWIDE.values():
        if f"2026-{STATE}-{suffix}" not in races:
            report.append(f"2026-{STATE}-{suffix} is not on the list")
    if rpage:
        rsen = sorted(int(k.rsplit("SS", 1)[1]) for k in rpage["rows"] if re.fullmatch(rf"2026-{STATE}-SS\d+", k))
        if rsen != nsen:
            report.append(f"the Election Results page's Senate districts {rsen} are not the list's")

    def identify(race, name, party):
        """(incumbent, state_member_id, note) for one listed name."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        pool = [p for p in legs if (p["party"] or "") == (party or "") and person_fits(name, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            p = pool[0]
            return 0, p["id"], f"Serves today in the Illinois {p['chamber']}, District {int(p['district'])}."
        return 0, None, None

    # ---- race rows: holders, jurisdictions, counties
    places, county_seen = {}, {}
    for rid, r in races.items():
        cids = []
        for cname in sorted((sections.get(rid) or {}).get("counties", set())):
            hit = counties.get(re.sub(r"[^A-Z]", "", cname.upper()))
            if not hit:
                report.append(f"{rid}: the canvass's county {cname!r} is not in the Census county file")
                continue
            cids.append(hit[0])
            county_seen[hit[0]] = hit[1]
        cids = sorted(cids)
        note, holder, special = [], None, 0
        if r["level"] == "statewide":
            heading = next(h for h, v in STATEWIDE.items() if v[0] == rid.rsplit("-", 1)[1])
            _suf, _kind, office, rkey = STATEWIDE[heading]
            holder = offs.get(rkey) if rkey else None
            if rkey is None:
                note.append(NO_ROSTER)
            if r["office_kind"] == "governor":
                note.append(GOV_NOTE)
            jur, jid, district, partisan = "Illinois", STATE, None, 1
            cids = None
        elif r["level"] == "legislature":
            chamber = "Senate" if r["office_kind"] == "state_senate" else "House"
            office = "State Senator" if chamber == "Senate" else "Representative in the General Assembly"
            hs = [p for p in legs if p["chamber"] == chamber and str(p["district"]).lstrip("0") == r["district"]]
            holder = hs[0] if len(hs) == 1 else None
            if holder is None:
                report.append(f"{rid}: {len(hs)} sitting members in the roster for this seat")
                note.append("The roster shows no sitting member for this seat.")
            if chamber == "Senate":
                note.append(SENATE_NOTE)
            district, partisan = r["district"], 1
            jur, jid = f"{chamber} District {district}", f"{STATE}-{district}"
            places[("senate" if chamber == "Senate" else "house", jid)] = (jur, cids)
        else:
            court = "Appellate Court" if r["court"] == "APPELLATE" else "Supreme Court"
            d = int(r["district"])
            district, partisan = str(d), 0 if r["retain"] else 1
            jur = f"{ORDINAL_WORD.get(d, ordinal(d))} {'Appellate' if r['court'] == 'APPELLATE' else 'Judicial'} District"
            jid = f"{STATE}-{'APP' if r['court'] == 'APPELLATE' else 'SC'}{d}"
            vac = (sections.get(rid) or {}).get("vacancy")
            if r["retain"]:
                office = f"Judge of the {court} (retention)"
                note.append(RETAIN_NOTE)
            else:
                office = f"Judge of the {court}"
                note.append(f"To fill the vacancy of the Hon. {vac}." if vac else
                            f"The State Board lists this seat as the {r['who'].title()} vacancy.")
        r.update(state=STATE, office=office, jurisdiction=jur, jurisdiction_id=jid, county_ids=json.dumps(cids) if cids else None,
                 district=district, seat=None, special=special, partisan=partisan, holder_id=holder["id"] if holder else None,
                 holder_name=holder["full"] if holder else None, holder_party=holder["party"] if holder else None,
                 election_date=GENERAL, note=" ".join(note) or None, _holder=holder)
    by_district = {}                              # a retention question's district counties, from a vacancy in the same district
    for r in races.values():
        if r["level"] == "court" and r["county_ids"]:
            by_district.setdefault(r["jurisdiction_id"], set()).update(json.loads(r["county_ids"]))
    for r in races.values():
        if r["level"] == "court":
            got = sorted(by_district.get(r["jurisdiction_id"], ()))
            if got and not r["county_ids"]:
                r["county_ids"] = json.dumps(got)
            places[("appellate_district" if r["court"] == "APPELLATE" else "judicial_district", r["jurisdiction_id"])] = (r["jurisdiction"], got or None)

    # ---- November candidates
    general, gone, parties, mismatch, mates = [], [], {}, [], {}
    for rid, cands in listed.items():
        race = races[rid]
        is_gov = race["office_kind"] == "governor"
        tickets = []
        for c in cands:
            if is_gov and not c["party"]:                      # the running mate's row
                if not tickets or tickets[-1]["mate"]:
                    mismatch.append(f"{rid}: a row with no party that does not follow a candidate for Governor")
                    continue
                fam = IL.letters(name_parts(tickets[-1]["name"])[1])
                mm = re.fullmatch(r"(.+?)\s*\(([^)]*)\)", c["name"])      # Christian Mitchell (Pritzker): the ticket's surname added
                tickets[-1]["mate"] = mm.group(1) if mm and IL.letters(mm.group(2)) == fam else c["name"]
                if c["status"]:
                    tickets[-1]["status"] = tickets[-1]["status"] or c["status"]
                continue
            tickets.append(dict(c, mate=None))
        for c in tickets:
            if is_gov and not c["mate"] and not c["status"]:
                mismatch.append(f"{rid}: {c['name']} has no running mate on the list")
            if race["level"] == "court" and race["retain"]:
                if c["party"]:
                    mismatch.append(f"{rid}: a retention candidate with a party printed")
                party, pcode = "Nonpartisan office", "N"
            else:
                if not c["party"]:
                    mismatch.append(f"{rid}: {c['name']} has no party on the list")
                party = c["party"].title()
                pcode = party_code(party)
            if c["status"]:
                gone.append((rid, c["name"], c["status"]))
                continue
            parties[party] = parties.get(party, 0) + 1
            notes = []
            if race["level"] == "court" and race["retain"]:
                inc, mid, n2 = 1, None, "The judge whose retention is on the ballot."
            else:
                inc, mid, n2 = identify(race, c["name"], party)
            if is_gov and c["mate"]:
                mates[(rid, party)] = c["mate"]
                notes.append(f"Running mate for Lieutenant Governor: {c['mate']}.")
            if n2:
                notes.append(n2)
            general.append([rid, "general", GENERAL, c["name"], party, pcode, None, inc, 0, None, None, None, mid, SRC_LIST,
                            " ".join(notes) or None])
    report += mismatch
    for rid in races:
        if not any(g[0] == rid for g in general):
            report.append(f"{rid}: no candidates on the November list")
    listed_count = sum(1 for rid, cs in listed.items() for c in cs if not (races[rid]["office_kind"] == "governor" and not c["party"]))
    if listed_count - len(gone) != len(general):
        report.append(f"count check: {listed_count} candidates listed, {len(gone)} removed or withdrawn, {len(general)} stored")

    # ---- the primary: canvass checked against the results pages; fields with two or more printed candidates
    respelled, unmatched = 0, []
    if rpage:
        theirs_all = rpage["rows"]
        for rid, s in sections.items():
            theirs = theirs_all.get(rid, [])
            if len(theirs) != len(s["cands"]):
                unmatched.append(f"{rid}: the canvass lists {len(s['cands'])} candidates, the results page {len(theirs)}")
                continue
            for c in s["cands"]:
                hit = [x for x in theirs if IL.letters(x[0]) == IL.letters(c["name"])]
                word = hit[0][1].upper() if len(hit) == 1 else ""
                if len(hit) != 1 or hit[0][2] != c["votes"] or not word.startswith(c["code"][:3]):
                    unmatched.append(f"{rid}: {c['name']} {c['code']} {c['votes']:,} is not on the results page as printed")
                    continue
                if hit[0][0] != c["name"]:
                    c["name"] = hit[0][0]
                    respelled += 1
        extra = sorted(set(theirs_all) - set(sections))
        if extra:
            unmatched.append(f"on the results pages but not read from the canvass: {extra}")
    report += [f"results page: {u}" for u in unmatched]

    nominee = {}
    for g in general:
        if g[4] in PARTY_WORD.values():
            if (g[0], g[4]) in nominee:
                report.append(f"{g[0]}: two {g[4]} candidates on the November list")
            nominee[(g[0], g[4])] = g[3]
    prim, nfields, lone, upset = [], 0, [], []
    for rid, s in sorted(sections.items()):
        if rid not in races:
            continue
        race = races[rid]
        for code in sorted({c["code"] for c in s["cands"]}):
            mine = [c for c in s["cands"] if c["code"] == code]
            printed = [c for c in mine if not c["wi"]]
            won = [c for c in mine if c["won"]]
            if len(printed) < 2:
                if len(mine) > 1:
                    lone.append(f"{rid} {code}")
                continue
            if code not in PARTY_WORD:
                raise SystemExit(f"Illinois (state races): a {code} primary with a field for {rid}; its party name is not set")
            nfields += 1
            party = PARTY_WORD[code]
            total = sum(c["votes"] for c in mine)
            top = max(mine, key=lambda c: c["votes"])
            if len(won) != 1 or won[0] is not top or sum(1 for c in mine if c["votes"] == top["votes"]) > 1:
                report.append(f"{rid} {code}: the canvass's (Won) mark is not on the one top vote-getter")
            winner = won[0] if len(won) == 1 else top
            listed_name = nominee.get((rid, party))
            if listed_name and not IL.same_person(winner["name"], listed_name):
                upset.append(f"{rid} {code}: the canvass's winner is {winner['name']}; the November list names {listed_name}")
            for c in mine:
                notes = [WRITE_IN_NOTE] if c["wi"] else []
                if c is winner and listed_name and IL.same_person(c["name"], listed_name):
                    name = listed_name
                else:
                    name = IL.shown(c["name"])
                    notes.append(CAPS_NOTE)
                if c.get("mate"):
                    mate = mates.get((rid, party)) if name == listed_name else None
                    notes.append(f"Running mate for Lieutenant Governor: {mate or IL.shown(c['mate'])}.")
                if c is winner and not listed_name:
                    notes.append(IL.NOT_ON_LIST)
                elif c is winner and not IL.same_person(c["name"], listed_name):
                    notes.append(f"Won the primary; the November list names {listed_name} as the party's candidate instead.")
                inc, mid, n2 = identify(race, name, party)
                if n2:
                    notes.append(n2)
                prim.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, inc, int(c["wi"]), c["votes"],
                             round(100 * c["votes"] / total, 1) if total else None, "advanced" if c is winner else "lost",
                             mid, SRC_CANVASS, " ".join(notes) or None])
    report += [f"primary: {u}" for u in upset]

    cands = general + prim
    keys = [(c[0], c[1], c[3]) for c in cands]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise SystemExit(f"Illinois (state races): candidate rows share race, election and name: {dup}")
    for c in cands:                               # the last look: no contact detail can reach the database
        if NOT_A_NAME.search(c[3]) or NOT_A_NAME.search(c[4] or "") or (c[14] and re.search(r"@|www|\d{3}", c[14])):
            raise SystemExit(f"Illinois (state races): a stored cell for {c[0]} failed the contact-detail check (not shown)")

    # ---- write: Illinois's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(county_seen.items())]
    place_rows += [(k, i, jur, json.dumps(cids) if cids else None, SRC_CANVASS if cids else SRC_LIST) for (k, i), (jur, cids) in sorted(places.items())]
    if len(county_seen) != COUNTIES:
        report.append(f"the canvass's district tables name {len(county_seen)} counties, not {COUNTIES}")

    # ---- the county and local part (nothing here changes a state row)
    lfolder = local_cache or (LOCAL_DIR if cache == CACHE else os.path.join(cache, "il", "local"))
    local = local_level(local_offices, glist, cpath, counties, lfolder, say=say, refresh=refresh)
    clash = sorted({r[0] for r in local["races"]} & set(races))
    if clash:
        raise SystemExit(f"Illinois: a local contest shares a race id with a state race ({clash[0]}); stopping")
    clash = sorted({(p[0], p[1]) for p in local["places"]} & {(p[0], p[1]) for p in place_rows})
    if clash:
        raise SystemExit(f"Illinois: a local place shares its kind and id with a state place ({clash[0]}); stopping")
    ln = local["counts"]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executescript(EXTRA_SCHEMA)
    with con:
        # Illinois's rows only: races, candidates, sources, gaps and notes by state; places by their county codes (17...) and IL- ids
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE (kind = 'county' AND id GLOB ?) OR id LIKE ?", (f"{FIPS}[0-9][0-9][0-9]", f"{STATE}-%"))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
        src = [(SRC_LIST, STATE, "official candidate list", "Illinois State Board of Elections",
                f"Website Candidate List, General Election November 3, 2026 (all candidates as of {glist['asof']})", glist["url"],
                dt.datetime.strptime(glist["asof"], "%m/%d/%Y").date().isoformat() if glist["asof"] else "", glist["read"],
                glist["sha256"], len(general) + ln["list stored"],
                f"The Candidate List page's Print This List. Read from {'the Board' if glist['origin'] == glist['url'] else 'a copy on disk'}; "
                f"the PDF is not kept. Only office headings and each candidate's party, name and status are read; the address rows under "
                f"candidates who filed by petition are never read. State offices: {len(races)} races, {len(general)} candidates; removed or "
                f"withdrawn, left off: {len(gone)}. Circuit courts and regional superintendents of schools ({ln['list headings']} headings, "
                f"{ln['list candidates']} names): {ln['regions']} regional superintendents, {ln['vacancies']} circuit vacancies and "
                f"{ln['retention']} retention questions, {ln['list stored']} candidates stored, each in one contest; {ln['retention withdrawn']} "
                f"judges who withdrew from retention and {ln['list removed or withdrawn'] - ln['retention withdrawn']} other removed or withdrawn "
                f"candidates left off; {ln['list headings not placed']} headings not placed. Not loaded here: {skipped['federal']} federal headings "
                "(the federal pages carry them). The list is not in ballot order, so ballot_order is left empty. Party labels as printed, in "
                "ordinary capitals.")]
        src.append((SRC_CANVASS, STATE, "official results", "Illinois State Board of Elections",
                    "Official Canvass, General Primary Election, March 17, 2026 (2026GPOfficialVote.pdf, Candidate Totals)", IL.CANVASS_URL,
                    IL.made_on(cpath), mtime(cpath), sha(cpath), sum(len(s["cands"]) for s in sections.values()),
                    "Linked as \"Candidate Totals\" on the Board's Downloadable Vote Totals page (year 2026). Statewide offices, State Senator, "
                    "Representative in the General Assembly and Judge of the Appellate Court: each candidate's votes, the (Won) mark and W-I for "
                    "declared write-ins (their votes count toward a field's total); each candidate's county rows checked against the summary, and "
                    "the county rows give each district's counties. A field is a party primary with two or more printed candidates. "
                    + ("Every check holds." if not cproblems else "Did not hold: " + "; ".join(cproblems) + ".")
                    + (f" One printed candidate with write-ins beside, not fields: {', '.join(lone)}." if lone else "")
                    + " The Regional Superintendent of Schools and Judge of the Circuit Court sections are read for places only: the counties "
                    "each region's heading names, the words naming each vacancy, and the counties each contest's county tables list. No vote "
                    "of a local primary is loaded."))
        if rpage:
            src.append((SRC_RESULTS, STATE, "official results", "Illinois State Board of Elections",
                        "Election Results, 2026 General Primary: Federal / Statewide, Senate, District All, Judicial (Election Vote Totals)",
                        RESULTS_BASE + RESULT_PAGES["Senate"], "", rpage["read"], sha(rpath),
                        sum(len(v) for v in rpage["rows"].values()),
                        "Candidate, party and total votes for the state offices, kept to check the canvass's names and totals; the share "
                        f"column is not read. Names spelled as these pages spell them where the two agree letter for letter: {respelled} "
                        "respelled. " + ("Every candidate agrees." if not unmatched else "Did not agree: " + "; ".join(unmatched) + ".")))
        src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_il.sqlite",
                    "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
                    len(legs) + len(offs), "Who holds each seat today; the roster carries the Governor and the Attorney General but not "
                    "the Secretary of State, the Comptroller or the Treasurer."))
        src.append((SRC_COUNTY, STATE, "boundaries", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
                    "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "2024", mtime(COUNTY_ZIP), sha(COUNTY_ZIP),
                    len(county_seen), "Illinois's county codes (5-digit FIPS) and names, matched to the canvass's county names by their letters."))
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["sources"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    kinds = {}
    for g in general:
        kinds[races[g[0]]["office_kind"]] = kinds.get(races[g[0]]["office_kind"], 0) + 1
    nrace = {}
    for r in races.values():
        nrace[r["office_kind"]] = nrace.get(r["office_kind"], 0) + 1
    say(f"    Illinois: {len(races)} races ({len(nsen)} Senate, {len(nhouse)} House, "
        f"{sum(1 for r in races.values() if r['level'] == 'statewide')} statewide, {sum(1 for r in races.values() if r['level'] == 'court')} "
        f"Appellate Court); {len(general)} candidates on the November list ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))}; "
        f"{len(gone)} removed or withdrawn left off); {nfields} primary fields, {len(prim)} primary rows, official votes")
    say(f"      parties on the November list: {dict(sorted(parties.items(), key=lambda x: -x[1]))}")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")

    # ---- what the local part loaded, and how its counts reconcile
    lk, ck, bk, sf = local["by_kind"], local["clerk"], local["board"], local["stored_from"]
    lr = collections.Counter(r[2] for r in local["races"])
    say(f"    Illinois, county and local: {len(local['races'])} contests ({', '.join(f'{k} {v}' for k, v in sorted(lr.items()))}), "
        f"{len(local['cands'])} candidates; {local['gap_counties']} counties named as gaps")
    say(f"      office kinds: {', '.join(f'{k} {v}' for k, v in sorted(lk.items()))}")
    say(f"      check: the State Board's list: {ln['list headings']} local headings and {ln['list candidates']} names = {ln['regions']} regions + "
        f"{ln['vacancies']} vacancies + {ln['retention']} retention questions + {ln['retention withdrawn']} retention questions withdrawn + "
        f"{ln['list headings not placed']} not placed; {ln['list stored']} candidates stored + {ln['list removed or withdrawn']} removed or withdrawn + "
        f"{ln['list candidates not placed']} not placed + {ln['names not shown']} not shown")
    if local["have"]["clerk"]:
        s2 = local["second"]
        say(f"      check: the Cook County Clerk's list: {ck['contests']} contests, {ck['lines']} lines = {sf['clerk contests']} stored contests "
            f"({sf['clerk']} candidates; lines that only say no candidate filed: {ck['no candidate lines']}) + {ck['judge']} judges' contests "
            f"({ck['judge lines checked']} circuit names, {ck['judge lines found']} on the State "
            f"Board's list; {ck['appellate lines']} appellate) + {ck['state']} federal and state contests ({ck['state lines']} lines) + {ck['not known']} "
            f"not known; read again party by party: "
            + (f"{s2['lines']} lines, {'the same' if s2['agrees'] else str(s2['differ']) + ' differ'}" if s2.get("done", True) else "not finished"))
    if local["have"]["board"]:
        say(f"      check: the Chicago Board's list: {bk['contests']} contests, {bk['lines']} lines = {sf['board contests']} Board of Education contests "
            f"({sf['board']} candidates) + {local['twice']} contests also on the Clerk's list and alike + {bk['judge']} judges' contests "
            f"({bk['judge lines checked']} circuit names, {bk['judge lines found']} on the State Board's list) + {bk['state']} federal and state "
            f"contests + {bk['not known']} not known; {bk['retention checked']} circuit retention judges, {bk['retention found']} on the State Board's "
            f"list; {bk['write-in lines']} write-in lines; {bk['off']} withdrawn or removed; rows read by columns and as whole lines: "
            f"{local['board_second']['alike']} of {local['board_second']['lines']} alike")
    for p in local["problems"]:
        say(f"      CHECK {p}")
    return len(general)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--refresh"]
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_il <database> [--refresh]")
    load(args[0], refresh="--refresh" in sys.argv[1:])
