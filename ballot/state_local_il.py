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

    python -m ballot.state_local_il <path to a test database>
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from urllib.error import HTTPError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ballot.pdftext as P  # noqa: E402
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


# ------------------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
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
    for off in glist["offices"]:
        kind, info = classify_heading(off["heading"])
        if kind in skipped:
            skipped[kind] += 1
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
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE (kind = 'county' AND id GLOB ?) OR id LIKE ?", (f"{FIPS}[0-9][0-9][0-9]", f"{STATE}-%"))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        src = [(SRC_LIST, STATE, "official candidate list", "Illinois State Board of Elections",
                f"Website Candidate List, General Election November 3, 2026 (all candidates as of {glist['asof']})", glist["url"],
                dt.datetime.strptime(glist["asof"], "%m/%d/%Y").date().isoformat() if glist["asof"] else "", glist["read"],
                glist["sha256"], len(general),
                f"The Candidate List page ({IL.PAGE}), Print This List. Read from {glist['origin'] if glist['origin'] != glist['url'] else 'the Board'}; "
                f"the PDF is not kept. Only office headings and each candidate's party, name and status are read. State offices: "
                f"{len(races)} races, {len(general)} candidates; removed or withdrawn, left off: {len(gone)}. Not loaded here: "
                f"{skipped['federal']} federal headings (the federal pages carry them) and {skipped['local']} circuit court and regional "
                "superintendent headings. The list is not in ballot order, so ballot_order is left empty. Party labels as printed, "
                "in ordinary capitals.")]
        src.append((SRC_CANVASS, STATE, "official results", "Illinois State Board of Elections",
                    "Official Canvass, General Primary Election, March 17, 2026 (2026GPOfficialVote.pdf, Candidate Totals)", IL.CANVASS_URL,
                    IL.made_on(cpath), mtime(cpath), sha(cpath), sum(len(s["cands"]) for s in sections.values()),
                    f"Linked as \"Candidate Totals\" on {IL.TOTALS_PAGE} (year 2026). Statewide offices, State Senator, Representative in "
                    "the General Assembly and Judge of the Appellate Court: each candidate's votes, the (Won) mark and W-I for declared "
                    "write-ins (their votes count toward a field's total); each candidate's county rows checked against the summary, and "
                    "the county rows give each district's counties. A field is a party primary with two or more printed candidates. "
                    + ("Every check holds." if not cproblems else "Did not hold: " + "; ".join(cproblems) + ".")
                    + (f" One printed candidate with write-ins beside, not fields: {', '.join(lone)}." if lone else "")))
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
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
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
    return len(general)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_il <database>")
    load(sys.argv[1])
